#!/usr/bin/env python3
"""Step B1 run-posture check — team-execution's wired consumer of the fleet
IntentEnvelope (#380, T4-F4-1).

Before a wave spawns (or between waves, when a worker/reviewer proposes a tier or
verify-depth escalation), the coordinator resolves the spend decision through the
fleet's single posture primitive instead of asking its own question:

* attended + spend increase + approval token  -> proceed with the increase
* attended + spend increase + NO token       -> ``PostureError`` (structural refusal,
  exit 2 — never a silent escalation, never an ad hoc re-ask)
* attended + no increase                     -> proceed at the default, silently
* unattended                                 -> the cache-tight default, silently
  (a requested increase is held at the default, recorded, never prompted)

The schema, interview, and resolver live at the canonical fleet-commons home
(``plugins/fleet-core/scripts/fleet_commons/intent_envelope.py``), loaded through the
vendored ``fleet_commons_shim`` beside this file. This script defines NO posture
question of its own — the fleet drift-guard test (``tests/test_intent_envelope.py``)
enforces that single-asker rule mechanically.

Usage:
    posture_check.py --envelope-file <envelope.json> [--spend-increase]
                     [--approval-token TOKEN]

Prints the resolved decision as JSON on stdout; a posture refusal prints a named
JSON error on stderr and exits 2 (distinct from usage/IO errors, exit 1).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)

_intent_envelope = fleet_commons_shim.load("intent_envelope")

# Re-exported for callers/tests that need to catch the typed refusal.
PostureError = _intent_envelope.PostureError
IntentEnvelopeError = _intent_envelope.IntentEnvelopeError


def check(
    envelope_data: dict[str, Any],
    *,
    spend_increase: bool = False,
    approval_token: str | None = None,
) -> dict[str, Any]:
    """Resolve one Step B1 spend decision through the envelope registry.

    Raises ``IntentEnvelopeError`` on a malformed envelope (fail closed — a wave never
    spawns under a posture nobody can strictly understand) and ``PostureError`` on an
    attended spend increase with no approval token.
    """
    envelope = _intent_envelope.IntentEnvelope.from_dict(envelope_data)
    decision = _intent_envelope.resolve_spend_action(
        envelope, spend_increase=spend_increase, approval_token=approval_token
    )
    return {"step": "B1", **decision.to_dict()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="posture_check",
        description="Resolve a Step B1 spend decision through the fleet intent envelope (#380).",
    )
    parser.add_argument(
        "--envelope-file", required=True, help="path to the run's committed intent envelope JSON"
    )
    parser.add_argument("--spend-increase", action="store_true")
    parser.add_argument("--approval-token", default=None)
    args = parser.parse_args(argv)

    try:
        data = json.loads(Path(args.envelope_file).read_text(encoding="utf-8"))
        result = check(data, spend_increase=args.spend_increase, approval_token=args.approval_token)
    except PostureError as exc:
        print(json.dumps({"error": "posture-error", "reason": str(exc)}), file=sys.stderr)
        return 2
    except (IntentEnvelopeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "invalid-input", "reason": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
