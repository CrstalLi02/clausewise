# Clausewise Backend (Python + FastAPI)

Implements the L1 access layer (API), L2 Harness collaboration layer, L3 Loop evolution layer, and L4 data and retrieval layer from the technical design.

## Directory Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point + lifespan + /metrics + seed accounts / field backfill
│   ├── config.py            # Environment config (DeepSeek / relay service / storage / Loop / auth / review)
│   ├── deps.py              # Dependency wiring (builds the global singleton container, incl. auth / review_engine)
│   ├── auth.py              # Auth: user accounts + HMAC tokens + roles (student/admin)
│   ├── api/                 # L1 access layer
│   │   ├── router.py        # Router aggregation
│   │   ├── schemas.py       # Request/response models
│   │   ├── deps.py          # Auth dependencies (get_optional_user / require_user / require_admin)
│   │   └── routes/          # auth / chat / documents / departments / feedback / admin / internal / health
│   ├── harness/             # L2 multi-agent collaboration
│   │   ├── orchestrator.py  # Master scheduler (DAG orchestration)
│   │   ├── base.py          # Intent / Answer / Citation / Verification types
│   │   └── agents/          # Intent / DeptRouter / Rewriter / Retrieval / Answer / Verifier / Feedback
│   ├── loop/                # L3 Loop evolution layer
│   │   ├── loop_engine.py   # Execute→Observe→Reflect→Adapt→Deploy
│   │   ├── skill_miner.py   # DBSCAN clustering + Skill drafts + sandbox backtesting
│   │   ├── default_skills.py # 3 idempotent executable baseline Skills
│   │   ├── skill_executor.py # Workflows, canary bucketing, and outcomes
│   │   ├── hook_engine.py   # Event-response hooks
│   │   ├── rule_engine.py   # Hard-constraint rules
│   │   └── feedback_collector.py
│   ├── review/              # Human review Loop (human in / on / out of the loop)
│   │   └── review_engine.py # Auto-generate questions → system answers → review order → cumulative accuracy → progressive exit
│   ├── memory/              # Fact plane + five memory planes: session / episodic / user / organization / learning
│   ├── retrieval/           # L4 BM25 + vector + hybrid retrieval + reranking
│   ├── pipeline/            # Document parsing / cleaning / chunking / metadata / indexing / conflict detection
│   ├── llm/                 # DeepSeek + relay service clients + Embedding
│   ├── storage/             # MongoDB / Redis / unified storage (with in-memory fallback)
│   └── utils/               # Logging / Prometheus metrics
├── scripts/                 # Seed data / demo data / department document import / dependency waiting
├── tests/                   # Unit + end-to-end smoke tests
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

## Requirements

- Python 3.9+ (3.11 recommended)
- MongoDB 7.0 (optional; not needed with `STORAGE_MODE=memory`)
- Redis 7 (optional; memory mode falls back to in-memory)

## Installation

### Option 1: Docker (Recommended)

```bash
# From the project root program/
docker compose up --build
```

### Option 2: Local

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure secrets
cp ../.env.example ../.env   # Edit and fill in DEEPSEEK_API_KEY / RELAY_API_KEY

# Start in memory mode (no MongoDB/Redis needed, for a quick try)
export STORAGE_MODE=memory
export EMBEDDING_PROVIDER=hash   # Use deterministic vectors when offline
uvicorn app.main:app --reload --port 8000
```

### Optional Dependencies

- Vector retrieval: `pip install chromadb` (or set `VECTOR_BACKEND=chroma`)
- Local vectors: `pip install sentence-transformers` (`EMBEDDING_PROVIDER=local`)
- OCR for scanned documents: `pip install paddleocr paddlepaddle` (large; install as needed)

## Environment Variables (Key)

| Variable | Description |
|---|---|
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | Primary chat model (default `deepseek-v4-flash`) |
| `RELAY_API_KEY` / `RELAY_BASE_URL` | Relay service (OpenAI-compatible), used for non-DeepSeek models such as bge |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | `relay` (`text-embedding-3-large`) / `local` / `hash` |
| `STORAGE_MODE` | `mongo` / `memory` |
| `LOOP_PHASE` | `human_in_loop` / `human_on_loop` / `human_out_of_loop` |
| `AUTH_SECRET` | Token signing secret (must be changed in production) |
| `REVIEW_QUESTION_COUNT` / `REVIEW_ACCURACY_THRESHOLD` / `REVIEW_MIN_SAMPLES` | Human review Loop: number of questions / exit threshold / minimum samples |

## Running and Verification

```bash
# Seed data (departments / glossary / organization calendar / default rules / 3 baseline Skills)
python -m scripts.seed_data

# Demo data (merged departments + per-department mock documents / pending review orders / badcases / initial Skills)
python -m scripts.seed_demo_data

# Import sample documents from department_files
python -m scripts.ingest_department_files --base ../department_files

# Tests
pytest
```

## Key Design Notes

1. **Lightweight Harness orchestration**: agents follow a fixed DAG (Intent→Rewrite→Retrieve→Answer→Verify),
   without depending on LangChain/AutoGen; inputs and outputs are structured and debuggable.
2. **Hybrid retrieval**: BM25 + vectors (`text-embedding-3-large`/local/hash) fused with RRF + reranking.
3. **Loop self-evolution**: feedback queue → Reflect attribution → Skill/Hook/Rule updates → canary deployment,
   with `LOOP_PHASE` controlling human in / on / out of the loop.
4. **Unified storage abstraction**: `DataStore` interface + Mongo/Memory implementations, runnable and testable offline.
5. **End-to-end fallback**: when the LLM is unconfigured or fails, each agent degrades automatically (keyword intent / glossary expansion / source text concatenation / heuristic verification), so the system never crashes.
6. **Auth and roles**: login issues HMAC tokens carrying `iat/exp`; identity comes only from the token, and resource operations verify user/department ownership.
7. **Human review Loop**: new documents auto-generate questions on ingestion → the system answers → a review order is sent to the department admin → the question bank/feedback accumulates;
   once a department's accuracy exceeds the threshold with enough samples, it enters `human_out_of_loop`, while stable spot checks and error rollback remain.
8. **Trustworthy memory**: official documents remain an independent fact plane; a unified `MemoryContextBuilder` selectively injects the five kinds of memory,
   organizational FAQs must be traced back to active original chunks, and users can view and delete their own low-sensitivity long-term memory.
9. **pi Agent Runtime**: the Python control plane executes Intent, Rewrite, Answer,
   Verify, and Reflect through the unified `/v1/agent/run` protocol; when pi fails it automatically falls back to the original Python agents without affecting fact and permission governance.
10. **Observable Loop jobs**: manual Loop runs execute asynchronously via Redis Stream, and jobs continuously record stage progress and return a structured report;
    the frontend polls automatically and shows feedback signals, root causes, candidates, release results, and before/after diffs of policy assets.

## API Docs

After startup, visit http://localhost:8000/docs. For the endpoint list, see [../docs/api.md](../docs/api.md).
