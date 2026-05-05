"""
Evaluation runner — measures agent accuracy against synthetic incident cases.

Usage:
    python -m evals.runner                  # run all cases, print report
    python -m evals.runner --output results.json   # also save raw results

Each case defines the expected action and whether it should be blocked.
The runner compares expected vs actual and computes accuracy metrics.

Runs in offline/heuristic mode by default (no API keys needed).
Set OPENAI_API_KEY and PINECONE_API_KEY in .env to run in LLM mode.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.agent.graph import run_incident_graph

CASES_FILE = Path(__file__).parent / "cases" / "cases.json"


@dataclass
class EvalResult:
    case_id: str
    incident_class: str
    title: str
    expected_action: str
    expected_blocked: bool
    actual_action: str
    actual_blocked: bool
    action_correct: bool
    blocked_correct: bool
    duration_ms: int
    error: str | None = None


async def run_case(case: dict) -> EvalResult:
    start = time.perf_counter()
    error = None
    actual_action = "error"
    actual_blocked = False

    try:
        result = await run_incident_graph(case["title"], case["signals"])
        actual_action = (result.get("action") or {}).get("action", "error")
        actual_blocked = (result.get("guardrail_result") or {}).get("blocked", False)
    except Exception as exc:
        error = str(exc)

    duration_ms = int((time.perf_counter() - start) * 1000)

    return EvalResult(
        case_id=case["id"],
        incident_class=case["incident_class"],
        title=case["title"],
        expected_action=case["expected_action"],
        expected_blocked=case["expected_blocked"],
        actual_action=actual_action,
        actual_blocked=actual_blocked,
        action_correct=actual_action == case["expected_action"],
        blocked_correct=actual_blocked == case["expected_blocked"],
        duration_ms=duration_ms,
        error=error,
    )


async def run_all(cases: list[dict]) -> list[EvalResult]:
    results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i:2}/{len(cases)}] {case['id']:<10} {case['title'][:55]}", end="", flush=True)
        result = await run_case(case)
        status = "✓" if result.action_correct and result.blocked_correct else "✗"
        print(f"  {status}  ({result.duration_ms}ms)")
        results.append(result)
    return results


def compute_metrics(results: list[EvalResult]) -> dict:
    total = len(results)
    if total == 0:
        return {}

    action_correct = sum(1 for r in results if r.action_correct)
    blocked_correct = sum(1 for r in results if r.blocked_correct)
    both_correct = sum(1 for r in results if r.action_correct and r.blocked_correct)
    errors = sum(1 for r in results if r.error)

    # Per-class breakdown
    classes: dict[str, dict] = {}
    for r in results:
        cls = r.incident_class
        if cls not in classes:
            classes[cls] = {"total": 0, "correct": 0}
        classes[cls]["total"] += 1
        if r.action_correct and r.blocked_correct:
            classes[cls]["correct"] += 1

    per_class = {
        cls: {
            "accuracy": round(v["correct"] / v["total"], 3),
            "correct": v["correct"],
            "total": v["total"],
        }
        for cls, v in classes.items()
    }

    avg_duration = sum(r.duration_ms for r in results) / total

    return {
        "total_cases": total,
        "action_accuracy": round(action_correct / total, 3),
        "blocked_accuracy": round(blocked_correct / total, 3),
        "overall_accuracy": round(both_correct / total, 3),
        "errors": errors,
        "avg_duration_ms": round(avg_duration),
        "per_class": per_class,
    }


def print_report(metrics: dict, results: list[EvalResult]) -> None:
    print("\n" + "=" * 60)
    print("  EVAL REPORT")
    print("=" * 60)
    print(f"  Total cases       : {metrics['total_cases']}")
    print(f"  Action accuracy   : {metrics['action_accuracy']:.1%}")
    print(f"  Blocked accuracy  : {metrics['blocked_accuracy']:.1%}")
    print(f"  Overall accuracy  : {metrics['overall_accuracy']:.1%}")
    print(f"  Avg duration      : {metrics['avg_duration_ms']}ms")
    print(f"  Errors            : {metrics['errors']}")

    print("\n  Per class:")
    for cls, data in metrics["per_class"].items():
        bar = "█" * data["correct"] + "░" * (data["total"] - data["correct"])
        print(f"    {cls:<20} {bar}  {data['correct']}/{data['total']}  ({data['accuracy']:.0%})")

    failures = [r for r in results if not (r.action_correct and r.blocked_correct)]
    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for r in failures:
            print(f"    {r.case_id:<10} expected action={r.expected_action} blocked={r.expected_blocked}")
            print(f"             actual   action={r.actual_action} blocked={r.actual_blocked}")
            if r.error:
                print(f"             error: {r.error}")

    print("=" * 60)


async def main(output_path: str | None = None) -> None:
    cases = json.loads(CASES_FILE.read_text())
    print(f"\nRunning {len(cases)} eval cases (offline/heuristic mode)...\n")

    results = await run_all(cases)
    metrics = compute_metrics(results)
    print_report(metrics, results)

    if output_path:
        output = {
            "metrics": metrics,
            "results": [asdict(r) for r in results],
        }
        Path(output_path).write_text(json.dumps(output, indent=2))
        print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Save raw results to JSON file")
    args = parser.parse_args()
    asyncio.run(main(args.output))
