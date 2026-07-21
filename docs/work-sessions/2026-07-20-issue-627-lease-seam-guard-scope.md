# Work session — issue #627 lease-seam and guard-scope defects

- **Date:** 2026-07-20
- **Issue:** [infiquetra/infiquetra-claude-plugins#627](https://github.com/infiquetra/infiquetra-claude-plugins/issues/627)
- **Branch:** `work/627-lease-seam-guard-scope` (from `origin/main` `83a170ff`)
- **Plan:** `docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md` (doc-review READY,
  artifact `docs/reviews/2026-07-20-issue-627-lease-seam-guard-scope-plan-doc-review.md`)
- **Execution vehicle:** cc-workflows-ultracode (operator-chosen), spec
  `docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-spec.json`, run `wf_82b39fe9-ab8`,
  invocation `bc0fcde8-b181-4215-ad9f-ee76322b9ee0` — U1→U2→U3→U4→U5 fully serialized,
  refute-3 verifier panels on U1/U2/U4 (worktree-isolated `saga:readonly-verifier`)

## What was built (by unit)

- **U1 (opus/high, panel 3-0 upheld):** opt-in `on_conflict` admission mode
  (`supersede` default | `refuse`) on `LeaseBroker.acquire_agent` /
  `_drop_superseded_resource_lease`, liveness via the existing `_expired` predicate, typed
  `LeaseConflictError` (subclass of `LeaseOwnershipError`) naming the live holder;
  `make_dispatcher` in `outcome_dispatcher.py` opts in; supersede/settlement precedence
  unchanged; dispatcher/broker prose de-overclaimed. KTD6 dispatch-identity determinism pinned.
- **U2 (opus/high, panel 2-1 upheld):** `except DispatcherError` arm in `_reconcile_once`
  beside the `BackendRateLimitError`/`BackendHaltError` arms — releases the per-subplot lease,
  appends a durable reducer-visible `(dispatch, halt)` record paired to the intent `key`,
  settles the attempt as `SILENT_NOOP` (closed vocabulary, no new member), continues the tick.
  Codex pin name mirrored (`test_advance_records_lease_refusal_as_halt_and_continues`). The one
  panel refutation was a true observation about pre-existing tree state (`ruff format --check`
  drift in `tests/test_saga_workflow_emitter.py`), not the unit's diff — fixed at the gate.
- **U3 (sonnet/medium):** the three receipt-spread halt appends (spend-gate, backend-menu,
  BackendHaltError arm) now spread first and set the literal `"kind": "dispatch"` last, with
  the receipt's own kind preserved as `receipt_kind`; dispatcher self-acknowledgment docstring
  retired; `test_outcome_report.py` `_halt` fixture spreads a real `HaltReceipt`; end-to-end
  halted-leaf visibility pinned through `advance()` → reducer → consolidated report.
- **U4 (opus/high, panel 3-0 upheld):** universal fail-closed ancestor walk in
  `outcome_compat._refuse_unsafe_handoff_ancestors` and
  `audit_store._refuse_unsafe_ancestors` — every existing component from the filesystem root,
  `lstat` never `resolve`, sole exemption world-writable **and** sticky (`S_ISVTX`);
  NFS/SMB/FAT32/exFAT shapes refuse with relocate guidance; tests driven through the real
  entry points (`Store.for_root(...).ensure()`, `resolve_common_dir`-derived `_write_once`)
  per the #624 lesson; group-writable acceptance twin added; "covers every caller" claim
  deleted from source.
- **U5 (sonnet/medium):** saga 0.107.0 + fleet-core 0.17.0 (plugin.json, marketplace.json,
  CHANGELOGs — the fleet-core entry explicitly corrects the 0.16.x "covers every caller"
  release note while leaving the historical line as history), drift-guard version pins updated
  in-commit, LEARNINGS entry on out-of-triad version pins, DECISIONS entry
  `{#lease-refuse-mode-and-universal-guard-627}` committed, codex follow-up defined at
  `docs/sdlc-issue-drafts/2026-07-20-codex-627-refreeze-and-worktree-lease-port.md`.

## Unplanned but load-bearing

The first live Workflow launch exposed a latent emitter defect: `execution_spec.py` emitted
`export const settlement` / `export const lease` after `export const meta`, and the Workflow
runtime rejects any `export` after the leading meta statement (`SyntaxError: Unexpected keyword
'export'`). Fixed in `44a5780f` (emitter + 3 test pins that had asserted the broken prefix).
See LEARNINGS `{#workflow-emitter-export-pins-627}`.

## Commits on the branch

1. `e0249de4` — plan, spec, emitted workflow, doc-review artifact, DECISIONS entry
2. `44a5780f` — emitter export fix + test-pin updates
3. `d2ab0b6d` — U5 release surfaces (amended in the session trailer)
4. `82d44465` — U1–U4 implementation + tests (786 insertions / 69 deletions, 13 files)

## Settlement and gates (all at `82d44465` unless noted)

- Post-run settlement: 5/5 units `delivered` attempt 1, 0 casualties, `halt_required: false`,
  DLQ empty, lease released (dispatch
  `workflow:2bf3fabdaa93188cd90a3d06:invocation:f3cf4f3fa551791db253bd48`).
- `uv run pytest -q`: **5318 passed, 0 failed, 1 skipped**
- `uv run ruff check .`: clean; `uv run ruff format --check .`: clean (2 files formatted)
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`: exit 0
- `uv run bandit -r plugins/`: no non-LOW findings in any changed file (all 6 HIGH / 25 MEDIUM
  pre-existing outside the diff)
- `python3 scripts/check_release_surface_parity.py`: all plugins in parity
- R7 gate: `grep -rn 'covers every caller' plugins/ --include='*.py'` → 0 matches
- Merge base re-verified: `git merge-base HEAD origin/main` = `origin/main` = `83a170ff`

## Next step

Run the Phase 5 programmatic `/code-review` gate at the branch head, then pause for operator
confirmation to open the PR (destination: merge; codex follow-up files via mission-control at
ship ceremony).
