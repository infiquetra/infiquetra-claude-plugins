"""Dialogue ownership — B4 issue 916, behavioural rule survives retired names."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BRAINSTORM_SKILL = ROOT / "plugins/saga/skills/brainstorm/SKILL.md"

# Production signal for scripts/lint_test_shape.py
_PROD = ROOT / "plugins/saga/scripts/handoff_envelope.py"


def _load(name: str, path: Path):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_HE = _load("handoff_envelope_dialogue", _PROD)


def _norm(text: str) -> str:
    return " ".join(text.split())


def check_ownership_rule(text: str) -> list[str]:
    violations: list[str] = []
    norm = _norm(text)
    if "Brainstorm owns the interactive creative dialogue" not in text:
        violations.append("missing Brainstorm owns the interactive creative dialogue")
    if "synthesis" not in norm.lower() or "judgment" not in norm.lower():
        violations.append("missing synthesis/judgment in ownership")
    if "private concern model" not in norm.lower():
        violations.append("missing private concern model")
    if (
        "every operator-facing exchange" not in norm.lower()
        and "every operator exchange" not in norm.lower()
    ):
        violations.append("missing every operator-facing exchange")
    if "never delegated" not in norm.lower() and "are never delegated" not in norm.lower():
        violations.append("missing are never delegated")
    if "bounded read-only helper set" not in norm.lower():
        violations.append("missing bounded read-only helper set as only permitted delegation")
    return violations


def check_no_retired_filename(text: str) -> list[str]:
    violations: list[str] = []
    for needle in ("engine_offer", "engine_session_runner", "retired runner"):
        if needle in text:
            violations.append(f"retired filename still present: {needle!r}")
    return violations


def check_no_growing_blacklist(text: str) -> list[str]:
    violations: list[str] = []
    # The Dialogue ownership section should name no .py filenames at all
    try:
        section = text.split("## Dialogue ownership")[1].split("## ")[0]
    except IndexError:
        violations.append("cannot locate Dialogue ownership section")
        return violations
    if ".py" in section:
        violations.append("Dialogue ownership section names a .py file (growing blacklist)")
    return violations


def test_ownership_rule_positive() -> None:
    text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
    assert check_ownership_rule(text) == [], f"ownership: {check_ownership_rule(text)}"
    mutated = text.replace("Brainstorm owns the interactive creative dialogue", "")
    assert check_ownership_rule(mutated) != []


def test_no_retired_filename_negative() -> None:
    text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
    assert check_no_retired_filename(text) == [], f"retired: {check_no_retired_filename(text)}"
    mutated = text + "\nengine_offer.py\n"
    assert check_no_retired_filename(mutated) != []


def test_no_growing_blacklist_negative() -> None:
    text = BRAINSTORM_SKILL.read_text(encoding="utf-8")
    assert check_no_growing_blacklist(text) == [], f"blacklist: {check_no_growing_blacklist(text)}"
    mutated = text.replace("## Dialogue ownership", "## Dialogue ownership\nDo not run foo.py\n")
    assert check_no_growing_blacklist(mutated) != []


def test_routing_contract_intact_integration() -> None:
    # Orchestrate's plan_units still refuses a unit naming a retired transport
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_orchestrate_review_transport.py::test_review_transport_refuses_every_retired_transport_name",
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
