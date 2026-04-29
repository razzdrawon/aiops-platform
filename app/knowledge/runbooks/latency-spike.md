# Runbook: Latency spike on checkout

## Symptoms
- p95 latency > 2s for checkout path
- CPU moderate but DB wait time elevated
- Traces show long spans on `db.query` or `inventory.reserve`

## Likely causes
- Hot key / missing index causing slow queries
- N+1 queries introduced in recent release
- DB connection pool contention

## Diagnosis steps
1. Open slow query log for checkout-related tables.
2. Compare trace waterfall before/after last deploy.
3. Validate pool settings vs traffic.

## Remediation
- Roll back release if regression tied to ORM change.
- **Scale up** read replicas or API concurrency only after confirming DB headroom.
- Apply emergency index if approved by DBA workflow (out of band for agents).

## Escalation
Database on-call if p95 > 5s sustained.
