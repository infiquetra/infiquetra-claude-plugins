---
name: orchestrate
description: The orchestrate register and tracked herdr event subscriber for multi-vendor runs, with revision-safe sentinels and reconnect catch-up. No session launching, predicate evaluation, routing, or mirror behavior yet. Triggers on "orchestrate register", "orchestrate subscriber", "herdr event catch-up", "the run register", ".orchestrate/register.json".
---

# orchestrate — register and event subscriber

`orchestrate` coordinates multi-vendor herdr sessions: Claude, Codex, Grok, Muse, Qwen, and agy
children dispatched under one operator-driven run, aggregated back through a mirror and woken by a
subscriber holding herdr's event socket across turns. This skill currently ships **two pieces of
that system: the register and subscriber**. The register is the whole state model (KTD5) and the
Claude↔Codex handoff seam (R12). The subscriber holds protocol 19 event streams, wakes the
orchestrator, and performs reconnect catch-up (KTD3/KTD12). Everything else — session launching,
predicate evaluation, spend gating, hang detection, routing, the `/orchestrate` command itself —
lands in later units of
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

`dispatch_revision_baseline` is the pane-output `revision` sampled immediately before dispatch.
An output-match sentinel is accepted only when its event revision is greater than that baseline;
this prevents matching a sentinel that was already present in scrollback before the new dispatch.

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
and checks declared `artifact_path` presence. It does not evaluate predicates.

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

## What is deliberately not here

No `commands/` entry (`/orchestrate` lands with the units that need an invocable surface — KTD2),
no session launching via the `agent` wrapper, no predicate evaluation, no mirror behaviour beyond
the register row it will eventually hold, no spend gate, and no hang detector.
