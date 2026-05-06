"""
LangGraph orchestration: linear decision pipeline with an explicit guardrail branch.
Async nodes keep parity with aiokafka/FastAPI workloads under load.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from app.agent.guardrails import validate_action
from app.agent.tools import dispatch
from app.knowledge.indexer import search_runbooks

load_dotenv()

# gpt-4o-mini pricing (per token)
_COST_PER_INPUT_TOKEN = 0.150 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 0.600 / 1_000_000


def _token_span(usage_metadata: dict[str, int] | None) -> dict[str, Any] | None:
    """Build a token summary dict from LangChain usage_metadata."""
    if not usage_metadata:
        return None
    inp = usage_metadata.get("input_tokens", 0)
    out = usage_metadata.get("output_tokens", 0)
    cost = round(inp * _COST_PER_INPUT_TOKEN + out * _COST_PER_OUTPUT_TOKEN, 8)
    return {"input": inp, "output": out, "cost_usd": cost}


def _node_span(
    node: str, perf_start: float, wall_start: float, tokens: dict | None = None
) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": datetime.fromtimestamp(wall_start, tz=timezone.utc).isoformat(),
        "duration_ms": int((time.perf_counter() - perf_start) * 1000),
        "tokens": tokens,
    }


class IncidentState(TypedDict, total=False):
    incident_id: str
    title: str
    signals: dict[str, Any]
    detector: dict[str, Any]
    diagnosis: dict[str, Any]
    action: dict[str, Any]
    guardrail_result: dict[str, Any]
    execution: dict[str, Any]
    report: str
    trace: list[dict[str, Any]]


class DiagnosisLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str
    suspected_root_cause: str
    matched_runbook_titles: list[str] = Field(default_factory=list)
    no_runbook_match: bool


class ActionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    service: str = Field(default="")
    target_revision: str = Field(default="")
    replicas: int = Field(default=0)
    reason: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    branch: str = Field(default="")


class ActionLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["rollback", "restart_service", "scale_up", "create_pr_fix", "noop"]
    params: ActionParams = Field(default_factory=ActionParams)
    destructive: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


def _heuristic_class(signals: dict[str, Any], title: str) -> str:
    t = title.lower()
    if signals.get("oom") or "oom" in t:
        return "oom"
    if signals.get("deploy_failed") or "deploy" in t:
        return "deploy_failure"
    if signals.get("db_cpu") or "database" in t or "db" in t:
        return "db_overload"
    er = float(signals.get("error_rate") or 0)
    p95 = float(signals.get("p95_ms") or 0)
    if er > 0.05 or "error" in t:
        return "high_error_rate"
    if p95 > 1500 or "latency" in t:
        return "latency_spike"
    return "unknown"


async def detector_node(state: IncidentState) -> dict[str, Any]:
    t0 = time.perf_counter()
    wall0 = time.time()
    signals = state.get("signals") or {}
    title = state.get("title") or "incident"
    classification = _heuristic_class(signals, title)
    span = _node_span("detector", t0, wall0)
    return {
        "detector": {
            "classification": classification,
            "severity_hint": "high" if float(signals.get("error_rate") or 0) > 0.1 else "medium",
        },
        "trace": (state.get("trace") or []) + [span],
    }


async def diagnoser_node(state: IncidentState) -> dict[str, Any]:
    t0 = time.perf_counter()
    wall0 = time.time()
    title = state.get("title", "")
    signals = state.get("signals") or {}
    detector = state.get("detector") or {}
    docs, matched = await search_runbooks(f"{title} {signals} {detector.get('classification')}")

    if not os.getenv("OPENAI_API_KEY"):
        span = _node_span("diagnoser", t0, wall0)
        return {
            "diagnosis": {
                "narrative": "OpenAI disabled — heuristic diagnosis from signals and class only (no LLM).",
                "suspected_root_cause": detector.get("classification", "unknown"),
                "matched_runbook_titles": [d.metadata.get("source", "") for d in docs[:3]],
                # Offline mode skips vector confidence; let deterministic heuristics propose actions.
                "no_runbook_match": False,
            },
            "trace": (state.get("trace") or []) + [span],
        }

    context = "\n\n".join(
        f"### {d.metadata.get('source')}\n{d.page_content[:1200]}" for d in docs[:4]
    ) or "(no retrieval context — index may be empty)"

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    structured = llm.with_structured_output(DiagnosisLLM, include_raw=True)
    prompt = [
        SystemMessage(
            content=(
                "You are an SRE copilot. Use the runbook excerpts when relevant. "
                "Set no_runbook_match=true when excerpts do not plausibly apply to the incident."
            )
        ),
        HumanMessage(
            content=(
                f"Incident title: {title}\nSignals: {signals}\nHeuristic class: {detector}\n\n"
                f"Runbook excerpts:\n{context}\n\nReturn structured diagnosis."
            )
        ),
    ]
    result = await structured.ainvoke(prompt)
    parsed: DiagnosisLLM = result["parsed"]
    usage = getattr(result.get("raw"), "usage_metadata", None)
    if not matched:
        parsed = parsed.model_copy(update={"no_runbook_match": True})
    span = _node_span("diagnoser", t0, wall0, _token_span(usage))
    return {
        "diagnosis": parsed.model_dump(),
        "trace": (state.get("trace") or []) + [span],
    }


async def action_selector_node(state: IncidentState) -> dict[str, Any]:
    t0 = time.perf_counter()
    wall0 = time.time()
    diagnosis = state.get("diagnosis") or {}
    detector = state.get("detector") or {}
    signals = state.get("signals") or {}

    if not os.getenv("OPENAI_API_KEY"):
        if diagnosis.get("no_runbook_match"):
            action = {
                "action": "create_pr_fix",
                "params": {
                    "title": "Investigate unmatched incident",
                    "description": str(diagnosis),
                    "branch": f"incident/{state.get('incident_id', 'unknown')[:8]}",
                },
                "destructive": False,
                "confidence": 0.55,
                "rationale": "No API / weak retrieval — safest path is human follow-up.",
            }
        else:
            cls = detector.get("classification")
            if cls in {"high_error_rate", "deploy_failure"}:
                action = {
                    "action": "rollback",
                    "params": {"service": signals.get("service", "checkout"), "target_revision": "stable-1"},
                    "destructive": True,
                    "confidence": 0.7,
                    "rationale": "Heuristic rollback for error/deploy class (expected to be blocked if confidence low).",
                }
            elif cls == "latency_spike":
                action = {
                    "action": "scale_up",
                    "params": {"service": signals.get("service", "checkout"), "replicas": 5},
                    "destructive": False,
                    "confidence": 0.72,
                    "rationale": "Heuristic scale for latency.",
                }
            else:
                action = {
                    "action": "noop",
                    "params": {"reason": "Insufficient deterministic mapping."},
                    "destructive": False,
                    "confidence": 0.5,
                    "rationale": "No strong heuristic action.",
                }
        span = _node_span("action_selector", t0, wall0)
        return {"action": action, "trace": (state.get("trace") or []) + [span]}

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    structured = llm.with_structured_output(ActionLLM, include_raw=True)
    prompt = [
        SystemMessage(
            content=(
                "Pick one remediation action. Mark destructive=true for rollback/restart that drops traffic. "
                "If no_runbook_match was true, prefer create_pr_fix or noop — avoid destructive tools unless evidence is strong. "
                "When proposing rollback/restart, confidence must exceed 0.85 or it will be blocked."
            )
        ),
        HumanMessage(
            content=(
                f"Detector: {detector}\nDiagnosis: {diagnosis}\nSignals: {signals}\n"
                "Return structured action with params matching the tool signature:\n"
                "rollback(service,target_revision); restart_service(service,reason); "
                "scale_up(service,replicas); create_pr_fix(title,description,branch); noop(reason)."
            )
        ),
    ]
    result = await structured.ainvoke(prompt)
    parsed: ActionLLM = result["parsed"]
    usage = getattr(result.get("raw"), "usage_metadata", None)
    span = _node_span("action_selector", t0, wall0, _token_span(usage))
    return {"action": parsed.model_dump(), "trace": (state.get("trace") or []) + [span]}


async def guardrail_node(state: IncidentState) -> dict[str, Any]:
    t0 = time.perf_counter()
    wall0 = time.time()
    action = state.get("action") or {}
    span = _node_span("guardrail", t0, wall0)
    return {
        "guardrail_result": validate_action(action),
        "trace": (state.get("trace") or []) + [span],
    }


def route_after_guardrail(state: IncidentState) -> Literal["executor", "reporter"]:
    gr = state.get("guardrail_result") or {}
    if gr.get("blocked"):
        return "reporter"
    return "executor"


async def executor_node(state: IncidentState) -> dict[str, Any]:
    t0 = time.perf_counter()
    wall0 = time.time()
    action = state.get("action") or {}
    name = action.get("action", "noop")
    params = action.get("params") or {}
    try:
        message = await dispatch(str(name), dict(params))
    except TypeError:
        message = await dispatch("noop", {"reason": f"bad params for {name}"})
    span = _node_span("executor", t0, wall0)
    return {
        "execution": {"tool": name, "message": message},
        "trace": (state.get("trace") or []) + [span],
    }


async def reporter_node(state: IncidentState) -> dict[str, Any]:
    t0 = time.perf_counter()
    wall0 = time.time()
    gr = state.get("guardrail_result") or {}
    ex = state.get("execution") or {}
    action = state.get("action") or {}
    diagnosis = state.get("diagnosis") or {}

    if gr.get("blocked"):
        report = (
            f"Incident {state.get('incident_id')}: blocked by guardrails ({gr.get('reason')}). "
            f"Proposed action={action.get('action')} destructive={action.get('destructive')} "
            f"confidence={action.get('confidence')}. Diagnosis summary: {diagnosis.get('narrative', '')}"
        )
    else:
        report = (
            f"Incident {state.get('incident_id')}: executed {ex.get('tool')} -> {ex.get('message')}. "
            f"Diagnosis: {diagnosis.get('narrative', '')}"
        )

    span = _node_span("reporter", t0, wall0)
    prior = state.get("trace") or []
    all_spans = prior + [span]

    # Roll up totals
    total_input = sum((s["tokens"] or {}).get("input", 0) for s in all_spans)
    total_output = sum((s["tokens"] or {}).get("output", 0) for s in all_spans)
    total_cost = round(
        total_input * _COST_PER_INPUT_TOKEN + total_output * _COST_PER_OUTPUT_TOKEN, 8
    )
    total_ms = sum(s["duration_ms"] for s in all_spans)

    trace = {
        "nodes": all_spans,
        "total_tokens": {"input": total_input, "output": total_output, "cost_usd": total_cost},
        "total_duration_ms": total_ms,
    }
    return {"report": report, "trace": trace}


def build_graph():
    graph = StateGraph(IncidentState)
    graph.add_node("detector", detector_node)
    graph.add_node("diagnoser", diagnoser_node)
    graph.add_node("action_selector", action_selector_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reporter", reporter_node)

    graph.add_edge(START, "detector")
    graph.add_edge("detector", "diagnoser")
    graph.add_edge("diagnoser", "action_selector")
    graph.add_edge("action_selector", "guardrail")
    graph.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {"executor": "executor", "reporter": "reporter"},
    )
    graph.add_edge("executor", "reporter")
    graph.add_edge("reporter", END)
    return graph.compile()


_compiled = None


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled


async def run_incident_graph(title: str, signals: dict[str, Any] | None = None) -> IncidentState:
    incident_id = str(uuid.uuid4())
    graph = get_compiled_graph()
    initial: IncidentState = {
        "incident_id": incident_id,
        "title": title,
        "signals": signals or {},
    }
    return await graph.ainvoke(initial)


__all__ = ["run_incident_graph", "build_graph", "IncidentState"]
