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
