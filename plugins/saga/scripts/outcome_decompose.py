#!/usr/bin/env python3
"""Decomposition, in-flight graph editing, and orphan reconciliation (U7).

The runner **drafts** a subplot DAG and the operator **reviews** it before anything dispatches — the
mandatory safety net for a mis-drafted graph (R20). This module owns the structural mutation half of
that flow + the in-flight edit *rules* (R33): the four growth mechanisms (draft/prune, lazy-grow,
elaborate-in-place, promote — each a distinct operation with its own edge cases, R21), the
**state-aware** legality of an edit once a leaf is dispatched, and **orphan reconciliation** (a pruned /
re-elaborated node closes its generated sub-issue and reaps its worktree rather than leaving zombies).

Three invariants this module enforces structurally:

* **Every mutation is atomic** (the U1 ``redirect_dependency`` shape, generalized): mutate a snapshot,
  ``validate``, and only **then** bump ``spec_revision`` + append the decision trail. A rejected edit
  (cycle / self-dep / dangling edge / cross-spec cycle) leaves the canonical spec — ``nodes``,
  ``depends_on``, ``spec_revision``, ``decision_trail`` — completely untouched (R26 canonical fidelity).
* **Edits are state-aware** (R33): a node already **dispatched** (in-flight) cannot be silently pruned
  or elaborated — that requires a terminal transition first — while an **undispatched** node edits
  freely. Legality is read from the live derived state (R17), never a stored scalar.
* **No layer dispatches before approval** (R20): approval is recorded **per ``spec_revision``**, so any
  structural edit (which bumps the revision) **re-closes** the gate until the new frontier's edges are
  re-approved. This ties R20's review-before-dispatch directly to R33's graph versioning.

Side-effecting orphan reconciliation (close the sub-issue, reap the worktree) runs **after** the spec
mutation is committed, through injected adapters, so a rejected edit never closes a live issue, and the
cleanup is best-effort + reported (the canonical prune already succeeded; cleanup is retryable).

House pattern (mirrors ``outcome_spec`` / ``outcome_merge``): pure functions over explicit values +
injected adapters, ``outcome`` imported lazily to avoid a cycle, no I/O at import.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_spec  # noqa: E402  (after the sys.path shim, by design)
import outcome_store  # noqa: E402

# Live derived states that mean "in-flight, handed to a backend" — an edit that would discard work
# silently is illegal against these (R33); a terminal transition must come first.
_IN_FLIGHT = frozenset({"dispatched"})


class DecomposeError(ValueError):
    """A decomposition / graph-edit operation was rejected (an illegal in-flight edit, a cross-spec
    cycle, a missing node). Distinct from ``OutcomeSpecError`` (a structural-validity failure) so a
    caller can tell "you may not edit this *now*" apart from "this graph is malformed"."""


# ---------------------------------------------------------------------------
# Live-state helper (R17 derived-on-read — never a stored scalar)
# ---------------------------------------------------------------------------


def _live_state(spec: Any, store: Any, subplot_id: str) -> str:
    """The node's live derived state (``outcome.derive_states``), imported lazily to avoid a cycle."""
    import outcome as outcome_engine

    return outcome_engine.derive_states(spec, store).get(subplot_id, "")


def _commit(spec: Any, *, reason: str, at: str) -> int:
    """Validate the mutated spec, then bump the revision + trail. Caller must have a rollback ready."""
    spec.validate()
    return spec.bump_revision(reason=reason, at=at)


# ---------------------------------------------------------------------------
# Node + edge edits (atomic snapshot-validate-then-bump)
# ---------------------------------------------------------------------------


def add_node(spec: Any, node_dict: dict[str, Any], *, at: str = "") -> int:
    """Add one declared node. Its ``depends_on`` must resolve (``validate`` enforces). Bumps revision."""
    node = outcome_spec.Node.from_dict(node_dict)
    if spec.node_by_id(node.subplot_id) is not None:
        raise DecomposeError(f"add_node: subplot_id {node.subplot_id!r} already exists")
    spec.nodes.append(node)
    try:
        return _commit(spec, reason=f"add node {node.subplot_id}", at=at)
    except outcome_spec.OutcomeSpecError:
        spec.nodes.pop()  # roll back; never advance revision/trail for a rejected add
        raise


