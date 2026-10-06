"""Dept Router (automatic department routing agent): matches a student question to the best-fitting department.

Strategy: exact keyword match (fast, explainable) → LLM semantic routing (fallback) → all departments.
Returns the routing result (dept_ids / matched_by / confidence / reasons / dept_names),
which the frontend uses to display "Automatically routed to the XX department".
"""
from __future__ import annotations

from typing import Any

from app.llm.client import ChatMessage, LLMClient
from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Department keyword routing table (covers all departments; a hit routes to that department, multiple departments allowed)
DEPT_KEYWORDS: dict[str, list[str]] = {
    "dept_jwc": ["course registration", "course selection", "withdraw", "exam", "grade", "credit", "student status", "enrollment status", "change major", "minor", "curriculum", "gpa", "retake", "academic affairs"],
    "dept_xsc": ["scholarship", "financial aid", "grant", "dormitory", "student club", "disciplinary", "student id", "mental health", "comprehensive evaluation", "work-study", "leave request", "student affairs"],
    "dept_cwc": ["payment", "refund", "tuition", "reimbursement", "finance", "invoice", "receipt of funds", "charge", "fee"],
    "dept_rsc": ["human resources", "professional title", "recruitment", "salary", "attendance", "social insurance", "onboarding", "resignation", "contract", "appointment", "personnel"],
    "dept_yjsy": ["graduate", "master", "phd", "doctoral", "degree", "thesis", "dissertation", "supervisor", "advisor", "proposal", "defense", "blind review", "mid-term", "graduate school"],
    "dept_zfxy": ["sino-french", "french", "study abroad", "exchange", "dual degree", "france", "luggage storage", "psychological assessment", "sino-french institute"],
    "dept_hqaq": ["logistics", "cafeteria", "dining hall", "apartment", "repair", "maintenance", "utilities", "security", "parking", "typhoon", "rainstorm", "flood", "emergency", "power outage", "safety"],
}

ROUTE_PROMPT = """You are a department routing assistant. Determine which department should best answer the student question, and output JSON:
{{"depts": ["dept_id"], "confidence": 0.0-1.0, "reason": "short reason"}}

Candidate departments:
{departments}

Student question: {query}
"""


class DeptRouter:
    """Automatic department routing: student question → best-matching department."""

    def __init__(self, llm: LLMClient, store: DataStore) -> None:
        self.llm = llm
        self.store = store

    async def route(self, query: str) -> dict[str, Any]:
        departments = await self.store.list_departments()
        dept_names = {d["_id"]: d.get("name", d["_id"]) for d in departments}
        valid = set(dept_names)

        # 1) Exact keyword match (fast, explainable)
        matched, reasons = self._keyword_match(query, valid)
        if matched:
            return self._result(matched, "keyword", min(0.95, 0.6 + 0.1 * len(matched)), reasons, dept_names)

        # 2) LLM semantic routing (when no keyword matches)
        try:
            dept_desc = ", ".join(f"{d['_id']}({d.get('name', '')})" for d in departments) or "dept_all(general)"
            data = await self.llm.complete_json(
                [ChatMessage.system("You are a department routing assistant."), ChatMessage.user(ROUTE_PROMPT.format(departments=dept_desc, query=query))],
                temperature=0.0,
            )
            depts = [d for d in (data.get("depts") or []) if d in valid]
            if depts:
                return self._result(depts, "llm", float(data.get("confidence", 0.7)), [data.get("reason", "")], dept_names)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Department routing LLM failed (%s), falling back to all departments", exc)

        # 3) All departments (no match)
        return self._result([], "all", 0.3, ["No specific department matched; searching all departments"], dept_names)

    @staticmethod
    def _keyword_match(query: str, valid: set[str]) -> tuple[list[str], list[str]]:
        matched: list[str] = []
        reasons: list[str] = []
        for dept, kws in DEPT_KEYWORDS.items():
            if dept not in valid:
                continue
            q = query.lower()
            hits = [k for k in kws if k in q]
            if hits:
                matched.append(dept)
                reasons.append(f"Matched keyword \"{hits[0]}\"")
        return matched, reasons

    @staticmethod
    def _result(dept_ids: list[str], matched_by: str, confidence: float, reasons: list[str], dept_names: dict[str, str]) -> dict[str, Any]:
        return {
            "dept_ids": dept_ids,
            "dept_names": [dept_names.get(d, d) for d in dept_ids],
            "matched_by": matched_by,
            "confidence": round(float(confidence), 2),
            "reasons": reasons,
        }
