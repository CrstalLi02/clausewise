"""Wait for MongoDB / Redis to be ready (for Docker startup)."""
from __future__ import annotations

import asyncio
import os
import sys

from app.config import get_settings


async def wait_mongo(uri: str, timeout: float = 60.0) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
            await client.admin.command("ping")
            print("MongoDB ready")
            return
        except Exception:
            await asyncio.sleep(2)
    print("MongoDB is not ready (continuing startup; the service will retry on its own)")


async def wait_redis(addr: str, timeout: float = 30.0) -> None:
    import redis.asyncio as aioredis

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = aioredis.from_url(addr)
            await r.ping()
            await r.aclose()
            print("Redis ready")
            return
        except Exception:
            await asyncio.sleep(2)
    print("Redis is not ready (continuing startup)")


async def main() -> None:
    settings = get_settings()
    if settings.storage_mode == "mongo":
        await wait_mongo(settings.mongodb_uri)
        await wait_redis(settings.redis_addr)


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
