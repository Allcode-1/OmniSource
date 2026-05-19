import argparse
import asyncio
from typing import Iterable

from app.core.database import init_db
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis_client
from app.core.tags import MASTER_TAGS
from app.ml.vectorizer import get_vectorizer
from app.models.content_meta import ContentMetadata
from app.schemas.content import UnifiedContent
from app.services.sync_service import ContentSyncService

configure_logging()
logger = get_logger(__name__)


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


async def _seed_metadata(
    sync_service: ContentSyncService,
    seed_home: bool,
    tag_limit: int,
    content_type: str,
) -> int:
    persisted = 0

    if seed_home:
        home_types = ["all", "movie", "music", "book"]
        if content_type != "all":
            home_types = [content_type]

        for current_type in home_types:
            home_data = await sync_service.content_service.get_home_data(current_type)
            for section_items in home_data.values():
                filtered = _filter_items(section_items, content_type)
                if not filtered:
                    continue
                persisted += await sync_service.persist_items(filtered)
        logger.info("Seeded home snapshot metadata count=%s", persisted)

    if tag_limit > 0:
        tags = list(MASTER_TAGS.keys())[:tag_limit]
        for idx, tag in enumerate(tags, start=1):
            discovery = await sync_service.content_service.get_discovery(tag)
            filtered = _filter_items(discovery, content_type)
            if filtered:
                persisted += await sync_service.persist_items(filtered)
            if idx % 5 == 0 or idx == len(tags):
                logger.info("Seeded tags progress=%s/%s persisted=%s", idx, len(tags), persisted)

    return persisted


def _build_query_filter(content_type: str, refresh_all: bool) -> dict[str, object]:
    query_filter: dict[str, object] = {}
    if not refresh_all:
        query_filter["features_vector.0"] = {"$exists": False}
    if content_type != "all":
        query_filter["type"] = content_type
    return query_filter


async def _backfill_vectors(
    content_type: str,
    refresh_all: bool,
    batch_size: int,
    max_docs: int,
) -> tuple[int, int]:
    vectorizer = get_vectorizer()
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

        for doc in batch:
            if max_docs > 0 and scanned >= max_docs:
                break

            last_id = doc.id
            scanned += 1
            text = _embedding_text(doc)
            if not text:
                continue

            vector = await asyncio.to_thread(vectorizer.get_embedding, text)
            if not vector:
                continue

            doc.features_vector = vector
            await doc.save()
            updated += 1

            if updated % 25 == 0:
                logger.info("Vector backfill progress updated=%s scanned=%s", updated, scanned)

    logger.info("Vector backfill completed updated=%s scanned=%s", updated, scanned)
    return updated, scanned


async def _invalidate_caches() -> None:
    await redis_client.delete_by_prefix("deep_research:")
    await redis_client.delete_by_prefix("user_recs:")
    await redis_client.delete_by_prefix("recs_v2_")
    await redis_client.delete_by_prefix("recs_v3_")
    await redis_client.delete_by_prefix("recs_v4_")
    await redis_client.delete_by_prefix("home_data_v2_")
    await redis_client.delete_by_prefix("home_data_v3_")
    await redis_client.delete_by_prefix("home_data_v4_")


async def main(args: argparse.Namespace) -> None:
    await _init_db_with_retries()
    sync_service = ContentSyncService()

    try:
        seeded = await _seed_metadata(
            sync_service=sync_service,
            seed_home=not args.no_seed_home,
            tag_limit=args.tag_limit,
            content_type=args.content_type,
        )

        updated, scanned = await _backfill_vectors(
            content_type=args.content_type,
            refresh_all=args.refresh_all,
            batch_size=args.batch_size,
            max_docs=args.max_docs,
        )

        await _invalidate_caches()
        logger.info(
            "Seed+backfill finished seeded=%s vector_updated=%s scanned=%s type=%s",
            seeded,
            updated,
            scanned,
            args.content_type,
        )
    finally:
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
        default=30,
        help="How many master tags to seed via discovery (0 disables).",
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
        "--no-seed-home",
        action="store_true",
        help="Skip home snapshot seeding.",
    )

    asyncio.run(main(parser.parse_args()))
