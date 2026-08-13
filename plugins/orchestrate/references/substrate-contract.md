# Session substrate contract

The orchestrate session lifecycle joins three external systems: the local `agent` launcher, Herdr,
and Git. Each boundary has a production adapter and a fail-loud contract. Register writes remain in
`register.py`; the lifecycle calls that locked, atomic API rather than adding another state store.

## Launch and recovery

`AgentWrapper` always uses the launcher's current-terminal, Herdr, no-focus, control-only path. It
first performs a dry-run and requires two facts from the preview: `cwd=` equals the exact resolved
working directory, and `herdr_workspace=` contains the requested workspace. The real invocation
uses the same arguments without `--dry-run`.

Before launch, the lifecycle writes a deterministic `orchestrate-<run-id>-<row-id>` task label and
moves the register row through `planned` to `launching`. The wrapper's returned JSON is the only
source for `agent_name`, `workspace_id`, `tab_id`, `pane_id`, and `reused`. `reused` describes the
workspace, not the new pane. The identifiers are written immediately while the phase remains
`launching`.

If a retry finds a `launching` row without identifiers, it searches the live Herdr snapshot for one
tab carrying the stored task label. One exact tab with one pane is recoverable; no match permits a
new launch, and more than one match is an error. Recovery therefore does not predict identifiers or
duplicate a child whose launch succeeded before the identifier write crashed.

## Readiness and effort

Launch success is not readiness. The lifecycle reads recent unwrapped pane content first and stops
on a workspace trust prompt without sending any work. It then establishes any in-session effort
directive. Qwen receives `/effort <rung>` and must emit its own full reasoning-effort acknowledgement;
the command's terminal echo is not enough. Other supported runtimes carry effort in the arguments
returned by fleet-core's `adapt_runtime_argv`.

Readiness uses a bounded `pane.output_matched` subscription over Herdr's Unix socket. The socket
subscription is confirmed before dispatch. The sentinel binds the run, child, purpose, and a fresh
nonce. The dispatch prompt contains the marker prefix and JSON payload as separate parts and tells
the child to join them with no separator. It never contains the complete sentinel, so terminal echo
cannot satisfy the subscription. The child-produced assembled sentinel moves the row to `ready`; a
timeout records `not_ready`. No lifecycle detector status can substitute for the interaction.

Herdr protocol 19 currently reports `read.revision=0` on live `pane.output_matched` events even when
the pane's own revision is positive and advancing. Those values are different counters and are not
ordered against each other. Freshness therefore comes from the complete nonce-bound identity and
the prompt construction, not a numeric comparison. The remaining failure mode is explicit: a child
can assemble and print the sentinel too early while reasoning. Readiness proves interaction and the
ability to follow the protocol; it does not prove task completion or satisfy the later predicate.

## Landing and scope

A read-only child runs in the ambient checkout with `integration_mode=none` and
`destination=none`. A mutating child receives a deterministic branch worktree with
`integration_mode=branch` and the branch name as its destination. Creating the worktree is not the
whole provisioning step: a newly created worktree has no checkout-local virtual environment, so
the child specification also carries an environment command. The default is `uv sync`. A failed
environment command raises a landing error before launch; retrying reuses the worktree and retries
the missing setup.

Supported runtimes receive real read-only or workspace-write flags where their command-line
interfaces expose those postures. Those flags do not express a file allowlist and are only defence
in depth. Enforcement is observational: after the child predicate runs, Git enumerates every
tracked and untracked changed path with the null-delimited porcelain format. The final set is
compared with the pre-dispatch set, and every newly changed path must equal a declared scope path or
live below a declared directory. An out-of-scope path fails completion even when the predicate
passed.

## Reaping and disappearance

Only a row already in `verified` may be reaped. The lifecycle writes `phase=reaped` and an expected
`exited` state before asking Herdr to close the tab. A missing tab without that recorded transition
is an unexplained disappearance and raises. A missing tab after the transition is expected. The
later integration gate owns authorization to exercise reaping on real work.
