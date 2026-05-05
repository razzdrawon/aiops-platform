"""
Compare two eval runs to track agent improvement over time.

Usage:
    python -m evals.report baseline.json current.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def compare(baseline: dict, current: dict) -> None:
    bm = baseline["metrics"]
    cm = current["metrics"]

    def delta(key: str) -> str:
        diff = cm[key] - bm[key]
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.1%}" if isinstance(diff, float) else f"{sign}{diff}"

    print("\n" + "=" * 60)
    print("  EVAL COMPARISON")
    print("=" * 60)
    print(f"  {'Metric':<25} {'Baseline':>10} {'Current':>10} {'Delta':>10}")
    print(f"  {'-'*55}")

    for key, label in [
        ("overall_accuracy", "Overall accuracy"),
        ("action_accuracy", "Action accuracy"),
        ("blocked_accuracy", "Blocked accuracy"),
    ]:
        b = f"{bm[key]:.1%}"
        c = f"{cm[key]:.1%}"
        d = delta(key)
        arrow = "↑" if cm[key] > bm[key] else ("↓" if cm[key] < bm[key] else "→")
        print(f"  {label:<25} {b:>10} {c:>10} {arrow} {d:>8}")

    print(f"\n  {'Class':<20} {'Baseline':>10} {'Current':>10} {'Delta':>10}")
    print(f"  {'-'*55}")
    all_classes = set(bm["per_class"]) | set(cm["per_class"])
    for cls in sorted(all_classes):
        b_acc = bm["per_class"].get(cls, {}).get("accuracy", 0)
        c_acc = cm["per_class"].get(cls, {}).get("accuracy", 0)
        diff = c_acc - b_acc
        sign = "+" if diff >= 0 else ""
        arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
        print(f"  {cls:<20} {b_acc:>9.0%} {c_acc:>10.0%} {arrow} {sign}{diff:.0%}")

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m evals.report baseline.json current.json")
        sys.exit(1)
    baseline = load(sys.argv[1])
    current = load(sys.argv[2])
    compare(baseline, current)
