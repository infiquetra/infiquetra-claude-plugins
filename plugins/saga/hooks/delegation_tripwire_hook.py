#!/usr/bin/env python3
"""
PreToolUse hook: block file-tool calls during an unproven armed delegation (#384, U3).

Fires on ``Write``/``Edit``/``MultiEdit``/``NotebookEdit``. Reads the delegation liveness
marker (fleet-core ``delegation_state.active(session_id)``) written by the dispatch layer
(KTD4): unarmed sessions see zero behavior change, zero further I/O. When armed, this hook
is the runtime half of the zero-engine-call tripwire — Claude cannot silently do the file
work itself while a delegation is supposedly in flight (KTD3's file-tool vocabulary matches
the transcript classifier's own).

Genuine-invocation evidence (KTD5): any run directory under the armed engine's
``bundle_root`` (``.claude/agy/runs/`` or ``.claude/codex/runs/``) containing a
``prompt.txt`` whose mtime is >= the marker's ``armed_at`` timestamp counts as proof a real
engine launch is underway. No such evidence -> block.

Properties (contract copied from ``pre_push_gate_hook.py`` exactly):
  - SILENT ON PASS / UNARMED: no output, exit 0.
  - BLOCKING ON UNPROVEN ARMED DELEGATION: exits 2, stderr names the armed engine, the
    expected evidence path, and the arm/disarm CLI.
  - FAIL-OPEN ON EVERY ERROR PATH: malformed stdin, unreadable marker, missing fleet-core
    shim/module, missing bundle roots -> exit 0.

Exit codes:
  0 — unarmed, evidence found, or any error (fail-open).
  2 — armed with no genuine-invocation evidence (blocking).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# fleet-core modules are loaded via saga's vendored shim (mirrors engine_dispatch.py:13-15).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _find_repo_root(cwd: str | None) -> Path:
    """Best-effort repo root: given cwd, else process cwd. Never raises."""
    try:
        if cwd:
            return Path(cwd)
    except Exception:
        pass
    return Path.cwd()


def _has_genuine_evidence(bundle_root: Path, armed_at: float) -> bool:
    """True if any run dir under ``bundle_root`` has a ``prompt.txt`` mtime >= ``armed_at``."""
    try:
        if not bundle_root.is_dir():
            return False
        for run_dir in bundle_root.iterdir():
            try:
                if not run_dir.is_dir():
                    continue
                prompt_path = run_dir / "prompt.txt"
                if not prompt_path.is_file():
                    continue
                if prompt_path.stat().st_mtime >= armed_at:
                    return True
            except OSError:
                continue
    except OSError:
        return False
    return False


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        # Malformed envelope — fail open.
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name not in _FILE_TOOLS:
        sys.exit(0)

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        # No session identity to key the marker on — nothing to check, fail open.
        sys.exit(0)

    repo_root = _find_repo_root(payload.get("cwd"))

    try:
        import fleet_commons_shim  # noqa: PLC0415

        delegation_state = fleet_commons_shim.load("delegation_state")
        delegation_audit = fleet_commons_shim.load("delegation_audit")
    except Exception:
        # fleet-core unavailable — fail open (never block on a missing dependency).
        sys.exit(0)

    try:
        entry = delegation_state.active(session_id, root=repo_root)
    except Exception:
        # Marker check must never raise; if it somehow does, fail open.
        sys.exit(0)

    if entry is None:
        # Unarmed — zero behavior change, zero further I/O.
        sys.exit(0)

    try:
        engine_config = delegation_audit.ENGINE_CONFIGS.get(entry.engine)
    except Exception:
        sys.exit(0)

    if engine_config is None:
        # Unknown/unconfigured engine on the marker — nothing to evidence-check, fail open.
        sys.exit(0)

    bundle_root = repo_root / engine_config.bundle_root

    try:
        proven = _has_genuine_evidence(bundle_root, entry.armed_at)
    except Exception:
        sys.exit(0)

    if proven:
        sys.exit(0)

    armed_since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry.armed_at))
    print(
        (
            f"[saga/delegation-tripwire] Delegation to '{entry.engine}' is armed (since "
            f"{armed_since}) but no genuine invocation evidence was found under "
            f"'{engine_config.bundle_root}/<run-id>/prompt.txt' — {tool_name} blocked.\n"
            "Expected evidence: a run directory under the armed engine's bundle root "
            "containing prompt.txt with mtime at or after the arm time.\n"
            "If this delegation is done, disarm it: "
            "python3 plugins/fleet-core/scripts/fleet_commons/delegation_state.py disarm "
            f"--session-id {session_id}\n"
            "To arm a genuine delegation: "
            "python3 plugins/fleet-core/scripts/fleet_commons/delegation_state.py arm "
            f"--engine {entry.engine} --session-id {session_id} --armed-by <caller>"
        ),
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
