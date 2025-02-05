provider "aws" {
  region = "eu-west-2"
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
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "eu-west-2a"  # Explicitly set AZ
  tags = {
    Name = "green-detective-public-subnet"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "eu-west-2b"
  tags = {
    Name = "green-detective-public-subnet-b"
  }
}

resource "aws_subnet" "public_c" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "eu-west-2c"
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

# ECS Cluster
resource "aws_ecs_cluster" "green_detective" {
  name = "green-detective"
}

# API Service
resource "aws_ecs_task_definition" "api" {
  family                   = "green-detective-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn         = data.aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${data.aws_ecr_repository.api.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8070
          hostPort      = 8070
        }
      ]
      environment = [
        {
          name  = "DJANGO_SETTINGS_MODULE"
          value = "green_detective.settings"
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.green_detective.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.public.id]
    security_groups = [aws_security_group.ecs.id]
  }

  load_balancer {
    target_group_arn = data.aws_lb_target_group.api.arn
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
  execution_role_arn         = data.aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "process"
      image     = "${data.aws_ecr_repository.process.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8071
          hostPort      = 8071
        }
      ]
      environment = [
        {
          name  = "DJANGO_SETTINGS_MODULE"
          value = "green_detective.settings"
        }
      ]
    }
  ])
}

resource "aws_ecs_service" "process" {
  name            = "process"
  cluster         = aws_ecs_cluster.green_detective.id
  task_definition = aws_ecs_task_definition.process.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.public.id]
    security_groups = [aws_security_group.ecs.id]
  }

  load_balancer {
    target_group_arn = data.aws_lb_target_group.process.arn
    container_name   = "process"
    container_port   = 8071
  }
}

# Database
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
  db_subnet_group_name   = data.aws_db_subnet_group.main.name
}

data "aws_db_subnet_group" "main" {
  name = "green-detective-db-subnet-group"
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
data "aws_lb" "green_detective" {
  name = "green-detective-lb"
}

# Target Groups
data "aws_lb_target_group" "api" {
  name = "green-detective-api-tg"
}

data "aws_lb_target_group" "process" {
  name = "green-detective-process-tg"
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = data.aws_lb.green_detective.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = data.aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "process" {
  load_balancer_arn = data.aws_lb.green_detective.arn
  port              = "81"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = data.aws_lb_target_group.process.arn
  }
}

# IAM Role
data "aws_iam_role" "ecs_task_execution_role" {
  name = "green-detective-ecs-task-execution-role"
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
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "green-detective-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis6.x"
  engine_version       = "6.x"
  port                 = 6379
  security_group_ids   = [aws_security_group.redis.id]
  subnet_group_name    = data.aws_elasticache_subnet_group.main.name
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
  name = "green-detective-db-credentials-v2"
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "root"
    password = var.db_password
    dbname   = "greendetective"
    host     = aws_db_instance.green_detective.endpoint
    port     = 5432
  })
}

# CloudWatch Logs
data "aws_cloudwatch_log_group" "api" {
  name = "/ecs/green-detective-api"
}

data "aws_cloudwatch_log_group" "process" {
  name = "/ecs/green-detective-process"
}

# Auto Scaling Policies
resource "aws_appautoscaling_target" "api" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 3
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "api-cpu-scaling"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    target_value = 50
  }
}

resource "aws_appautoscaling_target" "process" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.process.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 3
}

resource "aws_appautoscaling_policy" "process_cpu" {
  name               = "process-cpu-scaling"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.green_detective.name}/${aws_ecs_service.process.name}"
  scalable_dimension = "ecs:service:DesiredCount"

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    target_value = 50
  }
}

# Outputs
output "api_endpoint" {
  value = data.aws_lb.green_detective.dns_name
}

output "process_endpoint" {
  value = "${data.aws_lb.green_detective.dns_name}:81"
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

# ElastiCache Subnet Group
data "aws_elasticache_subnet_group" "main" {
  name = "green-detective-redis-subnet-group"
}
