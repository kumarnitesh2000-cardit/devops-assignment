output "application_url" {
  description = "Public URL for the FastAPI application and frontend."
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository used by the GitHub Actions workflow."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster deployed by this Terraform stack."
  value       = aws_ecs_cluster.app.name
}

output "backend_service_name" {
  value = aws_ecs_service.backend.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}

output "github_actions_role_arn" {
  description = "Configure this ARN as the AWS_ROLE_ARN GitHub Actions repository variable."
  value       = aws_iam_role.github_actions.arn
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  value = var.aws_region
}
