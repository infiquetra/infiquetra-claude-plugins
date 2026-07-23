# Doc review — issue #644 async PostToolUse race plan

**Target:** `docs/plans/2026-07-23-issue-644-async-posttooluse-race-plan.md` (+ companion spec
`docs/plans/2026-07-23-issue-644-async-posttooluse-race-spec.json`)

**Reviewed revision:** working tree at main `277f070d` (plan authored and reviewed same session)

**Verdict: ready.** One P1 was found and repaired in place (plan + spec amended, spec re-validated
with `--require-receipts` and re-emitted). No blocking findings remain. **Blocked: no.**

Linked: issue infiquetra/infiquetra-claude-plugins#644 · saga `issue-644` (lifecycle-phase plan,
destination merge, orchestration cc-workflows-ultracode)

## Verification basis

Every load-bearing anchor was re-verified against source this session, not carried from memory:
broker `record_parent_completed` :3895-3929 (kill branch :3913, stamp-and-keep :3922-3923,
admission pop :3924-3927), `_session_has_live_agents` :1952-1964 (counts any unexpired agent lease
— the plan's "admission half fixes itself" invariant holds), `_expired_static` :1987-1991,
`claim` :2609-2719 (`replace` :2696-2706 preserves `parent_completed_at`; candidate filter
:2655-2664 does not exclude stamped leases), `record_child_terminal` :3857-3893 (dual-signal
:3873), `_complete_foreground_lease` :3931-3961, `settle_batch` :3782-3822,
`DEFAULT_CLAIM_TTL_SECONDS = 30` :38; adapter `reserve_hook_agent` :302-351 (reserves at claim TTL
:313/:340), `record_hook_parent` :379-394 (ignores `hook_event_name` today — full payload is
delivered by `lease_lifecycle_hook.py` dispatch :67-68, observational posture :77-78); every
`parent_completed_at` reader enumerated (:172, :854, :934, :963, :2133, :3810, :3873, :3912,
:3956) — the settlement reader at :3810 produced D1. Tests the plan pins for update
(`test_unclaimed_failed_parent_releases_reservation` :528, session-scoping :534) and the
conformance truth-set (call-name only) confirmed. Formal rubric engine not run — plan-phase
artifact; readiness-skeptic pass applies.

## Findings

| ID | Priority | Status | Finding |
|---|---|---|---|
| D1 | P1 | **fixed** | `settle_batch` :3803-3812 releases only unclaimed-**and-unstamped** or claimed-and-dual-signal slots. The plan's new surviving state (stamped-unclaimed, parent signal recorded) matched neither arm, so an abandoned stamped slot would leak an expired lease past batch settlement — today's eager recycle (reset to unstamped) is precisely what made it drainable. KTD4's original "no special-casing needed" claim was wrong. **Fix applied:** KTD4, R6, and U1 (goal + test scenario g) amended in the plan; spec U1 prompt amended; spec re-validated + re-emitted. The added arm — release an unclaimed slot with `parent_completed_at` set — is settlement-time-only, so mid-run wave slots awaiting children (no parent signal yet) are unaffected. |
| D2 | P2 | open | Crossed-claim hazard: `claim()` binds the **oldest** compatible reservation (:2673-2679, fencing-sequence order). A surviving stamped reservation whose child never arrives can, within its ≤30 s TTL, be claimed by the **next** spawn's SubagentStart of the same agent type — the new child inherits the stale reservation's `isolation`/`tool_use_id` (fence mismatch possible). Partially pre-existing (a reservation that never receives any PostToolUse event lingers identically today); the fix widens it only to the plain-PostToolUse-then-no-child case, which async launch semantics make rare. Recommendation: U1 adds a test pinning current oldest-first behavior and the work-session doc records the residual; a design mitigation (e.g. claim preferring reservations without a parent stamp) touches #616 claim-policy territory — operator's call to fold in or defer. |
| D3 | P3 | open | "`PostToolUseFailure` fires for never-started spawns" is not live-verified. The design does not depend on it firing — if it never fires, the eager path is simply unused and abandoned reservations expire by the 30 s TTL (safe degradation). Record the observation in the R8 canary notes if a failure event is captured. |
| D4 | P3 | open | U1 scenario (f) (expired-reservation accounting) requires clock/monotonic manipulation; the suite has TTL-test precedent to follow — implementation detail, no plan change needed. |

## Spec/plan consistency

U-IDs, tiers (opus/high · sonnet/high · sonnet/medium), serialized `depends_on` U1→U2→U3, refute-3
panels on U1/U2, and the U1 worth-it receipt all match between plan and spec; post-fix spend
unchanged at 128/48/6 = 182. The emitted workflow carries `dispatch_settlement.v1` +
`workflow_lease_reservation.v1` (width 3, session_limit 3, `requires_prelaunch_reservation: true`).

## Residual risk

The reviewer is the plan's author (same session) — independence is limited; the refute-3 panels on
U1/U2 at execution time and the operator-gated R8 live canary are the compensating controls. D2 is
accepted-open unless the operator folds the mitigation in.
