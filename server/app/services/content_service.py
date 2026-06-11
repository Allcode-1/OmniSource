import asyncio
import re
from typing import List, Dict, Any, Awaitable, Callable, TypeVar
from urllib.parse import quote_plus

import httpx
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.content_keys import make_content_key
from app.integrations.tmdb import TMDBClient
from app.integrations.google_books import GoogleBooksClient
from app.integrations.spotify import SpotifyClient
from app.ml.vector_index import vector_index
from app.ml.vectorizer import get_vectorizer
from app.models.content_meta import ContentMetadata
from app.utils.mappers import ContentMapper
from app.utils.sanitizer import ContentSanitizer
from app.schemas.content import UnifiedContent, ContentPreview
from app.core.tags import get_tag_queries
from app.core.redis import redis_client
from app.core.logging import get_logger
from app.core.metrics import metrics_registry

logger = get_logger(__name__)
_T = TypeVar("_T")

_MUSIC_FALLBACK_ITEMS = [
    {
        "_id": "music_fallback_night_drive",
        "ext_id": "fallback-night-drive",
        "type": "music",
        "title": "Night Drive",
        "subtitle": "OmniSource Picks",
        "description": "Fallback music pick for empty Spotify responses.",
        "image_url": "https://placehold.co/600x600/111827/FAF0F0/png?text=Night+Drive",
        "rating": 8.6,
        "genres": ["synth", "night", "pop"],
        "release_date": "2026-01-01",
    },
    {
        "_id": "music_fallback_pulse_radio",
        "ext_id": "fallback-pulse-radio",
        "type": "music",
        "title": "Pulse Radio",
        "subtitle": "OmniSource Picks",
        "description": "Fallback music pick for empty Spotify responses.",
        "image_url": "https://placehold.co/600x600/0F766E/FAF0F0/png?text=Pulse+Radio",
        "rating": 8.2,
        "genres": ["pop", "dance"],
        "release_date": "2026-01-08",
    },
    {
        "_id": "music_fallback_velvet_skyline",
        "ext_id": "fallback-velvet-skyline",
        "type": "music",
        "title": "Velvet Skyline",
        "subtitle": "OmniSource Picks",
        "description": "Fallback music pick for empty Spotify responses.",
        "image_url": "https://placehold.co/600x600/7C2D12/FAF0F0/png?text=Velvet+Skyline",
        "rating": 8.0,
        "genres": ["chill", "pop"],
        "release_date": "2026-01-15",
    },
    {
        "_id": "music_fallback_future_static",
        "ext_id": "fallback-future-static",
        "type": "music",
        "title": "Future Static",
        "subtitle": "OmniSource Picks",
        "description": "Fallback music pick for empty Spotify responses.",
        "image_url": "https://placehold.co/600x600/1D4ED8/FAF0F0/png?text=Future+Static",
        "rating": 7.9,
        "genres": ["electronic", "rock"],
        "release_date": "2026-02-01",
    },
    {
        "_id": "music_fallback_soft_focus",
        "ext_id": "fallback-soft-focus",
        "type": "music",
        "title": "Soft Focus",
        "subtitle": "OmniSource Picks",
        "description": "Fallback music pick for empty Spotify responses.",
        "image_url": "https://placehold.co/600x600/831843/FAF0F0/png?text=Soft+Focus",
        "rating": 7.8,
        "genres": ["chill", "ambient"],
        "release_date": "2026-02-10",
    },
    {
        "_id": "music_fallback_golden_hour",
        "ext_id": "fallback-golden-hour",
        "type": "music",
        "title": "Golden Hour",
        "subtitle": "OmniSource Picks",
        "description": "Fallback music pick for empty Spotify responses.",
        "image_url": "https://placehold.co/600x600/A16207/100E0E/png?text=Golden+Hour",
        "rating": 7.7,
        "genres": ["pop", "warm"],
        "release_date": "2026-02-17",
    },
]

