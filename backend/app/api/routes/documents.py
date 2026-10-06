"""Document ingestion and management endpoints (admins; department admins are limited to their own department)."""
from __future__ import annotations
from typing import Optional

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.deps import require_admin, scope_dept
from app.api.schemas import ApiResponse, DocumentStatusUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

# Allowed document types (consistent with what pipeline/parser.py supports)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".html", ".htm", ".txt"}
_CHUNK = 1024 * 1024  # 1MB


@router.post("/upload", response_model=ApiResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    dept_id: str = Form(...),
    uploaded_by: str = Form(""),
    user: dict = Depends(require_admin),
):
    container = request.app.state.container
    scope = scope_dept(user)
    if scope and dept_id != scope:
        raise HTTPException(status_code=403, detail="Department admins can only upload documents to their own department")

    # 1) Extension allowlist
    original_name = Path(file.filename or "doc").name or "doc.txt"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {suffix or '(no extension)'}; only {sorted(ALLOWED_EXTENSIONS)} are supported")

    # 2) Size limit (enforced while reading, so oversized files cannot fill the disk)
    max_bytes = container.settings.max_upload_mb * 1024 * 1024
    upload_dir = Path(container.settings.upload_storage_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    job_dir = upload_dir / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    stored_path = job_dir / original_name
    total = 0
    try:
        with open(stored_path, "wb") as f:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the size limit of {container.settings.max_upload_mb}MB",
                    )
                f.write(chunk)
        job = await container.job_queue.enqueue("ingest_document", {
            "path": str(stored_path), "original_name": original_name,
            "dept_id": dept_id, "uploaded_by": user["id"],
        })
        return ApiResponse(data={"queued": True, "job_id": job["_id"], "file_name": original_name})
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Document ingestion failed (file=%s, dept=%s)", original_name, dept_id)
        stored_path.unlink(missing_ok=True)
        job_dir.rmdir()
        # Never echo internal exception details to the client
        return ApiResponse(code=1, message="Ingestion failed, please check the file format and try again")
    finally:
        await file.close()


@router.get("/jobs/{job_id}", response_model=ApiResponse)
async def get_upload_job(job_id: str, request: Request, user: dict = Depends(require_admin)):
    job = await request.app.state.container.store.get("async_jobs", job_id)
    if not job or (job.get("payload") or {}).get("uploaded_by") != user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    return ApiResponse(data=job)


@router.get("", response_model=ApiResponse)
async def list_documents(
    request: Request,
    dept_id: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    container = request.app.state.container
    scope = scope_dept(user)
    if scope:
        dept_id = scope  # Department admins only see their own department's documents
    docs = await container.store.list_documents(dept_id=dept_id, status=status)
    return ApiResponse(data=docs)


@router.get("/{doc_id}", response_model=ApiResponse)
async def get_document(doc_id: str, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    doc = await container.store.get_document(doc_id)
    if doc is None:
        return ApiResponse(code=1, message="Document not found")
    scope = scope_dept(user)
    if scope and doc.get("dept_id") != scope:
        raise HTTPException(status_code=403, detail="Not authorized to access documents of other departments")
    chunks = await container.store.list_chunks_by_doc(doc_id)
    doc["chunks"] = chunks
    return ApiResponse(data=doc)


@router.post("/{doc_id}/status", response_model=ApiResponse)
async def update_status(doc_id: str, body: DocumentStatusUpdate, request: Request, user: dict = Depends(require_admin)):
    container = request.app.state.container
    doc = await container.store.get_document(doc_id)
    if doc is None:
        return ApiResponse(code=1, message="Document not found")
    scope = scope_dept(user)
    if scope and doc.get("dept_id") != scope:
        raise HTTPException(status_code=403, detail="Not authorized to modify documents of other departments")
    allowed = {"draft", "review", "active", "archived", "deleted"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid document status")
    await container.indexer.set_status(doc_id, body.status)
    return ApiResponse(data={"doc_id": doc_id, "status": body.status})
