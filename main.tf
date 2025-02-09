variable "aws_access_key" {}
variable "aws_secret_key" {}

provider "aws" {
  region     = "eu-west-2"
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}

# VPC and Networking
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "green-detective-vpc"
  }

  lifecycle {
    ignore_changes = [cidr_block, tags]
  }

  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "eu-west-2a"
  map_public_ip_on_launch = true
  tags = {
    Name = "green-detective-public-subnet"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "eu-west-2b"
  map_public_ip_on_launch = true
  tags = {
    Name = "green-detective-public-subnet-b"
  }
}

resource "aws_subnet" "public_c" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.3.0/24"
  availability_zone       = "eu-west-2c"
  map_public_ip_on_launch = true
  tags = {
    Name = "green-detective-public-subnet-c"
  }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags = {
    Name = "green-detective-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
  tags = {
    Name = "green-detective-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_c" {
  subnet_id      = aws_subnet.public_c.id
  route_table_id = aws_route_table.public.id
}

# Security Groups
resource "aws_security_group" "ecs" {
  name        = "green-detective-ecs-sg"
  description = "Allow inbound traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Add a specific security group for ECR access
resource "aws_security_group" "ecr_endpoint" {
  name        = "green-detective-ecr-endpoint-sg"
  description = "Security group for ECR VPC endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "green_detective" {
  name = "green-detective"
}

# API Service
resource "aws_ecs_task_definition" "api" {
  family                   = "green-detective-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = data.aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${data.aws_ecr_repository.api.repository_url}:latest"
      essential = true
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/green-detective-api"
          "awslogs-region"        = "eu-west-2"
          "awslogs-stream-prefix" = "ecs"
        }
      }
      portMappings = [
        {
          containerPort = 8070
          hostPort      = 8070
        }
      ]
      secrets = [
        {
          name = "ENV_FILE"
          valueFrom = aws_secretsmanager_secret.env_variables.arn
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.green_detective.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public.id, aws_subnet.public_b.id, aws_subnet.public_c.id]
    security_groups  = [aws_security_group.ecs.id, aws_security_group.ecr_endpoint.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8070
  }
}

# Process Service
resource "aws_ecs_task_definition" "process" {
  family                   = "green-detective-process"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = data.aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "process"
      image     = "${data.aws_ecr_repository.process.repository_url}:latest"
      essential = true
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/green-detective-process"
          "awslogs-region"        = "eu-west-2"
          "awslogs-stream-prefix" = "ecs"
        }
      }
      portMappings = [
        {
          containerPort = 8071
          hostPort      = 8071
        }
      ]
      secrets = [
        {
          name = "ENV_FILE"
          valueFrom = aws_secretsmanager_secret.env_variables.arn
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "process" {
  name            = "process"
  cluster         = aws_ecs_cluster.green_detective.id
  task_definition = aws_ecs_task_definition.process.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public.id, aws_subnet.public_b.id, aws_subnet.public_c.id]
    security_groups  = [aws_security_group.ecs.id, aws_security_group.ecr_endpoint.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.process.arn
    container_name   = "process"
    container_port   = 8071
  }
}

# Database
resource "aws_db_subnet_group" "main" {
  name       = "green-detective-db-subnet-group"
  subnet_ids = [aws_subnet.public.id, aws_subnet.public_b.id, aws_subnet.public_c.id]

  tags = {
    Name = "green-detective-db-subnet-group"
  }
}

resource "aws_db_instance" "green_detective" {
  identifier             = "green-detective-db"
  allocated_storage      = 20
  storage_type           = "gp2"
  engine                 = "postgres"
  engine_version         = "17.2"
  instance_class         = "db.t3.micro"
  db_name                = "greendetective"
  username               = "root"
  password               = var.db_password
  parameter_group_name   = "default.postgres17"
  publicly_accessible    = false
  skip_final_snapshot    = true
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  backup_retention_period = 0
  backup_window          = "03:00-04:00"
}

resource "aws_security_group" "rds" {
  name        = "green-detective-rds-sg"
  description = "Allow inbound traffic to RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Load Balancer
resource "aws_lb" "green_detective" {
  name               = "green-detective-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.ecs.id]
  subnets            = [aws_subnet.public.id, aws_subnet.public_b.id, aws_subnet.public_c.id]

  enable_deletion_protection = false
}

# Target Groups
resource "aws_lb_target_group" "api" {
  name     = "green-detective-api-tg"
  port     = 8070
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health/"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
  }
}

resource "aws_lb_target_group" "process" {
  name     = "green-detective-process-tg"
  port     = 8071
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health/"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
  }
}

# Remove the existing HTTP listener for port 80
resource "aws_lb_listener" "api_http" {
  count = 0  # This will remove the existing resource

  # Required arguments
  load_balancer_arn = aws_lb.green_detective.arn
  port              = 80
  protocol          = "HTTP"

  # Required default_action block
  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "This listener is being removed"
      status_code  = "200"
    }
  }
}

# Keep the HTTPS listener
resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.green_detective.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = "arn:aws:acm:eu-west-2:${data.aws_caller_identity.current.account_id}:certificate/6e10eefb-fd64-47bc-8062-49e01e3c0105"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Add HTTP to HTTPS redirect
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.green_detective.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "process" {
  load_balancer_arn = aws_lb.green_detective.arn
  port              = "81"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.process.arn
  }
}

