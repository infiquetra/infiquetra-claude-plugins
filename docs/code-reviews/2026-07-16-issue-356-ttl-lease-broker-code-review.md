# Code Review — Issue #356 TTL Lease Broker

## Verdict

> **BLOCKED.** The implementation is scope-complete and its current quality gate is green, but the
> pinned revision has two data-loss defects, nine other P1 lifecycle/admission defects, and required
> concurrency/event-flow evidence gaps. No PR or merge is allowed until every finding below is fixed
> and the affected lenses and validators pass again.

| Field | Value |
|---|---|
| Target | `issue/356-ttl-lease-broker` against `origin/main` |
| Merge base | `8052bf56020b0d781db6288f6a1cb243e039c12b` |
| Reviewed revision | `8fa48fa747e465f5013eb989f116f65ee42ceec7` |
| Plan | `docs/plans/2026-07-15-issue-356-ttl-lease-broker-plan.md` |
| Work session | `docs/work-sessions/2026-07-16-issue-356-ttl-lease-broker.md` |
| Scope check | CLEAN |
| Blocked | true |

## Scope Check

The 46-file, 5,973-insertion diff implements the approved U1-U6 broker, adapters, hooks, worktree
integration, release surfaces, and tests. No unrelated product work or pre-existing worktree changes
are present.

## Plan Completion

| Unit | Status | Evidence |
|---|---|---|
| U1 — canonical broker and policy | DONE, review-blocked | fleet-core broker/policy plus broker tests |
| U2 — hook reservation, binding, fencing | DONE, review-blocked | Saga hooks/adapter plus hook tests |
| U3 — Workflow batch admission | DONE, review-blocked | execution metadata/emitter plus emitter tests |
| U4 — team and direct-runtime adoption | DONE, review-blocked | team protocol, engine/outcome adapters and tests |
| U5 — worktree ownership/reclamation | DONE, review-blocked | outcome worktree integration and tests |
| U6 — conformance and release closure | DONE, review-blocked | inventory, manifests, changelogs, docs, full gate |

COMPLETION: 6/6 built; 0/6 accepted until findings are resolved.

## Findings

