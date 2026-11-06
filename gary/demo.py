"""Scripted local demo. It rewrites only the sqlite file and photos inside its data dir."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from gary.app import App
from gary.errors import NotApproved, SafetyError
from gary.models import (
    CLASS_EMERGENCY,
    CLASS_NEEDS_REVIEW,
    CLASS_ROUTINE,
    STATUS_PENDING,
    InboundMessage,
    PhotoInput,
)
from gary.paths import assert_safe_data_dir


@dataclass
class DemoReport:
    data_dir: str
    adapter: str
    bluebubbles_enabled: bool
    routine_request_id: str
    emergency_request_id: str
    review_request_id: str
    emergency_approval_status: str
    review_approval_status: str
    blocked_before_approval: bool
    routine_execute_mode: str
    routine_delivered: bool
    spend_delivered: bool
    emergency_attempt_count: int
    attempt_count: int
    audit_count: int
    module_count: int
    runnable_module_ids: list[str]
    text: str

    def to_dict(self) -> dict:
        return {
            "data_dir": self.data_dir,
            "adapter": self.adapter,
            "bluebubbles_enabled": self.bluebubbles_enabled,
            "routine_request_id": self.routine_request_id,
            "emergency_request_id": self.emergency_request_id,
            "review_request_id": self.review_request_id,
            "emergency_approval_status": self.emergency_approval_status,
            "review_approval_status": self.review_approval_status,
            "blocked_before_approval": self.blocked_before_approval,
            "routine_execute_mode": self.routine_execute_mode,
            "routine_delivered": self.routine_delivered,
            "spend_delivered": self.spend_delivered,
            "emergency_attempt_count": self.emergency_attempt_count,
            "attempt_count": self.attempt_count,
            "audit_count": self.audit_count,
            "module_count": self.module_count,
            "runnable_module_ids": self.runnable_module_ids,
            "delivered": 0,
            "spent": 0,
            "dispatched": 0,
        }


def reset_data_dir(data_dir: Path) -> Path:
    safe = assert_safe_data_dir(data_dir)
    safe.mkdir(parents=True, exist_ok=True)
    database = safe / "gary.sqlite"
    if database.exists():
        database.unlink()
    for folder_name in ("photos", "_sample"):
        folder = safe / folder_name
        if folder.exists():
            shutil.rmtree(folder)
    return safe


def run_demo(data_dir: Path) -> DemoReport:
    safe = reset_data_dir(data_dir)
    app = App(safe)
    if app.settings.adapter_name != "mock" or app.settings.bluebubbles_enabled:
        raise SafetyError("demo runs only with the mock adapter and BlueBubbles disabled")

    sample = safe / "_sample" / "flicker.txt"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text("Stand-in photo bytes for the local demo.\n", encoding="utf-8")

    routine = app.submit(
        InboundMessage(
            channel="local_cli",
            sender_label="studio tenant (demo)",
            body="Flickering light in the studio office.",
            photos=[PhotoInput(path=str(sample), note="demo stand-in")],
        )
    )
    emergency = app.submit(
        InboundMessage(
            channel="local_cli",
            sender_label="office tenant (demo)",
            body="Burst pipe in the bathroom.",
        )
    )
    review = app.submit(
        InboundMessage(
            channel="local_cli",
            sender_label="hallway (demo)",
            body="Something is off in the hallway, not sure what.",
        )
    )
    if routine.triage.classification != CLASS_ROUTINE or routine.approval is not None:
        raise SafetyError("routine demo request was classified unexpectedly")
    if emergency.triage.classification != CLASS_EMERGENCY or emergency.approval is None:
        raise SafetyError("emergency demo request was classified unexpectedly")
    if review.triage.classification != CLASS_NEEDS_REVIEW or review.approval is None:
        raise SafetyError("unclassified demo request was classified unexpectedly")
    if not routine.photos or not routine.photos[0].sha256:
        raise SafetyError("demo photo metadata was not stored")

    draft = app.draft_message(
        routine.request.id,
        to_label="studio tenant (demo)",
        body="We can schedule a look at the flickering light. This draft has not been sent.",
    )
    blocked = _blocked(app, draft.id)
    app.gate.decide(draft.id, "approved", "Shear (demo)", "local demo label, not a real send")
    routine_result = app.gate.execute(draft.id)

    spend = app.request_spend("replacement bulb for the demo", "12.00 USD", routine.request.id)
    _blocked(app, spend.id)
    app.gate.decide(spend.id, "approved", "Shear (demo)", "local demo label, not a purchase")
    spend_result = app.gate.execute(spend.id)

    emergency_approval = app.store.get_approval(emergency.approval.id)
    review_approval = app.store.get_approval(review.approval.id)
    emergency_attempts = app.store.list_attempts(emergency.approval.id)
    attempts = app.store.list_attempts()
    if emergency_approval.status != STATUS_PENDING or review_approval.status != STATUS_PENDING:
        raise SafetyError("demo escalations were executed")
    if emergency_attempts or routine_result.delivered or spend_result.delivered:
        raise SafetyError("demo recorded a delivery or an emergency attempt")
    if any(item.delivered for item in attempts):
        raise SafetyError("an attempt was stored as delivered")

    runnable = [spec.id for spec in app.modules if spec.runnable]
    lines = [
        "Gary local demo",
        f"data directory: {safe}",
        "adapter: mock (dry-run)",
        "BlueBubbles: disabled",
        'Decision label "Shear (demo)" is a local string. It is not Shear\'s real OK.',
        "",
        "1. Routine intake",
        f"   id: {routine.request.id}",
        f"   class: {routine.triage.classification}",
        f"   photo: {routine.photos[0].filename} sha256={routine.photos[0].sha256} bytes={routine.photos[0].size_bytes}",
        "   escalation: none",
        "   sent: no",
        "",
        "2. Emergency intake",
        f"   id: {emergency.request.id}",
        f"   class: {emergency.triage.classification}",
        f"   rule: {emergency.triage.matched_rule}",
        "   escalation: human required",
        f"   draft approval: {emergency.approval.id} status={emergency_approval.status}",
        "   sent: no",
        "   dispatched: no",
        "",
        "3. Unclassified intake",
        f"   id: {review.request.id}",
        f"   class: {review.triage.classification}",
        "   escalation: human required",
        f"   draft approval: {review.approval.id} status={review_approval.status}",
        "   sent: no",
        "",
        "4. Outbound before approval",
        f"   blocked: {str(blocked).lower()}",
        "   sent: no",
        "",
        "5. Approved routine draft, then execute",
        f"   mode: {routine_result.mode}",
        f"   delivered: {str(routine_result.delivered).lower()}",
        f"   detail: {routine_result.detail}",
        "",
        "6. Approved spend label, then execute",
        f"   mode: {spend_result.mode}",
        f"   delivered: {str(spend_result.delivered).lower()}",
        f"   detail: {spend_result.detail}",
        "",
        f"audit entries: {len(app.store.list_audit(limit=500))}",
        f"modules: {len(app.modules)} ({len(runnable)} runnable workflow)",
        "",
        "Nothing was sent. Nothing was spent. No emergency dispatch exists.",
        "RESULT delivered=0 spent=0 dispatched=0 dry_run_records=2",
    ]
    return DemoReport(
        data_dir=str(safe),
        adapter=app.adapter.name,
        bluebubbles_enabled=app.settings.bluebubbles_enabled,
        routine_request_id=routine.request.id,
        emergency_request_id=emergency.request.id,
        review_request_id=review.request.id,
        emergency_approval_status=emergency_approval.status,
        review_approval_status=review_approval.status,
        blocked_before_approval=blocked,
        routine_execute_mode=routine_result.mode,
        routine_delivered=routine_result.delivered,
        spend_delivered=spend_result.delivered,
        emergency_attempt_count=len(emergency_attempts),
        attempt_count=len(attempts),
        audit_count=len(app.store.list_audit(limit=500)),
        module_count=len(app.modules),
        runnable_module_ids=runnable,
        text="\n".join(lines),
    )


def _blocked(app: App, approval_id: str) -> bool:
    try:
        app.gate.execute(approval_id)
    except NotApproved:
        return True
    raise SafetyError("execute succeeded without a recorded human approval")
