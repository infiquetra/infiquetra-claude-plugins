#!/usr/bin/env python3
"""Canonical outcome spec + DAG validator (OutcomeOrchestrator U1, KTD1/KTD2 keystone).

The `OutcomeOrchestrator` drives a whole **outcome** across sessions, worktrees, and
machines as a DAG of leaf sagas. This module is the spec at the root of that layer: a
canonical JSON document, a **superset of** ``execution_spec.ExecutionSpec`` in spirit
(same pure-function, ``from_dict``/``to_dict``/``validate`` house pattern) but modelling a
*concurrent DAG of subplots* rather than one linear unit list.

Two facts make this layer net-new rather than a reuse of ``Saga``/``ExecutionSpec``:

* The outcome is a **coordinator** over leaf sagas (R1/R2) — the linear ``Saga`` dataclass
  cannot model a concurrent DAG, and ``ExecutionSpec`` models a single session's unit fan-out,
  not a cross-session subplot graph with negative terminal states.
* The node schema captures the **operational state machine in data** (KTD2): ``state``,
  liveness (``timeout_seconds``/``heartbeat_seconds``), negative-state hooks (``github``,
  ``worktree``), and the parent->child link (``child_spec_ref``) live on the node so the
  reconcile loop (U3) is level-triggered and holds no authoritative in-memory DAG (R29).

Canonical placement (KTD1/R26): ``docs/outcomes/<outcome-id>/outcome-spec.json`` on the
outcome's own branch ``outcome/<slug>``. The committed spec is canonical for **structure +
decision-trail + cost**; GitHub is canonical for **completion**; the git-common-dir cache
(U2) is performance-only. JSON (not Markdown front-matter) is canonical so the round-trip is
deterministic and the repo's JSON-parser tests apply (KTD1 rejected Markdown + SQLite).

House testability pattern (mirrors ``execution_spec.py`` / ``saga.py``): pure functions, no
I/O at import, dataclasses with explicit ``from_dict`` so a JSON/branch-authored spec
round-trips deterministically and offline.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Current on-disk schema version. Bumped only on a breaking spec-shape change so an old
# committed spec can be migrated rather than silently mis-read (R26 store-by-facet).
SCHEMA_VERSION = 1

# A subplot_id is an identifier (interpolated raw into markdown tables, Mermaid node ids, and paths),
# so it must be a slug — letters, digits, dot, underscore, hyphen — never prose with spaces/pipes.
_SLUG = re.compile(r"[A-Za-z0-9._-]+")

# Closed node vocabularies. The validator does not invent values; it only checks that an
# authored node draws from these sets so a typo ("done!", "subagnt") fails validate rather
# than silently flowing into the reconcile loop as an unknown state/backend.

# A subplot is code-bearing (its completion contract is a merged PR, R11) or non-code (its
# contract is a durable completion tick + a canonical GitHub/spec marker, KTD4).
NODE_KINDS = ("code", "non-code")

# The operational state machine (KTD2). These are the states the reconcile loop transitions a
# node through; the negative terminal states (R32) are what let an outcome survive a closed
# PR / deleted branch / removed worktree / hung leaf without corrupting the DAG.
NODE_STATES = (
    "pending",  # declared, dependencies not yet all satisfied
    "ready",  # dependencies satisfied, awaiting dispatch (the frontier)
    "dispatched",  # handed to a backend; leaf saga minted
    "running",  # leaf executing
    "blocked",  # an upstream dependency paused/failed; this node waits (R22 cascade)
    "merging",  # code leaf is in the auto-merge queue (U6)
    "done",  # terminal SUCCESS — completion contract satisfied (R11)
    "failed",  # terminal-but-retryable failure (returns to leaf `work`, R12 conflict path)
    "rejected",  # terminal NEGATIVE — e.g. PR closed unmerged, branch deleted (R32)
    "stalled",  # terminal NEGATIVE — liveness timeout with no heartbeat (R31)
    "paused",  # operator- or cascade-paused; not yet terminal
)

# Terminal states unlock (or permanently close) a node for the parent barrier (U5). A code
# leaf unlocks dependents only from ``done``; the negative terminals cascade per R22/R32.
TERMINAL_STATES = frozenset({"done", "failed", "rejected", "stalled"})
SUCCESS_STATES = frozenset({"done"})

# The full executor menu (R6). ``cc-workflows-ultracode`` and ``goal``/``fork`` are
# host-dependent (degrade may drop them, KTD9); ``team-execution`` and ``inline`` always run.
NODE_BACKENDS = (
    "inline",
    "fork",
    "subagent",
    "team-execution",
    "cc-workflows-ultracode",
    "goal",
    "manual",
)

# Degrade policy per node (KTD9), enforced in the degrade path (U9), NOT in
# ``recompile_for_tier`` (the verified correction: that function is a by-mode dispatcher).
# ``halt`` — a guarantee-bearing leaf halts rather than degrade; ``operator_away_one_rung`` —
# an autonomous pre-side-effect leaf may drop one rung; ``none`` — no degrade constraint.
DEGRADE_POLICIES = ("halt", "operator_away_one_rung", "none")


class OutcomeSpecError(ValueError):
    """An outcome spec that violates a structural invariant or is malformed.

    Raised at ``validate`` time so a mis-built spec fails loudly **before any dispatch**
    (R20 review-before-dispatch / R31 DAG validation). Carrying the offending ``subplot_id``
    in the message keeps the failure actionable for ``/outcome`` and the decompose flow (U7).
    """


@dataclass
class Node:
    """One subplot in the outcome DAG — a node that maps to one leaf saga (or a child outcome).

    The node carries the **operational state machine in data** (KTD2): its lifecycle
    ``state``, the ``backend`` that runs it, the risk flags that gate degrade (``gated`` /
    ``risky`` / ``destructive`` / ``guarantee_tags`` / ``degrade_policy``), liveness budgets
    (``timeout_seconds`` / ``heartbeat_seconds``), its dependency barriers (``depends_on``),
    and the links out to its leaf saga (``leaf_saga_id``) or, when the node is itself an
    outcome, to its child spec (``child_spec_ref``, KTD10). ``github`` / ``worktree`` /
    ``evidence`` / ``cost`` are open pass-through maps whose detailed schemas land in the
    units that consume them (U5/U6/U7/U10) — kept open here so U1 does not pre-constrain them.
    """

    subplot_id: str
    title: str
    kind: str = "code"
    state: str = "pending"
    backend: str = "inline"
    gated: bool = False
    risky: bool = False
    destructive: bool = False
    guarantee_tags: list[str] = field(default_factory=list)
    degrade_policy: str = "none"
    timeout_seconds: int | None = None
    heartbeat_seconds: int | None = None
    depends_on: list[str] = field(default_factory=list)
    # The leaf saga this subplot dispatches to (set at dispatch time; empty before).
    leaf_saga_id: str = ""
    # A typed parent->child link (KTD10): when set, THIS node is itself an outcome and the
    # reconcile loop recurses. Distinct from ``leaf_saga_id`` and from saga's single-saga
    # ``orchestration_ref`` — never overload the latter (the rejected type-unsafe alternative).
    child_spec_ref: str = ""
    github: dict[str, Any] = field(default_factory=dict)
    worktree: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_outcome(self) -> bool:
        """True iff this node is itself a (child) outcome — reconcile recurses (KTD10)."""
        return bool(self.child_spec_ref)

    def validate(self, where: str, *, outcome_id: str) -> None:
        if not self.subplot_id:
            raise OutcomeSpecError(f"{where}: a node needs a non-empty subplot_id")
        sid = self.subplot_id
        # A subplot_id is an IDENTIFIER, not prose: it must be a slug (``[A-Za-z0-9._-]+``). It is
        # interpolated raw into a markdown table cell and a Mermaid node id (U8 report/topology), where
        # a ``|`` / space / backtick / newline would corrupt the render — and into store/worktree paths.
        # Constrain it at the source so a mis-drafted (e.g. LLM-authored) id fails ``validate`` BEFORE any
        # dispatch (R31), rather than silently breaking a downstream surface.
        if not _SLUG.fullmatch(sid):
            raise OutcomeSpecError(
                f"node {sid!r}: subplot_id must be a slug (letters, digits, '.', '_', '-')"
            )
        if self.kind not in NODE_KINDS:
            raise OutcomeSpecError(f"node {sid}: kind {self.kind!r} not in {NODE_KINDS}")
        if self.state not in NODE_STATES:
            raise OutcomeSpecError(f"node {sid}: state {self.state!r} not in {NODE_STATES}")
        if self.backend not in NODE_BACKENDS:
            raise OutcomeSpecError(f"node {sid}: backend {self.backend!r} not in {NODE_BACKENDS}")
        if self.degrade_policy not in DEGRADE_POLICIES:
            raise OutcomeSpecError(
                f"node {sid}: degrade_policy {self.degrade_policy!r} not in {DEGRADE_POLICIES}"
            )
        for label, value in (
            ("timeout_seconds", self.timeout_seconds),
            ("heartbeat_seconds", self.heartbeat_seconds),
        ):
            if value is not None and value <= 0:
                raise OutcomeSpecError(f"node {sid}: {label}={value} must be > 0 or null")
        if sid in self.depends_on:
            # Self-dependency: a node can never become ready (it waits on itself). Caught
            # explicitly so the message is precise rather than surfacing as a generic cycle.
            raise OutcomeSpecError(f"node {sid}: depends_on itself (self-dependency)")
        if self.child_spec_ref:
            # KTD10: a child outcome is a DISTINCT outcome. It may not point back at the
            # parent outcome (self-recursion) or carry its own subplot id. The deeper
            # cross-spec ancestor-cycle check needs ancestor context and lands with the
            # promote flow (U7); the local, dispatch-blocking constraints are checked here.
            if self.child_spec_ref == outcome_id:
                raise OutcomeSpecError(
                    f"node {sid}: child_spec_ref {self.child_spec_ref!r} points at its own "
                    f"parent outcome (self-recursion) — a child outcome must be distinct"
                )
            if self.child_spec_ref == sid:
                raise OutcomeSpecError(
                    f"node {sid}: child_spec_ref equals the node's own subplot_id"
                )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        subplot_id = str(data.get("subplot_id", ""))
        where = f"node {subplot_id or '<unnamed>'}"
        return cls(
            subplot_id=subplot_id,
            title=str(data.get("title", subplot_id)),
            kind=str(data.get("kind", "code")),
            state=str(data.get("state", "pending")),
            backend=str(data.get("backend", "inline")),
            gated=bool(data.get("gated", False)),
            risky=bool(data.get("risky", False)),
            destructive=bool(data.get("destructive", False)),
            guarantee_tags=_str_list(
                data.get("guarantee_tags"), where=where, field_name="guarantee_tags"
            ),
            degrade_policy=str(data.get("degrade_policy", "none")),
            timeout_seconds=_opt_int(data.get("timeout_seconds")),
            heartbeat_seconds=_opt_int(data.get("heartbeat_seconds")),
            depends_on=_str_list(data.get("depends_on"), where=where, field_name="depends_on"),
            leaf_saga_id=str(data.get("leaf_saga_id", "")),
            child_spec_ref=str(data.get("child_spec_ref", "")),
            # deepcopy the open pass-through maps so the Node owns a detached snapshot — a
            # caller that later mutates the source ``data`` cannot reach in and corrupt the
            # node's nested structures (and vice-versa for ``to_dict``).
            github=copy.deepcopy(dict(data.get("github", {}))),
            worktree=copy.deepcopy(dict(data.get("worktree", {}))),
            evidence=copy.deepcopy(dict(data.get("evidence", {}))),
            cost=copy.deepcopy(dict(data.get("cost", {}))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_id": self.subplot_id,
            "title": self.title,
            "kind": self.kind,
            "state": self.state,
            "backend": self.backend,
            "gated": self.gated,
            "risky": self.risky,
            "destructive": self.destructive,
            "guarantee_tags": list(self.guarantee_tags),
            "degrade_policy": self.degrade_policy,
            "timeout_seconds": self.timeout_seconds,
            "heartbeat_seconds": self.heartbeat_seconds,
            "depends_on": list(self.depends_on),
            "leaf_saga_id": self.leaf_saga_id,
            "child_spec_ref": self.child_spec_ref,
            # deepcopy so the returned dict is a detached snapshot: editing the serialized
            # output never leaks back into the live Node (the aliasing the finding flagged).
            "github": copy.deepcopy(self.github),
            "worktree": copy.deepcopy(self.worktree),
            "evidence": copy.deepcopy(self.evidence),
            "cost": copy.deepcopy(self.cost),
        }


@dataclass
class OutcomeSpec:
    """The canonical outcome document the OutcomeOrchestrator owns (KTD1).

    Superset-of-``ExecutionSpec`` in pattern, but the unit of work is a ``Node`` (subplot) in
    a concurrent DAG, and the spec additionally carries the canonical ``decision_trail`` (R26,
    the "why" that keeps cold re-entry non-lossy) and the ``cost_rollup`` (R24). ``nodes`` is
    the structural source of truth — sub-issues are GENERATED from it (no node/edge drift).
    """

    outcome_id: str
    objective: str
    nodes: list[Node] = field(default_factory=list)
    spec_revision: int = 1
    schema_version: int = SCHEMA_VERSION
    # The canonical decision trail (R26): append-only records of why the structure changed.
    # Open-shape dict entries (e.g. {"at", "kind", "subplot_id", "why"}) — kept canonical in
    # the committed spec so cold re-entry reconstructs the "why" with no cache (KTD5/F5).
    decision_trail: list[dict[str, Any]] = field(default_factory=list)
    # The cost rollup (R24). Populated by U10; empty here renders as "no data yet" (U8), never
    # a fabricated zero.
    cost_rollup: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def node_by_id(self, subplot_id: str) -> Node | None:
        for node in self.nodes:
            if node.subplot_id == subplot_id:
                return node
        return None

    def bump_revision(self, *, reason: str = "", at: str = "") -> int:
        """Increment ``spec_revision`` and record a decision-trail entry (R26).

        Every STRUCTURAL change must bump the revision so a stale reader/cache detects drift
        and re-derives. In U1 the only structural mutation is an edge redirect
        (``redirect_dependency``); node add/prune and promote land with the decompose flow
        (U7) and will bump through here too. Returns the new revision.
        """
        self.spec_revision += 1
        entry: dict[str, Any] = {"revision": self.spec_revision, "reason": reason}
        if at:
            entry["at"] = at
        self.decision_trail.append(entry)
        return self.spec_revision

    def redirect_dependency(
        self, subplot_id: str, old_dep: str, new_dep: str, *, at: str = ""
    ) -> None:
        """Redirect one dependency edge of a node and bump ``spec_revision`` (R21 versioning).

        An edge redirect is a structural mutation, so on success it bumps the revision (the
        test oracle: a redirect increments ``spec_revision``). The redirected node and the
        ``old_dep`` endpoint must exist, and the result must still pass ``validate`` (no
        cycle/self-dep/undeclared target introduced).

        **Atomic**: the redirect is applied to a snapshot and validated *before* the revision
        is bumped. A rejected redirect leaves the canonical spec — ``depends_on``,
        ``spec_revision``, and the append-only ``decision_trail`` — completely untouched, so a
        caller that catches ``OutcomeSpecError`` never ends up with a bumped revision and a
        decision-trail entry that lies about a change that was rejected (R26 canonical
        fidelity). The deeper "which edits are legal once a leaf is dispatched" and orphan
        *reconciliation* halves of R33 are state-aware and land with the decompose flow (U7).
        """
        node = self.node_by_id(subplot_id)
        if node is None:
            raise OutcomeSpecError(f"redirect_dependency: node {subplot_id!r} is not declared")
        if old_dep not in node.depends_on:
            raise OutcomeSpecError(
                f"redirect_dependency: node {subplot_id!r} does not depend on {old_dep!r}"
            )
        prior = list(node.depends_on)
        node.depends_on = [new_dep if d == old_dep else d for d in node.depends_on]
        try:
            self.validate()
        except OutcomeSpecError:
            node.depends_on = prior  # roll back; never advance revision/trail for a rejection
            raise
        self.bump_revision(reason=f"redirect {subplot_id}:{old_dep}->{new_dep}", at=at)

    def validate(self) -> None:
        """Validate the whole outcome spec — fail loudly BEFORE any dispatch (R20/R31).

        Enforces only the HARD, dispatch-blocking invariants, in order: non-empty
        ``outcome_id`` + ``objective``; at least one node; unique ``subplot_id``; per-node
        validity (closed vocabularies, self-dep, local ``child_spec_ref`` constraints); no
        ``child_spec_ref`` colliding with a declared sibling ``subplot_id``; every
        ``depends_on`` resolves to a declared node; and the graph is acyclic (Kahn).

        Graph DISCONNECTION is deliberately NOT a hard failure: an outcome may legitimately
        fan out into several independent workstreams under the objective (a pipeline plus an
        independent "update the changelog" subplot is a valid DAG). The "forgot to wire it in"
        smell is surfaced as a non-fatal advisory by ``structural_warnings`` instead, so it is
        reported consistently for a lone isolate AND a multi-node island without blocking a
        legitimate spec.
        """
        if not self.outcome_id:
            raise OutcomeSpecError("outcome spec needs a non-empty outcome_id")
        if not self.objective:
            raise OutcomeSpecError("outcome spec needs a non-empty objective")
        if not self.nodes:
            raise OutcomeSpecError("outcome spec needs at least one node")

        seen: set[str] = set()
        for node in self.nodes:
            node.validate(f"outcome {self.outcome_id}", outcome_id=self.outcome_id)
            if node.subplot_id in seen:
                raise OutcomeSpecError(f"duplicate subplot_id {node.subplot_id!r}")
            seen.add(node.subplot_id)

        for node in self.nodes:
            # A child_spec_ref must name a DISTINCT child outcome, never a sibling subplot in
            # THIS spec (a purely local fact, both ids present here — not a deferred cross-spec
            # check). The == own-subplot_id / == parent outcome_id cases already failed above.
            if node.child_spec_ref and node.child_spec_ref in seen:
                raise OutcomeSpecError(
                    f"node {node.subplot_id}: child_spec_ref {node.child_spec_ref!r} collides "
                    f"with a declared sibling subplot_id — a child outcome must be distinct"
                )
            for dep in node.depends_on:
                if dep not in seen:
                    raise OutcomeSpecError(
                        f"node {node.subplot_id}: depends_on {dep!r} is not a declared node"
                    )

        # Acyclicity (Kahn). A cycle has no valid layering -> fail validate (R31).
        dependency_layers(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeSpec:
        if "nodes" not in data or not isinstance(data["nodes"], list):
            raise OutcomeSpecError("outcome spec needs a 'nodes' list")
        return cls(
            outcome_id=str(data.get("outcome_id", "")),
            objective=str(data.get("objective", "")),
            nodes=[Node.from_dict(n) for n in data["nodes"]],
            spec_revision=_positive_int(data.get("spec_revision", 1), field_name="spec_revision"),
            schema_version=_positive_int(
                data.get("schema_version", SCHEMA_VERSION), field_name="schema_version"
            ),
            decision_trail=[copy.deepcopy(dict(d)) for d in data.get("decision_trail", [])],
            cost_rollup=copy.deepcopy(dict(data.get("cost_rollup", {}))),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outcome_id": self.outcome_id,
            "spec_revision": self.spec_revision,
            "objective": self.objective,
            "nodes": [n.to_dict() for n in self.nodes],
            "decision_trail": [copy.deepcopy(dict(d)) for d in self.decision_trail],
            "cost_rollup": copy.deepcopy(self.cost_rollup),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        """Deterministic JSON (stable key order, trailing newline) for the committed artifact."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> OutcomeSpec:
        return cls.from_dict(json.loads(text))


