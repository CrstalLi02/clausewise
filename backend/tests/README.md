# Tests

Runnable offline (`conftest.py` forces `STORAGE_MODE=memory` + `EMBEDDING_PROVIDER=hash`),
with no MongoDB/Redis/network/real LLM required.

```bash
cd backend
pytest            # Run everything
pytest tests/test_chunker.py   # Single file
```

Current baseline: **59 passed** (offline configuration).

| File | Coverage |
|---|---|
| `test_chunker.py` | Semantic chunking (heading hierarchy / size boundaries / empty documents) |
| `test_bm25.py` | BM25 retrieval + department filtering |
| `test_retrieval.py` | Hybrid retrieval + vector cosine |
| `test_agents.py` | No-LLM fallbacks for intent / rewriting / verification |
| `test_pipeline.py` | Parsing / cleaning |
| `test_loop.py` | Rule/hook engines + Skill Miner clustering |
| `test_e2e.py` | Ingestion → Q&A, Loop cycle smoke test |
| `test_loop_runtime.py` | Idempotent baseline Skill seeding, real workflows, canary, dynamic Rules, trace ordering, and rollback |
| `test_department_agents.py` | Department isolation / parallel partial success / shared vectors |
| `test_job_queue.py` | Redis Stream queue persistent state, running stage, and progress write-back |
| `test_memory_architecture.py` | Fact authority, five planes, source/isolation/sensitivity/TTL/deletion/atomic counters |
| `test_memory_migration.py` | Idempotency of legacy four-layer memory migration and isolation of unsourced FAQs |
| `test_memory_api.py` | User memory API, rejection of sensitive fields, and organizational memory admin permissions |
| `test_pi_runtime.py` | pi Runtime priority execution, local fallback, protocol, and enablement conditions |
| `test_document_versions.py` | Duplicate files, version chains, and old-version archiving |
| `test_review.py` | Per-question review judgments, no default pass for unreviewed items, and phase advancement |
| `test_store.py` / `test_redis_store.py` | Mongo atomic updates and Redis credential redaction in logs |
