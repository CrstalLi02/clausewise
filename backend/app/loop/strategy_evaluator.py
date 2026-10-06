"""Policy sandbox: re-runs baseline and candidate Skills on the same historical questions and records the comparison."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.harness.base import Intent
from app.loop.skill_executor import SkillPlan


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrategyEvaluator:
    def __init__(self, retrieval_agent, answer_agent, verifier_agent, rule_engine, skill_executor) -> None:
        self.retrieval = retrieval_agent
        self.answer = answer_agent
        self.verifier = verifier_agent
        self.rules = rule_engine
        self.executor = skill_executor

    async def replay_skill(self, skill: dict[str, Any], traces: list[dict[str, Any]], limit: int = 20) -> dict[str, Any]:
        patterns = skill.get("trigger", {}).get("intent_patterns", [])
        cases = [t for t in traces if any(p and p in t.get("query", "") for p in patterns)][:limit]
        baseline_scores: list[float] = []
        candidate_scores: list[float] = []
        details: list[dict[str, Any]] = []
        for trace in cases:
            query = trace.get("query", "")
            depts = (trace.get("intent") or {}).get("depts") or None
            rules = await self.rules.active_rules(depts)
            intent = Intent(type=(trace.get("intent") or {}).get("type", "other"), depts=depts or [])

            base_chunks = await self.retrieval.retrieve([query], depts, top_k=self.executor.default_top_k)
            base_answer = await self.answer.generate(query, base_chunks, rules=rules, intent=intent)
            base_verdict = await self.verifier.verify(query, base_answer, base_chunks)

            plan = SkillPlan(queries=[query], top_k=self.executor.default_top_k)
            self.executor._execute_workflow(plan, skill, query)
            candidate_chunks = await self.retrieval.retrieve(
                list(dict.fromkeys(plan.queries)), depts, top_k=plan.top_k
            )
            candidate_answer = await self.answer.generate(
                query, candidate_chunks, rules=rules, intent=intent,
                extra_instructions="; ".join(plan.instructions),
            )
            candidate_verdict = await self.verifier.verify(query, candidate_answer, candidate_chunks)
            base_score = float(base_verdict.score)
            candidate_score = float(candidate_verdict.score)
            baseline_scores.append(base_score)
            candidate_scores.append(candidate_score)
            details.append({
                "trace_id": trace.get("_id"), "query": query,
                "baseline_score": base_score, "candidate_score": candidate_score,
                "baseline_passed": base_verdict.passed, "candidate_passed": candidate_verdict.passed,
                "baseline_retrieved": len(base_chunks), "candidate_retrieved": len(candidate_chunks),
            })
        n = len(cases)
        baseline = sum(baseline_scores) / n if n else 0.0
        candidate = sum(candidate_scores) / n if n else 0.0
        return {
            "sample_count": n, "baseline_score": round(baseline, 4),
            "candidate_score": round(candidate, 4), "delta": round(candidate - baseline, 4),
            "passed": n > 0 and candidate >= baseline, "details": details, "created_at": _now(),
        }
