# Clausewise：Document Processing and Q&A Assistant

An intelligent processing and Q&A system for official policy documents in any multi-department organization — companies, government agencies, hospitals, universities, and more. The bundled demo dataset uses a university as an example (Academic Affairs, Student Affairs, Finance, Human Resources, Logistics, Graduate School, etc.); departments, documents, and glossary are fully configurable.

It covers the full loop of **"document ingestion → intelligent Q&A → self-evolution"**: automatic document parsing and ingestion, multi-agent collaborative Q&A with precise source tracing, Loop Engineering self-evolution (automatically accumulating Skills/Hooks/Rules), and per-department elastic scaling on K8s.

## Key Features

### 📄 Document Ingestion Pipeline
- **Multi-format parsing**: PDF (pdfplumber, falling back to pypdf), DOCX (paragraphs and tables), Markdown, HTML, and TXT, preserving heading hierarchy, lists, and tables.
- **Async processing**: uploads return immediately; a Redis Stream worker runs the pipeline, and the UI polls job status (`queued → running → completed/failed`).
- **Clause-level chunking**: splits along Chapter / Section / Article boundaries instead of fixed token windows (target 300–600 characters), so every answer can be traced to a specific clause.
- **Cleaning and metadata**: removes page numbers, headers, and watermarks; the LLM extracts effective date, document type, keywords, applicable audience, and cross-references.
- **Versioning and deduplication**: identical files are rejected; a new file with the same title becomes a new version linked by `supersedes`, and the old version is archived only after the new one is fully indexed (fail-safe, with cleanup on failure).
- **Cross-department conflict detection**: on ingestion, reference patterns are mined by regex and similar clauses from other departments are compared semantically, with the LLM judging real contradictions (e.g., two departments giving different deadlines for the same matter).

### 💬 Trusted Q&A
- **Automatic department routing**: explainable keyword matching → LLM semantic routing → fall back to all departments; the answer shows which department was chosen and why.
- **Multi-agent fixed DAG**: Intent → Query Rewrite (glossary synonyms, multiple queries) → Retrieval → Answer → Verifier, with no LangChain/AutoGen dependency.
- **Hybrid retrieval**: BM25 keywords + vector semantics fused with RRF, reranked by `bge-reranker-v2-m3`; hits are re-read from MongoDB and filtered to active documents only.
- **Citations and anti-hallucination**: every key conclusion is marked `[Source N]` and linked to the document, section, and original text; when nothing is found, the system says no explicit provision exists instead of guessing.
- **Independent verification**: the Verifier checks grounding, contradictions, omissions, and citation format, and sends answers back for rewriting up to 2 times.
- **Cross-department collaboration**: questions spanning departments are sent to department agents in parallel; partial success is allowed and degraded departments are reported.
- **Multi-turn context**: follow-up questions such as "and when is it due?" are resolved from the session summary and entities.

### 🧠 Governed Memory
- **One fact plane + five memory planes**: session working memory (Redis, 30-minute TTL), episodic memory, user semantic memory, organizational knowledge memory, and procedural learning memory (Skills/Hooks/Rules/experiments).
- **Facts always win**: only active official documents can be cited; organizational FAQs must be bound to a source chunk and version, and become stale automatically when that document is archived or replaced.
- **Privacy by design**: long-term user memory requires explicit consent, sensitive fields (ID numbers, passwords, health, financial details, etc.) are rejected, inferred preferences only become pending candidates, and users can view and delete their own memory.
- **Auditing**: every memory used in an answer is recorded in `memory_usage`, and writes/deletions in `memory_audit`.

