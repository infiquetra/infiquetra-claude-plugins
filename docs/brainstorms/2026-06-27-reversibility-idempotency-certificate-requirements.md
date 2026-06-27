---
date: 2026-06-27
topic: reversibility-idempotency-certificate
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-2 (Replace "Risk" Routing With a Computed Reversibility/Idempotency Certificate)
---

# Reversibility/Idempotency Certificate — One Authority for Autonomy

## Summary

Give saga **one computed authority over an operation's reversibility facts**, so "may saga do this
without a human?" is answered in exactly one place — conservative, enumerated, default-gate. Its first
consumer is autonomous `/outcome` board-sync: the engine's first autonomous writes across the
saga↔mission-control boundary, shipped inside a certified envelope rather than left to manual operator
keystrokes.

## Problem Frame

Saga decides autonomy today in **three or more scattered, hardcoded places**, each encoding a different
ad-hoc judgment with no shared definition of what makes an action safe to take without a human:

- `operator-keystroke-only` — the parent issue never auto-closes (`outcome_projection.py:81`).
- `had_side_effect → HALT` — a side-effected leaf never re-runs on a lesser backend while the operator
  is away (`outcome_dispatcher.py` `degrade_decision`).
- GitHub branch-protection — the existing PR squash-merge write side (`outcome_github.py:169-192`) is
  gated by CI/review status, an autoland-style certified envelope already living in the engine.

Each is a separate site, so there is no single answer to "what may saga do autonomously?" — the policy
cannot be audited in one place, cannot be extended without adding a fourth ad-hoc check, and the
*highest-value* autonomous behavior never ships because there is no principled envelope to ship it
inside.

That high-value behavior is **saga moving its own board during an `/outcome` campaign**. It is not
shipped: `outcome.py:369-373` explicitly defers every board mutation to "a later operator-initiated
mission-control consumer," and the projection is artifact-only (`outcome_projection.py:12-18`). So the
operator hand-drives the board — observed three times this campaign as manual board-add recovery on
issues #275 / #277 / #278. The saga↔mission-control write boundary is, today, **entirely
operator-initiated** (confirmed in both `outcome.py` and `outcome_projection.py`).

A note on the survivor's framing, corrected against the code: "risk" is **not** a literal routing field.
The backend recommender already routes on enumerated measured signals — `has_security`, `has_infra`,
`deployment_sensitive`, `needs_consensus`, `broad_independent_fanout`, `adversarial_confidence`
(`lifecycle_state.py:164-183`). The only conflation is one internal bool,
`elevated_risk = (has_security or has_infra or deployment_sensitive) and has_code_surface`. So this work
does **not** "remove risk routing." It builds the missing autonomy authority, decomposes the one real
proxy, and leaves the recommender untouched.

## Key Decisions

**KD1 — One authority over *facts*, not one decision.** The certificate computes an operation's
reversibility facts; it does **not** itself return a single verdict with a single default. Each consumer
applies *its own* default over the shared facts. This is load-bearing: the two call sites being unified
ask opposite-default questions over the same input — the new board-sync writer asks "may I perform this
write autonomously?" (**default GATE**), while the existing degrade ladder asks "may this leaf proceed
on a lesser backend while you are away?" (**default DEGRADE**, with side-effect as the HALT carve-out).
Forcing both through one predicate with one default would silently change the degrade behavior. One
definitional source for the facts; consumer-owned defaults.

**KD2 — Conservative, enumerated, default-gate — an allowlist, not a solver.** Reversibility and
abort-cost are not statically computable in general (the unanimous second-opinion refinement). The
certificate is therefore a **closed allowlist with default-deny**: an operation is autonomous only if it
is explicitly enumerated as safe; everything else gates. "Certificate" is the autoland-envelope metaphor
(autonomous only inside a certified envelope of enumerated conditions), **not** a claim of proof. The
doc uses the term in that bounded sense and nowhere implies a general reversibility decision procedure.

**KD3 — Subsume both existing invariants, proven-equivalent.** The two hardcoded autonomy checks are
rewritten to consult the single certificate: `had_side_effect → HALT` becomes the certificate's
"irreversible side-effect" fact; `operator-keystroke-only` becomes an `ALWAYS_OPERATOR` override entry
(parent-close is *reversible* — reopening exists — so it is a deliberate policy, not a reversibility
judgment, and the certificate respects it as a forced gate). After v1 there is **exactly one
definitional source** for autonomy with no residual ad-hoc checks. The rewrite must be behavior-equal to
today on both paths.

