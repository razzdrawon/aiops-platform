"""
Remediation tools are mocked: same signatures and async shape as production integrations
(API clients, Kubernetes, CI) but only log structured intent for safe local demos.
"""

from __future__ import annotations

import json
from typing import Any


def _log_tool(name: str, **kwargs: Any) -> str:
    payload = {"tool": name, "intent": kwargs}
    print(f"[TOOL] {json.dumps(payload, default=str)}")
    return f"{name} acknowledged (mock)"


async def rollback(service: str, target_revision: str) -> str:
    _log_tool("rollback", service=service, target_revision=target_revision)
    return "rollback scheduled (mock)"


async def restart_service(service: str, reason: str) -> str:
    _log_tool("restart_service", service=service, reason=reason)
    return "restart issued (mock)"


async def scale_up(service: str, replicas: int) -> str:
    _log_tool("scale_up", service=service, replicas=replicas)
    return "scale-up applied (mock)"


async def create_pr_fix(title: str, description: str, branch: str) -> str:
    _log_tool("create_pr_fix", title=title, description=description, branch=branch)
    return "PR opened (mock)"


async def noop(reason: str = "unspecified") -> str:
    _log_tool("noop", reason=reason)
    return "no automated change (mock)"


TOOL_REGISTRY = {
    "rollback": rollback,
    "restart_service": restart_service,
    "scale_up": scale_up,
    "create_pr_fix": create_pr_fix,
    "noop": noop,
}


async def dispatch(action_name: str, params: dict[str, Any]) -> str:
    if action_name not in TOOL_REGISTRY:
        return await noop(reason=f"unknown action {action_name}")
    fn = TOOL_REGISTRY[action_name]
    try:
        return await fn(**params)
    except TypeError:
        return await noop(reason=f"bad params for {action_name}: {params}")
