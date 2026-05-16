from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas.content import UnifiedContent, PlaylistUpdate
from app.schemas.analytics import (
    NotificationsResponse,
    TimelineItem,
    TrackEventRequest,
    UserStats,
)
from app.services.analytics_service import AnalyticsService
from app.services.library_service import LibraryService
from app.auth.dependencies import get_current_user
from app.models.content_meta import Playlist
from app.models.user import User

router = APIRouter(prefix="/actions", tags=["Actions"])
library_service = LibraryService()
analytics_service = AnalyticsService()

@router.post("/like")
async def toggle_like(content: UnifiedContent, current_user: User = Depends(get_current_user)):
    result = await library_service.toggle_like(str(current_user.id), content)
    if result.get("status") == "added":
        await analytics_service.track_event(
            str(current_user.id),
            TrackEventRequest(
                type="like",
                ext_id=content.external_id,
                content_type=content.type,
                meta={
                    "source": "toggle_like",
                    "title": content.title,
                    "subtitle": content.subtitle,
                    "image_url": content.image_url,
                    "rating": content.rating,
                    "genres": content.genres,
                    "release_date": content.release_date,
                },
            ),
            ranking_variant=current_user.ranking_variant,
        )
    return result

@router.get("/favorites", response_model=list[UnifiedContent])
async def get_favorites(type: str = None, current_user: User = Depends(get_current_user)):
    return await library_service.get_user_favorites(str(current_user.id), type)

@router.post("/playlists")
async def create_new_playlist(title: str, description: str = None, current_user: User = Depends(get_current_user)):
    if not title.strip():
        raise HTTPException(status_code=400, detail="Playlist title is required")
    return await library_service.create_playlist(str(current_user.id), title, description)

@router.get("/playlists")
async def get_my_playlists(current_user: User = Depends(get_current_user)):
    return await library_service.get_user_playlists(str(current_user.id))

@router.get("/playlists/{playlist_id}")
async def get_playlist_details(playlist_id: str, user=Depends(get_current_user)):
    payload = await library_service.get_playlist_details(str(user.id), playlist_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return payload

@router.delete("/playlists/{playlist_id}")
async def delete_playlist(playlist_id: str, current_user: User = Depends(get_current_user)):
    result = await library_service.delete_playlist(str(current_user.id), playlist_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "Playlist not found"))
    return {"message": "Deleted"}


@router.patch("/playlists/{playlist_id}")
async def update_playlist(
    playlist_id: str,
    payload: PlaylistUpdate,
    current_user: User = Depends(get_current_user),
):
    if payload.title is None and payload.description is None:
        raise HTTPException(status_code=400, detail="Nothing to update")

    updated = await library_service.update_playlist(
        str(current_user.id),
        playlist_id,
        title=payload.title,
        description=payload.description,
    )
    if isinstance(updated, dict) and updated.get("status") == "error":
        raise HTTPException(status_code=404, detail=updated["message"])
    return updated

@router.post("/playlists/{playlist_id}/add")
async def add_item_to_playlist(playlist_id: str, content: UnifiedContent, current_user: User = Depends(get_current_user)):
    playlist = await Playlist.get(playlist_id)
    if not playlist or playlist.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    result = await library_service.add_to_playlist(playlist_id, content)
    if result.get("status") == "success":
        await analytics_service.track_event(
            str(current_user.id),
            TrackEventRequest(
                type="playlist_add",
                ext_id=content.external_id,
                content_type=content.type,
                meta={
                    "playlist_id": playlist_id,
                    "title": content.title,
                    "subtitle": content.subtitle,
                    "image_url": content.image_url,
                    "rating": content.rating,
                    "genres": content.genres,
                    "release_date": content.release_date,
                },
            ),
            ranking_variant=current_user.ranking_variant,
        )
    return result

@router.delete("/playlists/{playlist_id}/remove/{content_ref}")
async def remove_item_from_playlist(
    playlist_id: str,
    content_ref: str,
    current_user: User = Depends(get_current_user),
):
    result = await library_service.remove_from_playlist(
        str(current_user.id),
        playlist_id,
        content_ref,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=403, detail="Access denied")
    return {"status": "success"}


@router.post("/event")
async def track_event(
    payload: TrackEventRequest,
    current_user: User = Depends(get_current_user),
):
    return await analytics_service.track_event(
        str(current_user.id),
        payload,
        ranking_variant=current_user.ranking_variant,
    )


@router.get("/timeline", response_model=list[TimelineItem])
async def timeline(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    return await analytics_service.get_timeline(str(current_user.id), limit=limit)


@router.get("/stats", response_model=UserStats)
async def stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
):
    return await analytics_service.get_stats(str(current_user.id), days=days)


@router.get("/notifications", response_model=NotificationsResponse)
async def notifications(current_user: User = Depends(get_current_user)):
    items = await analytics_service.get_notifications(current_user)
    return NotificationsResponse(items=items)
