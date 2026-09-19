# Work session — issue 1022, roles library

Built the roles library in `plugins/agent-launcher/roles/` from the plan at
`docs/plans/2026-09-19-issue-1022-roles-library-plan.md`. All seven implementation units landed in
four commits on branch `issue/1022`, based on commit `2044c363`.

## What was built, by unit

**U1 — the directory contract.** `plugins/agent-launcher/roles/README.md`. States the four required
headings, the four frontmatter keys, the role-to-file map, and the accounting for where each of the
25 retired `team-execution` prompts went. It also states its own two exemptions: it carries no
stop-rule heading, and it is the one file allowed to name the retired plugin.

**U2 — nine shaping, planning and control prompts.** `product.md`, `issue-reviewer.md`,
`planner.md`, `architect.md`, `delivery-manager.md`, `implementer.md`, `plan-reviewer.md`,
`review-controller.md`, `investigator.md`.

**U3 — three repair and release prompts.** `standard-repair-implementer.md`,
`expert-repair-implementer.md`, `release-worker.md`. The Release Worker absorbs the two retired
monitors and the deploy watcher as a "waiting for checks" section.

**U4 — the Lens Reviewer.** `lens-reviewer.md`, a shared reviewer half plus fifteen sections keyed
`#### <lens-id>` to the lifecycle's lens catalogue. It states no threshold of its own.

**U5 — the Functional Tester.** `functional-tester.md`, folding the eight retired tester prompts
into named strategies.

**U6 — the structural test.** `tests/test_roles_library.py`, 77 tests passing.

**U7 — release surfaces and journal.** `agent-launcher` 1.5.2 to 1.6.0 across the manifest, the
marketplace registry and the changelog; two `LEARNINGS.md` entries and four `DECISIONS.md` entries.

## Key decisions taken during execution

Everything load-bearing was settled in the plan. Two things were decided while building.

**The stop-rule check had to be anchored to a line start.** The card's acceptance criterion is an
unanchored `grep -L`, and it came back empty rather than naming the README, because the README
quotes the heading it mandates. The test uses the anchored form and asserts the README's exemption
positively. Recorded as a learning.

**The frontmatter parser had to understand an inline empty list.** `emits: []` on the Lens Reviewer
parsed as the string `"[]"`. Fixed with a seeded fixture for both spellings. Recorded as a learning.

## Files modified

Added: `plugins/agent-launcher/roles/README.md` and fourteen role prompts;
`tests/test_roles_library.py`; `docs/plans/2026-09-19-issue-1022-roles-library-plan.md`;
`docs/reviews/doc-review-issue-1022-2026-09-19.md`; this file.

Modified: `plugins/agent-launcher/.claude-plugin/plugin.json`,
`plugins/agent-launcher/CHANGELOG.md`, `.claude-plugin/marketplace.json`,
`docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`.

Deleted: nothing. The `team-execution` files are untouched; their removal is a separate issue.

## change_kinds

`["docs", "test", "config"]`

`requires_hard_test_gate(["docs", "test", "config"])` returns `False`. The change adds prompt text,
a structural test and release metadata; it adds no runtime behaviour, touches no security,
infrastructure, interface, deployment or data surface. The structural test is the coverage the
change earns, and it exists.

## Checks run

| Check | Result |
|---|---|
| `uv run pytest tests/test_roles_library.py -q` | 77 passed |
| `uv run ruff check tests/test_roles_library.py` | clean |
| `uv run ruff format --check tests/test_roles_library.py` | clean |
| `uv run mypy tests/test_roles_library.py --ignore-missing-imports` | clean |
| `scripts/check_release_surface_parity.py` | all plugins in parity |
| `tools/release_surface_diff_guard.py --base-ref 2044c363` | all changed plugins bumped |
| `scripts/lint_journal_order.py`, structural and `--base-ref 2044c363` | 0 violations |
| `scripts/sync_marketplace.py --check` before writing | only `agent-launcher` stale |
| `scripts/check_mermaid.py` | 25 fences across 31 files parsed |
| Card acceptance: file count | 15, floor is 14 |
| Card acceptance: anchored stop-rule grep | prints only the README, as intended |

## Answers taken from the coordinator, not asked

The coordinator supplied every choice these skills would otherwise put to the operator. Recorded
here as the skill requires.

| Question | Answer taken |
|---|---|
| Resume or mint a saga | Resume `issue-1022`; matched on plan path and branch |
| Branch | Stay on `issue/1022` |
| Execution backend | `inline`, honoured from the plan's `backend:` frontmatter without an offer |
| Doc-review gate | Passed, zero open findings; no override needed |
| Complexity triage | Large — 20 files across two plugins, tests and release surfaces. Plan-doc input, so no bounce to planning |
| Board moves | Submitted through the reconcile controller; both halves landed each time |
| Pull request | None. This card merges onto the integration branch by merge turn, performed by the coordinator |
| Ship ceremony | Not run; not pushed |
| Front-loaded draft pull request offer | Declined, per the no-pull-request instruction |
| Hard test gate | Not triggered by the derived change kinds |

## Next step

Run `/code-review` against this branch's diff from `2044c363`, repair any finding at priority P0 or
P1, and return to the coordinator for the merge turn.
