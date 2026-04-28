###############################################################################
# Synthetic ECS Fargate service per region.
# Container is a public nginx image by default; we overlay a custom config
# that responds 200 on /health. PR #5 can swap in a real Kafka-gated app.
###############################################################################

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution_primary" {
  provider           = aws.use1
  name               = "${var.app_name}-ecs-exec-use1"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = merge(local.common_tags_use1, { component = "iam-role" })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_primary" {
  provider   = aws.use1
  role       = aws_iam_role.ecs_execution_primary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_execution_secondary" {
  provider           = aws.use2
  name               = "${var.app_name}-ecs-exec-use2"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = merge(local.common_tags_use2, { component = "iam-role" })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secondary" {
  provider   = aws.use2
  role       = aws_iam_role.ecs_execution_secondary.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_cloudwatch_log_group" "task_primary" {
  provider          = aws.use1
  name              = "/ecs/${var.app_name}-test-app-use1"
  retention_in_days = 14
  tags              = merge(local.common_tags_use1, { component = "log-group" })
}

resource "aws_cloudwatch_log_group" "task_secondary" {
  provider          = aws.use2
  name              = "/ecs/${var.app_name}-test-app-use2"
  retention_in_days = 14
  tags              = merge(local.common_tags_use2, { component = "log-group" })
}

resource "aws_ecs_task_definition" "primary" {
  provider                 = aws.use1
  family                   = "${var.app_name}-test-app-use1"
  cpu                      = "256"
  memory                   = "512"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.ecs_execution_primary.arn

  container_definitions = jsonencode([{
    name      = "test-app"
    image     = var.container_image
    essential = true
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.task_primary.name
        "awslogs-region"        = var.primary_region
        "awslogs-stream-prefix" = "test-app"
      }
    }
  }])

  tags = merge(local.common_tags_use1, { component = "ecs-task-def" })
}

resource "aws_ecs_task_definition" "secondary" {
  provider                 = aws.use2
  family                   = "${var.app_name}-test-app-use2"
  cpu                      = "256"
  memory                   = "512"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  execution_role_arn       = aws_iam_role.ecs_execution_secondary.arn

  container_definitions = jsonencode([{
    name      = "test-app"
    image     = var.container_image
    essential = true
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.task_secondary.name
        "awslogs-region"        = var.secondary_region
        "awslogs-stream-prefix" = "test-app"
      }
    }
  }])

  tags = merge(local.common_tags_use2, { component = "ecs-task-def" })
}

resource "aws_ecs_service" "primary" {
  provider        = aws.use1
  name            = "${var.app_name}-test-app"
  cluster         = var.ecs_cluster_arn_primary
  task_definition = aws_ecs_task_definition.primary.arn
  desired_count   = var.task_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids_primary
    security_groups  = [aws_security_group.ecs_primary.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.alb_primary.arn
    container_name   = "test-app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.alb_primary]

  tags = merge(local.common_tags_use1, { component = "ecs-service" })
}

resource "aws_ecs_service" "secondary" {
  provider        = aws.use2
  name            = "${var.app_name}-test-app"
  cluster         = var.ecs_cluster_arn_secondary
  task_definition = aws_ecs_task_definition.secondary.arn
  desired_count   = var.task_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids_secondary
    security_groups  = [aws_security_group.ecs_secondary.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.alb_secondary.arn
    container_name   = "test-app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.alb_secondary]

  tags = merge(local.common_tags_use2, { component = "ecs-service" })
}
