import argparse
import asyncio
from argparse import Namespace

from app.core.redis import redis_client
from app.workers.precompute_worker import PrecomputeWorker
from run_demo_users import main as demo_users_main
from run_seed_vectors import main as seed_main


def build_args(args: argparse.Namespace, *, warm_caches: bool) -> Namespace:
    return Namespace(
        content_type=args.content_type,
        tag_limit=args.tag_limit,
        pages=args.pages,
        concurrency=args.concurrency,
        year_from=args.year_from,
        year_to=args.year_to,
        year_step=args.year_step,
        batch_size=args.batch_size,
        max_docs=0,
        refresh_all=True,
        semantic_vectors=args.semantic_vectors,
        no_seed_home=False,
        vectors_only=False,
        warm_caches=warm_caches,
        demo=True,
        keep_connections_open=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fill the demo database with broad content, vectors and warm caches.",
    )
    parser.add_argument(
        "--content-type",
        choices=["all", "movie", "music", "book"],
        default="all",
    )
    parser.add_argument("--pages", type=int, default=10)
    parser.add_argument("--tag-limit", type=int, default=140)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--year-from", type=int, default=1970)
    parser.add_argument("--year-to", type=int, default=2026)
    parser.add_argument("--year-step", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--semantic-vectors",
        action="store_true",
        help="Use SentenceTransformer instead of fast deterministic hash vectors.",
    )
    parser.add_argument(
        "--no-warm-caches",
        action="store_true",
        help="Fill DB and vectors, but skip Redis cache warmup.",
    )
    parser.add_argument(
        "--demo-users",
        type=int,
        default=12,
        help="Create demo users after catalog seeding (0 disables).",
    )
    parser.add_argument(
        "--demo-user-interactions",
        type=int,
        default=18,
        help="Positive-history items per generated demo user.",
    )
    parser.add_argument(
        "--reset-demo-users",
        action="store_true",
        help="Delete previous demo users before generating new ones.",
    )

    parsed = parser.parse_args()

    async def _main() -> None:
        has_demo_users = parsed.demo_users > 0
        await seed_main(
            build_args(
                parsed,
                warm_caches=(not parsed.no_warm_caches and not has_demo_users),
            ),
        )
        if parsed.demo_users > 0:
            await demo_users_main(
                Namespace(
                    users=parsed.demo_users,
                    interactions=parsed.demo_user_interactions,
                    seed=42,
                    reset=parsed.reset_demo_users,
                    keep_connections_open=True,
                ),
            )
            if not parsed.no_warm_caches:
                worker = PrecomputeWorker()
                try:
                    await worker.warm_global_caches()
                    await worker.precompute_user_recommendations()
                finally:
                    await worker.content_service.close()
                    await worker.recommender.close()
                    await worker.sync_service.content_service.close()
        await redis_client.close()

    asyncio.run(_main())
