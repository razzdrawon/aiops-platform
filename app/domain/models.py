"""
Domain models — pure Python dataclasses with zero external dependencies.

These represent the core concepts of the system and carry business rules.
They are distinct from ORM models (infrastructure layer) and API schemas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import ActionType, IncidentClass, IncidentStatus, Severity


@dataclass
class Signal:
    """A single telemetry event (log, metric, or trace) associated with an incident."""
    trace_id: str
    event_type: str          # "log" | "metric" | "trace"
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiagnosisResult:
    """Output of the diagnoser node — root cause analysis with confidence."""
    incident_class: IncidentClass
    narrative: str
    suspected_root_cause: str
    matched_runbook_titles: list[str] = field(default_factory=list)
    no_runbook_match: bool = False
    confidence: float = 0.0


@dataclass
class ActionResult:
    """Output of the action_selector node — what remediation to take."""
    action_type: ActionType
    params: dict[str, Any] = field(default_factory=dict)
    destructive: bool = False
    confidence: float = 0.0
    rationale: str = ""


@dataclass
class GuardrailResult:
    """Output of the guardrail node — whether the action is allowed."""
    blocked: bool
    reason: str
    action_type: ActionType
    confidence: float


@dataclass
class ExecutionResult:
    """Output of the executor node — what actually happened."""
    tool: str
    message: str
    success: bool = True


@dataclass
class Incident:
    """
    Core aggregate — represents a production incident from ingestion to resolution.

    Status transitions:
      PENDING → PROCESSING → RESOLVED
                           → BLOCKED   (guardrail stopped the action)
                           → FAILED    (pipeline error)
    """
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    signals: list[Signal] = field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    status: IncidentStatus = IncidentStatus.PENDING
    diagnosis: DiagnosisResult | None = None
    action: ActionResult | None = None
    guardrail: GuardrailResult | None = None
    execution: ExecutionResult | None = None
    report: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None

    @property
    def mttr_seconds(self) -> float | None:
        if self.resolved_at is None:
            return None
        return (self.resolved_at - self.created_at).total_seconds()

    def mark_resolved(self) -> None:
        self.status = IncidentStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)

    def mark_blocked(self) -> None:
        self.status = IncidentStatus.BLOCKED
        self.resolved_at = datetime.now(timezone.utc)

    def mark_failed(self) -> None:
        self.status = IncidentStatus.FAILED
        self.resolved_at = datetime.now(timezone.utc)
