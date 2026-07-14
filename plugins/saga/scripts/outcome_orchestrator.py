#!/usr/bin/env python3
"""Parent-owned completion barrier + harvest + cascade (U5).

"Done" in the OutcomeOrchestrator is a **parent-owned barrier predicate over the returned evidence**
(R9), never a child's self-report. This module owns that predicate and the per-subplot completion
**contract** (R11):

* a **code** leaf is done only when its **PR reads merged** (canonical on GitHub, R10/R11);
* a **non-code** leaf is done on its local completion tick **plus** a durable canonical marker — its
  tracking sub-issue reads **closed** (the cache-less-reconstructable path: a fresh machine reading
  GitHub sees it done), or, for untracked local work, a ``canonical``-flagged completion event in the
  store (cache-resident only — a wipe loses it; the committed-spec completion-log path is future);
* a **child-outcome** node (``child_spec_ref``, KTD10) is done only when the child outcome's own
  terminal state reads **successful** — the reconcile recurses into the child rather than reading its
  branch spec across worktrees.

``harvest`` runs the barrier over the whole spec each reconcile tick and **materializes** every
newly-satisfied contract as a success completion event in the store, so the existing frontier read
(``outcome_store.completed_subplots``) unlocks the next Kahn layer (R10) — and a cache-less machine
re-derives the same completions from GitHub. ``blocked_subtree`` is the R22 cascade: only the
downstream subtree of a hard-blocked node pauses; independent siblings keep running.

This module READS GitHub (``outcome_github``); the merge/close *actions* are U6. House pattern: pure
functions over injectable readers, no I/O at import.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import closure_gate  # noqa: E402  (after the sys.path shim, by design)
import intent_envelope  # noqa: E402
import manifest_store  # noqa: E402
import outcome_github  # noqa: E402
import outcome_spec  # noqa: E402
import outcome_store  # noqa: E402

# Per-subplot completion contracts (R11) — the thing the parent barrier verifies.
CONTRACT_CODE = "code:pr-merged"
CONTRACT_NONCODE = "non-code:tick+canonical-marker"
CONTRACT_CHILD = "child-outcome:terminal-success"

# A reader that returns a child outcome's terminal state ("done"/"failed"/"rejected"/.../"unknown")
# given its ``child_spec_ref`` — injected so the recursion is testable without a real child on disk.
ChildStateReader = Callable[[str], str]

# Sentinel: "this leaf has no dispatch-era envelope capture — evaluate under the spec's CURRENT
# intent" (pre-#433 records and never-dispatched leaves). Distinct from a captured None, which
# means "dispatched with NO committed envelope" and implies no checks even if one attaches later.
_CURRENT_INTENT = object()


def _dispatch_era_intents(store: Any) -> dict[str, Any]:
    """Per-subplot campaign envelope in force at each leaf's dispatch (#433 R5).

    Reads each subplot's dispatch records in BOTH phases — the pre-dispatch ``intent`` record
    and the settled ``commit`` record (both capture the same posture snapshot); the latest
    record wins, and a commit record always follows its intent record in ledger order, so the
    settled snapshot governs whenever one exists. The intent phase matters on its own for the
    crash-after-intent window: the backend effect may be live with no commit record ever
    written, and that leaf is in flight for EVERY consumer — the strand check (R6) already
    counts it, and this era map must too, or a loosening repost landing in that window would
    retroactively release the leaf's completion gate at harvest. A record whose ``posture``
    carries the ``"intent"`` key pins that leaf's completion gate to the campaign envelope
    captured at its dispatch — an in-flight leaf finishes under its dispatch-time posture, so
    a later loosening repost (e.g. ``reviews_required`` gate -> auto) never retroactively
    releases its implied closure checks, and a later tightening never retroactively imposes
    new ones. ``"intent": null`` is an explicit capture: dispatched with no committed
    envelope (implies no checks). A record with NO ``"intent"`` key predates dispatch-era
    capture and maps to :data:`_CURRENT_INTENT` (the pre-#433 behavior: the spec's current
    intent governs). Leaves with no dispatch record at all (e.g. externally-completed
    non-code work) are absent from the map — same fallback.
    """
    era: dict[str, Any] = {}
    for rec in outcome_store.read_ledger(store):
        if rec.get("kind") != "dispatch" or rec.get("phase") not in ("intent", "commit"):
            continue
        sid = str(rec.get("subplot_id", ""))
        posture = rec.get("posture")
        if isinstance(posture, dict) and "intent" in posture:
            era[sid] = posture["intent"]
        else:
            era[sid] = _CURRENT_INTENT
    return era


@dataclass
class BarrierVerdict:
    """The parent's verdict on one subplot's completion contract (R9)."""

    subplot_id: str
    satisfied: bool
    contract: str
    state: str  # the canonical state read (merged/closed/open/unknown/done/failed/...)
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_id": self.subplot_id,
            "satisfied": self.satisfied,
            "contract": self.contract,
            "state": self.state,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


def barrier_satisfied(
    node: Any,
    *,
    store: Any,
    github_runner: Callable[..., Any] | None = None,
    child_state_reader: ChildStateReader | None = None,
) -> BarrierVerdict:
    """The parent-owned barrier predicate (R9/R11). Returns satisfied=False (a HALT) on an unmet
    contract — never a child's self-report, always evidence the parent can re-verify on GitHub."""
    sid = node.subplot_id

    if node.is_outcome:  # child_spec_ref -> recurse into the child outcome's terminal state (KTD10)
        child = node.child_spec_ref
        state = child_state_reader(child) if child_state_reader is not None else "unknown"
        ok = state in outcome_spec.SUCCESS_STATES
        return BarrierVerdict(
            sid,
            ok,
            CONTRACT_CHILD,
            state,
            reason=(
                "child outcome terminal-successful" if ok else f"child {child!r} not done ({state})"
            ),
            evidence={"child_spec_ref": child, "child_state": state},
        )

    if node.kind == "code":
        pr = str(node.github.get("pr", ""))
        if not pr:
            return BarrierVerdict(sid, False, CONTRACT_CODE, "open", "no PR ref yet", {})
        state = outcome_github.pr_state(pr, runner=github_runner)
        return BarrierVerdict(
            sid,
            state == "merged",
            CONTRACT_CODE,
            state,
            reason=("PR merged" if state == "merged" else f"PR not merged ({state})"),
            evidence={"pr": pr, "pr_state": state},
        )

    # non-code: the canonical marker must read done so a cache-less machine reconstructs it.
    issue = str(node.github.get("issue", ""))
    if issue:
        marker = outcome_github.issue_state(issue, runner=github_runner)
        return BarrierVerdict(
            sid,
            marker == "closed",
            CONTRACT_NONCODE,
            marker,
            reason=("tracking issue closed" if marker == "closed" else f"tracking issue {marker}"),
            evidence={"issue": issue, "issue_state": marker},
        )
    # No tracking issue: the only marker is a completion event flagged ``canonical`` in the STORE.
    # This is **cache-resident** (NOT on GitHub or the committed spec), so unlike the issue-closed
    # path it is NOT cache-less-reconstructable — a wipe loses it. Acceptable for untracked local
    # non-code work; a cache-less non-code leaf needs a tracking sub-issue. (A committed-spec
    # completion-log marker is the future fully-cache-less path; not yet wired.)
    events = outcome_store.read_completion_events(store, sid)
    canonical = any(e.is_success and bool(e.payload.get("canonical")) for e in events)
    return BarrierVerdict(
        sid,
        canonical,
        CONTRACT_NONCODE,
        "done" if canonical else "open",
        reason=(
            "canonical completion tick recorded" if canonical else "no canonical completion marker"
        ),
        evidence={"has_canonical_event": canonical},
    )


