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
from voltagent.logging_utils import log_feedback
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
    station_id: str | None = None    # e.g. "STN-4471" — which charging station the technician is at
    charger_model: str | None = None  # e.g. "ChargePoint CT4021" — hardware/firmware context


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    language: str
    verified: bool
    confidence: float
    fallback: bool
    cache_hit: bool
    citations: list[dict] | None = None
    raw_source: dict | None = None
    fallback_reason: str | None = None


class FeedbackRequest(BaseModel):
    query_id: str
    resolved: bool                    # did this answer actually fix the technician's problem?


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> dict:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    return run_pipeline(request.text, station_id=request.station_id, charger_model=request.charger_model)


@app.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    """Technician reports back whether the answer actually resolved the
    issue. This is the raw signal the Insights `documentation_gap_detector`
    Spark job aggregates — a query_id with verified=True but resolved=False
    repeatedly is a stronger "our docs are wrong here" signal than
    low confidence alone."""
    log_feedback(query_id=request.query_id, resolved=request.resolved)
    return {"status": "recorded"}


@app.post("/query/speech")
def query_with_speech(request: QueryRequest) -> Response:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    result = run_pipeline(request.text, station_id=request.station_id, charger_model=request.charger_model)
    audio_bytes = synthesize_speech(result["answer"], result["language"])
    # Return audio directly; clients that also want the structured JSON
    # should call POST /query first and only hit this endpoint for playback,
    # or duplicate the call — kept simple rather than multipart for a demo.
    return Response(content=audio_bytes, media_type="audio/mpeg")
