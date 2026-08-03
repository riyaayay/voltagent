# VoltAgent

**Voice-first, verified RAG copilot for EV charging field technicians.**

VoltAgent lets a technician standing in front of a broken charger ask a question
out loud — in Hindi or English — and get back a spoken, *source-grounded* answer
pulled from OCPP protocol specs, hardware error-code manuals, and safety
compliance documents. A dedicated verifier agent checks every generated claim
against the retrieved source chunks before anything is spoken back; if it can't
verify the answer, it says so and surfaces the raw document instead of guessing.

This is not a "chat with your PDFs" demo. It assumes hands-full, non-desk,
possibly non-native-English field conditions, and it is built to fail loudly
(low-confidence fallback) instead of hallucinating a fix for a live electrical
system.

## Why it's built this way

| Problem with typical RAG demos | VoltAgent's answer |
|---|---|
| Assumes a desk and two free hands | Voice in, voice out (Web Speech API) |
| Assumes English fluency | Hindi/English query + response, language detected per-turn |
| Single retriever → generator → done | Retrieve → Generate → **Verify** → speak |
| No way to know if the answer is trustworthy | Verifier agent scores claim-to-source support; low-confidence answers fall back to "here's the raw doc" instead of a spoken guess |
| Re-answers identical fault codes from scratch every time | Cache layer keyed on normalized query + language |
| Black-box retrieval | Every response logged with retrieval scores, fusion ranks, and verifier confidence |

## Architecture

```
                         ┌────────────────────────────┐
  Technician (mic) ───▶  │  Frontend (Web Speech API)  │
                         │  frontend/index.html + app.js│
                         └──────────────┬──────────────┘
                                        │ POST /query  {text, lang}
                                        ▼
                         ┌────────────────────────────┐
                         │   FastAPI (voltagent/api)   │
                         └──────────────┬──────────────┘
                                        ▼
                         ┌────────────────────────────┐
                         │   LangGraph orchestration    │
                         │   (voltagent/agents/graph.py)│
                         │                              │
                         │  1. QueryAgent               │
                         │     - reformulate query      │
                         │     - detect language        │
                         │                              │
                         │  2. HybridRetriever           │
                         │     - Elasticsearch (BM25)    │
                         │     - Qdrant (dense/ST embed) │
                         │     - Reciprocal Rank Fusion  │
                         │                              │
                         │  3. GenerationAgent            │
                         │     - grounded prompt          │
                         │     - forced chunk citations    │
                         │                              │
                         │  4. VerifierAgent               │
                         │     - claim vs. source support   │
                         │     - confidence score            │
                         │     - fallback to raw doc if low  │
                         └──────────────┬──────────────┘
                                        ▼
                         ┌────────────────────────────┐
                         │  Cache (voltagent/cache.py)  │
                         │  LRU in-proc, Redis-ready     │
                         └──────────────┬──────────────┘
                                        ▼
                         ┌────────────────────────────┐
                         │  TTS (voltagent/voice/tts.py)│
                         │  → spoken answer, technician's│
                         │    language                   │
                         └────────────────────────────┘

  Every hop logs structured events → voltagent/logging_utils.py
  → observability/ (JSONL logs: retrieval scores, fusion ranks,
    verifier confidence, cache hit/miss, latency per stage)
```

## What each JD requirement maps to

| Requirement | Where |
|---|---|
| RAG architecture | `voltagent/agents/graph.py` (full retrieve → augment → generate loop) |
| LangChain/LangGraph | `voltagent/agents/graph.py` |
| Elasticsearch hybrid search | `voltagent/retrieval/sparse_es.py` + `fusion.py` |
| Vector databases | `voltagent/retrieval/dense_qdrant.py` |
| Agent-based AI systems | `voltagent/agents/verifier_agent.py` — a second agent that critiques the first, not single-shot generation |
| Low-latency / caching | `voltagent/cache.py` |
| Observability | `voltagent/logging_utils.py`, `scripts/evaluate_retrieval.py` |
| Prompt engineering | `voltagent/agents/generation_agent.py` (grounded, citation-forcing prompts) |

## Build stages (this is a multi-weekend project, by design)

1. **Stage 1 — core RAG loop.** Chunk OCPP/error-code PDFs, index into Qdrant,
   wire a single Gemini/OpenAI call for generation. Working demo, no fusion yet.
2. **Stage 2 — hybrid search.** Stand up Elasticsearch, add the BM25 leg,
   fuse with the dense leg via reciprocal rank fusion, move orchestration into
   LangGraph.
3. **Stage 3 — verification, caching, observability.** Add the verifier agent,
   the cache layer, and structured per-query logging.
4. **Stretch — voice.** Wire in Web Speech API (`frontend/`) for mic input and
   spoken output, add Hindi language routing end-to-end.

## Repo layout

```
voltagent/
├── voltagent/                  # Python package
│   ├── config.py                # env-driven settings
│   ├── logging_utils.py         # structured observability logging
│   ├── cache.py                 # LRU + Redis-compatible cache
│   ├── ingestion/
│   │   ├── loaders.py            # PDF loading
│   │   └── chunking.py           # chunking strategy
│   ├── retrieval/
│   │   ├── sparse_es.py          # Elasticsearch BM25 retriever
│   │   ├── dense_qdrant.py       # Qdrant dense retriever
│   │   └── fusion.py             # reciprocal rank fusion
│   ├── agents/
│   │   ├── query_agent.py        # reformulation + language detection
│   │   ├── generation_agent.py   # grounded generation with citations
│   │   ├── verifier_agent.py     # hallucination check / confidence
│   │   └── graph.py              # LangGraph wiring
│   ├── voice/
│   │   └── tts.py                # text-to-speech, language-routed
│   └── api/
│       └── main.py               # FastAPI app
├── scripts/
│   ├── ingest.py                 # end-to-end ingestion CLI
│   └── evaluate_retrieval.py     # recall@k / fusion eval harness
├── frontend/
│   ├── index.html                # mic capture + playback UI
│   ├── app.js                    # Web Speech API glue
│   └── styles.css
├── tests/
│   ├── test_fusion.py
│   ├── test_cache.py
│   └── test_verifier.py
├── data/raw/                     # drop source PDFs here
├── docker-compose.yml            # Elasticsearch + Qdrant, local dev
├── requirements.txt
└── .env.example
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your Gemini/OpenAI key
docker compose up -d   # starts Elasticsearch + Qdrant locally

# 1. Drop OCPP 2.0.1 spec + error-code PDFs into data/raw/
# 2. Ingest + index
python scripts/ingest.py --source data/raw

# 3. Run the API
uvicorn voltagent.api.main:app --reload --port 8000

# 4. Open frontend/index.html in a browser (served statically or via
#    `python -m http.server` from frontend/) and start talking.
```

## Data sources (public, no fabrication)

- OCPP 2.0.1 protocol specification (Open Charge Alliance, publicly downloadable)
- Publicly available EV charger hardware error-code manuals
- General EV safety compliance documentation

Place downloaded PDFs in `data/raw/` before running `scripts/ingest.py`.

## Honest limitations

- The verifier agent uses embedding-similarity + lightweight NLI-style scoring,
  not a fine-tuned factuality model — it catches unsupported claims and
  contradicted claims well, but it is not a formal proof of correctness.
- Elasticsearch and Qdrant are both required for the full hybrid path; Stage 1
  can run on Qdrant/Chroma alone if you want a faster first working demo.
- Hindi TTS/STT quality depends entirely on the browser's Web Speech API
  implementation — it's inconsistent across browsers, which is called out in
  `frontend/app.js`.
