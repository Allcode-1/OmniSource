import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import dependencies as deps
from app.api.routers import content as content_router
from app.schemas.content import UnifiedContent


def _item(ext_id: str, title: str, type_value: str = "movie") -> UnifiedContent:
    return UnifiedContent(
        id=f"id-{ext_id}",
        external_id=ext_id,
        type=type_value,
        title=title,
        subtitle=type_value.title(),
        image_url="https://image.tmdb.org/t/p/w500/item.jpg",
        rating=7.5,
    )


def _build_app(optional_user=None) -> FastAPI:
    app = FastAPI()
    app.include_router(content_router.router)
    if optional_user is not None:
        app.dependency_overrides[deps.get_optional_user] = lambda: optional_user
    return app


def _reset_image_cache() -> None:
    content_router._image_cache.clear()
    content_router._image_inflight.clear()
    content_router._image_cache_total_bytes = 0


def test_search_home_discover_delegate_to_service(monkeypatch) -> None:
    async def fake_search(query: str, type: str = "all"):
        assert query == "matrix"
        assert type == "movie"
        return [_item("m1", "Matrix")]

    async def fake_home(type: str = "all"):
        assert type == "book"
        return {"Featured": [_item("b1", "Book 1", type_value="book")]}

    async def fake_discover(tag: str):
        assert tag == "cyberpunk"
        return [_item("d1", "Discover")]

    monkeypatch.setattr(content_router.service, "get_unified_search", fake_search)
    monkeypatch.setattr(content_router.service, "get_home_data", fake_home)
    monkeypatch.setattr(content_router.service, "get_discovery", fake_discover)

    client = TestClient(_build_app())

    search_response = client.get("/content/search?query=matrix&type=movie")
    home_response = client.get("/content/home?type=book")
    discover_response = client.get("/content/discover?tag=cyberpunk")

    assert search_response.status_code == 200
    assert search_response.json()[0]["ext_id"] == "m1"

    assert home_response.status_code == 200
    assert home_response.json()["Featured"][0]["ext_id"] == "b1"

    assert discover_response.status_code == 200
    assert discover_response.json()[0]["ext_id"] == "d1"


def test_recommendations_auto_without_user_falls_back_to_service(monkeypatch) -> None:
    async def fake_service_recommendations(type: str = "all"):
        assert type == "music"
        return [_item("s1", "Song 1", type_value="music")]

    async def fail_ml(*args, **kwargs):
        raise AssertionError("ML branch should not run without authenticated user")

    monkeypatch.setattr(content_router.service, "get_recommendations", fake_service_recommendations)
    monkeypatch.setattr(content_router.ml_engine, "get_recommendations", fail_ml)
    client = TestClient(_build_app())

    response = client.get("/content/recommendations?type=music&mode=auto")
    assert response.status_code == 200
    assert response.json()[0]["ext_id"] == "s1"


def test_recommendations_auto_respects_user_hybrid_variant(monkeypatch) -> None:
    cached_payload = [_item("c1", "Cached").model_dump()]

    async def fake_get_cache(key: str):
        assert key == "user_recs:u1:movie"
        return cached_payload

    async def fail_ml(*args, **kwargs):
        raise AssertionError("Cache hit should skip ML call")

    monkeypatch.setattr(content_router.redis_client, "get_cache", fake_get_cache)
    monkeypatch.setattr(content_router.ml_engine, "get_recommendations", fail_ml)

    client = TestClient(
        _build_app(optional_user=SimpleNamespace(id="u1", ranking_variant="hybrid_ml")),
    )
    response = client.get("/content/recommendations?type=movie&mode=auto")
    assert response.status_code == 200
    assert response.json()[0]["ext_id"] == "c1"


def test_image_proxy_rejects_invalid_or_disallowed_urls() -> None:
    client = TestClient(_build_app())

    invalid_scheme = client.get(
        "/content/image-proxy",
        params={"url": "ftp://image.tmdb.org/t/p/w500/x.jpg"},
    )
    disallowed_host = client.get(
        "/content/image-proxy",
        params={"url": "https://evil.example.com/x.jpg"},
    )

    assert invalid_scheme.status_code == 400
    assert invalid_scheme.json()["detail"] == "Invalid image URL"

    assert disallowed_host.status_code == 400
    assert disallowed_host.json()["detail"] == "Image host is not allowed"


def test_image_proxy_returns_cached_content_without_fetch(monkeypatch) -> None:
    _reset_image_cache()
    url = "https://image.tmdb.org/t/p/w500/cached.jpg"
    payload = b"pngdata"
    content_router._image_cache[url] = (time.time() + 120, payload, "image/png", len(payload))
    content_router._image_cache_total_bytes = len(payload)

    async def fail_fetch(*args, **kwargs):
        raise AssertionError("_fetch_image should not run on cache hit")

    monkeypatch.setattr(content_router, "_fetch_image", fail_fetch)
    client = TestClient(_build_app())

    response = client.get("/content/image-proxy", params={"url": url})
    assert response.status_code == 200
    assert response.content == b"pngdata"
    assert response.headers["content-type"].startswith("image/png")


def test_image_proxy_fetches_and_caches_for_subsequent_calls(monkeypatch) -> None:
    _reset_image_cache()
    url = "https://image.tmdb.org/t/p/w500/live.jpg"
    captured = {"calls": 0}

    async def fake_fetch_image(raw_url: str):
        captured["calls"] += 1
        assert raw_url == url
        return b"jpegdata", "image/jpeg"

    monkeypatch.setattr(content_router, "_fetch_image", fake_fetch_image)
    client = TestClient(_build_app())

    first = client.get("/content/image-proxy", params={"url": url})
    second = client.get("/content/image-proxy", params={"url": url})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == b"jpegdata"
    assert second.content == b"jpegdata"
    assert captured["calls"] == 1
    assert url in content_router._image_cache


def test_image_proxy_cache_respects_total_byte_budget(monkeypatch) -> None:
    _reset_image_cache()
    original_budget = content_router._IMAGE_CACHE_MAX_TOTAL_BYTES
    try:
        content_router._IMAGE_CACHE_MAX_TOTAL_BYTES = 10
        url_a = "https://image.tmdb.org/t/p/w500/a.jpg"
        url_b = "https://image.tmdb.org/t/p/w500/b.jpg"
        fetched = {
            url_a: (b"12345678", "image/jpeg"),
            url_b: (b"abcd", "image/jpeg"),
        }

        async def fake_fetch_image(raw_url: str):
            return fetched[raw_url]

        monkeypatch.setattr(content_router, "_fetch_image", fake_fetch_image)
        client = TestClient(_build_app())

        first = client.get("/content/image-proxy", params={"url": url_a})
        second = client.get("/content/image-proxy", params={"url": url_b})

        assert first.status_code == 200
        assert second.status_code == 200
        assert content_router._image_cache_total_bytes <= 10
    finally:
        content_router._IMAGE_CACHE_MAX_TOTAL_BYTES = original_budget
