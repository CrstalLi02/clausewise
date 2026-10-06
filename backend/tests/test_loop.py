"""Tests for the Loop layer (rule/hook engines + Skill Miner clustering)."""
from __future__ import annotations

import pytest

from app.harness.base import Intent
from app.loop.hook_engine import HookEngine
from app.loop.rule_engine import RuleEngine
from app.loop.skill_miner import SkillMiner
from app.storage.store import MemoryStore


@pytest.mark.asyncio
async def test_rule_engine_seed_and_active():
    store = MemoryStore()
    engine = RuleEngine(store)
    await engine.seed_defaults()
    rules = await engine.active_rules()
    assert any(r["name"] == "no_guess_rule" for r in rules)


@pytest.mark.asyncio
async def test_hook_engine_apply():
    store = MemoryStore()
    engine = HookEngine(store)
    await engine.seed_defaults()
    hooks = await engine.active_hooks()
    intent = Intent(type="process_guide", depts=["dept_jwc"], raw={"query": "How do I handle course registration and payment"})
    depts = await engine.apply(hooks, intent, ["dept_jwc"])
    assert "dept_cwc" in depts  # cross_dept_hook expands to the Finance Office


def test_skill_miner_cluster():
    miner = SkillMiner(MemoryStore(), llm=None, min_cluster=2)
    queries = ["What is the course registration time", "When does course registration start", "How do I withdraw from a course", "What is the course withdrawal process"]
    # Approximate with hash vectors (only the dimensions need to match)
    vecs = [[0.1, 0.2], [0.1, 0.25], [0.9, 0.8], [0.9, 0.85]]
    clusters = miner.cluster(queries, vecs)
    assert clusters  # At least one cluster


def test_skill_miner_keyword_fallback():
    miner = SkillMiner(MemoryStore(), llm=None, min_cluster=2)
    queries = ["course registration time", "course registration start date", "course registration deadline"]
    clusters = miner._keyword_group(queries)
    assert clusters
