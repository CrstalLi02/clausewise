"""Organizational knowledge memory: derived knowledge with source, version, review, time validity, and department permissions."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.memory.policy import MemoryPolicy
from app.storage.store import DataStore


class OrganizationMemory:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def publish(
        self, scope: str, memory_type: str, title: str, content: str,
        source_refs: list[dict[str, Any]], dept_id: str = "", authority: str = "official_document",
        review_status: str = "approved", access_scope: list[str] | None = None,
        effective_from: Any = None, effective_to: Any = None, actor_id: str = "system",
    ) -> dict[str, Any]:
        if memory_type in {"faq", "procedure_tip", "conflict_resolution"} and not source_refs:
            raise ValueError("Organizational knowledge must be bound to an official source")
        verified_refs = await self._verify_sources(source_refs, dept_id if scope == "department" else "")
        if source_refs and not verified_refs:
            raise ValueError("Organizational knowledge source is invalid or the document is not active")
        item = {
            "_id": "orgmem_" + uuid.uuid4().hex, "scope": scope, "dept_id": dept_id,
            "type": memory_type, "title": title, "content": content,
            "source_refs": verified_refs, "source_doc_ids": sorted({r["doc_id"] for r in verified_refs}),
            "authority": authority, "confidence": 1.0, "review_status": review_status,
            "effective_from": effective_from, "effective_to": effective_to, "status": "active",
            "access_scope": access_scope or ["student", "teacher", "admin"],
            "usage_count": 0, "revision": 1, "created_by": actor_id,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        await self.store.upsert("org_memory_items", item)
        return item

    async def recall(
        self, query: str, dept_ids: list[str], role: str = "student", limit: int = 8
    ) -> list[dict[str, Any]]:
        from app.retrieval.bm25 import tokenize

        q_tokens = set(tokenize(query))
        candidates = [
            row for row in await self.store.find("org_memory_items", {"status": "active"})
            if MemoryPolicy.org_item_readable(row, dept_ids, role)
        ]
        valid: list[tuple[float, dict[str, Any]]] = []
        for item in candidates:
            sources = await self._verify_sources(item.get("source_refs") or [], item.get("dept_id", ""))
            if item.get("source_refs") and len(sources) != len(item.get("source_refs")):
                await self._mark_stale(item, "source_document_inactive_or_version_changed")
                continue
            text_tokens = set(tokenize(f"{item.get('title', '')} {item.get('content', '')}"))
            relevance = len(q_tokens & text_tokens) / max(len(q_tokens), 1) if q_tokens else 0.0
            score = relevance * MemoryPolicy.authority(item)
            if score > 0:
                valid.append((score, item))
        valid.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in valid[:limit]]

    async def source_chunks(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        chunks: list[dict[str, Any]] = []
        for item in items:
            await self.store.increment("org_memory_items", item["_id"], "usage_count", 1)
            for ref in item.get("source_refs") or []:
                chunk_id = ref.get("chunk_id")
                if not chunk_id or chunk_id in seen:
                    continue
                chunk = await self.store.get("chunks", chunk_id)
                doc = await self.store.get_document(ref.get("doc_id", ""))
                if chunk and doc and doc.get("status") == "active" and doc.get("version") == ref.get("document_version"):
                    chunks.append({**chunk, "id": chunk_id, "doc_title": doc.get("title", "")})
                    seen.add(chunk_id)
        return chunks

    async def invalidate_document(self, doc_id: str, reason: str = "document_inactive") -> int:
        changed = 0
        for item in await self.store.find("org_memory_items", {"status": "active"}):
            if doc_id in (item.get("source_doc_ids") or []):
                await self._mark_stale(item, reason)
                changed += 1
        return changed

    async def _verify_sources(self, refs: list[dict[str, Any]], dept_id: str = "") -> list[dict[str, Any]]:
        verified: list[dict[str, Any]] = []
        for ref in refs:
            doc = await self.store.get_document(ref.get("doc_id", ""))
            chunk = await self.store.get("chunks", ref.get("chunk_id", ""))
            if not doc or not chunk or doc.get("status") != "active":
                continue
            if dept_id and doc.get("dept_id") != dept_id:
                continue
            if ref.get("document_version") and ref.get("document_version") != doc.get("version"):
                continue
            verified.append({
                "doc_id": doc["_id"], "chunk_id": chunk["_id"],
                "document_version": doc.get("version", ""),
            })
        return verified

    async def _mark_stale(self, item: dict[str, Any], reason: str) -> None:
        item.update({"status": "stale", "stale_reason": reason, "updated_at": datetime.now(timezone.utc)})
        await self.store.upsert("org_memory_items", item)
