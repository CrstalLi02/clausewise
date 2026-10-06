"""Feedback Collector: aggregates three kinds of feedback signals (explicit/implicit/automatic) for the Loop Engine."""
from __future__ import annotations

from typing import Any, Optional

from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)


class FeedbackCollector:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def collect_explicit(self, session_id: str, user_id: str, query: str, answer: str, signal: str, detail: Optional[dict[str, Any]] = None) -> None:
        await self.store.insert_feedback(
            {
                "_id": self._new_id("explicit"),
                "session_id": session_id,
                "user_id": user_id,
                "query": query,
                "answer": answer,
                "kind": "explicit",
                "signal": signal,
                "detail": detail or {},
                "consumed": False,
                "created_at": self._now(),
            }
        )

    async def collect_implicit(self, session_id: str, user_id: str, query: str, answer: str, signal: str, detail: Optional[dict[str, Any]] = None) -> None:
        await self.store.insert_feedback(
            {
                "_id": self._new_id("implicit"),
                "session_id": session_id,
                "user_id": user_id,
                "query": query,
                "answer": answer,
                "kind": "implicit",
                "signal": signal,
                "detail": detail or {},
                "consumed": False,
                "created_at": self._now(),
            }
        )

    async def pending(self) -> list[dict[str, Any]]:
        return await self.store.list_pending_feedback()

    async def consume(self, ids: list[str]) -> None:
        await self.store.mark_feedback_consumed(ids)

    async def stats(self) -> dict[str, Any]:
        all_fb = await self.store.find("feedback")
        up = sum(1 for f in all_fb if f.get("signal") == "up")
        down = sum(1 for f in all_fb if f.get("signal") == "down")
        return {"total": len(all_fb), "up": up, "down": down, "adoption_rate": up / max(up + down, 1)}

    @staticmethod
    def _new_id(prefix: str) -> str:
        import uuid

        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
