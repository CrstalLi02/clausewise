"""Clausewise backend entry point (FastAPI)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest
from starlette.responses import Response

from app.api.router import api_router, root_router
from app.config import get_settings
from app.deps import build_container
from app.utils.logging import get_logger, setup_logging
from app.loop.default_skills import seed_default_skills

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    container = build_container(settings)
    app.state.container = container

    # Connect external dependencies (skipped in memory mode)
    if container.mongo is not None:
        try:
            await container.mongo.connect()
        except Exception as exc:  # noqa: BLE001
            logger.error("MongoDB connection failed: %s", exc)
    if hasattr(container.session_store, "connect"):
        try:
            await container.session_store.connect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis connection failed (%s), sessions fall back to memory", exc)

    # Seed default Rules / Hooks
    await container.rule_engine.seed_defaults()
    await container.hook_engine.seed_defaults()
    seeded_skills = await seed_default_skills(container.store)
    if seeded_skills:
        logger.info("Created %d executable baseline Skills", seeded_skills)

    # Seed accounts (student/admin)
    await container.auth.seed_users()

    # Backfill department Loop phase and review stats fields (compatible with legacy data)
    await _backfill_departments(container)

    # Rebuild in-memory retrieval indexes (BM25 + vectors) so documents already ingested into MongoDB are searchable across processes/restarts
    try:
        chunks = await container.store.list_active_chunks()
        if chunks:
            for c in chunks:
                container.bm25.add(c)
            # The shared Mongo vector store is persistent, so Pods do not need to re-embed all documents on startup.
            if settings.vector_backend != "mongo":
                texts = [c["content"] for c in chunks]
                vectors = await container.embeddings.embed(texts)
                for c, v in zip(chunks, vectors):
                    await container.vector_store.add(
                        c["embedding_id"],
                        v,
                        {"doc_id": c["doc_id"], "dept_id": c["dept_id"], "chunk_index": c["chunk_index"]},
                    )
            logger.info("Retrieval index rebuild complete: %d chunks (BM25 + vectors)", len(chunks))
        else:
            logger.info("No ingested documents, skipping retrieval index rebuild")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Retrieval index rebuild failed (%s); retrieval may be incomplete", exc)

    logger.info("%s started (storage=%s)", settings.app_name, settings.storage_mode)
    yield

    # Shutdown
    if container.mongo is not None:
        await container.mongo.close()
    if hasattr(container.session_store, "close"):
        await container.session_store.close()
    await container.pi_runtime.close()
    logger.info("Application shut down")


async def _backfill_departments(container) -> None:
    """Backfill loop_phase / review_stats / fade_out fields for existing departments (idempotent)."""
    from datetime import datetime, timezone

    try:
        for dept in await container.store.list_departments():
            changed = False
            if "loop_phase" not in dept:
                dept["loop_phase"] = "human_in_loop"
                changed = True
            if "review_stats" not in dept:
                dept["review_stats"] = {"total": 0, "correct": 0, "accuracy": 0.0}
                changed = True
            if "admin_users" not in dept:
                dept["admin_users"] = []
                changed = True
            if changed:
                dept["updated_at"] = datetime.now(timezone.utc).isoformat()
                await container.store.upsert_department(dept)
        logger.info("Department Loop phase field backfill complete")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Department field backfill failed: %s", exc)


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# CORS: explicit origin list; wildcard origins may not carry credentials (browser spec)
_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root_router)
app.include_router(api_router)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")


@app.get("/")
async def index():
    return {"app": settings.app_name, "docs": "/docs", "health": "/healthz"}
