---
title: VoltAgent
sdk: gradio
sdk_version: 5.49.1
python_version: "3.11"
app_file: app.py
---

# VoltAgent: Voice-First Verified RAG Copilot for EV Charger Technicians

VoltAgent is an AI copilot tailored for field technicians working on live EV charging equipment.
It uses hybrid retrieval (BM25 + multilingual dense vector search), LangGraph pipeline orchestration, and a strict Verifier Agent that audits generated answers against cited technical manuals.

## Running on Hugging Face Spaces (Free CPU)

This space uses the Gradio SDK as an ASGI launcher to run the full FastAPI application and Web Speech API frontend on host `0.0.0.0` and port `7860`.

### Features
- **Frontend**: Web Speech API voice capture (with Hindi/Hinglish language options) and audio response.
- **Retrieval**: In-process hybrid BM25 + dense vector embeddings with zero external Docker service requirements.
- **Verification**: Confidence scoring and citation alignment checking to prevent hallucinations in live electrical environments.
- **Safety**: Client IP rate-limiting and daily LLM quota enforcement.

### Configuration / Secrets (Hugging Face Space Settings)
Set in **Space Settings > Variables and secrets**:
- `GEMINI_API_KEY`: Google Gemini API key (recommended: `gemini-2.5-flash`).
- `SPARSE_BACKEND`: `bm25` (default).
- `CACHE_BACKEND`: `memory` (default).
- `DAILY_LLM_CAP`: Daily LLM call budget (default: `200`).

