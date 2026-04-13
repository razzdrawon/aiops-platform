# Runbook: High error rate on API tier

## Symptoms
- HTTP 5xx ratio climbs above 2% for 5 minutes
- Spike in `checkout_payment_failed` logs
- Trace shows failures concentrated on one pod revision

## Likely causes
- Bad deployment (config drift, missing secret)
- Downstream dependency timeout (payments provider)
- Resource exhaustion on a subset of nodes

## Diagnosis steps
1. Compare error rate by `service.version` — isolate canary vs stable.
2. Inspect recent deploys and feature flags.
3. Check dependency dashboards (payments, inventory).

## Remediation
- If correlated with new version: **rollback** to last known good.
- If dependency: enable circuit breaker / reduce traffic; page owning team.
- If saturation: **scale up** API replicas cautiously.

## Escalation
Page SRE if error rate remains >5% after rollback window (15 min).
