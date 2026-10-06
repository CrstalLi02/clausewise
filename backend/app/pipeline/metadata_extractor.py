"""Metadata extraction: the LLM extracts effective_date / doc_type / keywords / applicable_scope / cross_refs.

Also provides jieba keyword extraction (used for BM25 / chunk keywords).
"""
from __future__ import annotations

from typing import Any

from app.llm.client import ChatMessage, LLMClient
from app.utils.logging import get_logger

logger = get_logger(__name__)

EXTRACT_PROMPT = """You are a policy document metadata extraction assistant. Extract metadata from the given document text and output JSON only, without any explanation.

Fields:
- effective_date: effective date (YYYY-MM-DD, null if none)
- doc_type: document type, one of regulation(policy/regulation)/notice(notice)/guide(guide)/form(form)/other
- keywords: list of keywords (3-8 English phrases)
- applicable_scope: list of applicable audiences, a subset of: undergraduate(undergraduate students)/graduate(graduate students)/faculty(faculty)/staff(administrative staff)/all(everyone)
- cross_refs: list of other policy document names referenced in the text ([] if none)

JSON structure:
{{"effective_date": "...", "doc_type": "...", "keywords": [...], "applicable_scope": [...], "cross_refs": [...]}}

Document title: {title}

Document text (excerpt):
{text}
"""


class MetadataExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def extract(self, title: str, text: str) -> dict[str, Any]:
        text = text[:6000]  # Truncate to control cost
        messages = [
            ChatMessage.system("You are a rigorous policy document metadata extraction assistant."),
            ChatMessage.user(EXTRACT_PROMPT.format(title=title, text=text)),
        ]
        try:
            data = await self.llm.complete_json(messages, temperature=0.0)
            return self._normalize(data)
        except Exception as exc:  # noqa: BLE001 - metadata failures must not block ingestion
            logger.warning("Metadata extraction failed (%s), using defaults", exc)
            return {
                "effective_date": None,
                "doc_type": "other",
                "keywords": [],
                "applicable_scope": ["all"],
                "cross_refs": [],
            }

    @staticmethod
    def _normalize(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {"effective_date": None, "doc_type": "other", "keywords": [], "applicable_scope": ["all"], "cross_refs": []}
        allowed_types = {"regulation", "notice", "guide", "form", "other"}
        allowed_scope = {"undergraduate", "graduate", "faculty", "staff", "all"}
        return {
            "effective_date": data.get("effective_date") or None,
            "doc_type": data.get("doc_type") if data.get("doc_type") in allowed_types else "other",
            "keywords": [str(k) for k in (data.get("keywords") or [])][:8],
            "applicable_scope": [s for s in (data.get("applicable_scope") or []) if s in allowed_scope] or ["all"],
            "cross_refs": [str(r) for r in (data.get("cross_refs") or [])],
        }


def extract_keywords(text: str, top_k: int = 6) -> list[str]:
    """jieba TF-IDF keyword extraction (fully local, used for chunk keywords / BM25 enrichment)."""
    try:
        import jieba.analyse  # Lazy import

        return jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
    except Exception:  # noqa: BLE001
        return []
