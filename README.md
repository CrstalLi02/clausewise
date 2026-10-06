# Clausewise：Document Processing and Q&A Assistant

An intelligent processing and Q&A system for official policy documents in any multi-department organization — companies, government agencies, hospitals, universities, and more. The bundled demo dataset uses a university as an example (Academic Affairs, Student Affairs, Finance, Human Resources, Logistics, Graduate School, etc.); departments, documents, and glossary are fully configurable.

It covers the full loop of **"document ingestion → intelligent Q&A → self-evolution"**: automatic document parsing and ingestion, multi-agent collaborative Q&A with precise source tracing, Loop Engineering self-evolution (automatically accumulating Skills/Hooks/Rules), and per-department elastic scaling on K8s.

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