### 🔁 Self-Evolving Loop
- **Five-stage cycle**: Execute (record full traces) → Observe (explicit 👍/👎/corrections, implicit copy/follow-up/abandon, Verifier signals) → Reflect (root cause: retrieval / intent / generation / knowledge gap) → Adapt (generate Skill/Hook/Rule candidates) → Deploy.
- **Skills that actually change behavior**: a matched Skill expands the retrieval query, raises top-k, injects an output template, or adds calendar constraints — it is not just extra prompt text. Three executable baseline Skills ship by default, and the Skill Miner clusters frequent questions (DBSCAN) to propose new ones.
- **Safe rollout**: stable-hash treatment/control bucketing, versioned policy snapshots, same-question replay of baseline vs. candidate, and automatic rollback when the treatment underperforms.
- **Lifecycle management**: rarely used or low-success Skills are marked stale, superseded ones deprecated, and heavily overlapping Skills get merge proposals.
- **Mutable scope**: thresholds, weights, and triggers can change automatically, while Skill logic and rule content require human review.

### 👥 Human-in-the-Loop Review
- **Auto-generated tests**: each new document produces test questions that the system answers itself; department admins judge every answer and can submit corrections.
- **Progressive exit**: departments move from human-in-the-loop → human-on-the-loop → human-out-of-the-loop once accuracy ≥ 80% over at least 5 samples (configurable).
- **Spot checks**: out-of-the-loop departments are still sampled, and any error rolls them back to human-on-the-loop.

### 🛡️ Roles and Security
- **Three roles**: end user (Q&A, citations, history, personal memory), department admin (own department only), and super admin (global Loop, policies, all departments).
- **Strict isolation**: HMAC tokens with expiry; identity comes only from the token; sessions, feedback, and memory check ownership; department data is isolated on the backend.
- **Hardened internals**: internal endpoints require a shared token and fail closed; login rate limiting; upload type and size limits; pi agents only get the tools Python explicitly allows.

### 📊 Admin Console
Six panels: **Overview** (phase and accuracy per department), **Knowledge Assets** (departments, uploads, pipeline stages), **Trusted Review** (per-question review), **Evolution Loop** (live job tracking, structured reports, Skills/Hooks/Rules), **Memory & Experiments** (memory planes, fact plane, canary traffic, feedback radar), and **Agent Network** (per-department agent stacks).

### ☸️ Deployment, Scaling, and Resilience
- **Per-department elasticity**: each department agent is its own Deployment + HPA, scaled on the `clausewise_dept_agent_inflight` metric via the Prometheus Adapter (e.g., 1 replica for quiet departments, up to 20 for busy ones).
- **One-command local stack**: Docker Compose for MongoDB, Redis, backend, worker, pi agent, and web; Kubernetes manifests and a Helm chart for production.
- **Graceful degradation**: pi Runtime → local Python LLM → keyword/heuristic fallbacks, so the system keeps answering even when models are unavailable.
- **Observability**: Prometheus metrics for latency, retrieval hits, adoption, Skill triggers, and pi execution status.

> **Current limitations**: the full conflict review → notification → resolution workflow, OCR for scanned PDFs, statistical significance testing for experiments, circuit breakers/DLQ, and a real 1 → 20 Pod load-test report are not yet complete.

> For the detailed technical design, see [`design_files/Clausewise-Technical-Design-Cross-Department-Self-Evolving-Document-Processing-and-QA-Assistant.md`](design_files/Clausewise-Technical-Design-Cross-Department-Self-Evolving-Document-Processing-and-QA-Assistant.md)

## Architecture (separated frontend/backend + modular services)

```
┌────────────┐   REST    ┌──────────────────────────┐
│ Next.js     │ ───────► │ Python Orchestrator/API  │
└────────────┘           └────────────┬─────────────┘
                                      │ Parallel department routing
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                    dept-agent   dept-agent   dept-agent
                         └────────────┬────────────┘
                                      ▼
                        MongoDB + Redis Stream + Worker
```

| Service | Directory | Responsibility |
|---|---|---|
| Frontend | `web/` | React + Next.js chat interface |
| Backend | `backend/` | FastAPI: document parsing/chunking/vectorization, BM25 + vector hybrid retrieval, MongoDB/Redis storage, public REST API |
| Agent execution engine | `services/pi-agent/` | Unified model inference, agent loop, and controlled tool calling for Intent/Rewrite/Answer/Verify/Reflect |

