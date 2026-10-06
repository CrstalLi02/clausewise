# Storage Layer

MongoDB (async motor) + Redis (redis.asyncio) + in-memory fallback.

## Files

- `models.py` — Pydantic models for facts, policies, session events, user semantic memory, and organizational memory
- `mongodb.py` — MongoDB client + index creation
- `store.py` — `DataStore` unified interface + `MongoStore` / `MemoryStore`
- `redis_store.py` — sessions (working memory) + cache, `RedisSessionStore` / `MemorySessionStore`

## Collections (Technical Design Section 3.1 + auth/review extensions)

`departments` / `documents` / `chunks` / `doc_relations` / `skills` / `hooks` / `rules` /
`feedback` / `traces` / `glossary` / `user_profiles` / `dept_memory` / `global_memory` /
`faq_cache` / `users` / `review_orders` / `test_questions` /
`strategy_versions` / `strategy_executions` / `strategy_proposals` / `experiments` /
`vector_embeddings` / `async_jobs` / `conversation_events` / `conversation_summaries` /
`user_memory_items` / `org_memory_items` / `memory_candidates` / `memory_usage` /
`memory_audit` / `memory_topics` / `memory_sequences`

Of these:

- `users` — login accounts (roles `student`/`admin`; can be bound to a `dept_id` to act as a department admin)
- `review_orders` — human review orders (auto-generated questions for new documents → system answers → per-question judgments)
- `test_questions` — test question bank (accumulated review feedback that drives progressive department exit)
- `conversation_events/summaries` — episodic memory with TTL; traces no longer double as session history
- `user_memory_items` — fine-grained, versioned, deletable low-sensitivity user memory
- `org_memory_items` — organizational knowledge with official sources, department scope, review status, and time validity
- `memory_usage/audit` — memory usage and change audit
- `async_jobs` — `queued/running/completed/failed`, stage progress, and structured results for ingestion and Loop jobs

## Notes

- With `STORAGE_MODE=memory`, everything is implemented in memory, so offline development/testing needs no MongoDB/Redis.
- TTL indexes automatically clean up session events, summaries, user memory, organizational memory, and hot-spot details.
- Mongo `increment()` uses `$inc` for event sequence numbers and hot-spot counters across multiple Pods, avoiding lost updates from whole-document overwrites.
