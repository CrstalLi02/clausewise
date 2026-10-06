"""Memory lifecycle: TTL fallback, expiry archiving, per-user deletion, and auditing."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.memory.policy import parse_time
from app.storage.store import DataStore


class MemoryRetentionManager:
    TTL_COLLECTIONS = (
        "conversation_events", "conversation_summaries", "user_memory_items",
        "org_memory_items", "memory_topics",
    )

    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def prune_expired(self, current: datetime | None = None) -> dict[str, int]:
        current = current or datetime.now(timezone.utc)
        report: dict[str, int] = {}
        for collection in self.TTL_COLLECTIONS:
            count = 0
            for row in await self.store.find(collection):
                expires = parse_time(row.get("expires_at"))
                if expires and expires <= current:
                    await self.store.delete(collection, row["_id"])
                    count += 1
            report[collection] = count
        return report

    async def delete_user(self, user_id: str, actor_id: str) -> dict[str, int]:
        report: dict[str, int] = {}
        for collection in (
            "conversation_events", "conversation_summaries", "user_memory_items",
            "memory_candidates", "memory_usage", "user_profiles",
        ):
            rows = await self.store.find(collection, {"user_id": user_id})
            for row in rows:
                await self.store.delete(collection, row["_id"])
            report[collection] = len(rows)
        profile = await self.store.get("user_profiles", user_id)
        if profile:
            await self.store.delete("user_profiles", user_id)
            report["user_profiles"] = max(report.get("user_profiles", 0), 1)
        sequences = await self.store.find("memory_sequences", {"user_id": user_id})
        for sequence in sequences:
            await self.store.delete("memory_sequences", sequence["_id"])
        report["memory_sequences"] = len(sequences)
        await self.store.upsert("memory_audit", {
            "_id": "maudit_" + uuid.uuid4().hex, "actor_id": actor_id,
            "action": "delete_user_memory", "owner_id": user_id, "result": report,
            "created_at": datetime.now(timezone.utc),
        })
        return report
