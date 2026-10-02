# Infrastructure as Code (Terraform)

Provisions the AIOps platform on AWS: **ECS Fargate + RDS PostgreSQL + ALB + ECR**,
with optional **MSK** and **ElastiCache** behind feature flags.

> **Status:** the code is written and `terraform validate`-clean. It has **not**
> been applied — this repository ships the IaC as a portfolio artifact. Applying
> it creates real, billable AWS resources (see *Cost* below).

## Layout

```
terraform/
├── bootstrap/            # Remote-state backend (S3 + DynamoDB lock). Run ONCE.
├── modules/
│   ├── network/          # VPC, public/private subnets, IGW, NAT, route tables
│   ├── database/         # RDS PostgreSQL, subnet group, security group
│   ├── compute/          # ECS Fargate, ALB, ECR, IAM (least-privilege), logs
│   ├── messaging/        # Amazon MSK (managed Kafka) — optional
│   └── cache/            # ElastiCache (Redis) — optional
└── environments/
    └── dev/              # Composes the modules for the dev environment
```

### Why directories per environment (not workspaces)

Each environment is its own directory with its **own backend key** and isolated
state. Compared to `terraform workspaces` (which share one backend and make it
easy to apply to the wrong environment from the wrong workspace), separate
directories give explicit, reviewable, blast-radius-limited isolation. Adding
`staging`/`prod` = copy `dev/`, change `backend.tf`'s `key` and the `*.tfvars`.

## Architecture

```
            Internet
               │  :80 / :443
        ┌──────▼──────┐  public subnets
        │     ALB     │
        └──────┬──────┘
               │  app port (8000), ALB SG only
   ┌───────────▼───────────┐  private subnets
   │  ECS Fargate service  │  task pulls image from ECR,
   │      (app task)       │  reads secrets from Secrets Manager,
   └───────────┬───────────┘  logs to CloudWatch
               │  5432, app SG only
        ┌──────▼──────┐  private subnets
        │  RDS (PG)   │  encrypted, not public
        └─────────────┘
```

- **Secrets** (`DATABASE_URL`, `OPENAI_API_KEY`, `PINECONE_API_KEY`) live in AWS
  Secrets Manager and are injected at task start. Nothing secret is baked into
  the image or the task definition.
- **Least privilege**: the ECS execution role can read *only* the three secrets
  it needs; the task role is empty until the app makes its own AWS calls.
- **Network**: tasks and DB sit in private subnets; only the ALB is public.

## Usage

```bash
# 0) One-time: create the remote-state backend (uses local state).
cd terraform/bootstrap
terraform init && terraform apply

# 1) Provision an environment.
cd ../environments/dev
terraform init            # uses the S3 backend from step 0
export TF_VAR_openai_api_key="sk-..."     # optional; empty => offline mode
export TF_VAR_pinecone_api_key="..."      # optional
terraform plan
terraform apply

# 2) Build & push the image, then force a new deployment.
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$(terraform output -raw ecr_repository_url)"
docker build -t "$(terraform output -raw ecr_repository_url):$(git rev-parse --short HEAD)" .
docker push "$(terraform output -raw ecr_repository_url):$(git rev-parse --short HEAD)"
# (the CD pipeline automates this — see .github/workflows)

# Tear everything down.
terraform destroy
```

Migrations run as a **one-off ECS task** (`alembic upgrade head`), never on app
boot — mirroring the `migrate` service in `docker-compose.yml`.

## Optional components

`messaging` (MSK) and `cache` (ElastiCache) are **off by default** because MSK
alone is ~$130+/mo. Enable per environment:

```hcl
# terraform/environments/dev/terraform.tfvars
enable_messaging = true
enable_cache     = true
```

## Cost (rough, us-east-1, dev sizing)

| Component        | Est. monthly |
|------------------|--------------|
| ECS Fargate (1 task, 0.5 vCPU) | ~$9 |
| RDS db.t4g.micro | ~$13 |
| ALB              | ~$16 |
| NAT Gateway (1)  | ~$32 |
| **Core total**   | **~$70** |
| MSK (optional)   | +$130 |
| ElastiCache (optional) | +$12 |

> The NAT Gateway is the biggest fixed line item. For a throwaway demo you can
> set `single_nat_gateway = true` (already the dev default) or run tasks in
> public subnets — a documented trade-off, not done here to keep the design
> correct.
