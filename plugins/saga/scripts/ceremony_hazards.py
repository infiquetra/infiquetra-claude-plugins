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

Issue #635 (U4, R2) adds a third hazard on the same shape: ``branch_delete_targets_base``
fires when the branch ``branch_delete`` is about to delete IS the PR's base branch. It is
the independent second check behind the resolver — the live incident deleted
``outcome/norns-next-horizon`` local and origin because the deletion target came from the
saga's rolling ``branch`` field, and a refusal registered here lands before
``ship_ceremony.run()`` dispatches its runner or saves the tick.

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
    """A single detected hazard. ``acknowledgeable=False`` hazards (``merge_not_landed``
    and ``branch_delete_targets_base``, KTD3) can never be bypassed via
    ``--acknowledge-hazard`` — they resolve only by the underlying condition actually
    changing."""

    hazard_id: str
    transition: str
    message: str
    remedy: str
    acknowledgeable: bool


# Canonical hazard ids, in registry order (KTD3 / U1 test_hazard_ordering_is_registry_order).
# ``run()``'s ``--acknowledge-hazard`` flag draws its ``choices`` from this tuple.
STACKED_PR = "stacked_pr"
MERGE_NOT_LANDED = "merge_not_landed"
BRANCH_DELETE_TARGETS_BASE = "branch_delete_targets_base"

HAZARD_REGISTRY: tuple[str, ...] = (STACKED_PR, MERGE_NOT_LANDED, BRANCH_DELETE_TARGETS_BASE)

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
    resolved_head: str | None = None,
) -> Hazard | None:
    """Probes for an open PR based on the branch about to be deleted (branch_delete)
    or merged (merge) — R1 / U1 Behavior.

    ``resolved_head`` wins over the saga's recorded ``branch`` when the caller supplies
    one (issue #635 code-review). The summary line above is the contract — "the branch
    about to be deleted" — and on a leaf-into-outcome ceremony ``saga["branch"]`` is
    not that branch: it is re-stamped from ``git branch --show-current`` on every tick
    save, so after ``checkout_main`` it names the PR *base*. Probing the base asks the
    wrong question in both directions: a child PR stacked on the real head goes
    undetected and the branch is deleted out from under it, while every sibling leaf
    still open against the base fires a spurious hazard — and this one IS
    acknowledgeable, so spurious firings train the operator to wave it through.

    ``merge`` passes no ``resolved_head`` (only ``branch_delete`` confirms a target),
    so that transition keeps the recorded-branch operand it always had."""
    branch = str(resolved_head or saga.get("branch") or "")
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
    resolved_head: str | None = None,
) -> Hazard | None:
    """Probes the ceremony PR's live state before letting ``branch_delete`` run —
    the raw gh auto-merge/branch-delete flag reorder hazard (issue #346, R2). Not
    acknowledgeable (KTD3): it resolves only by the merge actually landing.

    ``resolved_head`` is part of the uniform probe signature (issue #635/U4) and is
    unused here: PR state, not the deletion target, is what this probe reads."""
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


