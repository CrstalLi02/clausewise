# Access Layer (L1)

REST API and health probes, with the unified prefix `/api/v1` and response shape `{code, message, data}`.

## Files

- `router.py` — router aggregation (`/api/v1` prefix)
- `schemas.py` — request/response Pydantic models
- `deps.py` — auth dependencies (`get_optional_user` / `require_user` / `require_admin`)
- `routes/auth.py` — login / current user / user list
- `routes/chat.py` — chat (non-streaming + SSE streaming + session history)
- `routes/documents.py` — document upload / job status / list / details / status (Redis Stream async ingestion)
- `routes/departments.py` — department management and conflict queries
- `routes/feedback.py` — explicit feedback collection
- `routes/memory.py` — view/write/delete the user's own memory; publish/revoke organizational memory
- `routes/admin.py` — dashboard / system insights / department sub-agents / review center / Loop job tracking / Skills / Glossary
- `routes/internal.py` — shared-token internal endpoints for allowlisted tool calls from department agents and the pi Runtime
- `routes/health.py` — `/healthz` (liveness) and `/readyz` (readiness)

## Authentication

After login, the frontend sends `Authorization: Bearer <token>` in the request header; the token contains `iat/exp`. User identity is taken only from the token;
session, feedback, and memory endpoints verify ownership, and organizational memory endpoints verify the department admin's scope.
Global Loop triggering, job history, and phase switching are available only to system admins; requests from department admins return 403.

## Notes

Routes obtain the global singleton container via `request.app.state.container`; there is no global mutable state, which makes test substitution easy.
