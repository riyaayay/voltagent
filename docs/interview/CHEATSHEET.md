# VoltAgent — 1-Page Interview Cheatsheet
*Read this in the elevator. Keep every claim anchored in repository evidence.*

---

## 1. The 30-Second Pitch
> "VoltAgent is a voice-first, bilingual copilot for EV charger field technicians working on live high-voltage equipment. Instead of trusting fluent LLM answers that might hallucinate a lethal torque or voltage specification, VoltAgent implements a dual-layer Verifier Agent that checks every sentence against retrieved manufacturer manuals using deterministic regex gates and multilingual cosine similarity. On a frozen held-out benchmark of 60 cases across real vendor manuals, it flags 90.0% of incorrect technical answers with a 13.3% false-flag rate on correct guidance."
<small>`docs/RESULTS.md:7-24`, `docs/SAFETY_CONTRACT.md:6-22`, `results/verifier_eval_heldout_60.json`</small>

---

## 2. The 3-Minute Pitch
1. **The Operational Problem**: Field technicians work with both hands on 400V/1000V DC chargers wearing Category III/IV PPE. Opening a 500-page PDF on a greasy phone screen is impossible, but standard conversational AI fails silently—paraphrasing a 50 ms delay into 500 ms or confusing 2.8 Nm of torque with 2.8 kg. A confident wrong answer is hazardous.
2. **The Architecture**:
   - **Voice In**: Browser Web Speech API (`SpeechRecognition`) captures English or Hindi (`hi-IN`).
   - **Query Reformulation**: Normalizes spoken error codes (e.g., "E 101", "ई-१०१" $\to$ "E101") while guaranteeing critical tokens are never lost.
   - **Hybrid Retrieval**: In-process BM25 lexical search combined with multilingual dense embeddings (`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`) via Reciprocal Rank Fusion ($k=60$).
   - **Strict Grounding**: Gemini 2.5 Flash / OpenAI synthesizes answers bounded by `<UNTRUSTED_DOCUMENT_DATA>` tags.
   - **Dual-Layer Verifier**: Deterministic numeric/unit/entity gate checks full chunk text for exact critical values, followed by per-sentence embedding cosine support scoring ($\ge 0.55$).
   - **Typed Outcome**: Returns Outcome `A` (Verified), `B1-B4` (Conservative Fallback with raw source chunk), or `C` (Degraded/Error).
3. **The Proof**: 97.9% fused Recall@5 across 48 ground-truth queries, 85.7% Hindi cross-lingual recall (where lexical search scored 0%), and 27/30 wrong answers flagged on unseen held-out validation.
<small>`docs/SAFETY_CONTRACT.md:14-22`, `voltagent/agents/graph.py:64-118`, `results/retrieval_eval_after_f022.json`</small>

---

## 3. The 8 Numbers to Memorize (Exact Repository Sources)

| # | Metric | Value | Exact Repo Source |
|---|---|---|---|
| **1** | **Overall Retrieval Recall@5** (Post F-022) | **97.9%** (47 / 48 queries) | `results/retrieval_eval_after_f022.json` (line 64 in `docs/RESULTS.md`) |
| **2** | **Fused Retrieval MRR** (Mean Reciprocal Rank) | **0.903** (Top-1 in 41 / 48) | `results/retrieval_eval_after_f022.json` (line 64 in `docs/RESULTS.md`) |
| **3** | **Hindi Cross-Lingual Recall@5** (Devanagari $\to$ English) | **85.7%** (6 / 7 queries, BM25 = 0.0%) | `results/retrieval_eval_after_f022.json` (line 67 in `docs/RESULTS.md`) |
| **4** | **Frozen 10-Wrong Benchmark Flag Rate** | **8 / 10 (80.0%)** flagged | `results/verifier_eval_frozen.txt:85` |
| **5** | **Frozen Correct Benchmark False-Flag Rate** | **0 / 20 (0.0%)** false flags | `results/verifier_eval_frozen.txt:88` |
| **6** | **Held-Out 60-Case Generalization Flag Rate** | **27 / 30 (90.0%)** flagged | `results/verifier_eval_heldout_60.json` (line 110 in `docs/RESULTS.md`) |
| **7** | **Held-Out 60-Case False-Flag Rate** | **4 / 30 (13.3%)** false flags (all on real PDFs) | `results/verifier_eval_heldout_60.json` (line 111 in `docs/RESULTS.md`) |
| **8** | **Corpus Page Scale & Chunk Count** | **711 pages** (710 extractable, 99.86%), **4,857 chunks** | `docs/CORPUS.md:5-7`, `results/clean_clone_run.txt:65` |

---

## 4. The 5 Limitations to Volunteer (Before They Ask)

1. **Dockerized Backends Were Evaluated via In-Process Fallbacks**: Full adapters for Elasticsearch 8.15.1 and Qdrant v1.11.3 are implemented (`voltagent/retrieval/sparse_es.py`, `dense_qdrant.py`), but all reported metrics were generated on local Windows CPU using `rank-bm25` and PyTorch exact cosine retrieval because Docker was not installed on the dev machine.
   *What to say*: "We built production adapters for Elasticsearch and Qdrant, but our benchmark numbers reflect zero-dependency in-process execution."
2. **Hindi Lexicon is Unreviewed by a Native Speaker**: The Devanagari numerals and Hindi technical unit mappings in `numeric_gate.py` and fallback strings in `SAFETY_CONTRACT.md` were authored mechanically and are explicitly commented as unreviewed by a native speaker.
   *What to say*: "The cross-lingual embedding retrieval works mathematically, but before field deployment in India, the Hindi terminology needs review by a native electrical technician."
3. **Multi-Row Table Dilution (Why 8/10, not 10/10)**: The verifier missed W01 (status LED color swap) and W02 (physiological shock current swap) because both true and false values existed within the same table chunk, allowing cosine similarity (>0.70) and regex presence to pass.
   *What to say*: "Our verifier operates at chunk granularity. When a table contains multiple rows with adjacent values, whole-chunk embeddings dilute. The fix is subpassage or row-level windowing."
4. **End-to-End Latency Percentiles are Not in Repo**: Individual verifier and retrieval latencies are measured (e.g., verifier takes 180–360 ms per query), but end-to-end network latencies over live Gemini API calls across 62 queries are not stored in a persistent benchmark table in the repo.
   *What to say*: "The local inference loop is sub-second, but live cloud LLM calls depend on external API latency; caching Outcome A mitigates this for frequent field queries."
5. **Browser Mic Requires Chrome/Edge**: The frontend relies on the Web Speech API (`webkitSpeechRecognition`), which works on `localhost` or HTTPS in Chromium browsers, but has partial/no support in Safari and Firefox.
   *What to say*: "For field deployment, we treat Web Speech API as a thin prototype interface; in production, technicians would use a dedicated mobile SDK."

---

## 5. The 5 Questions to Ask the Interviewer

1. *"How does your engineering team currently guard against hallucinations when LLMs synthesize electrical specs from vendor manuals—do you rely on prompt constraints, cross-encoders, or deterministic parsing?"*
2. *"In ChargePoint's error telemetry, what is the split between exact error codes and ambiguous symptoms—and how do you evaluate hybrid search recall for vague symptoms?"*
3. *"How do you handle firmware revision skew in the field when two chargers sharing a model name have contradictory diagnostic procedures?"*
4. *"What is your p95 latency budget for field voice queries over LTE, and do you stream audio to an edge server or do on-device wake-word detection?"*
5. *"For cross-lingual field support, do you translate queries upstream into English or embed directly into a shared multilingual vector space?"*

