---
title: "Issue #626 — outcome settlement-halt for externally-executed leaves"
type: fix
status: active
date: 2026-07-24
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/626
---

# Issue #626 — outcome settlement-halt for externally-executed leaves

## Summary

Issue #626 reports two defects in the OutcomeOrchestrator's dispatch/settlement gate: (1) board-sync
breaks on the `advance --autonomous` path in consumer repos, and (2) a leaf executed **outside** the
engine process (`backend: cc-workflows-ultracode` — a cc-workflows-ultracode Workflow leaf) never
settles, so its dispatch position stays `open` forever and halts the whole outcome's frontier on
every later tick.

**This is a verify-and-close plan, not a build plan.** Verified live at `03c2640c` (saga 0.114.0,
fleet-core 0.23.0, mission-control 2.10.1), ~1.5 of the 2 defects are already shipped by sibling
leaves and the residual direction (a) is already wired and idempotent in the harvester:

- **Defect 1** (board-sync consumer-repo breakage) is **resolved by #620** (shipped saga 0.114.0);
  R10 resolution-level acceptance already PASSED. #626's job is a verification leg, not a fix.
- **Defect 2, direction (b)** (an operator settle/waive verb) is **shipped by #618** (saga 0.109.0):
  the `dispatch-waiver` mechanism already provides the human exit from a forever-halt.
- **Defect 2, direction (a)** (auto-settle a harvested Workflow completion) is **already built** and
  **backend-agnostic**: `production_harvester` reconciles every dispatched subplot's materialized
  GitHub completion into a `settle_attempt(... DELIVERED)` on every tick.
- **Defect 2, direction (c)** (`casualty_threshold_percent=0` default) is decided **Option A — leave
  0, rely on #618 waive** (operator decision, 2026-07-24). No code change.

So #626 ships **zero required production code change**. The deliverable is a set of
characterization/regression-lock tests that pin the already-correct behavior, a Defect-1 board-sync
verification, a documented threshold decision, and an operator-gated live leg that proves the
auto-settle chain fires end-to-end for a real externally-executed leaf before the issue closes.
Closing #626 clears the last blocker on `infiquetra-codex-plugins#45` (codex sub-45) — the campaign
critical path.

## Problem Frame

The incident behind #626: leaf `sub-13` of a prior outcome was dispatched to an external executor,
could not finish (blocked on a Stripe dependency), and was honestly settled `silent-no-op`. With the
default `casualty_threshold_percent = 0`, that single casualty breached the halt gate permanently,
freezing the entire outcome frontier. The issue conflates two orthogonal failure modes that the plan
must keep strictly separate:

- **"The external executor finished, but the engine never learned."** A `cc-workflows-ultracode`
  leaf completes its work outside the coordinator process (it merges a PR / closes an issue on
  GitHub), so no in-process settle fact is written and the position stays `open`. This is a
  *bookkeeping* gap — the position *should* settle `delivered`. → **Direction (a).**
- **"The unit is a genuine casualty."** A real, honest block (the Stripe dependency) that will not
  complete. This *should not* halt the whole outcome forever. → **Direction (c) / the #618 waive.**

Fixing (a) does nothing for a real casualty; fixing (c)/waive does not auto-settle a completed
Workflow leaf. The plan takes an explicit position on each and proves they compose correctly.

### The halt mechanism (verified at `03c2640c`)

- `dispatch_settlement.py:55` — `DEFAULT_THRESHOLD_PERCENT = 0`.
- `dispatch_settlement.py:1060-1069` — a leaf whose latest attempt carries no settlement is state
  `"open"`; `current_complete = all(state in LEDGER_CLASSIFICATIONS)` is then `False`.
- `dispatch_settlement.py:1075-1088` — the halt gate: for each attempt, `if len(unresolved_casualties)
  * 100 > threshold * len(attempt_units): unresolved_threshold_breach = True`; with `threshold = 0`
  any single casualty (`100 > 0`) breaches, and `progress_halt = not current_complete or
  unresolved_threshold_breach`.
