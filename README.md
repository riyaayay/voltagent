# VoltAgent

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.11.9-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/Orchestration-LangGraph-FF6F00?style=flat-square" alt="LangGraph" />
  <img src="https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Embeddings-Multilingual_MPNet_768d-7C3AED?style=flat-square" alt="Embeddings" />
  <img src="https://img.shields.io/badge/Recall%405-97.9%25-16A34A?style=flat-square" alt="Recall@5" />
  <img src="https://img.shields.io/badge/Verifier_Detection-90.0%25-blue?style=flat-square" alt="Verifier Detection" />
</p>

**A voice-first, verified RAG copilot for EV charging technicians servicing live electrical infrastructure.**

VoltAgent enables a technician standing in front of an open, de-energizing DC fast charger to ask diagnostic questions out loud—in English, Hindi, or Hinglish—and receive instant, spoken, citation-grounded guidance pulled directly from manufacturer engineering manuals, OCPP 2.0.1 specifications, and OSHA compliance codes.

---

## The Field Reality: 400 Volts, Arc-Flash Gloves, and a Blinking Fault Code

Picture a field technician on a rainy afternoon at a highway charging plaza.

They are kneeling in front of a malfunctioning 50 kW DC fast charger. Their hands are encased in thick Category III rubber voltage-insulating gloves. They are wearing an arc-flash face shield. Multimeter leads are clipped across a DC bus terminal carrying residual energy from high-capacitance bus capacitors.

```
       Technician in PPE                  Live Charger Interior
   ┌───────────────────────┐            ┌───────────────────────┐
   │ • Class III Gloves    │   Hands    │ • 400V - 1000V DC Bus │
   │ • Arc-Flash Visor     │   Busy     │ • Charged Capacitors  │
   │ • Multimeter in hand  │ ─────────▶ │ • 50A - 200A Contactors│
   │ • Rain / Loud Ambient │            │ • Blinking Error LED  │
   └───────────────────────┘            └───────────────────────┘
```

The charger displays a blinking red status LED, or an OCPP gateway drops error code `E208`.

In this moment:
- **They cannot browse a phone screen.** Trying to pinch, zoom, and scroll through a 480-page manufacturer PDF with insulated gloves in the rain is physically impossible.
- **They cannot guess.** If an AI system summarizes a manual and casually suggests *"Wait 10 seconds before opening the cabinet"* instead of the manufacturer-mandated *"Wait 10 minutes for capacitor discharge below 50V"*, the technician faces severe shock or electrocution.
- **Paraphrase is dangerous.** If a model mistakes `2.8 Nm` of terminal screw torque for `2.8 kg`, the resulting under-torqued lug causes thermal runaway and an electrical fire.

> **The Core Mission Principle**: On live high-voltage equipment, **a confident wrong answer is the absolute worst outcome**. An honest, immediate *"I cannot verify this specification from the manual; here is page 9 of the safety documentation"* is always safe.

---

## Why Standard RAG Fails on Hardware

Generic "chat with your documents" pipelines fail silently on technical hardware:

```
Typical RAG Pipeline:
User Query ──▶ Embedding ──▶ Vector DB ──▶ LLM Generation ──▶ Spoken Output (SILENT FAILURE)
```

1. **Topical Cosine Dilution**: A vector embedder measures *semantic topicality*, not *arithmetic truth*. A claim stating *"DC bus discharge takes 10 seconds"* and a source stating *"DC bus discharge takes 10 minutes"* have a **0.95+ cosine similarity** because they discuss the exact same technical topic. Bi-encoders cannot tell them apart.
2. **The Table Dilution Problem**: Technical manuals arrange error codes and torque values in dense multi-row tables. When an entire table is retrieved as one chunk, an LLM hallucinating a value that belongs to row 3 will match the topical vector of the table, passing ordinary similarity checks.
3. **The Lexical / Semantic Gap in Mixed Languages**: Technicians often speak colloquially (*"Pulsar Plus me yellow light ka kya matlab hai?"*) or in pure Hindi (*"डीसी बस कैपेसिटर को डिस्चार्ज होने में कितना समय लगता है?"*). Lexical BM25 search achieves **0.0% recall** on Devanagari against English engineering manuals, while naive machine translation drops specialized electrical fault codes.

---

## The Safety Contract: Strictly Typed Outcomes

VoltAgent rejects unstructured conversational text. Every incoming request must terminate in exactly **one typed outcome** defined in [`docs/SAFETY_CONTRACT.md`](docs/SAFETY_CONTRACT.md):

