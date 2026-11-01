# STATUS: audited reality vs README

Audit dates: 2026-10-22 (static read), 2026-10-23 (first execution).
**Executed so far:** venv + full install (Python 3.11.9), `import voltagent.api.main` (OK),
`pytest` (23 passed, 1 skipped, 1 xfailed in ~62 s), one TestClient `/query` with the fake LLM and ES down.
**Not executed yet:** docker compose (ES/Qdrant), ingest, real retrieval, Spark jobs, frontend.
Anything not listed above remains `unverified`. Per-module statuses below are still mostly from reading.

| Module | Code status | Tests | Known problems (from reading) |
|---|---|---|---|
| config.py | complete | none | `.env` empty; default provider Gemini, so any LLM call without a key fails. `LLM_PROVIDER=fake` now supported. |
| logging_utils.py | partial | none | Only `query_complete` carries the trace id and is written only at the end of `build_response`; an exception leaves no trail. Error-code regex `E\d{3}` only. |
| cache.py | partial | test_cache.py (6 tests, read) | No corpus version in key; `E-101`/`E101`/`E 101` differ; Redis errors uncaught; no stampede guard; keyed on the LLM-reformulated query. |
| ingestion/loaders.py | partial | none | pypdf only, no OCR; one bad PDF aborts the directory load; no revision/model/date metadata. |
| ingestion/chunking.py | partial | none | Fixed token window per page; ignores tables, columns, headers/footers, number/unit boundaries; chunk_id = doc:page:window so same filename + different content collides. |
| retrieval/sparse_es.py | partial | none | `standard` analyzer; no Devanagari handling; no error handling. |
| retrieval/dense_qdrant.py | partial | none | No score floor; deprecated `client.search`; no dimension/model check; no error handling. |
| retrieval/fusion.py | complete | test_fusion.py (not read) | `rrf_k or default` treats 0 as unset; no tie-break; no empty-leg flag. |
| retrieval/hybrid.py | partial | none | Either leg raising fails the request. |
| agents/query_agent.py | partial | none | Only en/hi; no critical-token invariant after reformulation. |
| agents/generation_agent.py | partial | none | Chunk text pasted raw into prompt; regex citations; no retry/parse handling; no context cap. |
| agents/verifier_agent.py | partial, **unsafe** | 5 tests, none touch scoring | V1-V4 below. |
| agents/graph.py | partial | none | No exception handling or timeouts; cache-hit path never finalizes the trace; `_node_check_cache` is dead code. |
| api/main.py | partial | none | No `lang`; `/health` constant; no length limit; CORS `*`. |
| llm.py | **now complete for tests** | test_fake_llm.py (new, not yet run) | Fake added; real clients still have no timeout/retry. |
| voice/tts.py, scripts/*, frontend/* | not read | | |
| insights/* | present | test_feedback_loop.py (not read) | Spark jobs only. `feedback_loop.py` is the only request-path piece and only tightens the threshold (+0.15, cap 0.95). |
| Makefile / pytest.ini / requirements-dev.txt | **new, untested** | | Written this session, never executed. |

## Dependency finding: pyspark
`pyspark` is imported only by `voltagent/insights/spark_jobs/*` and `voltagent/insights/streaming/*`. Nothing on the request path, the tests or the verifier imports it (`feedback_loop.py` imports only json/os/time/config). `pandas` is imported only by `insights/log_export.py`; `pyarrow` is only mentioned there. Proposal: move `pyspark`, `pandas`, `pyarrow` to `requirements-insights.txt`. `structlog` and `rank-bm25` are listed but unused (grep found no import). Awaiting your decision before editing `requirements.txt` (not on the write allowlist, so you may need to make that edit or allow it).

## Git / flatten finding
The flatten is already committed (`b58dde9 "1"`). `git ls-files` shows `voltagent/` (the package: config.py, agents/, api/, ...) at the repo root, so the inner package directory is **not** gone; `voltagent.api.main` should resolve from the repo root. The old status noise (`D voltagent/voltagent/...`) was a nested layout. This is by reading only: the import test has not run (needs Python).

## Real current stage
Stage 2 code with Stage 3 scaffolding. Under one stage from the README.

## README promises that aren't true yet
1. "Checks every generated claim": only cosine of a sentence vs its first cited chunk; no numbers, units, codes, models or negation.
2. "Fails loudly": no exception handling; dependency failure = 500, not outcome C.
3. `POST /query {text, lang}`: no `lang`.
4. "Logged with retrieval scores, fusion ranks": only counts and fused ids.
5. Cache "normalized": no corpus version, no code-format normalization.
6. "Hindi/English end to end": no Hinglish, no Devanagari analyzer.
7. `docs/SAFETY_CONTRACT.md`, `docs/ARCHITECTURE.md` referenced by AGENTS.md: were missing/empty, now written.

## Verifier findings (to reproduce in Phase 3)
- V1: refusal returns `verified=True, confidence=1.0` (verifier_agent.py:74-77); test_verifier.py:37 asserts it.
- V2: cosine vs 0.55 only; wrong number/model in an on-topic sentence likely passes.
- V3: only the first `[n]` per sentence is checked.
- V4: no negation check; no deterministic numeric/unit/code gate.
