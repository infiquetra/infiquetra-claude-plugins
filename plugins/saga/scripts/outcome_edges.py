#!/usr/bin/env python3
"""outcome_edges — pure edge inference for /outcome --from-objective ingestion (#375 U2).

Maps GitHub blocked-by relationships (normalized as per-sub-issue ``blocked_by`` entries by
``discover_subissues``) into ``depends_on`` edges among the ingested sub-issue set. Entries may be
legacy bare numbers or typed ``{"repo": "owner/name", "number": N}`` references. Keeps only edges
whose both endpoints are ingested and unambiguous, and skips any edge that would close a cycle — so
the produced graph always passes ``OutcomeSpec.validate()``'s declared-target + Kahn acyclicity checks
(#375 KTD3).

Pure function of its input; no I/O, no GitHub calls — fully fixture-testable.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


def _number(value: Any) -> int:
    return int(value)


def _repo(value: Any) -> str:
    return str(value or "")


def _repo_slug(repo: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", repo).strip("-").lower()
    return slug or "unknown-repo"


def _sid(number: int, repo: str = "", *, qualified: bool = False) -> str:
    """Return the slug subplot_id for a normalized sub-issue."""
    if qualified:
        return f"sub-{_repo_slug(repo)}-{number}"
    return f"sub-{number}"


def subplot_ids_for_subissues(subissues: list[dict[str, Any]]) -> dict[tuple[str, int], str]:
    """Return the node assembler's canonical ``(repo, number) -> subplot_id`` map.

    Number-only IDs are preserved unless a number appears more than once in the ingested set. When
    that happens, every sub-issue with the duplicated number gets a repo-qualified ID.
    """
    counts = Counter(_number(sub["number"]) for sub in subissues)
    ids: dict[tuple[str, int], str] = {}
    duplicate_ordinals: dict[int, int] = {}
    for sub in subissues:
        number = _number(sub["number"])
        repo = _repo(sub.get("repo"))
        qualified = counts[number] > 1
        sid = _sid(number, repo, qualified=qualified)
        key = (repo, number)
        if key in ids:
            duplicate_ordinals[number] = duplicate_ordinals.get(number, 1) + 1
            sid = f"{sid}-{duplicate_ordinals[number]}"
        ids[key] = sid
    return ids


def _blocked_ref(value: Any) -> tuple[str, int]:
    if isinstance(value, dict):
        return _repo(value.get("repo")), _number(value.get("number"))
    return "", _number(value)


def edges_from_relationships(
    subissues: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    """Derive ``depends_on`` edges from each sub-issue's ``blocked_by`` list.

    ``a`` ``blocked_by`` ``b`` means ``a`` depends on ``b`` (``b`` must complete first). Returns
    ``(depends_on_by_subplot, dropped)`` where ``depends_on_by_subplot`` maps a subplot_id to its sorted
    dependency subplot_ids, and ``dropped`` lists ``{reason, from, to}`` for every edge not kept:

    - ``dangling``  — ``blocked_by`` references a sub-issue not in the ingested set.
    - ``ambiguous`` — a legacy number-only ref points at more than one ingested repo+number issue.
    - ``self``     — a sub-issue blocked by itself.
    - ``cycle``    — the edge would close a dependency cycle (any length), so it is dropped and reported
                     rather than left to fail ``validate`` downstream (#375 AC6/KTD3).
    """
    subplot_ids = subplot_ids_for_subissues(subissues)
    number_to_keys: dict[int, list[tuple[str, int]]] = {}
    for key in subplot_ids:
        number_to_keys.setdefault(key[1], []).append(key)
    dropped: list[dict[str, str]] = []
    deps: dict[str, set[str]] = {}

    def _resolve_ref(value: Any) -> tuple[tuple[str, int] | None, str]:
        repo, number = _blocked_ref(value)
        if repo:
            key = (repo, number)
            return (key, "") if key in subplot_ids else (None, "dangling")
        candidates = number_to_keys.get(number, [])
        if len(candidates) == 1:
            return candidates[0], ""
        if len(candidates) > 1:
            return None, "ambiguous"
        return None, "dangling"

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
        a_key = (_repo(sub.get("repo")), _number(sub["number"]))
        fa = subplot_ids[a_key]
        for b in sub.get("blocked_by", []) or []:
            b_key, error = _resolve_ref(b)
            b_repo, b_number = _blocked_ref(b)
            to = subplot_ids.get((b_repo, b_number), _sid(b_number))
            if error:
                dropped.append({"reason": error, "from": fa, "to": to})
                continue
            assert b_key is not None
            fb = subplot_ids[b_key]
            if b_key == a_key:
                dropped.append({"reason": "self", "from": fa, "to": fb})
                continue
            # Adding "fa depends_on fb" closes a cycle iff fb can already reach fa via deps.
            if _reachable(fb, fa):
                dropped.append({"reason": "cycle", "from": fa, "to": fb})
                continue
            deps.setdefault(fa, set()).add(fb)

    depends_on_by_subplot = {sid: sorted(targets) for sid, targets in deps.items()}
    return depends_on_by_subplot, dropped