# IAM Role
data "aws_iam_role" "ecs_task_execution_role" {
  name = "green-detective-ecs-task-execution-role"
}

# Update the IAM policy for full access
resource "aws_iam_role_policy" "ecs_full_access" {
  name = "green-detective-full-access"
  role = data.aws_iam_role.ecs_task_execution_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:*",
          "s3:*",
          "ecs:*",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECR Repositories
data "aws_ecr_repository" "api" {
  name = "green-detective-api"
}

data "aws_ecr_repository" "process" {
  name = "green-detective-process"
}

# S3 Bucket
data "aws_s3_bucket" "reports" {
  bucket = "green-detective-reports"
}

resource "aws_s3_bucket_policy" "reports" {
  bucket = data.aws_s3_bucket.reports.bucket
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = "arn:aws:s3:::green-detective-reports/*"
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# Redis Cache
resource "aws_elasticache_subnet_group" "main" {
  name       = "green-detective-redis-subnet-group"
  subnet_ids = [aws_subnet.public.id, aws_subnet.public_b.id, aws_subnet.public_c.id]

  tags = {
    Name = "green-detective-redis-subnet-group"
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "green-detective-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis6.x"
  engine_version       = "6.x"
  port                 = 6379
  security_group_ids   = [aws_security_group.redis.id]
  subnet_group_name    = aws_elasticache_subnet_group.main.name
}

resource "aws_security_group" "redis" {
  name        = "green-detective-redis-sg"
  description = "Allow inbound traffic to Redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Secrets Manager for Database Credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name = "green-detective-db-credentials-v3"
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "root"
    password = var.db_password
    engine   = "postgres"
    host     = aws_db_instance.green_detective.endpoint
    port     = 5432
    dbname   = "greendetective"
  })
}

# CloudWatch Logs
data "aws_cloudwatch_log_group" "api" {
  name = "/ecs/green-detective-api"
}

data "aws_cloudwatch_log_group" "process" {
  name = "/ecs/green-detective-process"
}

# Move these resources before the scaling policies
resource "aws_appautoscaling_target" "api" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 3
}

resource "aws_appautoscaling_target" "process" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.process.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 3
}

# Then keep the scaling policies after the targets
resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "api-cpu-scaling"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  policy_type        = "StepScaling"

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      scaling_adjustment          = 1
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = null
    }
  }

  depends_on = [aws_appautoscaling_target.api]
}

resource "aws_appautoscaling_policy" "process_cpu" {
  name               = "process-cpu-scaling"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.process.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  policy_type        = "StepScaling"

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      scaling_adjustment          = 1
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = null
    }
  }

  depends_on = [aws_appautoscaling_target.process]
}

# Add auto-scaling policies to scale down during off-hours
resource "aws_appautoscaling_scheduled_action" "scale_down_night" {
  name               = "scale-down-night"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule          = "cron(0 22 * * ? *)"

  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }
}

resource "aws_appautoscaling_scheduled_action" "scale_up_morning" {
  name               = "scale-up-morning"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule          = "cron(0 6 * * ? *)"

  scalable_target_action {
    min_capacity = 1
    max_capacity = 1
  }
}

# Outputs
output "api_endpoint" {
  value = "https://${aws_lb.green_detective.dns_name}"
}

output "process_endpoint" {
  value = "https://${aws_lb.green_detective.dns_name}:81"
}

output "database_endpoint" {
  value = aws_db_instance.green_detective.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "s3_bucket_name" {
  value = data.aws_s3_bucket.reports.bucket
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

data "aws_db_subnet_group" "main" {
  name = aws_db_subnet_group.main.name
}

data "aws_elasticache_subnet_group" "main" {
  name = aws_elasticache_subnet_group.main.name
}

resource "aws_budgets_budget" "monthly" {
  name              = "green-detective-monthly-budget"
  budget_type       = "COST"
  limit_amount      = "30"
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["nandangrover.5@gmail.com"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["nandangrover.5@gmail.com"]
  }
}

resource "aws_budgets_budget" "daily" {
  name              = "green-detective-daily-budget"
  budget_type       = "COST"
  limit_amount      = "1"
  limit_unit        = "USD"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "DAILY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["nandangrover.5@gmail.com"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["nandangrover.5@gmail.com"]
  }
}

# Add data source for current AWS account
data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "ecs_s3_access" {
  name = "green-detective-s3-access"
  role = data.aws_iam_role.ecs_task_execution_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::greendetective-env/live.env"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_secrets_access" {
  name = "green-detective-secrets-access"
  role = data.aws_iam_role.ecs_task_execution_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.env_variables.arn
      }
    ]
  })
}

resource "aws_secretsmanager_secret" "env_variables" {
  name = "green-detective-env-variables"
}

resource "aws_secretsmanager_secret_version" "env_variables" {
  secret_id = aws_secretsmanager_secret.env_variables.id
  secret_string = jsonencode({
    ENV_FILE = "s3://prod-greendetective/live.env"
    # Add other environment variables here if needed
  })
}
