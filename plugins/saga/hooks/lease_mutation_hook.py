#!/usr/bin/env python3
"""PreToolUse fencing for Bash and delegated file mutation tools (#356)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

_PREFIX = "[saga/fleet-lease]"


def _halt(message: str) -> NoReturn:
    print(
        f"{_PREFIX} HALT — delegated mutation refused: {message}. "
        "Return control to the root coordinator; do not retry from this child.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def dispatch(payload: dict[str, Any]) -> None:
    # Trusted hook identity is the arm signal. Root calls intentionally avoid fleet I/O.
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        return
    try:
        import lease_broker  # noqa: PLC0415

        lease_broker.verify_hook_mutation(payload)
    except Exception as exc:  # noqa: BLE001 - armed delegated paths fail closed on every skew.
        _halt(str(exc))


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
