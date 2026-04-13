# Runbook: OOM killed containers

## Symptoms
- Kubernetes events: `OOMKilled`
- Memory working set climbs until restart loop
- GC pressure metrics elevated

## Likely causes
- Memory leak in application code
- Traffic burst larger than limits
- Misconfigured heap / container limits

## Diagnosis steps
1. Inspect memory profile by version; correlate with deploy.
2. Check limits vs actual RSS growth over 24h.
3. Capture heap dump if policy allows.

## Remediation
- **Restart service** to restore availability (destructive to in-flight requests).
- Temporarily **scale up** memory limits only within approved bounds.
- Roll back version if leak confirmed.

## Escalation
Engage service owner for leak fix; SRE for capacity planning.
