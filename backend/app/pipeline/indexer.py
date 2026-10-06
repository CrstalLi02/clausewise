"""Ingestion orchestration: parse → clean → semantic chunking → metadata extraction → vectorization → index building."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from app.llm.embeddings import EmbeddingClient
from app.pipeline.chunker import Chunker
from app.pipeline.cleaner import TextCleaner
from app.pipeline.metadata_extractor import MetadataExtractor, extract_keywords
from app.pipeline.parser import DocumentParser
from app.retrieval.bm25 import BM25Index
from app.retrieval.vector_store import VectorStore
from app.storage.store import DataStore
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DuplicateDocumentError(ValueError):
    """A document with identical content already exists in the same department."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Union[str, Path]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


class Indexer:
    def __init__(
        self,
        store: DataStore,
        vector_store: VectorStore,
        embeddings: EmbeddingClient,
        bm25: BM25Index,
        llm=None,
    ) -> None:
        self.store = store
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.bm25 = bm25
        self.parser = DocumentParser()
        self.cleaner = TextCleaner()
        self.chunker = Chunker()
        self.metadata_extractor = MetadataExtractor(llm) if llm is not None else None
        self.organization_memory = None

    async def ingest(self, file_path: Union[str, Path], dept_id: str, uploaded_by: str = "system") -> dict[str, Any]:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        incoming_hash = file_hash(file_path)
        dept_docs = await self.store.list_documents(dept_id=dept_id)
        duplicate = next(
            (d for d in dept_docs if (d.get("source") or {}).get("file_hash") == incoming_hash and d.get("status") != "deleted"),
            None,
        )
        if duplicate:
            raise DuplicateDocumentError(f"The same file has already been ingested: {duplicate.get('title', duplicate['_id'])}")

        # 1. Parse
        parsed = self.parser.parse(file_path)
        # 2. Clean
        cleaned = self.cleaner.clean(parsed)
        # 3. Semantic chunking
        chunks = self.chunker.chunk(cleaned)
        if not chunks:
            raise ValueError(f"No valid content was parsed from the document: {file_path}")
        # 4. Metadata extraction (LLM, optional)
        meta: dict[str, Any] = {"effective_date": None, "doc_type": "other", "keywords": [], "applicable_scope": ["all"], "cross_refs": []}
        if self.metadata_extractor is not None:
            meta = await self.metadata_extractor.extract(cleaned.title, cleaned.text)

        # Same title within the same department counts as a version update; the most recently created version is the direct predecessor.
        same_title = [d for d in dept_docs if d.get("title") == cleaned.title and d.get("status") != "deleted"]
        same_title.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        previous = same_title[0] if same_title else None
        version = self._next_version(previous.get("version", "") if previous else "")
        doc_id = uuid.uuid4().hex
        doc: dict[str, Any] = {
            "_id": doc_id,
            "dept_id": dept_id,
            "title": cleaned.title,
            "doc_type": meta.get("doc_type", "other"),
            "version": version,
            "status": "indexing",
            "effective_date": meta.get("effective_date"),
            "expiry_date": None,
            "supersedes": previous.get("_id") if previous else None,
            "source": {
                "file_name": file_path.name,
                "file_hash": incoming_hash,
                "uploaded_by": uploaded_by,
                "uploaded_at": now_iso(),
            },
            "tags": meta.get("keywords", []),
            "chunk_count": len(chunks),
            "vector_status": "pending",
            "applicable_scope": meta.get("applicable_scope", ["all"]),
            "cross_refs": meta.get("cross_refs", []),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await self.store.insert_document(doc)

        stored_chunks: list[dict[str, Any]] = []
        try:
            # 5. Vectorize
            texts = [c["content"] for c in chunks]
            vectors = await self.embeddings.embed(texts)

            # 6. Build indexes (vectors + BM25 + MongoDB chunks)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}:{i}"
                content = chunk["content"]
                chunk_doc: dict[str, Any] = {
                    "_id": chunk_id,
                    "doc_id": doc_id,
                    "dept_id": dept_id,
                    "chunk_index": i,
                    "section_path": chunk["section_path"],
                    "section_title": chunk["section_title"],
                    "content": content,
                    "content_hash": chunk["content_hash"],
                    "char_count": chunk["char_count"],
                    "embedding_id": chunk_id,
                    "keywords": extract_keywords(content),
                    "metadata": chunk["metadata"],
                }
                stored_chunks.append(chunk_doc)
                await self.vector_store.add(
                    chunk_id, vectors[i],
                    {"doc_id": doc_id, "dept_id": dept_id, "chunk_index": i},
                )
                self.bm25.add(chunk_doc)
            await self.store.insert_chunks(stored_chunks)
            await self.store.update_document(
                doc_id, {"status": "active", "vector_status": "ready", "chunk_count": len(stored_chunks)}
            )
        except Exception:
            # Avoid leaving a searchable half-finished document after a failed ingestion.
            await self.vector_store.delete_by_doc(doc_id)
            for c in stored_chunks:
                self.bm25.remove(c["_id"])
            await self.store.delete_chunks_by_doc(doc_id)
            await self.store.delete("documents", doc_id)
            raise

        # Archive old versions only after the new version is fully ready, so the switch is fail-safe.
        for old in same_title:
            if old.get("status") == "active":
                await self.store.update_document(old["_id"], {"status": "archived", "updated_at": now_iso()})
                await self._remove_from_runtime_indexes(old["_id"])
                if self.organization_memory is not None:
                    await self.organization_memory.invalidate_document(old["_id"], "document_superseded")
        logger.info("Ingestion complete: %s (%d chunks, dept=%s)", file_path.name, len(stored_chunks), dept_id)
        return await self.store.get_document(doc_id) or doc

    async def reindex(self, doc_id: str) -> dict[str, Any]:
        """Rebuild vector and BM25 indexes from the chunk text persisted in MongoDB."""
        doc = await self.store.get_document(doc_id)
        if doc is None:
            raise KeyError(f"Document not found: {doc_id}")
        old_chunks = await self.store.list_chunks_by_doc(doc_id)
        if not old_chunks:
            raise ValueError(f"Document has no chunks to rebuild: {doc_id}")
        for c in old_chunks:
            self.bm25.remove(c["_id"])
        await self.vector_store.delete_by_doc(doc_id)
        vectors = await self.embeddings.embed([c["content"] for c in old_chunks])
        for c, vector in zip(old_chunks, vectors):
            await self.vector_store.add(
                c["_id"], vector,
                {"doc_id": doc_id, "dept_id": c["dept_id"], "chunk_index": c["chunk_index"]},
            )
            if doc.get("status") == "active":
                self.bm25.add(c)
        await self.store.update_document(doc_id, {"vector_status": "ready", "updated_at": now_iso()})
        logger.info("Index rebuilt for document %s", doc_id)
        return await self.store.get_document(doc_id) or doc

    async def set_status(self, doc_id: str, status: str) -> dict[str, Any]:
        doc = await self.store.get_document(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        if status == "active":
            await self.store.update_document(doc_id, {"status": status, "updated_at": now_iso()})
            return await self.reindex(doc_id)
        await self.store.update_document(doc_id, {"status": status, "updated_at": now_iso()})
        await self._remove_from_runtime_indexes(doc_id)
        if self.organization_memory is not None:
            await self.organization_memory.invalidate_document(doc_id, f"document_{status}")
        return await self.store.get_document(doc_id) or doc

    async def _remove_from_runtime_indexes(self, doc_id: str) -> None:
        for chunk in await self.store.list_chunks_by_doc(doc_id):
            self.bm25.remove(chunk["_id"])
        await self.vector_store.delete_by_doc(doc_id)

    @staticmethod
    def _next_version(previous: str) -> str:
        if not previous:
            return "1.0"
        try:
            major, minor = previous.split(".", 1)
            return f"{int(major)}.{int(minor) + 1}"
        except (ValueError, AttributeError):
            return "1.0"
