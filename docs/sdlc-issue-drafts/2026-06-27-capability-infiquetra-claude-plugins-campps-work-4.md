---
title: capability: infiquetra-claude-plugins campps work
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: infiquetra-claude-plugins campps work

### Objective
Give saga one source of truth for the reversibility facts that gate autonomous action — a conservative,
enumerated, default-gate certificate exposing a single `authorize_write` verdict — and ship its first
consumer: autonomous `/outcome` board-sync, the engine's first autonomous writes across the
saga↔mission-control boundary (today entirely operator-initiated). Board objective:
`improve-claude-plugins`. Tier-3 of the VECU port-seeds campaign (after S-1 #275, S-7 #277, S-5 #278).

---
date: 2026-06-27
topic: reversibility-idempotency-certificate
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-2 (Replace "Risk" Routing With a Computed Reversibility/Idempotency Certificate)
---

# Reversibility/Idempotency Certificate — One Authority for Reversibility-Gated Autonomy

## Summary

Give saga **one source of truth for the reversibility facts that gate autonomous action**, exposing a
single write-authorization verdict so "may saga perform this write without a human?" is answered in
exactly one place — conservative, enumerated, default-gate. Its first consumer is autonomous `/outcome`
board-sync: the engine's first autonomous writes across the saga↔mission-control boundary, shipped
inside a certified envelope rather than left to manual operator keystrokes.

## Problem Frame

Saga's reversibility-based autonomy is decided in **scattered, hardcoded places**, each encoding a
separate ad-hoc judgment with no shared definition of what makes an action safe to take without a human:

- `operator-keystroke-only` — the parent issue never auto-closes (`outcome_projection.py:81`).
- `had_side_effect → HALT` — a side-effected leaf never re-runs on a lesser backend
  (`outcome_dispatcher.py:271`), a *no-duplicate-side-effect* rule (R23).
- GitHub branch-protection — the existing PR squash-merge write side (`outcome_github.py:169-192`) is
  gated by CI/review status, an autoland-style certified envelope already living in the engine.

Each is a separate site, so there is no single answer to "what reversible action may saga take
autonomously?" — the policy cannot be audited in one place and cannot be extended without adding yet
another ad-hoc check. (Three *other* gates — `attending`, `guarantee_bearing` in `degrade_decision`, and
the `elevated_risk` backend suppressor in `lifecycle_state.py:180` — also influence what runs, but they
are presence, guarantee, and backend-selection judgments, **not** reversibility facts; they stay
separate and this work does not touch them.)

The high-value behavior this unlocks is **saga moving its own board during an `/outcome` campaign**. It
is not shipped: `outcome.py:1062-1065` documents that the sub-issue close adapter "is deferred to a
later operator-initiated mission-control consumer, so `issue_close` stays `None` until then," and the
projection is artifact-only (`outcome_projection.py:12-18`). So the operator hand-drives the board —
observed three times this campaign as manual board-add recovery on issues #275 / #277 / #278. The
saga↔mission-control write boundary is, today, **entirely operator-initiated**.

A note on the survivor's framing, corrected against the code: "risk" is **not** a literal routing field.
The backend recommender already routes on enumerated measured signals — `has_security`, `has_infra`,
`deployment_sensitive`, `needs_consensus`, `broad_independent_fanout`, `adversarial_confidence`
(`lifecycle_state.py:164-183`). The only conflation is one internal bool,
`elevated_risk = (has_security or has_infra or deployment_sensitive) and has_code_surface`, and it gates
*backend selection*, not autonomy. So this work does **not** "remove risk routing"; it builds the
missing autonomy authority and leaves the recommender untouched.

## Key Decisions

**KD1 — One authority over the facts; one centralized verdict for the new writer; the existing degrade
order preserved.** The certificate is the single definitional source of an operation's reversibility
facts. For the **new** autonomous-write consumer it exposes a centralized `authorize_write` verdict
(AUTHORIZED / GATE, default GATE) — the write policy lives in the authority, not scattered into the
caller. For the **existing** degrade ladder it supplies one fact (`side_effected`) into that ladder's
*unchanged* ordered decision (`available → attending → guarantee_bearing → side_effected →
lower-rung-or-HALT`, `outcome_dispatcher.py:256-290`); the certificate does **not** impose a default on
the degrade path or rewrite its order. One authority owns the facts and the write verdict; the degrade
order keeps its full existing logic and consumes one certificate-owned fact.

**KD2 — Conservative, enumerated, default-gate — an allowlist, not a solver.** Reversibility and
abort-cost are not statically computable in general (the unanimous second-opinion refinement). The
certificate is therefore a **closed allowlist with default-deny**: facts are **declared per enumerated
op**, not derived by a solver; an operation is autonomous only if explicitly enumerated as safe;
everything else gates. "Certificate" is the autoland-envelope metaphor (autonomous only inside a
certified envelope of enumerated conditions), **not** a claim of proof.

**KD3 — Subsume the reversibility-based checks, proven-equivalent; scope the claim honestly.** The two
hardcoded *reversibility-based* autonomy checks are rewritten to consult the single certificate:
`had_side_effect → HALT` is preserved as the certificate's **unconditional no-duplicate-side-effect
fact** (kept verbatim in behavior — it is duplicate-prevention, *not* a reversibility judgment, since a
reversible side effect still must not be duplicated); `operator-keystroke-only` becomes an
`ALWAYS_OPERATOR` override entry, gated because it is a **deliberate operator policy (R25)**,
independent of whether the op is reversible. After v1 there is one definitional source for the
**reversibility/duplicate-side-effect facts that gate autonomous writes** — presence (`attending`),
guarantee (`guarantee_bearing`), and backend-selection (`elevated_risk`) gates legitimately remain
separate. The rewrite must be behavior-equal to today on both subsumed paths.

**KD4 — Two reason-tiers, with idempotency as a universal precondition.** An operation earns autonomy
under exactly one *reason* tier; idempotency is **not** a tier but a precondition required of every
autonomous write (R15):

| Tier | Why it is safe | v1 members (real mission-control ops) |
|------|----------------|----------------------------------------|
| Reversible | A registered inverse restores prior state | `set-field` Status ↔ revert · issue-label add ↔ remove · sub-issue close ↔ reopen |
| Additive | Append-only, destroys no prior state, abort-cost bounded *by construction* (R6 coalescing) | issue progress comment |
| — (default) | Not enumerated → not autonomous | everything else → GATE |

Additive is deliberately separate from reversible: a comment has **no** true inverse (deleting it ≠
un-sending it — subscribers were already notified), so it is justified by a *constructed* abort-cost
bound (R6), not by reversibility. Labels in the reversible tier are **issue-field labels only**; repo
label-definition create/delete is not autonomous.

**KD5 — First consumer is board-sync; merge/deploy are permanently outside the envelope.** PR-merge and
deploy are **never** allowlisted — they stay HITL regardless of how the certificate evolves. v1 does
**not** touch the backend recommender (`lifecycle_state.py`); the recommender is a *designed-for but
unbuilt* future fact-consumer, and no v1 choice forecloses it.

## Actors

A1. **`/outcome` orchestrator** — the v1 consumer. At a board-relevant leaf transition it asks the
certificate's `authorize_write` verdict, performs the write via mission-control when AUTHORIZED, records
a saga tick; otherwise surfaces the op to the operator.

A2. **The operator** — receives every GATE'd op exactly as today, owns parent-close and all
non-allowlisted ops, and can always override an autonomous decision.

A3. **mission-control `sdlc_manager`** — executes the actual GitHub board mutation when saga drives it:
add-item-to-project, `set-field` (Status/Objective), issue-label sync, issue-close, comment
(`sdlc_manager.py` board ops, e.g. `:1043`). Today only ever operator-invoked; v1 opens it to saga for
the enumerated ops only.

## Requirements

### The certificate (the authority)

R1. There is exactly **one** evaluable authority that, for a given operation, is the source of its
reversibility facts and (for the write consumer) its autonomy verdict. No consumer re-derives these.

R2. The authority **declares** the enumerated facts per allowlisted op: `reversible` (a registered
inverse exists), `additive` (append-only, no prior-state destruction), `abort_cost` (a declared bound).
It also exposes one *instance* fact, `side_effected` (this specific leaf has already produced an
external side effect), for the degrade consumer. Op-kind facts (reversible/additive) and op-instance
facts (side_effected) are distinct subjects and the authority must answer both. The model reserves room
for routing-relevant facts (recorded/ephemeral, cost) a future backend consumer would add, without
building them in v1.

R3. Default is **GATE / deny**. An operation is autonomous only if explicitly enumerated.

R4. Facts are declared from **durable saga state and the operation's enumerated definition** — never
guessed from prose, an agent summary, or absence.

### Safety tiers, allowlist, and override

R5. **Reversible tier** — an op qualifies only if it carries a *registered inverse* that restores prior
state. v1 members (real ops): board `set-field` Status, issue-label add/remove, sub-issue close. Labels
are **issue-field labels only**; repo label-definition mutations are not in scope.

R6. **Additive tier** — an op qualifies if it is append-only and destroys no prior state, with
abort-cost bounded **by construction**: autonomous comments are *coalesced* (one progress comment per
meaningful leaf transition, not per tick) so they cannot become notification spam. v1 member: issue
progress comment.

R7. **`ALWAYS_OPERATOR` override** — a named set of ops that gate even when otherwise reversible,
because they are deliberate operator policy (R25). v1 member: parent-issue close.

R8. Anything not enumerated under a tier and not in the override set → **GATE**. The allowlist is the
whole envelope; there is no "probably fine" path.

R9. **Idempotency is a universal precondition, not a tier.** Every autonomous write carries an
idempotency key so a retry after a crash or duplicate trigger is a no-op, never a doubled side effect.

### Subsumption and migration equivalence

R10. The `had_side_effect → HALT` check (`outcome_dispatcher.py:271`) is preserved as the certificate's
`side_effected` fact and must produce the **identical** halt decision as today — an unconditional
no-duplicate-side-effect HALT, not a reversibility re-derivation.

R11. The full degrade decision order is unchanged (`available → attending → guarantee_bearing →
side_effected → lower-rung-or-HALT`). The certificate supplies only the `side_effected` fact into it;
it does not introduce a default, collapse the order, or alter the `attending` / `guarantee_bearing` /
no-lower-rung-HALT branches.

R12. The `operator-keystroke-only` parent-close gate (`outcome_projection.py:81`) is rewritten to an
`ALWAYS_OPERATOR` override entry, and parent-close must remain gated in **every** case it is gated
today.

R13. The certificate is the one authority over the **reversibility/duplicate-side-effect facts that
gate autonomous writes**; it does not subsume the presence (`attending`), guarantee (`guarantee_bearing`),
or backend-selection (`elevated_risk`) gates, which remain separate and unchanged.

R14. The **only** new behavior introduced by v1 is autonomous authorization (and execution) of the
enumerated board writes. No existing gate, halt, degrade, or routing decision changes behavior —
equivalence is a shipping requirement.

### First consumer — autonomous board-sync

R15. v1 **builds** the saga→mission-control write adapters the enumerated ops need — including the
sub-issue close/reopen adapter that is deferred and unbuilt today (`outcome.py:1062-1065`,
`issue_close = None`). An op cannot be allowlisted without its adapter (and, for reversible ops, its
inverse).

R16. At a board-relevant leaf transition, `/outcome` performs the enumerated reversible/additive board
writes autonomously when `authorize_write` returns AUTHORIZED: `set-field` Status, issue-label
add/remove, sub-issue-close-after-tester-ACCEPT, coalesced progress comment.

R17. A GATE'd board op surfaces to the operator exactly as the board surface does today — no autonomous
write, no silent skip.

R18. An AUTHORIZED autonomous write that **fails** (the saga↔mission-control boundary is fault-prone —
the recurring `create-prepared` PR-lookup defect lives here) is **bounded-retried** via its idempotency
key, then **surfaced to the operator on exhaustion** — fail-loud, never silent-drop, never wedge the
campaign.

R19. Every autonomous write is **recorded as a saga tick** capturing what was done, when, and why
authorized — so the autonomous action is auditable, and `/resume` / `/retro` can read "what saga did
while you were away."

R20. **PR-merge and deploy are never autonomous.** No allowlist entry exists for them; they remain
behind HITL and GitHub branch-protection regardless of the certificate.

R21. v1 does not modify the backend recommender. The facts authority is shaped so the recommender
*could* consume it later, but that consumer is out of scope here.

## Key Flows

F1. **Autonomous board-sync (happy path).** A leaf reaches a board-relevant state → `/outcome` asks
`authorize_write` → AUTHORIZED (reversible or additive tier) → saga drives mission-control to perform
the write → saga records a tick with the authorization basis.

F2. **Gate path.** The op is not enumerated, or is in `ALWAYS_OPERATOR` → verdict GATE → saga surfaces
it to the operator as today; no autonomous write occurs.

F3. **Subsumed degrade (equivalence).** A side-effected leaf, operator away → the unchanged degrade
order runs; at the `side_effected` branch it reads the certificate's fact → present → HALT, the same
decision the hardcoded check produced before subsumption, with `attending` / `guarantee_bearing` /
no-lower-rung branches all intact.

F4. **Failed autonomous write.** `authorize_write` AUTHORIZED → mission-control write fails → bounded
idempotent retry → still failing → surfaced to the operator; the campaign is not wedged and no
duplicate is written.

## Acceptance Examples

AE1. **Reversible authorized.** **Trigger:** a leaf enters review. The `set-field` Status move to "In
Progress" is in the reversible tier → AUTHORIZED → performed autonomously and recorded as a tick.
**Covers R5, R16, R19.**

AE2. **Reversible close authorized — adapter built.** **Trigger:** a leaf reaches tester-ACCEPT after
nonprod-deploy. The sub-issue close (reopen is its inverse) is AUTHORIZED and performed via the
close/reopen adapter v1 builds. **Covers R5, R15, R16.**

AE3. **Override gates a deliberate-policy op.** **Trigger:** an `/outcome` parent reaches
all-leaves-complete. Parent-close is in `ALWAYS_OPERATOR` (deliberate policy, R25) → GATE → the operator
closes it by keystroke, exactly as today, regardless of reversibility. **Covers R7, R12.**

AE4. **Additive authorized and coalesced.** **Trigger:** a leaf advances a phase. One coalesced progress
comment is posted autonomously; rapid successive ticks do not each spawn a comment. **Covers R6, R16.**

AE5. **Unenumerated op gates.** **Trigger:** a board op with no tier (e.g. a repo label-definition delete
or any repo mutation) is requested → default GATE → surfaced to the operator. **Covers R3, R8, R17.**

AE6. **Degrade equivalence — full order preserved.** **Trigger:** a destructive-leaf re-run is attempted
while the operator is away. The unchanged order reads the certificate's `side_effected` fact and returns
the **same** HALT decision as the pre-subsumption code; an `attending` operator or a no-lower-rung case
still HALTs identically. **Covers R10, R11, R14.**

AE7. **Merge is never autonomous.** **Trigger:** a PR is green and mergeable. No certificate allowlist
entry exists for merge → GATE; the merge stays behind operator action and branch-protection even though
`outcome_github.squash_merge` exists. **Covers R20.**

AE8. **Idempotent retry on failure.** **Trigger:** an autonomous `set-field` write fails on the
mission-control boundary. It is retried under its idempotency key (no duplicate); on exhaustion it
surfaces to the operator and the campaign continues. **Covers R9, R18.**

AE9. **Recommender unchanged.** **Trigger:** a plan that routed to team-execution before v1 is run
again. It still routes to team-execution; the recommender does not consult the certificate. **Covers
R21.**

## Scope Boundaries

**In scope (v1):**
- The single facts authority + `authorize_write` verdict (R1–R4) and the two-tier allowlist + override +
  default-gate + universal idempotency (R5–R9).
- Subsumption of the two reversibility-based invariants with proven equivalence, degrade order preserved
  in full (R10–R14).
- The first autonomous consumer: `/outcome` board-sync over the saga↔mission-control boundary, including
  building the unbuilt write/close adapters and the failure-surfacing path (R15–R19).

**Out of scope (v1):**
- The backend recommender rewrite — a *future* fact-consumer; `elevated_risk` stays as-is (R21).
- The presence (`attending`), guarantee (`guarantee_bearing`) gates — separate autonomy-adjacent
  judgments, left unchanged (R13).
- PR-merge and deploy autonomy — permanently HITL, never allowlisted (R20), not a deferral.
- Any static reversibility solver — the envelope is enumerated by construction (KD2).
- Mid-flight interrupt / agent hot-swap (ideation R13, parked) and capability-scoped agent sandboxing
  (ideation R14, promoted separately) — reversibility framing does not replace least-privilege for
  accidental or adversarial actions.

## Dependencies / Assumptions

- **Opens a currently-closed, fault-prone boundary.** v1 narrowly reverses the "all saga↔mission-control
  writes are operator-initiated" posture for the enumerated ops only. The recurring mission-control
  `create-prepared` PR-lookup defect lives on this same boundary; R18's bounded-retry + fail-loud path
  is the direct response, and `/plan` must design against that failure mode.
- **The real board ops are mission-control verbs, not abstractions.** Add-item-to-project, `set-field`
  (Status/Objective), issue-label sync, issue-close, comment (`sdlc_manager.py`, e.g. `:1043`). The
  allowlist is expressed in those terms.
- **The close/reopen adapter is unbuilt** (`outcome.py:1062-1065`, `issue_close = None`); v1 builds it
  (R15). This is net-new code, not a wiring change.
- **Verified — "risk" is not a literal routing field** (`lifecycle_state.py:164-183`); the lone
  conflation is `elevated_risk`, and it gates backend selection, not autonomy. This work does not delete
  a "risk router."
- **Verified — the subsumed checks exist where claimed**: `had_side_effect → HALT`
  (`outcome_dispatcher.py:271`), `operator-keystroke-only` (`outcome_projection.py:81`).
- **Verified — an autoland envelope already exists** (`outcome_github.py:169-192` write side gated by
  branch-protection) — precedent for "autonomous inside a certified envelope." Merge nonetheless stays
  out of the saga-side allowlist (R20).
- **Assumption — autonomous progress comments are wanted** (ideation framing), justifying the additive
  tier under the R6 coalescing bound; if not, drop R6 and the additive tier with no effect on the rest.

## Outstanding Questions

All deferred to planning; none block `/plan`.

- Where the certificate lives and the exact shape of the facts/verdict structure + allowlist registry →
  `/plan`.
- How a registered inverse is represented per reversible op (callable vs declarative) → `/plan`.
- Board-op **idempotency-key** design — likely keyed on issue-number + target-state; the
  `promote_scan.py:47` `repo:hash` key is scanner-specific and not directly reusable → `/plan`.
- The equivalence-proof method for the subsumed paths (golden tests over the existing `degrade_decision`
  table are the likely shape) → `/plan`.
- The exact leaf-state → board-transition mapping (which saga states drive which writes), grounded in the
  existing `/outcome` state model → `/plan`.

## Sources

- **Ideation survivor S-2** — `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (3/3 ADVANCE;
  refinement: conservative + enumerated, default-to-gate when unproven, not sold as proof).
- **Recommender + the one conflation** — `plugins/saga/scripts/lifecycle_state.py:164-183` (and
  `:180` `elevated_risk`, a backend-selection suppressor).
- **The subsumed checks + full degrade order** — `plugins/saga/scripts/outcome_dispatcher.py:256-290`
  (`had_side_effect → HALT` at `:271`) and `plugins/saga/scripts/outcome_projection.py:81`
  (`operator-keystroke-only`).
- **Deferred board mutation / unbuilt close adapter** — `plugins/saga/scripts/outcome.py:1062-1065`
  (`issue_close = None`); `plugins/saga/scripts/outcome_projection.py:12-18` (no auto-push).
- **Real mission-control board ops** — `plugins/mission-control/scripts/sdlc_manager.py` (e.g. `:1043`
  add-item-to-project + label-field sync).
- **Existing write-side envelope** — `plugins/saga/scripts/outcome_github.py:169-192`.
- **Recorded-vs-ephemeral / cosmetic risk-lean** — `plugins/saga/references/operator-choice.md` §3.3 and
  the advisory/gated consensus rows (`:87`).
- **Enum surfaces** — `plugins/saga/scripts/saga.py:70-71` (`DESTINATIONS`, `ORCHESTRATION_MODES`).
- **Journal** — `DECISIONS.md` `#operator-choice-framework`; `LEARNINGS.md`
  `#operator-choice-ultracode-framing-and-docs-proxies`.
- **External** — CAT-III autoland certification (the certified-envelope metaphor); Thread-Level
  Speculation (survivor basis).

### Intent
Build a single certificate authority that declares per-op reversibility facts and answers
`authorize_write` (AUTHORIZED / GATE, default GATE) for autonomous writes; subsume the two existing
reversibility-based autonomy checks (`had_side_effect → HALT` at `outcome_dispatcher.py:271`,
`operator-keystroke-only` at `outcome_projection.py:81`) into it proven-equivalent while preserving the
full degrade order; and ship the first autonomous consumer — `/outcome` board-sync (`set-field` Status,
issue-label add/remove, sub-issue close, coalesced progress comment) — including the unbuilt write/close
adapters (`outcome.py:1062-1065`, `issue_close = None`) and a bounded-retry / fail-loud failure path.
Full requirements, flows, and acceptance examples are in the embedded brainstorm above and at
`docs/brainstorms/2026-06-27-reversibility-idempotency-certificate-requirements.md` (doc-review verdict
READY — `docs/reviews/2026-06-27-reversibility-idempotency-certificate-readiness.md`).

### Out-of-scope / non-goals
- The backend recommender rewrite — `elevated_risk` (`lifecycle_state.py:180`) stays as-is; it is a
  future fact-consumer, not v1.
- The presence (`attending`) and guarantee (`guarantee_bearing`) gates — separate autonomy-adjacent
  judgments in `degrade_decision`, left unchanged.
- PR-merge and deploy autonomy — permanently HITL, never allowlisted (not a deferral).
- Any static reversibility solver — the envelope is enumerated by construction.
- Repo label-definition create/delete — only issue-field labels are in the reversible tier.
- Mid-flight interrupt / agent hot-swap and capability-scoped agent sandboxing (separate ideation items).

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- A new certificate authority — `plugins/saga/scripts/<certificate>.py` (declared facts + `authorize_write` verdict + the enumerated allowlist registry; home is `/plan`'s call).
- `plugins/saga/scripts/outcome_dispatcher.py` — route the `had_side_effect` branch (`:271`) through the certificate's `side_effected` fact; the rest of the degrade order (`:256-290`) unchanged.
- `plugins/saga/scripts/outcome_projection.py` — express `operator-keystroke-only` (`:81`) as the `ALWAYS_OPERATOR` override entry.
- `plugins/saga/scripts/outcome.py` — build the deferred sub-issue close/reopen adapter (`:1062-1065`) and the `/outcome` board-sync consumer + failure-surfacing path.
- `plugins/mission-control/scripts/sdlc_manager.py` — the board-write verbs saga drives (`set-field`, add-item-to-project, issue-label sync, close, comment).
- `tests/test_reversibility_certificate.py` — verdict / subsumption-equivalence / board-sync / failure tests (repo-root collected).

### Tests to add or update
- Verdict: enumerated reversible/additive ops → AUTHORIZED; unenumerated → GATE (default-deny); `ALWAYS_OPERATOR` (parent-close) → GATE.
- Subsumption equivalence: golden tests over `degrade_decision` — the certificate-routed path returns the identical action for every (available / attending / guarantee / side_effected / lower-rung) case (AE6).
- Idempotency: a repeated autonomous write is a no-op under its key (AE8).
- Failure path: a failed mission-control write is bounded-retried then surfaced to the operator; campaign not wedged, no duplicate (AE8).
- Additive coalescing: rapid successive ticks yield one comment, not many (AE4).
- Merge never autonomous: no allowlist entry → GATE (AE7).

### Context library links
- source_context: docs/brainstorms/2026-06-27-reversibility-idempotency-certificate-requirements.md
- doc_review: docs/reviews/2026-06-27-reversibility-idempotency-certificate-readiness.md
- ideation: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-2

### Acceptance criteria
- [ ] The certificate is the sole authority: enumerated ops → AUTHORIZED, everything else → GATE (default-deny). Check: `uv run pytest tests/test_reversibility_certificate.py -k authorize_verdict` → passes.
- [ ] Subsumption is behavior-equal: the certificate-routed `degrade_decision` returns the identical action on every existing case, with `attending` / `guarantee_bearing` / no-lower-rung branches intact. Check: `uv run pytest tests/test_reversibility_certificate.py -k degrade_equivalence` → passes.
- [ ] `/outcome` autonomously performs the enumerated board writes (`set-field` Status, issue-label, sub-issue close, coalesced comment) via the v1-built adapters, recorded as ticks. Check: `uv run pytest tests/test_reversibility_certificate.py -k board_sync` → passes.
- [ ] A failed autonomous write is bounded-retried then surfaced to the operator; no duplicate, campaign not wedged. Check: `uv run pytest tests/test_reversibility_certificate.py -k failure_surface` → passes.
- [ ] Merge, deploy, and parent-close are never autonomous (GATE). Check: `uv run pytest tests/test_reversibility_certificate.py -k always_gated` → passes.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/` → all pass.

### Verification
```bash
# Certificate + subsumption-equivalence + board-sync + failure tests
uv run pytest tests/test_reversibility_certificate.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/
```
Expected: all green; the certificate is the one authority for reversibility-gated autonomous writes,
subsumption is proven-equivalent on the degrade path, and `/outcome` autonomously syncs the board inside
the enumerated envelope with a fail-loud failure path.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-27-reversibility-idempotency-certificate-requirements.md
- Source type: brainstorm
- Source title: Reversibility/Idempotency Certificate — One Authority for Reversibility-Gated Autonomy
