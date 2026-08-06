---
title: Work session — U2 re-key teardown dispositions onto the worktree registry (#679)
date: 2026-08-05
issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/679
plan: docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md
doc_review: docs/reviews/doc-review-issue-677-2026-07-30.md
branch: feat/679-u2-unwind-teardown-dispositions
commit: de6a161d
final_commit: 1f206c42
pull_request: https://github.com/infiquetra/infiquetra-claude-plugins/pull/698
merge_commit: 415be251
saga: issue-679
orchestration: inline
---

# Work session — #679 U2 re-key teardown dispositions onto the worktree registry

## What this changed, in one paragraph

The #358 non-skippable team-run teardown contract enumerated its resources from the
fleet lease authority's lease list and acted on them with lease-indexed adapters
(release, process-stop, resident-stop, sweep-with-reaper). Unit U2 of the lease-broker
retirement (#677) strips all of it: teardown now enumerates the per-outcome **worktree
registries** (`<git-common-dir>/saga-outcomes/*/worktrees.json`) cross-checked with
`git worktree list` via `outcome_worktrees.live_worktrees`, and the sweep REPORTS
dispositions re-keyed on worktree path. It removes nothing from disk — per KTD12 it
never did (no production caller ever injected a reaper) — and the reaper seam is now
structurally gone, pinned by a regression sentinel.

## The census has no ownership axis (KTD1)

The lease list was owner-keyed (`owner_id == team_run_id`); the registry is not —
entries belong to outcome subplots. A run's teardown therefore reports the worktree
state of the whole repository, and `open_count` is re-defined to "census entries not
yet at a final disposition" so the completion gate stays reachable once the registry
stops shrinking on its own. The plan's word "re-key" understated this: a re-key plus a
lost axis. LEARNINGS `{#census-rekey-loses-the-ownership-axis}`.

## The five R5c rows converge on two branches (KTD3)

| R5c row | Re-keyed successor |
|---|---|
| `:1255` already-absent / lease-already-released | git-unlisted branch |
| `:1263` released / (reaped) | **deleted with the reaper seam** — `released` keeps its vocabulary slot, loses its producer |
| `:1269` retained / sweep:{reason} | git-listed branch |
| `:1272` already-absent / released-by-sweep | git-unlisted branch |
| `:1277` retained / not-a-sweep-candidate | git-listed branch |

- git-listed → `retained` / `worktree-listed` (no evidence refs, as before).
- git-unlisted → `already-absent` / `worktree-not-listed` with evidence
  `worktree:path-absent:<outcome-id>:<subplot-id>`. **`already-absent` changed
  meaning**: "git no longer lists this worktree", not "the lease head is gone". Both
  redefinitions named in the saga CHANGELOG under `Changed` (R5c consequence 1).

## Files modified

| File | Change |
|---|---|
| `plugins/saga/scripts/team_teardown.py` | 13 broker sites removed; census-based `DecisionInput`/`project`/driver; report-only sweep; deleted `default_broker`, `_current_head`, resident/process adapters, `register_subprocess`, `authorize_resident_stop`; `close_generation` vestigial constant 1; `repository_root_sha256` from the ledger's common dir; `recover --expired-only` re-keyed onto git-listed worktrees |
| `plugins/saga/hooks/team_teardown_hook.py` | Broker-free; threads `repo_root` into `read_decision_input`/`recover`; census-unavailable degrade replaces the broker-unavailable degrade |
| `tests/test_team_teardown.py` | Rewritten — 63 tests: event family, census + projection, terminal driver, the five R5c rows re-keyed, recovery, concurrency, guard lifecycle, CLI, disk-removal sentinel; distinct `sys.modules` key (U1's collision lesson applied up front) |
| `tests/test_teardown_ci_invariant.py` | Leak invariant re-keyed to registry-explained worktrees; source conformance re-keyed (worktree-add needs `outcome_worktrees.register`; subprocess rule retired) |
| `tests/test_saga_hooks.py` | Three teardown hook tests re-keyed (registry fixtures, git-listed skip) |
| `tests/test_team_execution_plugin.py` | Doc-contract test drops `term-then-kill`/`confirmed-stalled` (retired with their mechanisms); version pin 2.24.0 |
| `plugins/team-execution/.../references/teardown-reclamation.md` | Rewritten for the broker-free contract (R11) |
| `plugins/saga/references/teardown-consumer-sites.md` | Inventory rewritten: registry census columns, report-only seams (R11) |
| `docs/engineering-journal/DECISIONS.md` | `{#u2-rekeys-teardown-onto-worktree-registry-679}` KTD1–KTD6 |
| `docs/engineering-journal/LEARNINGS.md` | `{#census-rekey-loses-the-ownership-axis}` |
| `docs/engineering-journal/QUEUED.md` | `{#teardown-eviction-gate-retired-needs-u6-story}` |
| Release surfaces | saga 0.126.0 → 0.127.0 and team-execution 2.23.0 → 2.24.0 (plugin.json, regenerated marketplace.json, CHANGELOGs, version-pin tests) under the #429 diff guard (KTD6) |

## Deliberately not done

- **No registry mutation anywhere.** Teardown enumerates to report; deregistering stale
  entries is the outcome lifecycle's ownership (`stale_worktree_debits` names the
  harvester the sole mutation owner). Stale entries accumulate until manual
  reclamation — U3's documented procedure.
- **No eviction-gate replacement.** `authorize_resident_stop` retired with its trusted
  inputs; U6 (#683) decides whether eviction returns. QUEUED.
- **No `released` producer.** Its only source was the reap branch; manufacturing one
  would need disk removal (forbidden) or registry mutation (wrong owner).
- **U4/U7 re-notes still pending** (U4 per U1's KTD4; U7's R8 table now reads "on top
  of the per-unit versions" — this PR moved two more surfaces under it).

## Checks run

| Gate | Result |
|---|---|
| Full suite `uv run python -m pytest -q` | **5527 passed, 1 skipped, 0 failed** (5528 collected; baseline pre-U2: 5585 — net −57 retired broker-era tests) |
| `uv run pytest tests/test_team_teardown.py tests/test_teardown_ci_invariant.py tests/test_saga_hooks.py` | 63 + 13 + 39, all pass |
| `uv run ruff check . && uv run ruff format --check .` | clean (434 files) |
| `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | clean (268 files) |
| `uv run bandit -ll` | 0 medium+ on changed files |
| `python3 scripts/lint_journal_order.py --base-ref origin/main` | 0 violations |
| `python3 scripts/check_release_surface_parity.py` | all plugins in parity |
| `python3 tools/release_surface_diff_guard.py --base-ref origin/main` | all changed plugins bumped |
| Acceptance grep `lease_broker\|lease_authority\|fleet_leases\|_current_head` on `team_teardown.py` | no matches |
| Acceptance grep `broker\|default_broker` on the hook | no matches |
| Sentinel `tests/test_agy_run_lease.py` | unmodified (`git diff --exit-code`), 8 passed |

## Collected-count delta

Pre-U2 baseline: 5585 collected (5584 passed + 1 skipped). U2 retires 57 broker-era
tests (test_team_teardown.py 102 → 50 functions, CI invariant 14 → 13; hook and
team-execution files replaced/kept 1:1) and adds the re-keyed coverage: 5528 collected.

## Surprise during execution

The CI diff guard flagged **team-execution**, not just saga: the #429 guard does not
exempt `skills/**/references/**` — agent-facing instruction IS behavior — so the R11
rewrite of the teardown reference moved team-execution's release surface too
(2.23.0 → 2.24.0, second commit). Also: the team-execution doc-contract test pinned
two lease-era strings (`term-then-kill`, `confirmed-stalled`) that retired with their
mechanisms — the U1 file-disjoint-but-API-coupled lesson recurring in the test suite.

## Next step

Merge, then the campaign's next pulls are U3 (#680, dispatch/worktree routing — the
largest unit, holds the real worktree-reclamation loss) or U2-adjacent U5 prep; re-note
U4 (#681) before pulling it (its outcome.py row shrank with U1).
