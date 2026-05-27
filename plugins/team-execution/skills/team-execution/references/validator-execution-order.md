# Validator Execution Order - team-execution

Validators run after implementation and reviewer consensus.

---

## Phase B Order

1. Workers complete changes.
2. Reviewers reach consensus.
3. Scanners run against local artifacts and code.
4. PR/CI/merge/nonprod coordination happens only if scanner gates pass.
5. Testers validate deployed nonprod results.
6. Monitors verify CI and runtime signals.
7. Completion reports evidence and residual risk.

Reviewer non-consensus blocks validators unless the user explicitly overrides.

---

## Remediation Loops

Scanner and tester hard-fails may enter remediation:

1. Route finding to the responsible worker.
2. Worker fixes the issue.
3. Re-run only affected validators and relevant checks.
4. Record the loop in validator state.

Run a maximum of 3 remediation loops. After the third failed loop, escalate to the user with
evidence, attempted fixes, and remaining risk.

---

## Blocking Rules

Hard-fail scanner or tester findings block:

- Auto-merge.
- Nonprod deployment or publish.
- Completion.

Monitor blocked signals block completion only when the signal was required for the selected
workflow. Otherwise, report a warning.
