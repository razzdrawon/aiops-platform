"""
Unit tests for the heuristic detector node.

The detector classifies incidents based on signals and title keywords
without calling any LLM. These tests ensure the classification logic
is correct and deterministic.
"""
import pytest

from app.agent.graph import _heuristic_class


class TestDetectorBySignals:
    def test_oom_signal(self):
        assert _heuristic_class({"oom": True}, "") == "oom"

    def test_deploy_failed_signal(self):
        assert _heuristic_class({"deploy_failed": True}, "") == "deploy_failure"

    def test_db_cpu_signal(self):
        assert _heuristic_class({"db_cpu": 95}, "") == "db_overload"

    def test_high_error_rate_signal(self):
        assert _heuristic_class({"error_rate": 0.06}, "") == "high_error_rate"

    def test_error_rate_at_boundary(self):
        """error_rate > 0.05 triggers high_error_rate."""
        assert _heuristic_class({"error_rate": 0.051}, "") == "high_error_rate"

    def test_error_rate_below_boundary(self):
        assert _heuristic_class({"error_rate": 0.04}, "") == "unknown"

    def test_high_p95_latency(self):
        assert _heuristic_class({"p95_ms": 1600}, "") == "latency_spike"

    def test_p95_at_boundary(self):
        """p95_ms > 1500 triggers latency_spike."""
        assert _heuristic_class({"p95_ms": 1501}, "") == "latency_spike"

    def test_unknown_when_no_signals_match(self):
        assert _heuristic_class({"cpu": 30}, "") == "unknown"

    def test_empty_signals(self):
        assert _heuristic_class({}, "") == "unknown"


class TestDetectorByTitle:
    def test_oom_in_title(self):
        assert _heuristic_class({}, "OOM killed on checkout pod") == "oom"

    def test_deploy_in_title(self):
        assert _heuristic_class({}, "deploy failure on staging") == "deploy_failure"

    def test_database_in_title(self):
        assert _heuristic_class({}, "database connection pool exhausted") == "db_overload"

    def test_db_in_title(self):
        assert _heuristic_class({}, "db timeout on writes") == "db_overload"

    def test_error_in_title(self):
        assert _heuristic_class({}, "high error rate detected") == "high_error_rate"

    def test_latency_in_title(self):
        assert _heuristic_class({}, "latency spike on payment service") == "latency_spike"


class TestDetectorPriority:
    def test_oom_takes_priority_over_error_rate(self):
        """OOM is checked first."""
        assert _heuristic_class({"oom": True, "error_rate": 0.2}, "") == "oom"

    def test_deploy_takes_priority_over_latency(self):
        assert _heuristic_class({"deploy_failed": True, "p95_ms": 2000}, "") == "deploy_failure"
