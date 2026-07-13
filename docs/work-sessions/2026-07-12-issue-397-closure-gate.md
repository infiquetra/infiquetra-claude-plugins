---
title: Closure gate for /outcome (#397) — work session
date: 2026-07-12
issue: infiquetra/infiquetra-claude-plugins#397
plan: docs/plans/2026-07-12-closure-gate-plan.md
---

# Closure gate for /outcome (#397) — work session

## What was built

All 4 plan units landed, inline, single round:

- **U1** — `plugins/saga/scripts/closure_gate.py` (new): reads the merged evidence ledger (#398)
  for a node's declared `evidence.required_checks` and derives a typed `GateVerdict` — satisfied,
  or a named HALT (`missing-evidence:<id>`, `stale-sha:<id>`, `unresolved-fail:<id>`,
  `unsuperseded-fail:<id>`, `unrecognized-verdict:<id>`, `unresolvable-close-sha`,
  `chain-tamper:<id>`, `invalid-identity:<id>`). `evidence_ledger.py` gained one additive read
  helper, `history()`.
- **U2** — `outcome_orchestrator.harvest()`/`barrier_report()` wire the gate in: `harvest()` never
  writes a `done` completion event until the gate is satisfied; `barrier_report()` surfaces the
  gate's verdict under a `closure_gate` key per node. Both gained a defaulted
  `repo_root: Path = Path(".")`.
- **U3** — `plugins/saga/references/outcome-spec.md` documents the `Node.evidence` schema
  (`required_checks` / `reviewed_sha`) and the full HALT-reason vocabulary.
- **U4** — release surfaces: `plugin.json` 0.81.0 -> 0.82.0, `marketplace.json` regenerated,
  `CHANGELOG.md` entry, the pinned-version drift-guard test updated.

## Key decisions (mirrors the plan's KTDs + one found during implementation)

KTD1-KTD6 as planned (see the plan doc). **KTD7 (new, found during self-review):** the gate
classifies each verdict against its own closed vocabulary
(`_FAIL_VERDICTS = {FAIL, no-ship, blocked}` / `_PASS_VERDICTS = {PASS, ship, ship-with-deferred,
clean}`) rather than relying on `evidence_ledger.latest()`'s `superseded_fail` flag, which
hardcodes a literal `"FAIL"` sentinel the real shipped producers never write. Relying on the
literal sentinel would have silently satisfied the gate on a real `no-ship`/`blocked` verdict.

## Files modified

`plugins/saga/scripts/closure_gate.py` (new), `plugins/saga/scripts/evidence_ledger.py`,
`plugins/saga/scripts/outcome_orchestrator.py`, `plugins/saga/scripts/outcome.py`,
`plugins/saga/references/outcome-spec.md`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `tests/test_closure_gate.py` (new),
`tests/test_outcome_orchestrator.py` (new), `tests/test_evidence_ledger.py`,
`tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`,
`docs/engineering-journal/LEARNINGS.md`, `docs/evidence/leaf-evidence-integrity-sub-397/*`.

## Checks run

`pytest` (3378 passed, 1 skipped), `ruff check .` (clean), `ruff format --check .` (clean),
`mypy plugins/ scripts/ tests/ --ignore-missing-imports` (no issues, 192 files), `bandit -r` on
changed files (no findings). Every pre-existing `tests/test_outcome_*.py` file (11 files)
confirmed green, empirically verifying KTD6's backward-compatibility claim.

## Code review

Programmatic self-review found and fixed two P1 issues before PR-ready (see
`docs/evidence/leaf-evidence-integrity-sub-397/` for the full envelope, `check-id=code-review`,
`reviewed-sha=df68037528e9bb86b889ce93c423c14a013628d1`, verdict `clean`):

1. Verdict-vocabulary mismatch (real `/qa`/`/code-review` strings vs. the literal `"FAIL"`
   sentinel) — fixed (commit `2db7cd5`).
2. An uncaught `EvidenceLedgerError` on a malformed identity — fixed (commit `df68037`).

## Next step

Draft PR #568 is open on `work/397-closure-gate`. Push the full commit stack, confirm CI, and stop
at the PR-ready boundary — flipping ready-for-review, requesting review, and merging are explicit
operator-confirmation gates outside this work session's scope.
