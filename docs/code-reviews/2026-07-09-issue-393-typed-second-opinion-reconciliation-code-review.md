# Issue #393 Typed Second-Opinion Reconciliation Code Review

```text
══════════════════════════════════════════════════════════
 /code-review · docs/code-reviews/2026-07-09-issue-393-typ
══════════════════════════════════════════════════════════
 ⊘  Scope                                              [1]
 ⊘  Intent                                             [2]
 ✓  Lenses                                             [3]
 ✓  Review fan-out                                     [4]
 ⊘  Merge                                              [5]
 ✓  Validators                                         [6]
 ⊘  Verdict                                            [7]
══════════════════════════════════════════════════════════
[1] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
[2] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
[3] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
[4] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
[5] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
[6] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
[7] docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md
```

| Field | Value |
| --- | --- |
| Target | `work/393-typed-second-opinion-reconciliation` merge-base diff against `origin/main` |
| Reviewed revision | `e79d05fcbcab66e84bb4dddcf569f02d2c3e2823` |
| Base | `origin/main` merge-base `b3983105b17b8080463bf7770349fd52a0f30a17` |
| Mode | `programmatic` / `report-only` |
| Backend | `inline` |
| Linked issue | `infiquetra/infiquetra-claude-plugins#393` |
| Plan | `docs/plans/2026-07-09-issue-393-typed-second-opinion-reconciliation-plan.md` |
| Work session | `docs/work-sessions/2026-07-09-issue-393-typed-second-opinion-reconciliation.md` |
| Blocked | Yes |

## Scope Check

Scope Check: REQUIREMENTS MISSING

Intent: add typed, Claude-adjudicated reconciliation that accounts for every external-engine finding,
keeps external evidence advisory, bounds panel fan-out, records hash-chained reconciliation facts, and
exposes approval-gated retro proposals.

Delivered: the diff adds the planned registry, intent, manifest, panel, ledger, retro, documentation,
release, and test surfaces, but review-intent raw output is not bound to the declared findings envelope.

## Plan Completion

| Unit | Status | Evidence |
| --- | --- | --- |
| U1 Typed reconciliation registry and ledger writer | PARTIAL | `plugins/saga/scripts/reconcile.py` adds typed results and ledger facts, but `plugins/saga/scripts/engine_dispatch.py:121-137` replaces review output with declared findings without rejecting omitted raw-output findings. |
| U2 Canonical divergence intent and tier contract | DONE | `plugins/fleet-core/scripts/fleet_commons/tier_palette.py`; `plugins/fleet-core/scripts/fleet_commons/tier_policy.json`; `plugins/saga/scripts/execution_spec.py`. |
| U3 Rejected-offload disposition and evidence | DONE | `plugins/saga/scripts/provenance_manifest.py`; `plugins/saga/scripts/engine_dispatch.py`; focused manifest and reconciliation tests. |
| U4 Bounded advisory panel and foreman reconciliation | PARTIAL | Panel cap and foreman binding exist, but member dispatch shares the U1 review-output omission at `plugins/saga/scripts/engine_dispatch.py:121-137`. |
| U5 Read-only retro proposal view | DONE | `plugins/saga/scripts/reconcile.py:839-919`; `tests/test_saga_retro.py`. |
| U6 Documentation, decisions, release surfaces, and integration closure | CHANGED | Release surfaces are synchronized, but the work-session claim at `docs/work-sessions/2026-07-09-issue-393-typed-second-opinion-reconciliation.md:339-340` contradicts the accepted behavior in `tests/test_saga_engine_dispatch.py:348-375`. |

COMPLETION: 3 DONE, 2 PARTIAL, 1 CHANGED, 0 NOT-DONE, 0 UNVERIFIABLE.

## Required Before Merge Findings

### P1

| # | File | Issue | Reviewer | Confidence | Route |
| --- | --- | --- | --- | --- | --- |
| 1 | `plugins/saga/scripts/engine_dispatch.py:121` | Unlisted findings bypass reconciliation | correctness + security + API contract + adversarial | 100 | `gated_auto -> human` |

