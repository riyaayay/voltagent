"""Structured, per-query observability.

Every pipeline stage (retrieval, generation, verification, cache) emits one
structured event through `log_event`. Events are written as JSONL so they can
be tailed, grepped, or loaded into a dataframe for a quick dashboard — the
point is that a reviewer (or you, six weeks later) can answer "why did this
query get a bad answer?" from logs alone, without re-running anything.

This intentionally does NOT depend on a hosted observability platform
(Langfuse, Datadog, etc.) so the project runs with zero external accounts.
Swapping the sink for one of those later is a one-function change — see
`_write` below.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from voltagent.config import settings

logger = logging.getLogger("voltagent")
logging.basicConfig(level=settings.log_level)


def _write(event: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
    with open(settings.log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def log_event(stage: str, **fields: Any) -> None:
    """Emit one structured observability event.

    Example:
        log_event("retrieval", query_id=qid, sparse_hits=8, dense_hits=10,
                   fused_top_k=6, latency_ms=142)
    """
    event = {"ts": time.time(), "stage": stage, **fields}
    _write(event)
    logger.info("%s | %s", stage, {k: v for k, v in fields.items() if k != "chunks"})


@dataclass
class QueryTrace:
    """Accumulates everything about one end-to-end query for a single log line
    plus lets you time each stage. Use as a context manager per stage:

        trace = QueryTrace(query_text=q)
        with trace.stage("retrieval"):
            results = retriever.search(q)
        trace.record(retrieval_top_k=len(results))
        ...
        trace.finalize()
    """

    query_text: str
    query_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    language: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    _stage_start: float | None = None
    _current_stage: str | None = None

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = time.time()
        try:
            yield
        finally:
            elapsed_ms = round((time.time() - start) * 1000, 1)
            self.fields[f"{name}_latency_ms"] = elapsed_ms

    def record(self, **fields: Any) -> None:
        self.fields.update(fields)

    def finalize(self, **extra: Any) -> None:
        log_event(
            "query_complete",
            query_id=self.query_id,
            query_text=self.query_text,
            language=self.language,
            **self.fields,
            **extra,
        )
