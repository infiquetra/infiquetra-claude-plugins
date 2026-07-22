# Work session — issue #637 refuse-mode hardening: workflow run completed

- **Saga**: `issue-637` · branch `work/637-refuse-mode-hardening` (from `origin/main` `47dacede`)
- **Plan**: `docs/plans/2026-07-21-issue-637-refuse-mode-hardening-plan.md` (doc-review READY)
- **Backend**: `cc-workflows-ultracode` (operator-chosen) · run `wf_36c601cc-5a6`, invocation
  `98d9b60a-db43-4608-9f45-9fb95b100563` — relaunch after the halted `wf_881dd2cb-fa1`
  (see `2026-07-21-issue-637-work-halt-stale-hooks.md` for the halt forensics and #615 linkage)

## Execution

Serialized U1→U2→U3, 9 agents (3 units + refute-3 panels on U1/U2), 0 errors, ~57 min,
473k subagent tokens. Run was **ungoverned** per operator decision (installed lease hooks were
the #615 neutralization no-ops; canary `wf_428d7af7-c5a` proved child mutation first).

- **U1** (opus/high): pid-liveness at the refuse-mode admission gate —
  `_drop_superseded_resource_lease` refuse branch now ANDs
  `self._owner_state(prior_lease) != "dead"` (`fleet_commons/lease_broker.py:2175-2184`):
  provably dead owner supersedes with no TTL wait; live AND unknown refuse fail-closed; no
  same-owner bypass. 6 tests (dead-orphan, live, unknown pid-None, unreadable identity,
  same-owner-live, reboot). Verify panel: 3/3 upheld, zero refutations.
- **U2** (opus/high): `DispatcherLeaseTransientError(DispatcherError)` + shim-safe
  `_lease_conflict_error_type()` in `outcome_dispatcher.py`; lease-lifecycle raise sites
  reviewed site-by-site emit the transient subclass; `_reconcile_once` (`outcome.py`) keeps
  halt-and-continue for transient and aborts the tick loudly on any other `DispatcherError`.
  Verify panel: 3/3 upheld, zero refutations.
- **U3** (sonnet/medium): fleet-core 0.17.0→0.18.0, saga 0.107.0→0.108.0, marketplace sync,
  both CHANGELOGs, drift-guard pins (`test_saga_plugin.py`, `test_liveness_events.py`,
  `test_team_execution_liveness.py`). `check_release_surface_parity.py`: parity.

## Settlement + governance tail

- Dispatch `workflow:922e7a2d96eb74d4d21b6b48:invocation:56e348b402296b298db3773c`:
  U1/U2/U3 all settled `delivered` ("all expected deliverables present"), 0 casualties,
  `halt_required: false`, DLQ empty. Evidence under
  `.saga/workflow-evidence-98d9b60a-…/` (hash chain tail `50aa32bb0a7c…`).
- Lease release: `released_lease_ids: []` — consistent with the ungoverned run (no lease was
  ever bound; the reservation record is closed).
- **Armed hooks restored** from `*.orig-2026-07-22` in
  `~/.claude/plugins/cache/infiquetra-plugins/saga/0.107.0/hooks/` — verified byte-identical
  to repo 0.107.0 hooks (operator-chosen post-run posture; #615 remains the fix-for-real).

## Phase 3 gates (all green at `e86a4b45`)

- `uv run pytest -q`: **5329 passed, 1 skipped**
- `uv run ruff check .` + `uv run ruff format --check .`: clean (437 files)
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`: clean
- `uv run bandit -r plugins/`: no new findings — all 6 high-severity hits are vendored
  `.venv` third-party code or the pre-existing `board_progression.py:56` SHA1, untouched here

## Commit

`e86a4b45` — 14 files, +382/−29. Excluded from staging: operator's dirty
`docs/outcomes/external-engine-offload/report.md`, untracked `docs/sdlc-issue-drafts/*`,
untracked `.saga/`.

## Next

Phase 5 code-review gate at REVIEWED_SHA `e86a4b45` (hard gate on P0/P1 + staleness), then
PR-ready boundary; merge only under explicit operator confirmation.
