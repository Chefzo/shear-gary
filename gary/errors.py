"""Errors a caller can show to a person. They carry no secrets."""


class GaryError(Exception):
    """Base error for expected local failures."""


class ConfigError(GaryError):
    """Config or module definitions failed a safety check."""


class UnsafePath(GaryError):
    """A path would leave the working directory or temp area."""


class NotFoundError(GaryError):
    """A request or approval id is not in the local database."""


class IntakeError(GaryError):
    """A maintenance request was rejected before it was stored."""


class PhotoError(GaryError):
    """Photo metadata could not be stored."""


class GateError(GaryError):
    """The human approval gate refused the action."""


class NotApproved(GateError):
    """Execute was asked for something a person has not approved."""


class UnsupportedAction(GateError):
    """The action is outside the two gated kinds this starter records."""


class SafetyError(GaryError):
    """A result claimed a live side effect this starter must not record."""


class ModuleNotRunnable(GaryError):
    """The module is defined, and its workflow is not built."""
