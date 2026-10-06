"""Hybrid retrieval: BM25 + vectors with RRF (reciprocal rank fusion), followed by optional reranking."""
from __future__ import annotations

from typing import Any, Optional
import inspect

from app.retrieval.bm25 import BM25Index
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore
from app.utils.logging import get_logger

logger = get_logger(__name__)

RRF_K = 60.0


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Index,
        vector_store: VectorStore,
        reranker: Reranker,
        bm25_top: int = 20,
        vector_top: int = 20,
        top_k: int = 5,
    ) -> None:
        self.bm25 = bm25
        self.vector_store = vector_store
        self.reranker = reranker
        self.bm25_top = bm25_top
        self.vector_top = vector_top
        self.top_k = top_k

    async def retrieve(self, query: str, query_vec: list[float], dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        bm25_hits = self.bm25.search(query, top_k=self.bm25_top, dept_id=dept_id)
        if inspect.isawaitable(bm25_hits):
            bm25_hits = await bm25_hits
        vector_hits = await self.vector_store.search(query_vec, top_k=self.vector_top, dept_id=dept_id)
        fused: dict[str, dict[str, Any]] = {}

        def _add(hit: dict[str, Any], rank: int) -> None:
            id_ = hit["id"]
            if id_ not in fused:
                fused[id_] = dict(hit)
                fused[id_]["_rrf"] = 0.0
            fused[id_]["_rrf"] += 1.0 / (RRF_K + rank + 1)

        for rank, h in enumerate(bm25_hits):
            _add(h, rank)
        for rank, h in enumerate(vector_hits):
            _add(h, rank)

        candidates = list(fused.values())
        candidates.sort(key=lambda x: x["_rrf"], reverse=True)
        candidates = candidates[: max(self.top_k * 2, 10)]
        return await self.reranker.rerank(query, candidates, top_k=self.top_k)
