# Loop Evolution Layer (L3)

A feedback-driven self-optimization loop: Execute → Observe → Reflect → Adapt → Deploy.

## Files

- `loop_engine.py` — five-stage loop orchestration, bad case attribution (Reflect), canary deployment (Deploy)
- `default_skills.py` — three idempotent, genuinely executable baseline Skills and v1 policy snapshots
- `skill_miner.py` — trace embedding clustering (DBSCAN) → LLM-generated Skill drafts → sandbox backtesting
- `hook_engine.py` — event-response hooks (trigger evaluation + action application)
- `rule_engine.py` — hard-constraint rules (runtime injection + evolutionary updates)
- `feedback_collector.py` — aggregation of explicit/implicit/automatic feedback
- `skill_executor.py` — Skill workflow execution, stable treatment/control bucketing, outcome recording
- `strategy_evaluator.py` — same-question replay of baseline vs. candidate and policy quality comparison

## Human In / On / Out of the Loop

Controlled by `LOOP_PHASE`:

- `human_in_loop` — all automatic outputs are reviewed by humans
- `human_on_loop` — outputs with confidence ≥ `HOOK_HIGH_CONFIDENCE` take effect automatically
- `human_out_of_loop` — fully automatic within the defined scope

## Human Review Loop (Human In / On / Out of the Loop)

Besides the automatic evolution of Skills/Hooks/Rules, `../review/review_engine.py` implements a review loop centered on "humans progressively exiting":

1. After a new document is ingested, questions are generated automatically (the LLM creates test questions from the document's clauses).
2. The system answers using its own retrieval + generation chain (self-test).
3. A "review order" is generated and sent to the department admin, who judges each question correct/incorrect (accumulating feedback and the question bank).
4. When cumulative accuracy exceeds `REVIEW_ACCURACY_THRESHOLD` and samples ≥ `REVIEW_MIN_SAMPLES`,
   the department enters `human_out_of_loop`; documents not sampled pass automatically, and spot-check errors send it back to `human_on_loop`.

## Background Worker

`python -m scripts.async_worker` consumes async ingestion, feedback wake-up, and Loop jobs via Redis Stream.
Manual Loop jobs persist `queued/running/completed/failed`, record the current stage while running, and on completion return feedback, root causes, candidates,
release results, before/after changes to policy assets, and next-step suggestions; the admin console tracks them automatically via `/api/v1/admin/loop/jobs/{job_id}`.
Policy versions, experiments, and execution results are stored in `strategy_versions`, `experiments`, and `strategy_executions` respectively;
when treatment underperforms control, it is rolled back automatically.

## Baseline Skills and Auto-Mined Skills

Backend startup and `scripts.seed_data` idempotently create "Extreme Weather Safety Response", "Campus Procedure Step Navigation", and "Academic Milestone and Deadline Verification".
All three go directly into `SkillExecutor`, where they expand the query, raise top-k, inject output templates or calendar constraints, and record treatment/control,
hit counts, and success rates. Once traces reach the clustering threshold, the Skill Miner still generates new candidate Skills; both kinds of Skills share the same governance chain.

## Demo Data

`python -m scripts.seed_demo_data` generates mock documents, pending review orders, and badcases for each department, and writes
the rubric rules reflected from the badcases into each department's initial Skill (see `docs/loop-engineering.md`).
