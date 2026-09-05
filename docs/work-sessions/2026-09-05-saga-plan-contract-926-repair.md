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
