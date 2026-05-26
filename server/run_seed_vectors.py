import argparse
import asyncio
from dataclasses import dataclass
from typing import Iterable

from app.core.database import init_db
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis_client
from app.core.tags import MASTER_TAGS
from app.ml.vectorizer import get_vectorizer
from app.models.content_meta import ContentMetadata
from app.schemas.content import UnifiedContent
from app.services.sync_service import ContentSyncService
from app.utils.sanitizer import ContentSanitizer

configure_logging()
logger = get_logger(__name__)


@dataclass(frozen=True)
class SeedPlan:
    pages: int
    tag_limit: int
    movie_years: list[int]


_EXTRA_MOVIE_QUERIES = [
    "indie",
    "arthouse",
    "cult",
    "documentary",
    "animation",
    "family",
    "coming of age",
    "survival",
    "heist",
    "martial arts",
    "spy",
    "road trip",
    "time travel",
    "space opera",
    "dystopian",
    "supernatural",
    "detective",
    "biography",
    "sports",
    "musical",
]

_EXTRA_BOOK_QUERIES = [
    "subject:literary fiction",
    "subject:young adult",
    "subject:science fiction",
    "subject:business",
    "subject:psychology",
    "subject:technology",
    "subject:art",
    "subject:music",
    "subject:travel",
    "subject:health",
    "subject:poetry",
    "subject:philosophy",
    "subject:politics",
    "subject:science",
    "subject:cooking",
    "subject:education",
    "intitle:award winning fiction",
    "intitle:bestseller",
    "inauthor:asimov",
    "inauthor:agatha christie",
]

_EXTRA_MUSIC_QUERIES = [
    "genre:indie",
    "genre:alternative",
    "genre:electronic",
    "genre:house",
    "genre:techno",
    "genre:ambient",
    "genre:metal",
    "genre:punk",
    "genre:soul",
    "genre:funk",
    "genre:rnb",
    "genre:folk",
    "genre:latin",
    "genre:reggae",
    "genre:blues",
    "genre:instrumental",
    "new releases",
    "editorial picks",
    "soundtrack",
    "viral hits",
]

_TMDB_GENRE_IDS = {
    "action": 28,
    "adventure": 12,
    "animation": 16,
    "comedy": 35,
    "crime": 80,
    "drama": 18,
    "fantasy": 14,
    "history": 36,
    "horror": 27,
    "music": 10402,
    "mystery": 9648,
    "romance": 10749,
    "sci-fi": 878,
    "thriller": 53,
    "war": 10752,
    "western": 37,
}


async def _init_db_with_retries(attempts: int = 4) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            return
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            delay_seconds = min(5 * attempt, 20)
            logger.warning(
                "Mongo init failed attempt=%s/%s retry_in=%ss error=%s",
                attempt,
                attempts,
                delay_seconds,
                type(exc).__name__,
            )
            await asyncio.sleep(delay_seconds)
    if last_error is not None:
        raise last_error


def _embedding_text(doc: ContentMetadata) -> str:
    parts = [
        doc.title or "",
        doc.subtitle or "",
        getattr(doc, "description", None) or "",
        " ".join(doc.genres or []),
        doc.type or "",
        doc.release_date or "",
    ]
    return " ".join(part for part in parts if part).strip()


def _filter_items(
    items: Iterable[UnifiedContent],
    content_type: str,
) -> list[UnifiedContent]:
    if content_type == "all":
        return list(items)
    return [item for item in items if item.type == content_type]


