# Teardown consumer and spawn-site inventory (#358)

The terminal reclamation mechanism exists only at `plugins/saga/scripts/team_teardown.py`,
composing the #356 broker (`plugins/fleet-core/scripts/fleet_commons/lease_broker.py`) and
the #351 run-fact ledger (`plugins/saga/scripts/run_ledger.py`). Every production site
below reaches it through the plugin boundary; no second reclamation store exists.

| boundary | run-open | register | renewal | terminal driver | action owner | release | recovery | proof |
|---|---|---|---|---|---|---|---|---|
| Team Phase B0 | `lease_protocol.py open-run` (resolves `team_teardown.py open-run`) | n/a | n/a | n/a | root session | n/a | n/a | `run-opened` fact with session + root digest |
| Team Phase B1 resident spawn | uses B0 run id as `owner_id` | Saga `PreToolUse Agent\|Task` hook broker reservation (#356) | `lease_protocol.py renew` at wave boundaries | n/a | host runtime | B8 via terminal receipt | expired-lease recovery | broker lease with `agent_id` + `child_terminal_at` |
| Team owned subprocess spawn | uses B0 run id as `owner_id` | `team_teardown.register_subprocess` (pid, start, boot, argv digest, escalation on the lease) | lease TTL | n/a | coordinator | B8 `process-stop` | expired-lease recovery | lease `owner_pid`/`owner_process_start`/`boot_id` |
| Outcome worktree provisioning | outcome dispatch identity | `acquire_worktree` (#356) | `transfer_worktree` renewal | n/a | outcome coordinator | #356 `sweep` only | dead-owner proof + reap | worktree lease + outcome registry entry |
| Every observed terminal (success / hard-fail / operator-abort / andon) | existing run | n/a | n/a | `lease_protocol.py reclaim-all` → `team_teardown.reclaim_all` | root session | typed adapters | armed on retained/failed | `teardown-intent` … `teardown-complete` chain |
| SessionEnd | existing run | n/a | n/a | `request` only (no actions) | Saga hook (5 s) | none | later pass | `teardown-intent` fact — request evidence, never closure |
| SessionStart startup/resume | existing runs | n/a | n/a | `recover --expired-only --max-actions 4` | Saga hook (15 s) | typed adapters | this is the recovery seam | `recovery-observation` + absence/receipt evidence |
| Explicit operator CLI | existing runs | n/a | n/a | `status` / `request` / `reclaim-all` / `recover` | operator | typed adapters | bounded batches on request | `team_teardown.v1` projection |

Rules the conformance tests enforce:

- A spawn path that creates an Agent, subprocess, or worktree without broker registration
  under the run's owner identity is a leak-by-construction and fails source conformance.
- A terminal branch that asserts completion without the B8 driver (`reclaim-all` /
  `reclaim_all`) fails source conformance — B7 wording is draft-only.
- CI proves the leak invariant inside a temporary repository fixture only; it never
  enumerates, inspects, or deletes the developer's global worktree set. A live census is
  an attended dry-run action with separate resource-specific authority.
