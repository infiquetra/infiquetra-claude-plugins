"""Local workflow contract/model checks; authoritative GitHub execution is separate."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
REQUIRED = ["tests", "validate", "lint", "type-check", "security", "release-surfaces"]
PINS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/setup-node": "49933ea5288caeca8642d1e84afbd3f7d6820020",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "astral-sh/setup-uv": "d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86",
    "softprops/action-gh-release": "de2c0eb89ae2a093876385947365aca7b0e5f844",
}


def test_mandatory_contexts_and_publish_dependencies_remain() -> None:
    jobs = WORKFLOW["jobs"]
    assert [jobs[name]["name"] for name in REQUIRED] == [
        "Tests (Python 3.12)",
        "Validate Plugins",
        "Lint",
        "Type Check",
        "Security Scan",
        "Release Surface Parity",
    ]
    assert jobs["publish"]["needs"] == REQUIRED
    assert jobs["publish"]["if"] == "startsWith(github.ref, 'refs/tags/')"
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))
    assert set(triggers) == {"push", "pull_request", "workflow_dispatch"}
    assert triggers["push"]["tags"] == ["v*.*.*", "plugins/*/v*.*.*"]


def test_validation_authority_and_pr_runner_isolation() -> None:
    assert WORKFLOW["permissions"] == {"contents": "read"}
    for name in REQUIRED:
        job = WORKFLOW["jobs"][name]
        assert "permissions" not in job
        assert (
            job["runs-on"]
            == "${{ github.event_name == 'pull_request' && 'ubuntu-latest' || fromJSON(vars.WORKFLOW_RUNNER_LABELS || '\"ubuntu-latest\"') }}"
        )
        assert "secrets." not in str(job)
    assert WORKFLOW["jobs"]["publish"]["permissions"] == {"contents": "write"}
    assert (
        WORKFLOW["jobs"]["publish"]["runs-on"]
        == "${{ fromJSON(vars.WORKFLOW_RUNNER_LABELS || '\"ubuntu-latest\"') }}"
    )


def test_all_ci_actions_use_reviewed_same_major_official_commits() -> None:
    actions = [
        step["uses"] for job in WORKFLOW["jobs"].values() for step in job["steps"] if "uses" in step
    ]
    assert set(actions) == {f"{name}@{sha}" for name, sha in PINS.items()}
    assert all(re.fullmatch(r"[^@]+@[a-f0-9]{40}", action) for action in actions)


def test_security_gate_and_diagnostics_are_enforceable() -> None:
    steps = WORKFLOW["jobs"]["security"]["steps"]
    scan = next(step for step in steps if step["name"] == "Run bandit security scan")
    assert scan["run"] == "uv run python scripts/bandit_gate.py"
    assert "continue-on-error" not in scan
    artifact = steps[-1]
    assert artifact["if"] == "always()"
    assert artifact["uses"].startswith("actions/upload-artifact@")
    assert set(artifact["with"]["path"].splitlines()) == {
        "bandit-report.json",
        "bandit.log",
        "bandit-gate.json",
    }
    assert artifact["with"]["if-no-files-found"] == "error"


def test_independent_validation_steps_still_run() -> None:
    jobs = WORKFLOW["jobs"]
    runs = "\n".join(step.get("run", "") for name in REQUIRED for step in jobs[name]["steps"])
    for command in (
        "python -m pytest -v --cov=plugins --cov-report=xml --cov-report=term-missing",
        "scripts/validate_plugins.py",
        "marketplace/validator/validate.py",
        "scripts/check_ownership_lanes.py --verbose",
        "tools/agent_spec.py --report",
        "plugins/mission-control/scripts/check_pagination.py",
        "plugins/mission-control/scripts/board_census.py --check",
        "scripts/sync_marketplace.py --check",
        "scripts/check_release_surface_parity.py",
        "scripts/changelog_heading_lint.py",
        "scripts/lint_test_shape.py tests plugins --prod-module server",
        "plugins/saga/scripts/lint_gate_absence_contract.py",
        "scripts/lint_journal_order.py",
        "scripts/check_mermaid.py",
        "mypy plugins/ scripts/ tests/ --ignore-missing-imports",
        "plugins/mission-control/config/generated/check_issue_contract_parity.py",
    ):
        assert command in runs
    assert runs.count("ruff check .") == 1
    assert "pytest tests/test_changelog_heading_lint.py" not in runs
    release = jobs["release-surfaces"]["steps"]
    assert release[0]["with"]["fetch-depth"] == 0
    guards = [step for step in release if "--base-ref" in step.get("run", "")]
    assert len(guards) == 2
    assert all(step["if"] == "github.event_name == 'pull_request'" for step in guards)


def _model_publish(ref: str, outcomes: dict[str, str], boundary: Mock) -> None:
    """Model GitHub's implicit success() and declared needs; never publish anything."""
    job = WORKFLOW["jobs"]["publish"]
    if ref.startswith("refs/tags/") and all(
        outcomes.get(name) == "success" for name in job["needs"]
    ):
        boundary()


@pytest.mark.parametrize("dependency", REQUIRED)
@pytest.mark.parametrize("outcome", ["failure", "cancelled", "skipped", "missing"])
@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
def test_local_publication_model_blocks_every_unsuccessful_dependency(
    dependency: str, outcome: str, event: str
) -> None:
    assert event in WORKFLOW.get("on", WORKFLOW.get(True))
    states = dict.fromkeys(REQUIRED, "success")
    if outcome == "missing":
        del states[dependency]
    else:
        states[dependency] = outcome
    boundary = Mock()
    _model_publish("refs/tags/plugins/saga/v1.2.1", states, boundary)
    boundary.assert_not_called()


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
@pytest.mark.parametrize("ref", ["refs/tags/v1.0.0", "refs/heads/main"])
def test_local_success_model_reaches_only_mock_tag_boundary(event: str, ref: str) -> None:
    assert event in WORKFLOW.get("on", WORKFLOW.get(True))
    boundary = Mock()
    _model_publish(ref, dict.fromkeys(REQUIRED, "success"), boundary)
    assert boundary.call_count == int(ref.startswith("refs/tags/"))


def test_local_gate_uses_the_same_blocking_scanner_and_retains_diagnostics() -> None:
    text = (ROOT / "scripts/gate.sh").read_text()
    assert 'step "Run bandit security scan" uv run python scripts/bandit_gate.py' in text
    assert 'advisory "Run bandit security scan"' not in text
    assert "for diagnostic in bandit-report.json bandit.log bandit-gate.json" in text
    assert 'cp "$diagnostic" "$LOG_DIR/$diagnostic"' in text
