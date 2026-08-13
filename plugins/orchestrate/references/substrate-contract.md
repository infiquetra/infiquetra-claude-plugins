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

Enforcement is observational. Every child records the ambient checkout's immutable commit before
provisioning. U4 therefore requires a landing in a Git repository with at least one commit; a
non-repository or an unborn repository fails loudly instead of disabling committed-change
observation. A read-only child lands in the ambient checkout, so completion compares its committed
and uncommitted tracked and non-ignored changes with the launch baseline and applies its declared
path scope there. A mutating child lands in a separate branch worktree. Its committed tree is
compared with the merge base of the child tip and the ambient checkout's current tip, which excludes
upstream changes after a merge or rebase, and that result is unioned with uncommitted tracked and
non-ignored status in the child landing. The ambient checkout is observed separately from its
dispatch baseline; any attributed ambient change violates a mutating child's landing boundary even
when its relative path is declared in scope. SHA-256 fingerprints retain attribution when a path was
already dirty at dispatch. A landing path must equal a declared scope path or live below a declared
directory, and a boundary violation fails completion even when the predicate passed.

Shared-tree enforcement is observational and cannot identify which concurrent actor made a change.
For a mutating child, an operator or overlapping child that changes the ambient checkout during its
dispatch window can cause it to fail closed. For a read-only child, the shared checkout is the child
landing, so every change observed there since its baseline is attributed to that child even though
authorship is not established. Worktree isolation prevents collisions only when writers remain
inside their assigned landing.

**The read-only sibling repair.** U4 left one consequence of that open: two read-only children with
disjoint scopes, each writing only its own declared artifact into the shared checkout, each failed
the other's boundary check. A control that fails every child in the product's ordinary multi-child
configuration is not a usable control. U5 resolves it structurally rather than by suppression, and
the resolution has two halves.

First, **every child's deliverable lands in a directory that is exclusively its own**, inside its
own landing, at `.orchestrate/artifacts/<run-id>/<row-id>/`. That directory is required to be
ignored by the repository; the requirement is checked when the dispatch receipt is issued and fails
closed in a repository that does not ignore the orchestrate state directory, because the whole
attribution argument depends on it. The directory sits inside the landing rather than beside the
repository so a sandboxed mutating child can write to it at all. The child writes an in-flight
sibling there and the orchestrator renames it into place.

Second, **a read-only child's declared scope is a read scope, not a repository write allowlist.**
Its repository write allowlist is empty, so any repository-visible change during its window fails
the boundary check regardless of which child made it — and a correct read-only child now makes none,
because its deliverable is outside Git's view. Concurrent read-only children with disjoint scopes
therefore complete cleanly, which is the ordinary case, while a read-only child that does write into
the shared checkout still fails, with the existing message stating that authorship is not
established.

What this repair does **not** provide: the exclusive artifact directory is exclusive by assignment,
not by enforcement. Nothing in the filesystem stops a child from writing into a sibling's artifact
directory, and because that directory is invisible to Git the boundary check cannot observe it
either. Detecting deliberate cross-child writes requires a per-child filesystem boundary, which is
the same missing control named for Git-ignored paths below.

The completion evaluator is also held to this boundary. It runs the predicate inline in the child's
landing after the child has stopped, so the landing is snapshotted immediately before the predicate
runs and any predicate-authored change is recorded as a failure of the predicate rather than
attributed to the child.

**Git-ignored paths are outside U4 scope observation.** Git status deliberately omits them, and the
ambient runtime state changes as the orchestrator records lifecycle transitions, so this control
cannot reliably attribute ignored control-plane writes to one child. Protecting ignored paths such
as runtime state requires a separate filesystem boundary. This exclusion is explicit rather than a
claim that Git observes every filesystem write.

## Reaping and disappearance

Only a row already in `verified` may be reaped. The lifecycle writes `phase=reaped` and an expected
`exited` state before asking Herdr to close the tab. A missing tab without that recorded transition
is an unexplained disappearance and raises. A missing tab after the transition is expected.

`verified` is now written in exactly one place: a completion evaluation in which the predicate's
dependency closure is unchanged, the artifact was settled by the orchestrator's own rename, the
artifact carries this dispatch's pre-established run binding, the predicate passed, the boundary is
clean, the recorded destination actually changed, and — for judgment-shaped work — an independent
verifier's depth sample is on record. The integration clause is what makes reaping safe on real
work: a child whose change never landed cannot reach `verified`, so it cannot be reaped and its
worktree cannot be discarded with the change still in it.

A failed completion does not move `phase`. `PHASES` is closed and has no member meaning "evaluated
and failed", so the verdict is recorded in the row's own `completion` key instead, and never in
`observed_state` — that column is rewritten by the subscriber's snapshot catch-up for every row with
a live pane, so a failure recorded there would be erased while the child's pane is still open. The
full completion contract, including what each control does and does not establish, is in
[`predicates.md`](predicates.md).
