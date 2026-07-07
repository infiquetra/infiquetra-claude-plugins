"""Lifecycle tests for the codex delegate (R7): terminal bundles, whole-tree kill, live smoke.

Proves the R7 lifecycle guarantee of ``plugins/codex/scripts/codex_delegate.py``:

* A completed run's bundle is terminal and self-contained — a launcher process that exits
  immediately after the delegate returns leaves no live children and no non-terminal state.
* A fake codex that sleeps past ``--timeout-seconds`` gets its WHOLE process tree killed within
  the grace window (the fake bin's own child pid is polled directly), with a terminal timeout
  status and no ``running`` string anywhere in the bundle's state files.
* A delegate killed mid-run (SIGTERM, mirroring a caller's Bash-tool timeout) leaves a dead
  process tree and a diagnosable terminal bundle — never a ``running`` record.

Every red condition is hermetic: fake codex binaries, no network. The one live conformance
smoke is availability-gated on ``codex login status`` exiting 0 and SKIPS (never fails) when
codex is absent or unauthenticated — mirroring the Ollama Cloud smoke posture in
``tests/test_engine_bridge_http.py``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "codex" / "scripts" / "codex_delegate.py"

# Grace window (seconds) within which the whole codex process tree must be dead after the
# delegate reports a terminal status. _kill_process_tree escalates SIGTERM→SIGKILL with 2s
# waits, so 5s is generous without masking a leak.
GRACE_WINDOW_SECONDS = 5.0


def _load_module():
    scripts_dir = MODULE_PATH.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("codex_delegate_lifecycle_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


codex_delegate = _load_module()


# --- process-tree helpers ------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    """True while ``pid`` exists (zombies count as gone once reaped by their parent)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - pid reused by another uid; treat as alive
        return True
    # The pid exists — but a zombie child of a *dead* parent gets reaped by init/launchd, and a
    # zombie whose parent is us shows up in wait(); either way, `ps` distinguishes it.
    try:
        out = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover - ps unavailable
        return True
    if not out:
        return False
    return not out.startswith("Z")


def _wait_dead(pid: int, *, window: float = GRACE_WINDOW_SECONDS) -> bool:
    deadline = time.monotonic() + window
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def _read_pidfile(pidfile: Path, *, timeout: float = 15.0) -> tuple[int, int]:
    """Wait for the fake bin's pidfile and return (child_pid, fake_bin_pid)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pidfile.exists():
            lines = pidfile.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2:
                return int(lines[0]), int(lines[1])
        time.sleep(0.05)
    raise AssertionError(f"fake codex never wrote its pidfile at {pidfile}")


def _assert_no_running_in_state_files(bundle: Path) -> None:
    """No state file in the bundle may carry the string ``running`` (R4/R7)."""
    state_files = sorted(bundle.glob("*.json")) + [bundle / "projection.md"]
    for state_file in state_files:
        if not state_file.exists():
            continue
        content = state_file.read_text(encoding="utf-8")
        assert "running" not in content, f"non-terminal 'running' found in {state_file.name}"


# --- fake codex binaries (hermetic, no network) ---------------------------------------------------


def _write_shim(tmp_path: Path, body: str) -> Path:
    """Write an executable python fake codex plus a /bin/sh shim usable as --codex-bin."""
    bin_path = tmp_path / "fake-codex.py"
    bin_path.write_text(body, encoding="utf-8")
    bin_path.chmod(0o755)
    shim = tmp_path / "codex-shim"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bin_path}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return shim


def _tree_sleep_body(pidfile: Path, sleep_seconds: int = 300) -> str:
    """A fake codex that spawns its OWN child, records both pids, then sleeps far past timeout.

    The child inherits the fake bin's process group (the delegate started the fake in a new
    session), so a correct whole-tree kill takes it down; a broken direct-child-only kill
    leaves it alive — that asymmetry is what the timeout test polls for.
    """
    return f"""#!/usr/bin/env python3
import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep({sleep_seconds})"])
tmp = {str(pidfile)!r} + ".tmp"
with open(tmp, "w") as fh:
    fh.write(str(child.pid) + "\\n" + str(os.getpid()) + "\\n")
os.rename(tmp, {str(pidfile)!r})
sys.stdin.read()
print('{{"type": "session_start"}}', flush=True)
time.sleep({sleep_seconds})
print('{{"type": "done"}}', flush=True)
"""


def _well_behaved_body(pidfile: Path) -> str:
    """A fake codex whose child completes before it exits — a clean, terminal run."""
    return f"""#!/usr/bin/env python3
import json, os, subprocess, sys
argv = sys.argv[1:]
out_path = None
for i, tok in enumerate(argv):
    if tok == "-o":
        out_path = argv[i + 1]
child = subprocess.Popen([sys.executable, "-c", "pass"])
tmp = {str(pidfile)!r} + ".tmp"
with open(tmp, "w") as fh:
    fh.write(str(child.pid) + "\\n" + str(os.getpid()) + "\\n")