def harvest(
    spec: Any,
    *,
    store: Any,
    github_runner: Callable[..., Any] | None = None,
    child_state_reader: ChildStateReader | None = None,
    at: str = "",
    repo_root: Path = Path("."),
) -> list[str]:
    """Run the barrier over the spec and materialize each newly-satisfied contract as a success
    completion event in the store. Returns the newly-harvested subplot ids (R9/R10/R11).

    Idempotent: a subplot already success-completed in the store is skipped, and the write itself is
    idempotency-keyed, so re-harvesting (or a second machine) never double-records. This is the
    GitHub-canonical-completion -> cache materialization that unlocks the next Kahn layer.

    ``repo_root`` (#397) resolves the committed evidence ledger (``docs/evidence/<saga-id>/``,
    distinct from the git-common-dir cache ``store`` already resolves) for the closure gate — a
    SECOND, additive check run only after the GitHub barrier itself is satisfied. Defaulted to
    ``Path(".")`` so every caller that never declares a node's ``evidence.required_checks`` (every
    outcome spec that exists today) behaves exactly as before.
    """
    already = outcome_store.completed_subplots(store)
    harvested: list[str] = []
    # #380 (T8-F1-3): the committed intent envelope's ceremony gates imply closure checks —
    # `reviews_required: "gate"` requires `code-review` evidence before a code leaf may harvest
    # `done`. A spec with no intent (every pre-existing spec) implies nothing (unchanged).
    # #433 (R5): a dispatched leaf's implied checks come from its DISPATCH-ERA envelope (the
    # commit record's posture capture), never the current one — a mid-run repost governs future
    # dispatches, not in-flight completions.
    spec_intent = getattr(spec, "intent", None)
    era_intents = _dispatch_era_intents(store)
    for node in spec.nodes:
        sid = node.subplot_id
        if sid in already:
            continue
        verdict = barrier_satisfied(
            node, store=store, github_runner=github_runner, child_state_reader=child_state_reader
        )
        if not verdict.satisfied:
            continue
        # Closure gate (#397): a second, additive check — never a rewrite of the GitHub barrier
        # above. A node with no declared `required_checks` is trivially satisfied (R8), so this is
        # a no-op for every pre-existing outcome spec.
        node_intent = era_intents.get(sid, _CURRENT_INTENT)
        gate_verdict = closure_gate.evaluate(
            node,
            repo_root=repo_root,
            github_runner=github_runner,
            implied_checks=intent_envelope.implied_required_checks(
                spec_intent if node_intent is _CURRENT_INTENT else node_intent, node.kind
            ),
        )
        if not gate_verdict.satisfied:
            continue
        # Write to a FRESH attempt slot, never the implicit attempt 1: a subplot that already holds a
        # NON-success terminal (failed/rejected/stalled) at attempt 1 is not in `already`
        # (success-only), so a hardcoded attempt-1 write would collide with that slot's different
        # idempotency key and raise — wedging the whole reconcile loop. The constant idempotency key
        # plus the success-sticky `already` skip keep this idempotent regardless of attempt number.
        existing = outcome_store.read_completion_events(store, sid)
        attempt = max((e.attempt for e in existing), default=0) + 1
        payload = {"contract": verdict.contract, "evidence": verdict.evidence, "canonical": True}
        # Attach the advisory manifest pointer (R19/KTD1) when this leaf's dispatch recorded a
        # provenance manifest: saga_id convention = outcome id, execution_id = subplot id. Only
        # derivable when the store sits in the canonical <common>/saga-outcomes/<id> layout;
        # the pointer is advisory (R8) — any other layout, unsafe id, or absent manifest simply
        # means no pointer.
        if store.root.parent.name == outcome_store.STORE_NAMESPACE:
            outcome_id = store.root.name
            mstore = manifest_store.Store(
                root=store.root.parent.parent / manifest_store.MANIFEST_NAMESPACE / outcome_id
            )
            try:
                if mstore.manifest_path(sid).is_file():
                    payload = manifest_store.set_manifest_ref(payload, outcome_id, sid)
            except manifest_store.ManifestStoreError:
                pass
        event = outcome_store.CompletionEvent(
            subplot_id=sid,
            state="done",
            idempotency_key=f"harvest:{sid}:{verdict.contract}",
            attempt=attempt,
            at=at,
            payload=payload,
        )
        outcome_store.write_completion_event(store, event)
        harvested.append(sid)
    return harvested


