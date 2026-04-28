###############################################################################
# S3 buckets:
#  * profile bucket — versioned, CRR cross-region. Decision Engine reads from
#    the in-region bucket (SPEC §3.1).
#  * audit bucket — versioned, Object Lock (governance), CRR. Decision and
#    executor records.
###############################################################################

resource "aws_kms_key" "audit_primary" {
  provider                = aws.use1
  description             = "${var.app_name} audit & profile bucket encryption (primary)"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  tags                    = merge(local.common_tags_use1, { component = "kms" })
}

resource "aws_kms_key" "audit_secondary" {
  provider                = aws.use2
  description             = "${var.app_name} audit & profile bucket encryption (secondary)"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  tags                    = merge(local.common_tags_use2, { component = "kms" })
}

resource "aws_s3_bucket" "profile_primary" {
  provider      = aws.use1
  bucket        = "${var.app_name}-profiles-${data.aws_caller_identity.current.account_id}-use1"
  force_destroy = false
  tags          = merge(local.common_tags_use1, { component = "s3-profile" })
}

resource "aws_s3_bucket" "profile_secondary" {
  provider      = aws.use2
  bucket        = "${var.app_name}-profiles-${data.aws_caller_identity.current.account_id}-use2"
  force_destroy = false
  tags          = merge(local.common_tags_use2, { component = "s3-profile" })
}

resource "aws_s3_bucket_versioning" "profile_primary" {
  provider = aws.use1
  bucket   = aws_s3_bucket.profile_primary.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "profile_secondary" {
  provider = aws.use2
  bucket   = aws_s3_bucket.profile_secondary.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "profile_primary" {
  provider = aws.use1
  bucket   = aws_s3_bucket.profile_primary.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit_primary.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "profile_secondary" {
  provider = aws.use2
  bucket   = aws_s3_bucket.profile_secondary.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit_secondary.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "profile_primary" {
  provider                = aws.use1
  bucket                  = aws_s3_bucket.profile_primary.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "profile_secondary" {
  provider                = aws.use2
  bucket                  = aws_s3_bucket.profile_secondary.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Audit bucket (with Object Lock). Object Lock requires bucket created with
# the option enabled at creation time.
resource "aws_s3_bucket" "audit_primary" {
  provider            = aws.use1
  bucket              = "${var.app_name}-audit-${data.aws_caller_identity.current.account_id}-use1"
  object_lock_enabled = true
  force_destroy       = false
  tags                = merge(local.common_tags_use1, { component = "s3-audit" })
}

resource "aws_s3_bucket" "audit_secondary" {
  provider            = aws.use2
  bucket              = "${var.app_name}-audit-${data.aws_caller_identity.current.account_id}-use2"
  object_lock_enabled = true
  force_destroy       = false
  tags                = merge(local.common_tags_use2, { component = "s3-audit" })
}

resource "aws_s3_bucket_versioning" "audit_primary" {
  provider = aws.use1
  bucket   = aws_s3_bucket.audit_primary.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "audit_secondary" {
  provider = aws.use2
  bucket   = aws_s3_bucket.audit_secondary.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_object_lock_configuration" "audit_primary" {
  provider = aws.use1
  bucket   = aws_s3_bucket.audit_primary.id
  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.audit_object_lock_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.audit_primary]
}

resource "aws_s3_bucket_object_lock_configuration" "audit_secondary" {
  provider = aws.use2
  bucket   = aws_s3_bucket.audit_secondary.id
  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.audit_object_lock_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.audit_secondary]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_primary" {
  provider = aws.use1
  bucket   = aws_s3_bucket.audit_primary.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit_primary.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_secondary" {
  provider = aws.use2
  bucket   = aws_s3_bucket.audit_secondary.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit_secondary.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit_primary" {
  provider                = aws.use1
  bucket                  = aws_s3_bucket.audit_primary.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "audit_secondary" {
  provider                = aws.use2
  bucket                  = aws_s3_bucket.audit_secondary.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
