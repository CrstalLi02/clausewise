"""Long-running Loop background worker: periodically consumes feedback and runs the Loop cycle.

Used to deploy the Loop Engine service independently in K8s.
Usage: python -m scripts.loop_worker [--interval 300]
"""
from __future__ import annotations

import argparse
import asyncio

from app.config import get_settings
from app.deps import build_container
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def main(interval: int) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    container = build_container(settings)
    if container.mongo is not None:
        await container.mongo.connect()
    if hasattr(container.session_store, "connect"):
        try:
            await container.session_store.connect()
        except Exception:
            pass

    logger.info("Loop Worker started, interval %ss", interval)
    while True:
        try:
            report = await container.loop_engine.run_cycle()
            if report.get("observed"):
                logger.info("Loop cycle: %s", report)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Loop cycle error: %s", exc)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()
    asyncio.run(main(args.interval))
