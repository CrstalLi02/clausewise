"""Tests for department agent isolation, parallel partial success, and shared vectors."""
from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.integrations.dept_agent_client import DepartmentAgentClient
from app.retrieval.vector_store import MongoVectorStore
from app.storage.store import MemoryStore


@pytest.mark.asyncio
async def test_department_client_parallel_partial_success(monkeypatch):
    client = DepartmentAgentClient(Settings(dept_agents_enabled=True, dept_id=""))
    active = 0
    peak = 0

    async def fake(query, dept_id, session_id, user_id, memory_context=""):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        if dept_id == "dept_cwc":
            raise TimeoutError("timeout")
        return {"answer": dept_id, "dept_ids": [dept_id]}

    monkeypatch.setattr(client, "_answer_one", fake)
    results, failed = await client.answer_many(
        "leave of absence refund", ["dept_jwc", "dept_cwc"], "s1", "u1", "Previous topic: leave of absence"
    )
    assert peak == 2
    assert results[0]["dept_ids"] == ["dept_jwc"]
    assert failed == ["dept_cwc"]


@pytest.mark.asyncio
async def test_orchestrator_enforces_dept_id(fresh_container):
    c = fresh_container
    c.settings.dept_id = "dept_jwc"
    with pytest.raises(PermissionError):
        await c.orchestrator.answer("tuition", dept_ids=["dept_cwc"])


@pytest.mark.asyncio
async def test_mongo_vector_store_is_shared():
    store = MemoryStore()
    writer = MongoVectorStore(store)
    reader = MongoVectorStore(store)
    await writer.add("c1", [1.0, 0.0], {"doc_id": "d1", "dept_id": "dept_jwc"})
    hits = await reader.search([1.0, 0.0], dept_id="dept_jwc")
    assert hits and hits[0]["id"] == "c1"
    await reader.delete_by_doc("d1")
    assert await writer.count() == 0
