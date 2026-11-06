import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gary.demo import run_demo
from gary.paths import repo_root


def _run(*args: str, data_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "gary", *args]
    if data_dir is not None:
        command[3:3] = ["--data-dir", str(data_dir)]
    return subprocess.run(
        command,
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


class DemoAndCliTests(unittest.TestCase):
    def test_demo_library_stays_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_demo(Path(tmp) / "demo")
            self.assertFalse(report.bluebubbles_enabled)
            self.assertEqual(report.adapter, "mock")
            self.assertTrue(report.blocked_before_approval)
            self.assertFalse(report.routine_delivered)
            self.assertFalse(report.spend_delivered)
            self.assertEqual(report.emergency_attempt_count, 0)
            self.assertEqual(report.emergency_approval_status, "pending")
            self.assertEqual(report.attempt_count, 2)
            self.assertEqual(report.module_count, 8)
            self.assertEqual(report.runnable_module_ids, ["maintenance"])
            self.assertIn("RESULT delivered=0 spent=0 dispatched=0 dry_run_records=2", report.text)
            self.assertIn("Shear (demo)", report.text)
            self.assertGreater(report.audit_count, 0)

    def test_demo_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _run("demo", data_dir=Path(tmp) / "demo")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("RESULT delivered=0 spent=0 dispatched=0 dry_run_records=2", result.stdout)
            self.assertIn("BlueBubbles: disabled", result.stdout)
            self.assertNotIn("delivered: yes", result.stdout)

    def test_cli_intake_approval_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            intake = _run(
                "intake",
                "--sender",
                "suite 9",
                "--body",
                "Burst pipe under the sink",
                data_dir=data,
            )
            self.assertEqual(intake.returncode, 0, intake.stderr)
            self.assertIn("class: emergency", intake.stdout)
            self.assertIn("sent: no", intake.stdout)
            self.assertIn("dispatched: no", intake.stdout)

            pending = _run("approvals", "--json", data_dir=data)
            self.assertEqual(pending.returncode, 0, pending.stderr)
            rows = json.loads(pending.stdout)
            self.assertEqual(len(rows), 1)
            approval_id = rows[0]["id"]

            blocked = _run("execute", approval_id, data_dir=data)
            self.assertEqual(blocked.returncode, 1)
            self.assertIn("Nothing was sent", blocked.stderr)

            approved = _run("approve", approval_id, "--by", "Shear", data_dir=data)
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertIn("sent: no", approved.stdout)

            still = _run("approvals", "--json", data_dir=data)
            self.assertEqual(json.loads(still.stdout)[0]["status"], "approved")
            self.assertEqual(_run("audit", "--json", data_dir=data).returncode, 0)

            executed = _run("execute", approval_id, "--json", data_dir=data)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            payload = json.loads(executed.stdout)
            self.assertFalse(payload["delivered"])
            self.assertFalse(payload["spent"])
            self.assertEqual(payload["result"]["mode"], "dry_run")
            self.assertFalse(payload["result"]["delivered"])

    def test_poll_and_modules_and_config_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            poll = _run("poll", data_dir=data)
            self.assertEqual(poll.returncode, 0, poll.stderr)
            self.assertIn("contacted: no", poll.stdout)
            self.assertIn("messages: 0", poll.stdout)

        modules = _run("modules")
        self.assertEqual(modules.returncode, 0, modules.stderr)
        for module_id in (
            "maintenance",
            "barbershop_booking",
            "tour_scheduling",
            "tenant_marketing",
            "website_rebuild",
            "lead_gen",
            "hiring",
            "online_academy",
        ):
            self.assertIn(module_id, modules.stdout)
        self.assertIn("runnable", modules.stdout)
        self.assertIn("docs_only", modules.stdout)

        check = _run("config-check")
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("bluebubbles_enabled: false", check.stdout)
        self.assertIn("live_send: unavailable", check.stdout)
        self.assertIn("dispatch: unavailable", check.stdout)
        self.assertFalse((repo_root() / "data").exists())

    def test_spend_command_and_sample_photo_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            intake = _run(
                "intake",
                "--body",
                "Flickering light in the office.",
                "--photo",
                str(repo_root() / "samples" / "flicker.txt"),
                data_dir=data,
            )
            self.assertEqual(intake.returncode, 0, intake.stderr)
            self.assertIn("class: routine", intake.stdout)
            self.assertIn("photos: 1", intake.stdout)
            listed = _run("list", data_dir=data)
            request_id = listed.stdout.split()[0]
            show = _run("show", request_id, data_dir=data)
            self.assertIn("sha256=", show.stdout)
            self.assertIn("sent: no", show.stdout)

            spend = _run(
                "spend",
                "--summary",
                "replacement bulb",
                "--amount",
                "12.00 USD",
                "--request",
                request_id,
                data_dir=data,
            )
            self.assertEqual(spend.returncode, 0, spend.stderr)
            self.assertIn("spent: no", spend.stdout)
            approval_id = spend.stdout.splitlines()[0].split(": ", 1)[1]
            _run("approve", approval_id, "--by", "Shear", data_dir=data)
            executed = _run("execute", approval_id, data_dir=data)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertIn("Nothing was purchased", executed.stdout)
            self.assertIn("delivered: no", executed.stdout)


if __name__ == "__main__":
    unittest.main()
