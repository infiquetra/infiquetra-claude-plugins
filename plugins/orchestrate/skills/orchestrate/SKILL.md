---
name: orchestrate
description: The orchestrate register, tracked herdr subscriber, write-ahead child session lifecycle, and completion gate for multi-vendor runs, with interaction readiness, scoped worktrees, nonce-bound sentinels, reconnect catch-up, bounded predicates on settled run-bound artifacts, verified integration, and recorded reaping. No routing, spend gate, or mirror behavior yet. Triggers on "orchestrate register", "orchestrate subscriber", "orchestrate session lifecycle", "orchestrate completion", "orchestrate predicate", "herdr event catch-up", "the run register".
---

# orchestrate — register, event subscriber, session lifecycle, and completion

`orchestrate` coordinates multi-vendor herdr sessions: Claude, Codex, Grok, Muse, Qwen, and agy
children dispatched under one operator-driven run, aggregated back through a mirror and woken by a
subscriber holding herdr's event socket across turns. This skill currently ships **four pieces of
that system: the register, subscriber, child session lifecycle, and completion gate**. The register is the whole state model (KTD5) and the
Claude↔Codex handoff seam (R12). The subscriber holds protocol 19 event streams, wakes the
orchestrator, and performs reconnect catch-up (KTD3/KTD12). The session lifecycle owns write-ahead
launch, recovery, interaction readiness, landing isolation, scope checks, and recorded reaping.
Completion is the only path to `verified` (R5): a bounded, typed predicate run inline by the
orchestrator on a settled, run-bound artifact, inside a clean boundary, with integration to the
recorded destination verified before a child can be reaped.
Routing, spend gating, hang detection, mirror behavior, and the `/orchestrate`
command itself land in later units of
`docs/plans/2026-08-12-orchestrate-plugin-plan.md` and is deliberately absent here.

## What the register is

A single flat JSON document, global across a repository (not per-run), at
`.orchestrate/register.json`. One row per tracked entity: one per dispatched child, one for the
mirror, one for the subscriber. Per-run material — retired rows, run-scoped artifacts — lives
under `.orchestrate/runs/<run-id>/`.

The implementation is `scripts/register.py`. Read its module docstring before writing to the
register from any later unit — it documents every column's meaning, including two facts measured
first-hand while driving this build by hand (`docs/engineering-journal/LEARNINGS.md`,
`#pane-revision-is-the-liveness-signal` and `#agent-lifecycle-detectors-lie`):
`last_event_at` must be fed by herdr's pane-output `revision` counter, never by the
lifecycle-transition `state_change_seq` counter, which sits still for minutes on a healthy,
working child; and a child's own reported status is not a completion signal, so `expected_state` /
`observed_state` exist to record a disagreement rather than resolve it by trusting one side.

`pane.output_matched` reports `read.revision=0` while the pane's own counter is positive and
advancing, so those counters are never compared. The subscriber instead checks complete run,
child, purpose, and nonce identity. All sentinel producers use the public split-assembly helper so
the assembled marker stays out of echoed dispatch input.

## Contract this unit guarantees

- **Atomic, durable writes.** Every write is temp-sibling-file, `fsync`, then `os.replace` (not
  just temp-plus-`os.replace` — `fsync` before the replace is what keeps a machine crash right
  after a successful replace from leaving `register.json` present but empty, matching
  `run_ledger.py` / `manifest_store.py` elsewhere in this repository). No reader ever observes a
  torn file. Concurrent read-modify-write cycles are serialized with an exclusive advisory lock
  (`fcntl.flock`) around the register's own `.lock` sidecar, so two sequential writers never lose
  each other's row.