class ContentService:
    def __init__(self):
        self.tmdb = TMDBClient()
        self.books = GoogleBooksClient()
        self.spotify = SpotifyClient()
        self.mapper = ContentMapper()
        self.sanitizer = ContentSanitizer()
        self._inflight_search: dict[str, asyncio.Task[list[UnifiedContent]]] = {}
        self._inflight_home: dict[str, asyncio.Task[dict[str, list[UnifiedContent]]]] = {}
        self._inflight_discovery: dict[str, asyncio.Task[list[UnifiedContent]]] = {}
        self._inflight_recommendations: dict[str, asyncio.Task[list[UnifiedContent]]] = {}
        self._background_tasks: set[asyncio.Task] = set()

    def _record_error(self, stage: str, source: str, exc: Exception) -> None:
        metrics_registry.increment_app_event(
            "content_service_errors_total",
            {
                "stage": stage,
                "source": source,
                "error": type(exc).__name__,
            },
        )
        
        if hasattr(exc, "response") and exc.response is not None:
            logger.error(
                "TMDB HTTP Error Details -> stage=%s source=%s status=%s url=%s response_body=%s",
                stage,
                source,
                exc.response.status_code,
                exc.response.url,
                exc.response.text,
            )
        else:
            logger.warning(
                "Content service error stage=%s source=%s error=%s message=%s",
                stage,
                source,
                type(exc).__name__,
                str(exc),
            )      

    def _fallback_music(self, query: str = "", limit: int = 6) -> list[UnifiedContent]:
        normalized_query = query.lower().strip()
        items = [
            UnifiedContent.model_validate(item)
            for item in _MUSIC_FALLBACK_ITEMS
        ]
        if normalized_query:
            def score(item: UnifiedContent) -> int:
                haystack = " ".join(
                    [item.title, item.subtitle or "", *item.genres],
                ).lower()
                return sum(1 for token in normalized_query.split() if token in haystack)

            ranked = sorted(items, key=lambda item: score(item), reverse=True)
            if score(ranked[0]) > 0:
                items = ranked
        return items[:limit]

    async def _run_dedup(
        self,
        key: str,
        store: dict[str, asyncio.Task[_T]],
        factory: Callable[[], Awaitable[_T]],
    ) -> _T:
        task = store.get(key)
        if task is None:
            task = asyncio.create_task(factory())
            store[key] = task
        try:
            return await task
        finally:
            if store.get(key) is task:
                store.pop(key, None)

    @staticmethod
    def _embedding_text(item: UnifiedContent) -> str:
        return " ".join(
            [
                item.title,
                item.subtitle or "",
                item.description or "",
                " ".join(item.genres or []),
                item.release_date or "",
            ],
        ).strip()

    def _schedule_catalog_ingest(self, items: list[UnifiedContent]) -> None:
        valid_items = [
            item
            for item in items
            if item.external_id and item.type in {"movie", "music", "book"}
        ]
        if not valid_items:
            return
        task = asyncio.create_task(self._persist_catalog_items(valid_items))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _persist_catalog_items(self, items: list[UnifiedContent]) -> None:
        docs_to_vectorize: list[tuple[ContentMetadata, UnifiedContent]] = []
        supports_content_key = hasattr(ContentMetadata, "content_key")
        for item in items:
            content_key = make_content_key(item.type, item.external_id)
            doc = None
            if supports_content_key and content_key:
                doc = await ContentMetadata.find_one(
                    ContentMetadata.content_key == content_key,
                )
            if doc is None:
                doc = await ContentMetadata.find_one(
                    ContentMetadata.ext_id == item.external_id,
                    ContentMetadata.type == item.type,
                )

            if doc is None:
                doc = ContentMetadata(
                    content_key=content_key or None,
                    ext_id=item.external_id,
                    type=item.type,
                    title=item.title,
                    subtitle=item.subtitle,
                    description=item.description,
                    image_url=item.image_url,
                    rating=item.rating or 0.0,
                    release_date=item.release_date,
                    genres=item.genres or [],
                    album_id=item.album_id,
                    album_title=item.album_title,
                    artist_name=item.artist_name,
                    preview_url=item.preview_url,
                    external_url=item.external_url,
                    features_vector=[],
                )
                try:
                    await doc.insert()
                except DuplicateKeyError:
                    continue
            else:
                changed = False
                for attr, value in (
                    ("content_key", content_key or None),
                    ("title", item.title),
                    ("subtitle", item.subtitle),
                    ("description", item.description),
                    ("image_url", item.image_url),
                    ("release_date", item.release_date),
                    ("album_id", item.album_id),
                    ("album_title", item.album_title),
                    ("artist_name", item.artist_name),
                    ("preview_url", item.preview_url),
                    ("external_url", item.external_url),
                ):
                    if value and getattr(doc, attr, None) != value:
                        setattr(doc, attr, value)
                        changed = True
                rating = item.rating or 0.0
                if rating and doc.rating != rating:
                    doc.rating = rating
                    changed = True
                if item.genres and doc.genres != item.genres:
                    doc.genres = item.genres
                    changed = True
                if changed:
                    await doc.save()

            if doc is not None and not doc.features_vector:
                docs_to_vectorize.append((doc, item))

        if docs_to_vectorize:
            vectorizer = get_vectorizer()
            vectors = await asyncio.to_thread(
                vectorizer.get_batch_embeddings,
                [self._embedding_text(item) for _, item in docs_to_vectorize],
            )
            for (doc, _), vector in zip(docs_to_vectorize, vectors):
                if not vector:
                    continue
                doc.features_vector = vector
                doc.vector_dim = len(vector)
                doc.vector_model = getattr(vectorizer, "active_model_name", "unknown")
                await doc.save()
            vector_index.invalidate()
        logger.info(
            "Catalog auto-ingest completed items=%s vectorized=%s",
            len(items),
            len(docs_to_vectorize),
        )

    async def get_unified_search(self, query: str, type: str = "all") -> List[UnifiedContent]:
        cache_key = f"search:{type}:{query.lower().strip()}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return [UnifiedContent(**item) for item in cached]

        async def _build() -> list[UnifiedContent]:
            tasks = []
            i_map = []

            if type in ["all", "movie"]:
                tasks.append(self.tmdb.search_movies(query))
                i_map.append("movie")

            if type in ["all", "book"]:
                tasks.append(self.books.search_books(query))
                i_map.append("book")

            if type in ["all", "music"]:
                tasks.append(self.spotify.search_tracks(query))
                i_map.append("music")

            if not tasks:
                return []

            results_raw = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for idx, raw in enumerate(results_raw):
                current_type = i_map[idx]
                if isinstance(raw, Exception):
                    self._record_error("search_fetch", current_type, raw)
                    continue
                if not isinstance(raw, dict):
                    self._record_error(
                        "search_payload",
                        current_type,
                        TypeError("Invalid payload type"),
                    )
                    continue

                if current_type == "movie":
                    for item in raw.get("results", []):
                        try:
                            results.append(self.mapper.map_tmdb(item))
                        except (KeyError, TypeError, ValueError) as exc:
                            self._record_error("search_map", "movie", exc)
                            continue
                        except Exception as exc:
                            self._record_error("search_map_unexpected", "movie", exc)
                            continue
                elif current_type == "book":
                    for item in raw.get("items", []):
                        try:
                            results.append(self.mapper.map_google_books(item))
                        except (KeyError, TypeError, ValueError) as exc:
                            self._record_error("search_map", "book", exc)
                            continue
                        except Exception as exc:
                            self._record_error("search_map_unexpected", "book", exc)
                            continue
                elif current_type == "music":
                    for item in raw.get("tracks", {}).get("items", []):
                        try:
                            results.append(self.mapper.map_spotify(item))
                        except (KeyError, TypeError, ValueError) as exc:
                            self._record_error("search_map", "music", exc)
                            continue
                        except Exception as exc:
                            self._record_error("search_map_unexpected", "music", exc)
                            continue

            valid_results = [
                r for r in results if r.external_id and r.title and self.sanitizer.is_valid(r)
            ]
            sorted_results = sorted(valid_results, key=lambda x: x.rating or 0, reverse=True)
            await redis_client.set_cache(
                cache_key,
                [r.model_dump() for r in sorted_results],
                expire=600,
            )
            self._schedule_catalog_ingest(sorted_results)
            return sorted_results

        return await self._run_dedup(cache_key, self._inflight_search, _build)

    async def get_home_data(self, type: str = "all") -> Dict[str, List[UnifiedContent]]:
        cache_key = f"home_data_v4_{type}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return {k: [UnifiedContent(**i) for i in v] for k, v in cached.items()}

        async def _build() -> dict[str, list[UnifiedContent]]:
            source_specs: dict[str, tuple[str, Callable[[], Awaitable[Any]], Callable[[Any], UnifiedContent], str]] = {
                "movie_popular": (
                    "movie",
                    self.tmdb.get_popular_movies,
                    self.mapper.map_tmdb,
                    "",
                ),
                "movie_top": (
                    "movie",
                    self.tmdb.get_top_rated_movies,
                    self.mapper.map_tmdb,
                    "",
                ),
                "movie_action": (
                    "movie",
                    lambda: self.tmdb.search_movies("Action"),
                    self.mapper.map_tmdb,
                    "",
                ),
                "music_new": (
                    "music",
                    lambda: self.spotify.search_tracks("new music"),
                    self.mapper.map_spotify,
                    "new music",
                ),
                "music_rock": (
                    "music",
                    lambda: self.spotify.search_tracks("rock"),
                    self.mapper.map_spotify,
                    "rock",
                ),
                "music_pop": (
                    "music",
                    lambda: self.spotify.search_tracks("pop"),
                    self.mapper.map_spotify,
                    "pop",
                ),
                "book_fiction": (
                    "book",
                    lambda: self.books.search_books("subject:fiction"),
                    self.mapper.map_google_books,
                    "",
                ),
                "book_thriller": (
                    "book",
                    lambda: self.books.search_books("subject:thriller"),
                    self.mapper.map_google_books,
                    "",
                ),
                "book_history": (
                    "book",
                    lambda: self.books.search_books("subject:history"),
                    self.mapper.map_google_books,
                    "",
                ),
            }

            section_sources = {
                "Trending Now": ["movie_popular", "music_new", "book_fiction"],
                "Editor's Choice": ["movie_top", "music_rock", "book_thriller"],
                "New Releases": ["music_new", "movie_popular"],
                "Action & High Energy": ["movie_action", "music_pop"],
                "Must Read Classics": ["book_fiction"],
                "Discover Something New": ["book_history", "movie_top", "music_rock"],
            }

            needed_keys: list[str] = []
            for keys in section_sources.values():
                for key in keys:
                    source_type = source_specs[key][0]
                    if type != "all" and source_type != type:
                        continue
                    if key not in needed_keys:
                        needed_keys.append(key)

            raw_by_key: dict[str, Any] = {}
            if needed_keys:
                raw_res = await asyncio.gather(
                    *(source_specs[key][1]() for key in needed_keys),
                    return_exceptions=True,
                )
                raw_by_key = dict(zip(needed_keys, raw_res))

            def wrap(data, mapper_func, type_key, fallback_query: str = ""):
                if data is None or (type != "all" and type_key != type):
                    return []
                if isinstance(data, Exception):
                    self._record_error("home_fetch", type_key, data)
                    return []
                if not isinstance(data, dict):
                    self._record_error(
                        "home_payload",
                        type_key,
                        TypeError("Invalid payload type"),
                    )
                    return []

                if type_key == "movie":
                    items = data.get("results", [])
                elif type_key == "book":
                    items = data.get("items", [])
                else:
                    tracks = data.get("tracks")
                    items = tracks.get("items", []) if isinstance(tracks, dict) else []

                mapped = []
                for item in items:
                    try:
                        mapped_item = mapper_func(item)
                        if (
                            mapped_item.external_id
                            and mapped_item.title
                            and self.sanitizer.is_valid(mapped_item)
                        ):
                            mapped.append(mapped_item)
                    except (KeyError, TypeError, ValueError) as exc:
                        self._record_error("home_map", type_key, exc)
                        continue
                    except Exception as exc:
                        self._record_error("home_map_unexpected", type_key, exc)
                        continue
                if type_key == "music" and not mapped:
                    return self._fallback_music(fallback_query, limit=15)
                return mapped[:15]

            result: dict[str, list[UnifiedContent]] = {}
            for section, keys in section_sources.items():
                section_items: list[UnifiedContent] = []
                for key in keys:
                    source_type, _, mapper_func, fallback_query = source_specs[key]
                    section_items.extend(
                        wrap(
                            raw_by_key.get(key),
                            mapper_func,
                            source_type,
                            fallback_query,
                        ),
                    )
                result[section] = self.sanitizer.get_unique(section_items, limit=20)

            filtered = {key: value for key, value in result.items() if value}
            serializable = {key: [item.model_dump() for item in value] for key, value in filtered.items()}
            await redis_client.set_cache(cache_key, serializable, expire=1800)
            return filtered

        return await self._run_dedup(cache_key, self._inflight_home, _build)

    async def get_discovery(self, tag: str, type: str = "all") -> List[UnifiedContent]:
        cache_key = f"discovery:{type}:{tag.lower().strip()}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return [UnifiedContent(**item) for item in cached]

        async def _build() -> list[UnifiedContent]:
            queries = get_tag_queries(tag)
            fetchers: list[tuple[str, Awaitable[Any]]] = []
            if type in ["all", "movie"]:
                fetchers.append(("movie", self.tmdb.search_movies(queries.tmdb_keyword)))
            if type in ["all", "book"]:
                fetchers.append(("book", self.books.search_books(f"subject:{queries.google_books_subject}")))
            if type in ["all", "music"]:
                fetchers.append(("music", self.spotify.search_tracks(f"genre:{queries.spotify_genre}")))
            if not fetchers:
                return []

            tasks = [fetcher for _, fetcher in fetchers]
            results_raw = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            for index, raw in enumerate(results_raw):
                source = fetchers[index][0]
                if isinstance(raw, Exception):
                    self._record_error("discovery_fetch", source, raw)
                    continue
                if not isinstance(raw, dict):
                    self._record_error(
                        "discovery_payload",
                        source,
                        TypeError("Invalid payload type"),
                    )
                    continue
                try:
                    if source == "movie":
                        for item in raw.get("results", []):
                            results.append(self.mapper.map_tmdb(item))
                    elif source == "book":
                        for item in raw.get("items", []):
                            results.append(self.mapper.map_google_books(item))
                    elif source == "music":
                        tracks = raw.get("tracks")
                        items = tracks.get("items", []) if isinstance(tracks, dict) else []
                        for item in items:
                            results.append(self.mapper.map_spotify(item))
                except (KeyError, TypeError, ValueError) as exc:
                    self._record_error("discovery_map", source, exc)
                    continue
                except Exception as exc:
                    self._record_error("discovery_map_unexpected", source, exc)
                    continue

            filtered = [
                item
                for item in results
                if item.external_id and item.title and self.sanitizer.is_valid(item)
            ]
            unique_items = self.sanitizer.get_unique(filtered, limit=30)
            await redis_client.set_cache(
                cache_key,
                [item.model_dump() for item in unique_items],
                expire=1200,
            )
            self._schedule_catalog_ingest(unique_items)
            return unique_items

        return await self._run_dedup(cache_key, self._inflight_discovery, _build)

    async def get_recommendations(self, type: str = "all") -> List[UnifiedContent]:
        cache_key = f"recs_v4_{type}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return [UnifiedContent(**item) for item in cached]

        async def _build() -> list[UnifiedContent]:
            results: list[UnifiedContent] = []

            def safe_map(
                items: list[Any],
                mapper: Callable[[Any], UnifiedContent],
                source: str,
            ) -> list[UnifiedContent]:
                mapped: list[UnifiedContent] = []
                for item in items:
                    try:
                        mapped.append(mapper(item))
                    except (KeyError, TypeError, ValueError) as exc:
                        self._record_error("recommendations_map", source, exc)
                        continue
                    except Exception as exc:
                        self._record_error("recommendations_map_unexpected", source, exc)
                        continue
                return mapped

            if type == "movie":
                try:
                    raw = await self.tmdb.get_top_rated_movies()
                except Exception as exc:
                    self._record_error("recommendations_fetch", "movie", exc)
                    return []
                movie_items = (raw or {}).get("results", []) if isinstance(raw, dict) else []
                results = safe_map(movie_items, self.mapper.map_tmdb, "movie")
            elif type == "music":
                try:
                    raw = await self.spotify.search_tracks("pop")
                except Exception as exc:
                    self._record_error("recommendations_fetch", "music", exc)
                    return []
                tracks = (raw or {}).get("tracks", {}) if isinstance(raw, dict) else {}
                track_items = tracks.get("items", []) if isinstance(tracks, dict) else []
                results = safe_map(track_items, self.mapper.map_spotify, "music")
                if not results:
                    results = self._fallback_music("pop", limit=10)
            elif type == "book":
                try:
                    raw = await self.books.search_books("subject:recommended")
                except Exception as exc:
                    self._record_error("recommendations_fetch", "book", exc)
                    return []
                book_items = (raw or {}).get("items", []) if isinstance(raw, dict) else []
                results = safe_map(book_items, self.mapper.map_google_books, "book")
            else:
                m_raw, s_raw, b_raw = await asyncio.gather(
                    self.tmdb.get_top_rated_movies(),
                    self.spotify.search_tracks("pop"),
                    self.books.search_books("subject:fiction"),
                    return_exceptions=True,
                )
                if isinstance(m_raw, dict):
                    results.extend(
                        safe_map(m_raw.get("results", [])[:5], self.mapper.map_tmdb, "movie"),
                    )
                elif isinstance(m_raw, Exception):
                    self._record_error("recommendations_fetch", "movie", m_raw)
                if isinstance(s_raw, dict):
                    tracks = s_raw.get("tracks", {})
                    track_items = tracks.get("items", []) if isinstance(tracks, dict) else []
                    music_results = safe_map(
                        track_items[:5],
                        self.mapper.map_spotify,
                        "music",
                    )
                    results.extend(
                        music_results if music_results else self._fallback_music("pop", limit=5),
                    )
                elif isinstance(s_raw, Exception):
                    self._record_error("recommendations_fetch", "music", s_raw)
                if isinstance(b_raw, dict):
                    results.extend(
                        safe_map(b_raw.get("items", [])[:5], self.mapper.map_google_books, "book"),
                    )
                elif isinstance(b_raw, Exception):
                    self._record_error("recommendations_fetch", "book", b_raw)

            valid_results = [item for item in results if self.sanitizer.is_valid(item)]
            if valid_results:
                await redis_client.set_cache(
                    cache_key,
                    [item.model_dump() for item in valid_results],
                    expire=600,
                )
                self._schedule_catalog_ingest(valid_results)
            return valid_results

        return await self._run_dedup(cache_key, self._inflight_recommendations, _build)

    async def get_preview(
        self,
        content_type: str,
        external_id: str,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> ContentPreview | None:
        if content_type == "movie":
            return await self._get_movie_preview(external_id, title)
        if content_type == "music":
            return await self._get_music_preview(external_id, title, subtitle)
        if content_type == "book":
            return await self._get_book_preview(external_id, title)
        return None

    async def _get_movie_preview(
        self,
        external_id: str,
        title: str | None,
    ) -> ContentPreview | None:
        try:
            movie_id = int(external_id)
        except (TypeError, ValueError):
            return None

        data = await self.tmdb.get_movie_videos(movie_id)
        videos = data.get("results", []) if isinstance(data, dict) else []
        youtube_videos = [
            item
            for item in videos
            if isinstance(item, dict)
            and item.get("site") == "YouTube"
            and item.get("key")
        ]
        if not youtube_videos:
            query = f"{title or external_id} trailer"
            youtube_id = await self._find_youtube_video_id(query)
            if youtube_id is None:
                return None
            preview_title = title or "Trailer"
            return ContentPreview(
                content_type="movie",
                external_id=external_id,
                provider="YouTube",
                preview_type="video",
                title=preview_title,
                url=f"https://www.youtube.com/watch?v={youtube_id}",
                embed_url=f"https://www.youtube.com/embed/{youtube_id}",
                external_url=f"https://www.themoviedb.org/movie/{external_id}",
                is_playable=True,
            )

        def score(item: dict) -> tuple[int, int, str]:
            video_type = str(item.get("type") or "")
            official = bool(item.get("official"))
            return (
                1 if video_type.lower() == "trailer" else 0,
                1 if official else 0,
                str(item.get("published_at") or ""),
            )

        selected = sorted(youtube_videos, key=score, reverse=True)[0]
        key = str(selected["key"])
        preview_title = str(selected.get("name") or title or "Trailer")
        return ContentPreview(
            content_type="movie",
            external_id=external_id,
            provider="YouTube",
            preview_type="video",
            title=preview_title,
            url=f"https://www.youtube.com/watch?v={key}",
            embed_url=f"https://www.youtube.com/embed/{key}",
            external_url=f"https://www.themoviedb.org/movie/{external_id}",
            is_playable=True,
        )

    async def _get_music_preview(
        self,
        external_id: str,
        title: str | None,
        subtitle: str | None,
    ) -> ContentPreview | None:
        track = await self.spotify.get_track(external_id)
        if isinstance(track, dict):
            track_title = str(track.get("name") or title or "Track preview")
            artists = [
                artist.get("name")
                for artist in track.get("artists", [])
                if isinstance(artist, dict) and artist.get("name")
            ]
            artist_text = ", ".join(artists) or subtitle or ""
            external_url = (track.get("external_urls") or {}).get("spotify")
            preview_url = track.get("preview_url")
            if preview_url:
                return ContentPreview(
                    content_type="music",
                    external_id=external_id,
                    provider="Spotify",
                    preview_type="audio",
                    title=track_title,
                    url=preview_url,
                    external_url=external_url,
                    is_playable=True,
                )
            query_text = f"{artist_text} {track_title}".strip()
            youtube_id = await self._find_youtube_video_id(query_text)
            if youtube_id:
                return ContentPreview(
                    content_type="music",
                    external_id=external_id,
                    provider="YouTube",
                    preview_type="video",
                    title=track_title,
                    url=f"https://www.youtube.com/watch?v={youtube_id}",
                    embed_url=f"https://www.youtube.com/embed/{youtube_id}",
                    external_url=external_url,
                    is_playable=True,
                )
            query = quote_plus(query_text)
            if query:
                return ContentPreview(
                    content_type="music",
                    external_id=external_id,
                    provider="YouTube",
                    preview_type="external",
                    title=track_title,
                    url=f"https://www.youtube.com/results?search_query={query}",
                    external_url=external_url,
                    is_playable=False,
                )

        query_text = " ".join(part for part in [subtitle, title] if part)
        if not query_text:
            return None
        youtube_id = await self._find_youtube_video_id(query_text)
        if youtube_id:
            return ContentPreview(
                content_type="music",
                external_id=external_id,
                provider="YouTube",
                preview_type="video",
                title=title or "Music preview",
                url=f"https://www.youtube.com/watch?v={youtube_id}",
                embed_url=f"https://www.youtube.com/embed/{youtube_id}",
                is_playable=True,
            )
        query = quote_plus(query_text)
        return ContentPreview(
            content_type="music",
            external_id=external_id,
            provider="YouTube",
            preview_type="external",
            title=title or "Music preview",
            url=f"https://www.youtube.com/results?search_query={query}",
            is_playable=False,
        )

    async def _find_youtube_video_id(self, query: str) -> str | None:
        normalized = " ".join(query.split()).strip()
        if not normalized:
            return None

        try:
            async with httpx.AsyncClient(
                proxy=settings.SPOTIFY_PROXY_URL,
                timeout=httpx.Timeout(6.0, connect=2.0, read=6.0),
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    "https://www.youtube.com/results",
                    params={"search_query": normalized},
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                            "Mobile/15E148 Safari/604.1"
                        )
                    },
                )
        except Exception as exc:
            logger.info(
                "YouTube preview lookup failed query=%s error=%s",
                normalized,
                type(exc).__name__,
            )
            return None

        if response.status_code != 200:
            logger.info(
                "YouTube preview lookup returned status=%s query=%s",
                response.status_code,
                normalized,
            )
            return None

        seen: set[str] = set()
        for video_id in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', response.text):
            if video_id in seen:
                continue
            seen.add(video_id)
            return video_id
        return None

    async def _get_book_preview(
        self,
        external_id: str,
        title: str | None,
    ) -> ContentPreview | None:
        data = await self.books.get_volume(external_id)
        if not isinstance(data, dict):
            return None
        info = data.get("volumeInfo") if isinstance(data.get("volumeInfo"), dict) else {}
        access = data.get("accessInfo") if isinstance(data.get("accessInfo"), dict) else {}
        url = (
            info.get("previewLink")
            or info.get("infoLink")
            or access.get("webReaderLink")
        )
        if not url:
            return None
        return ContentPreview(
            content_type="book",
            external_id=external_id,
            provider="Google Books",
            preview_type="external",
            title=str(info.get("title") or title or "Book preview"),
            url=str(url),
            external_url=info.get("infoLink"),
            is_playable=False,
        )

    async def close(self) -> None:
        background_tasks = list(self._background_tasks)
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(
            *background_tasks,
            self.tmdb.close(),
            self.books.close(),
            self.spotify.close(),
            return_exceptions=True,
        )
