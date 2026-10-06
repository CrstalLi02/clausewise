"""LLM client layer.

- DeepSeekClient: primary chat model (https://api.deepseek.com)
- RelayClient: relay service (OpenAI-compatible, for non-DeepSeek models such as bge)
- EmbeddingClient: embedding model (calls text-embedding-3-large via the relay service by default)
"""
from app.llm.client import LLMClient, LLMError
from app.llm.deepseek import DeepSeekClient
from app.llm.relay import RelayClient
from app.llm.embeddings import EmbeddingClient

__all__ = [
    "LLMClient",
    "LLMError",
    "DeepSeekClient",
    "RelayClient",
    "EmbeddingClient",
]
