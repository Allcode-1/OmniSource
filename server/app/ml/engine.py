import asyncio
from collections import Counter
from datetime import datetime
from typing import Optional, List
from app.models.interaction import Interaction
from app.models.content_meta import ContentMetadata
from app.core.config import settings
from app.core.content_keys import make_content_key, split_content_key
from app.ml.similarity import SimilarityManager
from app.ml.vectorizer import get_vectorizer
from app.ml.vector_index import vector_index
from app.schemas.content import UnifiedContent
from app.core.redis import redis_client
from app.services.content_service import ContentService
from beanie.operators import In
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)


class RecommenderEngine:
    MIN_DEEP_VECTOR_CANDIDATES = 25
    MAX_RECOMMENDATION_CANDIDATES = 450
    MAX_DEEP_RESEARCH_CANDIDATES = 600
    CONTENT_TYPES = ("movie", "music", "book")
    ALL_TYPE_QUOTAS = {
        "movie": 0.34,
        "music": 0.34,
        "book": 0.32,
    }

    def __init__(self):
        self.similarity = SimilarityManager()
        self.content_service = ContentService()

    @property
    def event_weights(self) -> dict[str, float]:
        return {
            "view": settings.ML_EVENT_WEIGHT_VIEW,
            "open_detail": settings.ML_EVENT_WEIGHT_OPEN_DETAIL,
            "dwell_time": settings.ML_EVENT_WEIGHT_DWELL_TIME,
            "preview_open": settings.ML_EVENT_WEIGHT_PREVIEW_OPEN,
            "preview_play": settings.ML_EVENT_WEIGHT_PREVIEW_PLAY,
            "external_open": settings.ML_EVENT_WEIGHT_EXTERNAL_OPEN,
            "like": settings.ML_EVENT_WEIGHT_LIKE,
            "playlist_add": settings.ML_EVENT_WEIGHT_PLAYLIST_ADD,
        }

    @staticmethod
    def _to_unified_content(
        item: ContentMetadata,
        reason: str | None = None,
    ) -> UnifiedContent:
        return UnifiedContent(
            id=f"{item.type}_{item.ext_id}",
            external_id=item.ext_id,
            type=item.type,
            title=item.title,
            subtitle=item.subtitle or item.type.capitalize(),
            description=getattr(item, "description", None),
            image_url=item.image_url,
            rating=item.rating or 0.0,
            genres=item.genres or [],
            release_date=item.release_date,
            recommendation_reason=reason,
            album_id=getattr(item, "album_id", None),
            album_title=getattr(item, "album_title", None),
            artist_name=getattr(item, "artist_name", None),
            preview_url=getattr(item, "preview_url", None),
            external_url=getattr(item, "external_url", None),
        )

    @staticmethod
    def _type_label(content_type: str) -> str:
        return {
            "movie": "movie",
            "music": "track",
            "book": "book",
        }.get(content_type, "pick")

    @staticmethod
    def _clean_tags(tags: Optional[List[str]]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for tag in tags or []:
            value = tag.strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _normalized_genres(item: ContentMetadata) -> set[str]:
        return {
            genre.strip().lower()
            for genre in (item.genres or [])
            if genre and genre.strip()
        }

    @staticmethod
    def _normalized_text(value: object) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _music_identity(self, item: ContentMetadata) -> tuple[str, str]:
        artist = self._normalized_text(
            getattr(item, "artist_name", None) or getattr(item, "subtitle", None)
        )
        album = self._normalized_text(
            getattr(item, "album_id", None) or getattr(item, "album_title", None)
        )
        return artist, album

    def _build_reason(
        self,
        item: ContentMetadata,
        profile_genres: Counter[str],
        profile_titles: list[str],
        interest_tags: Optional[List[str]] = None,
        profile_artists: Counter[str] | None = None,
    ) -> str:
        if item.type == "music" and profile_artists:
            artist, _ = self._music_identity(item)
            if artist and profile_artists.get(artist, 0) > 0:
                display_artist = getattr(item, "artist_name", None) or item.subtitle
                if display_artist:
                    return f"More from {display_artist}"

        item_genres = self._normalized_genres(item)
        shared_genres = [
            genre
            for genre, _ in profile_genres.most_common()
            if genre in item_genres
        ]
        label = self._type_label(item.type)
        if shared_genres:
            return f"Because you like {shared_genres[0]} {label}s"
        if profile_titles:
            return f"Similar to {profile_titles[0]}"
        clean_tags = self._clean_tags(interest_tags)
        if clean_tags:
            return f"Because you selected {clean_tags[0]}"
        if item.rating and item.rating >= 8:
            return f"Highly rated {label}"
        return f"Recommended {label} for you"

    def _diversify_results(
        self,
        scored_results: list[tuple[float, ContentMetadata, str]],
        limit: int,
        content_type: Optional[str],
    ) -> list[tuple[ContentMetadata, str]]:
        if content_type and content_type != "all":
            return self._take_diverse(scored_results, limit, max_per_bucket=4)

        selected: list[tuple[float, ContentMetadata, str]] = []
        selected_refs: set[str] = set()
        by_type: dict[str, list[tuple[float, ContentMetadata, str]]] = {
            content_type: [] for content_type in self.CONTENT_TYPES
        }
        for row in scored_results:
            by_type.setdefault(row[1].type, []).append(row)

        quotas = self._all_type_quotas(limit)
        for current_type in self.CONTENT_TYPES:
            rows = by_type.get(current_type, [])
            if not rows:
                continue
            for row in self._take_diverse_rows(
                rows,
                quotas.get(current_type, 0),
                max_per_bucket=3,
            ):
                ref = self._doc_ref(row[1])
                if ref in selected_refs:
                    continue
                selected_refs.add(ref)
                selected.append(row)

        if len(selected) < limit:
            for row in self._take_diverse_rows(
                scored_results,
                limit,
                max_per_bucket=4,
            ):
                ref = self._doc_ref(row[1])
                if ref in selected_refs:
                    continue
                selected_refs.add(ref)
                selected.append(row)
                if len(selected) >= limit:
                    break

        selected.sort(key=lambda row: row[0], reverse=True)
        return [(item, reason) for _, item, reason in selected[:limit]]

    def _all_type_quotas(self, limit: int) -> dict[str, int]:
        remaining = max(limit, 0)
        quotas: dict[str, int] = {}
        for current_type in self.CONTENT_TYPES[:-1]:
            quota = min(remaining, max(1, round(limit * self.ALL_TYPE_QUOTAS[current_type])))
            quotas[current_type] = quota
            remaining -= quota
        quotas[self.CONTENT_TYPES[-1]] = max(0, remaining)
        return quotas

    def _take_diverse(
        self,
        rows: list[tuple[float, ContentMetadata, str]],
        limit: int,
        *,
        max_per_bucket: int,
    ) -> list[tuple[ContentMetadata, str]]:
        return [
            (item, reason)
            for _, item, reason in self._take_diverse_rows(
                rows,
                limit,
                max_per_bucket=max_per_bucket,
            )
        ]

    def _take_diverse_rows(
        self,
        rows: list[tuple[float, ContentMetadata, str]],
        limit: int,
        *,
        max_per_bucket: int,
    ) -> list[tuple[float, ContentMetadata, str]]:
        if limit <= 0:
            return []
        bucket_counts: Counter[str] = Counter()
        selected_rows: list[tuple[float, ContentMetadata, str]] = []
        deferred: list[tuple[float, ContentMetadata, str]] = []

        for row in rows:
            if len(selected_rows) >= limit:
                break
            bucket = self._diversity_bucket(row[1])
            if bucket_counts[bucket] >= max_per_bucket:
                deferred.append(row)
                continue
            selected_rows.append(row)
            bucket_counts[bucket] += 1

        for row in deferred:
            if len(selected_rows) >= limit:
                break
            selected_rows.append(row)

        return selected_rows[:limit]

    def _diversity_bucket(self, item: ContentMetadata) -> str:
        if item.type == "music":
            artist, album = self._music_identity(item)
            return f"music:{album or artist or item.ext_id}"
        genres = sorted(self._normalized_genres(item))
        if genres:
            return f"{item.type}:{genres[0]}"
        return f"{item.type}:{item.ext_id}"

    @staticmethod
    def _doc_ref(item: ContentMetadata) -> str:
        return (
            getattr(item, "content_key", None)
            or make_content_key(item.type, item.ext_id)
            or item.ext_id
        )

    def _candidate_limit(self, limit: int) -> int:
        multiplier = max(20, settings.ML_VECTOR_SEARCH_MULTIPLIER)
        return min(
            max(limit * multiplier, 250),
            self.MAX_RECOMMENDATION_CANDIDATES,
        )

    def _candidate_types(self, content_type: Optional[str]) -> list[str]:
        if content_type and content_type != "all":
            return [content_type]
        return list(self.CONTENT_TYPES)

    def _per_type_candidate_limit(
        self,
        content_type: Optional[str],
        candidate_limit: int,
    ) -> int:
        if content_type and content_type != "all":
            return candidate_limit
        return max(80, candidate_limit // len(self.CONTENT_TYPES))

    async def _candidate_scores(
        self,
        query_vector: list[float],
        target_dim: int,
        content_type: Optional[str],
        candidate_limit: int,
        exclude_refs: set[str] | None = None,
    ) -> list[tuple[ContentMetadata, float]]:
        if settings.ML_VECTOR_INDEX_ENABLED:
            return await self._candidate_scores_from_index(
                query_vector,
                content_type,
                candidate_limit,
                exclude_refs=exclude_refs,
            )
        return await self._candidate_scores_from_mongo(
            query_vector,
            target_dim,
            content_type,
            candidate_limit,
            exclude_refs=exclude_refs,
        )

    async def _candidate_scores_from_index(
        self,
        query_vector: list[float],
        content_type: Optional[str],
        candidate_limit: int,
        exclude_refs: set[str] | None = None,
    ) -> list[tuple[ContentMetadata, float]]:
        results: list[tuple[ContentMetadata, float]] = []
        per_type_limit = self._per_type_candidate_limit(content_type, candidate_limit)
        for current_type in self._candidate_types(content_type):
            matches = await vector_index.search(
                query_vector,
                content_type=current_type,
                limit=per_type_limit,
                exclude_refs=exclude_refs,
            )
            results.extend((match.item, match.score) for match in matches)
        return results

    async def _candidate_scores_from_mongo(
        self,
        query_vector: list[float],
        target_dim: int,
        content_type: Optional[str],
        candidate_limit: int,
        exclude_refs: set[str] | None = None,
    ) -> list[tuple[ContentMetadata, float]]:
        results: list[tuple[ContentMetadata, float]] = []
        excluded = exclude_refs or set()
        per_type_limit = self._per_type_candidate_limit(content_type, candidate_limit)

        for current_type in self._candidate_types(content_type):
            query_filter: dict[str, object] = {
                "features_vector.0": {"$exists": True},
                "vector_dim": target_dim,
                "type": current_type,
            }
            candidates = await ContentMetadata.find(query_filter).limit(per_type_limit).to_list()
            for item in candidates:
                item_ref = self._doc_ref(item)
                if item_ref in excluded or item.ext_id in excluded:
                    continue
                if not item.features_vector or len(item.features_vector) != target_dim:
                    continue
                similarity_score = self.similarity.calculate_cosine_similarity(
                    query_vector,
                    item.features_vector,
                )
                results.append((item, similarity_score))

        return results

    @staticmethod
    def _interest_score(
        similarity_score: float,
        rating_score: float,
        tag_overlap: int,
    ) -> float:
        return (
            similarity_score * settings.ML_INTEREST_SIMILARITY_WEIGHT
            + rating_score * settings.ML_INTEREST_RATING_WEIGHT
            + tag_overlap * settings.ML_INTEREST_TAG_WEIGHT
        )

    @staticmethod
    def _hybrid_score(
        similarity_score: float,
        rating_score: float,
        genre_overlap: int,
    ) -> float:
        return (
            similarity_score * settings.ML_HYBRID_SIMILARITY_WEIGHT
            + rating_score * settings.ML_HYBRID_RATING_WEIGHT
            + min(genre_overlap, 3) * settings.ML_HYBRID_GENRE_WEIGHT
        )

    async def _recommend_from_interests(
        self,
        content_type: Optional[str],
        limit: int,
        interest_tags: Optional[List[str]],
    ) -> list[tuple[ContentMetadata, str]]:
        clean_tags = self._clean_tags(interest_tags)[:5]
        if not clean_tags:
            return []

        tag_vectors = []
        for tag in clean_tags:
            vector = await asyncio.to_thread(get_vectorizer().get_embedding, tag)
            if vector:
                tag_vectors.append(np.array(vector))

        if not tag_vectors:
            return []

        vector_dims: Counter[int] = Counter(len(vector) for vector in tag_vectors)
        target_dim = vector_dims.most_common(1)[0][0]
        compatible_vectors = [
            vector for vector in tag_vectors if vector.shape[0] == target_dim
        ]
        if not compatible_vectors:
            return []

        profile_vector = np.mean(compatible_vectors, axis=0).tolist()
        candidate_limit = self._candidate_limit(limit)
        candidate_scores = await self._candidate_scores(
            profile_vector,
            target_dim,
            content_type,
            candidate_limit,
        )

        interest_counter: Counter[str] = Counter(clean_tags)
        scored_results: list[tuple[float, ContentMetadata, str]] = []
        for item, similarity_score in candidate_scores:
            if similarity_score <= 0:
                continue
            item_genres = self._normalized_genres(item)
            tag_overlap = len(item_genres.intersection(clean_tags))
            rating_score = max(0.0, min((item.rating or 0.0) / 10.0, 1.0))
            score = self._interest_score(
                similarity_score,
                rating_score,
                tag_overlap,
            )
            scored_results.append(
                (
                    score,
                    item,
                    self._build_reason(item, interest_counter, [], clean_tags),
                )
            )

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return self._diversify_results(scored_results, limit, content_type)

    async def get_recommendation_results(
        self,
        user_id: str,
        content_type: Optional[str] = None,
        limit: int = 10,
        interest_tags: Optional[List[str]] = None,
        exclude_interaction_refs: Optional[set[str]] = None,
        before_created_at: datetime | None = None,
    ) -> list[tuple[ContentMetadata, str]]:
        logger.info(
            "Building recommendations: user_id=%s type=%s limit=%s",
            user_id,
            content_type,
            limit,
        )

        interactions = await Interaction.find(
            Interaction.user_id == user_id,
            In(Interaction.type, list(self.event_weights.keys())),
        ).to_list()
        if before_created_at is not None:
            interactions = [
                interaction
                for interaction in interactions
                if getattr(interaction, "created_at", None) is not None
                and interaction.created_at < before_created_at
            ]

        if not interactions:
            interest_results = await self._recommend_from_interests(
                content_type=content_type,
                limit=limit,
                interest_tags=interest_tags,
            )
            if interest_results:
                logger.info(
                    "No interactions found for user=%s. Returning interest_based_count=%s",
                    user_id,
                    len(interest_results),
                )
                return interest_results

            query = ContentMetadata.find()
            if content_type and content_type != "all":
                query = query.find(ContentMetadata.type == content_type)

            fallback = await query.limit(limit).to_list()
            logger.info(
                "No interactions found for user=%s. Returning fallback_count=%s",
                user_id,
                len(fallback),
            )
            return [
                (
                    item,
                    self._build_reason(
                        item,
                        Counter(self._clean_tags(interest_tags)),
                        [],
                        interest_tags,
                    ),
                )
                for item in fallback
            ]

        excluded_interaction_refs = exclude_interaction_refs or set()
        interaction_weight_by_ref: dict[str, float] = {}
        for interaction in interactions:
            if not interaction.ext_id or interaction.ext_id == "app":
                continue
            content_ref = (
                getattr(interaction, "content_key", None)
                or make_content_key(getattr(interaction, "content_type", None), interaction.ext_id)
                or interaction.ext_id
            )
            if not content_ref:
                continue
            if (
                content_ref in excluded_interaction_refs
                or interaction.ext_id in excluded_interaction_refs
            ):
                continue
            base_weight = self.event_weights.get(interaction.type, 0.1)
            final_weight = float(interaction.weight or base_weight)
            interaction_weight_by_ref[content_ref] = (
                interaction_weight_by_ref.get(content_ref, 0.0) + final_weight
            )

        if not interaction_weight_by_ref:
            logger.info("No vectorizable interactions for user=%s", user_id)
            return await self._recommend_from_interests(
                content_type=content_type,
                limit=limit,
                interest_tags=interest_tags,
            )

        supports_content_key = hasattr(ContentMetadata, "content_key")
        interaction_refs = list(interaction_weight_by_ref.keys())
        if supports_content_key:
            interaction_or_filters: list[dict] = []
            keyed_refs = [ref for ref in interaction_refs if ":" in ref]
            legacy_refs = [ref for ref in interaction_refs if ":" not in ref]
            if keyed_refs:
                interaction_or_filters.append({"content_key": {"$in": keyed_refs}})
            if legacy_refs:
                interaction_or_filters.append({"ext_id": {"$in": legacy_refs}})
            for ref in interaction_refs:
                ref_type, ref_ext_id = split_content_key(ref)
                if ref_type and ref_ext_id:
                    interaction_or_filters.append({"type": ref_type, "ext_id": ref_ext_id})
            if not interaction_or_filters:
                logger.info("No metadata refs to build profile for user=%s", user_id)
                return await self._recommend_from_interests(
                    content_type=content_type,
                    limit=limit,
                    interest_tags=interest_tags,
                )
            interaction_docs = await ContentMetadata.find({"$or": interaction_or_filters}).to_list()
        else:
            ref_ext_ids: list[str] = []
            for ref in interaction_refs:
                ref_type, ref_ext_id = split_content_key(ref)
                ref_ext_ids.append(ref_ext_id if ref_type and ref_ext_id else ref)
            if not ref_ext_ids:
                logger.info("No metadata refs to build profile for user=%s", user_id)
                return await self._recommend_from_interests(
                    content_type=content_type,
                    limit=limit,
                    interest_tags=interest_tags,
                )
            interaction_docs = await ContentMetadata.find(
                In(ContentMetadata.ext_id, list(dict.fromkeys(ref_ext_ids))),
            ).to_list()

        weighted_vectors = []
        vector_dims: Counter[int] = Counter()
        profile_genres: Counter[str] = Counter()
        profile_artists: Counter[str] = Counter()
        profile_albums: Counter[str] = Counter()
        profile_titles: list[str] = []
        for doc in interaction_docs:
            if not doc.features_vector:
                continue
            doc_ref = (
                getattr(doc, "content_key", None)
                or make_content_key(doc.type, doc.ext_id)
                or doc.ext_id
            )
            weight = interaction_weight_by_ref.get(
                doc_ref,
                interaction_weight_by_ref.get(doc.ext_id, 0.0),
            )
            if weight <= 0:
                continue
            vector_dims[len(doc.features_vector)] += 1
            weighted_vectors.append((np.array(doc.features_vector), weight))
            for genre in self._normalized_genres(doc):
                profile_genres[genre] += weight
            if doc.type == "music":
                artist, album = self._music_identity(doc)
                if artist:
                    profile_artists[artist] += weight
                if album:
                    profile_albums[album] += weight
            if doc.title and len(profile_titles) < 3:
                profile_titles.append(doc.title)

        if not weighted_vectors:
            logger.info("No vectors in interaction docs for user=%s", user_id)
            return await self._recommend_from_interests(
                content_type=content_type,
                limit=limit,
                interest_tags=interest_tags,
            )

        target_dim = vector_dims.most_common(1)[0][0]
        total_weight = 0.0
        compatible_weighted_vectors = []
        skipped_history_mismatch = 0
        for vector, weight in weighted_vectors:
            if vector.shape[0] != target_dim:
                skipped_history_mismatch += 1
                continue
            compatible_weighted_vectors.append(vector * weight)
            total_weight += weight

        if not compatible_weighted_vectors or total_weight == 0:
            logger.info("No vectors in interaction docs for user=%s", user_id)
            return await self._recommend_from_interests(
                content_type=content_type,
                limit=limit,
                interest_tags=interest_tags,
            )

        user_profile_vector = (
            np.sum(compatible_weighted_vectors, axis=0) / total_weight
        ).tolist()

        candidate_limit = self._candidate_limit(limit)

        seen_refs = set(interaction_weight_by_ref.keys())
        scored_results: list[tuple[float, ContentMetadata, str]] = []
        skipped_candidates_mismatch = 0
        search_mode = "vector_index" if settings.ML_VECTOR_INDEX_ENABLED else "mongo_scan"
        candidate_scores = await self._candidate_scores(
            user_profile_vector,
            target_dim,
            content_type,
            candidate_limit,
            exclude_refs=seen_refs,
        )

        for item, similarity_score in candidate_scores:
            item_ref = (
                getattr(item, "content_key", None)
                or make_content_key(item.type, item.ext_id)
                or item.ext_id
            )
            if item_ref in seen_refs or item.ext_id in seen_refs:
                continue
            if not settings.ML_VECTOR_INDEX_ENABLED and len(item.features_vector) != target_dim:
                skipped_candidates_mismatch += 1
                continue

            rating_score = max(0.0, min((item.rating or 0.0) / 10.0, 1.0))
            genre_overlap = len(
                self._normalized_genres(item).intersection(profile_genres.keys())
            )
            hybrid_score = self._hybrid_score(
                similarity_score,
                rating_score,
                genre_overlap,
            )
            if item.type == "music":
                artist, album = self._music_identity(item)
                if artist and artist in profile_artists:
                    hybrid_score += min(profile_artists[artist], 3.0) * 0.035
                if album and album in profile_albums:
                    hybrid_score += min(profile_albums[album], 2.0) * 0.02
            scored_results.append(
                (
                    hybrid_score,
                    item,
                    self._build_reason(
                        item,
                        profile_genres,
                        profile_titles,
                        interest_tags,
                        profile_artists=profile_artists,
                    ),
                )
            )

        scored_results.sort(key=lambda x: x[0], reverse=True)

        logger.info(
            "ML filtering completed: user_id=%s events=%s mode=%s candidates=%s scored=%s returned=%s target_dim=%s skipped_history_mismatch=%s skipped_candidates_mismatch=%s",
            user_id,
            len(interactions),
            search_mode,
            len(candidate_scores),
            len(scored_results),
            min(limit, len(scored_results)),
            target_dim,
            skipped_history_mismatch,
            skipped_candidates_mismatch,
        )
        return self._diversify_results(scored_results, limit, content_type)

    async def get_recommendations(
        self,
        user_id: str,
        content_type: Optional[str] = None,
        limit: int = 10,
    ):
        results = await self.get_recommendation_results(
            user_id,
            content_type=content_type,
            limit=limit,
        )
        return [item for item, _ in results]

    async def get_deep_research(
        self,
        tag: str,
        content_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[UnifiedContent]:
        normalized_tag = tag.strip().lower()
        resolved_type = content_type if content_type and content_type != "all" else "all"
        cache_key = f"deep_research:{resolved_type}:{limit}:{normalized_tag}"
        cached = await redis_client.get_cache(cache_key)
        if isinstance(cached, list):
            return [UnifiedContent.model_validate(item) for item in cached]

        logger.info(
            "Deep research started: tag=%s type=%s limit=%s",
            tag,
            content_type,
            limit,
        )

        def _filter_discovery(items: List[UnifiedContent]) -> List[UnifiedContent]:
            if content_type and content_type != "all":
                return [item for item in items if item.type == content_type]
            return items

        async def _return_discovery(reason: str) -> List[UnifiedContent]:
            logger.info(
                "Using discovery fallback for tag=%s reason=%s type=%s",
                tag,
                reason,
                content_type,
            )
            fallback = _filter_discovery(
                await self.content_service.get_discovery(tag, resolved_type)
            )
            result = fallback[:limit]
            await redis_client.set_cache(
                cache_key,
                [item.model_dump() for item in result],
                expire=900,
            )
            return result

        tag_vector = await asyncio.to_thread(get_vectorizer().get_embedding, tag)
        if not tag_vector:
            logger.warning("Tag vector is empty for tag=%s", tag)
            return await _return_discovery("empty_tag_vector")
        tag_dim = len(tag_vector)

        query_filter: dict[str, object] = {
            "features_vector.0": {"$exists": True},
            "vector_dim": tag_dim,
        }
        if content_type and content_type != "all":
            query_filter["type"] = content_type
        candidates = (
            await ContentMetadata.find(query_filter)
            .limit(self.MAX_DEEP_RESEARCH_CANDIDATES)
            .to_list()
        )
        compatible_candidates = [
            item
            for item in candidates
            if item.features_vector and len(item.features_vector) == tag_dim
        ]

        if len(compatible_candidates) < self.MIN_DEEP_VECTOR_CANDIDATES:
            return await _return_discovery(
                f"small_vector_pool_{len(compatible_candidates)}"
            )

        scored_results = []
        for item in compatible_candidates:
            if not item.features_vector:
                continue

            score = self.similarity.calculate_cosine_similarity(tag_vector, item.features_vector)
            scored_results.append((score, item))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        filtered = [item for score, item in scored_results if score > 0]

        if not filtered:
            return await _return_discovery("no_positive_scores")

        result = [self._to_unified_content(item) for item in filtered[:limit]]
        if len(result) < limit:
            # Fill the tail with tag-based discovery to avoid undersized result sets.
            discovery = _filter_discovery(
                await self.content_service.get_discovery(tag, resolved_type)
            )
            merged: dict[str, UnifiedContent] = {
                f"{item.type}:{item.external_id}": item for item in result
            }
            for item in discovery:
                key = f"{item.type}:{item.external_id}"
                if key in merged:
                    continue
                merged[key] = item
                if len(merged) >= limit:
                    break
            result = list(merged.values())[:limit]

        await redis_client.set_cache(
            cache_key,
            [item.model_dump() for item in result],
            expire=900,
        )
        logger.info(
            "Deep research filtering completed: tag=%s candidates=%s compatible_candidates=%s matched=%s returned=%s",
            tag,
            len(candidates),
            len(compatible_candidates),
            len(filtered),
            len(result),
        )
        return result

    async def close(self) -> None:
        await self.content_service.close()
