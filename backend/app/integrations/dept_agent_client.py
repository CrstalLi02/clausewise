"""K8s department agent client: service discovery, concurrent calls, and partial success."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DepartmentAgentClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.dept_agents_enabled and not self.settings.dept_id

    @staticmethod
    def slug(dept_id: str) -> str:
        return dept_id.removeprefix("dept_").replace("_", "-")

    def url(self, dept_id: str) -> str:
        return self.settings.dept_agent_url_template.format(
            dept_id=dept_id, slug=self.slug(dept_id)
        ).rstrip("/")

    async def answer_many(
        self, query: str, dept_ids: list[str], session_id: str, user_id: str, memory_context: str = ""
    ) -> tuple[list[dict[str, Any]], list[str]]:
        raw = await asyncio.gather(
            *(self._answer_one(query, dept, session_id, user_id, memory_context) for dept in dept_ids),
            return_exceptions=True,
        )
        results: list[dict[str, Any]] = []
        failed: list[str] = []
        for dept, item in zip(dept_ids, raw):
            if isinstance(item, BaseException) or item is None:
                failed.append(dept)
                if isinstance(item, BaseException):
                    logger.warning("Department agent %s call failed: %s", dept, item)
            else:
                results.append(item)
        return results, failed

    async def _answer_one(
        self, query: str, dept_id: str, session_id: str, user_id: str, memory_context: str = ""
    ) -> dict[str, Any] | None:
        timeout = httpx.Timeout(
            self.settings.dept_agent_timeout, connect=self.settings.dept_agent_partial_timeout
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.url(dept_id)}/api/v1/internal/dept/answer",
                headers={"X-Internal-Token": self.settings.internal_api_token},
                json={
                    "query": query, "dept_id": dept_id, "user_id": user_id,
                    "session_id": f"{session_id}:{dept_id}",
                    "memory_context": memory_context,
                },
            )
            response.raise_for_status()
            body = response.json()
            return body.get("data") if body.get("code") == 0 else None
