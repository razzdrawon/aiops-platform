"""
Incident repository — abstract interface + SQLAlchemy implementation.

The abstract class lets unit tests inject a fake in-memory implementation
without touching the database. The concrete class is what the API uses.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import IncidentModel


class AbstractIncidentRepository(ABC):
    @abstractmethod
    async def save(self, incident: dict[str, Any]) -> IncidentModel:
        """Persist a new incident record."""

    @abstractmethod
    async def get_all(self) -> list[IncidentModel]:
        """Return all incidents ordered by created_at descending."""

    @abstractmethod
    async def get_by_id(self, incident_id: uuid.UUID) -> IncidentModel | None:
        """Return a single incident or None if not found."""


class SQLAlchemyIncidentRepository(AbstractIncidentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, incident: dict[str, Any]) -> IncidentModel:
        record = IncidentModel(
            id=uuid.UUID(incident["incident_id"]),
            title=incident.get("title", ""),
            status=self._resolve_status(incident),
            severity=incident.get("detector", {}).get("severity_hint", "medium"),
            signals=incident.get("signals", {}),
            detector=incident.get("detector"),
            diagnosis=incident.get("diagnosis"),
            action=incident.get("action"),
            guardrail=incident.get("guardrail_result"),
            execution=incident.get("execution"),
            report=incident.get("report", ""),
            resolved_at=datetime.now(timezone.utc),
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def get_all(self) -> list[IncidentModel]:
        result = await self._session.execute(
            select(IncidentModel).order_by(IncidentModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, incident_id: uuid.UUID) -> IncidentModel | None:
        result = await self._session.execute(
            select(IncidentModel).where(IncidentModel.id == incident_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _resolve_status(incident: dict[str, Any]) -> str:
        guardrail = incident.get("guardrail_result") or {}
        if guardrail.get("blocked"):
            return "blocked"
        if incident.get("execution"):
            return "resolved"
        return "failed"
