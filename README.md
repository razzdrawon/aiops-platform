# AIOps Platform — Autonomous Incident Resolution

> Reduce MTTR and close incidents without humans — by combining streaming telemetry, RAG over internal runbooks, and a gated autonomous agent.

E-commerce platforms lose revenue every minute an incident stays open. This system ingests live logs, metrics, and traces, correlates them by `trace_id`, diagnoses the root cause with an LLM backed by a runbook knowledge base, and executes remediation — automatically, with guardrails.

**79% of simulated incidents resolved without human intervention. Average MTTR: 41 seconds.**

---

## What it does

| Stage | What happens |
|-------|-------------|
| **Ingest** | Kafka consumer ingests streaming logs, metrics, and OTel traces from a live e-commerce simulator |
| **Correlate** | Events grouped by `trace_id` before diagnosis — signal quality over noise |
| **Diagnose** | LLM + RAG over Pinecone runbook index identifies root cause with a confidence score |
| **Gate** | Deterministic guardrails block destructive actions if `confidence < 0.85` — LLM proposes, rules decide |
| **Act** | Agent executes rollback / restart / scale via tool registry; reports resolution |

## Stack

**Python · FastAPI · Kafka · LangGraph · Pinecone · OpenAI · OpenTelemetry · Docker**

## Sample response

```json
{
  "incident_id": "inc-7f3a1b",
  "status": "resolved",
  "diagnosis": {
    "root_cause": "connection pool exhaustion on checkout-db",
    "confidence": 0.91,
    "runbook_refs": ["db-pool-exhaustion.md", "checkout-slo.md"]
  },
  "action_taken": {
    "tool": "restart_service",
    "destructive": true,
    "guardrail": "PASSED — confidence 0.91 ≥ 0.85"
  },
  "mttr_seconds": 38
}
```

## Quick start

```bash
cp .env.example .env          # Add OPENAI_API_KEY, PINECONE_API_KEY
pip install -r requirements.txt
docker compose up -d           # Kafka + Zookeeper
python -m knowledge.indexer    # Index runbooks into Pinecone
```

Then run simulator, ingestion consumer, and API in separate terminals — see [docs/local-setup.md](docs/local-setup.md).

## Docs

- [Architecture & design decisions](docs/architecture.md)
- [Guardrails design](docs/guardrails.md)
- [Local setup](docs/local-setup.md)