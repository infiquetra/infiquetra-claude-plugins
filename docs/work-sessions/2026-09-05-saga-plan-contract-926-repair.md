# Issue 926: repair after cycle 4

Baseline: `2a0b05545a9907c3d10a6f1089b0f9a856145bcd`. Independent cycle-4 review
rejected the previous closure claims. Its 59 findings remain the repair inventory;
passing individual tests below is not review acceptance. The integrator's merge and
Saga 0.157.0 release surfaces are preserved.

## Unit 1: contain documentation-command execution

Cycle-4 `sec01`: `test_plan_docs_wording_changes_do_not_fail` previously executed an
arbitrary path selected by the runbook. A disposable-checkout mutation substituted an
outside Python script that wrote a harmless marker and printed valid recommender JSON.

| State | Named test | Exit | Outside marker |
|---|---|---|---|
| Baseline with mutated runbook | `test_plan_docs_wording_changes_do_not_fail` | 0, 1 passed | Created |
| Repaired test with identical mutation | Same | 1, canonical-command assertion | Absent |
| Repaired test, restored runbook | Same | 0, 1 passed | Absent |

The permanent test also rejects absolute/traversal paths, another in-repository script,
interpreter options, and a canonical-name symlink escaping the checkout. No runtime file
changed. Other cycle-4 findings are still pending; no full-gate or score claim is made here.

## Unit 2: literal values, structured refusals, and stored provenance

v3 makes placeholders literal data and moves shell quoting into the renderer. v2 and
v1 carriers refuse with their observed version; this is a documentation-schema change,
not a Saga runtime change. Identity now binds to `derive_saga_id`'s actual parameters.
Fixed conditional contradictions, HTML-comment injection, and remaining Git conflict
delimiters refuse before a write. Refusals distinguish arguments, code loading, file
access, syntax, and contract/schema errors; successful writes identify the absolute root.
The consumer row includes the explicit-mode operator-choice consequence. Tests also
exercise carried divergence, blank rationales, and refused upgrades with a rationale.

The shortened runbook removes the false release statement and the incorrect blanket
downgrade rule. It documents the JSON keys/codes and raw-placeholder migration. The unused
REMEDY constant and unrelated section-sign re-encoding are removed. Full factual prose
and bypass coverage remain pending in subsequent units.

Validation: 57 focused tests passed. Twelve isolated implementation mutations each had a
green baseline and a failing named test; all mutations were discarded with their temporary
checkouts. [Machine receipt](../evidence/issue-926/repair-boundary-mutations.json). The first
diagnostic-size mutation was toothless because the outer error cap hid the inner echo;
the strengthened assertion now detects that echo and the repeated mutation is caught.

| Mutation | Named boundary test | Result |
|---|---|---|
| shell-data | `test_contract_values_are_shell_data` | baseline 0 → caught |
| marker-injection | `test_contract_rejects_corrupting_structure` | baseline 0 → caught |
| conditional-fixed | `test_contract_rejects_corrupting_structure` | baseline 0 → caught |
| identity | `test_contract_rejects_corrupting_structure` | baseline 0 → caught |
| comment-terminator | `test_contract_rejects_corrupting_structure` | baseline 0 → caught |
| conflict | `test_contract_rejects_corrupting_structure` | baseline 0 → caught |
| engine-exception | `test_contract_cli_reports_operation_and_checkout` | baseline 0 → caught |
| schema-observed | `test_contract_cli_reports_operation_and_checkout` | baseline 0 → caught |
| unbounded-error | `test_contract_cli_reports_operation_and_checkout` | baseline 0 → caught |
| usage-code | `test_contract_cli_reports_operation_and_checkout` | baseline 0 → caught |
| empty-root | `test_contract_cli_reports_operation_and_checkout` | baseline 0 → caught |
| write-root | `test_contract_cli_reports_operation_and_checkout` | baseline 0 → caught |

## Unit 3: require the real saved-result check before writing

The CLI now runs the existing saved-example test before success or writing. The test
uses the literal non-enum placeholders, expands enum choices across all four destinations
and three backends, and compares the whole saved snapshot with Plan's semantic outcomes.
It preserves prior unrelated state and rejects additional unrelated writes. Fixed destination,
recommendation, and deployment-autonomy examples exercise this same path, including the
full saved-result oracle after rendering. No second field-list validator was added.

