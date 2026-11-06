"""Local command line. Run from the repo root: python3 -m gary --help"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gary import __version__
from gary.app import App
from gary.config import load_modules, load_settings
from gary.demo import run_demo
from gary.errors import GaryError
from gary.models import InboundMessage, PhotoInput


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except GaryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _add_common(parser: argparse.ArgumentParser, *, suppress: bool) -> None:
    """Shared flags.

    Subparsers use SUPPRESS so an omitted flag does not wipe a value already
    parsed on the main parser. Flags work before or after the subcommand.
    """

    missing = argparse.SUPPRESS if suppress else None
    parser.add_argument("--config", type=Path, default=missing, help="TOML config. Default: config/gary.example.toml")
    parser.add_argument("--data-dir", type=Path, default=missing, help="Local data directory. Default: ./data")
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="Print JSON instead of text",
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_common(common, suppress=True)
    parser = argparse.ArgumentParser(
        prog="gary",
        description=(
            "Gary local starter for Shear's M1. Maintenance intake, audit log, "
            "and a human approval gate. Connectors dry-run. Nothing is sent or spent."
        ),
    )
    _add_common(parser, suppress=False)
    parser.add_argument("--version", action="version", version=f"gary {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser(
        "demo",
        help="Run the scripted local demo. Resets only its data directory.",
        parents=[common],
    )
    demo.set_defaults(func=cmd_demo)

    intake = sub.add_parser(
        "intake",
        help="Record one maintenance request from this machine",
        parents=[common],
    )
    intake.add_argument("--body", required=True)
    intake.add_argument("--sender", default="local")
    intake.add_argument("--channel", default="local_cli")
    intake.add_argument("--photo", action="append", default=[], help="Local file to store as photo metadata. Repeatable.")
    intake.set_defaults(func=cmd_intake)

    poll = sub.add_parser(
        "poll",
        help="Pull the configured adapter inbox. Mock is empty unless a test seeded it.",
        parents=[common],
    )
    poll.set_defaults(func=cmd_poll)

    listing = sub.add_parser("list", help="List stored maintenance requests", parents=[common])
    listing.set_defaults(func=cmd_list)

    show = sub.add_parser(
        "show",
        help="Show one request, its photo metadata, and related approvals",
        parents=[common],
    )
    show.add_argument("request_id")
    show.set_defaults(func=cmd_show)

    draft = sub.add_parser("draft", help="Queue an outbound draft. Does not send.", parents=[common])
    draft.add_argument("--request", required=True)
    draft.add_argument("--to", required=True, help="Recipient label. Not a live address book lookup.")
    draft.add_argument("--body", required=True)
    draft.set_defaults(func=cmd_draft)

    spend = sub.add_parser("spend", help="Queue a spend label. Does not buy anything.", parents=[common])
    spend.add_argument("--summary", required=True)
    spend.add_argument("--amount", required=True, help='Short label such as "12.00 USD".')
    spend.add_argument("--request", default=None)
    spend.set_defaults(func=cmd_spend)

    approvals = sub.add_parser("approvals", help="List human approval records", parents=[common])
    approvals.set_defaults(func=cmd_approvals)

    approve = sub.add_parser(
        "approve",
        help="Record a person's approval. Does not send or spend.",
        parents=[common],
    )
    approve.add_argument("approval_id")
    approve.add_argument("--by", required=True, help="Name label. This is not a login.")
    approve.add_argument("--note", default=None)
    approve.set_defaults(func=cmd_approve)

    deny = sub.add_parser("deny", help="Record a person's denial.", parents=[common])
    deny.add_argument("approval_id")
    deny.add_argument("--by", required=True)
    deny.add_argument("--note", default=None)
    deny.set_defaults(func=cmd_deny)

    execute = sub.add_parser(
        "execute",
        help="Run an approved item through the dry-run gate.",
        parents=[common],
    )
    execute.add_argument("approval_id")
    execute.set_defaults(func=cmd_execute)

    audit = sub.add_parser("audit", help="Show the append-only audit log", parents=[common])
    audit.add_argument("--limit", type=int, default=50)
    audit.set_defaults(func=cmd_audit)

    modules = sub.add_parser("modules", help="Show the eight business module definitions", parents=[common])
    modules.set_defaults(func=cmd_modules)

    check = sub.add_parser(
        "config-check",
        help="Load config and module definitions and report safety flags",
        parents=[common],
    )
    check.set_defaults(func=cmd_config_check)
    return parser


def cmd_demo(args: argparse.Namespace) -> int:
    report = run_demo(_data_dir(args, "data/demo"))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.text)
    return 0


def cmd_intake(args: argparse.Namespace) -> int:
    app = _app(args)
    result = app.submit(
        InboundMessage(
            body=args.body,
            sender_label=args.sender,
            channel=args.channel,
            photos=[PhotoInput(path=path) for path in args.photo],
        )
    )
    payload = result.to_dict()
    payload["sent"] = False
    payload["dispatched"] = False
    text = "\n".join(
        [
            f"id: {result.request.id}",
            f"class: {result.triage.classification}",
            f"rule: {result.triage.matched_rule or '-'}",
            f"escalation: {result.triage.escalation}",
            f"status: {result.request.status}",
            f"photos: {len(result.photos)}",
            "approval: "
            + (result.approval.id + " pending" if result.approval else "none"),
            "sent: no",
            "dispatched: no",
            result.triage.limitation,
        ]
    )
    _emit(args, payload, text)
    return 0


def cmd_poll(args: argparse.Namespace) -> int:
    app = _app(args)
    results = app.poll()
    payload = {
        "adapter": app.adapter.name,
        "mode": app.adapter.mode,
        "contacted": False,
        "count": len(results),
        "request_ids": [item.request.id for item in results],
    }
    text = "\n".join(
        [
            f"adapter: {app.adapter.name}",
            f"mode: {app.adapter.mode}",
            "contacted: no",
            f"messages: {len(results)}",
        ]
    )
    _emit(args, payload, text)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    app = _app(args)
    rows = app.store.list_requests()
    payload = [row.to_dict() for row in rows]
    if not rows:
        _emit(args, payload, "no requests")
        return 0
    lines = [f"{row.id}  {row.triage_class:13}  {row.status:16}  {row.sender_label}" for row in rows]
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    app = _app(args)
    request = app.store.get_request(args.request_id)
    photos = app.store.list_photos(request.id)
    approvals = app.store.list_approvals(request.id)
    payload = {
        "request": request.to_dict(),
        "photos": [photo.to_dict() for photo in photos],
        "approvals": [approval.to_dict() for approval in approvals],
        "sent": False,
        "dispatched": False,
    }
    lines = [
        f"id: {request.id}",
        f"status: {request.status}",
        f"class: {request.triage_class}",
        f"rule: {request.triage_rule or '-'}",
        f"escalation: {request.escalation}",
        f"channel: {request.channel}",
        f"sender: {request.sender_label}",
        f"created: {request.created_at}",
        f"body: {request.body}",
        f"reason: {request.triage_reason}",
        f"limitation: {request.triage_limitation}",
        "sent: no",
        "dispatched: no",
        "photos:",
    ]
    if photos:
        for photo in photos:
            lines.append(
                f"  - {photo.filename} bytes={photo.size_bytes} sha256={photo.sha256 or '-'} path={photo.stored_relative_path or '-'}"
            )
    else:
        lines.append("  - none")
    lines.append("approvals:")
    if approvals:
        for approval in approvals:
            lines.append(f"  - {approval.id} {approval.status} {approval.action_type} {approval.summary}")
    else:
        lines.append("  - none")
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    app = _app(args)
    approval = app.draft_message(args.request, args.to, args.body)
    return _print_approval(args, app, approval.id, "queued. sent: no")


def cmd_spend(args: argparse.Namespace) -> int:
    app = _app(args)
    approval = app.request_spend(args.summary, args.amount, args.request)
    return _print_approval(args, app, approval.id, "queued. spent: no")


def cmd_approvals(args: argparse.Namespace) -> int:
    app = _app(args)
    rows = app.store.list_approvals()
    payload = [row.to_dict() for row in rows]
    if not rows:
        _emit(args, payload, "no approvals")
        return 0
    lines = [f"{row.id}  {row.status:10}  {row.action_type:18}  {row.summary}" for row in rows]
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    app = _app(args)
    approval = app.gate.decide(args.approval_id, "approved", args.by, args.note)
    return _print_approval(args, app, approval.id, "recorded. execute is a separate step. sent: no. spent: no")


def cmd_deny(args: argparse.Namespace) -> int:
    app = _app(args)
    approval = app.gate.decide(args.approval_id, "denied", args.by, args.note)
    return _print_approval(args, app, approval.id, "denied. sent: no. spent: no")


def cmd_execute(args: argparse.Namespace) -> int:
    app = _app(args)
    result = app.gate.execute(args.approval_id)
    approval = app.store.get_approval(args.approval_id)
    payload = {"approval": approval.to_dict(), "result": result.to_dict(), "delivered": False, "spent": False}
    text = "\n".join(
        [
            f"approval: {approval.id}",
            f"status: {approval.status}",
            f"adapter: {result.adapter}",
            f"mode: {result.mode}",
            "delivered: no",
            "spent: no",
            f"detail: {result.detail}",
        ]
    )
    _emit(args, payload, text)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    app = _app(args)
    rows = app.store.list_audit(limit=max(1, args.limit))
    payload = [row.to_dict() for row in rows]
    if not rows:
        _emit(args, payload, "no audit entries")
        return 0
    lines = [f"{row.id:4}  {row.ts}  {row.actor}  {row.action}  {row.entity_type}:{row.entity_id or '-'}" for row in rows]
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_modules(args: argparse.Namespace) -> int:
    modules = load_modules()
    payload = [spec.to_dict() for spec in modules]
    lines = []
    for spec in modules:
        state = "runnable" if spec.runnable else spec.workflow
        lines.append(f"{spec.id:22}  {state:20}  {spec.name}")
    lines.append("runnable workflows implement intake. docs_only and none do not send, spend, or publish.")
    _emit(args, payload, "\n".join(lines))
    return 0


def cmd_config_check(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    modules = load_modules()
    runnable = [spec.id for spec in modules if spec.runnable]
    docs_only = [spec.id for spec in modules if spec.workflow == "docs_only"]
    defined = [spec.id for spec in modules if spec.workflow == "none"]
    payload = {
        "config": settings.config_path,
        "adapter": settings.adapter_name,
        "bluebubbles_enabled": settings.bluebubbles_enabled,
        "require_human": settings.require_human,
        "module_count": len(modules),
        "runnable_workflows": runnable,
        "docs_only": docs_only,
        "defined_only": defined,
        "live_send": False,
        "live_spend": False,
        "dispatch": False,
    }
    text = "\n".join(
        [
            f"config: {settings.config_path}",
            f"adapter: {settings.adapter_name}",
            f"bluebubbles_enabled: {str(settings.bluebubbles_enabled).lower()}",
            f"require_human: {str(settings.require_human).lower()}",
            f"modules: {len(modules)}",
            f"runnable_workflows: {', '.join(runnable)}",
            f"docs_only: {', '.join(docs_only)}",
            f"defined_only: {', '.join(defined)}",
            "forbidden_keys: none",
            "live_send: unavailable",
            "live_spend: unavailable",
            "dispatch: unavailable",
        ]
    )
    _emit(args, payload, text)
    return 0


def _app(args: argparse.Namespace) -> App:
    return App(_data_dir(args, "data"), args.config)


def _data_dir(args: argparse.Namespace, default: str) -> Path:
    if args.data_dir is not None:
        return Path(args.data_dir)
    return Path(default)


def _emit(args: argparse.Namespace, payload: object, text: str) -> None:
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(text)


def _print_approval(args: argparse.Namespace, app: App, approval_id: str, trailer: str) -> int:
    approval = app.store.get_approval(approval_id)
    text = "\n".join(
        [
            f"id: {approval.id}",
            f"status: {approval.status}",
            f"action: {approval.action_type}",
            f"summary: {approval.summary}",
            trailer,
        ]
    )
    _emit(args, approval.to_dict(), text)
    return 0
