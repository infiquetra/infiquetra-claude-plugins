# Issue 926: cycle-5 dependency repair

Baseline: `6b7587f7879f7c0ee414ba60f6b62fc69d33db6d`, branch `work/cp918-p5-maintenance`.
The operator requests readiness for all selected lenses at overall >=9 and dimension >=7.
Independent review owns those scores and its dispatch; no acceptance is claimed here.

## U1 — Remove the edit-time pytest dependency

Read every per-lens C5 record and the merged controller record. The three active findings
(agentusab05, arch09, testing07) identify one cause. The controller dismissed 21 contradicted
findings; their implemented fixes remain in place. The roster's anchors require correct
dependency direction, bounded invocation cost and direct evidence, not just finding closure.

Moved the existing parser, independent factual checks and saved-result oracle from test
helpers into `plan_save_proof.py`. The documentation command calls it directly. The test
shim has no parser copy. Explicit proof checks survive Python optimization. A callable
save adapter uses the unchanged engine's real parser/build/save path and private roots;
its injectable Git boundary avoids subprocess discovery in empty temporary directories.
The twelve real-CLI scenarios remain, using the same independent expected snapshot.

Added an offline Python/PyYAML-only test without a tests directory; it exercises all three
operations and field, condition and renderer-fact mutations under `-O`. Added callable
save containment to the existing path-escape regression. The external inventory includes
the packaged proof. Updated moved canary anchors and registered missing-dependency,
proof-bypass and callable-containment controls. Updated prerequisites and edit outcomes
in the runbook. Historical decisions explicitly identify the superseded pytest mechanism.

Evidence: baseline valid carrier refused without pytest (exit 2); baseline 25 tests took
194.43 seconds. After extraction and removing irrelevant Git discovery, 68 focused tests
pass in 25.08 seconds; mypy passes for 349 files. All 19 registered canaries were caught and the external packaging guard passed (71.48 seconds).
The callable-containment fault injection was then made side-effect-free and its canary
reconfirmed caught. Final gate remains pending. See
[dependency receipt](../evidence/issue-926/cycle5-dependency-repair.json).

Scope: no runtime, carrier schema, generated prose, board sentences, model/effort confirmation,
five unrelated rows, manifest or marketplace changes. Current integrator version 0.157.0
is preserved. No push, PR, merge, board/issue write or review dispatch.

Next: assemble dimension-level evidence and run the full gate at the frozen final commit.

## U2 — Preserve edit-time proof and make review evidence direct

The [before-repair receipt](../evidence/issue-926/cycle5-additional-before.json) records two
further isolated renderer mutations that exposed omissions in the existing pre-write proof:
changing the operator-choice clause to “derived on every save” and changing the save command
to a foreign `saga.py` path both wrote false documentation with exit 0. These were already
asserted by separate regression tests. The shared proof now applies both positive checks
before writing. This extends neither the schema nor runtime. Generic assertion messages were
replaced by named facts, and snapshot mismatches list differing field names without echoing
field values. The optimized, pytest-free CLI test exercises these failures and diagnostics.

The worktree had been detached at `6b7587f7` before this repair started. After U1 committed,
the work branch was advanced from that exact parent to `a2047d6b` and reattached; no history
was rewritten or other worktree changed. The issue-926 Saga thread was restored and advanced
locally with the existing inline operator choice.

## Review dimensions and the evidence they now have

These are preparation results, not new scores. The canonical roster uses all selected lenses,
overall >=9.0 and every applicable dimension >=7.0. Priority/confidence do not gate acceptance.

| Lens (C5 overall) | What the dimensions require here | Evidence and limit |
|---|---|---|
| Architecture (8.0) | Correct dependency direction; cohesive ownership; simple change path; clear errors, conventions and decisions. | Tool and tests depend on one callable proof; neither tool nor engine imports tests. Existing parser/fact/snapshot logic moved rather than copied. Runbook, decision and same-revision check explain ownership. A real minimal environment proves portability. |
| Correctness (8.9) | Complete required behavior, state preservation, correct boundaries, cleanup and all consumers. | Real parser/build/save plus twelve subprocess CLI cases compare whole saved snapshots; fixed/additional examples, contradictory conditions, phase boundaries, literal data, both identity kinds and unrelated state are exercised. Staging/rollback tests remain. Protected-byte audit traces untouched consumers. |
| Security (9.0) | Preserve command/data boundaries, containment, bounded diagnostics and dependency hygiene. | No new dependency; no pytest environment execution in editing. Controlled Bash capture, canonical command checks and both save adapters' containment tests remain. Fault injection cannot perform an escaping callable save. PyYAML SafeLoader and bounded error envelope unchanged; scan both maintenance modules. |
| Testing (8.1) | Behavior-sensitive coverage, realistic seams, edge cases and maintainable isolated execution. | CLI matrix retains real engine execution. Offline/optimized environment tests prove the extraction is usable and checks cannot disappear under `-O`. Named mutation outputs prove refusal, restoration, guard deletion, self-derived assertions and hollowing. Baseline 25 tests: 194.43s; repaired 26-test core: 25.56s before the final diagnostic addition. |
| Agent usability (7.4) | Discoverable invocation/schema, explicit constraints and success criteria, actionable JSON, bounded repeatable operation. | Short runbook names Python/PyYAML prerequisites, exact commands, schema/removal rules, eight error codes, edit example and retry outcomes. Real isolated runs return absolute root and structured errors without pytest. Repeated writes return `changed: []`; valid calls measured 0.44–0.73s. No elapsed-time threshold is used as a flaky test. |
| Documentation (7.92) | Shipped parity, complete prerequisites, navigation, consistent terms, runnable examples and safe recovery. | Existing generated ownership/link and wording tests retained; new prerequisites are actually exercised without test files. Add-example and complete conflict-recovery round trips run; operator-choice truth is checked before writes as well as by real engine cases. Historical pytest decisions explicitly superseded. |
| Adversarial (8.5) | Verify assumptions and failure paths; bounded environment behavior; justified scope and recovery. | Removal of pytest fixes the observed environment failure. Explicit checks survive optimization. Data, predicate, renderer, missing-boundary and bypass mutations refuse before document writes. Dropping proof, CI-only proof and duplicate validators are rejected with reasons. Existing staged rollback remains; concurrent editors/crash-atomic batches remain explicitly unsupported. |
| API contract (8.08) | Compatible operation/serialization/error/version contracts, idempotency, generated-consumer parity. | Same YAML v3 and CLI flags/outcomes/exits; absolute checkout identity remains. Obsolete/future schema refusals differ; errors name file/entry and now identify snapshot field differences. Read/write/check round trips prove parity and repeated-write behavior. No network API, SDK, pagination or rate-limit surface added. |
| Previous comments (9.0) | Verified complete disposition with current evidence. | Three active C5 findings map to U1. Controller-dismissed findings are not reopened; their implementation and 59-row historical ledger remain. U2 records two additional reproduced gaps and their before/after mutations. This table points reviewers at executable evidence rather than asking them to infer closure from commit titles. |

