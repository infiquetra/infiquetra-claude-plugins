---
title: "capability: dispatch settlement — fan-out manifest, casualty reconciliation, spawn-settle ledger, and dead-letter re-dispatch"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Govern fleet concurrency and reclaim leaked resources
---

# capability: dispatch settlement — fan-out manifest, casualty reconciliation, spawn-settle ledger, and dead-letter re-dispatch

### Objective

Govern fleet concurrency and reclaim leaked resources

### Tier

structural

### Wave

wave-1

## Summary

Every fan-out site in this fleet (team-execution reviewer/validator dispatch, `/outcome` leaf
dispatch, workflow emitters) can lose units silently today — a spawned agent can die, rate-limit
out, or leak a worktree, and the run keeps going as if nothing happened. This capability adds one
shared accounting contract across those sites: every fan-out writes a **dispatch manifest** (N
expected, unit IDs, expected deliverables) at spawn time; a **settlement pass** reconciles
delivered-vs-manifest and classifies every non-delivery (rate-killed, silent-no-op, idle,
leaked-worktree) into a structured casualty report; unsettled units land in a **dead-letter queue**
that the next advance re-dispatches at-least-once; and every spawn/settle event writes an
append-only **ledger** so `reconcile --leaks` can report open positions (spawned-but-unsettled)
independent of agent self-report. This deliberately adds zero throttling machinery — it is
detection and accounting, not a concurrency knob.

## Problem Frame

Three converging gaps, independently observed and already partially precedented in this repo:

1. **No fan-out accounting at all.** The recurring rate-limit failure pattern is not the absence
   of a concurrency knob — it is that most of a fan-out can die and the run proceeds as if it
   fully succeeded: "6 of 7 agents failed on rate-limiting... the emitter has no concurrency
   knob... KTD6 was aspiration, not machinery," observed across 3 repos
   (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §6 pattern 4, §7 pattern 4). The only
   existing concurrency-adjacent precedent in this fleet is a *prevention* cap, not a
   *reconciliation* mechanism: `VERIFY_N_CAP = 7` (`plugins/saga/scripts/execution_spec.py:114`)
   bounds refute-N verifier panel width but does nothing once a fan-out is already in flight.
   `/optimize` deliberately sheds the analogous `max_concurrent` fan-out and worktree-per-experiment
   isolation as a default (`plugins/saga/skills/optimize/SKILL.md:17-19`) — this capability does
   not re-litigate that shed; it is orthogonal (accounting, not throttling) and applies to
   team-execution/`/outcome` fan-out sites `/optimize` does not touch.
2. **Reviewer/validator fan-out has no delivered-vs-expected check.** team-execution's reviewer
   consensus step (`plugins/team-execution/skills/team-execution/SKILL.md:340`, Step B2:
   "Reviewers Reach Consensus") and its scanner/validator step (`SKILL.md:352`, Step B3) fan out to
   N reviewers/validators per `consensus-protocol.md` with no manifest of who was dispatched and no
   reconciliation of who actually returned a verdict — a reviewer that silently times out or
   returns nothing is indistinguishable from one that was never dispatched.
