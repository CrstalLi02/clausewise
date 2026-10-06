"""Retrieval Agent: runs hybrid retrieval (BM25 + vectors + rerank) and returns the top-k chunks."""
from __future__ import annotations

from typing import Any, Optional

from app.llm.embeddings import EmbeddingClient
from app.retrieval.hybrid import HybridRetriever
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RetrievalAgent:
    def __init__(self, hybrid: HybridRetriever, embeddings: EmbeddingClient, store) -> None:
        self.hybrid = hybrid
        self.embeddings = embeddings
        self.store = store

    async def retrieve(self, queries: list[str], dept_ids: Optional[list[str]] = None, top_k: int = 5) -> list[dict[str, Any]]:
        """Parallel retrieval over multiple queries × multiple departments, merged and deduplicated."""
        if not queries:
            return []
        dept_ids = dept_ids or [None]
        seen: dict[str, dict[str, Any]] = {}

        for query in queries:
            vec = await self.embeddings.embed_query(query)
            for dept_id in dept_ids:
                if dept_id == "dept_all":
                    dept_id = None
                hits = await self.hybrid.retrieve(query, vec, dept_id=dept_id)
                for h in hits:
                    id_ = h.get("id", "")
                    if id_ and id_ not in seen:
                        seen[id_] = h

        # After retrieval, backfill full chunks from persistent storage, since the vector store may return only metadata
        # and lose the body, keywords, and section info; also enforce that documents are still active before returning.
        chunks: list[dict[str, Any]] = []
        for chunk_id, hit in seen.items():
            stored = await self.store.get("chunks", chunk_id)
            if not stored:
                continue
            doc = await self.store.get_document(stored.get("doc_id", ""))
            if not doc or doc.get("status") != "active":
                continue
            full = dict(hit)
            full.update(stored)
            full["id"] = chunk_id
            full["doc_title"] = doc.get("title", "")
            chunks.append(full)
        chunks.sort(key=lambda x: x.get("rerank_score", x.get("_rrf", x.get("score", 0.0))), reverse=True)
        return chunks[:top_k]
