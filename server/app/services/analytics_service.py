from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.content_keys import make_content_key
from app.models.content_meta import ContentMetadata
from app.models.interaction import Interaction
from app.models.user import User
from app.ml.vectorizer import get_vectorizer
from app.schemas.analytics import (
    NotificationItem,
    TimelineItem,
    TrackEventRequest,
    UserStats,
)

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalyticsService:
    @property
    def default_weights(self) -> Dict[str, float]:
        return {
            "view": settings.ML_EVENT_WEIGHT_VIEW,
            "open_detail": settings.ML_EVENT_WEIGHT_OPEN_DETAIL,
            "dwell_time": settings.ML_EVENT_WEIGHT_DWELL_TIME,
            "search": settings.ML_EVENT_WEIGHT_SEARCH,
            "like": settings.ML_EVENT_WEIGHT_LIKE,
            "playlist_add": settings.ML_EVENT_WEIGHT_PLAYLIST_ADD,
        }

    async def track_event(
        self,
        user_id: str,
        payload: TrackEventRequest,
        ranking_variant: str | None = None,
    ):
        weight = payload.weight
        if weight is None:
            weight = self.default_weights.get(payload.type, 0.1)

        if payload.ext_id and payload.ext_id != "app" and payload.content_type:
            try:
                content_key = make_content_key(payload.content_type, payload.ext_id)
                supports_content_key = hasattr(ContentMetadata, "content_key")
                doc = None
                if supports_content_key and content_key:
                    doc = await ContentMetadata.find_one(
                        ContentMetadata.content_key == content_key,
                    )
                if doc is None:
                    if hasattr(ContentMetadata, "type"):
                        doc = await ContentMetadata.find_one(
                            ContentMetadata.ext_id == payload.ext_id,
                            ContentMetadata.type == payload.content_type,
                        )
                    else:
                        doc = await ContentMetadata.find_one(
                            ContentMetadata.ext_id == payload.ext_id,
                        )
                title = str(payload.meta.get("title") or payload.ext_id)
                subtitle = payload.meta.get("subtitle")
                image_url = payload.meta.get("image_url")
                rating = payload.meta.get("rating") or 0.0
                genres = payload.meta.get("genres") or []
                release_date = payload.meta.get("release_date")
                try:
                    safe_rating = float(rating)
                except (TypeError, ValueError):
                    safe_rating = 0.0

                if doc is None:
                    embedding_text = f"{title} {payload.meta.get('description') or ''}"
                    vectorizer = get_vectorizer()
                    vector = await asyncio.to_thread(
                        vectorizer.get_embedding,
                        embedding_text,
                    )
                    try:
                        doc_payload = {
                            "ext_id": payload.ext_id,
                            "type": payload.content_type,
                            "title": title,
                            "subtitle": subtitle,
                            "image_url": image_url,
                            "rating": safe_rating,
                            "genres": [str(item) for item in genres if item],
                            "release_date": release_date,
                            "features_vector": vector,
                            "vector_dim": len(vector) if vector else None,
                            "vector_model": getattr(
                                vectorizer,
                                "active_model_name",
                                "unknown",
                            )
                            if vector
                            else None,
                        }
                        if supports_content_key and content_key:
                            doc_payload["content_key"] = content_key
                        await ContentMetadata(**doc_payload).insert()
                    except DuplicateKeyError:
                        logger.info(
                            "Content metadata already exists (race): ext_id=%s",
                            payload.ext_id,
                        )
                else:
                    updated = False
                    if content_key and hasattr(doc, "content_key") and doc.content_key != content_key:
                        doc.content_key = content_key
                        updated = True
                    if not doc.title and title:
                        doc.title = title
                        updated = True
                    if not doc.image_url and image_url:
                        doc.image_url = str(image_url)
                        updated = True
                    if updated:
                        await doc.save()
            except Exception as exc:
                logger.warning(
                    "Metadata sync failed ext_id=%s error=%s",
                    payload.ext_id,
                    type(exc).__name__,
                )

        meta = dict(payload.meta)
        if ranking_variant:
            meta.setdefault("ranking_variant", ranking_variant)

        interaction_payload = {
            "user_id": user_id,
            "ext_id": payload.ext_id or "app",
            "content_type": payload.content_type,
            "type": payload.type,
            "weight": weight,
            "meta": meta,
        }
        if hasattr(Interaction, "content_key") and payload.ext_id and payload.ext_id != "app":
            interaction_payload["content_key"] = make_content_key(
                payload.content_type,
                payload.ext_id,
            ) or None

        interaction = Interaction(**interaction_payload)
        await interaction.insert()

        logger.info(
            "Tracked event user=%s type=%s ext_id=%s weight=%.3f",
            user_id,
            payload.type,
            interaction.ext_id,
            weight,
        )

        return {"status": "ok"}

    async def get_timeline(self, user_id: str, limit: int = 50) -> List[TimelineItem]:
        interactions = (
            await Interaction.find(Interaction.user_id == user_id)
            .sort("-created_at")
            .limit(limit)
            .to_list()
        )
        refs = [
            getattr(item, "content_key", None)
            or make_content_key(getattr(item, "content_type", None), item.ext_id)
            or item.ext_id
            for item in interactions
            if item.ext_id and item.ext_id != "app"
        ]
        meta_map: Dict[str, ContentMetadata] = {}
        if refs:
            supports_content_key = hasattr(ContentMetadata, "content_key")
            for ref in refs:
                doc = None
                if ":" in ref:
                    ref_type, ref_ext_id = ref.split(":", 1)
                    if supports_content_key:
                        doc = await ContentMetadata.find_one(ContentMetadata.content_key == ref)
                    if doc is None:
                        if hasattr(ContentMetadata, "type"):
                            doc = await ContentMetadata.find_one(
                                ContentMetadata.ext_id == ref_ext_id,
                                ContentMetadata.type == ref_type,
                            )
                        else:
                            doc = await ContentMetadata.find_one(
                                ContentMetadata.ext_id == ref_ext_id,
                            )
                else:
                    doc = await ContentMetadata.find_one(ContentMetadata.ext_id == ref)
                if doc is None:
                    continue
                canonical = (
                    getattr(doc, "content_key", None)
                    or make_content_key(doc.type, doc.ext_id)
                    or doc.ext_id
                )
                meta_map.setdefault(ref, doc)
                meta_map.setdefault(canonical, doc)
                meta_map.setdefault(doc.ext_id, doc)

        timeline: List[TimelineItem] = []
        for item in interactions:
            ref = (
                getattr(item, "content_key", None)
                or make_content_key(getattr(item, "content_type", None), item.ext_id)
                or item.ext_id
            )
            doc = meta_map.get(ref)
            timeline.append(
                TimelineItem(
                    id=str(item.id),
                    type=item.type,
                    ext_id=item.ext_id,
                    content_type=item.content_type,
                    weight=item.weight,
                    title=(doc.title if doc else item.meta.get("title")),
                    image_url=(doc.image_url if doc else item.meta.get("image_url")),
                    created_at=item.created_at,
                    meta=item.meta or {},
                )
            )
        return timeline

    async def get_stats(self, user_id: str, days: int = 30) -> UserStats:
        cutoff = _utc_now() - timedelta(days=days)
        interactions = await Interaction.find(
            Interaction.user_id == user_id,
            Interaction.created_at >= cutoff,
        ).to_list()

        counts = Counter(item.type for item in interactions)
        total_events = len(interactions)

        views = counts.get("view", 0)
        opens = counts.get("open_detail", 0)
        likes = counts.get("like", 0)

        dwell_values = [
            item.meta.get("seconds")
            for item in interactions
            if item.type == "dwell_time" and isinstance(item.meta.get("seconds"), (int, float))
        ]
        avg_dwell = round(sum(dwell_values) / len(dwell_values), 2) if dwell_values else 0.0

        content_type_counts = Counter(
            item.content_type for item in interactions if item.content_type
        )

        ab_metrics: Dict[str, Dict[str, float]] = {}
        for variant in ("content_only", "hybrid_ml"):
            variant_events = [
                item
                for item in interactions
                if item.meta.get("ranking_variant") == variant
            ]
            if not variant_events:
                continue
            variant_counts = Counter(item.type for item in variant_events)
            variant_views = variant_counts.get("view", 0)
            variant_opens = variant_counts.get("open_detail", 0)
            variant_likes = variant_counts.get("like", 0)
            ab_metrics[variant] = {
                "events": float(len(variant_events)),
                "ctr": round(variant_opens / variant_views, 4) if variant_views > 0 else 0.0,
                "save_rate": round(variant_likes / variant_opens, 4)
                if variant_opens > 0
                else 0.0,
            }

        ctr = round(opens / views, 4) if views > 0 else 0.0
        save_rate = round(likes / opens, 4) if opens > 0 else 0.0

        return UserStats(
            total_events=total_events,
            counts_by_type=dict(counts),
            ctr=ctr,
            save_rate=save_rate,
            avg_dwell_seconds=avg_dwell,
            top_content_types=dict(content_type_counts),
            ab_metrics=ab_metrics,
        )

    async def get_notifications(self, user: User) -> List[NotificationItem]:
        stats = await self.get_stats(str(user.id), days=14)
        now = _utc_now()
        notifications: List[NotificationItem] = []

        notifications.append(
            NotificationItem(
                id="digest-weekly",
                title="Weekly Digest Ready",
                body=f"You made {stats.total_events} interactions in the last 14 days.",
                level="info",
                created_at=now,
            )
        )

        if stats.counts_by_type.get("like", 0) == 0:
            notifications.append(
                NotificationItem(
                    id="likes-empty",
                    title="Save Content You Enjoy",
                    body="Tap heart on cards to improve your recommendations.",
                    level="warning",
                    created_at=now,
                )
            )

        if user.interests:
            notifications.append(
                NotificationItem(
                    id="interests",
                    title="New Picks For Your Interests",
                    body=f"Try Deep Research for: {', '.join(user.interests[:3])}.",
                    level="success",
                    created_at=now,
                )
            )

        if stats.ctr < 0.2 and stats.counts_by_type.get("view", 0) > 10:
            notifications.append(
                NotificationItem(
                    id="ctr-tip",
                    title="Tune Your Feed",
                    body="Use advanced search filters and like more items you open.",
                    level="warning",
                    created_at=now,
                )
            )

        return notifications
