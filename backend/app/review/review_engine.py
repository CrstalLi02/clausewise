"""Review engine (Human-in-the-loop Review Engine).

Turns the Loop's "humans progressively exit" into an observable process:

1. After a new document is ingested, the LLM automatically generates test questions from its content (building the question bank).
2. The system answers using its own retrieval + generation chain (self-test).
3. A "review order" is generated and sent to the department admin, who judges each question correct/incorrect (accumulating feedback).
4. Once cumulative accuracy exceeds the threshold (default 0.8) with enough samples, the department enters human_out_of_loop,
   human review is disabled, and later new documents pass automatically — a true progressive exit from the Loop.

Department loop_phase has three states:
- human_in_loop    : 100% human review (starting point)
- human_on_loop    : accuracy met but not enough samples yet; still accumulating evidence
- human_out_of_loop: threshold + samples met; human review disabled, the system passes automatically
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import Settings
from app.llm.client import ChatMessage, LLMClient
from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)

QUESTION_PROMPT = """You are a test question generator for school policy documents. Based on the given document content, generate {n} Q&A questions that test the document's core clauses.

Output a JSON array only (no other text):
[
  {{"question": "A specific, verifiable question", "expected": "Key points of the correct answer"}}
]

Requirements:
- Questions focus on core information such as policy clauses, eligibility conditions, milestones, and procedure steps.
- Answers must be directly findable in the document content, specific, and verifiable.
- Different questions cover different topics, avoiding repetition.