## Four required properties

The [mutation receipt](../evidence/issue-926/cycle5-final-mutations.json) records exact commands,
outputs and source hashes. All CLI mutations run in a disposable checkout with a pytest-free,
optimized Python interpreter.

| Property | Mutation and evidence |
|---|---|
| Real field or condition drift fails | `real-wrong-field`, `phase-status-drift`, `condition-drift`: validate/write exit 2, documents unchanged; restored validate exit 0. `test_contract_cli_without_pytest` and the existing engine/saved-tick guards prove the same boundary. |
| Wording-only prose change passes | `wording-only`: changed narrative remains intact; check exits 0 with `clean` and no changed paths. Existing wording guard also covers unrelated flags and save-operation mentions. |
| Malformed/duplicate facts fail safely | `duplicate-key` and `invalid-field`: exit 2 names YAML and entry; no writes. Existing malformed/structure/CLI guards additionally cover aliases, unsafe tags, deep input, encoding and conflict boundaries. |
| Bypass/self-derived validation is caught | `prewrite-proof-bypassed` makes the minimal-environment guard red; `factual-proof-self-derived` makes its independent negative control red. `guard-deleted` makes the external inventory red. `hollow-guard-normal-execution` makes the ordinary canary test red with `toothless`. Restored controls pass. These prove each guard-protection layer, not just the validator's happy path. |

## Issue 926 acceptance criteria

| Criterion | Current evidence |
|---|---|
| Correct Plan derived-state sentence | Corrected §5.0 preserved byte-identical to `a736c166`. |
| Remove unconditional committed-plan claim | The old “exists and is committed” claim remains absent; entry/exit requirements unchanged in this repair. |
| Preserve model-and-effort confirmation | §5.2a outside the owned note matches `a736c166`. |
| Correct emission-only effort comments | Existing complete honoring note is unchanged; native/proxy and renderer/tier inversion mutations refuse before writing. |
| Derive consumer-row checks | One carrier, independently parsed facts and whole saved-result expectations remain; wrong-real-field mutation fails without pytest. |
| Preserve issue-927 board prose | Entire §0.6 and §5.0 hashes match `a736c166`. |
| Preserve runtime behavior | `saga.py` and `effort_rider.py` match `a736c166` exactly. Only the maintenance proof uses existing injectable seams. |
| Preserve unrelated lifecycle/Workflow prose and five rows | Plan skill, saga-spec and execution-spec are unchanged from `6b7587f7`; all five non-Plan rows match `a736c166`. |
| Gate and release alignment | Integrator's 0.157.0 manifest/marketplace bytes match `2a0b0554`; changelog headings and older bodies unchanged. Run full 25-step gate after the final commit and report that exact revision's result separately. |

The final gate result is kept outside the source commit so recording it does not invalidate
its revision binding. No review, push, PR, merge or board/issue write is dispatched.


Final preparation: 68 focused tests pass in 25.48 seconds; all 50 final mutation outcomes
match expectations, including restored ordinary-canary execution (all 19 controls caught).
Repository Ruff and full-scope mypy pass; both maintenance modules also pass direct mypy
and have no Bandit findings. The protected-byte and changelog-heading/older-body audits pass.
See [current boundary hashes](../evidence/issue-926/cycle5-protected-boundaries.json).
Freeze this unit, then run the 25-step gate and bind its external receipt to that commit.


## U3 — Refile all unmerged journal entries under the newest section

The first full gate at `c273af8c` ran all 25 steps and exited 1 solely on the diff-scoped
journal ordering check. Its test suite passed: 7,728 passed, 7 skipped, 1 expected failure;
coverage was 85% overall, 94% for the maintenance CLI and 88% for the callable proof.
The log is preserved separately as `/tmp/gate-p5-c6-c273af8c-red/result.txt`.

The journal guard compares entry identity against the PR merge base, so adding September 6
sections also made nine September 5 repair entries “outside newest” while this PR remained
unmerged. Refiled only those entries, retaining every original body and explicitly recording
its original date. The [journal mutation receipt](../evidence/issue-926/cycle5-journal-order.json)
shows the original failures, zero violations after the move, and red again when a new entry
is put back under the older date. Both structural and diff-scoped lint now pass.

No code or test behavior changed after `c273af8c`. Commit this filing repair and rerun the full
gate at that new frozen revision; the first gate is not presented as green.
