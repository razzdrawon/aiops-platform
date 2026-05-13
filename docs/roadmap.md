# Roadmap

This document describes the planned phases for the AIOps platform and the engineering skills each one demonstrates.

---

## Phase 4 — Streaming + Integrations

**Goal:** Make the platform reactive and observable in real time, and connect it to the tools on-call engineers actually use.

**What to build:**

- `GET /incidents/{id}/stream` — SSE endpoint that pushes pipeline node events as they happen (`detected`, `diagnosed`, `action_selected`, `executed`, `resolved`)
- PagerDuty webhook receiver — ingest PagerDuty alerts as incident signals
- Slack notifier — post resolution summaries to a configurable channel when an incident closes
- Background task processing — decouple the Slack/PD calls from the request path using an async task queue (ARQ)

**Skills demonstrated:**

- Server-Sent Events with `sse-starlette`
- Webhook signature verification (PagerDuty HMAC)
- Third-party API integration
- Background task queues (ARQ + Redis)
- Event-driven architecture

---

## Phase 5 — Production Readiness

**Goal:** Add the operational layer that makes a service trustworthy in production. This is what separates a working prototype from something you'd actually run.

**What to build:**

- `GET /metrics` — Prometheus-compatible endpoint via `prometheus-fastapi-instrumentator`
- Custom metrics: `aiops_mttr_seconds`, `aiops_guardrail_block_total`, `aiops_cost_usd_total`, `aiops_node_latency_seconds{node=...}`
- Docker Compose service additions: Prometheus, Grafana (with pre-built dashboard JSON)
- Redis integration:
  - Cache RAG results by signal fingerprint (TTL = 5 min) to avoid redundant Pinecone calls
  - Rate limiting on `POST /incident` (e.g. 10 req/min per IP)
- API key authentication middleware — `X-API-Key` header, keys stored hashed in DB
- Distributed tracing: connect existing OpenTelemetry instrumentation to Jaeger (add to Docker Compose)
- Structured JSON logging with `structlog` — correlation ID per request

**Skills demonstrated:**

- Prometheus + Grafana observability stack
- Redis for caching and rate limiting
- API authentication patterns
- Distributed tracing end-to-end
- Structured logging

---

## Phase 6 — Cloud Deployment (AWS)

**Goal:** Take the Docker Compose stack and deploy it to AWS using infrastructure as code. Demonstrate that you can own the full path from code to production.

**What to build:**

- Terraform modules:
  - `modules/network` — VPC, subnets, security groups
  - `modules/compute` — ECS Fargate cluster + task definition + service
  - `modules/database` — RDS PostgreSQL (multi-AZ for prod)
  - `modules/messaging` — Amazon MSK (managed Kafka)
  - `modules/cache` — ElastiCache Redis
- Three environments via Terraform workspaces: `dev`, `staging`, `prod`
- Secrets management — AWS Secrets Manager for `DATABASE_URL`, `OPENAI_API_KEY`, etc.
- ECR — Docker image registry, images tagged by git SHA
- GitHub Actions CD step — on merge to `main`, build image → push to ECR → update ECS service
- ALB with HTTPS termination (ACM certificate)

**Skills demonstrated:**

- Terraform IaC — modules, workspaces, remote state (S3 + DynamoDB lock)
- AWS core services: ECS Fargate, RDS, MSK, ElastiCache, ECR, ALB, Secrets Manager
- Multi-environment configuration management
- CI/CD with automated deployment
- Container image lifecycle

---

## Skills map

```
Phase 1  Clean architecture · PostgreSQL · Kafka · Testing · CI
Phase 2  Evaluation framework · Accuracy / precision / recall
Phase 3  LLM observability · Token cost · Latency tracing
Phase 4  SSE streaming · Webhooks · Background tasks · Integrations
Phase 5  Prometheus · Grafana · Redis · Auth · Rate limiting · OTel traces
Phase 6  Terraform · AWS ECS/RDS/MSK · Multi-env · CD pipeline
```

All six phases together cover the full backend + AI engineering skill set expected in a senior role.
