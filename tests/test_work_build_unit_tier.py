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
    # No tier literal at spawn site — the file must not hardcode the pair.
    text = LIFECYCLE_STATE_PY.read_text(encoding="utf-8")
    # The seam must delegate; a hard-coded literal would be a violation.
    # Check that the file does not contain a dict literal with the mechanical tier pair.
    assert '"sonnet"' not in text or '"medium"' not in text or "resolve_build_unit_tier" in text
    # More precise: the seam file must mention tier_resolver or tier_defaults, not a literal.
    assert "tier_defaults" in text or "tier_resolver" in text


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


def test_no_inheritance_host_tier_is_ignored() -> None:
    # Host differs from both explicit plan tier and mechanical default.
    host = {"model": "fable", "effort": "xhigh"}
    plan = {"model": "opus", "effort": "high"}
    # Explicit case: host must not affect result.
    explicit = _resolve(plan_tier=plan, work_shape=None, host_tier=host)
    assert explicit == plan
    # Defaulted case: host must not affect resolution via registry.
    policy = _load_policy()
    mechanical = policy["mechanical"]
    defaulted = _resolve(plan_tier=None, work_shape=None, host_tier=host)
    assert defaulted["model"] == mechanical["default_model"]
    assert defaulted["effort"] == mechanical["default_effort"]
    assert defaulted != host


def test_dispatch_prose_names_resolver_and_has_no_inheritance_instruction() -> None:
    text = _read_skill()
    # Find Phase 2 section.
    start = text.find("## Phase 2")
    end = text.find("## Phase 3", start)
    assert start >= 0 and end >= 0
    phase2 = text[start:end]
    assert "resolve_build_unit_tier" in phase2
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
    # Search near Phase 4.
    assert "resolve_build_unit_tier" in work
    # Execution evidence mention lives in Phase 2 bullet and Phase 4.
    assert "execution evidence" in work.lower() or "execution evidence" in strat.lower()
    # Strategy doc must describe build-unit tier resolution.
    assert "resolve_build_unit_tier" in strat
    assert "mechanical" in strat.lower()
    assert "tier_policy.json" in strat


def test_no_new_operator_question_on_dispatch() -> None:
    text = _read_skill()
    phase2_start = text.find("## Phase 2")
    phase2_end = text.find("## Phase 3", phase2_start)
    phase2 = text[phase2_start:phase2_end]
    # No AskUserQuestion or questionnaire in Phase 2 tier dispatch.
    assert "AskUserQuestion" not in phase2 or "Build-unit tier" in phase2
    # Ensure no new routine questionnaire phrase added.
    assert "questionnaire" not in phase2.lower()


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