3. **Worktree/resource leaks are already a known, partially-solved shape — but only for
   `/outcome` worktrees, and only as leak-prevention, not general settlement.** `/outcome`'s
   worktree layer already tracks a live registry and reaps orphans rather than losing them silently
   (`plugins/saga/scripts/outcome_worktrees.py:254` `reap_worktree`, `:297` `harvest_worktrees`,
   comment at `:260`: "on disk would drop it from the cap accounting and leak it silently — the
   registry is the only record"). This is exactly the double-entry spawn/reap shape this capability
   generalizes, but today it is scoped to `/outcome` worktrees only — team-execution fan-out and
   the workflow emitter have no equivalent ledger, so a leaked reviewer spawn or an
   undelivered validator result has no analogous "open position" anyone can query.

Nothing today unifies these three into one contract, and nothing lets an operator ask "what did
the last fan-out actually deliver, and what's still open" across all three dispatch sites at once.

## Actors

- A1. **Dispatch manifest writer** — new; runs at spawn time on every fan-out site (team-execution
  reviewer/validator dispatch, `/outcome` leaf dispatch via
  `plugins/saga/scripts/outcome_dispatcher.py:101` `dispatch()`, workflow emitters), records N
  expected, unit IDs, and expected deliverables before any unit is launched.
- A2. **Settlement reconciler** — new; runs at collection time, diffs delivered-vs-manifest,
  classifies every gap (`rate-killed`, `silent-no-op`, `idle`, `leaked-worktree`) into a structured
  casualty report. Never trusts agent self-report — settlement is derived from manifest + returned
  artifacts only, mirroring the existing board<->saga reconciliation precedent that derives state
  from a ledger rather than a self-asserted status
  (`{#board-saga-reconcile-ktds-295}`, `plugins/saga/scripts/outcome_reconcile.py:1-21`).
- A3. **Dead-letter queue** — new; holds unsettled units after a casualty report; the next advance
  re-dispatches its contents at-least-once (idempotent re-dispatch, not exactly-once).
- A4. **Ledger** — new append-only journal of spawn/settle events, generalizing the pattern already
  proven for `/outcome` worktrees (`outcome_worktrees.py` registry) to every fan-out site; read by a
  new `reconcile --leaks` verb reporting open positions (spawned-but-unsettled).
- A5. **Operator** — invokes `reconcile --leaks`; sees a HALT (not a silent degrade) at the next
  gate when casualty rate crosses a threshold, consistent with this fleet's existing
  halt-not-degrade posture (`{#parallel-refuteN-emitter-plan-work-wiring}`, KTD6, `/work` halts
  off-host rather than silently substituting a degraded execution path).

## Requirements

**Dispatch manifest (absorbed H-F1-2, primary)**

- R1. Every fan-out site (team-execution Step B2/B3 reviewer and validator dispatch; `/outcome`
  leaf dispatch through `outcome_dispatcher.dispatch()`; workflow emitters) writes a dispatch
  manifest before launching any unit: N expected, per-unit ID, and expected deliverable shape.
- R2. A settlement pass reconciles delivered-vs-manifest after collection and emits a structured
  casualty report distinguishing at minimum: `delivered`, `rate-killed`, `silent-no-op`, `idle`.
  Casualty classification is derived from manifest + returned artifacts, never from an agent's own
  claim of completion.
- R3. When casualty rate for a fan-out exceeds an operator-configurable threshold, the next gate
  HALTs rather than proceeding on partial results (halt-not-degrade, consistent with KTD6). This
  capability adds zero throttling/concurrency-limiting machinery — it does not reintroduce
  `/optimize`'s shed `max_concurrent` knob (`optimize/SKILL.md:17-19`) and does not change
  `VERIFY_N_CAP` (`execution_spec.py:114`).

**Spawn-settle reconciliation ledger (absorbed T6-F5-6, facet)**

- R4. Every spawn and every settle (successful or casualty-classified) writes an append-only ledger
  record, generalizing the existing `/outcome` worktree registry pattern
  (`outcome_worktrees.py:120` `_registry_path`/`read_registry`, `:141` `register`, `:149`
  `deregister`) from "worktree lifecycle only" to "every fan-out unit across team-execution and
  `/outcome`."
- R5. A `reconcile --leaks` reader command reports open positions — units spawned but never
  settled — by diffing the ledger's spawn records against its settle records, independent of any
  in-memory fan-out state.
- R6. A fixture with 3 spawns and 2 reaps/settles asserts exactly 1 open position is reported.
- R7. A live run against this repo's own stale `/outcome` worktrees (a known leaked-resource
  category already tracked by `harvest_worktrees`, `outcome_worktrees.py:297`) is flagged by
  `reconcile --leaks` as an unsettled debit, demonstrating the generalized ledger subsumes rather
  than duplicates the existing worktree-only leak detector.

**Dead-letter queue + at-least-once re-dispatch (absorbed T6-F5-4, facet)**

- R8. Undelivered work (any unit the settlement pass classifies as unsettled) lands in a
  dead-letter queue as a distinct, queryable evidence lane — not silently dropped from the run's
  record.
