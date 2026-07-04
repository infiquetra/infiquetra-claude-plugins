---
title: "enhancement: ceremony hazard preflight, deterministic merge-watcher, and ship --undo rollback"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Automate the ship ceremony end-to-end
wave: wave-1
---

# enhancement: ceremony hazard preflight, deterministic merge-watcher, and ship --undo rollback

### Objective

Harden the guarded ship primitive (`pf-ship-ceremony-primitive`, `plugins/saga/scripts/ship_ceremony.py`)
against the concrete `gh`/git edge cases mined from real sessions — stacked PRs auto-closed
by a base merge, `gh pr merge --auto`/`--delete-branch` deleting more than intended, and
ceremonies that die partway through with no way back — by shipping one shared hazard
detector the ceremony consults before acting, a deterministic merge-watcher that replaces
raw `--auto`/`--delete-branch` flags, and a rollback manifest that makes `ship --undo`
possible. All three are one safety layer over the same primitive, not three standalone
features.

### Problem / motivation

- **Manual/raw ship ceremony is the single most-recurring cross-repo pain this ideation
  pass found.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119` records it as
  recurring pattern 1, ranked first by repo spread: "Manual ship ceremony — commit→PR→merge→
  checkout-main→pull→cleanup done by raw git/gh in session after session, even where
  saga/mission-control is installed (8 repos)." The primitive itself
  (`pf-ship-ceremony-primitive`) replaces the raw ritual; this issue is the safety layer that
  keeps that primitive from doing the wrong destructive thing when `gh` behaves in a
  surprising way.
- **The specific `gh` hazards are named, dated evidence, not speculation.**
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:147` lists as a session-mining
  singleton: "`gh pr merge --auto`/`--delete-branch` behavior surprises; stacked-PR
  auto-close + CI branch-trigger gap." Today nothing in the fleet detects a stacked-PR
  topology before merging a base branch, and nothing distinguishes "checks stayed green
  through the whole poll window" from "checks were green, then flipped, then the merge
  raced ahead anyway."
- **The ceremony has no rollback path today.** `/work`'s existing PR-continuation loop
  (`plugins/saga/skills/work/references/pr-continuation-loop.md:37`) only ever offers a
  forward `gh pr merge`, explicitly confirmed, with no undo branch if a downstream step
  (checkout-main, pull, cleanup) fails after the merge already landed. A ceremony that
  dies at "merged but not yet cleaned up" today leaves the operator to reconstruct state
  by hand.
- **This issue is deliberately a safety layer over the primitive, not a redesign of it.**
  Per the issue-map consolidation rationale: "All three harden the ship verb against the
  `gh` edge cases mined from sessions (auto-merge/delete-branch surprises): shared hazard
  detector, merge-expectation watcher, and rollback manifest are one safety layer shipped
  against the primitive." It depends on `pf-ship-ceremony-primitive`
  (`plugins/saga/scripts/ship_ceremony.py`, absorbing `T7-F4-1`/`H-F3-6`/`H-F2-3`) existing
  as the state machine this layer consults and wraps; it does not re-implement ceremony
  state transitions.

## Definition of Done

1. `plugins/saga/scripts/ceremony_hazards.py` — a hazard registry + `detect()` function
   returning an ordered list of typed warnings — consumed by the ship preflight step
   (before any merge/branch-delete action fires). Fixtures covering a stacked-PR topology
   and an auto-merge+delete-branch combination assert the ceremony refuses or reorders the
   action rather than deleting a base branch out from under an open child PR.
2. A deterministic merge-watcher that records the merge expectation (target SHA, required
   checks, review state) at PR-open time and re-validates it at merge time, replacing raw
   `gh pr merge --auto`/`--delete-branch` invocations; a mid-poll check-flip fixture
   asserts the watcher surfaces the divergence as a named failure rather than merging
   anyway. `--auto`/`--delete-branch` are retired from ceremony docs and code paths.
3. A rollback manifest written at each ceremony transition, consumed by a new
   `ship --undo` path that reverts a completed-but-unwanted ceremony (closes the PR,
   restores the pre-ceremony branch state, undoes the local cleanup) using only the
   manifest — no interactive reconstruction.

### Acceptance criteria
- [ ] **Stacked-PR hazard detection (T7-F4-4).** Given a fixture where the target branch
  has one or more open child PRs based on it (a stacked-PR topology), `ceremony_hazards.detect()`
  reports the hazard and the ship preflight refuses to proceed with a base-branch delete
  until the stack is explicitly acknowledged or resolved. Check: `uv run pytest
  tests/test_ceremony_hazards.py -k stacked_pr_hazard` → passes.