| Outcome Code | Outcome Name | Required Payload & System Guarantee |
| :---: | :--- | :--- |
| **`A`** | **Verified Answer** | Every critical numeric value and entity exactly matches cited source chunks. Semantic support $\ge 0.55$. Spoken in user's language with clickable PDF page citations. |
| **`B1`** | **Low Confidence Fallback** | Claim failed verification. The model **refuses to speak a guess**; emits a fixed safety line (*"I cannot verify this guidance"*) and renders the raw retrieved manual chunk on screen. |
| **`B2`** | **Source Conflict** | Contradictory values found across revisions (e.g. Manual v1 vs v2). Displays both citations side-by-side; refuses to pick one. |
| **`B3`** | **Ambiguous Query** | Query omits charger model or firmware revision. Speaks a clarifying question; offers no procedural advice until clarified. |
| **`B4`** | **Declined / No Support** | LLM refuses or retrieval scores fall below floor. Shows nearest docs; never reported as verified. |
| **`C`** | **Degraded / Outage** | External dependency failure (LLM quota, network timeout). Informs technician explicitly of which stage degraded; advises following site lock-out/tag-out (LOTO) protocols. |

---

## System Architecture

VoltAgent is orchestrated as a state machine in **LangGraph**, executing linear error-isolated nodes with deterministic safety verification:

```
 [ TECHNICIAN ]
       │
       │ (1) Hands-Free Audio Input (English / Hindi / Hinglish)
       ▼
 [ Web Speech API ] ──▶ Browser mic-to-text via Chrome/Edge (Zero client install)
       │
       │ (2) Raw Transcript (e.g. "E 101 fault code meaning")
       ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 1. QUERY AGENT (voltagent/agents/query_agent.py)                       │
 │    • Language Detection: Unicode script scanner + langdetect           │
 │    • Error Normalization: Normalizes spoken "E 101" / "ई-१०१" ──▶ E101 │
 │    • Critical Token Invariant: If rewriter drops error code, RESTORE!   │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 2. RESPONSE CACHE (voltagent/cache.py)                                 │
 │    • Cache Key: SHA-256(normalized_query + lang + corpus_version_hash) │
 │    • Auto-Invalidation: Re-ingesting a new PDF changes hash fleetwide │
 └───────────────────┬────────────────────────────────┬───────────────────┘
                     │ [CACHE HIT: Outcome A]         │ [CACHE MISS]
                     ▼                                ▼
              Instant Return           ┌──────────────────────────────────┐
               (0ms, $0 LLM)           │ 3. HYBRID RETRIEVAL (hybrid.py)  │
                                       └──────────────┬───────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       │                                                             │
                       ▼                                                             ▼
        ┌─────────────────────────────┐                               ┌─────────────────────────────┐
        │ Sparse Leg: BM25            │                               │ Dense Leg: Multilingual     │
        │ • Exact token match         │                               │ • mpnet-base-v2 (768-dim)   │
        │ • OCPP message names        │                               │ • Devanagari ──▶ English    │
        │ • 100% recall on codes      │                               │ • 85.7% cross-lingual recall│
        └──────────────┬──────────────┘                               └──────────────┬──────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
                                                      ▼
                       ┌─────────────────────────────────────────────────────────────┐
                       │ 4. RECIPROCAL RANK FUSION (RRF, k=60) (fusion.py)           │
                       │    Score(d) = Σ [ 1 / (60 + rank_i(d)) ]                    │
                       │    Merged candidate pool ──▶ Slices Top-6 Fused Chunks       │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
                                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────────┐
 │ 5. GROUNDED GENERATION AGENT (voltagent/agents/generation_agent.py)                      │
 │    • Context Isolation: Retrieved chunks wrapped in <UNTRUSTED_DOCUMENT_DATA> tags       │
 │    • Anti-Prompt-Injection: System refuses procedural commands found inside raw manuals  │
 │    • Citation Enforcement: LLM (Gemini 2.5 Flash / GPT-4o) appends bracket citations [1]│
 └────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────────┐
 │ 6. DUAL-LAYER VERIFIER AGENT (voltagent/agents/verifier_agent.py)                        │
 │    • Sentence Splitter: Preserves trailing citation anchors [1] (F-020 fix)              │
 │    • Layer 1: Deterministic Critical-Value Gate (numeric_gate.py)                        │
 │               Regex extracts: Volts, Amps, delays, torque (Nm), error codes, models      │
 │               Normalizes Devanagari numerals (३० ──▶ 30) & Hindi units (किलोवाट ──▶ kW)   │
 │               Zero tolerance: If claim has '5 min' and chunk has '10 min' ──▶ REJECT!    │
 │    • Layer 2: Negation Conflict Detector                                                 │
 │               Flags polarity flips: 'will charge' vs 'will not charge'                   │
 │    • Layer 3: Multilingual Semantic Cosine Scoring                                       │
 │               Computes cosine similarity against source text; threshold >= 0.55          │
 │    • Layer 4: Subpassage Anti-Dilution Windowing                                         │
 │               Extracts exact definition sentence for error codes; removes boilerplate    │
 └────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                              │
                                              ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────────┐
 │ 7. RESPONSE BUILDER & SAFETY COMPILER (voltagent/agents/graph.py)                        │
 │    • Outcome A : High confidence verified answer ──▶ Cache write + Browser TTS Readback  │
 │    • Outcome B1: Low confidence ──▶ Speak fallback line + display raw source PDF chunk   │
 │    • Outcome C : Degraded dependency ──▶ Identify failing node; advise safety procedure  │
 └──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## The Dual-Layer Verifier: Why Embeddings Alone Fail

The core architectural innovation of VoltAgent is the **decoupling of factual verification from the generative LLM**.

Many teams use *"LLM-as-a-judge"* (prompting an LLM to critique its own output). This is slow, doubles API token costs, and suffers from the exact same hallucination patterns. Other teams rely on bi-encoder cosine similarity alone, which fails on critical electrical numbers.

```
Why VoltAgent uses a Dual-Layer Verifier:

         Claim: "Wait 5 minutes before opening enclosure."
  Cited Source: "Wait 10 minutes before opening enclosure."
                             │
                             ├─────────────────────────────────────────┐
                             ▼                                         ▼
                 [ Semantic Bi-Encoder ]                     [ Deterministic Gate ]
             paraphrase-multilingual-mpnet                     numeric_gate.py
                             │                                         │
                    Cosine Score: 0.654                         Regex Extraction:
                 (Passes 0.55 Threshold!)                     Claim  = "5 min"
                             │                                Source = "10 min"
                             ▼                                         │
                  FAILED TO CATCH BUG!                                 ▼
                                                            VALUE MISMATCH: '5 min'
                                                            IMMEDIATE REJECTION (B1)
