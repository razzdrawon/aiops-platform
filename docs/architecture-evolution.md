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

## Phase 2 — Evaluation Framework

**Problem being solved:** after Phase 1 the agent's behavior was verified through integration tests against known inputs, but there was no systematic way to measure accuracy across incident classes or track regression over time.

### What was added

```
evals/
├── cases/
│   └── cases.json     ← 22 synthetic incident cases across 6 classes
├── runner.py          ← async runner with per-class accuracy reporting
└── report.py          ← comparison tool between two eval JSON outputs
```

**22 cases across 6 incident classes:**

| Class | Cases | Expected action |
|---|---|---|
| `high_error_rate` | 4 | rollback (blocked) |
| `deploy_failure` | 4 | rollback (blocked) |
| `latency_spike` | 4 | scale_up (allowed) |
| `db_overload` | 4 | noop (allowed) |
| `oom` | 3 | noop (allowed) |
| `unknown` | 3 | noop (allowed) |

Each case asserts two things: the expected `action` and whether the guardrail should `block` it. Both must be correct for a case to pass.

### Offline vs LLM mode

Running `python -m evals.runner` with API keys set produces **4.5% accuracy** — the LLM makes different decisions than the heuristic expectations. This is expected and intentional: the eval suite measures the **heuristic pipeline**, which is the reproducible baseline.

Running with `OPENAI_API_KEY="" PINECONE_API_KEY=""` produces **100% accuracy** across all 22 cases. This is the mode used in CI.

The gap between offline (100%) and LLM mode accuracy is a design signal: as the LLM pipeline improves, the eval suite can be extended with LLM-specific cases to track that separately.

### Comparison report

After saving two runs with `--output`:
```bash
python -m evals.runner --output baseline.json
# (make changes)
python -m evals.runner --output current.json
python -m evals.report baseline.json current.json
```

Output shows delta per metric and per class with directional arrows (↑ ↓ →).

### CI integration

The eval suite runs in CI after integration tests, with API keys explicitly cleared:

```yaml
- name: Run eval suite (offline mode)
  env:
    OPENAI_API_KEY: ""
    PINECONE_API_KEY: ""
  run: python -m evals.runner
```

Any regression in heuristic accuracy fails the build.

---

## Phases Ahead

| Phase | Focus | Key additions |
|---|---|---|
| **3 — Agent Observability** | LLM cost + latency tracking | Token usage per node, cost per incident, `GET /incidents/{id}/trace` |
| **4 — Streaming + Integrations** | Real-time pipeline visibility | SSE streaming, PagerDuty/OpsGenie webhooks, Slack notifications |

---

## What stays constant across all phases

- The domain layer has zero external imports
- Guardrails are deterministic Python — the LLM cannot override them
- The pipeline runs fully offline for testing
- Every new endpoint gets integration tests before the iteration closes
