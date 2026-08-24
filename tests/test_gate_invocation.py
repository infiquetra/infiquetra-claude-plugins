"""Unit tests for gate.sh long-run background invocation and result marker capture (#782)."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
GATE_SCRIPT = ROOT / "scripts" / "gate.sh"
CLAUDE_MD = ROOT / "CLAUDE.md"


def test_gate_syntax() -> None:
    """gate.sh must be valid bash syntax."""
    res = subprocess.run(["bash", "-n", str(GATE_SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 0, f"bash -n failed: {res.stderr}"


def test_claude_md_quality_checks_documentation() -> None:
    """CLAUDE.md must document the backgrounded invocation, timeout expectation, and re-entry rule."""
    content = CLAUDE_MD.read_text()
    assert "background" in content.lower()
    assert "GATE_LOG_DIR" in content
    assert "result.txt" in content
    assert "re-entry" in content.lower()
    assert "already running" in content.lower()
    assert (
        "Exit codes: `0` green · `1` a blocking step failed · `2` coverage is short of `ci.yml`"
        in content
    )
    assert "10-minute" in content or "600-second" in content


def test_gate_script_result_marker_and_re_entry_doc() -> None:
    """scripts/gate.sh must document safe re-entry and define RESULT_FILE."""
    content = GATE_SCRIPT.read_text()
    assert "RESULT_FILE=" in content
    assert "result.txt" in content
    assert "re-entry" in content.lower()
    assert "already running" in content.lower()


def test_gate_result_marker_captured_on_early_kill(tmp_path: Path) -> None:
    """A killed gate run overwrites any stale marker with an INTERRUPTED status.

    The signal goes to the whole process group, not to gate.sh alone. bash defers a
    trap until the foreground child it is waiting on returns, so signalling only the
    script can stall for as long as the running step takes (measured: ~8s against a
    sleeping child) and would leave an orphaned 24-step gate running under CI.
    """
    log_dir = tmp_path / "gate-logs"
    log_dir.mkdir()
    result_file = log_dir / "result.txt"

    # Seed the previous run's verdict: a reused GATE_LOG_DIR must not report it as this
    # run's outcome.
    result_file.write_text("GATE GREEN — 24 steps ran, 0 blocking failures, 0 uncovered.\n")

    env = {**os.environ, "GATE_LOG_DIR": str(log_dir)}
    proc = subprocess.Popen(
        ["bash", str(GATE_SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        # Let the run get past its preconditions and into real steps.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                _, stderr = proc.communicate()
                raise AssertionError(
                    f"gate.sh exited early (rc={proc.returncode}) before it could be "
                    f"interrupted: {stderr.decode(errors='replace')}"
                )
            if not result_file.exists():
                break
            time.sleep(0.1)
        else:
            raise AssertionError("gate.sh never cleared the stale result marker")

        # The process can still lose a precondition race between the poll and the
        # signal; report that as what it is rather than as a ProcessLookupError.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=30)
        assert proc.returncode != 3, "gate.sh failed a precondition instead of being interrupted"
    finally:
        if proc.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait(timeout=30)
        if proc.stderr is not None:
            proc.stderr.close()

    assert result_file.exists(), "result.txt was not created on early termination"
    result_content = result_file.read_text()
    assert "GATE INTERRUPTED" in result_content
    assert "GATE GREEN" not in result_content, "stale marker reported as this run's outcome"
