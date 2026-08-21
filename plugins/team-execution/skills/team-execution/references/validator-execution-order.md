# Validator Execution Order - team-execution

Validators run after implementation and a Code Review transition that permits progression.

---

## Phase B Order

1. Workers complete changes.
2. Team Execution collects reviewer evidence and invokes Saga's shared review scorer and transition
   engine.
3. Scanners run against local artifacts and code.
4. PR/CI/merge/nonprod coordination happens only if scanner gates pass.
5. Testers validate deployed nonprod results.
6. Monitors verify CI and runtime signals.
7. Completion reports evidence and residual risk.

A nonterminal review result blocks validators unless the user explicitly overrides. Team Execution
does not infer that state from reviewer prose or a private cutoff.

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

---

## Required-Evidence Absence (completeness gate)

At completion (Step B7), every **required, non-skipped** validator and leaf must have written an
evidence record (see `validator-evidence-state.md`). A required validator whose evidence record is
**absent at process exit** — and that was never marked `skipped-by-config` — is a `missing-output`
trip: a silent omission, where work that was supposed to produce evidence produced none. Treat it
as a completion block, exactly like a hard-fail finding; do not report completion.

A validator that is **`skipped-by-config`** (selected out — `required: false`, listed in
`disabled_validators`, or otherwise legitimately not run with a recorded `selection_reason`) is
**not** a trip. Its absent evidence is expected and is reported under "Skipped validators and why".

The distinction is the whole point of the gate: absence of evidence for something that was
*supposed to run* is the omission to catch (`missing-output`); absence for something deliberately
*not run* is normal. Checking only the recorded gate results misses the validator that silently
never ran at all.
