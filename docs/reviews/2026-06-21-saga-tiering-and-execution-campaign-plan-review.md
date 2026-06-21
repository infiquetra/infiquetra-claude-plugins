---
title: Doc Review — Saga Tiering & Execution-Mechanism Campaign Plan (full-hands-off readiness)
type: review
date: 2026-06-21
target: docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md
---

# Doc Review — Saga Tiering & Execution-Mechanism Campaign Plan

**Verdict: READY to drive `/work` (full-hands-off), with one recommended operator action.** Eight findings;
the two P1s are fixed in place, the P2 conflict/enforcement risks are mitigated, and the single standing
recommendation (enable branch protection) is an infra call that the hardened harness already compensates
for. No P0. No unresolved P0/P1 — `/work` will not block.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md` |
| Sibling reviewed | `docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js` (the executable harness) |
| Reviewed revision | working tree off `b73b688`; safe fixes applied in this review |
| Lens | standard readiness + **explicit full-hands-off readiness** (operator-requested) + rate-limit consciousness (operator-requested) |
| Blocked | No (no unresolved P0/P1) |
| Findings | 8 — 1 fixed-with-residual-recommendation, 2 fixed, 2 fixed, 3 residual/noted |
| Fixes applied | plan: KTD3, KTD9, Safety model (+full-hands-off + rate-limit subsections), U17, Risk Analysis (+R-RISK-1, rate-limit, oracle-gaming), Dependencies. harness: SPEC rule 5, header notes, merge step (drop `--admin`, poll discipline, conflict HALT, fix-loop cap), U17 prompt |
| Linked plan / saga | plan above; saga `task-saga-tiering-execution-campaign`; DECISIONS `#saga-tiering-execution-campaign-plan` |

## Readiness summary

The plan was already structurally sound (R-IDs/U-IDs mapped, per-unit tiers, AEs, citations). The
full-hands-off lens surfaced the real risk: **`main` is unprotected** (verified — HTTP 404 "Branch not
protected"), so the autonomous merge gate was enforcement-by-prose, and the harness used a `--admin` bypass
plus a "fix until green" loop that could game its own oracle. Those are now closed in both artifacts. The
publish path was verified safe (the CI `publish` job runs only on `refs/tags/*`, so merging epics cuts no
release). Rate-limit consciousness was added per the operator's request.

## Findings by priority

| ID | Pri | Finding | Status |
|---|---|---|---|
| F1 | P1 | `main` unprotected → the autonomous merge gate is the agent's poll discipline alone; `--admin` bypassed the only guard | **Fixed** (harness: plain `--squash`, merge only on all-SUCCESS, conflict/fix guardrails) + **residual recommendation** → enable branch protection (F1b, P2) |
| F2 | P1 | No rate-limit consciousness for an unattended multi-agent run (operator-requested) | **Fixed** — narrow concurrency, poll sleeps + cap, resumable dead-agent HALT, fix-loop cap; plan + harness |
| F3 | P1 | The "fix until green" loop could pass a red gate by weakening the test that guards it | **Fixed** — SPEC rule 5 (no test/assertion-weakening, no ignore-comments) + 3-attempt cap; Risk row |
| F4 | P2 | R4 (global tier rule) is outside the workflow with no enforcement; Epic 0 success depends on it | **Fixed** — U17 reconciliation flags R4 `applied-inline — operator confirm done`; marked REQUIRED |
| F5 | P2 | Autonomous rebase conflict resolution in load-bearing `saga.py` (U3 ∥ U4) | **Fixed** — KTD9 guardrail; harness aborts the rebase and leaves the epic unmerged for review |
| F1b | P2 | Branch protection not enabled (the proper fix for F1) | **Open — recommended operator action** (infra; harness compensates meanwhile) |
| F6 | P3 | Fresh re-run without `resumeFromRunId` has weaker per-unit idempotency than the resume path | **Noted** — `resumeFromRunId` is the supported recovery path; merge agents also probe existing PRs |
| F7 | P3 | Harness hardcodes the absolute `REPO` path | **Noted** — reference precedent; fine for single-operator/single-machine; flagged for portability |

## Applied fixes

Plan: hardened KTD3 (merge reality + no `--admin` + oracle-integrity), KTD9 (conflict HALT), the Safety
model (added Full-hands-off-readiness and Rate-limit-discipline subsections + REQUIRED-R4 tracking), U17
(reconciliation flags R4 + unmerged epics), Risk Analysis (new R-RISK-1, oracle-gaming, rate-limit rows;
tightened the saga.py-conflict row), and Dependencies (publish-on-tags + unprotected-main + resumability).

Harness: SPEC rule 5 (oracle integrity); header notes (merge gate + rate limits + resume); merge step
(dropped `--admin` → plain `--squash`, all-SUCCESS-only with ~25s poll sleeps and a cap, saga.py-conflict
abort, 3-attempt fix cap); U17 prompt (R4 + unmerged-epic reconciliation, same merge discipline).
`node --check` clean.

## Verified-safe (not findings)

- The CI `publish` job is `if: startsWith(github.ref, 'refs/tags/')` (`.github/workflows/ci.yml:158`) — so
  the unattended run publishes/tags/deploys nothing; merges land on `main` only.
- Citations spot-checked accurate: `lifecycle_state.py:158/163`, `saga.py:71`, `plan/SKILL.md:253`,
  `team-execution/SKILL.md:234`, recommender tests in `tests/test_saga_plugin.py`, validators at
  `marketplace/validator/validate.py` + `scripts/validate_plugins.py`.

## Residual risk

The strongest remaining lever is the operator's: with `main` unprotected, the merge gate is the harness's
poll discipline (now hardened, but still prose). Enabling branch protection with the 5 checks would move the
gate into GitHub's enforcement and is the recommended hardening before — or alongside — the first `/work`
run. Everything else is mitigated or noted.