def _opt_int(value: Any) -> int | None:
    """Coerce an optional integer field; ``None``/absent stays ``None``.

    Rejects ``bool`` and non-``int`` values loudly rather than coercing. A JSON ``true`` would
    otherwise become ``1`` (a silent 1-second liveness budget) while ``false`` becomes ``0``
    and is rejected — inconsistent handling of the same type error; a float like ``1.9`` would
    silently truncate to ``1`` and lose data in a doc advertised as deterministic. Both fail
    here, consistent with the module's closed-vocabulary, fail-on-typo discipline (R31).
    """
    if value is None:
        return None
    # ``bool`` is an ``int`` subclass, so check it FIRST or ``True``/``False`` slip through.
    if isinstance(value, bool):
        raise OutcomeSpecError(f"expected an integer or null, got bool {value!r}")
    if not isinstance(value, int):
        raise OutcomeSpecError(f"expected an integer or null, got {value!r}")
    return value


def _str_list(value: Any, *, where: str, field_name: str) -> list[str]:
    """Coerce a JSON list-of-strings field, rejecting a bare string.

    A JSON author who writes ``"depends_on": "a"`` (a string) instead of ``["a"]`` would
    otherwise have the string silently character-iterated into corrupted single-character
    edges (``"ab"`` -> ``["a", "b"]``) that can pass ``validate`` and feed the reconcile-loop
    frontier wrong edges. Any non-list value fails loudly here. ``None``/absent -> ``[]``.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise OutcomeSpecError(
            f"{where}: {field_name} must be a list, got {type(value).__name__} {value!r}"
        )
    return [str(v) for v in value]


def _positive_int(value: Any, *, field_name: str) -> int:
    """Coerce a required positive integer counter (revision / schema version), rejecting < 1.

    ``spec_revision`` and ``schema_version`` are monotonic drift-detectors (R26): a stale
    reader/cache compares revisions to know it must re-derive. A negative or zero seed is a
    latent footgun, so it fails at ``from_dict`` rather than validating clean.
    """
    if isinstance(value, bool):
        raise OutcomeSpecError(f"{field_name} must be a positive integer, got bool {value!r}")
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise OutcomeSpecError(f"{field_name} must be a positive integer, got {value!r}") from exc
    if ivalue < 1:
        raise OutcomeSpecError(f"{field_name} must be >= 1, got {ivalue}")
    return ivalue


# ---------------------------------------------------------------------------
# Topological dependency layering (Kahn) — the frontier engine for the reconcile loop
# ---------------------------------------------------------------------------


def dependency_layers(spec: OutcomeSpec) -> list[list[str]]:
    """Compute topological layers (Kahn) of subplot ids ready to run together.

    A parallel reimplementation of the same Kahn algorithm as
    ``execution_spec.dependency_layers``, keyed on ``Node.subplot_id`` / ``Node.depends_on``
    rather than reusing it — the two are deliberately divergent: ``execution_spec`` adds an
    implicit ``pilot`` barrier edge (an execution-session concept the outcome layer has no
    notion of), so they are NOT one shared engine and must not be assumed to agree. Each
    returned layer is a list of subplot ids whose dependencies are all satisfied by earlier
    layers; the reconcile loop (U3) intersects a layer with the not-yet-done set to derive the
    live frontier each tick.

    Raises ``OutcomeSpecError`` on a cycle (the remaining un-layered subplots are named) or on
    a ``depends_on`` id that resolves to no declared node. Within a layer, ids keep declaration
    order for deterministic emission.
    """
    ids = [n.subplot_id for n in spec.nodes]
    id_set = set(ids)

    preds: dict[str, set[str]] = {sid: set() for sid in ids}
    for node in spec.nodes:
        for dep in node.depends_on:
            if dep not in id_set:
                raise OutcomeSpecError(
                    f"node {node.subplot_id}: depends_on {dep!r} is not a declared node"
                )
            preds[node.subplot_id].add(dep)

    layers: list[list[str]] = []
    placed: set[str] = set()
    remaining = list(ids)  # declaration order preserved
    while remaining:
        ready = [sid for sid in remaining if preds[sid] <= placed]
        if not ready:
            raise OutcomeSpecError(
                f"dependency cycle among subplots: {', '.join(sorted(remaining))}"
            )
        layers.append(ready)
        placed.update(ready)
        remaining = [sid for sid in remaining if sid not in placed]

    return layers


def ready_frontier(spec: OutcomeSpec, completed: set[str]) -> list[str]:
    """The live frontier: not-yet-completed subplots whose deps are all in ``completed``.

    This is the level-triggered read the reconcile loop performs each tick (R29) — it derives
    what is dispatchable purely from the spec + the completion set, holding no in-memory DAG.
    Subplots already in ``completed`` are excluded (they have unlocked, not re-dispatch).
    """
    frontier: list[str] = []
    for node in spec.nodes:
        if node.subplot_id in completed:
            continue
        if all(dep in completed for dep in node.depends_on):
            frontier.append(node.subplot_id)
    return frontier


def _weakly_connected_components(spec: OutcomeSpec) -> list[set[str]]:
    """Weakly-connected components of the subplot graph (dependency edges as undirected).

    Components are returned in node-declaration order (the first component contains the
    earliest-declared node, etc.) so any rendering of them is deterministic.
    """
    ids = [n.subplot_id for n in spec.nodes]
    id_set = set(ids)
    adj: dict[str, set[str]] = {sid: set() for sid in ids}
    for node in spec.nodes:
        for dep in node.depends_on:
            if dep in id_set:
                adj[node.subplot_id].add(dep)
                adj[dep].add(node.subplot_id)

    components: list[set[str]] = []
    unvisited = set(ids)
    for sid in ids:  # declaration order -> deterministic component ordering
        if sid not in unvisited:
            continue
        stack = [sid]
        comp: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in unvisited:
                unvisited.discard(cur)
                comp.add(cur)
                stack.extend(adj[cur])
        components.append(comp)
    return components


def structural_warnings(spec: OutcomeSpec) -> list[str]:
    """Non-fatal structural smells — advisory only, never dispatch-blocking.

    ``validate`` enforces only the hard, dispatch-blocking invariants. Disconnection is NOT
    one of them: an outcome may legitimately fan out into several independent workstreams
    under the objective (a pipeline plus an independent "update the changelog" subplot is a
    valid DAG, and so is a pure no-edge fan-out). But a graph that splits into MORE THAN ONE
    weakly-connected component is *often* the "forgot to wire it in" authoring error (R33), so
    it is surfaced here for ``/outcome`` to show — consistently for a lone degree-0 isolate
    AND a multi-node island, which the earlier degree-0-only check handled inconsistently
    (false-positiving the isolate while silently passing the island). Dynamic orphan
    *reconciliation* (a node stranded by a later edit — close the sub-issue, reap the
    worktree, reconcile cost) is the state-aware runtime half of R33 and lands with the
    decompose/promote flow (U7).
    """
    components = _weakly_connected_components(spec)
    if len(components) <= 1:
        return []
    groups = "; ".join("{" + ", ".join(sorted(c)) + "}" for c in components)
    return [
        f"graph has {len(components)} disconnected components: {groups} — if these are not "
        f"intended as independent workstreams under the objective, an edge may be missing"
    ]


# ---------------------------------------------------------------------------
# CLI — validate / layers (testable, no I/O at import)
# ---------------------------------------------------------------------------


def _load_spec(path: str) -> OutcomeSpec:
    return OutcomeSpec.from_json(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate / inspect an outcome spec.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a spec JSON file")
    p_validate.add_argument("path")

    p_layers = sub.add_parser("layers", help="print topological layers of a spec")
    p_layers.add_argument("path")

    args = parser.parse_args(argv)
    try:
        spec = _load_spec(args.path)
        if args.command == "validate":
            spec.validate()
            print(
                json.dumps(
                    {
                        "valid": True,
                        "outcome_id": spec.outcome_id,
                        "nodes": len(spec.nodes),
                        "spec_revision": spec.spec_revision,
                        # Non-fatal structural smells (e.g. disconnected components). Empty
                        # when the graph is clean; surfaced so `/outcome` can warn without
                        # blocking a legitimately multi-workstream spec.
                        "warnings": structural_warnings(spec),
                    }
                )
            )
            return 0
        if args.command == "layers":
            spec.validate()
            print(json.dumps({"layers": dependency_layers(spec)}))
            return 0
    except OutcomeSpecError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
