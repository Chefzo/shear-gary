"""Maintenance intake. The only runnable business workflow in this starter."""

from __future__ import annotations

import re
from pathlib import Path

from gary.errors import IntakeError, ModuleNotRunnable
from gary.gate import ApprovalGate
from gary.models import (
    ESCALATE,
    REQUEST_ESCALATED,
    REQUEST_ROUTINE,
    Approval,
    InboundMessage,
    IntakeResult,
    ModuleSpec,
    Request,
)
from gary.photos import MAX_PHOTOS, store_photo
from gary.store import Store
from gary.triage import classify
from gary.util import new_id, utcnow

_CHANNEL = re.compile(r"^[a-z0-9._-]{1,40}$")


class MaintenanceIntake:
    def __init__(self, store: Store, gate: ApprovalGate, modules: list[ModuleSpec]) -> None:
        self.store = store
        self.gate = gate
        self.modules = modules

    def accept(self, message: InboundMessage) -> IntakeResult:
        module = maintenance_module(self.modules)
        channel = message.channel.strip()
        if not _CHANNEL.fullmatch(channel):
            raise IntakeError("channel must be a short local label such as local_cli")
        body = message.body.strip()
        if not body:
            raise IntakeError("body is required")
        if len(body) > 8000:
            raise IntakeError("body is too long")
        sender = message.sender_label.strip() or "unknown sender"
        if len(sender) > 200:
            raise IntakeError("sender label is too long")
        if len(message.photos) > MAX_PHOTOS:
            raise IntakeError(f"a request can store up to {MAX_PHOTOS} photos")

        triage = classify(body)
        request_id = new_id("req")
        request = Request(
            id=request_id,
            module_id=module.id,
            channel=channel,
            sender_label=sender,
            body=body,
            created_at=utcnow(),
            triage_class=triage.classification,
            triage_rule=triage.matched_rule,
            triage_reason=triage.reason,
            triage_limitation=triage.limitation,
            escalation=triage.escalation,
            status=REQUEST_ESCALATED if triage.escalation == ESCALATE else REQUEST_ROUTINE,
        )
        copied: list[Path] = []
        try:
            with self.store.transaction():
                self.store.insert_request(request)
                photos = []
                for incoming in message.photos:
                    photo, stored = store_photo(
                        self.store.photos_dir,
                        self.store.data_dir,
                        request_id,
                        new_id("photo"),
                        incoming,
                    )
                    if stored is not None:
                        copied.append(stored)
                    self.store.insert_photo(photo)
                    photos.append(photo)
                self.store.audit(
                    "gary",
                    "request_received",
                    "request",
                    request_id,
                    {
                        "module_id": module.id,
                        "channel": channel,
                        "sender_label": sender,
                        "excerpt": excerpt(body),
                        "photo_count": len(photos),
                        "dispatched": False,
                    },
                )
                self.store.audit(
                    "gary",
                    "triage_completed",
                    "request",
                    request_id,
                    {
                        "classification": triage.classification,
                        "matched_rule": triage.matched_rule,
                        "escalation": triage.escalation,
                        "dispatched": False,
                    },
                )
                approval: Approval | None = None
                if triage.escalation == ESCALATE:
                    approval = self.gate.request_message(
                        request_id=request_id,
                        summary=f"Human review ({triage.classification}) for {request_id}",
                        to_label="Shear or property manager",
                        body=escalation_body(request_id, triage.classification, sender, body),
                        channel=channel,
                        extra={"classification": triage.classification, "auto_send": False},
                    )
            return IntakeResult(request=request, photos=photos, triage=triage, approval=approval)
        except Exception:
            for path in copied:
                path.unlink(missing_ok=True)
            raise


def maintenance_module(modules: list[ModuleSpec]) -> ModuleSpec:
    for spec in modules:
        if spec.id == "maintenance":
            if not spec.runnable:
                raise ModuleNotRunnable("maintenance intake is not marked runnable")
            return spec
    raise ModuleNotRunnable("maintenance module is missing from config/modules.toml")


def require_module(modules: list[ModuleSpec], module_id: str) -> ModuleSpec:
    for spec in modules:
        if spec.id == module_id:
            if not spec.runnable:
                raise ModuleNotRunnable(
                    f"{spec.name} has workflow {spec.workflow!r}. "
                    "No workflow for it is implemented in this starter."
                )
            return spec
    raise ModuleNotRunnable(f"unknown module: {module_id}")


def escalation_body(request_id: str, classification: str, sender: str, body: str) -> str:
    return (
        f"Human review needed ({classification}). "
        f"Request {request_id} from {sender}. "
        f"Summary: {excerpt(body)} "
        "Gary has not contacted anyone and has not dispatched anyone. "
        "Shear or the property manager decides the next step."
    )


def excerpt(body: str, limit: int = 240) -> str:
    text = " ".join(body.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
