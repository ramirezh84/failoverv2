"""Diagram 12 — Per-region VPC layout and VPC endpoints.

Render with:
    uv run python docs/diagrams/12-vpc-and-endpoints.py
"""

# ruff: noqa: I001

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import (
    InternetGateway,
    PrivateSubnet,
    PublicSubnet,
    RouteTable,
    VPC,
    VPCEndpoint,
)

with Diagram(
    "VPC + Endpoints",
    show=False,
    filename="docs/diagrams/12-vpc-and-endpoints",
    outformat=["png", "svg"],
    graph_attr={"fontsize": "14", "bgcolor": "transparent"},
):
    with Cluster("VPC us-east-1 (10.10.0.0/16)"):
        igw = InternetGateway("IGW")
        with Cluster("Routable subnets (a/b/c)"):
            routable = PublicSubnet("/24 each")
            rt_pub = RouteTable("RT routable")
        with Cluster("Private subnets (a/b/c)"):
            private = PrivateSubnet("/24 each")
            rt_priv = RouteTable("RT private")
            with Cluster("Interface endpoints"):
                vpce_ssm = VPCEndpoint("ssm")
                vpce_sns = VPCEndpoint("sns")
                vpce_cw = VPCEndpoint("monitoring")
                vpce_logs = VPCEndpoint("logs")
                vpce_rds = VPCEndpoint("rds")
                vpce_states = VPCEndpoint("states")
                vpce_health = VPCEndpoint("health")
            with Cluster("Gateway endpoint"):
                vpce_s3 = VPCEndpoint("s3")
            lambdas = Lambda("Orchestrator Lambdas\n(VPC-attached)")
        igw >> rt_pub >> routable
        rt_priv >> private
        lambdas >> Edge(label="HTTPS") >> [vpce_ssm, vpce_sns, vpce_cw, vpce_logs, vpce_rds, vpce_states, vpce_health]
        lambdas >> vpce_s3
