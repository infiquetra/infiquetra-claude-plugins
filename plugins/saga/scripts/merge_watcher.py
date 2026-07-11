#!/usr/bin/env python3
"""merge_watcher.py — deterministic merge expectation (issue #346 U2).

The ceremony's ``merge`` transition used to trust whatever the PR's live state was at
the instant ``gh pr merge`` ran — no distinction between "checks stayed green through
the poll window" and "checks flipped and the merge raced ahead anyway." This module
records a merge *expectation* — head SHA, the full set of check contexts observed,
and the review decision — at PR-open time (KTD1), and offers two verbs to hold a
later merge to that baseline:

* ``validate`` — a point-in-time comparison against live PR state, the hard gate
  wired into ``ship_ceremony.run()``'s merge preflight (R4). Refuses on any named
  divergence: ``head_moved``, ``check_flipped``, ``check_missing``,
  ``review_regressed``, ``pr_not_open``.
* ``watch`` — polls N ticks through an injectable poll source and fails on any tick
  where a previously-passing required check goes non-passing, even if a later tick
  is green again (a mid-poll flip). This is a standalone CLI/library utility, not an
  internal loop wired into ``run()`` — ``run()`` stays single-shot and stateless
  (R4's division of labor).

Storage (KTD1): the expectation is a JSON sidecar at
``.claude/saga/sagas/<saga_id>/merge_expectation.json`` — git-ignored, machine-local,
written directly by this module (never through ``saga.py save``). A missing sidecar
is a named refusal with a remedy (KTD8), never a silent pass. Divergence never
auto-heals (KTD7): ``record --force`` is the only re-baseline path; a plain re-record
over an existing sidecar refuses.

House testability pattern (mirrors ``ship_ceremony.py`` / ``outcome_store.py``): every
function that shells out takes a ``runner`` callable, defaulted to ``subprocess.run``
resolved at call time (never bound as a default argument). No sleeping in library
code — ``watch()``'s core loop never calls ``time.sleep`` itself; a real-world caller
supplies a ``poll_source`` that does its own waiting (see ``_live_poll_source``),
and tests supply an instant, canned one.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Machine-local, git-ignored — sibling of the saga cache (SAGAS_DIR in saga.py) and
# the tier-session override sidecar (tier_session.py:29). No import of saga.py
# itself: this module has no dependency on the saga store (plan U2 — "Depends on:
# nothing"), only on the sidecar directory shape it already establishes.
STATE_DIR = Path(".claude/saga")
SAGAS_DIR = STATE_DIR / "sagas"
SIDECAR_NAME = "merge_expectation.json"

# Divergence kinds (R4) — the full, closed vocabulary MergeExpectationDivergedError.kind
# is drawn from. Kept as a tuple (not an Enum) to match the plain-string vocabulary
# style used by ship_ceremony.CeremonyTier/TRANSITIONS.
DIVERGENCE_KINDS: tuple[str, ...] = (
    "pr_not_open",
    "head_moved",
    "check_missing",
    "check_flipped",
    "review_regressed",
)

# Check conclusions/states treated as "passing" for required-check comparisons.
# Covers both CheckRun (`conclusion`) and legacy StatusContext (`state`) shapes
# gh's statusCheckRollup can emit.
_PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL"})


class MergeWatcherError(Exception):
    """Base error for merge_watcher.py — always caught at the CLI boundary and
    reported as a message, never an uncaught traceback."""


class MergeExpectationAlreadyRecordedError(MergeWatcherError):
    """A ``record`` call found an existing sidecar and ``force`` was not set
    (KTD7 — divergence never auto-heals; ``record --force`` is the only
    re-baseline path)."""


class MergeExpectationMissingError(MergeWatcherError):
    """No ``merge_expectation.json`` sidecar exists for this saga (KTD8 — an
    in-flight ceremony from before this feature, or a deleted sidecar). Carries a
    ``remedy`` naming the ``record`` command so the upgrade path is one command
    long."""

    def __init__(self, saga_id: str) -> None:
        self.saga_id = saga_id
        self.remedy = f"run: python3 merge_watcher.py record --saga-id {saga_id} --pr-number <N>"
        super().__init__(f"no merge_expectation.json recorded for saga {saga_id!r}; {self.remedy}")


class MergeExpectationDivergedError(MergeWatcherError):
    """Live PR state diverged from the recorded expectation. ``kind`` is one of
    ``DIVERGENCE_KINDS``; ``detail`` carries the kind-specific evidence (e.g. the
    expected vs. live SHA, or the check name that flipped)."""

    def __init__(self, kind: str, detail: Mapping[str, Any], *, tick: int | None = None) -> None:
        if kind not in DIVERGENCE_KINDS:
            raise ValueError(f"unrecognized divergence kind {kind!r}; expected {DIVERGENCE_KINDS}")
        self.kind = kind
        self.detail = dict(detail)
        self.tick = tick
        tick_note = f" (tick {tick})" if tick is not None else ""
        super().__init__(f"merge expectation diverged: {kind}{tick_note} — {self.detail}")


# --------------------------------------------------------------------------- #
# Subprocess helper — runner injectable, never bound as a default argument.
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
        raise MergeWatcherError(
            f"{' '.join(cmd)} failed (exit {result.returncode}): "
            f"{(getattr(result, 'stderr', '') or '').strip()}"
        )
    return result


# --------------------------------------------------------------------------- #
# Sidecar path + read/write
# --------------------------------------------------------------------------- #


def sidecar_path(repo_root: Path, saga_id: str) -> Path:
    return repo_root / SAGAS_DIR / saga_id / SIDECAR_NAME


def _read_sidecar(repo_root: Path, saga_id: str) -> dict[str, Any]:
    path = sidecar_path(repo_root, saga_id)
    if not path.exists():
        raise MergeExpectationMissingError(saga_id)
    with open(path, encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def _write_sidecar(repo_root: Path, saga_id: str, expectation: Mapping[str, Any]) -> Path:
    path = sidecar_path(repo_root, saga_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(expectation), indent=2, sort_keys=True) + "\n")
    return path


# --------------------------------------------------------------------------- #
# Live PR state — fetch + normalize gh's statusCheckRollup shapes.
# --------------------------------------------------------------------------- #


def _check_name(entry: Mapping[str, Any]) -> str:
    name = entry.get("name") or entry.get("context")
    if not name:
        raise MergeWatcherError(f"statusCheckRollup entry has no name/context: {entry!r}")
    return str(name)


def _check_passing(entry: Mapping[str, Any]) -> bool:
    conclusion = entry.get("conclusion") or entry.get("state")
    return conclusion in _PASSING_CONCLUSIONS


def normalize_pr_view(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a parsed ``gh pr view --json
    number,state,headRefOid,statusCheckRollup,reviewDecision`` payload into the
    shape both ``validate`` and the default poll source compare against."""
    rollup = raw.get("statusCheckRollup") or []
    checks = {_check_name(entry): _check_passing(entry) for entry in rollup}
    return {
        "pr_number": raw.get("number"),
        "state": raw.get("state"),
        "head_sha": raw.get("headRefOid"),
        "checks": checks,
        "review_state": raw.get("reviewDecision"),
    }


