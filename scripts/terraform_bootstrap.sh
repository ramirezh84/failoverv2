#!/usr/bin/env bash
# One-time bootstrap: create the Terraform state bucket + DynamoDB lock table
# in account `tbed`. Idempotent. After bootstrap, sed in the bucket name into
# every backend.tf.
set -euo pipefail

: "${AWS_PROFILE:=tbed}"
ACCOUNT_ID="$(aws --profile "$AWS_PROFILE" sts get-caller-identity --query Account --output text)"
REGION="us-east-1"
BUCKET="failoverv2-tfstate-${ACCOUNT_ID}"
LOCK_TABLE="failoverv2-tfstate-lock"

echo "Bootstrapping Terraform backend for account $ACCOUNT_ID in $REGION"
echo "  bucket=$BUCKET  lock_table=$LOCK_TABLE"

if ! aws --profile "$AWS_PROFILE" --region "$REGION" s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  aws --profile "$AWS_PROFILE" --region "$REGION" s3api create-bucket --bucket "$BUCKET"
  aws --profile "$AWS_PROFILE" --region "$REGION" s3api put-bucket-versioning \
    --bucket "$BUCKET" --versioning-configuration Status=Enabled
  aws --profile "$AWS_PROFILE" --region "$REGION" s3api put-bucket-encryption \
    --bucket "$BUCKET" --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  aws --profile "$AWS_PROFILE" --region "$REGION" s3api put-public-access-block \
    --bucket "$BUCKET" --public-access-block-configuration \
    'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
  echo "Created bucket $BUCKET"
else
  echo "Bucket $BUCKET already exists"
fi

if ! aws --profile "$AWS_PROFILE" --region "$REGION" dynamodb describe-table --table-name "$LOCK_TABLE" >/dev/null 2>&1; then
  aws --profile "$AWS_PROFILE" --region "$REGION" dynamodb create-table \
    --table-name "$LOCK_TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST
  echo "Created lock table $LOCK_TABLE"
else
  echo "Lock table $LOCK_TABLE already exists"
fi

# Sed the bucket name into every backend.tf. The PLACEHOLDER token is what
# every backend.tf ships with; a real apply replaces it with $BUCKET.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
find "$ROOT/terraform/apps" -name 'backend.tf' -print0 | while IFS= read -r -d '' f; do
  if grep -q "failoverv2-tfstate-PLACEHOLDER" "$f"; then
    sed -i.bak "s|failoverv2-tfstate-PLACEHOLDER|$BUCKET|g" "$f"
    rm -f "${f}.bak"
    echo "Replaced placeholder in $f"
  fi
done

echo
echo "Done. Now run: cd terraform/apps/test-app/base && terraform init && terraform apply"
