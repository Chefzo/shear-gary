from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

# Normalized key names that must not appear in config or audit details.
FORBIDDEN_KEY_NORMS = frozenset(
    {
        "password",
        "passwd",
        "token",
        "apikey",
        "secret",
        "privatekey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "accesstoken",
        "refreshtoken",
        "serverpassword",
        "bearertoken",
    }
)

# Value fragments that are credentials even when the key looks ordinary.
SECRET_VALUE_MARKERS = (
    "-----BEGIN",
    "sk_live_",
    "sk_test_",
    "xoxb-",
    "xoxp-",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def has_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if norm_key(str(key)) in FORBIDDEN_KEY_NORMS or has_forbidden_key(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(has_forbidden_key(item) for item in value)
    return False


def value_has_secret_marker(value: object) -> bool:
    if isinstance(value, str):
        return any(marker in value for marker in SECRET_VALUE_MARKERS)
    if isinstance(value, dict):
        return any(value_has_secret_marker(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(value_has_secret_marker(item) for item in value)
    return False


def sanitize_detail(detail: dict) -> dict:
    if has_forbidden_key(detail) or value_has_secret_marker(detail):
        return {"redacted": True, "reason": "detail included secret-like material"}
    return detail


def dump_json(detail: dict) -> str:
    return json.dumps(sanitize_detail(detail), sort_keys=True, separators=(",", ":"))


def clean_actor(value: str) -> str:
    text = value.strip()
    if not text or len(text) > 120:
        raise ValueError("actor label must be 1–120 characters")
    if value_has_secret_marker(text):
        raise ValueError("actor label looks like a credential")
    return text
