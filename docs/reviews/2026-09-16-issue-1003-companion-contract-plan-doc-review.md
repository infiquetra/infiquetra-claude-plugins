---
title: Issue 1003 Orchestrate / Agent Launcher companion-contract — plan document review
type: review
status: complete
date: 2026-09-16
assignment: issue-1003-plan-doc-review
verdict: accepted
blocked: false
candidate: working tree after plan repairs
reviewed:
  - docs/plans/2026-09-16-issue-1003-companion-contract-plan.md
  - docs/plans/2026-09-16-issue-1003-companion-contract-finite-test-plan.md
---

# Issue 1003 Orchestrate / Agent Launcher companion-contract — plan document review

The plan can drive `/work`. Remaining P0 and P1 findings were repaired in the plan before implementation.

## Applied fixes

D1. U1 now keeps the operator-visible fault `_bind_missing_launcher_names` already prints (`does not define {names}` plus the update remedy) for AST-missing names, so the existing write-side test family is not rewritten onto a new error dialect. A name-only stub uses that same family, not `not found`.

D2. KTD4 and TP-F101 now say the pairing test compares the shipped tree to `REQUIRED_LAUNCHER_NAMES` and does not encode semver. A later major bump updates the tuple and the floor together.

D3. U2 and the finite plan now name the agreement assertions in `tests/test_orchestrate_land_clean.py` and `tests/test_orchestrate_run_branch_resolution.py` as usable-companion cases that stay green, alongside `test_a_clean_run_reports_nothing`.

D4. U1 now states that `_validated_agent_launcher` remaining the floor check is not F106; F106 is the AST usability probe, and floor failures still exec.

D5. U1 AST collection counts assignment targets, so `ComposerState = _COMPOSER.ComposerState` in `launcher.py` satisfies the name. TP-F101 says the same. `cmd_status` keeps branching on `_AGENT_LAUNCHER_AVAILABLE`; no third flag.

## Readiness summary

Issue-phase cores: acceptance criteria map to named pytest functions in the finite test plan; devil's advocate finds one classification (missing / below-floor / ingested-but-unusable / usable) rather than eight designs; spec fidelity traces each R-ID to a child of #1003. No remaining P0 or P1.

## Remaining findings

| ID | Priority | Status | Finding |
|---|---|---|---|
| — | — | none | No remaining P0–P3. Residual: a stub that copies a `pane_input_inspection(...)` call shape can still pass the AST probe; the named F106 scenario is names-as-`return None`, which the probe refuses. |

## Rubric notes

| Rubric | Score | Note |
|---|---|---|
| acceptance_criteria_clarity | 9 | Each R-ID names a shipped function or CLI entry and a TP-* test. Error-string contract was the load-bearing hole; D1 closed it. |
| devils_advocate_issue | 9 | Eight findings, one classification, one PR. Below-floor is kept distinct so F107 cannot be implemented by collapsing KTD7 of #907. |
| spec_fidelity | 9 | Origin is issue 1003 plus the finite test plan. Non-goals match the parent. Floor stays `>=1.4.0`. |
| context_completeness | 9 | File paths and `orchestrate.py` line anchors are named. |
| issue_sizing | 8 | Eight children in one PR is the OBJECTIVE's grouping, not a hidden spec. |
| prerequisite_mapping | 9 | Issue 1002 restored `PANE_INSPECT_MAX_CHARS`; F111's cap half is named as already holding. |

## Review-result contract

- target path: `docs/plans/2026-09-16-issue-1003-companion-contract-plan.md`
- reviewed revision: working tree after D1–D5
- blocked: false
- linked issue: #1003
