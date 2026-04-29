# Runbook: Deployment failure / rollout stuck

## Symptoms
- CI pipeline red on deploy stage
- Rollout paused at canary with health check failures
- New pods crashloop before taking traffic

## Likely causes
- Invalid image tag or registry pull errors
- Startup probe failing (DB migration not applied)
- Incompatible config map change

## Diagnosis steps
1. Read deploy logs and pod events.
2. Diff config between previous and current revision.
3. Verify migrations and feature flags.

## Remediation
- **Rollback** to previous revision when health checks fail on canary.
- Fix forward with **create PR fix** for manifest issues when rollback not possible.

## Escalation
Platform team if registry or cluster-wide issue suspected.
