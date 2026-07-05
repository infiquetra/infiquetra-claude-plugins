---
title: ship_ceremony.py open_pr push fix (front-loaded/existing-PR path) — issue #478
type: fix
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/478
---

# ship_ceremony.py open_pr push fix (front-loaded/existing-PR path) — issue #478

## Summary

`ship_ceremony.py`'s `open_pr` transition, on the front-loaded/existing-PR path, flips a
draft PR ready via `gh pr ready <N>` but never pushes the local commits accumulated since
`start()` opened that draft. This plan pushes the branch before flipping ready, so CI
validates the real HEAD instead of a stale one. Two units: the code fix + regression tests
(U1), and the saga release-surface bump (U2).

## Problem Frame

The front-loaded `start` mode (issue #345) pushes the branch **once** and opens a draft PR
immediately after the saga mint — *before* any implementation work happens
(`ship_ceremony.py:408-434`). Critically, `start()` records `ceremony_transition="commit"`
in that same tick (`ship_ceremony.py:430-433`), which means the next `run` invocation skips
the `commit` transition entirely and lands on `open_pr`. The `commit` runner
(`_do_commit`, `ship_ceremony.py:234-241`) is the *only* place a push happens in this flow —
and it never executes.

So every commit made between `start()` and the `open_pr` flip sits unpushed. `_do_open_pr`'s
existing-PR branch (`ship_ceremony.py:249-253`) runs only `gh pr ready <N>` and returns — no
push. During #429's `/work` session, 8 commits of real implementation sat on the local branch
while CI validated only the `start()`-time HEAD (the plan/doc-review docs commit), silently
green. It was caught by manually diffing `origin/<branch>` against local `HEAD` before merge,
not by the ceremony — exactly the manual-ritual mistake this "resumable, guarded ship
primitive" exists to eliminate.

Post-`open_pr` commits (code-review fixes in round N) are *not* part of this gap: `/work`'s
round-N PR continuation loop already re-pushes them
(`plugins/saga/skills/work/references/pr-continuation-loop.md:33,35`), and the staleness gate
re-runs `/code-review` when HEAD moves past the reviewed SHA (same file, line 36). The single
unpushed window is `start()` → `open_pr`.

## Requirements

R1. `_do_open_pr`'s existing-PR (front-loaded) branch MUST push all pending local commits to
    the tracked remote branch **before** flipping the PR ready, so CI validates the current
    HEAD rather than the `start()`-time HEAD.

R2. The fix MUST NOT alter `start()`'s push behavior (already correct on first invocation) or
    the from-scratch fresh-PR `open_pr` path (which relies on `_do_commit` having pushed first).

R3. The push MUST be idempotent — a no-op ("Everything up-to-date", exit 0) when local ==
    remote — so re-running `open_pr`, or running it with no new commits, never fails.

R4. A transition-runner test MUST prove the tracked remote branch ref advances to local HEAD
    after `open_pr` on the existing-PR path with a deliberately-unpushed local commit; the
    existing full-ceremony, front-loaded, and transition-failure tests MUST still pass
    unchanged.

## Key Technical Decisions

**KTD1 — Extract a `_push_branch` helper; call it from both push sites.**

Extract `_push_branch(repo_root, *, runner)` emitting `git push -u origin <current-branch>`,
and call it from `_do_commit` (replacing its inline push) and from `_do_open_pr`'s existing-PR
branch. Rationale: one source for the push argv, no drift between the two sites, and the
extraction is behavior-preserving for `_do_commit` — the emitted argv stays
`["git", "push", "-u", "origin", <branch>]`, so
`test_transition_failure_does_not_advance_state`'s `fail_prefix=["git","push","-u","origin"]`
match still fires. `-u` is retained (harmless idempotent upstream re-set; `start()` already set
it on the front-loaded path).

**KTD2 — Do NOT push at `merge`, despite the issue's "ideally merge" hint.**

The issue suggests `merge`/`request_review` might need the same guard. They do not, and a
merge-time push is actively harmful:

- `/work`'s round-N loop already re-pushes post-`open_pr` commits (pr-continuation-loop.md:33,
  35), so U1 closes the only unpushed window (`start()` → `open_pr`).
- Pushing at `merge` would reset required CI checks to *pending*; `_do_merge`'s
  `gh pr merge <N> --squash` (`ship_ceremony.py:289-293`, no `--auto`) would then fail on the
  now-pending checks — or, on a non-gated repo, merge unvalidated code, which is the very bug
  class this fixes.
- Merging on a review that predates HEAD is already prevented by `/work`'s staleness gate
  (pr-continuation-loop.md:36).

