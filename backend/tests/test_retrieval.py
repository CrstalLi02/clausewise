"""Tests for hybrid retrieval (in-memory vectors + BM25 + heuristic reranking)."""
from __future__ import annotations

import pytest

from app.retrieval.bm25 import BM25Index
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import HeuristicReranker
from app.retrieval.vector_store import MemoryVectorStore
from app.storage.store import MemoryStore


@pytest.mark.asyncio
async def test_hybrid_retrieve(embeddings):
    bm25 = BM25Index()
    vs = MemoryVectorStore()
    docs = [
        {"_id": "c1", "doc_id": "d1", "dept_id": "dept_jwc", "chunk_index": 0, "content": "The undergraduate course registration rules specify the registration period."},
        {"_id": "c2", "doc_id": "d2", "dept_id": "dept_jwc", "chunk_index": 0, "content": "Course withdrawal must be requested within two weeks after classes begin."},
        {"_id": "c3", "doc_id": "d3", "dept_id": "dept_cwc", "chunk_index": 0, "content": "Tuition payment methods and schedule."},
    ]
    bm25.index(docs)
    vecs = await embeddings.embed([d["content"] for d in docs])
    for d, v in zip(docs, vecs):
        await vs.add(d["_id"], v, {"doc_id": d["doc_id"], "dept_id": d["dept_id"]})

    hybrid = HybridRetriever(bm25=bm25, vector_store=vs, reranker=HeuristicReranker(), top_k=3)
    query_vec = await embeddings.embed_query("When is the course registration period")
    hits = await hybrid.retrieve("When is the course registration period", query_vec)
    assert hits, "Should return retrieval results"
    assert hits[0]["id"] in {"c1", "c2", "c3"}


@pytest.mark.asyncio
async def test_vector_store_cosine(embeddings):
    vs = MemoryVectorStore()
    v = await embeddings.embed(["Undergraduate Course Registration Rules"])
    await vs.add("a", v[0], {"dept_id": "dept_jwc"})
    hits = await vs.search(v[0], top_k=1)
    assert hits and hits[0]["id"] == "a"
    assert hits[0]["score"] > 0.9


@pytest.mark.asyncio
async def test_retrieval_hydrates_vector_only_hit_and_filters_archived(embeddings):
    from app.harness.agents.retrieval_agent import RetrievalAgent

    store = MemoryStore()
    bm25 = BM25Index()
    vs = MemoryVectorStore()
    hybrid = HybridRetriever(bm25=bm25, vector_store=vs, reranker=HeuristicReranker(), top_k=5)
    agent = RetrievalAgent(hybrid, embeddings, store)
    for doc_id, status in (("active-doc", "active"), ("old-doc", "archived")):
        await store.insert_document({"_id": doc_id, "dept_id": "dept_jwc", "title": doc_id, "status": status})
        chunk = {
            "_id": f"{doc_id}:0", "doc_id": doc_id, "dept_id": "dept_jwc",
            "chunk_index": 0, "content": "The graduate thesis proposal must be at least five thousand words", "keywords": ["proposal"],
            "section_path": [], "section_title": "Requirements",
        }
        await store.insert_chunks([chunk])
        vector = await embeddings.embed_query(chunk["content"])
        await vs.add(chunk["_id"], vector, {"doc_id": doc_id, "dept_id": "dept_jwc", "chunk_index": 0})
    hits = await agent.retrieve(["The graduate thesis proposal must be at least five thousand words"], ["dept_jwc"], top_k=5)
    assert len(hits) == 1
    assert hits[0]["doc_id"] == "active-doc"
    assert hits[0]["content"]