- Exits from the halt: a late-delivery fact flipping the unit to `DELIVERED` (`:1083`), or a #618
  `dispatch-waiver` covering the cohort (`outcome.py:1206-1215`).

### The auto-settle chain — already wired, backend-agnostic (verified at `03c2640c`)

Every `advance` tick runs `production_harvester` (`outcome.py:2100-2209`). Two stages:

1. `outcome_orchestrator.harvest` (`outcome_orchestrator.py:186-274`) materializes each
   barrier-satisfied, closure-gate-passing node's **GitHub-canonical completion** (merged PR /
   closed issue) into the store as a `CompletionEvent(state="done")`, whose derived `is_success`
   property is then `True` (it is not a constructor field: `is_success` returns `state in
   SUCCESS_STATES`, and `SUCCESS_STATES = frozenset({"done"})` — `outcome_store.py:276-277`,
   `outcome_spec.py:78`).
2. The reconcile loop (`outcome.py:2148-2206`) iterates `outcome_dispatch_bindings(...)` — **every**
   dispatched subplot, with **no `site`/`backend` filter** — and for each subplot that has a
   materialized completion, calls:

   ```
   dispatch_settlement.settle_attempt(
       ledger, subplot_id=sid, dispatch_id=..., unit_id=sid, attempt=...,
       classification=(DELIVERED if is_success else SILENT_NOOP), ...)
   ```

Because the loop is keyed on *dispatched-and-has-a-completion*, not on execution site, an
externally-executed leaf's `open` position closes on the very tick that materializes its merged-PR /
closed-issue completion. **This is exactly #626's proposed direction (a) — already present.**

### Why the model is coherent, per execution outcome

| External leaf state | Completion event? | Settle | Position | Correct? |
|---|---|---|---|---|
| Succeeded (merged PR / closed issue) | `done` / `is_success` materialized by harvest | `DELIVERED` | closes → frontier advances | ✓ direction (a) |
| Still running (no merged PR yet) | none (barrier unsatisfied) | none | stays `open` | ✓ transient, correct |
| Genuinely blocked (Stripe) | none (never completes) | none | stays `open` → operator `waive` | ✓ direction (c) → #618 |

A silently-abandoned external leaf is an `open` position (waive territory), **not** a `SILENT_NOOP`
settle: the `SILENT_NOOP` branch (`:2192`) only fires when a *non-success completion event already
exists* in the store, which harvest-of-GitHub alone never writes.

### Idempotency — proven at the code level

`settle_attempt` (`dispatch_settlement.py:1545-1643`) is write-once per `(dispatch_id, unit_id,
attempt)`:

- Same classification already settled → returns the prior fact, **appends nothing** (`:1572-1594`);
  contradictory evidence under the same classification raises (`:1591`).
- Prior casualty → now `DELIVERED` → the idempotent **late-delivery** path (`:1595-1626`), which
  returns the prior late-delivery fact if present or appends exactly one.

So the harvester's every-tick re-settle of an already-settled leaf is a genuine no-op. This directly
answers the #626 pre-mortem's idempotency concern with no new code.

## Built-vs-Planned Reconciliation

