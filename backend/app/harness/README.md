# Harness Collaboration Layer (L2)

Fixed-DAG multi-agent orchestration (no dependency on LangChain/AutoGen).

## Collaboration Flow

```
Python Orchestrator → MemoryContext → pi Intent → pi Rewrite → Python Retrieval/Fact Plane → pi Answer → pi Verifier → Feedback
```

## Files

- `orchestrator.py` — master scheduler: builds the memory context, loads procedural memory, retrieves official facts, generates, verifies, and persists traces
- `base.py` — `Intent` / `Answer` / `Citation` / `VerificationResult` types
- `agents/intent_agent.py` — intent / department / identity / cross-department judgment (LLM + keyword fallback)
- `agents/query_rewriter.py` — completion / terminology normalization / multi-query (LLM + glossary fallback)
- `agents/retrieval_agent.py` — hybrid retrieval execution (multiple queries × multiple departments)
- `agents/answer_agent.py` — answer generation with citations (LLM + source-text concatenation fallback)
- `agents/verifier_agent.py` — verification (LLM + heuristic fallback)
- `agents/feedback_agent.py` — collects feedback and writes it to the queue

## Design Points

- Every agent has structured input and output and degrades automatically when the LLM fails, so the system never crashes because a model is unavailable.
- Cross-department collaboration is determined by Intent + Hooks that expand the department scope, and Retrieval searches multiple departments in parallel.
- User/session/organizational memory is selectively injected via `MemoryContextBuilder`; only fact-plane chunks can be cited.
- Unsourced FAQs may not be answered directly; when organizational memory is hit, the active document version must be re-checked and go through the Verifier.
- Intent/Rewrite/Answer/Verifier are uniformly executed by the pi Runtime; the original Python implementations serve as failure fallbacks.
- Python explicitly passes an allowlist of `allowed_tools`, so pi cannot expand tool permissions or bypass fact retrieval.
- `SkillExecutor` runs matched workflows before Retrieval and can expand the query/top-k or add output templates or calendar constraints;
  the baseline Skills in `default_skills.py` and Skills auto-mined by the Loop follow the same execution path.
