"""Base class for OpenAI-compatible LLM clients (async httpx implementation).

Does not depend on the openai SDK; calls /chat/completions directly for easier control of streaming output and cost accounting.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """LLM call error."""


class ChatMessage(dict):
    """Convenience constructors for message dicts."""

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "ChatMessage":
        return cls(role="assistant", content=content)


class LLMClient(ABC):
    """Abstract base class for OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, Any]] = None,
    ) -> str:
        """Non-streaming completion that returns text."""
        if not self.api_key:
            raise LLMError("API key not configured; cannot call the LLM")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self._chat_url(), headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            logger.error("LLM HTTP %s: %s", exc.response.status_code, body)
            raise LLMError(f"LLM request failed {exc.response.status_code}: {body}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM network error: {exc}") from exc

        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected LLM response format: {data}") from exc

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """Request JSON output and parse it (compatible with services that do not support response_format)."""
        text = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
        return self._extract_json(text)

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[str]:
        """SSE streaming completion that yields incremental text chunk by chunk."""
        if not self.api_key:
            raise LLMError("API key not configured; cannot call the LLM")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        payload.update(kwargs)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", self._chat_url(), headers=self._headers(), json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[len("data:") :].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0]["delta"].get("content")
                            if delta:
                                yield delta
                        except (KeyError, IndexError, json.JSONDecodeError):
                            continue
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM streaming request failed: {exc}") from exc

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Extract JSON from text (tolerating extra explanations/code fences in model output)."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        start = text.find("{")
        start_arr = text.find("[")
        if start == -1 or (0 <= start_arr < start):
            start = start_arr
        end = text.rfind("}")
        end_arr = text.rfind("]")
        end = max(end, end_arr)
        if start == -1 or end == -1 or end <= start:
            raise LLMError(f"Could not parse JSON from model output: {text[:200]}")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"JSON parsing failed: {text[:200]}") from exc

    @abstractmethod
    def name(self) -> str:
        """Client identifier (for logging and cost attribution)."""
