---
title: "Issue #526: ship_ceremony operator-confirm gate for always_operator transitions"
type: fix
status: active
date: 2026-07-11
origin: docs/engineering-journal/LEARNINGS.md#ship-ceremony-run-does-not-self-gate
---

# Issue #526: ship_ceremony operator-confirm gate for always_operator transitions

## Summary

Make `ship_ceremony.py run` refuse to execute an `always_operator`-tier transition (`merge`,
`branch_delete`) unless the caller passes `--operator-confirmed <transition>` naming that exact
transition. A bare `run` reaching a gated transition exits non-zero, names the withheld transition,
and leaves the ceremony ledger unadvanced. Release surfaces and the two guidance docs that already
*describe* merge as operator-confirmed are updated in the same PR so enforcement and documentation
tell one story.

---

## Problem Frame

`run()` (`plugins/saga/scripts/ship_ceremony.py:393-424`) executes the next unrun transition of the
linear ledger unconditionally; `TRANSITION_TIERS` (lines 95-103) is consulted only *after* execution,
to label the saga tick. The tier is documentation, not enforcement — the caller is the only gate. On
2026-07-07 a `/work` loop stepped `commit → push → open_pr → request_review → merge` and PR #525
merged to main (squash `2d35f36`) without the operator's word; the merge also auto-closed issue #390
via the templated `Fixes` line (LEARNINGS `{#ship-ceremony-run-does-not-self-gate}` + addendum). The
`/work` guidance (`plugins/saga/skills/work/SKILL.md:538-539`,
`plugins/saga/skills/work/references/pr-continuation-loop.md:99-104`) already frames merge as
"explicitly operator-confirmed" — the CLI just cannot enforce it.

---

## Requirements

- **R1.** A bare `run` whose upcoming transition is `always_operator`-tier refuses: non-zero exit, a
  message naming the withheld transition and the flag that unlocks it, and no state change (no
  transition runner invoked, no `saga.py save` recorded).
- **R2.** `run --operator-confirmed <transition>` executes the upcoming transition when the named
  transition matches it, recording the tick exactly as today.
- **R3.** When `--operator-confirmed <name>` does not match the upcoming transition, `run` refuses
  (non-zero exit, message naming both) and changes nothing — confirmation never "spills" onto a step
  the caller did not name.
- **R4.** Bare `run` behavior on `reversible`/`additive` transitions is unchanged; `start`,
  `install`, `uninstall` are untouched.
- **R5.** Tests cover the refusal path, the confirmed path, the mismatch path, and the CLI exit
  code/stderr shape, alongside the updated full-ceremony tests.
