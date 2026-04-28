###############################################################################
# Outer NLB (TLS, internet-facing) → ALB → ECS.
# We omit the API Gateway + inner NLB for the POC test harness baseline; these
# can be added per-app via profile.network.api_gw_id_*. The orchestrator
# behavior under test does not depend on the inner-NLB hop being present.
###############################################################################

# ---- Primary region ----
resource "aws_lb" "outer_primary" {
  provider                         = aws.use1
  name                             = "${var.app_name}-outer-use1"
  internal                         = false
  load_balancer_type               = "network"
  subnets                          = var.routable_subnet_ids_primary
  enable_cross_zone_load_balancing = true
  tags                             = merge(local.common_tags_use1, { component = "outer-nlb" })
}

resource "aws_lb_target_group" "outer_to_alb_primary" {
  provider    = aws.use1
  name        = "${var.app_name}-outer-tg-use1"
  port        = 80
  protocol    = "TCP"
  target_type = "alb"
  vpc_id      = var.vpc_id_primary
  health_check {
    protocol            = "HTTP"
    path                = "/health"
    port                = "80"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 10
    timeout             = 5
  }
  tags = merge(local.common_tags_use1, { component = "tg-outer" })
}

resource "aws_lb_listener" "outer_primary_tls" {
  provider          = aws.use1
  load_balancer_arn = aws_lb.outer_primary.arn
  port              = 443
  protocol          = "TLS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn_primary
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.outer_to_alb_primary.arn
  }
  tags = merge(local.common_tags_use1, { component = "listener-tls" })
}

resource "aws_lb" "alb_primary" {
  provider           = aws.use1
  name               = "${var.app_name}-alb-use1"
  internal           = true
  load_balancer_type = "application"
  subnets            = var.private_subnet_ids_primary
  security_groups    = [aws_security_group.alb_primary.id]
  tags               = merge(local.common_tags_use1, { component = "alb" })
}

resource "aws_lb_target_group" "alb_primary" {
  provider    = aws.use1
  name        = "${var.app_name}-alb-tg-use1"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id_primary
  health_check {
    path                = "/health"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 10
    timeout             = 5
  }
  tags = merge(local.common_tags_use1, { component = "tg-alb" })
}

resource "aws_lb_listener" "alb_primary" {
  provider          = aws.use1
  load_balancer_arn = aws_lb.alb_primary.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.alb_primary.arn
  }
}

resource "aws_lb_target_group_attachment" "outer_to_alb_primary" {
  provider         = aws.use1
  target_group_arn = aws_lb_target_group.outer_to_alb_primary.arn
  target_id        = aws_lb.alb_primary.arn
  port             = 80
  depends_on       = [aws_lb_listener.alb_primary]
}

# ---- Secondary region ----
resource "aws_lb" "outer_secondary" {
  provider                         = aws.use2
  name                             = "${var.app_name}-outer-use2"
  internal                         = false
  load_balancer_type               = "network"
  subnets                          = var.routable_subnet_ids_secondary
  enable_cross_zone_load_balancing = true
  tags                             = merge(local.common_tags_use2, { component = "outer-nlb" })
}

resource "aws_lb_target_group" "outer_to_alb_secondary" {
  provider    = aws.use2
  name        = "${var.app_name}-outer-tg-use2"
  port        = 80
  protocol    = "TCP"
  target_type = "alb"
  vpc_id      = var.vpc_id_secondary
  health_check {
    protocol            = "HTTP"
    path                = "/health"
    port                = "80"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 10
    timeout             = 5
  }
  tags = merge(local.common_tags_use2, { component = "tg-outer" })
}

resource "aws_lb_listener" "outer_secondary_tls" {
  provider          = aws.use2
  load_balancer_arn = aws_lb.outer_secondary.arn
  port              = 443
  protocol          = "TLS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn_secondary
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.outer_to_alb_secondary.arn
  }
  tags = merge(local.common_tags_use2, { component = "listener-tls" })
}

resource "aws_lb" "alb_secondary" {
  provider           = aws.use2
  name               = "${var.app_name}-alb-use2"
  internal           = true
  load_balancer_type = "application"
  subnets            = var.private_subnet_ids_secondary
  security_groups    = [aws_security_group.alb_secondary.id]
  tags               = merge(local.common_tags_use2, { component = "alb" })
}

resource "aws_lb_target_group" "alb_secondary" {
  provider    = aws.use2
  name        = "${var.app_name}-alb-tg-use2"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id_secondary
  health_check {
    path                = "/health"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 10
    timeout             = 5
  }
  tags = merge(local.common_tags_use2, { component = "tg-alb" })
}

resource "aws_lb_listener" "alb_secondary" {
  provider          = aws.use2
  load_balancer_arn = aws_lb.alb_secondary.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.alb_secondary.arn
  }
}

resource "aws_lb_target_group_attachment" "outer_to_alb_secondary" {
  provider         = aws.use2
  target_group_arn = aws_lb_target_group.outer_to_alb_secondary.arn
  target_id        = aws_lb.alb_secondary.arn
  port             = 80
  depends_on       = [aws_lb_listener.alb_secondary]
}

# Per-region routable hostname under the private hosted zone.
resource "aws_route53_record" "regional_primary" {
  provider = aws.use1
  zone_id  = var.route53_zone_id
  name     = "${var.app_name}.${var.primary_region}.${var.route53_zone_name}"
  type     = "A"
  alias {
    name                   = aws_lb.outer_primary.dns_name
    zone_id                = aws_lb.outer_primary.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "regional_secondary" {
  provider = aws.use1
  zone_id  = var.route53_zone_id
  name     = "${var.app_name}.${var.secondary_region}.${var.route53_zone_name}"
  type     = "A"
  alias {
    name                   = aws_lb.outer_secondary.dns_name
    zone_id                = aws_lb.outer_secondary.zone_id
    evaluate_target_health = true
  }
}
