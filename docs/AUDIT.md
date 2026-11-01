# Audit Report: VoltAgent Reality vs. Claims

Date: 2026-11-01
Environment: Windows (PowerShell), Python 3.11.9, PyTorch 2.14.1+cpu

## 1. Executive Summary

A full static and execution audit was conducted across every module, script, test, and frontend asset in the VoltAgent repository.
- Baseline test suite execution: **135 passed, 14 xfailed, 1 skipped** (150 total tests collected). The single initial test failure (`test_late_position_number_is_beyond_the_embedder_window`) was caused by test-execution order requiring a pre-cached tokenizer; once cached, it passes deterministically.
- All 14 `xfail` markers represent documented failure reproduction tests in `tests/test_failure_repros.py`, `tests/test_api_contract.py`, `tests/test_ingestion_repros.py`, and `tests/test_verifier_repros.py`.

---

## 2. Component Status Matrix

| Component | Status | Evidence / Test Details | Known Deficiencies & Security/Safety Gaps |
| :--- | :--- | :--- | :--- |
| **Query Agent** (`voltagent/agents/query_agent.py`) | **Broken / Unsafe** | `test_reformulation_that_drops_error_code_and_model_is_not_used` reproduces critical token drop (XFAIL). | Language detection via `langdetect` misclassifies Hinglish. If LLM reformulation drops fault codes or models (e.g. E203 on DC-60 -> "charger fault"), rewrite is returned unchecked. |
| **Retriever: ES BM25 Leg** (`voltagent/retrieval/sparse_es.py`) | **Broken / Fragile** | `test_dependency_down_returns_explicit_degraded_response_not_500` (XFAIL). | Standard analyzer has no Devanagari support. Unreachable Elasticsearch stalls on connection retries and raises unhandled `ConnectionError`, crashing the API with 500. `rank-bm25` is listed in requirements.txt but never wired. |
| **Retriever: Qdrant Dense Leg** (`voltagent/retrieval/dense_qdrant.py`) | **Working but Flawed** | `test_embedder_window.py` controls pass; F-022 cases XFAIL. | Embedder window is 128 wordpieces (`paraphrase-multilingual-mpnet-base-v2`, 1.1GB), but chunker produces 350-token chunks; text beyond wordpiece 128 is invisible. No score floor (F-013). Uses deprecated `client.search`. |
| **Retriever: Hybrid & RRF** (`voltagent/retrieval/hybrid.py`, `fusion.py`) | **Partial (RRF works, Hybrid fragile)** | `tests/test_fusion.py` passes (4/4 tests). `test_one_retrieval_leg_down_degrades_to_the_other_leg` (XFAIL). | `HybridRetriever.retrieve()` has zero error isolation: an outage on either sparse or dense leg causes complete retrieval failure with unhandled exception. |
| **Generation Agent** (`voltagent/agents/generation_agent.py`) | **Partial / Unsafe** | `test_prompt_frames_retrieved_text_as_untrusted_data` (XFAIL). | Prompt pastes retrieved chunks raw without untrusted-data boundaries. `is_insufficient` marker check looks only for English string; Hindi responses cannot trigger it properly. No context cap. |
| **Verifier Agent** (`voltagent/agents/verifier_agent.py`) | **Broken / Unsafe** | `test_refusal_is_not_reported_as_verified_answer` (XFAIL), `test_citation_to_unrelated_chunk_is_not_verified` (XFAIL). | **Critical safety hole**: LLM refusal (`is_insufficient=True`) returns `verified=True, confidence=1.0`. Only checks first cited chunk (`refs[0]`) for semantic similarity. Cosine similarity alone cannot detect negation flips or numeric errors. |
| **LangGraph Orchestrator** (`voltagent/agents/graph.py`) | **Broken / Incomplete** | Code review; cache bypass tests. | Dead code: `_node_check_cache` (lines 39-44) is completely unused. Cache hit bypasses `_node_build_response`, dropping telemetry (`trace.finalize` never runs). Uncaught exceptions crash pipeline without returning Outcome C. Response shape violates `SAFETY_CONTRACT.md`. |
| **Response Cache** (`voltagent/cache.py`) | **Partial / Fragile** | `tests/test_cache.py` (6 passed). | Keyed on LLM reformulated query (paraphrases miss cache). Query normalizer fails on whitespace variations (`E-101` vs `E 101`). No corpus version hash. Redis connection failure raises unhandled exception. |
| **FastAPI Service** (`voltagent/api/main.py`) | **Partial / Insecure** | `test_api_contract.py` (XFAIL). | Wide-open CORS (`allow_origins=["*"]`). `/health` returns static `{"status": "ok"}` without checking backend health; no `/ready` endpoint. `/query/speech` returns audio only without metadata. No payload length limits. |
| **Voice / TTS** (`voltagent/voice/tts.py`) | **Stubbed / Fragile** | Code review. | Uses `gTTS`, requiring external network calls to Google Translate's unofficial endpoint. Fails in air-gapped or sandboxed environments. |
| **Frontend** (`frontend/app.js`, `index.html`) | **Partial** | Code review. | Hardcoded `API_BASE = "http://localhost:8000"`. Relies on browser-specific Web Speech API (`SpeechRecognition`, `speechSynthesis`). No configurable backend URL. |
| **Insights & Feedback** (`voltagent/insights/`) | **Present / Split** | `tests/test_feedback_loop.py` passed (5/5). | Batch Spark jobs exist in `spark_jobs/` and `streaming/`. `pyspark`, `pandas`, `pyarrow` are in `requirements.txt` instead of `requirements-insights.txt`. |
| **CLI Scripts** (`scripts/*.py`) | **Broken direct execution** | `python scripts/ingest.py --help` fails with `ModuleNotFoundError: No module named 'voltagent'`. | Scripts do not self-bootstrap `sys.path` when executed directly via CLI from repo root. |
| **Test Suite** (`tests/`) | **Working Harness** | 150 tests collected, 135 passing, 14 xfailed, 1 skipped. | Tests accurately identify known issues via strict xfail markers. |

