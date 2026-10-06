from __future__ import annotations

import pytest

from scripts.migrate_memory import migrate


@pytest.mark.asyncio
async def test_legacy_memory_migration_is_idempotent(fresh_container):
    c = fresh_container
    await c.store.upsert_user_profile({
        "_id": "u1", "prefs": {"answer_style": "concise"},
        "history_queries": ["sensitive raw question"], "feedback_history": [{"signal": "down"}],
    })
    await c.store.upsert("dept_memory", {
        "_id": "dept_jwc", "dept_id": "dept_jwc",
        "faqs": [{"_id": "faq1", "question": "Course withdrawal?", "answer": "Week 8"}],
    })
    first = await migrate(c)
    second = await migrate(c)
    assert first["user_items"] == 1 and second["user_items"] == 0
    assert first["faq_candidates"] == 1 and second["faq_candidates"] == 0
    profile = await c.store.get_user_profile("u1")
    assert "history_queries" not in profile and "feedback_history" not in profile
    assert await c.store.find("org_memory_items") == []
