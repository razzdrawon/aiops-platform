"""
LangGraph orchestration: linear decision pipeline with an explicit guardrail branch.
Async nodes keep parity with aiokafka/FastAPI workloads under load.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from agents.guardrails import validate_action
from agents.tools import dispatch
from knowledge.indexer import search_runbooks

load_dotenv()


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
    signals = state.get("signals") or {}
    title = state.get("title") or "incident"
    classification = _heuristic_class(signals, title)
    return {
        "detector": {
            "classification": classification,
            "severity_hint": "high" if float(signals.get("error_rate") or 0) > 0.1 else "medium",
        }
    }


async def diagnoser_node(state: IncidentState) -> dict[str, Any]:
    title = state.get("title", "")
    signals = state.get("signals") or {}
    detector = state.get("detector") or {}
    docs, matched = await search_runbooks(f"{title} {signals} {detector.get('classification')}")

    if not os.getenv("OPENAI_API_KEY"):
        return {
            "diagnosis": {
                "narrative": "OpenAI disabled — heuristic diagnosis from signals and class only (no LLM).",
                "suspected_root_cause": detector.get("classification", "unknown"),
                "matched_runbook_titles": [d.metadata.get("source", "") for d in docs[:3]],
                # Offline mode skips vector confidence; let deterministic heuristics propose actions.
                "no_runbook_match": False,
            }
        }

    context = "\n\n".join(
        f"### {d.metadata.get('source')}\n{d.page_content[:1200]}" for d in docs[:4]
    ) or "(no retrieval context — index may be empty)"

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    structured = llm.with_structured_output(DiagnosisLLM)
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
    parsed: DiagnosisLLM = await structured.ainvoke(prompt)
    if not matched:
        parsed = parsed.model_copy(update={"no_runbook_match": True})
    return {"diagnosis": parsed.model_dump()}


async def action_selector_node(state: IncidentState) -> dict[str, Any]:
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
        return {"action": action}

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    structured = llm.with_structured_output(ActionLLM)
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
    parsed: ActionLLM = await structured.ainvoke(prompt)
    return {"action": parsed.model_dump()}


async def guardrail_node(state: IncidentState) -> dict[str, Any]:
    action = state.get("action") or {}
    return {"guardrail_result": validate_action(action)}


def route_after_guardrail(state: IncidentState) -> Literal["executor", "reporter"]:
    gr = state.get("guardrail_result") or {}
    if gr.get("blocked"):
        return "reporter"
    return "executor"


async def executor_node(state: IncidentState) -> dict[str, Any]:
    action = state.get("action") or {}
    name = action.get("action", "noop")
    params = action.get("params") or {}
    try:
        message = await dispatch(str(name), dict(params))
    except TypeError:
        message = await dispatch("noop", {"reason": f"bad params for {name}"})
    return {"execution": {"tool": name, "message": message}}


async def reporter_node(state: IncidentState) -> dict[str, Any]:
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
    return {"report": report}


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
