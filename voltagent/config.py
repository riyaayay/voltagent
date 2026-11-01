"""Central, env-driven configuration for VoltAgent.

Everything that varies between a laptop dev setup and a real deployment
lives here, not scattered across modules. Import `settings` everywhere else.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider ---
    llm_provider: str = "gemini"           # "gemini" | "openai" | "fake"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    generation_model: str = "gemini-1.5-flash"
    llm_timeout_seconds: float = 15.0

    # --- Sparse retrieval ---
    sparse_backend: str = "elasticsearch"  # "elasticsearch" | "bm25"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "voltagent-chunks"
    elasticsearch_timeout_seconds: float = 2.0

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "voltagent-chunks"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    qdrant_timeout_seconds: float = 3.0
    dense_score_floor: float = 0.20

    # --- Retrieval ---
    top_k_sparse: int = 10
    top_k_dense: int = 10
    top_k_fused: int = 6
    rrf_k: int = 60

    # --- Verifier ---
    verifier_confidence_threshold: float = 0.55

    # --- Cache ---
    cache_backend: str = "memory"          # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 2048
    corpus_version_hash: str = "v1"

    # --- API ---
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]
    max_query_text_length: int = 2000

    # --- Voice ---
    default_language: str = "en"           # "en" | "hi"

    # --- Observability ---
    log_level: str = "INFO"
    log_file: str = "observability/events.jsonl"

    # --- Ingestion ---
    chunk_size_tokens: int = 350
    chunk_overlap_tokens: int = 60

    # --- API ---
    cors_allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
    max_query_text_length: int = 4000

    # --- Insights (Spark/HDFS batch analytics layer) ---
    hdfs_uri: str | None = None
    insights_log_dir: str = "observability/parquet"
    priority_flags_path: str = "observability/priority_flags.json"
    spark_app_name: str = "voltagent-insights"
    fault_recurrence_window_days: int = 7
    documentation_gap_confidence_threshold: float = 0.5
    documentation_gap_min_occurrences: int = 3
    streaming_fault_spike_count: int = 3
    streaming_fault_spike_window_minutes: int = 60


settings = Settings()
