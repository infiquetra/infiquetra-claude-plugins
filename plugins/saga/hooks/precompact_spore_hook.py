#!/usr/bin/env python3
"""PreCompact hook: freeze the active saga box into a structured spore under a hard deadline."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import saga_spore
except Exception:
    sys.exit(0)

SPORE_DEADLINE_S = 1.5
SPORE_TTL_DAYS = 7


class DeadlineExceededError(Exception):
    """Raised by the SIGALRM handler when the freeze exceeds SPORE_DEADLINE_S."""


def _alarm_handler(signum: int, frame: object) -> None:
    raise DeadlineExceededError


def main() -> None:
    try:
        raw = sys.stdin.read()
    except Exception:
        sys.exit(0)

    if not raw.strip():
        sys.exit(0)

    try:
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)

    # R1. Tolerant stdin parse
    cwd = payload.get("cwd")
    session_id = payload.get("session_id")
    trigger = payload.get("trigger")

    # R7. Defensive trigger guard
    if trigger not in {"auto", "manual"}:
        sys.exit(0)

    if not session_id or not cwd:
        sys.exit(0)

    # R2. Repo root resolution
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode != 0 or not res.stdout:
            sys.exit(0)
        repo_root = Path(res.stdout.strip())
    except Exception:
        sys.exit(0)

    signal.signal(signal.SIGALRM, _alarm_handler)

    # R4. WALL-CLOCK DEADLINE
    try:
        signal.setitimer(signal.ITIMER_REAL, SPORE_DEADLINE_S)

        # Build spore
        now = datetime.now(UTC).isoformat()
        spore = saga_spore.build_spore(repo_root, session_id, now=now)
        if not spore.get("saga_box"):
            sys.exit(0)

        text = saga_spore.dump(spore)

        # R5. Write target (atomic)
        common_dir = saga_spore.outcome_store.resolve_common_dir(repo_root)
        out_path = saga_spore.spore_path(common_dir, session_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = out_path.with_suffix(".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, out_path)

        # R6. Orphan sweep
        cutoff = time.time() - (SPORE_TTL_DAYS * 86400)
        for p in out_path.parent.glob("*.json"):
            if p == out_path:
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
            except Exception:
                pass

    except Exception:
        # If build_spore raises for any reason, catch it, write nothing, exit 0
        pass
    finally:
        # Always cancel the timer
        signal.setitimer(signal.ITIMER_REAL, 0)

    # R8. Contract: ALWAYS exit 0, NEVER print a decision key, NEVER raise, silent hook
    sys.exit(0)


if __name__ == "__main__":
    main()
