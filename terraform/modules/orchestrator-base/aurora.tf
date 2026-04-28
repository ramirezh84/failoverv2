###############################################################################
# Aurora Global Database. Writer pinned to primary region. SPEC §3.1 / §5.
# CLAUDE.md §2 #7: orchestrator never auto-promotes; this resource graph stays
# untouched at runtime.
###############################################################################

resource "random_password" "aurora_master" {
  length           = 32
  special          = true
  override_special = "!@#%^*-_=+"
}

resource "aws_secretsmanager_secret" "aurora_master_primary" {
  provider = aws.use1
  name     = "/${var.app_name}/aurora/master_password"
  tags     = merge(local.common_tags_use1, { component = "secret" })
}

resource "aws_secretsmanager_secret_version" "aurora_master_primary" {
  provider      = aws.use1
  secret_id     = aws_secretsmanager_secret.aurora_master_primary.id
  secret_string = random_password.aurora_master.result
}

resource "aws_db_subnet_group" "aurora_primary" {
  provider   = aws.use1
  name       = "${var.app_name}-aurora-subnets"
  subnet_ids = aws_subnet.primary_private[*].id
  tags       = merge(local.common_tags_use1, { component = "db-subnet-group" })
}

resource "aws_db_subnet_group" "aurora_secondary" {
  provider   = aws.use2
  name       = "${var.app_name}-aurora-subnets"
  subnet_ids = aws_subnet.secondary_private[*].id
  tags       = merge(local.common_tags_use2, { component = "db-subnet-group" })
}

resource "aws_security_group" "aurora_primary" {
  provider    = aws.use1
  name        = "${var.app_name}-aurora-sg"
  description = "PostgreSQL access from app SG"
  vpc_id      = aws_vpc.primary.id
  egress {
    description = "All egress within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.primary.cidr_block]
  }
  tags = merge(local.common_tags_use1, { component = "sg-aurora" })
}

resource "aws_security_group_rule" "aurora_primary_ingress_from_lambda" {
  provider                 = aws.use1
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.primary_lambda.id
  security_group_id        = aws_security_group.aurora_primary.id
  description              = "PostgreSQL from orchestrator Lambdas"
}

resource "aws_security_group" "aurora_secondary" {
  provider    = aws.use2
  name        = "${var.app_name}-aurora-sg"
  description = "PostgreSQL access from app SG"
  vpc_id      = aws_vpc.secondary.id
  egress {
    description = "All egress within VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.secondary.cidr_block]
  }
  tags = merge(local.common_tags_use2, { component = "sg-aurora" })
}

resource "aws_security_group_rule" "aurora_secondary_ingress_from_lambda" {
  provider                 = aws.use2
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.secondary_lambda.id
  security_group_id        = aws_security_group.aurora_secondary.id
  description              = "PostgreSQL from orchestrator Lambdas"
}

resource "aws_rds_global_cluster" "this" {
  provider                  = aws.use1
  global_cluster_identifier = "${var.app_name}-global"
  engine                    = "aurora-postgresql"
  engine_version            = var.aurora_engine_version
  database_name             = var.aurora_database_name
  storage_encrypted         = true
  deletion_protection       = true
}

resource "aws_rds_cluster" "primary" {
  provider                            = aws.use1
  cluster_identifier                  = "${var.app_name}-use1"
  global_cluster_identifier           = aws_rds_global_cluster.this.id
  engine                              = aws_rds_global_cluster.this.engine
  engine_version                      = aws_rds_global_cluster.this.engine_version
  database_name                       = aws_rds_global_cluster.this.database_name
  master_username                     = var.aurora_master_username
  master_password                     = random_password.aurora_master.result
  db_subnet_group_name                = aws_db_subnet_group.aurora_primary.name
  vpc_security_group_ids              = [aws_security_group.aurora_primary.id]
  storage_encrypted                   = true
  iam_database_authentication_enabled = true
  deletion_protection                 = true
  apply_immediately                   = true
  skip_final_snapshot                 = false
  final_snapshot_identifier           = "${var.app_name}-use1-final"
  backup_retention_period             = 7
  copy_tags_to_snapshot               = true
  tags                                = merge(local.common_tags_use1, { component = "aurora-cluster" })

  lifecycle {
    ignore_changes = [global_cluster_identifier]
  }
}

resource "aws_rds_cluster_instance" "primary_writer" {
  provider             = aws.use1
  identifier           = "${var.app_name}-use1-writer"
  cluster_identifier   = aws_rds_cluster.primary.id
  instance_class       = var.aurora_instance_class
  engine               = aws_rds_cluster.primary.engine
  engine_version       = aws_rds_cluster.primary.engine_version
  db_subnet_group_name = aws_db_subnet_group.aurora_primary.name
  publicly_accessible  = false
  apply_immediately    = true
  tags                 = merge(local.common_tags_use1, { component = "aurora-instance" })
}

resource "aws_rds_cluster" "secondary" {
  provider                            = aws.use2
  cluster_identifier                  = "${var.app_name}-use2"
  global_cluster_identifier           = aws_rds_global_cluster.this.id
  engine                              = aws_rds_global_cluster.this.engine
  engine_version                      = aws_rds_global_cluster.this.engine_version
  db_subnet_group_name                = aws_db_subnet_group.aurora_secondary.name
  vpc_security_group_ids              = [aws_security_group.aurora_secondary.id]
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_key.audit_secondary.arn
  iam_database_authentication_enabled = true
  deletion_protection                 = true
  apply_immediately                   = true
  skip_final_snapshot                 = false
  final_snapshot_identifier           = "${var.app_name}-use2-final"
  copy_tags_to_snapshot               = true
  tags                                = merge(local.common_tags_use2, { component = "aurora-cluster" })

  depends_on = [aws_rds_cluster_instance.primary_writer]
}

resource "aws_rds_cluster_instance" "secondary_reader" {
  provider             = aws.use2
  identifier           = "${var.app_name}-use2-reader"
  cluster_identifier   = aws_rds_cluster.secondary.id
  instance_class       = var.aurora_instance_class
  engine               = aws_rds_cluster.secondary.engine
  engine_version       = aws_rds_cluster.secondary.engine_version
  db_subnet_group_name = aws_db_subnet_group.aurora_secondary.name
  publicly_accessible  = false
  apply_immediately    = true
  tags                 = merge(local.common_tags_use2, { component = "aurora-instance" })
}