- R9. The next advance (whether `/outcome advance` or the next team-execution fan-out step) re-
  dispatches every unit in the dead-letter queue. Re-dispatch is at-least-once: it is safe to
  re-dispatch a unit whose first attempt actually did land (idempotent on the consumer side),
  matching this fleet's existing at-least-once posture rather than attempting unimplementable
  exactly-once delivery.
- R10. A worker that emits no artifact-pointer acknowledgment within the dispatch window (the
  existing artifact-pointer ACK path, `plugins/team-execution/skills/team-execution/scripts/
  artifact_pointer.py`, `{#artifact-pointer-ktds-291}`) is classified `silent-no-op` and its unit
  lands in the DLQ evidence record after a bounded number of retries — retries are capped, never
  unbounded (consistent with this fleet's existing bounded-iteration posture, e.g. team-execution's
  "Maximum 3 review cycles" at `SKILL.md:344`).

## Key Flows

F1. **Clean fan-out.** Trigger: a fan-out site (team-execution B2/B3 or `/outcome` dispatch) spawns
N units. Manifest writer records N expected IDs/deliverables. All N return on time with valid
deliverables. Settlement pass marks all `delivered`; ledger records N spawns + N settles; no DLQ
entry. Covers R1, R2, R4.

F2. **Partial casualty, under threshold.** Trigger: 5 of 7 spawned agents return; 2 die mid-run
(rate-limited). Settlement pass names both casualties in the casualty report (`rate-killed`); since
casualty rate is under the configured threshold, the run proceeds but the 2 units land in the DLQ.
Next advance re-dispatches those 2 at-least-once. Covers R2, R6, R8, R9.

F3. **Casualty rate over threshold.** Trigger: same as F2 but casualty rate exceeds the threshold.
Next gate HALTs rather than proceeding on partial results; operator sees a named, typed failure
report, not a falsely-green run. Covers R3.

F4. **Silent no-op detection.** Trigger: a dispatched worker never emits its artifact-pointer ACK
within the window. Settlement pass classifies it `silent-no-op` distinct from `rate-killed`
(process never even started producing output vs. died mid-flight); unit lands in DLQ after bounded
retries. Covers R10.

F5. **Leak reconciliation.** Trigger: operator runs `reconcile --leaks` against the ledger.
Reconciler diffs spawn vs. settle records across all fan-out sites (team-execution, `/outcome`,
workflow emitter) and reports every open position, including a live example of this repo's own
stale `/outcome` worktrees. Covers R5, R7.

### Acceptance criteria
- [ ] Killing 2 of 5 spawned agents mid-run produces a casualty report naming both casualties by
  unit ID and classification; neither vanishes silently from the run's record (H-F1-2). Check:
  `uv run pytest tests/test_dispatch_settlement.py -k casualty_report_names_both` → passes.
- [ ] Casualty rate above the configured threshold HALTs the next gate instead of proceeding on
  partial results (H-F1-2, KTD6 halt-not-degrade). Check:
  `uv run pytest tests/test_dispatch_settlement.py -k casualty_rate_halts` → passes.
- [ ] Settlement classification is derived from manifest + returned artifacts, never from agent
  self-report (H-F1-2). Check: `uv run pytest tests/test_dispatch_settlement.py -k
  settlement_ignores_self_report` → passes (a worker that self-reports success but emits no
  matching artifact is still classified unsettled).
- [ ] A fixture with 3 spawns and 2 reaps/settles reports exactly 1 open position via `reconcile
  --leaks` (T6-F5-6). Check: `uv run pytest tests/test_dispatch_settlement.py -k
  three_spawn_two_reap_one_open` → passes.
- [ ] `reconcile --leaks` run against this repo's own `/outcome` worktree state flags stale
  worktrees as an unsettled debit (T6-F5-6). Check:
  `uv run pytest tests/test_dispatch_settlement.py -k stale_worktrees_flagged_as_debit` → passes.
- [ ] A unit that emits no artifact-pointer ACK within the dispatch window lands in the DLQ
  evidence record after bounded retries (T6-F5-4). Check: `uv run pytest
  tests/test_dispatch_settlement.py -k no_ack_lands_in_dlq_after_bounded_retries` → passes.
