from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

from app.auth.utils import hash_password
from app.core.content_keys import make_content_key
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis_client
from app.models.content_meta import ContentMetadata
from app.models.interaction import Interaction
from app.models.user import User

configure_logging()
logger = get_logger(__name__)


INTEREST_PROFILES = [
    ["action", "thriller", "rock"],
    ["fantasy", "animation", "family"],
    ["romance", "pop", "drama"],
    ["history", "war", "classical"],
    ["sci-fi", "cyberpunk", "electronic"],
    ["mystery", "crime", "jazz"],
    ["comedy", "dance", "adventure"],
    ["horror", "metal", "dark"],
]


def _doc_ref(doc: ContentMetadata) -> str:
    return make_content_key(doc.type, doc.ext_id) or doc.ext_id


def _event_weight(event_type: str) -> float:
    return {
        "view": 0.2,
        "open_detail": 0.5,
        "like": 1.0,
        "playlist_add": 0.8,
    }.get(event_type, 0.1)


async def _load_catalog() -> list[ContentMetadata]:
    return (
        await ContentMetadata.find({"features_vector.0": {"$exists": True}})
        .sort("-rating")
        .to_list()
    )


def _matches(doc: ContentMetadata, interests: list[str]) -> bool:
    genres = {genre.lower() for genre in doc.genres or []}
    text = f"{doc.title} {doc.subtitle or ''} {doc.description or ''}".lower()
    return any(interest in genres or interest in text for interest in interests)


async def _reset_demo_users() -> None:
    users = await User.find({"email": {"$regex": r"^demo\+"}}).to_list()
    user_ids = [str(user.id) for user in users]
    for user in users:
        await user.delete()
    if user_ids:
        await Interaction.find({"user_id": {"$in": user_ids}}).delete()
    logger.info("Reset demo users users=%s", len(users))


async def _upsert_user(index: int, interests: list[str]) -> User:
    email = f"demo+{index:02d}@omnisource.local"
    username = f"demo_user_{index:02d}"
    user = await User.find_one(User.email == email)
    if user is None:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password("DemoPass123!"),
            interests=interests,
            is_onboarding_completed=True,
            ranking_variant="hybrid_ml" if index % 2 else "content_only",
        )
        await user.insert()
    else:
        user.username = username
        user.interests = interests
        user.is_onboarding_completed = True
        user.ranking_variant = "hybrid_ml" if index % 2 else "content_only"
        await user.save()
    return user


async def _seed_interactions(
    user: User,
    docs: list[ContentMetadata],
    *,
    interactions_per_user: int,
    rng: random.Random,
) -> int:
    await Interaction.find({"user_id": str(user.id)}).delete()
    preferred = [doc for doc in docs if _matches(doc, user.interests)]
    pool = preferred or docs
    if not pool:
        return 0

    selected = rng.sample(pool, k=min(interactions_per_user, len(pool)))
    now = datetime.now(timezone.utc)
    created = 0
    for offset, doc in enumerate(reversed(selected)):
        base_time = now - timedelta(days=len(selected) - offset, hours=rng.randint(0, 12))
        events = ["view", "open_detail"]
        if offset % 2 == 0:
            events.append("like")
        if offset % 7 == 0:
            events.append("playlist_add")

        for event_index, event_type in enumerate(events):
            await Interaction(
                user_id=str(user.id),
                ext_id=doc.ext_id,
                content_key=_doc_ref(doc),
                content_type=doc.type,
                type=event_type,
                weight=_event_weight(event_type),
                meta={
                    "title": doc.title,
                    "genres": doc.genres,
                    "rating": doc.rating,
                    "ranking_variant": user.ranking_variant,
                    "demo": True,
                },
                created_at=base_time + timedelta(minutes=event_index * 7),
            ).insert()
            created += 1
    return created


async def main(args: argparse.Namespace) -> None:
    await init_db()
    if args.reset:
        await _reset_demo_users()

    docs = await _load_catalog()
    rng = random.Random(args.seed)
    total_events = 0
    for index in range(1, args.users + 1):
        interests = INTEREST_PROFILES[(index - 1) % len(INTEREST_PROFILES)]
        user = await _upsert_user(index, interests)
        total_events += await _seed_interactions(
            user,
            docs,
            interactions_per_user=args.interactions,
            rng=rng,
        )

    await redis_client.delete_by_prefix("user_recs:")
    logger.info(
        "Demo users seeded users=%s interactions=%s catalog_docs=%s",
        args.users,
        total_events,
        len(docs),
    )
    if not getattr(args, "keep_connections_open", False):
        await redis_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create demo users with realistic positive interaction history.",
    )
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--interactions", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true")
    parser.set_defaults(keep_connections_open=False)
    asyncio.run(main(parser.parse_args()))
