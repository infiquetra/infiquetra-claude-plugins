# Teardown and Reclamation Protocol (#358)

The executable contract behind `Step B8: Terminal Teardown and Reclamation`. One live
ownership authority (the #356 fleet broker), one historical fact stream (the #351
hash-chained `run_fact.v1` ledger, `kind=teardown`), and one derived projection
(`team_teardown.v1`). There is no second registry, mutable status file, TTL clock,
heartbeat store, or reaper decision engine.

## Run identity

- `lease_protocol.py open-run --session-id "$CLAUDE_CODE_SESSION_ID"` opens the bounded
  `team_run_id` at Step B0, before anything can spawn. The id is the run's broker
  `owner_id`; every resident, registered subprocess, and outcome worktree the run creates
  is acquired under it, so the owned-resource snapshot is exactly the broker's lease set
  for that owner.
- Teardown actions use a stable idempotency key derived from `team_run_id`, resource
  identity, resource generation, and action kind. Prompts, agent prose, arbitrary paths,
  environment values, and wall time can never replace trusted identity.
- The broker's `close-owner-admission` operation is monotonic and commits under the broker
  lock: after it, every acquire, reserve, claim, or retry for that exact run is refused
  while existing leases remain inspectable. Repeating close is idempotent; there is no
  reopen operation. The closed map is bounded, so under sustained churn an old record can
  be evicted and admission lapses open until re-closed under a fresh generation — the
  driver re-closes at pass start, snapshots after the close, and refuses its receipt
  unless the pass-local generation is still the closed one, so eviction can cost a retry
  but never a false completion. A re-issued generation replays the run's one recorded
  intent (generation is not intent identity).

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

`open_count == 0` plus a valid `teardown-complete` fact is the only completed teardown. A
terminal business result with open resources remains a truthful blocked terminal and can
be recovered later.

## Resource action matrix

| resource kind | trusted action | completion evidence | retain when |
|---|---|---|---|
| resident Agent teammate | runtime stop request, await terminal, broker release-owner | host stop/terminal receipts plus current token | no terminal receipt, mismatch, stop failure |
| owned subprocess | verify PID/start/boot/run, TERM, optional policy-bound KILL, release | process absence with same identity plus signal receipt | identity mismatch, permission, alive after allowed policy |
| outcome worktree | #356 `sweep` only | broker classification plus outcome registry/reap result | live owner, dirty/unmerged/unsafe path, reap failure |
| provisional/unused lease | broker idempotent release | exact owner/tool/batch identity | claimed by a live child or identity mismatch |

Subprocess stop policy is recorded on the broker lease at registration time
(`owned-subprocess:term-only` or `owned-subprocess:term-then-kill`); `SIGKILL` is sent only
under the explicit `term-then-kill` escalation class, after `SIGTERM` and the bounded
production wait. PID reuse, boot change, identity mismatch, permission errors, and a
still-live unowned process fail safe as `retained`.

Idle eviction consumes only #357 `confirmed-stalled` decisions or an explicit
segment-boundary shed, paired with current #356 ownership. Phi suspicion, chat activity, a
bare idle notice, or artifact-pointer age never stops a resident; warm peers within the
idle policy stay resident.

## Hook and recovery contract

Observed terminal paths run B8 synchronously. `SIGKILL`, process crash, or host death is
reclaimed only on a later recovery invocation after lease expiry and trusted dead-owner
proof — that delay is explicit, not a defect.

- `SessionEnd`: five-second bounded best-effort
  `request --cwd <trusted hook cwd> --reason <trusted reason>`; never says the run is
  closed merely because the hook ran or timed out.
- `SessionStart startup|resume`: read-only discovery of open runs, then the 15-second
  bounded `recover --expired-only --max-actions 4`; every destructive action still passes
  the same broker/process/worktree guards.
- Explicit CLI: `status`, `request`, `reclaim-all`, and `recover` (via
  `lease_protocol.py <verb>`, which resolves Saga's canonical `team_teardown.py`). JSON
  output is bounded with stable reason codes. Dry-run is available for attended census but
  is never accepted as completion.

## Failure honesty

- A retained or failed resource never disappears from the projection; the run stays
  terminal-but-blocked until recovery converges (stable action keys, no double-stop,
  double-release, or double-delete).
- If the driver crashes after an action but before its result fact, recovery reconciles
  trusted reality and appends `already-absent` for the existing action key rather than
  acting again.
- Corrupt authority, a broken ledger chain, unknown kinds, and identity mismatches are
  typed refusals — never silently dropped, never counted as released.
