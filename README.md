---
title: VoltAgent Copilot
emoji: ⚡
colorFrom: blue
colorTo: yellow
sdk: gradio
app_file: app.py
pinned: false
python_version: 3.11
---

# VoltAgent

**Voice-first, verified RAG copilot for EV charging field technicians.**

VoltAgent lets a technician standing in front of a broken charger ask a question out loud — in Hindi or English — and get back a spoken, *source-grounded* answer pulled from OCPP protocol specs, hardware error-code manuals, and safety compliance documents. A dedicated verifier agent checks every generated claim against the retrieved source chunks before anything is spoken back; if it can't verify the answer, it says so and surfaces the raw document instead of guessing.

This is not a "chat with your PDFs" demo. It assumes hands-full, non-desk, possibly non-native-English field conditions, and it is built to fail loudly (low-confidence fallback) instead of hallucinating a fix for a live electrical system.

---

## Why It's Built This Way

| Problem with typical RAG demos | VoltAgent's answer |
|---|---|
| Assumes a desk and two free hands | Voice in, voice out (Web Speech API) |
| Assumes English fluency | Hindi/English query + response, language detected per-turn |
| Single retriever → generator → done | Retrieve → Generate → **Verify** → speak |
| No way to know if the answer is trustworthy | Verifier agent scores claim-to-source support; low-confidence answers fall back to "here's the raw doc" instead of a spoken guess |
| Re-answers identical fault codes from scratch every time | Cache layer keyed on normalized query + language |
| Black-box retrieval | Every response logged with retrieval scores, fusion ranks, and verifier confidence |

---

## Architecture

```
                         ┌─────────────────────────────┐
  Technician (mic) ─────▶│  Frontend (Web Speech API)  │
                         │  frontend/index.html + app.js│
                         └──────────────┬──────────────┘
                                        │ POST /query  {text, lang}
                                        ▼
                         ┌─────────────────────────────┐
                         │   FastAPI (voltagent/api)   │
                         └──────────────┬──────────────┘
                                        ▼
                         ┌─────────────────────────────┐
                         │   LangGraph orchestration   │
                         │   (voltagent/agents/graph.py)│
                         │                             │
                         │  1. QueryAgent              │
                         │     - reformulate query     │
                         │     - detect language       │
                         │                             │
                         │  2. HybridRetriever         │
                         │     - BM25 (sparse leg)     │
                         │     - Qdrant (dense leg)    │
                         │     - Reciprocal Rank Fusion│
                         │                             │
                         │  3. GenerationAgent         │
                         │     - grounded prompt       │
                         │     - forced chunk citations│
                         │                             │
                         │  4. VerifierAgent           │
                         │     - entity / numeric gate │
                         │     - semantic cosine score │
                         │     - fallback to raw doc   │
                         └──────────────┬──────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │  Cache (voltagent/cache.py) │
                         │  In-memory / Redis          │
                         └──────────────┬──────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │  TTS (voltagent/voice/tts.py│
                         │  → spoken audio playback    │
                         └─────────────────────────────┘

  Every hop logs structured events → voltagent/logging_utils.py
  → observability/ (JSONL logs: retrieval scores, fusion ranks,
    verifier confidence, cache hit/miss, latency per stage)
```

---

## Deployment & Hosting

VoltAgent supports zero-Docker hosting on **Hugging Face Spaces** (Free CPU tier) via the Gradio ASGI launcher.

### Hugging Face Space Configuration
- **SDK**: `gradio` (ASGI launcher for `app.py`)
- **Port**: `7860`
- **Retrieval Engine**: In-process BM25 (`rank-bm25`) + in-process PyTorch dense vector cosine search (`dense.pt`)
- **Space Settings > Variables and secrets**:
  - `GEMINI_API_KEY`: Google Gemini API key
  - `SPARSE_BACKEND`: `bm25` (default)
  - `CACHE_BACKEND`: `memory` (default)
  - `DAILY_LLM_CAP`: `200` (daily call budget)
  - `RATE_LIMIT_PER_MINUTE`: `20` (IP rate limiting)

For more deployment options (low-RAM VPS, Qdrant Cloud), see [DEPLOY.md](file:///d:/voltagent-main/DEPLOY.md).

---

## Local Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env   # fill in your GEMINI_API_KEY or OPENAI_API_KEY

# 4. Ingest documents (bundled demo corpus or real manuals)
python scripts/ingest.py --source data/raw/synthetic

# 5. Launch local application
python app.py
```

Open `http://localhost:7860` in Google Chrome or Edge.

---

## Data Sources (Public, No Fabrication)

- **OCPP 2.0.1 Part 2 - Specification Edition 2**: Open Charge Alliance (OCA), [https://www.openchargealliance.org/protocols/ocpp-201/](https://www.openchargealliance.org/protocols/ocpp-201/)
- **OCPP 2.0.1 Part 2 - Appendices v1.3**: Open Charge Alliance (OCA), [https://www.openchargealliance.org/protocols/ocpp-201/](https://www.openchargealliance.org/protocols/ocpp-201/)
- **Wallbox Pulsar Plus NA Quick Reference & Status Guide**: Wallbox, [https://support.wallbox.com/na/](https://support.wallbox.com/na/)
- **Wallbox Pulsar Plus Installation Guide**: Wallbox, [https://support.wallbox.com/](https://support.wallbox.com/)
- **OSHA 3075 Controlling Electrical Hazards & EV Safety Compliance**: Occupational Safety and Health Administration (OSHA), U.S. Department of Labor, [https://www.osha.gov/publications/osha3075](https://www.osha.gov/publications/osha3075)

---

## Honest Limitations

- The verifier agent combines deterministic entity/unit regex parsing with multilingual cosine semantic similarity, not a fine-tuned NLI model. It reliably catches hallucinated error codes, swapped units, negation flips, and uncited claims, but does not provide formal mathematical proof.
- Full hybrid retrieval runs in-process with fallback backends (`rank-bm25` and PyTorch CPU embeddings) when Elasticsearch or Qdrant cluster daemons are not running.
- Hindi TTS and SpeechRecognition quality depend on browser Web Speech API engines (solid on Chrome and Edge; partial or absent on Firefox and Safari).