- [ ] **Auto-merge + delete-branch hazard detection (T7-F4-4).** Given a fixture combining
  `--auto` semantics with a base-branch delete request, `detect()` reports the hazard and
  the ceremony reorders (delete only after merge is confirmed landed) rather than deleting
  the base branch pre-emptively. Check: `uv run pytest tests/test_ceremony_hazards.py -k
  auto_merge_delete_branch_hazard` → passes.
- [ ] **Merge-watcher records expectation at PR-open (T7-F2-6).** Opening a PR through the
  ceremony writes a merge-expectation record (target SHA, required checks, review state)
  before any poll loop starts. Check: `uv run pytest tests/test_merge_watcher.py -k
  records_expectation_at_open` → passes.
- [ ] **Merge-watcher surfaces mid-poll divergence instead of merging (T7-F2-6).** Given a
  fixture where a required check transitions from passing to failing between poll ticks,
  the watcher raises a named divergence failure and does not call merge, even though the
  most recent poll before the flip was clean. Check: `uv run pytest
  tests/test_merge_watcher.py -k midpoll_check_flip_blocks_merge` → passes.
- [ ] **Raw `--auto`/`--delete-branch` retired from ceremony code and docs (T7-F2-6).** No
  ceremony code path invokes `gh pr merge` with `--auto` or `--delete-branch`; ceremony
  reference docs describe the merge-watcher instead. Check: `grep -rn -- "--auto\|--delete-branch"
  plugins/saga/scripts/ship_ceremony.py plugins/saga/scripts/ceremony_hazards.py
  plugins/saga/scripts/merge_watcher.py plugins/saga/skills/work/references/pr-continuation-loop.md`
  → no matches.
- [ ] **Rollback manifest written at each transition (T7-F1-2).** Running the ceremony
  end-to-end on a throwaway branch produces a rollback manifest with one entry per
  transition (branch created, PR opened, merged, cleaned up). Check: `uv run pytest
  tests/test_ship_undo.py -k manifest_written_per_transition` → passes.
- [ ] **`ship --undo` reverts a completed ceremony (T7-F1-2).** A test kills the ceremony
  after PR-open (before merge) and asserts `ship --undo` closes the PR and deletes the
  branch, leaving a clean tree; a second test lets the ceremony complete fully and asserts
  `--undo` reverts merge + cleanup back to the pre-ceremony state using only the manifest.
  Check: `uv run pytest tests/test_ship_undo.py -k undo_reverts_completed_ceremony` →
  passes.
- [ ] **Full suite, format, lint, types, security stay green.** Check: `uv run pytest &&
  uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/
  tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

### Out-of-scope / non-goals
In scope: one shared hazard-detection module, one deterministic merge-watcher replacing
raw `gh pr merge --auto`/`--delete-branch`, and one rollback manifest + `ship --undo` path
— all consumed by the existing ship-ceremony state machine.

Out of scope (do not do in this issue):

- **Building the ship-ceremony state machine itself.** `plugins/saga/scripts/ship_ceremony.py`
  (state machine, transition table, resume-from-state) is `pf-ship-ceremony-primitive`
  (`T7-F4-1`/`H-F3-6`/`H-F2-3`), a separate structural issue in the same objective. This
  issue consumes and wraps that primitive; it does not redesign its transitions.
- **The stacked-PR cascade guard's automatic rebase-and-reopen machinery.** Automatically
  rebasing, reopening, and CI-retriggering child PRs after a base merge is
  `pf-stacked-pr-cascade-guard` (`T7-F2-7`/`S-14`), a separate wave-3 moonshot explicitly
  described as sitting "behind the hazard preflight" this issue ships. This issue only
  detects and refuses/reorders around the stacked-PR hazard; it does not rebase or reopen
  anything automatically.
- **Ceremony-terminal teardown/reconciliation** (worktree cleanup, lease release after a
  successful ship) — that is `pf-ship-teardown-reconciliation`
  (`G-hybrids-3`/`T7-F5-2`/`T7-F4-7`/`T7-F2-2`), a separate issue in the same objective.
- **Board↔saga status reconciliation for the ceremony** — already shipped separately per
  `6b33eba feat(saga): board↔saga reconciliation on resume (#295) (#330)`; this issue does
  not touch board-status write paths.
- **Evidence-ledger / chain-of-custody changes** — `pf-evidence-gated-closure` /
  `pf-evidence-immutability` own that surface; the rollback manifest here is ceremony-scoped
  state, not the fleet's evidence-immutability ledger.

## Grounding References

- **Primary — `T7-F4-4`**, "ceremony_hazards.py — one shared preflight detector the ship
  verb consults." Basis: theme T7 (ship ceremony), frame F4 (ceremony-edge-cases);
  `dod_sketch`: "Merged ceremony_hazards.py (hazard registry + detect() returning ordered
  warnings) consumed by the ship preflight; test with stacked-PR and
  auto-merge+delete-branch fixtures asserts the ceremony refuses/reorders rather than
  deleting a base branch."
