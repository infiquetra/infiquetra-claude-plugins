# Doc review: issue #615 plan — workflow-child lease binding

**Readiness: READY — all findings resolved.** D1 (the one open P1, an operator design decision)
was pinned by Jeff on 2026-07-22 to resolution (i) — mutation-path opportunistic renewal — and the
plan's R5, KTD4, U1, and Risk Analysis were updated to carry the pinned design. Everything else
was repaired in place during the review. Every cited anchor re-verified against the working tree
at `ee8a2b1a`, requirement→unit mapping complete, scope boundaries sound.

- **Target**: `docs/plans/2026-07-22-issue-615-workflow-child-lease-binding-plan.md`
- **Reviewed revision**: working tree at `origin/main` `ee8a2b1a` (plan uncommitted, authored this
  session)
- **Blocked**: no — `/work` may proceed (D1 resolved by operator decision 2026-07-22)
- **Linked**: issue infiquetra/infiquetra-claude-plugins#615 · saga `issue-615` · outcome leaf
  `leaf-governed-execution-integrity-sub-615`
- **External opinion**: engine offer consulted (`engine_offer.py offer --stage doc-review`) —
  stored preference, `intent: none`, no dispatch; no external findings to adjudicate.

## Verification performed

Every `path:line` anchor in the plan was re-read in this session against the working tree: claim
filter and fallback (`fleet_commons/lease_broker.py:2634`, `:2645`), recycle
(`:3811-3827`), terminal condition (`:3748-3754`), `renew_batch` contract (`:3704-3735`), claim
idempotency (`:2607-2625`), `assert_write_target` non-renewal (`:3000-3039`), attest's unstamped
invariant (`workflow_emitter.py:162-172`), reserve (`:118-130`), the saga adapter's five hook-facing
functions (`plugins/saga/scripts/lease_broker.py:262-378`), both hook adapters, `hooks.json` event
wiring, emitted TTLs (`execution_spec.py:3331-3332`), version-pin sites
(`tests/test_liveness_events.py:698`, `tests/test_team_execution_liveness.py:179`/`:409`), the
hook-adapter test suite (`tests/test_saga_hooks.py`), and the codex frozen copy's hook surface.

## Findings

| # | Priority | Status | Finding |
| --- | --- | --- | --- |
| D1 | P1 | **resolved — operator pinned (i), 2026-07-22** | KTD4/R5 keep-alive was event-starved under the emitted TTLs (`execution_spec.py:3331-3332`, 30s claim / 300s execution): a lone child >300s expires mid-unit; spare slots expire after 30 idle seconds in low-width phases. No renewal source fires during a workflow run (`assert_write_target` does not renew; `liveness_reping_hook` is #357 SendMessage liveness, not lease renewal). Jeff pinned resolution (i) — mutation-path opportunistic renewal in `assert_write_target` for batch-member leases, in-lock, fail-closed preserved, non-batch untouched (R2). Plan R5/KTD4/U1/Risk updated. |
| D2 | P2 | repaired | KTD2/R3 claimed flow-matching ("the claim matching the stamp's flow") that is impossible — `SubagentStart` lacks the parent tool-use id (#356 KTD4). Reworded to deterministic ordering with the strict-additivity rationale (stamped-first preserves today's selection byte-for-byte; unstamped binding activates only where today raises `LeaseNotFoundError`); cross-binding noted as pre-existing and pinned (`tests/test_saga_hooks.py:152`). |
| D3 | P3 | repaired | U3 overstated "no `hooks/` directory" in the codex frozen copy — it exists with `hooks.json` + `session_context.py`, just no lease hooks. Corrected. |
| D4 | P3 | repaired | KTD3's blast radius lacked a named regression pin — added `tests/test_saga_hooks.py:421` (`test_both_lifecycle_signals_are_required_in_either_order`) as a must-stay-green scenario in U1. |
| D5 | P3 | repaired | R9 canary sequencing was implicit — made explicit that the canary runs against the installed cache only after the plugin update installs 0.110.0/0.19.0. |
| D6 | P3 | repaired | U4 lacked the sibling-PR same-version collision guard — added the merge-time re-bump note (repo LEARNINGS precedent). |

## Applied fixes

Six in-place edits to the plan: R3 reword (D2), KTD2 reword (D2), U1 scenario reword + KTD3
regression pin (D2/D4), U3 codex wording (D3), R9 sequencing note (D5), U4 collision note (D6),
plus the D1 open-fork block added to Risk Analysis so `/work` cannot miss it.

## Residual risk from limited evidence

- **Session-identity propagation** (already the plan's named pre-mortem): whether Workflow
  children's `SubagentStart` payloads carry the root `session_id` is statically unprovable; the R9
  canary verifies it first, with the `INFIQUETRA_FLEET_BATCH_ID` override as the ready mitigation.
- The reviewer is the plan's author (same session); anchors were re-verified mechanically, but an
  independent-eyes pass at `/code-review` time remains the stronger check, per the normal gauntlet.
