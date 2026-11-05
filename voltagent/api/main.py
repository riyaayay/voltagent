"""FastAPI app: the HTTP surface the frontend (and any other client) talks to.

Two endpoints:
  POST /query        - text in, structured verified answer out
  POST /query/speech  - text in, structured answer + synthesized audio out
                        (for clients that can't use Web Speech API directly)
  GET  /health        - liveness check
  GET  /ready         - readiness check (loading vs ready state for embedder/index)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from voltagent.agents.graph import run_pipeline
from voltagent.config import settings
from voltagent.logging_utils import log_feedback
from voltagent.voice.tts import synthesize_speech

logger = logging.getLogger(__name__)

# State tracking for readiness and rate limiting
_is_ready: bool = False
_ready_status: str = "loading"
_ip_request_times: dict[str, list[float]] = defaultdict(list)
_daily_llm_counter = {"date": "", "count": 0}


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    cutoff = now - 60.0
    times = [t for t in _ip_request_times[client_ip] if t > cutoff]
    if len(times) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {settings.rate_limit_per_minute} requests per minute per IP.",
        )
    times.append(now)
    _ip_request_times[client_ip] = times


def _check_daily_cap() -> None:
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _daily_llm_counter["date"] != today:
        _daily_llm_counter["date"] = today
        _daily_llm_counter["count"] = 0
    if _daily_llm_counter["count"] >= settings.daily_llm_cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily LLM call quota exceeded ({settings.daily_llm_cap} calls/day limit). Please try again tomorrow.",
        )
    _daily_llm_counter["count"] += 1


def _extract_client_ip(http_request: Request) -> str:
    forwarded = http_request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return http_request.client.host if http_request.client else "unknown"


def _warmup_backend():
    global _is_ready, _ready_status
    try:
        index_cache = Path("data/index_cache")
        bm25_cache = index_cache / "bm25.pkl"
        dense_cache = index_cache / "dense.pt"

        if not bm25_cache.exists() or not dense_cache.exists():
            _ready_status = "building_index"
            logger.info("Index cache missing. Building index from raw corpus...")
            from voltagent.ingestion.chunking import chunk_pages
            from voltagent.ingestion.loaders import load_directory
            from voltagent.retrieval.dense_qdrant import QdrantRetriever
            from voltagent.retrieval.sparse_es import ElasticsearchRetriever

            pages = []
            if Path("data/raw/synthetic").exists():
                pages.extend(load_directory("data/raw/synthetic"))
            if Path("data/raw/real").exists():
                pages.extend(load_directory("data/raw/real"))

            if pages:
                chunks = chunk_pages(pages, chunk_size_tokens=100, overlap_tokens=20)
                ElasticsearchRetriever().index_chunks(chunks)
                QdrantRetriever().index_chunks(chunks)
                logger.info("Index built with %d chunks.", len(chunks))

        _ready_status = "warming_embedder"
        from voltagent.retrieval.dense_qdrant import get_embedder
        get_embedder()

        _is_ready = True
        _ready_status = "ready"
        logger.info("VoltAgent backend is warm and ready.")
    except Exception as e:
        logger.error("Error during backend warmup: %s", e)
        _ready_status = f"error: {e}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up in background thread on startup
    threading.Thread(target=_warmup_backend, daemon=True).start()
    yield


app = FastAPI(title="VoltAgent API", version="0.1.0", lifespan=lifespan)

# CORS scoped to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    text: str = Field(..., max_length=settings.max_query_text_length)
    lang: str | None = None          # optional explicit language override ("en" | "hi")
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
    outcome: str | None = None


class FeedbackRequest(BaseModel):
    query_id: str
    resolved: bool                    # did this answer actually fix the technician's problem?


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness probe checking sparse and dense retriever dependencies and warmup."""
    body = {
        "ready": _is_ready,
        "status": _ready_status,
        "sparse_backend": settings.sparse_backend,
        "cache_backend": settings.cache_backend,
    }
    status_code = status.HTTP_200_OK if _is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=body)


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, http_request: Request) -> dict:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    client_ip = _extract_client_ip(http_request)
    _check_rate_limit(client_ip)
    _check_daily_cap()

    try:
        return run_pipeline(request.text, station_id=request.station_id, charger_model=request.charger_model)
    except Exception as e:
        logger.exception("Unexpected error in /query endpoint: %s", e)
        return {
            "query_id": "error",
            "answer": f"Backend processing error: {e}",
            "language": request.lang or "en",
            "verified": False,
            "confidence": 0.0,
            "fallback": True,
            "cache_hit": False,
            "fallback_reason": str(e),
            "outcome": "C",
            "citations": [],
            "raw_source": None,
        }



@app.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    log_feedback(query_id=request.query_id, resolved=request.resolved)
    return {"status": "recorded"}


@app.post("/query/speech")
def query_with_speech(request: QueryRequest, http_request: Request) -> Response:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    client_ip = _extract_client_ip(http_request)
    _check_rate_limit(client_ip)
    _check_daily_cap()

    result = run_pipeline(request.text, station_id=request.station_id, charger_model=request.charger_model)
    audio_bytes = synthesize_speech(result["answer"], result["language"])
    return Response(content=audio_bytes, media_type="audio/mpeg")


# Mount frontend/ static files at "/" so API and UI share the same origin
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