- [ ] DLQ re-dispatch on the next advance is idempotent (safe to re-dispatch a unit whose first
  attempt actually landed) (T6-F5-4). Check: `uv run pytest tests/test_dispatch_settlement.py -k
  dlq_redispatch_is_idempotent` → passes.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Out-of-scope / non-goals
- Does not add any concurrency-limiting/throttling knob. `/optimize`'s shed `max_concurrent`
  fan-out (`optimize/SKILL.md:17-19`) stays shed; `VERIFY_N_CAP` (`execution_spec.py:114`) is
  unchanged. This capability is detection-and-accounting only.
- Does not change team-execution's existing "Maximum 3 review cycles" bounded-iteration rule
  (`SKILL.md:344`) — DLQ retry bounds are a separate, explicitly-capped counter layered on top, not
  a replacement.
- Does not replace `/outcome`'s existing worktree registry/reaper (`outcome_worktrees.py`); it
  generalizes the same double-entry pattern to team-execution and workflow-emitter fan-out and
  gives it one shared query surface (`reconcile --leaks`), but the worktree-specific `reap_worktree`
  / `harvest_worktrees` mechanics stay as-is.
- Does not change who gates. Casualty HALTs surface to the existing gate/operator path; this
  capability does not introduce a new adjudication authority or touch
  `{#external-engines-never-gatekeepers}` (#283) — it is orthogonal to external-engine posture.
- Does not attempt exactly-once delivery. Re-dispatch is at-least-once by design (R9); consumer-side
  idempotency is the load-bearing guarantee, not delivery-count precision.
- Cross-repo: none. Internal `plugins/saga` and `plugins/team-execution` capability; no external-
  repo surface.

## Dependencies / Assumptions

- Assumes `VERIFY_N_CAP = 7` (`plugins/saga/scripts/execution_spec.py:114`) and `/optimize`'s
  shed `max_concurrent` fan-out (`plugins/saga/skills/optimize/SKILL.md:17-19`) remain unchanged;
  verified present today at both cited locations.
- Assumes team-execution's Step B2 ("Reviewers Reach Consensus",
  `plugins/team-execution/skills/team-execution/SKILL.md:340`) and Step B3 ("Scanners Run",
  `SKILL.md:352`) are the real reviewer/validator fan-out sites in the current SKILL.md — verified
  by direct read; earlier ideation notes referenced a differently-numbered "Step A7" that no longer
  matches current step lettering (`SKILL.md:218` Step A7 is "Embed Team Structure," not a fan-out
  site), so this draft grounds against the verified current step numbers instead.
- Assumes `/outcome`'s worktree registry/reaper (`plugins/saga/scripts/outcome_worktrees.py:120-297`)
  is the existing double-entry precedent to generalize — verified present and load-bearing (its own
  comments explicitly name the silent-leak risk it already guards against at `:260`).
