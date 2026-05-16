import asyncio
import time
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from typing import List
from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import redis_client
from app.services.content_service import ContentService
from app.schemas.content import UnifiedContent
from app.auth.dependencies import get_optional_user
from app.models.user import User
from app.ml.engine import RecommenderEngine

router = APIRouter(prefix="/content", tags=["content"])
service = ContentService()
ml_engine = RecommenderEngine()
logger = get_logger(__name__)

_ALLOWED_IMAGE_HOSTS = {
    "image.tmdb.org",
    "i.scdn.co",
    "books.google.com",
    "books.googleusercontent.com",
    "lh3.googleusercontent.com",
}
_IMAGE_CACHE_TTL_SECONDS = settings.IMAGE_PROXY_CACHE_TTL_SECONDS
_IMAGE_CACHE_MAX_ITEMS = settings.IMAGE_PROXY_CACHE_MAX_ITEMS
_IMAGE_MAX_BYTES = settings.IMAGE_PROXY_MAX_BYTES_PER_ITEM
_IMAGE_CACHE_MAX_TOTAL_BYTES = settings.IMAGE_PROXY_CACHE_MAX_TOTAL_BYTES
_MAX_IMAGE_REDIRECTS = settings.IMAGE_PROXY_MAX_REDIRECTS
_image_cache: dict[str, tuple[float, bytes, str, int]] = {}
_image_cache_total_bytes = 0
_image_cache_lock = asyncio.Lock()
_image_inflight: dict[str, asyncio.Task[tuple[bytes, str]]] = {}


async def _read_cached_image(url: str) -> tuple[bytes, str] | None:
    global _image_cache_total_bytes
    now = time.time()
    async with _image_cache_lock:
        payload = _image_cache.get(url)
        if payload is None:
            return None
        expires_at, content, content_type, size_bytes = payload
        if expires_at <= now:
            _image_cache.pop(url, None)
            _image_cache_total_bytes = max(0, _image_cache_total_bytes - size_bytes)
            return None
        return content, content_type


async def _write_cached_image(url: str, content: bytes, content_type: str) -> None:
    global _image_cache_total_bytes
    content_size = len(content)
    if content_size > _IMAGE_CACHE_MAX_TOTAL_BYTES:
        return

    async with _image_cache_lock:
        now = time.time()
        expired_keys = [
            key
            for key, (expires_at, _, _, _) in _image_cache.items()
            if expires_at <= now
        ]
        for key in expired_keys:
            _, _, _, old_size = _image_cache.pop(key)
            _image_cache_total_bytes = max(0, _image_cache_total_bytes - old_size)

        if url in _image_cache:
            _, _, _, existing_size = _image_cache.pop(url)
            _image_cache_total_bytes = max(0, _image_cache_total_bytes - existing_size)

        while (
            len(_image_cache) >= _IMAGE_CACHE_MAX_ITEMS
            or _image_cache_total_bytes + content_size > _IMAGE_CACHE_MAX_TOTAL_BYTES
        ) and _image_cache:
            oldest_key = min(_image_cache, key=lambda key: _image_cache[key][0])
            _, _, _, oldest_size = _image_cache.pop(oldest_key)
            _image_cache_total_bytes = max(0, _image_cache_total_bytes - oldest_size)

        _image_cache[url] = (
            time.time() + _IMAGE_CACHE_TTL_SECONDS,
            content,
            content_type,
            content_size,
        )
        _image_cache_total_bytes += content_size


def _validate_image_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise HTTPException(status_code=400, detail="Invalid image URL")
    if host not in _ALLOWED_IMAGE_HOSTS and not host.endswith(".googleusercontent.com"):
        raise HTTPException(status_code=400, detail="Image host is not allowed")
    return raw_url


