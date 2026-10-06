"""Human reviews must be submitted in full."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_review_rejects_missing_verdicts(fresh_container):
    c = fresh_container
    await c.store.insert_review_order({
        "_id": "review-1", "dept_id": "dept_test", "status": "pending",
        "qa_pairs": [{"question": "q1"}, {"question": "q2"}],
    })
    with pytest.raises(ValueError, match="Every question must be reviewed"):
        await c.review_engine.submit_review("review-1", [{"index": 0, "correct": True}], "admin")
    order = await c.store.get_review_order("review-1")
    assert order["status"] == "pending"


@pytest.mark.asyncio
async def test_review_error_becomes_trace_linked_feedback(fresh_container):
    c = fresh_container
    await c.store.upsert_department({"_id": "dept_test", "name": "Test Department"})
    await c.store.insert_review_order({
        "_id": "review-2", "dept_id": "dept_test", "status": "pending",
        "qa_pairs": [{
            "question": "What is the deadline?", "answer": "wrong answer", "trace_id": "trace-review-2",
            "expected": "correct answer", "citations": [], "confidence": 0.5,
        }],
    })
    await c.review_engine.submit_review(
        "review-2", [{"index": 0, "correct": False, "correction": "correct answer"}], "admin"
    )
    pending = await c.feedback_collector.pending()
    correction = next(f for f in pending if f.get("signal") == "correction")
    assert correction["detail"]["review_order_id"] == "review-2"
    assert correction["detail"]["trace_id"] == "trace-review-2"