- Assumes the artifact-pointer ACK path (`plugins/team-execution/skills/team-execution/scripts/
  artifact_pointer.py`, `{#artifact-pointer-ktds-291}`) is the mechanism a `silent-no-op` check hangs
  off of — verified shipped (issue #291, plan `docs/plans/2026-07-02-typed-artifact-pointer-passing-
  plan.md`).
- Assumes `outcome_dispatcher.dispatch()` (`plugins/saga/scripts/outcome_dispatcher.py:101`) is the
  single `/outcome`-side dispatcher seam every subplot routes through, per its own docstring at
  `:2-20` — verified as the intended manifest-writer attachment point for `/outcome` leaf dispatch.

## Definition of Done

- Every fan-out site (team-execution reviewer/validator dispatch, `/outcome` leaf dispatch,
  workflow emitters) writes a dispatch manifest at spawn time, and a settlement pass reconciles
  delivered-vs-manifest into a structured casualty report — derived from manifest + returned
  artifacts, never from agent self-report.
- Unsettled units land in a dead-letter queue that the next advance re-dispatches at-least-once;
  an append-only spawn/settle ledger backs a `reconcile --leaks` verb reporting open
  (spawned-but-unsettled) positions.
- Casualty rate crossing an operator-configurable threshold HALTs the next gate rather than
  proceeding on partial results.
- All Acceptance Criteria checks below pass, and full suite, format, lint, and types stay green.

## Success Criteria

- The dominant rate-limit-fan-out failure pattern (multi-repo recorded: "6 of 7 agents failed on
  rate-limiting") surfaces as a named casualty report instead of a silently-degraded, falsely-green
  run.
- `reconcile --leaks` can answer "what's spawned-but-unsettled right now" across team-execution and
  `/outcome` fan-out sites from the ledger alone, without depending on any agent's self-report.
- Undelivered work is never dropped from the run's record — it is either re-dispatched
  at-least-once or surfaces in the DLQ evidence lane for operator attention.
- Doc hands off clean: `/doc-review` can assess readiness without follow-ups; `/plan` can design
  the manifest schema, ledger storage format, and DLQ retry-bound mechanism without inventing
  user-facing behavior or scope.
- Release-surface artifacts updated in the same PR: `plugins/saga/.claude-plugin/plugin.json` and
  `plugins/team-execution/.claude-plugin/plugin.json` version bumps, `.claude-plugin/
  marketplace.json`, `plugins/saga/CHANGELOG.md` and `plugins/team-execution/CHANGELOG.md` entries,
  and any drift-guard test updates.
- A `docs/engineering-journal/DECISIONS.md` entry records the manifest/ledger schema choice and a
  "revisit when" condition tied to the next fan-out site this fleet adds.

### Release-surface checklist (plugin behavior changes in this issue)

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump for new manifest/ledger/DLQ schema
  and `reconcile --leaks` verb.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump for Step B2/B3 dispatch-
  manifest wiring.
- [ ] `.claude-plugin/marketplace.json` — updated entries for both plugins.
- [ ] `plugins/saga/CHANGELOG.md` and `plugins/team-execution/CHANGELOG.md` — entries describing
  the settlement contract.
- [ ] Any version/metadata drift-guard tests updated to match the new plugin.json/marketplace.json
  state.

### Out-of-scope / non-goals

- Reintroducing a concurrency/throttling knob (`max_concurrent` or equivalent) — this capability is
  detection-and-accounting only; `/optimize`'s shed knob stays shed.
- Changing `VERIFY_N_CAP` or team-execution's existing "Maximum 3 review cycles" bound — DLQ retry
  bounds are additive, not a replacement.
- Replacing `/outcome`'s worktree-specific registry/reaper mechanics — this generalizes the pattern
  and gives it a shared query surface, it does not rewrite `outcome_worktrees.py`.
- Exactly-once delivery guarantees — re-dispatch is explicitly at-least-once.
- Any cross-repo change — internal to `plugins/saga` and `plugins/team-execution`.

### Files expected to change

Indicative only; exact set is `/plan`'s to determine.

- `plugins/saga/scripts/dispatch_manifest.py` (new) — manifest schema, write-at-spawn helper.
- `plugins/saga/scripts/settlement.py` (new) — settlement reconciler, casualty classifier, ledger
  writer, `reconcile --leaks` reader.
- `plugins/saga/scripts/outcome_dispatcher.py` — wire manifest write into `dispatch()`.
- `plugins/saga/scripts/outcome_worktrees.py` — generalize registry read/write helpers for reuse by
  the shared ledger (or expose an adapter) rather than duplicating the pattern.
- `plugins/team-execution/skills/team-execution/SKILL.md` — reference dispatch manifest in Step
  B2/B3.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — wire
  manifest write/settlement read into reviewer fan-out.
- `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` — expose the ACK
  check the `silent-no-op` classifier depends on.
- `docs/engineering-journal/DECISIONS.md` — new entry for the manifest/ledger schema decision.
- `tests/test_dispatch_settlement.py` (new).

### Tests to add or update

- `tests/test_dispatch_settlement.py` — casualty-report naming, HALT-on-threshold, self-report-
  ignored settlement, 3-spawn/2-reap fixture, stale-worktree-as-debit, no-ACK-to-DLQ, idempotent
  re-dispatch (see Acceptance Criteria for exact `-k` selectors).
- `tests/test_outcome_dispatcher.py` — extend for manifest-write-on-dispatch, if that file exists
  today; otherwise add coverage in the new test file.

### Verification

```bash
uv run pytest tests/test_dispatch_settlement.py -v
uv run pytest tests/test_dispatch_settlement.py -k casualty_report_names_both
uv run pytest tests/test_dispatch_settlement.py -k casualty_rate_halts
uv run pytest tests/test_dispatch_settlement.py -k three_spawn_two_reap_one_open
uv run pytest tests/test_dispatch_settlement.py -k stale_worktrees_flagged_as_debit
uv run pytest tests/test_dispatch_settlement.py -k no_ack_lands_in_dlq_after_bounded_retries
uv run pytest tests/test_dispatch_settlement.py -k dlq_redispatch_is_idempotent
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none

**Justification.** This is mechanical-but-structural accounting work (manifest schema, ledger
append-only writer, casualty classifier) layered on an already-verified precedent
(`outcome_worktrees.py`'s registry/reaper) rather than novel judgment-heavy design — sonnet/high is
proportionate. Inline backend is sufficient: the work is confined to `plugins/saga` and
`plugins/team-execution` scripts/tests with no external-engine, review-panel, or cross-repo
dispatch surface that would justify a team-execution or chaperone-dispatch backend. No external LLM
involvement — this capability touches fan-out accounting, not engine adjudication, and stays clear
of `{#external-engines-never-gatekeepers}` (#283) entirely.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Grounding References

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/` (ideation ids `H-F1-2` primary;
  `T6-F5-6`, `T6-F5-4` facets)
- Source type: ideation survivor (absorbed, consolidated)
- Source title: Dispatch settlement: fan-out manifest with casualty reconciliation, double-entry
  spawn-settle ledger, and dead-letter re-dispatch
- Grounding: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` (§6 recurring-pain theme 4,
  "Rate-limit fan-out kills... 3 repos"; §7 pattern 4, "6 of 7 agents failed on rate-limiting");
  `plugins/saga/scripts/execution_spec.py:114` (`VERIFY_N_CAP`); `plugins/saga/skills/optimize/
  SKILL.md:17-19` (shed `max_concurrent` fan-out); `plugins/team-execution/skills/team-execution/
  SKILL.md:340,352` (Step B2/B3 reviewer/validator fan-out); `plugins/saga/scripts/
  outcome_worktrees.py:120-297` (existing worktree registry/reaper precedent);
  `plugins/saga/scripts/outcome_dispatcher.py:101` (`/outcome` dispatcher seam);
  `{#board-saga-reconcile-ktds-295}` (derive-from-ledger-not-self-report precedent);
  `{#artifact-pointer-ktds-291}` (artifact-pointer ACK path); `{#parallel-refuteN-emitter-plan-
  work-wiring}` KTD6 (halt-not-degrade precedent).

### Intent

Every fan-out site in this fleet (team-execution reviewer/validator dispatch, `/outcome` leaf dispatch, workflow emitters) can lose units silently today — a spawned agent can die, rate-limit out, or leak a worktree, and the run keeps going as if nothing happened. This capability adds one shared accounting contract across those sites: every fan-out writes a **dispatch manifest** (N expected, unit IDs, expected deliverables) at spawn time; a **settlement pass** reconciles delivered-vs-manifest and classifies every non-delivery (rate-killed, silent-no-op, idle, leaked-worktree) into a structured casualty report; unsettled units land in a **dead-letter queue** that the next advance re-dispatches at-least-once; and every spawn/settle event writes an append-only **ledger** so `reconcile --leaks` can report open positions (spawned-but-unsettled) independent of agent self-report. This deliberately adds zero throttling machinery — it is detection and accounting, not a concurrency knob.

### Context library links

_none_

### Inputs inventory

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/team-execution/CHANGELOG.md`
- `docs/engineering-journal/DECISIONS.md`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/351
- Number: 351
- Created at: 2026-07-04T07:46:40.664503+00:00

