#!/usr/bin/env python3
"""Infiquetra lifecycle destination and escalation helpers."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

DESTINATION_ALIASES = {
    "plan": "plan-only",
    "plan only": "plan-only",
    "plan-only": "plan-only",
    "planning": "plan-only",
    "pr": "pr",
    "pull request": "pr",
    "pull-request": "pr",
    "merge": "merge",
    "merged": "merge",
    "nonprod": "nonprod-deploy",
    "nonprod deploy": "nonprod-deploy",
    "nonprod-deploy": "nonprod-deploy",
    "deploy": "nonprod-deploy",
}


def normalize_destination(value: str) -> str:
    """Normalize user-facing destination labels."""

    key = " ".join(value.strip().lower().replace("_", "-").split())
    key = key.replace("nonprod-deployment", "nonprod-deploy")
    if key in DESTINATION_ALIASES:
        return DESTINATION_ALIASES[key]
    raise ValueError("destination must be one of: plan-only, pr, merge, nonprod-deploy")


def destination_includes_deploy(destination: str) -> bool:
    """Return whether the selected destination needs deployment orchestration."""

    return normalize_destination(destination) == "nonprod-deploy"


def should_offer_team_execution(
    *,
    file_count: int,
    phase_count: int,
    has_security: bool,
    has_infra: bool,
    cross_repo: bool,
    deployment_sensitive: bool,
) -> bool:
    """Decide whether the loop should offer team-execution."""

    return any(
        (
            file_count >= 8,
            phase_count >= 4,
            has_security,
            has_infra,
            cross_repo,
            deployment_sensitive,
        )
    )


def should_prompt_for_issue(*, has_issue: bool, is_trivial: bool, user_declined: bool) -> bool:
    """Ask whether to file an SDLC issue for non-trivial ad-hoc work."""

    return not has_issue and not is_trivial and not user_declined


def requires_hard_test_gate(change_kinds: Sequence[str]) -> bool:
    """Return whether a change kind requires explicit tests before shipping."""

    risky = {"behavior", "security", "infra", "api", "deployment", "data"}
    return bool(risky.intersection(kind.lower() for kind in change_kinds))


def recommend_execution_backend(
    *,
    file_count: int = 0,
    phase_count: int = 0,
    has_security: bool = False,
    has_infra: bool = False,
    cross_repo: bool = False,
    deployment_sensitive: bool = False,
    needs_consensus: bool = False,
    broad_independent_fanout: bool = False,
    workflow_available: bool = True,
) -> dict[str, object]:
    """Recommend an execution backend, mirroring operator-choice.md section 3.

    Reuses ``should_offer_team_execution`` for the team-execution trigger
    (passing all six required kwargs) and adds the ultracode branch. The
    precedence is lean (operator-choice section 3.3): team-execution wins over
    ultracode wins over inline.

    DELIBERATE DIVERGENCE from operator-choice section 3.1: that section frames
    the consensus signal as a **PLUS** on top of a size/risk trigger. Here a
    ``needs_consensus`` signal is **sufficient on its own** (``or
    needs_consensus``) — a small-but-contested job is a team-execution job even
    without a size/risk trigger, which is the more useful behavior for a real
    caller. This is intentional, not a transcription error.

    ``alternatives`` lists every *reachable* backend (capability-gated by
    ``workflow_available``) computed INDEPENDENTLY of which backend won
    precedence, so an overlap job (e.g. ``needs_consensus`` AND
    ``broad_independent_fanout``) recommends ``team-execution`` yet still lists
    ``cc-workflows-ultracode`` in ``alternatives`` — escalation stays one
    keystroke (operator-choice section 3.3).
    """

    team = (
        should_offer_team_execution(
            file_count=file_count,
            phase_count=phase_count,
            has_security=has_security,
            has_infra=has_infra,
            cross_repo=cross_repo,
            deployment_sensitive=deployment_sensitive,
        )
        or needs_consensus
    )
    ultracode = broad_independent_fanout and not (has_security or has_infra or deployment_sensitive)

    if team:
        recommended = "team-execution"
        rationale = "size/risk or consensus signal -> review consensus + gates fit"
    elif ultracode and workflow_available:
        recommended = "cc-workflows-ultracode"
        rationale = "broad independent fan-out without elevated risk -> deterministic fan-out"
    else:
        recommended = "inline"
        rationale = "no escalation signal -> the agent does the work itself"

    reachable = ["inline", "team-execution", "cc-workflows-ultracode"]
    if not workflow_available:
        reachable.remove("cc-workflows-ultracode")
    alternatives = [backend for backend in reachable if backend != recommended]

    return {
        "recommended": recommended,
        "rationale": rationale,
        "alternatives": alternatives,
        "omit_ultracode": not workflow_available,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize = subparsers.add_parser("normalize", help="normalize a user-facing destination label")
    normalize.add_argument("destination")

    backend = subparsers.add_parser(
        "recommend-backend", help="recommend an execution backend as JSON"
    )
    backend.add_argument("--file-count", type=int, default=0)
    backend.add_argument("--phase-count", type=int, default=0)
    backend.add_argument("--has-security", action="store_true")
    backend.add_argument("--has-infra", action="store_true")
    backend.add_argument("--cross-repo", action="store_true")
    backend.add_argument("--deployment-sensitive", action="store_true")
    backend.add_argument("--needs-consensus", action="store_true")
    backend.add_argument("--broad-fanout", action="store_true")
    backend.add_argument("--no-workflow", action="store_true")

    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return _build_parser().parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "normalize":
        print(normalize_destination(args.destination))
        return 0
    if args.command == "recommend-backend":
        result = recommend_execution_backend(
            file_count=args.file_count,
            phase_count=args.phase_count,
            has_security=args.has_security,
            has_infra=args.has_infra,
            cross_repo=args.cross_repo,
            deployment_sensitive=args.deployment_sensitive,
            needs_consensus=args.needs_consensus,
            broad_independent_fanout=args.broad_fanout,
            workflow_available=not args.no_workflow,
        )
        print(json.dumps(result))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
