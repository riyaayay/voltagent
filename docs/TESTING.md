# Testing

Markers (declared in `pytest.ini`, `--strict-markers` is on): `unit`, `integration`, `e2e`, `chaos`, `live`, `slow`.

| Command | Runs |
|---|---|
| `make test` | everything except integration, live, slow |
| `make test-unit` / `test-integration` / `test-chaos` | one tier |
| `pytest -m live` | real LLM; skipped when no API key is set |

Conventions
- Seed: `tests/conftest.py::SEED = 1234`; use the `rng` fixture, never global `random`.
- LLM: use the `fake_llm` fixture (`FakeLLMClient`). Only the LLM is faked. ES/Qdrant tests use the real docker-compose services.
- API tests use FastAPI `TestClient` inside pytest, not a live server.

## Baseline metrics (as of 2026-10-23, Phase 0; NOT the Phase 2 baseline)
Test suite, run on Windows 11 / Python 3.11.9 with the real embedder, fake LLM, **no Docker**:
Last full run before the numeric gate: `67 passed, 1 skipped (live), 18 xfailed in about 145 s`.
Latest run (2026-10-23, excluding `test_verifier_repros.py` and `test_embedder_window.py`, which need the 1.1 GB embedder and cannot load while Docker is resident, F-027): `128 passed, 1 skipped, 9 xfailed in 113 s`. The `slow` marker covers corpus generation, the real embedder and fresh-interpreter imports; `make test` skips `slow`.
Integration tier: Docker is up-able again (F-018 resolved) but not yet exercised: no ingest or retrieval test has run; memory (F-027) limits running the embedder and the containers together on this machine.

| Metric | Value | Source |
|---|---|---|
| Embedder | paraphrase-multilingual-mpnet-base-v2, 768-d, window 128 wordpieces | probe |
| Verifier cosine, correct claim | 0.685 (threshold 0.55) | probe, n=1 |
| Verifier cosine, wrong number / wrong unit | 0.654 / 0.682 (both accepted) | probe, n=1 each |
| Verifier cosine, negated / unrelated | 0.502 / 0.414 (both rejected) | probe, n=1 each |
| Verifier cosine, Hindi correct / Hindi wrong number | 0.572 / 0.524 | probe, n=1 each |
| ES-down request latency (no timeout configured) | about 60 s then HTTP 500 | one run |
| Recall@k, MRR (BM25 / dense / fused) | not measured | |
| Citation validity, numeric fidelity | not measured | |
| Verifier precision/recall | not measured | |
| False-confidence rate (expected B/C but got A) | not measured | |
| False-abstention rate | not measured | |
| Abstention calibration / chosen threshold | not measured | |
| Per-stage latency p50/p95, cache hit rate | not measured | |
| ES / Qdrant startup | containers created, ES green and Qdrant answering about 50 s later (one run) |
| ES heap | 143 MB used of 537 MB max (idle, empty index) |
| Host memory with Docker up | 7.7 GB RAM total, 0.8 GB free, 89% load (F-027) | |

The single-example cosine rows are probes, not distributions.

## Known test problems
- `tests/test_cache.py::test_memory_cache_roundtrip` calls `monkeypatch.setenv("CACHE_BACKEND", ...)` but `settings` is built at import time, so the setenv has no effect. It passes only because memory is the default. (F-017)
- `tests/test_verifier.py::test_verifier_passes_through_insufficient_answers_as_verified` asserts behaviour that violates the safety contract (F-002). It must be changed deliberately, with the reason recorded, when F-002 is fixed.
- Pre-existing tests are now marked `unit` (module-level `pytestmark`). `test_threshold_override_is_capped` was tautological (F-019) and has been rewritten to call the real function.
- Strict xfail tests are known-bug reproductions (see FAILURES.md). When a bug is fixed its test XPASSes, strict mode fails the run, and the xfail marker must be removed deliberately.