| #626 element | Status at `03c2640c` | Evidence | #626 action |
|---|---|---|---|
| Defect 1 — board-sync `--autonomous` resolves mission-control at `<cwd>/plugins/...` + version-less schema path | **Shipped by #620** | `outcome.py:1023-1059` routes `if autonomous:` through `outcome_board_sync.reconcile_board` (five-rung `fleet_commons/plugin_resolution.py`); R10 PASS on record | **Verify**, don't re-implement |
| Defect 2b — operator settle/waive verb | **Shipped by #618** | `outcome.py:1206-1215` `active_waiver_covers`; `dispatch_settlement.py:27 WAIVER_KIND="dispatch-waiver"`; R9-accepted | **Out of build scope** |
| Defect 2a — auto-settle a harvested Workflow completion as `delivered` | **Already wired, backend-agnostic** | `outcome.py:2148-2206` reconcile loop over `outcome_dispatch_bindings`; settle idempotent `:1572-1626` | **Characterize + lock + R-live** |
| Defect 2c — `casualty_threshold_percent=0` default | **Decision: Option A (leave 0)** | `dispatch_settlement.py:55`; operator decision 2026-07-24 | **Document, no code change** |
| codex sub-45 (`infiquetra-codex-plugins#45`) | Blocked on `[sub-615, sub-626]`; sub-615 done | outcome DAG (Objective #639) | Out (note: closing #626 unblocks it) |

## Requirements

R1–R6 are the closable acceptance surface of #626 under Option A. There is **no acknowledged
extension beyond the issue** in build terms — the issue's directions (a) and (b) are already
satisfied and (c) is a deliberate no-change decision. The extension #626 *does* add over "just close
it" is the **R-live** proof leg (R-live), following the #615 R9 / #620 R10 operator-gated pattern,
because a defect this load-bearing should not close on a code read alone.

- **R1 (Defect 1 verification).** An `advance --autonomous` tick from a non-monorepo cwd resolves
  mission-control via the plugin ladder and board-syncs (the resolved root + rung appear on the
  record). Traceable to #620; re-asserted in the #626 context so the issue's own Defect 1 is
  discharged with evidence.
- **R2 (Defect 2a characterization).** A dispatched externally-executed leaf (`site` reflecting an
  external backend) whose GitHub completion is materialized by harvest auto-settles its `open`
  position `DELIVERED`, and the next `advance` dispatches the previously-blocked frontier.
- **R3 (idempotency).** Repeated `advance` ticks under the same completion append **nothing** to the
  settlement ledger for an already-`DELIVERED` position; a casualty→delivered transition appends
  exactly one late-delivery fact and no more.
- **R4 (coherence of the three external-leaf states).** A still-running external leaf stays `open`
  (no false settle); a genuinely-blocked leaf stays `open` and the #618 `waive` is the sanctioned
  exit; a non-success completion event settles `SILENT_NOOP` (fail-closed) rather than `DELIVERED`.
- **R5 (threshold decision — Option A).** `DEFAULT_THRESHOLD_PERCENT` stays `0`; no per-manifest
  knob and no global-default flip ship in #626. The waive verb is documented as the operator's
  casualty exit. The decision and its revisit-when condition are recorded in DECISIONS.
- **R6 (no regression, honest release surface).** The full suite stays green; the halt-gate and #618
  waiver seams are provably unweakened; release surfaces (if the PR carries tests/docs) tell the same
  story as the diff — a saga patch bump only, with no fleet-core / mission-control bump.
- **R-live (operator-gated).** Prove the auto-settle chain end-to-end against a **real
  externally-executed leaf**: run the harvester over its ledger + store, observe the `DELIVERED`
  settle fact land, and confirm the frontier advances. Operator names the subject; no live campaign
  card is mutated to satisfy an acceptance criterion.

## Key Technical Decisions

### KTD1 — `casualty_threshold_percent` stays `0`; genuine casualties exit via the #618 waive (Option A)

**Decision (operator, 2026-07-24): leave the default at `0`.** A genuinely-blocked leaf halting the
frontier and requiring an explicit operator `waive` is honest, auditable behavior — not a defect. The
two *actual* problems the incident exposed are already solved: a finished-but-unlearned Workflow leaf
now auto-settles `DELIVERED` (direction a, already wired), and a real casualty has a first-class human
exit (the #618 `dispatch-waiver`). What remains is a policy choice about how loud a genuine block
should be, and the loud/explicit posture is the safe default.

**Rejected — flip the global default to non-zero.** `DEFAULT_THRESHOLD_PERCENT` governs *every*
outcome-site manifest, not just Workflow-executed ones (`dispatch_settlement.py:293,1470,1678` all
default from it). Flipping it silently changes halt semantics for all outcomes and could let real
failures slip past the gate everywhere — the opposite of what the incident wanted.

**Deferred — a per-manifest threshold knob with a conservative default.** A reasonable future
ergonomics improvement if operator waive-toil becomes measurable. **Revisit when:** an operator is
repeatedly waiving the *same class* of deferred casualty across ticks, i.e. the waive verb has become
a recurring chore rather than an exceptional acknowledgement. No evidence of that today.

### KTD2 — #626 ships zero production code change; it is verify-and-close

Direction (a) is already built and idempotent (see Problem Frame). Re-implementing an auto-settle we
already have is pure risk against a heavily-tested, load-bearing halt gate. The plan therefore adds
**tests and docs only**, and stakes the close on the R-live proof rather than on new code.

**Rejected — add a second, redundant settle-on-harvest path** "to be explicit." It would duplicate
`outcome.py:2148-2206`, risk double-settle races against the existing loop, and weaken the
single-writer invariant for no behavioral gain.

### KTD3 — the new tests are characterization / regression-lock, not red-first

Because the mechanism already exists, a test asserting auto-settle **passes against current code**. The
plan states this plainly and **does not manufacture a fake red state**. To satisfy the "a load-bearing
test must be able to fail" instinct honestly, the *verification technique* is a throwaway
**stash/neuter probe**: during R-live, temporarily neuter the reconcile loop (comment out the
`settle_attempt` call in a `git stash`-backed scratch edit), confirm the characterization test goes
red and the frontier re-halts, then restore. The probe is a verification act, never a shipped change.

### KTD4 — the R-live subject must be an externally-executed leaf; sub-626 itself is inline

`sub-626` is planned as a native inline work saga (`issue-626`), executed in-context — it settles
in-process and never leaves an `open` position, so it does **not** exercise direction (a). R-live
therefore needs a distinct subject: either a hermetic dispatch of a `cc-workflows-ultracode` leaf that
leaves an `open` position and is then harvested, or a replay of the harvester against a prior
externally-executed leaf's committed ledger + store. The operator names the subject.

## Implementation Units

### U1. Characterization + regression-lock tests for direction (a)

`tests/test_dispatch_settlement.py` and/or `tests/test_outcome*.py`:

- An externally-executed leaf with an `open` position, given a materialized `done`/`is_success`
  completion, auto-settles `DELIVERED` after a harvester tick; the frontier then dispatches (R2).
- Idempotency: a second harvester tick over the same completion appends no new settlement fact; the
  casualty→delivered transition appends exactly one late-delivery fact (R3).
- Coherence: a still-running leaf (barrier unsatisfied) stays `open`; a non-success completion event
  settles `SILENT_NOOP`, not `DELIVERED`; a genuinely-blocked leaf stays `open` and a `dispatch-waiver`
  is what advances it (R4). These must not weaken the existing halt-gate or #618 waiver seams.

### U2. Defect-1 board-sync verification test

Re-assert #620 in the #626 frame: an `advance --autonomous` tick from a non-monorepo cwd resolves
mission-control via the ladder and records the resolved root + rung (R1). If `test_outcome_board_sync`
already covers this at parity, U2 is a reference to that coverage plus one #626-scoped assertion rather
than net-new duplication — adjudicate against the existing suite before adding.

### U3. Documentation

- DECISIONS `{#outcome-settlement-halt-externally-executed-626}` — KTD1 (Option A) with rationale,
  rejected alternatives, and the revisit-when condition; KTD2/KTD3 (verify-and-close posture, no fake
  red).
- `docs/work-sessions/2026-07-24-issue-626-*.md` — the built-vs-planned reconciliation and the R-live
  evidence.

### U4. Release surfaces (only if the PR carries tests/docs)

- saga patch bump `0.114.0 → 0.115.0` (tests + CHANGELOG are part of the plugin's shipped surface and
  the drift pins key on the version); marketplace sync; `plugins/saga/CHANGELOG.md`; drift pins
  (`tests/test_saga_plugin.py`, `tests/test_liveness_events.py`, `tests/test_team_execution_liveness.py`);
  `scripts/check_release_surface_parity.py` clean.
- **No** fleet-core bump (no `fleet_commons/` change) and **no** mission-control bump (no verb added).
- Merge-time sibling-PR version-collision re-check (has bitten repeatedly across this campaign).

## Risk Analysis & Mitigation

- **#628 cross-runtime double-dispatch (note, do not fix).** `outcome_dispatch_bindings` is keyed by
  `subplot_id` (one binding per sid). If a leaf is double-dispatched across runtimes (Claude v2-blindness),
  the auto-settle resolves one `dispatch_id`'s binding and may leave the other's position accounted
  differently. #628 owns this. The R-live observation must confirm the auto-settle does not *paper over*
  a double-dispatched ledger; #626 does not attempt to reconcile the two dispatches.
- **Evidence-vs-acceptance (known property, out of scope).** Settle-on-harvest fires on *barrier
  satisfaction* (merged PR / closed issue), not on code-review/QA acceptance, because
  `required_checks` is opt-in and no outcome spec declares it (`closure_gate` is inert today). A leaf
  that merged a bad PR would auto-settle `DELIVERED`. Under Option A this is acceptable — the frontier
  already trusts the same barrier — but the plan states it. Evidence-gated settle, if ever wanted, is a
  `required_checks` opt-in and a separate change.
- **Characterization-test blind spot.** A test that passes against current code proves no regression but
  not that the mechanism is load-bearing. Mitigated by the KTD3 stash/neuter probe during R-live.
- **Release-surface drift.** The recurring same-version sibling-collision failure — re-bump at merge
  time if a sibling PR lands the same saga version first.

## Scope Boundaries

**In:** verification of Defect 1 (R1); characterization + idempotency + coherence tests for direction
(a) (R2–R4); the documented threshold decision (R5); the R-live proof; release surfaces if code/tests
ship.

**Out:** re-implementing Defect 1 (shipped #620); a new waive verb (shipped #618); any rewrite of the
`dispatch_settlement` halt gate; the #628 double-dispatch fix; #642 installed-plugins staleness; #635
ship-ceremony branch-target; codex sub-45 (downstream — closing #626 unblocks it). No global-default
flip and no per-manifest knob (KTD1).

## Alternatives Considered

- **Flip `DEFAULT_THRESHOLD_PERCENT` to non-zero** — rejected (KTD1): changes halt semantics for every
  outcome; risks hiding real failures globally.
- **Per-manifest threshold field with a conservative default** — deferred (KTD1): sound future
  ergonomics, no current evidence of waive-toil.
- **Add an explicit second settle-on-harvest path** — rejected (KTD2): duplicates existing wiring,
  invites double-settle races, no behavioral gain.
- **Close #626 on the code read alone** — rejected: a load-bearing settlement defect earns an
  operator-gated live proof (R-live) before it closes.

## Acceptance Criteria

R1–R6 are satisfied by the U1/U2 test scenarios and the U3/U4 surfaces above. **R-live** is the
operator-gated leg, run post-merge under armed hooks following the #615 R9 / #620 R10 pattern: against
an operator-named externally-executed leaf, run the harvester over its committed ledger + store, assert
a `DELIVERED` settle fact lands for the previously-`open` position, confirm the next `advance`
dispatches the previously-blocked frontier, and (KTD3) confirm via a throwaway stash/neuter probe that
removing the reconcile loop re-halts the frontier — proving the auto-settle is what unblocks it. The
operator confirms the subject before the run; no live campaign card is mutated to satisfy an
acceptance criterion.

## Recommended Tier

opus / high — confirmed. The interrogation was a settlement-model design decision on the coordinator's
dispatch gate with a cross-runtime (#628) interaction, which warranted the tier even though the
resulting plan is a minimal-change verify-and-close. Execution (`/work`) is tests + docs and can run at
a lower tier; the R-live judgment stays at opus.