> Python is the sole control plane: it owns the fixed DAG, authentication, facts, memory, department isolation, dynamic policies, canary releases, and rollbacks.
> pi is the unified probabilistic agent execution engine: it handles the agent loop, model calls, and controlled tool calling. pi does not directly decide data permissions or policy releases.

## Directory Structure

```
program/
├── README.md                 # This file
├── docker-compose.yml        # Full-stack orchestration (MongoDB/Redis/backend/worker/pi-agent/web)
├── .env.example              # Environment variable template
├── Makefile
├── docs/                     # Architecture / API / deployment / Loop docs
├── docs/change-audit.md      # Audit of code changes vs. documentation coverage
├── backend/                  # Python backend (see backend/README.md)
├── services/pi-agent/        # pi agent service (see services/pi-agent/README.md)
├── web/                      # Next.js frontend (see web/README.md)
├── deploy/                   # K8s / Helm deployment (see deploy/README.md)
├── design_files/             # Design inputs
└── department_files/         # Sample department documents
```

## 🚀 Running After Installing Docker Desktop (Recommended)

> Prerequisite: [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed and running (the Docker icon shows "running").

```bash
# 1. Enter the project directory
cd program

# 2. Copy the environment file and fill in real keys (or use the provided .env directly)
cp .env.example .env

# 3. Build and start the full stack in one command (the first run downloads images and is slow)
docker compose up --build -d

# 4. Check service status and logs
docker compose ps
docker compose logs -f
```

Once startup completes:

| Service | URL |
|---|---|
| Frontend chat interface | http://localhost:8080 |
| Backend API / OpenAPI docs | http://localhost:8000/docs |
| pi agent service | http://localhost:8100/health |
| MongoDB | `localhost:27017` (credentials in `.env`) |

### Importing Sample Department Documents (First Run)

```bash
# Seed data (departments / glossary / organization calendar / default rules)
docker compose exec backend python -m scripts.seed_data

# Import the PDF/Word files under department_files (the script auto-detects /app/department_files; you can also specify it explicitly)
docker compose exec backend python -m scripts.ingest_department_files --base /app/department_files
```

`seed_data` and the backend startup process idempotently initialize 3 executable baseline Skills (extreme-weather safety response, procedure step navigation, and academic milestone and deadline verification). They genuinely participate in query matching, retrieval expansion, answer templates, and policy execution records, and are not just for page display.

The admin-side "Evolution Loop" uses asynchronous job tracking: after it is triggered, the page automatically polls `queued → running → completed` and shows the Observe / Reflect / Adapt / Deploy stages, feedback signals, root causes, candidates, release results, and before/after changes to policy assets.

### Model Connectivity Self-Check (doctor)

```bash
# Verify that DeepSeek + the relay service (bge reranking / Embedding) can be called
docker compose exec backend python -m scripts.doctor

# Verify that the pi framework + DeepSeek work correctly
# Note: doctor depends on devDependencies (tsx), which are unavailable in the container image, so it can only be run locally:
cd services/pi-agent && npm install && npm run doctor
```

Stop and clean up:

```bash
docker compose down           # Stop
docker compose down -v        # Stop and remove data volumes
```

## Local Development (Without Docker)

Requires Python 3.9+ (3.11 recommended) and Node.js ≥ 22.19.

```bash
# 1) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export STORAGE_MODE=memory   # Use in-memory mode when MongoDB/Redis are unavailable
uvicorn app.main:app --reload --port 8000

# 2) pi agent service (in another terminal)
cd services/pi-agent
npm install
npm run dev                  # :8100

# 3) Frontend (in another terminal)
cd web
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # :3000
```

## Environment Variables (Key Items)

| Variable | Description | Default |
|---|---|---|
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | Primary chat model | `deepseek-v4-flash` |
| `RELAY_API_KEY` / `RELAY_BASE_URL` | Relay service (for non-DeepSeek models) | `https://yunwu.ai/v1` |
| `EMBEDDING_MODEL` | Embedding model (via the relay service) | `text-embedding-3-large` |
| `RERANKER_MODEL` | bge reranker model (via the relay service) | `BAAI/bge-reranker-v2-m3` |
| `PI_AGENT_ENABLED` | Whether to use pi to execute probabilistic agents uniformly; automatically falls back to the local Python implementation on failure | `true` |
| `PI_RUNTIME_TIMEOUT_*` | Per-stage timeouts for pi Intent/Rewrite/Answer/Verify/Reflect | `8/10/45/20/45s` |
| `DEPT_AGENTS_ENABLED` / `DEPT_ID` | Global department routing switch / enforced scope for a department Pod | `false` / empty |
| `VECTOR_BACKEND` | Vector storage; K8s uses the shared `mongo` | `memory` |
| `STORAGE_MODE` | `mongo` / `memory` | `mongo` |
| `AUTH_SECRET` | Token signing secret (**must be changed to a strong random value in production**) | dev placeholder |
| `INTERNAL_API_TOKEN` | Shared token for internal `/internal/*` endpoints (must match between backend and pi-agent) | empty (internal endpoints are unavailable if unset) |
| `SEED_DEMO_USERS` | Whether to create demo accounts (set to `false` in production) | `true` |
| `MAX_UPLOAD_MB` | Maximum document upload size | `20` |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` | Failed-login rate limiting | `5` / `300` |
| `MEMORY_SESSION_TTL_SECONDS` | Redis working-memory TTL | `1800` |
| `MEMORY_EVENT_RETENTION_DAYS` / `MEMORY_SUMMARY_RETENTION_DAYS` | Retention period for episodic events / summaries | `90` / `180` |
| `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD` | MongoDB root account (compose initialization) | `clausewise_admin` / strong random |
| `REDIS_PASSWORD` | Redis password (compose requirepass) | strong random |

> Verified in practice with `scripts/doctor.py`: DeepSeek `deepseek-v4-flash` ✅, relay service `gpt-5.5` ✅,
> `text-embedding-3-large` ✅, bge reranker `BAAI/bge-reranker-v2-m3` ✅.
> Note: this relay service does **not provide** `bge-m3` embedding or `gpt-5.5-pro` (these two names are invalid).

## Module READMEs

- [`backend/README.md`](backend/README.md)
- [`services/pi-agent/README.md`](services/pi-agent/README.md)
- [`web/README.md`](web/README.md)
- [`deploy/README.md`](deploy/README.md)
- [`docs/architecture.md`](docs/architecture.md) · [`docs/api.md`](docs/api.md) · [`docs/deployment.md`](docs/deployment.md) · [`docs/loop-engineering.md`](docs/loop-engineering.md)

## Tech Stack

Python 3.11 · FastAPI · MongoDB (motor) · Redis · Next.js 15 · React 19 · TypeScript ·
[pi](https://github.com/earendil-works/pi) (pi-agent-core + pi-ai) · DeepSeek (chat) ·
text-embedding-3-large / bge-reranker-v2-m3 (via the relay service) · Docker · Kubernetes · Helm

## Verification

```bash
cd backend && .venv/bin/pytest -q
cd web && npm run build
cd services/pi-agent && npm run build
```

The real-document evaluation set is located at `backend/evaluation/real_document_qa.json`. Running
`python -m scripts.evaluate_rag` yields Recall@5, MRR, citation accuracy, and answer consistency.
For the 1→20 replica load test of department agents, see `loadtest/README.md`.

## Memory and Fact Boundaries

The system adopts "one independent fact plane + five memory planes":

- `documents/chunks` is the highest-authority source of truth and is not part of model memory;
- Redis session working memory;
- MongoDB episodic events and summaries;
- Explainable, deletable user semantic memory;
- Organizational knowledge memory with official sources and department permissions;
- Procedural and learning memory composed of Skills/Hooks/Rules/experiments.

Every organizational FAQ must be bound to an active document chunk, and it automatically becomes invalid once the document is archived or replaced by a new version. See
[`backend/app/memory/README.md`](backend/app/memory/README.md) for details.
