"""Diagram 13 — What the test-harness Terraform module deploys.

Render with:
    uv run python docs/diagrams/13-test-harness.py
"""

# ruff: noqa: I001

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Fargate
from diagrams.aws.database import RDS
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import ELB, NLB, Route53

with Diagram(
    "Test Harness App",
    show=False,
    filename="docs/diagrams/13-test-harness",
    outformat=["png", "svg"],
    graph_attr={"fontsize": "14", "bgcolor": "transparent"},
):
    r53 = Route53("R53 failover record\ntest-app.failover.internal")
    canary = Cloudwatch("Synthetics canary\n(opposite region)")

    for region in ("us-east-1", "us-east-2"):
        with Cluster(region):
            outer = NLB(f"Outer NLB (TLS)\n{region}")
            alb = ELB(f"Inner ALB\n{region}")
            ecs = Fargate("test-app\n(nginx:1.27)")
            rds = RDS("Aurora\nGlobal member")
            r53 >> outer >> alb >> ecs
            ecs >> rds
            canary >> Edge(label="probes") >> outer
