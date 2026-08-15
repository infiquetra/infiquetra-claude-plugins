---
title: Orchestrate — boundary correction and review machinery
type: refactor
status: active
date: 2026-08-15
origin: docs/plans/2026-08-15-orchestrate-architecture-correction.md
---

# Orchestrate — boundary correction and review machinery

## Summary

Implement the two-part architecture correction: move the durable register's boundary so it stops
shadowing session facts the terminal multiplexer already owns, and give every review layer a loop
that terminates by construction. Supersedes the **unit breakdown** in
`docs/plans/2026-08-12-orchestrate-plugin-plan.md`; that plan's problem frame, evidence ledger and
module inventory still stand.

## Problem Frame

The composition unit is halted after five repair rounds with seven merge-blocking defects and a
three-vendor panel that declined to merge. The correction doc established why: none of the seven is a
logic error, and every one sits where the durable table meets the world. Separately, two campaigns
failed on review loops that could not terminate — one unbounded in breadth, one in depth.

This plan turns those two conclusions into landable units, and settles with evidence a question the
correction doc left open: whether to repair the halted unit in place or rebuild it.

---

## Grounding: what the halted unit is actually made of

An abstract-syntax-tree walk of `plugins/orchestrate/skills/orchestrate/scripts/runner.py` (3,656
file lines; 2,882 inside function and method bodies; `Coordinator` alone is 2,244 lines across 72
methods), with each method classified by whether it exists to reconcile the register's copy of
session facts against the world, or to compose modules that stop at their own boundaries:

| bucket | approx. lines | share of def-lines | representative members |
|---|---|---|---|
| substrate reconciliation | ~1,218 | ~42% | pid supervisor 116, `find_orphan` 40, `is_record_alive` 22, `stop_record` 21, `reconcile_startup` 75, `interrupted_dispatches` 68, `ensure_subscriber` 90, `stop_writers` 86, `_fence_producer` 62, route/launch custody 105, redelivery 117 |
| genuine composition | ~1,664 | ~58% | `launch_child` 120, `acceptance_receipt` 109, `spend_status` 81, dispatch claim family 143, plan parse/persist/approve 178, `integrate_child` 78, mirror glue 75, operator channel 76, ledger, subscription set |

The classification is the planner's, from the AST inventory plus the module docstrings; treat the
percentages as a well-grounded estimate, not a measurement.

**Where the seven merge-blocking defects fall:**

| defect | bucket | consequence of the boundary move |
|---|---|---|
| failed process query read as a negative result | substrate | evaporates — the query goes away |
| substring process identity, first match wins | substrate | evaporates — same |
| reused process id signalled | substrate | evaporates — same |
| replacement without confirming the prior stop | substrate | evaporates — liveness becomes a pane lookup |
| retry after a post-launch error opens a second paired session | substrate | mostly evaporates — becomes discover-then-adopt |
| provenance-blind terminal state opens the retirement gate | substrate | evaporates — the column stops existing |
| **session label is not injective** | composition | **survives — needs a fix on its merits** |
| **spend ceiling cannot tell unknown from zero** | composition | **survives — needs a fix on its merits** |

### KTD1 — Neither repair-in-place nor rebuild: move the boundary first, then repair what is left

Rebuilding discards ~1,664 lines of composition that the boundary move does not touch. A sixth
repair round spends effort on ~1,218 lines that are about to shrink or disappear, and five rounds of
evidence say that round would be followed by a seventh.

**Decision:** land the boundary move as units on the existing halted branch. Six of the seven
defects are expected to disappear as a consequence rather than as a repair. The two that survive get
units of their own, ranked on their own merits. The branch's safety ref is preserved throughout.

**Falsifiable prediction, and the gate on it:** after U1–U4, re-running the panel's own reproductions
must show the six substrate defects unreachable. If any survives, the boundary move did not do what
this plan claims and the unit escalates rather than continuing to U5 — the escalation budget from the
review machinery, applied to this plan's own execution.

---

## Requirements

**R1.** The durable register persists intent and outcome only. `pane_id`, `tab_id`, `cwd`, `pid`,
`observed_state` and `vendor` are no longer written to or read from a row.

**R2.** Session facts are answered by the multiplexer at read time, through one function per fact, so
there is a single place each question is decided.

**R3.** A query the multiplexer cannot answer is distinguishable from an answer of "nothing found",
and every consumer of the former fails closed.

**R4.** The event subscriber runs as the same script with the same argument vector inside a managed
pane. It remains a plain process: no vendor, no model, no tokens.

**R5.** The orchestrator checks the subscriber's pane before treating silence as "no events", on
every wake.

**R6.** `task_label` is injective over `(run_id, row_id)`: no two distinct valid pairs produce the
same label, proven by a property test over identifiers containing the delimiter.

