from __future__ import annotations

import argparse
import asyncio
import random
from dataclasses import dataclass
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


CONTENT_TYPES = ("movie", "music", "book")


@dataclass(frozen=True)
class InterestProfile:
    name: str
    interests: list[str]
    type_mix: dict[str, float]


INTEREST_PROFILES = [
    InterestProfile("night-drive", ["sci-fi", "cyberpunk", "electronic"], {"music": 0.56, "movie": 0.34, "book": 0.10}),
    InterestProfile("cinephile", ["action", "thriller", "crime"], {"movie": 0.68, "music": 0.18, "book": 0.14}),
    InterestProfile("reader", ["fantasy", "magic", "adventure"], {"book": 0.62, "movie": 0.25, "music": 0.13}),
    InterestProfile("soft-pop", ["romance", "pop", "drama"], {"music": 0.48, "book": 0.28, "movie": 0.24}),
    InterestProfile("history", ["history", "war", "documentary"], {"book": 0.44, "movie": 0.40, "music": 0.16}),
    InterestProfile("mystery", ["mystery", "detective", "jazz"], {"movie": 0.42, "book": 0.38, "music": 0.20}),
    InterestProfile("weekend", ["comedy", "family", "animation"], {"movie": 0.52, "music": 0.30, "book": 0.18}),
    InterestProfile("dark", ["horror", "metal", "dark"], {"music": 0.46, "movie": 0.42, "book": 0.12}),
    InterestProfile("maker", ["technology", "science", "business"], {"book": 0.50, "music": 0.28, "movie": 0.22}),
    InterestProfile("mixed", ["adventure", "indie", "coming-of-age"], {"movie": 0.34, "music": 0.34, "book": 0.32}),
]


def _doc_ref(doc: ContentMetadata) -> str:
    return make_content_key(doc.type, doc.ext_id) or doc.ext_id


def _event_weight(event_type: str) -> float:
    return {
        "view": 0.2,
        "open_detail": 0.5,
        "preview_open": 0.65,
        "preview_play": 1.15,
        "external_open": 0.55,
        "dwell_time": 0.3,
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


def _type_counts(total: int, type_mix: dict[str, float]) -> dict[str, int]:
    remaining = total
    counts: dict[str, int] = {}
    for content_type in CONTENT_TYPES[:-1]:
        count = min(remaining, round(total * type_mix.get(content_type, 0.0)))
        counts[content_type] = max(0, count)
        remaining -= counts[content_type]
    counts[CONTENT_TYPES[-1]] = max(0, remaining)
    return counts


def _sample_profile_docs(
    docs: list[ContentMetadata],
    profile: InterestProfile,
    *,
    total: int,
    rng: random.Random,
) -> list[ContentMetadata]:
    selected: list[ContentMetadata] = []
    selected_refs: set[str] = set()
    counts = _type_counts(total, profile.type_mix)

    for content_type, count in counts.items():
        if count <= 0:
            continue
        typed_docs = [doc for doc in docs if doc.type == content_type]
        preferred = [doc for doc in typed_docs if _matches(doc, profile.interests)]
        pool = preferred or typed_docs
        if not pool:
            continue
        sample_size = min(count, len(pool))
        for doc in rng.sample(pool, k=sample_size):
            ref = _doc_ref(doc)
            if ref in selected_refs:
                continue
            selected_refs.add(ref)
            selected.append(doc)

    if len(selected) < total:
        remainder = [
            doc
            for doc in docs
            if _doc_ref(doc) not in selected_refs
            and (_matches(doc, profile.interests) or doc.type in profile.type_mix)
        ]
        if remainder:
            for doc in rng.sample(remainder, k=min(total - len(selected), len(remainder))):
                selected_refs.add(_doc_ref(doc))
                selected.append(doc)

    rng.shuffle(selected)
    return selected[:total]


async def _reset_demo_users() -> None:
    users = await User.find({"email": {"$regex": r"^demo\+"}}).to_list()
    user_ids = [str(user.id) for user in users]
    for user in users:
        await user.delete()
    if user_ids:
        await Interaction.find({"user_id": {"$in": user_ids}}).delete()
    logger.info("Reset demo users users=%s", len(users))


async def _upsert_user(index: int, interests: list[str]) -> User:
    email = f"demo+{index:02d}@example.com"
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
    profile: InterestProfile,
    interactions_per_user: int,
    rng: random.Random,
) -> int:
    await Interaction.find({"user_id": str(user.id)}).delete()
    selected = _sample_profile_docs(
        docs,
        profile,
        total=interactions_per_user,
        rng=rng,
    )
    if not selected:
        return 0

    now = datetime.now(timezone.utc)
    created = 0
    for offset, doc in enumerate(reversed(selected)):
        base_time = now - timedelta(days=len(selected) - offset, hours=rng.randint(0, 12))
        events = ["view", "open_detail"]
        if offset % 3 != 1:
            events.append("preview_open")
        if doc.type in {"movie", "music"} and offset % 3 != 2:
            events.append("preview_play")
        if doc.type == "book" and offset % 4 == 0:
            events.append("external_open")
        if offset % 2 == 0:
            events.append("like")
        if offset % 7 == 0:
            events.append("playlist_add")
        if offset % 3 == 0:
            events.append("dwell_time")

        for event_index, event_type in enumerate(events):
            seconds = rng.randint(18, 140)
            weight = _event_weight(event_type)
            meta = {
                "title": doc.title,
                "genres": doc.genres,
                "rating": doc.rating,
                "ranking_variant": user.ranking_variant,
                "profile": profile.name,
                "demo": True,
            }
            if event_type == "dwell_time":
                meta["seconds"] = seconds
                weight = max(0.1, seconds / 60)
            if event_type.startswith("preview"):
                meta["provider"] = "demo"
                meta["preview_type"] = (
                    "audio"
                    if doc.type == "music"
                    else "external"
                    if doc.type == "book"
                    else "video"
                )
            if event_type == "external_open":
                meta["target"] = "source"

            await Interaction(
                user_id=str(user.id),
                ext_id=doc.ext_id,
                content_key=_doc_ref(doc),
                content_type=doc.type,
                type=event_type,
                weight=weight,
                meta=meta,
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
        profile = INTEREST_PROFILES[(index - 1) % len(INTEREST_PROFILES)]
        user = await _upsert_user(index, profile.interests)
        total_events += await _seed_interactions(
            user,
            docs,
            profile=profile,
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
