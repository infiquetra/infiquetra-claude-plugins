# Doc Review — /outcome board status schema-resolve plan

Ready to drive implementation: three evidence-backed gaps were fixed in place, no P0/P1 findings
remain, and the plan is not blocked.

## Review-result contract

**Target:** `docs/plans/2026-07-02-outcome-board-status-schema-resolve-plan.md`

**Reviewed revision:** working tree (plan not yet committed; repo at `373219a`).

**Blocked:** no.

**Linked issue:** infiquetra/infiquetra-claude-plugins#326. **Saga:** `issue-326` (plan phase,
destination merge, backend inline).

**Classification:** plan (`docs/plans/` path + `origin:`/`Implementation Units`/KTD/U-ID signals).
The rubric engine's phases (idea/issue/spec) do not cover plan artifacts, so the readiness-skeptic
pass ran directly.

## Applied fixes

Three fixes, each supported by direct repository evidence, edited the plan in place.

| # | Fix | Evidence |
|---|-----|----------|
| 1 | KTD3/U1: pinned `schema_path=None` to a module-file-relative default and made lazy resolution an explicit requirement; `advance` threads only `project`, never a second path source | Nine `reconcile_board` call sites in `tests/test_outcome_board_sync.py` pass no schema path with `tmp_path` stores; `test_advance_autonomous_drives_board_sync` (`:399`) runs the real `advance` against a bare tmp git repo (no schema file, `done`-only leaf) and must keep passing untouched |
| 2 | U1 test scenarios: added the required update to `test_candidate_ops_negative_terminals_and_blocked_emit_no_op` (`tests/test_outcome_board_sync.py:564`), which calls `_candidate_ops` with the old one-arg signature | Direct call at `:570-575`; the plan changes the signature to `_candidate_ops(state, status_map)` |
| 3 | U2 files: added `tests/test_saga_plugin.py:48`, which pins the saga version literal (`"0.49.0"`) and must be bumped with the release surfaces; clarified the DECISIONS entry already exists at plan time (extend, don't duplicate) | `tests/test_saga_plugin.py:48-49` asserts both the literal and plugin/marketplace parity |

## Readiness summary

The plan's load-bearing evidence was verified at plan time and re-checked here: the hardcode
(`outcome_board_sync.py:130`), the writer default (`outcome.py:451`) and bare call site
(`outcome.py:642`), the dispatcher state string (`outcome_dispatcher.py:147`), and the nested
`saga_lifecycle.phase_board_map` values for all three boards. One additional de-risking fact
surfaced during review: the `plan` and `review` phase rows resolve to identical statuses on every
board (`Ready`/`Ready`/`Committed` for operations/asgard/campps), so KTD2's choice of the `review`
row cannot produce a wrong status even if the phase-mapping judgment were contested. Requirements
map cleanly to units (R1-R5 → U1, R6 → U2); failure modes are enumerated with retryable semantics;
the campps `ready → "Committed"` behavior change is pinned, tested, and CHANGELOG-flagged.

## Remaining findings

| Priority | Finding | Status |
|----------|---------|--------|
| P3 | Ledger-key drift on mid-flight outcomes: previously-written `"In Progress"` idempotency keys will not match the new `"Ready"`/`"Active"` keys, so an in-flight outcome re-fires the status write once with the corrected value. Benign — at-least-once semantics, and the re-fire corrects the board. No plan change needed; implementer awareness only. | open (informational) |
| P3 | Stale comment at `tests/test_outcome_board_sync.py:244` cites `"In Progress"` as the SHA-1-fallback example for keys with spaces; the new status values contain no spaces. Refresh the comment during U1. | open |

## Residual risk from limited evidence

The live Operations board's actual Status options were not re-queried during this review; the
upstream plan's 2026-07-02 census (`Todo ×20, Done ×3`, drifted from declared `intent_flow`) is the
latest evidence. If the live board still lacks the `intent_flow` options, the schema-resolved write
of `"Ready"`/`"Active"` will fail loudly (fail-loud path, retryable) until Workstream B re-conforms
the board — an explicitly decoupled, out-of-scope dependency (plan KTD1 / Scope Boundaries). This
does not change plan readiness: the fix is correct against the canonical schema either way.
