import sqlite3
import tempfile
import unittest
from pathlib import Path

from gary.adapters import BlueBubblesAdapter, MockAdapter
from gary.app import App
from gary.errors import ModuleNotRunnable, NotApproved, PhotoError, SafetyError, UnsupportedAction
from gary.gate import SPEND_DETAIL
from gary.models import (
    CLASS_EMERGENCY,
    CLASS_ROUTINE,
    MODE_DRY_RUN,
    STATUS_APPROVED,
    STATUS_PENDING,
    AdapterResult,
    InboundMessage,
    PhotoInput,
)
from gary.photos import safe_filename
from gary.store import Store


def _app(root: Path) -> App:
    return App(root / "data")


class IntakeAndGateTests(unittest.TestCase):
    def test_routine_photo_metadata_and_no_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "flicker.txt"
            sample.write_text("stand-in bytes\n", encoding="utf-8")
            app = _app(root)
            result = app.submit(
                InboundMessage(
                    channel="local_cli",
                    sender_label="studio 4",
                    body="Flickering light near the door",
                    photos=[PhotoInput(path=str(sample))],
                )
            )
            self.assertEqual(result.triage.classification, CLASS_ROUTINE)
            self.assertIsNone(result.approval)
            self.assertEqual(result.request.status, "routine_logged")
            photo = result.photos[0]
            self.assertEqual(photo.filename, "flicker.txt")
            self.assertEqual(photo.size_bytes, sample.stat().st_size)
            self.assertIsNotNone(photo.sha256)
            self.assertTrue(photo.stored_relative_path)
            stored = root / "data" / photo.stored_relative_path
            self.assertEqual(stored.read_bytes(), sample.read_bytes())
            self.assertEqual(app.store.list_attempts(), [])
            actions = [entry.action for entry in app.store.list_audit(limit=20)]
            self.assertIn("request_received", actions)
            self.assertIn("triage_completed", actions)

    def test_metadata_only_photo_and_traversal_filename(self) -> None:
        self.assertEqual(safe_filename("../../etc/passwd"), "passwd")
        self.assertEqual(safe_filename(".."), "photo")
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            result = app.submit(
                InboundMessage(
                    channel="local_cli",
                    sender_label="tenant",
                    body="bulb out",
                    photos=[PhotoInput(filename="../../secret.png", content_type="image/png")],
                )
            )
            photo = result.photos[0]
            self.assertEqual(photo.filename, "secret.png")
            self.assertIsNone(photo.sha256)
            self.assertIsNone(photo.stored_relative_path)
            self.assertIsNone(photo.size_bytes)

    def test_missing_photo_file_is_rejected_without_a_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            with self.assertRaises(PhotoError):
                app.submit(
                    InboundMessage(
                        channel="local_cli",
                        sender_label="tenant",
                        body="bulb out",
                        photos=[PhotoInput(path=str(Path(tmp) / "missing.jpg"))],
                    )
                )
            self.assertEqual(app.store.list_requests(), [])

    def test_emergency_queues_a_human_and_does_not_send_or_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            result = app.submit(
                InboundMessage(
                    channel="local_cli",
                    sender_label="suite 2",
                    body="HVAC is down and the room is hot",
                )
            )
            self.assertEqual(result.triage.classification, CLASS_EMERGENCY)
            self.assertEqual(result.request.escalation, "human_required")
            self.assertIsNotNone(result.approval)
            approval = result.approval
            assert approval is not None
            self.assertEqual(approval.status, STATUS_PENDING)
            self.assertEqual(approval.action_type, "outbound_message")
            self.assertIn("has not dispatched", approval.payload["body"])
            self.assertEqual(approval.payload["to_label"], "Shear or property manager")
            self.assertFalse(approval.payload["auto_send"])
            self.assertEqual(app.store.list_attempts(approval.id), [])
            with self.assertRaises(NotApproved):
                app.gate.execute(approval.id)
            self.assertEqual(app.store.get_approval(approval.id).status, STATUS_PENDING)
            self.assertEqual(app.store.list_attempts(), [])

    def test_approve_does_not_send_until_execute_and_execute_is_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            result = app.submit(
                InboundMessage(channel="local_cli", sender_label="tenant", body="please change the air filter")
            )
            draft = app.draft_message(result.request.id, "tenant", "Thursday works for a filter change.")
            self.assertEqual(app.store.list_attempts(), [])
            app.gate.decide(draft.id, "approved", "Shear", "ok to record the dry-run")
            self.assertEqual(app.store.list_attempts(), [])
            executed = app.gate.execute(draft.id)
            self.assertEqual(executed.mode, MODE_DRY_RUN)
            self.assertFalse(executed.delivered)
            self.assertIn("not delivered", executed.detail)
            self.assertEqual(app.store.get_approval(draft.id).status, "executed")
            with self.assertRaises(NotApproved):
                app.gate.execute(draft.id)

    def test_denied_and_pending_block_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            result = app.submit(
                InboundMessage(channel="local_cli", sender_label="tenant", body="squeaky door")
            )
            draft = app.draft_message(result.request.id, "tenant", "We can look at the door.")
            app.gate.decide(draft.id, "denied", "Shear")
            with self.assertRaises(NotApproved):
                app.gate.execute(draft.id)
            self.assertEqual(app.store.list_attempts(), [])

    def test_spend_never_leaves_the_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            spend = app.request_spend("bulb", "12.00 USD", None)
            with self.assertRaises(NotApproved):
                app.gate.execute(spend.id)
            app.gate.decide(spend.id, "approved", "Shear")
            result = app.gate.execute(spend.id)
            self.assertFalse(result.delivered)
            self.assertEqual(result.detail, SPEND_DETAIL)
            self.assertEqual(app.store.list_attempts()[0].delivered, False)

    def test_long_digit_amount_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            with self.assertRaises(UnsupportedAction):
                app.request_spend("card-looking label", "4111111111111111", None)

    def test_dispatch_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            with self.assertRaises(UnsupportedAction):
                app.gate.request_unsupported("dispatch", "send a plumber now")
            actions = [entry.action for entry in app.store.list_audit(limit=10)]
            self.assertIn("action_refused", actions)
            self.assertEqual(app.store.list_attempts(), [])
            self.assertEqual(app.store.list_approvals(), [])

    def test_live_delivery_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            store = Store(root)

            class Delivering:
                name = "mock"
                mode = MODE_DRY_RUN

                def send(self, draft, approval_id):
                    del draft, approval_id
                    return AdapterResult(adapter="mock", mode="live", delivered=True, detail="nope")

            from gary.gate import ApprovalGate

            gate = ApprovalGate(store, Delivering(), actor="gary")
            approval = gate.request_message(
                request_id=None,
                summary="outbound",
                to_label="tenant",
                body="This must not be delivered.",
                channel="local_cli",
            )
            gate.decide(approval.id, "approved", "Shear")
            with self.assertRaises(SafetyError):
                gate.execute(approval.id)
            self.assertEqual(store.get_approval(approval.id).status, STATUS_APPROVED)
            self.assertEqual(store.list_attempts(), [])
            self.assertIn("execute_refused", [entry.action for entry in store.list_audit(limit=20)])

    def test_database_rejects_a_delivered_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data")
            from gary.gate import ApprovalGate

            gate = ApprovalGate(store, MockAdapter(), actor="gary")
            approval = gate.request_spend(summary="parts", amount_label="5 USD", request_id=None)
            conn = sqlite3.connect(store.path)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO outbound_attempts (
                            id, approval_id, adapter, mode, delivered, detail, created_at
                        ) VALUES ('try_bad', ?, 'mock', 'dry_run', 1, 'no', '2026-11-06T00:00:00+00:00')
                        """,
                        (approval.id,),
                    )
            finally:
                conn.close()

    def test_transaction_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data")
            from gary.models import Request

            request = Request(
                id="req_aabbccddeeff",
                module_id="maintenance",
                channel="local_cli",
                sender_label="tenant",
                body="bulb",
                created_at="2026-11-06T00:00:00+00:00",
                triage_class="routine",
                triage_rule="bulb",
                triage_reason="test",
                triage_limitation="test",
                escalation="none",
                status="routine_logged",
            )
            with self.assertRaises(RuntimeError):
                with store.transaction():
                    store.insert_request(request)
                    raise RuntimeError("boom")
            self.assertEqual(store.list_requests(), [])

    def test_audit_redacts_secret_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data")
            store.audit("gary", "note", "request", "req_1", {"body": "prefix sk_live_abc suffix"})
            entry = store.list_audit()[0]
            self.assertTrue(entry.detail["redacted"])
            self.assertNotIn("sk_live_", str(entry.detail))

    def test_defined_modules_do_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = _app(Path(tmp))
            self.assertEqual(app.run_module("maintenance").id, "maintenance")
            for module_id in (
                "barbershop_booking",
                "tour_scheduling",
                "tenant_marketing",
                "website_rebuild",
                "lead_gen",
                "hiring",
                "online_academy",
            ):
                with self.assertRaises(ModuleNotRunnable):
                    app.run_module(module_id)

    def test_bluebubbles_flag_still_does_not_contact(self) -> None:
        quiet = BlueBubblesAdapter(enabled=False)
        loud = BlueBubblesAdapter(enabled=True)
        self.assertEqual(quiet.poll(), [])
        self.assertEqual(loud.poll(), [])
        for adapter in (quiet, loud):
            result = adapter.send(None, "appr_test")  # type: ignore[arg-type]
            self.assertFalse(result.delivered)
            self.assertEqual(result.mode, "disabled")
            self.assertIn("Nothing was contacted", result.detail)
        self.assertIn("no BlueBubbles client", loud.send(None, "appr_test").detail)  # type: ignore[arg-type]

    def test_symlink_photo_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real.txt"
            target.write_text("bytes", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(target)
            app = _app(root)
            with self.assertRaises(PhotoError):
                app.submit(
                    InboundMessage(
                        channel="local_cli",
                        sender_label="tenant",
                        body="bulb out",
                        photos=[PhotoInput(path=str(link))],
                    )
                )


if __name__ == "__main__":
    unittest.main()
