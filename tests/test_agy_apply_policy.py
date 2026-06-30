"""Tests for U4 agy clone execution and apply policy."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
WRAPPER = ROOT / "plugins" / "agy" / "scripts" / "agy_delegate.py"
FAKE_AGY = ROOT / "tests" / "fixtures" / "agy" / "fake_agy.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    (repo / "allowed.txt").write_text("before\n", encoding="utf-8")
    _git(repo, "add", "README.md", "allowed.txt")
    _git(repo, "commit", "-m", "initial")
    return repo


def _payload(task: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "agy.delegation.v1",
        "role": "coder",
        "mode": "patch-only",
        "task": task,
        "model": "flash",
        "review_lens": None,
        "write_set": ["allowed.txt"],
        "apply_policy": "preserve-patch",
        "evidence": "summary",
        "verification": {
            "commands": [],
            "required": False,
            "run_scope": "clone",
        },
        "timeout_seconds": 5,
        "no_output_seconds": 3,
        "provenance_required": True,
    }
    payload.update(overrides)
    return payload


def _run_wrapper(
    tmp_path: Path,
    repo: Path,
    payload: dict[str, object],
    run_id: str,
) -> subprocess.CompletedProcess[str]:
    envelope_dir = tmp_path / "envelopes"
    envelope_dir.mkdir(exist_ok=True)
    envelope_path = envelope_dir / f"{run_id}.json"
    envelope_path.write_text(json.dumps(payload), encoding="utf-8")

    return subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            str(repo),
            "--run-id",
            run_id,
            "--envelope",
            str(envelope_path),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _bundle(repo: Path, run_id: str) -> Path:
    return repo / ".claude" / "agy" / "runs" / run_id


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_patch_only_preserves_clone_patch_without_live_mutation(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload("FAKE_AGY_WRITE allowed.txt::after\n"),
        "patch-only-run",
    )
    bundle = _bundle(repo, "patch-only-run")

    assert completed.returncode == 0
    assert _json(bundle / "result.json")["status"] == "patch_ready"
    assert _json(bundle / "run-lease.json")["real_agy_verdict"] == "real"
    assert _json(bundle / "changed-paths.json")["changed_paths"] == ["allowed.txt"]
    assert "after" in (bundle / "diff.patch").read_text(encoding="utf-8")
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"

    proof = _json(bundle / "git-proof.json")
    assert proof["base_sha"] == _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert proof["clone_path"] == str(bundle / "worktree")
    assert proof["removed_remotes"] == ["origin"]
    assert proof["clone_remotes_after"] == []
    assert proof["rogue_commits"] == []
    assert proof["clone_post_status"]["entries"]
    assert _git(bundle / "worktree", "remote").stdout == ""


def test_relative_repo_root_does_not_make_bundle_logs_clone_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    envelope_path = tmp_path / "relative-envelope.json"
    envelope_path.write_text(json.dumps(_payload("FAKE_AGY_MODE=success")), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(WRAPPER),
            "--repo-root",
            repo.name,
            "--run-id",
            "relative-root-run",
            "--envelope",
            str(envelope_path),
            "--launch-agy",
            "--agy-bin",
            str(FAKE_AGY),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    bundle = _bundle(repo, "relative-root-run")

    assert completed.returncode == 0
    assert _json(bundle / "result.json")["status"] == "success"
    assert _json(bundle / "changed-paths.json")["changed_paths"] == []
    assert (bundle / "agy.log").exists()
    assert (bundle / "diff.patch").read_text(encoding="utf-8") == ""


def test_auto_if_clean_applies_in_scope_patch_after_required_checks(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["test \"$(cat allowed.txt)\" = after"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "apply-run",
    )
    bundle = _bundle(repo, "apply-run")
    proof = _json(bundle / "git-proof.json")

    assert completed.returncode == 0
    assert _json(bundle / "result.json")["status"] == "applied"
    assert _json(bundle / "run-lease.json")["real_agy_verdict"] == "real"
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "after"
    assert proof["post_apply"]["live_changed_paths"] == ["allowed.txt"]
    assert proof["post_apply"]["only_expected_changes"] is True
    assert _json(bundle / "checks.json")["passed"] is True


def test_patch_only_with_explicit_write_set_flags_out_of_scope_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload("FAKE_AGY_WRITE outside.txt::oops\n"),
        "patch-out-of-scope-run",
    )
    bundle = _bundle(repo, "patch-out-of-scope-run")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "out_of_scope_mutation"
    assert _json(bundle / "checks.json")["out_of_scope_paths"] == ["outside.txt"]
    assert not (repo / "outside.txt").exists()


def test_no_write_clone_mutation_is_not_successful_patch_ready(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            role="reviewer",
            mode="no-write",
            write_set=[],
        ),
        "no-write-mutated-run",
    )
    bundle = _bundle(repo, "no-write-mutated-run")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "out_of_scope_mutation"
    assert _json(bundle / "checks.json")["out_of_scope_paths"] == ["allowed.txt"]
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"


def test_auto_if_clean_refuses_out_of_scope_clone_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE outside.txt::oops\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["true"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "out-of-scope-run",
    )
    bundle = _bundle(repo, "out-of-scope-run")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "out_of_scope_mutation"
    assert not (repo / "outside.txt").exists()
    assert _json(bundle / "checks.json")["out_of_scope_paths"] == ["outside.txt"]


def test_auto_if_clean_refuses_when_required_verification_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["exit 9"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "checks-failed-run",
    )
    bundle = _bundle(repo, "checks-failed-run")
    checks = _json(bundle / "checks.json")

    assert completed.returncode == 1
    assert _json(bundle / "result.json")["status"] == "checks_failed"
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"
    assert checks["passed"] is False
    assert checks["commands"][0]["return_code"] == 9


def test_auto_if_clean_dirty_live_repo_refuses_before_launch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")

    completed = _run_wrapper(
        tmp_path,
        repo,
        _payload(
            "FAKE_AGY_WRITE allowed.txt::after\n",
            mode="auto-if-clean",
            apply_policy="apply-if-clean",
            verification={
                "commands": ["true"],
                "required": True,
                "run_scope": "clone",
            },
        ),
        "dirty-run",
    )
    bundle = _bundle(repo, "dirty-run")
    result = _json(bundle / "result.json")
    proof = _json(bundle / "git-proof.json")

    assert completed.returncode == 1
    assert result["status"] == "checks_failed"
    assert result["agy_launched"] is False
    assert not (bundle / "worktree").exists()
    assert (repo / "allowed.txt").read_text(encoding="utf-8") == "before\n"
    assert proof["live_preflight"]["clean"] is False
    assert proof["live_preflight"]["changed_paths"] == ["README.md"]
