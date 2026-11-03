variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project name used to name AWS resources."
  type        = string
  default     = "devops-assignment"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "demo"
}

variable "vpc_cidr" {
  description = "CIDR range for the application VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "redis_node_type" {
  description = "ElastiCache node size; increase this for production workloads."
  type        = string
  default     = "cache.t4g.micro"
}

variable "backend_desired_count" {
  description = "Number of backend tasks to run."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Number of Celery worker tasks to run."
  type        = number
  default     = 1
}

variable "task_duration_seconds" {
  description = "Simulated duration for each notification task."
  type        = number
  default     = 10
}

variable "image_tag" {
  description = "Container image tag used when Terraform creates the first task definitions."
  type        = string
  default     = "bootstrap"
}

variable "github_repository" {
  description = "GitHub repository in owner/name format allowed to deploy."
  type        = string
  default     = "kumarnitesh2000-cardit/devops-assignment"
}

variable "github_branches" {
  description = "Git branches allowed to assume the deployment role."
  type        = list(string)
  default     = ["main", "devops_project"]
}
