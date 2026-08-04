"""Central, env-driven configuration for VoltAgent.

Everything that varies between a laptop dev setup and a real deployment
lives here, not scattered across modules. Import `settings` everywhere else.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider ---
    llm_provider: str = "gemini"           # "gemini" | "openai"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    generation_model: str = "gemini-1.5-flash"

    # --- Elasticsearch ---
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "voltagent-chunks"

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "voltagent-chunks"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

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

    # --- Voice ---
    default_language: str = "en"           # "en" | "hi"

    # --- Observability ---
    log_level: str = "INFO"
    log_file: str = "observability/events.jsonl"

    # --- Ingestion ---
    chunk_size_tokens: int = 350
    chunk_overlap_tokens: int = 60

    # --- Insights (Spark/HDFS batch analytics layer) ---
    hdfs_uri: str | None = None            # e.g. "hdfs://localhost:9000" — leave unset to use local filesystem
    insights_log_dir: str = "observability/parquet"     # partitioned by date/station_id
    priority_flags_path: str = "observability/priority_flags.json"
    spark_app_name: str = "voltagent-insights"
    fault_recurrence_window_days: int = 7
    documentation_gap_confidence_threshold: float = 0.5  # queries below this feed the gap detector
    documentation_gap_min_occurrences: int = 3           # min repeated low-confidence hits to flag a doc
    streaming_fault_spike_count: int = 3                 # N reports in the window trigger an alert
    streaming_fault_spike_window_minutes: int = 60


settings = Settings()
