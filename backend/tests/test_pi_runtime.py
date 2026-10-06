"""Tests for the protocol, priority execution, and fallback from the Python control plane to the pi Agent Runtime."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.harness.agents.answer_agent import AnswerAgent
from app.harness.agents.intent_agent import IntentAgent
from app.harness.agents.query_rewriter import QueryRewriter
from app.harness.agents.verifier_agent import VerifierAgent
from app.harness.base import Answer, Citation
from app.integrations.pi_runtime import PiAgentRuntimeClient
from app.storage.store import MemoryStore


class FakeLLM:
    def __init__(self, json_result=None, text_result="local"):
        self.json_result = json_result or {}
        self.text_result = text_result
        self.calls = 0

    async def complete_json(self, *args, **kwargs):
        self.calls += 1
        return self.json_result

    async def complete(self, *args, **kwargs):
        self.calls += 1
        return self.text_result


class FakePi:
    def __init__(self, json_result=None, text_result=None):
        self.json_result = json_result
        self.text_result = text_result
        self.calls = []

    async def run_json(self, agent_type, system_prompt, prompt, **kwargs):
        self.calls.append((agent_type, kwargs))
        return self.json_result

    async def run_text(self, agent_type, system_prompt, prompt, **kwargs):
        self.calls.append((agent_type, kwargs))
        return self.text_result


@pytest.mark.asyncio
async def test_intent_prefers_pi_without_calling_local_llm():
    store = MemoryStore()
    await store.upsert_department({"_id": "dept_jwc", "name": "Academic Affairs Office"})
    local = FakeLLM(json_result={"type": "other"})
    pi = FakePi(json_result={
        "type": "deadline_query", "depts": ["dept_jwc"], "user_role": "student",
        "entities": {"matter": "course withdrawal"}, "needs_cross_dept": False, "confidence": 0.9,
    })
    intent = await IntentAgent(local, store, pi, 1.0).infer("Course withdrawal deadline", "u1")
    assert intent.type == "deadline_query"
    assert local.calls == 0
    assert pi.calls[0][0] == "intent"


@pytest.mark.asyncio
async def test_rewriter_falls_back_to_local_when_pi_unavailable():
    store = MemoryStore()
    local = FakeLLM(json_result={"queries": ["local rewrite"]})
    pi = FakePi(json_result=None)
    queries = await QueryRewriter(local, store, pi, 1.0).rewrite("course withdrawal")
    assert queries == ["local rewrite"]
    assert local.calls == 1


@pytest.mark.asyncio
async def test_answer_and_verifier_use_pi_outputs():
    store = MemoryStore()
    chunk = {
        "_id": "d1:0", "doc_id": "d1", "dept_id": "dept_jwc",
        "chunk_index": 0, "content": "The course withdrawal deadline is week 8.", "section_path": [],
    }
    local = FakeLLM(text_result="local answer", json_result={"passed": False})
    pi_answer = FakePi(text_result="The course withdrawal deadline is week 8. [Source 1]")
    answer = await AnswerAgent(local, store, pi_answer, 5.0).generate("When can I withdraw from a course", [chunk])
    assert answer.content.startswith("The course withdrawal deadline is week 8")
    assert local.calls == 0

    pi_verify = FakePi(json_result={"passed": True, "score": 0.95, "issues": []})
    verdict = await VerifierAgent(local, pi_verify, 3.0).verify("When can I withdraw from a course", answer, [chunk])
    assert verdict.passed and verdict.score == 0.95
    assert local.calls == 0


def test_pi_runtime_requires_enabled_flag_and_internal_token():
    disabled = PiAgentRuntimeClient(Settings(pi_agent_enabled=False, internal_api_token="token"))
    missing_token = PiAgentRuntimeClient(Settings(pi_agent_enabled=True, internal_api_token=""))
    enabled = PiAgentRuntimeClient(Settings(pi_agent_enabled=True, internal_api_token="token"))
    assert not disabled.enabled
    assert not missing_token.enabled
    assert enabled.enabled
