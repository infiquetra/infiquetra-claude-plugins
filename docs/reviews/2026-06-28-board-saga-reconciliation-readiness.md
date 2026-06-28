---
date: 2026-06-28
target: docs/brainstorms/2026-06-28-board-saga-reconciliation-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review, 3-engine gated)
verdict: READY
blocked: false
---

# Readiness Review — Board↔Saga Reconciliation on Resume (R1)

## Verdict

**READY for `/plan`** after a structural re-bound. The draft framed R1 as an autonomous board *writer*
gated by S-2 (#279), treating #279 as "an authority with no caller." A three-engine adversarial panel
plus a pre-registered Claude critique converged on two defects, and codex's repo access surfaced a
third that the hermetic engines could not: **#279 already builds the entire autonomous board-sync
writer** — driver, adapters, idempotency key, bounded-retry failure path, and per-write recording
(#279 R9, R15–R19). R1's write path was duplication. The fix re-bounds R1 to its genuine residue: the
**resume-time reconciliation** #279 lacks — detecting when an outside writer changed the board while
saga was at rest, and resolving it HITL. That re-bound also dissolves the panel's other P0 (a
partial-failure scope blind spot): write atomicity and idempotency belong to #279's layer, which
already solves them, so R1 inherits the keys and records rather than re-solving the problem. The
operator's chosen scope (reconcile, HITL now / precedence later, not projection) is preserved — it
*is* the re-bounded R1. No `P0` remains.

## Method

Three external engines ran as gated generators under Claude-side verification; every finding was
checked against the document, the repo, or #279's brainstorm before adoption.

- **Codex / gpt-5.5** at `xhigh`, read-only, repo access — ran **wrapped through Headroom**
  (`headroom wrap codex -- exec …`, second confirmed wrapped run after R7). With repo access it read
  #279's actual brainstorm and raised the load-bearing P0: R1 duplicates #279's first autonomous
  board-sync consumer (R15–R19) rather than consuming it; it also grounded the crash-gap fix in #279's
  existing idempotency key (R9) + bounded retry (R18), flagged that the saga tick schema does not yet
  define board write-facts (so the "no new persistence" claim needed #279's R19 to own it), and
  corrected the premise citation.
- **agy / Gemini 3.1 Pro (High)** and **agy / Gemini 3.5 Flash (High)**, hermetic (doc + verified
  facts inlined, no repo access) — both independently raised the partial-failure scope blind spot as
  `P0` (a write that lands on GitHub but whose record is lost is permanently invisible to a
  recorded-facts-only reconcile scope), the reconcile-independence overstatement, and the false
  "sole-writer during execution" claim. Pro added the append-only "reconcile-override" record; Flash
  added the abort/pause resolution option.
- **Claude-side pre-registration + #279 read** — four findings recorded before the engines returned
  (`r1_prereg.md`): the independence overstatement (PR1) and the write-then-record atomicity gap (PR2)
  were predicted and confirmed; the structural duplication was **not** predicted — it required reading
  #279's brainstorm, which only codex's repo access prompted.

**Convergence as evidence.** The reconcile-independence overstatement was hit 4 ways (Pro + Flash +
codex + pre-reg). The partial-failure blind spot was hit 4 ways (Pro + Flash + codex + pre-reg PR2).
The structural duplication was codex-only and verified directly against #279 R15–R19. Three
independent angles on the symptoms, one repo-grounded angle on the cause.

## Applied fixes

All evidence-backed; the document was rewritten in place (filename corrected from
`autonomous-board-driver` to `board-saga-reconciliation` to match the re-bound).

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | Re-bound R1 to reconcile-only; the write path (authority + driver + adapters + idempotency + failure + recording) is #279's. Removes the duplication | Codex `P0` (repo access) + Claude verification | #279 brainstorm R9, R15–R19 + Scope Boundaries ("first autonomous consumer: `/outcome` board-sync") |
| 2 | Reconcile scope = saga-owned field *class* (not recorded-fact set) + idempotency-key cross-check, so a landed-but-unrecorded write is visible, not hidden | agy-Pro `P0` + agy-Flash `P0` + codex + Claude PR2 | #279 R9 (idempotency key) / R18 (retry) / R19 (record); doc KD2/KD3, AE3 |
| 3 | KD4: the reconcile diff is #279-independent, but a re-assert resolution re-drives through #279's `authorize_write` + adapter | agy-Pro `P1` + agy-Flash `P1` + codex `P1` + Claude PR1 | doc KD4, R1.7, AE4 |
| 4 | KD5: demote "sole writer / impossible by construction" — mid-run outside drift is possible but a rare accepted window; no resident monitor/polling in v1 | agy-Pro `P1` + agy-Flash `P1` + codex `P2` + Claude PR4 | doc Problem frame / KD5 / Scope-out |
| 5 | "No new persistence" now correct for R1 — #279 R19 owns the write-record schema; R1 reads it | Codex `P1` (saga schema) | doc KD2, R1.2, R1.9 |
| 6 | Resolution offers {accept board / re-assert saga / pause-hold}; never force-heal | agy-Flash `P2` | doc R1.5 |
| 7 | Adopting a board-won value = append a `reconcile-override` write-fact (append-only-clean) | agy-Pro `P2` | doc R1.7 |
| 8 | Premise citation tightened; existing gated PR-merge writes noted | Codex `P2` | `outcome.py:1065`, `outcome_github.py:170,187` |
| 9 | R1 wires existing mission-control verbs (read for fetch, #279's for write-back); invents no board ops | Codex `P3` | doc R1.9 |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P0 | R1 duplicates #279's autonomous board-sync writer | Codex (repo) + Claude verify | Fixed (re-bound to reconcile-only) |
| P0 | Partial-failure scope blind spot (landed-but-unrecorded write hidden) | agy-Pro + agy-Flash + codex + Claude | Fixed (owned-field-class scope + idempotency-key cross-check; atomicity is #279's layer) |
| P1 | Reconcile-independence overstated | agy-Pro + agy-Flash + codex + Claude | Fixed (diff independent, resolution depends on #279) |
| P1 | "Sole writer / impossible by construction" false | agy-Pro + agy-Flash + codex + Claude | Fixed (demoted to accepted v1 window) |
| P1 | saga schema has no board write-facts yet | Codex | Fixed (#279 R19 owns the schema; R1 reads it) |
| P2 | No abort/rollback in resolution | agy-Flash | Fixed (pause/hold option) |
| P2 | Append-only adoption of a board value underspecified | agy-Pro | Fixed (reconcile-override fact) |
| P2 | Premise citation imprecise | Codex | Fixed |
| P3 | Mission-control verbs already exist | Codex | Fixed (wire existing, invent none) |
| — | Live read-before-write mid-run guard | agy-Flash | Not adopted for v1 — declined as over-engineering for a solo board; the false claim it rode on was adopted; logged as deferred hardening (KD5) |

## Residual risk

- **R1 is now tightly coupled to #279 and meaningless before it.** It reconciles #279's writes, reads
  #279's records/keys as its baseline, and re-drives through #279's adapter. It must be planned and
  built **after** #279. The dependency is honest and stated, but it is a hard sequence, not a soft one.
- **The R19-record-sufficiency assumption.** If #279's per-write record is thinner than a reconcile
  baseline needs, R1's first `/plan` task is a small bounded addition to #279's record field — not an
  R1 writer. Flagged in Dependencies.
- **Q1 (reconcile trigger) is genuinely open** — automatic-on-resume vs operator-invoked, and whether
  it rides the S-3 #281 resume path. First `/plan` task.
- **The re-bound shrank R1's identity** from writer+reconciler to reconciler-only. This removes
  duplication (not scope-minimizing for its own sake), and it matches the operator's reframe — but it
  is a material change from the issue the operator first named, so it is surfaced for confirmation
  before the board push rather than filed silently.
- **Single-routing note (positive).** codex ran wrapped through Headroom this pass; clean provenance,
  no integrity caveat.

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`, team `campps`), same pipeline as S-1 (#275) … R7 (#293) — **after operator
confirmation of the re-bound**, since R1's identity changed mid-review. Recipient action: `/plan`,
whose first task is the Q1 reconcile-trigger decision, then the saga-owned field-class enumeration +
idempotency-key cross-check (Q2), planned strictly after #279's writer ships.
