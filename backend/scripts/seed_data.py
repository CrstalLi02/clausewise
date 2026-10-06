"""Seed data: departments / glossary / FAQ / organization calendar / default Rules & Hooks.

Usage: python -m scripts.seed_data
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.config import get_settings
from app.deps import build_container
from app.loop.default_skills import seed_default_skills

DEPARTMENTS = [
    {"_id": "dept_jwc", "name": "Academic Affairs Office", "name_en": "Academic Affairs", "category": "academic"},
    {"_id": "dept_xsc", "name": "Student Affairs Office", "name_en": "Student Affairs", "category": "student"},
    {"_id": "dept_cwc", "name": "Finance Office", "name_en": "Finance", "category": "finance"},
    {"_id": "dept_rsc", "name": "Human Resources Office", "name_en": "Human Resources", "category": "admin"},
    {"_id": "dept_yjsy", "name": "Graduate School", "name_en": "Graduate School", "category": "academic"},
    {"_id": "dept_zfxy", "name": "Sino-French Institute", "name_en": "Sino-French Institute", "category": "academic"},
    {"_id": "dept_hqaq", "name": "Logistics and Security Department", "name_en": "Logistics & Security", "category": "logistics"},
]

GLOSSARY = [
    {"canonical": "counselor", "synonyms": ["class advisor", "student advisor", "academic counselor"]},
    {"canonical": "course withdrawal", "synonyms": ["drop a course", "withdraw from a course", "course drop"]},
    {"canonical": "tuition", "synonyms": ["tuition fees", "school fees"]},
    {"canonical": "course registration", "synonyms": ["course selection", "registration system", "class enrollment"]},
    {"canonical": "credit", "synonyms": ["credit system", "credit hours"]},
]

CALENDAR = {
    "current_semester": "2025-2026 Semester 1",
    "semester_start": "2025-09-01",
    "semester_end": "2026-01-18",
    "week16_20": "Course registration period",
}


async def main() -> None:
    settings = get_settings()
    container = build_container(settings)
    if container.mongo is not None:
        await container.mongo.connect()
    if hasattr(container.session_store, "connect"):
        try:
            await container.session_store.connect()
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    store = container.store

    for dept in DEPARTMENTS:
        d = dict(dept)
        d.setdefault("admin_users", [])
        d.setdefault("agent_config", {"model": "deepseek-v4-flash", "temperature": 0.1, "max_tokens": 2048})
        d.setdefault("loop_phase", "human_in_loop")
        d.setdefault("review_stats", {"total": 0, "correct": 0, "accuracy": 0.0})
        d.setdefault("created_at", now)
        d["updated_at"] = now
        await store.upsert_department(d)
        print(f"[dept] {d['_id']} {d['name']}")

    for i, g in enumerate(GLOSSARY):
        entry = {
            "_id": f"glossary_seed_{i}",
            "canonical": g["canonical"],
            "synonyms": g["synonyms"],
            "dept_id": "",
            "created_by": "seed",
            "created_at": now,
        }
        await store.upsert_glossary(entry)
    print(f"[glossary] {len(GLOSSARY)} entries")

    await container.global_memory.set_calendar(CALENDAR)
    print("[calendar] Organization calendar written to global memory")

    await container.rule_engine.seed_defaults()
    await container.hook_engine.seed_defaults()
    print("[rules/hooks] Default rules and hooks seeded")
    created_skills = await seed_default_skills(store)
    print(f"[skills] Executable baseline Skills ready ({created_skills} newly added)")

    if container.mongo is not None:
        await container.mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
