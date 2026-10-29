"""Current lifecycle CLI artifact regressions; see lifecycle-fixture/README.md.

Every producer/reader runs in a fresh Python process against a private Git repository.
No production functions are mocked, no agents are launched, and no remote is contacted.
The supplied plan/review inputs are deterministic fixtures, not generated agent output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/saga/scripts"
SEED = ROOT / "tests/lifecycle-fixture/seed"
PLAN = "docs/plans/feature.md"
SAGA_ID = "issue-101"


@dataclass
class FixtureRepo:
    root: Path
    env: dict[str, str]

    def run(self, argv: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            argv,
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert result.returncode == expected, (
            f"CLI {argv} exited {result.returncode}, expected {expected}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        return result

    def git(self, *args: str) -> str:
        return self.run(["git", *args]).stdout.strip()

    def cli(self, script: str, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        return self.run([sys.executable, str(SCRIPTS / script), *args], expected)

    def saga(self, *args: str) -> dict[str, Any]:
        payload: dict[str, Any] = json.loads(self.cli("saga.py", *args).stdout)
        assert isinstance(payload, dict), "saga CLI output is not a JSON object"
        return payload

    def save(self, *args: str) -> dict[str, Any]:
        return self.saga("save", "--kind", "issue", "--id", "101", *args)


@pytest.fixture
def repo(tmp_path: Path) -> FixtureRepo:
    root = tmp_path / "repo"
    shutil.copytree(SEED, root)
    home = tmp_path / "home"
    home.mkdir()
    # An allowlist avoids forwarding host credentials, plugin roots, or Git overrides.
    # Git config/hooks are isolated too; the fixture never shares the parent's Git dir.
    env = {
        "PATH": os.defpath,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / "config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C.UTF-8",
    }
    fixture = FixtureRepo(root, env)
    fixture.git("init", "-q", "--initial-branch=main")
    fixture.git("config", "user.name", "Lifecycle Fixture")
    fixture.git("config", "user.email", "fixture@example.invalid")
    fixture.git("config", "commit.gpgsign", "false")
    fixture.git("config", "core.hooksPath", os.devnull)
    (root / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    fixture.git("add", ".")
    fixture.git("commit", "-q", "-m", "test: seed lifecycle fixture")
    assert (root / fixture.git("rev-parse", "--git-common-dir")).resolve() == root / ".git"
    assert fixture.git("remote") == ""
    return fixture


def tick_artifact(repo: FixtureRepo, saved: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = Path(saved["envelope_path"])
    assert path.resolve().is_relative_to(repo.root), f"tick escaped fixture: {path}"
    assert path.is_file(), f"saga tick missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"tick frontmatter missing: {path}"
    # Preserve the engine's unquoted scalar text, including digit-only or zero-prefixed
    # Git SHAs. YAML's implicit numeric coercion would make this oracle flaky.
    fields = yaml.load(text.split("---", 2)[1], Loader=yaml.BaseLoader)  # nosec B506 - BaseLoader constructs inert strings/collections only; SHA text must survive.
    assert fields["schema_version"] == "1.0", f"tick schema invalid: {path}"
    assert fields["saga_id"] == SAGA_ID, f"tick identity invalid: {path}"
    return path, fields


def assert_gate(snapshot: dict[str, Any], reference: str) -> None:
    expected = f"code-review:done:{reference}"
    assert expected in snapshot["gate_verdicts"], f"code-review gate record missing: {reference}"


def seed_review(repo: FixtureRepo) -> tuple[Path, Path, dict[str, Any]]:
    """The admission record and lens verdict are inputs; the CLI owns their persistence."""
    store = repo.root / ".claude/saga/runs"
    store.mkdir(parents=True)
    (store / "issue-101.json").write_text(
        json.dumps(
            {
                "schema": "run_record.v1",
                "issue": 101,
                "repo": "fixture/lifecycle",
                "review_cycles": [],
                "next_step": "review fixture",
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "schema": "review_result.v2",
        "revision": repo.git("rev-parse", "HEAD"),
        "roster_hash": "sha256:fixture-roster",
        "outcome": "accepted",
        "cycle": 1,
        "loop": "code_review",
        "unit": "U1",
        "findings": [],
        "per_lens_results": [
            {
                "lens": "correctness",
                "strictness": "standard",
                "scorable": True,
                "dimension_scores": {"intent-behavior-completeness": 9},
                "threshold": {"derived_overall_minimum": 9},
            }
        ],
    }
    source = repo.root / "review-input.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    return store, source, payload


def test_scenario_plan_to_work_appends_immutable_ticks(repo: FixtureRepo) -> None:
    report = json.loads(repo.cli("plan_artifact_conformance.py", "docs/plans").stdout)
    assert report["exit"] == 0 and report["findings"] == [], "fixture plan failed conformance"
    plan = repo.save(
        "--lifecycle-phase",
        "plan",
        "--phase-status",
        "complete",
        "--plan-path",
        PLAN,
        "--destination",
        "pr",
        "--orchestration-mode",
        "inline",
        "--summary",
        "plan ready",
    )
    first_path, first = tick_artifact(repo, plan)
    first_bytes = first_path.read_bytes()
    assert first["lifecycle_phase"] == "plan" and first["phase_status"] == "complete"
    assert first["plan_path"] == PLAN
    repo.git("checkout", "-q", "-b", "work/fixture")
    app = repo.root / "fixture_app.py"
    app.write_text(
        app.read_text() + '\n\ndef farewell(name: str) -> str:\n    return f"goodbye, {name}"\n'
    )
    repo.git("add", "fixture_app.py")
    repo.git("commit", "-q", "-m", "feat: add fixture farewell")
    work = repo.save("--lifecycle-phase", "work", "--summary", "work recorded")
    second_path, second = tick_artifact(repo, work)
    assert first_path != second_path, "save overwrote a prior immutable tick"
    assert first_path.read_bytes() == first_bytes, "plan tick changed after work save"
    assert second["branch"] == "work/fixture"
    assert second["head_sha"] == repo.git("rev-parse", "--short", "HEAD")
    assert second["last_commit_sha"] == repo.git("rev-parse", "HEAD")
    assert second["head_sha"] != first["head_sha"], "work tick retained the plan revision"
    restored = repo.saga("restore", "--saga-id", SAGA_ID)
    assert restored["found"] is True
    assert restored["plan_path"] == PLAN and restored["lifecycle_phase"] == "work"
    ticks = repo.saga("ticks", "--saga-id", SAGA_ID)
    assert ticks["count"] == 2, "saga log did not append exactly one work tick"
    assert [tick["summary"] for tick in ticks["ticks"]] == ["plan ready", "work recorded"]
    index = json.loads(Path(work["state_path"]).read_text())
    assert index["active_saga_id"] == SAGA_ID
    assert index["current_work"]["plan_path"] == PLAN


def test_scenario_review_result_crosses_store_and_gate_boundaries(repo: FixtureRepo) -> None:
    repo.git("checkout", "-q", "-b", "review/fixture")
    app = repo.root / "fixture_app.py"
    app.write_text(app.read_text().replace('f"hello, {name}"', 'f"Hello, {name}"'))
    repo.git("add", "fixture_app.py")
    repo.git("commit", "-q", "-m", "feat: capitalize fixture greeting")
    store, source, payload = seed_review(repo)
    comment = repo.root / "review-comment.md"
    repo.cli(
        "review_result.py",
        "--result",
        str(source),
        "--issue",
        "101",
        "--store-root",
        str(store),
        "--render-comment",
        str(comment),
    )
    persisted = json.loads((store / "issue-101.json").read_text())
    reread = json.loads(repo.cli("run_record.py", "--store-root", str(store), "show", "101").stdout)
    assert reread == persisted, "run-record CLI did not read the persisted review"
    assert len(reread["review_cycles"]) == 1, "review result was not appended"
    review = reread["review_cycles"][0]
    for key in ("schema", "revision", "unit", "outcome", "cycle", "loop", "roster_hash"):
        assert review[key] == payload[key], f"persisted review lost {key}"
    assert review["per_lens_results"][0]["derived_overall"] == 9.0
    assert payload["revision"] in comment.read_text(), "comment lost reviewed revision"
    reference = ".claude/saga/runs/issue-101.json"
    saved = repo.save(
        "--lifecycle-phase",
        "review",
        "--review-paths",
        "review-comment.md",
        "--gate-verdict",
        f"code-review:done:{reference}",
    )
    _, fields = tick_artifact(repo, saved)
    assert_gate(fields, reference)
    restored = repo.saga("restore", "--saga-id", SAGA_ID)
    assert_gate(restored, reference)
    assert restored["review_paths"] == ["review-comment.md"]
    assert repo.git("rev-parse", "HEAD") == payload["revision"], "artifact writing moved HEAD"


def test_scenario_resume_reads_ticks_despite_corrupt_index(repo: FixtureRepo) -> None:
    saved = repo.save(
        "--lifecycle-phase", "work", "--status", "paused", "--next-step", "resume fixture work"
    )
    path, _ = tick_artifact(repo, saved)
    before = path.read_bytes()
    index = Path(saved["state_path"])
    index.write_text("{broken index", encoding="utf-8")
    restored = repo.saga("restore", "--saga-id", SAGA_ID)
    assert restored["found"] and restored["status"] == "paused"
    assert restored["next_step"] == "resume fixture work"
    scan = repo.saga("scan")
    assert scan["count"] == 1 and scan["candidates"][0]["saga_id"] == SAGA_ID
    resumed = repo.save("--status", "active", "--summary", "resumed")
    tick_artifact(repo, resumed)
    assert path.read_bytes() == before, "resume rewrote the paused tick"
    assert repo.saga("restore", "--saga-id", SAGA_ID)["status"] == "active"
    assert repo.saga("ticks", "--saga-id", SAGA_ID)["count"] == 2
    assert json.loads(index.read_text())["sagas"][SAGA_ID]["status"] == "active"


@pytest.mark.parametrize(
    ("old", "new", "kind", "detail"),
    [
        ("status: ready\n", "", "missing-required-field", "status"),
        ("### U1.", "### Unit one.", "marker-missing", "U1"),
    ],
)
def test_seeded_invalid_plan_fails_with_named_finding(
    repo: FixtureRepo,
    old: str,
    new: str,
    kind: str,
    detail: str,
) -> None:
    plan = repo.root / PLAN
    plan.write_text(plan.read_text().replace(old, new), encoding="utf-8")
    report = json.loads(repo.cli("plan_artifact_conformance.py", "docs/plans", expected=1).stdout)
    assert report["exit"] == 1
    assert any(
        row["path"] == "feature.md"
        and row["kind"] == kind
        and row["failing"]
        and detail in row["detail"]
        for row in report["findings"]
    )


def test_missing_plan_directory_is_an_error(repo: FixtureRepo) -> None:
    result = repo.cli("plan_artifact_conformance.py", "absent/plans", expected=2)
    assert "not a directory" in json.loads(result.stderr)["error"]


def test_seeded_missing_tick_is_detected(repo: FixtureRepo) -> None:
    saved = repo.save("--lifecycle-phase", "plan", "--plan-path", PLAN)
    path, _ = tick_artifact(repo, saved)
    path.unlink()
    with pytest.raises(AssertionError, match="saga tick missing"):
        tick_artifact(repo, saved)
    assert repo.saga("restore", "--saga-id", SAGA_ID)["found"] is False


def test_seeded_missing_gate_is_detected(repo: FixtureRepo) -> None:
    saved = repo.save("--lifecycle-phase", "review")
    _, fields = tick_artifact(repo, saved)
    with pytest.raises(AssertionError, match="code-review gate record missing"):
        assert_gate(fields, "review-comment.md")
    with pytest.raises(AssertionError, match="code-review gate record missing"):
        assert_gate(repo.saga("restore", "--saga-id", SAGA_ID), "review-comment.md")


@pytest.mark.parametrize(
    ("field", "value", "diagnostic"),
    [
        ("schema", "review_result.unknown", "unknown result schema"),
        ("revision", "HEAD", "not a full forty-character commit"),
    ],
)
def test_seeded_invalid_review_refuses_to_write(
    repo: FixtureRepo,
    field: str,
    value: str,
    diagnostic: str,
) -> None:
    store, source, payload = seed_review(repo)
    record = store / "issue-101.json"
    before = record.read_bytes()
    payload[field] = value
    source.write_text(json.dumps(payload), encoding="utf-8")
    comment = repo.root / "refused-comment.md"
    result = repo.cli(
        "review_result.py",
        "--result",
        str(source),
        "--issue",
        "101",
        "--store-root",
        str(store),
        "--render-comment",
        str(comment),
        expected=2,
    )
    assert diagnostic in result.stderr
    assert record.read_bytes() == before, "refused review mutated the run record"
    assert not comment.exists(), "refused review rendered a comment"


def test_scheduled_entrypoint_retains_context_and_reports() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/lifecycle-regression.yml").read_text())
    assert workflow["name"] == "Lifecycle Regression"
    triggers = workflow.get("on", workflow.get(True))  # PyYAML treats unquoted on as a boolean.
    assert triggers["schedule"] and "workflow_dispatch" in triggers
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["lifecycle-regression"]
    assert job["name"] == "Lifecycle Regression (fixture-repo scenarios)"
    assert 0 < job["timeout-minutes"] <= 10
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "tests/test_lifecycle_regression_harness.py" in runs
    assert "--no-cov" in runs and "--junitxml=lifecycle-regression-report.xml" in runs
    upload = next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "lifecycle-regression-report.xml"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["retention-days"] == 7


def test_base_loader_preserves_scalars_and_keeps_python_tags_inert(tmp_path: Path) -> None:
    path = tmp_path / "tick.md"
    path.write_text(
        "---\nschema_version: 1.0\nsaga_id: issue-101\nsha: 0000000000000000000000000000000000000123\nflag: yes\nvalue: !!python/object/apply:builtins.eval ['1 + 1']\n---\n"
    )
    _, fields = tick_artifact(FixtureRepo(tmp_path, {}), {"envelope_path": str(path)})
    assert fields["sha"] == "0000000000000000000000000000000000000123"
    assert fields["flag"] == "yes"
    assert fields["value"] == ["1 + 1"]
