"""
Unit tests for the guardrail layer.

The guardrail is the most critical safety component — it decides whether
destructive actions (rollback, restart) are allowed to execute.
These tests cover the full confidence × destructive matrix.
No DB, no API keys, no network needed.
"""
import pytest

from app.agent.guardrails import validate_action


class TestDestructiveActions:
    def test_blocked_when_confidence_at_threshold(self):
        """Exactly 0.85 should be blocked — rule is strictly greater than."""
        result = validate_action({"destructive": True, "confidence": 0.85})
        assert result["blocked"] is True
        assert "0.85" in result["reason"]

    def test_blocked_when_confidence_below_threshold(self):
        result = validate_action({"destructive": True, "confidence": 0.7})
        assert result["blocked"] is True

    def test_blocked_when_confidence_zero(self):
        result = validate_action({"destructive": True, "confidence": 0.0})
        assert result["blocked"] is True

    def test_allowed_when_confidence_above_threshold(self):
        result = validate_action({"destructive": True, "confidence": 0.86})
        assert result["blocked"] is False
        assert result["reason"] == "ok"

    def test_allowed_when_confidence_is_one(self):
        result = validate_action({"destructive": True, "confidence": 1.0})
        assert result["blocked"] is False


class TestNonDestructiveActions:
    def test_always_allowed_regardless_of_confidence(self):
        result = validate_action({"destructive": False, "confidence": 0.0})
        assert result["blocked"] is False

    def test_allowed_with_low_confidence(self):
        result = validate_action({"destructive": False, "confidence": 0.3})
        assert result["blocked"] is False

    def test_allowed_with_high_confidence(self):
        result = validate_action({"destructive": False, "confidence": 0.99})
        assert result["blocked"] is False


class TestEdgeCases:
    def test_missing_confidence_defaults_to_zero(self):
        """Missing confidence is treated as 0.0 — destructive actions blocked."""
        result = validate_action({"destructive": True})
        assert result["blocked"] is True

    def test_invalid_confidence_string_treated_as_zero(self):
        result = validate_action({"destructive": True, "confidence": "high"})
        assert result["blocked"] is True

    def test_missing_destructive_defaults_to_false(self):
        """Missing destructive field is treated as non-destructive — always allowed."""
        result = validate_action({"confidence": 0.5})
        assert result["blocked"] is False

    def test_result_includes_confidence_and_destructive(self):
        result = validate_action({"destructive": True, "confidence": 0.9})
        assert "confidence" in result
        assert "destructive" in result
