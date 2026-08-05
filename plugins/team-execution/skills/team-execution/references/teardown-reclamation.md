# Teardown and Reclamation Protocol (#358, re-keyed by #677/U2)

The executable contract behind `Step B8: Terminal Teardown and Reclamation`. One
enumeration source (the per-outcome **worktree registries**,
`<git-common-dir>/saga-outcomes/*/worktrees.json`, cross-checked with
`git worktree list`), one historical fact stream (the #351 hash-chained `run_fact.v1`
ledger, `kind=teardown`), and one derived projection (`team_teardown.v1`). There is no
second registry, mutable status file, TTL clock, heartbeat store, or reaper decision
engine — and **teardown removes nothing from disk**: it reports dispositions. Worktree
removal was never teardown's job (no production caller ever injected a reaper), and the
lease authority that once carried the reap branch is retired.

## Run identity

- `lease_protocol.py open-run --session-id "$CLAUDE_CODE_SESSION_ID"` opens the bounded
  `team_run_id` at Step B0, before anything can spawn. The run-opened fact carries a
  repository identity digest derived from the ledger's git common dir (the lease
  authority's root digest retired with it), so discovery stays scoped to this
  repository.
- Teardown actions use a stable idempotency key derived from `team_run_id`, the
  worktree path, the registry coordinates (`<outcome-id>:<subplot-id>`), and the action
  kind. Prompts, agent prose, arbitrary paths, environment values, and wall time can
  never replace trusted identity.
- The lease-era close-owner-admission fence is retired. `teardown-intent` and
  `teardown-complete` facts keep a `close_generation` field as the vestigial constant 1
  so the fact shape is unchanged.

## What teardown enumerates

One census per decision: every entry in every outcome worktree registry under this
repository's git common dir, each cross-checked with `git worktree list` through
`outcome_worktrees.live_worktrees`. The census is repository-wide — registry entries
carry no team-run owner. A run's teardown therefore reports the worktrees the
repository's outcome machinery left behind, and a run completes when none of them is
unsettled.

## Event family (`kind=teardown`, closed)

`run-opened`, `teardown-intent`, `resource-attempt`, `resource-result`,
`recovery-observation`, `teardown-complete`. Transition validation and append share the
ledger's exclusive lock; facts carry bounded identity and evidence digests, never raw
prompts, message text, or stdout/stderr, and never a mutable open/closed summary. Open
runs, resources, and completion are projected from one chain-verified snapshot.

## Derived terminal contract

`status` and `reclaim-all` return one `team_teardown.v1` projection:

```text
team_run_id
terminal_reason: success | hard-fail | operator-abort | andon | recovered-crash
intent_id
resources[]:
  resource_id, generation, kind, owner_ref
  action, disposition, evidence_refs[]
open_count
released_count
retained_count
failed_count
completion_fact_ref: string | null
```

`open_count == 0` plus a valid `teardown-complete` fact is the only completed teardown.
`open_count` counts census entries whose action key has not reached a final disposition
— "still open" means "still unsettled". A terminal business result with registered,
git-listed worktrees remains a truthful blocked terminal and can be recovered after the
worktrees are removed out-of-band.

## Disposition vocabulary (re-keyed on worktree path)

The closed disposition vocabulary survives the retirement — `released`,
`already-absent`, `retained`, `failed` — re-keyed from `lease_id` to worktree path. The
worktree sweep reports exactly two branches:

| observation | disposition | reason code | evidence refs |
|---|---|---|---|
| git still lists the worktree | `retained` | `worktree-listed` | none |
| git no longer lists the worktree | `already-absent` | `worktree-not-listed` | `worktree:path-absent:<outcome-id>:<subplot-id>` |

Two redefinitions to read carefully:

- `already-absent` **changed meaning**: it now means "git no longer lists this
  worktree". Pre-retirement it meant "the lease head is gone", which said nothing about
  disk.
- The `released` disposition keeps its place in the vocabulary, but the sweep no longer
  produces it: its only producer was the reap branch, deleted with the reaper seam.
  `released` remains recordable by any adapter the driver is wired with.

## Hook and recovery contract

Observed terminal paths run B8 synchronously. Crash recovery is re-keyed onto the only
liveness signal left: a git-listed worktree.

- `SessionEnd`: five-second bounded best-effort
  `request --cwd <trusted hook cwd> --reason <trusted reason>`; never says the run is
  closed merely because the hook ran or timed out.
- `SessionStart startup|resume`: read-only discovery of open runs, then the 15-second
  bounded `recover --expired-only --max-actions 4`. `--expired-only` skips any run while
  the census still sees a git-listed worktree — recovery never finalizes reporting over
  a worktree someone may still be working in.
- Explicit CLI: `status`, `request`, `reclaim-all`, and `recover` (via
  `lease_protocol.py <verb>`, which resolves Saga's canonical `team_teardown.py`). JSON
  output is bounded with stable reason codes. Dry-run is available for attended census
  but is never accepted as completion.

## What retired with the lease authority

- Spawn-time registration of resident teammates and owned subprocesses
  (`register_subprocess`, the resident/process stop adapters, and the idle-eviction gate
  `authorize_resident_stop`) — their trusted identity source is gone; caller-asserted
  identity is the accepted loss for the interim.
- The owner-admission close fence and its still-closed recheck.
- The worktree reap branch and its reaper seam. Stale per-leaf worktrees accumulate
  until reclaimed by hand (documented manual reclamation lives with the outcome
  worktree lifecycle); teardown will report them `retained` until git no longer lists
  them, then `already-absent`.

## Failure honesty

- A retained or failed resource never disappears from the projection; the run stays
  terminal-but-blocked until recovery converges (stable action keys, no double-action).
- If the driver crashes after an action but before its result fact, recovery reconciles
  trusted reality and appends `already-absent` for the existing action key rather than
  acting again.
- A broken ledger chain, unknown kinds, and identity mismatches are typed refusals —
  never silently dropped, never counted as released.
- Teardown has no removal capability: no input makes it delete a worktree, deregister
  an entry, or truncate a ledger.
