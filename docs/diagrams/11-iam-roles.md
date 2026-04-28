# Diagram 11 — IAM Roles

**Audience:** Security review.

```mermaid
graph LR
  subgraph PerRegion [Per region]
    LambdaRole[orchestrator-lambda-useN<br/>Lambda execution role]
    SfnRole[sfn-useN<br/>Step Functions exec role]
    CanaryRole[canary-useN<br/>Synthetics canary role]
    ECSExecRole[ecs-exec-useN<br/>ECS task execution role]
  end

  LambdaRole -->|ssm:Get/Put/Delete| SSM[(SSM /failover/{app}/{region}/*)]
  LambdaRole -->|cloudwatch:PutMetricData<br/>condition: namespace=Failover/{app}*| CW[(CW)]
  LambdaRole -->|s3:GetObject ListBucket| ProfileBucket[(profile bucket)]
  LambdaRole -->|s3:PutObject| AuditBucket[(audit bucket)]
  LambdaRole -->|sns:Publish| SNS[(account-level topic)]
  LambdaRole -->|kms:Decrypt GenerateDataKey| KMS[(KMS keys)]
  LambdaRole -->|rds:Describe*| Aurora[(Aurora cluster)]
  LambdaRole -->|states:StartExecution<br/>SendTaskSuccess SendTaskFailure| SFN[(Step Functions)]
  LambdaRole -->|health:DescribeEvents| Health[(AWS Health)]

  SfnRole -->|lambda:InvokeFunction| Lambdas[(orchestrator Lambdas)]
  SfnRole -->|sns:Publish| SNS

  CanaryRole -->|s3:Put canary/*| AuditBucket
  CanaryRole -->|cloudwatch:PutMetricData<br/>condition: namespace=CloudWatchSynthetics| CW
```

No `Action: "*"`. `Resource: "*"` only on actions AWS does not support
resource-level scoping for (CW PutMetricData with namespace condition;
Health DescribeEvents); each occurrence carries a
`# iam-policy-check: allow-wildcard` directive.
