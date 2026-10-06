"""API request/response models."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None


class ChatRequest(BaseModel):
    query: str = Field(..., description="User question")
    session_id: Optional[str] = None
    dept_ids: Optional[list[str]] = None


class FeedbackRequest(BaseModel):
    session_id: str = ""
    query: str = ""
    answer: str = ""
    signal: str = Field(..., description="up | down | correction")
    detail: Optional[dict[str, Any]] = None


class ImplicitFeedbackRequest(BaseModel):
    session_id: str
    signal: str = Field(..., description="copy | follow_up | abandon")
    query: str = ""
    answer: str = ""
    detail: Optional[dict[str, Any]] = None


class DepartmentCreate(BaseModel):
    id: str
    name: str = ""
    name_en: str = ""
    category: str = "general"
    admin_users: list[str] = Field(default_factory=list)
    agent_config: dict[str, Any] = Field(default_factory=dict)


class DocumentStatusUpdate(BaseModel):
    status: str = Field(..., description="draft | review | active | archived | deleted")


class GlossaryCreate(BaseModel):
    canonical: str
    synonyms: list[str] = Field(default_factory=list)
    dept_id: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class ReviewVerdict(BaseModel):
    index: int
    correct: bool = False
    correction: str = ""


class ReviewSubmit(BaseModel):
    verdicts: list[ReviewVerdict] = Field(default_factory=list)


class LoopPhaseUpdate(BaseModel):
    phase: str = Field(..., description="human_in_loop | human_on_loop | human_out_of_loop")


class UserMemoryCreate(BaseModel):
    key: str
    value: Any
    category: str = "preference"
    consent: bool = True


class SourceRef(BaseModel):
    doc_id: str
    chunk_id: str
    document_version: str = ""


class OrganizationMemoryCreate(BaseModel):
    scope: str = "department"
    dept_id: str = ""
    type: str = "faq"
    title: str
    content: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    access_scope: list[str] = Field(default_factory=lambda: ["student", "teacher", "admin"])
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
