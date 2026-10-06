"""End-to-end smoke test: ingest → retrieve → answer (fully offline, no real LLM / external services)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ingest_and_answer(fresh_container, tmp_path):
    c = fresh_container
    await c.store.upsert_department(
        {
            "_id": "dept_jwc",
            "name": "Academic Affairs Office",
            "admin_users": [],
            "agent_config": {"model": "deepseek-v4-flash", "temperature": 0.1},
        }
    )

    # Write and ingest a document
    doc_file = tmp_path / "course_registration_rules.txt"
    doc_file.write_text("Chapter 1 Course Registration\nArticle 1 Students must complete course registration for the next semester during weeks 16 to 18 of each semester.", encoding="utf-8")
    doc = await c.indexer.ingest(doc_file, dept_id="dept_jwc", uploaded_by="test")
    assert doc["chunk_count"] >= 1
    assert doc["vector_status"] == "ready"

    # Q&A (no LLM configured → every agent falls back automatically and still produces a cited answer)
    result = await c.orchestrator.answer("When is course registration?", user_id="u1", dept_ids=["dept_jwc"])
    assert result["answer"]
    assert result["session_id"]
    events = await c.episodic_memory.session_events(result["session_id"], "u1")
    assert [event["type"] for event in events] == ["user_message", "assistant_message"]
    summary = await c.episodic_memory.get_summary(result["session_id"], "u1")
    assert summary and summary["summary"]


@pytest.mark.asyncio
async def test_loop_cycle_offline(fresh_container):
    c = fresh_container
    await c.rule_engine.seed_defaults()
    await c.hook_engine.seed_defaults()
    # Submit one thumbs-down feedback and trigger a cycle (runs offline)
    await c.feedback_collector.collect_explicit("s1", "u1", "How do I withdraw from a course", "answer", "down")
    report = await c.loop_engine.run_cycle()
    assert "observed" in report
