"""Evaluate retrieval and answer quality on a Q&A set built from real department documents.

Metrics: Recall@5, MRR, citation accuracy, answer consistency (coverage of the reference answer's key points).
By default it evaluates already-ingested data; run ingest_department_files.py first to import the repository's sample documents.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.deps import build_container
from scripts.ingest_department_files import resolve_dept

DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "real_document_qa.json"


def _normalize(text: str) -> str:
    return "".join(text.lower().split()).replace("：", ":").replace("－", "-").replace("‑", "-")


def _source_file(hit: dict[str, Any], docs: dict[str, dict[str, Any]]) -> str:
    return str((docs.get(hit.get("doc_id", ""), {}).get("source") or {}).get("file_name", ""))


async def evaluate(dataset_path: Path, top_k: int = 5, ingest_base: Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    container = build_container(settings)
    if container.mongo is not None:
        await container.mongo.connect()
    if hasattr(container.session_store, "connect"):
        try:
            await container.session_store.connect()
        except Exception:
            pass

    if ingest_base:
        suffixes = {".pdf", ".docx", ".md", ".markdown", ".txt", ".html", ".htm"}
        for path in sorted(p for p in ingest_base.rglob("*") if p.is_file() and p.suffix.lower() in suffixes):
            await container.indexer.ingest(path, resolve_dept(path), uploaded_by="evaluation")

    active_chunks = await container.store.list_active_chunks()
    if not active_chunks:
        raise RuntimeError("No active chunks to evaluate; ingest documents first or pass --ingest-base")
    container.bm25.index(active_chunks)
    vectors = await container.embeddings.embed([c["content"] for c in active_chunks])
    for chunk, vector in zip(active_chunks, vectors):
        await container.vector_store.add(
            chunk["_id"], vector,
            {"doc_id": chunk["doc_id"], "dept_id": chunk["dept_id"], "chunk_index": chunk["chunk_index"]},
        )

    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    docs = {d["_id"]: d for d in await container.store.list_documents(status="active")}
    rows: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []
    citation_scores: list[float] = []
    consistency_scores: list[float] = []

    for case in cases:
        hits = await container.retrieval_agent.retrieve([case["query"]], [case["dept_id"]], top_k=top_k)
        relevant = set(case["relevant_files"])
        rank = next((i for i, hit in enumerate(hits, 1) if _source_file(hit, docs) in relevant), 0)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)

        rules = await container.rule_engine.active_rules()
        answer = await container.orchestrator.answer_agent.generate(case["query"], hits, rules=rules)
        cited = answer.citations
        valid_citations = 0
        for citation in cited:
            chunk = await container.store.get("chunks", f"{citation.doc_id}:{citation.chunk_index}")
            doc = docs.get(citation.doc_id)
            if chunk and doc and doc.get("status") == "active" and citation.snippet in chunk.get("content", ""):
                valid_citations += 1
        citation_score = valid_citations / len(cited) if cited else 0.0
        citation_scores.append(citation_score)

        normalized_answer = _normalize(answer.content)
        terms = case.get("expected_terms") or []
        covered = sum(1 for term in terms if _normalize(term) in normalized_answer)
        consistency = covered / len(terms) if terms else 1.0
        consistency_scores.append(consistency)
        rows.append({
            "id": case["id"], "rank": rank, "hit_at_5": bool(rank and rank <= 5),
            "citation_correctness": round(citation_score, 4),
            "answer_consistency": round(consistency, 4),
            "retrieved_files": [_source_file(h, docs) for h in hits],
        })

    n = max(len(cases), 1)
    report = {
        "dataset": str(dataset_path), "cases": len(cases), "top_k": top_k,
        "recall_at_5": round(sum(1 for r in rows if r["hit_at_5"]) / n, 4),
        "mrr": round(sum(reciprocal_ranks) / n, 4),
        "citation_correctness": round(sum(citation_scores) / n, 4),
        "answer_consistency": round(sum(consistency_scores) / n, 4),
        "details": rows,
    }
    if container.mongo is not None:
        await container.mongo.close()
    return report


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ingest-base", type=Path, help="Import this directory in the same process before evaluating (suited to memory mode)")
    args = parser.parse_args()
    report = await evaluate(args.dataset, args.top_k, args.ingest_base)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
