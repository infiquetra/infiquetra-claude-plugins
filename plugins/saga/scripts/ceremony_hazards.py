#!/usr/bin/env python3
"""ceremony_hazards.py — hazard registry + ``detect()`` preflight for ship_ceremony.py
(issue #346, U1).

``ship_ceremony.py``'s ``run()`` executes the next unrun transition with no look at
the world beyond the saga ledger: ``branch_delete`` deletes the recorded branch
checking only that its name is non-empty and not ``main``, and nothing detects a
stacked-PR topology (an open child PR based on the branch about to be deleted) or
distinguishes "merge confirmably landed" from "delete request arrived before the
merge landed" (the raw gh auto-merge/branch-delete flag reorder hazard, issue #346). This
module is the pure, runner-injectable probe layer ``run()`` consults before those two
``always_operator``-tier transitions dispatch (KTD2) — it never mutates anything and
never advances ceremony state itself.

House testability pattern (mirrors ``ship_ceremony.py`` / ``outcome_store.py``): every
function that shells out takes a ``runner`` callable, defaulted to
``subprocess.run`` resolved at call time (never bound as a default argument), so
tests can pass a fake runner directly.

Fail-loud contract: a probe that cannot complete (non-zero exit, unparseable JSON)
raises ``HazardProbeError`` — ``detect()`` never swallows a probe failure into an
empty (i.e. "clean") result. Reversible transitions are not gated at all (R1/R2/U1
Behavior) and ``detect()`` returns ``[]`` for them without issuing any ``gh`` call —
no added latency on the steps that were never at risk.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PR_NUMBER_RE = re.compile(r"[0-9]+")

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class HazardError(Exception):
    """Base error for ceremony_hazards.py."""


class HazardProbeError(HazardError):
    """A ``gh`` probe failed (non-zero exit or unparseable JSON) — detect() never
    returns an empty list as if the topology were clean when a probe itself failed;
    it raises instead (fail-loud, U1 Behavior)."""


# --------------------------------------------------------------------------- #
# Hazard dataclass + ordered registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Hazard:
    """A single detected hazard. ``acknowledgeable=False`` hazards (currently just
    ``merge_not_landed``, KTD3) can never be bypassed via ``--acknowledge-hazard`` —
    they resolve only by the underlying condition actually changing."""

    hazard_id: str
    transition: str
    message: str
    remedy: str
    acknowledgeable: bool


# Canonical hazard ids, in registry order (KTD3 / U1 test_hazard_ordering_is_registry_order).
# ``run()``'s ``--acknowledge-hazard`` flag draws its ``choices`` from this tuple.
STACKED_PR = "stacked_pr"
MERGE_NOT_LANDED = "merge_not_landed"

HAZARD_REGISTRY: tuple[str, ...] = (STACKED_PR, MERGE_NOT_LANDED)

# Transitions this module gates at all (R1/R2/U1 Behavior: "Non-gated transitions
# return [] without probing"). Any transition not in this set costs zero ``gh``
# latency in detect().
GATED_TRANSITIONS: frozenset[str] = frozenset({"merge", "branch_delete"})


# --------------------------------------------------------------------------- #
# Subprocess helper — runner injectable, never bound as a default argument
# (mirrors ship_ceremony.py's ``_run``, kept module-local per U1 "Depends on:
# nothing" — this module must not import ship_ceremony.py).
# --------------------------------------------------------------------------- #


def _run(
    cmd: Sequence[str],
    *,
    cwd: Path,
    runner: Callable[..., Any] | None = None,
) -> subprocess.CompletedProcess[str]:
    run = runner if runner is not None else subprocess.run
    result = run(  # nosec B603 — fixed argv, no shell
        list(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if getattr(result, "returncode", 1) != 0:
        raise HazardProbeError(
            f"{' '.join(cmd)} failed (exit {result.returncode}): "
            f"{(getattr(result, 'stderr', '') or '').strip()}"
        )
    return result


def _run_gh_json(args: Sequence[str], *, repo_root: Path, runner: Callable[..., Any] | None) -> Any:
    result = _run(["gh", *args], cwd=repo_root, runner=runner)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HazardProbeError(
            f"gh {' '.join(args)} returned unparseable JSON: {result.stdout!r}"
        ) from exc


def _pr_number(pr_ref: str) -> str:
    """``pr_refs`` entries are stored as ``#123`` or a full URL; extract the number.
    Mirrors ``ship_ceremony.py``'s ``_pr_number`` (duplicated, not imported — U1
    "Depends on: nothing")."""
    return pr_ref.rsplit("/", 1)[-1].lstrip("#")


def _current_pr_number(saga: Mapping[str, Any]) -> str | None:
    refs = saga.get("pr_refs") or []
    if not refs:
        return None
    return _pr_number(refs[-1])


# --------------------------------------------------------------------------- #
# Individual probes — each returns a Hazard or None
# --------------------------------------------------------------------------- #


def _probe_stacked_pr(
    saga: Mapping[str, Any],
    *,
    transition: str,
    repo_root: Path,
    runner: Callable[..., Any] | None,
) -> Hazard | None:
    """Probes for an open PR based on the branch about to be deleted (branch_delete)
    or merged (merge) — R1 / U1 Behavior."""
    branch = str(saga.get("branch") or "")
    if not branch:
        return None
    stacked = _run_gh_json(
        ["pr", "list", "--base", branch, "--state", "open", "--json", "number,title"],
        repo_root=repo_root,
        runner=runner,
    )
    if not stacked:
        return None
    listing = ", ".join(f"#{pr['number']} {pr.get('title', '')}".strip() for pr in stacked)
    return Hazard(
        hazard_id=STACKED_PR,
        transition=transition,
        message=f"branch {branch!r} has open PR(s) based on it: {listing}",
        remedy=(
            "close or rebase the stacked PR(s) onto the ceremony PR's target, or "
            f"acknowledge with --acknowledge-hazard {STACKED_PR}"
        ),
        acknowledgeable=True,
    )


def _probe_merge_not_landed(
    saga: Mapping[str, Any],
    *,
    transition: str,
    repo_root: Path,
    runner: Callable[..., Any] | None,
) -> Hazard | None:
    """Probes the ceremony PR's live state before letting ``branch_delete`` run —
    R2, the raw gh auto-merge/branch-delete flag reorder hazard. Not
    acknowledgeable (KTD3): it resolves only by the merge actually landing."""
    pr_number = _current_pr_number(saga)
    if pr_number is None:
        # No PR recorded yet — branch_delete this early is already going to fail
        # its own sanity checks downstream; nothing to probe here.
        return None
    if not _PR_NUMBER_RE.fullmatch(pr_number):
        # Fail-loud, never fail-quiet: a garbled pr_refs entry must not read as
        # "no hazard" (and must never reach gh argv).
        raise HazardProbeError(
            f"pr_refs entry yields pr_number {pr_number!r}, not a plain PR number; "
            "refusing to probe with it"
        )
    pr = _run_gh_json(
        ["pr", "view", pr_number, "--json", "state,mergedAt"],
        repo_root=repo_root,
        runner=runner,
    )
    if pr.get("state") == "MERGED" and pr.get("mergedAt"):
        return None
    return Hazard(
        hazard_id=MERGE_NOT_LANDED,
        transition=transition,
        message=f"PR #{pr_number} has not confirmably merged (state={pr.get('state')!r})",
        remedy="wait for the merge to land (or resolve via ship --undo); not acknowledgeable",
        acknowledgeable=False,
    )


# Per-transition probe pipelines, in registry order (KTD3 ordering contract).
_PROBES_BY_TRANSITION: Mapping[str, tuple[Callable[..., Hazard | None], ...]] = {
    "branch_delete": (_probe_stacked_pr, _probe_merge_not_landed),
    "merge": (_probe_stacked_pr,),
}


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def detect(
    saga: Mapping[str, Any],
    upcoming: str,
    repo_root: Path,
    runner: Callable[..., Any] | None = None,
) -> list[Hazard]:
    """Probe live ``gh`` state for hazards on the upcoming transition.

    Non-gated transitions (anything outside ``GATED_TRANSITIONS``) return ``[]``
    without issuing any ``gh`` call. Gated transitions run their probe pipeline in
    ``HAZARD_REGISTRY`` order; a probe that raises propagates immediately —
    ``detect()`` never catches a probe failure and reports it as "no hazards".
    """
    probes = _PROBES_BY_TRANSITION.get(upcoming)
    if not probes:
        return []
    hazards: list[Hazard] = []
    for probe in probes:
        hazard = probe(saga, transition=upcoming, repo_root=repo_root, runner=runner)
        if hazard is not None:
            hazards.append(hazard)
    return hazards
