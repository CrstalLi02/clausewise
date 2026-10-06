"""Centralized configuration: read from environment variables / .env.

DeepSeek is the primary chat model; the relay service (OpenAI-compatible) is used for non-DeepSeek models such as bge.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- Service ----
    app_name: str = "Clausewise · Cross-Department Document Processing and Q&A Assistant"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    # Explicitly list allowed frontend origins (replace with real domains in production); wildcards are not allowed for credentialed requests
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    api_prefix: str = "/api/v1"

    # ---- DeepSeek (primary chat model) ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_temperature: float = 0.1
    deepseek_max_tokens: int = 2048
    deepseek_timeout: float = 60.0

    # ---- Relay service (non-DeepSeek models, OpenAI-compatible) ----
    relay_api_key: str = ""
    relay_base_url: str = "https://yunwu.ai/v1"
    relay_model: str = "gpt-5.5"

    # ---- Embedding ----
    # provider: relay | local | hash
    # Note: this relay service does not provide bge-m3 embedding; text-embedding-3-large (3072) is verified to work
    embedding_provider: str = "relay"
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072

    # ---- Storage ----
    storage_mode: str = "mongo"  # mongo | memory
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "clausewise"
    redis_addr: str = "redis://localhost:6379"
    redis_db: int = 0
    async_stream_name: str = "clausewise:jobs"
    upload_storage_dir: str = "/tmp/clausewise-uploads"

    # ---- Retrieval ----
    vector_backend: str = "memory"  # memory | mongo | chroma | milvus
    hybrid_topk: int = 5
    bm25_top: int = 20
    vector_top: int = 20
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # ---- pi agent service (deep Harness + Loop integration) ----
    # The Python Harness is the only production Q&A runtime; pi-agent is kept as an experimental service and is not wired into the main path by default.
    pi_agent_enabled: bool = True
    pi_agent_url: str = "http://localhost:8100"
    pi_agent_timeout: float = 120.0
    pi_runtime_timeout_intent: float = 8.0
    pi_runtime_timeout_rewrite: float = 10.0
    pi_runtime_timeout_answer: float = 45.0
    pi_runtime_timeout_verify: float = 20.0
    pi_runtime_timeout_reflect: float = 45.0

    # ---- Department agent service discovery ----
    dept_id: str = ""
    dept_agents_enabled: bool = False
    dept_agent_url_template: str = "http://dept-agent-{slug}:8000"
    dept_agent_timeout: float = 6.0
    dept_agent_partial_timeout: float = 2.0

    # ---- Loop evolution ----
    loop_enabled: bool = True
    skill_min_cluster: int = 20      # Minimum occurrences of the same question pattern within a 7-day window
    skill_sandbox_min_success: float = 0.85
    hook_high_confidence: float = 0.9  # Auto-apply threshold for high confidence
    loop_phase: str = "human_in_loop"  # human_in_loop | human_on_loop | human_out_of_loop (starts at Phase 1 by default)
    loop_gray_percent: float = 0.1
    loop_rollback_min_samples: int = 10
    loop_rollback_margin: float = 0.1
    review_sample_rate: float = 0.1

    # ---- Memory governance (fact plane + five memory planes) ----
    memory_session_ttl_seconds: int = 1800
    memory_event_retention_days: int = 90
    memory_summary_retention_days: int = 180
    memory_user_retention_days: int = 180
    memory_topic_retention_days: int = 90
    memory_max_recent_messages: int = 10
    memory_context_max_chars: int = 6000
    memory_user_limit: int = 8
    memory_org_limit: int = 8

    # ---- Authentication ----
    auth_secret: str = "clausewise-dev-secret-change-me"
    auth_token_ttl_hours: int = 24
    # Shared token for internal endpoints (/internal/*): internal endpoints are unavailable when empty (fail-closed)
    internal_api_token: str = ""
    # Demo seed account switch: production must use SEED_DEMO_USERS=false (and delete any created demo accounts)
    seed_demo_users: bool = True
    # Login rate limiting (in-memory, effective within a single process)
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    # ---- Upload limits ----
    max_upload_mb: int = 20

    # ---- Human review Loop (progressive department exit) ----
    review_question_count: int = 3       # Number of test questions auto-generated after a new document is ingested
    review_accuracy_threshold: float = 0.8   # Human review is disabled once accuracy exceeds this threshold
    review_min_samples: int = 5          # Minimum number of review samples required to reach the threshold

    # ---- Timeouts (end-to-end) ----
    timeout_intent: float = 1.0
    timeout_retrieval: float = 2.0
    timeout_answer: float = 5.0
    timeout_verify: float = 3.0

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
