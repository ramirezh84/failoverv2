"""Diagram 02 — Full network topology, both regions.

Render with:
    uv run python docs/diagrams/02-topology.py

Produces 02-topology.png and 02-topology.svg in the same directory. The
``diagrams-render-check`` CI job re-renders and diffs against the committed
files; commit fresh PNG/SVG whenever this script changes.
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Fargate
from diagrams.aws.database import RDS
from diagrams.aws.network import ELB, NLB, APIGateway, Route53, Endpoint
from diagrams.aws.security import ACM
from diagrams.onprem.queue import Kafka

GRAPH_ATTR = {"fontsize": "14", "bgcolor": "transparent", "labelloc": "t"}

with Diagram(
    "Failover Orchestrator — Network Topology",
    show=False,
    filename="docs/diagrams/02-topology",
    outformat=["png", "svg"],
    graph_attr=GRAPH_ATTR,
):
    r53 = Route53("Route 53\nfailover record")
    kafka = Kafka("On-prem Kafka\n(consumer-gated)")

    for region in ("us-east-1", "us-east-2"):
        with Cluster(f"VPC ({region})"):
            with Cluster("Routable subnets"):
                outer = NLB(f"Outer NLB\n(TLS, {region})")
                cert = ACM("ACM\n(self-signed POC)")
            with Cluster("Private subnets"):
                api_gw = APIGateway("API GW\n(optional)")
                inner_nlb = NLB("Inner NLB")
                alb = ELB("ALB")
                ecs = Fargate("ECS Fargate\n(warm standby ≥1)")
                aurora = RDS("Aurora\n(Global writer/reader)")
                vpce = Endpoint("VPC Endpoints\n(SSM/SNS/RDS/CW/...)")
            r53 >> Edge(label="DNS") >> outer
            outer >> Edge(label="TLS term") >> api_gw >> inner_nlb >> alb >> ecs
            ecs >> aurora
            ecs >> Edge(label="poll") >> kafka
            ecs >> vpce
            cert >> outer
