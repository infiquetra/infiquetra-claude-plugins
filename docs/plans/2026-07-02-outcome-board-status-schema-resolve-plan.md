---
title: Fix /outcome hardcoded board status — schema-resolve instead of "In Progress"
type: fix
status: active
date: 2026-07-02
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/326
---

# Fix /outcome hardcoded board status — schema-resolve instead of "In Progress"

## Summary

Replace the hardcoded `"In Progress"` board status in `/outcome`'s autonomous board-sync
(`plugins/saga/scripts/outcome_board_sync.py:130`) with a status resolved from mission-control's
canonical `sdlc-schema.json` for the target board, so the write is correct on the `intent_flow`
boards (operations, asgard) and on campps alike — and stays correct if a ladder or board changes.

## Problem Frame

`_candidate_ops` maps the `ready`/`dispatched` leaf states to `SET_FIELD_STATUS "In Progress"`, but
the default target board (operations, `outcome.py:451`) runs the `intent_flow` workflow
(`Idea → Shaping → Ready → Active → Verify → Done`) which has no `In Progress` status —
`"In Progress"` is a campps-workflow value. The write path is `--autonomous`-only and fail-loud, so
today this surfaces as a repeating failed board write. Upstream:
`infiquetra-context-library/docs/plans/2026-07-02-operations-board-followups-plan.md` Workstream A / U1
(cross-repo path; the doc-review for it is beside it under `docs/reviews/`).

**Issue verification (operator-requested).** All evidence claims in #326 were verified against the
code before planning:

- Confirmed: the hardcode at `plugins/saga/scripts/outcome_board_sync.py:130`; the
  `project="operations"` default at `plugins/saga/scripts/outcome.py:451` (and the call site at
  `outcome.py:642` passing no project at all); `outcome_dispatcher.py:147` setting
  `"status": "dispatched"`; the injected `board_writer` seam at `outcome_board_sync.py:151`;
  `workflows.intent_flow` canonical for operations + asgard with no `In Progress` status.
- Correction 1: `phase_board_map` is nested at `saga_lifecycle.phase_board_map` in
  `plugins/mission-control/config/sdlc-schema.json`, not top-level as the issue's path notation
  implies. Values are single-element lists per project (e.g. `work.operations = ["Active"]`).
- Correction 2: `tests/test_outcome_board_sync.py` already exists (the issue says "Add"). Its AE1
  test (`tests/test_outcome_board_sync.py:102`) asserts the buggy `"In Progress"` literal and must
  be corrected, not merely supplemented.

## Requirements

- R1. `_candidate_ops` carries no hardcoded board-status literal; the `ready`/`dispatched` statuses
  are resolved from `saga_lifecycle.phase_board_map` in
  `plugins/mission-control/config/sdlc-schema.json` for the target project.
- R2. Resolved values match the schema: on operations/asgard `ready → "Ready"`,
  `dispatched → "Active"`; on campps `ready → "Committed"`, `dispatched → "In Progress"`.
- R3. `done` (SUB_ISSUE_CLOSE) and the deferred no-op terminals (`blocked`/`failed`/`rejected`/
  `stalled`) are byte-for-byte unchanged in behavior.
- R4. The target project identity is defined once at the `advance` call site and threaded to both
  the board writer and the status resolver — the two can never disagree about the board.
- R5. Schema-resolution failure (file missing, unreadable, project absent from the map) is fail-loud
  and retryable: the status op records `{status: "failed"}` with no ledger key (next tick retries,
  R18-consistent); the schema-independent ops (progress comment, sub-issue close) still proceed.
  Never a silent skip; never a wedged tick.
