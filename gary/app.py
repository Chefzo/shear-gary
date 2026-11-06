"""Composition root for the local CLI and the demo."""

from __future__ import annotations

from pathlib import Path

from gary.adapters import build_adapter
from gary.config import load_modules, load_settings
from gary.errors import IntakeError, NotFoundError
from gary.gate import ApprovalGate
from gary.intake import MaintenanceIntake, require_module
from gary.models import Approval, InboundMessage, IntakeResult, ModuleSpec
from gary.paths import assert_safe_data_dir
from gary.store import Store


class App:
    def __init__(self, data_dir: Path, config_path: Path | None = None) -> None:
        self.settings = load_settings(config_path)
        self.data_dir = assert_safe_data_dir(data_dir)
        self.store = Store(self.data_dir)
        self.modules = load_modules()
        self.adapter = build_adapter(self.settings)
        self.gate = ApprovalGate(self.store, self.adapter, actor=self.settings.name)
        self.intake = MaintenanceIntake(self.store, self.gate, self.modules)

    def submit(self, message: InboundMessage) -> IntakeResult:
        return self.intake.accept(message)

    def poll(self) -> list[IntakeResult]:
        results = [self.intake.accept(message) for message in self.adapter.poll()]
        self.store.audit(
            self.settings.name,
            "adapter_poll",
            "adapter",
            self.adapter.name,
            {"count": len(results), "contacted": False, "mode": self.adapter.mode},
        )
        return results

    def draft_message(self, request_id: str, to_label: str, body: str) -> Approval:
        request = self.store.get_request(request_id)
        text = body.strip()
        recipient = to_label.strip()
        if not text:
            raise IntakeError("draft body is required")
        if not recipient:
            raise IntakeError("a recipient label is required")
        if len(text) > 4000:
            raise IntakeError("draft body is too long")
        return self.gate.request_message(
            request_id=request.id,
            summary=f"Outbound draft for {request.id}",
            to_label=recipient,
            body=text,
            channel=request.channel,
            extra={"auto_send": False},
        )

    def request_spend(self, summary: str, amount_label: str, request_id: str | None) -> Approval:
        if request_id:
            self.store.get_request(request_id)
        text = summary.strip()
        if not text:
            raise IntakeError("spend summary is required")
        return self.gate.request_spend(summary=text, amount_label=amount_label, request_id=request_id)

    def module(self, module_id: str) -> ModuleSpec:
        for spec in self.modules:
            if spec.id == module_id:
                return spec
        raise NotFoundError(f"unknown module: {module_id}")

    def run_module(self, module_id: str) -> ModuleSpec:
        """Return a module only when its workflow exists. Defined modules raise."""

        return require_module(self.modules, module_id)
