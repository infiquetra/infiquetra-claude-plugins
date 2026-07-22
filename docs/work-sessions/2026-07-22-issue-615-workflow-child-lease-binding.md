# Work session: issue #615 — workflow-child lease binding

- **Date**: 2026-07-22
- **Issue**: infiquetra/infiquetra-claude-plugins#615 (defect, high-priority)
- **Saga**: `issue-615` · outcome `governed-execution-integrity` leaf
  `leaf-governed-execution-integrity-sub-615`
- **Branch**: `work/615-workflow-child-lease-binding` (base `ee8a2b1a` = origin/main)
- **Plan**: `docs/plans/2026-07-22-issue-615-workflow-child-lease-binding-plan.md`
  (doc-review READY after the operator pinned D1 to resolution (i):
  `docs/reviews/2026-07-22-issue-615-workflow-child-lease-binding-plan-doc-review.md`)
- **Backend**: inline (operator-confirmed; recommender said team-execution — divergence recorded
  on the saga). Engine offer (work stage): advisory-only, unknown unit shape, no dispatch.

## What was built

- **U1 — fleet-core broker** (`15c15938`): `claim` accepts attested-but-unstamped batch slots
  with stamped-first ordering (`(unstamped-last, fencing_sequence, lease_id)`; non-batch
  candidate set and ordering byte-identical); `record_child_terminal` recycles an unstamped
  batch slot on the child signal alone (stamped slots keep the dual-signal contract); new
  `_renew_live_batch_siblings` keep-alive fires in-lock at claim/terminal, and
  `assert_write_target` opportunistically renews a mutating batch-member lease plus live
  siblings via `_renew_batch_member` (D1 resolution i — renewal scales with real activity,
  expired slots never resurrected). 9 new broker tests + the e2e workflow-child lifecycle test
  (`tests/test_saga_workflow_emitter.py::test_workflow_child_binds_without_pretool_stamp_and_waves_recycle`:
  reserve → attest → full-width SubagentStart claims with zero PreToolUse stamps → per-child
  mutation verification → child-terminal recycle → second wave → release settles clean).
- **U2 — saga hooks kill-switch** (`2026b45d`): both lease hooks honor
  `INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off` (exact string only, loud stderr notice, zero broker
  I/O when disarmed; anything else stays armed). 2 new hook tests (bypass + 5-value armed
  parametrization).
- **U3 — verification-only** (this doc): (a) the codex frozen saga copy carries no lease hooks
  (`hooks/` = `hooks.json` + `session_context.py` only) and this PR does not touch
  `plugins/saga/scripts/lease_broker.py` — codex re-freeze impact is nil, rides codex#45
  unchanged; (b) the `/work` workflow-launch choreography needs no edit — the driver protocol
  (`reserve`/`attest`/`renew`/`release`) is byte-unchanged.
- **U4 — release surfaces** (`beeba844`): fleet-core 0.18.0 → 0.19.0, saga 0.109.0 → 0.110.0
  (plugin.json ×2, marketplace.json), both CHANGELOGs, drift pins (`tests/test_saga_plugin.py`,
  `tests/test_liveness_events.py`, `tests/test_team_execution_liveness.py` ×2), DECISIONS
  `{#workflow-child-lease-binding-615}` (KTD1–KTD6, rejected alternatives, revisit
  conditions). Plus `d7ae3efc` style fixup: ruff format on the new broker tests.

## Key decisions during execution

- The stamped-first ordering key neutralizes its stamp term for non-batch claims
  (`batch is not None and lease.tool_use_id is None`) so R2's byte-identical guarantee holds
  literally — non-batch mixed stamped/unstamped ordering is pinned by
  `test_non_batch_claim_ordering_ignores_stamp_state`.
- `_renew_batch_member` re-reads the lease under the broker lock and skips renewal when the
  lease is gone, rebound, non-batch, or expired — the unlocked `verify_agent` read can go stale
  between verification and renewal, and renewal must never resurrect.
- Bandit reports 5 pre-existing severity-Low subprocess findings (B404/B603/B607) in
  `lease_broker.py` — identical count at the `ee8a2b1a` baseline; zero new findings.

## Checks run

- Full battery at `d7ae3efc` (post-format head): **5364 passed, 0 failed, 1 skipped**.
- `ruff check` clean; `ruff format --check` clean (one drift caught locally and fixed —
  the same class CI caught on #618).
- `mypy plugins/ scripts/ tests/ --ignore-missing-imports`: clean.
- `bandit` on the three touched scripts: no new findings vs baseline.
- `python3 scripts/check_release_surface_parity.py`: all plugins in parity.

## Next step

Programmatic `/code-review` gate, then PR-open/merge under operator confirmation. **R9 live
acceptance is post-merge + post-plugin-update, operator-gated**: with ARMED installed hooks
(saga 0.110.0 + fleet-core 0.19.0 in the plugin cache), a one-agent canary workflow performs a
`Write` end-to-end and a direct unadmitted `Agent` spawn is still refused — passing retires the
per-launch hook-neutralization ritual (memory `workflow-lease-hooks-neutralized-615` → historical).
