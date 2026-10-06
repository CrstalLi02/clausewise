"""Rule Engine: hard-constraint rules (highest priority), runtime injection + evolutionary updates."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Built-in global rules (starting point of the loop)
DEFAULT_RULES = [
    {
        "_id": "rule_cite_source",
        "name": "cite_source_rule",
        "scope": "global",
        "content": "Every answer must include citations of the source clauses.",
        "priority": 100,
        "status": "active",
        "auto_generated": False,
        "confidence": 1.0,
        "created_by": "system",
        "created_at": "",
    },
    {
        "_id": "rule_no_guess",
        "name": "no_guess_rule",
        "scope": "global",
        "content": "When the documents contain no explicit answer, you must say 'No explicit provision was found in the current policy documents'; never fabricate.",
        "priority": 100,
        "status": "active",
        "auto_generated": False,
        "confidence": 1.0,
        "created_by": "system",
        "created_at": "",
    },
]


class RuleEngine:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def seed_defaults(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for rule in DEFAULT_RULES:
            r = dict(rule)
            r["created_at"] = r["created_at"] or now
            if await self.store.get("rules", r["_id"]) is None:
                await self.store.upsert_rule(r)

    async def active_rules(self, dept_ids: Optional[list[str]] = None) -> list[dict[str, Any]]:
        rules = await self.store.list_rules(status="active")
        if dept_ids:
            allowed = set(dept_ids)
            rules = [
                r for r in rules
                if r.get("scope") == "global"
                or (r.get("scope") == "department" and r.get("dept_id") in allowed)
            ]
        else:
            rules = [r for r in rules if r.get("scope") == "global"]
        rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
        return rules

    def format_rules(self, rules: list[dict[str, Any]]) -> str:
        if not rules:
            return "- Always cite sources\n- Never fabricate without a basis"
        return "\n".join(f"- {r.get('content', '')}" for r in rules)

    async def register(self, rule: dict[str, Any], auto_activate: bool = False) -> None:
        rule["status"] = "active" if auto_activate else rule.get("status", "pending")
        rule.setdefault("auto_generated", True)
        rule.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        await self.store.upsert_rule(rule)

    async def approve(self, rule_id: str) -> None:
        rule = await self.store.get("rules", rule_id)
        if rule:
            rule["status"] = "active"
            await self.store.upsert_rule(rule)

    async def deprecate(self, rule_id: str) -> None:
        rule = await self.store.get("rules", rule_id)
        if rule:
            rule["status"] = "deprecated"
            await self.store.upsert_rule(rule)
