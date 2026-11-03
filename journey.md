# Journey

## Decisions

- Kept FastAPI and Celery as separate runtime processes while sharing one small image, avoiding duplicate dependency and build configuration.
- Made Redis host, port, database, TLS, password, and task duration configurable. Compose uses its Redis service name; AWS injects the managed Redis endpoint and AUTH token.
- Served the existing single-page frontend from FastAPI and changed it to use `window.location.origin`. This avoids a fixed localhost URL and keeps browser requests same-origin in local and cloud environments.
- Sent worker output to stdout so Docker and CloudWatch can collect logs instead of relying on a container-local file.
- Used Compose and a local Redis container for developer runs; used ECS Fargate, ElastiCache, ECR, Secrets Manager, and CloudWatch for AWS.
- Used GitHub's OIDC federation for short-lived deployment credentials rather than storing long-lived AWS access keys.
- Created the Terraform state bucket in a separate bootstrap module because an S3 backend must exist before the application stack can initialize its remote state.

## Challenges and fixes

- The original Celery URL targeted `localhost`, which would resolve to each container itself. The worker now builds its Redis URL from environment settings.
- The frontend was pinned to `http://localhost:8000`. It now targets the current origin and the API serves the page at `/`.
- Celery's failed task state is also ready. The status endpoint now checks failure before completion so failures are not mislabeled.
- Cloud task execution needs outbound connectivity to pull images and send logs. To avoid a NAT Gateway cost in this assessment, tasks use public subnets with inbound traffic restricted by security groups; Redis is in private subnets.

## Validation and remaining work

- Python syntax checks passed for the changed backend modules, and the Compose file parsed as YAML.
- Docker, Terraform, AWS CLI, and Node.js were unavailable in the implementation environment, so an image build, `terraform validate`, cloud apply, and browser run remain to be performed by the developer.
- Before real use, add HTTPS with an ACM certificate and custom domain, use private task subnets with suitable VPC endpoints/NAT, review scaling and backups, and assess task-level IAM, alerting, and Redis availability requirements.
- Cloud resources incur ongoing charges. Follow the teardown steps in `instructions.md` after the assessment, while preserving the Terraform state bucket until state is no longer needed.

## Claim processing assignment

- Added `claims_pipeline` as a separate FastAPI app so it does not change the original notifier API.
- Uses PyPDF to extract text per page, a structured-output LLM call to classify pages, and LangGraph `Send` routing so only relevant page text reaches each of the ID, discharge summary, and itemized bill agents.
- The three agent branches join at an aggregator. Bill line amounts are summed in code with decimal arithmetic before returning JSON.
- Added request limits and rejects malformed, encrypted, and textless PDFs. Scanned documents need OCR before submission; OCR is not bundled.
- An offline fake-model graph test verifies classification, page isolation, and result aggregation. Real extraction requires an approved `OPENAI_API_KEY` and sends assigned claim page text to the configured OpenAI model.