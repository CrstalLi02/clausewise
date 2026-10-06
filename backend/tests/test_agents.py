"""Tests for the agents' no-LLM fallback logic."""
from __future__ import annotations

from app.harness.base import Answer, VerificationResult
from app.harness.agents.intent_agent import IntentAgent
from app.harness.agents.query_rewriter import QueryRewriter
from app.harness.agents.verifier_agent import VerifierAgent


class _FakeLLM:
    """Fake LLM whose complete raises, to test fallbacks."""

    def __init__(self):
        self.calls = 0

    async def complete(self, *a, **kw):
        self.calls += 1
        raise RuntimeError("no llm")

    async def complete_json(self, *a, **kw):
        self.calls += 1
        raise RuntimeError("no llm")


def test_intent_fallback():
    store = _MemStore()
    agent = IntentAgent(_FakeLLM(), store)
    import asyncio

    intent = asyncio.run(agent.infer("In which week is the course withdrawal deadline?", "u1", "Previous topic: course withdrawal"))
    assert intent.type == "deadline_query"
    assert "dept_jwc" in intent.depts


def test_query_rewriter_fallback():
    store = _MemStore()
    rw = QueryRewriter(_FakeLLM(), store)
    import asyncio

    queries = asyncio.run(rw.rewrite("How do I withdraw from a course", None))
    assert queries and queries[0] == "How do I withdraw from a course"


def test_verifier_heuristic():
    v = VerifierAgent(_FakeLLM())
    import asyncio

    answer = Answer(content="According to the rules, courses must be withdrawn before week 8", citations=[])
    result = asyncio.run(v.verify("course withdrawal time", answer, []))
    assert isinstance(result, VerificationResult)


class _MemStore:
    async def list_departments(self):
        return [{"_id": "dept_jwc", "name": "Academic Affairs Office"}, {"_id": "dept_cwc", "name": "Finance Office"}]

    async def get_user_profile(self, user_id):
        return None

    async def list_glossary(self):
        return []
