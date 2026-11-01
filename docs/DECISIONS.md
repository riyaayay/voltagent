# VoltAgent Architectural Decisions & Tradeoffs

## ADR-001: Dependency Isolation — PySpark Split
- **Context**: `requirements.txt` previously contained `pyspark`, `pandas`, and `pyarrow`. PySpark is only imported by batch and streaming analytics jobs in `voltagent/insights/` and is never needed on the core request path, API service, or verifier test suite.
- **Decision**: Created `requirements-insights.txt` containing `pyspark>=3.5.0`, `pandas>=2.0.0`, and `pyarrow>=14.0.0`. Core `requirements.txt` retains only fast, direct dependencies required for the FastAPI, LangGraph, and hybrid search pipeline.
- **Consequence**: Environment installation time on Python 3.11 reduced significantly; deployment container images reduced by over 600 MB.

## ADR-002: Dual-Leg Retrieval Fallbacks with In-Process Persistence
- **Context**: In development or cost-constrained environments (e.g. laptop development with limited RAM, CI runners), running full Docker containers for Elasticsearch and Qdrant consumes substantial memory (WSL VM memory paging pressure, F-027).
- **Decision**: Implemented `SPARSE_BACKEND=elasticsearch|bm25` in `voltagent/retrieval/sparse_es.py` and `InProcessDenseRetriever` in `voltagent/retrieval/dense_qdrant.py`. Both backends persist their indexed chunks and precomputed embeddings to `data/index_cache/` (`bm25.pkl` and `dense.pt`).
- **Consequence**: The entire ingestion, retrieval, and verification pipeline operates with zero external services when needed, while maintaining 100% interface compatibility with production Elasticsearch 8.x and Qdrant 1.x clusters.

## ADR-003: Dual-Layer Verifier — Deterministic Gate + Semantic Embedding Scoring
- **Context**: Cosine similarity between sentence embeddings alone cannot reliably catch swapped numbers (5 mA vs 50 mA), wrong units (1.40 m vs 1.40 in), or negation flips (V1-V4, F-001). Conversely, purely keyword-based checking cannot handle linguistic paraphrasing or cross-lingual queries (Hindi to English).
- **Decision**: Combined a deterministic entity gate (`numeric_gate.py`) and a deterministic negation conflict detector with multilingual semantic support scoring (`paraphrase-multilingual-mpnet-base-v2` at threshold 0.55). The deterministic gate reads the full text of cited chunks, checking numbers + units, error codes, charger models, and OCPP message types.
- **Consequence**: Achieved an 80.0% wrong-case flag rate on the frozen adversarial benchmark (`test_wrong_10.json`) while maintaining a 0.0% false-flag rate on correct answers (`test_correct.json`).

## ADR-004: Windows Import Order Hazard Mitigation (F-021)
- **Context**: On Windows with Python 3.11, importing `elasticsearch` before `torch` triggers `WinError 1114` during C10 DLL initialization due to native runtime conflicts.
- **Decision**: Guarded import sequence in `tests/conftest.py` and ensured that `voltagent/retrieval/hybrid.py` imports `dense_qdrant` (torch) before `sparse_es` (elasticsearch). Documented in `tests/test_import_order.py`.
- **Consequence**: Eliminates native crash during startup on Windows hosts.

## ADR-005: Strict Safety Contract Degradation (Outcome C)
- **Context**: Previously, if Elasticsearch or Qdrant was unreachable, the FastAPI service threw an unhandled exception resulting in an HTTP 500 status code.
- **Decision**: Wrapped pipeline execution in `voltagent/agents/graph.py` with structured degradation boundaries. If either leg fails, hybrid retrieval falls back to the surviving leg and flags `degraded_stages`. If catastrophic unhandled failure occurs, the pipeline catches the exception, logs a complete trace, and returns an HTTP 200 response with typed `Outcome C` ("Cannot answer / degraded").
- **Consequence**: Field technicians never encounter raw 500 error pages, stack traces, or silent failures.
