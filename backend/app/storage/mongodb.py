"""MongoDB async client (motor) and index creation."""
from __future__ import annotations
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MongoDB:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        if self.settings.storage_mode != "mongo":
            return
        self.client = AsyncIOMotorClient(self.settings.mongodb_uri)
        self.db = self.client[self.settings.mongodb_db]
        await self._ensure_indexes()
        logger.info("MongoDB connected: %s", self.settings.mongodb_db)

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()

    async def _ensure_indexes(self) -> None:
        assert self.db is not None
        indexes: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
            # MongoDB automatically creates a unique `_id` index. Recreating it
            # with options is rejected by MongoDB 7, so no explicit index is needed.
            "departments": [],
            "documents": [
                ([("dept_id", 1), ("status", 1)], {}),
                ([("title", 1)], {}),
                ([("dept_id", 1), ("source.file_hash", 1)], {}),
                ([("dept_id", 1), ("title", 1), ("created_at", -1)], {}),
            ],
            "chunks": [
                ([("doc_id", 1)], {}),
                ([("dept_id", 1), ("doc_id", 1), ("chunk_index", 1)], {}),
            ],
            "doc_relations": [
                ([("from_doc", 1)], {}),
                ([("to_doc", 1)], {}),
                ([("relation_type", 1)], {}),
            ],
            "skills": [([("dept_id", 1), ("status", 1)], {}), ([("name", 1)], {})],
            "hooks": [([("dept_id", 1), ("status", 1)], {})],
            "rules": [([("scope", 1), ("status", 1)], {})],
            "feedback": [([("consumed", 1), ("created_at", 1)], {})],
            "traces": [([("created_at", 1)], {}), ([("session_id", 1)], {})],
            "glossary": [([("canonical", 1)], {})],
            "user_profiles": [],
            "strategy_versions": [([("artifact_id", 1), ("version", -1)], {})],
            "strategy_executions": [
                ([("artifact_id", 1), ("group", 1), ("created_at", -1)], {}),
                ([("session_id", 1)], {}),
            ],
            "strategy_proposals": [([("status", 1), ("created_at", -1)], {})],
            "experiments": [([("artifact_id", 1), ("status", 1)], {})],
            "vector_embeddings": [
                ([("dept_id", 1)], {}), ([("doc_id", 1)], {}),
            ],
            "async_jobs": [([("status", 1), ("created_at", 1)], {})],
            "conversation_events": [
                ([("session_id", 1), ("seq", 1)], {"unique": True}),
                ([("user_id", 1), ("created_at", -1)], {}),
                ([("expires_at", 1)], {"expireAfterSeconds": 0}),
            ],
            "conversation_summaries": [
                ([("user_id", 1), ("updated_at", -1)], {}),
                ([("expires_at", 1)], {"expireAfterSeconds": 0}),
            ],
            "user_memory_items": [
                ([("user_id", 1), ("key", 1), ("status", 1)], {}),
                ([("expires_at", 1)], {"expireAfterSeconds": 0}),
            ],
            "org_memory_items": [
                ([("scope", 1), ("dept_id", 1), ("type", 1), ("status", 1)], {}),
                ([("source_doc_ids", 1)], {}),
                ([("expires_at", 1)], {"expireAfterSeconds": 0}),
            ],
            "memory_candidates": [([("status", 1), ("created_at", -1)], {})],
            "memory_usage": [([("memory_id", 1), ("created_at", -1)], {}), ([("trace_id", 1)], {})],
            "memory_audit": [([("actor_id", 1), ("created_at", -1)], {})],
            "memory_topics": [
                ([("dept_id", 1), ("date", -1)], {}),
                ([("expires_at", 1)], {"expireAfterSeconds": 0}),
            ],
        }
        for coll, idx_list in indexes.items():
            for keys, kwargs in idx_list:
                try:
                    await self.db[coll].create_index(keys, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to create index %s%s: %s", coll, keys, exc)

    def collection(self, name: str):
        if self.db is None:
            raise RuntimeError("MongoDB is not connected")
        return self.db[name]
