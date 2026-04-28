###############################################################################
# ECS Fargate clusters in both regions. Per CLAUDE.md §2.1 POC-F, the test
# harness app is the only service; the cluster is shared.
###############################################################################

resource "aws_ecs_cluster" "primary" {
  provider = aws.use1
  name     = "${var.app_name}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = merge(local.common_tags_use1, { component = "ecs-cluster" })
}

resource "aws_ecs_cluster" "secondary" {
  provider = aws.use2
  name     = "${var.app_name}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = merge(local.common_tags_use2, { component = "ecs-cluster" })
}
