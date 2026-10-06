# Architecture and Module Breakdown

## 1. Service Topology (Separated Frontend/Backend + Modular Services)

```
┌────────────┐   REST /api/v1   ┌──────────────────────────┐
│ Next.js     │ ───────────────► │ Python Orchestrator/API  │
└────────────┘                  └───────────┬──────────────┘
                          Control plane     │        Agent execution
                                           ├──────────────► pi Runtime
                                           │ Parallel HTTP
                         ┌─────────────────┼─────────────────┐
                         ▼                 ▼                 ▼
                  dept-agent-jwc    dept-agent-cwc    dept-agent-*
                         └─────────────────┬─────────────────┘
                                           ▼
                               MongoDB + Redis Stream
```

## 2. Five-Layer Architecture → Code Mapping

| Layer | Design Components | Code Location |
|---|---|---|
| L1 Access layer | API Gateway / REST / Web | `backend/app/api/`, `web/` (Next.js) |
| L2 Harness collaboration layer | Orchestrator / Intent / Rewriter / Retrieval / Answer / Verifier / Feedback | `backend/app/harness/` |
| L3 Loop evolution layer | Loop Engine / Skill Miner / Hook / Rule / policy experiments | `backend/app/loop/` |
| L4 Data and retrieval layer | MongoDB / Vector / Embedding / BM25 / Reranker | `backend/app/pipeline/`, `backend/app/retrieval/`, `backend/app/storage/` |
| L5 Infrastructure layer | Docker / K8s / Redis / Monitoring | `deploy/`, `docker-compose.yml` |

## 3. Data Flow of a Single Q&A Request

1. `web` calls `POST /api/v1/chat` (proxied to the backend via Next.js rewrites).
2. `backend/app/harness/orchestrator.py` builds the dynamic policy and memory context and holds sole control.
3. The fixed Python DAG calls the pi Runtime to execute Intent, Rewrite, Answer, and Verify; when pi is unavailable it falls back to the local Python implementation.
4. Department agents are strictly isolated via `DEPT_ID` and only access their own documents; cross-department requests allow partial success and return the failed departments.
   The global Orchestrator passes the governed, budget-trimmed memory context through to department agents to keep entities consistent across turns.
5. MongoDB stores shared vectors, policy versions, experiment buckets, and execution results; Redis Stream carries ingestion, feedback, and Loop jobs.
6. Manual Loop runs record stage progress and structured results via persistent job records; the Web UI polls automatically instead of treating the enqueued `job_id` as an execution report.

## 4. The Fact Plane and Five Memory Planes

```text
active documents/chunks (facts)
          │
          ▼
MemoryContextBuilder
  ├─ Redis session working memory
  ├─ conversation_events/summaries episodic memory
  ├─ user_memory_items user semantic memory
  ├─ org_memory_items organizational knowledge memory
  └─ Skills/Hooks/Rules/Experiments procedural learning memory
```

Official facts have the highest authority. Organizational memory can only aid recall; the system must re-verify its `doc/chunk/version` and add the original chunk
to the evidence set. User preferences and session summaries can never become policy citations. Context usage is written to `memory_usage` and linked to the trace.

## 5. Control Plane and Execution Plane

- Python is the sole control plane, ensuring permissions, facts, memory, and policies each have a single source of truth.
- `services/pi-agent` is the unified agent execution plane, executing Intent/Rewrite/Answer/Verify/Reflect.
- Python passes in the governed prompt, official chunks, dynamic Rules, allowed tools, and per-stage timeouts.
- pi does not read MongoDB, does not decide `dept_id`, and does not release policies; on call failure Python automatically degrades.
- `loop/default_skills.py` provides three executable baseline Skills; automatically mined Skills share the same version, canary, and outcome governance.

## 6. Responsibility Boundaries

- **Python backend**: deterministic logic — document parsing/chunking/vectorization, hybrid retrieval, storage, public API, conflict detection, authentication, human review Loop.
- **pi-agent**: probabilistic reasoning execution — agent loop, model calls, structured output, and allowlisted tool calling.
- **web**: presentation and interaction (login / student Q&A / admin console), communicating with the backend only via REST.

## 7. Authentication and Human Review

- `backend/app/auth.py`: accounts + HMAC tokens, roles `student`/`admin` (can be bound to a `dept_id` to act as a department admin).
- `backend/app/review/review_engine.py`: auto-generate questions for new documents → system answers → review order → cumulative accuracy → progressive department exit (human-in-the-loop → out-of-the-loop).
- `backend/app/api/deps.py`: `require_user` / `require_admin` / `scope_dept` auth dependencies; all admin endpoints require the admin role,
  department admins (non-empty `dept_id`) have data isolation, and system admins (empty `dept_id`) see everything.

## 8. Automatic Department Routing (DeptRouter)

- `backend/app/harness/agents/dept_router.py`: student question → best-matching department.
  Strategy: exact keyword match (`DEPT_KEYWORDS`, explainable) → LLM semantic routing → fall back to all departments.
  Returns `{dept_ids, dept_names, matched_by, confidence, reasons}`.
- When the user does not specify `dept_ids`, `Orchestrator.answer()` first calls `DeptRouter.route()`, passes the routing result through to the Python DAG,
  and returns a `route` field in the response, which the frontend uses to display "Automatically routed to the XX department".
