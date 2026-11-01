# VoltAgent- check

**Voice-first, verified RAG copilot for EV charging field technicians.**

VoltAgent lets a technician standing in front of a broken charger ask a question
out loud â€” in Hindi or English â€” and get back a spoken, *source-grounded* answer
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
| Single retriever â†’ generator â†’ done | Retrieve â†’ Generate â†’ **Verify** â†’ speak |
| No way to know if the answer is trustworthy | Verifier agent scores claim-to-source support; low-confidence answers fall back to "here's the raw doc" instead of a spoken guess |
| Re-answers identical fault codes from scratch every time | Cache layer keyed on normalized query + language |
| Black-box retrieval | Every response logged with retrieval scores, fusion ranks, and verifier confidence |

## Architecture

```
                         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  Technician (mic) â”€â”€â”€â–¶  â”‚  Frontend (Web Speech API)  â”‚
                         â”‚  frontend/index.html + app.jsâ”‚
                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â”‚ POST /query  {text, lang}
                                        â–¼
                         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                         â”‚   FastAPI (voltagent/api)   â”‚
                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â–¼
                         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                         â”‚   LangGraph orchestration    â”‚
                         â”‚   (voltagent/agents/graph.py)â”‚
                         â”‚                              â”‚
                         â”‚  1. QueryAgent               â”‚
                         â”‚     - reformulate query      â”‚
                         â”‚     - detect language        â”‚
                         â”‚                              â”‚
                         â”‚  2. HybridRetriever           â”‚
                         â”‚     - Elasticsearch (BM25)    â”‚
                         â”‚     - Qdrant (dense/ST embed) â”‚
                         â”‚     - Reciprocal Rank Fusion  â”‚
                         â”‚                              â”‚
                         â”‚  3. GenerationAgent            â”‚
                         â”‚     - grounded prompt          â”‚
                         â”‚     - forced chunk citations    â”‚
                         â”‚                              â”‚
                         â”‚  4. VerifierAgent               â”‚
                         â”‚     - claim vs. source support   â”‚
                         â”‚     - confidence score            â”‚
                         â”‚     - fallback to raw doc if low  â”‚
                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â–¼
                         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                         â”‚  Cache (voltagent/cache.py)  â”‚
                         â”‚  LRU in-proc, Redis-ready     â”‚
                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â–¼
                         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                         â”‚  TTS (voltagent/voice/tts.py)â”‚
                         â”‚  â†’ spoken answer, technician'sâ”‚
                         â”‚    language                   â”‚
                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

  Every hop logs structured events â†’ voltagent/logging_utils.py
  â†’ observability/ (JSONL logs: retrieval scores, fusion ranks,
    verifier confidence, cache hit/miss, latency per stage)
```

## Build stages (this is a multi-weekend project, by design)

1. **Stage 1 â€” core RAG loop.** Chunk OCPP/error-code PDFs, index into Qdrant,
   wire a single Gemini/OpenAI call for generation. Working demo, no fusion yet.
2. **Stage 2 â€” hybrid search.** Stand up Elasticsearch, add the BM25 leg,
   fuse with the dense leg via reciprocal rank fusion, move orchestration into
   LangGraph.
3. **Stage 3 â€” verification, caching, observability.** Add the verifier agent,
   the cache layer, and structured per-query logging.
4. **Stretch â€” voice.** Wire in Web Speech API (`frontend/`) for mic input and
   spoken output, add Hindi language routing end-to-end.

## Repo layout

```
voltagent/
â”œâ”€â”€ voltagent/                  # Python package
â”‚   â”œâ”€â”€ config.py                # env-driven settings
â”‚   â”œâ”€â”€ logging_utils.py         # structured observability logging
â”‚   â”œâ”€â”€ cache.py                 # LRU + Redis-compatible cache
â”‚   â”œâ”€â”€ ingestion/
â”‚   â”‚   â”œâ”€â”€ loaders.py            # PDF loading
â”‚   â”‚   â””â”€â”€ chunking.py           # chunking strategy
â”‚   â”œâ”€â”€ retrieval/
â”‚   â”‚   â”œâ”€â”€ sparse_es.py          # Elasticsearch BM25 retriever
â”‚   â”‚   â”œâ”€â”€ dense_qdrant.py       # Qdrant dense retriever
â”‚   â”‚   â””â”€â”€ fusion.py             # reciprocal rank fusion
â”‚   â”œâ”€â”€ agents/
â”‚   â”‚   â”œâ”€â”€ query_agent.py        # reformulation + language detection
â”‚   â”‚   â”œâ”€â”€ generation_agent.py   # grounded generation with citations
â”‚   â”‚   â”œâ”€â”€ verifier_agent.py     # hallucination check / confidence
â”‚   â”‚   â””â”€â”€ graph.py              # LangGraph wiring
â”‚   â”œâ”€â”€ voice/
â”‚   â”‚   â””â”€â”€ tts.py                # text-to-speech, language-routed
â”‚   â””â”€â”€ api/
â”‚       â””â”€â”€ main.py               # FastAPI app
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ ingest.py                 # end-to-end ingestion CLI
â”‚   â””â”€â”€ evaluate_retrieval.py     # recall@k / fusion eval harness
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ index.html                # mic capture + playback UI
â”‚   â”œâ”€â”€ app.js                    # Web Speech API glue
â”‚   â””â”€â”€ styles.css
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ test_fusion.py
â”‚   â”œâ”€â”€ test_cache.py
â”‚   â””â”€â”€ test_verifier.py
â”œâ”€â”€ data/raw/                     # drop source PDFs here
â”œâ”€â”€ docker-compose.yml            # Elasticsearch + Qdrant, local dev
â”œâ”€â”€ requirements.txt
â””â”€â”€ .env.example
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

- **OCPP 2.0.1 Part 2 - Specification Edition 2**: Open Charge Alliance (OCA), [https://www.openchargealliance.org/protocols/ocpp-201/](https://www.openchargealliance.org/protocols/ocpp-201/)
- **OCPP 2.0.1 Part 2 - Appendices v1.3**: Open Charge Alliance (OCA), [https://www.openchargealliance.org/protocols/ocpp-201/](https://www.openchargealliance.org/protocols/ocpp-201/)
- **Wallbox Pulsar Plus NA Quick Reference & Status Guide**: Wallbox, [https://support.wallbox.com/na/](https://support.wallbox.com/na/)
- **Wallbox Pulsar Plus Installation Guide**: Wallbox, [https://support.wallbox.com/](https://support.wallbox.com/)
- **OSHA 3075 Controlling Electrical Hazards & EV Safety Compliance**: Occupational Safety and Health Administration (OSHA), U.S. Department of Labor, [https://www.osha.gov/publications/osha3075](https://www.osha.gov/publications/osha3075)

Place downloaded PDFs in `data/raw/` or `data/raw/real/` before running `scripts/ingest.py`.

## Honest limitations

- The verifier agent uses embedding-similarity + lightweight NLI-style scoring,
  not a fine-tuned factuality model â€” it catches unsupported claims and
  contradicted claims well, but it is not a formal proof of correctness.
- Elasticsearch and Qdrant are both required for the full hybrid path; Stage 1
  can run on Qdrant/Chroma alone if you want a faster first working demo.
- Hindi TTS/STT quality depends entirely on the browser's Web Speech API
  implementation â€” it's inconsistent across browsers, which is called out in
  `frontend/app.js`.
