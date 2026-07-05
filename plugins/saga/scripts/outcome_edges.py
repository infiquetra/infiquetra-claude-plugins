#!/usr/bin/env python3
"""outcome_edges — pure edge inference for /outcome --from-objective ingestion (#375 U2).

Maps GitHub blocked-by relationships (normalized as a per-sub-issue ``blocked_by: [number,...]`` list
by ``discover_subissues``) into ``depends_on`` edges among the ingested sub-issue set. Keeps only edges
whose both endpoints are ingested, and skips any edge that would close a cycle — so the produced graph
always passes ``OutcomeSpec.validate()``'s declared-target + Kahn acyclicity checks (#375 KTD3).

Pure function of its input; no I/O, no GitHub calls — fully fixture-testable.
"""

from __future__ import annotations

from typing import Any


def _sid(number: int) -> str:
    """The slug subplot_id for a sub-issue number (mirrors the ingestion assembler)."""
    return f"sub-{number}"


def edges_from_relationships(
    subissues: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    """Derive ``depends_on`` edges from each sub-issue's ``blocked_by`` list.

    ``a`` ``blocked_by`` ``b`` means ``a`` depends on ``b`` (``b`` must complete first). Returns
    ``(depends_on_by_subplot, dropped)`` where ``depends_on_by_subplot`` maps a subplot_id to its sorted
    dependency subplot_ids, and ``dropped`` lists ``{reason, from, to}`` for every edge not kept:

    - ``dangling`` — ``blocked_by`` references a number not in the ingested set.
    - ``self``     — a sub-issue blocked by itself.
    - ``cycle``    — the edge would close a dependency cycle (any length), so it is dropped and reported
                     rather than left to fail ``validate`` downstream (#375 AC6/KTD3).
    """
    ingested = {s["number"] for s in subissues}
    dropped: list[dict[str, str]] = []
    deps: dict[str, set[str]] = {}

    def _reachable(start: str, target: str) -> bool:
        """True iff ``target`` is reachable from ``start`` following existing ``deps`` edges."""
        stack = [start]
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(deps.get(node, ()))
        return False

    for sub in subissues:
        a = sub["number"]
        for b in sub.get("blocked_by", []) or []:
            if b not in ingested:
                dropped.append({"reason": "dangling", "from": _sid(a), "to": f"sub-{b}"})
                continue
            if b == a:
                dropped.append({"reason": "self", "from": _sid(a), "to": _sid(a)})
                continue
            fa, fb = _sid(a), _sid(b)
            # Adding "fa depends_on fb" closes a cycle iff fb can already reach fa via deps.
            if _reachable(fb, fa):
                dropped.append({"reason": "cycle", "from": fa, "to": fb})
                continue
            deps.setdefault(fa, set()).add(fb)

    depends_on_by_subplot = {sid: sorted(targets) for sid, targets in deps.items()}
    return depends_on_by_subplot, dropped
