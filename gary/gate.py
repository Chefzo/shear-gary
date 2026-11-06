"""Human approval gate.

Approving records a decision. Execute is a second step. Execute writes a
dry-run or disabled attempt and never a delivery. Spend has no payment
connector. Dispatch is refused.
"""

from __future__ import annotations

import re

from gary.adapters import BlueBubblesAdapter, MockAdapter
from gary.errors import NotApproved, SafetyError, UnsupportedAction
from gary.models import (
    ACTION_MESSAGE,
    ACTION_SPEND,
    ALLOWED_ACTIONS,
    ALLOWED_MODES,
    MODE_DRY_RUN,
    STATUS_APPROVED,
    STATUS_DENIED,
    STATUS_PENDING,
    AdapterResult,
    Approval,
    Attempt,
    OutboundDraft,
)
from gary.store import Store
from gary.util import clean_actor, new_id, utcnow

SPEND_DETAIL = "No spend connector is installed. Nothing was purchased, booked, or billed."


class ApprovalGate:
    def __init__(self, store: Store, adapter: MockAdapter | BlueBubblesAdapter, actor: str = "gary") -> None:
        self.store = store
        self.adapter = adapter
        self.actor = actor

    def request_message(
        self,
        *,
        request_id: str | None,
        summary: str,
        to_label: str,
        body: str,
        channel: str,
        extra: dict | None = None,
    ) -> Approval:
        payload = {
            "to_label": to_label,
            "body": body,
            "channel": channel,
            "request_id": request_id,
        }
        if extra:
            payload.update(extra)
        return self._request(ACTION_MESSAGE, request_id, summary, payload)

    def request_spend(
        self,
        *,
        summary: str,
        amount_label: str,
        request_id: str | None,
    ) -> Approval:
        label = amount_label.strip()
        if not label or len(label) > 40:
            raise UnsupportedAction("amount label must be 1–40 characters")
        if re.search(r"\d{13,}", label):
            raise UnsupportedAction("amount label has a long digit run; use a short price label")
        payload = {
            "summary": summary,
            "amount_label": label,
            "request_id": request_id,
            "note": "Label only. No payment connector.",
        }
        return self._request(ACTION_SPEND, request_id, summary, payload)

    def request_unsupported(self, action_type: str, summary: str) -> None:
        self.store.audit(
            self.actor,
            "action_refused",
            "approval",
            None,
            {"action_type": action_type, "summary": summary, "delivered": False},
        )
        raise UnsupportedAction(
            "That action is not available. Automatic dispatch is not supported. "
            "This starter only records outbound_message and spend, and it does not send or spend."
        )

    def decide(self, approval_id: str, decision: str, decided_by: str, note: str | None = None) -> Approval:
        if decision not in {STATUS_APPROVED, STATUS_DENIED}:
            raise SafetyError("decision must be approved or denied")
        try:
            actor = clean_actor(decided_by)
        except ValueError as exc:
            raise SafetyError(str(exc)) from exc
        decided_at = utcnow()
        with self.store.transaction():
            approval = self.store.decide_approval(
                approval_id, decision, actor, _note(note), decided_at
            )
            self.store.audit(
                actor,
                "approval_decided",
                "approval",
                approval.id,
                {"decision": decision, "delivered": False, "spent": False},
            )
        return approval

    def execute(self, approval_id: str) -> AdapterResult:
        approval = self.store.get_approval(approval_id)
        if approval.status == STATUS_PENDING:
            self._blocked(approval, "Approval is still pending. Nothing was sent or spent.")
        if approval.status == STATUS_DENIED:
            self._blocked(approval, "Approval was denied. Nothing was sent or spent.")
        if approval.status != STATUS_APPROVED:
            self._blocked(approval, "This approval cannot be executed. Nothing was sent or spent.")
        if approval.action_type == ACTION_MESSAGE:
            result = self._send(approval)
        elif approval.action_type == ACTION_SPEND:
            result = AdapterResult(
                adapter="none",
                mode=MODE_DRY_RUN,
                delivered=False,
                detail=SPEND_DETAIL,
            )
        else:
            self.request_unsupported(approval.action_type, approval.summary)
            raise UnsupportedAction(approval.action_type)
        self._record(approval, result)
        return result

    def _request(self, action_type: str, request_id: str | None, summary: str, payload: dict) -> Approval:
        if action_type not in ALLOWED_ACTIONS:
            self.request_unsupported(action_type, summary)
        approval = Approval(
            id=new_id("appr"),
            request_id=request_id,
            action_type=action_type,
            summary=summary.strip(),
            payload=payload,
            status=STATUS_PENDING,
            requested_at=utcnow(),
            decided_at=None,
            decided_by=None,
            decision_note=None,
            executed_at=None,
        )
        with self.store.transaction():
            self.store.insert_approval(approval)
            self.store.audit(
                self.actor,
                "approval_requested",
                "approval",
                approval.id,
                {
                    "action_type": action_type,
                    "request_id": request_id,
                    "status": STATUS_PENDING,
                    "delivered": False,
                },
            )
        return approval

    def _send(self, approval: Approval) -> AdapterResult:
        payload = approval.payload
        draft = OutboundDraft(
            to_label=str(payload.get("to_label", "")),
            body=str(payload.get("body", "")),
            channel=str(payload.get("channel", self.adapter.name)),
            request_id=approval.request_id,
        )
        return self.adapter.send(draft, approval.id)

    def _record(self, approval: Approval, result: AdapterResult) -> Attempt:
        if result.delivered or result.mode not in ALLOWED_MODES:
            self.store.audit(
                self.actor,
                "execute_refused",
                "approval",
                approval.id,
                {"reason": "live delivery is not recordable", "delivered": False},
            )
            raise SafetyError(
                "Refusing to record a live delivery. This starter has no live connector."
            )
        executed_at = utcnow()
        attempt = Attempt(
            id=new_id("try"),
            approval_id=approval.id,
            adapter=result.adapter,
            mode=result.mode,
            delivered=False,
            detail=result.detail,
            created_at=executed_at,
        )
        with self.store.transaction():
            self.store.insert_attempt(attempt)
            self.store.mark_approval_executed(approval.id, executed_at)
            self.store.audit(
                self.actor,
                "execute_dry_run",
                "approval",
                approval.id,
                {
                    "adapter": result.adapter,
                    "mode": result.mode,
                    "action_type": approval.action_type,
                    "delivered": False,
                    "spent": False,
                },
            )
        return attempt

    def _blocked(self, approval: Approval, message: str) -> None:
        self.store.audit(
            self.actor,
            "execute_blocked",
            "approval",
            approval.id,
            {"status": approval.status, "delivered": False, "spent": False},
        )
        raise NotApproved(message)


def _note(note: str | None) -> str | None:
    if note is None:
        return None
    text = note.strip()
    if len(text) > 500:
        raise SafetyError("decision note is too long")
    return text or None
