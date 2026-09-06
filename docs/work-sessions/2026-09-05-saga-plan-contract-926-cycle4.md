# P5 cycle 4 — documentation contract repair (#926)

> **Historical submission receipt for `04cbb0ce`, rejected by independent cycle-4 review.**
> The claims below describe that worker's intended closure and are not current proof.
> The authoritative correction is the [post-cycle-4 repair receipt](2026-09-05-saga-plan-contract-926-repair.md).
> In particular, the tier-cell assertion was still unbound; the inventory detected only
> first-statement hollow bodies; and the universal `REMEDY` was unwired but still defined.
> `eb735566` actually deletes that constant. Cycle-3 previous-comments `prev02` (tier pin)
> and `prev03` (false Python-coverage rationale) were omitted here; both now have explicit
> corrected dispositions in the accepted plan and current repair ledger.
> The byte audit below applies to `04cbb0ce`, not the integrator's reviewed revision:
> `4fcd314a`/`2a0b0554` legitimately advanced release surfaces to 0.157.0. Current repairs
> compare runtime/protected prose to `a736c166` and release files to `2a0b0554`.


The operator authorized this fourth repair cycle after the cycle-3 cap outcome at `b4ef1925`.
The worker resumed the existing issue-926 Saga Work thread inline. Independent review remains
coordinator-owned; no review acceptance is claimed. No push, PR, merge, board or issue write.

## U1 — smaller contract and behavior boundaries

