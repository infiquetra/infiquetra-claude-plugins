#!/usr/bin/env python3
"""Claude hook adapter for pre-spawn reservation, binding, and safe release (#356)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

_PREFIX = "[saga/fleet-lease]"


def _halt(message: str) -> NoReturn:
    print(f"{_PREFIX} HALT — {message}", file=sys.stderr)
    raise SystemExit(2)


def _warn_child(message: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": (
                        f"{_PREFIX} No live fleet lease was bound: {message}. "
                        "All delegated mutation tools will fail closed; return control to the parent."
                    ),
                }
            }
        )
    )


def dispatch(payload: dict[str, Any]) -> None:
    event = payload.get("hook_event_name")
    try:
        import lease_broker  # noqa: PLC0415

        if event == "PreToolUse":
            lease_broker.reserve_hook_agent(payload)
        elif event == "SubagentStart":
            lease_broker.claim_hook_agent(payload)
        elif event == "SubagentStop":
            lease_broker.record_hook_terminal(payload)
        elif event in ("PostToolUse", "PostToolUseFailure"):
            lease_broker.record_hook_parent(payload)
        else:
            raise lease_broker.HookInputError(f"unsupported hook event {event!r}")
    except Exception as exc:  # noqa: BLE001 - event posture is selected below.
        if event == "PreToolUse":
            _halt(f"agent reservation refused before spawn: {exc}")
        if event == "SubagentStart":
            _warn_child(str(exc))
            return
        # These events are observational: authority remains until the other signal or TTL.
        print(f"{_PREFIX} lifecycle update retained for retry: {exc}", file=sys.stderr)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (OSError, json.JSONDecodeError) as exc:
        _halt(f"invalid hook input: {exc}")
    if not isinstance(payload, dict):
        _halt("hook input must be a JSON object")
    dispatch(payload)


if __name__ == "__main__":
    main()
