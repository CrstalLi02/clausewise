"""Tests for persistent job state in the async queue."""
from __future__ import annotations

import pytest

from app.storage.job_queue import JobQueue
from app.storage.redis_store import MemorySessionStore
from app.storage.store import MemoryStore


@pytest.mark.asyncio
async def test_job_queue_memory_fallback():
    store = MemoryStore()
    queue = JobQueue(store, MemorySessionStore(), "jobs")
    job = await queue.enqueue("run_loop", {"requested_by": "admin"})
    pending = await queue.next_jobs()
    assert pending[0]["_id"] == job["_id"]
    assert pending[0]["status"] == "running"
    assert (await store.get("async_jobs", job["_id"]))["status"] == "running"
    await queue.update_progress(job["_id"], {"stage": "reflect", "detail": "attributing"})
    progressing = await store.get("async_jobs", job["_id"])
    assert progressing["progress"]["stage"] == "reflect"
    await queue.finish(job, "completed", {"observed": 1})
    saved = await store.get("async_jobs", job["_id"])
    assert saved["status"] == "completed"