def _fetch_live_state(
    pr_number: int | str, *, repo_root: Path, runner: Callable[..., Any] | None
) -> dict[str, Any]:
    result = _run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,state,headRefOid,statusCheckRollup,reviewDecision",
        ],
        cwd=repo_root,
        runner=runner,
    )
    return normalize_pr_view(json.loads(result.stdout))


# --------------------------------------------------------------------------- #
# record — capture the baseline (R3, KTD1)
# --------------------------------------------------------------------------- #


def record(
    *,
    saga_id: str,
    pr_number: int | str,
    repo_root: Path,
    force: bool = False,
    runner: Callable[..., Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Capture ``{pr_number, head_sha, required_checks, review_state, recorded_at}``
    from live PR state and write it to the sidecar.

    This repository has no branch-protection rules, so there is no API-defined
    "required" check set — ``required_checks`` is the full set of check contexts
    observed at record time, and that recorded set is what ``validate``/``watch``
    hold the merge to.

    Refuses if a sidecar already exists (KTD7) unless ``force`` is set — the only
    re-baseline path, for the legitimate case of a round-N+1 push after review
    changes.
    """
    path = sidecar_path(repo_root, saga_id)
    if path.exists() and not force:
        raise MergeExpectationAlreadyRecordedError(
            f"merge_expectation.json already recorded for saga {saga_id!r}; "
            "pass force=True (--force) to re-baseline, or run 'validate' against "
            "the existing expectation"
        )
    live = _fetch_live_state(pr_number, repo_root=repo_root, runner=runner)
    expectation = {
        "pr_number": live["pr_number"],
        "head_sha": live["head_sha"],
        "required_checks": sorted(live["checks"]),
        "review_state": live["review_state"],
        "recorded_at": now or datetime.now(UTC).isoformat(),
    }
    _write_sidecar(repo_root, saga_id, expectation)
    return expectation


# --------------------------------------------------------------------------- #
# validate — point-in-time hard gate (R4, KTD8)
# --------------------------------------------------------------------------- #


def _compare_snapshot(expectation: Mapping[str, Any], live: Mapping[str, Any]) -> None:
    """Raise ``MergeExpectationDivergedError`` on the first divergence found, checked in
    a fixed, deterministic order so the same input always reports the same kind."""
    if live.get("state") != "OPEN":
        raise MergeExpectationDivergedError(
            "pr_not_open",
            {"expected": "OPEN", "live_state": live.get("state")},
        )
    if live.get("head_sha") != expectation.get("head_sha"):
        raise MergeExpectationDivergedError(
            "head_moved",
            {
                "expected_head_sha": expectation.get("head_sha"),
                "live_head_sha": live.get("head_sha"),
            },
        )
    required = set(expectation.get("required_checks") or [])
    live_checks: Mapping[str, bool] = live.get("checks") or {}
    missing = sorted(required - set(live_checks))
    if missing:
        raise MergeExpectationDivergedError("check_missing", {"missing_checks": missing})
    non_passing = sorted(name for name in required if not live_checks.get(name, False))
    if non_passing:
        raise MergeExpectationDivergedError("check_flipped", {"non_passing_checks": non_passing})
    baseline_review = expectation.get("review_state")
    live_review = live.get("review_state")
    if baseline_review == "APPROVED" and live_review != "APPROVED":
        raise MergeExpectationDivergedError(
            "review_regressed",
            {"expected_review_state": baseline_review, "live_review_state": live_review},
        )


def validate(
    *,
    saga_id: str,
    repo_root: Path,
    pr_number: int | str | None = None,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Re-fetch live PR state and compare it against the recorded expectation.

    Raises ``MergeExpectationMissingError`` (KTD8) if no sidecar exists, or
    ``MergeExpectationDivergedError`` naming the first divergence found. Returns the
    (unmodified) expectation on a clean match.
    """
    expectation = _read_sidecar(repo_root, saga_id)
    live = _fetch_live_state(
        pr_number if pr_number is not None else expectation["pr_number"],
        repo_root=repo_root,
        runner=runner,
    )
    _compare_snapshot(expectation, live)
    return expectation


# --------------------------------------------------------------------------- #
# watch — flip-catching poll window (R4)
# --------------------------------------------------------------------------- #


def _live_poll_source(
    pr_number: int | str,
    *,
    repo_root: Path,
    runner: Callable[..., Any] | None,
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[int], Mapping[str, Any]]:
    """The real, network-talking poll source used by the CLI. Sleeps between ticks
    (never on tick 0) — this IO adapter is deliberately outside ``watch()``'s pure
    loop so the loop itself never sleeps (module docstring)."""

    def _poll(tick: int) -> Mapping[str, Any]:
        if tick > 0 and interval_seconds > 0:
            sleep(interval_seconds)
        return _fetch_live_state(pr_number, repo_root=repo_root, runner=runner)

    return _poll


def watch(
    *,
    saga_id: str,
    repo_root: Path,
    poll_source: Callable[[int], Mapping[str, Any]],
    ticks: int,
) -> dict[str, Any]:
    """Poll ``ticks`` times via the injected ``poll_source(tick_index)`` and fail on
    any tick where a previously-passing required check goes non-passing — even if a
    later tick recovers (R4's mid-poll-flip guarantee). No sleeping happens here;
    any real-world delay between ticks lives entirely inside the caller-supplied
    ``poll_source`` (see ``_live_poll_source``).

    Also raises immediately on ``pr_not_open``, ``head_moved``, or
    ``check_missing`` at any tick — those are unambiguous divergences the instant
    they're observed, not something that needs multiple ticks to confirm.
    ``review_regressed`` is evaluated once, against the final tick's state.
    """
    if ticks < 1:
        raise MergeWatcherError(f"ticks must be >= 1, got {ticks}")
    expectation = _read_sidecar(repo_root, saga_id)
    required = set(expectation.get("required_checks") or [])
    seen_passing: set[str] = set()
    last_live: Mapping[str, Any] | None = None

    for tick in range(ticks):
        live = poll_source(tick)
        last_live = live
        if live.get("state") != "OPEN":
            raise MergeExpectationDivergedError(
                "pr_not_open",
                {"expected": "OPEN", "live_state": live.get("state")},
                tick=tick,
            )
        if live.get("head_sha") != expectation.get("head_sha"):
            raise MergeExpectationDivergedError(
                "head_moved",
                {
                    "expected_head_sha": expectation.get("head_sha"),
                    "live_head_sha": live.get("head_sha"),
                },
                tick=tick,
            )
        live_checks: Mapping[str, bool] = live.get("checks") or {}
        missing = sorted(required - set(live_checks))
        if missing:
            raise MergeExpectationDivergedError(
                "check_missing", {"missing_checks": missing}, tick=tick
            )
        for name in sorted(required):
            passing = bool(live_checks.get(name, False))
            if passing:
                seen_passing.add(name)
            elif name in seen_passing:
                raise MergeExpectationDivergedError(
                    "check_flipped",
                    {"check": name, "was_passing_before_tick": tick},
                    tick=tick,
                )

    baseline_review = expectation.get("review_state")
    live_review = (last_live or {}).get("review_state")
    if baseline_review == "APPROVED" and live_review != "APPROVED":
        raise MergeExpectationDivergedError(
            "review_regressed",
            {"expected_review_state": baseline_review, "live_review_state": live_review},
            tick=ticks - 1,
        )
    return {"saga_id": saga_id, "ticks": ticks, "final_state": dict(last_live or {})}


# --------------------------------------------------------------------------- #
# CLI subcommands
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="repo root (default: cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="capture the merge expectation baseline")
    p_record.add_argument("--saga-id", required=True)
    p_record.add_argument("--pr-number", required=True)
    p_record.add_argument(
        "--force", action="store_true", help="re-baseline over an existing sidecar (KTD7)"
    )

    p_validate = sub.add_parser("validate", help="point-in-time compare live PR state to baseline")
    p_validate.add_argument("--saga-id", required=True)
    p_validate.add_argument(
        "--pr-number", default=None, help="override the PR number recorded in the expectation"
    )

    p_watch = sub.add_parser("watch", help="poll N ticks, catching a mid-poll check flip")
    p_watch.add_argument("--saga-id", required=True)
    p_watch.add_argument("--pr-number", required=True)
    p_watch.add_argument("--ticks", type=int, default=3)
    p_watch.add_argument("--interval-seconds", type=float, default=5.0)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root

    try:
        if args.command == "record":
            result = record(
                saga_id=args.saga_id,
                pr_number=args.pr_number,
                repo_root=repo_root,
                force=args.force,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "validate":
            result = validate(saga_id=args.saga_id, repo_root=repo_root, pr_number=args.pr_number)
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "watch":
            poll_source = _live_poll_source(
                args.pr_number,
                repo_root=repo_root,
                runner=None,
                interval_seconds=args.interval_seconds,
            )
            result = watch(
                saga_id=args.saga_id,
                repo_root=repo_root,
                poll_source=poll_source,
                ticks=args.ticks,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        else:  # pragma: no cover - argparse enforces valid choices
            parser.error(f"unknown command {args.command!r}")
            return 2
    except MergeWatcherError as exc:
        print(f"merge_watcher: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
