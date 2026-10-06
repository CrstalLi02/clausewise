"""Unified data access layer: DataStore interface + MongoStore + MemoryStore.

MongoStore is for production; MemoryStore is for offline development / unit tests (STORAGE_MODE=memory).
All methods operate on dicts (BSON-like), with `_id` as the string primary key.
"""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.storage.mongodb import MongoDB
from app.utils.logging import get_logger

logger = get_logger(__name__)

COLLECTIONS = (
    "departments",
    "documents",
    "chunks",
    "doc_relations",
    "skills",
    "hooks",
    "rules",
    "feedback",
    "traces",
    "glossary",
    "user_profiles",
    "dept_memory",
    "global_memory",
    "faq_cache",
    "users",
    "review_orders",
    "test_questions",
    "strategy_versions",
    "strategy_executions",
    "strategy_proposals",
    "experiments",
    "vector_embeddings",
    "async_jobs",
    "conversation_events",
    "conversation_summaries",
    "user_memory_items",
    "org_memory_items",
    "memory_candidates",
    "memory_usage",
    "memory_audit",
    "memory_topics",
    "memory_sequences",
)


class DataStore(ABC):
    """Unified interface for all storage backends."""

    # ---------- Generic ----------
    @abstractmethod
    async def upsert(self, collection: str, doc: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get(self, collection: str, id_: str) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    async def find(self, collection: str, query: Optional[dict[str, Any]] = None, limit: int = 0) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete(self, collection: str, id_: str) -> None: ...

    @abstractmethod
    async def count(self, collection: str, query: Optional[dict[str, Any]] = None) -> int: ...

    @abstractmethod
    async def increment(
        self, collection: str, id_: str, field: str, amount: int = 1, defaults: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]: ...

    # ---------- Domain convenience methods ----------
    async def upsert_department(self, dept: dict[str, Any]) -> None:
        await self.upsert("departments", dept)

    async def get_department(self, dept_id: str) -> Optional[dict[str, Any]]:
        return await self.get("departments", dept_id)

    async def list_departments(self) -> list[dict[str, Any]]:
        return await self.find("departments")

    async def insert_document(self, doc: dict[str, Any]) -> None:
        await self.upsert("documents", doc)

    async def get_document(self, doc_id: str) -> Optional[dict[str, Any]]:
        return await self.get("documents", doc_id)

    async def list_documents(self, dept_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if dept_id:
            query["dept_id"] = dept_id
        if status:
            query["status"] = status
        return await self.find("documents", query)

    async def update_document(self, doc_id: str, update: dict[str, Any]) -> None:
        doc = await self.get_document(doc_id)
        if doc is None:
            return
        doc.update(update)
        await self.upsert("documents", doc)

    async def insert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        for c in chunks:
            await self.upsert("chunks", c)

    async def list_chunks_by_doc(self, doc_id: str) -> list[dict[str, Any]]:
        return await self.find("chunks", {"doc_id": doc_id})

    async def get_chunks_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        out = []
        for id_ in ids:
            c = await self.get("chunks", id_)
            if c:
                out.append(c)
        return out

    async def delete_chunks_by_doc(self, doc_id: str) -> None:
        for c in await self.list_chunks_by_doc(doc_id):
            await self.delete("chunks", c["_id"])

    async def list_all_chunks(self, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        query = {"dept_id": dept_id} if dept_id else None
        return await self.find("chunks", query)

    async def list_active_chunks(self, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        active_docs = await self.list_documents(dept_id=dept_id, status="active")
        active_ids = {d["_id"] for d in active_docs}
        return [c for c in await self.list_all_chunks(dept_id) if c.get("doc_id") in active_ids]

    async def insert_relation(self, rel: dict[str, Any]) -> None:
        await self.upsert("doc_relations", rel)

    async def list_relations(self, relation_type: Optional[str] = None, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if relation_type:
            query["relation_type"] = relation_type
        rels = await self.find("doc_relations", query)
        if dept_id:
            # Relations carry from_dept to make department filtering easy
            rels = [r for r in rels if r.get("from_dept") == dept_id or r.get("to_dept") == dept_id]
        return rels

    async def upsert_skill(self, skill: dict[str, Any]) -> None:
        await self.upsert("skills", skill)

    async def list_skills(self, dept_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        skills = await self.find("skills", query)
        if dept_id:
            skills = [s for s in skills if s.get("dept_id") == dept_id or s.get("scope") == "global"]
        return skills

    async def get_skill(self, skill_id: str) -> Optional[dict[str, Any]]:
        return await self.get("skills", skill_id)

    async def upsert_hook(self, hook: dict[str, Any]) -> None:
        await self.upsert("hooks", hook)

    async def list_hooks(self, dept_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"status": status} if status else {}
        hooks = await self.find("hooks", query)
        if dept_id:
            hooks = [h for h in hooks if h.get("dept_id") == dept_id or h.get("scope") == "global"]
        return hooks

    async def upsert_rule(self, rule: dict[str, Any]) -> None:
        await self.upsert("rules", rule)

    async def list_rules(self, scope: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"status": status} if status else {}
        rules = await self.find("rules", query)
        if scope:
            rules = [r for r in rules if r.get("scope") in (scope, "global")]
        return rules

    async def insert_feedback(self, fb: dict[str, Any]) -> None:
        await self.upsert("feedback", fb)

    async def list_pending_feedback(self) -> list[dict[str, Any]]:
        return await self.find("feedback", {"consumed": False})

    async def mark_feedback_consumed(self, ids: list[str]) -> None:
        for id_ in ids:
            fb = await self.get("feedback", id_)
            if fb:
                fb["consumed"] = True
                await self.upsert("feedback", fb)

    async def insert_trace(self, trace: dict[str, Any]) -> None:
        await self.upsert("traces", trace)

    async def list_recent_traces(self, limit: int = 500) -> list[dict[str, Any]]:
        rows = await self.find("traces")
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return rows[:limit] if limit else rows

    async def list_glossary(self) -> list[dict[str, Any]]:
        return await self.find("glossary")

    async def upsert_glossary(self, entry: dict[str, Any]) -> None:
        await self.upsert("glossary", entry)

    async def get_user_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self.get("user_profiles", user_id)

    async def upsert_user_profile(self, profile: dict[str, Any]) -> None:
        await self.upsert("user_profiles", profile)

    # ---------- Users / review orders / test question bank ----------
    async def upsert_user(self, user: dict[str, Any]) -> None:
        await self.upsert("users", user)

    async def list_users(self) -> list[dict[str, Any]]:
        return await self.find("users")

    async def insert_review_order(self, order: dict[str, Any]) -> None:
        await self.upsert("review_orders", order)

    async def get_review_order(self, order_id: str) -> Optional[dict[str, Any]]:
        return await self.get("review_orders", order_id)

    async def list_review_orders(self, dept_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if dept_id:
            query["dept_id"] = dept_id
        if status:
            query["status"] = status
        return await self.find("review_orders", query)

    async def update_review_order(self, order_id: str, update: dict[str, Any]) -> None:
        order = await self.get_review_order(order_id)
        if order is None:
            return
        order.update(update)
        await self.upsert("review_orders", order)

    async def insert_test_question(self, q: dict[str, Any]) -> None:
        await self.upsert("test_questions", q)

    async def list_test_questions(self, dept_id: Optional[str] = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"dept_id": dept_id} if dept_id else {}
        return await self.find("test_questions", query)


class MemoryStore(DataStore):
    """In-memory implementation (single process, for offline development / testing)."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {c: {} for c in COLLECTIONS}

    async def upsert(self, collection: str, doc: dict[str, Any]) -> None:
        self._ensure(collection)
        d = copy.deepcopy(doc)
        self._data[collection][d["_id"]] = d

    async def get(self, collection: str, id_: str) -> Optional[dict[str, Any]]:
        self._ensure(collection)
        d = self._data[collection].get(id_)
        return copy.deepcopy(d) if d else None

    async def find(self, collection: str, query: Optional[dict[str, Any]] = None, limit: int = 0) -> list[dict[str, Any]]:
        self._ensure(collection)
        rows = list(self._data[collection].values())
        if query:
            rows = [r for r in rows if self._match(r, query)]
        def _sort_key(row: dict[str, Any]) -> str:
            value = row.get("created_at", row.get("updated_at", ""))
            return value.isoformat() if hasattr(value, "isoformat") else str(value or "")

        rows.sort(key=_sort_key, reverse=True)
        if limit:
            rows = rows[:limit]
        return [copy.deepcopy(r) for r in rows]

    async def delete(self, collection: str, id_: str) -> None:
        self._ensure(collection)
        self._data[collection].pop(id_, None)

    async def count(self, collection: str, query: Optional[dict[str, Any]] = None) -> int:
        return len(await self.find(collection, query))

    async def increment(
        self, collection: str, id_: str, field: str, amount: int = 1, defaults: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        self._ensure(collection)
        doc = copy.deepcopy(self._data[collection].get(id_)) or {"_id": id_, **copy.deepcopy(defaults or {})}
        target = doc
        parts = field.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = int(target.get(parts[-1], 0)) + amount
        self._data[collection][id_] = copy.deepcopy(doc)
        return copy.deepcopy(doc)

    def _ensure(self, collection: str) -> None:
        if collection not in self._data:
            self._data[collection] = {}

    @staticmethod
    def _match(doc: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(doc.get(k) == v for k, v in query.items())


class MongoStore(DataStore):
    """MongoDB implementation."""

    def __init__(self, mongo: MongoDB) -> None:
        self.mongo = mongo

    def _coll(self, collection: str):
        return self.mongo.collection(collection)

    async def upsert(self, collection: str, doc: dict[str, Any]) -> None:
        await self._coll(collection).replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def get(self, collection: str, id_: str) -> Optional[dict[str, Any]]:
        doc = await self._coll(collection).find_one({"_id": id_})
        return doc

    async def find(self, collection: str, query: Optional[dict[str, Any]] = None, limit: int = 0) -> list[dict[str, Any]]:
        cursor = self._coll(collection).find(query or {})
        if limit:
            cursor = cursor.limit(limit)
        return [d async for d in cursor]

    async def delete(self, collection: str, id_: str) -> None:
        await self._coll(collection).delete_one({"_id": id_})

    async def count(self, collection: str, query: Optional[dict[str, Any]] = None) -> int:
        return await self._coll(collection).count_documents(query or {})

    async def increment(
        self, collection: str, id_: str, field: str, amount: int = 1, defaults: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        from pymongo import ReturnDocument

        # MongoDB rejects an update that mutates a nested path with `$inc` while
        # `$setOnInsert` also initializes one of its parents, for example
        # `prefs.intent_counts.x` together with `prefs={}`. The increment itself
        # creates the nested path on insert, so omit only overlapping defaults.
        insert_defaults = {
            key: value for key, value in (defaults or {}).items()
            if key != field and not field.startswith(f"{key}.") and not key.startswith(f"{field}.")
        }
        update: dict[str, Any] = {"$inc": {field: amount}}
        if insert_defaults:
            update["$setOnInsert"] = insert_defaults
        return await self._coll(collection).find_one_and_update(
            {"_id": id_}, update,
            upsert=True, return_document=ReturnDocument.AFTER,
        )


def build_store(mongo: Optional[MongoDB]) -> DataStore:
    """Build the store according to STORAGE_MODE."""
    if mongo is not None and mongo.settings.storage_mode == "mongo":
        return MongoStore(mongo)
    return MemoryStore()