```

### The Verifier's 4 Internal Defense Layers:
1. **Citation Integrity**: Validates that every factual sentence contains a citation bracket and that the cited chunk ID exists in the retrieved set.
2. **Deterministic Critical-Value Gate (`numeric_gate.py`)**: A zero-LLM, regex-driven exact parser that checks:
   - **Units & Magnitudes**: `V`, `kV`, `A`, `mA`, `kW`, `kWh`, `s`, `ms`, `min`, `h`, `Nm`, `ft-lb`, `m`, `mm`, `cm`, `kg`, `psi`.
   - **Unit Invariance**: Normalizes representations (`min` = `minute` = `मिनट`), but enforces magnitude boundaries (`mA != A`, `ms != s`, `kW != kWh`).
   - **Devanagari Digits**: Translates Devanagari numerals (`०१२३४५६७८९` $\to$ `0123456789`).
   - **Exact Code Matching**: Normalizes `E-101`, `E101`, and `E 101` as identical, while rejecting `E-014` vs `E-0140`.
3. **Deterministic Negation Conflict Check**: Regex analyzes auxiliary verbs (`will`, `shall`, `can`, `must`) paired with negations (`not`, `never`, `cannot`), preventing dangerous polarity inversions.
4. **Code-Passage Anti-Dilution**: When verifying an error code definition (e.g. `E208`), strips boilerplate lead-in text (*"Fault Code E208 indicates"*) and compares the core semantic predicate against the specific line defining that code, eliminating whole-chunk table dilution.

---

## Measured Benchmark Results

All metrics are recorded from immutable execution outputs under [`results/`](results/) and documented in [`docs/RESULTS.md`](docs/RESULTS.md).

### 1. Hybrid Retrieval Benchmark (Evaluated on `gold.json`)
Evaluated across 48 ground-truth technical queries (33 English, 15 cross-lingual Hindi/Hinglish):

| Metric | Sparse Leg (BM25) | Dense Leg (Multilingual) | Fused (RRF $k=60$) | Impact of Fusion |
|---|:---:|:---:|:---:|---|
| **Overall Recall@5** | 85.4% | 91.7% | **97.9%** (47 / 48) | **+6.2%** over dense alone |
| **Mean Reciprocal Rank (MRR)** | 0.830 | 0.842 | **0.903** | Top-1 result in 41 of 48 queries |
| **Hindi Devanagari Recall@5** | 0.0% *(lexical gap)* | **85.7%** (6 / 7) | **85.7%** | Bridges cross-lingual barrier |
| **English Queries Recall@5** | **100.0%** (33 / 33) | 93.9% | **100.0%** | Perfect recall on technical codes |
| **Hinglish Queries Recall@5** | **100.0%** (8 / 8) | 87.5% | **100.0%** | Captures mixed-language syntax |

> **The F-022 Discovery**: The multilingual embedder truncates inputs after **128 wordpieces**. Initially, chunks were sliced at 350 tokens, causing dense retrieval to miss text buried deep in chunks. Re-chunking to **100 tokens** (with 20-token overlap) aligned the physical corpus with the embedder's receptive field, directly boosting Hindi Devanagari recall from **71.4% to 85.7%** and overall fused recall from **95.8% to 97.9%**.

### 2. Adversarial Verifier Generalization Benchmarks

```
   Frozen 10-Wrong Benchmark                  Unseen Held-Out 60-Case Benchmark
  (test_wrong_10.json, SHA dd0e...)               (heldout_60.json, SHA 0a75...)

   Wrong Flag Rate: 8 / 10 (80.0%)               Wrong Flag Rate: 27 / 30 (90.0%)
   False Flags:     0 / 20 (0.0%)                False Flags:     4 / 30 (13.3%)
