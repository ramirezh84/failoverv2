###############################################################################
# Makefile — operator workflow per SPEC §8.7.1.
###############################################################################

SHELL          := /bin/bash
.SHELLFLAGS    := -eu -o pipefail -c
.DEFAULT_GOAL  := help

AWS_PROFILE    ?= tbed
APP            ?= test-app
PRIMARY_REGION ?= us-east-1
SECONDARY_REGION ?= us-east-2

ROOT           := $(CURDIR)
TF_BASE        := $(ROOT)/terraform/apps/$(APP)/base
TF_RUNTIME     := $(ROOT)/terraform/apps/$(APP)/runtime
TF_VARS        := -var-file=$(ROOT)/terraform/apps/$(APP)/shared.tfvars

RESULTS_DIR    := $(ROOT)/tests/results
SCENARIO_RESET_TIMEOUT := 30

UV             := uv

# AWS CLI helper that always picks up the profile.
AWS            := AWS_PROFILE=$(AWS_PROFILE) aws --region $(PRIMARY_REGION)

###############################################################################
# Help
###############################################################################
.PHONY: help
help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_.-]+:.*?## / { printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

###############################################################################
# Bootstrap
###############################################################################
.PHONY: bootstrap
bootstrap: ## One-time: create S3 state bucket + DDB lock table, sed backend.tf placeholders
	bash $(ROOT)/scripts/terraform_bootstrap.sh

###############################################################################
# Harness lifecycle (SPEC §8.7.1)
###############################################################################
.PHONY: harness-up
harness-up: ## Apply base + runtime layers (idempotent). Reuses live infra if up.
	@echo "==> Applying base layer ($(TF_BASE)) — slow if cold (Aurora 15-25 min)."
	cd $(TF_BASE) && AWS_PROFILE=$(AWS_PROFILE) terraform init -input=false
	cd $(TF_BASE) && AWS_PROFILE=$(AWS_PROFILE) terraform apply $(TF_VARS) -auto-approve
	@echo "==> Uploading profile to base profile bucket."
	$(MAKE) upload-profile
	@echo "==> Applying runtime layer ($(TF_RUNTIME))."
	$(MAKE) runtime-apply

.PHONY: runtime-apply
runtime-apply: ## Apply only the runtime layer (Lambdas, Step Functions, etc.). <5 min typical.
	cd $(TF_RUNTIME) && AWS_PROFILE=$(AWS_PROFILE) terraform init -input=false
	cd $(TF_RUNTIME) && AWS_PROFILE=$(AWS_PROFILE) terraform apply $(TF_VARS) \
	  -var "base_state_bucket=$$(AWS_PROFILE=$(AWS_PROFILE) $(AWS) sts get-caller-identity --query Account --output text | xargs -I{} echo failoverv2-tfstate-{})" \
	  -auto-approve

.PHONY: harness-down
harness-down: ## Destroy everything. Use only when explicitly stable or for clean restart.
	@printf "Are you sure you want to destroy %s harness? [yes/N] " "$(APP)"
	@read CONFIRM; if [ "$$CONFIRM" != "yes" ]; then echo "aborted"; exit 1; fi
	cd $(TF_RUNTIME) && AWS_PROFILE=$(AWS_PROFILE) terraform destroy $(TF_VARS) \
	  -var "base_state_bucket=$$(AWS_PROFILE=$(AWS_PROFILE) $(AWS) sts get-caller-identity --query Account --output text | xargs -I{} echo failoverv2-tfstate-{})" \
	  -auto-approve
	cd $(TF_BASE) && AWS_PROFILE=$(AWS_PROFILE) terraform destroy $(TF_VARS) -auto-approve

.PHONY: upload-profile
upload-profile: ## Upload profiles/$(APP).yaml to the base layer's profile bucket.
	@PROFILE_BUCKET=$$(cd $(TF_BASE) && AWS_PROFILE=$(AWS_PROFILE) terraform output -raw profile_bucket_primary); \
	echo "==> Uploading profiles/$(APP).yaml to s3://$$PROFILE_BUCKET/$(APP)/profile.yaml"; \
	$(AWS) s3 cp $(ROOT)/profiles/$(APP).yaml "s3://$$PROFILE_BUCKET/$(APP)/profile.yaml"

