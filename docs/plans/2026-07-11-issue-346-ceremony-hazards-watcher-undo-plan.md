---
title: "Issue #346: ceremony hazard preflight, deterministic merge-watcher, and ship --undo rollback"
type: feat
status: active
date: 2026-07-11
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Issue #346: ceremony hazard preflight, deterministic merge-watcher, and ship --undo rollback

## Summary

Ship one safety layer over `plugins/saga/scripts/ship_ceremony.py` (the #345 primitive, now carrying
the #526 operator gate): a hazard registry + `detect()` preflight the ceremony consults before its
destructive transitions, a deterministic merge-watcher that records a merge expectation at PR-open
and re-validates it at merge time, and a rollback manifest written per transition that powers a
gated `ship --undo` path. Three cooperating modules, one consumer — the existing transition table —
plus the doc and release surfaces in the same PR.

---

## Problem Frame

`run()` executes the next unrun transition with no look at the world beyond the saga ledger:
`_do_merge` (`plugins/saga/scripts/ship_ceremony.py:345-349`) merges whatever the PR's current state
is at that instant, and `_do_branch_delete` (lines 364-373) deletes the recorded branch checking
only that its name is non-empty and not `main`. Nothing detects a stacked-PR topology (an open child
PR based on the branch about to be deleted), nothing distinguishes "checks stayed green through the
poll window" from "checks flipped and the merge raced ahead," and a ceremony that dies after merge
leaves the operator reconstructing state by hand — there is no undo. The session-mined evidence is
named in the issue: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119` (manual ship
ceremony, recurring pattern 1 across 8 repos) and `:147` (the `gh pr merge --auto`/`--delete-branch`
surprise singleton). Grounding note: the raw flags are **already absent** from all of
`plugins/saga/` (verified 2026-07-11 — every grep hit is the unrelated `--autonomous`), so R5 below
is a keep-clean guard plus the watcher mechanism, not a retirement sweep.

---

## Requirements

- **R1.** Stacked-PR hazard: given a branch-delete whose target branch has ≥1 open PR based on it,
  `ceremony_hazards.detect()` reports a typed hazard and the `run()` preflight refuses the delete
  (non-zero exit, hazard id + remedy named, ledger unadvanced) until the hazard is explicitly
  acknowledged or resolved.
- **R2.** Merge-landed guard (the auto-merge+delete-branch reorder): `branch_delete` refuses until
  the ceremony PR's live state is `MERGED` — a delete request arriving while the merge has not
  confirmably landed is reported as a hazard, never executed pre-emptively.
- **R3.** The merge-watcher records a merge expectation — target head SHA, required check names,
  review state — at PR-open time (both the `open_pr` transition and front-loaded `start`), before
  any poll loop exists.
- **R4.** At merge time the watcher re-validates the expectation against live PR state; any
  divergence (head moved, required check flipped or missing, review regressed, PR not open) is a
  named failure that blocks the merge. A mid-poll check flip — passing at one poll tick, failing at
  a later one — is caught even when the latest pre-flip poll was clean. Division of labor: the
  point-in-time hard gate wired into `run()`'s merge preflight is `validate`; the flip-catching
  poll window is the `watch` verb, a CLI/library utility exercised directly by the AC fixture and
  offered in the U5 guidance as the pre-merge wait — `run()` itself stays single-shot and
  stateless, never growing an internal poll loop.
- **R5.** No ceremony code path or ceremony reference doc invokes or instructs `gh pr merge
  --auto`/`--delete-branch`; the docs describe the merge-watcher instead. (Baseline is already
  clean; the grep in Verification is the guard.)
- **R6.** Every successful ceremony transition appends one entry to a rollback manifest carrying
  the data needed to revert it (branch + head SHA, PR number, squash-merge SHA, pre-merge
  `origin/main` SHA, remote-ref-created flag).
- **R7.** `ship --undo` reverts a ceremony from the manifest alone: killed after PR-open → closes
  the PR and deletes the pushed branch, leaving a clean tree; fully completed → reverts merge and
  cleanup back to pre-ceremony state (forward-only revert commit; branch resurrected from its
  recorded SHA). Undo is resumable and idempotent — entries are marked undone as they revert.
- **R8.** Undo of any `always_operator`-reversing entry is itself operator-gated (KTD5); a bare
  `--undo` covering only reversible entries runs without extra confirmation.
- **R9.** Release surfaces move in the same PR: `plugins/saga/.claude-plugin/plugin.json` (0.76.0 →
  0.77.0), `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, the drift-guard pin in
  `tests/test_saga_plugin.py`, a dated `docs/engineering-journal/LEARNINGS.md` entry recording the
  mined `--auto`/`--delete-branch` pattern and this fix, and the KTD record in
  `docs/engineering-journal/DECISIONS.md`.

---

## Key Technical Decisions

- **KTD1 — ceremony sidecar store, not saga tick fields.** The merge expectation and rollback
  manifest live as JSON sidecars in the saga's own directory —
  `.claude/saga/sagas/<saga_id>/merge_expectation.json` and
  `.claude/saga/sagas/<saga_id>/rollback_manifest.json` — written by their owning modules, never
  through `saga.py save`. Rationale: saga list fields are full-snapshot per tick (an appender that
  forgets one entry clobbers the rest), extending `saga.py`'s schema for ceremony-private state is
  churn with no second consumer, and `.claude/saga/` already hosts non-tick JSON state
  (`effort-ledger.json` on disk today; the #365 override mechanism at `tier_session.py:29` writes
  `tier-session-override.json` there on demand). The store is git-ignored and machine-local,
  matching the ceremony ledger's existing locality; the durable cross-machine truth (PR state,
  merge SHA) remains GitHub.
