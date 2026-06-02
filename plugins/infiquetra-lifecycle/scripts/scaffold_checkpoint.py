#!/usr/bin/env python3
"""Write a saga tick (thin wrapper over the unified saga engine).

This was the per-phase *checkpoint* scaffolder. Under the 0.4.0 saga model it is
a thin wrapper over ``saga.py``: a "checkpoint" is now one immutable, timestamped
saga *tick* written to ``.claude/infiquetra-lifecycle/sagas/<saga_id>/<YYYYMMDD-
HHMMSS>.md`` (append-only — never overwritten), and the derived ``state.json``
index is refreshed atomically. The legacy CLI flags and the four printed JSON
keys (``checkpoint_path`` / ``state_path`` / ``phase`` / ``status``) are
preserved; ``checkpoint_path`` now points at the new immutable tick (the saga
``envelope_path``) instead of a name-encoded checkpoint file.

The legacy ``--status`` flag here means *phase completion* (pending |
in_progress | complete); the saga engine calls that ``phase_status`` (its own
``status`` is thread disposition), so this wrapper remaps ``--status`` ->
``phase_status`` and reports the phase status back under the legacy ``status``
key.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["issue", "task"], default="issue")
    parser.add_argument("--id", required=True, help="Issue number or task slug")
    parser.add_argument("--round", type=int)
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument(
        "--status", choices=["pending", "in_progress", "complete"], default="pending"
    )
    parser.add_argument("--phase-title", default="")
    parser.add_argument("--issue-ref", default="")
    parser.add_argument("--destination", default="plan-only")
    parser.add_argument("--progress-pct", type=int, default=0)
    parser.add_argument("--plan-path", default="")
    parser.add_argument("--work-session-path", default="")
    parser.add_argument("--last-commit-sha", default="")
    parser.add_argument("--current-work", default="")
    parser.add_argument("--blockers", default="None")
    parser.add_argument("--important-context", default="")
    parser.add_argument("--next-steps", default="", help="pipe-separated list")
    return parser.parse_args()


def _build_saga(args: argparse.Namespace) -> saga.Saga:
    """Map the legacy checkpoint flags onto a ``Saga`` tick."""
    saga_id = saga.derive_saga_id(args.kind, str(args.id))
    # A single --work-session-path becomes a one-item snapshot list; an empty
    # string clears (snapshot semantics), preserving the legacy "set it now" feel.
    work_sessions: saga.ListOrAbsent = [args.work_session_path] if args.work_session_path else []
    summary = args.phase_title or f"Phase {args.phase}"
    # Fold the free-form checkpoint prose into the saga body so it is not lost.
    notes_parts = [part for part in (args.current_work, args.important_context) if part]
    return saga.Saga(
        saga_id=saga_id,
        kind=args.kind,
        id=str(args.id),
        lifecycle_phase="work",
        phase_status=args.status,
        next_step=args.next_steps.split("|", 1)[0] if args.next_steps else "",
        issue_ref=args.issue_ref,
        destination=args.destination,
        round=args.round or 0,
        phase=args.phase,
        progress_pct=args.progress_pct,
        plan_path=args.plan_path,
        work_session_paths=work_sessions,
        last_commit_sha=args.last_commit_sha,
        blockers=args.blockers,
        summary=summary,
        remaining="\n".join(args.next_steps.split("|")) if args.next_steps else "",
        notes="\n\n".join(notes_parts),
    )


def main() -> int:
    args = parse_args()
    result = saga.save(Path.cwd(), _build_saga(args))
    print(
        json.dumps(
            {
                "checkpoint_path": result["envelope_path"],
                "state_path": result["state_path"],
                "phase": result["phase"],
                # Legacy "status" was the phase-completion status fed in.
                "status": args.status,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
