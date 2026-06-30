"""
Tests for the Spore PreCompact/SessionStart seam boundary (R13).

This module drives BOTH hooks out-of-process against real git repos and real
saga states to prove the components-present != end-to-end guard. It creates
real git repos, uses the real `saga.save` and `outcome_store`, invokes the
hooks via subprocess (matching production invocation), and verifies the spore file
is created, consumed, and deleted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
PRECOMPACT_HOOK = ROOT / "plugins" / "saga" / "hooks" / "precompact_spore_hook.py"
SESSIONSTART_HOOK = ROOT / "plugins" / "saga" / "hooks" / "compact_spore_session_hook.py"

# The scripts dir must be on sys.path before importing the sibling saga modules (by-path, not a package).
sys.path.insert(0, str(SAGA_SCRIPTS))
import outcome  # noqa: E402
import outcome_spec  # noqa: E402
import outcome_store  # noqa: E402
import saga  # noqa: E402
import saga_spore  # noqa: E402


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env_args = [
        "git",
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "-c",
        "commit.gpgsign=false",
        *args,
    ]
    return subprocess.run(env_args, cwd=str(cwd), check=True, capture_output=True, text=True)


def _run_hook(
    hook_script: Path, cwd: Path, payload: dict | bytes
) -> subprocess.CompletedProcess[bytes]:
    payload_bytes = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
    return subprocess.run(
        [sys.executable, str(hook_script)],
        input=payload_bytes,
        cwd=str(cwd),
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo_path)
    return repo_path


def _common_dir(repo: Path) -> Path:
    d = Path(_git("rev-parse", "--git-common-dir", cwd=repo).stdout.strip())
    if not d.is_absolute():
        d = repo / d
    return d


def test_seam_happy_path_single_saga(repo: Path) -> None:
    """1. SEAM HAPPY PATH (single saga, no outcome)."""
    session_id = "sess-happy-1"
    saga_id = "test-saga-happy"

    s = saga.Saga(
        saga_id=saga_id,
        kind="task",
        id="t",
        lifecycle_phase="work",
        phase_status="in_progress",
        status="active",
        next_step="do U2",
    )
    saga.save(repo, s)
    (repo / saga.STATE_DIR / "state.json").write_text(json.dumps({"active_saga_id": saga_id}))

    # Run PreCompact
    payload_precompact = {"session_id": session_id, "cwd": str(repo), "trigger": "auto"}
    res_precompact = _run_hook(PRECOMPACT_HOOK, repo, payload_precompact)
    assert res_precompact.returncode == 0

    common = _common_dir(repo)
    spore_file = common / "saga-spores" / f"{session_id}.json"
    assert spore_file.exists()

    # Run SessionStart
    payload_session = {"session_id": session_id, "cwd": str(repo), "source": "compact"}
    res_session = _run_hook(SESSIONSTART_HOOK, repo, payload_session)
    assert res_session.returncode == 0

    stdout = res_session.stdout.decode("utf-8")
    assert stdout.strip() != ""
    out_payload = json.loads(stdout)
    ctx = out_payload["hookSpecificOutput"]["additionalContext"]

    assert "AUTHORITATIVE" in ctx
    assert saga_id in ctx
    assert "do U2" in ctx

    # Assert spore file is GONE afterward
    assert not spore_file.exists()


def test_seam_campaign_small_outcome(repo: Path) -> None:
    """2. SEAM CAMPAIGN (real small 3-node outcome + leaf saga)."""
    session_id = "sess-campaign-1"

    spec = outcome_spec.OutcomeSpec.from_dict(
        {
            "outcome_id": "ship-auth",
            "objective": "Ship auth",
            "nodes": [
                {"subplot_id": "U1", "title": "u1", "kind": "code"},
                {"subplot_id": "U2", "title": "u2", "kind": "code", "depends_on": ["U1"]},
                {"subplot_id": "U3", "title": "u3", "kind": "code", "depends_on": ["U1"]},
            ],
        }
    )
    outcome.save_spec(repo, spec)
    store = outcome._store(repo, "ship-auth")
    store.ensure()
    outcome_store.write_completion_event(
        store, outcome_store.CompletionEvent(subplot_id="U1", state="done", idempotency_key="k:U1")
    )

    saga_id = "leaf-ship-auth-U2"
    s = saga.Saga(
        saga_id=saga_id,
        kind="task",
        id="t",
        lifecycle_phase="work",
        phase_status="in_progress",
        status="active",
        next_step="u2 work",
    )
    saga.save(repo, s)
    (repo / saga.STATE_DIR / "state.json").write_text(json.dumps({"active_saga_id": saga_id}))

    # PreCompact
    res_pre = _run_hook(
        PRECOMPACT_HOOK, repo, {"session_id": session_id, "cwd": str(repo), "trigger": "auto"}
    )
    assert res_pre.returncode == 0

    # SessionStart
    res_sess = _run_hook(
        SESSIONSTART_HOOK, repo, {"session_id": session_id, "cwd": str(repo), "source": "compact"}
    )
    assert res_sess.returncode == 0

    stdout = res_sess.stdout.decode("utf-8")
    out_payload = json.loads(stdout)
    ctx = out_payload["hookSpecificOutput"]["additionalContext"]

    assert "READY FRONTIER" in ctx
    assert "U2" in ctx
    assert "U3" in ctx

    common = _common_dir(repo)
    spore_file = common / "saga-spores" / f"{session_id}.json"
    assert not spore_file.exists()


def test_over_budget_spore(repo: Path) -> None:
    """3. OVER-BUDGET (R5/AE2) - synthetic over-budget spore."""
    session_id = "sess-overbudget"
    common = _common_dir(repo)

    # Write a synthetic spore directly
    leaves: dict[str, dict[str, Any]] = {}
    for i in range(5):
        leaves[f"R{i}"] = {"state": "ready"}
    for i in range(1000):
        leaves[f"D{i}"] = {"state": "done"}

    frontier = [f"R{i}" for i in range(5)]

    spore = {
        "provenance": {
            "session_id": session_id,
            "repo_root": str(repo),
            "saga_id": "leaf-test-R0",
            "generated_at": "2026-06-30T10:00:00Z",
        },
        "saga_box": {
            "saga_id": "leaf-test-R0",
            "lifecycle_phase": "work",
            "phase_status": "in_progress",
            "status": "active",
            "next_step": "test over budget",
        },
        "dag": {"outcome_id": "test", "objective": "test", "frontier": frontier, "leaves": leaves},
        "pointers": {},
    }

    spore_path = saga_spore.spore_path(common, session_id)
    spore_path.parent.mkdir(parents=True, exist_ok=True)
    spore_path.write_text(saga_spore.dump(spore), encoding="utf-8")

    # SessionStart ONLY
    res = _run_hook(
        SESSIONSTART_HOOK, repo, {"session_id": session_id, "cwd": str(repo), "source": "compact"}
    )
    assert res.returncode == 0

    stdout = res.stdout.decode("utf-8")
    out_payload = json.loads(stdout)
    ctx = out_payload["hookSpecificOutput"]["additionalContext"]

    # Assert size and contents
    assert len(ctx) <= 9000
    for i in range(5):
        assert f"R{i}" in ctx
    assert "more leaves — see" in ctx

    # Assert spore file is gone
    assert not spore_path.exists()


def test_mismatched_session(repo: Path) -> None:
    """4. MISMATCHED SESSION (R9/AE4)."""
    session_a = "sess-A"
    session_b = "sess-B"

    saga_id = "test-saga-mismatch"
    s = saga.Saga(
        saga_id=saga_id,
        kind="task",
        id="t",
        lifecycle_phase="work",
        phase_status="in_progress",
        status="active",
        next_step="test mismatch",
    )
    saga.save(repo, s)
    (repo / saga.STATE_DIR / "state.json").write_text(json.dumps({"active_saga_id": saga_id}))

    # PreCompact for session A
    res_pre = _run_hook(
        PRECOMPACT_HOOK, repo, {"session_id": session_a, "cwd": str(repo), "trigger": "auto"}
    )
    assert res_pre.returncode == 0

    common = _common_dir(repo)
    spore_a = common / "saga-spores" / f"{session_a}.json"
    assert spore_a.exists()

    # SessionStart for session B
    res_sess = _run_hook(
        SESSIONSTART_HOOK, repo, {"session_id": session_b, "cwd": str(repo), "source": "compact"}
    )
    assert res_sess.returncode == 0
    assert not res_sess.stdout.strip()

    # Session A spore is still present
    assert spore_a.exists()


def test_degrade_no_saga(repo: Path) -> None:
    """5. DEGRADE (R12/AE3) - repo with NO saga."""
    session_id = "sess-degrade"

    # PreCompact
    res_pre = _run_hook(
        PRECOMPACT_HOOK, repo, {"session_id": session_id, "cwd": str(repo), "trigger": "auto"}
    )
    assert res_pre.returncode == 0
    assert not res_pre.stdout.strip()

    common = _common_dir(repo)
    spore = common / "saga-spores" / f"{session_id}.json"
    assert not spore.exists()

    # SessionStart
    res_sess = _run_hook(
        SESSIONSTART_HOOK, repo, {"session_id": session_id, "cwd": str(repo), "source": "compact"}
    )
    assert res_sess.returncode == 0
    assert not res_sess.stdout.strip()


def test_worktree_storage_location(tmp_path: Path) -> None:
    """6. WORKTREE STORAGE LOCATION (KD3/AE6)."""
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=main_repo)
    # create a dummy commit to allow worktree add
    (main_repo / "dummy.txt").write_text("hello")
    _git("add", "dummy.txt", cwd=main_repo)
    _git("commit", "-q", "-m", "init", cwd=main_repo)

    wt_path = tmp_path / "wt"
    _git("worktree", "add", str(wt_path), "-b", "feat", cwd=main_repo)

    session_id = "sess-worktree"
    saga_id = "wt-saga"

    s = saga.Saga(
        saga_id=saga_id,
        kind="task",
        id="t",
        lifecycle_phase="work",
        phase_status="in_progress",
        status="active",
        next_step="worktree test",
    )
    saga.save(wt_path, s)
    (wt_path / saga.STATE_DIR / "state.json").write_text(json.dumps({"active_saga_id": saga_id}))

    # PreCompact
    res_pre = _run_hook(
        PRECOMPACT_HOOK, wt_path, {"session_id": session_id, "cwd": str(wt_path), "trigger": "auto"}
    )
    assert res_pre.returncode == 0

    main_common = _common_dir(main_repo)
    spore = main_common / "saga-spores" / f"{session_id}.json"
    assert spore.exists()

    # SessionStart
    res_sess = _run_hook(
        SESSIONSTART_HOOK,
        wt_path,
        {"session_id": session_id, "cwd": str(wt_path), "source": "compact"},
    )
    assert res_sess.returncode == 0

    stdout = res_sess.stdout.decode("utf-8")
    assert stdout.strip() != ""

    # Spore consumed
    assert not spore.exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
