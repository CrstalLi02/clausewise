# REST API Reference

The backend listens on `http://localhost:8000` by default; interactive docs are at `/docs` (Swagger UI).

## General Conventions

- Prefix: `/api/v1`
- Response shape: `{"code": 0, "message": "ok", "data": ...}`; errors have `code != 0`.
- Authentication: after login, the frontend sends `Authorization: Bearer <token>` in the request header; admin endpoints require the admin role.

## Auth Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Log in, returns `{token, user}`; accounts `student/student123`, `admin/admin123` |
| GET | `/api/v1/auth/me` | Current logged-in user |
| GET | `/api/v1/auth/users` | User list (admin) |

## Admin Endpoints (Admin Only)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/admin/dashboard` | Loop overview dashboard (department phases / review stats / Skills / feedback / traces) |
| GET | `/api/v1/admin/agents` | Visualization data for each department's sub-agents |
| GET | `/api/v1/admin/review/orders` | Review order list (filterable by dept_id/status) |
| GET | `/api/v1/admin/review/orders/{id}` | Review order details (questions / system answers / citations) |
| POST | `/api/v1/admin/review/orders/{id}/submit` | Submit review results (per-question judgments, cumulative accuracy, automatic Loop phase advancement) |
| POST | `/api/v1/admin/documents/{doc_id}/review` | (Re)generate a review order for a document |
| GET | `/api/v1/admin/review/stats` | Review statistics and progressive-exit progress per department |
| GET | `/api/v1/admin/feedback/pending` | Pending feedback (Observe) |
| GET | `/api/v1/admin/traces` | Recent Q&A traces (Execute) |
| POST | `/api/v1/admin/loop/phase` | Set the global Loop phase |
| GET | `/api/v1/admin/system-insights` | Aggregated view of the five memory planes, fact plane, feedback, and policy experiments |

> Human review Loop: new documents auto-generate questions on ingestion → the system answers → a review order is sent to the department admin → per-question judgments accumulate into the question bank and feedback;
> when a department's cumulative accuracy ≥ `REVIEW_ACCURACY_THRESHOLD` and samples ≥ `REVIEW_MIN_SAMPLES`, the department automatically enters
> `human_out_of_loop`, documents not sampled pass automatically, and spot checks and error rollback remain in place.

> Department admin data isolation: admins with a non-empty `dept_id` (e.g., `jwc_admin`) can only see/operate on their own department's
> department, documents, Skills, Hooks/Rules, and review orders when calling admin endpoints; cross-department access returns 403. System admins (`admin`, empty `dept_id`) see everything.

## Endpoint List

### Health Checks

- `GET /healthz` — liveness probe (K8s liveness)
- `GET /readyz` — readiness probe (checks MongoDB/Redis connections, K8s readiness)

### Chat

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/chat` | Non-streaming Q&A, returns answer + citations |
| POST | `/api/v1/chat/stream` | SSE streaming Q&A |
| GET | `/api/v1/chat/{session_id}/history` | Session history |
| DELETE | `/api/v1/chat/{session_id}` | Clear a session |

Request body:

```json
{
  "query": "In which week is the course withdrawal deadline?",
  "session_id": "uuid",
  "dept_ids": null
}
```

`user_id` is taken only from the Bearer token; identity fields submitted by the client are not accepted. Session reads and deletes also verify ownership.

> Students no longer pick a department manually: pass `null` for `dept_ids`, and the backend's **DeptRouter (automatic department routing agent)** matches the question to the best-fitting department.
> The response includes a new `route` field: `{dept_ids, dept_names, matched_by(keyword|llm|all), confidence, reasons}`, which the frontend uses to display "Automatically routed to the XX department".

### Document Ingestion

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/documents/upload` | Upload a document (multipart), returns a Redis Stream async job id |
| GET | `/api/v1/documents/jobs/{job_id}` | Query the status of an ingestion job you started |
| GET | `/api/v1/documents` | Document list (filtered by department) |
| GET | `/api/v1/documents/{doc_id}` | Document details |
| POST | `/api/v1/documents/{doc_id}/status` | Update status (review/archive) |

### Departments

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/departments` | Department list |
| POST | `/api/v1/departments` | Create a department |
| GET | `/api/v1/departments/{dept_id}/conflicts` | Conflict detection results for the department |

### Feedback

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/feedback` | Submit explicit feedback (thumbs-up / thumbs-down / correction) |
| POST | `/api/v1/feedback/implicit` | Submit implicit feedback (copy/follow_up/abandon) |

### Memory Governance

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/memory/me` | View the current user's active low-sensitivity long-term memory |
| POST | `/api/v1/memory/me` | Write preferences/profile data after explicit user consent; sensitive fields are rejected |
| DELETE | `/api/v1/memory/me/{memory_id}` | Delete one of the current user's own memories |
| GET | `/api/v1/memory/sessions/{session_id}/summary` | View your own session summary |
| GET | `/api/v1/memory/organization` | Admins view organizational memory within their permission scope |
| POST | `/api/v1/memory/organization` | Publish organizational memory with official source refs |
| DELETE | `/api/v1/memory/organization/{memory_id}` | Revoke organizational memory within your permission scope |

Organizational `faq/procedure_tip/conflict_resolution` entries are rejected when they lack an active `doc_id/chunk_id/document_version` source.

### Loop / Admin

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/admin/skills` | Skills list |
| POST | `/api/v1/admin/skills/{id}/approve` | Approve a Skill |
| POST | `/api/v1/admin/loop/run` | Manually trigger one Loop cycle |
| GET | `/api/v1/admin/loop/jobs/{job_id}` | Query a Loop job's live status, stage progress, and structured results (system admin) |
| GET | `/api/v1/admin/loop/jobs?limit=10` | Recent Loop job history (system admin) |
| GET | `/api/v1/admin/loop/stats` | Loop run statistics |
| GET | `/api/v1/admin/glossary` | Glossary |
| POST | `/api/v1/admin/glossary` | Add a glossary mapping |

## Internal Endpoints (Called by Department Agents / pi Runtime)

Prefix `/api/v1/internal/*`, for allowlisted tool calls from department agents and the pi Runtime; not frontend-facing.
**All internal endpoints require the request header `X-Internal-Token: <INTERNAL_API_TOKEN>`** (must match the pi-agent environment variable);
when `INTERNAL_API_TOKEN` is not configured, internal endpoints return 503 directly (fail-closed).

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/internal/retrieve` | Hybrid retrieval, returns chunks (with doc_title) |
| POST | `/api/v1/internal/dept/answer` | Department-agent-specific Q&A; enforces that the request dept_id matches the instance `DEPT_ID` |
| GET | `/api/v1/internal/departments` | Department list |
| GET | `/api/v1/internal/calendar` | School calendar (global memory) |
| GET | `/api/v1/internal/glossary` | Glossary |
| POST | `/api/v1/internal/feedback` | Submit feedback |
| GET | `/api/v1/internal/feedback/pending` | Pending feedback |
| POST | `/api/v1/internal/artifacts` | Save Skills/Hooks/Rules (Loop outputs) |

## pi Agent Service Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/answer` | Q&A (pi-orchestrated DAG) |
| POST | `/loop/run` | Trigger a Loop cycle |

`/answer` and `/loop/run` are compatibility endpoints of the pi Runtime, not the production web path. Production Q&A uses the fixed Python DAG calling
`/v1/agent/run`; the production Loop is governed by the Python `LoopEngine` + Redis Stream Worker, with pi only executing probabilistic agents such as Reflect.
