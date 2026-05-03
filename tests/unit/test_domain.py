"""
Unit tests for domain models.

Pure Python — no DB, no LLM, no network. Tests the business rules
embedded in the domain layer.
"""
from datetime import datetime, timezone

import pytest

from app.domain.enums import IncidentStatus, Severity
from app.domain.exceptions import GuardrailBlockedError, IncidentNotFoundError
from app.domain.models import Incident


class TestIncidentLifecycle:
    def test_default_status_is_pending(self):
        incident = Incident(title="test")
        assert incident.status == IncidentStatus.PENDING

    def test_mark_resolved_sets_status_and_timestamp(self):
        incident = Incident(title="test")
        incident.mark_resolved()
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None

    def test_mark_blocked_sets_status_and_timestamp(self):
        incident = Incident(title="test")
        incident.mark_blocked()
        assert incident.status == IncidentStatus.BLOCKED
        assert incident.resolved_at is not None

    def test_mark_failed_sets_status(self):
        incident = Incident(title="test")
        incident.mark_failed()
        assert incident.status == IncidentStatus.FAILED

    def test_mttr_is_none_when_not_resolved(self):
        incident = Incident(title="test")
        assert incident.mttr_seconds is None

    def test_mttr_calculated_correctly(self):
        incident = Incident(title="test")
        incident.mark_resolved()
        assert incident.mttr_seconds is not None
        assert incident.mttr_seconds >= 0

    def test_default_severity_is_medium(self):
        incident = Incident(title="test")
        assert incident.severity == Severity.MEDIUM

    def test_id_is_unique_per_instance(self):
        a = Incident(title="a")
        b = Incident(title="b")
        assert a.id != b.id


class TestDomainExceptions:
    def test_guardrail_blocked_error_message(self):
        exc = GuardrailBlockedError(action="rollback", confidence=0.7, threshold=0.85)
        assert "rollback" in str(exc)
        assert "0.7" in str(exc)
        assert "0.85" in str(exc)

    def test_incident_not_found_error_message(self):
        exc = IncidentNotFoundError("abc-123")
        assert "abc-123" in str(exc)
