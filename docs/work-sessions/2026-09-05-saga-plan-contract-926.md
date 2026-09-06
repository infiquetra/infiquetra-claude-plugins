# Issue 926 P5 — structured Plan save documentation contract

**Date:** 2026-09-05 · **Branch:** `work/cp918-p5-maintenance` · **Backend:** inline
**Skill:** `saga:work`; resumed the existing `issue-926` saga. No model, effort, or profile change.
**Plan:** [accepted redesign](../plans/2026-09-05-saga-plan-maintenance-926-p5-structured-contract-plan.md)
at `54f788ad`; implementation baseline `a736c166`.
**change_kinds:** `docs`, `behavior` (the new edit-time validator/renderer CLI).
`requires_hard_test_gate(["docs", "behavior"])` returned `true`; tests and the full gate are required.
Saga runtime behavior remains unchanged. The operator forbids external writes and assigns independent
Code Review to the coordinator; no PR-ready or review-acceptance outcome is claimed here.

## Implementation units

| Unit | State | Evidence |
|---|---|---|
| U1: canonical contract, loader, renderer, engine binding | Complete, `f9ec1a3d` | 12 contract/routing tests passed; Ruff, mypy, validate clean; both original guards retained during migration |
| U2: generated regions and contract pins | Complete, `f9b4ffe7` | Six contract tests plus seven unchanged routing tests pass; full migration diff, hunk inventory, and protected-byte checks in commit message |
| U3: inventory, canaries, journal, final proofs | Complete; this commit | 111 neighboring tests pass; 56 matrix runs match expected outcomes; healthy canaries caught both mutations |

Already conforming: shared Phase 5.3 parser, quoted-hash handling, routing tests, explicit-mode
operator-choice semantics, the command-card pointer, and issue 927's board prose. These were retained.
The interim document-derived field comparison and prose classifier were replaced. The model/card
routing lists and model pointer were completed. The superseded journal record is preserved in Archive.

## Four falsifiable properties

All destructive probes ran in disposable copies, never the live tree. Every probe restored its
inputs; restored contract and inventory runs passed. The U3 commit message carries each observed
mutation output line. The matrix contains 51 expected red runs and five green controls.

| Property | Observed output |
|---|---|
| Real field drift | `phantom-field: exit 1; writes[10] ('risk_tier'): --risk-tier is not an option of saga.py save` |
| Real condition drift | `valid-condition-drift: exit 1; saga-spec.md: the /plan consumer row differs from its rendering` |
| Wording-only changes | `wording-only-in-memory: exit 0; 1 passed` — both documents' prose and Phase 5.3 changed, owned regions retained |
| Malformed facts | `missing-equals: exit 1; writes[4] ('deploy_autonomy').when: missing keys ['equals']` |
| Duplicate facts | `duplicate-field: exit 1; writes[10] ('plan_path'): duplicate name also at writes[2] ('plan_path')` |
| Guard deletion | `inventory-delete-test_saga_spec_consumer_row.py: exit 1; required Plan contract guard input is missing` |
| Self-derived renderer | `self-derived-renderer: exit 1; DID NOT RAISE <class 'AssertionError'>` — changed contract input exposes reading the output back |
| Bypassed binding | `bypassed-engine-binding: exit 1; DID NOT RAISE <class 'AssertionError'>` |

The rest of the matrix covers added template flags; stray commands in plain, titled, tilde, indented,
and inline shapes; swapped effort mechanism; missing effort module/reference; wrong schema and
unknown keys; duplicate YAML keys/template IDs; all six missing/duplicate begin/end markers;
missing/duplicate row with simultaneous skill drift; deletion of each of three guard files;
renaming each of six test functions; and bypassed row/region pins. All structural `render --write`
refusals exited 2 and left both document files byte-identical to their pre-command state.

The three independent falsifiability layers have different responsibilities:

- Inventory catches deleted files or missing/duplicate test names during the ordinary gate.
- Inline proofs catch short-circuited assertions and output-reading renderers during the gate.
- Scheduled canaries mutate actual files. `plan-save-contract-row: caught` and
  `plan-save-contract-engine-binding: caught` on healthy guards. With inline proofs intact, either
  bypass makes the canary baseline fail: `error; baseline_exit=1`. With the associated inline
  proof also removed: `toothless; baseline_exit=0`. Both cases were run for both canaries.

