# Architecture: AIOps Incident Resolution Platform

Audience: senior engineers and engineering managers evaluating this as a portfolio project.

---

## System Overview

The platform automates incident triage and remediation for a synthetic e-commerce service. Signals flow from an instrumented checkout simulator through Kafka-based correlation, into a LangGraph decision pipeline that diagnoses root cause, selects a remediation action, enforces safety guardrails, and executes the result — all with a structured audit trail.

```
Simulator (:8010)
  │  OTel-instrumented FastAPI; emits log + metric events per request
  │  ~15% error rate, ~10% high-latency; realistic trace-correlated signal pairs
  ▼
Kafka: ecommerce.events
  │
Ingestion Consumer
  │  Buffers events by trace_id; flushes correlated batch when threshold reached
  │  Publishes structured batch (trace_id, events[], correlation_ts)
  ▼
Kafka: incidents.correlated
  │
Control API (:8000)
  │  POST /incident → run_incident_graph()
  │  In-memory history; exposes MTTR + block-rate via GET /metrics/summary
  ▼
LangGraph Pipeline
  Detector → Diagnoser → Action Selector → Guardrail
                                                │
                                    blocked ────┤
                                                │ allowed
                                            Executor
                                                │
                                           Reporter (always runs)
```

---

## Why Event-Driven

Pulling incidents on a polling interval introduces arbitrary lag and creates a tight coupling between the source and the decision pipeline. The Kafka topology decouples production rate from consumption rate: the simulator and consumer are independently deployable, and back-pressure is handled by Kafka's log retention rather than a synchronous request chain.

The second reason is multi-signal correlation. A single checkout failure produces two Kafka messages: a log event and a metric event, both sharing the same `trace_id`. A polling model would need to join those in a query; Kafka lets the consumer buffer and flush them as a single correlated batch. This is the foundation for the correlation step.

---

## Correlation Before Diagnosis

A raw log event like `checkout status=payment_timeout` does not carry enough signal to distinguish "this one request timed out" from "the payment service is degraded." The correlation step holds events by `trace_id` until a configurable flush threshold (`CORRELATION_FLUSH_EVENTS`, default 2) is met, then publishes a batch that includes both the error log and the latency metric together.

This matters for diagnosis accuracy. When the Diagnoser and the RAG retrieval receive the correlated batch — containing error type, latency value, service name, and timestamp — they have enough context to retrieve relevant runbook sections and form a specific root-cause hypothesis. Without correlation, the pipeline would diagnose individual signal events, most of which are too sparse to trigger confident action proposals.

In production, the threshold and windowing policy would be replaced with a watermark-based time window (e.g., flush after 30 s or N events, whichever comes first), but the structural contract — correlated batch as the pipeline's unit of work — remains the same.

---

## LangGraph Orchestration

The pipeline is a `StateGraph` over a single `IncidentState` TypedDict. Each node is an async function that receives the full state and returns a partial update; LangGraph merges updates into the shared state. The only routing decision is a conditional edge after Guardrail: blocked → Reporter directly, allowed → Executor → Reporter.

Why LangGraph over a plain async function chain:

1. **Explicit state contract.** `IncidentState` is the schema. Every node declares what it reads and writes. There is no hidden mutable context.
2. **Replaceable nodes.** Swapping the heuristic Detector for an ML classifier, or the mock Executor for a real Kubernetes client, is a node-level change with no impact on the rest of the graph.
3. **Conditional routing as first-class graph topology.** The guardrail branch is encoded in the graph definition, not buried in an if-else inside an executor function. The blocked path is visible in the graph structure.
4. **Async throughout.** All six nodes are `async def`. The graph uses `ainvoke`, keeping parity with the aiokafka and FastAPI async event loops.

The single conditional edge is intentional. More branches add more paths through the graph, more state combinations to reason about, and more surface area for the LLM to exploit by nudging state in earlier nodes. This design keeps the LLM's influence bounded to Diagnoser and Action Selector; all routing is deterministic Python.

---

## Guardrails Design

```python
# agents/guardrails.py
def validate_action(action: dict) -> dict:
    if action["destructive"] and action["confidence"] <= 0.85:
        return {"blocked": True, "reason": "destructive actions require confidence > 0.85"}
    return {"blocked": False, "reason": "ok"}
```

