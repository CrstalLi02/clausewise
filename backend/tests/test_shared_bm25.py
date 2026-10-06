from __future__ import annotations

import pytest

from app.retrieval.bm25 import SharedBM25Index
from app.storage.store import MemoryStore


@pytest.mark.asyncio
async def test_shared_bm25_reads_latest_active_chunks():
    store = MemoryStore()
    index = SharedBM25Index(store)
    await store.insert_document({"_id": "d1", "dept_id": "dept_jwc", "status": "active"})
    await store.insert_chunks([{"_id": "c1", "doc_id": "d1", "dept_id": "dept_jwc", "content": "graduate thesis proposal deadline"}])
    assert (await index.search("proposal deadline", dept_id="dept_jwc"))[0]["id"] == "c1"
    await store.update_document("d1", {"status": "archived"})
    assert await index.search("proposal deadline", dept_id="dept_jwc") == []