def _probe_branch_delete_targets_base(
    saga: Mapping[str, Any],
    *,
    transition: str,
    repo_root: Path,
    runner: Callable[..., Any] | None,
    resolved_head: str | None = None,
) -> Hazard | None:
    """Probes whether ``branch_delete``'s target IS the PR's base branch — issue #635,
    R2. Not acknowledgeable (KTD3): there is no legitimate case for deleting the branch
    the ceremony just merged into, so there is nothing an operator could acknowledge.

    The base comes from the PR itself (``baseRefName`` — the shared, externally durable
    record). The head is ``resolved_head`` when the caller supplies one:
    ``ship_ceremony.run()`` passes the value ``resolve_ceremony_refs()`` produced, i.e.
    the branch the runner will actually hand to ``git branch -d`` /
    ``git push origin --delete``.

    **Which rung this protects, stated precisely, because the honest answer is "not all
    of them".** When the resolver answered on rung 1, ``resolved_head`` and ``base``
    both came from the same ``gh pr view --json headRefName,baseRefName`` record, and
    GitHub forbids a same-repo PR whose head IS its base — so on rung 1 the two operands
    cannot be equal and this probe is structurally inert. That is fine: rung 1 is
    authoritative and cannot produce a wrong target in the first place.

    This probe exists for **rung 2**, where the head comes from the opened-resource
    manifest's ``ceremony-branch:`` entry and the base from the PR — two genuinely
    independent records that can agree wrongly. That is the ``outcome/norns-next-horizon``
    incident shape: local ceremony evidence naming the base branch as the head, with a
    destructive ``git branch -d`` downstream of it. See
    ``tests/test_ship_ceremony.py::test_branch_delete_targets_base_fires_on_the_rung_2_incident_topology``
    for the reachable case; the sibling tests that force ``head == base`` on the PR
    record prove the refusal ORDERING, on a topology GitHub cannot actually produce.

    With no ``resolved_head`` supplied it falls back to the PR's own ``headRefName``,
    which keeps a standalone ``detect()`` call meaningful (a fork PR can legitimately
    report head == base) without ever inventing a target.

    An absent or empty ref name never matches: ``"" == ""`` must not read as "the target
    is the base". A missing answer is a missing answer, not a hazard."""
    pr_number = _current_pr_number(saga)
    if pr_number is None:
        # No PR recorded yet — nothing authoritative to compare against; branch_delete
        # this early fails its own downstream checks.
        return None
    if not _PR_NUMBER_RE.fullmatch(pr_number):
        raise HazardProbeError(
            f"pr_refs entry yields pr_number {pr_number!r}, not a plain PR number; "
            "refusing to probe with it"
        )
    pr = _run_gh_json(
        ["pr", "view", pr_number, "--json", "headRefName,baseRefName"],
        repo_root=repo_root,
        runner=runner,
    )
    base = str(pr.get("baseRefName") or "")
    head = str(resolved_head or pr.get("headRefName") or "")
    if not head or not base or head != base:
        return None
    return Hazard(
        hazard_id=BRANCH_DELETE_TARGETS_BASE,
        transition=transition,
        message=(
            f"branch_delete would delete {head!r}, which is PR #{pr_number}'s base branch "
            "— the branch this ceremony merged INTO"
        ),
        remedy=(
            "do not delete the base; re-resolve this ceremony's head (the PR's headRefName "
            "and the opened-resource manifest's ceremony-branch: entry are the only valid "
            "sources) and re-run. Not acknowledgeable"
        ),
        acknowledgeable=False,
    )


# Per-transition probe pipelines, in registry order (KTD3 ordering contract).
_PROBES_BY_TRANSITION: Mapping[str, tuple[Callable[..., Hazard | None], ...]] = {
    "branch_delete": (
        _probe_stacked_pr,
        _probe_merge_not_landed,
        _probe_branch_delete_targets_base,
    ),
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
    *,
    resolved_head: str | None = None,
) -> list[Hazard]:
    """Probe live ``gh`` state for hazards on the upcoming transition.

    Non-gated transitions (anything outside ``GATED_TRANSITIONS``) return ``[]``
    without issuing any ``gh`` call. Gated transitions run their probe pipeline in
    ``HAZARD_REGISTRY`` order; a probe that raises propagates immediately —
    ``detect()`` never catches a probe failure and reports it as "no hazards".

    ``resolved_head`` (issue #635/U4, optional and keyword-only so every existing
    call site is unchanged) is the branch the caller has resolved as this ceremony's
    deletion target. ``branch_delete_targets_base`` compares it against the PR's own
    base, and ``_probe_stacked_pr`` uses it as the branch to ask about.

    That comparison spans two INDEPENDENT records only when the caller resolved on
    rung 2 (manifest head vs PR base). When the caller resolved on rung 1, both
    operands came from one ``gh pr view`` record and the comparison is inert by
    construction — correctly, because rung 1 cannot produce a wrong target. Do not
    restate this as "two derivation paths" without that qualification; it was written
    that way once and was false.
    """
    probes = _PROBES_BY_TRANSITION.get(upcoming)
    if not probes:
        return []
    hazards: list[Hazard] = []
    for probe in probes:
        hazard = probe(
            saga,
            transition=upcoming,
            repo_root=repo_root,
            runner=runner,
            resolved_head=resolved_head,
        )
        if hazard is not None:
            hazards.append(hazard)
    return hazards
