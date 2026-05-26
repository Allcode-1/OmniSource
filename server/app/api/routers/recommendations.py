from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.ml.engine import RecommenderEngine
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/recommendations", tags=["ML Recommendations"])
engine = RecommenderEngine()

@router.get("/")
async def get_my_recommendations(
    type: Optional[str] = Query("all"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    results = await engine.get_recommendation_results(
        str(current_user.id),
        content_type=type,
        limit=limit,
        interest_tags=getattr(current_user, "interests", []),
    )
    return [
        engine._to_unified_content(item, reason=reason)
        for item, reason in results
    ]
