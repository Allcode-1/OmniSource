from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import dependencies as deps
from app.api.routers import recommendations as recommendations_router
from app.schemas.content import UnifiedContent


def _build_app(current_user) -> FastAPI:
    app = FastAPI()
    app.include_router(recommendations_router.router)
    app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return app


def test_get_my_recommendations_delegates_to_engine(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1")
    captured = {}

    async def fake_get_recommendations(
        user_id: str,
        content_type: str = "all",
        limit: int = 10,
        interest_tags=None,
    ):
        captured["user_id"] = user_id
        captured["content_type"] = content_type
        captured["limit"] = limit
        return [(SimpleNamespace(ext_id="x1"), "Because you liked movies")]

    def fake_to_unified_content(item, reason=None):
        return UnifiedContent(
            id="movie_x1",
            external_id=item.ext_id,
            type="movie",
            title="X1",
            recommendation_reason=reason,
        )

    monkeypatch.setattr(
        recommendations_router.engine,
        "get_recommendation_results",
        fake_get_recommendations,
    )
    monkeypatch.setattr(
        recommendations_router.engine,
        "_to_unified_content",
        fake_to_unified_content,
    )
    client = TestClient(_build_app(current_user))

    response = client.get("/recommendations/?type=movie&limit=3")
    assert response.status_code == 200
    assert response.json()[0]["ext_id"] == "x1"
    assert response.json()[0]["recommendation_reason"] == "Because you liked movies"
    assert captured == {
        "user_id": "u1",
        "content_type": "movie",
        "limit": 3,
    }


def test_get_my_recommendations_uses_defaults(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u2")
    captured = {}

    async def fake_get_recommendations(
        user_id: str,
        content_type: str = "all",
        limit: int = 10,
        interest_tags=None,
    ):
        captured["user_id"] = user_id
        captured["content_type"] = content_type
        captured["limit"] = limit
        return []

    monkeypatch.setattr(
        recommendations_router.engine,
        "get_recommendation_results",
        fake_get_recommendations,
    )
    client = TestClient(_build_app(current_user))

    response = client.get("/recommendations/")
    assert response.status_code == 200
    assert captured == {
        "user_id": "u2",
        "content_type": "all",
        "limit": 10,
    }


def test_get_my_recommendations_validates_limit_bounds() -> None:
    current_user = SimpleNamespace(id="u3")
    client = TestClient(_build_app(current_user))

    low_response = client.get("/recommendations/?limit=0")
    high_response = client.get("/recommendations/?limit=60")

    assert low_response.status_code == 422
    assert high_response.status_code == 422
