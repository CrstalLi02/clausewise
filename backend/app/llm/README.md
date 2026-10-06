# LLM Client Layer

A unified OpenAI-compatible interface (async httpx), distinguishing DeepSeek from the relay service.

## Files

- `client.py` — `LLMClient` base class: `complete` / `complete_json` / `stream` (SSE)
- `deepseek.py` — DeepSeek primary chat model (`deepseek-v4-flash`)
- `relay.py` — relay service client (OpenAI-compatible, including `/embeddings`)
- `embeddings.py` — embedding models (relay `text-embedding-3-large` / local / deterministic hash fallback)

## Conventions

- Chat model: DeepSeek (`DEEPSEEK_*` environment variables)
- Embedding and bge reranker: relay service (`RELAY_*`, OpenAI-compatible); this relay service does not support bge-m3 embedding.
- Fails fast when no key is configured (raises `LLMError`) so the upper-layer agent can degrade, without making a network request
