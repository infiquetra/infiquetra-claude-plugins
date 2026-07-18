#!/usr/bin/env python3
"""Claude hook adapter for team-run teardown recovery seams (#358 R5/R11).

``SessionEnd`` records a bounded best-effort teardown *request* (close fence + intent) for
this trusted session's open runs — it never claims the run is closed. ``SessionStart``
(``startup|resume``) runs one bounded, expired-only recovery pass. Both act only on the
hook's canonical repository (the run-fact ledger under its git common dir), use trusted
hook JSON for session and cwd, and fail visibly without fabricating completion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

_PREFIX = "[saga/team-teardown]"
_RECOVERY_MAX_ACTIONS = 4


def _note(message: str) -> None:
    print(f"{_PREFIX} {message}", file=sys.stderr)


def _now_utc_text() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def dispatch(payload: dict[str, Any]) -> None:
    import run_ledger
    import team_teardown

    event = str(payload.get("hook_event_name") or "")
    session_id = str(payload.get("session_id") or "")
    cwd = str(payload.get("cwd") or "")
    if not session_id or not cwd:
        _note("missing trusted session_id/cwd — no teardown action taken")
        return
    repo_root = Path(cwd)
    try:
        ledger = run_ledger.RunLedger.resolve(repo_root)
    except Exception:  # noqa: BLE001 - not a git repo: cross-repo-safe silent degrade
        return
    try:
        broker = team_teardown.default_broker()
    except team_teardown.TeardownError as exc:
        _note(f"broker unavailable — no teardown action taken: {exc}")
        return

    if event == "SessionEnd":
        decision = team_teardown.read_decision_input(ledger, broker)
        targets = team_teardown._matching_open_runs(
            decision, root_sha256=str(broker.root_sha256), session_id=session_id
        )
        for run_id in targets:
            recorded = team_teardown.request(
                ledger,
                broker,
                subplot_id="team-execution-run",
                team_run_id=run_id,
                terminal_reason="operator-abort",
                at=_now_utc_text(),
            )
            _note(
                f"recorded teardown request for {run_id} "
                f"(intent {recorded['intent_id'][:12]}…) — request evidence only, "
                "not closure"
            )
        return

    if event == "SessionStart":
        outcome = team_teardown.recover(
            ledger,
            broker,
            team_teardown.production_adapters(broker),
            subplot_id="team-execution-run",
            expired_only=True,
            max_actions=_RECOVERY_MAX_ACTIONS,
            at_provider=_now_utc_text,
        )
        acted = [item for item in outcome.get("recovered_runs", []) if item.get("actions_taken")]
        if acted:
            _note(f"recovery pass acted on {len(acted)} run(s): {json.dumps(acted)}")
        return

    _note(f"unhandled hook event {event!r} — no teardown action taken")


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        _note("malformed hook payload — no teardown action taken")
        return
    if not isinstance(payload, dict):
        _note("non-object hook payload — no teardown action taken")
        return
    try:
        dispatch(payload)
    except Exception as exc:  # noqa: BLE001 - a hook failure is visible, never a blocker
        _note(f"teardown hook failed visibly (run state unchanged is NOT closure): {exc}")


if __name__ == "__main__":
    main()
