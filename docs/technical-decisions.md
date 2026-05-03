# Technical Decisions

Key engineering decisions, the reasoning behind them, and the trade-offs accepted.

---

## 1. LangGraph over vanilla LangChain Agents

LangChain's standard agent loop is a ReAct-style loop: the LLM decides what to do next at each step. That's powerful for open-ended tasks but wrong here.

Incident remediation has a **fixed, auditable pipeline**:
```
detector → diagnoser → action_selector → guardrail → executor → reporter
```

The guardrail node must be deterministic Python — it cannot be a tool the LLM calls. With LangGraph, the graph topology is defined in code. The LLM influences node outputs but never controls which node runs next. That's a hard requirement for anything that touches production infrastructure.

**Key terms:** LangGraph, State Machine, Deterministic Routing, Agentic Systems.

---

## 2. Guardrails outside the LLM

The guardrail logic lives in `app/agent/guardrails.py` as plain Python:

```python
if destructive and confidence <= 0.85:
    return {"blocked": True, ...}
```

It is never a tool, never a prompt, never a memory the LLM can read or modify. This is intentional — the LLM proposes, the rules decide. An LLM cannot be prompt-injected into skipping a safety check it doesn't know exists.

The threshold is `> 0.85` (strictly greater than), not `>= 0.85`. This is also intentional — 0.85 exactly is blocked. Confidence values are continuous floats from the LLM; there is no natural reason to treat 0.85 as "safe enough."

**Key terms:** Guardrails, Deterministic Safety, Human-in-the-Loop, LLM Safety.

---

## 3. Graceful degradation without API keys

When `OPENAI_API_KEY` or `PINECONE_API_KEY` are absent, the pipeline falls back to heuristic detection and deterministic action selection. The full graph still runs — detector, diagnoser, action_selector, guardrail, executor, reporter — but using rule-based logic instead of LLM calls.

This enables:
- **Local development** without spending on API calls
- **CI/CD** where secrets are intentionally absent in test environments
- **Unit and integration tests** that verify behavior without mocking the LLM

The trade-off: heuristic mode is less accurate than LLM mode. That gap is measured by the evaluation framework (Phase 2).

**Key terms:** Graceful Degradation, Offline Mode, Testability, Cost Control.

---

## 4. JSONB columns for AI output instead of normalized tables

Incident data has several nested objects: `signals`, `diagnosis`, `action`, `guardrail`, `execution`. These could be normalized into separate tables with foreign keys.

We chose JSONB columns instead.

**Trade-offs:**

| | JSONB | Normalized tables |
|---|---|---|
| Schema migrations | Free — add fields to JSON without `ALTER TABLE` | Required for every new field |
| SQL filtering on nested fields | Requires JSON operators (`->`, `->>`) | Native SQL |
| Join complexity | None — incident is one row | Multiple joins |
| AI output shape | Semi-structured, evolves with prompts | Must be stable |
| Read pattern | Always reads the full incident | Could read partial data |

**Why JSONB wins here:** AI output is semi-structured by nature — the fields in `diagnosis` or `action` evolve as prompts change. Locking that into a normalized schema means a migration for every prompt tweak. The read pattern is always "give me the full incident" — there is no case where we need only the diagnosis without the action. And we never query `WHERE diagnosis->>'confidence' > 0.9` at the DB level — that filtering happens in the eval runner in Python.

**Key terms:** JSONB, Semi-structured Data, Schema Evolution, PostgreSQL.

---

## 5. RAG over fine-tuning for runbook knowledge

The diagnoser uses RAG (Retrieval-Augmented Generation): at inference time, it searches a Pinecone index for relevant runbook excerpts and injects them into the prompt.

The alternative is fine-tuning a model on runbook content.

**Why RAG:**
- Runbooks change frequently — a new runbook is indexed in seconds, no retraining
- Fine-tuning requires labeled examples and compute budget
- RAG is auditable — you can see exactly which chunks were retrieved for a given diagnosis
- The `no_runbook_match` flag gives the graph a signal when retrieval confidence is low, allowing it to choose safer actions

**Key terms:** RAG, Retrieval-Augmented Generation, Pinecone, Vector Search, Fine-tuning.

---

## 6. Abstract repository pattern for testability

`AbstractIncidentRepository` defines the interface. `SQLAlchemyIncidentRepository` implements it. Tests can inject a fake in-memory implementation without touching PostgreSQL.

```python
class FakeIncidentRepository(AbstractIncidentRepository):
    def __init__(self):
        self._store = {}

    async def save(self, incident):
        ...
    async def get_all(self):
        ...
```

This matters because integration tests are slow (they hit a real DB) and can't run offline. Unit tests that need the repository use the fake — they run in milliseconds with no infrastructure.

**Key terms:** Repository Pattern, Dependency Inversion, Testability, Fake vs Mock.

---

## 7. `app/` namespace for absolute imports

All application code lives under `app/`. Imports are always `from app.X import Y`.

The alternative — flat module layout (`from agents.graph import ...`) — only works when Python is run from the project root. A test runner, a script, or a Docker container that changes the working directory breaks silently.

Absolute imports under a single namespace work from anywhere.

**Key terms:** Python Packaging, Import Resolution, Namespace Packages.

---

## Glossary

| Term | Definition |
|---|---|
| **LangGraph** | Graph-based agent orchestration framework — nodes are functions, edges define control flow |
| **RAG** | Retrieval-Augmented Generation — inject retrieved documents into LLM context at inference time |
| **Guardrail** | Deterministic rule that gates LLM-proposed actions — lives outside the model |
| **Graceful degradation** | System continues to function (with reduced capability) when external dependencies are unavailable |
| **JSONB** | PostgreSQL binary JSON column type — supports indexing and operators on nested fields |
| **Offline mode** | Pipeline runs with heuristic logic when API keys are absent |
| **Abstract repository** | Interface that decouples application logic from the specific DB implementation |
| **Confidence threshold** | Minimum model-stated confidence required to allow destructive actions (> 0.85) |
| **MTTR** | Mean Time To Resolve — average time from incident creation to resolution |
| **Structured output** | LLM response constrained to a Pydantic schema — prevents free-form JSON that breaks parsers |
