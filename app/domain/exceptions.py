class AIOpsError(Exception):
    """Base exception for all domain errors."""


class GuardrailBlockedError(AIOpsError):
    """Raised when a guardrail blocks a destructive action."""

    def __init__(self, action: str, confidence: float, threshold: float) -> None:
        self.action = action
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"Action '{action}' blocked: confidence {confidence} does not exceed threshold {threshold}"
        )


class DiagnosisError(AIOpsError):
    """Raised when the diagnosis pipeline fails unexpectedly."""


class IncidentNotFoundError(AIOpsError):
    """Raised when an incident ID does not exist in the repository."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = incident_id
        super().__init__(f"Incident '{incident_id}' not found")
