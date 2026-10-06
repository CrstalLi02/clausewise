"""Relay service client (OpenAI-compatible).

Used for non-DeepSeek models such as bge, for example:
    base_url=https://yunwu.ai/v1, api_key=relay service key.

Built-in retry and timeout control for Embedding / Rerank, retrying automatically on relay network hiccups;
final failures are degraded by the upper layer (EmbeddingClient / Reranker) to hash / heuristics.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.config import Settings
from app.llm.client import LLMClient, LLMError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RelayClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.relay_base_url,
            api_key=settings.relay_api_key,
            model=settings.relay_model,
            timeout=settings.deepseek_timeout,
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
        )

    def name(self) -> str:
        return "relay"

    async def _post_json(self, url: str, payload: dict[str, Any], retries: int = 2) -> dict[str, Any]:
        """POST with retries: 4xx (auth/model-name errors) is not retried; network errors/5xx are retried."""
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=self._headers(), json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise LLMError(f"Request failed {exc.response.status_code}: {exc.response.text[:300]}") from exc
                last_exc = exc
            except httpx.HTTPError as exc:
                last_exc = exc
            if attempt < retries - 1:
                await asyncio.sleep(1.0)
        raise LLMError(f"Network error (failed after {retries} retries): {last_exc}") from last_exc

    async def embed(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]:
        """Call the relay service /embeddings endpoint to generate vectors."""
        if not self.api_key:
            raise LLMError("Relay service API key not configured; cannot call Embedding")
        payload: dict[str, Any] = {"model": model or "text-embedding-3-large", "input": texts}
        data = await self._post_json(f"{self.base_url}/embeddings", payload)
        try:
            items = sorted(data["data"], key=lambda d: d.get("index", 0))
            return [item["embedding"] for item in items]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Embedding response format: {str(data)[:300]}") from exc

    async def rerank(self, query: str, documents: list[str], model: Optional[str] = None) -> list[float]:
        """Call the relay service /rerank endpoint (bge-reranker-v2-m3, etc.) and return a list of relevance scores."""
        if not self.api_key:
            raise LLMError("Relay service API key not configured; cannot call Rerank")
        payload: dict[str, Any] = {
            "model": model or "BAAI/bge-reranker-v2-m3",
            "query": query,
            "documents": documents,
        }
        data = await self._post_json(f"{self.base_url}/rerank", payload)
        try:
            return [float(r.get("relevance_score", 0.0)) for r in data["results"]]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Rerank response format: {str(data)[:300]}") from exc