The broad scan of save flags in arbitrary prose is deleted. The remaining unowned-command
check recognizes command syntax, so ordinary prose mentioning `saga.py save` or flags for
other phases does not fail. The CLI uses the matching checkout tool and its development
environment; each proof invocation has a private temporary directory. Failure output keeps
the actual assertion rather than allowing unrelated pytest cleanup warnings to displace it.

The ordinary pytest gate now runs all twelve P5 registry mutations. The first-statement
AST approximation is removed; the external AST inventory proves presence only. This closes
the interval in which a hollow guard could ship before the next scheduled canary run.

Validation: 23 focused cases passed; the ordinary behavioral-canary test passed in 153.98s
with all twelve entries caught. Its first attempt found a stale v2 schema anchor, which was
updated to v3 before the passing run. [Thirty-seven isolated outcomes](../evidence/issue-926/repair-semantic-mutations.json)
record baseline/restored success, refusal without writes for each removed field, wrong and
additional real options, condition drift and a comma-delimited ADR example; wording-only
changes remain valid and clean. Removing the CLI preflight, hollowing guards after a real
first statement, and deleting the guard file each fail their named ordinary pytest check.

Remaining work includes binding the renderer's factual prose, generated ownership metadata,
the historical finding-ledger corrections, simplifying the remaining configurable surfaces,
and the full gate at the final frozen commit. These receipts do not claim review acceptance.

## Unit 4: independent factual pins, simpler inputs, and complete dispositions

The effort carrier now contains only native/proxy declarations; its seam, parameters and
reference come from their existing owners. The loader handles structure/identity, while the
one pytest engine binding serves both regression and edit-time verification. Custom module
registration is replaced by `runpy`. The CLI checks document boundaries before its behavioral
preflight so marker/conflict failures retain direct file/entry diagnostics.

Independent positive assertions bind the complete generated effort/tier note and the Reads
cell. Each region has symmetric markers, source/renderer attribution, a hand-edit warning,
and the actual guard name. A false renderer plus freshly rendered output fails these assertions;
the new factual-self-guard canary detects removal of that assertion. Ordinary narrative stays
outside the contract. The fourth Plan example in execution-spec is replaced with a resolving
link. The runbook's protocol table and recovery path have executable controls, including a full
conflict-resolution round trip. Obsolete schema and future-tool remedies differ. Non-UTF-8
owned documents and escaping engine symlinks have named, structured refusals.

Additional conditional enum fields are varied one at a time. Mutating ADR references to depend
on `kind: task` or `orchestration_recommended: inline` now fails even though the old scenario
matrix always chose those values. Bypassing the added coverage makes its negative control fail.
Legitimate fixed examples, including an underscore in the example ID, continue to work.

The historical plan, journal and cycle-4 work session now explicitly correct their rejected
closure claims. The [complete ledger](../evidence/issue-926/cycle4-finding-dispositions.md) maps
59/59 cycle-4 findings; it also dispositions the omitted cycle-3 previous-comments `prev02`
and `prev03`. The [document audit](../evidence/issue-926/repair-document-audit.json) fails when a
ledger row is removed and passes when restored. Accepted-plan frontmatter and older changelog
bodies remain unchanged. No test is claimed to prove the truth of arbitrary historical prose.

The maintainer tool has 287 AST statements, down from 310 at cycle 3. Physical lines are 507
(499 at cycle 3; 466 at the rejected cycle-4 submission), so this is a reduction in executable
and configurable policy, not a claim that every size metric decreased. The current unit removes
79 net lines from the tool relative to `d7192810`. No generic validation or transaction framework
was added. The decision records the prose-only alternative and why it does not satisfy the
operator's four required proofs.

Validation before the frozen gate: 66 focused tests passed; repository Ruff and full-scope
mypy passed (349 files). The final mutation receipt is
[repair-final-mutations.json](../evidence/issue-926/repair-final-mutations.json).
The batch records 53 expected outcomes, including 21 caught canary mutations and the restored
25-case focused suite passing. A subsequent audit found one additional candidate-phase parsing
gap, to be fixed in the next unit before the final gate. These are preparation results;
independent lens scoring remains coordinator-owned.

## Four required properties

