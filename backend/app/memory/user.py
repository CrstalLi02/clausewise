"""User memory: user profiles (MongoDB user_profiles, long-term)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.storage.store import DataStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserMemory:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def get_profile(self, user_id: str) -> dict[str, Any]:
        return await self.store.get_user_profile(user_id) or {
            "_id": user_id,
            "user_id": user_id,
            "role": "student",
            "prefs": {},
            "query_count": 0,
            "feedback_counts": {},
            "created_at": _now(),
        }

    async def record_query(self, user_id: str, query: str, intent_type: str = "") -> None:
        defaults = {
            "user_id": user_id, "role": "student", "prefs": {},
            "feedback_counts": {}, "created_at": _now(),
        }
        await self.store.increment("user_profiles", user_id, "query_count", 1, defaults)
        if intent_type:
            await self.store.increment("user_profiles", user_id, f"prefs.intent_counts.{intent_type}", 1, defaults)

    async def record_feedback(self, user_id: str, signal: str, query: str) -> None:
        await self.store.increment(
            "user_profiles", user_id, f"feedback_counts.{signal}", 1,
            {"user_id": user_id, "role": "student", "prefs": {}, "created_at": _now()},
        )

    async def set_pref(self, user_id: str, key: str, value: Any) -> None:
        profile = await self.get_profile(user_id)
        profile.setdefault("prefs", {})[key] = value
        await self.store.upsert_user_profile(profile)
