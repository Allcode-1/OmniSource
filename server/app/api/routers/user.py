from fastapi import APIRouter, Depends, HTTPException, status
from beanie.exceptions import RevisionIdWasChanged
from pymongo.errors import DuplicateKeyError
from app.models.user import User
from app.models.interaction import Interaction
from app.models.content_meta import Playlist
from app.schemas.user import (
    OnboardingComplete,
    RankingVariantUpdate,
    UserRead,
    UserUpdate,
)
from app.auth.dependencies import get_current_user
from app.core.logging import get_logger
from app.core.redis import redis_client

router = APIRouter(prefix="/user", tags=["user"])
logger = get_logger(__name__)

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/update", response_model=UserRead)
async def update_user(data: UserUpdate, current_user: User = Depends(get_current_user)):
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return current_user

    for key, value in update_dict.items():
        setattr(current_user, key, value)

    try:
        await current_user.save()
    except DuplicateKeyError as exc:
        logger.warning(
            "User update conflict (duplicate key): user=%s fields=%s",
            current_user.id,
            list(update_dict.keys()),
        )
        raise HTTPException(status_code=409, detail="Username is already taken") from exc
    except RevisionIdWasChanged as exc:
        if isinstance(exc.__cause__, DuplicateKeyError):
            logger.warning(
                "User update conflict (duplicate key via revision wrapper): user=%s fields=%s",
                current_user.id,
                list(update_dict.keys()),
            )
            raise HTTPException(
                status_code=409,
                detail="Username is already taken",
            ) from exc
        logger.warning(
            "User update revision conflict: user=%s fields=%s",
            current_user.id,
            list(update_dict.keys()),
        )
        raise HTTPException(
            status_code=409,
            detail="Profile changed in another session. Please retry.",
        ) from exc

    logger.info("User updated id=%s fields=%s", current_user.id, list(update_dict.keys()))
    return current_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(current_user: User = Depends(get_current_user)):
    # 1. delete all likes and interactions of user
    await Interaction.find(Interaction.user_id == str(current_user.id)).delete()
    
    # 2. delete all playlists of user
    await Playlist.find(Playlist.user_id == str(current_user.id)).delete()
    
    # 3. delete user itself
    await current_user.delete()
    logger.info("User deleted id=%s", current_user.id)
    
    return None

@router.post("/complete-onboarding", response_model=UserRead)
async def complete_onboarding(
    data: OnboardingComplete, 
    current_user: User = Depends(get_current_user)
):
    current_user.interests = data.interests
    current_user.is_onboarding_completed = True
    await current_user.save()
    await redis_client.delete_by_prefix(f"user_recs:{current_user.id}:")
    logger.info("Onboarding completed user=%s interests=%s", current_user.id, len(data.interests))
    return current_user

@router.get("/tags")
async def get_available_tags():
    from app.core.tags import MASTER_TAGS 
    return list(MASTER_TAGS.keys())


@router.get("/ranking-variant")
async def get_ranking_variant(current_user: User = Depends(get_current_user)):
    return {"ranking_variant": current_user.ranking_variant}


@router.patch("/ranking-variant")
async def update_ranking_variant(
    payload: RankingVariantUpdate,
    current_user: User = Depends(get_current_user),
):
    current_user.ranking_variant = payload.ranking_variant
    await current_user.save()
    await redis_client.delete_by_prefix(f"user_recs:{current_user.id}:")
    logger.info(
        "Ranking variant updated user=%s variant=%s",
        current_user.id,
        payload.ranking_variant,
    )
    return {"ranking_variant": current_user.ranking_variant}
