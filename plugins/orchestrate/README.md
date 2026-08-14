# orchestrate

Cross-vendor multi-session orchestration over [herdr](https://github.com/infiquetra): dispatch
work to Claude, Codex, Grok, Muse, Qwen, and agy children as tracked herdr sessions, aggregate
their results, and hold the operator's conversation steady while they run.

**This release ships the register, tracked herdr event subscriber, child session lifecycle, and
completion** — write-ahead launch, interaction readiness, scoped worktrees, recorded reaping, and
the only path a child reaches `verified`: a bounded predicate run on a settled, run-bound artifact,
inside its boundary, with its destination actually changed and, for judgment work, a claimed
independent verifier's depth sample on record. See `skills/orchestrate/SKILL.md` for the full contract and
`CHANGELOG.md` for what is and is not implemented yet. The full design lives in
`docs/plans/2026-08-12-orchestrate-plugin-plan.md`.

## Register

The live register is the whole state model for a run: one row per dispatched child, one for the
mirror, one for the subscriber. It is one JSON document per `run_id`, held outside every
working tree (default `~/.orchestrate/registers/<run_id>.json`). A `run_id` is host-global, so
two runtimes on one host and one checkout that name the same id share one live document.
Two checkouts of one `run_id` are a collision. `retire_run` forgets the per-run secret
first, then archives into the recorded work location, then deletes the live file and the
recorded-root sidecar. Sidecar create, key mint, key delete, and retirement share one
per-run lock, so when retirement returns that generation's key and sidecar are gone.
Forgetting the key requires that recorded location, including when the live file is
already gone. See `scripts/register.py`'s module docstring for the full column reference.

## Event subscriber

`scripts/herdr_events.py` validates and holds protocol 19 `events.subscribe` streams over
`~/.config/herdr/herdr.sock`. `scripts/subscriber.py` carries its own ordinary register row, wakes
the orchestrator with `agent.prompt`, and runs one bounded snapshot catch-up at startup and after
every reconnect. Catch-up records lifecycle disagreement and checks whether each declared
`artifact_path` exists. That column is written only once an artifact has actually settled, and as an
absolute path: declaring it at dispatch would make every reconnect of every in-flight child ask the
operator for attention about a file that is not supposed to exist yet, and a relative path would be
resolved against the ambient checkout while a mutating child's artifact lives in its worktree.

See `references/herdr-event-api.md` for the exact request shape, dotted-versus-underscored event
vocabularies, sentinel revision guard, and subscriber command-line interface.

## Session lifecycle

`scripts/session_lifecycle.py` previews and launches children through the `agent` wrapper's
control-only path. It records launch intent before the side effect, recovers interrupted launches
by their run-bound task label, and records the wrapper's returned workspace, tab, pane, and actual
agent name.

Readiness is a bounded interaction, not a lifecycle-status guess: the child must assemble and emit
a unique nonce-bound sentinel that never appears whole in the echoed prompt. Mutating work gets a
branch worktree and an explicit environment setup; read-only work stays in the ambient checkout.
Every child records a launch commit. Committed and repository-visible uncommitted changes are
compared with the declared scope even when the work predicate passes, and any attributed ambient
checkout change violates a mutating child's isolated landing boundary. Git-ignored paths are an
explicit limitation, not silently described as covered. Every child is launched with its runtime's
ordinary workspace-write posture — a read-only flag would have forbidden the artifact every child is
required to write, and no supported CLI accepts a path allowlist. That posture is the only real
containment: it prevents writes *outside* the workspace. Inside the workspace nothing is prevented.
The boundary check is post-hoc, partial detection — it runs after the child stops, reports rather
than blocks, sees only tracked and non-ignored paths, and cannot establish authorship in a shared
checkout — and a read-only child's empty repository write allowlist means any repository-visible
write fails its completion.
Launch and observation are fixed to Herdr's default session. See
`references/substrate-contract.md` for the adapter and failure contract.

## Completion

`scripts/completion.py` is the only place a child reaches `verified`. The orchestrator establishes
the expected evidence identity *before* dispatch — run-binding token, destination pre-state,
predicate dependency closure and content digest — then settles the artifact by renaming the child's
in-flight file itself, runs the bounded predicate, checks the boundary, verifies the destination
changed, and for judgment work requires a claimed independent verifier's depth sample.

The live register sits outside every landing, addressed by `run_id`. A sandboxed child cannot
write it by working in its landing. Claude and Muse expose no workspace-write flag. Mode
`0600` on the run key excludes other operating-system accounts, not a child running as this
account, so for those runtimes this module does not defend against a child that reads the
key. The durable records still carry a keyed digest so a digest that does not match this
run's key authenticates against nothing. The seal does not establish authorship against a
child that can read the key. Evaluation is safe to re-run for one dispatch, and a
row's phase is `verified` if and only if its latest verdict is a pass.

`references/predicates.md` states what each control establishes and — control by control, with the
closure walk enumerated member by member — what it does not.
