module "orchestrator_base" {
  source           = "../../../modules/orchestrator-base"
  providers        = { aws.use1 = aws.use1, aws.use2 = aws.use2 }
  app_name         = var.app_name
  primary_region   = var.primary_region
  secondary_region = var.secondary_region
}

module "test_harness_app" {
  source           = "../../../modules/test-harness-app"
  providers        = { aws.use1 = aws.use1, aws.use2 = aws.use2 }
  app_name         = var.app_name
  primary_region   = var.primary_region
  secondary_region = var.secondary_region

  vpc_id_primary                = module.orchestrator_base.vpc_id_primary
  vpc_id_secondary              = module.orchestrator_base.vpc_id_secondary
  private_subnet_ids_primary    = module.orchestrator_base.private_subnet_ids_primary
  private_subnet_ids_secondary  = module.orchestrator_base.private_subnet_ids_secondary
  routable_subnet_ids_primary   = module.orchestrator_base.routable_subnet_ids_primary
  routable_subnet_ids_secondary = module.orchestrator_base.routable_subnet_ids_secondary
  ecs_cluster_arn_primary       = module.orchestrator_base.ecs_cluster_arn_primary
  ecs_cluster_arn_secondary     = module.orchestrator_base.ecs_cluster_arn_secondary
  acm_certificate_arn_primary   = module.orchestrator_base.acm_certificate_arn_primary
  acm_certificate_arn_secondary = module.orchestrator_base.acm_certificate_arn_secondary
  route53_zone_id               = module.orchestrator_base.route53_zone_id
  route53_zone_name             = module.orchestrator_base.route53_zone_name
}
