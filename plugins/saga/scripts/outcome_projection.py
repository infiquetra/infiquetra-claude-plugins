#!/usr/bin/env python3
"""Mission-control secondary portfolio projection (U8 — R25).

The subplot-DAG progress **auto-projects** into mission-control as a generated **secondary** portfolio
view (R25): no manual ``/handoff``, no hand-authored status. Two invariants this module enforces
structurally:

* **Generated from the spec + store, never hand-authored.** Every field is *computed* (derived-on-read,
  R17) from the committed spec + the completion/dispatch store — there is **no operator-writable status
  field**. The projection a fresh machine produces from the same state is identical; an operator can
  never set a number that lies about the work.
* **It is a SECONDARY view; closing the parent stays an operator keystroke (R25).** The projection
  reports progress and the attention surface, but it never auto-closes the parent issue — that remains
  the operator's deliberate decision (encoded here as ``parent_close = "operator-keystroke-only"`` so a
  downstream mission-control consumer cannot mistake the projection for a close signal).

This module produces the projection *artifact*; the actual mission-control GitHub write is a separate,
operator-initiated consumer (the saga <-> mission-control boundary), so there is no auto-push here.

House pattern (mirrors the other ``outcome_*`` modules): pure functions over explicit values,
``outcome`` imported lazily to avoid a cycle, no I/O at import.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_report  # noqa: E402  (after the sys.path shim, by design)

PROJECTION_SCHEMA = "outcome-projection/1"


def project(spec: Any, store: Any) -> dict[str, Any]:
    """The generated secondary portfolio projection for one outcome (R25) — derived-on-read, no status field.

    Every value is computed from ``spec`` + ``store``: the live state counts (``derive_states``), the
    ready frontier, the blocked set, progress, and the consolidated attention summary (R18). There is no
    field the operator sets; ``parent_close`` is fixed to ``operator-keystroke-only`` so a consumer never
    treats the projection as an auto-close.
    """
    import outcome as outcome_engine
    import reversibility_certificate as _rc  # lazy, certificate is the single authority (R12, AE3)

    states = outcome_engine.derive_states(spec, store)
    counts: dict[str, int] = {}
    for st in states.values():
        counts[st] = counts.get(st, 0) + 1
    done = counts.get("done", 0)
    total = len(spec.nodes)
    items = outcome_report.consolidate(spec, store)
    return {
        "schema": PROJECTION_SCHEMA,
        "outcome_id": spec.outcome_id,
        "objective": spec.objective,
        "spec_revision": spec.spec_revision,
        # display_percent never reads 100 below completion (banker's-rounding would invite a premature
        # parent-close) and never rounds a real-progress outcome down to 0.
        "progress": {
            "done": done,
            "total": total,
            "percent": outcome_report.display_percent(done, total),
        },
        # Live state per node — GENERATED from the store, never a stored/operator-set scalar (R17).
        "states": states,
        "state_counts": counts,
        # The frontier is derived from the SAME states map (not a separate success-only ready_frontier),
        # so a negative-terminal / HALTed node is never re-listed as dispatchable — it stays consistent
        # with its own `states` entry.
        "frontier": sorted(sid for sid, st in states.items() if st == "ready"),
        "blocked": sorted(sid for sid, st in states.items() if st == "blocked"),
        # The attention surface (R18) as a count + the top item, so the portfolio view ranks outcomes.
        "attention": {
            "count": len(items),
            "top": items[0].to_dict() if items else None,
        },
        "complete": done == total,
        # R25/R12: the projection is a SECONDARY view — parent-issue-close is ALWAYS_OPERATOR (GATE)
        # per the certificate, so closing the parent always stays an operator keystroke (AE3).
        "parent_close": (
            "operator-keystroke-only"
            if _rc.authorize_write(_rc.OpKind.PARENT_ISSUE_CLOSE) is _rc.GATE
            else "autonomous"
        ),
        "generated": "derived-on-read from spec + store (no operator-writable status, R17/R25)",
    }


def projection_markdown(spec: Any, store: Any) -> str:
    """A compact human-readable rendering of :func:`project` for a portfolio glance."""
    p = project(spec, store)
    prog = p["progress"]
    att = p["attention"]
    top = att["top"]
    top_line = f"{top['kind']}:{top['subplot_id']}" if top else "none"
    return (
        f"- **{p['outcome_id']}** — {p['objective']} · "
        f"{prog['done']}/{prog['total']} ({prog['percent']}%) · "
        f"attention: {att['count']} (top: {top_line}) · "
        f"{'complete' if p['complete'] else 'in-flight'}\n"
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Outcome mission-control projection (U8/R25) — generated secondary view."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("outcome_id")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)

    import outcome as outcome_engine

    root = Path(args.repo_root).resolve()
    spec = outcome_engine.load_spec(root, args.outcome_id)
    store = outcome_engine._store(root, args.outcome_id)
    if args.markdown:
        print(projection_markdown(spec, store), end="")
    else:
        print(json.dumps(project(spec, store), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
