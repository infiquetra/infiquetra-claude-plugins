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

U4 intentionally supports only Herdr's `default` session. Launch, command-line control, socket
observation, and the register all use that same fixed session; named sessions require a later
end-to-end routing contract and cannot be selected through the child specification.

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
interfaces expose those postures. Mutating Codex uses `workspace-write`, Grok uses its `workspace`
sandbox, Qwen enables its project sandbox, and Agy enables its terminal-restrictions sandbox. Muse's
sandbox is enabled by default and its existing-worktree arguments bind the landing. Claude exposes
no command-line flag that limits writes to the launch working directory. These controls do not
express the declared path allowlist and remain defence in depth.

Enforcement is observational. A branch child records the immutable base commit before its worktree
is created. Completion unions the committed `base_commit..HEAD` name-status diff with uncommitted
tracked and non-ignored status in the child landing. It separately records the ambient checkout's
commit and status baseline, then compares its committed and uncommitted tracked and non-ignored
changes too. A child therefore cannot evade the check by writing or committing a normal repository
path outside its worktree. SHA-256 fingerprints retain attribution when a path was already dirty at
dispatch. Every attributed path must equal a declared scope path or live below a declared directory,
and an outside path fails completion even when the predicate passed.

**Git-ignored paths are outside U4 scope observation.** Git status deliberately omits them, and the
ambient runtime state changes as the orchestrator records lifecycle transitions, so this control
cannot reliably attribute ignored control-plane writes to one child. Protecting ignored paths such
as runtime state requires a separate filesystem boundary. This exclusion is explicit rather than a
claim that Git observes every filesystem write.

## Reaping and disappearance

Only a row already in `verified` may be reaped. The lifecycle writes `phase=reaped` and an expected
`exited` state before asking Herdr to close the tab. A missing tab without that recorded transition
is an unexplained disappearance and raises. A missing tab after the transition is expected. The
later integration gate owns authorization to exercise reaping on real work.
