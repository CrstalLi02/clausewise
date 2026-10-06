# Memory Architecture: One Fact Plane + Five Memory Planes

Official policy documents are not model memory; they form an independent fact plane with the highest authority. All long-term memory must have an explicit scope, source, time validity, and deletion policy.

| Plane | Implementation | Storage | Purpose |
|---|---|---|---|
| Fact plane | `facts.py` | `documents/chunks/doc_relations/glossary` | Returns only active official source text; the sole factual basis for answer citations |
| Session working memory | `working.py` | Redis | Recent messages, summary, entities, departments, and chunk IDs; TTL defaults to 30 minutes |
| Episodic memory | `episodic.py` | `conversation_events/conversation_summaries` | Append-only message events, session restoration, and rolling summaries |
| User semantic memory | `user_semantic.py` | `user_memory_items/memory_candidates` | Explicit user preferences and verified profile data; sensitive items are rejected, inferred items await review |
| Organizational knowledge memory | `organization.py` | `org_memory_items/memory_topics` | FAQs, procedure tips, organization calendar, and coordination outcomes; FAQs must be bound to an official source |
| Procedural/learning memory | `learning.py` + `app/loop/` | Skills/Hooks/Rules/experiment collections | Changes how the next round executes; supports canary, replay, and rollback |

## Unified Context

`context_builder.py` is the only read entry point. It recalls selectively by user, department, role, time validity, and authority level, and enforces a character budget.
The code entry classes are `FactPlane` and `MemoryContextBuilder`.
The context feeds into Intent, Query Rewriter, and Answer; memory can only help resolve references, user preferences, and retrieval direction, and can never be cited as policy.
When organizational memory is hit, the system re-reads the active source text for its `doc_id/chunk_id/document_version` before handing it to Answer and Verifier.

## Authority Order

```text
active official documents > admin-reviewed organizational memory > explicit user statements > session summaries > system inferences
```

System inferences never go directly into answers. When `source_type=inferred` and there is no consent, they are only written to `memory_candidates`.

## Lifecycle and Privacy

- Working memory: Redis TTL of 30 minutes, storing only chunk IDs, never the full retrieved text.
- Session events: 90 days by default; summaries and low-sensitivity user memory: 180 days by default.
- `mongodb.py` creates TTL indexes for these collections; `retention.py` provides explicit cleanup for memory mode and the background worker.
- Long-term memory of ID numbers, passwords, psychological assessment results, health, disciplinary records, and financial details is prohibited.
- Users can view, explicitly write, and delete their own memories via `/api/v1/memory/me`.
- Department admins can only manage their own department's organizational memory; archiving or superseding a document marks derived organizational memory as stale.
- `memory_usage` records the memories actually injected into answers along with the trace; `memory_audit` records writes and deletions.

## Legacy Data Migration

```bash
python -m scripts.migrate_memory
```

The migration script converts legacy user preferences into fine-grained memories and removes raw question/feedback text from long-term profiles; unsourced legacy FAQs only enter the pending-review candidates and never take effect directly.
