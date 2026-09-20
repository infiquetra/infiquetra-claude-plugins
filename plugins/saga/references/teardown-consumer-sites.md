# Teardown consumer and spawn-site inventory (#358, re-keyed by #677/U2)

The terminal reclamation mechanism exists only at `plugins/saga/scripts/team_teardown.py`,
composing the per-outcome **worktree registries**
(`<git-common-dir>/saga-outcomes/*/worktrees.json`) and the #351 run-fact ledger
(`plugins/saga/scripts/run_ledger.py`). Every production site below reaches it through
the plugin boundary; no second reclamation store exists.

#677/U2 retired the fleet lease authority from this contract. Teardown enumerates
worktrees via `outcome_worktrees.live_worktrees` (registry cross-checked with
`git worktree list`) and only ever REPORTS their dispositions — it removes nothing from
disk (KTD12: it never did; no production caller ever injected a reaper). The
lease-era seams — spawn-time registration of residents and subprocesses, admission
closing, lease release, and the sweep reaper — are gone from this surface.

| boundary | run-open | worktree census | terminal driver | action owner | disposition | recovery | proof |
|---|---|---|---|---|---|---|---|
| Team Phase B0 | file-disjoint run-open (no lease broker) | n/a | n/a | root session | n/a | n/a | `run-opened` fact with session + repository identity digest |
| Outcome worktree provisioning | outcome dispatch identity | registry entry written by `outcome_worktrees.register` | n/a | outcome coordinator | reported by B8, never removed | out-of-band removal + manual reclamation (#677) | registry entry + `git worktree list` |
| Every observed terminal (success / hard-fail / operator-abort / andon) | existing run | every registered worktree in this repository | `team_teardown.reclaim_all` | root session | `retained` (git lists it) / `already-absent` (git no longer lists it — the re-defined meaning) | armed on retained/failed | `teardown-intent` … `teardown-complete` chain |
| SessionEnd | existing run | n/a | `request` only (no actions) | Saga hook (5 s) | none | later pass | `teardown-intent` fact — request evidence, never closure |
| SessionStart startup/resume | existing runs | `live_worktrees` per outcome registry | `recover --expired-only --max-actions 4` | Saga hook (15 s) | report-only, same adapters | this is the recovery seam; skips runs with git-listed worktrees | `recovery-observation` + absence evidence |
| Explicit operator CLI | existing runs | same census | `status` / `request` / `reclaim-all` / `recover` | operator | report-only | bounded batches on request | `team_teardown.v1` projection |

Rules the conformance tests enforce:

- A source that adds a worktree (`git worktree add`) without naming the registry
  registration seam (`outcome_worktrees.register`) is a leak-by-construction and fails
  source conformance. (The subprocess registration rule retired with the lease
  authority — spawn-time subprocess identity is an accepted loss of the retirement.)
- A terminal branch that asserts completion without the B8 driver (`reclaim-all` /
  `reclaim_all`) fails source conformance — B7 wording is draft-only.
- CI proves the leak invariant inside a temporary repository fixture only; it never
  enumerates, inspects, or deletes the developer's global worktree set. A live census is
  an attended dry-run action; teardown has no removal capability to attend.