os.rename(tmp, {str(pidfile)!r})
child.wait()
piped = sys.stdin.read()
print(json.dumps({{"type": "session_start"}}))
print(json.dumps({{"type": "stdin_echo", "bytes": len(piped)}}))
sys.stdout.flush()
if out_path:
    with open(out_path, "w") as fh:
        fh.write("lifecycle final message")
sys.exit(0)
"""


def _delegate_argv(*, repo_root: Path, run_id: str, shim: Path, timeout_seconds: int) -> list[str]:
    return [
        sys.executable,
        str(MODULE_PATH),
        "--role",
        "reviewer",
        "--task",
        "Lifecycle probe task.",
        "--timeout-seconds",
        str(timeout_seconds),
        "--no-output-seconds",
        str(timeout_seconds),
        "--repo-root",
        str(repo_root),
        "--run-id",
        run_id,
        "--codex-bin",
        str(shim),
    ]


# --- (a) completed run: terminal, self-contained, launcher exit leaves nothing alive -------------


def test_completed_run_bundle_is_terminal_and_launcher_exit_leaves_no_children(tmp_path) -> None:
    """A launcher that exits immediately after the delegate returns leaves no live children.

    The delegate is synchronous: when its process exits, the whole delegation is over. The fake
    codex records its own pid and its child's pid; both must be dead the moment the delegate
    process has exited, and the bundle on disk must be terminal and self-contained.
    """
    pidfile = tmp_path / "pids.txt"
    shim = _write_shim(tmp_path, _well_behaved_body(pidfile))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # The "launcher" is this Popen: it waits for the delegate and then does nothing else.
    launcher = subprocess.Popen(
        _delegate_argv(repo_root=repo_root, run_id="completed-run", shim=shim, timeout_seconds=60),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = launcher.communicate(timeout=60)
    assert launcher.returncode == 0, stderr.decode()

    child_pid, fake_pid = _read_pidfile(pidfile, timeout=1)
    # Delegate already returned — the tree must ALREADY be gone, no grace needed.
    assert not _pid_alive(fake_pid), "fake codex outlived the delegate"
    assert _wait_dead(child_pid, window=1.0), "fake codex's child outlived the delegate"

    bundle = repo_root / ".claude" / "codex" / "runs" / "completed-run"
    payload = json.loads((bundle / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["codex_launched"] is True
    assert payload["return_code"] == 0
    assert payload["receipt_emitted"] is True
    # Self-contained: every evidence surface present without any live process behind it.
    for name in (
        "envelope.json",
        "prompt.txt",
        "command.json",
        "transcript.jsonl",
        "last-message.txt",
        "result.json",
        "projection.md",
        "bridge-receipt.json",
    ):
        assert (bundle / name).exists(), name
    assert (bundle / "last-message.txt").read_text(encoding="utf-8") == "lifecycle final message"
    _assert_no_running_in_state_files(bundle)
    assert "Status: success" in stdout.decode()


# --- (b) timeout: WHOLE tree killed within the grace window --------------------------------------


def test_timeout_kills_whole_process_tree_within_grace_window(tmp_path) -> None:
    """A fake codex sleeping past --timeout-seconds loses its ENTIRE tree, child included.

    This is the anti-zombie proof: the fake bin spawns its own child and the test polls that
    child's pid directly. A kill that only reaches the direct child (the fake bin) but not the
    grandchild fails this test — verified red against exactly that broken variant.
    """
    pidfile = tmp_path / "pids.txt"
    shim = _write_shim(tmp_path, _tree_sleep_body(pidfile))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    envelope = codex_delegate.Envelope.from_mapping(
        {
            "schema": codex_delegate.SCHEMA,
            "role": "reviewer",
            "task": "Lifecycle probe task.",
            "timeout_seconds": 1,
            "no_output_seconds": 1,
        }
    )
    result = codex_delegate.create_supervised_bundle(
        envelope,
        repo_root=repo_root,
        run_id="timeout-run",
        codex_bin=str(shim),
    )

    child_pid, fake_pid = _read_pidfile(pidfile, timeout=1)
    assert _wait_dead(fake_pid), "fake codex still alive past the grace window"
    assert _wait_dead(child_pid), (
        "fake codex's CHILD survived the timeout kill — the delegate killed only the direct "
        "child, not the whole process tree"
    )

    assert result.status in {"timeout", "no_output"}
    bundle = repo_root / ".claude" / "codex" / "runs" / "timeout-run"
    payload = json.loads((bundle / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] in {"timeout", "no_output"}
    assert payload["codex_launched"] is True
    _assert_no_running_in_state_files(bundle)
    # The sleeper's completion sentinel must never appear — it died mid-sleep.
    assert '"type": "done"' not in (bundle / "transcript.jsonl").read_text(encoding="utf-8")


# --- (c) delegate killed mid-run: dead tree + diagnosable terminal bundle ------------------------


def test_delegate_killed_mid_run_leaves_dead_tree_and_diagnosable_bundle(tmp_path) -> None:
    """SIGTERM to the delegate mid-run (a caller's Bash-tool timeout) is die-clean (R4/R7).

    The whole codex tree — fake bin AND its child — must be dead within the grace window, and
    the bundle must be a diagnosable terminal record: result.json present, terminal status,
    never ``running``.
    """
    pidfile = tmp_path / "pids.txt"
    shim = _write_shim(tmp_path, _tree_sleep_body(pidfile))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    delegate = subprocess.Popen(
        _delegate_argv(repo_root=repo_root, run_id="killed-run", shim=shim, timeout_seconds=300),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        # Wait until codex is demonstrably mid-run (its tree exists), then kill the delegate.
        child_pid, fake_pid = _read_pidfile(pidfile)
        assert _pid_alive(fake_pid)
        assert _pid_alive(child_pid)
        delegate.send_signal(signal.SIGTERM)
        exit_code = delegate.wait(timeout=30)
    finally:
        if delegate.poll() is None:  # pragma: no cover - only on assertion failure above
            delegate.kill()
            delegate.wait(timeout=10)

    assert exit_code != 0, "die-clean must exit nonzero"
    assert _wait_dead(fake_pid), "fake codex survived the delegate's death"
    assert _wait_dead(child_pid), "fake codex's child survived the delegate's death"

    bundle = repo_root / ".claude" / "codex" / "runs" / "killed-run"
    payload = json.loads((bundle / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] in codex_delegate.STATUSES  # terminal vocabulary only
    assert payload["status"] != "running"
    assert payload["codex_launched"] is True
    assert payload["error"], "a killed run must carry a diagnosable error message"
    _assert_no_running_in_state_files(bundle)
    assert '"type": "done"' not in (bundle / "transcript.jsonl").read_text(encoding="utf-8")


# --- availability-gated live smoke (skip, never fail, without an authenticated codex) ------------


def _codex_authenticated() -> bool:
    codex = shutil.which("codex")
    if not codex:
        return False
    try:
        return (
            subprocess.run(
                [codex, "login", "status"], capture_output=True, timeout=30, check=False
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(
    not _codex_authenticated(),
    reason="availability-gated smoke: codex absent or `codex login status` nonzero -- skip, never fail",
)
def test_codex_live_smoke_round_trip() -> None:  # pragma: no cover - live codex
    """One real ``codex exec`` round-trip through the delegate: receipt + transcript + last message.

    Gated on ``codex login status`` exiting 0 (verified live: exits 0 when authenticated) —
    mirrors the Ollama Cloud availability-gated smoke posture in tests/test_engine_bridge_http.py.
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="codex-live-smoke-") as tmp:
        repo_root = Path(tmp) / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True, timeout=30)
        (repo_root / "README.md").write_text("live smoke fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, timeout=30)
        subprocess.run(
            ["git", "-c", "user.email=smoke@test", "-c", "user.name=smoke", "commit", "-qm", "init"],
            cwd=repo_root,
            check=True,
            timeout=30,
        )

        envelope = codex_delegate.Envelope.from_mapping(
            {
                "schema": codex_delegate.SCHEMA,
                "role": "reviewer",
                "task": "Reply with the single word: ok",
                "timeout_seconds": 300,
                "no_output_seconds": 300,
            }
        )
        result = codex_delegate.create_supervised_bundle(
            envelope,
            repo_root=repo_root,
            run_id="live-smoke",
        )
        bundle = repo_root / ".claude" / "codex" / "runs" / "live-smoke"
        payload = json.loads((bundle / "result.json").read_text(encoding="utf-8"))
        assert payload["codex_launched"] is True
        # A completed round-trip: codex exited 0. Locally-configured codex tooling (e.g. an MCP
        # server dropping `.serena/`) can dirty a fresh repo and flip the reviewer scan to
        # out_of_scope_mutation — that is the diff-scan doing its job, not a smoke failure, so
        # both terminal statuses prove the round-trip.
        assert payload["return_code"] == 0, payload
        assert result.status in {"success", "out_of_scope_mutation"}, payload
        # Receipt: emitted iff launched, and it validates against bridge_receipt.v1.
        receipt = json.loads((bundle / "bridge-receipt.json").read_text(encoding="utf-8"))
        assert receipt["engine_id"] == "codex"
        assert receipt["transport"] == "cli"
        assert codex_delegate._bridge_receipt.validate_receipt(receipt) == []
        # Transcript: real JSONL flowed.
        assert (bundle / "transcript.jsonl").read_text(encoding="utf-8").strip()
        # Last message: codex wrote its final agent message via -o.
        assert (bundle / "last-message.txt").read_text(encoding="utf-8").strip()
        _assert_no_running_in_state_files(bundle)
