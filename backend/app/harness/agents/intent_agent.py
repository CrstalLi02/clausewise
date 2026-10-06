"""Intent Agent: intent recognition / department routing / user identity / whether cross-department handling is needed."""
from __future__ import annotations

from typing import Any

from app.harness.base import Intent
from app.llm.client import ChatMessage, LLMClient
from app.storage.store import DataStore
from app.utils.logging import get_logger
from app.integrations.pi_runtime import PiAgentRuntimeClient

logger = get_logger(__name__)

INTENT_PROMPT = """You are an intent recognition assistant for policy inquiries. Determine the intent type of the user question, the departments involved, and whether cross-department collaboration is needed.

Output JSON only:
{{
  "type": "regulation_consult|process_guide|deadline_query|complaint|chitchat|other",
  "depts": ["dept_id"],           // Involved department ids, chosen from the candidate departments; use ["dept_all"] if undetermined
  "user_role": "student|teacher|admin",
  "entities": {{}},               // Key entities, e.g. {{"matter": "course withdrawal", "semester": "Fall 2025"}}
  "needs_cross_dept": false,      // Whether multiple departments are involved
  "confidence": 0.0-1.0
}}

Candidate departments:
{departments}

User profile: {profile}

User question: {query}
"""


class IntentAgent:
    def __init__(
        self, llm: LLMClient, store: DataStore, pi_runtime: PiAgentRuntimeClient | None = None,
        timeout: float = 1.0,
    ) -> None:
        self.llm = llm
        self.store = store
        self.pi_runtime = pi_runtime
        self.timeout = timeout

    async def infer(self, query: str, user_id: str = "", memory_context: str = "") -> Intent:
        departments = await self.store.list_departments()
        dept_desc = ", ".join(f"{d['_id']}({d.get('name', '')})" for d in departments) or "dept_all(general)"
        profile = await self.store.get_user_profile(user_id) or {}
        profile_text = memory_context or str(profile)[:500]

        try:
            prompt = INTENT_PROMPT.format(departments=dept_desc, profile=profile_text[:2000], query=query)
            data = None
            if self.pi_runtime is not None:
                data = await self.pi_runtime.run_json(
                    "intent", "You are a rigorous intent recognition assistant for policy inquiries.", prompt,
                    timeout_seconds=self.timeout,
                )
            if not isinstance(data, dict):
                messages = [
                    ChatMessage.system("You are a rigorous intent recognition assistant."),
                    ChatMessage.user(prompt),
                ]
                data = await self.llm.complete_json(messages, temperature=0.0)
            intent = Intent.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Intent recognition LLM failed (%s), using keyword fallback", exc)
            intent = self._keyword_fallback(query)

        # Normalize: make sure the departments are valid
        valid_depts = {d["_id"] for d in departments}
        if not intent.depts or (len(intent.depts) == 1 and intent.depts[0] == "dept_all"):
            intent.depts = sorted(valid_depts) if valid_depts else ["dept_all"]
        intent.depts = [d for d in intent.depts if d in valid_depts or d == "dept_all"] or ["dept_all"]
        return intent

    @staticmethod
    def _keyword_fallback(query: str) -> Intent:
        """Keyword rule fallback when no LLM is available."""
        dept_keywords = {
            "dept_jwc": ["course registration", "course selection", "exam", "grade", "credit", "withdraw", "academic affairs", "curriculum", "change major"],
            "dept_xsc": ["scholarship", "financial aid", "grant", "dormitory", "student club", "disciplinary", "student id", "mental health"],
            "dept_cwc": ["payment", "refund", "tuition", "reimbursement", "finance", "invoice"],
            "dept_rsc": ["human resources", "professional title", "recruitment", "salary", "leave request", "attendance"],
            "dept_yjsy": ["graduate", "master", "phd", "doctoral", "thesis", "dissertation", "supervisor", "advisor", "proposal", "defense"],
            "dept_zfxy": ["sino-french", "french", "study abroad", "exchange", "dual degree", "france", "luggage storage"],
            "dept_hqaq": ["logistics", "cafeteria", "dining hall", "apartment", "repair", "maintenance", "utilities", "security", "parking", "typhoon", "rainstorm", "flood", "emergency", "safety"],
        }
        q = query.lower()
        depts = [d for d, kws in dept_keywords.items() if any(k in q for k in kws)]
        intent_type = "other"
        if any(k in q for k in ["deadline", "when", "latest", "due", "time"]):
            intent_type = "deadline_query"
        elif any(k in q for k in ["what should i do", "how to", "how do i", "how can i", "process", "procedure", "steps"]):
            intent_type = "process_guide"
        elif any(k in q for k in ["complain", "complaint", "suggestion", "report"]):
            intent_type = "complaint"
        elif any(k in q for k in ["hello", "thank", "are you there"]) or q.strip() in {"hi", "hey"}:
            intent_type = "chitchat"
        elif depts:
            intent_type = "regulation_consult"
        return Intent(
            type=intent_type,
            depts=depts or ["dept_all"],
            needs_cross_dept=len(depts) > 1,
            confidence=0.6,
            raw={"fallback": True},
        )
