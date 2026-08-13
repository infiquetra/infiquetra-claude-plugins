# orchestrate

Cross-vendor multi-session orchestration over [herdr](https://github.com/infiquetra): dispatch
work to Claude, Codex, Grok, Muse, Qwen, and agy children as tracked herdr sessions, aggregate
their results, and hold the operator's conversation steady while they run.

**This release ships the register, tracked herdr event subscriber, and child session lifecycle** —
including write-ahead launch, interaction readiness, scoped worktrees, and recorded reaping. See
`skills/orchestrate/SKILL.md` for the full contract and `CHANGELOG.md` for what is and is not
implemented yet. The full design lives in
`docs/plans/2026-08-12-orchestrate-plugin-plan.md`.

## Register

`.orchestrate/register.json` is the whole state model for a run: one row per dispatched child,
one for the mirror, one for the subscriber. It is global (not per-run), keyed by `run_id`, with
atomic read/write and forward-compatible rows so Claude and Codex sessions can hand a run off to
each other without losing state either one wrote. See `scripts/register.py`'s module docstring
for the full column reference.

## Event subscriber

`scripts/herdr_events.py` validates and holds protocol 19 `events.subscribe` streams over
`~/.config/herdr/herdr.sock`. `scripts/subscriber.py` carries its own ordinary register row, wakes
the orchestrator with `agent.prompt`, and runs one bounded snapshot catch-up at startup and after
every reconnect. Catch-up records lifecycle disagreement and checks whether each declared
`artifact_path` exists; predicate evaluation is not part of this release.

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
Final Git changed paths are compared in full with the declared scope even when the work predicate
passes. See `references/substrate-contract.md` for the adapter and failure contract.
