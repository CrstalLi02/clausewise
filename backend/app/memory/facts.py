"""Independent authoritative fact plane: exposes only active official documents and their original chunks."""
from __future__ import annotations

from typing import Any

from app.storage.store import DataStore


class FactPlane:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    async def active_chunk(self, chunk_id: str, dept_ids: list[str] | None = None) -> dict[str, Any] | None:
        chunk = await self.store.get("chunks", chunk_id)
        if not chunk:
            return None
        doc = await self.store.get_document(chunk.get("doc_id", ""))
        if not doc or doc.get("status") != "active":
            return None
        if dept_ids and doc.get("dept_id") not in set(dept_ids):
            return None
        return {**chunk, "id": chunk_id, "doc_title": doc.get("title", ""), "document_version": doc.get("version", "")}

    async def validate_refs(
        self, refs: list[dict[str, Any]], dept_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        valid: list[dict[str, Any]] = []
        for ref in refs:
            chunk = await self.active_chunk(ref.get("chunk_id", ""), dept_ids)
            if not chunk or chunk.get("doc_id") != ref.get("doc_id"):
                continue
            if ref.get("document_version") and ref["document_version"] != chunk.get("document_version"):
                continue
            valid.append({
                "doc_id": chunk["doc_id"], "chunk_id": chunk["_id"],
                "document_version": chunk.get("document_version", ""),
            })
        return valid
