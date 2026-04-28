###############################################################################
# EventBridge per-minute schedules for signal_collector + decision_engine.
###############################################################################

resource "aws_cloudwatch_event_rule" "signal_collector_primary" {
  provider            = aws.use1
  name                = "${var.app_name}-signal-collector-use1"
  description         = "Run signal_collector every minute (primary)"
  schedule_expression = "rate(1 minute)"
  tags                = merge(local.common_tags_use1, { component = "eventbridge" })
}

resource "aws_cloudwatch_event_target" "signal_collector_primary" {
  provider = aws.use1
  rule     = aws_cloudwatch_event_rule.signal_collector_primary.name
  arn      = aws_lambda_function.primary["signal_collector"].arn
  input    = jsonencode({})
}

resource "aws_lambda_permission" "signal_collector_primary" {
  provider      = aws.use1
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.primary["signal_collector"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.signal_collector_primary.arn
}

resource "aws_cloudwatch_event_rule" "decision_engine_primary" {
  provider            = aws.use1
  name                = "${var.app_name}-decision-engine-use1"
  description         = "Run decision_engine every minute (primary)"
  schedule_expression = "rate(1 minute)"
  tags                = merge(local.common_tags_use1, { component = "eventbridge" })
}

resource "aws_cloudwatch_event_target" "decision_engine_primary" {
  provider = aws.use1
  rule     = aws_cloudwatch_event_rule.decision_engine_primary.name
  arn      = aws_lambda_function.primary["decision_engine"].arn
}

resource "aws_lambda_permission" "decision_engine_primary" {
  provider      = aws.use1
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.primary["decision_engine"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.decision_engine_primary.arn
}

# Mirror in secondary
resource "aws_cloudwatch_event_rule" "signal_collector_secondary" {
  provider            = aws.use2
  name                = "${var.app_name}-signal-collector-use2"
  description         = "Run signal_collector every minute (secondary)"
  schedule_expression = "rate(1 minute)"
  tags                = merge(local.common_tags_use2, { component = "eventbridge" })
}

resource "aws_cloudwatch_event_target" "signal_collector_secondary" {
  provider = aws.use2
  rule     = aws_cloudwatch_event_rule.signal_collector_secondary.name
  arn      = aws_lambda_function.secondary["signal_collector"].arn
}

resource "aws_lambda_permission" "signal_collector_secondary" {
  provider      = aws.use2
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secondary["signal_collector"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.signal_collector_secondary.arn
}

resource "aws_cloudwatch_event_rule" "decision_engine_secondary" {
  provider            = aws.use2
  name                = "${var.app_name}-decision-engine-use2"
  description         = "Run decision_engine every minute (secondary)"
  schedule_expression = "rate(1 minute)"
  tags                = merge(local.common_tags_use2, { component = "eventbridge" })
}

resource "aws_cloudwatch_event_target" "decision_engine_secondary" {
  provider = aws.use2
  rule     = aws_cloudwatch_event_rule.decision_engine_secondary.name
  arn      = aws_lambda_function.secondary["decision_engine"].arn
}

resource "aws_lambda_permission" "decision_engine_secondary" {
  provider      = aws.use2
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.secondary["decision_engine"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.decision_engine_secondary.arn
}