---

## 3. Investigation of Known Suspects

1. **Dead `_node_check_cache` in `graph.py`**:
   - Confirmed dead code. The graph defines `_node_check_cache` at line 39, but `build_graph()` registers `_node_cache_lookup` instead.
2. **Cache key uses reformulated query**:
   - Confirmed. Key is computed from `qr.reformulated_query`. Because LLM rewrites vary based on slight prompt perturbations or stochasticity, paraphrases of identical fault codes miss the cache.
3. **Hindi handling in the verifier**:
   - The embedder (`paraphrase-multilingual-mpnet-base-v2`) supports Hindi text embeddings, but threshold calibration is not language-specific. Hindi claims evaluated against English source passages score lower than English-to-English pairs.
4. **`is_insufficient` returns `verified=True, confidence=1.0`**:
   - Confirmed severe vulnerability. Line 81 of `verifier_agent.py` explicitly returns `VerificationResult(verified=True, confidence=1.0, fallback=False)` when `generation.is_insufficient` is true. An LLM can completely dodge verification by declining to answer.
5. **`/query/speech` returns audio only**:
   - Confirmed. Returns `Response(content=audio_bytes, media_type="audio/mpeg")` without JSON response metadata, citations, query_id, or confidence.
6. **Wide-open CORS**:
   - Confirmed. `app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)` allows any origin.
7. **Elasticsearch failure behaviour**:
   - Confirmed. Default ES client has no fast fail or timeout; connection failure hangs on retries and propagates unhandled `ConnectionError`. No graceful degradation to dense-only or to the `rank-bm25` fallback.
8. **Scripts `sys.path` self-bootstrapping**:
   - `scripts/ingest.py` and `scripts/evaluate_retrieval.py` fail immediately with `ModuleNotFoundError: No module named 'voltagent'` when run as `python scripts/<script>.py`.
9. **`requirements.txt` dependency isolation**:
   - `requirements.txt` incorrectly bundles `pyspark==3.5.3`, `pandas==2.2.3`, and `pyarrow==17.0.0`, which are only needed for the offline Insights Spark layer.