The guardrail is a pure Python function with no LLM involvement. It runs as a dedicated graph node between Action Selector and Executor, so it cannot be bypassed by prompt injection or unexpected LLM output.

The design reflects a specific threat model: the LLM may propose a destructive action (rollback, restart) with insufficient evidence. Destructiveness is explicitly declared by the Action Selector in its structured output (`destructive: bool`). The guardrail enforces that any destructive proposal must carry `confidence > 0.85`; anything lower is blocked and routed directly to the Reporter without execution.

A second mechanism reinforces this: when the RAG retrieval returns no confident runbook match (`no_runbook_match=True`), the Action Selector's system prompt instructs it to prefer `create_pr_fix` or `noop`. This biases the LLM toward low-risk actions before the guardrail even evaluates. The guardrail is the hard stop; the prompt instruction is an early filter that reduces the frequency of guardrail interventions.

The strict `>` (not `>=`) at 0.85 is intentional — a model stating exactly 0.85 confidence is not considered sufficient.

**What this does not cover in production:** rate limits on action frequency, cross-incident deduplication (don't restart the same service twice in 5 minutes), and human-in-the-loop approval for any destructive action regardless of confidence. Those are extension points, not gaps in this architecture.

---

## RAG Over Runbooks

Five runbooks cover the incident classes the Detector recognizes: OOM, deploy failure, DB overload, high error rate, latency spike. At index time, each runbook is chunked into 900-character segments with 120-character overlap, embedded with `text-embedding-3-small` (1536 dimensions), and upserted into a Pinecone serverless index with cosine similarity.

At query time, the Diagnoser builds a retrieval query from the incident title, signals, and heuristic classification, then retrieves the top-4 chunks. The match is considered high-confidence only if the best cosine distance is ≤ 0.45 (`RAG_MATCH_DISTANCE_MAX`). Exceeding that threshold sets `no_runbook_match=True`, which propagates forward to bias the Action Selector away from destructive options.

The retrieval query concatenates `title + signals + classification` rather than the title alone. The heuristic classification (e.g., `db_overload`) is a token the embeddings model can match against runbook section headers directly, improving recall over a raw title like "High error rate in checkout service."

The cosine distance threshold is the main tuning knob. At 0.45 it errs toward false negatives (no match) over false positives (wrong runbook match), which is conservative: an unmatched incident gets a `create_pr_fix` or `noop`, not a destructive action.

---

## Production Extension Points

The architecture is designed so that each layer can be upgraded independently without restructuring the pipeline.

**Correlation window.** Replace the event-count flush threshold with a time-window watermark (Kafka Streams or Faust). The downstream contract — a `correlated` batch published to `incidents.correlated` — is unchanged.

**Real remediation tools.** `TOOL_REGISTRY` in `agents/tools.py` maps action names to async functions. Each mock is a ~10-line stub. Replacing `rollback` with a GitHub Actions workflow dispatch or a Kubernetes rollout rollback is a drop-in substitution. The guardrail evaluates the same `destructive + confidence` fields regardless.

**Guardrail policies.** `validate_action()` is a single function. Extending it to enforce rate limits, cross-incident deduplication, or service-specific confidence floors requires adding logic to one file with no graph changes.

**Persistence.** The API uses an in-memory list with an asyncio lock. Production replacement: write each `IncidentState` to Postgres (or append to S3) after `reporter_node` completes. The graph returns the full state; serialization is a post-graph step.

**Observability.** The simulator is already OTel-instrumented (traces and metrics). Wiring the pipeline nodes to emit spans via `opentelemetry-api` would give end-to-end trace context from the Kafka message to the executed tool — no architectural change, just instrumentation.

**Model substitution.** `OPENAI_MODEL` controls the LLM. Both Diagnoser and Action Selector use `with_structured_output` against Pydantic schemas (`DiagnosisLLM`, `ActionLLM`). Any LangChain-compatible chat model that supports structured output is a drop-in replacement.

**Offline / CI mode.** When `OPENAI_API_KEY` or `PINECONE_API_KEY` is absent, Diagnoser and Action Selector fall back to deterministic heuristics. The full graph still executes, making end-to-end integration tests runnable in CI without cloud credentials.
