"""Admin endpoints: Skills / Loop / Glossary / review center / dashboard / department sub-agent visualization.

Apart from login/Q&A, all admin-side endpoints require admin privileges (Bearer token).
Department admins (non-empty dept_id) only see their own department's data; system admins (empty dept_id) see everything.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import require_admin, scope_dept
from app.api.schemas import ApiResponse, GlossaryCreate, LoopPhaseUpdate, ReviewSubmit
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scoped(items: list[dict[str, Any]], scope: Optional[str], dept_field: str = "dept_id", include_global: bool = False) -> list[dict[str, Any]]:
    """Filter by the admin's visible scope: return everything when scope is empty; otherwise only their own department (global items may be included)."""
    if not scope:
        return items
    out = []
    for it in items:
        if it.get(dept_field) == scope:
            out.append(it)
        elif include_global and it.get("scope") == "global":
            out.append(it)
    return out


def _check_scope(owner_dept: str, scope: Optional[str]) -> None:
    """Verify that the resource belongs to the current admin's department scope."""
    if scope and owner_dept != scope:
        raise HTTPException(status_code=403, detail="Not authorized to access data of other departments")


# ==================== Dashboard (Loop overview) ====================
@router.get("/dashboard", response_model=ApiResponse)
async def dashboard(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    store = container.store
    settings = container.settings
    scope = scope_dept(user)

    departments = _scoped(await store.list_departments(), scope, dept_field="_id")
    docs = _scoped(await store.list_documents(), scope)
    chunks = _scoped(await store.list_all_chunks(), scope)
    skills = _scoped(await store.list_skills(), scope, include_global=True)
    hooks = _scoped(await store.list_hooks(), scope, include_global=True)
    rules = _scoped(await store.list_rules(), scope, include_global=True)
    feedback = await container.feedback_collector.stats()
    traces = await store.list_recent_traces(limit=300)
    pending_reviews = _scoped(await store.list_review_orders(status="pending"), scope)
    test_questions = _scoped(await store.list_test_questions(), scope)
    relations = await store.list_relations()
    if scope:
        relations = [r for r in relations if r.get("from_dept") == scope or r.get("to_dept") == scope]

    dept_rows = []
    for d in departments:
        did = d.get("_id", "")
        stats = d.get("review_stats") or {"total": 0, "correct": 0, "accuracy": 0.0}
        dept_rows.append(
            {
                "_id": did,
                "name": d.get("name", did),
                "name_en": d.get("name_en", ""),
                "category": d.get("category", ""),
                "admin_users": d.get("admin_users", []),
                "agent_config": d.get("agent_config", {}),
                "loop_phase": d.get("loop_phase", "human_in_loop"),
                "review_stats": stats,
                "fade_out": d.get("fade_out"),
                "doc_count": sum(1 for x in docs if x.get("dept_id") == did),
                "chunk_count": sum(1 for x in chunks if x.get("dept_id") == did),
                "skill_count": sum(1 for s in skills if s.get("dept_id") == did or s.get("scope") == "global"),
                "conflict_count": sum(
                    1 for r in relations if r.get("relation_type") == "conflict"
                    and (r.get("from_dept") == did or r.get("to_dept") == did)
                ),
            }
        )

    return ApiResponse(
        data={
            "loop_phase_global": settings.loop_phase,
            "loop_enabled": settings.loop_enabled,
            "thresholds": {
                "accuracy": settings.review_accuracy_threshold,
                "min_samples": settings.review_min_samples,
                "high_confidence": settings.hook_high_confidence,
                "skill_min_cluster": settings.skill_min_cluster,
                "skill_sandbox_min_success": settings.skill_sandbox_min_success,
            },
            "departments": dept_rows,
            "skills": skills,
            "hooks": hooks,
            "rules": rules,
            "feedback": feedback,
            "trace_count": len(traces),
            "pending_review_count": len(pending_reviews),
            "test_question_count": len(test_questions),
        }
    )


# ==================== Department sub-agent visualization ====================
@router.get("/agents", response_model=ApiResponse)
async def agents(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    store = container.store
    scope = scope_dept(user)

    departments = _scoped(await store.list_departments(), scope, dept_field="_id")
    docs = _scoped(await store.list_documents(), scope)
    skills = _scoped(await store.list_skills(), scope)
    hooks = _scoped(await store.list_hooks(), scope, include_global=True)

    rows = []
    for d in departments:
        did = d.get("_id", "")
        topic_rows = await store.find("memory_topics", {"dept_id": did})
        topic_counts: dict[str, int] = {}
        for topic in topic_rows:
            key = topic.get("topic_key", "other")
            topic_counts[key] = topic_counts.get(key, 0) + int(topic.get("count", 0))
        hot = sorted(topic_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        config = d.get("agent_config") or {}
        rows.append(
            {
                "_id": did,
                "name": d.get("name", did),
                "name_en": d.get("name_en", ""),
                "agent_config": config,
                "model": config.get("model", container.settings.deepseek_model),
                "temperature": config.get("temperature", container.settings.deepseek_temperature),
                "loop_phase": d.get("loop_phase", "human_in_loop"),
                "review_stats": d.get("review_stats") or {"total": 0, "correct": 0, "accuracy": 0.0},
                "doc_count": sum(1 for x in docs if x.get("dept_id") == did),
                "skill_count": sum(1 for s in skills if s.get("dept_id") == did),
                "hook_count": sum(1 for h in hooks if h.get("dept_id") == did or h.get("scope") == "global"),
                "hot_queries": [{"q": q, "n": c} for q, c in hot],
                "replicas": 1 if config.get("replicas") is None else config.get("replicas"),
            }
        )
    return ApiResponse(data=rows)


# ==================== Review center ====================
@router.get("/review/orders", response_model=ApiResponse)
async def list_review_orders(
    request: Request,
    dept_id: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    container = request.app.state.container
    scope = scope_dept(user)
    if scope:
        dept_id = scope  # Department admins can only see their own department's review orders
    return ApiResponse(data=await container.store.list_review_orders(dept_id=dept_id, status=status))


@router.get("/review/orders/{order_id}", response_model=ApiResponse)
async def get_review_order(order_id: str, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    order = await container.store.get_review_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Review order not found")
    _check_scope(order.get("dept_id", ""), scope_dept(user))
    return ApiResponse(data=order)


@router.post("/review/orders/{order_id}/submit", response_model=ApiResponse)
async def submit_review(order_id: str, body: ReviewSubmit, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    order = await container.store.get_review_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Review order not found")
    _check_scope(order.get("dept_id", ""), scope_dept(user))
    try:
        order = await container.review_engine.submit_review(
            order_id, [v.model_dump() for v in body.verdicts], user["id"]
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=order)


@router.get("/review/stats", response_model=ApiResponse)
async def review_stats(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    store = container.store
    scope = scope_dept(user)
    departments = _scoped(await store.list_departments(), scope, dept_field="_id")
    rows = []
    for d in departments:
        did = d.get("_id", "")
        stats = d.get("review_stats") or {"total": 0, "correct": 0, "accuracy": 0.0}
        rows.append(
            {
                "dept_id": did,
                "name": d.get("name", did),
                "loop_phase": d.get("loop_phase", "human_in_loop"),
                "stats": stats,
                "fade_out": d.get("fade_out"),
                "threshold": container.settings.review_accuracy_threshold,
                "min_samples": container.settings.review_min_samples,
            }
        )
    return ApiResponse(data=rows)


# ==================== (Re)generate a review order for a document ====================
@router.post("/documents/{doc_id}/review", response_model=ApiResponse)
async def generate_review(doc_id: str, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    doc = await container.store.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    _check_scope(doc.get("dept_id", ""), scope_dept(user))
    order = await container.review_engine.create_review_order(doc)
    return ApiResponse(data=order)


# ==================== Loop observation ====================
@router.get("/feedback/pending", response_model=ApiResponse)
async def pending_feedback(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    scope = scope_dept(user)
    pending = await container.feedback_collector.pending()
    if scope:
        pending = [p for p in pending if (p.get("detail") or {}).get("dept_id") == scope]
    return ApiResponse(data=pending)


@router.get("/traces", response_model=ApiResponse)
async def list_traces(request: Request, limit: int = 50, user: dict = Depends(require_admin)):
    container = request.app.state.container
    scope = scope_dept(user)
    traces = await container.store.list_recent_traces(limit=limit)
    if scope:
        traces = [t for t in traces if scope in (t.get("intent") or {}).get("depts", [])]
    return ApiResponse(data=traces)


@router.post("/loop/phase", response_model=ApiResponse)
async def set_loop_phase(body: LoopPhaseUpdate, request: Request, user: dict = Depends(require_admin)):
    """Set the global Loop phase (only affects the auto-apply threshold for Skills/Hooks/Rules).

    Note: each department's human review phase (loop_phase) is driven independently by cumulative accuracy and sample size,
    and is not affected by this global switch, so departments that have not met the bar are never pushed to "human out of the loop" by mistake. System admins only.
    """
    if scope_dept(user):
        raise HTTPException(status_code=403, detail="Only system admins can set the global phase")
    container = request.app.state.container
    if body.phase not in ("human_in_loop", "human_on_loop", "human_out_of_loop"):
        raise HTTPException(status_code=400, detail="Invalid phase")
    container.settings.loop_phase = body.phase
    return ApiResponse(data={"loop_phase": body.phase})


# ==================== Skills / Hooks / Rules / Glossary ====================
@router.get("/skills", response_model=ApiResponse)
async def list_skills(request: Request, status: Optional[str] = None, user: dict = Depends(require_admin)):
    container = request.app.state.container
    skills = await container.store.list_skills(status=status)
    return ApiResponse(data=_scoped(skills, scope_dept(user), include_global=True))


@router.post("/skills/{skill_id}/approve", response_model=ApiResponse)
async def approve_skill(skill_id: str, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    skill = await container.store.get_skill(skill_id)
    if skill is None:
        return ApiResponse(code=1, message="Skill not found")
    scope = scope_dept(user)
    if scope and skill.get("dept_id") != scope:
        raise HTTPException(status_code=403, detail="Not authorized to review Skills of other departments")
    skill["status"] = "active"
    await container.store.upsert_skill(skill)
    return ApiResponse(data=skill)


@router.post("/loop/run", response_model=ApiResponse)
async def run_loop(request: Request, user: dict = Depends(require_admin)):
    if scope_dept(user):
        raise HTTPException(status_code=403, detail="Only system admins can trigger the global Loop")
    container = request.app.state.container
    job = await container.job_queue.enqueue("run_loop", {"requested_by": user["id"]})
    return ApiResponse(data={
        "queued": True, "job_id": job["_id"], "status": job["status"],
        "message": "The Loop has been queued; the page will keep tracking the results of all five stages",
    })


@router.get("/loop/jobs/{job_id}", response_model=ApiResponse)
async def get_loop_job(job_id: str, request: Request, user: dict = Depends(require_admin)):
    if scope_dept(user):
        raise HTTPException(status_code=403, detail="Only system admins can view global Loop jobs")
    job = await request.app.state.container.store.get("async_jobs", job_id)
    if not job or job.get("type") != "run_loop":
        raise HTTPException(status_code=404, detail="Loop job not found")
    return ApiResponse(data=job)


@router.get("/loop/jobs", response_model=ApiResponse)
async def list_loop_jobs(request: Request, limit: int = 10, user: dict = Depends(require_admin)):
    if scope_dept(user):
        raise HTTPException(status_code=403, detail="Only system admins can view global Loop jobs")
    jobs = await request.app.state.container.store.find("async_jobs", {"type": "run_loop"})
    jobs.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
    return ApiResponse(data=jobs[: max(1, min(limit, 50))])


@router.get("/loop/stats", response_model=ApiResponse)
async def loop_stats(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    return ApiResponse(data=await container.loop_engine.stats())


@router.get("/system-insights", response_model=ApiResponse)
async def system_insights(request: Request, user: dict = Depends(require_admin)):
    """Aggregate the memory, fact, and evolution planes, returning only the stats and non-sensitive metadata the admin dashboard needs."""
    container = request.app.state.container
    store = container.store
    scope = scope_dept(user)

    docs = _scoped(await store.list_documents(), scope)
    chunks = _scoped(await store.list_all_chunks(), scope)
    relations = await store.list_relations()
    if scope:
        relations = [r for r in relations if r.get("from_dept") == scope or r.get("to_dept") == scope]

    traces = await store.list_recent_traces(limit=500)
    if scope:
        traces = [t for t in traces if scope in (t.get("intent") or {}).get("depts", [])]
    session_ids = {t.get("session_id") for t in traces if t.get("session_id")}
    events = await store.find("conversation_events")
    summaries = await store.find("conversation_summaries")
    if scope:
        events = [e for e in events if e.get("session_id") in session_ids]
        summaries = [s for s in summaries if s.get("session_id") in session_ids]

    user_items = await store.find("user_memory_items")
    candidates = await store.find("memory_candidates")
    org_items = await store.find("org_memory_items")
    topics = await store.find("memory_topics")
    usage = await store.find("memory_usage")
    if scope:
        # Department admins only see their own department's/global organizational memory; user long-term memory stats are not exposed.
        user_items = []
        candidates = []
        org_items = [m for m in org_items if m.get("scope") == "global" or m.get("dept_id") == scope]
        topics = [m for m in topics if m.get("dept_id") == scope]
        usage = [m for m in usage if m.get("session_id") in session_ids]

    skills = _scoped(await store.list_skills(), scope, include_global=True)
    hooks = _scoped(await store.list_hooks(), scope, include_global=True)
    rules = _scoped(await store.list_rules(), scope, include_global=True)
    artifact_ids = {x.get("_id") for x in skills + hooks + rules}
    experiments = [x for x in await store.find("experiments") if not scope or x.get("artifact_id") in artifact_ids]
    executions = [x for x in await store.find("strategy_executions") if not scope or x.get("artifact_id") in artifact_ids]
    versions = [x for x in await store.find("strategy_versions") if not scope or x.get("artifact_id") in artifact_ids]
    proposals = await store.find("strategy_proposals")
    if scope:
        proposals = [p for p in proposals if any(skill_id in artifact_ids for skill_id in p.get("skill_ids", []))]

    feedback = await store.find("feedback")
    if scope:
        trace_ids = {t.get("_id") for t in traces}
        feedback = [f for f in feedback if f.get("trace_id") in trace_ids or (f.get("detail") or {}).get("dept_id") == scope]

    def count_status(rows: list[dict[str, Any]], status: str) -> int:
        return sum(1 for row in rows if row.get("status") == status)

    return ApiResponse(data={
        "memory_planes": [
            {"key": "working", "name": "Working memory", "count": len(session_ids), "detail": f"{len(session_ids)} active/traceable sessions", "store": "Redis · TTL"},
            {"key": "episodic", "name": "Episodic memory", "count": len(events), "detail": f"{len(events)} events / {len(summaries)} summaries", "store": "MongoDB · Append-only"},
            {"key": "user", "name": "User semantic memory", "count": count_status(user_items, "active"), "detail": f"{len(candidates)} candidates pending confirmation" if not scope else "User privacy is hidden in the department view", "store": "MongoDB · Consent"},
            {"key": "organization", "name": "Organizational knowledge memory", "count": count_status(org_items, "active"), "detail": f"{len(org_items)} source-bound knowledge items", "store": "MongoDB · Source-bound"},
            {"key": "learning", "name": "Procedural learning memory", "count": len(skills) + len(hooks) + len(rules), "detail": f"{len(skills)} Skills · {len(hooks)} Hooks · {len(rules)} Rules", "store": "Versioned Policy"},
        ],
        "fact_plane": {
            "documents": len(docs), "active_documents": count_status(docs, "active"),
            "chunks": len(chunks), "relations": len(relations),
            "conflicts": sum(1 for r in relations if r.get("relation_type") == "conflict"),
        },
        "governance": {
            "usage_records": len(usage),
            "stale_org_memory": count_status(org_items, "stale"),
            "pending_candidates": count_status(candidates, "pending"),
        },
        "evolution": {
            "strategy_versions": len(versions), "executions": len(executions),
            "experiments": experiments, "proposals": proposals[:20],
            "treatment": sum(1 for x in executions if x.get("group") == "treatment"),
            "control": sum(1 for x in executions if x.get("group") == "control"),
        },
        "signals": {
            key: sum(1 for row in feedback if row.get("signal") == key)
            for key in ("up", "down", "correction", "copy", "follow_up", "abandon", "verifier_pass", "verifier_fail")
        },
        "recent_traces": [
            {"id": t.get("_id"), "query": t.get("query", ""), "latency_ms": t.get("latency_ms", 0),
             "success": t.get("success", False), "intent": (t.get("intent") or {}).get("type", ""),
             "created_at": str(t.get("created_at", ""))}
            for t in traces[:12]
        ],
    })


@router.get("/glossary", response_model=ApiResponse)
async def list_glossary(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    return ApiResponse(data=await container.store.list_glossary())


@router.post("/glossary", response_model=ApiResponse)
async def create_glossary(body: GlossaryCreate, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    entry = {
        "_id": "glossary_" + uuid.uuid4().hex,
        "canonical": body.canonical,
        "synonyms": body.synonyms,
        "dept_id": body.dept_id,
        "created_by": "admin",
        "created_at": _now(),
    }
    await container.store.upsert_glossary(entry)
    return ApiResponse(data=entry)


@router.get("/hooks", response_model=ApiResponse)
async def list_hooks(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    return ApiResponse(data=_scoped(await container.store.list_hooks(), scope_dept(user), include_global=True))


@router.get("/rules", response_model=ApiResponse)
async def list_rules(request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    return ApiResponse(data=_scoped(await container.store.list_rules(), scope_dept(user), include_global=True))
