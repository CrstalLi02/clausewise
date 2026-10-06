"""User semantic memory: fine-grained, explainable, deletable stable user facts and preferences."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.memory.policy import MemoryPolicy
from app.storage.store import DataStore


class UserSemanticMemory:
    def __init__(self, store: DataStore, retention_days: int = 180) -> None:
        self.store = store
        self.retention_days = retention_days

    async def remember(
        self, user_id: str, key: str, value: Any, category: str = "preference",
        source_type: str = "explicit_user", source_event_id: str = "",
        confidence: float = 1.0, consent: bool = True, actor_id: str = "system",
    ) -> dict[str, Any]:
        if MemoryPolicy.is_sensitive(key, value):
            raise ValueError("Sensitive information may not be written to long-term user memory")
        if source_type == "inferred" and not consent:
            candidate = {
                "_id": "mcand_" + uuid.uuid4().hex, "user_id": user_id, "key": key,
                "value": value, "category": category, "source_type": source_type,
                "source_event_id": source_event_id, "confidence": confidence,
                "status": "pending", "created_at": datetime.now(timezone.utc),
            }
            await self.store.upsert("memory_candidates", candidate)
            return candidate
        existing = [
            row for row in await self.store.find("user_memory_items", {"user_id": user_id, "key": key, "status": "active"})
        ]
        revision = max((int(row.get("revision", 0)) for row in existing), default=0) + 1
        for row in existing:
            row["status"] = "superseded"
            await self.store.upsert("user_memory_items", row)
        current = datetime.now(timezone.utc)
        item = {
            "_id": "umem_" + uuid.uuid4().hex, "user_id": user_id, "key": key,
            "value": value, "category": category, "source_type": source_type,
            "source_event_id": source_event_id, "authority": source_type,
            "confidence": confidence, "sensitivity": "low", "consent": consent,
            "status": "active", "revision": revision, "last_confirmed_at": current,
            "created_at": current, "expires_at": current + timedelta(days=self.retention_days),
        }
        await self.store.upsert("user_memory_items", item)
        await self._audit(actor_id, "remember", item["_id"], user_id)
        return item

    async def recall(self, user_id: str, query: str = "", limit: int = 8) -> list[dict[str, Any]]:
        rows = [
            row for row in await self.store.find("user_memory_items", {"user_id": user_id, "status": "active"})
            if MemoryPolicy.user_item_readable(row, user_id)
        ]
        query_lower = query.lower()
        rows.sort(
            key=lambda row: (
                1 if row.get("key", "").lower() in query_lower else 0,
                MemoryPolicy.authority(row), row.get("last_confirmed_at"),
            ),
            reverse=True,
        )
        return rows[:limit]

    async def forget(self, user_id: str, memory_id: str, actor_id: str) -> bool:
        item = await self.store.get("user_memory_items", memory_id)
        if not item or item.get("user_id") != user_id:
            return False
        item["status"] = "deleted"
        item["deleted_at"] = datetime.now(timezone.utc)
        await self.store.upsert("user_memory_items", item)
        await self._audit(actor_id, "forget", memory_id, user_id)
        return True

    async def _audit(self, actor_id: str, action: str, memory_id: str, owner_id: str) -> None:
        await self.store.upsert("memory_audit", {
            "_id": "maudit_" + uuid.uuid4().hex, "actor_id": actor_id, "action": action,
            "memory_id": memory_id, "owner_id": owner_id, "created_at": datetime.now(timezone.utc),
        })