def add_dependency(spec: Any, subplot_id: str, dep: str, *, at: str = "") -> int:
    """Add a dependency edge ``subplot_id -> dep`` (atomic; rejects a cycle/dangling edge)."""
    node = _require_node(spec, subplot_id, "add_dependency")
    if dep in node.depends_on:
        raise DecomposeError(f"add_dependency: {subplot_id!r} already depends on {dep!r}")
    prior = list(node.depends_on)
    node.depends_on = [*node.depends_on, dep]
    try:
        return _commit(spec, reason=f"add edge {subplot_id}->{dep}", at=at)
    except outcome_spec.OutcomeSpecError:
        node.depends_on = prior
        raise


def remove_dependency(spec: Any, subplot_id: str, dep: str, *, at: str = "") -> int:
    """Remove a dependency edge ``subplot_id -> dep`` (atomic). The edge must exist."""
    node = _require_node(spec, subplot_id, "remove_dependency")
    if dep not in node.depends_on:
        raise DecomposeError(f"remove_dependency: {subplot_id!r} does not depend on {dep!r}")
    prior = list(node.depends_on)
    node.depends_on = [d for d in node.depends_on if d != dep]
    try:
        return _commit(spec, reason=f"remove edge {subplot_id}->{dep}", at=at)
    except outcome_spec.OutcomeSpecError:
        node.depends_on = prior
        raise


def lazy_grow(spec: Any, new_node_dicts: Sequence[dict[str, Any]], *, at: str = "") -> int:
    """Append a later layer as evidence arrives (R21 lazy growth) — add nodes that depend on the
    existing graph, in one atomic, validated batch. Distinct from ``elaborate`` (which *splits* a node):
    lazy-grow adds depth/breadth without removing anything. All-or-nothing: a bad batch rolls back fully.
    """
    new_nodes = [outcome_spec.Node.from_dict(d) for d in new_node_dicts]
    existing_ids = {n.subplot_id for n in spec.nodes}
    for n in new_nodes:
        if n.subplot_id in existing_ids:
            raise DecomposeError(f"lazy_grow: subplot_id {n.subplot_id!r} already exists")
        existing_ids.add(n.subplot_id)
    before = list(spec.nodes)
    spec.nodes.extend(new_nodes)
    try:
        return _commit(spec, reason=f"lazy-grow +{len(new_nodes)} nodes", at=at)
    except outcome_spec.OutcomeSpecError:
        spec.nodes[:] = before
        raise


def promote(
    spec: Any, subplot_id: str, child_spec_ref: str, *, ancestors: Sequence[str] = (), at: str = ""
) -> int:
    """Promote a cheap subplot row to its own child saga (R21): set its ``child_spec_ref``.

    The cross-spec **cycle guard** (R20/R31): a child outcome may not point back at THIS outcome or any
    **ancestor** outcome in the chain (``ancestors`` = the parent outcome ids), which would make the
    recursion non-terminating. The local constraints (== own subplot_id, == a sibling subplot_id, ==
    this outcome_id) are enforced by ``validate``; this adds the deferred ancestor check U1 named.

    NOTE on the ``/outcome promote`` CLI: it promotes a node in a single spec and has **no
    nested-outcome traversal yet**, so it cannot supply ``ancestors`` — from the CLI only the
    immediate ``== this outcome_id`` self-cycle is caught here (deeper ancestor cycles are not, because
    no ancestor chain exists to check against). An actual *runtime* infinite recursion is still
    prevented downstream by the ``seen``-set guard in ``outcome.production_harvester``'s
    ``child_state_reader``. The full ancestor chain becomes available — and gets threaded in here — when
    the cross-outcome traversal lands (U8 projection / a future nested-advance); until then the CLI gap
    is deliberate, not silent.
    """
    node = _require_node(spec, subplot_id, "promote")
    if not child_spec_ref:
        raise DecomposeError("promote: child_spec_ref must be non-empty")
    forbidden = set(ancestors) | {spec.outcome_id}
    if child_spec_ref in forbidden:
        raise DecomposeError(
            f"promote: child_spec_ref {child_spec_ref!r} points at an ancestor outcome "
            f"({sorted(forbidden)}) — a cross-spec cycle (R20/R31)"
        )
    prior = node.child_spec_ref
    node.child_spec_ref = child_spec_ref
    try:
        return _commit(spec, reason=f"promote {subplot_id} -> child {child_spec_ref}", at=at)
    except outcome_spec.OutcomeSpecError:
        node.child_spec_ref = prior
        raise


