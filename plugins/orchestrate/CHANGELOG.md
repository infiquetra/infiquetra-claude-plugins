# Changelog

## [0.1.0] - 2026-08-13

### Added

Initial scaffold (U2 of `docs/plans/2026-08-12-orchestrate-plugin-plan.md`). This ships the
plugin shape and the register only — the state model for a herdr-driven multi-vendor run, plus
the Claude<->Codex handoff seam (R12). Nothing else in the plan ships yet.

- `scripts/register.py`: a flat, global, `run_id`-keyed JSON register at
  `.orchestrate/register.json`, with atomic read/write (temp file + `os.replace`), an exclusive
  advisory lock around read-modify-write cycles so concurrent writers never lose each other's
  row, forward-compatible rows (an unknown key nested inside a child row, written by one runtime,
  survives a write by the other — C4), and a schema-version gate that halts with a durable
  receipt at `.orchestrate/halt-receipt.json` rather than mutating the register on an
  unsupported version (C3). Columns are grouped Identity / Substrate / Work / Lifecycle / Time /
  Accounting, documented in the module docstring.
- `skills/orchestrate/SKILL.md`: documents the register contract for later units to build against.
- `plugin.json` manifest and `README.md`.

### Not in this release

- The subscriber, `events.subscribe` client, session launching, predicate evaluation, spend
  gating, hang detection, routing, or the `/orchestrate` command itself. Those are later units
  (U3-U10) of the same plan.
