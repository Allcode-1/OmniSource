import asyncio
import json
import time
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisService:
    def __init__(self):
        self.enabled = bool(settings.REDIS_ENABLED and settings.REDIS_URL)
        self.redis_url = settings.REDIS_URL or "redis://localhost:6379"
        self._timeout = settings.REDIS_OPERATION_TIMEOUT_SECONDS
        self._down_cooldown_seconds = 10.0
        self.client = None
        if self.enabled:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
                health_check_interval=30,
                retry_on_timeout=True,
            )
        self._is_available = True
        self._was_down_logged = False
        self._retry_after_monotonic = 0.0

    @property
    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        return "up" if self._is_available else "down"

    async def health_status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self._should_skip():
            return "down"
        return "up" if await self.ping() else "down"

    def _mark_up(self) -> None:
        self._is_available = True
        self._was_down_logged = False
        self._retry_after_monotonic = 0.0

    def _mark_down(self, message: str) -> None:
        self._is_available = False
        self._retry_after_monotonic = (
            time.monotonic() + self._down_cooldown_seconds
        )
        if not self._was_down_logged:
            logger.warning(message)
            self._was_down_logged = True

    def _should_skip(self) -> bool:
        return (not self._is_available) and (
            time.monotonic() < self._retry_after_monotonic
        )

    async def ping(self) -> bool:
        if self.client is None:
            return False
        try:
            await asyncio.wait_for(self.client.ping(), timeout=self._timeout)
            self._mark_up()
            return True
        except Exception as exc:
            self._mark_down(f"Redis ping failed: {type(exc).__name__}")
            return False

    async def get_cache(self, key: str):
        if self.client is None or self._should_skip():
            return None
        try:
            data = await asyncio.wait_for(self.client.get(key), timeout=self._timeout)
            self._mark_up()
            if data:
                logger.debug("Cache hit: %s", key)
                return json.loads(data)
            logger.debug("Cache miss: %s", key)
            return None
        except Exception:
            self._mark_down("Redis is down. Falling back to DB/API.")
            return None

    async def set_cache(self, key: str, value: Any, expire: int = 3600):
        if self.client is None or self._should_skip():
            return
        try:
            await asyncio.wait_for(
                self.client.set(key, json.dumps(value), ex=expire),
                timeout=self._timeout,
            )
            self._mark_up()
            logger.debug("Cache set: %s (ttl=%s)", key, expire)
        except Exception:
            self._mark_down(f"Failed to write cache key: {key}")

    async def delete_cache(self, key: str) -> None:
        if self.client is None or self._should_skip():
            return
        try:
            await asyncio.wait_for(self.client.delete(key), timeout=self._timeout)
            self._mark_up()
            logger.debug("Cache delete: %s", key)
        except Exception:
            self._mark_down(f"Failed to delete cache key: {key}")

    async def delete_by_prefix(self, prefix: str, limit: int | None = None) -> int:
        if self.client is None or self._should_skip():
            return 0
        deleted = 0
        pattern = f"{prefix}*"
        try:
            cursor = 0
            while True:
                cursor, keys = await asyncio.wait_for(
                    self.client.scan(cursor=cursor, match=pattern, count=100),
                    timeout=self._timeout,
                )
                if keys:
                    await asyncio.wait_for(
                        self.client.delete(*keys),
                        timeout=self._timeout,
                    )
                    deleted += len(keys)
                if cursor == 0 or (limit is not None and deleted >= limit):
                    break
            self._mark_up()
            if deleted:
                logger.debug("Cache delete prefix: %s deleted=%s", prefix, deleted)
        except Exception:
            self._mark_down(f"Failed to delete cache by prefix: {prefix}")
        return deleted

    async def close(self):
        if self.client is None:
            return
        try:
            await self.client.aclose()
        except Exception:
            pass


redis_client = RedisService()