def elaborate(
    spec: Any,
    store: Any,
    subplot_id: str,
    child_node_dicts: Sequence[dict[str, Any]],
    *,
    at: str = "",
) -> int:
    """Split an over-sized **undispatched** subplot in place into sub-nodes (R21 elaborate-in-place).

    State-aware (R33): elaborating a node that has already **dispatched** would discard in-flight work,
    so it is rejected — only an undispatched node may be elaborated. The splice is deterministic:

    * the elaborated node's **upstream** (its ``depends_on``) is inherited by every sub-node that has no
      authored predecessor among the sub-nodes (the entries);
    * every node that depended on the elaborated node is rewired to depend on the sub-nodes that no
      other sub-node depends on (the sinks);
    * the elaborated node is removed and the sub-nodes added — atomically (validate-then-bump; a bad
      split rolls the whole spec back).
    """
    node = _require_node(spec, subplot_id, "elaborate")
    state = _live_state(spec, store, subplot_id)
    if state in _IN_FLIGHT:
        raise DecomposeError(
            f"elaborate: {subplot_id!r} is {state!r} (in-flight) — elaborate only before dispatch "
            f"(R33); transition it to terminal first, or add fresh nodes via lazy_grow"
        )
    if state in outcome_spec.TERMINAL_STATES:
        raise DecomposeError(
            f"elaborate: {subplot_id!r} is already {state!r} (terminal) — elaborate is only valid "
            f"before dispatch (R33); add fresh nodes via lazy_grow instead"
        )
    sub_nodes = [outcome_spec.Node.from_dict(d) for d in child_node_dicts]
    if not sub_nodes:
        raise DecomposeError(f"elaborate: {subplot_id!r} needs at least one sub-node")

    sub_ids = {n.subplot_id for n in sub_nodes}
    upstream = list(node.depends_on)
    # Entries = sub-nodes with no predecessor among the sub-nodes -> inherit the elaborated upstream
    # (deduped, so an entry that already declares one of the inherited deps does not get a doubled edge).
    for sn in sub_nodes:
        if not any(d in sub_ids for d in sn.depends_on):
            sn.depends_on = [*upstream, *(d for d in sn.depends_on if d not in upstream)]
    # Sinks = sub-nodes no other sub-node depends on -> the elaborated node's dependents rewire here.
    depended_on = {d for sn in sub_nodes for d in sn.depends_on if d in sub_ids}
    sinks = [sn.subplot_id for sn in sub_nodes if sn.subplot_id not in depended_on]

    before_nodes = list(spec.nodes)
    before_edges = {n.subplot_id: list(n.depends_on) for n in spec.nodes}
    # Remove the elaborated node; rewire its dependents onto the sinks; append the sub-nodes.
    spec.nodes[:] = [n for n in spec.nodes if n.subplot_id != subplot_id]
    for n in spec.nodes:
        if subplot_id in n.depends_on:
            rewired = [d for d in n.depends_on if d != subplot_id]
            for sink in sinks:
                if sink not in rewired:
                    rewired.append(sink)
            n.depends_on = rewired
    spec.nodes.extend(sub_nodes)
    try:
        return _commit(spec, reason=f"elaborate {subplot_id} -> {sorted(sub_ids)}", at=at)
    except outcome_spec.OutcomeSpecError:
        spec.nodes[:] = before_nodes
        for n in spec.nodes:
            n.depends_on = before_edges.get(n.subplot_id, n.depends_on)
        raise


# ---------------------------------------------------------------------------
# Prune + orphan reconciliation (R33 — close the sub-issue, reap the worktree, no zombies)
# ---------------------------------------------------------------------------


