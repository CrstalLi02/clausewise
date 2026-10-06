"""pi Agent Runtime client.

Python owns the control plane and fact/memory governance; this client only hands governed probabilistic execution requests to pi.
Returns None on failure, so each Python agent can degrade to its existing local LLM/rule implementation.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

import httpx

from app.config import Settings
from app.utils.logging import get_logger
from app.utils import metrics

logger = get_logger(__name__)

AgentType = Literal["intent", "rewrite", "answer", "verify", "reflect"]
OutputMode = Literal["text", "json"]


class PiAgentRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.pi_agent_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def enabled(self) -> bool:
        return self.settings.pi_agent_enabled and bool(self.base_url) and bool(self.settings.internal_api_token)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.pi_agent_timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def run(
        self, agent_type: AgentType, system_prompt: str, prompt: str,
        output_mode: OutputMode = "json", allowed_tools: Optional[list[str]] = None,
        timeout_seconds: float = 30.0, trace_id: str = "",
    ) -> Any | None:
        if not self.enabled:
            metrics.PI_AGENT_EXECUTION.labels(agent=agent_type, status="disabled").inc()
            return None
        timeout_ms = max(250, min(int(timeout_seconds * 1000), 120_000))
        try:
            response = await self._http().post(
                f"{self.base_url}/v1/agent/run",
                headers={"X-Internal-Token": self.settings.internal_api_token},
                json={
                    "agentType": agent_type, "systemPrompt": system_prompt, "prompt": prompt,
                    "outputMode": output_mode, "allowedTools": allowed_tools or [],
                    "timeoutMs": timeout_ms, "traceId": trace_id,
                },
                timeout=timeout_seconds + 2.0,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("code") != 0:
                metrics.PI_AGENT_EXECUTION.labels(agent=agent_type, status="error").inc()
                logger.warning("pi runtime %s returned an error: %s", agent_type, body.get("message"))
                return None
            data = body.get("data") or {}
            metrics.PI_AGENT_EXECUTION.labels(agent=agent_type, status="success").inc()
            return data.get("output")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            metrics.PI_AGENT_EXECUTION.labels(agent=agent_type, status="fallback").inc()
            logger.warning("pi runtime %s call failed, falling back to the Python agent: %s", agent_type, exc)
            return None

    async def run_json(self, agent_type: AgentType, system_prompt: str, prompt: str, **kwargs: Any) -> Any | None:
        return await self.run(agent_type, system_prompt, prompt, output_mode="json", **kwargs)

    async def run_text(self, agent_type: AgentType, system_prompt: str, prompt: str, **kwargs: Any) -> str | None:
        result = await self.run(agent_type, system_prompt, prompt, output_mode="text", **kwargs)
        return result if isinstance(result, str) else None