- R6. Release surfaces updated in the same PR per repo policy: `plugins/saga/.claude-plugin/plugin.json`
  (patch bump from 0.49.0), `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, and any
  version-drift guard tests stay green.

## Key Technical Decisions

- KTD1 — Schema-resolve, not a literal `"Active"` swap: a literal re-breaks on the next ladder or
  board change and stays wrong for campps; resolving from `sdlc-schema.json` is correct for every
  board and deliberately decouples this fix from the Operations-ladder decision (Workstream B of the
  upstream plan / the sibling `infiquetra-sdlc-mainentance` issue).
- KTD2 — Leaf-state → lifecycle-phase mapping: `ready` (pre-dispatch, approved-awaiting-start) maps
  through the `review` phase row and `dispatched` (routed-and-running) through the `work` phase row
  of `phase_board_map`, taking the first (only) list entry per project. The schema's own review-row
  note ("the doc-review gate is the Ready→Active gate") confirms `ready` belongs on the pre-Active
  side. Consequence worth flagging: on campps, `ready` changes from `"In Progress"` to
  `"Committed"` — a behavior change beyond the operations fix, but it is the schema-correct value
  and exactly what "schema-resolve" means.
- KTD3 — Resolution locus and threading: a pure helper `_resolve_status_map(schema_path, project)`
  lives in `outcome_board_sync.py` beside its consumer; `reconcile_board` gains
  `project: str = "operations"` and `schema_path: Path | None = None` parameters. `schema_path=None`
  resolves to the module-file-relative default
  `Path(__file__).resolve().parents[2] / "mission-control" / "config" / "sdlc-schema.json"` — one
  derivation, one default; the cross-plugin reach itself follows the existing precedent at
  `outcome.py:465`. Resolution is **lazy** — attempted only when a `ready`/`dispatched` leaf
  actually needs a status (see U1 approach; an existing integration test depends on this). The
  caller (`outcome.py` `advance`) gains an optional `project: str = "operations"` parameter passed
  to both `_default_board_writer` and `reconcile_board` (R4); it does not construct the schema path.
  Rejected alternatives: resolving the map in `outcome.py` and injecting it — keeps
  `outcome_board_sync` schema-free but strands the mapping logic away from its consumer and makes
  the resolver untestable through the module's own seam; deriving `schema_path` from `repo_root` in
  `advance` — creates a second path source, and the existing `reconcile_board` unit tests (nine
  call sites in `tests/test_outcome_board_sync.py` passing no schema path, stores under `tmp_path`)
  would all need threading edits for no behavioral gain.
- KTD4 — Failure mode is per-op fail-loud, not tick-fatal: mirrors the module's existing
  ledger-fault stance (`outcome_board_sync.py:284-289`) — a schema problem must not wedge the tick
  or discard the records gathered so far, and must leave the op retryable (no ledger key written).

## Implementation Units

### U1. Schema-resolved status in `_candidate_ops` + project threading

Replace the hardcoded literal with the schema-resolved status map and thread the project identity
from `advance` down to both writer and resolver.

**Goal:** `ready`/`dispatched` board statuses come from `saga_lifecycle.phase_board_map` for the
target project; one `project` source at the call site.

**Requirements:** R1, R2, R3, R4, R5.

**Dependencies:** none.

**Files:** `plugins/saga/scripts/outcome_board_sync.py` (modify: `_candidate_ops`,
`reconcile_board`, new `_resolve_status_map`); `plugins/saga/scripts/outcome.py` (modify: `advance`
signature and the `reconcile_board`/`_default_board_writer` call site at `outcome.py:642-644`);
tests in `tests/test_outcome_board_sync.py`.

**Approach:** per KTD2/KTD3. `_candidate_ops(state, status_map)` becomes pure over the resolved
map; `_resolve_status_map` reads the schema JSON and returns
`{"ready": <status>, "dispatched": <status>}` or raises a descriptive error that `reconcile_board`
converts into per-op `failed` records (KTD4). Resolution must stay lazy — attempted only when a
`ready`/`dispatched` leaf is present: `test_advance_autonomous_drives_board_sync`
(`tests/test_outcome_board_sync.py:399`) runs the real `advance` against a bare tmp git repo with
no schema file and only a `done` leaf, and must keep passing untouched. The
`ISSUE_PROGRESS_COMMENT` coalescing, `done` handling, and negative-terminal no-ops are untouched
(R3).

**Patterns to follow:** lazy-import/pure-function house pattern already in
`outcome_board_sync.py:9-11`; cross-plugin path construction at `outcome.py:465`; the recording-fake
`board_writer` test pattern at `tests/test_outcome_board_sync.py:84`.

**Test scenarios** (extend/correct `tests/test_outcome_board_sync.py`):

- Correct existing AE1 (`:102`): a `ready` leaf on the default (operations) board records
  `target_state == "Ready"`, not `"In Progress"`.
- Update the direct-call signature test `test_candidate_ops_negative_terminals_and_blocked_emit_no_op`
  (`tests/test_outcome_board_sync.py:564`): it calls `_candidate_ops(state)` with the old one-arg
  signature and must pass a status map; its assertions (negative terminals → no ops, live states →
  ops) are unchanged.
- Happy path: a `dispatched` leaf on operations → `"Active"`; parametrize project over
  `asgard → "Active"` and `campps → "In Progress"`.
- Behavior-change lock: a `ready` leaf on campps → `"Committed"` (KTD2 consequence, asserted
  deliberately).
- Unchanged paths: `done` still emits SUB_ISSUE_CLOSE with empty target; a negative-terminal state
  still emits no ops.
- Error path (R5/KTD4): nonexistent `schema_path` → the status op records `{status: "failed"}`,
  no ledger key is written, the progress comment still posts, and a subsequent reconcile with a
  valid path succeeds (retryability).
- Error path: a project absent from `phase_board_map` → same failed-record semantics.
- No-literal guard: assert the resolved map is sourced from the real
  `plugins/mission-control/config/sdlc-schema.json` (run `_resolve_status_map` against the real
  file in-repo) and that `outcome_board_sync.py`'s source contains no `"In Progress"` literal.

**Verification:** full `uv run pytest tests/test_outcome_board_sync.py` green; existing
`test_outcome_*.py` suite unaffected; on-board semantics match R2 exactly.

### U2. Release surfaces + engineering journal

Ship the installed-plugin metadata and the decision record in the same PR.

**Goal:** plugin metadata tells the same story as the diff (repo policy), and KTD1/KTD2 land in the
canonical decision record.

**Requirements:** R6.

**Dependencies:** U1.

**Files:** `plugins/saga/.claude-plugin/plugin.json` (0.49.0 → 0.49.1),
`.claude-plugin/marketplace.json` (matching version), `plugins/saga/CHANGELOG.md`,
`tests/test_saga_plugin.py:48` (the version literal is pinned there and must be bumped in step),
`docs/engineering-journal/DECISIONS.md` (plan-time entry `{#outcome-board-status-schema-resolve-326}`
already exists — confirm/extend it if implementation deviates rather than adding a duplicate).

**Approach:** patch bump — bug fix, no schema/command surface change. CHANGELOG entry names the
behavior change on campps explicitly so an operator reading release notes is not surprised.

**Test expectation:** none — release-surface metadata; the existing version-drift guard tests are
the check.

**Verification:** drift-guard tests green; `plugin.json` and `marketplace.json` versions match.

## Scope Boundaries

- Out of scope: the Operations-ladder decision and any live-board remap (Workstream B/U2-U3 of the
  upstream plan — an operator-owned ADR in the sibling issue). This fix is deliberately
  ladder-agnostic (KTD1).
- Out of scope: board ops for `blocked`/`failed`/`rejected`/`stalled` (deferred non-goal carried
  forward from the original board-sync plan).
- Out of scope: making `project` operator-configurable end-to-end (a CLI flag on `/outcome`
  commands). `advance` gains the parameter with the current default; exposing it is follow-up work
  if a non-operations outcome campaign materializes.
- Not a non-goal but noted: the campps `ready → "Committed"` change ships here as a consequence of
  schema-resolution (KTD2), asserted by test and called out in the CHANGELOG.
