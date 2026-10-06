"""Answer Agent: generates cited answers from retrieved chunks while obeying hard-constraint Rules."""
from __future__ import annotations

from typing import Any, Optional

from app.harness.base import Answer, Citation, Intent
from app.llm.client import ChatMessage, LLMClient
from app.utils.logging import get_logger
from app.integrations.pi_runtime import PiAgentRuntimeClient

logger = get_logger(__name__)

ANSWER_PROMPT = """You are "Clausewise", a school policy consultation assistant. Answer the user question based on the given policy clauses.

[Rules you must follow]
{rules}

[Answer requirements]
- Answer only based on the given clauses and never fabricate; if the clauses contain no explicit answer, state clearly "No explicit provision was found in the current policy documents".
- After each key conclusion, mark the citation number in the form [Source 1].
- Use concise, accurate English, with bullet points when helpful.

[Reference clauses]
{chunks}

User question: {query}
"""


class AnswerAgent:
    def __init__(
        self, llm: LLMClient, store, pi_runtime: PiAgentRuntimeClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.llm = llm
        self.store = store
        self.pi_runtime = pi_runtime
        self.timeout = timeout

    async def generate(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        rules: list[dict[str, Any]] | None = None,
        intent: Optional[Intent] = None,
        user_prefs: Optional[dict[str, Any]] = None,
        extra_instructions: str = "",
        memory_context: str = "",
    ) -> Answer:
        rules = rules or []
        rules_text = "\n".join(f"- {r.get('content', '')}" for r in rules) or "- Always cite sources"
        if extra_instructions:
            rules_text += "\n" + extra_instructions
        if memory_context:
            rules_text += "\nThe following memory is only for understanding context and answer style; it must not be used as policy facts or citation sources:\n" + memory_context[:2400]
        if not chunks:
            return Answer(content="No explicit provision was found in the current policy documents. Please consult the relevant department.", citations=[], dept_ids=[])

        chunks_text, citations = self._format_chunks(chunks)
        try:
            prompt = ANSWER_PROMPT.format(rules=rules_text, chunks=chunks_text, query=query)
            content = None
            if self.pi_runtime is not None:
                content = await self.pi_runtime.run_text(
                    "answer", "You are a school policy consultation assistant whose answers are rigorous and well-grounded.", prompt,
                    allowed_tools=[], timeout_seconds=self.timeout,
                )
            if not content:
                messages = [
                    ChatMessage.system("You are a school policy consultation assistant whose answers are rigorous and well-grounded."),
                    ChatMessage.user(prompt),
                ]
                content = await self.llm.complete(messages, temperature=0.2)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Answer generation LLM failed (%s), falling back to source-text concatenation", exc)
            content = self._fallback_answer(query, chunks)

        dept_ids = sorted({c["dept_id"] for c in chunks if c.get("dept_id")})
        return Answer(content=content, citations=citations, dept_ids=dept_ids, confidence=0.7)

    def _format_chunks(self, chunks: list[dict[str, Any]]) -> tuple[str, list[Citation]]:
        lines: list[str] = []
        citations: list[Citation] = []
        for i, c in enumerate(chunks, start=1):
            lines.append(f"[Source {i}] {c.get('content', '')}")
            citations.append(
                Citation(
                    doc_id=c.get("doc_id", ""),
                    doc_title=c.get("doc_title", c.get("section_title", "")),
                    dept_id=c.get("dept_id", ""),
                    chunk_index=c.get("chunk_index", 0),
                    section_path=c.get("section_path", []),
                    snippet=c.get("content", "")[:200],
                )
            )
        return "\n\n".join(lines), citations

    @staticmethod
    def _fallback_answer(query: str, chunks: list[dict[str, Any]]) -> str:
        parts = ["According to the retrieved policy clauses:"]
        for i, c in enumerate(chunks[:3], start=1):
            parts.append(f"[Source {i}] {c.get('content', '')[:300]}")
        return "\n".join(parts)
