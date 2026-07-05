---
title: saga.py branch field refreshes on every save (not just first) — issue #480
type: fix
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/480
---

# saga.py branch field refreshes on every save (not just first) — issue #480

## Summary

`saga.py`'s `save()` only auto-derives the `branch` field from live git state on a saga's
*first-ever* save (`if not merged.branch`), so a saga minted by `/plan` while on `main` — before
its work branch exists — carries `branch="main"` permanently, even after `/work` re-saves it on
the work branch. This plan makes `branch` refresh from live git on **every** save, with one guard
beyond the empty-read check: a save made back on the default branch (`main`/`master`) must not
overwrite an already-recorded real work branch — otherwise `ship_ceremony.py`'s own `checkout_main`
progress-save would re-clobber it right before `branch_delete`. One code+test unit (U1) and the
saga release-surface bump (U2).

> **Revision (2026-07-05, during `/work`).** The original plan chose *pure* live-git-wins (drop the
> first-save-only guard outright). `/work`'s test gate caught that this breaks two
> `test_ship_ceremony.py` tests: the ceremony records progress via `saga.py save` after every
> transition, so a save after `checkout_main` resets `branch` to `main`. KTD1 and U1 below reflect
> the corrected, ceremony-safe design (protected refresh). This is a rare case where the plan's core
> KTD was wrong and the test gate — not review — was the thing that caught it.

## Problem Frame

`save()` captures git state and applies it only when the field is still empty
(`plugins/saga/scripts/saga.py:746-752`):

```python
git = current_git_state(root, runner=runner)
if not merged.branch and git["branch"]:
    merged = _replace(merged, branch=git["branch"])
if not merged.head_sha and git["head"]:
    merged = _replace(merged, head_sha=git["head"])
if not merged.last_commit_sha and git["last_commit"]:
    merged = _replace(merged, last_commit_sha=git["last_commit"])
```

The `if not merged.<field>` guard fires only on the first save (when the dataclass default is
still `""`). Every later save runs through `_merge`'s scalar carry-forward
(`saga.py:613-617`) — an incoming `Saga` with `branch=""` (the CLI never sets it; there is no
`--branch` flag, confirmed at `saga.py:1341-1345`) inherits the prior tick's value — so the
first-captured branch is frozen for the saga's entire life.

The common lifecycle triggers this every time: `/plan` mints the saga on `main` (locking
`branch="main"`), then `/work` *advances the same saga id* on the work branch. `work/SKILL.md:151`
explicitly instructs "**Save the saga while on the work branch** … so the cached `branch`" is
correct — but that save carries `main` forward and the instruction silently does nothing.

Downstream impact, both observed and latent:

- **Observed:** `ship_ceremony.py`'s `_do_branch_delete` (`ship_ceremony.py:322-331`, guard at
  `:325-328`) reads the stored `saga.branch` and refuses to delete `"main"` (a correct safety
  guard). It fired and
  refused during #477 *and* #478's ship ceremonies, forcing manual branch cleanup both times.
  No corruption — the guard did its job on bad input.
- **Latent:** `/code-review`'s branch-match fallback for finding the work-thread saga
  (cited in `work/SKILL.md:151,181`) relies on the same stored `branch`; it is silently
  unreliable for any saga minted on `main`.

Crucially, the ceremony **does** re-save the saga: `ship_ceremony.run` calls
`saga.py save --ceremony-transition <T>` after every transition (`ship_ceremony.py:377`) to record
progress. So `branch_delete` reads a stored field last written by the ceremony's *own*
post-`checkout_main` progress-save — meaning a naive live-git refresh would rewrite `branch` to
`main` at exactly the wrong moment (proven by two `test_ship_ceremony.py` failures under the first
attempt). The fix must therefore refresh on `/work`'s work-branch save yet **decline to downgrade**
a recorded work branch when a later save lands back on `main`. Because `_do_checkout_main` hard-codes
`git checkout main`, "the default branch" is concretely `main` (with `master` as a courtesy), so the
protection mirrors the ceremony's own constant.

## Requirements

R1. A saga's `branch` field MUST reflect the actual current git branch after **any** save, not
    only the first — so `/work`'s save on the work branch overwrites a `main` captured at
    `/plan` mint time. (Issue acceptance criterion 1.)

