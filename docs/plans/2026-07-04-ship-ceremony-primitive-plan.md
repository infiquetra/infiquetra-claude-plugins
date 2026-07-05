---
title: ship_ceremony.py — one composable, resumable, guarded ship primitive
type: feat
status: active
date: 2026-07-04
origin: docs/sdlc-issue-drafts/plugin-fleet/pf-ship-ceremony-primitive.md
---

# ship_ceremony.py — one composable, resumable, guarded ship primitive

## Summary

Replace the raw, hand-typed `commit → PR → merge → checkout-main → pull → branch-delete`
sequence `/work` currently drives inline with one CLI primitive, `ship_ceremony.py`: an
explicit, resumable transition table that ticks the issue's existing work-thread saga per
transition, is callable both from `/work` and from a terminal-only git alias, and supports a
front-loaded mode that opens a draft PR at `/work` start so "ship" later is a flip-to-ready
rather than a fresh ritual.

## Problem Frame

Session-mining synthesis ranks "manual ship ceremony" the #1 recurring pain pattern by repo
spread (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119-121`): commit → PR →
merge → checkout-main → pull → cleanup done via raw `git`/`gh` in-session, even in repos
where saga/mission-control are installed (8 repos). `plugins/saga/skills/work/SKILL.md`
section 5.4 hand-drives `gh pr create` + reviewer request (`work/SKILL.md:445`) and, once
approved/clean/fresh, offers `gh pr merge` (`work/SKILL.md:452`) — there is no state machine,
no resume-from-interruption, and no recorded post-merge cleanup step (checkout-main, pull,
branch-delete) anywhere in the flow. Three ideation facets converge on this gap and are
absorbed into one issue per the portfolio-groom consolidation rule
(`{#plugin-portfolio-groom-17-to-7}`): the core state machine (T7-F4-1), a git-surface entry
point independent of a live Claude Code conversation (H-F3-6), and front-loading ceremony
prep to `/work` start so shipping becomes flip-to-ready (H-F2-3).

## Requirements

R1. `plugins/saga/scripts/ship_ceremony.py` implements an explicit, ordered transition table
— `commit → open/reuse PR → request review → merge → checkout-main → pull →
branch-delete` — as a stateless CLI script (re-reads state each invocation, matching the
house pattern in `saga.py` / `outcome_store.py` / `execution_spec.py`).

R2. Every transition is resumable: invoking the primitive again after an interruption
continues from the last-recorded transition rather than restarting or duplicating a
completed one (e.g. never opens a second PR for the same branch).

R3. Every transition records, in the state it persists: (a) which transition ran, (b) a
reversibility tier for that transition (see KTD1), and (c) enough to resume. This state
rides the issue's existing work-thread saga as new tick fields (KTD2) — `/work`'s existing
restore already picks it up; there is no second store to keep in sync.

R4. The primitive is invocable from two distinct entry points that share one implementation:
(a) `/work`'s existing PR-ready flow (`work/SKILL.md` section 5.4), replacing the raw `gh pr
create` / `gh pr merge` calls there; (b) a git-surface entry point — a local git alias
(`git ship`) installed/uninstalled by the primitive itself — so ceremony can be triggered
from a terminal without a live Claude Code conversation (KTD3).

R5. Merge, PR-open, and review-request remain explicitly operator-confirmed mutating steps
in both entry points — the primitive automates transition *sequencing and bookkeeping*, not
*authorization*. This preserves `/work`'s existing "must not silently mutate GitHub" boundary
(`work/SKILL.md` section 5.5).

R6. `plugins/saga/skills/work/SKILL.md` no longer contains any raw ceremony `git`/`gh`
commands (`git checkout`, `git pull`, `git branch -d`, ad hoc `gh pr create` / `gh pr
merge`) — section 5.4 delegates to `ship_ceremony.py` instead.

R7. A front-loaded mode (`ship_ceremony.py start`), invoked at `/work` Phase 1 after the
saga mint, pushes an initial scaffold commit on the working branch and opens a draft PR
carrying the plan link. The primitive's later transitions detect the existing draft PR and
flip it ready rather than opening a new one.

## Key Technical Decisions

**KTD1 — Ceremony transitions get their own reversibility-tier registry, not
`reversibility_certificate.py`.** `reversibility_certificate.py`'s own docstring states its
`OpKind` allowlist is scoped to mission-control board/issue verbs and *intentionally excludes*
"merge, deploy, and repo-level mutations" (R20 in that module). Reusing it for `git
checkout` / `gh pr merge` / `git branch -d` would fight its closed-allowlist design. Instead
`ship_ceremony.py` defines a small local `CeremonyTier` mirroring that module's vocabulary
(`reversible` / `additive` / `always_operator`) for consistency, applied to its own seven
transitions: `commit` (reversible — amend/reset), `open_pr` (reversible — can close), `merge`
(`always_operator` — never auto-fired, R5), `checkout_main` / `pull` (reversible), `branch_delete`
(`always_operator` — destructive and not silently retried after a failed later step).

**KTD2 — Ceremony state is new fields on the existing work-thread saga tick, not a second
store.** The alternative (a dedicated `.claude/saga/ship-ceremony/<branch>/` side-channel,
mirroring `outcome_store.py`'s ledger) would give `/work` two state sources to reconcile on
resume. Since every ceremony run already has a governing issue saga (via `/work`'s Phase 1.4
mint, or via the git-alias path resolving the current saga by branch — the saga already
keys on `branch`, per `saga-spec.md` §2), the primitive appends its transition index and tier
to that saga's next tick instead. `saga.py save` gains two optional flags,
`--ceremony-transition <name>` and `--ceremony-tier <reversible|additive|always_operator>`,
written into a `ceremony_state` block; ceremony resume reads the latest tick's
`ceremony_state.transition_index`.

**KTD3 — Git-surface entry point is a local git alias only, never a git hook.** The issue
text says "alias/hook pack"; a real hook (`pre-push`, `post-commit`) fires automatically on a
git event with no operator confirmation step, which directly conflicts with R5 (merge /
PR-open / review-request must stay explicitly confirmed) and with the repo's existing
"never silently mutate GitHub" boundary. `ship_ceremony.py install` writes a **local**
(`--local`, not `--global`) `git config alias.ship '!python3 <abs path>/ship_ceremony.py
run'` — scoped to this repo checkout, never touching global git config — plus `ship_ceremony.py
uninstall` that runs `git config --unset alias.ship`. No repo precedent existed for
git-alias installers (verified: no `git config.*alias` hits outside this issue's own scope) —
this establishes the pattern rather than following one.

**KTD4 — Front-loaded mode reuses `/work`'s existing branch/PR-link, doesn't reinvent it.**
`ship_ceremony.py start` runs immediately after `/work` Phase 1.4's saga mint (so `issue_ref`
and `plan_path` already exist to build the PR body/link) and before Phase 2 unit execution
begins. The scaffold commit is the mint's own saga-tick artifact commit (already produced
today) rather than a synthetic empty commit — no new commit-shape KTD needed.

## Implementation Units

### U1. Transition-table core and reversibility tiers

**Goal:** the ordered, resumable transition table plus the local `CeremonyTier` registry (KTD1), named distinctly from `reversibility_certificate.Tier` to avoid symbol collision where both modules are imported (e.g. in tests).

**Requirements:** R1, R2, R3, KTD1, KTD2.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (new); `tests/test_ship_ceremony.py` (new).

**Approach:** `TRANSITIONS = ("commit", "open_pr", "request_review", "merge",
"checkout_main", "pull", "branch_delete")`, each mapped to an `OpFacts`-shaped tuple `(tier,
runner_fn)`. `run(argv)` resolves the current saga: if `--issue-ref` is passed, call `saga.py
restore --saga-id issue-<N>` directly; otherwise call `saga.py scan` (verified: it lists every
candidate with a `branch` field but has no branch filter of its own) and pick the candidate
whose `branch` matches the current `git rev-parse --abbrev-ref HEAD` — the filtering is
`ship_ceremony.py`'s own responsibility, not a `scan` capability. It then reads
`ceremony_state.transition_index` from its latest tick
(default `0` when absent), executes the next transition, writes the advanced index + tier
back via `saga.py save --ceremony-transition ... --ceremony-tier ...`, and stops (one
transition per invocation — this is what makes resumption trivial: the next invocation just
re-reads state and continues).

**Patterns to follow:** stateless-CLI-rereads-state pattern in `plugins/saga/scripts/saga.py`
and `outcome_store.py`; `OpKind`/`Tier` vocabulary *shape* (not the symbol name) in `reversibility_certificate.py`
(mirrored, not imported — KTD1).

**Test scenarios:**
- Happy path: full ceremony run against a throwaway branch drives all seven transitions in
  order; each tick shows the advancing `transition_index` and a tier consistent with KTD1's
  table.
- Edge: invoking the primitive on a saga already at `transition_index=7` (complete) is a
  no-op that reports "already shipped," not a re-run of `branch_delete`.
- Error path: a transition's underlying `git`/`gh` call fails (e.g. `gh pr create` returns
  non-zero) — state is NOT advanced past the failed transition, and the failure reason is
  surfaced, not swallowed.
- Resume: kill the process after transition 3 (`open_pr`); re-invoke; transitions 1-3 are not
  re-run (no second PR opened), execution continues at transition 4.
- Edge: `saga.py scan` returns more than one candidate whose `branch` matches the current
  branch (e.g. a stale saga from a deleted-and-reused branch name) — the primitive refuses to
  guess and reports the ambiguity (asking for an explicit `--issue-ref`) rather than silently
  picking the newest.

**Verification:** `tests/test_ship_ceremony.py -k full_ceremony_throwaway_branch` and `-k
resume_from_state` pass; a manual throwaway-branch run shows one saga tick per transition
with the expected tier annotations.

### U2. `saga.py save` ceremony-state fields

**Goal:** the two new optional flags and the `ceremony_state` tick block U1 depends on.

**Requirements:** R3, KTD2.

**Dependencies:** none (parallel with U1's design, sequenced before U1's tests can pass).

**Files:** `plugins/saga/scripts/saga.py`; `plugins/saga/references/saga-spec.md` (document
the new field); `tests/test_saga_*.py` (extend existing save/restore round-trip coverage).

**Approach:** add `--ceremony-transition` (one of `TRANSITIONS`) and `--ceremony-tier` (one
of `reversible|additive|always_operator`) to the existing argument parser; on save, merge
`{"transition": ..., "tier": ..., "index": <computed>}` into a `ceremony_state` key in the
tick's frontmatter, computing `index` as the position of `transition` in the fixed
`TRANSITIONS` order (never trust an externally-passed index — recompute it, so a stale caller
can't skip ahead). Restore surfaces `ceremony_state` unchanged from the latest tick.

**Patterns to follow:** existing optional-flag-merges-into-frontmatter pattern already used
for `--pr-refs`, `--rounds-seen` in `saga.py`.

**Test scenarios:**
- Happy path: `save --ceremony-transition open_pr --ceremony-tier reversible` on a restored
  saga produces a tick whose `ceremony_state.index == 1`.
- Edge: omitting both ceremony flags on an ordinary (non-ceremony) `save` call leaves
  `ceremony_state` absent — existing non-ceremony callers are unaffected.
- Error path: an unrecognized `--ceremony-transition` value is rejected by argparse `choices`
  before any write happens.

**Verification:** existing saga save/restore test suite stays green; new cases assert the
`ceremony_state` round-trip.

### U3. Wire `/work` Phase 5.4 to `ship_ceremony.py` (R6)

**Goal:** replace `work/SKILL.md` section 5.4's raw `gh pr create` / `gh pr merge` / cleanup
prose with calls into the primitive, preserving R5's confirmation gates.

**Requirements:** R4(a), R5, R6.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/skills/work/SKILL.md` (section 5.4, and the section 5.4 references
in `plugins/saga/skills/work/references/pr-continuation-loop.md` where it describes
merge-under-confirmation).

**Approach:** section 5.4's "offer to open PR" step becomes "offer to run `ship_ceremony.py
run` through `open_pr` + `request_review`"; the post-approval merge step becomes "offer to
run `ship_ceremony.py run` through `merge` → `checkout_main` → `pull` → `branch_delete`" —
each still gated by the exact same operator-confirmation language already in section 5.4 (no
regression on R5). Update `pr-continuation-loop.md`'s "Merge is a confirmed git op `/work`
owns" section to name the primitive as the mechanism, not a new authority.

**Patterns to follow:** the existing confirm-then-`gh pr merge` prose being replaced, kept
word-for-word except substituting the call target.

**Test scenarios:**
- Integration: a skill-doc drift-guard test (mirroring the existing `test_saga_plugin.py`
  version-string assertions) asserts `work/SKILL.md` contains a reference to
  `ship_ceremony.py` in section 5.4.
- Error path / regression: `grep -nE "git (checkout|pull|branch -d)|gh pr
  (create|merge)" plugins/saga/skills/work/SKILL.md` returns no matches (AC6).

**Verification:** `tests/test_ship_ceremony.py -k skill_doc_no_raw_ceremony_commands`
(new) passes; existing `/work` skill-doc tests stay green.

### U4. Git-surface entry point: `install` / `uninstall` (R4b, KTD3)

**Goal:** the local git alias installer/uninstaller and the `git ship` invocation path.

**Requirements:** R4(b), KTD3.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (adds `install` / `uninstall` /
`run` subcommands); `tests/test_ship_ceremony.py`.

**Approach:** `ship_ceremony.py install` resolves its own absolute path
(`Path(__file__).resolve()`) and runs `git config --local alias.ship '!python3 <path> run'`
from the repo root; `ship_ceremony.py uninstall` runs `git config --local --unset
alias.ship`, tolerating "already absent" as success (idempotent uninstall). `run` (invoked
either directly or via `git ship`) resolves the current saga via the `scan`-then-filter-by-branch
path from U1 (no `--issue-ref` flag needed from the terminal) and executes the next
transition exactly as U1's core does — `run` IS the shared implementation;
`install`/`uninstall` only manage the alias.

**Patterns to follow:** none in-repo (KTD3 notes this is new ground) — model on `git config
--local` semantics directly, no wrapper shell script needed since git aliases support the
`!<shell command>` form.

**Test scenarios:**
- Happy path: `install` in a throwaway repo clone sets `alias.ship` in that clone's local
  git config only (not global); `git ship` on a throwaway branch drives the same transition
  as invoking the script directly (parity, AC4).
- Edge: `uninstall` when no alias is installed exits 0 (idempotent), not an error.
- Edge: `install` when `alias.ship` already exists and points somewhere else (e.g. a
  developer's pre-existing personal alias) refuses to overwrite silently — reports the
  existing value and requires an explicit `--force` to replace it. `install` when the
  existing `alias.ship` already points at this same script is a no-op success (idempotent
  install).
- Integration: after `uninstall`, `git config --local --get alias.ship` fails (no residue,
  AC3).

**Verification:** `tests/test_ship_ceremony.py -k git_surface_entry_point` and `-k
parity_git_surface_vs_work` pass.

### U5. Front-loaded draft-PR mode (`ship_ceremony.py start`, R7, KTD4)

**Goal:** the `/work`-Phase-1 hook that mints the draft PR up front.

**Requirements:** R7, KTD4.

**Dependencies:** U1, U3.

**Files:** `plugins/saga/scripts/ship_ceremony.py` (adds `start` subcommand);
`plugins/saga/skills/work/SKILL.md` (Phase 1.4, invoke `start` right after the saga mint).

**Approach:** `start` pushes the current branch (already created by Phase 1.4's mint) and
opens a draft PR (`gh pr create --draft`) whose body links the plan path already present on
the saga (`plan_path`) — no new plan-link mechanism needed, it reads the field U2/KTD2 already
persists. Records the draft `pr_refs` on the saga immediately (reusing the existing
`pr_refs` tick field, not a new one). The later `open_pr` transition (U1) checks for an
existing draft `pr_refs` entry first and flips it ready (`gh pr ready`) instead of creating a
second PR.

**Patterns to follow:** existing `pr_refs` field semantics already used in section 5.4
(`work/SKILL.md:448`).

**Test scenarios:**
- Happy path: `start` on a fresh mint opens a draft PR whose body contains the plan-doc
  path; the saga's `pr_refs` is populated immediately (not deferred to Phase 5.4).
- Integration: a subsequent full ceremony `run` reaching `open_pr` detects the existing draft
  PR and flips it ready rather than calling `gh pr create` again (assert exactly one PR
  exists for the branch after the full run).

**Verification:** `tests/test_ship_ceremony.py -k front_loaded_draft_pr` passes.

### U6. Release surfaces and journal (mechanical, no behavioral test)

**Goal:** keep plugin metadata and the engineering journal in step with the shipped
behavior, per the repo's per-PR release-surface rule.

**Requirements:** none directly (repo-wide `CLAUDE.md` obligation, not a Gate-E R-ID).

**Dependencies:** U1-U5.

**Files:** `plugins/saga/.claude-plugin/plugin.json` (version bump from `0.53.0`);
`.claude-plugin/marketplace.json` (matching saga entry bump); `plugins/saga/CHANGELOG.md`
(new dated entry); `tests/test_saga_plugin.py` (drift-guard version string);
`docs/engineering-journal/DECISIONS.md` (KTD1-KTD4 as a `{#ship-ceremony-primitive-345}`
entry); `docs/plans/2026-07-04-plugin-fleet-execution-order.md` (tick checklist row 4).

**Approach:** mirror the exact release-surface pattern from the #463 arc (version bump +
CHANGELOG entry + drift-guard test update + DECISIONS entry, all in the same PR).

**Test scenarios:** `Test expectation: none -- mechanical metadata sync, covered by existing
drift-guard version-string tests once updated.`

**Verification:** `tests/test_saga_plugin.py` and the marketplace drift-guard tests pass with
the new version string.

## Scope Boundaries

**Out of scope:**
- Any change to who authorizes merge / PR-open / review-request — those remain explicitly
  operator-confirmed; this issue automates sequencing and bookkeeping only (R5).
- `/qa`'s post-merge advisory routing and `lifecycle_phase` advancement — unchanged; `/work`
  continues not to own deploy or issue-filing.
- Deploy/canary mutation — owned by the `deploy` plugin, untouched here.
- Any new consensus/review protocol — this is a mechanical sequencing primitive, not a
  review-gate change; the existing P0/P1 + staleness gate ahead of PR-ready is unchanged.
- Backfilling the ceremony into the other 7 repos the grounding brief's finding cites — this
  issue ships the primitive in `infiquetra-claude-plugins` only.
- Real git hooks (`pre-push`, `post-commit`) as an alternative entry point — explicitly
  rejected in KTD3; only a git alias is in scope.

**Deferred to follow-up work:**
- Propagating the installed git alias to the other 7 repos, once this primitive is proven
  here (noted as future work, not tracked by an issue yet).

## Recommended Executor Profile (carried from Gate E draft)

Model: sonnet. Effort: high. Backend: team-execution (multi-file: new script + skill-doc
rewrite + saga-schema addition + new install/uninstall surface — consensus-worthy fan-out,
but a well-scoped mechanical state-machine build, not opus-tier judgment).
