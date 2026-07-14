"""End-to-end lifecycle regression harness on the fixture repo (#428).

Drives the canonical lifecycle scenario definitions under ``tests/lifecycle-fixture/scenarios/``
headlessly against throwaway clones of the fixture repo (see ``tests/lifecycle_harness.py``)
and asserts on artifact shape — plus the seeded-failure baseline controls proving every
"passed" verdict could actually have gone red.

NAMING CONSTRAINT (load-bearing): the issue's acceptance criterion counts collected node lines
containing the substring ``scenario``::

    uv run pytest tests/test_lifecycle_regression_harness.py --collect-only -q | grep -c scenario

must equal the number of scenario files (3-5). So exactly two test callables here carry that
substring — ``test_scenario`` (parametrized over every non-happy-path definition) and
``test_healthy_scenario_checks_all_four_artifact_families`` (the happy path) — and no other
test name or parameter id may contain it. ``test_collected_names_match_fixture_definitions``
enforces this mechanically.
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess  # nosec B404 — git CLI only, fixed argv, no shell
import sys
from pathlib import Path
from typing import Any

import lifecycle_harness as lh
import pytest
import yaml

HAPPY_PATH_ID = "spec-plan-work"
ALL_DEFINITION_IDS = sorted(p.stem for p in lh.list_scenarios())
NON_HAPPY_IDS = [sid for sid in ALL_DEFINITION_IDS if sid != HAPPY_PATH_ID]

WORKFLOW_PATH = lh.ROOT / ".github" / "workflows" / "lifecycle-regression.yml"
CI_PATH = lh.ROOT / ".github" / "workflows" / "ci.yml"


def _defn(
    steps: list[dict[str, Any]], assertions: list[dict[str, Any]], **over: Any
) -> dict[str, Any]:
    """A minimal inline definition that passes the same strict validation as file-backed ones."""
    base: dict[str, Any] = {
        "id": "inline",
        "title": "inline definition",
        "description": "constructed by a test",
        "steps": steps,
        "assertions": assertions,
    }
    base.update(over)
    return base


def _run_file(sid: str, tmp_path: Path) -> lh.ScenarioResult:
    workdir = lh.make_workdir(tmp_path)
    return lh.run_scenario_file(lh.SCENARIOS_DIR / f"{sid}.json", workdir)


# ---------------------------------------------------------------------------
# The canonical runs (healthy fixture repo -> no violations)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("definition_id", NON_HAPPY_IDS)
def test_scenario(definition_id: str, tmp_path: Path) -> None:
    """Each canonical definition runs green on a healthy fixture clone, independently (R2)."""
    result = _run_file(definition_id, tmp_path)
    assert result.violations == [], (
        f"{definition_id} reported violations on a healthy run: {result.violations}"
    )
    assert result.families_checked, f"{definition_id} checked no artifact-shape family"
    assert result.steps_run > 0


def test_healthy_scenario_checks_all_four_artifact_families(tmp_path: Path) -> None:
    """The happy path passes AND verifiably checked all four families (R3) — not a subset."""
    result = _run_file(HAPPY_PATH_ID, tmp_path)
    assert result.violations == [], f"healthy run reported violations: {result.violations}"
    missing = lh.CANONICAL_FAMILIES - result.families_checked
    assert not missing, f"healthy run skipped artifact-shape families: {sorted(missing)}"
    for family in sorted(lh.CANONICAL_FAMILIES):
        # Named in the output so a `-rP`/`-s` run shows exactly what was verified.
        print(f"artifact-shape family checked: {family}")


# ---------------------------------------------------------------------------
# Seeded-failure baseline controls (R4 + "a green that cannot go red is vacuous"):
# for every canonical family, a deliberately broken run must fail with the NAMED violation.
# ---------------------------------------------------------------------------


def test_seeded_failure_worktree_left_behind_is_named(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "worktree_open", "outcome_id": "fx-leak", "subplot_id": "sub-leak"}],
        assertions=[{"kind": "worktree_reclaimed"}],
    )
    result = lh.run_scenario(defn, workdir)
    assert result.violations, "a leaked worktree passed the reclamation assertion"
    assert any(lh.VIOLATION_WORKTREE in v for v in result.violations), result.violations
    assert any("sub-leak" in v for v in result.violations), (
        f"the leaked worktree path is not named: {result.violations}"
    )


def test_seeded_failure_missing_saga_entry_is_named(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "git", "args": ["status", "--porcelain"]}],  # no saga save ever runs
        assertions=[{"kind": "saga_log_appended", "saga_id": "issue-404", "min_ticks": 1}],
    )
    result = lh.run_scenario(defn, workdir)
    assert result.violations, "a saga with no ticks passed the append assertion"
    assert any(lh.VIOLATION_SAGA in v for v in result.violations), result.violations
    assert any("issue-404" in v for v in result.violations), result.violations


def test_seeded_failure_invalid_spec_json_is_named(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[
            {
                "kind": "write_file",
                "path": "docs/plans/broken-spec.json",
                "json": {"name": "broken", "description": "missing units", "repo": "."},
            }
        ],
        assertions=[{"kind": "execution_spec_valid", "path": "docs/plans/broken-spec.json"}],
    )
    result = lh.run_scenario(defn, workdir)
    assert result.violations, "an invalid execution spec passed validation"
    assert any(lh.VIOLATION_SPEC_INVALID in v for v in result.violations), result.violations
    # The production validator's own reason is carried through (e.g. the missing 'units' list).
    assert any("units" in v for v in result.violations), result.violations


def test_seeded_failure_missing_spec_file_is_named(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "git", "args": ["status", "--porcelain"]}],
        assertions=[{"kind": "execution_spec_valid", "path": "docs/plans/never-written.json"}],
    )
    result = lh.run_scenario(defn, workdir)
    assert any(lh.VIOLATION_SPEC_MISSING in v for v in result.violations), result.violations


def test_seeded_failure_missing_gate_record_is_named(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[
            {
                "kind": "run_saga_cli",
                "script": "saga",
                "args": [
                    "save",
                    "--id",
                    "103",
                    "--kind",
                    "issue",
                    "--lifecycle-phase",
                    "review",
                    "--summary",
                    "review tick with NO gate verdict",
                ],
            }
        ],
        assertions=[{"kind": "gate_record_present", "saga_id": "issue-103", "gate": "code-review"}],
    )
    result = lh.run_scenario(defn, workdir)
    assert result.violations, "a tick without a gate verdict passed the gate-record assertion"
    assert any(lh.VIOLATION_GATE in v for v in result.violations), result.violations
    assert any("code-review" in v for v in result.violations), result.violations


# ---------------------------------------------------------------------------
# Fail-closed: anything the harness cannot strictly understand is an ERROR, never a pass.
# ---------------------------------------------------------------------------


def test_fail_closed_unknown_step_kind(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "telepathy"}],
        assertions=[{"kind": "worktree_reclaimed"}],
    )
    with pytest.raises(lh.LifecycleHarnessError, match="unknown kind 'telepathy'"):
        lh.run_scenario(defn, workdir)


def test_fail_closed_unknown_assertion_kind(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "git", "args": ["status"]}],
        assertions=[{"kind": "vibes_check"}],
    )
    with pytest.raises(lh.LifecycleHarnessError, match="unknown kind 'vibes_check'"):
        lh.run_scenario(defn, workdir)


def test_fail_closed_unknown_top_level_key(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "git", "args": ["status"]}],
        assertions=[{"kind": "worktree_reclaimed"}],
        allow_failures=True,
    )
    with pytest.raises(lh.LifecycleHarnessError, match="unknown top-level keys"):
        lh.run_scenario(defn, workdir)


def test_fail_closed_unknown_step_key(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "git", "args": ["status"], "retries": 3}],
        assertions=[{"kind": "worktree_reclaimed"}],
    )
    with pytest.raises(lh.LifecycleHarnessError, match="unknown keys \\['retries'\\]"):
        lh.run_scenario(defn, workdir)


def test_fail_closed_malformed_definition_file(tmp_path: Path) -> None:
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(lh.LifecycleHarnessError, match="cannot parse"):
        lh.load_scenario(bad)


def test_fail_closed_id_must_match_file_stem(tmp_path: Path) -> None:
    mismatched = tmp_path / "other-name.json"
    mismatched.write_text(
        json.dumps(
            _defn(
                steps=[{"kind": "git", "args": ["status"]}],
                assertions=[{"kind": "worktree_reclaimed"}],
                id="not-other-name",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(lh.LifecycleHarnessError, match="file stem"):
        lh.load_scenario(mismatched)


def test_fail_closed_path_traversal_in_write_file(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "write_file", "path": "../escape.txt", "text": "nope"}],
        assertions=[{"kind": "worktree_reclaimed"}],
    )
    with pytest.raises(lh.LifecycleHarnessError, match="traversal-free"):
        lh.run_scenario(defn, workdir)


def test_fail_closed_cli_script_not_in_allowlist(tmp_path: Path) -> None:
    workdir = lh.make_workdir(tmp_path)
    defn = _defn(
        steps=[{"kind": "run_saga_cli", "script": "rm_rf", "args": ["boom"]}],
        assertions=[{"kind": "worktree_reclaimed"}],
    )
    with pytest.raises(lh.LifecycleHarnessError, match="unknown script 'rm_rf'"):
        lh.run_scenario(defn, workdir)


# ---------------------------------------------------------------------------
# Fixture-repo isolation (R1) + coverage-by-construction meta-checks (R5/R6)
# ---------------------------------------------------------------------------


def _git_out(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(  # nosec B603 — fixed argv, no shell
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout.strip()


def test_fixture_repo_is_a_real_isolated_git_repo() -> None:
    """R1: `tests/lifecycle-fixture` is its own git repo whose remote differs from the parent's."""
    lh.ensure_fixture_repo()
    assert _git_out(["rev-parse", "--is-inside-work-tree"], lh.FIXTURE_DIR) == "true"
    fixture_remote = _git_out(["remote", "get-url", "origin"], lh.FIXTURE_DIR)
    assert fixture_remote == lh.FIXTURE_REMOTE
    parent_remotes = _git_out(["remote", "-v"], lh.ROOT)
    assert lh.FIXTURE_REMOTE not in parent_remotes, (
        "the fixture repo's remote must differ from every parent-repo remote"
    )
    # The nested .git may never dirty the parent tree (git hardcodes .git path exclusion,
    # so this porcelain query — scoped to the nested .git — must always be empty).
    assert _git_out(["status", "--porcelain", "--", "tests/lifecycle-fixture/.git"], lh.ROOT) == ""