R2. A save made where `git branch --show-current` returns empty (detached HEAD, mid-rebase, or
    git unavailable) MUST NOT clobber a previously-stored branch — the prior value carries
    forward. (Safety invariant preserved by keeping the non-empty guard.)

R3. `_do_branch_delete`'s existing safety guard (refuse on empty/`"main"`) MUST be left intact;
    this fix removes the *bad input* that tripped it, not the guard. (Issue acceptance
    criterion 3.)

R4. The regression MUST be covered in `tests/test_saga_saga.py` (where `save()`'s git-state
    merge is already tested). (Issue acceptance criterion 2.)

R5. A save made **on the default branch** (`main`/`master`) MUST NOT overwrite a `branch` that
    already holds a real (non-default) work branch — otherwise `ship_ceremony.py`'s `checkout_main`
    progress-save erases the branch `branch_delete` still needs. (Discovered via `/work`'s test
    gate; guards the two `test_ship_ceremony.py` ceremony tests.)

## Key Technical Decisions

**KTD1: Refresh `branch` from live git on every save, but never let a save on the default branch
overwrite an already-recorded real work branch ("protected refresh") — chosen over both *pure*
live-git-wins and an explicit `--branch` CLI flag.**
The issue frames the fix as live-git-wins **or** an explicit `--branch` override. An auto-refresh
is preferable: `/work` already re-saves on the work branch (`work/SKILL.md:151`), so refreshing
makes that existing instruction true with **zero caller changes** and no new CLI surface, whereas a
flag would require every caller to remember it. But *pure* live-git-wins (this plan's first draft)
is broken: `ship_ceremony.run` records progress via `saga.py save` after every transition, so the
save after `checkout_main` resets `branch` to `main` right before `branch_delete` — the `/work` test
gate proved this with two `test_ship_ceremony.py` failures. The fix keeps the auto-refresh but adds
a downgrade guard: when the live branch is a default branch (`main`/`master`) *and* a real work
branch is already stored, the save leaves `branch` untouched. The empty-read guard is also retained
so a detached-HEAD / no-git read (`""`) never wipes a stored value (R2). The `main`/`master` set is
not arbitrary — `_do_checkout_main` hard-codes `git checkout main`, so the guard mirrors the
ceremony's own constant.

**KTD2: Scope the behavior change to `branch` only; leave `head_sha` and `last_commit_sha` on
first-save-only capture as a Deferred Follow-Up.**
The two sibling fields at `saga.py:749-752` share the identical `if not merged.<field>` pattern
and the identical staleness symptom. The issue explicitly "scopes to `branch` specifically" and
defers them, and the operating instruction for this campaign is to keep scope tight to the named
issue. A consumer audit done during planning shows refreshing them would be safe and probably
beneficial (`head_sha` → `status_card.py:307`, a display-only CI reference that would then track
the latest commit; `last_commit_sha` → no behavior-gating consumer, set only in
`scaffold_checkpoint.py:81`), so a follow-up is a one-line-each change with the safety already
established. A short code comment marks the asymmetry and cites this decision so the review gate
reads it as deliberate, not an oversight.

## Implementation Units

### U1 — Refresh `branch` on every save + regression tests

Feature-bearing. Add a module constant `_DEFAULT_BRANCHES = frozenset({"main", "master"})`, then in
`plugins/saga/scripts/saga.py` `save()` (refresh block `:746-752`) replace the first-save-only
`branch` guard with a protected refresh:

```python
live_branch = git["branch"]
downgrades_work_branch = (
    live_branch in _DEFAULT_BRANCHES
    and bool(merged.branch)
    and merged.branch not in _DEFAULT_BRANCHES
)
if live_branch and not downgrades_work_branch:
    merged = _replace(merged, branch=live_branch)
if not merged.head_sha and git["head"]:
    merged = _replace(merged, head_sha=git["head"])
if not merged.last_commit_sha and git["last_commit"]:
    merged = _replace(merged, last_commit_sha=git["last_commit"])
```

`head_sha`/`last_commit_sha` keep first-save-only capture (KTD2 deferral); a block comment on the
refresh explains both the live-git tracking and the downgrade guard.

Test scenarios — add to `tests/test_saga_saga.py`, following the existing
`test_save_captures_git_state_from_runner` fixture idiom (a `fake_git` runner returning
per-subcommand stdout, injected via `_set_runner`):

- **`test_save_refreshes_branch_on_later_save`** — save once with the runner reporting branch A
  (asserts A captured), then re-save with the runner reporting branch B, and assert
  `restore(...).branch == "B"` (the *new* branch, proving the first-save value is not frozen).
  This is the direct R1 regression and the exact scenario in the issue.
- **`test_save_empty_branch_does_not_clobber_stored_branch`** — save with a runner reporting a
  real branch, then re-save with a runner whose `--show-current` returns `""` (detached HEAD),
  and assert the stored branch is unchanged (carry-forward preserved). Covers R2.
- **`test_save_on_default_branch_preserves_stored_work_branch`** — record a real work branch, then
  re-save with the runner reporting `main`, and assert the stored branch is unchanged. Covers R5 —
  the ceremony's `checkout_main` progress-save must not downgrade the work branch. This is the
  regression the first draft missed.

Test expectation: the three scenarios above, plus the full `test_ship_ceremony.py` suite (30
tests) staying green — the end-to-end proof the protected refresh is ceremony-safe.

### U2 — Release-surface bump (saga 0.54.3 → 0.54.4)

Non-feature. Patch bump across the tri-lock:

- `plugins/saga/.claude-plugin/plugin.json` — `0.54.3` → `0.54.4`.
- `plugins/saga/CHANGELOG.md` — new `## [0.54.4] - 2026-07-05` entry with a Fix bullet citing
  #480 (branch refreshes on every save; canonical `## [X.Y.Z] - YYYY-MM-DD` heading grammar).
- `.claude-plugin/marketplace.json` — regenerate via `python3 scripts/sync_marketplace.py`
  (single-source generator; do not hand-edit).
- `tests/test_saga_plugin.py` — bump the saga version literal assertion to `0.54.4`.

Test expectation: the version-literal parity assertion in `tests/test_saga_plugin.py` plus
`check_release_surface_parity.py` / `release_surface_diff_guard.py --base-ref origin/main`.

## Scope Boundaries

**Out of scope:**

- Modifying `_do_branch_delete`'s guard (R3 — it behaved correctly on bad input).
- Adding a `--branch` CLI flag (KTD1 chose protected auto-refresh; no current caller needs to
  record a branch different from its checkout).
- Refreshing `head_sha` / `last_commit_sha` (KTD2 — Deferred Follow-Up below).

**Deferred Follow-Up (not a non-goal — a scoped next step):** `head_sha` and `last_commit_sha`
share the identical first-save-only pattern at `saga.py:749-752`. Planning-time consumer audit
established that refreshing both is safe (`head_sha` → `status_card.py:307` display-only CI ref;
`last_commit_sha` → no behavior-gating consumer). A follow-up issue can flip both with the same
one-line-each change; the safety analysis is already done here.

## Verification

- `uv run pytest tests/ -k saga -q` — the issue's named check; the two new U1 scenarios pass and
  the existing `test_save_captures_git_state_from_runner` still passes (first-save capture is
  unchanged).
- `uv run pytest` — full suite green (no test depends on `branch` carrying forward across a
  git-branch change; confirmed the only `.branch ==` assertion is the single-save first-capture
  case).
- `uv run ruff check .` · `ruff format --check .` · `uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports`.
- `python3 scripts/sync_marketplace.py` · `python3 scripts/check_release_surface_parity.py` ·
  `python3 tools/release_surface_diff_guard.py --base-ref origin/main`.
- Programmatic `/code-review` at the work-to-PR boundary.

## Closeout

- Tick #480's row in `docs/plans/2026-07-04-plugin-fleet-execution-order.md` with the PR /
  squash SHA.
- Close #480 with the merged-PR reference (do not rely on the doc tick alone — the #477 miss
  showed the tick and the issue-close are separate closeout artifacts).
- File (or note) the `head_sha`/`last_commit_sha` follow-up per KTD2.
