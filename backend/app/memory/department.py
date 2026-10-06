"""Department memory: department-level knowledge (Skills/Hooks/Rules, FAQs, glossary, conflicts, hot-topic trends)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.storage.store import DataStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DepartmentMemory:
    def __init__(self, store: DataStore, topic_retention_days: int = 90) -> None:
        self.store = store
        self.topic_retention_days = topic_retention_days

    async def get_dept_memory(self, dept_id: str) -> dict[str, Any]:
        mem = await self.store.get("dept_memory", dept_id)
        if mem is None:
            mem = {"_id": dept_id, "dept_id": dept_id, "faqs": [], "hot_queries": {}, "conflicts": [], "created_at": _now()}
        return mem

    async def bump_hot_query(self, dept_id: str, query: str) -> None:
        from app.retrieval.bm25 import tokenize

        tokens = [token for token in tokenize(query) if len(token.strip()) > 1]
        topic = tokens[0] if tokens else "other"
        day = datetime.now(timezone.utc).date().isoformat()
        await self.store.increment(
            "memory_topics", f"{dept_id}:{day}:{topic}", "count", 1,
            {
                "dept_id": dept_id, "topic_key": topic, "date": day,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=self.topic_retention_days),
            },
        )

    async def add_faq(self, dept_id: str, question: str, answer: str, source: str = "loop_engine") -> None:
        raise ValueError("FAQs must be bound to official source_refs via OrganizationMemory.publish")

    async def match_faq(self, dept_id: str, query: str) -> Optional[dict[str, Any]]:
        """FAQ-first matching (keyword overlap) so hot questions hit the cache directly."""
        return None

    async def record_conflict(self, dept_id: str, relation: dict[str, Any]) -> None:
        mem = await self.get_dept_memory(dept_id)
        mem.setdefault("conflicts", []).append(relation)
        mem["conflicts"] = mem["conflicts"][-100:]
        await self.store.upsert("dept_memory", mem)
