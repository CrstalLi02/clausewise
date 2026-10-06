"""Redis Stream async job queue with Mongo/Memory persistent-state fallback."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.storage.store import DataStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobQueue:
    def __init__(self, store: DataStore, session_store, stream_name: str) -> None:
        self.store = store
        self.session_store = session_store
        self.stream_name = stream_name
        self.consumer_name = f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    async def enqueue(self, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        job = {
            "_id": "job_" + uuid.uuid4().hex, "type": job_type, "payload": payload,
            "status": "queued", "created_at": _now(), "updated_at": _now(),
        }
        await self.store.upsert("async_jobs", job)
        redis = getattr(self.session_store, "_redis", None)
        if redis is not None:
            await redis.xadd(self.stream_name, {"job_id": job["_id"], "type": job_type})
        return job

    async def next_jobs(self, count: int = 10, block_ms: int = 1000) -> list[dict[str, Any]]:
        redis = getattr(self.session_store, "_redis", None)
        if redis is not None:
            try:
                await redis.xgroup_create(self.stream_name, "workers", id="0", mkstream=True)
            except Exception as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
            records = await redis.xreadgroup(
                "workers", self.consumer_name, {self.stream_name: ">"}, count=count, block=block_ms
            )
            jobs: list[dict[str, Any]] = []
            for _, entries in records:
                for stream_id, fields in entries:
                    job = await self.store.get("async_jobs", fields["job_id"])
                    if job:
                        job["_stream_id"] = stream_id
                        job["status"] = "running"
                        job["updated_at"] = _now()
                        await self.store.upsert("async_jobs", {k: v for k, v in job.items() if k != "_stream_id"})
                        jobs.append(job)
            return jobs
        jobs = await self.store.find("async_jobs", {"status": "queued"}, limit=count)
        for job in jobs:
            job["status"] = "running"
            job["updated_at"] = _now()
            await self.store.upsert("async_jobs", job)
        return jobs

    async def finish(self, job: dict[str, Any], status: str, result: Any = None) -> None:
        stored = await self.store.get("async_jobs", job["_id"]) or job
        stored.update({"status": status, "result": result, "updated_at": _now()})
        await self.store.upsert("async_jobs", stored)
        redis = getattr(self.session_store, "_redis", None)
        if redis is not None and job.get("_stream_id"):
            await redis.xack(self.stream_name, "workers", job["_stream_id"])

    async def update_progress(self, job_id: str, progress: dict[str, Any]) -> None:
        stored = await self.store.get("async_jobs", job_id)
        if not stored:
            return
        stored.update({"status": "running", "progress": progress, "updated_at": _now()})
        await self.store.upsert("async_jobs", stored)
