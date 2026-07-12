# Doc Review — Issue #347 plan (ship ends in teardown)

One-line verdict: **READY** — no P0/P1 findings remain; three evidence-backed safe fixes were
applied in place, the sharpest being a sibling-session guard on the idle reclaim path.

## Review-result contract

- **Target**: `docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-plan.md`
  (companion spec `docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation-spec.json`,
  emitted `docs/plans/2026-07-11-issue-347-ship-teardown-reconciliation.workflow.js`)
- **Reviewed revision**: working tree on `main` at `ec85a0c` (plan/spec not yet committed)
- **Blocked**: no
- **Classification**: plan (content-shape + `docs/plans/` path); readiness-skeptic pass — the
  idea/issue rubric phases do not apply to a plan artifact
- **External engine offer**: `engine_offer.py offer --stage doc-review` returned stored
  preference `intent=none`, `prompt_required=false` — no external panel dispatched
- **Linked**: issue infiquetra/infiquetra-claude-plugins#347; saga `issue-347` (plan tick
  2026-07-12T03:15Z); outcome ship-ceremony-hardening sub-347

## Applied fixes

| # | Fix | Evidence |
|---|---|---|
| F1 | KTD8/U3/Risk: idle reclaim now applies the idle bound **per candidate worktree** (skip merged+clean worktrees with recent activity), closing the sibling-session race where a live session sitting clean on a just-merged head loses its cwd to another session's SessionStart hook | Failure mode derivable from the plan's own KTD6 skip conditions (dirty/unmerged only) + `plugins/saga/hooks/hooks.json` SessionStart running per session |
| F2 | U3: dropped the stale "(if present)" hedge — `tests/test_outcome_worktrees.py` exists (15.7K) | `ls tests/` |
| F3 | Spec/plan drift: spec U3 `files` gained `tests/test_reversibility_certificate.py`, and both plan and spec now state the new reversible op kind must land with its inverse descriptor | `tests/test_reversibility_certificate.py:241` `test_every_reversible_op_kind_has_registered_inverse` iterates the registry |

Spec re-validated (`execution_spec.py validate --require-receipts` OK) and workflow re-emitted
after F1/F3.

## Verification performed

Claims checked against live sources, not the author's memory: `ship_ceremony.py:124-163`
(TRANSITIONS ends at `branch_delete`; `next_transition` returns `None` — the R3 seam),
`outcome_worktrees.py:141/254/297` (register / reap keep-on-failure / harvest derive-on-read),
`reversibility_certificate.py:68-73` (`Tier.REVERSIBLE` exists) and `:239` (`authorize_write`
default-GATE), `board_progression.py:127` (authorize-every-op-kind pattern), `hooks.json`
(SessionStart block present, matcher shape), live `git worktree list` (17 worktrees, 11 from a
completed session + 4 agent worktrees — all unregistered, confirming KTD6's porcelain-sweep
rationale), saga plugin at 0.77.0. All six issue AC `-k` selectors map to named
`test_AC_<n>_<scenario>` tests across U1-U4; R1-R8 map onto U1-U5 with no orphans.

## Remaining findings

| # | Priority | Status | Finding |
|---|---|---|---|
| D1 | P3 | open | `TeardownBlockedError`'s owning module is unstated (natural reading: defined in `ship_teardown.py`, imported by `ship_ceremony.py` — a sensible default the implementer can take without asking) |

## Residual risk from limited evidence

- `outcome_worktrees.reap_worktree` takes an outcome `store`; mapping a swept `.saga-worktrees/`
  path back to its outcome store is left to U3's implementer (path structure
  `.saga-worktrees/<outcome>/<subplot>` makes this derivable; flagged here so the reviewer of U3
  checks it rather than assuming).
- Background sessions have no liveness oracle (KTD4 acknowledges this); the manifest's
  evidence-bearing `close` is the designed mitigation, not an omission.
