"""Redis Stream worker: processes async document ingestion, Loop wake-up, and other jobs."""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import get_settings
from app.deps import build_container
from app.utils.logging import setup_logging


async def process(container, job):
    payload = job.get("payload") or {}
    if job["type"] == "ingest_document":
        path = Path(payload["path"])
        try:
            doc = await container.indexer.ingest(
                path, payload["dept_id"], payload["uploaded_by"]
            )
            # Persisted files are named by UUID; restore the original filename for display and version detection.
            doc.setdefault("source", {})["file_name"] = payload.get("original_name", path.name)
            await container.store.update_document(doc["_id"], {"source": doc["source"]})
            relations = await container.conflict_detector.run_for_document(doc)
            review = await container.review_engine.create_review_order(doc)
            return {"document_id": doc["_id"], "relations": len(relations), "review_id": (review or {}).get("_id")}
        finally:
            path.unlink(missing_ok=True)
            try:
                path.parent.rmdir()
            except OSError:
                pass
    if job["type"] in {"feedback_received", "run_loop"}:
        async def progress(stage, detail):
            await container.job_queue.update_progress(job["_id"], {
                "stage": stage, "detail": detail,
            })

        result = await container.loop_engine.run_cycle(progress_callback=progress)
        result["memory_retention"] = await container.memory_retention.prune_expired()
        return result
    raise ValueError(f"Unknown job type: {job['type']}")


async def main():
    settings = get_settings()
    setup_logging(settings.log_level)
    container = build_container(settings)
    if container.mongo is not None:
        await container.mongo.connect()
    if hasattr(container.session_store, "connect"):
        await container.session_store.connect()
    while True:
        for job in await container.job_queue.next_jobs():
            try:
                result = await process(container, job)
                await container.job_queue.finish(job, "completed", result)
            except Exception as exc:
                await container.job_queue.finish(job, "failed", {"error": str(exc)})
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
