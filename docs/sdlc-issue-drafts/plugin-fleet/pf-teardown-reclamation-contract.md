---
title: capability: non-skippable teardown & reclamation contract for team-execution
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Govern fleet concurrency and reclaim leaked resources
---

# capability: non-skippable teardown & reclamation contract for team-execution

### Objective

Govern fleet concurrency and reclaim leaked resources.

### Problem Frame

`team-execution`'s Step-by-step run lifecycle in
`plugins/team-execution/skills/team-execution/SKILL.md` goes from `Step B0: Parse the Approved Team
Plan` (`:277`) through `Step B6: Monitors Verify Runtime Signals` (`:389`) to `Step B7: Completion`
(`:403`) — and stops there. Step B7 reports worker changes, reviewer scores, gate results, and
residual risks; it never tears down or reclaims anything it spawned (worktrees, resident teammates,
lease-holding state). There is no Step B8. Nothing in the run lifecycle is contractually obligated
to run on exit, so any process that dies mid-run (killed session, crashed host, operator
interrupt) leaks whatever it registered — worktrees, spawned processes, resident-teammate state —
with no backstop to notice or clean it up later.

This is not hypothetical: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88` records
direct evidence of the leak in this repo's own worktree store — a stale-worktree buildup
"inflating repo 10x+" — and names it explicitly as "same disease [as] team-execution's missing
Step B8." The same brief's recurring-pattern scan (`:139-140`) separately surfaces "subagents idle
without delivering; stale idle notifications — coordinator must detect and re-ping," reproduced
live in that ideation session, which is the resident-teammate half of the same disease: nothing
evicts a teammate that stops delivering.

Two prior decisions bound the shape of any fix here rather than leaving it open-ended:

- `{#worker-cache-scheduling}` (`docs/engineering-journal/DECISIONS.md:1950`) settled that
  derivation lives saga-side and residency lives team-side — a named-teammate warm-pool model.
  Any idle-eviction mechanism for resident teammates must sit on top of that residency model, not
  replace it, and must not reopen the KTD1–KTD5 tradeoffs already recorded there.
- Any lease records this capability consumes should come from `pf-resource-lease-broker`'s output
  where that capability has already landed, but this capability must ship and be independently
  useful against its own reclamation ledger even if the lease broker has not landed yet (see
  Dependencies below).

Today, nothing in the codebase registers a spawned worktree, process, or resident teammate against
any tracked ledger at creation time, so there is no data structure a teardown step could even walk
to reclaim. The fix is one deliverable, not four independent ones: a non-skippable exit-time
contract with nothing to execute against is a no-op; a reclamation ledger nothing reads at exit is
inert data; a time-based reaper without a ledger to check against re-leaks silently on every crash
that beats it to the punch; and a CI invariant with no contract or ledger behind it has nothing
honest to assert. They are graded, in order, as the primary mechanism (the contract), the
substrate it executes against (the ledger), the backstop for what the contract cannot catch
because the process died before it could run (the TTL reaper and idle-TTL eviction), and the proof
that keeps the whole thing honest over time (the CI leak invariant).

### Requirements

Each requirement below traces to one absorbed idea from the plugin-fleet ideation pool
(`docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json`, theme T6 "teardown-reclamation").

**R1 — Non-skippable Step B8 (absorbed: `T6-F2-1`, primary).** `team-execution`'s run lifecycle
gains a `Step B8: Teardown & Reclaim` after the existing `Step B7: Completion`
(`plugins/team-execution/skills/team-execution/SKILL.md:403`). Step B8 is not optional, not
skipped on early exit, and not skipped on failure paths — it runs whenever a run reaches a
terminal state (success, hard-fail, or operator abort), and it calls `reclaim_all()` against the
reclamation ledger (R2) before the run is considered complete.

**R2 — Register-on-spawn reclamation ledger (absorbed: `T6-F4-1`, facet).** A shared reclamation-
ledger primitive: every worktree, spawned process, and resident-teammate registration writes an
entry to the ledger at creation time (register-on-spawn), keyed so that `reclaim_all()` is
idempotent — calling it twice, or calling it after a partial prior reclaim, must not error and
must not double-free.

**R3 — TTL-after-finished worktree reaper (absorbed: `T6-F5-1`, facet).** A time-based backstop
(Kubernetes-/Janitor-Monkey-style) sweeps worktrees whose owning run finished or whose owning
process no longer exists, once a TTL window has elapsed, independent of whether Step B8 ran. This
is what catches the case Step B8 structurally cannot: the process died before reaching any
teardown step at all.

**R4 — Idle-TTL eviction for resident teammates (absorbed: `T6-F6-2`, facet).** Resident teammates
(per `{#worker-cache-scheduling}`, `docs/engineering-journal/DECISIONS.md:1950`) that go idle
past a configured TTL are evicted automatically. This engages, and must not contradict, the
existing warm-pool residency posture from that decision — it adds an idle bound on top of
residency, it does not remove residency or revert to per-call spawn.

**R5 — CI leak invariant (absorbed: `T6-F6-8`, facet).** A CI test enumerates ledgered vs. actual
worktree state and fails the build when the worktree store holds entries the ledger does not know
about (unledgered leaks). This test must fail red against the repo's current state until the
existing leaked worktrees are cleaned up as part of this change, per
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`.

### Out-of-scope / non-goals
- **In scope:** Step B8 lifecycle addition to `team-execution`'s run steps; the reclamation-ledger
  primitive and its register-on-spawn call sites; the TTL worktree reaper; idle-TTL eviction for
  resident teammates; the CI leak-invariant test; cleanup of the currently-leaked worktrees so the
  new CI test starts green after this change lands.
- **Out of scope / non-goals:**
  - Redesigning `{#worker-cache-scheduling}`'s residency model — this consumes that decision's
    warm-pool posture, it does not reopen KTD1–KTD5.
  - Building `pf-resource-lease-broker`'s lease-record format — this capability consumes lease
    records where that capability's output is present, but ships and is independently useful
    against the reclamation ledger without waiting on it.
  - Any new orchestration-level concurrency cap (`VERIFY_N_CAP`, `execution_spec.py:114`) — that
    is a separate rate-limit/concurrency-governance theme, not a teardown concern.
  - Retroactive backfill of registration for resource kinds not covered by R2's initial scope
    (worktrees, spawned processes, resident teammates) — new resource kinds get their own
    register-on-spawn call site added in a follow-up, not invented speculatively here.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/team-execution/skills/team-execution/SKILL.md` — add `Step B8: Teardown & Reclaim`
  after the existing `Step B7: Completion` (`:403`).
- `plugins/team-execution/scripts/reclamation_ledger.py` (new, proposed path) — register-on-spawn
  ledger primitive + idempotent `reclaim_all()`.
- `plugins/team-execution/scripts/worktree_reaper.py` (new, proposed path) — TTL-after-finished
  worktree sweep.
- `plugins/team-execution/references/` — new reference doc for the teardown contract and idle-TTL
  eviction policy, alongside existing `validator-execution-order.md` / `consensus-protocol.md`.
- `tests/test_reclamation_ledger.py`, `tests/test_worktree_reaper.py` (new) — unit coverage for R2,
  R3.
- `tests/test_teardown_ci_invariant.py` (new) — the CI leak invariant from R5.
- `plugins/team-execution/.claude-plugin/plugin.json`, root `.claude-plugin/marketplace.json`,
  `plugins/team-execution/CHANGELOG.md` — version/metadata bump for the Step B8 behavior change
  (see Release-surface checklist).

### Acceptance criteria
- [ ] Every spawned worktree, process, and resident-teammate registration writes a register-on-
      spawn entry to the reclamation ledger at creation time.
      Check: `uv run pytest tests/test_reclamation_ledger.py -k register_on_spawn` → passes.
- [ ] Calling `reclaim_all()` twice, or after a partial prior reclaim, is idempotent (no error, no
      double-free).
      Check: `uv run pytest tests/test_reclamation_ledger.py -k idempotent_reclaim_all` → passes.
- [ ] A run killed mid-execution (simulated process kill before Step B8 can run) is fully reclaimed
      by the TTL reaper within its configured TTL window, with no operator action required.
      Check: `uv run pytest tests/test_worktree_reaper.py -k killed_mid_run_reclaimed` → passes.
- [ ] A resident teammate that goes idle past the configured idle-TTL is evicted automatically,
      without disabling or bypassing the `{#worker-cache-scheduling}` warm-pool residency model.
      Check: `uv run pytest tests/test_reclamation_ledger.py -k idle_ttl_eviction` → passes.
- [ ] Step B8 runs on every terminal path of a `team-execution` run — success, hard-fail, and
      operator abort — and is not skippable by configuration.
      Check: `uv run pytest tests/test_teardown_ci_invariant.py -k step_b8_runs_on_all_terminal_paths`
      → passes.
- [ ] The CI leak-invariant test fails red against the repo's current worktree state (leaked,
      unledgered worktrees present) before cleanup, and passes green after the leaked worktrees
      from `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88` are cleaned up as part of
      this change.
      Check: `uv run pytest tests/test_teardown_ci_invariant.py -k unledgered_worktree_fails_ci` →
      passes only after cleanup lands in this PR.
- [ ] Full suite, format, lint, and types stay green.
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
      → all pass.

### Dependencies / Assumptions

- Consumes `pf-resource-lease-broker`'s lease records where that capability has already landed,
  but does not block on it — this capability ships and is independently useful against its own
  reclamation ledger regardless of lease-broker landing order.
- Builds on `{#worker-cache-scheduling}` (`docs/engineering-journal/DECISIONS.md:1950`) — the
  named-teammate residency model. Idle-TTL eviction (R4) must compose with that decision, not
  reopen it. Revisit-when for that decision: "named-teammate residency proves insufficient, or
  idle-poll justifies formal wave queue" — if this capability's implementation reveals either
  condition, flag it back to that decision rather than silently reworking it here.
- Assumes the current worktree leak (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`)
  is still present at implementation time; if it has already been manually cleaned up between now
  and `/plan`, the CI invariant (R5) must still be exercised via a planted/simulated leak in its
  test rather than skipped for lack of a live leak to catch.
- Any read-only/verify-class Agent-tool spawn introduced for verification during this work must use
  `subagent_type: saga:readonly-verifier` + `isolation: "worktree"` per
  `plugins/saga/references/sandbox-spawn-sites.md`.

## Grounding References

- Absorbed ideas (`docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json`, theme T6
  "teardown-reclamation"):
  - `T6-F2-1` (primary) — "Step B8: non-skippable run-exit Teardown & Reclaim contract."
  - `T6-F4-1` (facet) — "Shared reclamation-ledger primitive: register-on-spawn, idempotent
    `reclaim_all`."
  - `T6-F5-1` (facet) — "TTL-after-finished worktree reaper (Kubernetes / Janitor Monkey)."
  - `T6-F6-2` (facet) — "Immortal workers, inverted: an idle-TTL eviction protocol for resident
    teammates."
  - `T6-F6-8` (facet) — "Make teardown non-optional: an executable leak invariant that fails CI."
  - Consolidation rationale (`docs/plans/.../issue-map/issue-map-final.json`, slug
    `pf-teardown-reclamation-contract`): "Contract without backstop re-leaks on crash; backstop
    without contract normalizes leaking — they are one deliverable."
- Binding decisions this build engages:
  - `{#worker-cache-scheduling}` (`docs/engineering-journal/DECISIONS.md:1950`) — named-teammate
    residency model that R4's idle-TTL eviction must compose with.
- Direct evidence:
  - `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88` — "15 stale abandoned saga
    worktrees in `.worktrees/` inflating repo 10x+ → direct evidence theme 6
    (teardown/reclamation), same disease [as] team-execution's missing Step B8."
  - `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:139-140` — "Subagents idle without
    delivering; stale idle notifications — coordinator must detect and re-ping (2 repos; also
    reproduced live in this very session)" — the resident-teammate half of the same disease,
    grounding R4.
  - `plugins/team-execution/skills/team-execution/SKILL.md:277-410` — the full Step B0–B7 run
    lifecycle, ending at `Step B7: Completion` (`:403`) with no teardown/reclaim step.

## Definition of Done

- Every worktree, process, and resident teammate spawned by a `team-execution` run is reclaimed
  exactly once, whether the run completes normally, fails hard, is aborted by the operator, or is
  killed outright by an external process/host failure.
- The repo's worktree store can no longer silently accumulate leaked entries — CI catches it before
  merge.
- `/doc-review` can assess readiness without follow-ups; `/plan` can design the ledger's data model,
  the reaper's scheduling mechanism, and Step B8's exact placement without inventing user-facing
  scope.

## Recommended Executor Profile

- Model: sonnet
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution

### Release-surface checklist

Step B8 is a user-visible behavior change to `team-execution`'s run lifecycle — update all of the
following in the same PR:

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
      non-skippable Step B8 behavior.
- [ ] root `.claude-plugin/marketplace.json` — matching version bump for `team-execution`.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry describing Step B8, the reclamation ledger,
      the TTL reaper, idle-TTL eviction, and the CI leak invariant.
- [ ] Any version/metadata drift-guard tests in `tests/` — confirm they pass against the bumped
      version and updated skill/reference file set.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json` (theme T6,
  "teardown-reclamation") + `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` +
  issue-map slug `pf-teardown-reclamation-contract`
- Source type: ideation (plugin-fleet ideation, Gate B → issue-map)
- Source title: Non-skippable teardown: Step B8 run-exit Teardown & Reclaim contract,
  register-on-spawn reclamation ledger, TTL worktree reaper, idle-TTL eviction, and a CI leak
  invariant

### Context library links

_none_

### Tests to add or update

- `tests/test_reclamation_ledger.py`
- `tests/test_teardown_ci_invariant.py`
- `tests/test_worktree_reaper.py`

### Verification

```bash
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

### Intent

`team-execution`'s Step-by-step run lifecycle in `plugins/team-execution/skills/team-execution/SKILL.md` goes from `Step B0: Parse the Approved Team Plan` (`:277`) through `Step B6: Monitors Verify Runtime Signals` (`:389`) to `Step B7: Completion` (`:403`) — and stops there. Step B7 reports worker changes, reviewer scores, gate results, and residual risks; it never tears down or reclaims anything it spawned (worktrees, resident teammates, lease-holding state). There is no Step B8. Nothing in the run lifecycle is contractually obligated to run on exit, so any process that dies mid-run (killed session, crashed host, operator interrupt) leaks whatever it registered — worktrees, spawned processes, resident-teammate state — with no backstop to notice or clean it up later.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/358
- Number: 358
- Created at: 2026-07-04T07:48:48.419577+00:00

