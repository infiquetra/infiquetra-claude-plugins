"""Tests for the Saga shared engine-offer helper (#451)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
HELPER_SCRIPT = SCRIPT_DIR / "engine_offer.py"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"

STAGE_SKILLS = {
    "ideate": ROOT / "plugins" / "saga" / "skills" / "ideate" / "SKILL.md",
    "brainstorm": ROOT / "plugins" / "saga" / "skills" / "brainstorm" / "SKILL.md",
    "work": ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md",
    "doc-review": ROOT / "plugins" / "saga" / "skills" / "doc-review" / "SKILL.md",
    "code-review": ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md",
}


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


E = _load("engine_offer", HELPER_SCRIPT)


def test_intent_tier_resolution_uses_existing_model_effort_vocabulary() -> None:
    execution_spec = _load("execution_spec_for_engine_offer", EXECUTION_SPEC_SCRIPT)

    judgment = E.resolve_offer("code-review", unit_shape="judgment")
    mechanical = E.resolve_offer("work", unit_shape="mechanical")

    assert judgment.intent == "second-opinion"
    assert judgment.model == "opus"
    assert judgment.effort == "high"
    assert mechanical.intent == "offload"
    assert mechanical.model == "sonnet"
    assert mechanical.effort == "medium"
    assert judgment.advisory_only is True
    assert mechanical.advisory_only is True
    assert judgment.model in execution_spec.MODELS
    assert judgment.effort in execution_spec.EFFORTS
    assert mechanical.model in execution_spec.MODELS
    assert mechanical.effort in execution_spec.EFFORTS


def test_unsupported_stage_fails_loudly() -> None:
    with pytest.raises(E.EngineOfferError, match="stage"):
        E.resolve_offer("retro")


def test_unattended_silent_reuse(tmp_path: Path) -> None:
    E.save_preference(
        tmp_path,
        "work",
        E.Preference(intent="offload", model="sonnet", effort="medium"),
    )

    offer = E.resolve_offer("work", repo_root=tmp_path, attended=False, unit_shape="judgment")

    assert offer.intent == "offload"
    assert offer.source == "stored"
    assert offer.prompt_required is False


def test_attended_prompt_once_then_persisted_preference_suppresses_prompt(tmp_path: Path) -> None:
    first = E.resolve_offer("ideate", repo_root=tmp_path, attended=True)
    assert first.prompt_required is True
    assert first.choices[0] == "second-opinion"

    E.save_preference(tmp_path, "ideate", E.Preference(intent="none"))
    second = E.resolve_offer("ideate", repo_root=tmp_path, attended=True)

    assert second.intent == "none"
    assert second.source == "stored"
    assert second.prompt_required is False


def test_none_roundtrip_suppresses_future_offers(tmp_path: Path) -> None:
    saved_path = E.save_preference(tmp_path, "doc-review", E.Preference(intent="none"))

    raw = json.loads(saved_path.read_text())
    assert raw["stages"]["doc-review"] == {"intent": "none"}

    offer = E.resolve_offer("doc-review", repo_root=tmp_path, unit_shape="judgment")
    assert offer.intent == "none"
    assert offer.model is None
    assert offer.effort is None


def test_unknown_work_shape_defaults_to_no_offer() -> None:
    offer = E.resolve_offer("work", unit_shape="unknown", attended=True)

    assert offer.intent == "none"
    assert offer.model is None
    assert offer.effort is None
    assert offer.prompt_required is True
    assert offer.choices[0] == "none"


def test_saving_same_stage_preference_twice_leaves_valid_json(tmp_path: Path) -> None:
    first_path = E.save_preference(
        tmp_path,
        "work",
        E.Preference(intent="offload", model="sonnet", effort="medium"),
    )
    second_path = E.save_preference(tmp_path, "work", E.Preference(intent="none"))

    assert second_path == first_path
    raw = json.loads(second_path.read_text(encoding="utf-8"))
    assert raw == {"version": 1, "stages": {"work": {"intent": "none"}}}
    assert E.resolve_offer("work", repo_root=tmp_path, unit_shape="mechanical").intent == "none"


def test_malformed_preferences_fail_loudly(tmp_path: Path) -> None:
    prefs_path = tmp_path / ".saga" / "engine-prefs.json"
    prefs_path.parent.mkdir()
    prefs_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(E.EngineOfferError, match="malformed JSON"):
        E.load_preferences(tmp_path)


def test_cli_offer_and_remember_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        E.main(
            [
                "offer",
                "--stage",
                "work",
                "--repo-root",
                str(tmp_path),
                "--unit-shape",
                "mechanical",
            ]
        )
        == 0
    )
    offer = json.loads(capsys.readouterr().out)
    assert offer["intent"] == "offload"

    assert (
        E.main(
            [
                "remember",
                "--stage",
                "work",
                "--repo-root",
                str(tmp_path),
                "--intent",
                "none",
            ]
        )
        == 0
    )
    remembered = json.loads(capsys.readouterr().out)
    assert remembered["intent"] == "none"

    assert E.resolve_offer("work", repo_root=tmp_path, unit_shape="mechanical").intent == "none"


def test_mechanical_opt_out_default() -> None:
    explicit = E.resolve_offer("work", unit_shape="mechanical")
    fingerprinted = E.resolve_offer(
        "work",
        labels=["scaffold"],
        text="Generate a deterministic template scaffold",
    )

    assert explicit.intent == "offload"
    assert fingerprinted.intent == "offload"
    assert fingerprinted.prompt_required is False


def test_judgment_shape_does_not_default_to_offload() -> None:
    offer = E.resolve_offer(
        "work",
        text="Architecture review for a design trade-off in a generated scaffold",
    )

    assert offer.unit_shape == "judgment"
    assert offer.intent == "second-opinion"
    assert offer.intent != "offload"


def test_drift_guard_stage_skills_reference_shared_engine_offer_helper() -> None:
    for stage, path in STAGE_SKILLS.items():
        text = path.read_text(encoding="utf-8")
        expected = f"engine_offer.py offer --stage {stage}"
        assert expected in text, f"{path} must call the shared engine_offer helper"
        if "engine-prefs.json" in text:
            assert "engine_offer.py" in text, f"{path} must not hand-roll engine preferences"


def test_engine_preference_file_is_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".saga/engine-prefs.json" in gitignore
