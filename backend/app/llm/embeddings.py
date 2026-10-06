"""Embedding model client.

provider:
- relay: calls the embedding model via the relay service (default)
- local: local sentence-transformers (offline fallback)
- hash : deterministic hash vectors (dev/test only, works without network)
"""
from __future__ import annotations
from typing import Optional

import hashlib
import math
import re

from app.config import Settings
from app.llm.relay import RelayClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    def __init__(self, settings: Settings, relay: Optional[RelayClient] = None) -> None:
        self.settings = settings
        self.provider = settings.embedding_provider.lower()
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self.relay = relay
        self._local_model = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.provider == "relay":
            if self.relay is None or not self.settings.relay_api_key:
                logger.warning("Relay service key not configured, falling back to hash vectors (dev only)")
                return [self._hash_embed(t) for t in texts]
            try:
                vecs = await self.relay.embed(texts, model=self.model)
                self.dim = len(vecs[0])
                return vecs
            except Exception as exc:  # noqa: BLE001 - embedding failures must not block the main ingestion flow
                logger.warning("Relay embedding failed (%s), falling back to hash vectors", exc)
                return [self._hash_embed(t) for t in texts]
        if self.provider == "local":
            return self._local_embed(texts)
        return [self._hash_embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        vecs = await self.embed([text])
        return vecs[0]

    def _local_embed(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer  # Lazy import, optional dependency
        except ImportError:
            logger.warning("sentence-transformers is not installed, falling back to hash vectors")
            return [self._hash_embed(t) for t in texts]
        if self._local_model is None:
            self._local_model = SentenceTransformer(self.model)
        vecs = self._local_model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic hash vectors: hash character n-grams into a sparse vector, then normalize.

        For offline dev/testing only; carries no real semantics, but guarantees cosine is computable and similar texts land close together.
        """
        text = self._normalize(text)
        dim = max(self.dim, 128)
        vec = [0.0] * dim
        ngrams = [text]
        if len(text) > 2:
            ngrams += [text[i : i + 2] for i in range(len(text) - 1)]
        for ng in ngrams:
            for suffix in ("", " "):
                h = hashlib.md5((ng + suffix).encode("utf-8")).digest()
                idx = int.from_bytes(h[:4], "big") % dim
                sign = 1.0 if h[4] % 2 == 0 else -1.0
                vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    @staticmethod
    def _normalize(text: str) -> str:
        text = re.sub(r"\s+", "", text)
        return text.lower()
