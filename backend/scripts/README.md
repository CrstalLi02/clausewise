# Scripts

| Script | Purpose |
|---|---|
| `seed_data.py` | Idempotent seed data: departments / glossary / school calendar / default Rules & Hooks / 3 executable baseline Skills |
| `seed_demo_data.py` | Optional demo extension: mock documents, review orders, badcases, and department Skills; not required for normal startup |
| `doctor.py` | Checks model connectivity for DeepSeek, the relay service, Embedding/Reranker, etc. |
| `ingest_department_files.py` | Imports the sample documents in `department_files` |
| `loop_worker.py` | Legacy scheduled worker (kept for compatibility; production uses `async_worker.py`) |
| `async_worker.py` | Redis Stream worker: document ingestion, feedback wake-up, Loop |
| `evaluate_rag.py` | Real department document evaluation: Recall@5 / MRR / citation accuracy / answer consistency |
| `migrate_memory.py` | Migrates the legacy four-layer monolithic memory to the fact plane + five memory planes |
| `wait_for_deps.py` | Waits for MongoDB/Redis to be ready before startup (Docker) |

Usage:

```bash
python -m scripts.seed_data
python -m scripts.ingest_department_files --base ../department_files
python -m scripts.migrate_memory
python -m scripts.async_worker
python -m scripts.evaluate_rag --output evaluation-report.json
STORAGE_MODE=memory EMBEDDING_PROVIDER=hash python -m scripts.evaluate_rag --ingest-base ../department_files
```
