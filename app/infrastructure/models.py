"""
SQLAlchemy ORM models — separate from domain dataclasses.

Design decision: complex nested objects (signals, diagnosis, action, guardrail,
execution) are stored as JSONB columns rather than normalized relational tables.

Trade-off:
  PRO — simpler schema, no joins needed, schema evolution is free (add fields
        to JSON without migrations), fits the semi-structured nature of AI output.
  CON — no SQL filtering on nested fields without JSON operators, no FK integrity.

This is the right call here: incident data is written once and read as a whole.
We never need to query "all incidents where diagnosis.confidence > 0.9" at the DB
level — that filtering happens in the application layer or in the eval runner.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class IncidentModel(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    report: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Semi-structured AI output — stored as JSONB for flexibility
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    detector: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diagnosis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    action: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    guardrail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    execution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
