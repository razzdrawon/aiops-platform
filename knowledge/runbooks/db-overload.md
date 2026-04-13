# Runbook: Database overload

## Symptoms
- DB CPU > 85% sustained
- Growing queue depth on checkout writes
- Lock wait time elevated; timeouts in API

## Likely causes
- Sudden traffic surge or batch job colliding with OLTP
- Missing indexes on hot paths
- Long transactions holding locks

## Diagnosis steps
1. Identify top SQL by total time and lock time.
2. Map queries to services and deploy windows.
3. Check replication lag and failover health.

## Remediation
- Throttle non-critical workloads at edge.
- **Scale up** primary or add read capacity if architecture supports reads for hot paths.
- Coordinate with DBA for kill of offending long queries (human-in-the-loop).

## Escalation
Declare incident if replication lag breaches SLO.
