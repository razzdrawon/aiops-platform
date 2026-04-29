"""
Rule-based guardrails live outside the LLM so policy stays deterministic and auditable.
Destructive actions require high model-stated confidence to proceed — this blocks "creative" risk.
"""

from __future__ import annotations

from typing import Any


def validate_action(action: dict[str, Any]) -> dict[str, Any]:
    destructive = bool(action.get("destructive"))
    try:
        confidence = float(action.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    if destructive and confidence <= 0.85:
        return {
            "blocked": True,
            "reason": "destructive actions require confidence > 0.85",
            "destructive": destructive,
            "confidence": confidence,
        }

    return {
        "blocked": False,
        "reason": "ok",
        "destructive": destructive,
        "confidence": confidence,
    }
