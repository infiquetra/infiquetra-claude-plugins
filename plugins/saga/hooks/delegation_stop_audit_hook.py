#!/usr/bin/env python3
"""
Stop/SubagentStop hook: turn-end delegation audit — the transcript itself is the witness
(#384, U4).

Registered under BOTH ``Stop`` and ``SubagentStop`` (same script, both marker-gated). The
input carries ``transcript_path`` + ``stop_hook_active``; ``SubagentStop`` additionally
carries ``agent_id``/``agent_type``, and its ``transcript_path`` IS the subagent's own
transcript — which is exactly the delegation-bearing transcript for bridge-agent runs.

Logic (KTD8 cost bounds — marker stat FIRST):
  1. Unarmed session -> exit 0 without ever opening the transcript.
  2. Armed -> classify the transcript with the engine-parametrized fleet-core auditor
     (``delegation_audit.classify``, 8 MiB streaming cap), corroborate the engine's bundle
     artifacts (``result.json`` launch flag + receipt presence since ``armed_at``), and
     reconcile the two signals.
  3. Clean ``real`` classification + corroborating bundle -> disarm the marker + exit 0
     (next turn starts unarmed).
  4. ``fallback_suspected`` OR transcript-vs-bundle divergence (``DELEGATION_INTEGRITY``)
     -> HALT: exit 2 with stderr instructing Claude to surface the audit failure and re-run
     the delegation genuinely.

Loop guard (KTD2, operator-confirmed): when ``stop_hook_active`` is true and the audit
still fails, write an audit record to ``.claude/delegation/audits/<ts>.json``, print a
banner to stderr, and exit 0 — exactly one forced continuation, never an infinite block.

FAIL-OPEN on every error path: malformed stdin, missing fleet-core shim/module, unreadable
marker, missing transcript while armed (banner, never crash) -> exit 0.

Exit codes:
  0 — unarmed, clean pass, loop-guarded second failure, or any error (fail-open).
  2 — armed turn whose audit failed for the first time (blocking; stderr carries the reason).
"""

from __future__ import annotations

import contextlib
import json
import sys
import time
from pathlib import Path
from typing import Any

# fleet-core modules are loaded via saga's vendored shim (mirrors delegation_tripwire_hook.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

_BANNER_PREFIX = "[saga/delegation-stop-audit]"


def _find_repo_root(cwd: str | None) -> Path:
    """Best-effort repo root: given cwd, else process cwd. Never raises."""
    try:
        if cwd:
            return Path(cwd)
    except Exception:
        pass
    return Path.cwd()


def _write_audit_record(repo_root: Path, record: dict[str, Any]) -> str | None:
    """Best-effort audit record under ``.claude/delegation/audits/<ts>.json``. Never raises."""
    try:
        audits_dir = repo_root / ".claude" / "delegation" / "audits"
        audits_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        path = audits_dir / f"{ts}-{record.get('session_id', 'unknown')}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _fail_reason(verdict: str, engine: str, delegation_audit: Any) -> str:
    """Human/Claude-facing reason for a failed audit, naming DELEGATION_INTEGRITY on divergence."""
    if verdict == delegation_audit.DELEGATION_INTEGRITY:
        return (
            f"DELEGATION_INTEGRITY: the transcript shows a genuine '{engine}' invocation, "
            f"but the engine's bundle artifacts (result.json launch flag / receipt) do not "
            "corroborate a real launch. The two independent signals diverge — this is never "
            "silently resolved in either direction."
        )
    return (
        f"fallback_suspected: this turn was armed for a '{engine}' delegation, but the "
        "transcript shows Claude doing the work itself (file tools) with no genuine "
        f"'{engine}' engine invocation."
    )


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        # Malformed envelope — fail open.
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        sys.exit(0)

    repo_root = _find_repo_root(payload.get("cwd"))

    try:
        import fleet_commons_shim  # noqa: PLC0415

        delegation_state = fleet_commons_shim.load("delegation_state")
        delegation_audit = fleet_commons_shim.load("delegation_audit")
    except Exception:
        # fleet-core unavailable — fail open (never block on a missing dependency).
        sys.exit(0)

    # KTD8: marker stat FIRST — an unarmed turn exits without opening the transcript.
    try:
        entry = delegation_state.active(session_id, root=repo_root)
    except Exception:
        sys.exit(0)
    if entry is None:
        sys.exit(0)

    stop_hook_active = payload.get("stop_hook_active") is True
    transcript_raw = payload.get("transcript_path")
    transcript_path = (
        Path(transcript_raw) if isinstance(transcript_raw, str) and transcript_raw else None
    )

    if transcript_path is None or not transcript_path.is_file():
        # Armed but no transcript to audit — banner, never crash, fail open.
        print(
            f"{_BANNER_PREFIX} armed delegation to '{entry.engine}' but the transcript "
            f"path is missing/unreadable ({transcript_raw!r}); audit skipped (fail-open).",
            file=sys.stderr,
        )
        sys.exit(0)

    try:
        classification = delegation_audit.classify(transcript_path, entry.engine)
        corroboration = delegation_audit.corroborate(
            entry.engine, since_ts=entry.armed_at, root=repo_root
        )
        # The hook has no engine self-report channel; the transcript's own claim stands in:
        # a `real` classification asserts a genuine launch, so a non-corroborating bundle is
        # exactly the named divergence (DELEGATION_INTEGRITY), and `fallback_suspected` passes
        # through unchanged.
        verdict = delegation_audit.reconcile(classification, corroboration, self_report="ok")
    except Exception:
        # Auditor failure — fail open, never crash a turn end.
        sys.exit(0)

    record: dict[str, Any] = {
        "hook": "delegation_stop_audit_hook",
        "session_id": session_id,
        "engine": entry.engine,
        "armed_at": entry.armed_at,
        "armed_by": entry.armed_by,
        "verdict": verdict,
        "stop_hook_active": stop_hook_active,
        "transcript_path": str(transcript_path),
        "classification": classification.to_jsonable(),
        "corroboration": corroboration.to_jsonable(),
        "audited_at": time.time(),
    }

    if verdict == delegation_audit.REAL:
        # Clean real + corroborated pass: disarm so the next turn starts unarmed, exit 0.
        with contextlib.suppress(Exception):
            delegation_state.disarm(session_id, root=repo_root)
        _write_audit_record(repo_root, record)
        sys.exit(0)

    reason = _fail_reason(verdict, entry.engine, delegation_audit)

    if stop_hook_active:
        # KTD2 loop guard: exactly one forced continuation, never an infinite block.
        record["loop_guard"] = True
        record_path = _write_audit_record(repo_root, record)
        print(
            f"{_BANNER_PREFIX} LOOP GUARD: the delegation audit still fails after one "
            f"forced continuation ({reason}). Audit record: {record_path or 'unwritable'}. "
            "Allowing the stop (exit 0) to avoid an infinite block — investigate before "
            "trusting this turn's delegation.",
            file=sys.stderr,
        )
        sys.exit(0)

    _write_audit_record(repo_root, record)
    print(
        f"{_BANNER_PREFIX} HALT — delegation audit failed for engine '{entry.engine}': "
        f"{reason}\n"
        "Surface this audit failure to the operator explicitly, then re-run the delegation "
        f"genuinely through the '{entry.engine}' engine (do not do the file work yourself). "
        "The turn may not end with an unproven delegation still armed.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
