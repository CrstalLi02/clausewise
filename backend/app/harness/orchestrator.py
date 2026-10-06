"""Orchestrator: the master scheduler that orchestrates the multi-agent DAG for one Q&A exchange.

Flow: load Skills/Hooks/Rules → FAQ cache → Intent → Hook expansion → Rewrite → Retrieve
      → Answer → Verify (up to 2 rewrites) → return answer + citations + trace.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from app.config import Settings
from app.harness.agents.answer_agent import AnswerAgent
from app.harness.agents.dept_router import DeptRouter
from app.harness.agents.feedback_agent import FeedbackAgent
from app.harness.agents.intent_agent import IntentAgent
from app.harness.agents.query_rewriter import QueryRewriter
from app.harness.agents.retrieval_agent import RetrievalAgent
from app.harness.agents.verifier_agent import VerifierAgent
from app.harness.base import Answer, Citation
from app.integrations.pi_client import PiAgentClient
from app.integrations.dept_agent_client import DepartmentAgentClient
from app.loop.hook_engine import HookEngine
from app.loop.loop_engine import LoopEngine
from app.loop.rule_engine import RuleEngine
from app.loop.skill_executor import SkillExecutor
from app.memory.department import DepartmentMemory
from app.memory.user import UserMemory
from app.memory.working import WorkingMemory
from app.memory.episodic import EpisodicMemory
from app.memory.organization import OrganizationMemory
from app.memory.context_builder import MemoryContext, MemoryContextBuilder
from app.storage.store import DataStore
from app.utils.logging import get_logger
from app.utils import metrics

logger = get_logger(__name__)

MAX_VERIFY_RETRY = 2


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        store: DataStore,
        working_memory: WorkingMemory,
        user_memory: UserMemory,
        dept_memory: DepartmentMemory,
        episodic_memory: EpisodicMemory,
        memory_context_builder: MemoryContextBuilder,
        organization_memory: OrganizationMemory,
        intent_agent: IntentAgent,
        dept_router: DeptRouter,
        query_rewriter: QueryRewriter,
        retrieval_agent: RetrievalAgent,
        answer_agent: AnswerAgent,
        verifier_agent: VerifierAgent,
        feedback_agent: FeedbackAgent,
        loop_engine: LoopEngine,
        hook_engine: HookEngine,
        rule_engine: RuleEngine,
        skill_executor: SkillExecutor,
        dept_agent_client: Optional[DepartmentAgentClient] = None,
        pi_client: Optional[PiAgentClient] = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.working_memory = working_memory
        self.user_memory = user_memory
        self.dept_memory = dept_memory
        self.episodic_memory = episodic_memory
        self.memory_context_builder = memory_context_builder
        self.organization_memory = organization_memory
        self.intent_agent = intent_agent
        self.dept_router = dept_router
        self.query_rewriter = query_rewriter
        self.retrieval_agent = retrieval_agent
        self.answer_agent = answer_agent
        self.verifier_agent = verifier_agent
        self.feedback_agent = feedback_agent
        self.loop_engine = loop_engine
        self.hook_engine = hook_engine
        self.rule_engine = rule_engine
        self.skill_executor = skill_executor
        self.dept_agent_client = dept_agent_client
        self.pi_client = pi_client

    async def answer(
        self,
        query: str,
        session_id: str = "",
        user_id: str = "anonymous",
        dept_ids: Optional[list[str]] = None,
        external_memory_context: str = "",
    ) -> dict[str, Any]:
        session_id = session_id or uuid.uuid4().hex
        started = time.perf_counter()

        # 0. Automatic department routing (when the user specifies no department, DeptRouter picks the best match)
        route: Optional[dict[str, Any]] = None
        effective_dept_ids = dept_ids
        if self.settings.dept_id:
            if effective_dept_ids and any(d != self.settings.dept_id for d in effective_dept_ids):
                raise PermissionError("Department agents may not handle requests for other departments")
            effective_dept_ids = [self.settings.dept_id]
        if not effective_dept_ids:
            route = await self.dept_router.route(query)
            effective_dept_ids = route.get("dept_ids") or None

        # Session/episodic memory: append-only record of user input, and build the first-stage context.
        previous = await self.working_memory.history(session_id)
        if previous and previous[-1].get("role") == "assistant":
            # A follow-up question in the same session is weak negative feedback; the Loop later weighs it together with explicit feedback.
            await self.loop_engine.feedback_collector.collect_implicit(
                session_id, user_id, query, previous[-1].get("content", ""), "follow_up",
                {"previous_answer": previous[-1].get("content", "")},
            )
        await self.working_memory.append_message(session_id, "user", query)
        await self.episodic_memory.append_event(session_id, user_id, "user_message", query)
        initial_memory = await self.memory_context_builder.build(
            session_id, user_id, query, effective_dept_ids, include_organization=False
        )

        # 1. Load dynamic Hooks; Rules are loaded once the department scope is determined.
        hooks = await self.hook_engine.active_hooks()

        # 3. Intent
        initial_prompt = "\n".join(text for text in [external_memory_context, initial_memory.prompt_text()] if text)
        intent = await self.intent_agent.infer(query, user_id, initial_prompt)
        intent.raw["query"] = query
        await self.working_memory.set_intent(session_id, intent.raw)

        # 4. Hook expansion (cross-department collaboration)
        resolved_depts = list(effective_dept_ids or intent.depts)
        matched_hooks = self.hook_engine.evaluate(hooks, query, intent)
        resolved_depts = await self.hook_engine.apply(matched_hooks, intent, resolved_depts)
        rules = await self.rule_engine.active_rules(resolved_depts)
        memory_context = await self.memory_context_builder.build(
            session_id, user_id, query, resolved_depts, role=intent.user_role, include_organization=True
        )
        memory_prompt = "\n".join(text for text in [external_memory_context, memory_context.prompt_text()] if text)

        if self.dept_agent_client is not None and self.dept_agent_client.enabled and resolved_depts:
            sub_answers, failed = await self.dept_agent_client.answer_many(
                query, resolved_depts, session_id, user_id, memory_prompt
            )
            if sub_answers:
                degraded: list[str] = []
                if failed:
                    fallback_chunks = await self.retrieval_agent.retrieve([query], failed, top_k=self.settings.hybrid_topk)
                    fallback_rules = await self.rule_engine.active_rules(failed)
                    fallback = await self.answer_agent.generate(query, fallback_chunks, rules=fallback_rules, intent=intent)
                    fallback = await self._enrich_citations(fallback)
                    if fallback.content:
                        sub_answers.append({
                            "answer": fallback.content, "citations": [c.to_dict() for c in fallback.citations],
                            "dept_ids": failed, "confidence": fallback.confidence,
                        })
                        degraded = list(failed)
                        failed = []
                merged = self._merge_department_answers(sub_answers, failed, degraded)
                trace_id = await self._finalize(session_id, user_id, query, merged, intent.type, [], started)
                await self.memory_context_builder.record_usage(memory_context, session_id, trace_id, user_id)
                return self._to_response(session_id, merged, [], intent.type, route=route)

        # 5. Query Rewrite
        queries = await self.query_rewriter.rewrite(query, intent, memory_prompt)
        matched_skills = await self.skill_executor.matching(query, resolved_depts)
        skill_plan = await self.skill_executor.prepare(
            query, queries, matched_skills, session_id=session_id, user_id=user_id
        )

        # 6. Retrieval
        chunks = await self.retrieval_agent.retrieve(skill_plan.queries, resolved_depts, top_k=skill_plan.top_k)
        # Organizational memory can only guide re-checking of official facts; its source chunks are deduplicated together with regular retrieval evidence.
        retrieved_chunks = list(chunks)
        chunks = []
        seen_chunks: set[str] = set()
        for source_chunk in memory_context.evidence_chunks:
            chunk_id = source_chunk.get("_id") or source_chunk.get("id")
            if chunk_id and chunk_id not in seen_chunks:
                chunks.append(source_chunk)
                seen_chunks.add(chunk_id)
        for retrieved in retrieved_chunks:
            chunk_id = retrieved.get("_id") or retrieved.get("id")
            if chunk_id and chunk_id not in seen_chunks:
                chunks.append(retrieved)
                seen_chunks.add(chunk_id)
        chunks = chunks[: skill_plan.top_k]
        await self.working_memory.set_retrieved(session_id, chunks)

        # 7. Answer (injecting the actual execution results of the Skill workflow)
        skill_hints = "；".join(skill_plan.instructions)
        answer = await self.answer_agent.generate(
            query, chunks, rules=rules, intent=intent, extra_instructions=skill_hints,
            memory_context=memory_prompt,
        )
        answer = await self._enrich_citations(answer)

        # 8. Verify (up to 2 rewrites)
        for _ in range(MAX_VERIFY_RETRY):
            verdict = await self.verifier_agent.verify(query, answer, chunks)
            answer.verification = verdict.to_dict()
            if verdict.passed:
                break
            logger.info("Answer verification failed, sending back for rewrite: %s", verdict.issues)
            answer = await self.answer_agent.generate(
                query, chunks, rules=rules, intent=intent,
                extra_instructions="The previous answer had the following issues; please fix them: " + "; ".join(verdict.issues),
                memory_context=memory_prompt,
            )
            answer = await self._enrich_citations(answer)

        # 8.5 Update metrics of the matched Skills (trigger count + success rate)
        if matched_skills:
            await self._record_skill_usage(matched_skills, answer.verification.get("passed", True))

        # 9. Wrap up: working memory / trace / automatic feedback / user & department memory
        trace_id = await self._finalize(session_id, user_id, query, answer, intent.type, chunks, started)
        await self.skill_executor.record_outcome(
            skill_plan.execution_ids, answer.verification.get("passed", True), trace_id
        )
        await self.memory_context_builder.record_usage(memory_context, session_id, trace_id, user_id)
        return self._to_response(session_id, answer, chunks, intent.type, route=route)

    async def answer_stream(self, query: str, session_id: str, user_id: str = "anonymous") -> AsyncIterator[str]:
        """SSE streaming: reuses the full orchestration of answer, but streams the answer content in chunks."""
        result = await self.answer(query, session_id=session_id, user_id=user_id)
        content = result["answer"]
        # Simple chunking (true streaming could hook the LLM stream into the Answer Agent layer)
        for i in range(0, len(content), 16):
            yield content[i : i + 16]

    @staticmethod
    def _merge_department_answers(
        results: list[dict[str, Any]], failed: list[str], degraded: Optional[list[str]] = None
    ) -> Answer:
        sections: list[str] = []
        citations: list[Citation] = []
        dept_ids: list[str] = []
        scores: list[float] = []
        for item in results:
            current = list(item.get("dept_ids") or [])
            dept_ids.extend(current)
            label = ", ".join(current) or "Relevant departments"
            sections.append(f"[{label}]\n{item.get('answer', '')}")
            scores.append(float(item.get("confidence", 0.0)))
            for c in item.get("citations") or []:
                citations.append(Citation(
                    doc_id=c.get("doc_id", ""), doc_title=c.get("doc_title", ""),
                    dept_id=c.get("dept_id", ""), chunk_index=c.get("chunk_index", 0),
                    section_path=c.get("section_path", []), snippet=c.get("snippet", ""),
                ))
        if failed:
            sections.append("The following departments are temporarily unavailable; results from the other departments are returned: " + ", ".join(failed))
        if degraded:
            sections.append("The following department services timed out; a degraded answer from shared retrieval is used: " + ", ".join(degraded))
        return Answer(
            content="\n\n".join(sections), citations=citations,
            dept_ids=sorted(set(dept_ids)), confidence=sum(scores) / len(scores) if scores else 0.0,
            verification={
                "passed": bool(results), "partial": bool(failed),
                "failed_departments": failed, "degraded_departments": degraded or [],
            },
        )

    # ---------- Internal ----------
    async def _match_active_skills(self, query: str) -> list[dict[str, Any]]:
        """Match active Skills by intent keywords."""
        skills = await self.store.list_skills(status="active")
        q = query.lower()
        return [s for s in skills if any(p and p.lower() in q for p in s.get("trigger", {}).get("intent_patterns", []))]

    @staticmethod
    def _skill_hint_text(matched: list[dict[str, Any]]) -> str:
        if not matched:
            return ""
        return "Additional requirements: " + "; ".join(
            f"Matched skill [{s.get('name', '')}], handle as {s.get('action', {}).get('type', 'workflow')}" for s in matched
        )

    async def _record_skill_usage(self, matched_skills: list[dict[str, Any]], passed: bool) -> None:
        """Update metrics of matched Skills: trigger count + success count + success rate + last triggered time."""
        now = datetime.now(timezone.utc).isoformat()
        for s in matched_skills:
            metrics.SKILL_TRIGGER.labels(skill=s.get("name", s.get("_id", ""))).inc()
            m = dict(s.get("metrics") or {})
            m["trigger_count"] = int(m.get("trigger_count", 0)) + 1
            m["success_count"] = int(m.get("success_count", 0)) + (1 if passed else 0)
            m["success_rate"] = round(m["success_count"] / m["trigger_count"], 4)
            m["last_triggered"] = now
            s["metrics"] = m
            await self.store.upsert_skill(s)

    @staticmethod
    def _answer_from_pi(pi_result: dict[str, Any]) -> Answer:
        """Convert the result returned by the pi service into an Answer."""
        citations = [
            Citation(
                doc_id=c.get("doc_id", ""),
                doc_title=c.get("doc_title", ""),
                dept_id=c.get("dept_id", ""),
                chunk_index=c.get("chunk_index", 0),
                section_path=c.get("section_path", []),
                snippet=c.get("snippet", ""),
            )
            for c in pi_result.get("citations", [])
        ]
        return Answer(
            content=pi_result.get("answer", ""),
            citations=citations,
            dept_ids=pi_result.get("deptIds", []),
            confidence=float(pi_result.get("confidence", 0.8)),
            verification=pi_result.get("verification", {}),
        )

    async def _enrich_citations(self, answer: Answer) -> Answer:
        """Fill in document titles and department info for citations."""
        for c in answer.citations:
            if c.doc_id and not c.doc_title:
                doc = await self.store.get_document(c.doc_id)
                if doc:
                    c.doc_title = doc.get("title", c.doc_title)
                    c.dept_id = doc.get("dept_id", c.dept_id)
        return answer

    async def _finalize(
        self,
        session_id: str,
        user_id: str,
        query: str,
        answer: Answer,
        intent_type: str,
        chunks: list[dict[str, Any]],
        started: float,
    ) -> str:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await self.working_memory.append_message(session_id, "assistant", answer.content)

        # Automatic feedback (Verifier result)
        signal = "verifier_pass" if answer.verification.get("passed", True) else "verifier_fail"
        await self.feedback_agent.collect(
            session_id=session_id,
            user_id=user_id,
            query=query,
            answer=answer,
            signal=signal,
            kind="auto",
            intent_type=intent_type,
        )

        # Trace (for Loop replay)
        trace = {
                "session_id": session_id,
                "user_id": user_id,
                "query": query,
                "intent": {"type": intent_type, "depts": answer.dept_ids},
                "retrieved_chunks": chunks[:10],
                "answer": answer.content,
                "citations": [c.to_dict() for c in answer.citations],
                "verification": answer.verification,
                "latency_ms": latency_ms,
                "cost": 0.0,
                "success": answer.verification.get("passed", True),
            }
        await self.loop_engine.record_trace(trace)
        await self.episodic_memory.append_event(
            session_id, user_id, "assistant_message", answer.content, dept_ids=answer.dept_ids,
            trace_id=trace["_id"], metadata={"citations": [c.to_dict() for c in answer.citations]},
        )
        # Deterministic rolling summary to avoid an extra LLM call; an async summarizer could improve quality later.
        context = await self.working_memory.get_context(session_id)
        recent = context.get("messages", [])[-4:]
        summary = " | ".join(f"{m.get('role')}:{m.get('content', '')[:240]}" for m in recent)
        await self.working_memory.set_summary(session_id, summary)
        await self.episodic_memory.update_summary(
            session_id, user_id, summary, entities=context.get("entities") or {},
            citation_ids=[c.to_dict().get("doc_id", "") + ":" + str(c.to_dict().get("chunk_index", 0)) for c in answer.citations],
        )

        # User memory / department hot topics
        await self.user_memory.record_query(user_id, query, intent_type)
        for dept_id in answer.dept_ids:
            await self.dept_memory.bump_hot_query(dept_id, query)

        metrics.QUERY_TOTAL.labels(dept=",".join(answer.dept_ids) or "all", intent=intent_type).inc()
        metrics.QUERY_LATENCY.labels(dept=",".join(answer.dept_ids) or "all").observe(latency_ms / 1000.0)
        return trace["_id"]

    @staticmethod
    def _to_response(
        session_id: str,
        answer: Answer,
        chunks: list[dict[str, Any]],
        intent_type: str,
        route: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "answer": answer.content,
            "citations": [c.to_dict() for c in answer.citations],
            "dept_ids": answer.dept_ids,
            "confidence": answer.confidence,
            "intent_type": intent_type,
            "verification": answer.verification,
            "retrieved_count": len(chunks),
            "route": route,
        }
