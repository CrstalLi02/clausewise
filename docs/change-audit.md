# Code and Documentation Consistency Audit

This file records the documentation coverage check performed on 2026-08-17 for the first three phases of changes. The current code is the source of truth for status.

| Improvement | Main Code | Original Doc Status | Action This Round |
|---|---|---|---|
| Tokens carry `iat/exp`; identity comes only from the token | `backend/app/auth.py`, `api/routes/chat.py` | API examples still contained `user_id`; token expiry undocumented | Updated root/backend/API docs |
| Session, feedback, department, and conflict permissions | `api/routes/*.py` | Admin auth only vaguely described | Added ownership and department-scope descriptions |
| Active document filtering, chunk backfill, conflict detection fixes | `retrieval_agent.py`, `conflict_detector.py` | Not covered by retrieval docs | Updated retrieval/architecture docs |
| Duplicate hashing, version chains, archive invalidation | `pipeline/indexer.py` | Undocumented | Updated Pipeline/backend docs |
| Real evaluation set and four metrics | `evaluation/`, `scripts/evaluate_rag.py` | Root README had an entry point; testing docs incomplete | Added evaluation commands and metric definitions |
| Python Harness as the sole control plane | `harness/orchestrator.py`, config | Early root architecture diagram described full delegation to pi | Python retains governance; pi uniformly executes the five probabilistic agents |
| Skill execution, canary, replay, rollback | `loop/skill_executor.py`, `strategy_evaluator.py` | Loop docs only described the old canary concept | Updated Loop module and collection docs |
| Redis Stream async ingestion/feedback/Loop | `storage/job_queue.py`, `scripts/async_worker.py` | API still described synchronous upload; Loop README still described a scheduled worker | Updated API, Loop, and deployment docs |
| Independent department agents, `DEPT_ID` isolation, partial success | `dept_agent_client.py`, `internal.py` | Deployment docs incomplete | Updated architecture/API/deployment docs |
| Shared Mongo vectors and stateless BM25 | `vector_store.py`, `bm25.py` | Backend README still centered on Chroma/bge-m3 | Updated retrieval and deployment docs |
| Prometheus Adapter + custom HPA | `deploy/k8s/prometheus-adapter.yaml` | `docs/deployment.md` still described QPS/CPU | Updated to the inflight Pods metric |
| Fact plane + five memory planes | `app/memory/facts.py`, `context_builder.py`, etc. | Done | Root/backend/architecture/API/storage/memory/Loop/deployment docs all updated |
| pi Agent Runtime | `integrations/pi_runtime.py`, `services/pi-agent/src/server.ts` | Done | Unified `/v1/agent/run`, internal auth, allowlisted tools, and Python fallback |
| Loop async job visualization | `backend/app/api/routes/admin.py`, `backend/app/storage/job_queue.py`, `web/src/components/admin/LoopPanel.tsx` | Old frontend only showed the enqueued `job_id` | Added stage progress, job history, structured results, and before/after policy diffs |
| Executable baseline Skills | `loop/default_skills.py`, `loop/skill_executor.py` | Initial Skill list was empty and could not be demoed | Idempotently seeded three real workflows with versions, buckets, and metrics |
| Frontend three roles and memory/experiment views | `web/src/components/` | Old page features were scattered; core planes were invisible | Added role-based consoles, `InsightsPanel`, personal memory, and permission-consistent display |

Audit rule: every new module must have at least one traceable entry in its module README, `docs/architecture.md`, and any necessary API/deployment docs; request models follow the FastAPI schemas.
