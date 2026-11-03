# Developer Instructions

## Prerequisites

- Docker Desktop with Docker Compose v2
- Git
- For cloud deployment: Terraform 1.10+, AWS CLI v2, an AWS account with permissions to create VPC, ECS, ElastiCache, ECR, IAM, Secrets Manager, CloudWatch, and S3 resources

## Run locally

From the repository root:

```sh
cp .env.example .env
docker compose build
docker compose up -d
```

Open <http://localhost:8000>. Enter an email and select **Send notification**. The page calls `POST /notify/` and polls `GET /task_status/{task_id}` until the task completes or fails.

The claim-processing API is available at <http://localhost:8001/docs>. Set `OPENAI_API_KEY` in `.env` before submitting claims. For an API request example and workflow details, see [claims_pipeline/README.md](claims_pipeline/README.md).

Useful commands:

```sh
docker compose ps
docker compose logs -f backend worker
docker compose logs -f redis
docker compose logs -f claims-api
docker compose restart backend worker
docker compose down
```

To stop the stack and also remove the local Redis data volume, use `docker compose down -v`. This permanently deletes the local Redis task data.

The `TASK_DURATION_SECONDS` and `LOG_LEVEL` settings are in `.env`. Redis host, port, database, TLS, and password are configurable through environment variables; local Compose sets the Redis hostname to its service name. Do not commit `.env` or put cloud credentials in it.

### Run the claim API without Docker

Install the requirements into a Python environment, set the LLM key, then run:

```sh
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
uvicorn claims_pipeline.main:app --reload --port 8001
```

This service uses `POST /api/process` with multipart form fields `claim_id` and `file`. API docs are served at <http://localhost:8001/docs>. The default upload limit is 20 MiB and 100 pages; use `MAX_PDF_BYTES` and `MAX_PDF_PAGES` to adjust these caps. Text-based PDFs are supported directly. Scanned/image-only pages need OCR before upload. Claim contents are sent to the configured OpenAI model, so use only data you are authorized to process and an approved provider/account.

## AWS deployment

This configuration creates chargeable AWS resources. Review the AWS pricing for Fargate, ElastiCache, the load balancer, ECR, and CloudWatch before applying. The demo exposes HTTP on port 80; configure an ACM certificate, HTTPS listener, and domain before using it with real users. Fargate tasks use public subnets to avoid NAT Gateway cost, but security groups restrict inbound traffic; use private task subnets and VPC endpoints/NAT for a production network design.

### 1. Configure AWS and repository details

Configure the AWS CLI credentials for the account and region you intend to use:

```sh
aws configure
aws sts get-caller-identity
```

Terraform currently defaults to `us-east-1`, repository `kumarnitesh2000-cardit/devops-assignment`, and deployment branches `main` and `devops_project`. Override these in a local `terraform.tfvars` if your fork or branch differs. The `.gitignore` excludes that file.

Create `infra/state/terraform.tfvars` with a globally unique S3 bucket name and region, for example:

```hcl
aws_region       = "us-east-1"
state_bucket_name = "your-unique-devops-assessment-terraform-state"
```

Initialize and create the encrypted, versioned state bucket:

```sh
terraform -chdir=infra/state init
terraform -chdir=infra/state plan
terraform -chdir=infra/state apply
```

### 2. Initialize the application stack

Copy the backend configuration example and replace the bucket placeholder with the bucket name created above:

```sh
cp infra/terraform/backend.hcl.example infra/terraform/backend.hcl
terraform -chdir=infra/terraform init -backend-config=backend.hcl
```

Create `infra/terraform/terraform.tfvars` (not committed) and set your repository and branch if needed:

```hcl
github_repository = "YOUR_GITHUB_OWNER/devops-assignment"
github_branches   = ["main", "devops_project"]
aws_region        = "us-east-1"
```

Create ECR before the first full apply, then push a bootstrap image so the initial ECS tasks can start:

```sh
terraform -chdir=infra/terraform plan -target=aws_ecr_repository.app
terraform -chdir=infra/terraform apply -target=aws_ecr_repository.app
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/devops-assignment-demo"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
docker build -t "$ECR_URI:bootstrap" .
docker push "$ECR_URI:bootstrap"
```

Apply the full stack and inspect the outputs:

```sh
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
terraform -chdir=infra/terraform output
```

The `application_url` output is the public demo URL. Inspect deployment and logs with:

```sh
aws ecs describe-services --cluster devops-assignment-demo \
  --services devops-assignment-demo-backend devops-assignment-demo-worker
aws logs tail /ecs/devops-assignment-demo/backend --follow
aws logs tail /ecs/devops-assignment-demo/worker --follow
```

### 3. Enable automatic GitHub deployments

After Terraform outputs `github_actions_role_arn`, add these **repository Actions variables** in GitHub Settings > Secrets and variables > Actions > Variables:

- `AWS_ROLE_ARN`: the `github_actions_role_arn` Terraform output
- `AWS_REGION`: the Terraform `aws_region` output
- `AWS_ACCOUNT_ID`: the Terraform `aws_account_id` output

The workflow uses GitHub OIDC, so no long-lived AWS access key is stored in GitHub. It builds an image tagged with the commit SHA, pushes it to ECR, registers updated ECS task definitions, deploys both services, and waits for them to stabilize. A push to `main` triggers deployment; `workflow_dispatch` can trigger it manually.

If you fork or rename the repository, update `github_repository` in Terraform and apply again. The IAM OIDC trust policy only permits the configured repository and branches.

### 4. Tear down

To remove the application resources when finished:

```sh
terraform -chdir=infra/terraform destroy
```

ECR images must be deleted before Terraform can delete the ECR repository because `force_delete` is disabled. Preserve the state bucket until the application stack is fully removed; it has `prevent_destroy` enabled. Removing the state bucket should be a deliberate separate change after confirming the state is no longer needed.