```

- **Frozen 10-Wrong Set (`test_wrong_10.json`)**: 8 of 10 adversarial perturbations flagged as low-confidence fallback (0.0% false flags on 20 correct manual claims).
- **Held-Out 60-Case Generalization (`heldout_60.json`)**: On 60 unseen cases (30 wrong, 30 correct; 44 from real PDFs) authored without seeing verifier code, the verifier caught **27 of 30 wrong answers (90.0%)** with a **13.3% false-flag rate** on correct guidance.
- **Why 8 of 10, Not 10?**: The verifier missed W01 (status color swap) and W02 (shock current swap) because both true and false values appeared in adjacent rows of the same table chunk. We refused to artificially special-case color names in code; the architectural remedy is row-level table chunking or cross-encoder NLI reranking.

---

## The Real Hardware & Standards Corpus

VoltAgent indexes **711 total pages** across 5 real manufacturer manuals and standard specifications (710 extractable, 99.86% text ratio), chunked into **4,857 content-addressed chunks**:

```
 4,857 Indexed Chunks:
 ├── ocpp-2.0.1-spec.pdf (Open Charge Alliance, 481 pages, 3,602 chunks)
 │   └── Protocol state machines, TransactionEventRequest, requirement IDs, error codes
 ├── ocpp-2.0.1-appendices.pdf (Open Charge Alliance, 39 pages, 287 chunks)
 │   └── Components (AirCoolingSystem, Controller), variable tables, telemetry units
 ├── wallbox-pulsar-plus-install.pdf (Wallbox, 112 pages, 692 chunks)
 │   └── 16A-48A electrical ratings, NEMA 4 specs, wire gauges (AWG 6-10), mounting heights
 ├── ev-safety-compliance.pdf (OSHA Publication 3075, 71 pages, 234 chunks)
 │   └── 29 CFR 1910 standards, 50V live part guarding, LOTO rules, shock current thresholds
 ├── charger-error-codes.pdf (Wallbox NA, 8 pages, 35 chunks)
 │   └── Pulsar Plus LED halo colors (Green, Blue, Yellow, Red), breaker rating current limits
 └── data/raw/synthetic/* (VoltCo Test Corpus, 7 synthetic PDFs, 7 chunks)
     └── Near-duplicate codes (E203 vs E208), revision contradictions (v1 10 min vs v2 5 min)
```

*(Note: Real vendor PDFs are fetched directly from public sources and gitignored per redistribution policy).*

---

## 1-Command Local Setup & Run

VoltAgent runs locally on Windows 11 / PowerShell 5.1 with Python 3.11. No Docker or external cluster services are required for evaluation.

### 1. Automated Environment Setup
Open PowerShell as Administrator (or standard user) and run:
```powershell
.\scripts\setup.ps1
```
*Checks for Python 3.11, creates `.venv`, upgrades pip, installs `requirements.txt`, and copies `.env.example` $\to$ `.env`.*

### 2. Ingest the Document Corpus
```powershell
.\scripts\ingest.ps1
```
*Parses PDFs, slices 4,857 chunks (100 tokens, 20 overlap), and builds the local BM25 and dense embedding index cache under `data/index_cache/`.*

### 3. Launch the Copilot
```powershell
.\scripts\run.ps1
```
*Starts Uvicorn serving both the FastAPI REST endpoints and the browser voice interface at:*
👉 **`http://127.0.0.1:8000/`**

### 4. Run the Automated Demo Suite
In a second PowerShell window, run the canned 7-case benchmark runner:
```powershell
.\scripts\demo.ps1
```
*Fires English error code lookups, OSHA safety thresholds, cross-lingual Hindi queries, and adversarial safety bypass tests, logging outcomes to `results/demo_run.txt`.*

---

## Engineering Transparency Ledger

To ensure scientific honesty, here is the record of what runs live vs. in-process fallback:

| Component | Architecture Role | Execution Engine in Benchmarks | Credential / Service Used |
|---|---|---|---|
| **Sparse Retrieval** | Lexical Search | In-process `RankBM25Retriever` (`rank-bm25`) | Local memory; zero external services |
| **Dense Retrieval** | Multilingual Search | In-process PyTorch exact cosine (`dense.pt`) | Local CPU Sentence-Transformers |
| **Generation** | Grounded Synthesis | Google Gemini API (`gemini-2.5-flash`) | Live `GEMINI_API_KEY` (with 429 exponential backoff) |
| **Verifier Agent** | Claim Verification | Deterministic `numeric_gate.py` + local CPU cosine | Zero LLM calls; 100% reproducible on CPU |
| **Elasticsearch & Qdrant**| Production Adapters | Fallback active; adapters implemented in code | Docker was not run on local Windows host |
| **Hindi Lexicon** | Devanagari Normalization| Transliterated mapping in `numeric_gate.py` | Explicitly noted as unreviewed by native speaker |

---

## Repository Structure

```
voltagent-main/
├── voltagent/                  # Core Python package
│   ├── agents/                 # LangGraph orchestration & verification
│   │   ├── graph.py            # StateGraph compilation & typed outcome builder
│   │   ├── query_agent.py      # Language detection & critical token preservation
│   │   ├── generation_agent.py # Untrusted context tagging & citation prompt
│   │   ├── verifier_agent.py   # Multi-layer claim verification & support scoring
│   │   └── numeric_gate.py     # Deterministic regex parser for numbers & units
│   ├── ingestion/              # PDF loading, header stripping, token chunking
│   ├── retrieval/              # Sparse BM25, dense Qdrant, RRF fusion, hybrid search
│   ├── insights/               # PySpark nightly documentation gap detector
│   ├── voice/                  # gTTS audio synthesis fallback
│   ├── cache.py                # Response caching with corpus version invalidation
│   ├── config.py               # Pydantic env settings
│   └── llm.py                  # Gemini, OpenAI, and FakeLLM client abstractions
├── data/
│   ├── raw/real/               # 5 real vendor & safety manuals (711 pages)
│   ├── raw/synthetic/          # 7 synthetic edge-case PDFs + FACTS.json
│   └── eval/                   # gold.json, dev.json, test_wrong_10.json, heldout_60.json
├── frontend/                   # Web Speech API browser UI (index.html, app.js, styles.css)
├── scripts/                    # setup.ps1, ingest.ps1, run.ps1, demo.ps1, evaluation scripts
├── results/                    # Immutable benchmark results, JSONs, and test transcripts
└── docs/                       # SAFETY_CONTRACT.md, RESULTS.md, CORPUS.md, FAILURES.md
```

---

## License & Safety Notice

This codebase is licensed under the Apache 2.0 License. Real vendor manuals cited herein remain the intellectual property of their respective publishers (Open Charge Alliance, Wallbox, and U.S. Department of Labor OSHA) and are not redistributed. 

**Safety Warning**: VoltAgent is a field assistance prototype. Technicians must always consult physical lockout/tagout (LOTO) site procedures and verify equipment de-energization using certified Category III/IV multimeters before touching live electrical components.
