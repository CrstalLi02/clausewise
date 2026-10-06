"""Redis sessions (working memory) and cache, with in-memory fallback (offline dev/testing)."""
from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from app.config import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

SESSION_TTL = 30 * 60  # Working memory TTL=30min
CACHE_TTL = 3600       # FAQ cache TTL=1h


def _redact_redis_addr(addr: str) -> str:
    """Keep connection diagnostics useful without logging credentials."""
    parsed = urlsplit(addr)
    if parsed.password is None:
        return addr
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    username = f"{parsed.username}:***@" if parsed.username else "***@"
    return urlunsplit((parsed.scheme, f"{username}{hostname}{port}", parsed.path, parsed.query, parsed.fragment))


class SessionStore:
    """Session store interface."""

    async def set_session(self, session_id: str, data: dict[str, Any], ttl: int = SESSION_TTL) -> None: ...
    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def cache_get(self, key: str) -> Optional[Any]: ...
    async def cache_set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> None: ...


class MemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, Any] = {}

    async def set_session(self, session_id: str, data: dict[str, Any], ttl: int = SESSION_TTL) -> None:
        self._sessions[session_id] = json.loads(json.dumps(data, default=str))

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def cache_get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    async def cache_set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> None:
        self._cache[key] = value


class RedisSessionStore(SessionStore):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._redis = None

    async def connect(self) -> None:
        import redis.asyncio as aioredis  # Lazy import

        self._redis = aioredis.from_url(self.settings.redis_addr, db=self.settings.redis_db, decode_responses=True)
        await self._redis.ping()
        logger.info("Redis connected: %s", _redact_redis_addr(self.settings.redis_addr))

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    @property
    def redis(self):
        if self._redis is None:
            raise RuntimeError("Redis is not connected")
        return self._redis

    async def set_session(self, session_id: str, data: dict[str, Any], ttl: int = SESSION_TTL) -> None:
        await self.redis.set(f"session:{session_id}", json.dumps(data, default=str), ex=ttl)

    async def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        raw = await self.redis.get(f"session:{session_id}")
        return json.loads(raw) if raw else None

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(f"session:{session_id}")

    async def cache_get(self, key: str) -> Optional[Any]:
        raw = await self.redis.get(f"cache:{key}")
        return json.loads(raw) if raw else None

    async def cache_set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> None:
        await self.redis.set(f"cache:{key}", json.dumps(value, default=str), ex=ttl)


def build_session_store(settings: Settings) -> SessionStore:
    if settings.storage_mode == "mongo":
        store = RedisSessionStore(settings)
        return store
    return MemorySessionStore()
