# Work session — issue 1037, the shaping judgments

Built all six units of `docs/plans/2026-09-19-shaping-judgments-plan.md` on branch `issue/1037`, based on `origin/main` at commit `866d3670`. Saga bumps from `0.159.3` to `0.160.0`.

## What was built, by unit

**U1 — the module and its front door.** `plugins/saga/scripts/shaping_judgments.py`: a frozen-dataclass registry of eleven judgments, a single `judge(state, name, *, ask=...)` entry point that asks one judgment's whole question set in one request, and an argparse front door whose eleven subcommands are generated from the registry so the two cannot drift. The fleet-core client arrives through the vendored `fleet_commons_shim`, exactly as `execution_spec.py` loads its fleet modules. No HTTP, retry or redaction code was written here.

**U2 — the six ideate judgments.** `dedupe`, `axis`, `grounding-fit`, `tactical-scope`, `rubric`, `revival`. Dedupe adds pair generation and a union-find grouping bounded by a named cap of 64 candidates. Tactical scope gained a real code-level union, `tactical_scope_union`, carrying ideate's own keyword list — the plan said the keyword list was a floor, and a floor written only in prose is not a floor.

**U3 — the four brainstorm judgments.** `scope-tier`, `consequence`, `question-order`, `readiness`. The consequence factors and the seven readiness criteria are each one named list in the module.

**U4 — the office-hours routing choice.** `route`, over the five Phase 3 destinations, returning the full distribution.

**U5 — the skill wiring.** A short advisory-judgments section in each of the three skills, plus pointers in the ideate convergence reference (rubric and revival) and the brainstorm requirements-section contract (readiness). No existing question, rule, gate or prohibition was rewritten.

**U6 — release surfaces and journal.** Saga `0.160.0` across `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md` and the version pin in `tests/test_saga_plugin.py`, plus three `DECISIONS.md` entries in the same commit.

## The open P2 from the doc review, resolved

The doc review left one question open: whether a declined judgment or a failed call still records a verdict. **It does not.** That follows `plugins/fleet-core/scripts/jev.py`, which returns before its logging block on any non-`ok` status: the evaluation harness joins answers to labels on `decision_id` and scores agreement per confidence band, so a record with no answer has nothing to score and would only inflate the denominator of "thirty real uses" with calls the model never made. Recorded as `DECISIONS.md {#verdicts-for-answers-only-1037}`.

## Change kinds

`change_kinds = ["behavior", "docs"]`. Behavior is in the list, so `requires_hard_test_gate` applies and the gate is satisfied: `tests/test_shaping_judgments.py` carries 41 tests covering every unit.

## Guard discipline — watched failing before trusted

Three guards were verified by mutation rather than by assertion that they work.

The four U5 skill-wiring guards were written before the skill edits and run: they failed, naming the three skills that did not yet call the module. They pass now.

Two behavioral mutations were then applied to the finished module and the suite re-run. Making `dedupe_groups` return only the first member of each group killed `test_grouping_never_removes_a_candidate` and `test_matched_candidates_share_one_group` — which is the exact failure the plan's third decision forbids. Adding `axis_spread` back to the per-idea rubric killed `test_the_rubric_excludes_axis_spread`. The module was restored from a copy and the suite returned to green.

## Live verification

The card's first acceptance criterion ran against a real requirements document — the issue 1031 brainstorm, taken from the integration branch `parent/1018` — and printed one probability per readiness criterion at exit 0. Seven criteria, seven probabilities. Two are worth naming because they read as correct rather than as noise: acceptance examples came back at 0.11, and that document indeed has no acceptance-examples section, while "could a planner proceed cold" came back at 0.55 with a confidence of 0.10, which is the model correctly reporting that it cannot tell. `TYPESAFE_API_KEY` was confirmed present by testing the variable's length; it was never printed and appears in no file this card creates.

## Checks run

Inner loop, all green: `ruff check`, `ruff format --check`, `mypy plugins/ scripts/ tests/`, the touched tests plus the two brainstorm guard files (146 passed), `check_release_surface_parity.py`, `release_surface_diff_guard.py --base-ref origin/main`, `sync_marketplace.py --check`, `marketplace/validator/validate.py` (15 plugins, 0 errors), and `lint_journal_order.py`. The full suite across both pytest roots ran before the push.

Two repairs were needed during the loop: `ruff format` reformatted the two new files, and mypy caught one `no-any-return` in the test file's fake-client factory, fixed by typing the `result` override explicitly instead of passing it through `**overrides`.

## Decisions carried from the coordinator

Every known-set choice in this stage was answered in advance by the coordinator's message; each is recorded here with that message as its source.

| Choice | Answer | Source |
|---|---|---|
| Saga | resume `issue-1037`, never mint a second | coordinator message |
| Branch | stay on `issue/1037` | coordinator message |
| Execution backend | `inline`, which the plan's frontmatter already recorded, so the skill honours it without offering | plan frontmatter, confirmed by the coordinator |
| Doc-review gate | passed, no override needed or permitted | `docs/reviews/2026-09-19-shaping-judgments-plan-doc-review.md` |
| Complexity triage | Large by file count (11), executed inline | skill default; the units overlap on one file, which the Parallel Safety Check downgrades to serial regardless, and this run spawns no subagents |
| Front-loaded ship ceremony | declined | the coordinator directs `gh pr create` instead, as an authorized and recorded fallback |
| Board moves | Designing, Ready for Active and Implementing submitted; all three returned `written` with `field` reading `Stage+Status` | coordinator message |
| Merge | not offered; the coordinator merges after checks pass | coordinator message |

## Next step

Open the pull request to `main` and hand back to the coordinator.