- **Facet — `T7-F2-6`**, "Retire raw `gh pr merge --auto/--delete-branch` for a
  deterministic saga merge-watcher." Basis: theme T7, frame F2 (ceremony-edge-cases);
  `dod_sketch`: "Merged merge-watcher that records merge expectations at PR-open and
  matches them at merge time + a retired-flags doc; test simulates a mid-poll check flip
  and asserts the watcher surfaces the divergence rather than merging."
- **Facet — `T7-F1-2`**, "Ship-ceremony rollback manifest: `/ship --undo` for
  partial-failure recovery." Basis: theme T7, frame F1 (ship-verb); `dod_sketch`: "Merged
  rollback-manifest schema + `/ship --undo` branch; test kills the ceremony after PR-open
  and asserts `--undo` closes the PR and deletes the branch, leaving a clean tree."
- **Consolidation rationale (issue-map, `pf-ship-hazard-preflight-and-undo`):** "All three
  harden the ship verb against the gh edge cases mined from sessions (auto-merge/delete-branch
  surprises): shared hazard detector, merge-expectation watcher, and rollback manifest are
  one safety layer shipped against the primitive."
- **Recurring-pain grounding** — `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119`
  (theme 7, "Manual ship ceremony," ranked #1 by repo spread across 8 repos) and
  `:147` (session-mining singleton naming the exact `gh pr merge --auto`/`--delete-branch`
  surprises and the stacked-PR auto-close + CI branch-trigger gap this issue fixes).
- **Depends on** `pf-ship-ceremony-primitive` (absorbing `T7-F4-1`/`H-F3-6`/`H-F2-3`,
  `plugins/saga/scripts/ship_ceremony.py`) — that issue must land first or in the same
  wave, since this issue's hazard detector, merge-watcher, and undo manifest all attach to
  its transition table.
- **Existing primitive this issue reuses without modifying:**
  `plugins/saga/skills/work/references/pr-continuation-loop.md:37` (current confirmed
  `gh pr merge` offer this issue's merge-watcher supersedes).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** Well-scoped safety layer over an existing (sibling-issue) primitive —
  three cooperating modules (hazard registry, merge-watcher, rollback manifest) with
  concrete fixture-driven acceptance criteria and no open architectural question; high
  effort reflects the number of `gh`-behavior edge cases to fixture correctly, not any
  need for consensus review or an external engine.

### Release-surface checklist

This issue adds new ceremony-safety modules to the `saga` plugin and retires raw
`gh pr merge` flag usage from its docs. Update in same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new hazard-detector,
  merge-watcher, and `ship --undo` surfaces).
- [ ] `.claude-plugin/marketplace.json` — reflect version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the hazard preflight, deterministic
  merge-watcher, and `ship --undo` rollback path, and the retirement of raw
  `--auto`/`--delete-branch` usage.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. marketplace/plugin.json
  parity test) re-run green after bump.
- [ ] `docs/engineering-journal/LEARNINGS.md` — dated entry recording the mined
  `gh pr merge --auto`/`--delete-branch` surprise pattern as concrete evidence and
  pointing at this issue's hazard detector/merge-watcher as the durable fix.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/ceremony_hazards.py` — new hazard registry + `detect()` (proposed
  path).
- `plugins/saga/scripts/merge_watcher.py` — new deterministic merge-expectation
  recorder/matcher replacing raw `--auto`/`--delete-branch` calls (proposed path).
- `plugins/saga/scripts/ship_ceremony.py` — preflight call-site wiring to
  `ceremony_hazards.detect()` and `merge_watcher`; rollback-manifest write per transition
  (existing file from `pf-ship-ceremony-primitive`, extended here).
