# Validation Guide

Step-by-step instructions for running and verifying each phase of the system.

---

## Phase 1 — Foundation

### Prerequisites

- Python 3.11+
- Docker (for PostgreSQL and Kafka)
- No API keys needed for offline mode

### Setup

```bash
# Clone and enter the project
git clone git@github.com:razzdrawon/aiops-platform.git
cd aiops-platform

# Create virtual environment with Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
```

### Start infrastructure

```bash
# Terminal 1 — PostgreSQL (background)
docker-compose up -d db

# Apply migrations
alembic upgrade head
```

### Run unit tests (no DB, no API keys)

```bash
pytest tests/unit/ -v
```

Expected: **40 passed in ~1s**

### Run integration tests (requires PostgreSQL)

```bash
# Create test database
docker-compose exec db psql -U aiops_user -d aiops -c "CREATE DATABASE aiops_test;"

# Run migrations on test DB
TEST_DATABASE_URL=postgresql+asyncpg://aiops_user:aiops_pass@localhost:5432/aiops_test \
  alembic upgrade head

# Run integration tests
TEST_DATABASE_URL=postgresql+asyncpg://aiops_user:aiops_pass@localhost:5432/aiops_test \
  pytest tests/integration/ -v
```

Expected: **12 passed in ~45s** (each test runs the full LangGraph pipeline in offline mode)

### Start the API

```bash
# Terminal 2 — API server
uvicorn app.api.main:app --port 8000 --reload
```

### Verify the pipeline end-to-end

```bash
# Trigger an incident — runs the full agent pipeline
curl -s -X POST http://localhost:8000/incident \
  -H "Content-Type: application/json" \
  -d '{"title": "High error rate on checkout", "signals": {"error_rate": 0.12, "service": "checkout"}}' \
  | python3 -m json.tool
```

Expected response includes:
- `incident_id` — UUID persisted in PostgreSQL
- `status` — `"resolved"` or `"blocked"`
- `graph.detector.classification` — `"high_error_rate"`
- `graph.diagnosis.suspected_root_cause` — narrative from heuristic or LLM
- `graph.guardrail_result.blocked` — `false` (action was non-destructive)

```bash
# Verify persistence — incidents survive server restarts
curl -s http://localhost:8000/incidents | python3 -m json.tool

# Get a single incident by ID
curl -s http://localhost:8000/incidents/<incident_id> | python3 -m json.tool

# Metrics summary
curl -s http://localhost:8000/metrics/summary | python3 -m json.tool
```

### Test guardrail blocking

To see the guardrail in action, trigger an incident classified as a deploy failure — the heuristic action selector proposes `rollback` (destructive) with confidence 0.7, which is below the 0.85 threshold:

```bash
curl -s -X POST http://localhost:8000/incident \
  -H "Content-Type: application/json" \
  -d '{"title": "Deploy failure on checkout", "signals": {"deploy_failed": true, "service": "checkout"}}' \
  | python3 -m json.tool
```

Expected: `graph.guardrail_result.blocked: true`, `status: "blocked"`

### Test with LLM mode (optional — requires API keys)

Add your keys to `.env`:
```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
```

Index the runbooks into Pinecone (one-time):
```bash
python -m app.knowledge.indexer
```

Restart the API and trigger incidents — the diagnoser will now use RAG + GPT instead of heuristics.

---

## Terminals summary

| Terminal | What runs |
|---|---|
| 1 | `docker-compose up -d db` (background, stays running) |
| 2 | `uvicorn app.api.main:app --port 8000 --reload` |
| Any | `curl` commands and `pytest` |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `alembic upgrade head` fails | Make sure `db` container is running: `docker-compose up -d db` |
| `asyncpg` import error | Make sure you're using Python 3.11 venv: `python --version` |
| Integration tests timeout | The pipeline runs the full LangGraph graph per test — 45s is expected |
| Port 8000 already in use | Use `--port 8001` if order-platform is also running locally |