**R7.** The spend ceiling distinguishes a row whose spend is unknown from a row whose spend is zero.
An unknown row fails the ceiling closed rather than being omitted from the total.

**R8.** `session_lifecycle` retains only tier, scope, label and landing. Session creation is
delegated to the wrapper and session driving to the multiplexer.

**R9.** Every review layer runs under a loop bound: at most three iterations per unit, re-review
scoped to the delta, findings deduplicated by defect class rather than by location.

**R10.** A review emits one of three verdicts: `pass`, `halt-and-repair`, `halt-and-escalate`.

**R11.** `halt-and-escalate` is emitted mechanically when one defect class recurs in a third
iteration, independent of the rank that class was given.

**R12.** A unit may escalate once. The budget is a constant in code, not a parameter.

**R13.** The consensus panel is separable from the loop bound and is configured per layer: required
for code review and qa, optional for doc review, absent for the orchestration-plan review.

**R14.** A dimension declares its instrument — gate or score. Where a layer carries both, the rank
binds the decision and the score records convergence.

**R15.** The orchestration-plan rigor pass applies evidence-backed safe fixes in place and reports
the remainder with recommendations, then hands the plan to the operator, who is its only voter.

**R16.** `/code-review` and `/doc-review` dispatch an external reviewer through a managed session.
The operator-facing offer, its durable gate-record contract, provider and egress selection, tier
selection, and atomic persistence of request state are unchanged.

**R17.** An external-only offer mode exists, which excludes the home vendor's panel entirely.

**R18.** Losing quorum under external-only halts and tells the operator. It never falls back to the
excluded vendor.

---

## Key Technical Decisions

**KTD1 — Move the boundary first, then repair what survives.** Recorded above with its evidence and
its falsifiable gate.

**KTD2 — One read-through function per session fact, not a substrate object.** A `SessionFacts`
value object rebuilt per read would re-create the shadow with a shorter lifetime and reintroduce the
same divergence within a single call. Each fact gets a named function that asks and answers now.
Rejected: caching with a TTL — a TTL is a shadow whose staleness is a tunable.

**KTD3 — The multiplexer's "cannot answer" is an exception, not a sentinel.** Sentinel returns are
what produced the recurring class nine times. The existing discovery helper already raises on every
failure path and returns a value only after a complete, well-formed query; the read-through functions
follow that precedent rather than inventing a result wrapper.

**KTD4 — The label becomes injective by encoding length, not by changing the delimiter.** Choosing a
delimiter that "cannot appear" is a claim about identifiers this codebase does not own. Encoding the
run identifier's length makes collision impossible for any pair. Rejected: hashing — it makes the
label unreadable in a pane list, which is the operator-facing property that made labels useful.

**KTD5 — Unknown spend is a distinct total, not an excluded row.** The accounting module already
documents that excluding is not charging zero; the ceiling gate makes it so anyway. The total becomes
a pair — a known sum and an unknown-row count — and the gate refuses on a non-zero unknown count
rather than comparing a smaller number to the ceiling.

**KTD6 — The loop bound ships as a module, the panel as a separate module.** They are separable by
design and configured per layer. A single "review protocol" object would force doc review to carry
panel machinery it does not use, and force the orchestration-plan review to carry a scoring
denominator with one voter in it.

**KTD7 — Defect-class identity is declared by the reviewer, reconciled by the engine.** A reviewer
names the class it believes a finding belongs to; the engine tracks recurrence across iterations. It
is not inferred from summary text, because inference across vendors with different phrasing is the
kind of fuzzy match that fails silently and would make the escalation trigger unreliable.

**KTD8 — The external-session transport is a new `Runner` implementation, not a rewrite.**
`second_opinion.dispatch_second_opinion` already takes `runner: engine_dispatch.Runner` as an
injected protocol (`plugins/saga/scripts/second_opinion.py:971`). The change is an additional runner
plus its selection, leaving the 1,496-line module's contract intact.

---

## Execution order — the loop bound ships first and governs everything after it

U-IDs below are stable and are **not** the execution order. The review loop bound (U6) has no
dependencies, and every other unit in this plan is reviewed. So it is built **first**, and from the
moment it exists, every subsequent unit's review runs through it:

```
   U6  review loop bound  ────────────┐
        (3 iterations/unit,           │  governs the review of
         delta-scoped re-review,      │  every unit below it
         dedup by class,              │
         three verdicts,              │
         escalation budget = 1)       │
                                      ▼
   U1  register keeps intent      ──► reviewed under the bound
   U2  session facts are asked    ──► reviewed under the bound
   U3  subscriber becomes a pane  ──► reviewed under the bound
   U4  remove the seam            ──► reviewed under the bound  ── GATE
   U5  label + spend              ──► reviewed under the bound
   U7  panel + rigor pass         ──► reviewed under the bound
   U8  saga transport             ──► reviewed under the bound
```

