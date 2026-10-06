"""Import the sample department documents under department_files.

Directory name → department id mapping; recursively finds pdf/docx/md/txt/html.
Usage: python -m scripts.ingest_department_files [--base ../department_files]
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.config import get_settings
from app.deps import build_container

# Directory name (or keyword, case-insensitive) → dept_id mapping
DEPT_MAP = {
    "academic affairs": "dept_jwc",
    "student affairs": "dept_xsc",
    "finance": "dept_cwc",
    "human resources": "dept_rsc",
    "logistics": "dept_hqaq",      # Logistics and Security Department (merged; there is no separate Logistics Office)
    "graduate school": "dept_yjsy",
    "sino-french": "dept_zfxy",
    "security": "dept_hqaq",
}

SUFFIXES = {".pdf", ".docx", ".doc", ".md", ".markdown", ".txt", ".html", ".htm"}

# Candidate directories (by priority): local backend/ directory, /app inside the Docker container, compose mount point
BASE_CANDIDATES = ["../department_files", "/app/department_files", "department_files"]


def resolve_base(explicit: str | None) -> Path:
    """Resolve the sample document root: prefer the explicit path, otherwise the first existing candidate."""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p.resolve()
        print(f"Warning: the specified directory does not exist, trying candidate paths: {explicit}")
    for cand in BASE_CANDIDATES:
        p = Path(cand)
        if p.exists():
            return p.resolve()
    return Path(explicit or BASE_CANDIDATES[0]).resolve()


def resolve_dept(path: Path) -> str:
    for part in path.parts:
        name = part.lower().replace("_", " ")
        for key, dept_id in DEPT_MAP.items():
            if key in name:
                return dept_id
    return "dept_all"


async def main(base: str) -> None:
    base_path = resolve_base(base or None)
    if not base_path.exists():
        print(f"Directory not found: {base_path} (you can pass --base explicitly, e.g. --base /app/department_files)")
        return

    settings = get_settings()
    container = build_container(settings)
    if container.mongo is not None:
        await container.mongo.connect()
    if hasattr(container.session_store, "connect"):
        try:
            await container.session_store.connect()
        except Exception:
            pass

    files = [p for p in base_path.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES]
    print(f"Found {len(files)} documents to import")

    ok, fail = 0, 0
    for fp in files:
        dept_id = resolve_dept(fp)
        try:
            doc = await container.indexer.ingest(fp, dept_id=dept_id, uploaded_by="seed")
            await container.conflict_detector.run_for_document(doc)
            print(f"[ok] {fp.name} -> {dept_id} ({doc['chunk_count']} chunks)")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {fp.name}: {exc}")
            fail += 1

    print(f"Done: {ok} succeeded, {fail} failed")
    if container.mongo is not None:
        await container.mongo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="", help="Sample document root (auto-detects ../department_files or /app/department_files by default)")
    args = parser.parse_args()
    asyncio.run(main(args.base))
