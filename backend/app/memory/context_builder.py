"""Unified memory context builder: selective recall, source checks, character budget, and usage auditing."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.memory.episodic import EpisodicMemory
from app.memory.learning import LearningMemory
from app.memory.organization import OrganizationMemory
from app.memory.user_semantic import UserSemanticMemory
from app.memory.working import WorkingMemory
from app.storage.store import DataStore


@dataclass
class MemoryContext:
    session: dict[str, Any] = field(default_factory=dict)
    user_items: list[dict[str, Any]] = field(default_factory=list)
    org_items: list[dict[str, Any]] = field(default_factory=list)
    procedures: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    evidence_chunks: list[dict[str, Any]] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)

    def prompt_text(self) -> str:
        sections: list[str] = []
        summary = self.session.get("summary")
        entities = self.session.get("entities") or {}
        recent = self.session.get("recent_messages") or []
        if summary:
            sections.append(f"Session summary: {summary}")
        if entities:
            sections.append(f"Confirmed entities: {entities}")
        if recent:
            sections.append("Recent conversation: " + " | ".join(f"{m.get('role')}:{m.get('content')}" for m in recent))
        if self.user_items:
            sections.append("Explicit user preferences/profile: " + "; ".join(f"{m.get('key')}={m.get('value')}" for m in self.user_items))
        if self.org_items:
            sections.append("Organizational memory hints (official sources must be re-checked): " + "; ".join(m.get("content", "") for m in self.org_items))
        return "\n".join(sections)


class MemoryContextBuilder:
    def __init__(
        self, store: DataStore, working: WorkingMemory, episodic: EpisodicMemory,
        user_semantic: UserSemanticMemory, organization: OrganizationMemory, learning: LearningMemory,
        max_chars: int = 6000, user_limit: int = 8, org_limit: int = 8, recent_limit: int = 10,
    ) -> None:
        self.store = store
        self.working = working
        self.episodic = episodic
        self.user_semantic = user_semantic
        self.organization = organization
        self.learning = learning
        self.max_chars = max_chars
        self.user_limit = user_limit
        self.org_limit = org_limit
        self.recent_limit = recent_limit

    async def build(
        self, session_id: str, user_id: str, query: str, dept_ids: list[str] | None = None,
        role: str = "student", include_organization: bool = True,
    ) -> MemoryContext:
        state = await self.working.get_context(session_id)
        summary = await self.episodic.get_summary(session_id, user_id)
        session = {
            "summary": (summary or {}).get("summary", state.get("summary", "")),
            "entities": {**((summary or {}).get("resolved_entities") or {}), **(state.get("entities") or {})},
            "recent_messages": (state.get("messages") or [])[-self.recent_limit:],
            "active_dept_ids": state.get("active_dept_ids") or [],
        }
        users = await self.user_semantic.recall(user_id, query, self.user_limit)
        org = await self.organization.recall(query, dept_ids or [], role, self.org_limit) if include_organization and dept_ids else []
        procedures = await self.learning.recall(query, dept_ids or []) if dept_ids else {}
        evidence = await self.organization.source_chunks(org)
        context = MemoryContext(
            session=session, user_items=users, org_items=org, procedures=procedures, evidence_chunks=evidence,
            memory_ids=[m["_id"] for m in users + org],
        )
        self._apply_budget(context)
        return context

    def _apply_budget(self, context: MemoryContext) -> None:
        while len(context.prompt_text()) > self.max_chars:
            if context.org_items:
                context.org_items.pop()
            elif context.user_items:
                context.user_items.pop()
            elif context.session.get("recent_messages"):
                context.session["recent_messages"].pop(0)
            else:
                break
        retained = {item["_id"] for item in context.user_items + context.org_items}
        context.memory_ids = [id_ for id_ in context.memory_ids if id_ in retained]

    async def record_usage(
        self, context: MemoryContext, session_id: str, trace_id: str, user_id: str = ""
    ) -> None:
        for memory_id in context.memory_ids:
            await self.store.upsert("memory_usage", {
                "_id": "muse_" + uuid.uuid4().hex, "memory_id": memory_id,
                "session_id": session_id, "trace_id": trace_id,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc),
            })
