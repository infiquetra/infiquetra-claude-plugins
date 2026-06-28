---
date: 2026-06-28
topic: board-saga-reconciliation
maturity: requirements-ready
source: ideation R1/A3 (docs/ideation/2026-06-26-vecu-port-seeds-ideation.md) — revived survivor, re-bounded
depends_on: "#279 (S-2 reversibility/idempotency certificate — the autonomous board-sync writer)"
repo: infiquetra-claude-plugins
---

# Board↔Saga Reconciliation on Resume (R1)

## Summary

R1 is the **resume-time reconciliation companion** to S-2 (#279). #279 builds the autonomous
board-sync *writer* — at a board-relevant leaf transition it drives the enumerated reversible/additive
writes (Status, labels, sub-issue close, coalesced progress comments), each under an idempotency key
with a bounded-retry/fail-loud path, and records every write as a saga tick (#279 R9, R15–R19). What
#279 does **not** do is notice when an *outside* writer — the operator, a GitHub auto-review, a future
review agent — changed the board while saga was at rest. That blind spot is R1.

R1 runs at the next resume / session start: it re-fetches the live board for the fields saga owns,
diffs them against #279's recorded writes (and its in-flight idempotency keys), and on any divergence
surfaces the conflict and asks the operator. It does not force-heal, it is HITL today (a writer-
precedence rule is a deferred seam), and it does not make the board a projection of saga state.

## Problem frame

**What #279 already owns (verified against its brainstorm).** #279's v1 is the first autonomous
board-sync consumer: `/outcome` drives `set-field` Status, issue-label add/remove, sub-issue-close-
after-tester-ACCEPT, and coalesced progress comments autonomously when `authorize_write` returns
AUTHORIZED (#279 R16); it builds the write/close adapters (R15), carries a universal idempotency key
(R9), bounded-retries failed writes and surfaces on exhaustion (R18), and records every autonomous
write as a tick "so `/resume` / `/retro` can read what saga did while you were away" (R19). PR-merge
and deploy are never autonomous (R20). R1 must **consume** this, not duplicate it.

**The gap #279 leaves.** R19 is an audit trail of saga's *own* writes — it records what saga did. It
never re-reads the live board to detect what *someone else* did. So if the operator closes the issue,
or a CI bot moves a label, while saga is stopped, #279 is unaware: it keeps its recorded state and
would happily drive the next write against a board that has moved underneath it. Nothing closes that
loop today.

**The temporal reality (the operator's reframe — and the whole of R1).** When does an outside change
matter, and when can saga see it?

- **While saga executes**, #279 is the de-facto writer. An outside edit mid-run (an operator or CI
  touching a label during a 10-minute gate) is *possible* but rare; v1 accepts that window rather than
  adding a live guard.
- **Outside drift mostly arises while saga is at rest** — paused, stopped, session closed.
- **Saga is blind at rest.** It is not running; it cannot observe the change until it next wakes.
  *How will saga ever know?* It cannot — until resume.

So there is no resident monitor and no polling in v1; the earliest supported detection is the
SessionStart / `/resume` boundary. Reconcile-on-wake is the mechanism, and HITL is the resolution.

## Key decisions

**KD1 — R1 is reconcile-only; the write path is entirely #279's.** Authority, driver, adapters,
idempotency key, failure path, and per-write recording all live in #279 (R9, R15–R19). R1 adds no
writer. This removes the duplication the first draft introduced. (Considered and rejected: folding
reconcile *into* #279 — #279 is scope-locked and READY; reconcile is a distinct mechanism that can
only run *after* #279's writer ships, so it is cleaner as a sequenced companion issue.)

**KD2 — R1's baseline is #279's own records.** The reconcile baseline = #279's per-write tick records
(R19) **union** its in-flight idempotency keys (R9/R18). That union is the complete picture of "what
#279 did or was doing." R1 adds no new persistence — #279 owns the write-record schema.

**KD3 — Reconcile scope is the saga-owned field *class*, not the dynamic recorded-fact set.** R1 diffs
a fixed, enumerated set of fields saga owns — Status, the saga-managed label set, issue open/closed,
saga-authored comments — regardless of whether a write-fact was recorded. A field saga owns but whose
record was lost to a crash (write landed on GitHub, the R19 tick never appended) is still in scope, so
the drift is visible; the idempotency-key cross-check (KD2) tells "saga's own unconfirmed write" from
"an outside change." A label the operator hand-added, which saga never owned, is simply **out of
scope** — not drift. This closes the partial-failure blind spot the panel flagged while keeping the
no-false-positive property.

**KD4 — The diff is #279-independent; the *resolution* is not.** Fetching the board and computing the
divergence needs only mission-control read verbs. But resolving a conflict by re-asserting saga's value
("the board is wrong, fix it") re-drives a board write, which must pass #279's `authorize_write` and go
through its adapter and idempotency key. R1 read/diff/ask stands alone; R1 write-back depends on #279.

**KD5 — Mid-run outside drift is an accepted v1 window, not an impossibility.** The earlier "saga is
the sole writer during execution → no drift" claim was false: an operator or CI can edit the board
during a long gate. v1 does not guard that window (no live read-before-write); reconcile-on-wake is the
net that catches it at the next resume. A live read-before-write guard is a deferred hardening, not v1.

**KD6 — Resolution is HITL now; writer-precedence is a deferred seam.** On divergence R1 offers the
operator {accept the board, re-assert saga (re-drive via #279), pause/hold} and never force-heals. The
future ("a designated review agent's change is authoritative for field X → auto-resolve") routes
through one replaceable decision hook; v1 leaves the seam and keeps HITL behind it.

**KD7 — Co-ownership, not projection.** The board is not a projection of saga state; saga is not the
sole writer; R1 never overwrites the operator's edits without asking. (Operator did not select the
full board-as-projection option.)

## Requirements

- **R1.1 (trigger)** On resume / session start of a saga whose #279-driven board issue exists, R1 runs
  reconciliation. (Whether it also runs on an explicit "check the board" and whether it rides the S-3
  #281 resume path is Q1.)
- **R1.2 (baseline)** R1 reads #279's recorded write-facts (R19) and in-flight idempotency keys
  (R9/R18) for the issue as the reconcile baseline. R1 persists nothing new of its own.
- **R1.3 (scope + cross-check)** R1 fetches the live board for the enumerated saga-owned field class
  (Status, saga-managed labels, issue open/closed, saga comments — Q2) and diffs against the baseline.
  A landed-but-unrecorded write is reconciled via the idempotency-key cross-check (KD2/KD3), not
  excluded for lack of a record.
- **R1.4** If every saga-owned field matches the baseline, reconciliation is silent and saga continues.
- **R1.5 (divergence)** On divergence R1 surfaces a concrete report — field, saga value, board value,
  and the external author if discoverable — and offers {accept board, re-assert saga, pause/hold}. It
  never force-heals and never silently proceeds.
- **R1.6 (external-close case)** If the issue was closed externally while saga was at rest,
  reconciliation surfaces it (saga=open, board=closed, closed-by) and asks; it neither silently
  auto-closes the saga nor silently ignores the close.
- **R1.7 (resolution recording)** R1 records the operator's resolution as an explicit
  `reconcile-override` write-fact appended to #279's record stream (append-only-clean). A "re-assert
  saga" resolution re-drives the write through #279's `authorize_write` + adapter (KD4).
- **R1.8 (future seam)** The resolution decision in R1.5 routes through a single replaceable policy hook
  so a later writer-precedence rule can supersede the HITL ask without touching the fetch or diff.
- **R1.9 (grounding)** R1 adds no new persistence and no new board operations: it reads #279's records
  via existing mission-control read verbs and re-drives via #279's write path. It does not duplicate
  #279's writer (KD1).

## Key flow

**Reconcile (on wake)**
```
resume / session start of a saga with a #279-driven board issue
   |
   v  baseline = #279 records (R19) UNION in-flight idempotency keys (R9/R18)
   v  fetch live board -- ONLY saga-owned field class (KD3 scope)
   v  diff vs baseline  (idempotency-key cross-check resolves landed-but-unrecorded writes)
   +-- all match -> silent, continue
   +-- divergence -> surface {field, saga=X, board=Y, author?}
                     -> offer {accept board | re-assert saga (re-drive via #279) | pause/hold}
                     -> record a reconcile-override write-fact   [future: precedence hook auto-resolves]
```
(There is no "drive" flow here — autonomous writing is #279's F1.)

## Acceptance examples

- **AE1 (external close).** Operator closes the issue between sessions → next `/resume` →
  reconciliation surfaces "saga=open, board=closed (closed by @operator)" → asks → operator picks
  "close saga" → R1 records a reconcile-override and closes. No silent auto-close. **Covers R1.6, R1.7.**
- **AE2 (scope discipline — no false positive).** While saga is stopped, the operator hand-adds a
  freeform label saga never owned → next resume → that label is outside the saga-owned field class →
  **no false drift**, reconciliation silent. **Covers R1.3, R1.4.**
- **AE3 (partial-failure — no blind spot).** #279's autonomous Status write lands on GitHub but the
  R19 tick is lost to a crash → next resume → Status is in scope (KD3) and an in-flight idempotency key
  exists with no confirmation (KD2) → R1 recognizes saga's own unconfirmed write, confirms it against
  the board, and completes the record rather than hiding it. **Covers R1.2, R1.3.**
- **AE4 (re-assert depends on #279).** Reconciliation finds a CI bot moved Status while saga was at
  rest; operator picks "re-assert saga" → R1 re-drives the Status write **through #279's
  `authorize_write` + adapter + idempotency key**, not a direct write. **Covers R1.5, R1.7, KD4.**

## Scope boundaries

**In:** resume-time reconciliation of board↔saga divergence over #279's writer; HITL resolution with
{accept / re-assert / pause}; the reconcile-override record; the deferred writer-precedence seam.

**Out:** the autonomous **write path** itself (owned by #279 — R9, R15–R19); board-as-projection /
saga-as-sole-writer; any resident monitor, polling, or webhook (earliest detection is resume — a
webhook/scheduled probe is an explicit future option, not v1); a built writer-precedence model (seam
only); live read-before-write mid-run guarding (deferred hardening, KD5); PR-merge / deploy autonomy
(permanently HITL via #279 R20).

## Dependencies & assumptions

- **Hard — #279.** R1 is meaningless without #279's writer: it reconciles #279's writes, reads #279's
  R19 records + R9 idempotency keys as its baseline, and re-drives resolutions through #279's
  `authorize_write` + adapter. R1 therefore plans **after** #279 ships — you cannot reconcile writes
  that do not yet exist. Brainstorm: `docs/brainstorms/2026-06-27-reversibility-idempotency-certificate-requirements.md`;
  review `docs/reviews/2026-06-27-reversibility-idempotency-certificate-readiness.md`.
- **Soft / existing:** mission-control read verbs (`issue_state`, board reads) for the live fetch.
- **Assumption:** #279's R19 record carries enough per-write detail (field, value, basis) to serve as a
  reconcile baseline. If R19's record is thinner than that, R1's first `/plan` task is to specify the
  minimal added field on #279's record — a small, bounded #279 touch, not an R1 writer.

## Outstanding questions (for /plan)

- **Q1 (resolve-before-planning) — the reconcile trigger.** Automatic on every `/resume` / SessionStart
  of a board-bearing saga (silent unless divergent), or operator-invoked ("check the board")? And does
  it ride the **existing** SessionStart(source=compact) / resume path from S-3 #281, or need its own
  hook? (Lean: automatic-but-silent-unless-divergent on the S-3 path, so safety does not depend on the
  operator remembering to ask.)
- **Q2 — the saga-owned field class.** Enumerate exactly which board fields/objects R1 treats as
  saga-owned (Status, the managed-label set, issue open/closed, saga comments) and confirm the
  idempotency-key cross-check shape so a landed-but-unrecorded write is reconciled, not missed.
- **Q3 — the precedence seam shape.** Is the R1.8 hook a per-field "authoritative writer" lookup, and
  is sketching its signature now worth it vs a pure deferral? (Lean: define the call site + signature,
  defer the policy.)

## Sources

- Ideation R1/A3 framing — `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (Reconciliation +
  Did-not-survive table).
- **#279 scope (re-bound driver of this whole reframe)** — its brainstorm R9, R15–R19, R20 and Scope
  Boundaries ("first autonomous consumer: `/outcome` board-sync … R15–R19"); readiness review
  "Scope observation" (net-new adapter + failure path is #279's, plainly stated).
- Premise — `outcome.py:1065` (`issue_close` stays None until an operator-initiated mission-control
  consumer exists, i.e. #279); `outcome_github.py:170,187` (existing gated PR-merge writes only).
- saga append-only log substrate — `DECISIONS.md:960`; #279 R19 owns the autonomous-write record.
- Operator reconciliation reframe — this session (temporal drift / reconcile-on-wake /
  HITL-now-precedence-later).
- Doc-review (3-engine gated, this session) — codex (repo access) found the #279 write-path
  duplication; both agy engines + codex converged on the partial-failure scope blind spot and the
  reconcile-independence overstatement.
