"""Reranking.

Priority:
1. RelayReranker — calls bge-reranker-v2-m3 via the relay service (default, requires the relay key)
2. CrossEncoderReranker — local sentence-transformers (optional)
3. HeuristicReranker — keyword-overlap heuristic (zero-cost fallback)
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.llm.relay import RelayClient
from app.retrieval.bm25 import tokenize
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Reranker:
    """Reranker interface."""

    async def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError


class HeuristicReranker(Reranker):
    """Heuristic reranking: keyword overlap ratio + bonus for clause-number hits (zero-cost fallback)."""

    async def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        q_tokens = set(tokenize(query))
        for c in candidates:
            content = c.get("content", "")
            c_tokens = set(tokenize(content))
            overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
            clause_hit = 1.0 if re.search(r"\bArticle\s+(?:\d+|[IVXLC]+)\b", content) else 0.0
            base = float(c.get("score", 0.0))
            c["rerank_score"] = base + 0.3 * overlap + 0.2 * clause_hit
        ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return ranked[:top_k]


class RelayReranker(Reranker):
    """Calls bge-reranker (bge-reranker-v2-m3) via the relay service."""

    def __init__(self, relay: RelayClient, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.relay = relay
        self.model_name = model_name

    async def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        if not candidates:
            return []
        docs = [c.get("content", "") for c in candidates]
        try:
            scores = await self.relay.rerank(query, docs, model=self.model_name)
        except Exception as exc:  # noqa: BLE001 - fall back to heuristics when reranking fails
            logger.warning("Relay rerank failed (%s), falling back to heuristics", exc)
            return await HeuristicReranker().rerank(query, candidates, top_k)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return ranked[:top_k]


class CrossEncoderReranker(Reranker):
    """Local cross-encoder reranking (optional, requires sentence-transformers)."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.model_name = model_name
        self._model = None

    async def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        if self._model is None:
            from sentence_transformers import CrossEncoder  # Lazy import

            self._model = CrossEncoder(self.model_name)
        pairs = [(query, c.get("content", "")) for c in candidates]
        scores = self._model.predict(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        ranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return ranked[:top_k]


def build_reranker(enabled: bool, model_name: str = "BAAI/bge-reranker-v2-m3", relay: Optional[RelayClient] = None) -> Reranker:
    if enabled:
        if relay is not None and relay.api_key:
            return RelayReranker(relay, model_name)
        try:
            import sentence_transformers  # noqa: F401

            return CrossEncoderReranker(model_name)
        except ImportError:
            logger.warning("Relay key not configured and sentence-transformers not installed, falling back to heuristic reranking")
    return HeuristicReranker()
