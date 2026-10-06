"""Query Rewriter: fills in omitted information, normalizes terminology (via the glossary), and generates multiple retrieval queries."""
from __future__ import annotations
from typing import Optional

from app.harness.base import Intent
from app.llm.client import ChatMessage, LLMClient
from app.storage.store import DataStore
from app.utils.logging import get_logger
from app.integrations.pi_runtime import PiAgentRuntimeClient

logger = get_logger(__name__)

REWRITE_PROMPT = """You are a retrieval query rewriting assistant. Rewrite the user question into 1-3 queries better suited for retrieval (fill in omissions, normalize terminology).

Glossary:
{glossary}

Output JSON only:
{{"queries": ["query1", "query2"]}}

User question: {query}
"""


class QueryRewriter:
    def __init__(
        self, llm: LLMClient, store: DataStore, pi_runtime: PiAgentRuntimeClient | None = None,
        timeout: float = 2.0,
    ) -> None:
        self.llm = llm
        self.store = store
        self.pi_runtime = pi_runtime
        self.timeout = timeout

    async def rewrite(self, query: str, intent: Optional[Intent] = None, memory_context: str = "") -> list[str]:
        glossary = await self.store.list_glossary()
        gloss_text = "; ".join(f"{g['canonical']}≈{'/'.join(g.get('synonyms', []))}" for g in glossary[:50])
        try:
            prompt = REWRITE_PROMPT.format(glossary=gloss_text, query=query) + (
                f"\nConversation memory: {memory_context[:1600]}" if memory_context else ""
            )
            data = None
            if self.pi_runtime is not None:
                data = await self.pi_runtime.run_json(
                    "rewrite", "You are a retrieval query rewriting assistant.", prompt,
                    timeout_seconds=self.timeout,
                )
            if not isinstance(data, dict):
                messages = [ChatMessage.system("You are a retrieval query rewriting assistant."), ChatMessage.user(prompt)]
                data = await self.llm.complete_json(messages, temperature=0.2)
            queries = data.get("queries") if isinstance(data, dict) else None
            if isinstance(queries, list):
                return self._dedupe([q for q in queries if isinstance(q, str) and q.strip()])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query rewriting failed (%s), using the original query + glossary expansion", exc)
        return self._glossary_expand(query, glossary)

    def _glossary_expand(self, query: str, glossary: list[dict]) -> list[str]:
        """Glossary synonym expansion (no-LLM fallback)."""
        queries = [query]
        expanded = query
        for g in glossary:
            canonical = g.get("canonical", "")
            if canonical and canonical.lower() in query.lower():
                for syn in g.get("synonyms", []):
                    if syn and syn.lower() not in expanded.lower():
                        expanded += f" {syn}"
        if expanded != query:
            queries.append(expanded)
        return self._dedupe(queries)

    @staticmethod
    def _dedupe(queries: list[str]) -> list[str]:
        seen: list[str] = []
        for q in queries:
            if q and q not in seen:
                seen.append(q)
        return seen or ["*"]
