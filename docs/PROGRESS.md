# PROGRESS: Implementation & Verification Status

## Phase 0: Audit & Foundation (COMPLETED)
- [x] Static audit of all modules, agents, API endpoints, and tests recorded in `docs/AUDIT.md`.
- [x] Contract formalized in `docs/SAFETY_CONTRACT.md`.
- [x] Script self-bootstrapping added to all entry points in `scripts/*.py`.
- [x] PySpark/pandas/pyarrow isolated from core runtime into `requirements-insights.txt`.
- [x] Windows import order hazard (F-021) guarded and documented in `tests/test_import_order.py`.

## Phase 1: Real & Synthetic Corpus + Ground Truth Evaluation Sets (COMPLETED)
- [x] Real PDF corpus inventory executed (`scripts/inventory_real_corpus.py`): 5 documents, 711 pages (99.86% digital text quality, zero unreadable scans) documented in `docs/CORPUS.md`.
- [x] Synthetic corpus generated with distinct "VoltCo" branding and mandatory footers (`SYNTHETIC TEST DOCUMENT`).
- [x] Gold evaluation dataset created: `data/eval/gold.json` (62 queries: 32 real-doc queries with verbatim evidence quotes, 15 Hindi/Hinglish cross-lingual with `needs_native_review: true`, 10 out-of-scope probes, 5 adversarial).
- [x] Automated quote validation script `scripts/validate_gold.py` verified 48/48 evidence quotes verbatim in source PDFs with zero query leakage into corpus.
- [x] Frozen benchmark evaluation sets generated and committed:
  - `data/eval/test_wrong_10.json`: 10 perturbed adversarial cases covering 10 distinct failure modes (7 from real PDFs).
  - `data/eval/test_correct.json`: 20 verified correct cases (14 from real PDFs).
  - `data/eval/dev.json`: 5 disjoint tuning cases.
- [x] Benchmark protocol and immutable SHA-256 integrity hashes recorded in `docs/EVAL_PROTOCOL.md` (Git commit `9f794ba`).

## Phase 2: Pipeline Hardening & Root-Cause Bug Fixes (COMPLETED)
- [x] **F-001 (Numeric/Unit Gate)**: Deterministic value checking for number+unit pairs, error codes, charger models, and OCPP message types in `voltagent/agents/numeric_gate.py`. 41 unit tests passing.
- [x] **F-002 (Refusal Handling)**: Model declines (`is_insufficient=True`) correctly classified as unverified fallback (Outcome B4) with confidence 0.0, never verified.
- [x] **F-003 (Citation Integrity)**: Verifier agent now checks every cited chunk for semantic support; unrelated chunks trigger failure.
- [x] **F-004 (Graceful Degradation)**: Unhandled errors and dependency failures caught in `graph.py` and returned as typed HTTP 200 Outcome C responses.
- [x] **F-005 (Retrieval Isolation)**: Hybrid retriever isolates sparse and dense legs so one leg failing allows the surviving leg to fulfill the request.
- [x] **F-006 (Query Reformulation Invariant)**: Added alphanumeric error code preservation check in `voltagent/agents/query_agent.py`.
- [x] **F-007 (Untrusted Data Framing)**: Retrieved chunk data wrapped in `<UNTRUSTED_DOCUMENT_DATA>` tags.
- [x] **F-008 & F-009 & F-010 (Cache Hardening)**: Error code normalization, corpus version hash inclusion, and graceful in-memory fallback on Redis failure.
- [x] **F-011 & F-012 & F-025 & F-026 (Ingestion Hardening)**: Per-file try/catch, content-addressed SHA-1 chunk IDs, PUA font filtering, and repeated header stripping.
- [x] Negation conflict detection implemented in `verifier_agent.py` to prevent negation flips (V4).

## Phase 3: Claim Verification & Packaging (COMPLETED)
- [x] Claim (A) LangGraph orchestration verified with passing API contract and pipeline tests.
- [x] Claim (B) Hybrid BM25 + Qdrant search with RRF served via hardened FastAPI service with in-process persistent fallbacks (`SPARSE_BACKEND=bm25`).
- [x] Claim (C) Evaluated on frozen benchmark: **8 / 10 (80.0%)** wrong cases flagged, **0 / 20 (0.0%)** false flags on correct cases, threshold 0.55. (Output: `results/verifier_eval_frozen.txt`).
- [x] Production multi-stage `Dockerfile` created with non-root security.
- [x] `docker-compose.yml` updated with `app`, `elasticsearch`, `qdrant`, and `redis`.
- [x] GitHub Actions CI workflow created (`.github/workflows/ci.yml`).
- [x] Observability log summarizer implemented in `scripts/summarize_logs.py`.
- [x] Complete test suite passing: 149 passed, 3 xfailed (documented hazards), 0 failed in 75.36s (`results/pytest_final.txt`).
