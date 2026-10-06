"""Feedback Agent: collects feedback (explicit/implicit/automatic) and writes it to the feedback queue for the Loop Engine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.harness.base import Answer
from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeedbackAgent:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def collect(
        self,
        session_id: str,
        user_id: str,
        query: str,
        answer: Answer,
        signal: str = "auto",
        kind: str = "auto",
        dept_ids: Optional[list[str]] = None,
        intent_type: str = "",
        detail: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        record = {
            "_id": uuid.uuid4().hex,
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "answer": answer.content,
            "kind": kind,  # explicit | implicit | auto
            "signal": signal,  # up|down|correction|follow_up|copy|verifier_pass|verifier_fail
            "dept_ids": dept_ids or answer.dept_ids,
            "intent_type": intent_type,
            "detail": detail or {},
            "consumed": False,
            "created_at": _now(),
        }
        await self.store.insert_feedback(record)
        return record

    async def collect_explicit(
        self,
        session_id: str,
        user_id: str,
        query: str,
        answer_text: str,
        signal: str,
        detail: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Explicit feedback (thumbs-up/thumbs-down/correction), called by the API layer."""
        from app.harness.base import Answer as _Answer

        return await self.collect(
            session_id=session_id,
            user_id=user_id,
            query=query,
            answer=_Answer(content=answer_text),
            signal=signal,
            kind="explicit",
            detail=detail,
        )
