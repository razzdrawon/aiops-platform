"""
FastAPI control plane: trigger the LangGraph remediation pipeline and expose
incident history for the dashboard.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_incident_graph
from app.infrastructure.database import get_session
from app.repositories.incident_repository import SQLAlchemyIncidentRepository

app = FastAPI(title="AIOps Control API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentRequest(BaseModel):
    title: str = Field(..., min_length=3)
    signals: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/incident")
async def create_incident(
    body: IncidentRequest,
    session: AsyncSession = Depends(get_session),
):
    started = datetime.now(timezone.utc)
    try:
        result = await run_incident_graph(body.title, body.signals)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    finished = datetime.now(timezone.utc)
    duration_ms = int((finished - started).total_seconds() * 1000)

    repo = SQLAlchemyIncidentRepository(session)
    record = await repo.save(dict(result))

    return {
        "incident_id": str(record.id),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_ms": duration_ms,
        "title": record.title,
        "status": record.status,
        "graph": result,
    }


@app.get("/incidents")
async def list_incidents(session: AsyncSession = Depends(get_session)):
    repo = SQLAlchemyIncidentRepository(session)
    records = await repo.get_all()
    return [
        {
            "incident_id": str(r.id),
            "title": r.title,
            "status": r.status,
            "severity": r.severity,
            "created_at": r.created_at.isoformat(),
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in records
    ]


@app.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    session: AsyncSession = Depends(get_session),
):
    import uuid
    repo = SQLAlchemyIncidentRepository(session)
    record = await repo.get_by_id(uuid.UUID(incident_id))
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "incident_id": str(record.id),
        "title": record.title,
        "status": record.status,
        "severity": record.severity,
        "signals": record.signals,
        "detector": record.detector,
        "diagnosis": record.diagnosis,
        "action": record.action,
        "guardrail": record.guardrail,
        "execution": record.execution,
        "report": record.report,
        "created_at": record.created_at.isoformat(),
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
    }


@app.get("/metrics/summary")
async def metrics_summary(session: AsyncSession = Depends(get_session)):
    repo = SQLAlchemyIncidentRepository(session)
    records = await repo.get_all()
    if not records:
        return {"count": 0, "mttr_ms_avg": None, "blocked_rate": None}

    blocked = sum(1 for r in records if r.status == "blocked")
    resolved = [
        r for r in records
        if r.resolved_at and r.created_at
    ]
    mttr_vals = [
        (r.resolved_at - r.created_at).total_seconds()
        for r in resolved
    ]
    return {
        "count": len(records),
        "mttr_seconds_avg": round(sum(mttr_vals) / len(mttr_vals), 1) if mttr_vals else None,
        "blocked_rate": round(blocked / len(records), 3),
    }
