from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import redis_client
from app.core.tags import MASTER_TAGS
from app.ml.engine import RecommenderEngine
from app.models.user import User
from app.services.content_service import ContentService
from app.services.sync_service import ContentSyncService

logger = get_logger(__name__)


class PrecomputeWorker:
    def __init__(self):
        self.content_service = ContentService()
        self.recommender = RecommenderEngine()
        self.sync_service = ContentSyncService()

    async def warm_global_caches(self):
        logger.info("Warming global caches...")
        await asyncio.gather(
            self.content_service.get_home_data("all"),
            self.content_service.get_home_data("movie"),
            self.content_service.get_home_data("music"),
            self.content_service.get_home_data("book"),
            self.content_service.get_recommendations("all"),
            self.content_service.get_recommendations("movie"),
            self.content_service.get_recommendations("music"),
            self.content_service.get_recommendations("book"),
        )

        tags = list(MASTER_TAGS.keys())[: max(0, settings.CACHE_WARMUP_TAG_LIMIT)]
        for tag in tags:
            await self.content_service.get_discovery(tag)
            await self.recommender.get_deep_research(tag, content_type="all")

        logger.info("Global cache warmup finished tags=%s", len(tags))

    async def precompute_user_recommendations(self, limit: int | None = None):
        limit = limit or settings.CACHE_WARMUP_USER_LIMIT
        users = await User.find_all().limit(limit).to_list()
        logger.info("Precomputing recommendations for users=%s", len(users))

        for user in users:
            for content_type in ("all", "movie", "music", "book"):
                recs = await self.recommender.get_recommendation_results(
                    str(user.id),
                    content_type=content_type,
                    limit=20,
                    interest_tags=getattr(user, "interests", []),
                )
                payload = [
                    self.recommender._to_unified_content(item, reason=reason).model_dump()
                    for item, reason in recs
                ]
                await redis_client.set_cache(
                    f"user_recs:{user.id}:{content_type}",
                    payload,
                    expire=3600,
                )

        logger.info("User recommendation precompute completed")

    async def run_once(self):
        await self.warm_global_caches()
        await self.sync_service.sync_home_snapshot()
        await self.precompute_user_recommendations()
        logger.info("Precompute worker completed")


async def run_precompute_once():
    worker = PrecomputeWorker()
    await worker.run_once()
