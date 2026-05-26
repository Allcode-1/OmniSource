from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import dependencies as deps
from app.api.routers import content as content_router
from app.schemas.content import UnifiedContent


def _item(
    *,
    id_value: str,
    ext_id: str,
    title: str,
    rating: float,
    type_value: str = "movie",
) -> UnifiedContent:
    return UnifiedContent(
        id=id_value,
        external_id=ext_id,
        type=type_value,
        title=title,
        subtitle=type_value.title(),
        image_url="https://image.test/item.jpg",
        rating=rating,
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(content_router.router)
    return app


def test_trending_deduplicates_and_sorts(monkeypatch) -> None:
    async def fake_home_data(type: str = "all"):
        return {
            "sectionA": [
                _item(id_value="1", ext_id="same", title="Old", rating=5.0),
                _item(id_value="2", ext_id="high", title="High", rating=9.0),
            ],
            "sectionB": [
                _item(id_value="3", ext_id="same", title="New", rating=7.0),
            ],
        }

    monkeypatch.setattr(content_router.service, "get_home_data", fake_home_data)
    app = _build_app()
    client = TestClient(app)

    response = client.get("/content/trending?type=all")
    assert response.status_code == 200

    items = [UnifiedContent.model_validate(item) for item in response.json()]
    assert len(items) == 2
    assert len({item.external_id for item in items}) == 2
    assert [item.rating for item in items] == sorted(
        [item.rating for item in items], reverse=True
    )


def test_recommendations_uses_cache_hit_for_hybrid_ml(monkeypatch) -> None:
    cached_payload = [
        _item(id_value="1", ext_id="cached", title="Cached item", rating=8.1).model_dump()
    ]
    set_cache_called = {"value": False}

    async def fake_get_cache(key: str):
        return cached_payload

    async def fake_set_cache(*args, **kwargs):
        set_cache_called["value"] = True

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("ML engine should not be called on cache hit")

    monkeypatch.setattr(content_router.redis_client, "get_cache", fake_get_cache)
    monkeypatch.setattr(content_router.redis_client, "set_cache", fake_set_cache)
    monkeypatch.setattr(
        content_router.ml_engine,
        "get_recommendation_results",
        fail_if_called,
    )

    app = _build_app()
    app.dependency_overrides[deps.get_optional_user] = lambda: SimpleNamespace(
        id="user-1", ranking_variant="hybrid_ml"
    )
    client = TestClient(app)

    response = client.get("/content/recommendations?type=movie&mode=hybrid_ml")
    assert response.status_code == 200
    items = [UnifiedContent.model_validate(item) for item in response.json()]
    assert len(items) == 1
    assert items[0].external_id == "cached"
    assert set_cache_called["value"] is False


def test_recommendations_cache_miss_uses_ml_and_sets_cache(monkeypatch) -> None:
    set_cache_payload = {}

    async def fake_get_cache(key: str):
        return None

    async def fake_ml_recommendations(*args, **kwargs):
        return [(SimpleNamespace(), "Because you liked action movies")]

    def fake_to_unified_content(item, reason=None):
        return _item(id_value="2", ext_id="ml", title="ML item", rating=7.7)

    async def fake_set_cache(key: str, value, expire: int = 0):
        set_cache_payload["key"] = key
        set_cache_payload["value"] = value
        set_cache_payload["expire"] = expire

    async def fail_service_fallback(*args, **kwargs):
        raise AssertionError("Fallback service should not be used when ML has data")

    monkeypatch.setattr(content_router.redis_client, "get_cache", fake_get_cache)
    monkeypatch.setattr(content_router.redis_client, "set_cache", fake_set_cache)
    monkeypatch.setattr(
        content_router.ml_engine,
        "get_recommendation_results",
        fake_ml_recommendations,
    )
    monkeypatch.setattr(content_router.ml_engine, "_to_unified_content", fake_to_unified_content)
    monkeypatch.setattr(content_router.service, "get_recommendations", fail_service_fallback)

    app = _build_app()
    app.dependency_overrides[deps.get_optional_user] = lambda: SimpleNamespace(
        id="user-42", ranking_variant="hybrid_ml"
    )
    client = TestClient(app)

    response = client.get("/content/recommendations?type=movie&mode=hybrid_ml")
    assert response.status_code == 200
    items = [UnifiedContent.model_validate(item) for item in response.json()]
    assert len(items) == 1
    assert items[0].external_id == "ml"
    assert "user_recs:user-42:movie" in set_cache_payload["key"]
    assert set_cache_payload["expire"] == 3600


def test_recommendations_falls_back_to_content_service_when_ml_empty(monkeypatch) -> None:
    fallback_items = [_item(id_value="9", ext_id="fallback", title="Fallback", rating=6.0)]

    async def fake_get_cache(key: str):
        return None

    async def fake_ml_recommendations(*args, **kwargs):
        return []

    async def fake_service_recommendations(type: str = "all"):
        return fallback_items

    monkeypatch.setattr(content_router.redis_client, "get_cache", fake_get_cache)
    monkeypatch.setattr(
        content_router.ml_engine,
        "get_recommendation_results",
        fake_ml_recommendations,
    )
    monkeypatch.setattr(
        content_router.service, "get_recommendations", fake_service_recommendations
    )

    app = _build_app()
    app.dependency_overrides[deps.get_optional_user] = lambda: SimpleNamespace(
        id="user-2", ranking_variant="hybrid_ml"
    )
    client = TestClient(app)

    response = client.get("/content/recommendations?type=movie&mode=hybrid_ml")
    assert response.status_code == 200
    items = [UnifiedContent.model_validate(item) for item in response.json()]
    assert len(items) == 1
    assert items[0].external_id == "fallback"
