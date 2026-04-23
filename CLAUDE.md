# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIOps platform for automated incident resolution. A LangGraph state machine receives correlated incidents via Kafka, runs RAG-augmented diagnosis using Pinecone + OpenAI, selects a remediation action, enforces deterministic guardrails, and executes mock tools — all auditable and safe to run locally without cloud keys.

## Setup

```bash
cp .env.example .env           # Add OPENAI_API_KEY and PINECONE_* if using LLM mode
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d           # Starts Kafka + Zookeeper
python -m knowledge.indexer    # One-time: embed runbooks into Pinecone (requires PINECONE_API_KEY)
```

## Running (three separate terminals)

```bash
# Terminal 1 — Simulator (synthetic incident source on :8010)
uvicorn simulator.ecommerce_app:app --port 8010 --reload

# Terminal 2 — Ingestion consumer (trace-id correlation, publishes to incidents.correlated)
python -m ingestion.consumer

# Terminal 3 — Control API (:8000)
uvicorn api.main:app --port 8000 --reload
```

Dashboard: open `dashboard/index.html` directly in a browser (polls `:8000` every 8 s).

## Testing an Incident Manually

```bash
curl -s -X POST http://localhost:8000/incident \
  -H "Content-Type: application/json" \
  -d '{"title":"High error rate","signals":["5xx spike","p99 latency 3s"],"service":"checkout"}' | jq .
```

## Architecture

### Data Flow

```
Simulator (:8010) ──Kafka ecommerce.events──> Ingestion Consumer
                                                      │
                                         Kafka incidents.correlated
                                                      │
                                              API (:8000) ──triggers──> LangGraph Pipeline
```

### LangGraph Pipeline (`agents/graph.py`)

Six sequential nodes; the only branch is after **Guardrail**:

| Node | Mode | Output |
|---|---|---|
| **Detector** | Heuristic only | `incident_type` (oom / deploy_failure / db_overload / high_error_rate / latency_spike / unknown) |
| **Diagnoser** | Heuristic fallback or RAG + OpenAI | `diagnosis`, `no_runbook_match` flag |
| **Action Selector** | Map-based fallback or OpenAI → `ActionLLM` | `action_name`, `params`, `destructive`, `confidence` |
| **Guardrail** | Deterministic Python (`agents/guardrails.py`) | `blocked`, `reason` |
| **Executor** | Mock tools (`agents/tools.py`) | `execution_result` (if allowed) |
| **Reporter** | Always runs | Final narrative in `report` |

Conditional edge after Guardrail: blocked → Reporter directly; allowed → Executor → Reporter.

### Offline / Heuristic Mode

When `OPENAI_API_KEY` or `PINECONE_API_KEY` is absent, the Diagnoser and Action Selector fall back to deterministic heuristics. The full pipeline still runs end-to-end — useful for development and demos without cloud credentials.

### Guardrail Policy (`agents/guardrails.py`)

Single function `validate_action()`. Destructive actions (rollback, restart_service) require `confidence > 0.85`. This runs outside the LLM and cannot be prompt-injected. The strict `>` (not `>=`) at 0.85 is intentional.

### Executor Tools (`agents/tools.py`)

Five mock tools: `rollback`, `restart_service`, `scale_up`, `create_pr_fix`, `noop`. All log structured JSON intent; none have real side effects. Swapping a mock for a real integration is a ~10-line change in `TOOL_REGISTRY`.

### RAG System (`knowledge/`)

`knowledge/indexer.py` chunks the five runbooks in `knowledge/runbooks/`, embeds with `text-embedding-3-small`, and upserts to Pinecone serverless. The Diagnoser retrieves top-4 chunks with cosine distance threshold `RAG_MATCH_DISTANCE_MAX` (default 0.45). Exceeding the threshold sets `no_runbook_match=True`, which instructs the Action Selector to prefer `create_pr_fix` or `noop` over destructive actions.

### API (`api/main.py`)

Four endpoints: `GET /health`, `POST /incident`, `GET /incidents`, `GET /metrics/summary`. History is in-memory with an asyncio lock — not persisted across restarts.

## Key Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | _(empty)_ | Enables LLM diagnosis/action; empty = offline mode |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM for diagnosis + action selection |
| `PINECONE_API_KEY` | _(empty)_ | Enables vector retrieval; empty = heuristic mode |
| `PINECONE_INDEX_NAME` | `aiops-runbooks` | Pinecone index for runbooks |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `RAG_MATCH_DISTANCE_MAX` | `0.45` | Cosine distance ceiling; higher = less strict retrieval |
| `CORRELATION_FLUSH_EVENTS` | `2` | Events per trace before flushing as an incident |

## No Test Suite Yet

No testing framework is currently integrated. The README roadmap lists guardrail truth-table unit tests and graph-level integration tests as the top two priorities. When adding tests, the guardrail is the highest-value first target (destructive × confidence matrix).

## Commit Conventions

Always use Conventional Commits format: type: short description in present tense, lowercase

Types:
- feat: new feature or capability
- fix: bug fix
- test: adding or updating tests
- refactor: code change that does not add features or fix bugs
- docs: README or documentation only
- chore: tooling, deps, config (no production code)

Examples:
- feat: add confidence threshold validation to guardrail layer
- fix: handle kafka consumer rebalance during correlation window
- test: add unit tests for guardrail confidence threshold logic
- refactor: extract trace correlation logic into dedicated module
- docs: reframe mock tools as intentional safe-by-design decision

Rules:
- One logical change per commit — never batch unrelated changes
- Never commit directly to main — use feature branches
- Branch naming: type/short-description (e.g. test/guardrail-unit-tests)

## Git Commit Rules

Never add Co-Authored-By trailers to commits.
Do not include any Claude or Anthropic attribution in commit messages.
Commits must appear as authored solely by the developer.