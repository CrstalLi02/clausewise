"""Episodic memory: append-only conversation events and conversation summaries."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.storage.store import DataStore


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EpisodicMemory:
    def __init__(self, store: DataStore, event_days: int = 90, summary_days: int = 180) -> None:
        self.store = store
        self.event_days = event_days
        self.summary_days = summary_days

    async def append_event(
        self, session_id: str, user_id: str, event_type: str, content: str,
        dept_ids: list[str] | None = None, trace_id: str = "", metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sequence = await self.store.increment(
            "memory_sequences", session_id, "seq", 1, {"session_id": session_id, "user_id": user_id}
        )
        seq = int(sequence["seq"])
        created = _now()
        event = {
            "_id": "event_" + uuid.uuid4().hex, "session_id": session_id, "user_id": user_id,
            "seq": seq, "type": event_type, "content": content, "dept_ids": dept_ids or [],
            "trace_id": trace_id, "metadata": metadata or {}, "created_at": created,
            "expires_at": created + timedelta(days=self.event_days),
        }
        await self.store.upsert("conversation_events", event)
        return event

    async def session_events(self, session_id: str, user_id: str) -> list[dict[str, Any]]:
        rows = await self.store.find("conversation_events", {"session_id": session_id, "user_id": user_id})
        rows.sort(key=lambda row: int(row.get("seq", 0)))
        return rows

    async def update_summary(
        self, session_id: str, user_id: str, summary: str, entities: dict[str, Any] | None = None,
        unresolved: list[str] | None = None, citation_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        created = _now()
        row = {
            "_id": session_id, "session_id": session_id, "user_id": user_id,
            "summary": summary, "resolved_entities": entities or {},
            "unresolved_questions": unresolved or [], "citation_ids": citation_ids or [],
            "authority": "conversation_summary", "updated_at": created,
            "expires_at": created + timedelta(days=self.summary_days),
        }
        await self.store.upsert("conversation_summaries", row)
        return row

    async def get_summary(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        row = await self.store.get("conversation_summaries", session_id)
        return row if row and row.get("user_id") == user_id else None

    async def delete_session(self, session_id: str, user_id: str) -> None:
        for event in await self.session_events(session_id, user_id):
            await self.store.delete("conversation_events", event["_id"])
        summary = await self.get_summary(session_id, user_id)
        if summary:
            await self.store.delete("conversation_summaries", summary["_id"])
        await self.store.delete("memory_sequences", session_id)
