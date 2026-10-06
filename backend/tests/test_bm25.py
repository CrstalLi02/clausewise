"""Tests for BM25 retrieval."""
from __future__ import annotations

from app.retrieval.bm25 import BM25Index, tokenize


def test_tokenize_english():
    tokens = tokenize("Undergraduate Course Registration Rules")
    assert "course" in tokens and "registration" in tokens


def test_bm25_search():
    idx = BM25Index()
    docs = [
        {"_id": "c1", "dept_id": "dept_jwc", "content": "Undergraduate course registration for the next semester is completed during weeks 16 to 18 of each semester."},
        {"_id": "c2", "dept_id": "dept_jwc", "content": "Course withdrawal applications must be submitted within two weeks after classes begin."},
        {"_id": "c3", "dept_id": "dept_cwc", "content": "The tuition payment deadline is before the start of each semester."},
    ]
    idx.index(docs)
    hits = idx.search("course registration", top_k=2)
    assert hits, "Should return retrieval results"
    assert hits[0]["id"] == "c1"


def test_bm25_dept_filter():
    idx = BM25Index()
    docs = [
        {"_id": "c1", "dept_id": "dept_jwc", "content": "Clauses related to course registration."},
        {"_id": "c2", "dept_id": "dept_cwc", "content": "Clauses related to course registration payment."},
    ]
    idx.index(docs)
    hits = idx.search("registration", top_k=5, dept_id="dept_jwc")
    assert all(h["dept_id"] == "dept_jwc" for h in hits)


def test_bm25_filters_before_topk():
    idx = BM25Index()
    docs = [
        {"_id": f"other-{i}", "dept_id": "dept_other", "content": "registration registration registration"}
        for i in range(25)
    ]
    docs.append({"_id": "target", "dept_id": "dept_jwc", "content": "registration"})
    idx.index(docs)
    hits = idx.search("registration", top_k=5, dept_id="dept_jwc")
    assert [h["id"] for h in hits] == ["target"]
