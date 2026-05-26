import argparse
import asyncio
import json

from app.core.database import init_db
from app.core.logging import configure_logging
from app.core.redis import redis_client
from app.ml.evaluation import MLEvaluationService

configure_logging()


async def main(args: argparse.Namespace) -> None:
    await init_db()
    service = MLEvaluationService()
    try:
        report = await service.build_report(
            sample_users=args.sample_users,
            recommendation_limit=args.limit,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        await asyncio.gather(
            service.engine.close(),
            redis_client.close(),
            return_exceptions=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Print catalog, interaction and recommendation readiness metrics.",
    )
    parser.add_argument(
        "--sample-users",
        type=int,
        default=25,
        help="How many users with positive interactions to sample.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="How many recommendations to generate per sampled user.",
    )
    asyncio.run(main(parser.parse_args()))
