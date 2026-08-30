#!/usr/bin/env python3
"""Saga Plan's versioned structured pre-answer carrier (#924, ``plan_pre_answers.v1``).

A caller that has already settled a decision hands it to ``/plan`` as a fenced JSON
block in the invocation text, instead of letting the conversation re-ask it:

```json
{
  "schema": "plan_pre_answers.v1",
  "caller": "orchestrate",
  "backend": "inline",
  "destination": "plan-only"
}
```

Intake, not a phase (plan KTD4): evaluated once, before the conversation begins. The
only visible effects a carrier may produce are narration of an applied value together
with its caller, and the absence of a question that would otherwise have been asked.

Contract shape (plan KTD5):

* ``schema`` — the version token ``plan_pre_answers.v1``. An unrecognised token is
  refused whole; no field from that carrier is applied.
* ``backend`` — decision field, from ``inline | team-execution | cc-workflows-ultracode``
  (the enum Phase 5.2 records into the plan-doc ``backend:`` field). Optional.
* ``destination`` — decision field, from ``plan-only | pr | merge | nonprod-deploy``
  (the enum Phase 5.1 asks and the tick's ``--destination`` carries). Optional. Both
  omitted is a valid empty carrier.
* ``caller`` — envelope metadata naming the supplying capability for the narration.
  NOT a decision field: exactly two decision fields are admitted, and ``caller`` sits
  outside that admission limit.

Pure functions: reads the text it is given, writes nothing, reads no file (KTD5).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SCHEMA_TOKEN = "plan_pre_answers.v1"
SCHEMA_FAMILY = "plan_pre_answers"

# The two admitted decision fields and their declared enums (R15). The backend enum is
# the one Phase 5.2 records (the plan-doc contract, saga-spec §15); the destination
# enum is the one Phase 5.1 asks (DESTINATIONS, saga-spec §4).
BACKEND_ENUM = ("inline", "team-execution", "cc-workflows-ultracode")
DESTINATION_ENUM = ("plan-only", "pr", "merge", "nonprod-deploy")
DECISION_ENUMS: dict[str, tuple[str, ...]] = {
    "backend": BACKEND_ENUM,
    "destination": DESTINATION_ENUM,
}
DECISION_FIELDS: tuple[str, ...] = tuple(DECISION_ENUMS)

# Envelope keys that are not decision fields.
ENVELOPE_KEYS = frozenset({"schema", "caller", *DECISION_FIELDS})

_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class PreAnswerOutcome:
    """The result of one carrier evaluation.

    ``applied`` — decision field -> supplied value; each is narrated with ``caller``.
    ``omitted`` — decision fields the carrier left out; they follow the normal adaptive
    conversation. Absence is never an error (R17).
    ``stop`` — when not None, the run stops and surfaces this reason; nothing is
    applied and nothing becomes a silent default (R18, R19).
    ``caller`` — the supplying capability for the narration (R16); None when nothing
    is applied.
    """

    applied: Mapping[str, str]
    omitted: tuple[str, ...]
    stop: str | None
    caller: str | None


def extract_carrier(invocation_text: str) -> dict[str, Any] | None:
    """The first fenced JSON block declaring a ``plan_pre_answers`` schema, else None.

    The transport is a fenced JSON block in the ``/plan`` invocation text — the same
    seam callers already write prose into (KTD5). Blocks that are not JSON objects, or
    that declare a different schema family, are not carriers and are ignored.
    """
    for block in _FENCE_RE.findall(invocation_text):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        schema = parsed.get("schema")
        if isinstance(schema, str) and schema.startswith(SCHEMA_FAMILY):
            return parsed
    return None


def evaluate_carrier(
    carrier: Mapping[str, Any], established: Mapping[str, str] | None = None
) -> PreAnswerOutcome:
    """Validate one carrier object; return applied values, omissions, and any stop.

    A stop is a whole-carrier verdict: nothing is applied, so an invalid or
    contradictory value can never become a silent default and a refused carrier is
    never partially applied (R18, R19).
    """
    schema = carrier.get("schema")
    if schema != SCHEMA_TOKEN:
        return PreAnswerOutcome(
            applied={},
            omitted=(),
            stop=(
                f"pre-answer carrier refused whole: unrecognised schema token {schema!r} "
                f"(expected {SCHEMA_TOKEN!r}); no field was applied"
            ),
            caller=None,
        )

    unknown = sorted(set(carrier) - ENVELOPE_KEYS)
    if unknown:
        listed = ", ".join(f"`{key}`" for key in unknown)
        verb = "is" if len(unknown) == 1 else "are"
        return PreAnswerOutcome(
            applied={},
            omitted=(),
            stop=(
                f"pre-answer carrier refused: {listed} {verb} not admitted — exactly "
                "`backend` and `destination` are the decision fields (`caller` is "
                "envelope metadata, not a decision field)"
            ),
            caller=None,
        )

    caller = carrier.get("caller")
    if caller is not None and not isinstance(caller, str):
        return PreAnswerOutcome(
            applied={},
            omitted=(),
            stop="pre-answer carrier refused: `caller` must be a string naming the "
            "supplying capability",
            caller=None,
        )

    established = established or {}
    applied: dict[str, str] = {}
    for field_name, enum in DECISION_ENUMS.items():
        if field_name not in carrier:
            continue
        value = carrier[field_name]
        if not isinstance(value, str) or value not in enum:
            return PreAnswerOutcome(
                applied={},
                omitted=(),
                stop=(
                    f"pre-answer conflict: `{field_name}` value {value!r} is not one of "
                    f"{' | '.join(enum)}; nothing was applied — surface the conflict, "
                    "never a silent default"
                ),
                caller=None,
            )
        settled = established.get(field_name)
        if settled is not None and settled != value:
            return PreAnswerOutcome(
                applied={},
                omitted=(),
                stop=(
                    f"pre-answer conflict: supplied `{field_name}` value {value!r} "
                    f"contradicts the already-established value {settled!r}; neither "
                    "side is preferred — surface the conflict"
                ),
                caller=None,
            )
        applied[field_name] = value

    omitted = tuple(name for name in DECISION_FIELDS if name not in carrier)
    return PreAnswerOutcome(applied=applied, omitted=omitted, stop=None, caller=caller)


def evaluate(
    invocation_text: str, established: Mapping[str, str] | None = None
) -> PreAnswerOutcome:
    """Evaluate the carrier in one ``/plan`` invocation text, if any (Phase 0.7 intake).

    No carrier means nothing applied, nothing omitted, and no stop (R20): direct
    ``/plan`` proceeds exactly as it does today.
    """
    carrier = extract_carrier(invocation_text)
    if carrier is None:
        return PreAnswerOutcome(applied={}, omitted=(), stop=None, caller=None)
    return evaluate_carrier(carrier, established)
