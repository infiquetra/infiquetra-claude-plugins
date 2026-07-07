#!/usr/bin/env python3
"""Empty-delivery HALT at the delegated-unit boundary (plan U5, R7, KTD6).

A delegated unit that claims delivery (produced a patch/output the chaperone is
about to apply and commit) but changed zero paths in the working tree is a
silent no-op masquerading as done work. This module is a pure verdict function
plus a thin CLI wrapper — it never commits anything itself and mints no new
auto-commit machinery. It only *gates* the chaperone's existing, documented
commit step (see `external-engine-workers.md` §5 "Apply"): a HALT verdict means
the chaperone must stop and surface the halt instead of proceeding to that
step; a proceed verdict authorizes the chaperone to continue to it.

This is distinct from `manifest_store.py`'s `missing-output` trip
(`manifest_store.py:249-363`), which checks the *returned-value* axis (did the
engine hand back evidence at all). This module checks the *file-delivery* axis
(did the working tree actually change) and does not touch `manifest_store.py`.
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
import sys
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryVerdict:
    """Typed verdict for the empty-delivery check.

    ``halt`` is True only when the unit claimed delivery but zero paths
    changed. ``reason`` is a short human-readable explanation. ``changed_path_
    count`` and ``claims_delivery`` are echoed back for caller logging/tests.
    """

    halt: bool
    reason: str
    changed_path_count: int
    claims_delivery: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "halt": self.halt,
            "reason": self.reason,
            "changed_path_count": self.changed_path_count,
            "claims_delivery": self.claims_delivery,
        }


def check_empty_delivery(changed_paths: Sequence[str], claims_delivery: bool) -> DeliveryVerdict:
    """Pure verdict: HALT iff delivery is claimed and zero paths changed.

    A unit that never claimed delivery in the first place (a legitimately
    read-only unit — e.g. a survey/investigation pass) is never HALTed here
    regardless of how many paths changed.
    """

    count = len(changed_paths)
    if claims_delivery and count == 0:
        return DeliveryVerdict(
            halt=True,
            reason=(
                "unit claims delivery but changed zero paths — empty delivery at the "
                "delegated-unit boundary (R7); halting before the chaperone-owned commit step"
            ),
            changed_path_count=count,
            claims_delivery=claims_delivery,
        )
    if claims_delivery:
        reason = f"delivery claimed and {count} path(s) changed — proceed to commit step"
    else:
        reason = "no delivery claimed — read-only unit, nothing to gate"
    return DeliveryVerdict(
        halt=False,
        reason=reason,
        changed_path_count=count,
        claims_delivery=claims_delivery,
    )


def _parse_porcelain_z(raw: bytes) -> list[str]:
    """Parse ``git status --porcelain -z`` output into a list of changed paths."""

    if not raw:
        return []
    # NUL-separated records; rename/copy entries carry two path segments back
    # to back (old NUL new) with no distinguishing marker in this stream other
    # than the leading status codes — for our purposes (a boolean "did the
    # tree change") counting every non-empty NUL-delimited record is correct
    # and doesn't require distinguishing renames from ordinary edits.
    tokens = raw.decode("utf-8", errors="surrogateescape").split("\0")
    return [t for t in tokens if t]


def git_status_changed_paths(cwd: str | None = None) -> list[str]:
    """Return changed paths from ``git status --porcelain -z``.

    Raises ``RuntimeError`` with a clean message (not a stack trace) when run
    outside a git repository or when git is unavailable.
    """

    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", "status", "--porcelain", "-z"],
            check=False,
            capture_output=True,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git executable not found") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"not a git repository (or git failed): {stderr or 'unknown error'}")

    return _parse_porcelain_z(result.stdout)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--claims-delivery",
        action="store_true",
        help="the unit claims it delivered file changes",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="directory to run git status in (defaults to current directory)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        changed_paths = git_status_changed_paths(cwd=args.cwd)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    verdict = check_empty_delivery(changed_paths, args.claims_delivery)
    print(json.dumps(verdict.to_dict(), indent=2, sort_keys=True))
    return 1 if verdict.halt else 0


if __name__ == "__main__":
    sys.exit(main())
