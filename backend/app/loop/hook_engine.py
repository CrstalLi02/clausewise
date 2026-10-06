"""Hook Engine: event responses (what to trigger when), runtime evaluation + evolutionary updates."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.harness.base import Intent
from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Built-in cross-department Hook: course registration + payment → search both Academic Affairs and Finance
DEFAULT_HOOKS = [
    {
        "_id": "hook_cross_dept",
        "name": "cross_dept_hook",
        "dept_id": "",
        "scope": "global",
        "trigger": {
            "intent_patterns": ["course registration", "payment", "refund", "leave of absence"],
            "keyword_any": ["course registration", "payment", "refund", "leave of absence"],
            "min_depts": 1,
        },
        "action": {"type": "cross_dept_retrieval", "expand_depts": True},
        "confidence": 1.0,
        "status": "active",
        "auto_generated": False,
        "created_by": "system",
        "created_at": "",
    }
]


class HookEngine:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def seed_defaults(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for hook in DEFAULT_HOOKS:
            h = dict(hook)
            h["created_at"] = h["created_at"] or now
            if await self.store.get("hooks", h["_id"]) is None:
                await self.store.upsert_hook(h)

    async def active_hooks(self, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        return await self.store.list_hooks(dept_id=dept_id, status="active")

    def evaluate(self, hooks: list[dict[str, Any]], query: str, intent: Intent) -> list[dict[str, Any]]:
        """Return the matched hooks (whose trigger conditions are satisfied)."""
        matched: list[dict[str, Any]] = []
        for hook in hooks:
            trigger = hook.get("trigger", {})
            patterns = trigger.get("intent_patterns", []) + trigger.get("keyword_any", [])
            if patterns and any(p and p.lower() in query.lower() for p in patterns):
                matched.append(hook)
        return matched

    async def apply(self, hooks: list[dict[str, Any]], intent: Intent, dept_ids: list[str]) -> list[str]:
        """Apply hook actions (e.g., expand the cross-department retrieval scope)."""
        result = list(dept_ids)
        query = intent.raw.get("query", "")
        # Static mapping from trigger keywords to departments (cross-department collaboration example)
        kw_dept = {
            "course registration": "dept_jwc",
            "payment": "dept_cwc",
            "refund": "dept_cwc",
            "leave of absence": "dept_jwc",
        }
        for hook in hooks:
            action = hook.get("action", {})
            if action.get("type") == "cross_dept_retrieval" or action.get("expand_depts"):
                for kw, d in kw_dept.items():
                    if kw in query.lower() and d not in result:
                        result.append(d)
        return result

    async def register(self, hook: dict[str, Any], auto_activate: bool = False) -> None:
        hook["status"] = "active" if auto_activate else hook.get("status", "pending")
        hook.setdefault("auto_generated", True)
        hook.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        await self.store.upsert_hook(hook)

    async def approve(self, hook_id: str) -> None:
        hook = await self.store.get("hooks", hook_id)
        if hook:
            hook["status"] = "active"
            await self.store.upsert_hook(hook)
