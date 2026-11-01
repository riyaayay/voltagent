# VoltAgent Deployment Guide

This guide covers deployment options for VoltAgent, ranging from free zero-cost hosting to scalable low-RAM cloud setups.

---

## 1. Zero-Cost / Free CPU Hosting: Hugging Face Spaces

VoltAgent can be deployed directly to Hugging Face Spaces on the free CPU tier (2 vCPU, 16 GB RAM) with zero Docker infrastructure.

### Configuration
- **Space SDK**: `gradio` (used strictly as an ASGI launcher for `app.py`; no Gradio UI components needed)
- **Entry point**: `app.py` (mounts `frontend/` static files at `/` and runs `uvicorn` on `0.0.0.0:7860`)
- **Python version**: `3.11`
- **Retrieval Engine**: In-process BM25 (`rank-bm25`) + in-process PyTorch dense vector cosine search with cached index

### Deployment Steps
1. Create a new Space on Hugging Face:
   - Select **Gradio** as the Space SDK.
   - Choose the free **CPU basic** hardware tier.
2. In **Space Settings > Variables and secrets**:
   - Add Secret: `GEMINI_API_KEY` (or `OPENAI_API_KEY`)
   - Add Variable: `SPARSE_BACKEND` = `bm25`
   - Add Variable: `CACHE_BACKEND` = `memory`
   - Add Variable: `DAILY_LLM_CAP` = `200` (optional call ceiling)
   - Add Variable: `RATE_LIMIT_PER_MINUTE` = `20` (IP rate limiting)
3. Push the repository files to the Space git remote:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/voltagent
   git push space main
   ```
4. On first boot:
   - If `data/index_cache/` is included, the app starts in ~10 seconds.
   - If `data/index_cache/` is absent, the startup lifespan automatically indexes the bundled demo corpus (`data/raw/synthetic` + OSHA 3075) and caches it.
   - The `/ready` endpoint returns HTTP 503 (`status: loading`) until the multilingual embedder is warm in memory, then switches to HTTP 200 (`status: ready`).

---

## 2. Low-RAM Budget Cloud Options (< 8 GB RAM)

If deploying to low-memory VPS instances (e.g. Hetzner Cloud CPX11 2GB, DigitalOcean 2GB Droplet, or Railway/Render free/starter tiers):

| Architecture Option | Memory Footprint | External Services | Recommended For |
| :--- | :--- | :--- | :--- |
| **A. In-Process (Current)** | ~1.2 GB peak (CPU embedder) | None (zero external dependencies) | Free Spaces, small VPS, local dev |
| **B. Qdrant Cloud + In-Process BM25** | ~350 MB (client only) | Qdrant Cloud (Free 1GB cluster) | Low-RAM VPS ($4-6/mo) |
| **C. Full Docker Cluster** | ~4.5 GB | Elasticsearch + Qdrant + Redis | Dedicated enterprise servers |

### Running Option B (Qdrant Cloud + BM25):
1. Sign up for a free 1GB cluster at [cloud.qdrant.io](https://cloud.qdrant.io/).
2. Set environment variables:
   ```env
   SPARSE_BACKEND=bm25
   CACHE_BACKEND=memory
   QDRANT_URL=https://<your-cluster-id>.us-east-1-0.aws.cloud.qdrant.io:6333
   QDRANT_API_KEY=<your-qdrant-api-key>
   ```

---

## 3. Environment Variables Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `None` | Google Gemini API key for Query & Generation agents |
| `OPENAI_API_KEY` | `None` | OpenAI API key (alternative provider) |
| `LLM_PROVIDER` | `gemini` | `gemini`, `openai`, or `fake` (for hermetic test runs) |
| `GENERATION_MODEL` | `gemini-2.5-flash` | Active model (`gemini-2.5-flash`, `gemini-2.5-pro`, `gpt-4o-mini`) |
| `SPARSE_BACKEND` | `bm25` | `bm25` (in-process) or `elasticsearch` (cluster) |
| `CACHE_BACKEND` | `memory` | `memory` (TTLCache) or `redis` (distributed cluster) |
| `VERIFIER_CONFIDENCE_THRESHOLD` | `0.55` | Confidence score cutoff for Claim (C) verification |
| `DAILY_LLM_CAP` | `200` | Maximum allowed LLM completions per day |
| `RATE_LIMIT_PER_MINUTE` | `20` | Maximum requests per minute per IP address |
| `PORT` | `7860` (or `8000`) | Listening port |
| `HOST` | `0.0.0.0` | Binding interface |

---

## 4. Live LLM Smoke Test Command

To verify live LLM connectivity with configured API credentials:

```powershell
# Windows PowerShell
.venv\Scripts\pytest.exe tests/test_fake_llm.py -k "test_live_provider_smoke"
```

```bash
# Linux / macOS / CI
pytest tests/test_fake_llm.py -k "test_live_provider_smoke"
```

If no API key is present in `.env`, the test automatically skips with `"no LLM API key configured"`. When a valid key is set, the test runs live and validates response generation.

---

## 5. Local Verification & Launch Checklist

Run the pre-flight checklist before pushing to production:

```powershell
# 1. Run unit test suite
.venv\Scripts\pytest.exe tests/ -m "unit"

# 2. Check embedder and index cache
.venv\Scripts\python.exe -c "from voltagent.retrieval.dense_qdrant import get_embedder; print(get_embedder())"

# 3. Launch local Spaces simulator
.venv\Scripts\python.exe app.py
```

Open `http://localhost:7860` in Google Chrome or Edge. Ensure microphone permissions are granted for Web Speech API transcription.

