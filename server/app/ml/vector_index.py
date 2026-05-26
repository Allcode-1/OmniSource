from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from app.core.config import settings
from app.core.content_keys import make_content_key
from app.core.logging import get_logger
from app.models.content_meta import ContentMetadata

logger = get_logger(__name__)


@dataclass
class VectorSearchMatch:
    item: ContentMetadata
    score: float


@dataclass
class _VectorIndexSnapshot:
    items: list[ContentMetadata]
    matrix: np.ndarray
    refs: list[str]
    dim: int
    built_at: float


class InMemoryVectorIndex:
    """Small exact vector index for local/demo deployments.

    It keeps normalized vectors in RAM and scores candidates with a single
    matrix multiplication. This is still exact search, but it avoids repeatedly
    pulling and looping over Mongo documents on every recommendation request.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, _VectorIndexSnapshot] = {}

    def invalidate(self) -> None:
        self._snapshots.clear()

    async def _build_snapshot(self, content_type: str) -> _VectorIndexSnapshot:
        query_filter: dict[str, object] = {"features_vector.0": {"$exists": True}}
        if content_type != "all":
            query_filter["type"] = content_type

        query = ContentMetadata.find(query_filter).sort("-rating")
        if settings.ML_VECTOR_INDEX_MAX_ITEMS > 0:
            query = query.limit(settings.ML_VECTOR_INDEX_MAX_ITEMS)
        docs = await query.to_list()

        dims: dict[int, int] = {}
        for doc in docs:
            if doc.features_vector:
                dims[len(doc.features_vector)] = dims.get(len(doc.features_vector), 0) + 1

        if not dims:
            return _VectorIndexSnapshot([], np.empty((0, 0)), [], 0, time.monotonic())

        target_dim = max(dims.items(), key=lambda item: item[1])[0]
        items: list[ContentMetadata] = []
        vectors: list[np.ndarray] = []
        refs: list[str] = []

        for doc in docs:
            vector = doc.features_vector or []
            if len(vector) != target_dim:
                continue
            arr = np.array(vector, dtype=float)
            norm = np.linalg.norm(arr)
            if norm <= 0:
                continue
            items.append(doc)
            vectors.append(arr / norm)
            refs.append(make_content_key(doc.type, doc.ext_id) or doc.ext_id)

        matrix = np.vstack(vectors) if vectors else np.empty((0, target_dim))
        snapshot = _VectorIndexSnapshot(
            items=items,
            matrix=matrix,
            refs=refs,
            dim=target_dim,
            built_at=time.monotonic(),
        )
        logger.info(
            "Vector index built type=%s items=%s dim=%s",
            content_type,
            len(snapshot.items),
            snapshot.dim,
        )
        return snapshot

    async def _snapshot(self, content_type: str) -> _VectorIndexSnapshot:
        normalized_type = content_type if content_type in {"movie", "music", "book"} else "all"
        snapshot = self._snapshots.get(normalized_type)
        now = time.monotonic()
        if (
            snapshot is None
            or now - snapshot.built_at > settings.ML_VECTOR_INDEX_TTL_SECONDS
        ):
            snapshot = await self._build_snapshot(normalized_type)
            self._snapshots[normalized_type] = snapshot
        return snapshot

    async def search(
        self,
        query_vector: Iterable[float],
        *,
        content_type: str = "all",
        limit: int = 100,
        exclude_refs: set[str] | None = None,
    ) -> list[VectorSearchMatch]:
        vector = np.array(list(query_vector), dtype=float)
        if vector.size == 0:
            return []

        snapshot = await self._snapshot(content_type)
        if snapshot.dim == 0 or snapshot.matrix.size == 0:
            return []
        if vector.shape[0] != snapshot.dim:
            logger.info(
                "Vector index dim mismatch query_dim=%s index_dim=%s type=%s",
                vector.shape[0],
                snapshot.dim,
                content_type,
            )
            return []

        norm = np.linalg.norm(vector)
        if norm <= 0:
            return []
        scores = snapshot.matrix @ (vector / norm)
        requested = min(max(limit, 1), len(snapshot.items))
        candidate_count = min(max(requested * 2, requested), len(snapshot.items))
        ranked_indexes = np.argpartition(scores, -candidate_count)[-candidate_count:]
        ranked_indexes = ranked_indexes[np.argsort(scores[ranked_indexes])[::-1]]

        excluded = exclude_refs or set()
        matches: list[VectorSearchMatch] = []
        for index in ranked_indexes:
            item = snapshot.items[int(index)]
            ref = snapshot.refs[int(index)]
            if ref in excluded or item.ext_id in excluded:
                continue
            matches.append(VectorSearchMatch(item=item, score=float(scores[int(index)])))
            if len(matches) >= requested:
                break
        return matches


vector_index = InMemoryVectorIndex()
