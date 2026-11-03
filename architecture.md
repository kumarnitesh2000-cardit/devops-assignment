# Deployment Architecture

```mermaid
flowchart LR
    Developer[Developer push to main] --> Actions[GitHub Actions]
    Actions -->|GitHub OIDC role| AWS[AWS account]
    Actions -->|Build and push SHA-tagged image| ECR[Amazon ECR]
    Actions -->|Register task definitions and deploy| ECS[Amazon ECS Fargate]

    Browser[User browser] -->|HTTP| ALB[Application Load Balancer]
    ALB -->|Port 8000| API[FastAPI backend task]
    API -->|Enqueue and poll result| Redis[(Amazon ElastiCache Redis)]
    Redis -->|Task queue| Worker[Celery worker task]
    Worker -->|Task result| Redis

    API --> BackendLogs[CloudWatch backend logs]
    Worker --> WorkerLogs[CloudWatch worker logs]
    API -. secret injection .-> Secrets[AWS Secrets Manager]
    Worker -. secret injection .-> Secrets
    Secrets --> Redis

    Terraform[Terraform] --> VPC[VPC and security groups]
    Terraform --> ALB
    Terraform --> ECS
    Terraform --> ECR
    Terraform --> Redis
    Terraform --> Secrets
    Terraform --> Logs[CloudWatch log groups]
    Terraform --> OIDC[GitHub OIDC provider and deploy role]
```

The ALB is public. Fargate tasks run in public subnets to avoid NAT Gateway cost for this assessment; their inbound security groups only allow backend traffic from the ALB, and the worker accepts no inbound traffic. ElastiCache uses private subnets, encryption in transit and at rest, and a generated AUTH token stored in Secrets Manager.