**KD4 — Three enumerated safety tiers.** The allowlist is not flat. An operation qualifies under exactly
one tier, each with a distinct safety justification:

| Tier | Justification | v1 members |
|------|---------------|------------|
| Reversible | A registered inverse exists (true undo) | board status-move ↔ revert · label add ↔ remove · nonprod-close ↔ reopen |
| Idempotent | Retry-safe via an idempotency key; re-apply is a no-op | (applies to every autonomous write — see R12) |
| Additive | Append-only, destroys no prior state, bounded abort-cost | issue progress comment |
| — (default) | Not enumerated → not autonomous | everything else → GATE |

Additive is deliberately separated from reversible: a comment has **no** true inverse (deleting it ≠
un-sending it — subscribers were already notified), so it is justified by bounded abort-cost, not by
reversibility. This keeps the autonomous progress-comment value the ideation called for ("good comments
= useful progress summaries, not robotic status pings") with honest reasoning.

**KD5 — First consumer is board-sync; merge/deploy are permanently outside the envelope.** The first
autonomous consumer is `/outcome` board-sync. PR-merge and deploy are **never** allowlisted — they stay
HITL regardless of how the certificate evolves. v1 does **not** touch the backend recommender
(`lifecycle_state.py`); the recommender is a *designed-for but unbuilt* future fact-consumer, and no v1
choice forecloses it.

## Actors

A1. **`/outcome` orchestrator** — the v1 consumer. At a board-relevant leaf transition it asks the
certificate, performs the write via mission-control when AUTHORIZED, and records a saga tick; otherwise
surfaces the op to the operator.

A2. **The operator** — receives every GATE'd op exactly as today, owns parent-close and all
non-allowlisted ops, and can always override an autonomous decision.

A3. **mission-control `sdlc_manager`** — executes the actual GitHub board mutation when saga drives it.
Today it is only ever operator-invoked; v1 opens it to saga for the enumerated ops only.

## Requirements

### The certificate (the authority)

R1. There is exactly **one** evaluable authority that answers, for a given operation, what its
reversibility facts are. No consumer computes these facts ad hoc; all consult the single source.

R2. The authority computes the facts the autonomy decision needs: `reversible` (registered inverse
exists), `idempotent` (retry-safe), `additive` (append-only, no prior-state destruction), `abort_cost`
(bounded vs unbounded), and `side_effected` (already produced an external side effect). The model
reserves room for routing-relevant facts (`recorded`/ephemeral, `cost`) a future backend consumer would
add, without building them in v1.

R3. Default is **GATE / deny**. An operation is autonomous only if explicitly enumerated. The authority
never infers autonomy for an unrecognized op.

R4. Facts are derived only from **durable saga state and the operation's declared definition** — never
guessed from prose, an agent summary, or absence. (The verify-before-claiming invariant, applied to the
autonomy decision.)

### Safety tiers, allowlist, and override

R5. **Reversible tier** — an op qualifies only if it carries a *registered inverse* that restores prior
state. v1 members: board status-move, label add/remove, nonprod-close-after-ACCEPT.

R6. **Additive tier** — an op qualifies if it is append-only and destroys no prior state, justified by
bounded abort-cost rather than reversibility. v1 member: issue progress comment.

R7. **`ALWAYS_OPERATOR` override** — a named set of ops that gate even when otherwise reversible,
because they are deliberate operator policy. v1 member: parent-issue close.

R8. Anything not enumerated under a tier and not in the override set → **GATE**. The allowlist is the
whole envelope; there is no "probably fine" path.

### Subsumption and migration equivalence

R9. The `had_side_effect → HALT` check in the degrade ladder is rewritten to consult the certificate's
`side_effected` / `reversible` facts, and must produce the **identical** halt/degrade decision as today
on every existing case.

R10. The `operator-keystroke-only` parent-close gate is rewritten to an `ALWAYS_OPERATOR` override
entry, and parent-close must remain gated in **every** case it is gated today.

R11. Each consumer retains its own default: the board-sync writer defaults to GATE; the degrade ladder
defaults to DEGRADE. The certificate supplies facts, not the default.

R12. The **only** new behavior introduced by v1 is autonomous authorization of the enumerated board
writes. No existing gate, halt, degrade, or routing decision changes behavior — equivalence is a
shipping requirement, not a hope.

### First consumer — autonomous board-sync

R13. At a board-relevant leaf transition, `/outcome` performs the enumerated reversible/additive board
writes autonomously when the certificate returns AUTHORIZED: status-move, label add/remove,
nonprod-close-after-tester-ACCEPT, and progress comment.

R14. A GATE'd board op surfaces to the operator exactly as the board surface does today — no autonomous
write, no silent skip.

R15. Every autonomous write is **idempotent** (carries an idempotency key; a retry after a crash or
duplicate trigger is a no-op, never a doubled side effect) and is **recorded as a saga tick** capturing
what was done, when, and why it was authorized — so the autonomous action is auditable after the fact.

R16. **PR-merge and deploy are never autonomous.** No allowlist entry exists for them; they remain
behind HITL and GitHub branch-protection regardless of the certificate.

R17. v1 does not modify the backend recommender. The facts authority is shaped so the recommender
*could* consume it later, but that consumer is out of scope here.

## Key Flows

F1. **Autonomous board-sync (happy path).** A leaf reaches a board-relevant state → `/outcome` asks the
certificate for that op → AUTHORIZED (reversible or additive tier) → saga drives mission-control to
perform the write → saga records a tick with the authorization basis.

F2. **Gate path.** The op is not enumerated, or is in `ALWAYS_OPERATOR` → certificate returns GATE →
saga surfaces it to the operator as today; no autonomous write occurs.

F3. **Subsumed degrade (equivalence).** A side-effected leaf, operator away → the degrade ladder asks
the certificate for `side_effected` → fact present → ladder applies its own default → HALT, the same
decision the hardcoded check produced before subsumption.

## Acceptance Examples

AE1. **Reversible authorized.** **Trigger:** a leaf enters review. The status-move to "In Progress" is
in the reversible tier → AUTHORIZED → performed autonomously and recorded as a tick. **Covers R5, R13,
R15.**

AE2. **Reversible close authorized.** **Trigger:** a leaf reaches tester-ACCEPT after nonprod-deploy.
The sub-issue close is reversible (reopen is the inverse) → AUTHORIZED → performed autonomously.
**Covers R5, R13.**

AE3. **Override gates a reversible op.** **Trigger:** an `/outcome` parent reaches all-leaves-complete.
Parent-close is reversible (reopen exists) but is in `ALWAYS_OPERATOR` → GATE → the operator closes it
by keystroke, exactly as today. **Covers R7, R10.**

AE4. **Additive authorized.** **Trigger:** a leaf advances a phase. A progress comment summarizing what
changed is in the additive tier → AUTHORIZED → posted autonomously. **Covers R6, R13.**

AE5. **Unenumerated op gates.** **Trigger:** a board op with no tier and no inverse (e.g. a destructive
relabel or any repo mutation) is requested → default GATE → surfaced to the operator. **Covers R3, R8,
R14.**

AE6. **Degrade equivalence.** **Trigger:** a destructive-leaf re-run is attempted while the operator is
away. The rewritten degrade path consults the certificate and returns the **same** HALT decision the
pre-subsumption code returned for that case. **Covers R9, R11, R12.**

AE7. **Merge is never autonomous.** **Trigger:** a PR is green and mergeable. No certificate allowlist
entry exists for merge → GATE; the merge stays behind operator action and branch-protection even though
`outcome_github.squash_merge` exists. **Covers R16.**

AE8. **Idempotent retry.** **Trigger:** an autonomous status-move is re-triggered after a crash. The
idempotency key makes the second attempt a no-op; the board is not double-written. **Covers R15.**

AE9. **Recommender unchanged.** **Trigger:** a plan that routed to team-execution before v1 is run
again. It still routes to team-execution; the recommender does not consult the certificate. **Covers
R17.**

## Scope Boundaries

**In scope (v1):**
- The single facts authority (R1–R4) and the three-tier allowlist + override + default-gate (R5–R8).
- Subsumption of the two existing autonomy invariants with proven equivalence (R9–R12).
- The first autonomous consumer: `/outcome` board-sync over the saga↔mission-control boundary (R13–R15).

**Out of scope (v1):**
- The backend recommender rewrite — a *future* fact-consumer; the `elevated_risk` conflation stays as-is
  in v1 (R17).
- PR-merge and deploy autonomy — permanently HITL, never allowlisted (R16), not a deferral.
- Any static reversibility solver — the envelope is enumerated by construction (KD2).
- Mid-flight interrupt / agent hot-swap (ideation R13, parked for feasibility) and capability-scoped
  agent sandboxing (ideation R14, promoted separately) — complementary but distinct; reversibility
  framing does not replace least-privilege for accidental or adversarial actions.

## Dependencies / Assumptions

- **Opens a currently-closed boundary.** v1 narrowly reverses the "all saga↔mission-control writes are
  operator-initiated" posture for the enumerated ops only. The recurring mission-control
  `create-prepared` PR-lookup defect lives on this same boundary; autonomous writes must handle its
  failure modes — relevant for `/plan`.
- **Verified — "risk" is not a literal routing field.** The recommender routes on enumerated measured
  signals (`lifecycle_state.py:164-183`); the lone conflation is `elevated_risk`. This work adds an
  autonomy authority and decomposes that one proxy; it does not delete a "risk router."
- **Verified — autonomous board-mutation is not shipped.** `outcome.py:369-373` defers it;
  `outcome_projection.py:81` is `operator-keystroke-only`. v1 ships the first such path. The ideation
  doc's "R1 REVIVED → live" is aspirational and is corrected here.
- **Verified — an autoland envelope already exists.** `outcome_github.py:169-192` has a write side
  (squash-merge, branch-update) gated by GitHub branch-protection — precedent for "autonomous inside a
  certified envelope." Merge nonetheless stays out of the saga-side allowlist (R16).
- **Assumption — autonomous progress comments are wanted** (ideation framing), justifying the additive
  tier; if not, drop R6 and the additive tier with no effect on the rest.

## Outstanding Questions

All deferred to planning; none block `/plan`.

- Where the certificate lives and the exact shape of the facts struct + allowlist registry → `/plan`.
- How a registered inverse is represented per reversible op (callable vs declarative) → `/plan`.
- Idempotency-key derivation for board ops — candidate reuse of the `repo:hash` pattern at
  `promote_scan.py:47` → `/plan`.
- The equivalence-proof method for the two subsumed call sites (golden tests over the existing decision
  tables are the likely shape) → `/plan`.
- The exact leaf-state → board-transition mapping (which saga states drive which writes), grounded in
  the existing `/outcome` state model → `/plan`.

## Sources

- **Ideation survivor S-2** — `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (3/3 ADVANCE;
  refinement: conservative + enumerated, default-to-gate when unproven, not sold as proof).
- **Recommender + the one conflation** — `plugins/saga/scripts/lifecycle_state.py:164-183`.
- **The two subsumed invariants** — `outcome_dispatcher.py` `degrade_decision` (`had_side_effect → HALT`)
  and `plugins/saga/scripts/outcome_projection.py:81` (`operator-keystroke-only`).
- **Deferred board mutation** — `plugins/saga/scripts/outcome.py:369-373`;
  `plugins/saga/scripts/outcome_projection.py:12-18`.
- **Existing write-side envelope** — `plugins/saga/scripts/outcome_github.py:169-192`.
- **Recorded-vs-ephemeral / cosmetic risk-lean** — `plugins/saga/references/operator-choice.md` §3.3 and
  the advisory/gated consensus rows (`:87`).
- **Enum surfaces** — `plugins/saga/scripts/saga.py:70-71` (`DESTINATIONS`, `ORCHESTRATION_MODES`).
- **Journal** — `DECISIONS.md` `#operator-choice-framework`; `LEARNINGS.md`
  `#operator-choice-ultracode-framing-and-docs-proxies` (the correction that ultracode *has* review
  depth — establishing why "risky → avoid workflows" is no longer about validation capacity).
- **External** — CAT-III autoland certification (the certified-envelope metaphor); Thread-Level
  Speculation (survivor basis).
