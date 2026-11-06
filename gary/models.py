from __future__ import annotations

from dataclasses import asdict, dataclass, field


CLASS_EMERGENCY = "emergency"
CLASS_ROUTINE = "routine"
CLASS_NEEDS_REVIEW = "needs_review"
ESCALATE = "human_required"
NO_ESCALATION = "none"

ACTION_MESSAGE = "outbound_message"
ACTION_SPEND = "spend"
ALLOWED_ACTIONS = frozenset({ACTION_MESSAGE, ACTION_SPEND})

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"
STATUS_EXECUTED = "executed"

MODE_DRY_RUN = "dry_run"
MODE_DISABLED = "disabled"
MODE_BLOCKED = "blocked"
ALLOWED_MODES = frozenset({MODE_DRY_RUN, MODE_DISABLED, MODE_BLOCKED})

REQUEST_ESCALATED = "escalated"
REQUEST_ROUTINE = "routine_logged"

TRIAGE_LIMITATION = (
    "Phrase-list triage only. This is not a life-safety system, not a call to "
    "emergency services, and not a promise that danger will be detected. "
    "Gary does not dispatch help."
)


@dataclass(frozen=True)
class Settings:
    name: str
    adapter_name: str
    bluebubbles_enabled: bool
    require_human: bool
    config_path: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModuleSpec:
    id: str
    name: str
    workflow: str
    summary: str
    human_gates: tuple[str, ...]
    intended: tuple[str, ...]
    not_implemented: tuple[str, ...]
    blockers: tuple[str, ...]
    docs: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def runnable(self) -> bool:
        return self.workflow == "maintenance_intake"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["runnable"] = self.runnable
        return data


@dataclass
class PhotoInput:
    path: str | None = None
    filename: str | None = None
    content_type: str | None = None
    note: str | None = None


@dataclass
class InboundMessage:
    body: str
    sender_label: str
    channel: str
    photos: list[PhotoInput] = field(default_factory=list)


@dataclass(frozen=True)
class TriageResult:
    classification: str
    matched_rule: str | None
    matched_phrase: str | None
    escalation: str
    reason: str
    limitation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Request:
    id: str
    module_id: str
    channel: str
    sender_label: str
    body: str
    created_at: str
    triage_class: str
    triage_rule: str | None
    triage_reason: str
    triage_limitation: str
    escalation: str
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Photo:
    id: str
    request_id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    stored_relative_path: str | None
    note: str | None
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Approval:
    id: str
    request_id: str | None
    action_type: str
    summary: str
    payload: dict
    status: str
    requested_at: str
    decided_at: str | None
    decided_by: str | None
    decision_note: str | None
    executed_at: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OutboundDraft:
    to_label: str
    body: str
    channel: str
    request_id: str | None


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    mode: str
    delivered: bool
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Attempt:
    id: str
    approval_id: str
    adapter: str
    mode: str
    delivered: bool
    detail: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditEntry:
    id: int
    ts: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    detail: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IntakeResult:
    request: Request
    photos: list[Photo]
    triage: TriageResult
    approval: Approval | None

    def to_dict(self) -> dict:
        return {
            "request": self.request.to_dict(),
            "photos": [photo.to_dict() for photo in self.photos],
            "triage": self.triage.to_dict(),
            "approval": None if self.approval is None else self.approval.to_dict(),
        }