Remote-vs-local integrity *at merge* is `/work`'s responsibility (its round-N re-push +
staleness gate), not the ceremony's. `_do_merge` stays unchanged. `request_review` needs no
push — it is a deliberate no-op since #477.

## Implementation Units

### U1. Push accumulated commits on the front-loaded `open_pr` path

Close the reported gap and prove it with a regression test.

**Files:** `plugins/saga/scripts/ship_ceremony.py`, `tests/test_ship_ceremony.py`.

**Change:** Add `_push_branch(repo_root, *, runner)` that resolves the current branch and runs
`git push -u origin <branch>` via `_run`. Rewrite `_do_commit` to call it. In `_do_open_pr`,
inside the `if existing:` branch, call `_push_branch(...)` **before** `_run(["gh","pr","ready",
pr_number], ...)`.

**Test scenarios** (`tests/test_ship_ceremony.py`, using the `ceremony_repo` fixture + `FakeGh`):

- `test_open_pr_pushes_pending_commits_on_existing_pr_path` — call `start()` (pushes scaffold,
  opens draft #1, records `ceremony_transition="commit"`); write + commit a new local file so
  local HEAD is one commit ahead of `origin/feat/pf-throwaway-345`; assert the origin ref is
  *behind* HEAD (the pre-fix bug state); run the `open_pr` transition; assert
  `git rev-parse origin/feat/pf-throwaway-345` equals `git rev-parse HEAD` and the PR is no
  longer draft. This is issue #478's second acceptance test made concrete.
- Regression guard: `test_front_loaded_draft_pr`, `test_full_ceremony_throwaway_branch`, and
  `test_transition_failure_does_not_advance_state` must pass unchanged (the extraction is
  behavior-preserving; the new push is an idempotent no-op when local == remote).

### U2. Release-surface bump (saga 0.54.2 → 0.54.3)

Mechanical parity update in the same PR (CLAUDE.md release-surface rule; CI's #429 diff-guard
hard-blocks a plugin code change with no matching bump).

**Files:** `plugins/saga/.claude-plugin/plugin.json` (`0.54.2` → `0.54.3`);
`plugins/saga/CHANGELOG.md` (new `## [0.54.3] - 2026-07-05` Fix entry citing #478);
`.claude-plugin/marketplace.json` (regenerated, never hand-edited);
`tests/test_saga_plugin.py` (version-literal `0.54.2` → `0.54.3`).

**Command:** `python3 scripts/sync_marketplace.py` regenerates `marketplace.json` from the
bumped `plugin.json`.

**Test expectation:** none — mechanical release-surface parity, guarded by
`scripts/check_release_surface_parity.py`, `tools/release_surface_diff_guard.py`, and the
`test_saga_plugin.py` version-literal assertion.

## Scope Boundaries

**Out of scope:**

- Any push or guard at the `merge` transition (KTD2) — redundant with `/work`'s round-N
  re-push and staleness gate, and harmful to CI gating.
- `request_review` — a deliberate no-op since #477; nothing to push.
- The from-scratch fresh-PR `open_pr` path (`ship_ceremony.py:254-275`) — it relies on
  `_do_commit` having pushed and is unaffected.
- `start()`'s push behavior and the #345 dual-entry front-loaded architecture.
- `/work`'s round-N push behavior — already correct.

**Deferred to follow-up work:** none required. A belt-and-suspenders `/work`-side pre-merge
`origin/<branch> == HEAD` assertion was considered and rejected — the grounded evidence
(round-N re-push + staleness gate) makes it redundant; not filed.

## Verification

```bash
uv run pytest tests/test_ship_ceremony.py -k open_pr -v
uv run pytest tests/test_ship_ceremony.py -q
uv run pytest && uv run ruff check . && uv run ruff format --check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
python3 scripts/sync_marketplace.py --check
python3 scripts/check_release_surface_parity.py
python3 tools/release_surface_diff_guard.py --base-ref origin/main
```

## Closeout (executed by `/work`)

- Release surfaces bumped in the same PR (U2): `plugin.json`, `marketplace.json`, `CHANGELOG.md`,
  version-literal test.
- Tick issue #478's row in
  `docs/plans/2026-07-04-plugin-fleet-execution-order.md` "Defects found during execution"
  (`[ ]` → `[x]`) in the same PR, citing the PR/commit.
- Engineering-journal capture in the same commit if the work yields a durable learning/decision
  (KTD1/KTD2 → `DECISIONS.md`).
- Board status → `Done` at ship if the mission-control mapping allows (repo is currently
  unmapped in `project-mappings.json`; #477 shipped with the board field left empty — do not
  block merge on it).
