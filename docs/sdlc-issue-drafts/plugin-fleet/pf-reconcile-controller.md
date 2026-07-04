---
title: capability: one level-triggered reconcile controller for /work, /loop, /outcome
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: moonshot
wave: wave-3
objective: Ship run-start intent envelope for lifecycle autonomy
---

# capability: one level-triggered reconcile controller for /work, /loop, /outcome

### Objective

Ship run-start intent envelope for lifecycle autonomy

### Tier

moonshot

### Wave

wave-3

## Summary

`/outcome` today has two separate, hand-wired board-consistency mechanisms — an idempotency-key
write ledger (`outcome_board_sync.reconcile_board`, #279) and a resume-time drift detector
(`outcome_reconcile.detect`/`decide`, #295) — and neither is available to `/work` or `/loop`, which
still narrate board moves through raw `mission-control` calls with no idempotency guard and no
outside-drift detection. This capability extracts both mechanisms into one shared,
Kubernetes-style level-triggered `reconcile_controller` module and wires it into `/work` and
`/loop` in addition to `/outcome`, so a rapid double tick converges on a single write everywhere,
and an outside edit to a saga-owned board field is re-detected and corrected on the next reconcile
tick regardless of which command is driving the lifecycle.

## Problem Frame

`outcome_board_sync.py` already proves the idempotency-key half of this problem for `/outcome`
alone: `reconcile_board` (`plugins/saga/scripts/outcome_board_sync.py:177`) computes a deterministic
`cert.idempotency_key(op_kind_str, repo, number, target_state)`
(`plugins/saga/scripts/outcome_board_sync.py:336`, key recipe documented at
`plugins/saga/scripts/reversibility_certificate.py:281`) and skips the write if a ledger file for
that key already exists — collapsing a rapid double tick to one write. But its own module docstring
names the gap this capability closes: "#279's `outcome_board_sync` drives autonomous board writes
and records each success as an idempotency-key file in `store.root/board-sync/`, but never re-reads
the live board. So an outside writer (operator, CI, a review agent) who changes a saga-owned board
field while saga is at rest is never noticed — and because a recorded key makes the next tick
*skip* the op, the drift persists forever." (`plugins/saga/scripts/outcome_reconcile.py:4-8`).
`outcome_reconcile.detect` (`plugins/saga/scripts/outcome_reconcile.py:219`) and `.decide`
(`plugins/saga/scripts/outcome_reconcile.py:418`) were built to close that loop, but only at
`/outcome` resume time (landed via #295, `6b33eba feat(saga): board↔saga reconciliation on
resume`).

Neither mechanism reaches `/work` or `/loop`. `plugins/saga/skills/work/SKILL.md:54` and `:374`
route post-merge board moves through raw `mission-control` `issue_progress.py` calls with no
idempotency key and no drift re-check; `plugins/saga/skills/loop/SKILL.md` likewise narrates
`--phase-status`/handoff status moves directly, never consulting a shared write ledger. This is
exactly the gap the binding decision register names: the `/outcome` campaign already committed to
"Derived-on-read status, never committed status fields; HALT-not-degrade" and the grounding brief
lists "mission-control board/field drift... item-list pagination silently truncating... racing (4
repos)" as a recurring pattern (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:126-128`).
Consolidating both mechanisms into one controller, rather than re-deriving them a third and fourth
time inside `/work` and `/loop`, is also the deliberate scope-narrowing move recorded against this
idea in ideation (`consolidation_rationale`, issue-map): standalone moonshot generalization,
deliberately sequenced **behind** `pf-board-progression-shared-writer` (the certificate-gated writer
extraction tracked separately as ideation id `T7-F4-2`, dod: merged
`board_progression.py` extracted from `outcome_board_sync` and consumed by `/work` post-merge and
`/loop` on-route).

## Actors

- A1. Reconcile controller — new system actor; runs a level-triggered tick loop consulting the
  idempotency-key ledger, recomputing expected state, and reading live board/issue state, shared by
  `/outcome`, `/work`, and `/loop`.
- A2. `/outcome`, `/work`, `/loop` — existing commands; each becomes a controller consumer instead
  of an independent, hand-wired board writer.
- A3. Outside writer (operator, CI, a review agent) — may change a saga-owned board field while any
  of the three commands is at rest; the controller's next tick must notice and correct.

## Requirements

R1. The controller extracts `outcome_board_sync.reconcile_board`'s idempotency-key write path
(`plugins/saga/scripts/outcome_board_sync.py:177`, key recipe
`plugins/saga/scripts/reversibility_certificate.py:281`) and `outcome_reconcile`'s detect/decide
drift-reconciliation path (`plugins/saga/scripts/outcome_reconcile.py:219`,`:418`) into one shared
module, with zero behavior change to `/outcome`'s existing call sites (regression-tested).

R2. `/work`'s post-merge board move (`plugins/saga/skills/work/SKILL.md:54`,`:374`) and `/loop`'s
phase-status board move route through the shared controller instead of a raw `mission-control`
call, gaining the same idempotency-key guard `/outcome` already has.

R3. The controller is level-triggered, not edge-triggered: a tick recomputes expected state fresh
from durable saga fields every time (mirrors `outcome_reconcile`'s "expected" view,
`plugins/saga/scripts/outcome_reconcile.py:219`), rather than trusting a cached "already handled"
flag — so a crash between compute and write is safely retried, not skipped.

R4. A rapid double tick (two ticks racing on the same op before either's ledger file lands)
converges on exactly one applied write and one ledger entry, never two.

R5. An outside board/issue field change made while `/work` or `/loop` is at rest (not just
`/outcome`, which already has this via #295) is detected on that command's next reconcile tick and
corrected — or, if the drift is on a HALT-classified (irreversible) transition, surfaced as a named
HALT rather than silently overwritten.

R6. This capability is sequenced strictly behind `pf-board-progression-shared-writer`
(`board_progression.py` extraction, ideation id `T7-F4-2`): if that extraction has not landed, this
capability's plan must fold the extraction in as its first phase rather than duplicating it.

## Key Flows

F1. **Rapid double tick, single writer.** Trigger: two reconcile ticks fire for the same
(repo, issue, op, target_state) before either's write lands. Controller resolves via the shared
idempotency key; second tick observes the first's in-flight/landed ledger entry and no-ops.
Covers R1, R4.

F2. **Outside drift on a resting command.** Trigger: an operator or CI edits a saga-owned board
Status field while `/work` is between invocations (not `/outcome`). On `/work`'s next reconcile
tick, the controller's drift-detect view (recomputed expected vs. live) flags the mismatch and
either corrects it (reversible) or HALTs with a named reason (irreversible). Covers R2, R3, R5.

F3. **Crash-safe resume.** Trigger: process dies after computing expected state but before the
ledger write lands. Next tick (any of the three commands) recomputes from durable fields, finds no
ledger entry, and completes the write — no permanent skip. Covers R1, R3.

### Out-of-scope / non-goals
- This capability does not change `/outcome`'s existing autonomous-status allowlist or reversal
  semantics — those are owned by `{#operator-choice-framework}` and the "Derived-on-read status,
  never committed status fields; HALT-not-degrade" `/outcome` binding decision and stay as-is.
- Does not widen which board transitions are autonomous vs. gated for `/work` or `/loop` beyond
  whatever `pf-board-progression-shared-writer` already establishes; this capability is about one
  shared *mechanism* (idempotency + drift detection), not new autonomy scope.
- Does not touch `mission-control`'s own `card_validator.py` or field-drift audit logic — only the
  saga-side write/reconcile path that calls into it.
- Does not add a standing/scheduled reconcile daemon; ticks remain triggered by command invocation
  (`/work`, `/loop`, `/outcome` running), matching the existing resume-time trigger model.

## Dependencies / Assumptions

- Hard sequencing dependency on `pf-board-progression-shared-writer` (`board_progression.py`
  extraction, ideation id `T7-F4-2`) — this capability generalizes that extraction; if it has not
  landed, extracting it is this capability's first phase, not a parallel track.
- Assumes `outcome_board_sync.py` (#279) and `outcome_reconcile.py` (#295) remain the two source
  modules to unify — verified present and load-bearing today (`git log` shows #295 landed via
  `6b33eba feat(saga): board↔saga reconciliation on resume (#295) (#330)`).
- Assumes `/work` and `/loop` currently have no idempotency-key guard on board writes — verified by
  absence: `plugins/saga/skills/work/SKILL.md:54,374` and `plugins/saga/skills/loop/SKILL.md` route
  through raw `mission-control` calls / `--phase-status` narration with no ledger reference.
- Binding decision `{#worker-cache-scheduling}` and the never-gatekeepers decision
  (`{#external-engines-never-gatekeepers}`) are not implicated — this is an internal saga-plugin
  refactor with no external-LLM surface.

## Success Criteria

- `/work` and `/loop` board moves are provably idempotent under a rapid double tick (reproduced by
  a race test), matching `/outcome`'s existing guarantee.
- An outside field change made while `/work` or `/loop` is at rest is re-detected and corrected (or
  HALTed) on the next reconcile tick — closing the exact gap `outcome_reconcile.py`'s docstring
  named for `/outcome` alone.
- Zero regression in `/outcome`'s existing board-sync and resume-reconcile test suites.
- `docs/engineering-journal/DECISIONS.md` gains an entry recording the controller as the one shared
  mechanism (superseding three independent hand-wired paths), with a "revisit when" condition tied
  to any future fourth lifecycle command needing board writes.

### Out-of-scope / non-goals

- Widening `/work`/`/loop` autonomous-status allowlists beyond what `pf-board-progression-shared-writer`
  already establishes.
- A standing/scheduled reconcile daemon — ticks stay invocation-triggered.
- Changes to `mission-control`'s `card_validator.py` schema or field-drift audit.
- Cross-repo (non-`infiquetra-claude-plugins`) board reconciliation.

### Files expected to change

- `plugins/saga/scripts/reconcile_controller.py` — new shared module (idempotency-key write +
  drift-detect/decide, unifying `outcome_board_sync.reconcile_board` and
  `outcome_reconcile.detect`/`.decide`).
- `plugins/saga/scripts/outcome_board_sync.py` — refactored to delegate to
  `reconcile_controller` (no external behavior change).
- `plugins/saga/scripts/outcome_reconcile.py` — refactored to delegate to `reconcile_controller`
  (no external behavior change).
- `plugins/saga/skills/work/SKILL.md` — post-merge board move routed through
  `reconcile_controller` instead of a raw `mission-control` call.
- `plugins/saga/skills/loop/SKILL.md` — phase-status board move routed through
  `reconcile_controller`.
- `tests/test_reconcile_controller.py` — new: race-reproduction (rapid double tick → single write)
  and outside-drift (live field changed while `/work`/`/loop` at rest → re-detected next tick)
  tests.
- `plugins/saga/CHANGELOG.md` — entry for the controller extraction and `/work`/`/loop` wiring.
- `docs/engineering-journal/DECISIONS.md` — new entry per Success Criteria.

### Acceptance criteria
- [ ] Rapid double tick on the same (repo, issue, op, target_state) converges on exactly one
  applied write and one ledger entry, for all three of `/outcome`, `/work`, `/loop`.
  Check: `uv run pytest tests/test_reconcile_controller.py -k rapid_double_tick` → passes.
- [ ] An outside field change made while `/work` is at rest (no `/outcome` resume involved) is
  re-detected and corrected on `/work`'s next reconcile tick.
  Check: `uv run pytest tests/test_reconcile_controller.py -k work_outside_drift` → passes.
- [ ] An outside field change made while `/loop` is at rest is re-detected and corrected on
  `/loop`'s next reconcile tick.
  Check: `uv run pytest tests/test_reconcile_controller.py -k loop_outside_drift` → passes.
- [ ] An irreversible-transition outside drift HALTs with a named reason rather than being
  silently overwritten, for all three consumers.
  Check: `uv run pytest tests/test_reconcile_controller.py -k halt_on_irreversible_drift` → passes.
- [ ] `/outcome`'s pre-existing board-sync and resume-reconcile test suites remain green after the
  extraction (zero behavior regression).
  Check: `uv run pytest tests/test_outcome_board_sync.py tests/test_outcome_reconcile.py` → passes.
- [ ] Crash between expected-state compute and ledger write is safely retried on the next tick, not
  permanently skipped.
  Check: `uv run pytest tests/test_reconcile_controller.py -k crash_safe_resume` → passes.
- [ ] Full repo gate stays green.
  Check: `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

## Definition of Done

`/work` and `/loop` board moves are provably idempotent under rapid double tick, matching
`/outcome`'s existing guarantee, and an outside field change made while `/work` or `/loop` rest
is re-detected and corrected (or HALTed on irreversible transitions) on the next reconcile tick.
`/outcome`'s existing board-sync resume-reconcile test suites remain green with zero regression,
and `docs/engineering-journal/DECISIONS.md` gains the entry recording the controller as the one
shared mechanism superseding the three independent hand-wired paths.

## Release-surface checklist

This capability changes saga plugin behavior (new shared module, `/work` and `/loop` SKILL.md
wiring) — update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry for the controller extraction.
- [ ] Any version/metadata drift-guard tests (`tests/test_*marketplace*`, `tests/test_*plugin_json*`
  if present) — confirm they pass against the bumped version.

## Recommended executor profile

- **Model:** sonnet
- **Effort:** xhigh
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is a mechanical-but-hazardous refactor (unifying two already-correct
  modules behind one interface, then rewiring two more consumers) rather than a novel-design task —
  sonnet is the right tier per the fleet's model/effort tiering guidance. `xhigh` effort is
  warranted because the race-condition and outside-drift test surface is exactly where subtle
  concurrency bugs hide (this capability's whole point is closing a previously-shipped drift gap),
  and because the hard sequencing dependency on `pf-board-progression-shared-writer` requires
  careful plan-time verification of that capability's landed state before work starts. No
  external-LLM involvement — this is an internal refactor with no generator/advisory-reviewer role
  to delegate.

### Handoff maturity

requirements-ready

### Suggested next action

Verify `pf-board-progression-shared-writer` (ideation id `T7-F4-2`) has landed before running
`/plan` on this issue — if not landed, fold its extraction in as this plan's first phase. Otherwise
use `/plan <issue>` to create an implementation plan.

## Grounding References

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json` (ideation id `T7-F5-4`)
- Source type: ideation survivor (absorbed, primary role)
- Source title: One reconcile controller for /work, /loop, /outcome — Kubernetes-style
  level-triggered convergence
- Grounding: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` (theme 7, "Lifecycle
  auto-progression & the ship ceremony"; binding decision register; `/outcome` campaign
  derived-on-read status decision)

### Intent

`/outcome` today has two separate, hand-wired board-consistency mechanisms — an idempotency-key write ledger (`outcome_board_sync.reconcile_board`, #279) and a resume-time drift detector (`outcome_reconcile.detect`/`decide`, #295) — and neither is available to `/work` or `/loop`, which still narrate board moves through raw `mission-control` calls with no idempotency guard and no outside-drift detection. This capability extracts both mechanisms into one shared, Kubernetes-style level-triggered `reconcile_controller` module and wires it into `/work` and `/loop` in addition to `/outcome`, so a rapid double tick converges on a single write everywhere, and an outside edit to a saga-owned board field is re-detected and corrected on the next reconcile tick regardless of which command is driving the lifecycle.

### Context library links

_none_

### Tests to add or update

- `tests/test_outcome_board_sync.py`
- `tests/test_outcome_reconcile.py`
- `tests/test_reconcile_controller.py`

### Verification

```bash
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

### Inputs inventory

- `plugins/saga/skills/loop/SKILL.md`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/scripts/reconcile_controller.py`
- `plugins/saga/scripts/outcome_board_sync.py`
- `plugins/saga/scripts/outcome_reconcile.py`
- `plugins/saga/skills/work/SKILL.md`
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

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/450
- Number: 450
- Created at: 2026-07-04T08:17:37.182735+00:00

