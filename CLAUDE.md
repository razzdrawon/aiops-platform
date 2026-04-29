# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIOps Platform — an autonomous incident resolution agent that ingests streaming telemetry, diagnoses root causes with RAG + LLM, and executes remediation with deterministic guardrails.

**Current phase:** Phase 1 — Foundation (clean architecture, persistence, tests, CI).

**Roadmap phases:** Evaluation Framework → Agent Observability → Streaming + Integrations.

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the API locally (requires .env with DATABASE_URL)
uvicorn app.api.main:app --reload

# Run everything via Docker (recommended)
docker-compose up

# Apply migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Unit tests only — no DB, no API keys needed
pytest tests/unit/ -v

# Integration tests — requires PostgreSQL
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=app --cov-report=term-missing

# Run evaluation suite
python -m evals.runner
```

## Architecture

Five strict layers — dependencies only flow downward, never up:

```
API (FastAPI routes + Pydantic schemas)
  ↓
Use Cases (application orchestration)
  ↓
Domain (pure Python — zero framework imports, zero DB, zero LLM)
  ↓
Repository interfaces (abstract base classes)
  ↓
Infrastructure (SQLAlchemy ORM models + concrete repos)
```

The agent pipeline (`app/agent/`) lives at the use case level — it is orchestration, not domain logic. The domain layer has no LangGraph, no OpenAI, no FastAPI.

### Layer responsibilities

- **`app/domain/`** — dataclass models (`Incident`, `Signal`, `DiagnosisResult`, `ActionResult`), enums (`IncidentStatus`, `ActionType`, `Severity`), domain exceptions. Zero external imports.
- **`app/repositories/base.py`** — abstract async interfaces. All methods are `async`.
- **`app/use_cases/`** — one class per operation. Receives repository interfaces via constructor injection; unit tests use in-memory fakes.
- **`app/agent/`** — LangGraph pipeline. Nodes: detector → diagnoser → action_selector → guardrail → executor → reporter. Each node is a pure async function.
- **`app/infrastructure/`** — SQLAlchemy ORM models (distinct from domain dataclasses), concrete repositories, async engine + session factory.
- **`app/api/`** — FastAPI routers, Pydantic schemas, `dependencies.py` wires use cases per-request via `Depends`.
- **`app/knowledge/`** — Pinecone RAG indexer and search. Called by the diagnoser node.
- **`app/ingestion/`** — Kafka consumer. Normalizes, correlates by `trace_id`, triggers the pipeline.

### Guardrails

`app/agent/guardrails.py` lives **outside the LLM**. Deterministic rules the LLM cannot override:
- Destructive actions (rollback, restart) require `confidence > 0.85`
- If blocked, the pipeline skips executor and goes straight to reporter

### Testing strategy

- **Unit tests** (`tests/unit/`) — no DB, no API keys. Test guardrails, detector heuristics, domain models with fake repos.
- **Integration tests** (`tests/integration/`) — real PostgreSQL. `conftest.py` creates tables, yields session, rolls back after each test.
- **Evals** (`evals/`) — synthetic incident cases with expected actions. Measures accuracy, precision, recall of the full pipeline.

### Graceful degradation

If `OPENAI_API_KEY` or `PINECONE_API_KEY` are not set, the pipeline falls back to heuristic diagnosis and deterministic action selection. The app runs fully offline — no API calls made.

## Key Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL async connection string |
| `OPENAI_API_KEY` | _(empty)_ | Enables LLM mode; empty = offline heuristic mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM for diagnosis + action selection |
| `PINECONE_API_KEY` | _(empty)_ | Enables RAG; empty = heuristic mode |
| `PINECONE_INDEX_NAME` | `aiops-runbooks` | Pinecone index for runbooks |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `RAG_MATCH_DISTANCE_MAX` | `0.45` | Cosine distance ceiling for runbook retrieval |
| `CORRELATION_FLUSH_EVENTS` | `2` | Events per trace before flushing as an incident |

## Commit Rules

Never add `Co-Authored-By` trailers or any Claude/Anthropic attribution to commits. Commits must appear as authored solely by the developer.

## Workflow Rules

**Never commit without explicit instruction.** After completing a feature or phase, stop and explain how to validate the work (commands to run, endpoints to test, expected output). Wait for explicit approval before creating any git commit or running `git push`.

The developer reviews code and runs tests before deciding to commit each version.