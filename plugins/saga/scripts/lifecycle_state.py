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
    consensus_is_gated: bool = True,
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

    GATED vs ADVISORY consensus (R7 keystone). A ``needs_consensus`` signal is
    no longer an unconditional hard-force to team-execution. The governance axis
    (operator-choice section 3.1) splits it:

    * **gated** consensus (``consensus_is_gated=True``, the default) — the verdict
      must BLOCK a merge/deploy and PERSIST as standing evidence. Only
      team-execution offers a reviewer-CONSENSUS gate + named scanners + a guarded
      deploy, so gated consensus is a team-execution job even when small. Default
      True keeps every existing caller's behavior (a bare ``needs_consensus=True``
      still recommends team-execution).
    * **advisory** consensus (``consensus_is_gated=False``) — N throwaway
      in-session votes the operator acts on themselves; nothing is recorded or
      blocks. That is a dynamic-workflow judge-panel, so advisory consensus feeds
      the existing ``adversarial_confidence`` ultracode trigger instead of forcing
      team-execution. A contested-but-not-gated job therefore reaches the advisory
      ultracode branch and never regresses to inline.

    This stops the old unconditional ``or needs_consensus`` hard-force: only the
    GATED branch reaches team-execution; the advisory branch is OR'd into the
    ultracode trigger beside ``adversarial_confidence``.

    ``has_code_surface`` (default True) neutralizes the code-shaped team-execution
    proxies for pure docs/spec/research work (see ``should_offer_team_execution``).
    It also gates the ultracode RISK SUPPRESSOR below: ``has_infra`` /
    ``has_security`` are ``parse_issue.py`` keyword matches (mention, not touch),
    so on a docs change they are false positives that must not block an ultracode
    fan-out any more than they force team-execution.

    ``adversarial_confidence`` (default False) is the second ultracode trigger
    beside ``broad_independent_fanout``: prove-by-refutation / judge-panel /
    perspective-diverse verification is an ultracode shape (deterministic
    INDEPENDENT verification, not merely breadth). Advisory consensus rides the
    same branch. Without either, "stress-test this from many angles" work with no
    deploy/security signal would fall to inline.

    ``alternatives`` lists every *reachable* backend (capability-gated by
    ``workflow_available``) computed INDEPENDENTLY of which backend won
    precedence, so an overlap job (e.g. GATED ``needs_consensus`` AND
    ``broad_independent_fanout``) recommends ``team-execution`` yet still lists
    ``cc-workflows-ultracode`` in ``alternatives`` — escalation stays one
    keystroke (operator-choice section 3.3).
    """

    gated_consensus = needs_consensus and consensus_is_gated
    advisory_consensus = needs_consensus and not consensus_is_gated
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
        or gated_consensus
    )
    # The risk suppressor only bites when there is a real code/scanner surface:
    # has_infra / has_security are keyword matches that false-positive on docs.
    elevated_risk = (has_security or has_infra or deployment_sensitive) and has_code_surface
    ultracode = (
        broad_independent_fanout or adversarial_confidence or advisory_consensus
    ) and not elevated_risk

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


# Orchestration tiers, ordered from the most-capable (dynamic workflows, Claude Code
# only) down to the always-runnable inline baseline. Capability-portable degradation
# (R11) only ever recompiles DOWN this ladder — a host that cannot run dynamic
# workflows still runs team-execution or, at the floor, the inline/serial baseline.
# The enum strings are the frozen wire contract (mirrors saga.py ORCHESTRATION_MODES).
ORCHESTRATION_TIERS = ("cc-workflows-ultracode", "team-execution", "inline")

# Only the dynamic-workflow tier needs the Workflow tool. team-execution and inline
# run on any host, so an off-host resume only ever downgrades AWAY from this one tier.
_HOST_DEPENDENT_TIERS = frozenset({"cc-workflows-ultracode"})


def recheck_orchestration_capability(
    *,
    orchestration_mode: str,
    workflow_available: bool,
    fallback_mode: str = "team-execution",
) -> dict[str, object]:
    """Re-check host capability on resume and recompile ONLY the orchestration tier (R11).

    Capability-portable degradation. Every authored plan carries a runnable inline/serial
    baseline; the dynamic-workflow layer applies only on a capable host. On an off-host
    resume the Workflow tool is re-checked here; if the chosen tier is host-dependent
    (``cc-workflows-ultracode``) and the host cannot run it, this recompiles ONLY the
    orchestration tier DOWN the :data:`ORCHESTRATION_TIERS` ladder. The unit specs and
    per-unit ``{model, effort}`` tiers are NOT touched here — they survive the recompile
    untouched (that preservation is the emitter's job; this function decides the new
    orchestration tier and the human-readable downgrade note).

    ``fallback_mode`` is the preferred landing tier when a downgrade is needed (default
    ``team-execution``, the next rung down — still parallel/gated, just host-portable).
    If the caller asks for a fallback that is itself host-dependent or unknown, this floors
    to ``inline`` — the always-runnable baseline — rather than picking another tier that
    might also be unavailable.

    AE3 contract — this NEVER errors and NEVER silently runs nothing:

    * **Host CAN run the chosen tier** (``workflow_available`` True, or the mode is not
      host-dependent): ``downgraded=False``, ``to == orchestration_mode`` — run as authored.
    * **Host CANNOT run the chosen tier**: ``downgraded=True``, ``to`` is a runnable tier
      (never empty), and ``note`` is a one-line, surfaceable downgrade message.
    * **Unknown / empty mode**: treated as the inline baseline — ``downgraded=False``,
      ``to == "inline"`` — never an exception, never an empty target.

    Returns a JSON-serializable dict::

        {
          "downgraded": bool,
          "from": <the mode as resumed>,       # echoed input
          "to": <the runnable orchestration tier>,   # NEVER empty
          "note": <one-line downgrade note, or ""> ,
          "workflow_available": bool,           # echoed capability probe
        }
    """

    resumed = orchestration_mode or "inline"

    # An unknown stored mode is floored to the inline baseline rather than trusted — a
    # host that cannot identify the tier still runs SOMETHING (AE3: never run nothing).
    if resumed not in ORCHESTRATION_TIERS:
        return {
            "downgraded": False,
            "from": resumed,
            "to": "inline",
            "note": "",
            "workflow_available": workflow_available,
        }

    host_can_run = workflow_available or resumed not in _HOST_DEPENDENT_TIERS
    if host_can_run:
        # The authored tier is runnable here — no downgrade, run as authored.
        return {
            "downgraded": False,
            "from": resumed,
            "to": resumed,
            "note": "",
            "workflow_available": workflow_available,
        }

    # Off-host: recompile the orchestration tier DOWN. Prefer the requested fallback, but
    # only if it is itself a runnable (host-portable, known) tier; otherwise floor to
    # inline — never land on another host-dependent tier that might also be unavailable.
    if fallback_mode in ORCHESTRATION_TIERS and fallback_mode not in _HOST_DEPENDENT_TIERS:
        target = fallback_mode
    else:
        target = "inline"

    note = (
        f"Downgraded orchestration {resumed} -> {target}: the Workflow tool is "
        f"unavailable on this host. Unit specs and per-unit tiers preserved; only "
        f"the orchestration tier recompiled."
    )
    return {
        "downgraded": True,
        "from": resumed,
        "to": target,
        "note": note,
        "workflow_available": workflow_available,
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
    backend.add_argument(
        "--advisory-consensus",
        action="store_true",
        help="treat the consensus signal as ADVISORY (throwaway votes) -> ultracode, not gated team-execution",
    )
    backend.add_argument("--broad-fanout", action="store_true")
    backend.add_argument("--adversarial-confidence", action="store_true")
    backend.add_argument("--no-code-surface", action="store_true")
    backend.add_argument("--no-workflow", action="store_true")

    recheck = subparsers.add_parser(
        "recheck-capability",
        help="re-check host capability on resume and recompile the orchestration tier (R11)",
    )
    recheck.add_argument(
        "--orchestration-mode",
        default="inline",
        help="the tier as resumed (cc-workflows-ultracode|team-execution|inline)",
    )
    recheck.add_argument(
        "--no-workflow",
        action="store_true",
        help="the Workflow tool is unavailable on this host (off-host resume)",
    )
    recheck.add_argument(
        "--fallback-mode",
        default="team-execution",
        help="preferred landing tier on a downgrade (default: team-execution; floors to inline)",
    )

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
            consensus_is_gated=not args.advisory_consensus,
            broad_independent_fanout=args.broad_fanout,
            adversarial_confidence=args.adversarial_confidence,
            has_code_surface=not args.no_code_surface,
            workflow_available=not args.no_workflow,
        )
        print(json.dumps(result))
        return 0
    if args.command == "recheck-capability":
        result = recheck_orchestration_capability(
            orchestration_mode=args.orchestration_mode,
            workflow_available=not args.no_workflow,
            fallback_mode=args.fallback_mode,
        )
        print(json.dumps(result))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
