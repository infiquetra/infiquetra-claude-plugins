#!/usr/bin/env python3
"""Find recent ignored Infiquetra loop checkpoints and active state."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

STATE_DIR = Path(".claude/infiquetra-loop")
CHECKPOINT_RE = re.compile(
    r"^(?P<kind>issue|task)-(?P<id>[a-zA-Z0-9_-]+?)"
    r"(?:-round-(?P<round>\d+))?"
    r"-phase(?P<phase>\d+)(?:-(?P<status>complete|pending|in_progress))?\.md$"
)


def read_state_json() -> dict[str, object] | None:
    state_path = STATE_DIR / "state.json"
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def humanize_age(mtime: float) -> str:
    delta = time.time() - mtime
    if delta < 60:
        return f"{int(delta)} seconds ago"
    if delta < 3600:
        return f"{int(delta // 60)} minutes ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hours ago"
    return f"{int(delta // 86400)} days ago"


def next_phase(checkpoint: dict[str, object]) -> int:
    phase = int(checkpoint.get("phase", 0))
    return phase + 1 if checkpoint.get("phase_status") == "complete" else phase


def scan_checkpoints() -> list[dict[str, object]]:
    checkpoint_dir = STATE_DIR / "checkpoints"
    if not checkpoint_dir.exists():
        return []
    candidates: list[dict[str, object]] = []
    for path in checkpoint_dir.glob("*.md"):
        match = CHECKPOINT_RE.match(path.name)
        if not match:
            continue
        status = match.group("status") or "pending"
        record = {
            "path": str(path),
            "name": path.name,
            "mtime": path.stat().st_mtime,
            "kind": match.group("kind"),
            "id": match.group("id"),
            "round": int(match.group("round")) if match.group("round") else None,
            "phase": int(match.group("phase")),
            "phase_status": status,
        }
        record["next_phase"] = next_phase(record)
        record["age"] = humanize_age(float(record["mtime"]))
        candidates.append(record)
    return sorted(candidates, key=lambda candidate: float(candidate["mtime"]), reverse=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-candidates", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = read_state_json()
    checkpoints = scan_checkpoints()
    print(
        json.dumps(
            {
                "found": bool(state and state.get("current_work")) or bool(checkpoints),
                "state": state,
                "candidates": checkpoints[: args.max_candidates],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
