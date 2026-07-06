#!/usr/bin/env python3
"""Session-local tier override (#365 U1).

A run-scoped, machine-local file the operator writes via ``/tier`` to steer model/effort tier mid-run
without aborting a run: a **ceiling** the emitters clamp every unit down to, plus per-unit **overrides**
for a mid-run patch. Git-ignored (lives under ``.claude/saga/``), never committed. One file per
checkout; per-session isolation for concurrent sessions is out of scope for v1 (single-operator
assumption). Off-palette values fail loud on read and write so a hand-edited file never silently
mis-steers a run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402  (after the sys.path shim, by design)

_tier_palette = fleet_commons_shim.load("tier_palette")
MODELS: tuple[str, ...] = _tier_palette.MODELS
EFFORTS: tuple[str, ...] = _tier_palette.EFFORTS

# Machine-local, git-ignored — sibling of the saga cache (STATE_DIR in saga.py).
OVERRIDE_PATH = Path(".claude/saga/tier-session-override.json")


class TierSessionError(ValueError):
    """Raised for a malformed or off-palette session override."""


def _override_path(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / OVERRIDE_PATH


def _validate_tier(tier: Any, where: str) -> dict[str, str]:
    if not isinstance(tier, dict) or "model" not in tier or "effort" not in tier:
        raise TierSessionError(f"{where}: tier must be {{'model', 'effort'}}, got {tier!r}")
    model, effort = str(tier["model"]), str(tier["effort"])
    if model not in MODELS:
        raise TierSessionError(f"{where}: model {model!r} not in {MODELS}")
    if effort not in EFFORTS:
        raise TierSessionError(f"{where}: effort {effort!r} not in {EFFORTS}")
    # Reject an on-palette-but-unrunnable tier (e.g. haiku/xhigh -- haiku's ceiling is high). A
    # nonsensical ceiling would otherwise clamp units to an un-runnable {model, effort}; catch it loudly
    # at the source instead of silently mis-steering a run.
    if not _tier_palette.supports_effort(model, effort):
        raise TierSessionError(
            f"{where}: {model}/{effort} is unrunnable -- {model}'s effort ceiling is "
            f"{_tier_palette.effort_ceiling(model)!r}"
        )
    return {"model": model, "effort": effort}


def read_session_override(root: Path | None = None) -> dict[str, Any]:
    """Return the session override, or an empty ``{ceiling: None, unit_overrides: {}}`` when absent.

    Validates on read so a hand-edited file fails loud rather than silently mis-steering a run.
    """
    path = _override_path(root)
    if not path.exists():
        return {"ceiling": None, "unit_overrides": {}}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    ceiling = data.get("ceiling")
    if ceiling is not None:
        ceiling = _validate_tier(ceiling, "ceiling")
    overrides_raw = data.get("unit_overrides") or {}
    overrides = {
        uid: _validate_tier(t, f"unit_overrides[{uid}]") for uid, t in overrides_raw.items()
    }
    return {"ceiling": ceiling, "unit_overrides": overrides}


def _write(data: dict[str, Any], root: Path | None = None) -> Path:
    path = _override_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def set_ceiling(model: str, effort: str, root: Path | None = None) -> Path:
    """Write a run-scoped tier ceiling; validates against the palette."""
    tier = _validate_tier({"model": model, "effort": effort}, "ceiling")
    data = read_session_override(root)
    data["ceiling"] = tier
    return _write(data, root)


def set_unit_override(unit_id: str, model: str, effort: str, root: Path | None = None) -> Path:
    """Record a per-unit tier override for a mid-run patch; validates against the palette."""
    tier = _validate_tier({"model": model, "effort": effort}, f"unit_overrides[{unit_id}]")
    data = read_session_override(root)
    data.setdefault("unit_overrides", {})[unit_id] = tier
    return _write(data, root)


def clear(root: Path | None = None) -> bool:
    """Remove the session override file (end-of-run reset). Returns True iff a file was removed."""
    path = _override_path(root)
    if path.exists():
        path.unlink()
        return True
    return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Session-local tier override (/tier).")
    sub = parser.add_subparsers(dest="command", required=True)
    ceil = sub.add_parser("set-ceiling", help="write a run-scoped tier ceiling")
    ceil.add_argument("model")
    ceil.add_argument("effort")
    unit = sub.add_parser("set-unit", help="record a per-unit tier override")
    unit.add_argument("unit_id")
    unit.add_argument("model")
    unit.add_argument("effort")
    sub.add_parser("show", help="print the current session override as JSON")
    sub.add_parser("clear", help="remove the session override file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "set-ceiling":
            print(str(set_ceiling(args.model, args.effort)))
        elif args.command == "set-unit":
            print(str(set_unit_override(args.unit_id, args.model, args.effort)))
        elif args.command == "show":
            print(json.dumps(read_session_override(), indent=2, sort_keys=True))
        elif args.command == "clear":
            print("removed" if clear() else "no override file")
    except TierSessionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
