"""LangGraph orchestration: Query Agent -> Hybrid Retriever -> Generation
Agent -> Verifier Agent -> (cache write) -> response.

This is intentionally a linear graph today (no branching/looping) but it's
built as a graph rather than a plain function chain because the natural next
iterations ARE graph-shaped: e.g. "if verifier fails, loop back to
retrieval with a broadened query" is a two-line edge change here, and would
be a rewrite if this were a flat pipeline function.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from voltagent.agents.generation_agent import GenerationResult, run_generation_agent
from voltagent.agents.query_agent import QueryAgentResult, run_query_agent
from voltagent.agents.verifier_agent import VerificationResult, run_verifier_agent
from voltagent.cache import cache
from voltagent.logging_utils import QueryTrace
from voltagent.retrieval.hybrid import HybridRetriever, RetrievedChunk


class GraphState(TypedDict, total=False):
    raw_query: str
    query_result: QueryAgentResult
    retrieved_chunks: list[RetrievedChunk]
    generation: GenerationResult
    verification: VerificationResult
    trace: QueryTrace
    cache_hit: bool
    final_response: dict[str, Any]


_retriever = HybridRetriever()


def _node_check_cache(state: GraphState) -> GraphState:
    # Cache is only checked AFTER language detection, since the cache key is
    # language-scoped — but we don't know the query's language before running
    # the query agent, so this graph runs query agent first, then checks
    # cache before paying for retrieval+generation. See node ordering below.
    return state


def _node_query_agent(state: GraphState) -> GraphState:
    trace = state["trace"]
    with trace.stage("query_agent"):
        result = run_query_agent(state["raw_query"])
    trace.language = result.language
    state["query_result"] = result
    return state


def _node_cache_lookup(state: GraphState) -> GraphState:
    qr = state["query_result"]
    trace = state["trace"]
    with trace.stage("cache_lookup"):
        hit = cache.get(qr.reformulated_query, qr.language)
    if hit:
        state["cache_hit"] = True
        state["final_response"] = {**hit, "cache_hit": True}
    else:
        state["cache_hit"] = False
    return state


def _route_after_cache(state: GraphState) -> str:
    return "respond_from_cache" if state.get("cache_hit") else "retrieve"


def _node_retrieve(state: GraphState) -> GraphState:
    qr = state["query_result"]
    trace = state["trace"]
    with trace.stage("retrieval"):
        chunks = _retriever.retrieve(qr.reformulated_query, query_id=trace.query_id)
    trace.record(retrieved_count=len(chunks))
    state["retrieved_chunks"] = chunks
    return state


def _node_generate(state: GraphState) -> GraphState:
    qr = state["query_result"]
    trace = state["trace"]
    with trace.stage("generation"):
        result = run_generation_agent(qr.reformulated_query, qr.language, state["retrieved_chunks"])
    trace.record(is_insufficient=result.is_insufficient, cited_chunks=len(result.cited_chunk_ids))
    state["generation"] = result
    return state


def _node_verify(state: GraphState) -> GraphState:
    trace = state["trace"]
    with trace.stage("verification"):
        result = run_verifier_agent(state["generation"], query_text=state["query_result"].reformulated_query)
    trace.record(
        verified=result.verified,
        confidence=result.confidence,
        fallback=result.fallback,
        threshold_applied=result.threshold_applied,
    )
    state["verification"] = result
    return state


def _node_build_response(state: GraphState) -> GraphState:
    qr = state["query_result"]
    generation = state["generation"]
    verification = state["verification"]
    trace = state["trace"]

    if verification.fallback:
        top_chunk = state["retrieved_chunks"][0] if state["retrieved_chunks"] else None
        response = {
            "answer": (
                "I'm not confident enough in a generated answer for this one. "
                "Here's the most relevant source passage instead."
            ),
            "language": qr.language,
            "verified": False,
            "confidence": verification.confidence,
            "fallback": True,
            "fallback_reason": verification.fallback_reason,
            "raw_source": {
                "doc_title": top_chunk.doc_title,
                "page_number": top_chunk.page_number,
                "text": top_chunk.text,
            }
            if top_chunk
            else None,
        }
    else:
        response = {
            "answer": generation.answer_text,
            "language": qr.language,
            "verified": True,
            "confidence": verification.confidence,
            "fallback": False,
            "citations": [
                {"chunk_id": c.chunk_id, "doc_title": c.doc_title, "page_number": c.page_number}
                for c in generation.used_chunks
                if c.chunk_id in generation.cited_chunk_ids
            ],
        }

    if cache.should_cache({"verified": verification.verified, "fallback": verification.fallback}):
        cache.set(qr.reformulated_query, qr.language, response)

    state["final_response"] = {**response, "cache_hit": False}
    trace.finalize(final_verified=response["verified"])
    return state


def build_graph() -> Any:
    graph = StateGraph(GraphState)

    graph.add_node("query_agent", _node_query_agent)
    graph.add_node("cache_lookup", _node_cache_lookup)
    graph.add_node("retrieve", _node_retrieve)
    graph.add_node("generate", _node_generate)
    graph.add_node("verify", _node_verify)
    graph.add_node("build_response", _node_build_response)

    graph.set_entry_point("query_agent")
    graph.add_edge("query_agent", "cache_lookup")
    graph.add_conditional_edges(
        "cache_lookup", _route_after_cache, {"respond_from_cache": END, "retrieve": "retrieve"}
    )
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "verify")
    graph.add_edge("verify", "build_response")
    graph.add_edge("build_response", END)

    return graph.compile()


_compiled_graph = build_graph()


def run_pipeline(
    raw_query: str, station_id: str | None = None, charger_model: str | None = None
) -> dict[str, Any]:
    """Public entry point used by the API layer.

    `station_id`/`charger_model` are passed through purely for observability
    — they ride along in the log line so the Insights batch layer can
    aggregate faults per station and correlate with hardware/firmware. They
    don't affect retrieval or generation.
    """
    trace = QueryTrace(query_text=raw_query, station_id=station_id, charger_model=charger_model)
    initial_state: GraphState = {"raw_query": raw_query, "trace": trace}
    final_state = _compiled_graph.invoke(initial_state)
    response = final_state["final_response"]
    response["query_id"] = trace.query_id
    return response
