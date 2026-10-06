"""Built-in baseline Skills used by the real runtime and the admin demo.

These are idempotent, executable workflow policies rather than display-only rows.
They provide a safe baseline before enough production traces exist for Skill Miner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.storage.store import DataStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_SKILLS: list[dict[str, Any]] = [
    {
        "_id": "skill_dept_hqaq_emergency_seed",
        "name": "Extreme Weather Safety Response",
        "description": "Expands fact recall for rainstorm, typhoon, and flood-prevention questions, and organizes answers by risks, actions, and how to get help.",
        "dept_id": "dept_hqaq", "scope": "department",
        "trigger": {
            "intent_patterns": ["rainstorm", "typhoon", "flood", "extreme weather", "safety"],
            "entities_required": ["matter"], "confidence_threshold": 0.75,
        },
        "action": {
            "type": "workflow",
            "steps": [
                {"step": 1, "action": "extract_entity", "params": {"entity": "matter"}},
                {"step": 2, "action": "retrieve", "params": {"query": "{matter} warning shelter emergency phone campus safety", "top_k": 8}},
                {"step": 3, "action": "generate", "params": {"template": "Risks - Actions - Help checklist"}},
            ],
        },
        "unique_rules": ["Emergency phone numbers, opening hours, and response levels must be checked verbatim against the source; never fill in information the source does not provide."],
        "rubric_rules": ["The answer must cover at least three dimensions: travel, buildings/labs, and getting help in danger, with sources attached to key actions."],
    },
    {
        "_id": "skill_dept_zfxy_procedure_seed",
        "name": "Procedure Step Navigation",
        "description": "Turns operating instructions such as the psychological assessment and luggage storage into ordered steps with conditions and sources.",
        "dept_id": "dept_zfxy", "scope": "department",
        "trigger": {
            "intent_patterns": ["psychological assessment", "luggage storage", "instructions", "how do i apply", "steps"],
            "entities_required": ["matter"], "confidence_threshold": 0.72,
        },
        "action": {
            "type": "workflow",
            "steps": [
                {"step": 1, "action": "extract_entity", "params": {"entity": "matter"}},
                {"step": 2, "action": "retrieve", "params": {"query": "{matter} login requirements steps submission notes", "top_k": 7}},
                {"step": 3, "action": "generate", "params": {"template": "Prerequisites - Steps - Completion check"}},
            ],
        },
        "unique_rules": ["Step order must match the source; for pledge-form questions, distinguish location, deadline, retrieval restrictions, and the responsible party."],
        "rubric_rules": ["Keep the original names of system buttons or pages; do not replace them with vague synonyms."],
    },
    {
        "_id": "skill_academic_deadline_seed",
        "name": "Academic Milestone and Deadline Verification",
        "description": "Expands recall of time-related evidence for proposal, defense, and deadline questions, and requires distinguishing document dates from event dates.",
        "dept_id": "", "scope": "global",
        "trigger": {
            "intent_patterns": ["proposal", "defense", "deadline", "when", "latest"],
            "entities_required": ["matter"], "confidence_threshold": 0.78,
        },
        "action": {
            "type": "workflow",
            "steps": [
                {"step": 1, "action": "retrieve", "params": {"query": "{matter} notice date time location deadline", "top_k": 8}},
                {"step": 2, "action": "call_tool", "params": {"tool": "calendar_lookup"}},
                {"step": 3, "action": "generate", "params": {"template": "Milestone verification table"}},
            ],
        },
        "unique_rules": ["Clearly distinguish the notice publication date, the material submission deadline, the defense date, and the applicable audience."],
        "rubric_rules": ["When a policy conflicts with the organization calendar, treat the current active policy text as the factual basis and prompt for human confirmation."],
    },
]


async def seed_default_skills(store: DataStore) -> int:
    created = 0
    for template in DEFAULT_SKILLS:
        if await store.get_skill(template["_id"]) is not None:
            continue
        skill = {
            **template, "metrics": {
                "trigger_count": 0, "success_count": 0, "success_rate": 0.0,
                "avg_latency_ms": 0, "last_triggered": "",
            },
            "version": 1, "status": "active", "auto_generated": False,
            "confidence": 1.0, "gray_percent": 1.0, "created_by": "system_seed",
            "origin": "builtin_baseline", "created_at": _now(),
        }
        await store.upsert_skill(skill)
        await store.upsert("strategy_versions", {
            "_id": f"strategy_version_{skill['_id']}_v1_seed",
            "artifact_id": skill["_id"], "artifact_type": "skill", "version": 1,
            "reason": "builtin_baseline_seeded", "snapshot": skill, "created_at": _now(),
        })
        created += 1
    return created
