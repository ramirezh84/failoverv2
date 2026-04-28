###############################################################################
# Security groups for the topology Outer NLB → API GW → Inner NLB → ALB → ECS.
###############################################################################

resource "aws_security_group" "outer_nlb_primary" {
  provider    = aws.use1
  name        = "${var.app_name}-outer-nlb"
  description = "Outer NLB ingress on 443"
  vpc_id      = var.vpc_id_primary
  ingress {
    description = "TLS from anywhere (POC; JPMC port restricts)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "All egress within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(local.common_tags_use1, { component = "sg-outer-nlb" })
}

resource "aws_security_group" "alb_primary" {
  provider    = aws.use1
  name        = "${var.app_name}-alb"
  description = "ALB ingress on 80"
  vpc_id      = var.vpc_id_primary
  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  egress {
    description = "All egress to VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }
  tags = merge(local.common_tags_use1, { component = "sg-alb" })
}

resource "aws_security_group" "ecs_primary" {
  provider    = aws.use1
  name        = "${var.app_name}-ecs"
  description = "ECS task ingress from ALB"
  vpc_id      = var.vpc_id_primary
  ingress {
    description     = "From ALB SG"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_primary.id]
  }
  egress {
    description = "All egress within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }
  tags = merge(local.common_tags_use1, { component = "sg-ecs" })
}

resource "aws_security_group" "outer_nlb_secondary" {
  provider    = aws.use2
  name        = "${var.app_name}-outer-nlb"
  description = "Outer NLB ingress on 443"
  vpc_id      = var.vpc_id_secondary
  ingress {
    description = "TLS from anywhere (POC)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "All egress within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(local.common_tags_use2, { component = "sg-outer-nlb" })
}

resource "aws_security_group" "alb_secondary" {
  provider    = aws.use2
  name        = "${var.app_name}-alb"
  description = "ALB ingress on 80"
  vpc_id      = var.vpc_id_secondary
  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  egress {
    description = "All egress to VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }
  tags = merge(local.common_tags_use2, { component = "sg-alb" })
}

resource "aws_security_group" "ecs_secondary" {
  provider    = aws.use2
  name        = "${var.app_name}-ecs"
  description = "ECS task ingress from ALB"
  vpc_id      = var.vpc_id_secondary
  ingress {
    description     = "From ALB SG"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_secondary.id]
  }
  egress {
    description = "All egress within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }
  tags = merge(local.common_tags_use2, { component = "sg-ecs" })
}