This is deliberate and it is the plan's own answer to how the last campaign failed: the previous unit
ran five review rounds because no bound existed. Building the bound first means this plan cannot
repeat that, and it **dogfoods the machinery by real use** rather than by its unit tests alone — the
loop bound is exercised seven times before anything else depends on it being right.

**U6 itself is reviewed under the unbounded process**, because it is what makes the process bounded.
That is unavoidable and it is the reason U6 is specified tightly and kept small. Its review is
explicitly capped at three iterations by hand.

**R19.** Every unit in this plan after U6 has its review conducted through the shipped loop bound,
not by an ad-hoc protocol. A unit whose review cannot be run through it is a defect in U6.

### Waves — the critical path is the dependency chain, not concurrency

Concurrency is bounded **per vendor**, not in total: a unit's builder plus its two-reviewer panel
(reviewers are never the builder's vendor) consumes exactly one slot per vendor, so three units can
be in flight at once and still sit at each vendor's cap. The limiter here is the U1→U5 dependency
chain, not the fleet.

```
   WAVE 0   U6  review loop bound            <- everything waits on this
              |
   WAVE 1   U1 register   U7 panel+rigor   U8 saga transport   <- 3 in parallel,
              |            (dep: U6)        (dep: none)           builder rotated
              |                                                   across vendors
   WAVE 2   U2 session facts are asked
              |
   WAVE 3   U3 subscriber becomes a pane
              |
   WAVE 4   U4 remove the seam  ============ GATE: are the six unreachable?
              |                              fail -> escalate, do not continue
   WAVE 5   U5 label injective + unknown spend
```

Six waves for eight units. U7 and U8 fold into the chain's shadow rather than extending it.

---

## Implementation Units

U-IDs are stable identifiers, not an order — see **Execution order** above. U1–U5 land on the halted
composition branch; U6–U7 are new modules in the orchestrate plugin; U8 touches the saga plugin and
has a different blast radius.

### U1. Register keeps intent and outcome

Remove the substrate columns from the register's schema, its ownership table, and every writer.

**Requirements:** R1.
**Files:** `plugins/orchestrate/skills/orchestrate/scripts/register.py`, and every module that writes
a substrate column.
**Depends on:** nothing.
**Test scenarios** (`tests/test_orchestrate_register.py`): writing a substrate column raises rather
than being silently accepted; a row round-trips through persistence carrying intent and outcome only;
an abstract-syntax-tree walk asserts no module writes a removed column, so the guard is structural
rather than conventional.

### U2. Session facts are asked, not stored

Add one read-through function per session fact, each asking the multiplexer and raising when it
cannot answer.

**Requirements:** R2, R3.
**Files:** `session_lifecycle.py` (the read-through functions), `runner.py` (call sites).
**Depends on:** U1.
**Test scenarios** (`tests/test_orchestrate_session_lifecycle.py`): a fact present in the snapshot is
returned; a fact absent from a complete snapshot returns the absence; a snapshot that cannot be
obtained raises and does not return an absence; a test walks the module's syntax tree to assert each
fact has exactly one asking site.

### U3. The subscriber becomes a managed pane, with a deadman

Start the subscriber in a managed pane with the same argument vector. Replace pid-based liveness with
a pane lookup. Check the pane on every orchestrator wake before treating silence as quiet.

**Requirements:** R4, R5.
**Files:** `runner.py` (supervisor and its callers), `subscriber.py` (start path only; the event
loop and the wake push are unchanged).
**Depends on:** U2.
**Test scenarios** (`tests/test_orchestrate_composition.py`): the subscriber is started in a pane and
its argument vector is byte-identical to the current one; liveness is answered by a pane lookup and
never by a process table; a wake with a missing subscriber pane surfaces the loss rather than
proceeding; the pid supervisor and its identity helpers are gone, asserted by name.

### U4. Remove the reconciliation seam

Delete the composition code that exists only to reconcile the register's copy against the world, and
thin the paths that partially did.

**Requirements:** R8. Closes six of the seven defects as a consequence.
**Files:** `runner.py`, `session_lifecycle.py`.
**Depends on:** U3.
**Test scenarios** (`tests/test_orchestrate_composition.py`): each of the six substrate defects is
re-run from the panel's own reproduction and is unreachable — six named regression tests, one per
defect, each describing the behaviour rather than its provenance; the surviving composition
properties (launch-once under a real two-process barrier, retirement refusing beside a live writer,
acceptance receipt sealing) still hold unchanged.

**Gate:** if any of the six survives, this unit escalates rather than continuing.

### U5. Two defects that survive the boundary move

Make the session label injective, and make the spend ceiling distinguish unknown from zero.

**Requirements:** R6, R7.
**Files:** `session_lifecycle.py` (`task_label`), `accounting.py` (`run_actual_tokens` and the
ceiling gate), `runner.py` (the gate's caller).
**Depends on:** U4.
**Test scenarios:** a property test over identifiers containing the delimiter asserts no two distinct
valid pairs collide (`tests/test_orchestrate_session_lifecycle.py`); a run with one unknown-spend row
refuses a launch that the current total would have allowed, and the refusal names the unknown row
(`tests/test_orchestrate_accounting.py`).

### U6. The review loop bound

A module implementing iteration counting, delta scoping, defect-class dedup, the three verdicts, and
the fixed escalation budget.

**Requirements:** R9, R10, R11, R12.
**Files:** new `plugins/orchestrate/skills/orchestrate/scripts/review_loop.py`.
**Depends on:** nothing. **Built first** — see Execution order.
**Test scenarios** (`tests/test_orchestrate_review_loop.py`): a fourth iteration is refused; a
re-review receives only the delta; the same class in a third iteration yields `halt-and-escalate`
regardless of its rank; a second escalation for one unit is refused; the escalation budget is a
constant with no parameter path to change it, asserted by a syntax-tree walk.

### U7. The consensus panel and the orchestration-plan rigor pass

Per-lens scoring, quorum, vendor exclusion, per-dimension instrument selection, and the single-voter
rigor pass over an orchestration plan.

**Requirements:** R13, R14, R15.
**Files:** new `consensus_panel.py`; `planning.py` (the rigor pass over a plan).
**Depends on:** U6.
**Test scenarios** (`tests/test_orchestrate_consensus_panel.py`): a reviewer whose vendor built the
unit is excluded from the roster; losing a voting seat below quorum halts the panel rather than
scoring a smaller denominator; a gate dimension refuses a numeric threshold and a score dimension
refuses a rank; the rigor pass applies a safe fix in place and reports the remainder with a
recommendation, and never returns a verdict of its own.

### U8. External reviewers as managed sessions, and an external-only mode

A new `Runner` that dispatches into a managed session, its selection, the external-only offer mode,
and the quorum-loss halt.

**Requirements:** R16, R17, R18.
**Files:** `plugins/saga/scripts/second_opinion.py` (runner selection only),
`plugins/saga/scripts/engine_offer.py` (the new mode), `plugins/saga/skills/code-review/SKILL.md`,
`plugins/saga/skills/doc-review/SKILL.md`.
**Depends on:** nothing in this plan; independent blast radius.
**Test scenarios** (`tests/test_saga_second_opinion.py`): the managed-session runner satisfies the
existing `Runner` protocol and the module's contract is unchanged; the offer surface is
byte-identical apart from the new mode; external-only excludes the home panel; quorum loss under
external-only halts and does not fall back; the gate-record contract still opens, satisfies, and
resolves-absent exactly as before.

---

## Scope Boundaries

**Out of scope — true non-goals.** Rewriting the paired worker session or the completion gate; both
were examined and stay in their current roles. Changing the operator-facing offer wording in either
saga skill. Changing what the register stores about intent or outcome.

**Deferred to follow-up work.** The lens roster for code review, and whether lenses are named
personas or model-and-effort combinations — the operator has called this secondary. Whether qa's
panel uses code review's roster. How the rigor pass expresses a missing acceptance test: a gate
dimension or a refusal to launch. The surface unit's version alignment, which is blocked until the
composition branch lands. The port to the companion repository, which is gated behind a live
acceptance run.

---

## Risk Analysis and Mitigation

**The boundary move does not close the six defects.** This is the plan's central claim and it is
falsifiable. U4 carries a gate that re-runs the panel's own reproductions; failing it escalates
rather than continuing. Mitigation is the gate itself, not optimism.

**The multiplexer is asked too often.** Replacing stored facts with queries trades a divergence risk
for a latency and availability risk. Mitigation: the read-through functions are per-fact and called
at decision points rather than in loops, and KTD2 explicitly rejects the caching that would trade the
risk back.

**The review machinery is built by the process it constrains.** U6 alone is reviewed under the
unbounded process, since it is what makes the process bounded; its review is capped at three
iterations by hand. Every other unit, U7 included, is reviewed through the shipped bound (R19).
Mitigation: U6 is small and tightly specified, its test scenarios are its specification, and it is
exercised seven times by real use before anything depends on it being right.

**Saga skill changes have a wider blast radius than orchestrate.** U8 touches two shipped skills.
Mitigation: the injected-runner seam means the module contract is unchanged, and the test scenarios
require the offer surface to be byte-identical apart from the new mode.
