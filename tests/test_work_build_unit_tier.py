"""U2 #929 — build-unit tier resolution pins.

Work's direct build-unit dispatch must resolve an explicit tier from the plan
or a documented default from the shared work-shape policy, never from the host
session. The resolver seam lives in lifecycle_state.py and delegates to the
existing tier chain.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
EXEC_STRATEGY = (
    ROOT / "plugins" / "saga" / "skills" / "work" / "references" / "execution-strategy.md"
)
LIFECYCLE_STATE_PY = ROOT / "plugins" / "saga" / "scripts" / "lifecycle_state.py"
TIER_POLICY = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "tier_policy.json"


def _read_skill() -> str:
    return WORK_SKILL.read_text(encoding="utf-8")


def _load_policy() -> dict[str, dict[str, str]]:
    return json.loads(TIER_POLICY.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# A {model, effort} pair written as a literal -- the shape the spawn site must never carry.
_TIER_PAIR_LITERAL = re.compile(
    r"""["']model["']\s*:\s*["'][a-z0-9.-]+["']\s*,\s*["']effort["']\s*:\s*["'][a-z]+["']"""
)


def _resolver():
    """The real `resolve_build_unit_tier` callable, loaded by path like its sibling helpers."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("lifecycle_state_sig", LIFECYCLE_STATE_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve_build_unit_tier


def _resolve(*args, **kwargs):
    # Lazy import to avoid top-level side effects.
    import importlib.util

    spec = importlib.util.spec_from_file_location("lifecycle_state", LIFECYCLE_STATE_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod.resolve_build_unit_tier(*args, **kwargs)


def test_explicit_plan_tier_wins_unchanged() -> None:
    plan = {"model": "opus", "effort": "high"}
    result = _resolve(plan_tier=plan, work_shape=None)
    assert result == plan
    # Ensure a different work_shape does not affect explicit win.
    result2 = _resolve(plan_tier=plan, work_shape="judgment")
    assert result2 == plan


def test_default_mechanical_resolves_from_shared_policy_not_literal() -> None:
    policy = _load_policy()
    mechanical = policy["mechanical"]
    result = _resolve(plan_tier=None, work_shape=None)
    assert result["model"] == mechanical["default_model"]
    assert result["effort"] == mechanical["default_effort"]
    # No tier literal at the spawn site. The earlier form of this assertion ended in
    # `or "resolve_build_unit_tier" in text`, and that substring is the name of the function the
    # file DEFINES -- so the disjunction was true on every possible tree and the assertion could
    # never fail. Proved by mutation: hard-coding the pair at the spawn site left it green.
    text = LIFECYCLE_STATE_PY.read_text(encoding="utf-8")
    assert not _TIER_PAIR_LITERAL.search(text), (
        "a {model, effort} pair literal appears at the spawn site; the tier must resolve through "
        "the shared registry"
    )
    assert "tier_defaults" in text, "the seam must delegate to the shared resolution chain"


def test_the_literal_guard_can_actually_fail() -> None:
    """Control for the assertion above: prove the pattern detects what its name forbids.

    An absence assertion is green on a tree where it could never match anything, which is exactly
    how the retired form passed.
    """
    assert _TIER_PAIR_LITERAL.search('    return {"model": "sonnet", "effort": "medium"}')
    assert _TIER_PAIR_LITERAL.search("    return {'model': 'opus', 'effort': 'high'}")
    assert not _TIER_PAIR_LITERAL.search(
        '        return {"model": str(plan_tier["model"]), "effort": str(plan_tier["effort"])}'
    )


def test_judgment_shape_resolves_its_registry_default() -> None:
    policy = _load_policy()
    judgment = policy["judgment"]
    result = _resolve(plan_tier=None, work_shape="judgment")
    assert result["model"] == judgment["default_model"]
    assert result["effort"] == judgment["default_effort"]
    # Ensure shape argument is honoured, not ignored.
    mechanical = policy["mechanical"]
    assert (result["model"], result["effort"]) != (
        mechanical["default_model"],
        mechanical["default_effort"],
    )


def test_no_inheritance_the_resolver_has_no_host_input_at_all() -> None:
    """Non-inheritance proved structurally and behaviourally, not by a discarded parameter.

    The earlier form passed a `host_tier` argument the function accepted and threw away. A
    parameter whose only purpose is to be ignored cannot make its own guard fail: the test asserted
    that discarding works.
    """
    import inspect

    parameters = set(inspect.signature(_resolver()).parameters)
    assert parameters == {"plan_tier", "work_shape"}, (
        f"the resolver must take no host or session input at all; got {sorted(parameters)}"
    )


def test_no_inheritance_a_hostile_environment_does_not_leak_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host-looking environment must not move the answer."""
    for name in ("CLAUDE_MODEL", "CLAUDE_EFFORT", "SAGA_MODEL", "SAGA_EFFORT", "MODEL", "EFFORT"):
        monkeypatch.setenv(name, "fable")
    policy = _load_policy()
    mechanical = policy["mechanical"]
    defaulted = _resolve(plan_tier=None, work_shape=None)
    assert defaulted["model"] == mechanical["default_model"]
    assert defaulted["effort"] == mechanical["default_effort"]
    explicit = _resolve(plan_tier={"model": "opus", "effort": "high"}, work_shape=None)
    assert explicit == {"model": "opus", "effort": "high"}


