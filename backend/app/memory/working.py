"""Working memory: current session context (Redis, TTL=30min)."""
from __future__ import annotations

from typing import Any

from app.storage.redis_store import SessionStore

MAX_HISTORY = 10


class WorkingMemory:
    def __init__(self, session_store: SessionStore, ttl: int = 1800, max_history: int = MAX_HISTORY) -> None:
        self.sessions = session_store
        self.ttl = ttl
        self.max_history = max_history

    async def get_context(self, session_id: str) -> dict[str, Any]:
        ctx = await self.sessions.get_session(session_id) or {}
        ctx.setdefault("messages", [])
        ctx.setdefault("intent", {})
        ctx.setdefault("retrieved", [])
        ctx.setdefault("summary", "")
        ctx.setdefault("entities", {})
        ctx.setdefault("active_dept_ids", [])
        ctx.setdefault("citation_ids", [])
        ctx.setdefault("revision", 0)
        return ctx

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        ctx = await self.get_context(session_id)
        ctx["messages"].append({"role": role, "content": content})
        ctx["messages"] = ctx["messages"][-self.max_history:]
        ctx["revision"] = int(ctx.get("revision", 0)) + 1
        await self.sessions.set_session(session_id, ctx, ttl=self.ttl)

    async def set_intent(self, session_id: str, intent: dict[str, Any]) -> None:
        ctx = await self.get_context(session_id)
        ctx["intent"] = intent
        ctx["entities"].update(intent.get("entities") or {})
        ctx["active_dept_ids"] = intent.get("depts") or ctx.get("active_dept_ids", [])
        ctx["revision"] = int(ctx.get("revision", 0)) + 1
        await self.sessions.set_session(session_id, ctx, ttl=self.ttl)

    async def set_retrieved(self, session_id: str, chunks: list[dict[str, Any]]) -> None:
        ctx = await self.get_context(session_id)
        ctx["retrieved"] = [c.get("_id") or c.get("id") for c in chunks if c.get("_id") or c.get("id")]
        ctx["citation_ids"] = ctx["retrieved"][:10]
        ctx["revision"] = int(ctx.get("revision", 0)) + 1
        await self.sessions.set_session(session_id, ctx, ttl=self.ttl)

    async def set_summary(self, session_id: str, summary: str) -> None:
        ctx = await self.get_context(session_id)
        ctx["summary"] = summary
        ctx["revision"] = int(ctx.get("revision", 0)) + 1
        await self.sessions.set_session(session_id, ctx, ttl=self.ttl)

    async def history(self, session_id: str) -> list[dict[str, str]]:
        ctx = await self.get_context(session_id)
        return ctx["messages"]

    async def clear(self, session_id: str) -> None:
        await self.sessions.delete_session(session_id)
