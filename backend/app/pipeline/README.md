# Document Processing Pipeline

Upload → parse → clean → semantic chunking → metadata extraction → vectorization → index building → cross-department relation mining.

## Files

- `parser.py` — parses PDF/Word/Markdown/HTML/TXT uniformly into structured blocks (preserving heading hierarchy / tables / lists)
- `cleaner.py` — header/footer/watermark removal and full-width/half-width normalization
- `chunker.py` — chunks along clause-level semantic boundaries (chapter/section/article/clause), targeting 300-600 characters
- `metadata_extractor.py` — LLM extraction of effective date / type / keywords / scope / references
- `indexer.py` — ingestion orchestration (parse → chunk → vectors → BM25 → MongoDB)
- `conflict_detector.py` — cross-department conflict detection (rule-level references + semantic similarity + LLM judgment)

## Semantic Chunking Strategy

- Instead of hard-splitting by fixed tokens, sections are divided by heading hierarchy (chapter/section/article/clause)
- Clause boundaries (Article X / numbering) are the minimal units
- Short chunks are merged and over-long chunks are hard-split to stay within the target range

## Versions and Derived Memory

- Duplicate ingestion of the same file hash within the same department is rejected.
- A new file with the same title forms a `supersedes` version chain; the old version is archived only after the new version is ready.
- When a document is archived, deleted, or superseded by a new version, the `org_memory_items` bound to that version are automatically marked stale.