def test_an_explicit_plan_tier_is_validated_like_its_sibling_path() -> None:
    """ "Explicit wins" is about precedence, not about skipping the vocabulary check.

    The shape path can only ever produce a registry value; the explicit path used to return
    anything carrying both keys, so a plan naming a model that does not exist reached a spawn.
    """
    with pytest.raises(ValueError, match="is not one of"):
        _resolve(plan_tier={"model": "gpt-5", "effort": "high"}, work_shape=None)
    with pytest.raises(ValueError, match="is not one of"):
        _resolve(plan_tier={"model": "opus", "effort": "maximum"}, work_shape=None)
    # And a legal explicit tier still wins unchanged.
    assert _resolve(plan_tier={"model": "haiku", "effort": "low"}, work_shape=None) == {
        "model": "haiku",
        "effort": "low",
    }


def test_dispatch_prose_names_resolver_and_has_no_inheritance_instruction() -> None:
    text = _read_skill()
    # Find Phase 2 section.
    start = text.find("## Phase 2")
    end = text.find("## Phase 3", start)
    assert start >= 0 and end >= 0
    phase2 = text[start:end]
    # The dispatch prose must name something an agent can RUN. Naming the Python function alone --
    # `lifecycle_state.py:resolve_build_unit_tier` -- told an agent to call a function with no CLI
    # entry point, which is an instruction it cannot follow.
    assert "resolve-build-unit-tier" in phase2, (
        "Phase 2 must name the runnable resolver subcommand, not just a Python symbol"
    )
    assert "lifecycle_state.py resolve-build-unit-tier" in phase2, (
        "the subcommand must appear as a runnable invocation against the script"
    )
    # Forbidden inheritance phrasing must not appear anywhere in the skill.
    for pattern in [
        r"inherit",
        r"the session's model",
        r"the host's model",
        r"carry forward the .* effort",
    ]:
        assert re.search(pattern, text, flags=re.IGNORECASE) is None, (
            f"Work still contains forbidden inheritance phrasing {pattern!r}"
        )
    # Also ensure Phase 2 does not contain those patterns (stricter).
    for pattern in [r"inherit", r"the session's model", r"the host's model"]:
        assert re.search(pattern, phase2, flags=re.IGNORECASE) is None


