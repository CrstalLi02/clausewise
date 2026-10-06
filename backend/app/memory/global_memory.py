"""Global memory: knowledge shared across departments (global Skills/Rules, organization calendar, organization-wide glossary)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.storage.store import DataStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GlobalMemory:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def get(self) -> dict[str, Any]:
        mem = await self.store.get("global_memory", "global")
        if mem is None:
            mem = {"_id": "global", "calendar": {}, "global_rules": [], "created_at": _now()}
        return mem

    async def set_calendar(self, calendar: dict[str, Any]) -> None:
        mem = await self.get()
        mem["calendar"] = calendar
        await self.store.upsert("global_memory", mem)
        await self.store.upsert("org_memory_items", {
            "_id": "orgmem_global_calendar", "scope": "global", "dept_id": "",
            "type": "calendar", "title": "Current organization calendar", "content": str(calendar),
            "source_refs": [], "source_doc_ids": [], "authority": "admin_approved",
            "confidence": 1.0, "review_status": "approved", "status": "active",
            "access_scope": ["student", "teacher", "admin"], "revision": 1,
            "updated_at": datetime.now(timezone.utc),
        })

    async def get_calendar(self) -> dict[str, Any]:
        item = await self.store.get("org_memory_items", "orgmem_global_calendar")
        if item and item.get("status") == "active":
            mem = await self.get()
            return mem.get("calendar", {})
        mem = await self.get()
        return mem.get("calendar", {})

    async def add_global_rule(self, rule: str) -> None:
        mem = await self.get()
        mem.setdefault("global_rules", []).append(rule)
        await self.store.upsert("global_memory", mem)
