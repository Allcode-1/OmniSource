from __future__ import annotations

from collections import Counter
from math import log2
from typing import Any

from beanie.operators import In

from app.core.config import settings
from app.core.content_keys import make_content_key, split_content_key
from app.core.logging import get_logger
from app.ml.engine import RecommenderEngine
from app.models.content_meta import ContentMetadata
from app.models.interaction import Interaction

logger = get_logger(__name__)


class MLEvaluationService:
    CONTENT_TYPES = ("movie", "music", "book")
    POSITIVE_EVENTS = (
        "like",
        "playlist_add",
        "preview_play",
        "external_open",
        "open_detail",
    )

    def __init__(self, engine: RecommenderEngine | None = None):
        self.engine = engine or RecommenderEngine()

    @staticmethod
    def _ratio(part: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round(part / total, 4)

    async def _count_docs(self, query: dict[str, Any] | None = None) -> int:
        if query is None:
            return await ContentMetadata.find().count()
        return await ContentMetadata.find(query).count()

    async def _catalog_report(self) -> dict[str, Any]:
        total = await self._count_docs()
        by_type = {}
        for content_type in ("movie", "music", "book"):
            type_total = await self._count_docs({"type": content_type})
            vectorized = await self._count_docs(
                {"type": content_type, "features_vector.0": {"$exists": True}},
            )
            with_genres = await self._count_docs(
                {"type": content_type, "genres.0": {"$exists": True}},
            )
            with_release = await self._count_docs(
                {
                    "type": content_type,
                    "release_date": {"$nin": [None, ""]},
                },
            )
            with_description = await self._count_docs(
                {
                    "type": content_type,
                    "description": {"$nin": [None, ""]},
                },
            )
            with_vector_metadata = await self._count_docs(
                {
                    "type": content_type,
                    "features_vector.0": {"$exists": True},
                    "vector_dim": {"$nin": [None, 0]},
                    "vector_model": {"$nin": [None, ""]},
                },
            )
            by_type[content_type] = {
                "total": type_total,
                "vectorized": vectorized,
                "vector_coverage": self._ratio(vectorized, type_total),
                "vector_metadata_coverage": self._ratio(
                    with_vector_metadata,
                    vectorized,
                ),
                "genre_coverage": self._ratio(with_genres, type_total),
                "release_date_coverage": self._ratio(with_release, type_total),
                "description_coverage": self._ratio(with_description, type_total),
            }

        vectorized_total = await self._count_docs(
            {"features_vector.0": {"$exists": True}},
        )
        return {
            "total_documents": total,
            "vectorized_documents": vectorized_total,
            "vector_coverage": self._ratio(vectorized_total, total),
            "by_type": by_type,
        }

    async def _interaction_report(self) -> dict[str, Any]:
        event_counts = {}
        for event_type in (
            "view",
            "open_detail",
            "preview_open",
            "preview_play",
            "external_open",
            "like",
            "playlist_add",
            "dwell_time",
        ):
            event_counts[event_type] = await Interaction.find(
                Interaction.type == event_type,
            ).count()

        positive = await Interaction.find(
            In(Interaction.type, list(self.POSITIVE_EVENTS)),
        ).to_list()
        users = {item.user_id for item in positive if item.user_id}
        return {
            "event_counts": event_counts,
            "positive_interactions": len(positive),
            "users_with_positive_interactions": len(users),
        }

    async def _recommendation_report(
        self,
        sample_users: int,
        limit: int,
    ) -> dict[str, Any]:
        if sample_users <= 0:
            return {
                "users_sampled": 0,
                "generated_recommendations": 0,
                "avg_recommendations_per_user": 0.0,
                "reason_coverage": 0.0,
                "type_distribution": {},
            }

        positives = await Interaction.find(
            In(Interaction.type, list(self.POSITIVE_EVENTS)),
        ).sort("-created_at").limit(max(sample_users * 10, sample_users)).to_list()

        user_ids = []
        seen = set()
        for item in positives:
            if not item.user_id or item.user_id in seen:
                continue
            seen.add(item.user_id)
            user_ids.append(item.user_id)
            if len(user_ids) >= sample_users:
                break

        reason_count = 0
        total_recs = 0
        type_counter: Counter[str] = Counter()
        recommendations_per_user = []
        for user_id in user_ids:
            recs = await self.engine.get_recommendation_results(
                user_id,
                content_type="all",
                limit=limit,
            )
            recommendations_per_user.append(len(recs))
            for item, reason in recs:
                total_recs += 1
                type_counter[item.type] += 1
                if reason:
                    reason_count += 1

        avg_recs = (
            round(sum(recommendations_per_user) / len(recommendations_per_user), 2)
            if recommendations_per_user
            else 0.0
        )
        return {
            "users_sampled": len(user_ids),
            "generated_recommendations": total_recs,
            "avg_recommendations_per_user": avg_recs,
            "reason_coverage": self._ratio(reason_count, total_recs),
            "type_distribution": dict(type_counter),
        }

    @staticmethod
    def _interaction_ref(item: Interaction) -> str:
        return (
            getattr(item, "content_key", None)
            or make_content_key(getattr(item, "content_type", None), item.ext_id)
            or item.ext_id
        )

    @staticmethod
    def _content_ref(item: ContentMetadata) -> str:
        return make_content_key(item.type, item.ext_id) or item.ext_id

    @staticmethod
    def _matches_holdout(item: ContentMetadata, holdout_ref: str) -> bool:
        item_ref = MLEvaluationService._content_ref(item)
        _, holdout_ext_id = split_content_key(holdout_ref)
        return item_ref == holdout_ref or item.ext_id == holdout_ref or (
            bool(holdout_ext_id) and item.ext_id == holdout_ext_id
        )

    def _rank_metrics(
        self,
        items: list[ContentMetadata],
        holdout_ref: str,
        limit: int,
    ) -> dict[str, float | int | None]:
        rank = None
        for index, item in enumerate(items[:limit], start=1):
            if self._matches_holdout(item, holdout_ref):
                rank = index
                break

        hit = 1 if rank is not None else 0
        return {
            "hit": hit,
            "recall": float(hit),
            "ndcg": round(1 / log2(rank + 1), 4) if rank else 0.0,
            "mrr": round(1 / rank, 4) if rank else 0.0,
            "rank": rank,
        }

    async def _content_only_candidates(
        self,
        *,
        exclude_refs: set[str],
        content_type: str,
        limit: int,
    ) -> list[ContentMetadata]:
        query_filter: dict[str, Any] = {}
        if content_type and content_type != "all":
            query_filter["type"] = content_type

        docs = (
            await ContentMetadata.find(query_filter)
            .sort("-rating")
            .limit(max(limit * 20, limit))
            .to_list()
        )
        result: list[ContentMetadata] = []
        for doc in docs:
            ref = self._content_ref(doc)
            if ref in exclude_refs or doc.ext_id in exclude_refs:
                continue
            result.append(doc)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _empty_quality_metrics() -> dict[str, Any]:
        return {
            "users_evaluated": 0,
            "hit_rate_at_k": 0.0,
            "recall_at_k": 0.0,
            "ndcg_at_k": 0.0,
            "mrr": 0.0,
            "avg_rank": 0.0,
        }

    @staticmethod
    def _aggregate_quality(rows: list[dict[str, float | int | None]]) -> dict[str, Any]:
        if not rows:
            return MLEvaluationService._empty_quality_metrics()

        ranks = [row["rank"] for row in rows if isinstance(row.get("rank"), int)]
        users = len(rows)
        hits = sum(int(row["hit"]) for row in rows)
        return {
            "users_evaluated": users,
            "hit_rate_at_k": round(hits / users, 4),
            "recall_at_k": round(sum(float(row["recall"]) for row in rows) / users, 4),
            "ndcg_at_k": round(sum(float(row["ndcg"]) for row in rows) / users, 4),
            "mrr": round(sum(float(row["mrr"]) for row in rows) / users, 4),
            "avg_rank": round(sum(ranks) / len(ranks), 2) if ranks else 0.0,
        }

    async def _offline_quality_report(
        self,
        sample_users: int,
        limit: int,
    ) -> dict[str, Any]:
        if sample_users <= 0:
            return {
                "k": limit,
                "users_considered": 0,
                "users_skipped": 0,
                "variants": {
                    "content_only": self._empty_quality_metrics(),
                    "hybrid_ml": self._empty_quality_metrics(),
                },
            }

        positives = await Interaction.find(
            In(Interaction.type, list(self.POSITIVE_EVENTS)),
        ).sort("-created_at").limit(max(sample_users * 100, 200)).to_list()

        by_user: dict[str, list[Interaction]] = {}
        for item in positives:
            if not item.user_id or not item.ext_id:
                continue
            by_user.setdefault(item.user_id, []).append(item)

        content_rows: list[dict[str, float | int | None]] = []
        hybrid_rows: list[dict[str, float | int | None]] = []
        content_rows_by_type: dict[str, list[dict[str, float | int | None]]] = {
            content_type: [] for content_type in self.CONTENT_TYPES
        }
        hybrid_rows_by_type: dict[str, list[dict[str, float | int | None]]] = {
            content_type: [] for content_type in self.CONTENT_TYPES
        }
        users_considered = 0
        users_skipped = 0

        for user_id, user_events in by_user.items():
            refs_seen: set[str] = set()
            distinct_events: list[Interaction] = []
            for item in user_events:
                ref = self._interaction_ref(item)
                if not ref or ref in refs_seen:
                    continue
                refs_seen.add(ref)
                distinct_events.append(item)

            if len(distinct_events) < settings.ML_EVAL_HOLDOUT_MIN_POSITIVES:
                users_skipped += 1
                continue

            holdout = distinct_events[0]
            holdout_ref = self._interaction_ref(holdout)
            train_refs = {
                self._interaction_ref(item)
                for item in distinct_events[1:]
                if self._interaction_ref(item)
            }
            train_ext_ids = {split_content_key(ref)[1] or ref for ref in train_refs}
            excluded_for_baseline = train_refs.union(train_ext_ids)

            users_considered += 1
            content_type = holdout.content_type or "all"
            content_only = await self._content_only_candidates(
                exclude_refs=excluded_for_baseline,
                content_type=content_type,
                limit=limit,
            )
            content_metrics = self._rank_metrics(content_only, holdout_ref, limit)
            content_rows.append(content_metrics)
            if content_type in content_rows_by_type:
                content_rows_by_type[content_type].append(content_metrics)

            hybrid = await self.engine.get_recommendation_results(
                user_id,
                content_type=content_type,
                limit=limit,
                exclude_interaction_refs={holdout_ref, holdout.ext_id},
                before_created_at=holdout.created_at,
            )
            hybrid_metrics = self._rank_metrics(
                [item for item, _ in hybrid],
                holdout_ref,
                limit,
            )
            hybrid_rows.append(hybrid_metrics)
            if content_type in hybrid_rows_by_type:
                hybrid_rows_by_type[content_type].append(hybrid_metrics)

            if users_considered >= sample_users:
                break

        return {
            "k": limit,
            "users_considered": users_considered,
            "users_skipped": users_skipped,
            "holdout_policy": "latest positive event per user; train on previous positive events",
            "variants": {
                "content_only": self._aggregate_quality(content_rows),
                "hybrid_ml": self._aggregate_quality(hybrid_rows),
            },
            "by_type": {
                content_type: {
                    "content_only": self._aggregate_quality(
                        content_rows_by_type[content_type],
                    ),
                    "hybrid_ml": self._aggregate_quality(
                        hybrid_rows_by_type[content_type],
                    ),
                }
                for content_type in self.CONTENT_TYPES
            },
        }

    async def build_report(
        self,
        sample_users: int = 25,
        recommendation_limit: int = 20,
    ) -> dict[str, Any]:
        logger.info(
            "Building ML evaluation report sample_users=%s limit=%s",
            sample_users,
            recommendation_limit,
        )
        return {
            "catalog": await self._catalog_report(),
            "interactions": await self._interaction_report(),
            "recommendations": await self._recommendation_report(
                sample_users=sample_users,
                limit=recommendation_limit,
            ),
            "offline_quality": await self._offline_quality_report(
                sample_users=sample_users,
                limit=recommendation_limit,
            ),
        }
