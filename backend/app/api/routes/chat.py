"""Chat endpoints: non-streaming + SSE streaming + session history."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ApiResponse, ChatRequest
from app.api.deps import require_user
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


async def _assert_session_owner(container, session_id: str, user_id: str, *, require_exists: bool = False) -> None:
    if not session_id:
        return
    traces = await container.store.find("traces", {"session_id": session_id}, limit=1)
    events = await container.store.find("conversation_events", {"session_id": session_id}, limit=1)
    owner = (events[0].get("user_id") if events else None) or (traces[0].get("user_id") if traces else None)
    if require_exists and not owner:
        raise HTTPException(status_code=404, detail="Session not found")
    if owner and owner != user_id:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("", response_model=ApiResponse)
async def chat(req: ChatRequest, request: Request, user: dict = Depends(require_user)):
    container = request.app.state.container
    await _assert_session_owner(container, req.session_id or "", user["id"])
    result = await container.orchestrator.answer(
        query=req.query,
        session_id=req.session_id or "",
        user_id=user["id"],
        dept_ids=req.dept_ids,
    )
    return ApiResponse(data=result)


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request, user: dict = Depends(require_user)):
    container = request.app.state.container
    await _assert_session_owner(container, req.session_id or "", user["id"])

    async def event_stream():
        async for chunk in container.orchestrator.answer_stream(
            req.query, session_id=req.session_id or "", user_id=user["id"]
        ):
            yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _history_from_traces(container, session_id: str) -> list[dict]:
    """Rebuild session history from persisted traces (recoverable even after Redis working memory expires)."""
    traces = await container.store.find("traces", {"session_id": session_id})
    traces.sort(key=lambda t: t.get("created_at", ""))
    messages: list[dict] = []
    for t in traces:
        messages.append({"role": "user", "content": t.get("query", "")})
        messages.append(
            {
                "role": "assistant",
                "content": t.get("answer", ""),
                "citations": t.get("citations") or [],
                "query": t.get("query", ""),
            }
        )
    return messages


async def _history_from_events(container, session_id: str, user_id: str) -> list[dict]:
    events = await container.episodic_memory.session_events(session_id, user_id)
    messages: list[dict] = []
    for event in events:
        if event.get("type") not in {"user_message", "assistant_message"}:
            continue
        row = {"role": "user" if event["type"] == "user_message" else "assistant", "content": event.get("content", "")}
        if event["type"] == "assistant_message":
            row["citations"] = (event.get("metadata") or {}).get("citations", [])
        messages.append(row)
    return messages


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(request: Request, user: dict = Depends(require_user)):
    """List a user's past sessions (most recently active first) for the frontend "Recent" sidebar."""
    container = request.app.state.container
    summaries = await container.store.find("conversation_summaries", {"user_id": user["id"]})
    if summaries:
        def _session_title(summary: dict) -> str:
            raw = (summary.get("summary") or "New conversation").split(" | ", 1)[0].strip()
            return (raw[5:] if raw.startswith("user:") else raw)[:50] or "New conversation"

        sessions = [
            {
                "session_id": s["session_id"], "title": _session_title(s),
                "message_count": await container.store.count("conversation_events", {"session_id": s["session_id"]}),
                "updated_at": str(s.get("updated_at", "")),
            } for s in summaries
        ]
        return ApiResponse(data=sorted(sessions, key=lambda s: s["updated_at"], reverse=True))
    traces = await container.store.find("traces", {"user_id": user["id"]})
    # Sort ascending by time so the title comes from the session's first question
    traces.sort(key=lambda t: t.get("created_at", ""))
    groups: dict[str, dict] = {}
    for t in traces:
        sid = t.get("session_id") or ""
        if not sid:
            continue
        g = groups.setdefault(
            sid,
            {"session_id": sid, "title": "", "message_count": 0, "updated_at": ""},
        )
        if not g["title"]:
            g["title"] = (t.get("query") or "")[:50]
        g["message_count"] += 2  # One question plus one answer
        ts = t.get("created_at", "") or ""
        if ts > g["updated_at"]:
            g["updated_at"] = ts
    sessions = sorted(groups.values(), key=lambda s: s["updated_at"], reverse=True)
    return ApiResponse(data=sessions)


@router.get("/{session_id}/history", response_model=ApiResponse)
async def history(session_id: str, request: Request, user: dict = Depends(require_user)):
    container = request.app.state.container
    await _assert_session_owner(container, session_id, user["id"], require_exists=True)
    # Prefer rebuilding full history from persisted traces; fall back to working memory for empty sessions
    messages = await _history_from_events(container, session_id, user["id"])
    if not messages:
        messages = await _history_from_traces(container, session_id)
    if not messages:
        messages = await container.working_memory.history(session_id)
    return ApiResponse(data=messages)


@router.delete("/{session_id}", response_model=ApiResponse)
async def clear_session(session_id: str, request: Request, user: dict = Depends(require_user)):
    container = request.app.state.container
    await _assert_session_owner(container, session_id, user["id"], require_exists=True)
    await container.working_memory.clear(session_id)
    await container.episodic_memory.delete_session(session_id, user["id"])
    # Also delete the session's persisted traces so it disappears from the "Recent" history list
    for t in await container.store.find("traces", {"session_id": session_id}):
        await container.store.delete("traces", t["_id"])
    return ApiResponse(data={"cleared": session_id})