| Property | Mutation and named check | Output |
|---|---|---|
| Real field/condition drift fails | Each removed Plan field, an unrelated real option, extra writes, incorrect deployment condition; `test_plan_examples_save_the_intended_tick` and `test_plan_save_contract_binds_to_engine`. Additional kind/recommendation predicates are covered. | Unit-3 receipt: validate/write exit 2 with unchanged documents; final receipt: predicate mutations exit 2, restored validate exit 0. |
| Wording-only edits do not fail | Ordinary narrative, unrelated flags and bare `saga.py save` mentions; `test_plan_docs_wording_changes_do_not_fail`. | `wording-only`: exit 0, `clean`, no changed paths. |
| Malformed/duplicate facts fail safely | Duplicate mapping keys/entries, aliases, malformed values, deep YAML, HTML delimiters and bad document structure; malformed/structure/CLI guards. | Registered controls: green baseline then `caught`; CLI controls assert exit 2 with file and entry. |
| Bypass/self-derived checks are caught | Preflight removal, guard deletion, second-statement hollowing, false renderer/output agreement, factual assertion removal and predicate-coverage removal. | Unit-3 named pytest checks exit 1; final factual-self-guard `caught`; predicate-coverage bypass exits 1, restored guard passes. Ordinary pytest runs all registered controls. |

## Issue 926 acceptance evidence at the repair boundary

| Criterion | Evidence |
|---|---|
| Plan's derived-state sentence no longer names Work's path | Existing corrected §5.0 is retained byte-identical to `a736c166`. |
| The unconditional committed-plan claim is removed | Existing entry/exit prose requires the durable plan and cleared review; the old “exists and is committed” text remains absent. |
| Model-and-effort confirmation unchanged | §5.2a outside the owned effort note matches `a736c166` byte-for-byte. |
| Emission-only effort comments corrected | Complete generated honoring note binds to observed `inject_effort` behavior, both resolver attributes, the paired tier cell and coupling note; false render mutations fail. |
| Consumer row is checked derivedly | YAML-to-row/command parsing plus independent whole saved-result semantics; derived operator choice is included. |
| Issue 927 board prose unchanged | Entire §0.6 and §5.0 hashes match `a736c166`; see the protected-byte receipt. |
| Runtime behavior unchanged | `saga.py` and `effort_rider.py` match `a736c166` byte-for-byte. |
| Unrelated lifecycle-position/Workflow prose and five rows unchanged | §5.2a except the owned note and all five non-Plan consumer rows match their baseline. Only the reviewed duplicate Plan save snippet in execution-spec becomes a link. |
| Gate/release alignment | Integrator-established 0.157.0 manifest/marketplace bytes match `2a0b0554`. All changelog headings and older bodies are unchanged. The full 25-step gate runs after the final commit; its frozen SHA, exit code and result.txt are reported separately without a later source commit. |

[Protected-byte receipt](../evidence/issue-926/protected-boundaries.json). No push, PR, merge,
board or issue mutation; no model/effort/profile change. The coordinator dispatches independent
review. The frozen gate result is implementation evidence, not a lens score.


## Unit 5: candidate/file parser parity before the frozen gate

A final audit found that `assert_regions` parsed an edited candidate as a whole document,
while an unchanged document used the shared Phase 5.3 reader. Removing the phase heading
and changing a literal path together produced `valid` and `rendered`, then twelve failing
saved-example tests after the write. The shared reader now accepts explicit text; all candidates
use it, and both missing boundary headings are tested with simultaneous output drift. Example
IDs are read from that same phase. Routing's existing default reader path stays intact.

[Before/after receipt](../evidence/issue-926/repair-phase-boundary-mutations.json): before,
validate/write exited 0 and the subsequent ordinary test exited 1 (12 failures); after,
validate/write exit 2 without edits and restored validate exits 0. The phase-parser bypass
canary and first-failure-diagnostic mutation each report `caught` from a green baseline.
The new canary joins the ordinary pytest gate (15 registered P5 controls total).

The first focused attempt correctly failed the new diagnostic assertion: twelve failure
summaries crowded out the heading error. Preflight now stops at the first failure, uses a
short traceback, and identifies the failing test file in its envelope. This is a diagnostics
change only; every scenario still executes on a healthy input. No runtime file changed.

Final narrow validation: **66 passed in 94.91s**. Full-scope mypy passed 349 files;
repository Ruff and the protected-byte audit passed. Implementation is ready to freeze for
the full gate. The final gate receipt will name this unit's commit explicitly.
