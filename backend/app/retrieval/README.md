# Data and Retrieval Layer (L4)

BM25 keywords + vector semantics + RRF fusion + reranking.

## Files

- `bm25.py` — BM25; in multi-Pod `mongo` mode it is computed statelessly from the shared active chunks
- `vector_store.py` — vector store abstraction (in-memory / shared Mongo / Chroma; can switch to Milvus at scale)
- `reranker.py` — reranking (heuristic by default, optional cross-encoder)
- `hybrid.py` — hybrid retrieval (RRF reciprocal rank fusion)

## Retrieval Flow

1. BM25 recalls the top `BM25_TOP`
2. Vector cosine recalls the top `VECTOR_TOP`
3. RRF fusion
4. Reranking (optional reranker)
5. Return the top `HYBRID_TOPK`
6. Backfill full chunks from MongoDB and re-verify that the documents are active
