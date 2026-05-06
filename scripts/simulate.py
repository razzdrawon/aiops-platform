"""
Incident load simulator — fires synthetic incidents against the running API.

Usage:
    python scripts/simulate.py                  # 20 incidents, localhost:8001
    python scripts/simulate.py --count 50
    python scripts/simulate.py --count 10 --base-url http://localhost:8000
    python scripts/simulate.py --delay 0.5      # 0.5s between requests (default: 0.2s)

Covers all incident classes so the dashboard shows a realistic distribution:
high_error_rate, deploy_failure, latency_spike, db_overload, oom, unknown.
"""
from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timezone

import httpx

INCIDENT_TEMPLATES = [
    # high_error_rate
    {
        "title": "High error rate on checkout service",
        "signals": {"error_rate": 0.12, "service": "checkout"},
    },
    {
        "title": "5xx spike on payment processor",
        "signals": {"error_rate": 0.25, "service": "payments"},
    },
    {
        "title": "Error rate detected on order service",
        "signals": {"error_rate": 0.07, "service": "orders"},
    },
    # deploy_failure
    {
        "title": "Deploy failure on staging environment",
        "signals": {"deploy_failed": True, "service": "checkout"},
    },
    {
        "title": "Deployment rollout failed on production",
        "signals": {"deploy_failed": True, "service": "inventory"},
    },
    {
        "title": "Canary deploy failure detected",
        "signals": {"deploy_failed": True, "error_rate": 0.09, "service": "recommendations"},
    },
    # latency_spike
    {
        "title": "Latency spike on payment service",
        "signals": {"p95_ms": 2000, "service": "payments"},
    },
    {
        "title": "P99 latency degradation on checkout",
        "signals": {"p95_ms": 3500, "service": "checkout"},
    },
    {
        "title": "Slow response times on search service",
        "signals": {"p95_ms": 1600, "service": "search"},
    },
    {
        "title": "Latency spike detected on API gateway",
        "signals": {"p95_ms": 4200, "p99_ms": 8000, "service": "api-gateway"},
    },
    # db_overload
    {
        "title": "Database CPU overload on checkout-db",
        "signals": {"db_cpu": 95, "service": "checkout"},
    },
    {
        "title": "Database connection pool exhausted",
        "signals": {"db_cpu": 88, "db_connections": 500, "service": "orders"},
    },
    {
        "title": "High database load detected",
        "signals": {"db_cpu": 72, "service": "analytics"},
    },
    # oom
    {
        "title": "OOM killed on worker pod",
        "signals": {"oom": True, "service": "worker"},
    },
    {
        "title": "Container OOM restart loop detected",
        "signals": {"oom": True, "restart_count": 5, "service": "checkout"},
    },
    {
        "title": "Memory limit exceeded on search pods",
        "signals": {"oom": True, "memory_mb": 4096, "service": "search"},
    },
    # unknown
    {
        "title": "Unusual metric pattern detected",
        "signals": {"cpu": 45, "disk_io": 80},
    },
    {
        "title": "Anomaly detected in telemetry",
        "signals": {"anomaly_score": 0.9},
    },
    {
        "title": "System alert triggered",
        "signals": {},
    },
]


async def fire(client: httpx.AsyncClient, base_url: str, incident: dict, index: int) -> None:
    try:
        resp = await client.post(
            f"{base_url}/incident",
            json=incident,
            timeout=30.0,
        )
        data = resp.json()
        status = data.get("status", "?")
        duration = data.get("duration_ms", "?")
        print(f"  [{index:3}] {status:<10} {duration:>6}ms  {incident['title'][:55]}")
    except Exception as exc:
        print(f"  [{index:3}] ERROR  {incident['title'][:55]}  — {exc}")


async def main(count: int, base_url: str, delay: float) -> None:
    print(f"\nFiring {count} incidents at {base_url}\n")
    started = datetime.now(timezone.utc)

    pool = INCIDENT_TEMPLATES * (count // len(INCIDENT_TEMPLATES) + 1)
    random.shuffle(pool)
    incidents = pool[:count]

    async with httpx.AsyncClient() as client:
        for i, incident in enumerate(incidents, 1):
            await fire(client, base_url, incident, i)
            if delay > 0 and i < count:
                await asyncio.sleep(delay)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"\nDone — {count} incidents in {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=20, help="Number of incidents to fire")
    parser.add_argument("--base-url", default="http://localhost:8001", help="API base URL")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds between requests")
    args = parser.parse_args()
    asyncio.run(main(args.count, args.base_url, args.delay))
