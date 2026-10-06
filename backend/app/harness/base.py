"""Shared Harness-layer types: Intent / Answer / VerificationResult / Trace."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

INTENT_TYPES = ("regulation_consult", "process_guide", "deadline_query", "complaint", "chitchat", "other")


@dataclass
class Intent:
    type: str = "other"
    depts: list[str] = field(default_factory=list)
    user_role: str = "student"
    entities: dict[str, Any] = field(default_factory=dict)
    needs_cross_dept: bool = False
    confidence: float = 0.5
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intent":
        if not isinstance(data, dict):
            return cls()
        t = data.get("type", "other")
        if t not in INTENT_TYPES:
            t = "other"
        return cls(
            type=t,
            depts=[str(d) for d in (data.get("depts") or [])],
            user_role=str(data.get("user_role", "student")),
            entities=data.get("entities") or {},
            needs_cross_dept=bool(data.get("needs_cross_dept", False)),
            confidence=float(data.get("confidence", 0.5)),
            raw=data,
        )


@dataclass
class Citation:
    doc_id: str = ""
    doc_title: str = ""
    dept_id: str = ""
    chunk_index: int = 0
    section_path: list[str] = field(default_factory=list)
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "dept_id": self.dept_id,
            "chunk_index": self.chunk_index,
            "section_path": self.section_path,
            "snippet": self.snippet,
        }


@dataclass
class Answer:
    content: str = ""
    citations: list[Citation] = field(default_factory=list)
    dept_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "citations": [c.to_dict() for c in self.citations],
            "dept_ids": self.dept_ids,
            "confidence": self.confidence,
            "verification": self.verification,
        }


@dataclass
class VerificationResult:
    passed: bool = True
    score: float = 1.0
    issues: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationResult":
        if not isinstance(data, dict):
            return cls()
        return cls(
            passed=bool(data.get("passed", data.get("pass", True))),
            score=float(data.get("score", 1.0)),
            issues=[str(i) for i in (data.get("issues") or [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "score": self.score, "issues": self.issues}
