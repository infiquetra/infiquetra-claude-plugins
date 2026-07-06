---
title: Work session — runtime ladder climbing (#364)
issue: infiquetra/infiquetra-claude-plugins#364
plan: docs/plans/2026-07-06-runtime-ladder-climbing-plan.md
branch: feat/364-runtime-ladder-climbing
date: 2026-07-06
---

# Work session — runtime ladder climbing (#364)

**Built the full DoD (all 6 mechanisms, 9 ACs).** saga-only; full repo gate green; four commits
plus fixes from two adversarial rounds.

## What was built (by U-ID)

- **U1 — `escalate_tier()`** (`4e62d18`): pair-level one-rung climb in `execution_spec.py` —
  effort-first then model (KTD1), `supports_effort` invariant, `None` at the top of the ladder or
  when a ceiling blocks the climb (KTD2 — callers render HALT, never a silent same-tier re-run).
  Ladder-walk test proves one-axis-per-step termination at `fable/xhigh`.
- **U2 — `escalate_on_signal`** (`4e62d18`): optional unit flag (absent field round-trips
  byte-identical). Attended emission (default): the refute throw carries an
  `escalation-proposal: <old> -> <new> (+1 <axis> rung)` — the ask gate is the `/work` operator
  loop + the existing #365 `/tier` patch (KTD4; no ask machinery enters the emitted script).
  Unattended emission (`emit --unattended`, KTD3 — a run property, never spec state): ONE
  in-script retry at the climbed tier via `replace(unit, tier=climbed)` (prompt, opts, budget
  rider, and the fresh verify panel all follow the climb, R4), then HALT if still refuted (KTD5 —
  one climb per unit per run). `let`-vs-`const` declaration tracks actual reassignment
  (`_emits_climb_retry`). v1 validate exclusions: no-panel (dead wiring), `iterate_to_consensus`
  and fan-out (doc-review P1s — unbounded-spend compositions).
- **U3 — `pull_cord`** (`4e62d18`): the gate helper accepts `{"pull_cord": "<reason>"}` as a
  worker-initiated out-of-depth disposition, distinct from success and from the missing/malformed
  throws (empty or non-string cords fall through to normal validation). Cheap-tier units with a
  return contract carry the cord rider; every cord batches into ONE end-of-run coordinator
  escalation entry carrying its one-rung proposal (KTD7); cord units are never marked complete
  (the batched check fails the run before it returns).
- **U4 — `/work` between-rounds recovery step** (`b1b7182`): documented at the round-bump seam in
  `references/pr-continuation-loop.md` + the Phase 0.4 pointer — on a failure row, propose exactly
  one rung with the ordinal cost delta, end-clamped, gated on the `is_escalation`
  confirm-before-re-emit pattern; de-escalation is mentioned-never-auto-applied (the #368
  write-back is the durable home for cheapening judgment).
- **U5 — release surface** (`b1b7182`): `references/execution-spec.md` documents the new field,
  disposition, and flag; saga 0.67.0→0.68.0; CHANGELOG; marketplace sync; version-pin test;
  DECISIONS `{#runtime-ladder-climbing-364}` (KTD1-KTD7).

## Adversarial gate — round 1: 1 P1 + 1 P2 found by execution, both fixed

`saga:readonly-verifier` (worktree, node --check + runtime execution with mocked agents) upheld
the escalation walk, ceiling HALT semantics, wave-path retry, JS validity, and release parity —
and CONFIRMED two real gaps (`73190cf` fixes both):

- **P1 — cord proposals ignored the session ceiling**: `_emit_gate_call` computed `cordProposal`
  via `escalate_tier(unit.tier)` without `ceiling=`, so a pulled cord could recommend a tier the
  operator's own #365 cap forbids — inconsistent with the ceiling-aware `escalate_on_signal` path
  in the same script. `session_ceiling` now threads through all five gate-call sites; the batch
  null-branch names both no-climb causes.
- **P2 — `pull_cord` name collision**: a legitimate `returns` key named `pull_cord` would be
  silently swallowed as a cord. `validate` now rejects it as a reserved return-disposition key.

## Adversarial gate — round 2 (re-verify of `73190cf`)

CLEAN — no P0/P1/P2 remaining. All probes SAFE by execution: the original P1 repro emits no
`cordProposal:` at any of the five gate-call sites under a blocking ceiling (iterate loop and wave
thunk included); climb-room ceilings still propose exactly one rung; the unattended retry gate's
cord proposal correctly vanishes when the ceiling equals the climbed tier; reserved-key rejection
matches only the exact `pull_cord` key (`cord_pull`/`pull_cords` pass); `node --check` passes on
ceiling-set unattended emission; full suite 2271 passed; release surface parity holds at 0.68.0.

## Gates

- `uv run pytest` — 2271 passed, 1 skipped (19 new #364 tests; every issue-AC `-k` selector
  matches: `escalate_tier`, `escalate_on_signal_one_rung`, `escalate_on_signal_top_of_ladder_halts`,
  `escalate_attended_asks`, `escalate_unattended_silent`, `pull_cord_disposition`,
  `pull_cord_not_complete_batched`).
- ruff format/check, mypy (CI scope), bandit `-ll` on the changed script — clean.
- Note: the issue's AC file `tests/test_execution_spec.py` does not exist; the suite is
  `tests/test_saga_execution_spec.py` (recorded in the plan).

## Follow-ups

- Lifting the v1 composition exclusions (iterate_to_consensus, fan-out) and unattended silent
  climb for cords — recorded as Deferred Follow-Up Work in the plan; revisit with #366/#367
  telemetry + the priced classifier.