- **Forward compatibility (C4), at both levels.** A row is always a plain `dict`, never
  reconstructed through a fixed-field type: `upsert_row` merges the fields a caller supplies into
  whatever already exists at that row id rather than replacing the row, so a key nested inside a
  child row that one runtime wrote and the other does not know about survives a write by the
  other. The same holds at the **document root** — the loader returns the document exactly as it
  read it (only normalizing `rows`) rather than rebuilding a known `{schema_version, rows}`
  envelope, so a document-root key one runtime writes (a handoff cursor, say) survives an ordinary
  write by the other, on both the `upsert_row` and the `retire_run` path.
- **A schema version this code does not support halts loudly (C3).** `register.py` writes a halt
  receipt to `.orchestrate/halt-receipt.json` and raises, without ever touching
  `register.json` itself.
- **Retiring a run only touches that run's own rows, and is genuinely idempotent.** `retire_run`
  moves every row whose `run_id` matches into `.orchestrate/runs/<run-id>/register-final.json`,
  durably, before the live register is rewritten — every other run's rows are left exactly as
  they were. Retiring the same run again after it already succeeded returns the existing archive
  path unchanged rather than recomputing an empty set and overwriting it; retiring a run with
  nothing live and no prior archive writes nothing and returns `None`.
- **Both hang-detection time columns always exist on a row.** `deadline` and `max_quiet_seconds`
  are alternative strategies — a caller sets whichever fits a given dispatch — and `upsert_row`
  seeds whichever one a caller didn't set to `None` at row creation, so this pair specifically
  always round-trips regardless of which strategy a row uses. Every other optional column stays
  genuinely absent until some later phase transition sets it.

## Using the register from Python

```python
from pathlib import Path
import register  # scripts/register.py, on sys.path for the invoking skill/command

root = Path.cwd()
register.upsert_row(root, "child-1", {"run_id": "run-abc", "phase": "planned", "agent": "claude"})
rows = register.read_rows(root, run_id="run-abc")
register.retire_run(root, "run-abc")
```

Or from the shell, for quick inspection:

```bash
python3 plugins/orchestrate/skills/orchestrate/scripts/register.py show --run-id run-abc
python3 plugins/orchestrate/skills/orchestrate/scripts/register.py retire run-abc
```

## Event subscription and catch-up

`scripts/herdr_events.py` opens `~/.config/herdr/herdr.sock`, validates every requested
subscription, and sends the request documented in `references/herdr-event-api.md`. Request event
types are dotted (`pane.exited`); broadcast event names are underscored (`pane_exited`). A malformed
or underscored subscription is an error, never an ignored entry.

`scripts/subscriber.py` is the single-purpose process that holds the event stream across turns. It
creates an ordinary register row with `agent="subscriber"`, wakes the orchestrator through
`agent.prompt`, and runs one `session.snapshot` catch-up after every accepted subscription,
including startup. Catch-up updates `observed_state`, reports disagreement with `expected_state`,
and checks declared `artifact_path` presence. Its `observed_state_source` records whether the value
was directly observed or inferred from pane/tab presence. A catch-up failure is reported but does
not close the accepted event stream. It does not evaluate predicates.

The subscriber only accepts `pane.output_matched` entries built from a complete substring sentinel;
a regex or ordinary-text output match is valid for Herdr generally but is a startup error here
because it cannot satisfy the subscriber's identity guard. More than one sentinel subscription may
target the same pane, so readiness and completion interactions can both remain active.

The spawning unit supplies the subscriber pane, orchestrator pane, run identity, and complete JSON
subscription list:

```bash
python3 plugins/orchestrate/skills/orchestrate/scripts/subscriber.py \
  --root "$PWD" \
  --run-id run-abc \
  --row-id subscriber-run-abc \
  --pane-id w1:p2 \
  --orchestrator-pane w1:p1 \
  --subscriptions-json '[{"type":"pane.exited"}]'
```

## Child session lifecycle

`scripts/session_lifecycle.py` launches through `agent --herdr-control-only` only after a dry-run
confirms the exact absolute working directory and intended Herdr workspace. A run-bound task label
and `launching` register phase are durable before the launch side effect. A retry discovers that
label before launching, so a crash after process creation cannot duplicate the child.