#### Finding 1: Unlisted findings bypass reconciliation

- Severity: P1
- Status: validated, unresolved, merge-blocking
- Fingerprint: `plugins/saga/scripts/engine_dispatch.py:121:trust-boundary`
- Requires verification: yes
- Pre-existing: no
- Why it matters: for `second-opinion` and `divergence`, the dispatch boundary derives
  `canonical_evidence` solely from the runner's declared `findings`, overwrites the original `output`,
  and never checks that the two match. A runner can therefore include a net-new finding in raw output,
  omit it from `findings`, and obtain a reconciliation whose source IDs and digest cover only the listed
  subset. `satisfy_gate()` then accepts that incomplete reconciliation, violating R2 and the stated
  epoch-3 remediation.
- Evidence:
  - `plugins/saga/scripts/engine_dispatch.py:121-137` renders the typed findings and replaces
    `self.evidence` without an equality check against the original review output.
  - `tests/test_saga_engine_dispatch.py:348-375` explicitly accepts different raw summaries with hidden
    text and asserts that the hidden text disappears from canonical evidence.
  - `docs/work-sessions/2026-07-09-issue-393-typed-second-opinion-reconciliation.md:339-340` states the
    opposite contract: raw review output must exactly match the canonical ordered findings envelope so
    an unlisted finding cannot be hidden.
  - Independent reproduction at reviewed HEAD returned `gate_accepted=true` after reconciling one listed
    finding while raw output contained an additional unlisted finding.
- Suggested fix: before replacing review-intent evidence, require the original `output` to equal
  `render_source_findings(source_findings)` exactly and reject mismatches. Replace the current
  summary-independence test with a mismatch-refusal regression, and add a panel regression proving a
  hidden raw-output finding reaches neither the foreman nor ledger facts. Assumption: the work-session's
  exact-envelope statement is the intended contract.

## Review Lenses

All lenses and the finding validation ran inline. No reviewer agents, Team Execution cycle, or
external-engine second opinion was invoked.

| Lens | Result |
| --- | --- |
| correctness | Blocked by Finding 1. |
| security | Blocked by Finding 1 at the external-output trust boundary. |
| testing | Blocked because the current regression test asserts the unsafe behavior. |
| maintainability / conventions | No surviving finding before the stop condition. |
| reliability | No surviving finding before the stop condition. |
| API contract | Blocked by Finding 1. |
| adversarial / red-team | Blocked by the proven omitted-finding path. |
| agent-native | No surviving finding before the stop condition. |

## Validator Pass

No provenance manifest tree was present in this worktree, so no Stage-B manifest skip applied.

Finding 1 was independently rechecked against the reviewed code and reproduced with a direct read-only
dispatch/reconciliation/gate script. The gate accepted the listed-only reconciliation while the raw output
contained an additional hidden finding. Validator result: validated.

## Checks

- `git rev-parse HEAD` and `git status --short --branch` — clean reviewed HEAD confirmed.
- `git fetch origin main --quiet` — base refreshed.
- `git merge-base origin/main HEAD` — `b3983105b17b8080463bf7770349fd52a0f30a17`.
- Complete merge-base diff inventory — 50 files, 5,459 insertions, 197 deletions.
- Direct read-only reproduction — `gate_accepted=true` with one listed finding reconciled and one
  additional raw-output finding omitted.

## Coverage

Suppressed findings: 0. Over-budget validators: 0.

Residual risk: this bounded review stopped on the first independently validated P1 as explicitly required.
The remaining merge-base diff was not represented as clean, and no statement is made that other findings
do not exist.

Testing gap: the full focused or repository test matrix was not rerun after the surviving finding because
the operator's stop-on-survivor rule ended the gate. The existing focused test at
`tests/test_saga_engine_dispatch.py:348-375` is code evidence for the defect because it codifies the
unsafe acceptance path.

> **Verdict:** BLOCKED. Finding 1 survives validation and requires operator decision before any fix or
> further merge-readiness review.