- **R6.** Release surfaces move together in the same PR: `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, and the drift-guard pin at
  `tests/test_saga_plugin.py:48`.
- **R7.** The guidance surfaces that instruct running the ceremony through `merge` →
  `branch_delete` name the flag: `plugins/saga/skills/work/SKILL.md` (Phase-5 merge step),
  `plugins/saga/skills/work/references/pr-continuation-loop.md` (approved-fresh row), and the
  module docstring's R5 paragraph in `ship_ceremony.py`.

---

## Key Technical Decisions

- **KTD1 — Confirmation names the transition: `--operator-confirmed <transition>`, not a bare
  boolean.** Binds the operator's word to one specific step. A bare boolean would spill onto
  whatever transition happens to be next — the exact shape-mismatch failure of PR #525, where the
  caller believed the next step was a draft-PR stop while the ledger was at `merge`. An interactive
  TTY prompt was rejected: `/work` and other agent callers are non-TTY, and the `git ship` alias
  (`!python3 <script> run`) appends trailing args, so `git ship --operator-confirmed merge` works
  unchanged at the terminal.
- **KTD2 — Enforce by tier lookup, never a name list.** The gate checks
  `TRANSITION_TIERS[upcoming] == CeremonyTier.ALWAYS_OPERATOR`, so any future transition declared
  `always_operator` inherits enforcement with zero extra wiring.
- **KTD3 — Refuse before dispatch, before the save.** The check sits in `run()` after
  `next_transition()` resolves `upcoming` (and after the `upcoming is None` "already shipped"
  early return) and before `_RUNNERS[upcoming]` — raising a new
  `OperatorConfirmationError(ShipCeremonyError)`. The existing CLI boundary
  (`main()`, lines 583-585) already converts `ShipCeremonyError` to stderr + exit 1, and the ledger
  is provably unadvanced because neither the runner nor `saga.py save` was reached.
- **KTD4 — The mismatch rule is uniform across tiers.** If the flag is present and its value does
  not equal the upcoming transition, refuse — even when the upcoming transition is reversible.
  One rule, no tier special-casing, and a mispredicted ledger position always surfaces instead of
  half-working.
- **KTD5 — Minor version bump (0.75.23 → 0.76.0).** Behavior change plus a new CLI surface on a
  shipped primitive; patch would understate it.

---

## Implementation Units

### U1. The gate in `run()` + CLI flag + tests

**Goal:** enforcement lands in `plugins/saga/scripts/ship_ceremony.py` with full test coverage.

**Changes:** add `OperatorConfirmationError(ShipCeremonyError)`; extend `run()` with keyword
`operator_confirmed: str | None = None` implementing KTD2/KTD3/KTD4; add
`--operator-confirmed <transition>` (choices: `TRANSITIONS`) to the `run` subparser and plumb it
through `main()`; update the module docstring's R5 paragraph; include the confirmation in the
success status line (e.g. `ran transition 'merge' (tier=always_operator, operator-confirmed)`) so
transcripts carry the audit trail.

**Test scenarios** (`tests/test_ship_ceremony.py`, house fake-runner pattern):

1. Bare `run` with upcoming `merge` → raises `OperatorConfirmationError` naming `merge`; the merge
   runner is never invoked and no `save` is recorded (ledger stays at `request_review`).
2. Bare `run` with upcoming `branch_delete` → same refusal naming `branch_delete`.
3. `run(operator_confirmed="merge")` at `merge` → executes, tick recorded with
   `tier=always_operator`.
4. `run(operator_confirmed="merge")` when upcoming is `commit` → mismatch refusal, nothing executed
   or recorded (KTD4).
5. CLI: bare `run` at a gated step exits 1 with the withheld-transition message on stderr (extend
   the `test_cli_main_reports_error_and_exits_nonzero` pattern, line 556); CLI with
   `--operator-confirmed merge` proceeds.
6. Existing tests that drive `run()` through a gated step, updated to pass the confirmation — the
   diff itself demonstrating the new contract: `test_full_ceremony_throwaway_branch:238` and
   `test_already_complete_ceremony_is_a_noop:268` (both loop all 7 transitions),
   `test_resume_from_state:255` (its 4th call executes `merge`), and
   `test_merge_before_open_pr_is_a_named_failure:502` (must pass `operator_confirmed="merge"` so
   the new refusal doesn't fire before the `pr_refs` guard the test exists to exercise). Verified
   complete against a census of all 14 `SC.run(` call sites — every other site stops at reversible
   steps, and `test_parity_git_surface_vs_work:284` calls no `run()` at all. Bare-run behavior
   over the reversible prefix (`commit → request_review`) asserted unchanged.
7. Flag on a completed ceremony: `run(operator_confirmed="merge")` when every transition has
   already run returns `already shipped` unchanged — the `upcoming is None` early return
   (`ship_ceremony.py:404-405`) stays ahead of the gate.

### U2. Guidance-surface alignment

**Goal:** every doc that instructs driving the ceremony through gated transitions names the flag.

**Changes:** `plugins/saga/skills/work/SKILL.md` (the Phase-5 merge step, ~lines 528-541) and
`plugins/saga/skills/work/references/pr-continuation-loop.md` (~lines 99-104) say the confirmed
merge run is `ship_ceremony.py run --operator-confirmed merge` (then `checkout_main` → `pull` bare,
then `--operator-confirmed branch_delete`).

**Test expectation:** none — guidance prose; behavior is covered by U1.

### U3. Release surfaces + engineering journal

**Goal:** installed-plugin metadata and the journal tell the same story as the diff (repo rule).

**Changes:** `plugins/saga/.claude-plugin/plugin.json` → `0.76.0`; `.claude-plugin/marketplace.json`
saga entry; `plugins/saga/CHANGELOG.md` `[0.76.0]` entry; drift-guard pin
`tests/test_saga_plugin.py:48`; DECISIONS entry for KTD1 (named-transition confirmation) already
staged with this plan; LEARNINGS `{#ship-ceremony-run-does-not-self-gate}` gets a one-line shipped
addendum referencing the PR.

**Test scenarios** (`tests/test_saga_plugin.py`): the existing version drift guard passes against
the new pin — no new tests needed beyond the pin update.

**Dependency order:** U1 first; U2 and U3 follow independently, all in one PR (single-commit-scale
change; the units are review lenses, not separate landings).

---

## Scope Boundaries

**Out of scope (true non-goals):**

- `start`, `install`, `uninstall` subcommands — `start` never steps a gated transition (push +
  draft PR only, line 427-482); nothing to gate.
- Caller-identity detection (proving a human typed the flag) — the flag is an auditable assertion
  in the transcript, which is the contract the outcome layer's ALWAYS_OPERATOR classification
  expects; identity proof is a different problem.
- The outcome coordinator's board-sync gating (`reversibility_certificate.py`) — deliberately
  separate vocabularies (ship_ceremony KTD1, module docstring).
- Changing merge semantics (`--squash`, auto-close `Fixes` line) — #526 gates *when* merge runs,
  not *how*.

**Deferred to Follow-Up Work:**

- #520 delegation-tripwire hardening (F1 requeue counter) — the sibling producer-without-consumer
  class this defect belongs to; tracked separately.
- A `status` subcommand to preview the upcoming transition without running it — would have helped
  the #525 shape-mismatch loop but is additive UX, not this defect.
