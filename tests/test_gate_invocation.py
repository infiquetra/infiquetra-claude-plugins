"""Unit tests for gate.sh long-run background invocation and result marker capture (#782)."""

from __future__ import annotations

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
    """An interrupted/killed gate run must write an INTERRUPTED status to result.txt."""
    log_dir = tmp_path / "gate-logs"
    env = {**os.environ, "GATE_LOG_DIR": str(log_dir)}

    proc = subprocess.Popen(
        ["bash", str(GATE_SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Allow the process to start up and set up trap / log dir
    time.sleep(0.3)

    # Terminate the process (simulating a timeout kill like SIGTERM)
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)

    result_file = log_dir / "result.txt"
    assert result_file.exists(), "result.txt was not created on early termination"
    result_content = result_file.read_text()
    assert "GATE INTERRUPTED" in result_content
