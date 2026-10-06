"""Feedback collection endpoints (explicit feedback)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import ApiResponse, FeedbackRequest, ImplicitFeedbackRequest
from app.api.deps import require_user
from app.utils import metrics
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=ApiResponse)
async def submit_feedback(body: FeedbackRequest, request: Request, user: dict = Depends(require_user)):
    container = request.app.state.container
    traces = await container.store.find("traces", {"session_id": body.session_id})
    owned = [t for t in traces if t.get("user_id") == user["id"]]
    if not body.session_id or not owned:
        raise HTTPException(status_code=404, detail="Session not found")
    # Feedback must correspond to a system answer in this session, preventing forged training signals.
    if not any(t.get("query") == body.query and t.get("answer") == body.answer for t in owned):
        raise HTTPException(status_code=400, detail="Feedback does not match any answer in the session")
    await container.feedback_collector.collect_explicit(
        session_id=body.session_id,
        user_id=user["id"],
        query=body.query,
        answer=body.answer,
        signal=body.signal,
        detail=body.detail,
    )
    metrics.FEEDBACK_TOTAL.labels(kind=body.signal).inc()
    if body.signal == "up":
        metrics.record_adoption("up")
    elif body.signal == "down":
        metrics.record_adoption("down")
    # Update user memory
    await container.user_memory.record_feedback(user["id"], body.signal, body.query)
    if body.signal in {"down", "correction"}:
        await container.job_queue.enqueue("feedback_received", {"feedback_user": user["id"]})
    return ApiResponse(data={"received": body.signal})


@router.post("/implicit", response_model=ApiResponse)
async def submit_implicit_feedback(
    body: ImplicitFeedbackRequest, request: Request, user: dict = Depends(require_user)
):
    if body.signal not in {"copy", "follow_up", "abandon"}:
        raise HTTPException(status_code=400, detail="Invalid implicit feedback type")
    container = request.app.state.container
    traces = await container.store.find("traces", {"session_id": body.session_id})
    if not any(t.get("user_id") == user["id"] for t in traces):
        raise HTTPException(status_code=404, detail="Session not found")
    await container.feedback_collector.collect_implicit(
        body.session_id, user["id"], body.query, body.answer, body.signal, body.detail
    )
    if body.signal in {"follow_up", "abandon"}:
        await container.job_queue.enqueue("feedback_received", {"feedback_user": user["id"]})
    return ApiResponse(data={"received": body.signal})