- **KTD2 — preflight placement.** Hazard detection and watcher validation run inside `run()` after
  the #526 operator-confirmation gate and before `_RUNNERS[upcoming]` dispatch and the `saga.py
  save` — a preflight refusal leaves the ledger provably unadvanced, the same proof shape the #526
  tests use (origin-main-SHA equality + branch-still-exists assertions).
- **KTD3 — named hazard acknowledgment.** Bypassing a detected hazard requires
  `--acknowledge-hazard <hazard-id>` (repeatable, `choices` drawn from the registry), mirroring the
  #526 named-confirmation pattern. There is no boolean acknowledge-everything flag; a refusal
  message lists exactly the detected hazard ids and their remedies. `merge_not_landed` (R2) is
  **not acknowledgeable** — it resolves only by the merge actually landing (or undo); acknowledging
  a stacked-PR hazard is a legitimate operator judgment, deleting a base branch under an open child
  never is by accident.
- **KTD4 — undo is forward-only.** Undoing a landed merge produces `git revert <recorded squash
  SHA>` on `main` (a new commit), and a deleted branch is resurrected from its recorded head SHA.
  `ship --undo` never rewrites history — no `push --force`, no `reset` on a shared ref. If a
  recorded SHA is unreachable (squash-discarded commits GC'd on origin, absent locally), undo
  surfaces a named `SHA_UNREACHABLE` failure for that entry rather than fabricating state.
- **KTD5 — undo gating mirrors forward tiers.** `undo` joins the operator-confirmation palette:
  when the undo plan includes entries that reverse `always_operator` transitions (merge,
  branch_delete), the caller must pass `--operator-confirmed undo`; a plan touching only
  reversible entries (e.g. killed-after-PR-open) runs on the explicit `--undo` flag alone. Same
  refuse-before-dispatch, ledger-unadvanced contract as the forward gate.
- **KTD6 — `ship --undo` is `run --undo`.** The undo entry point is a flag on the existing `run`
  subcommand, so the installed `git ship` alias (`!python3 <script> run`, which appends trailing
  args) works unchanged as `git ship --undo`. `ship_undo.py` holds the engine; `run()` only
  dispatches to it.
- **KTD7 — divergence never auto-heals.** A watcher divergence blocks the merge and stays blocked
  until the operator explicitly re-baselines with `merge_watcher.py record --force` (the legitimate
  case: a round-N+1 push after review changes). The watcher never silently refreshes its own
  expectation.
- **KTD8 — missing expectation is a named refusal, not a silent pass.** A merge preflight finding
  no `merge_expectation.json` (in-flight ceremony from before this feature, or a sidecar deleted)
  refuses with a remedy line naming the `record` command. Strictness is the point of the layer;
  the remedy keeps the upgrade path one command long.

---

## Implementation Units

### U1. `ceremony_hazards.py` — hazard registry + `detect()`

**Goal:** A pure, runner-injectable module: `Hazard` dataclass (`hazard_id`, `transition`,
`message`, `remedy`, `acknowledgeable`), an ordered registry, and
`detect(saga, upcoming, repo_root, runner) -> list[Hazard]` probing live `gh` state.

**Behavior:** For `branch_delete`: probe `gh pr list --base <branch> --state open --json
number,title` → `stacked_pr` hazard per R1 (acknowledgeable); probe the ceremony PR's `gh pr view
--json state,mergedAt` → `merge_not_landed` hazard per R2 (not acknowledgeable). For `merge`:
`stacked_pr` probe against the work branch (children based on the branch being merged are about to
be re-based by the squash — report, acknowledgeable). Non-gated transitions return `[]` without
probing (no added `gh` latency on reversible steps). A failed probe raises (fail-loud), never
returns an empty list as if clean.

**Files:** `plugins/saga/scripts/ceremony_hazards.py` (new), `tests/test_ceremony_hazards.py` (new).

**Depends on:** nothing.

**Test scenarios** (`tests/test_ceremony_hazards.py`, module-local fake runner — the full
`FakeGh`/bare-origin rig stays in `tests/test_ship_ceremony.py` for U4's integration tests):
`test_stacked_pr_hazard_reported_for_branch_delete` (AC grep `-k stacked_pr_hazard`);
`test_auto_merge_delete_branch_hazard_reorders` — delete requested, PR not yet `MERGED` →
`merge_not_landed` reported, marked non-acknowledgeable (AC `-k auto_merge_delete_branch_hazard`);
`test_no_hazards_on_clean_topology_returns_empty`; `test_reversible_transitions_probe_nothing`
(runner records zero `gh` calls); `test_probe_failure_raises_not_empty`;
`test_hazard_ordering_is_registry_order`.

### U2. `merge_watcher.py` — deterministic merge expectation

**Goal:** Record/validate/watch verbs over the KTD1 sidecar: `record` captures `{pr_number,
head_sha, required_checks: [name...], review_state, recorded_at}` from `gh pr view --json
number,headRefOid,statusCheckRollup,reviewDecision`. This repo has no branch-protection rules, so
there is no API-defined "required" set — the recorded baseline is the full set of check contexts
observed at record time, and that recorded set is what `validate`/`watch` hold the merge to; `validate` re-fetches and compares, raising a
typed `MergeExpectationDiverged` naming the divergence kind (`head_moved`, `check_flipped`,
`check_missing`, `review_regressed`, `pr_not_open`) — or `MergeExpectationMissing` per KTD8;
`watch` polls N ticks through an injectable poll source and fails on any tick where a
previously-passing required check is non-passing, even if the final tick is green again.

**Behavior:** All comparisons are against the recorded baseline (KTD7); `record --force` is the
only re-baseline path. No sleeping in library code — the poll source and tick delay are injected so
tests are deterministic and instant.

**Files:** `plugins/saga/scripts/merge_watcher.py` (new), `tests/test_merge_watcher.py` (new).

**Depends on:** nothing.

**Test scenarios** (`tests/test_merge_watcher.py`):
`test_records_expectation_at_open` — sidecar written with SHA/checks/review before any poll (AC
`-k records_expectation_at_open`); `test_midpoll_check_flip_blocks_merge` — pass→fail→pass
sequence across ticks still raises `check_flipped` (AC `-k midpoll_check_flip_blocks_merge`);
`test_head_moved_divergence_named`; `test_review_regressed_divergence_named`;
`test_missing_expectation_refuses_with_remedy` (KTD8); `test_record_force_rebaselines`
(KTD7 — plain re-`record` over an existing sidecar refuses; `--force` succeeds);
`test_validate_matches_clean_state_passes`.

### U3. `ship_undo.py` — rollback manifest + undo engine

**Goal:** Manifest append/read helpers (one JSON-lines-style entry per transition in the KTD1
sidecar: `{transition, tier, branch, head_sha, pr_number, merge_sha, pre_merge_main_sha,
remote_created, undone: false}`) and `undo(saga, repo_root, operator_confirmed, runner)` executing
the reverse plan newest→oldest per KTD4, marking each entry `undone: true` as it lands (resumable,
stateless re-read like the forward ceremony).

**Behavior:** Reverse steps — `branch_delete` → recreate branch from `head_sha` + push;
`pull`/`checkout_main` → restore the recorded pre-ceremony checkout (no-op if already there);
`merge` → `git revert <merge_sha>` on `main` + push (KTD4); `open_pr` → `gh pr close <N>`;
`commit` → delete the remote ref iff `remote_created`. Newest→oldest governs **mutation order**,
not which ref is HEAD — ref-sensitive steps manage their own checkout explicitly (the merge revert
checks out `main` for itself regardless of where a prior checkout-undo left HEAD). Gating per KTD5
computed from the entries in scope before anything executes. Empty or fully-undone manifest → no-op success message. Unreachable
SHA → named `SHA_UNREACHABLE` failure, remaining entries untouched.

**Files:** `plugins/saga/scripts/ship_undo.py` (new), `tests/test_ship_undo.py` (new).

**Depends on:** nothing (manifest writer lives here; U4 calls it).

**Test scenarios** (`tests/test_ship_undo.py`):
`test_manifest_written_per_transition` — end-to-end throwaway-branch ceremony produces one entry
per transition (AC `-k manifest_written_per_transition`; drives the real `ship_ceremony.run` via
the U4 hook, so this test lands green only after U4 — ordering note for `/work`);
`test_undo_after_kill_at_pr_open_closes_pr_and_deletes_branch` (reversible-only plan, bare
`--undo` suffices per KTD5); `test_undo_reverts_completed_ceremony` — revert commit on main +
branch resurrected, from manifest alone (AC `-k undo_reverts_completed_ceremony`);
`test_undo_of_merged_ceremony_requires_operator_confirmed_undo` (refusal: no `gh`/`git` mutation
recorded, manifest unmarked); `test_undo_is_resumable_after_partial_failure`;
`test_empty_manifest_is_noop_success`; `test_unreachable_sha_named_failure`.

### U4. `ship_ceremony.py` wiring — preflight, manifest hook, `--undo`

**Goal:** Wire the three modules into the transition table without redesigning it: in `run()`,
after the #526 gate and before dispatch (KTD2), call `ceremony_hazards.detect()` for the upcoming
transition and refuse on unacknowledged hazards (`--acknowledge-hazard`, KTD3); for `merge`, call
`merge_watcher.validate` (KTD8 on absence); after every successful transition, append the U3
manifest entry; in `_do_open_pr` and `start`, call `merge_watcher.record`; add `--undo` to the
`run` subcommand dispatching to `ship_undo.undo` (KTD6) and extend the `--operator-confirmed`
palette with `undo` (KTD5). The `--undo` branch forks **before** the forward gate and mismatch
checks — `--operator-confirmed undo` must never trip the forward mismatch rule against the
upcoming forward transition.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (extend), `tests/test_ship_ceremony.py`
(extend — the `FakeGh` rig grows `pr list --base` and `statusCheckRollup` handling).

**Depends on:** U1, U2, U3.

**Test scenarios** (`tests/test_ship_ceremony.py` extensions):
`test_branch_delete_refused_on_stacked_pr_until_acknowledged` — refusal leaves origin-main SHA and
ledger unchanged; `--acknowledge-hazard stacked_pr` unlocks; `test_merge_not_landed_blocks_branch_delete_and_is_not_acknowledgeable`;
`test_merge_preflight_validates_expectation_and_diverged_blocks` (ledger-unadvanced proof);
`test_open_pr_and_start_both_record_expectation`; `test_manifest_appended_per_transition_in_full_ceremony`;
`test_run_undo_dispatches_to_ship_undo_and_gh_ship_alias_shape_unchanged`;
`test_full_ceremony_green_path_unchanged_when_no_hazards` (regression: the four-invocation #526
flow still passes with the new hooks active).

### U5. Ceremony docs describe the new layer

**Goal:** `plugins/saga/skills/work/references/pr-continuation-loop.md` "Merge is a confirmed git
op" section gains the watcher + hazard + undo contract (expectation recorded at PR-open, validated
at merge, divergence blocks, hazards need named acknowledgment, `git ship --undo` exists and is
gated); `plugins/saga/skills/work/SKILL.md` Phase-5 merge step gets one pointer line. Lines stay
≤106 chars (the #526 review's prose-blowout finding); no `--auto`/`--delete-branch` tokens
introduced (R5 grep must stay clean).

**Files:** `plugins/saga/skills/work/references/pr-continuation-loop.md`,
`plugins/saga/skills/work/SKILL.md`.

**Depends on:** U4.

**Test expectation:** none — guidance prose; the R5 grep in Verification is the mechanical check.

### U6. Release surfaces + journal

**Goal:** 0.76.0 → 0.77.0 in `plugins/saga/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`; drift-guard pin in `tests/test_saga_plugin.py`; CHANGELOG entry
covering hazard preflight, merge-watcher, and `ship --undo`; dated LEARNINGS entry (mined
`--auto`/`--delete-branch` pattern → this durable fix); DECISIONS entry mirroring the KTDs (drafted
at plan time, ships in this PR).

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`.

