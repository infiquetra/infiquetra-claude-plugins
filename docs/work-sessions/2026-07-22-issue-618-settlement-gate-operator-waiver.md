# Work session: issue #618 — settlement-gate operator waiver

- **Date**: 2026-07-22
- **Issue**: infiquetra/infiquetra-claude-plugins#618 (defect)
- **Saga**: `issue-618` · outcome `governed-execution-integrity` leaf
  `leaf-governed-execution-integrity-sub-618`
- **Branch**: `work/618-settlement-gate-operator-waiver` (base `53cd65f5` = origin/main)
- **Plan**: `docs/plans/2026-07-22-issue-618-settlement-gate-operator-waiver-plan.md`
  (doc-review READY, zero open findings:
  `docs/reviews/2026-07-22-issue-618-settlement-gate-operator-waiver-plan-doc-review.md`)
- **Backend**: inline (recommended = chosen; recorded on the saga)

## What was built

- **U1 — waiver primitives** (`60828eab`): new `dispatch-waiver` run-fact kind in
  `run_ledger.FACT_KINDS`; `dispatch_settlement.blocking_roster` / `record_waiver` /
  `covering_waivers` / `active_waiver_covers`; closed waiver schema with its own canonicalizer;
  site-agnostic `waive` CLI subcommand (fact-field flag names). 14 new tests incl. the
  roster-empty ⇔ halt-false property pin through the late-delivery resolve.
- **U2 — gate integration + operator verb** (`ebb18782`): the frontier settlement gate
  (`outcome.py`) partitions halt-required reports into covered/uncovered; uncovered halts
  byte-identically (reason names only uncovered ids); a fully covered gate dispatches and appends
  one `settlement-waived` receipt per newly dispatched sid keyed
  `settlement-waiver:<sid>:<digest16>` (digest over sorted covering-waiver roster digests). New
  `outcome.py waive` verb with `approve`-style provenance (`--answerer` → `waived_by`). 3 gate
  scenario tests + CLI verb test; `FACT_KINDS` drift pin in `test_pulse_telemetry.py` updated.
- **U3 — release surfaces** (`8af39df2`): saga 0.108.0 → 0.109.0 (plugin.json,
  marketplace.json, `test_saga_plugin.py` pin), CHANGELOG entry, DECISIONS
  `{#settlement-waiver-618}` (KTD1–KTD5, rejected alternatives, #626 revisit condition).
  `check_release_surface_parity.py` clean.

## Key decisions during execution

- `blocking_roster` takes `(ledger, dispatch_id)` rather than the plan's literal
  `(report)` signature: `CasualtyReport.entries` keeps a late-delivered casualty's original
  classification while the halt derivation uses `latest_states` (delivered), so an entries-only
  roster would break roster-empty ⇔ halt-false. The report body was refactored into a shared
  `_report_and_roster(records, dispatch)` so roster and halt derive from the same computation —
  the drift risk the plan's own risk note flagged, closed structurally. Grant-time validation
  runs inside the ledger write lock (`append_fact_built_atomic` builder), so a settle racing the
  grant cannot stamp a stale roster.
- Gate-scenario tests live in `tests/test_outcome_dispatcher.py` (beside the sibling
  settlement-gate scenarios and their fixtures), not `test_outcome_command.py` as the plan
  guessed; the verb CLI tests live in `test_outcome_command.py`.

## Checks run

- Full battery at `8af39df2`: **5346 passed, 1 skipped**.
- `ruff check` + `ruff format --check`: clean. `mypy plugins/ scripts/ tests/`: clean.
- `bandit`: zero findings on the three touched scripts at both HEAD and the origin/main baseline.
- `python3 scripts/check_release_surface_parity.py`: all plugins in parity.

## Not done (deliberately)

- **R9 live acceptance** (waive the real
  `outcome:ee6590d89de1aff1cadb5e8c621b8b8b:frontier:6be9782deb6268350d4b9b36` cohort and
  advance sub-615) — held for its own explicit operator go; it mutates the live outcome ledger.
- PR open / review request / merge — gated per the intent envelope (all ceremony gates = `gate`).

## Next step

Programmatic `/code-review` gate at the branch head, then PR-ready routing to the operator.