def prune(
    spec: Any,
    store: Any,
    subplot_id: str,
    *,
    issue_close: Callable[[str], bool] | None = None,
    worktree_ops: Any | None = None,
    at: str = "",
) -> dict[str, Any]:
    """Remove a node + drop every edge to it (atomic), then reconcile its orphans (R33).

    **State-aware** (R33): a node that is **dispatched** (in-flight) may not be pruned — pruning a live
    leaf would silently discard its in-flight work — so it must reach a terminal state first. An
    **undispatched** node prunes freely; a **terminal** node (``done`` / ``failed`` / ``rejected`` /
    ``stalled``) also prunes freely as **explicit operator abandonment** — note a ``failed`` leaf is
    terminal-but-retryable (it would otherwise return to ``work``), so pruning it is the operator
    deciding to abandon that retry; that is a deliberate `/outcome prune`, not a silent discard. The spec
    mutation is atomic (validate-then-bump; a rejected prune leaves the spec untouched). **Then** orphan
    reconciliation runs (best-effort, after the canonical prune is committed, so a rejected prune never
    closes a live issue):

    * close the node's generated GitHub sub-issue (``issue_close(ref)``) if it has one (U8 generates the
      ref; U7 closes it on prune);
    * reap the node's worktree (``outcome_worktrees.reap_worktree``) if ``worktree_ops`` is given;
    * report which dependents were orphaned (their edge to the pruned node was dropped).

    Returns a reconcile summary so ``/outcome`` can show exactly what was cleaned up.
    """
    node = _require_node(spec, subplot_id, "prune")
    state = _live_state(spec, store, subplot_id)
    if state in _IN_FLIGHT:
        raise DecomposeError(
            f"prune: {subplot_id!r} is {state!r} (in-flight) — prune needs a terminal transition "
            f"first (R33); cannot silently discard a dispatched leaf's work"
        )

    dependents = [n.subplot_id for n in spec.nodes if subplot_id in n.depends_on]
    before_nodes = list(spec.nodes)
    before_edges = {n.subplot_id: list(n.depends_on) for n in spec.nodes}
    spec.nodes[:] = [n for n in spec.nodes if n.subplot_id != subplot_id]
    for n in spec.nodes:
        if subplot_id in n.depends_on:
            n.depends_on = [d for d in n.depends_on if d != subplot_id]
    try:
        _commit(spec, reason=f"prune {subplot_id}", at=at)
    except outcome_spec.OutcomeSpecError:
        spec.nodes[:] = before_nodes
        for n in spec.nodes:
            n.depends_on = before_edges.get(n.subplot_id, n.depends_on)
        raise

    # --- orphan reconciliation (best-effort; the canonical prune already succeeded) ---
    summary: dict[str, Any] = {
        "pruned": subplot_id,
        "spec_revision": spec.spec_revision,
        "dependents_orphaned": sorted(dependents),
        "closed_issue": None,
        "reaped_worktree": False,
    }
    issue_ref = str(node.github.get("issue", "") or node.github.get("sub_issue", ""))
    if issue_ref and issue_close is not None and issue_close(issue_ref):
        summary["closed_issue"] = issue_ref
    if worktree_ops is not None:
        import outcome_worktrees

        summary["reaped_worktree"] = outcome_worktrees.reap_worktree(
            store, subplot_id, worktree_ops, at=at
        )
    return summary


def _require_node(spec: Any, subplot_id: str, where: str) -> Any:
    node = spec.node_by_id(subplot_id)
    if node is None:
        raise DecomposeError(f"{where}: node {subplot_id!r} is not declared")
    return node


# ---------------------------------------------------------------------------
# Approval gate (R20 — no layer dispatches before the operator approves the frontier's edges)
# ---------------------------------------------------------------------------


def _approvals_dir(store: Any) -> Path:
    return store.root / "approvals"


def approve_frontier(store: Any, spec: Any, *, at: str = "") -> int:
    """Record the operator's approval of the current ``spec_revision``'s frontier (R20). Idempotent.

    Approval is keyed by revision, so it is **consumed** by the next structural edit (which bumps the
    revision) — re-approval is then required before the new frontier dispatches. Returns the approved
    revision.
    """
    rev = spec.spec_revision
    d = _approvals_dir(store)
    d.mkdir(parents=True, exist_ok=True)
    outcome_store._write_once(
        d / f"r{rev}.json", json.dumps({"spec_revision": rev, "at": at}) + "\n"
    )
    return rev


def frontier_approved(store: Any, spec_revision: int) -> bool:
    """Whether the operator has approved the given ``spec_revision``'s frontier (R20 dispatch gate)."""
    return (_approvals_dir(store) / f"r{spec_revision}.json").exists()


def make_dispatch_gate(store: Any, spec: Any) -> Callable[[str], bool]:
    """The dispatch gate ``advance``/``_reconcile_once`` consults: a leaf may dispatch only once the
    **current** ``spec_revision``'s frontier is approved (R20). A structural edit bumps the revision and
    re-closes the gate, so a mis-drafted edit can never auto-dispatch before re-review.
    """
    rev = spec.spec_revision

    def _gate(_subplot_id: str) -> bool:
        return frontier_approved(store, rev)

    return _gate


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Outcome decomposition / graph-edit rules (U7) — describe the policy."
    )
    parser.parse_args(argv)
    print(
        json.dumps(
            {
                "mechanisms": ["draft/prune", "lazy-grow", "elaborate-in-place", "promote"],
                "in_flight_rule": "a dispatched node needs a terminal transition before prune/elaborate",
                "orphan_reconcile": "prune closes the sub-issue + reaps the worktree + drops edges",
                "approval": "per spec_revision; a structural edit re-closes the dispatch gate (R20/R33)",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
