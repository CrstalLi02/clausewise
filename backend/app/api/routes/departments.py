"""Department management endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import ApiResponse, DepartmentCreate
from app.api.deps import require_admin, require_user, scope_dept
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=ApiResponse)
async def list_departments(request: Request, _: dict = Depends(require_user)):
    container = request.app.state.container
    return ApiResponse(data=await container.store.list_departments())


@router.post("", response_model=ApiResponse)
async def create_department(body: DepartmentCreate, request: Request, user: dict = Depends(require_admin)):
    if scope_dept(user):
        raise HTTPException(status_code=403, detail="Only system admins can create departments")
    container = request.app.state.container
    now = datetime.now(timezone.utc).isoformat()
    dept = {
        "_id": body.id,
        "name": body.name,
        "name_en": body.name_en,
        "category": body.category,
        "admin_users": body.admin_users,
        "agent_config": body.agent_config or {"model": "deepseek-v4-flash", "temperature": 0.1},
        "created_at": now,
        "updated_at": now,
    }
    await container.store.upsert_department(dept)
    return ApiResponse(data=dept)


@router.get("/{dept_id}/conflicts", response_model=ApiResponse)
async def dept_conflicts(dept_id: str, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    scope = scope_dept(user)
    if scope and scope != dept_id:
        raise HTTPException(status_code=403, detail="Not authorized to view conflicts of other departments")
    rels = await container.store.list_relations(relation_type="conflict", dept_id=dept_id)
    return ApiResponse(data=rels)