def test_throwaway_clone_never_reuses_the_parent_git_dir(tmp_path: Path) -> None:
    """Scenario runs happen in a self-contained clone: own .git, own remote, seed files present."""
    workdir = lh.make_workdir(tmp_path)
    assert (workdir / ".git").is_dir()
    assert _git_out(["remote", "get-url", "origin"], workdir) == lh.FIXTURE_REMOTE
    assert (workdir / "fixture_app.py").is_file()
    # git may print the common dir relative to the queried repo — resolve against the clone,
    # never the test process cwd (os.path.join ignores the base for an absolute answer).
    common_dir = _git_out(["rev-parse", "--git-common-dir"], workdir)
    assert Path(os.path.join(workdir, common_dir)).resolve() == (workdir / ".git").resolve()


def test_definition_count_is_canonical() -> None:
    """R2: at least 3 and at most 5 canonical definitions, happy path among them."""
    assert 3 <= len(ALL_DEFINITION_IDS) <= 5, ALL_DEFINITION_IDS
    assert HAPPY_PATH_ID in ALL_DEFINITION_IDS
    # Every file parses strictly at collection time (fail closed on drift in any definition).
    for path in lh.list_scenarios():
        lh.load_scenario(path)


def test_collected_names_match_fixture_definitions() -> None:
    """Coverage-by-construction + the acceptance grep-count invariant.

    Every definition file is exercised: the non-happy ones through ``test_scenario``'s
    parametrization (glob-driven, so a new file is picked up automatically) and the happy path
    through ``test_healthy_scenario_checks_all_four_artifact_families``. Exactly those two
    callables carry the ``scenario`` substring, so the collected-node grep count equals the
    definition-file count.
    """
    assert sorted([*NON_HAPPY_IDS, HAPPY_PATH_ID]) == ALL_DEFINITION_IDS
    module = sys.modules[__name__]
    named = sorted(
        name
        for name, obj in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("test_") and "scenario" in name
    )
    assert named == [
        "test_healthy_scenario_checks_all_four_artifact_families",
        "test_scenario",
    ], f"only the two canonical runners may carry the 'scenario' substring, found: {named}"
    assert not any("scenario" in sid for sid in ALL_DEFINITION_IDS), (
        "definition ids may not contain 'scenario' (it would skew the acceptance grep count)"
    )


