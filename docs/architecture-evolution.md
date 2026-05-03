# Architecture Evolution

This document tracks how the system architecture grew over time and why each decision was made.

---

## Phase 1 — Foundation

**Problem being solved:** the original codebase had working AI logic but no structure — modules were flat at the root, there was no persistence, no tests, and no way to verify the agent's behavior systematically.

### Starting point (before Phase 1)

```
aiops-platform/
├── agents/          ← LangGraph pipeline
├── api/             ← FastAPI with in-memory _history
├── ingestion/       ← Kafka consumer
├── knowledge/       ← RAG indexer
├── simulator/       ← fake e-commerce service
└── requirements.txt
```

Problems:
- `from agents.graph import ...` only worked if you ran Python from the project root
- Incident history lived in `_history: list[dict]` — lost on every restart
- No tests — impossible to verify guardrail behavior or detector classification
- No separation between framework code and business logic

### Iteration 1.1 — Restructure + pyproject.toml

Moved all application code under a single `app/` namespace. Created the domain layer.

```
app/
├── domain/          ← pure Python: models, enums, exceptions
├── agent/           ← LangGraph pipeline
├── api/             ← FastAPI
├── knowledge/       ← RAG indexer
├── ingestion/       ← Kafka consumer
└── config.py        ← centralized settings
```

**Key change:** `from app.agent.graph import ...` works from anywhere — tests, scripts, other modules. The import path is now absolute and predictable.

**Domain layer added:** `Incident`, `Signal`, `DiagnosisResult`, `ActionResult`, `GuardrailResult`, `ExecutionResult` as pure Python dataclasses. Zero external dependencies — testable without a database or LLM.

### Iteration 1.2 — Persistence

Replaced the in-memory `_history` list with PostgreSQL via SQLAlchemy async.

```
app/
├── infrastructure/
│   ├── database.py    ← async engine + session factory
│   └── models.py      ← IncidentModel ORM
└── repositories/
    └── incident_repository.py  ← AbstractIncidentRepository + SQLAlchemy impl
```

**New endpoints:**
- `GET /incidents/{id}` — retrieve a single incident by UUID
- `GET /metrics/summary` — now computes MTTR from real timestamps, not request duration

Incidents now survive server restarts. MTTR and blocked_rate are computed from real data.

### Iteration 1.3 — Tests + CI

**52 tests total:**

| Suite | Tests | What's covered |
|---|---|---|
| `tests/unit/test_guardrails.py` | 13 | confidence × destructive matrix, edge cases |
| `tests/unit/test_detector.py` | 13 | signal-based and title-based classification |
| `tests/unit/test_domain.py` | 14 | Incident lifecycle, MTTR calculation, exceptions |
| `tests/integration/test_api.py` | 12 | All API endpoints with real PostgreSQL |

Unit tests run in ~1s with no external dependencies. Integration tests run the full pipeline in offline mode (no API keys needed).

**GitHub Actions CI** runs on every push to `main`, `develop`, and `release/*` branches.

### Architecture after Phase 1

```
┌─────────────────────────────────────────┐
│  API Layer (FastAPI)                    │  ← HTTP in/out, Pydantic schemas
│  app/api/main.py                        │
├─────────────────────────────────────────┤
│  Agent Pipeline (LangGraph)             │  ← Orchestrates LLM calls
│  app/agent/graph.py                     │
│    detector → diagnoser → action        │
│    → guardrail → executor → reporter    │
├─────────────────────────────────────────┤
│  Domain Layer (Pure Python)             │  ← Business rules, no I/O
│  app/domain/                            │
├─────────────────────────────────────────┤
│  Repository Interfaces                  │  ← Abstractions, no SQL here
│  app/repositories/                      │
├─────────────────────────────────────────┤
│  Infrastructure (SQLAlchemy + asyncpg)  │  ← ORM models, concrete repos
│  app/infrastructure/                    │
└─────────────────────────────────────────┘

External dependencies:
  PostgreSQL  ← incident persistence
  Kafka       ← telemetry ingestion (ingestion/consumer.py)
  Pinecone    ← runbook RAG index (knowledge/indexer.py)
  OpenAI      ← LLM diagnosis + action selection
```

**Graceful degradation:** if `OPENAI_API_KEY` or `PINECONE_API_KEY` are absent, the pipeline uses heuristic fallbacks. The full pipeline runs end-to-end with no API calls.

---

## Phases Ahead

| Phase | Focus | Key additions |
|---|---|---|
| **2 — Evaluation Framework** | Measure agent accuracy | Synthetic incident cases, runner, precision/recall report |
| **3 — Agent Observability** | LLM cost + latency tracking | Token usage per node, cost per incident, `GET /incidents/{id}/trace` |
| **4 — Streaming + Integrations** | Real-time pipeline visibility | SSE streaming, PagerDuty/OpsGenie webhooks, Slack notifications |

---

## What stays constant across all phases

- The domain layer has zero external imports
- Guardrails are deterministic Python — the LLM cannot override them
- The pipeline runs fully offline for testing
- Every new endpoint gets integration tests before the iteration closes
