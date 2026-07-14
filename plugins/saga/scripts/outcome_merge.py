#!/usr/bin/env python3
"""Auto-merge queue + GitHub negative terminal states (U6) — envelope-gated since #449.

A non-gated, clean code subplot auto-merges (server-side squash) to unlock its dependents (R12)
**only under an explicit envelope authorization** (#449): the queue is the engine consumer that
``ceremony_gates.merge`` was recorded for. Per merge attempt, FRESH at authorization time, all of
these must hold or the leaf ``waits-operator`` with a precise reason:

* the campaign's committed intent envelope declares ``ceremony_gates.merge: "auto"`` — an
  envelope-less campaign or a ``merge: "gate"`` posture waits for the operator's keystroke
  (the never-autonomous default is the ENGINE's behavior now, not just recorded posture);
* exactly ONE active (unexpired, unrevoked, fingerprint- and revision-bound) merge-scope
  envelope token resolves from the outcome store's ``envelope-tokens`` lane — posture alone is
  recorded intent, never a credential (#380 threat model); zero or ambiguous tokens GATE;
* the pre-squash ``authorized`` attribution record lands durably in the board-sync ledger —
  a merge that cannot be attributed is not performed (fail closed, audit-first).

Revocation (``envelope_token.py revoke``) is re-read from disk before EVERY squash attempt, so
it stops the very next merge — including later leaves within the same tick (R4). **Residual
window, documented not claimed away:** the envelope posture itself is read through
``intent_reader`` — the production wiring reads the ON-DISK spec per authorization, but a direct
caller that passes no reader falls back to the tick's in-memory spec, where a mid-tick repost is
seen only next tick; token revocation is the immediate stop verb in both wirings. A crash between
the squash landing and the ``merged``-phase attribution record loses only that record (the
``authorized``-phase record + GitHub's own merged-by audit survive); it is never backfilled,
because post-hoc attribution would assert a pre-merge authorization nobody re-verified.

The gate evidence (required CI green + review/consensus) is the leaf's own already-passed gate, surfaced
to the coordinator as GitHub's ``mergeStateStatus`` (``blocked`` = gates not green yet -> wait). Because
concurrent siblings can both look clean on stale bases, merges are **serialized** and guarded:

* **GitHub is the authoritative atomic guard**, not a local SHA check: ``gh pr merge --squash
  --match-head-commit <head>`` is rejected by GitHub if the PR is not mergeable — base moved
  (``behind``), a conflict (``dirty``), the head moved, or required checks unmet — so a stale tree can
  never be squashed (R12/R30). The loop classifies via ``merge_state``: ``behind`` -> **rebase
  (update-branch) then re-verify**; ``dirty`` -> **conflict** (fail the leaf back to ``work`` + page,
  never a silent skip); a GitHub-rejected squash (``error``) **reloops** to re-classify; base churn is
  **capped** then halt + page (no starvation spin).
* **R34 safe-degrade:** an ``unknown`` merge-state or unreadable base (gh outage) **defers** the merge
  (``not-ready``) — a gh outage never fails a leaf or performs a wrong merge.

Negative GitHub terminals are modeled (R32): a **PR closed-unmerged** or a **definitely-404 deleted
branch** records a sticky ``rejected`` terminal so dependents do not hang — it cascades like a block
(R22). A PR already merged out-of-band is detected and never double-merged. A ``conflict`` records a
**retryable** ``failed`` terminal (it re-enters the queue once /work fixes it — only ``rejected`` /
``stalled`` permanently skip).

The CALLER (``advance``) runs ``process_merge_queue`` under the held coordinator lease, so the queue is
single-writer **cross-process** too (R13). GitHub operations are injected as a :class:`MergeOps`
adapter, so the whole queue is unit-testable with no real ``gh``; ``github_merge_ops`` wires the real
``outcome_github`` write side. No I/O at import.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_github  # noqa: E402  (after the sys.path shim, by design)
import outcome_orchestrator  # noqa: E402
import outcome_store  # noqa: E402

# Base-churn cap: how many times a sibling-merge can move the base out from under us before we stop
# and page the operator instead of spinning (R12 "no starvation spin").
MERGE_CAP = 3


@dataclass
class MergeOps:
    """The GitHub operations the merge queue needs — injected so the queue is testable with no gh."""

    pr_state: Callable[[str], str]  # merged / closed / open / unknown
    base_oid: Callable[[str], str]  # the PR base branch tip SHA ("" = unknown)
    merge_state: Callable[[str], str]  # clean / behind / blocked / dirty / unstable / unknown
    update_branch: Callable[[str], bool]  # rebase/update the PR branch onto its base
    squash_merge: Callable[[str], str]  # merged / conflict / error
    branch_exists: Callable[[str], bool]


def github_merge_ops(runner: Callable[..., Any] | None = None) -> MergeOps:
    """The real adapter, wiring ``outcome_github``'s read+write side (degraded-to-safe throughout).

    ``squash_merge`` passes the PR head SHA as ``--match-head-commit`` so GitHub itself is the atomic
    guard — it rejects the merge if the head moved since, so a stale tree can never be squashed.
    """
    return MergeOps(
        pr_state=lambda r: outcome_github.pr_state(r, runner=runner),
        base_oid=lambda r: outcome_github.base_ref_oid(r, runner=runner),
        merge_state=lambda r: outcome_github.merge_state(r, runner=runner),
        update_branch=lambda r: outcome_github.update_branch(r, runner=runner),
        squash_merge=lambda r: outcome_github.squash_merge(
            r, expected_head=outcome_github.head_ref_oid(r, runner=runner), runner=runner
        ),
        branch_exists=lambda b: outcome_github.branch_exists(b, runner=runner),
    )


@dataclass
class MergeOutcome:
    """The result of attempting to auto-merge one subplot.

    ``authorizing_envelope_id`` / ``token_id`` (#449) are set only on an
    envelope-authorized ``merged`` outcome and emitted only when set, so every
    pre-existing record shape round-trips byte-identical.
    """

    subplot_id: str
    state: (
        str  # merged / already-merged / rejected / conflict / capped / waits-operator / not-ready
    )
    reason: str
    cycles: int = 0
    authorizing_envelope_id: str = ""
    token_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "subplot_id": self.subplot_id,
            "state": self.state,
            "reason": self.reason,
            "cycles": self.cycles,
        }
        if self.authorizing_envelope_id:
            out["authorizing_envelope_id"] = self.authorizing_envelope_id
        if self.token_id:
            out["token_id"] = self.token_id
        return out


def auto_merge_one(
    node: Any,
    ops: MergeOps,
    *,
    max_cycles: int = MERGE_CAP,
    merge_authorizer: Callable[[], Any] | None = None,
) -> MergeOutcome:
    """Attempt to auto-merge one subplot (R12/R32/R34), under the #449 merge ceremony.

    **GitHub is the authoritative atomic guard**, not a local SHA check: ``squash_merge`` (with
    ``--match-head-commit``) is rejected by GitHub if the PR is not mergeable — base moved (behind),
    a conflict, or required checks unmet — so a stale tree cannot be squashed. The loop classifies via
    ``merge_state`` (GitHub's own readiness): ``dirty`` -> conflict (leaf back to ``work``); ``behind``
    -> rebase + re-verify; ``blocked`` -> wait for gates; ``unknown`` / unreadable base -> **defer**
    (R34, a gh outage never fails a leaf). A squash that GitHub rejects (``error`` — base/head moved or
    a transient blip) **reloops** to re-classify, never a stale merge; base churn is **capped** at
    ``max_cycles`` then halt + page (no starvation spin).

    **#449 merge ceremony (fail closed).** ``merge_authorizer`` is a zero-arg callable that
    performs the FRESH envelope-token authorization (posture + token + pre-squash attribution
    record) and returns a ``reversibility_certificate.EnvelopeAuthorization``. It gates every
    GitHub WRITE this loop can perform — ``update_branch`` (rebase) and ``squash_merge`` — and
    is re-invoked before each one, so a revocation stops the very next write (R4). Read-only
    classification (dirty -> conflict, blocked/unknown -> defer) runs for every campaign, so
    conflict recording and /work re-engagement never depend on merge authority. ``None`` (no
    authority supplied) behaves as an always-GATE authorizer: there is NO tokenless
    auto-merge (or auto-rebase) path left.
    """
    sid = node.subplot_id
    pr = str(node.github.get("pr", ""))
    branch = str(node.github.get("branch", ""))
    if not pr:
        return MergeOutcome(sid, "not-ready", "no PR ref")

    def _ceremony() -> Any:
        if merge_authorizer is None:
            return None  # no authority supplied -> always GATE (fail closed, #449)
        return merge_authorizer()

    def _gated(auth: Any, cycles: int) -> MergeOutcome:
        reason = (
            "no merge ceremony authority supplied — merge-class writes wait for the "
            "operator (#449 fail-closed default)"
            if auth is None
            else f"merge ceremony gated: {getattr(auth, 'reason', 'no reason given')}"
        )
        return MergeOutcome(sid, "waits-operator", reason, cycles)

    # 1) Out-of-band / negative-terminal checks FIRST (never double-merge; reject hangs-free, R32).
    state = ops.pr_state(pr)
    if state == "merged":
        return MergeOutcome(
            sid, "already-merged", "PR already merged out-of-band — no duplicate merge"
        )
    if state == "closed":
        return MergeOutcome(
            sid, "rejected", "PR closed unmerged (R32) — terminal, cascades like a block"
        )
    if branch and not ops.branch_exists(branch):
        return MergeOutcome(sid, "rejected", "branch deleted (R32) — terminal")

    # 2) Gated / risky / destructive subplots are never auto-merged — they wait for the operator
    #    (R12), envelope or no envelope: a #449 token never overrides a leaf's own gating flags.
    if node.gated or node.risky or node.destructive:
        return MergeOutcome(sid, "waits-operator", "gated/risky/destructive — operator merges")

    # 3) The GitHub-guarded merge loop, base-churn capped (R12). Reads classify for every
    #    campaign; every WRITE (update_branch, squash_merge) is #449 ceremony-gated first.
    cycles = 0
    while cycles < max_cycles:
        ms = ops.merge_state(pr)
        if ms == "dirty":
            return MergeOutcome(
                sid, "conflict", "merge conflict — leaf back to work + page (R12)", cycles
            )
        if ms == "unknown":
            # gh degraded — never squash on an unknown readiness, never fail the leaf (R34).
            return MergeOutcome(
                sid, "not-ready", "merge readiness unknown (gh degraded) — defer", cycles
            )
        if ms == "behind":
            # #449: a rebase is a GitHub write — ceremony-gated exactly like the squash.
            auth = _ceremony()
            if str(getattr(auth, "verdict", "")) != "AUTHORIZED":
                return _gated(auth, cycles)
            ops.update_branch(pr)  # rebase; the leaf re-verifies its own gate after the update
            cycles += 1
            continue
        if ms == "blocked":
            return MergeOutcome(sid, "not-ready", "required CI/review gates not green yet", cycles)
        # clean / unstable -> let GitHub perform the atomic guarded squash.
        if not ops.base_oid(pr):
            return MergeOutcome(
                sid, "not-ready", "base unreadable (gh degraded) — defer (R34)", cycles
            )
        # #449: the envelope-token authorization, FRESH per squash attempt (revocation between
        # attempts — or between two leaves in one tick — stops the very next squash, R4).
        auth = _ceremony()
        if str(getattr(auth, "verdict", "")) != "AUTHORIZED":
            return _gated(auth, cycles)
        if ops.squash_merge(pr) == "merged":
            return MergeOutcome(
                sid,
                "merged",
                "server-side squash-merged (GitHub-guarded, envelope-authorized #449)",
                cycles,
                authorizing_envelope_id=str(auth.authorizing_envelope_id),
                token_id=str(auth.token_id),
            )
        # GitHub rejected the squash (head/base moved, or transient) -> reloop and re-classify.
        cycles += 1
    return MergeOutcome(
        sid, "capped", f"base churned {max_cycles}x — halt + page, no spin (R12)", cycles
    )


def _is_mergeable_kind(node: Any) -> bool:
    # Only code leaves with a PR auto-merge; non-code/child-outcome complete via their own contract (U5).
    return node.kind == "code" and not node.is_outcome and bool(node.github.get("pr"))


# ---------------------------------------------------------------------------
# #449 merge ceremony — the ceremony_gates.merge engine consumer
# ---------------------------------------------------------------------------


def _ledger_dir(store: Any) -> Path:
    """The board-sync ledger dir (single-sourced against outcome_board_sync, KTD4)."""
    import outcome_board_sync  # noqa: PLC0415

    return outcome_board_sync._board_sync_dir(store)  # noqa: SLF001


def make_merge_authorizer(
    spec: Any,
    store: Any,
    node: Any,
    *,
    now: Callable[[], float] = time.time,
    intent_reader: Callable[[], tuple[Mapping[str, Any] | None, int]] | None = None,
) -> Callable[[], Any]:
    """Build one leaf's per-squash merge authorizer (#449) — every call is fresh.

    Each invocation re-derives EVERYTHING at authorization time: the committed envelope
    posture via ``intent_reader`` (the production wiring reads the ON-DISK spec; the
    default falls back to the in-memory ``spec`` — residual documented in the module
    docstring), the single active merge token from the outcome store's token lane
    (``envelope_token.resolve_merge_token``: fresh disk reads, revocation- and
    expiry-checked, fingerprint- and revision-bound, ambiguity GATEs), and the
    certificate verdict. On AUTHORIZED it durably writes the pre-squash ``authorized``
    attribution record — and converts a record-write fault into GATE, because a merge
    whose authorization cannot be attributed is not performed (fail closed, audit-first).

    ``other_gates_green=True`` is the call-site fact: ``auto_merge_one`` invokes the
    authorizer only after GitHub's own readiness (``merge_state`` clean/unstable), the
    DAG dependency gate, and the gated/risky/destructive check have all passed.
    """
    import board_progression  # noqa: PLC0415
    import envelope_token  # noqa: PLC0415
    import reversibility_certificate as cert  # noqa: PLC0415

    lane = envelope_token.tokens_dir(store.root)
    pr = str(node.github.get("pr", ""))

    def _read_intent() -> tuple[Mapping[str, Any] | None, int]:
        if intent_reader is not None:
            return intent_reader()
        return (spec.intent, spec.intent_revision or 0)

    def _authorize() -> Any:
        try:
            intent, revision = _read_intent()
        except Exception as exc:  # noqa: BLE001 — an unreadable posture must GATE, not crash the tick
            return cert.EnvelopeAuthorization(
                cert.GATE,
                f"committed posture could not be read at authorization time — failing "
                f"closed: {exc}",
            )
        # Posture pre-check for a first-cause operator reason (the token layer re-checks
        # both conditions independently — lesson 10: enforce at every seam).
        if intent is None:
            return cert.EnvelopeAuthorization(
                cert.GATE,
                "no committed intent envelope — merge-class writes stay operator-gated "
                '(capture ceremony_gates.merge: "auto" at run start AND mint an envelope '
                "token to enable auto-merge, #449)",
            )
        try:
            envelope_mod = envelope_token._intent_envelope()  # noqa: SLF001
            parsed = envelope_mod.IntentEnvelope.from_dict(dict(intent))
            if parsed.ceremony_gates.merge != envelope_mod.AUTO:
                return cert.EnvelopeAuthorization(
                    cert.GATE,
                    f"committed ceremony_gates.merge is {parsed.ceremony_gates.merge!r} — "
                    "the operator's recorded posture does not permit autonomous merge (#449)",
                )
        except Exception as exc:  # noqa: BLE001 — an invalid envelope must GATE, not crash the tick
            return cert.EnvelopeAuthorization(
                cert.GATE,
                f"committed intent envelope could not be strictly understood — failing "
                f"closed: {exc}",
            )
        now_iso = datetime.fromtimestamp(now(), tz=UTC).isoformat()
        auth = envelope_token.authorize_merge_under_envelope(
            lane,
            outcome_id=spec.outcome_id,
            envelope=intent,
            intent_revision=revision,
            other_gates_green=True,
            now=now_iso,
        )
        if auth.verdict != cert.AUTHORIZED:
            return auth
        try:
            ledger = _ledger_dir(store)
        except Exception as exc:  # noqa: BLE001 — an unattributable merge must GATE, not crash
            return cert.EnvelopeAuthorization(
                cert.GATE,
                "authorized, but the board-sync ledger is unavailable — refusing to "
                f"merge unattributed (fail closed): {exc}",
            )
        record = board_progression.record_envelope_authorized_merge(
            ledger,
            phase="authorized",
            outcome_id=spec.outcome_id,
            subplot_id=node.subplot_id,
            pr=pr,
            authorizing_envelope_id=auth.authorizing_envelope_id,
            token_id=auth.token_id,
            now=now,
        )
        if record["status"] == "error":
            return cert.EnvelopeAuthorization(
                cert.GATE,
                "authorized, but the pre-squash attribution record could not be written — "
                f"refusing to merge unattributed (fail closed): {record.get('error', '')}",
            )
        return auth

    return _authorize


# Terminal-negative states that should NOT be retried by the merge queue. ``failed`` is deliberately
# EXCLUDED — a conflict fails the leaf back to ``work``, and once /work fixes it the leaf must re-enter
# the queue (a permanent skip on ``failed`` is the conflict-recovery deadlock).
_QUEUE_TERMINAL = frozenset({"rejected", "stalled"})


def _skip_set(store: Any) -> set[str]:
    """Subplots the merge queue skips: already merged (success) OR truly-terminal (rejected/stalled).

    A ``failed`` leaf is intentionally retryable (re-enters the queue once its conflict is resolved).
    """
    skip = set(outcome_store.completed_subplots(store, successful_only=True))
    for node_id in outcome_store.completed_subplots(store, successful_only=False):
        events = outcome_store.read_completion_events(store, node_id)
        if events and events[-1].state in _QUEUE_TERMINAL:
            skip.add(node_id)
    return skip


def process_merge_queue(
    spec: Any,
    store: Any,
    ops: MergeOps,
    *,
    max_cycles: int = MERGE_CAP,
    now: Callable[[], float] = time.time,
    intent_reader: Callable[[], tuple[Mapping[str, Any] | None, int]] | None = None,
) -> dict[str, Any]:
    """Serialize the auto-merge of every eligible code subplot (one at a time) and record negative
    terminals. Returns the per-subplot outcomes + the rejected set + its cascade.

    Serialized by construction (sequential) — and the CALLER holds the coordinator lease (R13), so it
    is single-writer cross-process too: two coordinators cannot both squash on stale bases. The
    skip-set is **success OR truly-terminal-negative (rejected/stalled)** — a ``conflict`` records a
    ``failed`` terminal which is RETRYABLE (so a conflicted-then-fixed leaf re-enters the queue; not a
    permanent skip), while ``rejected`` (R32) is terminal and cascades (R22).

    **Dependency-gated (R12 + the DAG).** A code leaf is merged only once **all of its ``depends_on`` are
    success-complete** — GitHub's mergeability does NOT model the outcome DAG, so a coincidentally-clean
    PR for a leaf whose upstream is incomplete (especially a *non-code* upstream that produces no
    base-blocking merge) would otherwise squash prematurely, out of dependency order. The frontier gate is
    the orchestrator's, not GitHub's.

    **Envelope-gated (#449).** Every leaf gets a per-squash ``make_merge_authorizer`` closure —
    posture + token + certificate, all fresh per attempt; a leaf that fails the ceremony records
    ``waits-operator`` with the precise reason (visible in the tick result, retried next tick,
    never a terminal). An envelope-authorized merge writes an ``authorized`` attribution record
    BEFORE the squash and a ``merged`` record after it into the board-sync ledger, both carrying
    ``authorizing_envelope_id`` (R5); the merged record's write status is surfaced on the outcome
    as ``attribution`` (a post-squash ledger fault is loud, never thrown — the squash already
    committed; the record is never backfilled later, see the module docstring).
    """
    import board_progression  # noqa: PLC0415

    skip = _skip_set(store)
    success = outcome_store.completed_subplots(store)  # success-only -> the dependency gate
    outcomes: list[dict[str, Any]] = []
    rejected: list[str] = []
    for node in spec.nodes:
        if node.subplot_id in skip or not _is_mergeable_kind(node):
            continue
        if not all(dep in success for dep in node.depends_on):
            continue  # upstream not all done -> never merge out of dependency order (R12 + the DAG)
        authorizer = make_merge_authorizer(spec, store, node, now=now, intent_reader=intent_reader)
        outcome = auto_merge_one(node, ops, max_cycles=max_cycles, merge_authorizer=authorizer)
        outcome_dict = outcome.to_dict()
        if outcome.state == "merged" and outcome.authorizing_envelope_id:
            # R5: the post-squash `merged` attribution record (write-once; fault surfaced —
            # never thrown, the squash already committed).
            try:
                outcome_dict["attribution"] = board_progression.record_envelope_authorized_merge(
                    _ledger_dir(store),
                    phase="merged",
                    outcome_id=spec.outcome_id,
                    subplot_id=node.subplot_id,
                    pr=str(node.github.get("pr", "")),
                    authorizing_envelope_id=outcome.authorizing_envelope_id,
                    token_id=outcome.token_id,
                    now=now,
                )
            except Exception as exc:  # noqa: BLE001 — surfaced loudly on the record, never raised
                outcome_dict["attribution"] = {
                    "status": "error",
                    "error": f"merged, but the attribution record could not be written: {exc}",
                }
        outcomes.append(outcome_dict)
        if outcome.state == "rejected":
            _record_terminal(store, node.subplot_id, "rejected", outcome.reason)
            rejected.append(node.subplot_id)
        elif outcome.state == "conflict":
            # fail the leaf back to work — a NON-success terminal that does not unlock dependents (R12)
            _record_terminal(store, node.subplot_id, "failed", outcome.reason)
    cascade = sorted(outcome_orchestrator.blocked_subtree(spec, set(rejected)))
    return {"outcomes": outcomes, "rejected": rejected, "cascade_paused": cascade}


def _record_terminal(store: Any, sid: str, state: str, reason: str) -> None:
    """Record a NEGATIVE terminal completion event (rejected/failed) at a fresh attempt, idempotently."""
    existing = outcome_store.read_completion_events(store, sid)
    if any(e.state == state for e in existing):
        return  # already recorded this terminal
    attempt = max((e.attempt for e in existing), default=0) + 1
    outcome_store.write_completion_event(
        store,
        outcome_store.CompletionEvent(
            subplot_id=sid,
            state=state,
            idempotency_key=f"terminal:{sid}:{state}",
            attempt=attempt,
            payload={"reason": reason},
        ),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Outcome auto-merge queue (U6) — describe the policy."
    )
    parser.add_argument("--cap", type=int, default=MERGE_CAP)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                "merge_cap": args.cap,
                "policy": "envelope-gated (#449: ceremony_gates.merge=auto + one active merge "
                "token, fresh per squash, attributed to the authorizing envelope); serialized "
                "squash-merge; base-SHA-guarded; rebase-reverify on behind; conflict->work+page; "
                "closed-unmerged/branch-deleted->rejected cascade",
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
