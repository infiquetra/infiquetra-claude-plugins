# Work session — board_progression shared writer (#344)

- **Date:** 2026-07-05
- **Issue:** #344 (Phase 0 item 6, execution-order row 6) — objective #332 (intent envelope)
- **Plan:** `docs/plans/2026-07-05-board-progression-shared-writer-344-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-board-progression-shared-writer-344-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-05-board-progression-344-code-review.md`
- **Backend:** inline. **Driver:** autonomous Phase 0 (Opus/xhigh).

## What shipped

Extracted `/outcome`'s certificate-gated autonomous board writer into a plugin-agnostic
`board_progression.py`, wired `/work` (post-merge) and `/loop` (render) as consumers, and added a
derived `project_arc` lifecycle renderer — widening *who writes* without widening *what may be written
autonomously* (the allowlist stays in `reversibility_certificate`).

- **U1** `board_progression.py` — `authorize_and_write` per-op primitive + own `_write_once`/
  `_safe_ledger_name` + moved-in `default_board_writer` + a `write` CLI (skill-invokable).
- **U2** `reconcile_board` delegates to it (zero behavior diff; `outcome_store._write_once` injected;
  helper surface re-exported so `outcome_reconcile` is untouched).
- **U3** `status_card.project_arc` — gate-sequence idea→deploy arc, pure over durable saga fields.
- **U4/U5** `/work` post-merge fires the allowlisted moves via the CLI; `/loop` renders the arc and
  sequences (never writes — router principle, KTD3).
- **U6** release surfaces: saga 0.56.0 → **0.57.0**, marketplace regenerated, CHANGELOG, version literal.

## Findings resolved mid-build (small, fixed inline — no filing)

1. **Doc-review P1 (skill→CLI seam):** the plan defined only a library function; markdown skills
   invoke CLIs. Added the `write` CLI + moved `default_board_writer` into the shared module (KTD6).
2. **Doc-review P1 (helper stranding):** `outcome_reconcile:256` consumes 5 `outcome_board_sync`
   helpers incl. `_safe_ledger_name`; re-exported it so nothing strands.
3. **Impl (test-patchability):** the ledger-fault test monkeypatches `outcome_store._write_once`;
   made `write_once` an injected dependency (default = own; `/outcome` injects `outcome_store`'s) to
   preserve zero-behavior-diff *and* plugin-agnosticism.
4. **Impl (phantom mypy):** partial-scope `mypy` reported a false `dict(HaltReceipt)` overload error;
   full CI-scope run is clean. Lesson: validate type errors at CI scope.

## Gates

`pytest` 2012 passed (16 new); `ruff check` + `ruff format --check` clean; full-scope `mypy` clean;
release-surface parity + diff-guard green.
