# Outcome worktree reclamation (operator path)

How abandoned sub-outcome worktrees get reclaimed now that the fleet lease broker is gone (#677/U3).

## What changed

`plugins/saga/scripts/outcome_worktrees.py` routes each autonomous sub-outcome into one durable,
named, owner-tagged git worktree under `.saga-worktrees/<outcome_id>/<subplot_id>/`. Before #677,
the lease broker's sweep — `lease_authority.sweep(worktree_reaper=...)` — was the only **automatic**
reaper that crossed run boundaries: it found worktrees whose owning runs were gone and removed them.
That sweep was retired with the broker. What survives unchanged:

- **Terminal reaping.** A sub-outcome that reaches any terminal state is reaped by
  `harvest_worktrees` on the next advance pass of the same outcome (`reap_worktree` → deregister).
- **Path-absent settlement.** A registered entry whose worktree git no longer lists is settled by
  the next harvest pass on its own — git is the liveness source of truth (the U6 lesson).
- **Prune-path reaping.** `outcome_decompose.py prune` and ship teardown still reap the worktrees
  of the sub-outcomes they remove, authority-free.

What is **lost** is the cross-run sweep: if a run is abandoned mid-flight (crash, operator kill,
machine loss) with live dispatched worktrees, nothing automatic removes them. They accumulate until
reclaimed by hand — this procedure. The loss is recorded in
`docs/engineering-journal/DECISIONS.md` with its revisit-when condition.

## Step 1 — Inventory (report-only)

```bash
python3 plugins/saga/scripts/outcome_worktrees.py --reclaim-list --repo-root /path/to/repo
```

`--reclaim-list` prints a JSON inventory of every outcome worktree candidate under the repository's
git-common-dir (`saga-outcomes/*/worktrees.json` registries plus anything on disk under
`.saga-worktrees/`). It never removes anything. Each candidate carries `outcome_id`, `subplot_id`,
`path`, the `registry` file that claims it (empty when none does), and one of three states:

| State | Meaning | Action |
|---|---|---|
| `live` | Git still lists the path | Reclaiming abandons that sub-outcome's in-flight work — see the R32 note below before removing |
| `path-absent` | Registered, but git no longer lists the path | Nothing to remove; the owning outcome's next harvest pass settles the entry on its own |
| `unregistered` | On disk under `.saga-worktrees/` but claimed by no registry | A stranded leftover; safe to remove after confirming no run still needs it |

## Step 2 — Remove

For each candidate you choose to reclaim:

```bash
git worktree remove --force <path>     # the candidate's "path" field
git worktree prune                     # drop git's own stale bookkeeping
```

`--force` is required: abandoned worktrees normally carry untracked build state. Remove the on-disk
directory only if git no longer knows it (an `unregistered` candidate may already be detached from
git's bookkeeping); otherwise let `git worktree remove` do the removal so git's records stay
consistent.

No registry surgery is needed:

- Removing a **`live`** worktree is detected out-of-band on the next harvest pass — the entry's
  sub-outcome reaches the **R32 worktree-removed terminal** (`rejected`, sticky, cascades to its
  dependents via `blocked_subtree`) exactly as if the worktree had vanished for any other reason.
  That is the designed consequence, not corruption: the working state is gone, so the node must not
  silently retry.
- A **`path-absent`** entry settles itself; removing nothing is the correct action.
- An **`unregistered`** directory has no registry entry by definition.

## When to run this

There is no schedule and nothing wires this inventory to any lifecycle tick — that is deliberate.
Run it when `.saga-worktrees/` grows past what live outcomes explain, after a crash-heavy session,
or when disk pressure says so. The 88-worktree manual cleanup that preceded this procedure is the
precedent for the shape: inventory first, remove explicitly, never opportunistically.

## Non-goals

- Do not build an automatic reaper over `reclaim_candidates` — wiring it to a tick is a scope
  reversal of #677's accepted loss and needs its own decision record.
- Do not remove a `live` worktree whose sub-outcome is still dispatching unless you accept the R32
  `rejected` cascade for that subtree; the outcome will not resume in a fresh worktree.
