###############################################################################
# Self-signed CA + leaf cert per region for the outer NLB TLS listener.
# SPEC §2.1 POC-A — JPMC port supplies the internal CA.
###############################################################################

resource "tls_private_key" "ca" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_self_signed_cert" "ca" {
  private_key_pem = tls_private_key.ca.private_key_pem
  subject {
    common_name  = "${var.app_name}-poc-ca"
    organization = "failoverv2"
  }
  validity_period_hours = 8760 # 1 year
  is_ca_certificate     = true
  allowed_uses          = ["cert_signing", "crl_signing", "digital_signature", "key_encipherment"]
}

resource "tls_private_key" "leaf_primary" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_cert_request" "leaf_primary" {
  private_key_pem = tls_private_key.leaf_primary.private_key_pem
  subject {
    common_name = "${var.app_name}.${var.primary_region}.failover.internal"
  }
  dns_names = [
    "${var.app_name}.${var.primary_region}.failover.internal",
    "${var.app_name}.failover.internal",
  ]
}

resource "tls_locally_signed_cert" "leaf_primary" {
  cert_request_pem      = tls_cert_request.leaf_primary.cert_request_pem
  ca_private_key_pem    = tls_private_key.ca.private_key_pem
  ca_cert_pem           = tls_self_signed_cert.ca.cert_pem
  validity_period_hours = 8760
  allowed_uses          = ["server_auth", "digital_signature", "key_encipherment"]
}

resource "tls_private_key" "leaf_secondary" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_cert_request" "leaf_secondary" {
  private_key_pem = tls_private_key.leaf_secondary.private_key_pem
  subject {
    common_name = "${var.app_name}.${var.secondary_region}.failover.internal"
  }
  dns_names = [
    "${var.app_name}.${var.secondary_region}.failover.internal",
    "${var.app_name}.failover.internal",
  ]
}

resource "tls_locally_signed_cert" "leaf_secondary" {
  cert_request_pem      = tls_cert_request.leaf_secondary.cert_request_pem
  ca_private_key_pem    = tls_private_key.ca.private_key_pem
  ca_cert_pem           = tls_self_signed_cert.ca.cert_pem
  validity_period_hours = 8760
  allowed_uses          = ["server_auth", "digital_signature", "key_encipherment"]
}

resource "aws_acm_certificate" "primary" {
  provider          = aws.use1
  private_key       = tls_private_key.leaf_primary.private_key_pem
  certificate_body  = tls_locally_signed_cert.leaf_primary.cert_pem
  certificate_chain = tls_self_signed_cert.ca.cert_pem
  tags              = merge(local.common_tags_use1, { component = "acm" })

  lifecycle { create_before_destroy = true }
}

resource "aws_acm_certificate" "secondary" {
  provider          = aws.use2
  private_key       = tls_private_key.leaf_secondary.private_key_pem
  certificate_body  = tls_locally_signed_cert.leaf_secondary.cert_pem
  certificate_chain = tls_self_signed_cert.ca.cert_pem
  tags              = merge(local.common_tags_use2, { component = "acm" })

  lifecycle { create_before_destroy = true }
}
