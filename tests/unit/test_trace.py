"""
Unit tests for agent observability — trace structure, token cost calculation,
and node span helpers. All tests run offline with no API keys.
"""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("PINECONE_API_KEY", "")

from app.agent.graph import (
    _COST_PER_INPUT_TOKEN,
    _COST_PER_OUTPUT_TOKEN,
    _token_span,
    run_incident_graph,
)


# ---------------------------------------------------------------------------
# _token_span helper
# ---------------------------------------------------------------------------


def test_token_span_none_input():
    assert _token_span(None) is None


def test_token_span_empty_dict():
    assert _token_span({}) is None


def test_token_span_calculates_cost():
    span = _token_span({"input_tokens": 1_000_000, "output_tokens": 1_000_000})
    assert span is not None
    assert span["input"] == 1_000_000
    assert span["output"] == 1_000_000
    expected_cost = round(
        1_000_000 * _COST_PER_INPUT_TOKEN + 1_000_000 * _COST_PER_OUTPUT_TOKEN, 8
    )
    assert span["cost_usd"] == expected_cost


def test_token_span_zero_tokens():
    span = _token_span({"input_tokens": 0, "output_tokens": 0})
    assert span is not None
    assert span["cost_usd"] == 0.0


def test_token_span_only_input():
    span = _token_span({"input_tokens": 500, "output_tokens": 0})
    assert span["cost_usd"] == round(500 * _COST_PER_INPUT_TOKEN, 8)


# ---------------------------------------------------------------------------
# Full pipeline trace shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_present_in_result():
    result = await run_incident_graph("High error rate on checkout", {"error_rate": 0.12})
    assert "trace" in result
    assert result["trace"] is not None


@pytest.mark.asyncio
async def test_trace_has_all_nodes():
    result = await run_incident_graph("High error rate on checkout", {"error_rate": 0.12})
    trace = result["trace"]
    node_names = [n["node"] for n in trace["nodes"]]
    # Blocked path skips executor
    assert "detector" in node_names
    assert "diagnoser" in node_names
    assert "action_selector" in node_names
    assert "guardrail" in node_names
    assert "reporter" in node_names


@pytest.mark.asyncio
async def test_trace_allowed_path_includes_executor():
    result = await run_incident_graph("Latency spike on payment", {"p95_ms": 2000})
    trace = result["trace"]
    node_names = [n["node"] for n in trace["nodes"]]
    assert "executor" in node_names


@pytest.mark.asyncio
async def test_trace_blocked_path_skips_executor():
    result = await run_incident_graph("Deploy failure on checkout", {"deploy_failed": True})
    trace = result["trace"]
    node_names = [n["node"] for n in trace["nodes"]]
    assert "executor" not in node_names


@pytest.mark.asyncio
async def test_trace_has_totals():
    result = await run_incident_graph("High error rate on checkout", {"error_rate": 0.12})
    trace = result["trace"]
    assert "total_tokens" in trace
    assert "total_duration_ms" in trace
    assert "input" in trace["total_tokens"]
    assert "output" in trace["total_tokens"]
    assert "cost_usd" in trace["total_tokens"]


@pytest.mark.asyncio
async def test_trace_offline_tokens_are_null():
    """In offline mode no LLM calls are made — all node token fields are None."""
    result = await run_incident_graph("DB overload on checkout", {"db_cpu": 95})
    trace = result["trace"]
    for node in trace["nodes"]:
        assert node["tokens"] is None, f"Expected null tokens for {node['node']}"


@pytest.mark.asyncio
async def test_trace_offline_cost_is_zero():
    result = await run_incident_graph("Latency spike on search", {"p95_ms": 1600})
    trace = result["trace"]
    assert trace["total_tokens"]["cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_trace_node_has_started_at():
    result = await run_incident_graph("OOM on worker", {"oom": True})
    trace = result["trace"]
    for node in trace["nodes"]:
        assert "started_at" in node
        assert node["started_at"].startswith("20")  # sanity check: current century


@pytest.mark.asyncio
async def test_trace_duration_ms_non_negative():
    result = await run_incident_graph("Anomaly detected", {})
    trace = result["trace"]
    for node in trace["nodes"]:
        assert node["duration_ms"] >= 0
    assert trace["total_duration_ms"] >= 0