Document title: {title}
Document content:
{content}
"""

SELF_ANSWER_SYSTEM = "You are a school policy consultation assistant whose answers are rigorous and well-grounded."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewEngine:
    def __init__(
        self,
        settings: Settings,
        store: DataStore,
        llm: LLMClient,
        retrieval_agent: Any,
        answer_agent: Any,
        rule_engine: Any,
        feedback_collector: Any = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.llm = llm
        self.retrieval_agent = retrieval_agent
        self.answer_agent = answer_agent
        self.rule_engine = rule_engine
        self.feedback_collector = feedback_collector

    # ---------- Question generation ----------
    async def generate_questions(self, doc: dict[str, Any], n: Optional[int] = None) -> list[dict[str, str]]:
        n = n or self.settings.review_question_count
        chunks = await self.store.list_chunks_by_doc(doc["_id"])
        content = self._doc_content(chunks)
        if not content:
            return []
        try:
            msg = ChatMessage.user(QUESTION_PROMPT.format(n=n, title=doc.get("title", ""), content=content))
            data = await self.llm.complete_json(
                [ChatMessage.system("You are a test question generator. Output JSON only."), msg], temperature=0.4, max_tokens=1500
            )
            if isinstance(data, list):
                return [q for q in data if isinstance(q, dict) and q.get("question")][:n]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Test question generation LLM failed (%s), using heuristic fallback", exc)
        return self._heuristic_questions(doc, chunks, n)

    # ---------- Review order generation ----------
    async def create_review_order(self, doc: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Generate a review order for a newly ingested document (auto-generate questions → system answers → send for review)."""
        dept_id = doc.get("dept_id", "")
        questions = await self.generate_questions(doc)
        if not questions:
            logger.info("No test questions generated for document %s, skipping the review order", doc.get("title", ""))
            return None

        qa_pairs: list[dict[str, Any]] = []
        for q in questions:
            answer = await self._self_answer(q["question"], [dept_id] if dept_id else None)
            qa_pairs.append(
                {
                    "question": q["question"],
                    "expected": q.get("expected", ""),
                    "answer": answer["content"],
                    "citations": answer["citations"],
                    "confidence": answer["confidence"],
                    "trace_id": answer.get("trace_id", ""),
                    "verdict": None,   # None | "auto" | "approved" | "rejected"
                    "correct": None,   # None | True | False
                    "correction": "",
                }
            )

        phase = await self.get_dept_phase(dept_id)
        sample_bucket = int(hashlib.sha256(doc.get("_id", "").encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        sampled_review = phase == "human_out_of_loop" and sample_bucket < self.settings.review_sample_rate
        auto = phase == "human_out_of_loop" and not sampled_review
        order: dict[str, Any] = {
            "_id": "review_" + uuid.uuid4().hex,
            "dept_id": dept_id,
            "doc_id": doc.get("_id", ""),
            "doc_title": doc.get("title", ""),
            "status": "auto_approved" if auto else "pending",
            "qa_pairs": qa_pairs,
            "total": len(qa_pairs),
            "correct": len(qa_pairs) if auto else 0,
            "accuracy": 1.0 if auto else None,
            "loop_phase_at_create": phase,
            "sampled_review": sampled_review,
            "created_at": _now(),
            "reviewed_at": _now() if auto else None,
            "reviewed_by": "system(auto)" if auto else None,
        }
        if auto:
            for pair in qa_pairs:
                pair["verdict"] = "auto"
                pair["correct"] = True
            # Also write to the question bank after auto-passing (accumulating feedback)
            for pair in qa_pairs:
                await self._add_test_question(dept_id, doc, pair, verdict="auto", correct=True)

        await self.store.insert_review_order(order)
        logger.info("Generated review order %s (dept=%s, phase=%s, %d questions)", order["_id"], dept_id, phase, len(qa_pairs))
        return order

    # ---------- Review submission ----------
    async def submit_review(
        self, order_id: str, verdicts: list[dict[str, Any]], reviewer: str
    ) -> dict[str, Any]:
        order = await self.store.get_review_order(order_id)
        if order is None:
            raise KeyError(f"Review order not found: {order_id}")
        if order.get("status") not in ("pending",):
            return order

        pairs: list[dict[str, Any]] = order["qa_pairs"]
        by_index = {v.get("index"): v for v in verdicts if isinstance(v.get("index"), int)}
        expected_indexes = set(range(len(pairs)))
        if set(by_index) != expected_indexes:
            missing = sorted(expected_indexes - set(by_index))
            extra = sorted(set(by_index) - expected_indexes)
            raise ValueError(f"Every question must be reviewed; missing={missing}, out of range={extra}")
        correct = 0
        for i, pair in enumerate(pairs):
            v = by_index.get(i)
            assert v is not None
            is_correct = bool(v.get("correct", False))
            pair["verdict"] = "approved" if is_correct else "rejected"
            pair["correct"] = is_correct
            pair["correction"] = v.get("correction", "") if not is_correct else ""
            if is_correct:
                correct += 1
            # Write to the question bank + feedback
            await self._add_test_question(
                order.get("dept_id", ""), {"_id": order.get("doc_id", ""), "title": order.get("doc_title", "")},
                pair, verdict=pair["verdict"], correct=is_correct,
            )
            if not is_correct and self.feedback_collector is not None:
                await self.feedback_collector.collect_explicit(
                    session_id=f"review:{order_id}", user_id=reviewer, query=pair.get("question", ""),
                    answer=pair.get("answer", ""), signal="correction",
                    detail={
                        "source": "review", "review_order_id": order_id,
                        "trace_id": pair.get("trace_id", ""), "dept_id": order.get("dept_id", ""),
                        "correction": pair.get("correction", ""),
                    },
                )

        total = len(pairs)
        accuracy = correct / max(total, 1)
        order["correct"] = correct
        order["accuracy"] = round(accuracy, 4)
        order["status"] = "reviewed"
        order["reviewed_at"] = _now()
        order["reviewed_by"] = reviewer
        await self.store.insert_review_order(order)

        # Update department review stats + progressive exit decision
        dept_id = order.get("dept_id", "")
        await self._update_dept_review_stats(dept_id, total, correct)
        new_phase = await self.maybe_fade_out(dept_id)
        # When an out-of-the-loop spot check finds errors, roll back to human-on-the-loop immediately to stop further auto-passing.
        if order.get("sampled_review") and correct < total:
            dept = await self.store.get_department(dept_id)
            if dept:
                dept["loop_phase"] = "human_on_loop"
                dept["rollback_reason"] = f"Spot-check review order {order_id} found {total - correct} errors"
                dept["updated_at"] = _now()
                await self.store.upsert_department(dept)
                new_phase = "human_on_loop"
        logger.info("Review order %s complete: %d/%d (%.2f), department %s → %s", order_id, correct, total, accuracy, dept_id, new_phase)
        return order

    # ---------- Department review stats and progressive exit ----------
    async def get_dept_phase(self, dept_id: str) -> str:
        dept = await self.store.get_department(dept_id) if dept_id else None
        if dept is None:
            return "human_in_loop"
        return dept.get("loop_phase", "human_in_loop")

    async def dept_review_stats(self, dept_id: str) -> dict[str, Any]:
        dept = await self.store.get_department(dept_id) if dept_id else None
        stats = (dept or {}).get("review_stats") or {"total": 0, "correct": 0, "accuracy": 0.0}
        stats.setdefault("accuracy", stats.get("correct", 0) / max(stats.get("total", 0), 1))
        return stats

    async def _update_dept_review_stats(self, dept_id: str, total: int, correct: int) -> None:
        if not dept_id:
            return
        dept = await self.store.get_department(dept_id)
        if dept is None:
            return
        stats = dept.get("review_stats") or {"total": 0, "correct": 0}
        stats["total"] = stats.get("total", 0) + total
        stats["correct"] = stats.get("correct", 0) + correct
        stats["accuracy"] = round(stats["correct"] / max(stats["total"], 1), 4)
        dept["review_stats"] = stats
        await self.store.upsert_department(dept)

    async def maybe_fade_out(self, dept_id: str) -> str:
        """Advance the department loop_phase based on cumulative accuracy and sample size (humans progressively exit)."""
        if not dept_id:
            return "human_in_loop"
        dept = await self.store.get_department(dept_id)
        if dept is None:
            return "human_in_loop"
        stats = dept.get("review_stats") or {"total": 0, "correct": 0, "accuracy": 0.0}
        accuracy = float(stats.get("accuracy", 0.0))
        samples = int(stats.get("total", 0))
        threshold = self.settings.review_accuracy_threshold
        min_samples = self.settings.review_min_samples

        old_phase = dept.get("loop_phase", "human_in_loop")
        if accuracy >= threshold and samples >= min_samples:
            new_phase = "human_out_of_loop"
        elif accuracy >= threshold:
            new_phase = "human_on_loop"
        else:
            new_phase = "human_in_loop"

        if new_phase != old_phase:
            dept["loop_phase"] = new_phase
            dept["updated_at"] = _now()
            dept["fade_out"] = {
                "achieved_at": _now(),
                "accuracy": accuracy,
                "samples": samples,
                "reason": f"Accuracy {accuracy:.0%} ≥ {threshold:.0%} and samples {samples} ≥ {min_samples}",
            } if new_phase == "human_out_of_loop" else dept.get("fade_out")
            await self.store.upsert_department(dept)
            logger.info("Department %s Loop phase advanced: %s → %s (accuracy=%.2f, samples=%d)", dept_id, old_phase, new_phase, accuracy, samples)
        return new_phase

    # ---------- Internal ----------
    async def _self_answer(self, query: str, dept_ids: Optional[list[str]]) -> dict[str, Any]:
        try:
            chunks = await self.retrieval_agent.retrieve([query], dept_ids, top_k=5)
            rules = await self.rule_engine.active_rules(dept_ids)
            answer = await self.answer_agent.generate(query, chunks, rules=rules)
            trace_id = "trace_review_" + uuid.uuid4().hex
            await self.store.insert_trace({
                "_id": trace_id, "session_id": "review", "user_id": "review_engine",
                "query": query, "intent": {"type": "review", "depts": dept_ids or []},
                "retrieved_chunks": chunks[:10], "answer": answer.content,
                "citations": [c.to_dict() for c in answer.citations], "verification": {},
                "latency_ms": 0, "cost": 0.0, "success": True, "created_at": _now(),
            })
            return {
                "content": answer.content,
                "citations": [c.to_dict() for c in answer.citations],
                "confidence": answer.confidence,
                "trace_id": trace_id,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("System self-test answer failed (%s): %s", query, exc)
            return {"content": "(System self-test answer failed; please judge manually)", "citations": [], "confidence": 0.0}

    async def _add_test_question(
        self, dept_id: str, doc: dict[str, Any], pair: dict[str, Any], verdict: str, correct: bool
    ) -> None:
        await self.store.insert_test_question(
            {
                "_id": "tq_" + uuid.uuid4().hex,
                "dept_id": dept_id,
                "doc_id": doc.get("_id", ""),
                "doc_title": doc.get("title", ""),
                "question": pair.get("question", ""),
                "expected": pair.get("expected", ""),
                "answer": pair.get("answer", ""),
                "verdict": verdict,
                "correct": correct,
                "correction": pair.get("correction", ""),
                "created_at": _now(),
            }
        )

    @staticmethod
    def _doc_content(chunks: list[dict[str, Any]], limit: int = 6000) -> str:
        parts: list[str] = []
        total = 0
        for c in chunks:
            text = c.get("content", "")
            if total + len(text) > limit:
                parts.append(text[: max(0, limit - total)])
                break
            parts.append(text)
            total += len(text)
        return "\n\n".join(parts)

    @staticmethod
    def _heuristic_questions(doc: dict[str, Any], chunks: list[dict[str, Any]], n: int) -> list[dict[str, str]]:
        questions: list[dict[str, str]] = []
        for c in chunks[:n]:
            title = c.get("section_title") or (c.get("section_path") or ["Relevant clauses"])[-1]
            if not c.get("content", "").strip():
                continue
            questions.append(
                {
                    "question": f"What does \"{doc.get('title', 'this document')}\" specify regarding \"{title}\"?",
                    "expected": c.get("content", "")[:120],
                }
            )
        return questions[:n]
