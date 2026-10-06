# Loop Engineering Self-Evolution Mechanism

## 1. Loop vs Automation

- **Automation**: runs a fixed process on a schedule with deterministic input/logic/output (e.g., "re-index new documents every night").
- **Loop**: each round's results become feedback input that **changes the next round's behavior** (e.g., "thumbs-down → root-cause analysis → adjust the retrieval strategy → better next time").

## 2. The Five-Stage Loop

```
Execute ──► Observe ──► Reflect ──► Adapt ──► Deploy ──┐
   ▲                                                   │
   └───────────────────────────────────────────────────┘
```

| Stage | Implementation | Responsibility |
|---|---|---|
| Execute | `loop_engine.py` | Answer using the current Skills/Hooks/Rules and record the full trace |
| Observe | `feedback_collector.py` | Collect explicit (thumbs-up/down/corrections), implicit (follow-up questions/copying), and automatic (Verifier self-check) feedback |
| Reflect | `loop_engine.py` + pi Runtime | pi generates root causes and candidate suggestions; Python validates, replays, and releases |
| Adapt | `skill_miner.py` / `hook_engine.py` / `rule_engine.py` | Generate Skill/Hook/Rule updates that go to review or take effect automatically |
| Deploy | `loop_engine.py` | Canary release, full rollout after backtest validation, then back to Execute |

`skill_executor.py` assigns treatment/control stably, and `strategy_evaluator.py` replays both baseline and candidate on the same historical questions;
executions, versions, and experiments are written to `strategy_executions`, `strategy_versions`, and `experiments`, and degraded policies are rolled back automatically.

## 3. Mutable Scope

| Object | Auto-modifiable | Requires Human Review | Not Auto-modifiable |
|---|---|---|---|
| Skills | Trigger conditions, parameter templates | Skill body (prompt logic) | — |
| Hooks | Trigger thresholds, routing rules | Hook action definitions | — |
| Rules | Weights, priority, top-k | Rule content | — |

## 4. Success Metrics

- Answer quality: adoption rate (👍/👎), number of cited clauses per answer (≥1), Verifier score (0-1)
- Retrieval quality: Hit Rate@5, MRR
- Efficiency targets: first token < 2s, P99 < 8s, per-turn cost < ¥0.02; SSE currently still streams chunks only after the full answer is generated, so the first-token target has not yet been met
- Coverage: answerable rate ≥ 90%

## 5. Humans Progressively Exit the Loop

- **Phase 1 human-in-the-loop**: all automatic outputs must be reviewed by a human before taking effect.
- **Phase 2 human-on-the-loop**: outputs with confidence > `HOOK_HIGH_CONFIDENCE` take effect automatically; others go to the review queue.
- **Phase 3 human-out-of-the-loop**: fully automatic within the defined scope.

Controlled via the `LOOP_PHASE` environment variable: `human_in_loop | human_on_loop | human_out_of_loop`.

## 6. Skills / Hooks / Rules

- **Skills**: procedural knowledge — "how to do it". E.g., `deadline_query` (deadline lookup + organization calendar tool + countdown template).
- **Hooks**: event responses — "what to trigger when". E.g., `cross_dept_hook` (course registration + payment → search both Academic Affairs and Finance).
- **Rules**: hard constraints — "must be obeyed". E.g., `cite_source_rule` (must include citations), `no_guess_rule` (say so explicitly when there is no basis).

### Executable Baseline Skills

`backend/app/loop/default_skills.py` idempotently provides three real workflows at startup: extreme-weather safety response, procedure step navigation,
and academic milestone and deadline verification. They demonstrate the full execution chain before high-frequency traces reach the auto-mining threshold, and they genuinely change the query, top-k,
output template, or calendar constraints while recording versions, buckets, hits, and success rates. Automatically mined Skills use the same `SkillExecutor`.

## 7. Human Review Loop (Progressive Department Exit)

`backend/app/review/review_engine.py` turns "humans progressively exit" into an observable process:

1. **Auto-generated questions**: after a new document is ingested, the LLM generates test questions from its clauses (accumulated in the `test_questions` bank).
2. **System answers**: answers using its own retrieval + generation chain (with citations).
3. **Review order**: questions + answers are sent to the department admin (`review_orders`), who judges each one correct/incorrect.
4. **Progressive exit**: when cumulative accuracy ≥ `REVIEW_ACCURACY_THRESHOLD` (default 0.8) and samples ≥ `REVIEW_MIN_SAMPLES` (default 5),
   the department advances to `human_out_of_loop`; spot checks continue at `REVIEW_SAMPLE_RATE`, and errors automatically send it back to `human_on_loop`.

Department `loop_phase` has three states: `human_in_loop` (100% human) → `human_on_loop` (accuracy met, accumulating samples) → `human_out_of_loop` (automatic).

> Tip: the Observe stage of `POST /admin/loop/run` (the frontend's "Manually trigger a Loop") only reads "unconsumed feedback"
> (records in the `feedback` collection with `consumed=False`), and marks them all as consumed when the loop finishes.
> So a second click returns `observed: 0` (feedback has been processed; this is normal); to repeat the demo, re-run
> `python -m scripts.seed_demo_data` to restore the badcases.
>
> The admin console now automatically polls `/api/v1/admin/loop/jobs/{job_id}`, showing `queued/running/completed/failed`, stage progress,
> signals, root causes, candidates, release results, and before/after diffs; the `job_id` returned on enqueue is no longer treated as the final report.

## 8. Demo Extension Skills and Rubric Rules

After running the optional `seed_demo_data`, each demo department also gets a Skill (`skill_<dept>_seed`) containing:

- `unique_rules`: rules unique to that department (e.g., Academic Affairs: "course withdrawal deadline is week 8; refunds are proportional to remaining weeks"), written statically by the seed.
- `rubric_rules`: scorecard rules summarized from badcase reflection, **initially empty and accumulated via Reflect→Adapt after running the Loop**.
  When "Manually trigger a Loop" runs, `_deterministic_suggestions` extracts rule suggestions from each badcase's `detail.rule`
  and appends each rule to the corresponding department Skill's `rubric_rules` (while also generating global/department Rules pending review).

Skill metrics: `trigger_count` / `success_count` / `success_rate` / `last_triggered` are updated in real time after every Q&A that hits the Skill
(`orchestrator._record_skill_usage`).

Demo data generation: `python -m scripts.seed_demo_data` (merged departments + mock documents + pending review orders + badcases + initial Skills).

Traces are observational data; only Skills/Hooks/Rules that have passed review or experimental validation enter procedural memory. The Loop must never
promote sensitive user text directly into long-term user memory.

pi only participates in the probabilistic analysis of Reflect and never activates policies directly; Mutable Scope, experiments, review, and rollback remain under Python's control.
