"""Channel adapter boundary.

Mock is the default and the only adapter the sample config selects.
BlueBubbles is the intended Mac Messenger shape and stays unable to connect.
This module imports no HTTP or socket client.
"""

from __future__ import annotations

from gary.errors import ConfigError
from gary.models import (
    MODE_DISABLED,
    MODE_DRY_RUN,
    AdapterResult,
    InboundMessage,
    OutboundDraft,
    Settings,
)


class MockAdapter:
    """In-memory inbox for tests and the local CLI. send() never transmits."""

    name = "mock"
    mode = MODE_DRY_RUN

    def __init__(self) -> None:
        self._inbox: list[InboundMessage] = []

    def seed(self, message: InboundMessage) -> None:
        self._inbox.append(message)

    def poll(self) -> list[InboundMessage]:
        messages = list(self._inbox)
        self._inbox.clear()
        return messages

    def send(self, draft: OutboundDraft, approval_id: str) -> AdapterResult:
        del draft, approval_id
        return AdapterResult(
            adapter=self.name,
            mode=MODE_DRY_RUN,
            delivered=False,
            detail="Mock adapter dry-run. The message was not delivered.",
        )


class BlueBubblesAdapter:
    """Optional boundary for a future local BlueBubbles client.

    enabled in config does not open a port, read a thread, or send.
    Contact Key Verification on Enzo's separate Mac is not evidence about
    Shear's M1.
    """

    name = "bluebubbles"

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.mode = MODE_DISABLED

    def poll(self) -> list[InboundMessage]:
        return []

    def send(self, draft: OutboundDraft, approval_id: str) -> AdapterResult:
        del draft, approval_id
        if self.enabled:
            detail = (
                "BlueBubbles is marked enabled in config, and this starter still has "
                "no BlueBubbles client. Nothing was contacted."
            )
        else:
            detail = "BlueBubbles is disabled. Nothing was contacted."
        return AdapterResult(
            adapter=self.name,
            mode=MODE_DISABLED,
            delivered=False,
            detail=detail,
        )


def build_adapter(settings: Settings) -> MockAdapter | BlueBubblesAdapter:
    if settings.adapter_name == "mock":
        return MockAdapter()
    if settings.adapter_name == "bluebubbles":
        return BlueBubblesAdapter(enabled=settings.bluebubbles_enabled)
    raise ConfigError(f"unknown adapter: {settings.adapter_name}")