###############################################################################
# Scenario tests (SPEC §8.7.2)
###############################################################################
.PHONY: scenarios-all stable-suite scenarios-parallel scenarios-sequential
scenarios-all: scenarios-parallel scenarios-sequential ## Parallel batch then sequential batch; consolidated report.

scenarios-parallel: ## Non-mutating scenarios (1, 2, 3, 5, 13, 14) in parallel.
	@mkdir -p $(RESULTS_DIR)
	$(UV) run pytest tests/chaos/test_scenario_01_deployment_503_blip.py \
	                 tests/chaos/test_scenario_02_alb_unhealthy_only.py \
	                 tests/chaos/test_scenario_03_single_az_outage.py \
	                 tests/chaos/test_scenario_05_api_gw_5xx_storm.py \
	                 tests/chaos/test_scenario_13_profile_change_mid_incident.py \
	                 tests/chaos/test_scenario_14_canary_self_failure.py \
	                 -m chaos -n auto

scenarios-sequential: ## Mutating scenarios (4, 7, 8, 9, 10, 11, 12) sequential.
	@mkdir -p $(RESULTS_DIR)
	$(UV) run pytest tests/chaos/test_scenario_04_full_region_outage.py \
	                 tests/chaos/test_scenario_07_dry_run.py \
	                 tests/chaos/test_scenario_08_manual_with_aurora_approval.py \
	                 tests/chaos/test_scenario_09_aurora_confirmation_timeout.py \
	                 tests/chaos/test_scenario_10_failback.py \
	                 tests/chaos/test_scenario_11_mid_failover_lambda_crash.py \
	                 tests/chaos/test_scenario_12_split_brain_attempt.py \
	                 -m chaos

stable-suite: ## Run scenarios-all THREE consecutive times; pass only if every run is clean.
	for i in 1 2 3; do \
	  echo "==> stable-suite run $$i/3"; \
	  $(MAKE) scenarios-all || { echo "stable-suite failed on run $$i"; exit 1; }; \
	done
	@echo "stable-suite PASSED — 3 consecutive clean runs."

scenario-%: ## Run scenario N (1-14). Produces tests/results/scenario-N.json.
	@mkdir -p $(RESULTS_DIR)
	@N=$*; \
	FILE=$$(find tests/chaos -name "test_scenario_$$(printf '%02d' $$N)_*.py" | head -1); \
	if [ -z "$$FILE" ]; then echo "Scenario $$N not found"; exit 1; fi; \
	$(UV) run pytest "$$FILE" -m chaos -v --no-cov

.PHONY: scenario-reset
scenario-reset: ## Reset orchestrator runtime state (SSM, control metric, in-flight SFN). <30s.
	bash $(ROOT)/scripts/scenario_reset.sh $(APP) $(PRIMARY_REGION) $(SECONDARY_REGION)

###############################################################################
# Logs / state inspection
###############################################################################
.PHONY: logs-tail
logs-tail: ## Tail every relevant Lambda's logs for scenario N (SCENARIO=N).
	@: $${SCENARIO?usage: make logs-tail SCENARIO=N}
	bash $(ROOT)/scripts/logs_tail.sh $(APP) $(PRIMARY_REGION) $(SCENARIO)

.PHONY: state-dump
state-dump: ## Dump full orchestrator state (SSM, alarms, Step Functions, S3 audit) as JSON.
	bash $(ROOT)/scripts/state_dump.sh $(APP) $(PRIMARY_REGION) $(SECONDARY_REGION)

###############################################################################
# Quality
###############################################################################
.PHONY: lint test
lint: ## ruff + mypy.
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy lib lambdas cli

test: ## pytest with coverage.
	$(UV) run pytest

###############################################################################
# Internal helpers
###############################################################################
.PHONY: _state_bucket_name
_state_bucket_name:
	@$(AWS) sts get-caller-identity --query 'Account' --output text \
	  | xargs -I{} echo "failoverv2-tfstate-{}"
