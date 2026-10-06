"""Health check / readiness probe."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request):
    container = request.app.state.container
    issues = []
    if container.mongo is not None and container.mongo.db is None:
        issues.append("mongodb")
    if container.session_store is not None and hasattr(container.session_store, "redis") and container.session_store._redis is None:
        issues.append("redis")
    if issues:
        return JSONResponse(status_code=503, content={"status": "not_ready", "issues": issues})
    return {"status": "ready"}