def test_malformed_overlay_raises_through_seam(tmp_path: Path) -> None:
    # Create a malformed .saga/tier-defaults.json and prove the seam delegates
    # to the existing overlay contract rather than falling back silently.
    overlay_dir = tmp_path / ".saga"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    (overlay_dir / "tier-defaults.json").write_text("{ not valid json", encoding="utf-8")
    orig_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        import importlib.util

        spec = importlib.util.spec_from_file_location("lifecycle_state_tmp", LIFECYCLE_STATE_PY)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[arg-type]
        with pytest.raises(Exception) as excinfo:
            mod.resolve_build_unit_tier(plan_tier=None, work_shape=None)
        # Must be TierDefaultsError (subclass of ValueError) from tier_defaults.
        assert (
            "not valid JSON" in str(excinfo.value)
            or "TierDefaultsError" in type(excinfo.value).__name__
            or isinstance(excinfo.value, ValueError)
        )
    finally:
        os.chdir(orig_cwd)


def test_resolved_tier_in_execution_evidence_prose() -> None:
    work = _read_skill()
    strat = EXEC_STRATEGY.read_text(encoding="utf-8")
    # Phase-4 work-session must mention recording the tier.
    assert "resolve-build-unit-tier" in work
    # Execution evidence mention lives in Phase 2 bullet and Phase 4.
    assert "execution evidence" in work.lower() or "execution evidence" in strat.lower()
    # Strategy doc must describe build-unit tier resolution.
    assert "resolve_build_unit_tier" in strat
    assert "mechanical" in strat.lower()
    assert "tier_policy.json" in strat


def test_no_new_operator_question_on_dispatch() -> None:
    """Issue #929 forbids a new operator question in the tier dispatch. Assert that, unconditionally.

    The disjunct `or "Build-unit tier" in phase2` made this guard unfailable: the repair itself
    added that heading to Phase 2, so the second operand is always true and an `AskUserQuestion`
    seeded into the dispatch passed. That is the same defect class the tier repair was written to
    fix, recurring inside the file that fixed it -- and what it let through is exactly the thing
    the issue names.
    """
    text = _read_skill()
    phase2_start = text.find("## Phase 2")
    phase2_end = text.find("## Phase 3", phase2_start)
    assert phase2_start >= 0 and phase2_end > phase2_start, "Phase 2 must be findable"
    phase2 = text[phase2_start:phase2_end]
    assert "AskUserQuestion" not in phase2
    assert "questionnaire" not in phase2.lower()


def test_the_dispatch_question_guard_can_actually_fail() -> None:
    """Control: the assertions above must reject a Phase 2 that DOES carry a questionnaire.

    Without this, a guard that reads the wrong slice of the document -- or an empty one -- reports
    the same green as a guard that is working."""
    seeded = "## Phase 2\nAsk the operator with AskUserQuestion which tier to use.\n## Phase 3"
    phase2 = seeded[seeded.find("## Phase 2") : seeded.find("## Phase 3")]
    assert "AskUserQuestion" in phase2, "the control fixture must contain what the guard forbids"
    # The real slice must not be empty, or the guard passes vacuously on any document.
    text = _read_skill()
    real = text[text.find("## Phase 2") : text.find("## Phase 3", text.find("## Phase 2"))]
    assert len(real) > 500, "Phase 2 must be a substantial slice, not an empty or truncated one"
    assert "Build-unit tier" in real, "and it must be the slice that carries the tier dispatch"


def test_premium_choice_boundary_left_untouched() -> None:
    # U2's diff must not touch execution_spec.py or plan/SKILL.md per R10.
    # Pin by checking that work/SKILL.md does not add a Work-side premium check.
    text = _read_skill()
    phase2 = text[text.find("## Phase 2") : text.find("## Phase 3")]
    # The premium-choice boundary lives in execution_spec.py validate --require-receipts
    # and plan/SKILL.md; Work must not add its own premium check.
    assert "premium-choice" not in phase2.lower() and "premium_choice" not in phase2.lower()
    # Also ensure lifecycle_state seam does not gain premium logic.
    seam_text = LIFECYCLE_STATE_PY.read_text(encoding="utf-8")
    assert seam_text.count("resolve_build_unit_tier") == 1 or "premium" not in seam_text.lower()
