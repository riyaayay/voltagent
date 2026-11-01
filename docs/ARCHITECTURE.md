# Architecture

Request path (see README for the diagram):
`POST /query` -> `agents/graph.py` (LangGraph, linear) ->
query_agent -> cache_lookup -> retrieve (ES BM25 + Qdrant dense, RRF) -> generate -> verify -> build_response (+cache write).

| Piece | File | Notes |
|---|---|---|
| Config | `voltagent/config.py` | pydantic-settings, `.env` |
| LLM | `voltagent/llm.py` | `LLMClient` interface; Gemini, OpenAI, and deterministic `FakeLLMClient` (`LLM_PROVIDER=fake`, or `set_llm_client()` in tests) |
| Ingestion | `voltagent/ingestion/` | pypdf loader, per-page token chunking |
| Retrieval | `voltagent/retrieval/` | `sparse_es`, `dense_qdrant`, `fusion` (RRF), `hybrid` |
| Agents | `voltagent/agents/` | query, generation, verifier, graph |
| Cache | `voltagent/cache.py` | TTLCache or Redis |
| Insights | `voltagent/insights/` | Spark batch jobs; only `feedback_loop.py` is on the request path (reads a JSON flag file, only ever tightens the verifier threshold) |
| Voice | `voltagent/voice/tts.py`, `frontend/` | gTTS server side, Web Speech API in the browser |

Test tiers: see `docs/TESTING.md`. Safety rules: `docs/SAFETY_CONTRACT.md`.
