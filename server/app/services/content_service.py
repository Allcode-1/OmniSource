import asyncio
from typing import List, Dict, Any, Awaitable, Callable, TypeVar
from app.integrations.tmdb import TMDBClient
from app.integrations.google_books import GoogleBooksClient
from app.integrations.spotify import SpotifyClient
from app.utils.mappers import ContentMapper
from app.utils.sanitizer import ContentSanitizer
from app.schemas.content import UnifiedContent
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

    def _record_error(self, stage: str, source: str, exc: Exception) -> None:
        metrics_registry.increment_app_event(
            "content_service_errors_total",
            {
                "stage": stage,
                "source": source,
                "error": type(exc).__name__,
            },
        )
        logger.warning(
            "Content service error stage=%s source=%s error=%s",
            stage,
            source,
            type(exc).__name__,
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
            return sorted_results

        return await self._run_dedup(cache_key, self._inflight_search, _build)

    async def get_home_data(self, type: str = "all") -> Dict[str, List[UnifiedContent]]:
        cache_key = f"home_data_v4_{type}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return {k: [UnifiedContent(**i) for i in v] for k, v in cached.items()}

        async def _build() -> dict[str, list[UnifiedContent]]:
            tasks = [
                self.tmdb.get_popular_movies(),
                self.tmdb.get_top_rated_movies(),
                self.tmdb.search_movies("Action"),
                self.spotify.search_tracks("new music"),
                self.spotify.search_tracks("rock"),
                self.spotify.search_tracks("pop"),
                self.books.search_books("subject:fiction"),
                self.books.search_books("subject:thriller"),
                self.books.search_books("subject:history"),
            ]

            raw_res = await asyncio.gather(*tasks, return_exceptions=True)

            def wrap(data, mapper_func, type_key, fallback_query: str = ""):
                if type != "all" and type_key != type:
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

            result = {
                "Trending Now": wrap(raw_res[0], self.mapper.map_tmdb, "movie")
                + wrap(raw_res[3], self.mapper.map_spotify, "music", "new music")
                + wrap(raw_res[6], self.mapper.map_google_books, "book"),
                "Editor's Choice": wrap(raw_res[1], self.mapper.map_tmdb, "movie")
                + wrap(raw_res[4], self.mapper.map_spotify, "music", "rock")
                + wrap(raw_res[7], self.mapper.map_google_books, "book"),
                "New Releases": wrap(raw_res[3], self.mapper.map_spotify, "music", "new music")
                + wrap(raw_res[0], self.mapper.map_tmdb, "movie"),
                "Action & High Energy": wrap(raw_res[2], self.mapper.map_tmdb, "movie")
                + wrap(raw_res[5], self.mapper.map_spotify, "music", "pop"),
                "Must Read Classics": wrap(raw_res[6], self.mapper.map_google_books, "book"),
                "Discover Something New": wrap(raw_res[8], self.mapper.map_google_books, "book")
                + wrap(raw_res[1], self.mapper.map_tmdb, "movie")
                + wrap(raw_res[4], self.mapper.map_spotify, "music", "rock"),
            }

            filtered = {key: value for key, value in result.items() if value}
            serializable = {key: [item.model_dump() for item in value] for key, value in filtered.items()}
            await redis_client.set_cache(cache_key, serializable, expire=1800)
            return filtered

        return await self._run_dedup(cache_key, self._inflight_home, _build)

    async def get_discovery(self, tag: str) -> List[UnifiedContent]:
        cache_key = f"discovery:{tag.lower().strip()}"
        cached = await redis_client.get_cache(cache_key)
        if cached:
            return [UnifiedContent(**item) for item in cached]

        async def _build() -> list[UnifiedContent]:
            queries = get_tag_queries(tag)
            tasks = [
                self.tmdb.search_movies(queries.tmdb_keyword),
                self.books.search_books(f"subject:{queries.google_books_subject}"),
                self.spotify.search_tracks(f"genre:{queries.spotify_genre}"),
            ]
            results_raw = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            for index, raw in enumerate(results_raw):
                source = "movie" if index == 0 else "book" if index == 1 else "music"
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
                    if index == 0:
                        for item in raw.get("results", []):
                            results.append(self.mapper.map_tmdb(item))
                    elif index == 1:
                        for item in raw.get("items", []):
                            results.append(self.mapper.map_google_books(item))
                    elif index == 2:
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
            return valid_results

        return await self._run_dedup(cache_key, self._inflight_recommendations, _build)

    async def close(self) -> None:
        await asyncio.gather(
            self.tmdb.close(),
            self.books.close(),
            self.spotify.close(),
            return_exceptions=True,
        )
