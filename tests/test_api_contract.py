"""API-level safety-contract checks, run through TestClient with the fake LLM.

The retrieval backend is pointed at a closed local port with a 1 s timeout and no
retries, so the test is fast and does not depend on whether docker compose is up.
A dependency being down is a failure mode the contract must survive (outcome C,
never a raw 500).
"""
import pytest
from elasticsearch import Elasticsearch
from fastapi.testclient import TestClient

from voltagent.agents import graph
from voltagent.api.main import app


@pytest.fixture
def es_unreachable(monkeypatch):
    dead = Elasticsearch("http://127.0.0.1:9", request_timeout=1, max_retries=0)
    monkeypatch.setattr(graph._retriever.sparse, "client", dead)


@pytest.mark.e2e
def test_dependency_down_returns_explicit_degraded_response_not_500(fake_llm, es_unreachable):
    # raise_server_exceptions=False so an unhandled error shows up as the HTTP
    # 500 a technician's client would actually receive.
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/query", json={"text": "E-101 on Voltara DC-60"})

    assert resp.status_code == 200, f"unhandled failure surfaced as HTTP {resp.status_code}"
    body = resp.json()
    assert body["verified"] is False
    assert body["answer"]
