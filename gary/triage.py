"""Phrase-list triage for maintenance intake.

Edit EMERGENCY_RULES and ROUTINE_RULES with Shear. A paraphrase that is not
in the lists becomes needs_review and still waits for a person. Matching a
phrase does not dispatch anyone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gary.models import (
    CLASS_EMERGENCY,
    CLASS_NEEDS_REVIEW,
    CLASS_ROUTINE,
    ESCALATE,
    NO_ESCALATION,
    TRIAGE_LIMITATION,
    TriageResult,
)


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    phrase: str


# Longer phrases are listed before shorter ones so the recorded match stays specific.
EMERGENCY_RULES: tuple[_Rule, ...] = (
    _Rule("burst_pipe", "burst pipe"),
    _Rule("burst_pipe", "pipe burst"),
    _Rule("flooding", "flooding"),
    _Rule("flooding", "flood"),
    _Rule("water_leak", "water leak"),
    _Rule("water_leak", "major leak"),
    _Rule("sewage", "sewage"),
    _Rule("gas", "gas smell"),
    _Rule("gas", "smell of gas"),
    _Rule("gas", "smell gas"),
    _Rule("carbon_monoxide", "carbon monoxide"),
    _Rule("fire_or_smoke", "smoke"),
    _Rule("fire_or_smoke", "fire"),
    _Rule("sparking", "sparking"),
    _Rule("sparking", "sparks"),
    _Rule("no_heat", "no heat"),
    _Rule("no_heat", "heat is out"),
    _Rule("no_heat", "heat out"),
    _Rule("hvac_down", "hvac is down"),
    _Rule("hvac_down", "hvac down"),
    _Rule("hvac_down", "hvac out"),
    _Rule("hvac_down", "a/c is down"),
    _Rule("hvac_down", "ac is down"),
    _Rule("hvac_down", "a/c is out"),
    _Rule("hvac_down", "ac is out"),
    _Rule("hvac_down", "no a/c"),
    _Rule("hvac_down", "no ac"),
    _Rule("power_outage", "power outage"),
    _Rule("power_outage", "power is out"),
    _Rule("power_outage", "no power"),
)

ROUTINE_RULES: tuple[_Rule, ...] = (
    _Rule("flickering_light", "flickering light"),
    _Rule("flickering_light", "flickering"),
    _Rule("bulb", "light bulb"),
    _Rule("bulb", "lightbulb"),
    _Rule("bulb", "bulb"),
    _Rule("filter", "air filter"),
    _Rule("filter", "filter"),
    _Rule("paint", "paint"),
    _Rule("squeak", "squeaky"),
    _Rule("squeak", "squeak"),
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text) is not None


def _first(text: str, rules: tuple[_Rule, ...]) -> _Rule | None:
    for rule in rules:
        if _contains_phrase(text, rule.phrase):
            return rule
    return None


def classify(text: str) -> TriageResult:
    normalized = _normalize(text)
    emergency = _first(normalized, EMERGENCY_RULES)
    if emergency is not None:
        return TriageResult(
            classification=CLASS_EMERGENCY,
            matched_rule=emergency.rule_id,
            matched_phrase=emergency.phrase,
            escalation=ESCALATE,
            reason=f"Matched emergency phrase {emergency.phrase!r}. A person decides the response.",
            limitation=TRIAGE_LIMITATION,
        )
    routine = _first(normalized, ROUTINE_RULES)
    if routine is not None:
        return TriageResult(
            classification=CLASS_ROUTINE,
            matched_rule=routine.rule_id,
            matched_phrase=routine.phrase,
            escalation=NO_ESCALATION,
            reason=f"Matched routine phrase {routine.phrase!r}. Logged for scheduling. Nobody was contacted.",
            limitation=TRIAGE_LIMITATION,
        )
    return TriageResult(
        classification=CLASS_NEEDS_REVIEW,
        matched_rule=None,
        matched_phrase=None,
        escalation=ESCALATE,
        reason="No emergency or routine phrase matched. A person needs to classify this.",
        limitation=TRIAGE_LIMITATION,
    )
