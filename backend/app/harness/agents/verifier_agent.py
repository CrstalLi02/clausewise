"""Verifier Agent: answer verification (citation support / contradiction with the source / omissions / format); failures are sent back for rewriting."""
from __future__ import annotations

from typing import Any

from app.harness.base import Answer, VerificationResult
from app.llm.client import ChatMessage, LLMClient
from app.utils.logging import get_logger
from app.integrations.pi_runtime import PiAgentRuntimeClient

logger = get_logger(__name__)

VERIFY_PROMPT = """You are an answer verification assistant. Check whether the answer is reliable and output JSON only:
{{"passed": true/false, "score": 0.0-1.0, "issues": ["issue 1", "issue 2"]}}

Checks:
1. Whether every key conclusion is supported by a clause (cited source)
2. Whether it contradicts the source text
3. Whether key information is missing
4. Whether the citation format is correct

Reference clauses:
{chunks}

Answer:
{answer}

User question: {query}
"""


class VerifierAgent:
    def __init__(
        self, llm: LLMClient, pi_runtime: PiAgentRuntimeClient | None = None, timeout: float = 3.0,
    ) -> None:
        self.llm = llm
        self.pi_runtime = pi_runtime
        self.timeout = timeout

    async def verify(self, query: str, answer: Answer, chunks: list[dict[str, Any]]) -> VerificationResult:
        if not chunks:
            return VerificationResult(passed=True, score=0.9, issues=[])
        chunks_text = "\n\n".join(f"[{i+1}] {c.get('content', '')[:500]}" for i, c in enumerate(chunks[:8]))
        try:
            prompt = VERIFY_PROMPT.format(chunks=chunks_text, answer=answer.content, query=query)
            data = None
            if self.pi_runtime is not None:
                data = await self.pi_runtime.run_json(
                    "verify", "You are a rigorous answer verification assistant.", prompt,
                    timeout_seconds=self.timeout,
                )
            if not isinstance(data, dict):
                messages = [ChatMessage.system("You are a rigorous answer verification assistant."), ChatMessage.user(prompt)]
                data = await self.llm.complete_json(messages, temperature=0.0)
            return VerificationResult.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer verification LLM failed (%s), using heuristic verification", exc)
            return self._heuristic(answer, chunks)

    @staticmethod
    def _heuristic(answer: Answer, chunks: list[dict[str, Any]]) -> VerificationResult:
        issues: list[str] = []
        if not answer.citations:
            issues.append("The answer lacks cited sources")
        if not answer.content.strip():
            issues.append("The answer is empty")
        score = 1.0 - 0.3 * len(issues)
        return VerificationResult(passed=len(issues) == 0, score=max(score, 0.0), issues=issues)