The wrapper's JSON response is the only source for workspace, tab, pane, reused-workspace status,
and the actual uniquified agent name. Readiness subscribes before dispatch and requires the child
to assemble and emit a nonce-bound sentinel that never appears whole in the echoed prompt. Pane
content is checked for a trust prompt first. The lifecycle never treats `agent_status` alone as
readiness. Qwen receives its resolved `/effort` command in-session and must emit its own
acknowledgement before work is dispatched.

Mutating children receive a branch worktree plus an explicit environment setup; read-only children
stay in the ambient checkout. The lifecycle is fixed to Herdr's default session. Every child gets
its runtime's ordinary workspace-write posture, mutating or not: each is dispatched with an artifact
it must write and no supported CLI accepts a path allowlist, so a read-only flag would forbid the
one write the protocol requires. The scope control
records a launch commit for every child and unions committed changes with uncommitted tracked and
non-ignored changes. A mutating child's declared scope applies only to its isolated landing; every
attributed ambient-checkout change violates that boundary. Git-ignored paths remain an explicit
limitation requiring a separate filesystem boundary. Reaping records the transition before closing
the tab.

See `references/substrate-contract.md` for the adapter, recovery, residual readiness risk, and
failure contract.

## Completion — the only path to `verified`

`scripts/completion.py` decides whether a child is done, and records why either way. A predicate is
a typed, closed schema: a fixed argument vector with a bounded timeout and output cap, rejected
rather than clamped when it exceeds either, and rejected outright when it is shell text. It runs
inline in the orchestrator's own process tree — the mirror never decides (KTD6).

Before dispatch the orchestrator issues a receipt: a run-binding token the child must carry inside
its deliverable, the destination's exact pre-dispatch state, and a digest over the predicate's
resolved dependency closure. A predicate whose closure lives where the child can write is rejected
before evaluation, and a closure that changes between dispatch and evaluation fails as tampered.

The receipt must belong to the child being evaluated: the specification, landing, baseline and
receipt arrive as independent arguments, so run, row and landing are checked against it first.

Settlement is performed, not inferred. The child writes only an in-flight sibling of its
destination; the orchestrator requires the destination to be untouched and then renames the
in-flight file into place itself, so the predicate only ever reads a renamed path. That rename is
one-shot, so it is recorded and replayed — which is what makes re-evaluation after a restart, and
the two-step sequence judgment work needs, reachable at all. Every child's deliverable lands in a
directory that is exclusively its own and invisible to the repository boundary, which is what lets
concurrent read-only children in one checkout each complete cleanly.

The register is not a trusted store. It is Git-ignored, it sits inside every child's landing, and
every child can write files there — so the durable receipt and settlement record each carry a keyed
digest under a per-run secret held outside the repository. A record the orchestrator did not write
authenticates against nothing.

Integration to the recorded destination is verified before `verified` is written, so a child whose
change never landed cannot be reaped. Judgment-shaped work additionally requires an independent
verifier's depth sample, bound by digest to the settled artifact, naming a verifier session that
actually exists in the register with the vendor and model it claims, and supporting at least one
sampled claim — all of it persisted, so a sampled child and an unsampled one are not the same green
row. A row's phase is `verified` if and only if its latest verdict is a pass: a failing
re-evaluation demotes a previously verified row rather than leaving a contradiction the reap gate
would read as a pass, and a `reaped` row keeps its terminal phase whichever way the verdict goes.
The receipt binds every input the verdict depends on — work shape, scope, mutability, integration
target and the changed-paths baseline, not only the identity labels — and the predicate runs in its
own process group that is killed before the evidence is re-observed.

See `references/predicates.md` for the full contract, including what each control does **not**
establish.

## What is deliberately not here

No `commands/` entry (`/orchestrate` lands with the units that need an invocable surface — KTD2),
no planning or vendor routing, no admission control, no mirror behaviour beyond the register row it
will eventually hold, no spend gate, and no hang detector.
