import time

import pytest
from fastapi import HTTPException

from app.api.routers import content as content_router


class _FakeResponse:
    def __init__(
        self, status_code: int, content: bytes = b"", headers=None, text: str = ""
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.text = text


class _FakeAsyncClient:
    def __init__(self, response_or_exc):
        self._response_or_exc = response_or_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        if isinstance(self._response_or_exc, Exception):
            raise self._response_or_exc
        return self._response_or_exc


class _SequencedAsyncClient:
    def __init__(self, responses):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, *args, **kwargs):
        response_or_exc = self._responses[url]
        if isinstance(response_or_exc, Exception):
            raise response_or_exc
        return response_or_exc


@pytest.mark.asyncio
async def test_read_cached_image_removes_expired_entries() -> None:
    content_router._image_cache.clear()
    content_router._image_cache_total_bytes = 0
    url = "https://image.tmdb.org/t/p/w500/old.jpg"
    content_router._image_cache[url] = (time.time() - 10, b"x", "image/jpeg", 1)
    content_router._image_cache_total_bytes = 1

    result = await content_router._read_cached_image(url)
    assert result is None
    assert url not in content_router._image_cache
    assert content_router._image_cache_total_bytes == 0


@pytest.mark.asyncio
async def test_write_cached_image_eviction_when_cache_is_full(monkeypatch) -> None:
    content_router._image_cache.clear()
    content_router._image_cache_total_bytes = 0
    monkeypatch.setattr(content_router, "_IMAGE_CACHE_MAX_ITEMS", 1)

    await content_router._write_cached_image("url-1", b"a", "image/jpeg")
    await content_router._write_cached_image("url-2", b"b", "image/png")

    assert "url-1" not in content_router._image_cache
    assert "url-2" in content_router._image_cache


@pytest.mark.asyncio
async def test_fetch_image_raises_502_on_network_error(monkeypatch) -> None:
    monkeypatch.setattr(
        content_router.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(RuntimeError("boom")),
    )

    with pytest.raises(HTTPException) as error:
        await content_router._fetch_image("https://image.tmdb.org/t/p/w500/x.jpg")
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_fetch_image_uses_tmdb_fallback_after_direct_failure(monkeypatch) -> None:
    source_url = "https://image.tmdb.org/t/p/w500/x.jpg"
    fallback_url = content_router._tmdb_fallback_url(source_url)
    assert fallback_url is not None

    responses = {
        source_url: RuntimeError("tmdb cdn unavailable"),
        fallback_url: _FakeResponse(
            200,
            content=b"fallback-image",
            headers={"content-type": "image/jpeg"},
        ),
    }
    monkeypatch.setattr(
        content_router.httpx,
        "AsyncClient",
        lambda **kwargs: _SequencedAsyncClient(responses),
    )

    content, media_type = await content_router._fetch_image(source_url)

    assert content == b"fallback-image"
    assert media_type == "image/jpeg"


def test_tmdb_fallback_is_internal_only() -> None:
    fallback_url = content_router._tmdb_fallback_url(
        "https://image.tmdb.org/t/p/w500/x.jpg",
    )
    assert fallback_url is not None

    with pytest.raises(HTTPException) as error:
        content_router._validate_image_url(fallback_url)
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_image_raises_502_on_non_200_status(monkeypatch) -> None:
    monkeypatch.setattr(
        content_router.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(_FakeResponse(404, text="not found")),
    )

    with pytest.raises(HTTPException) as error:
        await content_router._fetch_image("https://image.tmdb.org/t/p/w500/x.jpg")
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_fetch_image_raises_400_for_non_image_content_type(monkeypatch) -> None:
    response = _FakeResponse(
        200, content=b"{}", headers={"content-type": "application/json"}
    )
    monkeypatch.setattr(
        content_router.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(response),
    )

    with pytest.raises(HTTPException) as error:
        await content_router._fetch_image("https://image.tmdb.org/t/p/w500/x.jpg")
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_image_returns_content_and_media_type(monkeypatch) -> None:
    response = _FakeResponse(
        200,
        content=b"image-bytes",
        headers={"content-type": "image/webp; charset=binary"},
    )
    monkeypatch.setattr(
        content_router.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(response),
    )

    content, media_type = await content_router._fetch_image(
        "https://image.tmdb.org/t/p/w500/x.jpg",
    )
    assert content == b"image-bytes"
    assert media_type == "image/webp"
