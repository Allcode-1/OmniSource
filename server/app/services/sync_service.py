from __future__ import annotations

import asyncio
from typing import Iterable

from app.core.logging import get_logger
from app.core.content_keys import make_content_key
from app.ml.vectorizer import get_vectorizer
from app.models.content_meta import ContentMetadata
from app.schemas.content import UnifiedContent
from app.services.content_service import ContentService

logger = get_logger(__name__)


class ContentSyncService:
    def __init__(self):
        self.content_service = ContentService()

    async def persist_items(self, items: Iterable[UnifiedContent]) -> int:
        item_list = list(items)
        count = 0
        supports_content_key = hasattr(ContentMetadata, "content_key")
        docs_to_vectorize: list[tuple[ContentMetadata, UnifiedContent]] = []
        for item in item_list:
            if not item.external_id:
                continue

            content_key = make_content_key(item.type, item.external_id)
            doc = None
            if supports_content_key:
                doc = await ContentMetadata.find_one(
                    ContentMetadata.content_key == content_key,
                )
            if doc is None:
                if hasattr(ContentMetadata, "type"):
                    doc = await ContentMetadata.find_one(
                        ContentMetadata.ext_id == item.external_id,
                        ContentMetadata.type == item.type,
                    )
                else:
                    doc = await ContentMetadata.find_one(
                        ContentMetadata.ext_id == item.external_id,
                    )
            if doc:
                if supports_content_key and hasattr(doc, "content_key"):
                    doc.content_key = content_key
                doc.type = item.type
                doc.title = item.title
                doc.subtitle = item.subtitle
                doc.description = item.description
                doc.image_url = item.image_url
                doc.rating = item.rating or 0.0
                doc.release_date = item.release_date
                doc.genres = item.genres
                await doc.save()
            else:
                payload = {
                    "ext_id": item.external_id,
                    "type": item.type,
                    "title": item.title,
                    "subtitle": item.subtitle,
                    "description": item.description,
                    "image_url": item.image_url,
                    "rating": item.rating or 0.0,
                    "release_date": item.release_date,
                    "genres": item.genres,
                    "features_vector": [],
                }
                if supports_content_key:
                    payload["content_key"] = content_key
                doc = ContentMetadata(**payload)
                await doc.insert()
            if doc is not None and not doc.features_vector:
                docs_to_vectorize.append((doc, item))
            count += 1

        if docs_to_vectorize:
            vectorizer = get_vectorizer()
            texts = [
                " ".join(
                    [
                        item.title,
                        item.subtitle or "",
                        item.description or "",
                        " ".join(item.genres or []),
                        item.release_date or "",
                    ],
                )
                for _, item in docs_to_vectorize
            ]
            vectors = await asyncio.to_thread(vectorizer.get_batch_embeddings, texts)
            for (doc, _), vector in zip(docs_to_vectorize, vectors):
                if not vector:
                    continue
                doc.features_vector = vector
                doc.vector_dim = len(vector)
                doc.vector_model = getattr(vectorizer, "active_model_name", "unknown")
                await doc.save()
        return count

    async def sync_home_snapshot(self) -> int:
        total = 0
        for content_type in ("all", "movie", "music", "book"):
            data = await self.content_service.get_home_data(content_type)
            for section in data.values():
                total += await self.persist_items(section)

        logger.info("Background sync completed. persisted_items=%s", total)
        return total
