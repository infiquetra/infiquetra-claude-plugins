# Doc review - concurrency policy plan (#350)

Verdict: **READY AT OPERATOR GATE** - all issue-rubric and readiness findings were fixed in place;
zero P0-P3 findings remain. Implementation is intentionally blocked until the outcome and exact
Verified Workflow candidate are approved.

## Review-Result Contract

- **Target:** `docs/plans/2026-07-15-issue-350-concurrency-policy-plan.md`
- **Reviewed revision:** working tree on `outcome/lease-safe-runtime-continuity`, base
  `a20cc3ce6d74`
- **Blocked status:** document is not blocked; execution is blocked at the explicit operator gates
- **Linked issue:** infiquetra/infiquetra-claude-plugins#350, outcome node `sub-350`
- **Linked outcome:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` (local review draft)
- **Review artifact:** `docs/reviews/2026-07-15-issue-350-concurrency-policy-plan-doc-review.md`
- **Override rationale:** none
- **External panel:** not invoked; the panel is opt-in and the operator did not request external egress

## Applied Fixes

The review corrected the issue-defined aggregate formula, closed the policy schema and precedence,
added requirement/dependency traceability, pinned real test and release files, exposed the shared
release-surface serialization with #351, repaired the machine-checked workflow section, and replaced
an inaccurate read-only-sandbox claim with the actual mutation contract and root diff audit.

## Issue-Rubric Results

All three core issue rubrics and all applicable extras ran inline. Scores reflect the remediated plan.

| Rubric | Score | Finding | Status |
|---|---:|---|---|
| acceptance criteria clarity | 9 | The plan initially left read-only/env/lane/run interaction and effective ceiling behavior under-specified | FIXED - exact order, failure behavior, JSON shape, and R-to-test mapping added |
| devil's advocate | 8 | Ten ACs create a broad PR, but every change serves one governor and a partial emitter-only slice would preserve bypasses | ACCEPTED - five dependency-ordered units and hard stop conditions bound the work |
| spec fidelity | 9 | R7/KTD5 initially replaced AC8's explicit layer-width times verifier-width product with a different overlap formula | FIXED - AC8's conservative product is now the binding guard |
| context completeness | 10 | One cited regression file did not exist and release fixtures were vague | FIXED - `tests/test_saga_execution_spec.py` and `tests/test_saga_plugin.py` are named exactly |
| issue sizing | 8 | Schema, emitters, registry, conformance, and release surfaces span several files | ACCEPTED - they are coupled enforcement points for one policy; no unrelated refactor remains |
| prerequisite mapping | 9 | #350/#351 were described as fully parallel despite both editing Saga release surfaces | FIXED - logical independence is preserved, while implementation/merge is serialized and #356 is named downstream |

## Readiness Findings

Every readiness finding was a safe, evidence-backed fix.

| ID | Priority | Finding | Status |
|---|---|---|---|
| D350-1 | P1 | The Workflow Structure parser treated the following `###` subsection as table rows, so the proposed workflow was not executable | FIXED - operating contract moved to its own H2; installed parser and selection policy pass |
| D350-2 | P1 | `tests/test_execution_spec.py` was named but does not exist; the live regression suite is `tests/test_saga_execution_spec.py` | FIXED - all file and command references corrected |
| D350-3 | P2 | The release unit did not pin the current Saga version or the test that hardcodes it | FIXED - 0.96.0 to 0.97.0 and `tests/test_saga_plugin.py` are explicit |
| D350-4 | P2 | Requirement-to-unit/test coverage and parent/outcome approval state were implicit | FIXED - traceability, requirement coverage, downstream, and operator gates added |
| D350-5 | P2 | The workflow claimed named profiles guaranteed read-only workspace access although current V2 may reapply the parent permission profile | FIXED - `mutation=none` is the authorization boundary; root baseline/diff audit fails any child mutation |
| D350-6 | P2 | Frontmatter used `status: proposed`, which is outside the plan artifact's active/completed lifecycle contract | FIXED - plan status is `active`; operator approval remains a separate execution gate |

## Evidence Verified

- Live `execution_spec.py` owns `VERIFY_N_CAP`, `ExecutionSpec`, dependency layering,
  `_emit_panel_reconciliation`, and dynamic workflow emission.
- Fleet-core already owns the cost-weight vocabulary; Saga must reuse it rather than add another
  table.
- Engine lane definitions live in `plugins/saga/references/engine-registry.yaml` and parse through
  `plugins/saga/scripts/engine_registry.py`.
- `tests/test_saga_execution_spec.py`, `tests/test_saga_engine_registry.py`, and
  `tests/test_saga_plugin.py` exist; the originally named `tests/test_execution_spec.py` does not.
- Saga is currently 0.96.0 and `tests/test_saga_plugin.py` pins that literal.
- Workflow digest `7b84779088a63ef8e6c893a1246bd7744922b1b3a7c938a6bf3833e883e04146`
  passes the installed role/profile binding and requires `validate-concurrency`.

## Remaining Findings by Priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual Risk

The issue is larger than the median one-PR slice and the aggregate product is deliberately
conservative relative to today's sequential panel emission. Those are explicit issue constraints,
not missing decisions. This review ran inline in the authoring session; independent implementation
review remains mandatory in the approved Verified Workflow and later `/code-review` gate.
