---
name: delegation-audit
description: Reconcile the durable delegation audit store against claimed dispositions, flagging any delegation that claims real external-engine execution but has no receipt proving it ran. Read-only, advisory, on-demand — never a gate, never a background job. Triggers on "/delegation-audit", "did this delegation actually run", "audit delegations", "check for fallback no-ops", or a post-incident question about whether an agy/codex run was real.
---

# Delegation Audit

`/delegation-audit` answers **"Which of these delegations actually ran, and which only claimed to?"**
It reconciles the durable delegation audit store (`~/.claude/delegation-audit` by default,
`plugins/fleet-core/scripts/fleet_commons/audit_store.py`) against every mirrored delegation's own
disposition, and flags exactly the ones that claim real execution (`ran-as-requested` / agy's
`agy_launched`) but carry no schema-valid `bridge_receipt.v1` proving it — a no-op, in the fleet's own
silent-fallback vocabulary (`docs/engineering-journal/LEARNINGS.md` §6.1).

## What it is not

- **Not a gate.** It never blocks a merge, a deploy, or any lifecycle command. It is a read-only
  query the operator (or a debugging session) runs on demand.
- **Not the Stop-hook tripwire.** `delegation_stop_audit_hook.py` already runs a live,
  always-on transcript classification at session-stop time over the *disposable* bundle root
  (`.claude/agy/runs`, `.claude/codex/runs`). `/delegation-audit` is a different, complementary
  surface: a point-in-time reconciliation over the *durable* mirror, so the question can still be
  asked after the originating bundle/worktree is long gone.
- **Not a standing dashboard.** No scheduled runs, no watcher. Point-in-time only, matching issue
  #396's own non-goal.

## Running it

```bash
python3 plugins/saga/scripts/delegation_audit_query.py [--audit-store <path>] [--run-id <id> ...]
```

Omit `--audit-store` to read the default (`~/.claude/delegation-audit`); omit `--run-id` to
reconcile every run currently mirrored in the store. The report is JSON:

```json
{
  "audit_store_root": "/home/operator/.claude/delegation-audit",
  "run_count": 2,
  "flagged_count": 1,
  "flagged": [{"run_id": "...", "flagged": true, "claimed_real": true, "observed_real": false, "reason": "..."}],
  "clean": [{"run_id": "...", "flagged": false, "claimed_real": true, "observed_real": true, "reason": "clean"}]
}
```

## How reconciliation works

For each run, `fleet_commons/delegation_audit.py`'s `reconcile_store` derives:

- **Claimed disposition** — the mirrored `manifest.json`'s `disposition` field
  (`ran-as-requested` claims real execution; `fell-back-to-claude` / `substituted-engine` /
  `rejected-offload` do not), or, when no manifest was mirrored, agy's own `result.json`
  (`agy_launched` + a passing `status`).
- **Observed proof** — a mirrored `receipt.json` that validates as a schema-valid
  `bridge_receipt.v1` (`bridge_receipt.validate_receipt`).
- **Flag** — exactly when claimed-real and NOT observed-real. A run that never claimed real
  execution, or that claims real execution AND carries a valid receipt, is never flagged.

Every step degrades to "no signal" rather than raising on a missing or corrupt mirrored file — a
partially-populated or damaged store never crashes the audit, it just reports what it can.

## Interaction method

This is a read-only reporting skill — it never mutates state, so there is nothing to confirm.
Render the JSON report's `flagged` list plainly to the operator; if empty, say so ("no no-ops found
across N runs") rather than silence.

## Boundary negatives

`/delegation-audit` does **NOT**:

- write to, prune, or migrate the audit store — that is `agy_delegate.py` / `engine_dispatch.py`'s
  mirror-write path and a future retention-policy issue, not this skill;
- gate a merge, deploy, or any lifecycle command — findings are advisory only, exactly like every
  other external-engine evidence surface (`{#external-engines-never-gatekeepers}`, #283);
- re-implement or replace the Stop-hook tripwire (`delegation_stop_audit_hook.py`) — the two
  surfaces answer the same question over two different (disposable vs. durable) evidence sources;
- change chaperone-dispatch's executor model — it only reports on evidence that model already
  produced.
