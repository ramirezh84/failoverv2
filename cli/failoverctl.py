"""failoverctl — operator CLI per SPEC §8.5.

Wraps boto3 directly. Picks up AWS credentials via AWS_PROFILE (default
``tbed``) and the standard SDK chain. Outputs JSON for downstream tooling.

Subcommands:
    status   — current SSM state, latest decision, latest Step Functions execution
    failover — invoke manual_trigger Lambda (direction=failover)
    failback — invoke manual_trigger Lambda (direction=failback)
    dryrun   — invoke manual_trigger Lambda (direction=dryrun)
    approve  — invoke approval_callback Lambda (decision=approve)
    abort    — invoke approval_callback Lambda (decision=abort)
    drain    — invoke indicator_updater Lambda directly with role=DRAINING
    history  — list recent Step Functions executions and S3 audit entries
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import boto3


def _client(service: str, region: str) -> Any:
    """Construct a boto3 client; the CLI runs outside the VPC, so the
    standard regional public endpoint is correct."""
    profile = os.environ.get("AWS_PROFILE", "tbed")
    session = boto3.Session(profile_name=profile)
    return session.client(service, region_name=region)  # type: ignore[call-overload]


def _region_for(_app: str, region_arg: str | None) -> str:
    if region_arg:
        return region_arg
    return os.environ.get("AWS_REGION") or "us-east-1"


def _invoke(function_name: str, region: str, payload: dict[str, Any]) -> dict[str, Any]:
    lam = _client("lambda", region)
    resp = lam.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    body = resp["Payload"].read().decode("utf-8")
    parsed = json.loads(body) if body else {}
    if resp.get("FunctionError"):
        sys.stderr.write(f"Lambda returned FunctionError: {resp['FunctionError']}\n")
        sys.stderr.write(json.dumps(parsed, indent=2) + "\n")
        sys.exit(2)
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, default=str, sort_keys=True))


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    region = _region_for(args.app, args.region)
    ssm = _client("ssm", region)

    out: dict[str, Any] = {"app": args.app, "region": region}
    for name in ("role", "decision", "in_flight"):
        try:
            r = ssm.get_parameter(Name=f"/failover/{args.app}/{region}/{name}")
            out[name] = r["Parameter"]["Value"]
        except ssm.exceptions.ParameterNotFound:
            out[name] = None

    sfn = _client("stepfunctions", region)
    sm_failover = f"arn:aws:states:{region}:{_account_id()}:stateMachine:{args.app}-failover"
    sm_failback = f"arn:aws:states:{region}:{_account_id()}:stateMachine:{args.app}-failback"
    out["recent_failover_executions"] = _list_executions(sfn, sm_failover, limit=5)
    out["recent_failback_executions"] = _list_executions(sfn, sm_failback, limit=5)
    _print(out)
    return 0


def cmd_failover(args: argparse.Namespace) -> int:
    return _trigger(args.app, args.region, "failover", args.operator, args.dry_run)


def cmd_failback(args: argparse.Namespace) -> int:
    return _trigger(args.app, args.region, "failback", args.operator, args.dry_run)


def cmd_dryrun(args: argparse.Namespace) -> int:
    return _trigger(args.app, args.region, "dryrun", args.operator, dry_run=True)


def _trigger(app: str, region: str | None, direction: str, operator: str, dry_run: bool) -> int:
    region = _region_for(app, region)
    function = f"{app}-manual_trigger-{_region_suffix(region)}"
    out = _invoke(
        function, region, {"direction": direction, "operator": operator, "dry_run": dry_run}
    )
    _print(out)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    return _approval(args.app, args.region, args.task_token, "approve", args.operator, args.reason)


def cmd_abort(args: argparse.Namespace) -> int:
    return _approval(args.app, args.region, args.task_token, "abort", args.operator, args.reason)


def _approval(
    app: str, region: str | None, task_token: str, decision: str, operator: str, reason: str
) -> int:
    region = _region_for(app, region)
    function = f"{app}-approval_callback-{_region_suffix(region)}"
    out = _invoke(
        function,
        region,
        {
            "task_token": task_token,
            "decision": decision,
            "operator": operator,
            "reason": reason,
        },
    )
    _print(out)
    return 0


def cmd_drain(args: argparse.Namespace) -> int:
    region = _region_for(args.app, args.region)
    function = f"{args.app}-indicator_updater-{_region_suffix(region)}"
    out = _invoke(
        function,
        region,
        {
            "app_name": args.app,
            "region": region,
            "role": "DRAINING",
            "executor_run_id": f"manual-drain-{args.operator}",
            "sequence": 0,
            "dry_run": args.dry_run,
        },
    )
    _print(out)
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    region = _region_for(args.app, args.region)
    sfn = _client("stepfunctions", region)
    sm_arn = f"arn:aws:states:{region}:{_account_id()}:stateMachine:{args.app}-failover"
    out = {
        "executions": _list_executions(sfn, sm_arn, limit=args.limit),
    }
    _print(out)
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _account_id() -> str:
    sts = _client("sts", "us-east-1")
    return str(sts.get_caller_identity()["Account"])


def _region_suffix(region: str) -> str:
    return {"us-east-1": "use1", "us-east-2": "use2"}.get(region, region.replace("-", ""))


def _list_executions(sfn: Any, state_machine_arn: str, *, limit: int) -> list[dict[str, Any]]:
    try:
        resp = sfn.list_executions(stateMachineArn=state_machine_arn, maxResults=limit)
    except sfn.exceptions.StateMachineDoesNotExist:
        return []
    return [
        {
            "name": e["name"],
            "status": e["status"],
            "started": e.get("startDate"),
            "stopped": e.get("stopDate"),
            "execution_arn": e["executionArn"],
        }
        for e in resp.get("executions", [])
    ]


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("app")
    p.add_argument(
        "--region",
        help="AWS region for the call (default: AWS_REGION or us-east-1).",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="failoverctl", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Show current SSM state + recent executions.")
    _add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    p_fo = sub.add_parser("failover", help="Trigger failover.")
    _add_common(p_fo)
    p_fo.add_argument("--operator", default=os.environ.get("USER", "anonymous"))
    p_fo.add_argument("--dry-run", action="store_true")
    p_fo.set_defaults(func=cmd_failover)

    p_fb = sub.add_parser("failback", help="Trigger failback.")
    _add_common(p_fb)
    p_fb.add_argument("--operator", default=os.environ.get("USER", "anonymous"))
    p_fb.add_argument("--dry-run", action="store_true")
    p_fb.set_defaults(func=cmd_failback)

    p_dr = sub.add_parser("dryrun", help="Trigger a dry-run failover (no real action).")
    _add_common(p_dr)
    p_dr.add_argument("--operator", default=os.environ.get("USER", "anonymous"))
    p_dr.set_defaults(func=cmd_dryrun)

    p_app = sub.add_parser("approve", help="Approve a paused Aurora gate.")
    _add_common(p_app)
    p_app.add_argument("--task-token", required=True)
    p_app.add_argument("--operator", default=os.environ.get("USER", "anonymous"))
    p_app.add_argument("--reason", default="")
    p_app.set_defaults(func=cmd_approve)

    p_ab = sub.add_parser("abort", help="Abort a paused Aurora gate.")
    _add_common(p_ab)
    p_ab.add_argument("--task-token", required=True)
    p_ab.add_argument("--operator", default=os.environ.get("USER", "anonymous"))
    p_ab.add_argument("--reason", default="")
    p_ab.set_defaults(func=cmd_abort)

    p_drain = sub.add_parser("drain", help="Force a region's indicator to DRAINING.")
    _add_common(p_drain)
    p_drain.add_argument("--operator", default=os.environ.get("USER", "anonymous"))
    p_drain.add_argument("--dry-run", action="store_true")
    p_drain.set_defaults(func=cmd_drain)

    p_hist = sub.add_parser("history", help="List recent Step Functions executions.")
    _add_common(p_hist)
    p_hist.add_argument("--limit", type=int, default=10)
    p_hist.set_defaults(func=cmd_history)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