## Issue 926 acceptance criteria

| Criterion | Evidence |
|---|---|
| Derived-state sentence no longer names a work-session path | Retained baseline correction in Plan §5.0; protected section hash unchanged |
| “Plan exists and is committed” corrected/removed | Retained §5.0 correction; §5.2 now explicitly assigns committing the document to the executor |
| Model-and-effort confirmation unchanged | Baseline lines 492, 514, and 538–542 checked byte-for-byte; no hunk touches confirmation |
| Emission-only comments gone; native/proxy accurate | Generated honoring note; real `inject_effort` calls across every public effort/kind, swapped mechanisms fail |
| Consumer row lists declared fields, derived check | Both templates and row render from YAML; real parser/Saga binding and exact output pins; ten original fields in order |
| No board-move sentence edited | Entire §0.6 and §5.0 byte-identical to `a736c166` |
| No behavior changed | `saga.py`, `effort_rider.py`, shared reader and routing tests byte-identical; no enum/parser edits |
| Duplicated lifecycle-position prose left alone | No edits outside the accepted Plan hunks; other skills untouched |
| Full gate exits 0; release surfaces aligned | Gate exit 0, all 25 steps covered; manifests/registry/version heading unchanged at 0.156.0 |

Protected hashes: §0.6 `ec2c9eaa60f567196d393cb87fd424edc59ec4ab97f338902cdd85e821e938e0`;
§5.0 `920c8d7bdebf7bb3414f71ccf3e299855424d540e58a5f77fd412a5078bbb3ee`.
All five unrelated consumer rows are byte-identical to the baseline.

## Plan reconciliation and limits

The first full gate exposed one consumer omitted by the accepted plan: the old
`tests/test_tier_resolver.py::test_effort_emitted_into_plan_tier_table` pinned the removed marker
and exact prose. It was retired in favor of the generated-region and engine-binding tests,
leaving the Team Execution guard unchanged. Mypy also required an explicit observations-list
type annotation. Both repairs are confined to tests. The wording proof now preserves fenced
and inline code while rewording prose.

No new runtime design was invented. The accepted YAML example needed a block scalar so `#993`
survives as note text. This is a representation repair of the specified content. Two plan statements
needed explicit disposition: the operator approved removing the obsolete suppression token from
active code/guidance while preserving historical plans/archives; and the canary's actual baseline
behavior makes a bypass caught by an inline proof report `error`, not `toothless`. The implementation
preserves the existing canary design and reports both outcomes accurately, as proved above.

Free prose elsewhere is outside contract coverage. No layer claims to resist coordinated deletion
of all layers. The Team Execution note remains issue #993; extending the other five consumers is
future work. Release 0.156.0's heading date remains the integrator's responsibility.

## Validation and next step

Narrow checks: 111 tests passed across the contract, routing, packaging and canary modules; the
prescribed filter selected six and passed. Ruff and targeted mypy pass. Renderer validate/check
are clean; two consecutive write passes are no-ops. Journal order lint passes.

Full gate attempt 1: exit 1; 7,601 passed, one obsolete Plan prose pin failed, seven skipped,
one xfailed. Mypy reported the new observations-list annotation. Both have been repaired; the
111-test narrow run and the gate's exact mypy invocation pass. A limited-scope mypy invocation
also produced cached diagnostics in unrelated modules; a clean full-scope check and a subsequent
exact gate invocation passed without editing those modules.

Full gate attempt 2: **exit 0**. Result marker:

```text
GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered.
```

The full suite passed: **7,601 passed, 7 skipped, 1 xfailed**. Mypy checked 348 source files.
The new renderer has 83% measured coverage (CLI subprocess proofs are additionally recorded).
There are two nonblocking advisories: live board-schema census and Bandit (143 findings).
The prescribed narrow filter was rerun after the repairs: **6 passed**.

**Next step:** return the frozen revision to the coordinator for independent Saga Code Review. Selected lenses: architecture-
maintainability, correctness, security, testing, previous-comments, adversarial, documentation-
clarity, agent-usability, api-contract. Required: each derived overall ≥9.0 and every applicable
dimension ≥7.0, combiner all. Findings' priority/confidence are metadata, not gates.
