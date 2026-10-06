"""Aggregates all API routes."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, auth, chat, departments, documents, feedback, health, internal, memory

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(documents.router)
api_router.include_router(departments.router)
api_router.include_router(feedback.router)
api_router.include_router(admin.router)
api_router.include_router(internal.router)
api_router.include_router(memory.router)

# Health checks are not mounted under the v1 prefix
root_router = APIRouter()
root_router.include_router(health.router)