def blocked_subtree(spec: Any, blocked_ids: set[str]) -> set[str]:
    """R22 cascade: the set of subplots transitively DOWNSTREAM of any hard-blocked node.

    Only the downstream subtree of a block pauses; a subplot with no dependency path to a blocked node
    keeps running. The blocked nodes themselves are NOT included (they are the cause, not the cascade).
    """
    dependents: dict[str, list[str]] = {n.subplot_id: [] for n in spec.nodes}
    for node in spec.nodes:
        for dep in node.depends_on:
            if dep in dependents:
                dependents[dep].append(node.subplot_id)
    paused: set[str] = set()
    stack = [b for b in blocked_ids if b in dependents]
    while stack:
        cur = stack.pop()
        for dependent in dependents.get(cur, []):
            if dependent not in paused:
                paused.add(dependent)
                stack.append(dependent)
    return paused


def barrier_report(
    spec: Any,
    *,
    store: Any,
    github_runner: Callable[..., Any] | None = None,
    child_state_reader: ChildStateReader | None = None,
    repo_root: Path = Path("."),
) -> dict[str, dict[str, Any]]:
    """Every node's barrier verdict (derived-on-read, for the cockpit/report). No writes.

    Also runs the closure gate (#397) per node and merges its verdict under a ``closure_gate`` key
    — so an operator sees the gate's NAMED HALT reason (``stale-sha:<id>``, ``missing-
    evidence:<id>``, ...) even when the GitHub-only barrier above already reads satisfied.
    """
    report: dict[str, dict[str, Any]] = {}
    # #380: mirror harvest() exactly — the report must evaluate the SAME gate the harvester
    # enforces (intent-implied checks included), or the operator-facing verdict reads satisfied
    # while the done transition is actually gated (enforcement/observability disagreement).
    # #433 (R5): the mirror includes the dispatch-era envelope — the report tells the same
    # dispatch-time story harvest enforces, so an in-flight leaf never reads "released" after a
    # loosening repost it does not follow.
    spec_intent = getattr(spec, "intent", None)
    era_intents = _dispatch_era_intents(store)
    for node in spec.nodes:
        verdict = barrier_satisfied(
            node, store=store, github_runner=github_runner, child_state_reader=child_state_reader
        ).to_dict()
        node_intent = era_intents.get(node.subplot_id, _CURRENT_INTENT)
        verdict["closure_gate"] = closure_gate.evaluate(
            node,
            repo_root=repo_root,
            github_runner=github_runner,
            implied_checks=intent_envelope.implied_required_checks(
                spec_intent if node_intent is _CURRENT_INTENT else node_intent, node.kind
            ),
        ).to_dict()
        report[node.subplot_id] = verdict
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Outcome completion barrier — report verdicts.")
    parser.add_argument("spec_json", help="path to an outcome-spec.json")
    args = parser.parse_args(argv)

    spec = outcome_spec.OutcomeSpec.from_json(Path(args.spec_json).read_text(encoding="utf-8"))
    spec.validate()
    # A bare-report CLI cannot resolve the per-outcome store/GitHub without more context; it prints
    # the static contract per node so an operator can see what each leaf must satisfy.
    contracts = {
        n.subplot_id: (
            CONTRACT_CHILD
            if n.is_outcome
            else CONTRACT_CODE
            if n.kind == "code"
            else CONTRACT_NONCODE
        )
        for n in spec.nodes
    }
    print(json.dumps({"outcome_id": spec.outcome_id, "contracts": contracts}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
