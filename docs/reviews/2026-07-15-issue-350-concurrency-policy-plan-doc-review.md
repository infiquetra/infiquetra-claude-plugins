# Doc review - concurrency policy plan (#350), attempt 6

The amended plan is implementation-ready at the exact operator gate. All safe fixes were applied in place and zero P0-P3 findings remain.

## Review-Result Contract

| field | value |
|---|---|
| target | `docs/plans/2026-07-15-issue-350-concurrency-policy-plan.md` |
| reviewed revision | working tree at `99549aaa2c4cae3003bdb14cd5b71b2bd46b27fd` |
| reviewed plan SHA-256 | `5a47c88548e9395e1d2ec87d2684886c7872326aac6bf709f89327e878eb6048` |
| blocked status | document ready; execution waits for the exact attempt-6 workflow preview |
| linked issue | `infiquetra/infiquetra-claude-plugins#350` |
| linked outcome | `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json` revision 3 |
| review artifact | `docs/reviews/2026-07-15-issue-350-concurrency-policy-plan-doc-review.md` |
| override rationale | none |

## Applied Fixes

The review converted the operator's approved attempt-6 recommendations into a decision-complete routing, test, and workflow contract.

| ID | Priority | Finding | Applied fix |
|---|---|---|---|
| A6-D1 | P1 | The attempt-5 plan explicitly prohibited attempt 6 and did not bind the newly approved Sol/max repair workflow | Added the attempt-6 scope, fresh repair/preflight/final graph, exact role/profile/model/effort bindings, and an attempt-7 stop |
| A6-D2 | P1 | “Freeze capability routing” omitted the resolver inputs needed to make admission and dispatch consume the same decision | Pinned one emit-scoped overlay, calibration snapshot, resolver memo, `role_kind=worker`, rendered prompt context, UTF-8 byte estimate, and unit ID |
| A6-D3 | P1 | Emitting both capability and engine would violate the existing XOR selector contract | Kept serialized capability unchanged, emitted only the resolved exact engine selector, and retained capability in the inert dispatch marker |
| A6-D4 | P1 | Required native-child independence could never pass when the current host join classifies matching child receipts as diagnostic | Kept every fresh Sol/max dispatch mandatory but made independence preferred; a truthful root-inline duplicate supplies gate evidence without a false child/model claim |
| A6-D5 | P2 | The attempt-5 conformance language did not close split fragments, JavaScript Unicode line terminators, reaching-definition kills, or Workflow host globals | Added exact mutation fixtures for fragment joining, `U+2028`/`U+2029`, overwrite/alias/dead-branch bypasses, and the independent `parallel`-inclusive host baseline |
| A6-D6 | P2 | Review processes could invalidate their own no-write receipts through ignored caches | Bound coverage, bytecode, UV, XDG, Ruff, and MyPy outputs to unique `/tmp` roots and required before/after ordinary, ignored, and Git-control audits |
| A6-D7 | P2 | Two required-evidence IDs made the installed tester schema impossible to seal because it requires exactly one command-output record | Bound each tester row to one `tester-evidence` ID and one protected composite command-output record; typed cases retain the individual ordered check results inside that record |

## Readiness Evidence

The amended artifact now gives an unfamiliar implementer one unambiguous route through all four technical findings and the invalid-receipt failure.

| check | evidence | status |
|---|---|---|
| requirement mapping | R6, KTD8, U2, U4, verification, and attempt-6 scope all name the same frozen-route and conformance invariants | PASS |
| selector contract | `execution_spec.py` rejects simultaneous engine and capability; the plan emits one exact engine and keeps capability as provenance | PASS |
| runtime-resolution parity | `engine_resolver.resolve` already accepts repository overlay, calibration, role kind, and task context; the plan binds each input once per emission | PASS |
| workflow syntax | installed `verified_workflow_readiness.py` resolved `#workflow-structure` with `ready=true` | PASS |
| role/profile drift | all five installed role hashes and `review_max`, `review_high`, and `test_medium` profile hashes equal the table | PASS |
| mutation ownership | the Sol/max repair author works only in a disposable copy; root alone applies accepted source changes and owns Git/GitHub actions | PASS |
| tester evidence shape | both tester rows bind one composite protected command-output record, matching the installed `tester-evidence.v1` one-record derivation rule | PASS |
| stop behavior | fallback, halt, non-exact route, model/effort mismatch, workspace mutation, any P0-P3 finding, or missing gate evidence blocks | PASS |

## Remaining Findings by Priority

No findings remain: P0 0, P1 0, P2 0, P3 0.

## Residual Risk

Native Sol/max receipts may remain diagnostic even when their model and effort readback matches. The plan handles that explicitly by retaining their independent findings and repeating each selected lens inline for gate authority; it never upgrades diagnostic evidence into an attested receipt.
