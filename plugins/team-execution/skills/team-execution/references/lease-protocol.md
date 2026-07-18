# Team-execution lease protocol

Every direct `Agent` fan-out is admitted by Saga's installed `PreToolUse` lifecycle hook before the
provider call. Team-execution does not keep a second counter and does not reserve a Workflow batch:
the hook's exact `(CLAUDE_CODE_SESSION_ID, tool_use_id, agent_type)` reservation is the authority.
`SubagentStart` binds the provider-assigned agent id, and delegated mutations remain fenced by that
bound lease.

Before the first worker, reviewer, or validator `Agent` call, prove the broker is installed:

```bash
TEAM_LEASE="${CLAUDE_PLUGIN_ROOT:-plugins/team-execution}/skills/team-execution/scripts/lease_protocol.py"
test -n "$CLAUDE_CODE_SESSION_ID" || { echo "HALT — missing Claude session id" >&2; exit 2; }
python3 "$TEAM_LEASE" preflight --session-id "$CLAUDE_CODE_SESSION_ID"
```

Preflight pins team-execution's complete default admission snapshot in the shared authority. The
Agent hook consumes that exact session record; it never reconstructs or widens policy from defaults.
The wrapper requires fleet-core lease protocol 2, which includes broker-owned prepare, commit,
abort, and exact-receipt successor acquisition; a version mismatch halts before fan-out.

At a wave or result-collection boundary, renew all live agent leases for the trusted Claude session:

```bash
python3 "$TEAM_LEASE" renew --session-id "$CLAUDE_CODE_SESSION_ID"
```

There is no background renewer. A call may outlive its TTL; expiry revokes authorization and frees
capacity but does not preempt provider inference. If renewal reports any expired or superseded member,
halt the wave and settle it instead of silently granting fresh authority.

## Step B8 teardown

After Step B7, send an explicit stop to every named resident worker, reviewer, and validator. Wait for
each handle to report terminal. Do not infer terminal state from silence or timeout. Only then run:

```bash
python3 "$TEAM_LEASE" teardown --session-id "$CLAUDE_CODE_SESSION_ID" \
  --terminal-agent-id "$AGENT_ID_1" --terminal-agent-id "$AGENT_ID_2"
```

The wrapper refuses an unclaimed reservation or a bound child lacking either the persisted
`SubagentStop` signal or an explicitly verified terminal id. It releases only agent leases for that
session, then sweeps expired agent debris. A crashed or ambiguous child remains leased until TTL and a
later sweep; teardown must not be used as a speculative capacity reset. Worktree leases are outside
this command's authority.
