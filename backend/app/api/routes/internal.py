"""Internal endpoints: called by the pi-agent service (data/retrieval/storage), never exposed publicly.

- All endpoints require the request header `X-Internal-Token: <INTERNAL_API_TOKEN>` (see app/api/deps.require_internal).
- /internal/retrieve        Hybrid retrieval
- /internal/departments     Department list
- /internal/calendar        School calendar (global memory)
- /internal/glossary        Glossary
- /internal/feedback        Submit feedback
- /internal/feedback/pending Pending feedback
- /internal/artifacts       Save Skills/Hooks/Rules (Loop outputs)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import require_internal
from app.utils.logging import get_logger
from app.utils import metrics

logger = get_logger(__name__)
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal)],
)


class RetrieveRequest(BaseModel):
    query: str
    dept_ids: Optional[list[str]] = None
    top_k: int = 5


class FeedbackInternalRequest(BaseModel):
    query: str = ""
    answer: str = ""
    signal: str = "down"


class ArtifactRequest(BaseModel):
    type: str = Field(..., description="skill | hook | rule")
    name: str = ""
    content: str = ""
    trigger: str = ""
    steps: str = ""
    action: str = ""
    confidence: Optional[float] = None


class DepartmentAnswerRequest(BaseModel):
    query: str
    dept_id: str
    session_id: str = ""
    user_id: str = "internal"  # Callable only with the internal service token; public user identities are not accepted
    memory_context: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest, request: Request):
    container = request.app.state.container
    configured = container.settings.dept_id
    if configured and any(d != configured for d in (req.dept_ids or [configured])):
        raise HTTPException(status_code=403, detail="Department agents may not search across departments")
    effective_depts = [configured] if configured else (req.dept_ids or None)
    chunks = await container.retrieval_agent.retrieve(
        [req.query], effective_depts, top_k=req.top_k
    )
    # Fill in document titles to make citations traceable
    for c in chunks:
        if not c.get("doc_title") and c.get("doc_id"):
            doc = await container.store.get_document(c["doc_id"])
            if doc:
                c["doc_title"] = doc.get("title", "")
    return {"code": 0, "message": "ok", "data": chunks}


@router.post("/dept/answer")
async def department_answer(req: DepartmentAnswerRequest, request: Request):
    container = request.app.state.container
    configured = container.settings.dept_id
    if not configured:
        raise HTTPException(status_code=503, detail="This instance is not a department agent")
    if req.dept_id != configured:
        raise HTTPException(status_code=403, detail="Requested department does not match DEPT_ID")
    metrics.DEPT_AGENT_INFLIGHT.labels(dept=configured).inc()
    try:
        result = await container.orchestrator.answer(
            req.query, session_id=req.session_id, user_id=req.user_id, dept_ids=[configured],
            external_memory_context=req.memory_context,
        )
        metrics.DEPT_AGENT_REQUEST.labels(dept=configured, status="success").inc()
        return {"code": 0, "message": "ok", "data": result}
    except Exception:
        metrics.DEPT_AGENT_REQUEST.labels(dept=configured, status="error").inc()
        raise
    finally:
        metrics.DEPT_AGENT_INFLIGHT.labels(dept=configured).dec()


@router.get("/departments")
async def departments(request: Request):
    container = request.app.state.container
    return {"code": 0, "message": "ok", "data": await container.store.list_departments()}


@router.get("/calendar")
async def calendar(request: Request):
    container = request.app.state.container
    return {"code": 0, "message": "ok", "data": await container.global_memory.get_calendar()}


@router.get("/glossary")
async def glossary(request: Request):
    container = request.app.state.container
    return {"code": 0, "message": "ok", "data": await container.store.list_glossary()}


@router.post("/feedback")
async def feedback(req: FeedbackInternalRequest, request: Request):
    container = request.app.state.container
    await container.feedback_collector.collect_explicit(
        session_id="",
        user_id="pi-agent",
        query=req.query,
        answer=req.answer,
        signal=req.signal,
    )
    return {"code": 0, "message": "ok", "data": {"received": req.signal}}


@router.get("/feedback/pending")
async def feedback_pending(request: Request):
    container = request.app.state.container
    return {"code": 0, "message": "ok", "data": await container.feedback_collector.pending()}


@router.post("/artifacts")
async def artifacts(req: ArtifactRequest, request: Request):
    container = request.app.state.container
    now = _now()
    auto = container.settings.loop_phase == "human_out_of_loop"
    conf = req.confidence if req.confidence is not None else 0.6
    status = "active" if (auto or conf >= container.settings.hook_high_confidence) else "pending"

    artifact: dict[str, Any]
    if req.type == "skill":
        artifact = {
            "_id": "skill_" + uuid.uuid4().hex,
            "name": req.name or "auto_skill",
            "dept_id": "",
            "scope": "global",
            "trigger": {"intent_patterns": [req.trigger] if req.trigger else [], "confidence_threshold": 0.75},
            "action": {"type": "workflow", "steps": [{"step": 1, "action": "retrieve", "params": {"query": req.steps or req.name}}]},
            "metrics": {"trigger_count": 0, "success_rate": 0.0},
            "version": 1,
            "status": status,
            "auto_generated": True,
            "confidence": conf,
            "created_by": "pi_loop",
            "created_at": now,
        }
        await container.store.upsert_skill(artifact)
    elif req.type == "hook":
        artifact = {
            "_id": "hook_" + uuid.uuid4().hex,
            "name": req.name or "auto_hook",
            "dept_id": "",
            "scope": "global",
            "trigger": {"intent_patterns": [req.trigger] if req.trigger else []},
            "action": {"type": req.action or "cross_dept_retrieval"},
            "confidence": conf,
            "status": status,
            "auto_generated": True,
            "created_by": "pi_loop",
            "created_at": now,
        }
        await container.store.upsert_hook(artifact)
    elif req.type == "rule":
        artifact = {
            "_id": "rule_" + uuid.uuid4().hex,
            "name": req.name or "auto_rule",
            "scope": "global",
            "content": req.content or req.trigger,
            "priority": 50,
            "confidence": conf,
            "status": status,
            "auto_generated": True,
            "created_by": "pi_loop",
            "created_at": now,
        }
        await container.store.upsert_rule(artifact)
    else:
        return {"code": 1, "message": f"Unknown artifact type: {req.type}", "data": None}

    return {"code": 0, "message": "ok", "data": artifact}
