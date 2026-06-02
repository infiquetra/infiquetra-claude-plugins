#!/usr/bin/env python3
"""Find in-flight saga work (thin wrapper over the unified saga engine).

This was the checkpoint scanner. Under the 0.4.0 saga model it is a thin wrapper
over ``saga.py``: candidates come from ``saga.scan`` (one per saga, the latest
immutable tick of each, ordered by FILENAME descending — never ``mtime``),
appended with any flagged legacy ``checkpoints/`` entries for one back-compat
version. The derived ``state.json`` index is read for the active-work signal.

The legacy CLI flag (``--max-candidates``) and the three printed JSON keys
(``found`` / ``state`` / ``candidates``) are preserved. Candidate dicts now carry
the richer saga scan shape (``saga_id``, ``lifecycle_phase``, ``status``,
``next_step``, ``updated_at`` ...) instead of the old mtime/age fields.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the sibling ``saga.py`` engine is importable whether this script is run
# directly (its dir is already ``sys.path[0]``) or loaded via importlib from an
# arbitrary cwd (the test harness does not add the script dir to ``sys.path``).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import saga  # noqa: E402  (path bootstrap must run before this import)


def read_state_json(root: Path) -> dict[str, object] | None:
    state_path = root / saga.STATE_DIR / "state.json"
    if not state_path.exists():
        return None
    try:
        loaded: dict[str, object] = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return loaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-candidates", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    state = read_state_json(root)
    candidates = saga.scan(root, max_candidates=args.max_candidates)
    print(
        json.dumps(
            {
                "found": bool(state and state.get("current_work")) or bool(candidates),
                "state": state,
                "candidates": candidates,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