- `plugins/saga/scripts/ship_undo.py` — new `ship --undo` entry point consuming the
  rollback manifest (proposed path).
- `plugins/saga/skills/work/references/pr-continuation-loop.md` — replace the raw
  `gh pr merge` confirmation language with the merge-watcher flow; remove
  `--auto`/`--delete-branch` mentions.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version sync.
- `plugins/saga/CHANGELOG.md` — release entry.
- `tests/test_ceremony_hazards.py` — stacked-PR hazard, auto-merge+delete-branch hazard
  fixtures.
- `tests/test_merge_watcher.py` — records-at-open, mid-poll-check-flip fixtures.
- `tests/test_ship_undo.py` — manifest-per-transition, undo-after-partial-failure,
  undo-after-full-completion fixtures.
- `docs/engineering-journal/LEARNINGS.md` — dated entry.

### Verification

```bash
# New hazard-detector, merge-watcher, and undo unit tests
uv run pytest tests/test_ceremony_hazards.py tests/test_merge_watcher.py tests/test_ship_undo.py -v

# Retired-flag guard: no raw --auto/--delete-branch usage remains in ceremony code/docs
grep -rn -- "--auto\|--delete-branch" plugins/saga/scripts/ship_ceremony.py \
  plugins/saga/scripts/ceremony_hazards.py plugins/saga/scripts/merge_watcher.py \
  plugins/saga/skills/work/references/pr-continuation-loop.md; echo "exit: $?"

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the retired-flag grep finds no matches (exit `1`); stacked-PR and
auto-merge+delete-branch fixtures show the ceremony refusing/reordering rather than
deleting a base branch; the mid-poll-check-flip fixture shows the watcher blocking merge;
`ship --undo` reverts both a partial and a fully-completed ceremony from its manifest
alone.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan (after or alongside
`pf-ship-ceremony-primitive`, which this issue depends on).

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json (`T7-F4-4`,
  `T7-F2-6`, `T7-F1-2`)
- Source type: issue-map
- Source title: Ceremony hazard preflight, deterministic merge-watcher, and ship --undo
  rollback

### Context library links

_none_

### Tests to add or update

- `tests/test_ceremony_hazards.py`
- `tests/test_merge_watcher.py`
- `tests/test_ship_undo.py`

### Intent

- **Manual/raw ship ceremony is the single most-recurring cross-repo pain this ideation pass found.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119` records it as recurring pattern 1, ranked first by repo spread: "Manual ship ceremony — commit→PR→merge→ checkout-main→pull→cleanup done by raw git/gh in session after session, even where saga/mission-control is installed (8 repos)." The primitive itself (`pf-ship-ceremony-primitive`) replaces the raw ritual; this issue is the safety layer that keeps that primitive from doing the wrong destructive thing when `gh` behaves in a surprising way. - **The specific `gh` hazards are named, dated evidence, not speculation.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:147` lists as a session-mining singleton: "`gh pr merge --auto`/`--delete-branch` behavior surprises; stacked-PR auto-close + CI branch-trigger gap." Today nothing in the fleet detects a stacked-PR topology before merging a base branch, and nothing distinguishes "checks stayed green through the whole poll window" from "checks were green, then flipped, then the merge raced ahead anyway." - **The ceremony has no rollback path today.** `/work`'s existing PR-continuation loop (`plugins/saga/skills/work/references/pr-continuation-loop.md:37`) only ever offers a forward `gh pr merge`, explicitly confirmed, with no undo branch if a downstream step (checkout-main, pull, cleanup) fails after the merge already landed. A ceremony that dies at "merged but not yet cleaned up" today leaves the operator to reconstruct state by hand. - **This issue is deliberately a safety layer over the primitive, not a redesign of it.** Per the issue-map consolidation rationale: "All three harden the ship verb against the `gh` edge cases mined from sessions (auto-merge/delete-branch surprises): shared hazard detector, merge-expectation watcher, and rollback manifest are one safety layer shipped against the primitive." It depends on `pf-ship-ceremony-primitive` (`plugins/saga/scripts/ship_ceremony.py`, absorbing `T7-F4-1`/`H-F3-6`/`H-F2-3`) existing as the state machine this layer consults and wraps; it does not re-implement ceremony state transitions.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/346
- Number: 346
- Created at: 2026-07-04T07:45:09.622361+00:00

