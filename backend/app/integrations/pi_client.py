"""pi agent service HTTP client: the Python backend delegates Harness/Loop reasoning to pi (with local fallback).

The pi service URL is configured via `PI_AGENT_URL`; on call failure the Orchestrator falls back to local agents.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PiAgentClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.pi_agent_url.rstrip("/")
        self.timeout = settings.pi_agent_timeout

    @property
    def enabled(self) -> bool:
        return self.settings.pi_agent_enabled and bool(self.base_url)

    async def answer(
        self,
        query: str,
        session_id: str,
        user_id: str,
        dept_ids: Optional[list[str]] = None,
    ) -> dict[str, Any] | None:
        """Call the pi service /answer. Returns the result dict, or None on failure."""
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/answer",
                    headers={"X-Internal-Token": self.settings.internal_api_token},
                    json={"query": query, "sessionId": session_id, "userId": user_id, "deptIds": dept_ids},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("pi-agent /answer call failed: %s", exc)
            return None
        if data.get("code") != 0:
            logger.warning("pi-agent /answer returned an error: %s", data.get("message"))
            return None
        return data.get("data")

    async def run_loop(self) -> dict[str, Any] | None:
        """Call the pi service /loop/run. Returns None on failure."""
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/loop/run", json={},
                    headers={"X-Internal-Token": self.settings.internal_api_token},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("pi-agent /loop/run call failed: %s", exc)
            return None
        if data.get("code") != 0:
            return None
        return data.get("data")

    async def health(self) -> bool:
        """Liveness check."""
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
