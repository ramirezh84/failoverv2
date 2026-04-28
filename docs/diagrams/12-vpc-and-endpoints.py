"""Diagram 12 — Per-region VPC layout and VPC endpoints.

Render with:
    uv run python docs/diagrams/12-vpc-and-endpoints.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import (
    InternetGateway,
    PrivateSubnet,
    PublicSubnet,
    RouteTable,
    Endpoint,
)

with Diagram(
    "VPC + Endpoints",
    show=False,
    filename="docs/diagrams/12-vpc-and-endpoints",
    outformat=["png", "svg"],
    graph_attr={"fontsize": "14", "bgcolor": "transparent"},
):  # noqa: SIM117 — diagrams library requires nested context for the cluster hierarchy
    with Cluster("VPC us-east-1 (10.10.0.0/16)"):
        igw = InternetGateway("IGW")
        with Cluster("Routable subnets (a/b/c)"):
            routable = PublicSubnet("/24 each")
            rt_pub = RouteTable("RT routable")
        with Cluster("Private subnets (a/b/c)"):
            private = PrivateSubnet("/24 each")
            rt_priv = RouteTable("RT private")
            with Cluster("Interface endpoints (12)"):
                vpce_ssm = Endpoint("ssm")
                vpce_sns = Endpoint("sns")
                vpce_cw = Endpoint("monitoring")
                vpce_logs = Endpoint("logs")
                vpce_rds = Endpoint("rds")
                vpce_states = Endpoint("states")
                vpce_synth = Endpoint("synthetics")
                vpce_events = Endpoint("events")
                vpce_lambda = Endpoint("lambda")
                vpce_sts = Endpoint("sts")
                vpce_sm = Endpoint("secretsmanager")
                vpce_health = Endpoint("health\n(AZ-restricted)")
            with Cluster("Gateway endpoint"):
                vpce_s3 = Endpoint("s3")
            lambdas = Lambda("Orchestrator Lambdas\n(VPC-attached)")
        igw >> rt_pub >> routable
        rt_priv >> private
        (
            lambdas
            >> Edge(label="HTTPS")
            >> [
                vpce_ssm,
                vpce_sns,
                vpce_cw,
                vpce_logs,
                vpce_rds,
                vpce_states,
                vpce_synth,
                vpce_events,
                vpce_lambda,
                vpce_sts,
                vpce_sm,
                vpce_health,
            ]
        )
        lambdas >> vpce_s3
