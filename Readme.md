# DevOps and Claim Processing Assignments

This repository contains two independent FastAPI applications: the original Celery/Redis task notifier and a LangGraph-based PDF claim extraction API.

## Quick start

```sh
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000>, submit an email, and watch the task status update. To run the claims API, set `OPENAI_API_KEY` in `.env`, then run:

```sh
docker compose up --build claims-api
```

Open <http://localhost:8001/docs> for its interactive API. See [claims_pipeline/README.md](claims_pipeline/README.md) for the upload request and graph details, and [instructions.md](instructions.md) for full local and cloud instructions.

## Components

- `backend/main.py`: FastAPI endpoints and frontend serving route
- `backend/worker.py`: Celery app and background task
- `frontend/index.html`: single-page task submission and polling UI
- `Dockerfile` and `docker-compose.yml`: local containerized stack
- `infra/terraform/`: AWS network, ECR, ECS Fargate, ElastiCache Redis, IAM, Secrets Manager, and CloudWatch resources
- `infra/state/`: encrypted, versioned S3 Terraform state bucket
- `.github/workflows/deploy.yml`: GitHub Actions build and ECS deployment using OIDC
- `claims_pipeline/`: separate PDF upload API, LangGraph workflow, and three extraction agents
- `tests/test_claim_workflow.py`: offline graph routing test with a fake structured-output model

See [architecture.md](architecture.md) for the cloud resource diagram and [journey.md](journey.md) for implementation decisions and production considerations.
