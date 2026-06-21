"""
Tests for the stale-main SessionStart wrapper hook.

The wrapper (`plugins/saga/hooks/stale_main_session_hook.py`) runs the repo's
own `tools/stale_main_guard.py` at session start and injects its output as
SessionStart `additionalContext` — but ONLY when that guard tool is present at
the CWD repo root (the repo-presence guard that keeps the distributed saga
plugin inert in any other repo).

These tests drive the hook as a real subprocess with stdin set to a SessionStart
payload. They build a throwaway git repo under `tmp_path` and drop in a FAKE
guard tool (a tiny script whose stdout/stderr we control) so the wrapper's
behaviour is exercised end-to-end WITHOUT any real `git fetch` — the fake guard
never touches the network. No state lands under the repo-root `.claude/`.

Cases:
  (a) git repo WITHOUT tools/stale_main_guard.py -> exit 0, guard NOT invoked,
      no output.
  (b) not a git repo (rev-parse fails) -> exit 0, silent.
  (c) git repo WITH the guard, guard prints a stale warning -> exit 0 and the
      warning reaches stdout inside the additionalContext shape.
  (d) git repo WITH the guard, guard silent (exit 0, no output) -> exit 0,
      wrapper prints nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HOOK_SCRIPT = ROOT / "plugins" / "saga" / "hooks" / "stale_main_session_hook.py"

# A guard that, when invoked, proves it ran by writing a sentinel file. Used to
# assert the guard is NOT invoked when the repo-presence check should fail.
_SENTINEL_GUARD = """\
import sys
from pathlib import Path
Path(sys.argv[0]).parent.parent.joinpath("GUARD_RAN").write_text("ran")
print("[stale-main-guard] WARNING: local 'main' is 2 commit(s) behind", file=sys.stderr)
"""

# A guard that prints a stale warning to stderr (the real guard writes to stderr).
_WARNING_GUARD = """\
import sys
print("[stale-main-guard] WARNING: local 'main' is 3 commit(s) behind origin/main.", file=sys.stderr)
"""

# A guard that is silent (up to date) — exit 0, no output on either stream.
_SILENT_GUARD = """\
import sys
sys.exit(0)
"""


def _init_git_repo(path: Path) -> None:
    """Initialise a minimal git repo at ``path`` (no remote, no network)."""
    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_guard(repo: Path, body: str) -> None:
    """Drop a fake guard tool at ``<repo>/tools/stale_main_guard.py``."""
    tools = repo / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "stale_main_guard.py").write_text(body, encoding="utf-8")


def _run_hook(cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the wrapper hook from ``cwd`` with a SessionStart payload on stdin."""
    payload = {
        "session_id": "test-session",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": str(cwd),
        "hook_event_name": "SessionStart",
        "source": "startup",
    }
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_repo_without_guard_tool_stays_inert(tmp_path: Path) -> None:
    """(a) git repo lacking tools/stale_main_guard.py -> exit 0, guard not run, no output."""
    repo = tmp_path / "other-repo"
    repo.mkdir()
    _init_git_repo(repo)
    # Drop a sentinel guard in the WRONG place so we can prove it is never run.
    # (The presence check looks for tools/stale_main_guard.py at the repo root;
    # here we deliberately do NOT create it.)

    result = _run_hook(repo)

    assert result.returncode == 0
    assert result.stdout.strip() == ""
    # No guard tool present, so nothing under the repo could have been invoked.
    assert not (repo / "GUARD_RAN").exists()


def test_not_a_git_repo_is_silent(tmp_path: Path) -> None:
    """(b) not a git repo (rev-parse fails) -> exit 0, silent."""
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    # Even if a guard tool exists, a non-repo cwd must short-circuit BEFORE it.
    _write_guard(not_a_repo, _SENTINEL_GUARD)

    result = _run_hook(not_a_repo)

    assert result.returncode == 0
    assert result.stdout.strip() == ""
    # The repo-presence path is gated on rev-parse succeeding; guard never runs.
    assert not (not_a_repo / "GUARD_RAN").exists()


def test_guard_present_and_stale_emits_additional_context(tmp_path: Path) -> None:
    """(c) guard present + prints a stale warning -> exit 0, warning in additionalContext."""
    repo = tmp_path / "this-repo"
    repo.mkdir()
    _init_git_repo(repo)
    _write_guard(repo, _WARNING_GUARD)

    result = _run_hook(repo)

    assert result.returncode == 0
    assert result.stdout.strip() != ""
    parsed = json.loads(result.stdout)
    hso = parsed["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "3 commit(s) behind" in hso["additionalContext"]
    assert "stale-main-guard" in hso["additionalContext"]


def test_guard_present_and_silent_prints_nothing(tmp_path: Path) -> None:
    """(d) guard present but silent (exit 0, no output) -> exit 0, wrapper prints nothing."""
    repo = tmp_path / "this-repo-fresh"
    repo.mkdir()
    _init_git_repo(repo)
    _write_guard(repo, _SILENT_GUARD)

    result = _run_hook(repo)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_hook_script_exists() -> None:
    """Sanity: the wrapper hook script is present at the wired path."""
    assert HOOK_SCRIPT.is_file()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
