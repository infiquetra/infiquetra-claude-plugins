"""Surviving-hook contracts for Saga after the lease retirement (#356, #677/U5).

The lease lifecycle hook and the saga broker wrapper are deleted by campaign #677 unit U5;
this module now pins what REMAINS: the team teardown hook still fires on its session seams,
and the hook manifest carries no lease registration — with the registrations that shared the
lease hook's matcher blocks still armed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SAGA = ROOT / "plugins" / "saga"
POLICY_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "concurrency_policy.py"
)
HOOKS_JSON = SAGA / "hooks" / "hooks.json"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


P = _load(POLICY_PATH, "saga_hook_policy_under_test")


def _environment(authority: Path, **overrides: str) -> dict[str, str]:
    result = dict(os.environ)
    result.update(
        {
            "INFIQUETRA_FLEET_STATE_DIR": str(authority),
            "INFIQUETRA_FLEET_SESSION_LIMIT": "3",
            "INFIQUETRA_FLEET_AGGREGATE_LIMIT": "7",
            "INFIQUETRA_FLEET_POLICY_SHA256": P.AdmissionLimits().policy_sha256(),
            "INFIQUETRA_FLEET_MUTATION": "read-write",
            "INFIQUETRA_FLEET_CLAIM_TTL_SECONDS": "30",
            "INFIQUETRA_FLEET_TTL_SECONDS": "300",
        }
    )
    result.update(overrides)
    return result


def _run_hook(
    path: Path,
    payload: dict[str, Any] | bytes,
    *,
    cwd: Path,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return _run_hook_text(path, encoded, cwd=cwd, environment=environment)


def _run_hook_text(
    path: Path, payload: bytes, *, cwd: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=cwd,
        env=environment,
        input=payload.decode("utf-8", errors="replace"),
        capture_output=True,
        check=False,
        text=True,
    )


def _commands(entries: list[dict[str, Any]], matcher: str | None = None) -> list[str]:
    result: list[str] = []
    for entry in entries:
        if matcher is not None and entry.get("matcher") != matcher:
            continue
        result.extend(hook["command"] for hook in entry.get("hooks", []))
    return result


# The three write-fence tests that lived here were removed with `lease_mutation_hook.py` (#671),
# and the lease lifecycle tests beside them were removed with `lease_lifecycle_hook.py`
# (#677/U5). The broker-level behavior they incidentally covered stays pinned directly:
# supersede-becomes-head at `test_fleet_lease_broker.py:862`
# (`test_retry_supersedes_at_full_capacity`) and the fence's own two branches at `:1958`/`:1990`
# — until campaign #677 unit U7 deletes that module too.


def test_hooks_json_retires_the_lease_lifecycle_hook_and_keeps_its_neighbours() -> None:
    """#677/U5: no lease registration survives anywhere in the manifest, and the hooks that
    shared the lease hook's matcher blocks are still armed — the guard against the manifest
    edit taking a neighbouring registration with it."""

    events = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    for event, entries in events.items():
        assert not any("lease_lifecycle_hook.py" in command for command in _commands(entries)), (
            f"lease lifecycle hook still registered on {event}"
        )

    # No mutation fence on the write path since #671; the lease lifecycle hook that shared its
    # kill switch is gone with #677/U5, and U7's re-add guard is the only path that could
    # restore either — see DECISIONS {#fence-carried-batch-renewal-671}.
    assert not any(
        "lease_mutation_hook.py" in command
        for matcher in (None, "Bash|Write|Edit|MultiEdit|NotebookEdit")
        for command in _commands(events["PreToolUse"], matcher)
    )

    # Surviving neighbours of the edited blocks:
    assert any(
        "team_spawn_residency_hook.py" in command
        for command in _commands(events["PreToolUse"], "Agent|Task")
    )
    assert any(
        "delegation_stop_audit_hook.py" in command for command in _commands(events["SubagentStop"])
    )
    assert any(
        "journal_nudge_hook.py" in command for command in _commands(events["PostToolUse"], "Bash")
    )

    # The two events whose ONLY registrant was the lease hook are gone entirely — an empty
    # event block would be a dead entry, not a retirement.
    assert "SubagentStart" not in events
    assert "PostToolUseFailure" not in events


# --------------------------------------------------------------- team teardown hook (#358)

TEAM_TEARDOWN_HOOK = SAGA / "hooks" / "team_teardown_hook.py"


def _teardown_modules() -> tuple[ModuleType, ModuleType]:
    scripts = SAGA / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    ledger_module = _load(scripts / "run_ledger.py", "run_ledger_for_teardown_hook_tests")
    teardown_module = _load(scripts / "team_teardown.py", "team_teardown_for_hook_tests")
    return ledger_module, teardown_module


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--quiet", str(repo)], check=True, capture_output=True, timeout=30
    )
    return repo


def test_session_end_records_request_only_for_this_sessions_open_runs(tmp_path: Path) -> None:
    ledger_module, teardown_module = _teardown_modules()
    repo = _git_repo(tmp_path)
    ledger = ledger_module.RunLedger.resolve(repo)
    teardown_module.open_run(
        ledger,
        subplot_id="hook-test",
        session_id="session-mine",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-mine",
    )
    teardown_module.open_run(
        ledger,
        subplot_id="hook-test",
        session_id="session-other",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-other",
    )

    result = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {"hook_event_name": "SessionEnd", "session_id": "session-mine", "cwd": str(repo)},
        cwd=repo,
        environment=_environment(tmp_path / "authority"),
    )
    assert result.returncode == 0
    assert "request evidence only" in result.stderr
    facts = ledger_module.read_facts(ledger)
    intents = {f["team_run_id"] for f in facts if f.get("event") == "teardown-intent"}
    assert intents == {"team-run-mine"}


def _seed_registry(repo: Path, outcome_id: str, subplot_id: str, path: Path) -> None:
    store_dir = repo / ".git" / "saga-outcomes" / outcome_id
    store_dir.mkdir(parents=True, exist_ok=True)
    registry = store_dir / "worktrees.json"
    data = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
    entries = data.get("worktrees", {})
    entries[subplot_id] = {"path": str(path), "outcome_id": outcome_id, "repo_root": str(repo)}
    registry.write_text(
        json.dumps({"worktrees": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_session_start_recovers_run_whose_worktrees_are_all_absent(tmp_path: Path) -> None:
    ledger_module, teardown_module = _teardown_modules()
    repo = _git_repo(tmp_path)
    ledger = ledger_module.RunLedger.resolve(repo)
    teardown_module.open_run(
        ledger,
        subplot_id="hook-test",
        session_id="session-crashed",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-crashed",
    )
    # The crashed run's worktree is registered but git no longer lists it — the
    # broker-free liveness signal recovery acts on (#677/U2).
    _seed_registry(
        repo,
        "hook-outcome",
        "crashed-sub",
        repo / ".saga-worktrees" / "hook-outcome" / "crashed-sub",
    )

    result = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {
            "hook_event_name": "SessionStart",
            "source": "startup",
            "session_id": "session-new",
            "cwd": str(repo),
        },
        cwd=repo,
        environment=_environment(tmp_path / "authority"),
    )
    assert result.returncode == 0
    facts = ledger_module.read_facts(ledger)
    events = {f["event"] for f in facts if f.get("team_run_id") == "team-run-crashed"}
    assert "teardown-complete" in events
    assert "recovery-observation" in events
    # Teardown removed nothing from disk: the registry entry is untouched evidence.
    assert (repo / ".git" / "saga-outcomes" / "hook-outcome" / "worktrees.json").exists()


def test_session_start_skips_runs_with_git_listed_worktrees(tmp_path: Path) -> None:
    ledger_module, teardown_module = _teardown_modules()
    repo = _git_repo(tmp_path)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "seed.txt"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=hook@test",
            "-c",
            "user.name=Hook",
            "commit",
            "-q",
            "-m",
            "seed",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    ledger = ledger_module.RunLedger.resolve(repo)
    teardown_module.open_run(
        ledger,
        subplot_id="hook-test",
        session_id="session-live",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-live",
    )
    live_path = repo / ".saga-worktrees" / "hook-outcome" / "live-sub"
    live_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--quiet", "--detach", str(live_path)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    _seed_registry(repo, "hook-outcome", "live-sub", live_path)

    result = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {
            "hook_event_name": "SessionStart",
            "source": "resume",
            "session_id": "session-new",
            "cwd": str(repo),
        },
        cwd=repo,
        environment=_environment(tmp_path / "authority"),
    )
    assert result.returncode == 0
    facts = ledger_module.read_facts(ledger)
    events = {f["event"] for f in facts if f.get("team_run_id") == "team-run-live"}
    assert "teardown-complete" not in events
    assert "recovery-observation" in events  # honesty: observed, nothing safe to reclaim
    assert live_path.exists()


def test_teardown_hook_is_visible_and_nonblocking_on_bad_input(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    malformed = _run_hook_text(
        TEAM_TEARDOWN_HOOK,
        b"not json at all",
        cwd=repo,
        environment=_environment(tmp_path / "authority"),
    )
    assert malformed.returncode == 0
    assert "malformed hook payload" in malformed.stderr

    plain_dir = tmp_path / "not-a-repo"
    plain_dir.mkdir()
    non_git = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {"hook_event_name": "SessionEnd", "session_id": "s", "cwd": str(plain_dir)},
        cwd=plain_dir,
        environment=_environment(tmp_path / "authority"),
    )
    assert non_git.returncode == 0
    assert "teardown-complete" not in non_git.stdout


def test_hooks_json_arms_bounded_teardown_recovery_seams() -> None:
    events = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    session_end = [
        hook
        for group in events["SessionEnd"]
        for hook in group["hooks"]
        if "team_teardown_hook.py" in hook["command"]
    ]
    assert session_end and session_end[0]["timeout"] == 5
    session_start = [
        hook
        for group in events["SessionStart"]
        if group.get("matcher") == "startup|resume"
        for hook in group["hooks"]
        if "team_teardown_hook.py" in hook["command"]
    ]
    assert session_start and session_start[0]["timeout"] == 15
