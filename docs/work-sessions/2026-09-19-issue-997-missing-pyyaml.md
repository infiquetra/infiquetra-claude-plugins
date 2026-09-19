# Work session — issue 997, a missing PyYAML outside the plan_save_contract envelope

**Date:** 2026-09-19 · **Issue:** infiquetra/infiquetra-claude-plugins#997 · **Parent grouping:** #1005
**Plan:** `docs/plans/2026-09-19-issue-997-plan-save-contract-missing-pyyaml-plan.md`
**Doc review:** `docs/reviews/doc-review-issue-997-2026-09-19.md` (passed, no P0 or P1)
**Branch:** `issue/997` · **Base:** `9f1bae8a` · **Saga:** `issue-997` (resumed, never re-minted)

## What was built

**U1 — deferred the PyYAML import and the loader class.** `plugins/saga/scripts/plan_save_contract.py`
no longer imports PyYAML at module scope. `yaml_module()` imports it at first use and converts an
`ImportError` into the documented refusal; `unique_loader(yaml)` builds the duplicate-key loader
against the module that call returns, because `class UniqueLoader(yaml.SafeLoader)` needs the real
base class at class-creation time and so could not stay at module scope either. A new `TOOL`
constant holds this script's repo-relative path; `verify_saved_examples` now uses it instead of
re-spelling the same literal.

**U2 — the guard.** `test_contract_cli_envelopes_a_missing_pyyaml` in
`tests/test_saga_plan_contract_boundaries.py` builds a throwaway virtual environment with PyYAML
genuinely absent — it asserts the absence first, so it cannot pass by finding a system copy — and
drives the real command line through it: `validate`, `render --check` and `render --write` each
return exit 2 with `code: engine`, `entry: python dependency`, `file:
plugins/saga/scripts/plan_save_contract.py` and `PyYAML` in the error; no owned document changes;
`--help` returns usage at exit 0 and is not JSON; and the same checkout under the suite's own
interpreter still validates.

**U3 — the canary.** `tools/canary_registry.json` gained `plan-save-contract-missing-pyyaml`, whose
mutation hoists the import back to module scope.

**U4 — release surfaces and journal.** Saga `0.159.1` to `0.159.2` across
`plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md` and the drift-guard literal in `tests/test_saga_plugin.py`. One
`LEARNINGS.md` entry and one `DECISIONS.md` entry.

## Watching the guard fail before it passed

Twice, in both directions, in the real condition the plan's decision names.

1. Before the fix, the new guard failed against the unmodified script:
   `ModuleNotFoundError: No module named 'yaml'` at `plan_save_contract.py:26`, exit 1, no JSON.
   A genuinely empty virtual environment, not the `PYTHONPATH` stub the card used.
2. After the fix it passed. The canary then re-proved it mechanically: entry
   `plan-save-contract-missing-pyyaml` reports `result: caught` with `baseline_exit: 0`, which is
   the guard passing on clean code and dying on the reverted fix.

The canary's `guard` string and the test function name were verified to match by running the canary
and reading its verdict, not by comparing the two strings by eye.

## Key decisions

Carried from the plan, unchanged during execution: defer the import rather than sentinel it (KTD1);
reuse the existing `engine` code rather than open the closed error-code set (KTD2); leave `main()`'s
narrow handler alone (KTD3); prove it in a real virtual environment (KTD4).

## Files modified

- `plugins/saga/scripts/plan_save_contract.py`
- `tests/test_saga_plan_contract_boundaries.py`
- `tests/test_saga_plugin.py`
- `tools/canary_registry.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/engineering-journal/DECISIONS.md`

## change_kinds

`behavior`

The tool's observable command-line behaviour changes on an interpreter without PyYAML, so
`requires_hard_test_gate(["behavior"])` applies and the hard test gate is satisfied by U2's guard
plus U3's canary. Nothing here touches security, infrastructure, an API surface, deployment or
data.

## Choices, and where each answer came from

`AskUserQuestion` was unavailable for this run. Every known-set choice was answered by the
coordinator's stage-two instruction unless noted; none was invented.

| Choice | Answer | Source |
|---|---|---|
| Resume or mint a saga | Resume `issue-997` | Coordinator's stage-two message; `saga.py scan` matched one candidate |
| Branch | Stay on `issue/997` | Coordinator's stage-two message |
| Execution backend | `inline` | The plan's `backend:` frontmatter; the skill honours the field and does not offer |
| Doc-review gate | Passed, no override | `docs/reviews/doc-review-issue-997-2026-09-19.md`; coordinator confirmed no override is permitted |
| Complexity triage | Small-medium, task list from the U-IDs | Skill default for four units; coordinator directed documented defaults |
| Round-N detection | Fresh build, round 1 | The restored saga carried no `pr_refs` |
| Ship-ceremony draft-PR offer (§1.4) | Declined | Coordinator directed the `gh pr create` fallback because the ceremony's worktree path is invasive to the shared checkout |
| Front-loaded second opinion | Not triggered | No target failed three fix attempts |
| Mission Control board moves | Submitted as the skill says | Coordinator's stage-two message |
| Merge confirmation | No | Coordinator merges after the required checks pass |
| Continuation routing | Return to the coordinator | Coordinator's stage-two message |

## Next step

Code review on the branch against base `9f1bae8a`, then open the pull request to `main`.