**Depends on:** U4.

**Test expectation:** none — release metadata; the drift-guard and full suite in Verification are
the mechanical checks.

---

## Scope Boundaries

Out of scope (do not do in this issue):

- **The ceremony state machine itself** — transitions, ledger, resume semantics are #345's shipped
  surface; this layer consults and wraps, never redesigns.
- **Automatic rebase/reopen of child PRs after a base merge** — `pf-stacked-pr-cascade-guard`
  (wave-3), which sits behind this issue's hazard preflight. Here we only detect and
  refuse/acknowledge.
- **Ceremony-terminal teardown/reconciliation** — `pf-ship-teardown-reconciliation`.
- **The outcome DAG auto-merge queue** (`plugins/saga/scripts/outcome_github.py:338`) — a separate,
  deliberate merge authority (code-review #526 finding 4, report-only); routing it through the
  watcher is a new issue if ever wanted.
- **Board↔saga reconciliation and evidence-ledger surfaces** — already shipped / separately owned.

Deferred to follow-up work (distinct from non-goals): GitHub-side issue state after a merge undo —
`git revert` does not reopen an issue auto-closed by the squash's `Fixes #N` line; the undo path
prints a reminder naming the issue rather than mutating it (issue-state writes belong to
mission-control).

---

## Risk Analysis & Mitigation

- **Undo of a landed merge is an outward mutation on `main`.** Mitigated three ways: forward-only
  revert (KTD4), the `--operator-confirmed undo` gate (KTD5), and refusal-before-dispatch with
  ledger/manifest proofs in tests. Pre-mortem: the likeliest failure is a revert that half-applies
  (revert lands locally, push rejected) — the engine treats push failure as the entry NOT undone
  (marker only set after push confirms), so resume retries cleanly.
- **Preflight adds `gh` probes to gated transitions.** Bounded: only `merge`/`branch_delete` probe
  (U1 behavior), reversible steps stay zero-network; a probe failure fails loud rather than
  proceeding blind.
- **In-flight ceremonies at upgrade time have no expectation sidecar.** KTD8 turns this into a
  one-command remedy instead of a silent pass or a hard dead-end.
- **Fixture complexity.** The mid-poll flip and stacked-topology fixtures are the real work (the
  issue's own executor-profile justification). Mitigated by module-local fakes (U1-U3) and
  extending the proven `FakeGh` rig only for U4 integration paths.

## Alternatives Considered

- **Store expectation/manifest on saga ticks** — rejected: full-snapshot list semantics make
  append-only bookkeeping clobber-prone, and it couples `saga.py`'s schema to ceremony-private
  state (KTD1).
- **A separate `undo` subcommand + reinstalled alias** — rejected: breaks every installed
  `git ship` alias and the muscle-memory UX; `run --undo` is alias-compatible (KTD6).
- **Reusing `reversibility_certificate.py` for undo tiers** — rejected for the same reason #345
  KTD1 declined it: its `OpKind` allowlist deliberately excludes merge/repo-level mutations.
- **Watcher auto-refreshes expectation on divergence** — rejected: silently re-baselining is
  exactly the "merge raced ahead anyway" failure the issue exists to kill (KTD7).

---

## Verification

```bash
# New module suites
uv run pytest tests/test_ceremony_hazards.py tests/test_merge_watcher.py tests/test_ship_undo.py -v

# Retired-flag guard (expected: no matches, grep exits 1)
grep -rn -- "--auto\|--delete-branch" plugins/saga/scripts/ship_ceremony.py \
  plugins/saga/scripts/ceremony_hazards.py plugins/saga/scripts/merge_watcher.py \
  plugins/saga/skills/work/references/pr-continuation-loop.md; echo "exit: $?"

# Full repo gate (CI parity — format check is a separate gate from lint)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```