def _unique_terms(terms: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        value = " ".join(term.strip().split())
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _build_seed_plan(args: argparse.Namespace) -> SeedPlan:
    if args.demo:
        pages = max(args.pages, 8)
        tag_limit = max(args.tag_limit, 120)
    else:
        pages = args.pages
        tag_limit = args.tag_limit

    current_year = 2026
    first_year = max(1900, args.year_from)
    last_year = min(current_year + 1, args.year_to)
    step = max(1, args.year_step)
    years = list(range(last_year, first_year - 1, -step))
    return SeedPlan(pages=max(1, pages), tag_limit=tag_limit, movie_years=years)


def _tag_terms() -> tuple[list[str], list[str], list[str]]:
    movie_terms = []
    book_terms = []
    music_terms = []
    for tag, mapping in MASTER_TAGS.items():
        movie_terms.extend([tag, mapping.tmdb_keyword])
        book_terms.append(f"subject:{mapping.google_books_subject}")
        music_terms.extend([mapping.spotify_genre, f"genre:{mapping.spotify_genre}"])
    return (
        _unique_terms([*movie_terms, *_EXTRA_MOVIE_QUERIES]),
        _unique_terms([*book_terms, *_EXTRA_BOOK_QUERIES]),
        _unique_terms([*music_terms, *_EXTRA_MUSIC_QUERIES]),
    )


def _extract_items(payload, source: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    if source == "movie":
        raw = payload.get("results", [])
    elif source == "book":
        raw = payload.get("items", [])
    else:
        tracks = payload.get("tracks")
        raw = tracks.get("items", []) if isinstance(tracks, dict) else []
    return raw if isinstance(raw, list) else []


async def _gather_limited(calls, concurrency: int):
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run(call):
        async with semaphore:
            try:
                return await call()
            except Exception as exc:
                logger.warning("Seed fetch failed error=%s", type(exc).__name__)
                return exc

    return await asyncio.gather(*(run(call) for call in calls), return_exceptions=False)


async def _metadata_count(content_type: str) -> int:
    query = ContentMetadata.find()
    if content_type != "all":
        query = query.find(ContentMetadata.type == content_type)
    return await query.count()


async def _seed_metadata(
    sync_service: ContentSyncService,
    seed_home: bool,
    plan: SeedPlan,
    content_type: str,
    concurrency: int,
    seed_tags: bool,
    expanded_seed: bool,
) -> int:
    persisted = 0
    sanitizer = ContentSanitizer()

    if seed_home:
        home_types = ["all", "movie", "music", "book"]
        for current_type in home_types:
            home_data = await sync_service.content_service.get_home_data(current_type)
            for section_items in home_data.values():
                filtered = _filter_items(section_items, content_type)
                if not filtered:
                    continue
                persisted += await sync_service.persist_items(filtered)
        logger.info("Seeded home snapshot metadata count=%s", persisted)

    if seed_tags and plan.tag_limit > 0:
        tags = list(MASTER_TAGS.keys())[:plan.tag_limit]
        for idx, tag in enumerate(tags, start=1):
            discovery = await sync_service.content_service.get_discovery(tag, content_type)
            filtered = _filter_items(discovery, content_type)
            if filtered:
                persisted += await sync_service.persist_items(filtered)
            if idx % 5 == 0 or idx == len(tags):
                logger.info("Seeded tags progress=%s/%s persisted=%s", idx, len(tags), persisted)

    if expanded_seed:
        expanded = await _seed_expanded_provider_queries(
            sync_service=sync_service,
            content_type=content_type,
            plan=plan,
            concurrency=concurrency,
            sanitizer=sanitizer,
        )
        persisted += expanded

    return persisted


async def _seed_expanded_provider_queries(
    sync_service: ContentSyncService,
    content_type: str,
    plan: SeedPlan,
    concurrency: int,
    sanitizer: ContentSanitizer,
) -> int:
    service = sync_service.content_service
    movie_terms, book_terms, music_terms = _tag_terms()
    persisted = 0

    if content_type in ("all", "movie"):
        persisted += await _seed_movies(
            sync_service,
            movie_terms=movie_terms[: plan.tag_limit + len(_EXTRA_MOVIE_QUERIES)],
            years=plan.movie_years,
            pages=plan.pages,
            concurrency=concurrency,
            sanitizer=sanitizer,
        )

    if content_type in ("all", "book"):
        persisted += await _seed_books(
            sync_service,
            book_terms=book_terms[: plan.tag_limit + len(_EXTRA_BOOK_QUERIES)],
            pages=plan.pages,
            concurrency=concurrency,
            sanitizer=sanitizer,
        )

    if content_type in ("all", "music"):
        persisted += await _seed_music(
            sync_service,
            music_terms=music_terms[: plan.tag_limit + len(_EXTRA_MUSIC_QUERIES)],
            pages=plan.pages,
            concurrency=concurrency,
            sanitizer=sanitizer,
        )

    await service.close()
    return persisted


async def _seed_movies(
    sync_service: ContentSyncService,
    movie_terms: list[str],
    years: list[int],
    pages: int,
    concurrency: int,
    sanitizer: ContentSanitizer,
) -> int:
    service = sync_service.content_service
    calls = []
    for page in range(1, pages + 1):
        calls.extend(
            [
                lambda page=page: service.tmdb.get_popular_movies(page=page),
                lambda page=page: service.tmdb.get_top_rated_movies(page=page),
            ]
        )
    for term in movie_terms:
        for page in range(1, pages + 1):
            calls.append(lambda term=term, page=page: service.tmdb.search_movies(term, page=page))
    for year in years:
        for genre_id in _TMDB_GENRE_IDS.values():
            calls.append(
                lambda year=year, genre_id=genre_id: service.tmdb.discover_movies(
                    year=year,
                    genre_id=genre_id,
                    sort_by="vote_average.desc",
                )
            )

    persisted = 0
    for batch_index in range(0, len(calls), concurrency * 4):
        batch_calls = calls[batch_index : batch_index + concurrency * 4]
        payloads = await _gather_limited(batch_calls, concurrency)
        items: list[UnifiedContent] = []
        for payload in payloads:
            for raw in _extract_items(payload, "movie"):
                try:
                    item = service.mapper.map_tmdb(raw)
                except Exception:
                    continue
                if item.external_id and item.title and sanitizer.is_valid(item):
                    items.append(item)
        unique_items = sanitizer.get_unique(items, limit=len(items))
        persisted += await sync_service.persist_items(unique_items)
        if persisted and persisted % 250 == 0:
            logger.info("Seeded movie expanded persisted=%s", persisted)

    logger.info("Seeded movie expanded count=%s calls=%s", persisted, len(calls))
    return persisted


async def _seed_books(
    sync_service: ContentSyncService,
    book_terms: list[str],
    pages: int,
    concurrency: int,
    sanitizer: ContentSanitizer,
) -> int:
    service = sync_service.content_service
    calls = []
    for term in book_terms:
        for page in range(pages):
            calls.append(
                lambda term=term, page=page: service.books.search_books(
                    term,
                    start_index=page * 40,
                    max_results=40,
                )
            )

    persisted = 0
    for batch_index in range(0, len(calls), concurrency * 4):
        batch_calls = calls[batch_index : batch_index + concurrency * 4]
        payloads = await _gather_limited(batch_calls, concurrency)
        items: list[UnifiedContent] = []
        for payload in payloads:
            for raw in _extract_items(payload, "book"):
                try:
                    item = service.mapper.map_google_books(raw)
                except Exception:
                    continue
                if item.external_id and item.title and sanitizer.is_valid(item):
                    items.append(item)
        unique_items = sanitizer.get_unique(items, limit=len(items))
        persisted += await sync_service.persist_items(unique_items)

    logger.info("Seeded book expanded count=%s calls=%s", persisted, len(calls))
    return persisted


async def _seed_music(
    sync_service: ContentSyncService,
    music_terms: list[str],
    pages: int,
    concurrency: int,
    sanitizer: ContentSanitizer,
) -> int:
    service = sync_service.content_service
    calls = []
    for term in music_terms:
        for page in range(pages):
            calls.append(
                lambda term=term, page=page: service.spotify.search_tracks(
                    term,
                    offset=page * 50,
                    limit=50,
                )
            )

    persisted = 0
    for batch_index in range(0, len(calls), concurrency * 4):
        batch_calls = calls[batch_index : batch_index + concurrency * 4]
        payloads = await _gather_limited(batch_calls, concurrency)
        items: list[UnifiedContent] = []
        for payload in payloads:
            for raw in _extract_items(payload, "music"):
                try:
                    item = service.mapper.map_spotify(raw)
                except Exception:
                    continue
                if item.external_id and item.title and sanitizer.is_valid(item):
                    items.append(item)
        unique_items = sanitizer.get_unique(items, limit=len(items))
        persisted += await sync_service.persist_items(unique_items)

    logger.info("Seeded music expanded count=%s calls=%s", persisted, len(calls))
    return persisted


def _build_query_filter(content_type: str, refresh_all: bool) -> dict[str, object]:
    query_filter: dict[str, object] = {}
    if not refresh_all:
        query_filter["$or"] = [
            {"features_vector.0": {"$exists": False}},
            {"vector_dim": {"$in": [None, 0]}},
            {"vector_model": {"$in": [None, ""]}},
        ]
    if content_type != "all":
        query_filter["type"] = content_type
    return query_filter


async def _backfill_vectors(
    content_type: str,
    refresh_all: bool,
    batch_size: int,
    max_docs: int,
    semantic_vectors: bool,
) -> tuple[int, int]:
    vectorizer = get_vectorizer()
    if not semantic_vectors:
        vectorizer.use_hash_fallback()
    await asyncio.to_thread(vectorizer.get_embedding, "vectorizer warmup")

    updated = 0
    scanned = 0
    last_id = None

    while True:
        if max_docs > 0 and scanned >= max_docs:
            break

        query_filter = _build_query_filter(content_type, refresh_all)
        if last_id is not None:
            query_filter["_id"] = {"$gt": last_id}

        batch = (
            await ContentMetadata.find(query_filter)
            .sort("+_id")
            .limit(batch_size)
            .to_list()
        )
        if not batch:
            break

        docs_with_text: list[tuple[ContentMetadata, str]] = []
        for doc in batch:
            if max_docs > 0 and scanned >= max_docs:
                break

            last_id = doc.id
            scanned += 1
            text = _embedding_text(doc)
            if not text:
                continue
            docs_with_text.append((doc, text))

        if not docs_with_text:
            continue

        vectors = await asyncio.to_thread(
            vectorizer.get_batch_embeddings,
            [text for _, text in docs_with_text],
        )
        for doc, vector in zip((doc for doc, _ in docs_with_text), vectors):
            if not vector:
                continue

            doc.features_vector = vector
            doc.vector_dim = len(vector)
            doc.vector_model = getattr(vectorizer, "active_model_name", "unknown")
            await doc.save()
            updated += 1

            if updated % 25 == 0:
                logger.info("Vector backfill progress updated=%s scanned=%s", updated, scanned)

    logger.info("Vector backfill completed updated=%s scanned=%s", updated, scanned)
    return updated, scanned


async def _invalidate_caches() -> None:
    from app.ml.vector_index import vector_index

    vector_index.invalidate()
    await redis_client.delete_by_prefix("deep_research:")
    await redis_client.delete_by_prefix("user_recs:")
    await redis_client.delete_by_prefix("recs_v2_")
    await redis_client.delete_by_prefix("recs_v3_")
    await redis_client.delete_by_prefix("recs_v4_")
    await redis_client.delete_by_prefix("home_data_v2_")
    await redis_client.delete_by_prefix("home_data_v3_")
    await redis_client.delete_by_prefix("home_data_v4_")


async def _warm_caches() -> None:
    from app.workers.precompute_worker import PrecomputeWorker

    worker = PrecomputeWorker()
    try:
        await worker.warm_global_caches()
        await worker.precompute_user_recommendations()
    finally:
        await asyncio.gather(
            worker.content_service.close(),
            worker.recommender.close(),
            worker.sync_service.content_service.close(),
            return_exceptions=True,
        )


async def main(args: argparse.Namespace) -> None:
    await _init_db_with_retries()
    sync_service = ContentSyncService()
    plan = _build_seed_plan(args)
    refresh_all = args.refresh_all or args.demo
    before_count = await _metadata_count(args.content_type)

    try:
        seeded = await _seed_metadata(
            sync_service=sync_service,
            seed_home=(not args.no_seed_home and not args.vectors_only),
            plan=plan,
            content_type=args.content_type,
            concurrency=args.concurrency,
            seed_tags=not args.vectors_only,
            expanded_seed=not args.vectors_only,
        )
        after_seed_count = await _metadata_count(args.content_type)

        updated, scanned = await _backfill_vectors(
            content_type=args.content_type,
            refresh_all=refresh_all,
            batch_size=args.batch_size,
            max_docs=args.max_docs,
            semantic_vectors=args.semantic_vectors,
        )

        await _invalidate_caches()
        if args.warm_caches or args.demo:
            await _warm_caches()
        logger.info(
            "Seed+backfill finished submitted=%s new_or_net_docs=%s before=%s after=%s vector_updated=%s scanned=%s type=%s pages=%s tags=%s",
            seeded,
            after_seed_count - before_count,
            before_count,
            after_seed_count,
            updated,
            scanned,
            args.content_type,
            plan.pages,
            plan.tag_limit,
        )
    finally:
        if not getattr(args, "keep_connections_open", False):
            await asyncio.gather(
                sync_service.content_service.close(),
                redis_client.close(),
                return_exceptions=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed content metadata and backfill vectors for deep research.",
    )
    parser.add_argument(
        "--content-type",
        choices=["all", "movie", "music", "book"],
        default="all",
        help="Restrict seeding/backfill to a content type.",
    )
    parser.add_argument(
        "--tag-limit",
        type=int,
        default=60,
        help="How many master tags to seed via discovery (0 disables).",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="How many provider pages/offsets to scan for each seed query.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="How many provider requests to run at the same time.",
    )
    parser.add_argument(
        "--year-from",
        type=int,
        default=1970,
        help="Earliest movie release year for TMDB discover expansion.",
    )
    parser.add_argument(
        "--year-to",
        type=int,
        default=2026,
        help="Latest movie release year for TMDB discover expansion.",
    )
    parser.add_argument(
        "--year-step",
        type=int,
        default=4,
        help="Step between movie release years in expanded TMDB discover seeding.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Documents per backfill batch.",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=0,
        help="Hard cap for processed documents (0 = no cap).",
    )
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Recompute vectors for all docs, not only missing ones.",
    )
    parser.add_argument(
        "--semantic-vectors",
        action="store_true",
        help="Use SentenceTransformer vectors. Default uses fast deterministic hash vectors.",
    )
    parser.add_argument(
        "--no-seed-home",
        action="store_true",
        help="Skip home snapshot seeding.",
    )
    parser.add_argument(
        "--vectors-only",
        action="store_true",
        help="Do not call providers; only backfill missing vectors and refresh caches.",
    )
    parser.add_argument(
        "--warm-caches",
        action="store_true",
        help="Warm home, discovery and user recommendation caches after seeding.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed a broader demo dataset, refresh vectors and warm caches.",
    )

    asyncio.run(main(parser.parse_args()))
