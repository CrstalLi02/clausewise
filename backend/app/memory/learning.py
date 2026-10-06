"""Procedural/learning memory plane: unified reads of Skills, Hooks, Rules, and experiment state."""
from __future__ import annotations

from typing import Any

from app.storage.store import DataStore


class LearningMemory:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def recall(self, query: str, dept_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        allowed = set(dept_ids)
        skills = [
            item for item in await self.store.list_skills(status="active")
            if (item.get("scope") == "global" or item.get("dept_id") in allowed)
            and any(pattern and pattern in query for pattern in item.get("trigger", {}).get("intent_patterns", []))
        ]
        hooks = [
            item for item in await self.store.list_hooks(status="active")
            if item.get("scope") == "global" or item.get("dept_id") in allowed
        ]
        rules = [
            item for item in await self.store.list_rules(status="active")
            if item.get("scope") == "global" or item.get("dept_id") in allowed
        ]
        experiments = [
            item for item in await self.store.find("experiments", {"status": "running"})
            if any(item.get("artifact_id") == skill.get("_id") for skill in skills)
        ]
        return {"skills": skills, "hooks": hooks, "rules": rules, "experiments": experiments}
