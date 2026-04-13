"""
FastAPI control plane: trigger the LangGraph remediation pipeline and expose incident history for the dashboard.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.graph import run_incident_graph

load_dotenv()

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


_history: list[dict[str, Any]] = []
_history_lock = asyncio.Lock()


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/incident")
async def create_incident(body: IncidentRequest):
    started = datetime.now(timezone.utc)
    try:
        result = await run_incident_graph(body.title, body.signals)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finished = datetime.now(timezone.utc)
    record = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_ms": int((finished - started).total_seconds() * 1000),
        "title": body.title,
        "signals": body.signals,
        "graph": result,
    }
    async with _history_lock:
        _history.insert(0, record)
    return record


@app.get("/incidents")
async def list_incidents():
    async with _history_lock:
        return list(_history)


@app.get("/metrics/summary")
async def metrics_summary():
    async with _history_lock:
        rows = list(_history)
    if not rows:
        return {"count": 0, "mttr_ms_avg": None, "blocked_rate": None}
    mttr_vals = [r["duration_ms"] for r in rows if r.get("duration_ms") is not None]
    blocked = sum(
        1
        for r in rows
        if (r.get("graph") or {}).get("guardrail_result", {}).get("blocked")
    )
    return {
        "count": len(rows),
        "mttr_ms_avg": int(sum(mttr_vals) / len(mttr_vals)) if mttr_vals else None,
        "blocked_rate": blocked / len(rows),
    }