def test_scheduled_workflow_is_separate_from_blocking_ci() -> None:
    """R5: the harness runs from its own cron-scheduled workflow, not a ci.yml job."""
    assert WORKFLOW_PATH.is_file(), f"missing scheduled workflow: {WORKFLOW_PATH}"
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    triggers = data.get("on") or data.get(True)  # yaml 1.1 parses the bare key `on` as True
    assert isinstance(triggers, dict) and "schedule" in triggers, (
        "lifecycle-regression.yml must be cron-scheduled"
    )
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "tests/test_lifecycle_regression_harness.py" in text, (
        "the scheduled workflow must invoke this harness"
    )
    ci_text = CI_PATH.read_text(encoding="utf-8")
    assert "lifecycle-regression" not in ci_text, (
        "the harness job must not live inside the PR-blocking ci.yml"
    )


def test_definitions_dir_has_no_strays() -> None:
    """Only .json definitions (and nothing else) live under scenarios/ — no dead weight."""
    entries = [p for p in lh.SCENARIOS_DIR.iterdir() if p.name != ".DS_Store"]
    assert all(p.suffix == ".json" and p.is_file() for p in entries), sorted(
        str(p) for p in entries
    )


def test_seed_dir_is_present_and_git_free() -> None:
    """The seed tree carries no .git of its own — repo-ness is minted per clone."""
    assert (lh.SEED_DIR / "fixture_app.py").is_file()
    assert not (lh.SEED_DIR / ".git").exists()
    assert shutil.which("git"), "harness requires git on PATH"
