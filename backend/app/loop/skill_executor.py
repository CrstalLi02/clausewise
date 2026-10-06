"""Runtime Skill executor: stable canary bucketing and workflow execution, rather than just concatenating prompts."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.storage.store import DataStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SkillPlan:
    queries: list[str]
    top_k: int
    instructions: list[str] = field(default_factory=list)
    treatment_skills: list[dict[str, Any]] = field(default_factory=list)
    execution_ids: list[str] = field(default_factory=list)


class SkillExecutor:
    def __init__(self, store: DataStore, default_top_k: int = 5) -> None:
        self.store = store
        self.default_top_k = default_top_k

    async def matching(self, query: str, dept_ids: list[str] | None = None) -> list[dict[str, Any]]:
        skills = await self.store.list_skills(status="active")
        allowed = set(dept_ids or [])
        return [
            s for s in skills
            if (s.get("scope") == "global" or not allowed or s.get("dept_id") in allowed)
            and any(p and p.lower() in query.lower() for p in s.get("trigger", {}).get("intent_patterns", []))
        ]

    async def prepare(
        self, query: str, base_queries: list[str], skills: list[dict[str, Any]],
        session_id: str, user_id: str,
    ) -> SkillPlan:
        plan = SkillPlan(queries=list(base_queries), top_k=self.default_top_k)
        for skill in skills:
            percent = float(skill.get("gray_percent", 1.0))
            percent = max(0.0, min(1.0, percent))
            bucket_key = f"{user_id}:{session_id}:{skill.get('_id')}:{skill.get('version', 1)}"
            bucket = int(hashlib.sha256(bucket_key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
            group = "treatment" if bucket < percent else "control"
            execution_id = "strategy_exec_" + uuid.uuid4().hex
            await self.store.upsert("strategy_executions", {
                "_id": execution_id, "artifact_type": "skill", "artifact_id": skill.get("_id"),
                "version": skill.get("version", 1), "experiment_id": skill.get("experiment_id", ""),
                "group": group, "bucket": round(bucket, 6), "session_id": session_id,
                "user_id": user_id, "query": query, "success": None, "created_at": _now(),
            })
            plan.execution_ids.append(execution_id)
            if group == "control":
                continue
            plan.treatment_skills.append(skill)
            self._execute_workflow(plan, skill, query)
        plan.queries = list(dict.fromkeys(q for q in plan.queries if q))
        return plan

    def _execute_workflow(self, plan: SkillPlan, skill: dict[str, Any], query: str) -> None:
        action = skill.get("action") or {}
        for step in action.get("steps") or []:
            kind = step.get("action")
            params = step.get("params") or {}
            if kind == "retrieve":
                template = str(params.get("query") or query)
                plan.queries.append(template.replace("{matter}", query))
                plan.top_k = max(plan.top_k, int(params.get("top_k", plan.top_k)))
            elif kind == "generate":
                template = params.get("template")
                if template and template != "default":
                    plan.instructions.append(f"Use the output template: {template}")
            elif kind == "call_tool" and params.get("tool") == "calendar_lookup":
                plan.instructions.append("When answering about dates or deadlines, you must consult the school calendar and state the basis for each date explicitly.")
        for rubric in skill.get("rubric_rules") or []:
            plan.instructions.append(str(rubric))

    async def record_outcome(self, execution_ids: list[str], success: bool, trace_id: str) -> None:
        for id_ in execution_ids:
            row = await self.store.get("strategy_executions", id_)
            if row:
                row.update({"success": bool(success), "trace_id": trace_id, "completed_at": _now()})
                await self.store.upsert("strategy_executions", row)
