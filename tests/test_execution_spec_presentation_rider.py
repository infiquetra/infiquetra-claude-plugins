"""Oracle tests for the house-style presentation rider stamped into emitted agent() prompts.

Issue #704 U5. ``execution_spec._agent_prompt`` is the single funnel for every worker prompt saga
emits, so the canonical presentation contract is appended there once and nowhere else. These tests
police three properties the refute-3 panel attacks:

1. the rider reaches every emitted ``agent()`` worker prompt EXACTLY once (never twice, through any
   of the three ``_agent_prompt`` call sites: the routing context, the unattended escalation retry,
   and the inline-baseline renderer);
2. the stamped text is byte-identical to
   ``plugins/house-style/references/subagent-presentation-preamble.md``;
3. verifier prompts are NOT stamped -- saga spawns every verifier as ``saga:readonly-verifier``,
   whose definition file carries the preamble instead.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"
CANONICAL_PREAMBLE = (
    ROOT / "plugins" / "house-style" / "references" / "subagent-presentation-preamble.md"
)


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec", EXECUTION_SPEC_SCRIPT)
_load("lifecycle_state", SCRIPT_DIR / "lifecycle_state.py")


@pytest.fixture(autouse=True)
def _external_engine_preflight_is_deterministically_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ES.engine_resolver,
        "preflight",
        lambda *_args, **_kwargs: {"available": True, "reason": "test snapshot"},
    )


def _routing_snapshots() -> dict[str, object]:
    return {
        "routing_overlay": ES.engine_overlay.EngineOverlay(),
        "routing_calibration": ES.engine_calibration.CalibrationSignals(),
    }


# --- Spec fixtures ---------------------------------------------------------------------------

_WORKER_UNIT: dict[str, object] = {
    "unit_id": "U1",
    "label": "U1",
    "tier": {"model": "sonnet", "effort": "medium"},
    "prompt": "do the work",
    "returns": ["result"],
}

_CHEAP_FANOUT_UNIT: dict[str, object] = {
    "unit_id": "U2",
    "label": "U2",
    "tier": {"model": "haiku", "effort": "low"},
    "prompt": "do the cheap fan-out work",
    "returns": ["result"],
    "fanout": True,
    "targets": ["alpha", "beta"],
    "depends_on": ["U1"],
}


def _spec(units: list[dict[str, object]], name: str = "rider-demo") -> Any:
    spec = ES.ExecutionSpec.from_dict(
        {"name": name, "description": "d", "repo": "/tmp/r", "units": units}
    )
    spec.validate()
    return spec


def _panel_unit(**overrides: object) -> dict[str, object]:
    unit = dict(_WORKER_UNIT)
    unit["verify"] = {"n": 3, "pass_rule": "majority"}
    unit.update(overrides)
    return unit


def _escalate_unit() -> dict[str, object]:
    unit = _panel_unit()
    unit["escalate_on_signal"] = True
    return unit


# --- Emitted-prompt extraction (independent oracle) ------------------------------------------

_JS_STRING = r'"(?:[^"\\]|\\.)*"'
# The first argument of an emitted `agent(` call, whether passed directly (worker) or wrapped in
# the __verifierPrompt() helper (verifier). Deliberately parsed out of the emitted text rather
# than derived from execution_spec internals.
_AGENT_CALL = re.compile(r"agent\(\s*\n\s*(__verifierPrompt\(\s*)?(" + _JS_STRING + r")")


def _emitted_prompts(script: str) -> list[tuple[str, str]]:
    """Return ``(kind, prompt)`` for every ``agent()`` call in an emitted workflow script."""
    found: list[tuple[str, str]] = []
    for match in _AGENT_CALL.finditer(script):
        kind = "VERIFIER" if match.group(1) else "WORKER"
        found.append((kind, json.loads(match.group(2))))
    return found


def _workers(script: str) -> list[str]:
    return [prompt for kind, prompt in _emitted_prompts(script) if kind == "WORKER"]


def _verifiers(script: str) -> list[str]:
    return [prompt for kind, prompt in _emitted_prompts(script) if kind == "VERIFIER"]


# --- Byte identity with the canonical preamble -----------------------------------------------


def test_rider_is_byte_identical_to_canonical_preamble_file() -> None:
    canonical = CANONICAL_PREAMBLE.read_text(encoding="utf-8")
    # The constant is the file verbatim; only the file's trailing newline is dropped, because the
    # rider is joined into a prompt with "\n\n" separators rather than concatenated raw.
    assert canonical.rstrip("\n") == ES.PRESENTATION_RIDER
    assert canonical == ES.PRESENTATION_RIDER + "\n"
    assert canonical.startswith(ES.PRESENTATION_RIDER)


def test_canonical_preamble_file_exists_and_is_non_trivial() -> None:
    # Guards the failure mode where the reference file is deleted or emptied and the byte-identity
    # test above degrades into comparing two empty strings.
    assert CANONICAL_PREAMBLE.is_file()
    assert len(ES.PRESENTATION_RIDER) > 1000
    assert ES.PRESENTATION_RIDER.startswith("## Presentation contract (Infiquetra house style)")


# --- LENS 1: every emitted worker prompt carries the rider exactly once -----------------------


def test_every_emitted_agent_prompt_carries_the_rider() -> None:
    script = str(ES.emit_workflow_script(_spec([_WORKER_UNIT, _CHEAP_FANOUT_UNIT])))
    workers = _workers(script)
    assert len(workers) == 2
    for prompt in workers:
        assert ES.PRESENTATION_RIDER in prompt


def test_rider_appears_exactly_once_per_emitted_prompt() -> None:
    script = str(ES.emit_workflow_script(_spec([_WORKER_UNIT, _CHEAP_FANOUT_UNIT])))
    for prompt in _workers(script):
        assert prompt.count(ES.PRESENTATION_RIDER) == 1
        # The section header is the cheapest independent double-application tell: a second copy
        # spliced in by a downstream emitter would raise this count even if whitespace differed.
        assert prompt.count("## Presentation contract (Infiquetra house style)") == 1


def test_rider_appears_once_across_call_site_build_emission_routing_context() -> None:
    # Call site 1: _build_emission_routing_context renders each unit's prompt once and every
    # emitter (_emit_thunk, _emit_parallel_wave, _emit_verify_loop_singleton) reads it back off
    # UnitRouting -- so a unit emitted through a parallel wave must not gain a second copy.
    spec = _spec(
        [
            _WORKER_UNIT,
            {
                "unit_id": "U3",
                "label": "U3",
                "tier": {"model": "sonnet", "effort": "medium"},
                "prompt": "a sibling that runs in the same wave",
                "returns": ["result"],
            },
        ]
    )
    script = str(ES.emit_workflow_script(spec))
    workers = _workers(script)
    assert len(workers) == 2
    assert [p.count(ES.PRESENTATION_RIDER) for p in workers] == [1, 1]
    # Whole-script accounting: two emitted worker prompts, two rider copies, no third.
    assert script.count("## Presentation contract (Infiquetra house style)") == 2


def test_rider_appears_once_across_call_site_unattended_escalation_retry() -> None:
    # Call site 2: the _emit_verify_panel unattended one-rung climb re-renders the retry prompt.
    spec = _spec([_escalate_unit()])
    script = str(ES.emit_workflow_script(spec, unattended=True, **_routing_snapshots()))
    assert "climbing ONE rung to sonnet/high" in script  # the retry branch really is emitted
    workers = _workers(script)
    assert len(workers) == 2  # the initial call plus the climbed retry
    for prompt in workers:
        assert prompt.count(ES.PRESENTATION_RIDER) == 1


def test_rider_appears_once_across_call_site_inline_baseline() -> None:
    # Call site 3: emit_inline_baseline renders the same prompts into operator-facing markdown.
    baseline = ES.emit_inline_baseline(_spec([_WORKER_UNIT, _CHEAP_FANOUT_UNIT]))
    assert baseline.count("## Presentation contract (Infiquetra house style)") == 2


def test_rider_survives_a_prompt_that_already_mentions_presentation() -> None:
    # A unit whose own prompt quotes the contract must still get exactly one appended copy; the
    # emitter never deduplicates, so the count is prompt-mentions plus one.
    unit = dict(_WORKER_UNIT)
    unit["prompt"] = "follow the presentation contract in the house-style plugin"
    script = str(ES.emit_workflow_script(_spec([unit])))
    assert _workers(script)[0].count(ES.PRESENTATION_RIDER) == 1


# --- LENS 2: verifier prompts are deliberately NOT stamped -----------------------------------


def test_verifier_prompts_do_not_carry_the_rider() -> None:
    spec = _spec([_panel_unit()])
    script = str(ES.emit_workflow_script(spec, **_routing_snapshots()))
    verifiers = _verifiers(script)
    assert len(verifiers) == 3  # the refute-3 panel really is emitted
    for prompt in verifiers:
        assert ES.PRESENTATION_RIDER not in prompt
        assert "## Presentation contract" not in prompt
    # Every verifier is spawned as the readonly-verifier agent, whose definition file carries the
    # preamble instead (issue #704 U6) -- that is why stamping here would be a double-application.
    assert script.count('agentType: "saga:readonly-verifier"') == 3


def test_verifier_prompt_builder_is_untouched_by_the_rider() -> None:
    spec = _spec([_panel_unit()])
    unit = spec.unit_by_id("U1")
    assert unit is not None
    assert ES.PRESENTATION_RIDER not in ES._verifier_prompt(unit)


# --- LENS 3 / degenerate inputs ---------------------------------------------------------------


def test_zero_unit_spec_behaviour_is_unchanged_by_the_rider() -> None:
    # The plan's scenario reads "a spec with zero units emits without error", but the emitter has
    # always rejected an empty spec in validate() (execution_spec.py:1731), before any prompt is
    # rendered. The rider must not change that: the same SpecError, with the same message.
    spec = ES.ExecutionSpec.from_dict(
        {"name": "empty", "description": "d", "repo": "/tmp/r", "units": []}
    )
    with pytest.raises(ES.SpecError, match="spec needs at least one unit"):
        ES.emit_workflow_script(spec)


def test_zero_unit_inline_baseline_behaviour_is_unchanged_by_the_rider() -> None:
    # emit_inline_baseline validates too (execution_spec.py:3975), so the empty spec is rejected
    # on that path as well -- again unchanged by the rider.
    spec = ES.ExecutionSpec.from_dict(
        {"name": "empty", "description": "d", "repo": "/tmp/r", "units": []}
    )
    with pytest.raises(ES.SpecError, match="spec needs at least one unit"):
        ES.emit_inline_baseline(spec)


def test_agent_prompt_orders_the_rider_ahead_of_the_return_contract() -> None:
    # The return contract is what the workflow gate parses, so it keeps the final position; the
    # preamble's own text defers to it explicitly. Order is asserted, not assumed.
    spec = _spec([_WORKER_UNIT])
    unit = spec.unit_by_id("U1")
    assert unit is not None
    prompt = ES._agent_prompt(spec, unit)
    assert prompt.startswith("do the work\n\n")
    assert prompt.index(ES.PRESENTATION_RIDER) < prompt.index("RETURN CONTRACT (all tiers)")
