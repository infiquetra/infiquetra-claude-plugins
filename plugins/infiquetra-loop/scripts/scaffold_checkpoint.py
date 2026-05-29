#!/usr/bin/env python3
"""Scaffold ignored Infiquetra loop checkpoint state."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

STATE_DIR = Path(".claude/infiquetra-loop")
CHECKPOINT_DIR = STATE_DIR / "checkpoints"

DEFAULT_TEMPLATE = """# {{phase_title}}

- Date: {{date}}
- Issue: {{issue_ref}}
- Destination: {{destination}}
- Phase: {{phase_number}}
- Status: {{phase_status}}
- Plan: {{plan_path}}
- Work session: {{work_session_path}}
- Commit: {{last_commit_sha}}
- Progress: {{progress_pct}}%
- Blockers: {{blockers}}

## Current Work

{{current_work}}

## Important Context

{{important_context}}
"""


def render_template(template: str, context: dict[str, object]) -> str:
    def render_var(match: re.Match[str]) -> str:
        return str(context.get(match.group(1), ""))

    return re.sub(r"\{\{(\w+)\}\}", render_var, template)


def checkpoint_path(args: argparse.Namespace) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-round-{args.round}" if args.round else ""
    name = f"{args.kind}-{args.id}{suffix}-phase{args.phase}-{args.status}.md"
    return CHECKPOINT_DIR / name


def update_state_json(context: dict[str, object], args: argparse.Namespace) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = STATE_DIR / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except json.JSONDecodeError:
        state = {}

    state["last_updated"] = datetime.now(UTC).isoformat()
    state["current_work"] = {
        "kind": args.kind,
        "id": args.id,
        "round": args.round,
        "phase": args.phase,
        "phase_status": args.status,
        "destination": args.destination,
        "plan_path": args.plan_path,
        "work_session_path": args.work_session_path,
    }
    if args.next_steps:
        state["current_work"]["next_steps"] = args.next_steps.split("|")
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


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


def main() -> int:
    args = parse_args()
    context = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
        "phase_title": args.phase_title or f"Phase {args.phase}",
        "phase_number": args.phase,
        "phase_status": args.status,
        "issue_ref": args.issue_ref,
        "destination": args.destination,
        "progress_pct": args.progress_pct,
        "plan_path": args.plan_path,
        "work_session_path": args.work_session_path,
        "last_commit_sha": args.last_commit_sha,
        "current_work": args.current_work,
        "blockers": args.blockers,
        "important_context": args.important_context,
    }
    out_path = checkpoint_path(args)
    out_path.write_text(render_template(DEFAULT_TEMPLATE, context), encoding="utf-8")
    update_state_json(context, args)
    print(
        json.dumps(
            {
                "checkpoint_path": str(out_path),
                "state_path": str(STATE_DIR / "state.json"),
                "phase": args.phase,
                "status": args.status,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
