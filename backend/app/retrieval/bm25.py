"""BM25 keyword retrieval (jieba tokenization + pure Python implementation, no external index dependency)."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


def tokenize(text: str) -> list[str]:
    """Tokenize text with jieba, lowercasing English words."""
    text = text.lower()
    tokens: list[str] = []
    try:
        import jieba  # Lazy import

        tokens = [t for t in jieba.cut(text) if t.strip()]
    except ImportError:
        tokens = re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text)
    # Drop pure punctuation/whitespace tokens
    tokens = [t for t in tokens if t.strip() and not re.fullmatch(r"[\W_]+", t)]
    return tokens


class BM25Index:
    """BM25 retriever with department filtering."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: dict[str, dict[str, Any]] = {}  # id -> {content, dept_id, ...}
        self._tokens: dict[str, list[str]] = {}
        self._df: Counter = Counter()
        self._doc_len: dict[str, int] = {}
        self._avg_len: float = 0.0
        self._n: int = 0

    def index(self, docs: list[dict[str, Any]]) -> None:
        """docs: [{_id, content, dept_id, ...}]; fully rebuilds the index."""
        self._docs = {}
        self._tokens = {}
        self._df = Counter()
        self._doc_len = {}
        for d in docs:
            id_ = d["_id"]
            toks = tokenize(d.get("content", ""))
            if not toks:
                continue
            self._docs[id_] = d
            self._tokens[id_] = toks
            self._doc_len[id_] = len(toks)
            for t in set(toks):
                self._df[t] += 1
        self._n = len(self._docs)
        self._avg_len = sum(self._doc_len.values()) / max(self._n, 1)

    def add(self, doc: dict[str, Any]) -> None:
        """Incrementally add a single document (simple implementation: add it and update the statistics)."""
        id_ = doc["_id"]
        toks = tokenize(doc.get("content", ""))
        if not toks:
            return
        self._docs[id_] = doc
        self._tokens[id_] = toks
        self._doc_len[id_] = len(toks)
        for t in set(toks):
            self._df[t] += 1
        self._n += 1
        self._avg_len = sum(self._doc_len.values()) / max(self._n, 1)

    def remove(self, doc_id: str) -> None:
        toks = self._tokens.pop(doc_id, [])
        for t in set(toks):
            self._df[t] -= 1
            if self._df[t] <= 0:
                del self._df[t]
        self._docs.pop(doc_id, None)
        self._doc_len.pop(doc_id, None)
        self._n = len(self._docs)
        self._avg_len = sum(self._doc_len.values()) / max(self._n, 1)

    def search(self, query: str, top_k: int = 10, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        q_tokens = tokenize(query)
        if not q_tokens or self._n == 0:
            return []
        scores: dict[str, float] = {}
        qf = Counter(q_tokens)
        for t, qt in qf.items():
            df = self._df.get(t, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            for id_, toks in self._tokens.items():
                tf = toks.count(t)
                if tf == 0:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * self._doc_len[id_] / max(self._avg_len, 1e-6))
                scores[id_] = scores.get(id_, 0.0) + idf * (tf * (self.k1 + 1)) / denom * qt

        # Department filtering must happen before top-k truncation; otherwise high-scoring results from other departments
        # would crowd out the candidates the target department should have returned.
        ranked = sorted(
            (item for item in scores.items() if not dept_id or self._docs[item[0]].get("dept_id") == dept_id),
            key=lambda x: x[1],
            reverse=True,
        )
        out = []
        for id_, score in ranked[:top_k]:
            doc = self._docs[id_]
            out.append({"id": id_, "score": float(score), **doc})
        return out


class SharedBM25Index:
    """Stateless lexical retrieval that reads active chunks from shared storage."""

    def __init__(self, store, k1: float = 1.5, b: float = 0.75) -> None:
        self.store = store
        self.k1 = k1
        self.b = b

    def index(self, docs: list[dict[str, Any]]) -> None:
        return None

    def add(self, doc: dict[str, Any]) -> None:
        return None

    def remove(self, doc_id: str) -> None:
        return None

    async def search(self, query: str, top_k: int = 10, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        transient = BM25Index(k1=self.k1, b=self.b)
        transient.index(await self.store.list_active_chunks(dept_id))
        return transient.search(query, top_k=top_k, dept_id=dept_id)
