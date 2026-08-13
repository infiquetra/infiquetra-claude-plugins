# Changelog

## [0.2.0] - 2026-08-13

### Added

- A strict protocol 19 event client for `~/.config/herdr/herdr.sock`. It emits dotted
  `events.subscribe` request types, rejects underscored broadcast names and malformed entries, and
  verifies the `subscription_started` acknowledgement before dispatching events.
- A single-purpose tracked subscriber process that holds the socket across turns and wakes the
  orchestrator pane through `agent.prompt`.
- Startup and reconnect catch-up through `session.snapshot`. It records `expected_state` versus
  `observed_state` disagreement and checks run-bound `artifact_path` presence without adding
  predicate wiring before predicate evaluation exists.
- `dispatch_revision_baseline`, the optional register column holding the pane revision sampled at
  dispatch. Run-and-child sentinels are honoured only at a later revision, preventing stale
  scrollback from satisfying a new interaction.
- A schema fixture captured from the installed herdr binary plus real Unix-socket tests for stream
  closure, reconnect, missed child exit recovery, and the remaining event-client error cases.

### Not in this release

- Session launching, readiness or reap transitions, predicate evaluation, routing, mirror
  behaviour, spend gating, hang detection, and the `/orchestrate` command.

## [0.1.0] - 2026-08-13

### Added

Initial scaffold (U2 of `docs/plans/2026-08-12-orchestrate-plugin-plan.md`). This ships the
plugin shape and the register only — the state model for a herdr-driven multi-vendor run, plus
the Claude<->Codex handoff seam (R12). Nothing else in the plan ships yet.

- `scripts/register.py`: a flat, global, `run_id`-keyed JSON register at
  `.orchestrate/register.json`, with atomic durable writes (temp sibling file, `fsync`, then
  `os.replace` — matching `run_ledger.py` and `manifest_store.py` elsewhere in this repository),
  an exclusive advisory lock around read-modify-write cycles so concurrent writers never lose
  each other's row, and a schema-version gate that halts with a durable receipt at
  `.orchestrate/halt-receipt.json` rather than mutating the register on an unsupported version
  (C3). Columns are grouped Identity / Substrate / Work / Lifecycle / Time / Accounting,
  documented in the module docstring.
- **Forward compatibility (C4) at both levels.** A key written by one runtime and unknown to the
  other survives a write by the other, whether it sits **inside a child row** or **at the
  document root**. Both matter to the handoff: rows are merged rather than replaced, and the
  loader preserves the document it read instead of rebuilding a known envelope, on both the
  upsert and the retire path. Genuinely optional columns stay absent rather than being seeded, so
  "unknown key" remains distinguishable from "known but unset" across the seam.
- **Retirement is idempotent.** Retiring a run moves its rows to
  `.orchestrate/runs/<run-id>/register-final.json` and leaves other runs untouched; retiring the
  same run again returns the existing archive rather than overwriting it. The durable copy is
  written before the live register is rewritten, so an interrupted retirement duplicates rows
  rather than losing them — and re-running it, which is the documented recovery, is safe.
- `skills/orchestrate/SKILL.md`: documents the register contract for later units to build against.
- `plugin.json` manifest and `README.md`.

### Not in this release

- The subscriber, `events.subscribe` client, session launching, predicate evaluation, spend
  gating, hang detection, routing, or the `/orchestrate` command itself. Those are later units
  (U3-U10) of the same plan.
