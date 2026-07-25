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

## Shipped (2026-07-22, operator go)

- PR #640 opened at `0f7138a6`, CI caught one ruff-format drift in `tests/test_saga_plugin.py`
  (the finding-7 comment repair shortened the pinned assertion below the wrap threshold) —
  fixed in `4f830e1c`; pre-merge delta (`0f7138a6` + `4f830e1c` + `737e6c29`) adjudicated
  clean in the code-review artifact. All checks green at `737e6c29`; merged via
  `ship_ceremony` (operator-confirmed) as `82761c1e`; branch deleted; issue #618 auto-closed
  completed; Operations board card → Done.
- Leaf harvest: `link-pr` PR #640 to `sub-618`, `leaf_saga_id` set in the spec, `code-review`
  evidence entry (verdict `clean`) at close SHA `737e6c29` under
  `leaf-governed-execution-integrity-sub-618`; `advance` harvested sub-618 → **done** (2/9).

## R9 live acceptance — PASSED (2026-07-22)

Against the real halted cohort, on branch `outcome/governed-execution-integrity` (main merged
in to pick up the shipped verb):

1. Post-harvest `advance` still settlement-halted sub-615 on
   `outcome:ee6590d89de1aff1cadb5e8c621b8b8b:frontier:6be9782deb6268350d4b9b36` — the defect
   reproducing one final time on the shipped code.
2. `outcome.py waive governed-execution-integrity --dispatch-id <that cohort> --answerer jeff`
   → `appended: true`, roster_digest `7a2fa898…82f39a0`.
3. Next `advance` → `dispatched: ["sub-615"]`, zero halts, and exactly one `settlement-waived`
   receipt in the outcome ledger: key `settlement-waiver:sub-615:217cf0830d409451`, naming the
   covered dispatch_id and full waiver provenance (`waived_by: jeff`, reason, roster digest).