Implemented the cycle-4 amendment in
[the decision record](../engineering-journal/DECISIONS.md#926-plan-save-contract-single-source).
The loader binds real options, enum placeholders, producer flags and effort mechanisms before
rendering. The edit-time tool has stable example groups, explicit checkout ownership, JSON
refusals, staged writes and rollback. Tests parse emitted facts independently, execute saves,
and exercise refusal/recovery, with one scheduled mutation per guard. The removed configuration
and rejected no-check alternative are recorded in the decision. The maintainer runbook is at
`plugins/saga/references/plan-save-contract.md`.

Focused validation: 118 tests passed across contract, routing, tier, packaging and canary modules.
Ruff and focused mypy passed. The byte audit against `a736c166` passed for entire §0.6, §5.0,
and §5.2a outside the permitted effort comment (including unchanged model/effort confirmation),
the five unrelated rows, both runtime files, and manifest/marketplace files.

## U2 — mutation receipts and final gate preparation

The source implementation is 466 lines (499 at cycle 3). Explicit schema/policy options
were removed, rather than transferred to another validator. Added surface is testing, canary registration and the maintainer runbook.
The remaining size primarily serves code binding, three generated regions, JSON CLI reporting
and the requested failure recovery. There is no new runtime dependency or runtime behavior change.

The mutation matrix recorded **91 expected outcomes**: 36 failing pytest runs, 11 CLI refusals
(exit 2), and 44 successful baselines/restores or intended render operations. Every negative
pytest proof was followed by the named restored check passing. Full outputs and commands are
machine-local in `/tmp/p5-c4-proofs/results.json` (75 runs) and
`/tmp/p5-c4-extra/results.json` (16 runs); each names its corresponding `.log` file.
The unchanged-output checks in the wrong-field CLI probes verify neither document was written.
These are implementation receipts, not lens scores or independent review.

| Required property | Broken behavior and observed output | Restored proof |
|---|---|---|
| Real field or condition drift fails | `real-wrong-field-write`: exit 2, `writes: missing Plan producer flags ['orchestration_recommended']`; `valid-condition-drift`: exit 1 after successful rerender, saved `deploy_autonomy` differs. | Binding test: 1 passed; saved-tick matrix: 4 passed. |
| Wording-only edits remain green | `wording-only-both-documents`: changed ordinary text in both actual documents; all 12 contract cases passed. | Restored module: 12 passed. |
| Malformed/duplicate facts fail safely | `duplicate-key-validate`: exit 2, file plus line/key diagnostic; `nul-reference-validate`: exit 2 naming `effort_honoring.reference`; alias inputs refuse before graph construction. | Loader guard restored: 1 passed per case. |
| Bypass and self-derived validation are caught | `row-helper-bypass` and `region-helper-bypass`: exit 1, `DID NOT RAISE`; `renderer-reads-own-row` and `renderer-reads-own-template`: exit 1 on changed input; `guard-file-deleted` and `hollow-guard`: external packaging guard exit 1. | Each affected guard restored: 1 passed. Scheduled canaries separately prove the execution layer below. |

All nine registered P5 canaries reported **caught** with healthy guards. Hollowing each named
guard in a disposable copy made each corresponding canary report **toothless**. This proves the
scheduled layer does not equate collection/success with a live guard. The external inventory
separately rejects those hollow bodies. Results: `/tmp/p5-c4-canaries/results.json`, 18 records.
The checked-in inline controls, external inventory and registry are the three shipped layers;
these temporary runners only collect their falsification evidence.

Focused validation: 118 tests passed. The prescribed selector passed 12 tests with 6,901
deselected. Full-scope mypy passed 348 source files; repository Ruff passed. A focused coverage
measurement before the final interface/heading refinements covered 255/272 validator statements
(93.75%); the final gate owns final-revision coverage and is reported separately.

## Cycle-3 finding dispositions by failure cause

All 65 typed findings are mapped exactly once below. IDs refer to the coordinator's
`review_result_c3.json`. A repair disposition is not an assertion that any dimension now scores
9: the nine selected lenses and their independent scoring remain the coordinator's next step.

| Findings | Final change | Falsifiable evidence |
|---|---|---|
| `adv01`, `adv06`, `testing01`, `agentusab01`, `api01` | Loader validates real options, exact enum placeholders, and independent upstream save tokens before writing. Saved-tick assertions supply Plan intent. | real-wrong-field-write; phantom-field-write; false-enum; valid-condition-drift |
| `adv04`, `adv07`, `agentusab10`, `doc08`, `corr04`, `corr07`, `testing11` | Removed the hand-written deploy enum and per-template omission/note rules; all conditional additions remain available in both groups. Unknown fixed fields are named as fields. | valid-condition-drift; test_plan_examples_save_the_intended_tick (four destination/backend cases); malformed controls |
| `adv05`, `testing02`, `agentusab03`, `doc02`, `arch02` | Removed editable factual notes; restored both resolver attribute names and pair emission pin. Native/proxy declarations execute against the real seam. | tier-attribute-dropped; false-effort-mechanism; test_effort_emitted_into_plan_tier_table |
| `corr01`, `corr02`, `api03`, `arch01` | Removed free-text row inputs; values must be enum choices, placeholders are single-line, NUL references refuse, quoted hashes retain following flags. | free-factual-note; nul-reference-validate; non-enum-literal-bypass; quoted-hash-regression |
| `adv03`, `api02`, `corr05`, `agentusab04`, `agentusab06`, `agentusab07`, `arch06`, `api04` | Staged replacements roll back, failed rollback retains named backups, refusals carry file/entry/code, and schema family/version differ. Removed the universal retry remedy and omit interface. | rollback-bypass; rollback-backup-lost; schema-code-regression; test_plan_renderer_refusals_and_rollback |
| `adv02`, `api08` | Stable groups accept additional examples through an ordinary YAML edit, then check/write/check converges; no per-example markers. | plan-save-contract-add-example canary; test_plan_renderer_edit_workflow |
| `testing03`, `testing10`, `adv08`, `testing08`, `testing09`, `arch03`, `arch04` | Output facts and commands are parsed independently of the renderer. Mutation tokens derive from entries, with explicit changed-input assertions; no copied row, fixed writes index or self-comparison. | renderer-drops-fact; renderer-drops-flag; renderer-reads-own-row; renderer-reads-own-template |
| `testing05`, `arch07` | Packaging inventory lives outside the guarded file, rejects empty/hollow bodies, and requires a scheduled canary for every guard. Generated markers no longer cite a test name as proof. | guard-file-deleted; hollow-guard; nine healthy/caught and nine hollow/toothless canaries |
| `testing07`, `doc04` | Stray save commands are rejected throughout the Plan skill; release notes state that scope. | stray-fenced; stray-tilde; stray-titled; stray-indented; stray-inline (all appended after a new later heading) |
| `testing06`, `doc01`, `corr06`, `api05`, `api06` | Documented and executed explicit-choice refusal, including choice without a mode, as well as accepted downgrade, resume and empty initial state. Runbook describes identity and provenance storage without claiming an exhaustive row. | test_operator_choice_rule_matches_engine; plan-save-contract-operator-choice canary |
| `agentusab02`, `agentusab05`, `agentusab09`, `doc03`, `doc09`, `doc10`, `doc05`, `doc06` | Added a concise maintainer runbook, runnable recommender, both generator owners, JSON exit meanings, conflict/rollback recovery and unreleased heading convention. Fixed the model-relative pointer; terminology is generated region. | runbook-command-broken; runbook-inventory-broken; model-relative-link-broken; heading-wording-coupling; test_plan_docs_wording_changes_do_not_fail |
| `agentusab08`, `doc07` | Shortened the row to its payload fields/conditions; derivation, rationale and other stored fields live in the linked runbook. | test_saga_spec_plan_consumer_row_matches_contract; renderer-drops-fact |
| `adv09`, `arch05`, `corr08` | Explicitly considered prose-only/no-check delivery; retained only required verification. Deleted unused flags_of and configurable policy without an oracle. Validator source shrinks from 499 to 466 lines; no new dependency. | decision record; full routing/contract tests; mutation matrix |
| `testing04` | Malformed shapes, duplicate keys/entries, invalid enum values, unsupported notes/omits, bad references, aliases and interface failures have executable refusal controls. | test_plan_save_contract_loads_and_rejects_malformed_entries; duplicate-key; recursive-alias; shared-alias; loader-bypass |
| `sec01` | Deleted the quadratic prose scanner; alias inputs now refuse before graph construction rather than traverse a shared graph. | recursive-alias; shared-alias |
| `sec02` | Recorded the parent-terminalized Wave One marketplace-field residual without reopening it or changing marketplace bytes. | protected byte audit; explicit cycle-4 scope boundary |
| `api07`, `corr03` | One explicit --root selects the target checkout code, YAML and output together; foreign --contract is removed. | test_plan_renderer_edit_workflow; test_plan_renderer_refusals_and_rollback |

`prev01`: the historical finding ledger now explicitly contains 55 cycle-2 rows plus the two
cycle-1 security carry-forwards. `cycle1-sec01` is resolved by deleting the scanner/alias walk
and exercising alias refusal. `cycle1-sec02` records the parent's terminalized Wave One
marketplace disposition; no marketplace repair or custody expansion is claimed.

## Issue 926 acceptance evidence

| Acceptance criterion | Evidence |
|---|---|
| Derived-state sentence no longer names Work's path | Existing §5.0 sentence names the plan document and reviewed readiness; retained byte-identical to `a736c166`. |
| Unconditional committed-plan claim corrected | Existing Phase 0.2 requires a durable plan and cleared review; the removed “exists and is committed” claim remains absent. |
| Model-and-effort confirmation unchanged | Entire §5.2a outside the allowed effort comment is byte-identical to `a736c166`. |
| Accurate native/proxy effort description | `inject_effort` behavior binding and restored model/effort cell pin; false mechanism and missing attribute mutations fail. |
| Consumer row matches declared fields derivedly | YAML-to-row and YAML-to-command parsing plus actual saved-tick semantics; no second hardcoded field list. |
| No board prose edited | Entire §0.6 SHA256 `ec2c9eaa60f567196d393cb87fd424edc59ec4ab97f338902cdd85e821e938e0`; §5.0 `920c8d7bdebf7bb3414f71ccf3e299855424d540e58a5f77fd412a5078bbb3ee`, both equal `a736c166`. |
| No runtime behavior change | `saga.py` and `effort_rider.py` byte-identical to `a736c166`; only documentation tooling/tests changed. |
| Duplicated lifecycle-position and unrelated Workflow prose untouched | §5.2a outside the effort note and other non-target prose retained; the five other spec rows also compare byte-for-byte. |
| Gate and aligned release surfaces | Saga remains 0.156.0; manifest and marketplace bytes unchanged. The full 25-step gate is run **after** the final commit; its SHA, exit code and result.txt are returned as a machine-local receipt, without a later source commit. |

Protected-byte audit: `/tmp/p5-c4-protected.json`; baseline `a736c166`. No model, effort, profile,
board, issue, push, PR or merge change. The sole remaining action after the frozen-revision gate
is for the coordinator to dispatch independent Saga Code Review; the worker stops there.
