# Issue #454 Blind External-Engine Divergent Generator Code Review

| field | value |
|---|---|
| target | `work/454-blind-divergent-generator` vs `origin/main` |
| reviewed revision | `707da44510fffd15b394add5071c9b11d8ba9aa5` |
| merge base | `19180750bd8c35d619e762aa9ff605c5936630c3` |
| linked issue | `infiquetra/infiquetra-claude-plugins#454` |
| plan | `docs/plans/2026-07-09-issue-454-blind-external-engine-divergent-generator-plan.md` |
| work session | `docs/work-sessions/2026-07-09-issue-454-blind-external-engine-divergent-generator.md` |
| orchestration mode | `inline` |
| blocked | no |

## Review Team

- correctness - always-on; checked generator-lane wait boundary, merge provenance, and no gate
  exemption.
- security - always-on; checked that external-engine output remains provenance-only and does not gain
  authority over Phase 3 scoring.
- testing - always-on; checked structural tests pin dispatch, blindness, provenance, no-exemption, and
  graceful degradation.
- maintainability/conventions - always-on; checked release surfaces, changelog, marketplace, and
  journal alignment.
- reliability - selected because the diff defines external dispatch failure behavior.
- agent-native - selected because `/ideate` is the operator-facing skill surface.
- adversarial/red-team - selected because the change introduces an external-engine generation path and
  must not create a privileged survivor route.

No deploy/migration, performance, or API-contract lens was selected; the diff does not touch deploy
state, runtime data paths, public schemas, or query/performance-sensitive code.

## Scope Check

Scope Check: CLEAN

Intent: Add one blind, best-effort external-engine divergent-generator lane to `/ideate` Phase 2, with
`engine-generated` provenance and no Phase 3 scoring exemption.

Delivered: The diff updates `/ideate` skill docs, convergence/artifact references, structural tests,
release metadata, changelog, journal, plan, plan review, work-session receipt, and this review artifact.

## Plan Completion

| unit | status | evidence |
|---|---|---|
| U1 - Phase 2 external-engine lane contract | DONE | `plugins/saga/skills/ideate/SKILL.md:505` names `offload` with `sonnet/medium`; `plugins/saga/skills/ideate/SKILL.md:509` requires the same substituted prompt inputs; `plugins/saga/skills/ideate/SKILL.md:516` records non-blocking failure behavior; `tests/test_ideate_engine_lane.py:40` pins the merge boundary. |
| U2 - engine-generated provenance surfaces | DONE | `plugins/saga/skills/ideate/SKILL.md:524` tags only external-lane candidates; `plugins/saga/skills/ideate/references/ideation-artifact.md:60` adds `engine-generated` as provenance only; `plugins/saga/skills/ideate/references/ideation-artifact.md:97` shows it entering through Phase 2. |
| U3 - no-exemption convergence contract | DONE | `plugins/saga/skills/ideate/references/convergence-and-partnership.md:40` says `engine-generated` uses the same rejection criteria and survivor scoring; `plugins/saga/skills/ideate/references/convergence-and-partnership.md:106` lists it as source provenance only; `tests/test_ideate_engine_lane.py:92` pins the tag in the no-exemption note. |
| U4 - release surfaces and journal | DONE | `plugins/saga/.claude-plugin/plugin.json:3`, `.claude-plugin/marketplace.json:86`, `plugins/saga/CHANGELOG.md:3`, `tests/test_saga_plugin.py:48`, and `docs/engineering-journal/DECISIONS.md:5` all align on the #454 release surface. |

COMPLETION: 4/4 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

## Findings

No open P0, P1, P2, or P3 findings remain.

### Resolved During Review

| severity | status | finding | evidence | resolution |
|---|---|---|---|---|
| P2 | resolved | The merge boundary heading still said "After all frame agents return," which could imply the external generator lane was not included in the wait/merge boundary. | Pre-fix `plugins/saga/skills/ideate/SKILL.md` heading; plan required merge after available generators returned. | Commit `707da44` changed the heading to `After all available generator lanes return` and updated `tests/test_ideate_engine_lane.py` boundary assertions. |

## Validation

- `uv run pytest tests/test_saga_doc_formatting.py tests/test_ideate_engine_lane.py tests/test_saga_plugin.py -v` - 65 passed.
- `uv run python scripts/sync_marketplace.py --check` - passed.
- `uv run python scripts/check_release_surface_parity.py` - passed.
- `uv run ruff check .` - passed.
- `uv run ruff format --check .` - 277 files already formatted.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` - success, no issues in 170 source files.
- `git diff --check 19180750bd8c35d619e762aa9ff605c5936630c3` - passed.

The work-session receipt also records a broader pre-clarity-fix local pytest run:
`COVERAGE_FILE=/tmp/cov-454-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`
with 2665 passed and 1 skipped. The final post-fix change was markdown/test boundary wording, so the
focused Saga contract suite was rerun on the reviewed SHA.

## Coverage

Suppressed findings: 0.

Residual risks: no live external engine was invoked, by design. This change is a markdown-runtime
contract with structural tests; CI should still run the normal repository checks after PR creation.

Testing gaps: the direct `uv run bandit -r plugins/ -q` attempt reported pre-existing repo-wide findings
outside this markdown/test/release-metadata diff. It is not counted as a passing gate in this review.

> Verdict: unblocked for PR. No open P0/P1 findings remain.