| # | Sev | File:line | Issue | Reviewer | Confidence | Route | Status |
|---|---|---|---|---|---:|---|---|
| 1 | P0 | `plugins/saga/scripts/outcome_worktrees.py:533` | Dead coordinator identity can reap active worktrees | devils | 100 | `manual -> review-fixer` | open |
| 2 | P0 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:1788` | Reacquisition races destructive worktree reaping | devils, architecture, security, concurrency | 100 | `manual -> review-fixer` | open |
| 3 | P1 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:1323` | Worktree acquisition steals live ownership | devils | 100 | `gated_auto -> review-fixer` | open |
| 4 | P1 | `plugins/saga/scripts/outcome_worktrees.py:369` | Failed registration rollback can drop all authority | architecture | 100 | `gated_auto -> review-fixer` | open |
| 5 | P1 | `plugins/saga/scripts/lease_broker.py:234` | Expired delegated parent can mint fresh authority | security | 100 | `gated_auto -> review-fixer` | open |
| 6 | P1 | `plugins/saga/scripts/workflow_emitter.py:192` | Workflow release revokes still-live children | event-flow | 100 | `gated_auto -> review-fixer` | open |
| 7 | P1 | `plugins/team-execution/skills/team-execution/scripts/lease_protocol.py:82` | Step B8 validation and release are not atomic | event-flow | 100 | `gated_auto -> review-fixer` | open |
| 8 | P1 | `plugins/saga/scripts/lease_broker.py:107` | Normal Saga hooks ignore resolved concurrency | devils | 100 | `manual -> review-fixer` | open |
| 9 | P1 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:818` | Same-session admission can upshift a live ceiling | architecture | 100 | `gated_auto -> review-fixer` | open |
| 10 | P1 | `plugins/saga/scripts/engine_dispatch.py:746` | Engine leases lose resolved policy and retry identity | devils, architecture | 100 | `gated_auto -> review-fixer` | open |
| 11 | P1 | `plugins/saga/scripts/engine_dispatch.py:510` | Expired engine output is persisted before lease settlement | root | 100 | `gated_auto -> review-fixer` | open |
| 12 | P1 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:1456` | Symlinked targets escape leased worktrees | devils, security | 100 | `gated_auto -> review-fixer` | open |
| 13 | P1 | `tests/test_concurrency_conformance.py:620` | Conformance ignores acquire, renew, and release edges | testing | 100 | `safe_auto -> review-fixer` | open |
| 14 | P1 | `tests/test_saga_plugin.py:65` | Workflow test does not enforce prelaunch attestation order | testing | 100 | `safe_auto -> review-fixer` | open |
| 15 | P1 | `tests/test_saga_hooks.py:148` | Parallel hook transitions are tested only serially | testing | 100 | `safe_auto -> review-fixer` | open |
| 16 | P1 | `tests/test_fleet_lease_broker.py:528` | Multiprocess proof covers aggregate admission only | concurrency | 100 | `safe_auto -> review-fixer` | open |
| 17 | P2 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:1665` | Parent completion is not session-scoped | devils | 100 | `safe_auto -> review-fixer` | open |
| 18 | P2 | `plugins/saga/scripts/engine_dispatch.py:797` | Lease cleanup masks primary dispatch failures | devils, architecture | 100 | `gated_auto -> review-fixer` | open |
| 19 | P2 | `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:923` | Hot resource-head history is unbounded | security | 100 | `manual -> review-fixer` | open |
| 20 | P2 | `tests/test_fleet_lease_broker.py:357` | Wrong-owner and wrong-token refusal lack proof | testing | 100 | `safe_auto -> review-fixer` | open |
| 21 | P2 | `tests/test_outcome_worktrees.py:342` | Reclamation acceptance bypasses real Git | testing | 100 | `safe_auto -> review-fixer` | open |

### Failure modes and required fixes

1. The worktree lease records the first one-shot coordinator PID, while later ticks renew only time.
   Transfer exact-token ownership to the current coordinator before renewal; prove an active child is
   never reaped after a TTL gap.
2. Sweep drops the broker lock before physical removal. Add a resource-scoped reaping claim or hold
   equivalent exclusion through final token validation, removal, and authority finalization; race it
   against same-resource acquisition.
3. Worktree acquisition unconditionally supersedes live ownership. Make live acquisition idempotent
   only for the exact owner contract and refuse every competing owner until validated reclamation.
4. Register durable worktree/lease recovery state before Git creation, and retain it whenever rollback
   removal fails.
5. Verify a nested Agent/Task caller's trusted parent `agent_id` and session before reserving a child.
6. Replace unrestricted Workflow `release_owner` with batch settlement that deletes only unused or
   two-signal-terminal slots.
7. Move Step B8 terminal validation and session release into one broker lock transaction.
8. Persist/consume the exact resolved Saga admission snapshot for normal direct calls; armed Saga
   paths must not silently substitute defaults.
9. Reject differing live same-session policy, limit, or mutation snapshots; never widen from the
   candidate alone.
10. Pass resolved engine admission unchanged and fence retries under stable execution identity.
11. Renew/verify immediately after the external runner and before any ledger/manifest/fact write.
12. Resolve existing path components and reject symlink escape before delegated file-tool mutation.
13. Extend conformance negative mutations to every required acquire/reserve, renew, and release edge.
14. Assert `reserve -> attest -> Workflow -> authoritative return/cancel -> release` ordering.
15. Add synchronized multiprocess claim and dual-completion tests.
16. Add multiprocess same-session and atomic batch contention proof.
17. Scope parent completion to trusted `(session_id, tool_use_id)`.
18. Preserve the primary exception and attach cleanup failure as secondary evidence in engine and
   outcome dispatch.
19. Move closed historical heads out of the hot read-modify-write registry or apply a bounded,
   safety-preserving compaction contract.
20. Prove wrong owner/token and stale-token release/renew leave registry authority unchanged.
21. Add a temporary real-Git reclamation/retry acceptance test.

All findings are introduced by this diff and require verification after repair.

## Rejected Candidate Findings

- Team teardown's explicit terminal IDs are trusted root-coordinator assertions required by the
  approved Step B8 contract; accepting them is not an authorization bypass under the stated threat
  model. Finding #7 still fixes the real snapshot-to-release race.
- Symlinked *authority ancestors* require the trusted local operator to configure or retarget the
  authority path and are outside the stated malicious-operator threat model. Final root, lock, and
  registry nodes remain no-follow, ownership, type, and mode checked.

## Coverage And Validator Evidence

- Prior implementation gate: `4618 passed, 1 skipped`; Ruff check/format, mypy, and diff check passed.
- Architecture/security/devil/testing reviews: all blocking; expected fixed profiles were
  `gpt-5.6-sol/high`. The orchestrator supplied fixed `review_high` roles; child-local runtime receipts
  were not exposed, so no stronger runtime-attestation claim is made.
- Concurrency validator: 25 broker tests and five focused cases passed, but the required gate hard
  failed on reaping/reacquisition and incomplete multiprocess proof.
- Event-flow validator: 143 focused tests passed, but the required gate hard failed on premature
  Workflow release and non-atomic Step B8 teardown.
- Testing lens: 314 focused tests passed; four negative mutations incorrectly remained green.
- Bandit's two high findings are pre-existing in unchanged files; changed production files have no
  medium/high Bandit findings.

## Route

Return to `/work`, fix all P0-P2 findings, rerun affected reviewers/validators on the new revision,
then run the full repository gate. PR/merge remains blocked.
