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
    has_code_surface: bool = True,
) -> bool:
    """Decide whether the loop should offer team-execution.

    ``has_code_surface`` defaults True, so every existing caller is unchanged.
    Set it False for pure docs/spec/research/journal work (no code, no IaC, no
    API contract, no deployable artifact). It neutralizes the OUTPUT-BLIND
    proxies — the ones that fire on the *mention* or *volume* of risk rather than
    a real ship/scanner surface that team-execution's gates can act on:

    * ``file_count`` / ``phase_count`` — volume and sequencing, not governance.
    * ``has_infra`` / ``has_security`` — ``parse_issue.py`` keyword regexes
      (terraform, lambda, auth, iam, ...) trip on infra/security DOCS that touch
      nothing deployable.
    * ``deployment_sensitive`` — cannot truthfully hold when there is no deploy.

    ``cross_repo`` SURVIVES the neutralizer: crossing a repo boundary crosses an
    OWNERSHIP boundary, a multi-party coordination/consensus need that holds even
    for docs. (``needs_consensus`` survives in ``recommend_execution_backend`` for
    the same reason.)
    """

    code_shaped = any(
        (
            file_count >= 8,
            phase_count >= 4,
            has_security,
            has_infra,
            deployment_sensitive,
        )
    )
    return (code_shaped and has_code_surface) or cross_repo


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
    adversarial_confidence: bool = False,
    has_code_surface: bool = True,
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

    ``has_code_surface`` (default True) neutralizes the code-shaped team-execution
    proxies for pure docs/spec/research work (see ``should_offer_team_execution``).
    It also gates the ultracode RISK SUPPRESSOR below: ``has_infra`` /
    ``has_security`` are ``parse_issue.py`` keyword matches (mention, not touch),
    so on a docs change they are false positives that must not block an ultracode
    fan-out any more than they force team-execution.

    ``adversarial_confidence`` (default False) is the second ultracode trigger
    beside ``broad_independent_fanout``: prove-by-refutation / judge-panel /
    perspective-diverse verification is an ultracode shape (deterministic
    INDEPENDENT verification, not merely breadth). Without it, "stress-test this
    from many angles" work with no deploy/security signal would fall to inline.

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
            has_code_surface=has_code_surface,
        )
        or needs_consensus
    )
    # The risk suppressor only bites when there is a real code/scanner surface:
    # has_infra / has_security are keyword matches that false-positive on docs.
    elevated_risk = (has_security or has_infra or deployment_sensitive) and has_code_surface
    ultracode = (broad_independent_fanout or adversarial_confidence) and not elevated_risk

    if team:
        recommended = "team-execution"
        rationale = "size/risk or consensus signal -> review consensus + gates fit"
    elif ultracode and workflow_available:
        recommended = "cc-workflows-ultracode"
        rationale = (
            "broad fan-out or adversarial-confidence pass without elevated risk"
            " -> deterministic independent verification"
        )
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
    backend.add_argument("--adversarial-confidence", action="store_true")
    backend.add_argument("--no-code-surface", action="store_true")
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
            adversarial_confidence=args.adversarial_confidence,
            has_code_surface=not args.no_code_surface,
            workflow_available=not args.no_workflow,
        )
        print(json.dumps(result))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
