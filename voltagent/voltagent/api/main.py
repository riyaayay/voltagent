"""FastAPI app: the HTTP surface the frontend (and any other client) talks to.

Two endpoints:
  POST /query        - text in, structured verified answer out
  POST /query/speech  - text in, structured answer + synthesized audio out
                        (for clients that can't use Web Speech API directly)
  GET  /health        - liveness check
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from voltagent.agents.graph import run_pipeline
from voltagent.voice.tts import synthesize_speech

app = FastAPI(title="VoltAgent API", version="0.1.0")

# Wide-open CORS for local dev against a static frontend served from a
# different port. Tighten this before deploying anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    text: str


class QueryResponse(BaseModel):
    answer: str
    language: str
    verified: bool
    confidence: float
    fallback: bool
    cache_hit: bool
    citations: list[dict] | None = None
    raw_source: dict | None = None
    fallback_reason: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> dict:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    return run_pipeline(request.text)


@app.post("/query/speech")
def query_with_speech(request: QueryRequest) -> Response:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    result = run_pipeline(request.text)
    audio_bytes = synthesize_speech(result["answer"], result["language"])
    # Return audio directly; clients that also want the structured JSON
    # should call POST /query first and only hit this endpoint for playback,
    # or duplicate the call — kept simple rather than multipart for a demo.
    return Response(content=audio_bytes, media_type="audio/mpeg")
