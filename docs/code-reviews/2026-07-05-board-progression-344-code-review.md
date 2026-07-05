# Code-review (programmatic gate) — board_progression shared writer (#344)

- **Scope:** `feat/pf-board-progression-shared-writer-344` vs `origin/main` (U1–U6).
- **Mode:** programmatic inline gate (no agent spawn), backend inline.
- **Verdict:** PASS — no P0/P1. Not blocked; PR-ready.

## Lenses applied

| Lens | Finding |
|---|---|
| Extraction fidelity (zero behavior diff) | PASS — 60 `test_outcome_board_sync`/`test_outcome_reconcile` tests pass unchanged; per-op record shapes match key-for-key; `outcome_store._write_once` injected as `write_once` so the ledger-fault monkeypatch (`test_ledger_write_fault_surfaces_not_wedges`) still fires. |
| Import structure | PASS — `board_progression` depends only on `reversibility_certificate` (lazy); `outcome_board_sync`/`outcome` lazily re-export from it. One-directional, no cycle. |
| Autonomy / security (KTD2) | PASS — every op routes through `authorize_write` before any writer call; merge/deploy/unknown op-kinds default-GATE; `PARENT_ISSUE_CLOSE` ALWAYS_OPERATOR→GATE. A consumer cannot widen the allowlist. CLI uses `subprocess.run` with a list arg (no shell), op validated pre-dispatch. |
| Derived-on-read purity (KD4) | PASS — `project_arc` reads only `saga_obj` durable fields via `getattr`; render determinism asserted (AE5). No board Status/cache/ledger read for glyphs. |
| Router-principle (KTD3) | PASS — `/loop` doc wires render + sequencing only; the autonomous write fires from `/work`'s post-merge path. |

## Findings

| Priority | Finding | Status |
|---|---|---|
| P3 | The CLI write-record ledger under `.claude/saga/board-progression` grows unbounded (write-once idempotency keys). | Open — by-design parity with `/outcome`'s `store.root/board-sync` ledger; not a regression. No action. |

## Gates

Full CI-parity gate green pre-PR: `pytest` 2012 passed (16 new), `ruff check` + `ruff format --check`
clean, full-scope `mypy plugins/ scripts/ tests/` clean, release-surface parity + diff-guard green.
