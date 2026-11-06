"""Load the committed sample config and the eight module definitions.

Unknown keys fail closed. There is no key that turns on a live send or a
live charge.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from gary.errors import ConfigError
from gary.models import ModuleSpec, Settings
from gary.paths import repo_root
from gary.util import has_forbidden_key, norm_key, value_has_secret_marker

EXAMPLE_CONFIG = repo_root() / "config" / "gary.example.toml"
MODULES_PATH = repo_root() / "config" / "modules.toml"

EXPECTED_MODULE_IDS = (
    "maintenance",
    "barbershop_booking",
    "tour_scheduling",
    "tenant_marketing",
    "website_rebuild",
    "lead_gen",
    "hiring",
    "online_academy",
)

REQUIRED_GATES = frozenset({"outbound_contact", "spend"})
WORKFLOWS = frozenset({"maintenance_intake", "docs_only", "none"})


def load_settings(path: Path | None = None) -> Settings:
    config_path = EXAMPLE_CONFIG if path is None else Path(path)
    if not config_path.is_file():
        raise ConfigError(f"config file not found: {config_path}")
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    _reject_secrets(data, str(config_path))
    _reject_unknown(data)
    gary = data["gary"]
    adapter = data["adapter"]
    bluebubbles = data["bluebubbles"]
    approvals = data["approvals"]
    name = gary["name"]
    adapter_name = adapter["name"]
    enabled = bluebubbles["enabled"]
    require_human = approvals["require_human"]
    if not isinstance(name, str) or not name.strip():
        raise ConfigError("gary.name must be a short label")
    if len(name) > 40:
        raise ConfigError("gary.name is too long")
    if adapter_name not in {"mock", "bluebubbles"}:
        raise ConfigError(
            "adapter.name must be mock or bluebubbles. "
            "Inkbox is Rhonda's relay and is not a Gary connector in this starter."
        )
    if not isinstance(enabled, bool):
        raise ConfigError("bluebubbles.enabled must be true or false")
    if require_human is not True:
        raise ConfigError(
            "approvals.require_human must be true. This starter has no unattended send or spend mode."
        )
    if adapter_name == "mock" and enabled:
        raise ConfigError("bluebubbles.enabled must be false while adapter.name is mock")
    return Settings(
        name=name.strip(),
        adapter_name=adapter_name,
        bluebubbles_enabled=enabled,
        require_human=True,
        config_path=str(config_path),
    )


def load_modules(path: Path | None = None) -> list[ModuleSpec]:
    modules_path = MODULES_PATH if path is None else Path(path)
    if not modules_path.is_file():
        raise ConfigError(f"module file not found: {modules_path}")
    with modules_path.open("rb") as handle:
        data = tomllib.load(handle)
    _reject_secrets(data, str(modules_path))
    source_note = data.get("source_note", "")
    if not isinstance(source_note, str) or "user-supplied" not in source_note.lower():
        raise ConfigError("modules source_note must say the business facts are user-supplied")
    raw_modules = data.get("module")
    if not isinstance(raw_modules, list):
        raise ConfigError("modules.toml needs a [[module]] entry for each business module")
    specs = [_module_from_dict(item) for item in raw_modules]
    ids = tuple(spec.id for spec in specs)
    if ids != EXPECTED_MODULE_IDS:
        raise ConfigError(
            "module ids must stay in the eight-branch order: " + ", ".join(EXPECTED_MODULE_IDS)
        )
    runnable = [spec.id for spec in specs if spec.runnable]
    if runnable != ["maintenance"]:
        raise ConfigError("only the maintenance module may use the maintenance_intake workflow")
    return specs


def _module_from_dict(item: object) -> ModuleSpec:
    if not isinstance(item, dict):
        raise ConfigError("each module entry must be a table")
    allowed = {
        "id",
        "name",
        "workflow",
        "summary",
        "human_gates",
        "intended",
        "not_implemented",
        "blockers",
        "docs",
        "notes",
    }
    unknown = set(item) - allowed
    if unknown:
        raise ConfigError("unknown module fields: " + ", ".join(sorted(unknown)))
    for key in ("id", "name", "workflow", "summary", "human_gates", "notes"):
        if key not in item:
            raise ConfigError(f"module is missing {key}")
    workflow = item["workflow"]
    if workflow not in WORKFLOWS:
        raise ConfigError(f"unsupported workflow: {workflow}")
    module_id = item["id"]
    if workflow == "maintenance_intake" and module_id != "maintenance":
        raise ConfigError("maintenance_intake is only valid on the maintenance module")
    if workflow == "docs_only" and module_id != "website_rebuild":
        raise ConfigError("docs_only is only valid on the website_rebuild module")
    gates = _strings(item["human_gates"], "human_gates")
    if not REQUIRED_GATES.issubset(gates):
        raise ConfigError("every module needs human gates for outbound_contact and spend")
    if module_id == "maintenance" and "emergency_decision" not in gates:
        raise ConfigError("maintenance needs the emergency_decision human gate")
    docs = _strings(item.get("docs", []), "docs")
    for rel in docs:
        doc_path = Path(rel)
        if doc_path.is_absolute() or ".." in doc_path.parts:
            raise ConfigError(f"doc path must stay inside the repo: {rel}")
        if workflow == "docs_only" and not (repo_root() / doc_path).is_file():
            raise ConfigError(f"missing docs for {module_id}: {rel}")
    return ModuleSpec(
        id=str(module_id),
        name=str(item["name"]),
        workflow=str(workflow),
        summary=str(item["summary"]),
        human_gates=tuple(gates),
        intended=tuple(_strings(item.get("intended", []), "intended")),
        not_implemented=tuple(_strings(item.get("not_implemented", []), "not_implemented")),
        blockers=tuple(_strings(item.get("blockers", []), "blockers")),
        docs=tuple(docs),
        notes=tuple(_strings(item["notes"], "notes")),
    )


def _strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ConfigError(f"{label} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _reject_secrets(data: object, label: str) -> None:
    if has_forbidden_key(data) or value_has_secret_marker(data):
        raise ConfigError(f"{label} contains a forbidden secret-like key or value. Nothing was loaded.")


def _reject_unknown(data: dict) -> None:
    expected = {"gary": {"name"}, "adapter": {"name"}, "bluebubbles": {"enabled"}, "approvals": {"require_human"}}
    if set(data) != set(expected):
        raise ConfigError(
            "config sections must be gary, adapter, bluebubbles, and approvals. "
            f"Got: {', '.join(sorted(map(str, data)))}"
        )
    for section, keys in expected.items():
        table = data[section]
        if not isinstance(table, dict):
            raise ConfigError(f"{section} must be a table")
        extra = {norm_key(str(key)) for key in table} - {norm_key(key) for key in keys}
        # Compare raw keys so a renamed secret cannot hide beside the allowed key.
        if set(table) != keys or extra:
            raise ConfigError(
                f"{section} only allows {', '.join(sorted(keys))}. "
                "URL, password, and token fields are not config in this starter."
            )