async def _fetch_image(url: str) -> tuple[bytes, str]:
    current_url = _validate_image_url(url)
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            for _ in range(_MAX_IMAGE_REDIRECTS + 1):
                upstream = await client.get(
                    current_url,
                    headers={"User-Agent": "OmniSource/1.0"},
                )
                status = upstream.status_code
                if status in (301, 302, 303, 307, 308):
                    location = upstream.headers.get("location")
                    if not location:
                        raise HTTPException(status_code=502, detail="Invalid redirect response")
                    current_url = _validate_image_url(urljoin(current_url, location))
                    continue

                if status != 200:
                    logger.warning(
                        "Image proxy upstream status=%s url=%s",
                        status,
                        current_url,
                    )
                    raise HTTPException(status_code=502, detail="Unable to fetch image")

                content_type = (
                    (upstream.headers.get("content-type") or "image/jpeg")
                    .split(";")[0]
                    .strip()
                )
                if not content_type.startswith("image/"):
                    raise HTTPException(status_code=400, detail="URL does not point to an image")

                header_length = upstream.headers.get("content-length")
                if header_length and header_length.isdigit() and int(header_length) > _IMAGE_MAX_BYTES:
                    raise HTTPException(status_code=413, detail="Image is too large")

                content = upstream.content
                if len(content) > _IMAGE_MAX_BYTES:
                    raise HTTPException(status_code=413, detail="Image is too large")
                return content, content_type
            raise HTTPException(status_code=502, detail="Too many redirects")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        logger.warning("Image proxy fetch failed url=%s error=%s", url, type(exc).__name__)
        raise HTTPException(status_code=502, detail="Unable to fetch image")

@router.get("/search", response_model=List[UnifiedContent])
async def search(
    query: str = Query(..., min_length=2),
    type: str = Query("all") 
):
    return await service.get_unified_search(query, type)

@router.get("/home")
async def home(type: str = Query("all")):
    return await service.get_home_data(type)

@router.get("/discover", response_model=List[UnifiedContent])
async def discover(tag: str = Query(...)):
    return await service.get_discovery(tag)


@router.get("/image-proxy")
async def image_proxy(url: str = Query(..., min_length=8, max_length=1500)):
    _validate_image_url(url)

    cached = await _read_cached_image(url)
    if cached is not None:
        content, content_type = cached
        return Response(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    async with _image_cache_lock:
        inflight = _image_inflight.get(url)
        if inflight is None:
            inflight = asyncio.create_task(_fetch_image(url))
            _image_inflight[url] = inflight

    try:
        content, content_type = await inflight
        await _write_cached_image(url, content, content_type)
    finally:
        async with _image_cache_lock:
            if _image_inflight.get(url) is inflight:
                _image_inflight.pop(url, None)

    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )

@router.get("/trending", response_model=List[UnifiedContent])
async def trending(type: str = Query("all")):
    data = await service.get_home_data(type)
    all_items = []
    for category_list in data.values():
        all_items.extend(category_list)
    
    unique_items = {
        f"{item.type}:{item.external_id}": item
        for item in all_items
    }.values()
    result = list(unique_items)
    
    return sorted(result, key=lambda x: getattr(x, "rating", 0) or 0, reverse=True)

@router.get("/recommendations", response_model=List[UnifiedContent])
async def recommendations(
    type: str = Query("all"),
    mode: str = Query("auto"),
    current_user: User | None = Depends(get_optional_user),
):
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = (
            current_user.ranking_variant if current_user is not None else "content_only"
        )

    if resolved_mode == "hybrid_ml" and current_user is not None:
        cache_key = f"user_recs:{current_user.id}:{type}"
        cached = await redis_client.get_cache(cache_key)
        if isinstance(cached, list) and cached:
            return [UnifiedContent(**item) for item in cached]

        ml_items = await ml_engine.get_recommendations(
            str(current_user.id),
            content_type=type,
            limit=20,
        )
        if ml_items:
            payload = [
                ml_engine._to_unified_content(item).model_dump() for item in ml_items
            ]
            await redis_client.set_cache(cache_key, payload, expire=3600)
            return [UnifiedContent(**item) for item in payload]

    return await service.get_recommendations(type)
