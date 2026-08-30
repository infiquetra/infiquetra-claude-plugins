"""Versioned structured pre-answer carrier — issue #924 (unit U3).

Runtime tests against ``plugins/saga/scripts/plan_pre_answers.py`` (plan KTD5), plus
the rigidity pin on the Phase 0 intake subsection. None of these tests asserts a Plan
question, its wording, or the order of the conversation (R29): the guard is asserted
as the absence of rigid prose shapes in the subsection this unit adds, and as runtime
behaviour — applied and narrated, fall-through on absence, stop on conflict, an unknown
schema refused whole.

Mutation wiring (issue 924's mutation proof):

* removing the conflict stop from the validator fails the invalid-value and
  contradiction tests (they assert the stop and an empty ``applied``, so a fallback to
  any default fails them);
* removing the caller from the outcome fails the caller-recorded test;
* breaking the fence extraction fails every test that carries a block.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "saga"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
PLAN_SKILL = PLUGIN_ROOT / "skills" / "plan" / "SKILL.md"

SCHEMA_TOKEN = "plan_pre_answers.v1"


def _load_module(script_name: str) -> ModuleType:
    """Load a script module by file path, registered in ``sys.modules``.

    Registration matters: ``plan_pre_answers.py`` defines a frozen ``@dataclass`` and
    (on Python 3.12+) dataclass processing looks the class's ``__module__`` up in
    ``sys.modules`` while building it — the same convention as
    ``test_saga_plan_save_and_routing.py``.
    """
    name = script_name.removesuffix(".py")
    path = SCRIPTS_DIR / script_name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pre_answers() -> ModuleType:
    return _load_module("plan_pre_answers.py")


def _invocation(carrier: Mapping[str, object]) -> str:
    """A realistic ``/plan`` invocation text carrying the carrier in a fenced block."""
    payload = json.dumps(carrier, indent=2)
    return f"/plan work issue #924 — settle the plan for the carrier contract.\n\n```json\n{payload}\n```\n"


# --- positive: applied and narrated, with the caller ---------------------------------


def test_valid_backend_is_applied_with_its_caller(pre_answers: ModuleType) -> None:
    carrier = {"schema": SCHEMA_TOKEN, "caller": "orchestrate", "backend": "inline"}

    outcome = pre_answers.evaluate(_invocation(carrier))

    assert outcome.stop is None
    assert outcome.applied == {"backend": "inline"}
    # The narration contract (R16): the applied value and the supplying caller are
    # returned together. Dropping the caller from the outcome fails this assertion.
    assert outcome.caller == "orchestrate"


def test_omitted_destination_falls_through_without_stop(pre_answers: ModuleType) -> None:
    carrier = {"schema": SCHEMA_TOKEN, "caller": "orchestrate", "backend": "inline"}

    outcome = pre_answers.evaluate(_invocation(carrier))

    assert outcome.stop is None
    assert "destination" in outcome.omitted
    assert "destination" not in outcome.applied
    assert outcome.applied == {"backend": "inline"}


def test_empty_carrier_is_valid_and_omits_both(pre_answers: ModuleType) -> None:
    outcome = pre_answers.evaluate(_invocation({"schema": SCHEMA_TOKEN}))

    assert outcome.stop is None
    assert outcome.applied == {}
    assert set(outcome.omitted) == {"backend", "destination"}


def test_carrier_is_found_among_unrelated_fenced_blocks(pre_answers: ModuleType) -> None:
    carrier = {"schema": SCHEMA_TOKEN, "caller": "orchestrate", "backend": "team-execution"}
    text = (
        "/plan resume issue #924\n\n"
        "Prior state for context:\n\n"
        "```bash\npython3 plugins/saga/scripts/saga.py scan\n```\n\n"
        "The caller's settlement:\n\n"
        f"```json\n{json.dumps(carrier, indent=2)}\n```\n\n"
        "```\nnot json at all\n```\n"
    )

    outcome = pre_answers.evaluate(text)

    assert outcome.stop is None
    assert outcome.applied == {"backend": "team-execution"}
    assert outcome.caller == "orchestrate"


# --- negative: absence is not an error (R17, R20) ------------------------------------


def test_no_carrier_applies_nothing_omits_nothing_stops_nothing(pre_answers: ModuleType) -> None:
    # Direct /plan: an issue reference with no carrier. Nothing applied, nothing
    # narrated (no caller), nothing stopped — the conversation proceeds as today.
    outcome = pre_answers.evaluate("/plan work issue #924 — plan the carrier contract.")

    assert outcome.applied == {}
    assert outcome.omitted == ()
    assert outcome.stop is None
    assert outcome.caller is None


def test_other_schema_families_are_not_carriers(pre_answers: ModuleType) -> None:
    text = (
        '/plan work issue #924\n\n```json\n{"schema": "intent.v1", "run_mode": "attended"}\n```\n'
    )

    outcome = pre_answers.evaluate(text)

    assert outcome.applied == {}
    assert outcome.omitted == ()
    assert outcome.stop is None
    assert outcome.caller is None


# --- negative: conflict stops, never defaults (R18) ----------------------------------


@pytest.mark.parametrize("bad_value", ["claude-cloud", "Team-Execution", 42, None], ids=str)
def test_invalid_backend_stops_and_never_defaults(
    pre_answers: ModuleType, bad_value: object
) -> None:
    carrier = {"schema": SCHEMA_TOKEN, "caller": "orchestrate", "backend": bad_value}

    outcome = pre_answers.evaluate(_invocation(carrier))

    # The stop — and, as important, what does NOT happen: no value is applied, so an
    # invalid supply can never become a silent default. Removing the conflict stop
    # from the validator fails this test.
    assert outcome.stop is not None
    assert "backend" in outcome.stop
    assert outcome.applied == {}
    assert outcome.caller is None


def test_contradiction_stops_and_prefers_neither_side(pre_answers: ModuleType) -> None:
    carrier = {"schema": SCHEMA_TOKEN, "caller": "orchestrate", "backend": "team-execution"}

    outcome = pre_answers.evaluate(_invocation(carrier), established={"backend": "inline"})

    assert outcome.stop is not None
    assert outcome.applied == {}
    # The reason names both values — neither side is silently preferred.
    assert "team-execution" in outcome.stop
    assert "inline" in outcome.stop

    # A supplied value agreeing with the established one is applied, not stopped.
    agreeing = {"schema": SCHEMA_TOKEN, "caller": "orchestrate", "backend": "inline"}
    agreed = pre_answers.evaluate(_invocation(agreeing), established={"backend": "inline"})
    assert agreed.stop is None
    assert agreed.applied == {"backend": "inline"}


# --- negative: unknown schema refused whole (R19) -------------------------------------


def test_unknown_schema_token_is_refused_whole(pre_answers: ModuleType) -> None:
    carrier = {
        "schema": "plan_pre_answers.v2",
        "caller": "orchestrate",
        "backend": "inline",
        "destination": "plan-only",
    }

    outcome = pre_answers.evaluate(_invocation(carrier))

    assert outcome.stop is not None
    assert "plan_pre_answers.v2" in outcome.stop
    # Refused whole, asserted field by field: nothing is partially applied.
    assert "backend" not in outcome.applied
    assert "destination" not in outcome.applied
    assert outcome.applied == {}
    assert outcome.caller is None


# --- negative: the two-field admission limit (R15) ------------------------------------


def test_third_field_is_rejected_not_ignored(pre_answers: ModuleType) -> None:
    carrier = {
        "schema": SCHEMA_TOKEN,
        "caller": "orchestrate",
        "backend": "inline",
        "destination": "plan-only",
        "scope_class": "medium",
    }

    outcome = pre_answers.evaluate(_invocation(carrier))

    assert outcome.stop is not None
    assert "scope_class" in outcome.stop
    assert outcome.applied == {}


def test_caller_is_metadata_outside_the_admission_limit(pre_answers: ModuleType) -> None:
    carrier = {
        "schema": SCHEMA_TOKEN,
        "caller": "orchestrate",
        "backend": "inline",
        "destination": "pr",
    }

    outcome = pre_answers.evaluate(_invocation(carrier))

    # `caller` plus both admitted decision fields: accepted, not counted against the
    # two-field limit.
    assert outcome.stop is None
    assert outcome.applied == {"backend": "inline", "destination": "pr"}
    assert outcome.caller == "orchestrate"
    assert outcome.omitted == ()


# --- contract pin: the intake subsection adds no rigidity (R8, R29) -------------------


def test_phase0_intake_subsection_adds_no_rigidity_shapes() -> None:
    # Rigidity guard, scoped to the prose this unit adds: the Phase 0 intake
    # subsection must not introduce a question, a checklist, a questionnaire, or a
    # fixed sequence. Asserting the absence of new prose shapes — never a statement
    # about the conversation's questions, wording, or order, which R29 forbids. The
    # broader file legitimately uses some of these words outside the intake
    # subsection (Phase 1's "generic checklist", Phase 4's gap checklist, Phase 5's
    # questions), so the pin is scoped to the subsection's own text.
    text = PLAN_SKILL.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^### 0\.7 .*?(?=^## )", text)
    assert match is not None, "Phase 0 intake subsection missing from plan/SKILL.md"
    subsection = match.group(0)
    # Anchor: this is the pre-answer intake subsection, not some other 0.7.
    assert "plan_pre_answers.v1" in subsection
    lowered = subsection.lower()
    for banned in ("askuserquestion", "checklist", "questionnaire", "in order, ask", "answer each"):
        assert banned not in lowered, (
            f"the Phase 0 intake subsection introduced a rigidity shape: {banned!r}"
        )
