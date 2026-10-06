"""Core invariants of the fact plane + five memory planes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio

import pytest


async def _seed_fact(container, doc_id="doc1", dept_id="dept_jwc", version="1.0"):
    await container.store.insert_document({
        "_id": doc_id, "dept_id": dept_id, "title": "Course Registration Rules",
        "version": version, "status": "active",
    })
    await container.store.insert_chunks([{
        "_id": f"{doc_id}:0", "doc_id": doc_id, "dept_id": dept_id,
        "chunk_index": 0, "content": "Students must complete course withdrawal before week 8.",
        "section_path": ["Course withdrawal"], "section_title": "Course withdrawal deadline",
    }])


@pytest.mark.asyncio
async def test_fact_plane_only_returns_active_scoped_chunks(fresh_container):
    c = fresh_container
    await _seed_fact(c)
    assert await c.fact_plane.active_chunk("doc1:0", ["dept_jwc"])
    assert await c.fact_plane.active_chunk("doc1:0", ["dept_cwc"]) is None
    await c.store.update_document("doc1", {"status": "archived"})
    assert await c.fact_plane.active_chunk("doc1:0") is None


@pytest.mark.asyncio
async def test_organization_memory_requires_and_rechecks_sources(fresh_container):
    c = fresh_container
    await _seed_fact(c)
    with pytest.raises(ValueError, match="official source"):
        await c.organization_memory.publish(
            "department", "faq", "Course withdrawal", "Before week 8", [], dept_id="dept_jwc"
        )
    item = await c.organization_memory.publish(
        "department", "faq", "Course withdrawal deadline", "Students must complete course withdrawal before week 8",
        [{"doc_id": "doc1", "chunk_id": "doc1:0", "document_version": "1.0"}],
        dept_id="dept_jwc",
    )
    assert (await c.organization_memory.recall("Course withdrawal deadline", ["dept_jwc"]))[0]["_id"] == item["_id"]
    assert await c.organization_memory.recall("Course withdrawal deadline", ["dept_cwc"]) == []
    await c.store.update_document("doc1", {"status": "archived"})
    assert await c.organization_memory.recall("Course withdrawal deadline", ["dept_jwc"]) == []
    assert (await c.store.get("org_memory_items", item["_id"]))["status"] == "stale"


@pytest.mark.asyncio
async def test_user_memory_consent_sensitivity_revision_and_forget(fresh_container):
    c = fresh_container
    with pytest.raises(ValueError, match="Sensitive"):
        await c.user_semantic_memory.remember("u1", "id number", "123456")
    candidate = await c.user_semantic_memory.remember(
        "u1", "answer_style", "concise", source_type="inferred", consent=False
    )
    assert candidate["status"] == "pending"
    first = await c.user_semantic_memory.remember("u1", "answer_style", "concise", actor_id="u1")
    second = await c.user_semantic_memory.remember("u1", "answer_style", "detailed", actor_id="u1")
    assert second["revision"] == 2
    assert (await c.store.get("user_memory_items", first["_id"]))["status"] == "superseded"
    assert await c.user_semantic_memory.forget("u1", second["_id"], "u1")
    assert await c.user_semantic_memory.recall("u1") == []


@pytest.mark.asyncio
async def test_working_memory_stores_chunk_ids_and_context_respects_budget(fresh_container):
    c = fresh_container
    await c.working_memory.append_message("s1", "user", "Course withdrawal deadline")
    await c.working_memory.set_intent("s1", {"depts": ["dept_jwc"], "entities": {"matter": "course withdrawal"}})
    await c.working_memory.set_retrieved("s1", [{"_id": "doc1:0", "content": "must not enter Redis"}])
    state = await c.working_memory.get_context("s1")
    assert state["retrieved"] == ["doc1:0"]
    assert "must not enter Redis" not in str(state)
    await c.user_semantic_memory.remember("u1", "answer_style", "concise")
    context = await c.memory_context_builder.build("s1", "u1", "course withdrawal", ["dept_jwc"])
    assert context.session["entities"]["matter"] == "course withdrawal"
    assert "answer_style" in context.prompt_text()
    assert len(context.prompt_text()) <= c.settings.memory_context_max_chars


@pytest.mark.asyncio
async def test_episodic_sequence_history_and_retention(fresh_container):
    c = fresh_container
    first = await c.episodic_memory.append_event("s1", "u1", "user_message", "question")
    second = await c.episodic_memory.append_event("s1", "u1", "assistant_message", "answer")
    assert (first["seq"], second["seq"]) == (1, 2)
    assert [e["content"] for e in await c.episodic_memory.session_events("s1", "u1")] == ["question", "answer"]
    expired = {
        "_id": "expired", "session_id": "old", "user_id": "u1",
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    await c.store.upsert("conversation_events", expired)
    report = await c.memory_retention.prune_expired()
    assert report["conversation_events"] == 1


@pytest.mark.asyncio
async def test_hot_topics_use_atomic_aggregate(fresh_container):
    c = fresh_container
    await c.dept_memory.bump_hot_query("dept_jwc", "Course withdrawal deadline")
    await c.dept_memory.bump_hot_query("dept_jwc", "Course withdrawal deadline")
    topics = await c.store.find("memory_topics", {"dept_id": "dept_jwc"})
    assert len(topics) == 1 and topics[0]["count"] == 2


@pytest.mark.asyncio
async def test_hot_topics_concurrent_increment(fresh_container):
    c = fresh_container
    await asyncio.gather(*(c.dept_memory.bump_hot_query("dept_jwc", "Course withdrawal deadline") for _ in range(20)))
    topics = await c.store.find("memory_topics", {"dept_id": "dept_jwc"})
    assert topics[0]["count"] == 20


@pytest.mark.asyncio
async def test_memory_usage_and_user_deletion(fresh_container):
    c = fresh_container
    item = await c.user_semantic_memory.remember("u1", "answer_style", "concise")
    context = await c.memory_context_builder.build("s1", "u1", "answer style", [])
    await c.memory_context_builder.record_usage(context, "s1", "trace1", "u1")
    usage = await c.store.find("memory_usage", {"user_id": "u1"})
    assert usage and usage[0]["memory_id"] == item["_id"]
    report = await c.memory_retention.delete_user("u1", "admin")
    assert report["user_memory_items"] == 1
    assert await c.store.find("memory_usage", {"user_id": "u1"}) == []
