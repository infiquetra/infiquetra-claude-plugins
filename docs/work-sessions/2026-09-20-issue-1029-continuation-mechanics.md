---
issue: infiquetra/infiquetra-claude-plugins#1029
plan: docs/plans/2026-09-20-issue-1029-continuation-mechanics-plan.md
review: docs/reviews/doc-review-issue-1029-2026-09-20.md
branch: issue/1029
date: 2026-09-20
---

# Work session — issue 1029, continuation mechanics

Built the five units of the plan on `issue/1029`, branched from `parent/1018` at `b98e94ea`.
There is no pull request and no per-card code review for this card by operator decision on
2026-09-19: the parent pull request (issue 1030) carries one code review for the whole parent, and
each card proves itself with tests, the full suite, and the merge onto the integration branch.

## The decisions taken, and where each came from

Every choice the `/work` skill would have asked was supplied by the run coordinator up front. None
was invented here, and none is a production, destructive, credential, permission, billing,
external-commitment, or process-authority decision.

| Choice | Taken | Source |
|---|---|---|
| The open question on `/plan` continuing into `/work` | KTD4 stands as written | The run coordinator, 2026-09-20, from the card's own objective and the operator's standing direction for parent 1018 that the lifecycle steps run automatically with the answers taken at admission |
| The preservation contract beside it | Pull-request open, review request, and merge stay explicitly confirmed; a continuation that would fire one without a confirmation is a stop | The same message; implemented in `/work` §5.4 and guarded by `test_the_preservation_contract_survives_in_work` |
| Saga | Resumed `issue-1029` from this worktree's store; no second saga minted | The coordinator's message |
| Branch | Stayed on `issue/1029` | The coordinator's message |
| Execution backend | `inline` | The plan's `backend:` frontmatter and the `plan_pre_answers.v1` carrier |
| Document-review gate | Passed with nothing above `P2` open; no override needed or permitted | `docs/reviews/doc-review-issue-1029-2026-09-20.md` |
| Code review | None in this stage | Operator decision, 2026-09-19 |
| Complexity triage | Fresh build, not a round-N re-entry | The skill's documented default; no prior pull request exists for this card |
| Ceremony start | Declined | It opens a draft pull request, and this card opens none |
| The card's third acceptance criterion | Proved by invoking the hook script directly against a temporary repository and record, both cases | The coordinator's message |
| Version | saga 0.167.0 | `origin/parent/1018` read at `b98e94ea` showing 0.166.0, immediately before the bump |

## Board moves

| Move | Result |
|---|---|
| `Planning` / `Designing` (at the start of planning) | `written`, `field: Stage+Status`, one attempt |
| `Planning` / `Ready for Active` (after the plan review passed) | `written`, `field: Stage+Status`, one attempt |
| `Active` / `Implementing` (at the start of the build) | `written`, `field: Stage+Status`, one attempt |

The `/work` skill's two terminal moves — `Verify` / `Awaiting verification` and `Retro` / `Ready to
close` — were **not** submitted, and the skill's own rule is why: all four of its stated conditions
must hold, and the first two do not. This card has no merged pull request of its own and no closed
sub-issue; the parent's pull request carries both. Submitting either move here would claim a state
the card has not reached.

## What was built

**U1 — the suppression rule, in one place.** `plugins/saga/scripts/next_step_context.py`. It
resolves the issue from this worktree's active saga and then from an `issue/<N>` branch name, loads
the run record from the primary checkout's store, and returns the step or nothing. It is a module
of its own rather than a function on `run_record` because `saga_spore` imports `saga` and `saga`
imports `run_record`, so a resolver on the record would close an import cycle that the lazy import
would then hide at runtime.

**U2 — the session-start hook.** `plugins/saga/hooks/next_step_session_hook.py`, registered for
`startup|resume`. The matching suppression landed in `saga_spore.serialize()` so the compaction
boundary and the cold start read one rule.

**U3 — the suggestion hook.** `plugins/saga/hooks/prompt_suggestion_hook.py`, registered on
`UserPromptSubmit`, local matching only.

**U4 — the endings.** `/plan` §5.6, `/doc-review`'s closing section, `/work` §5.4 and §5.5,
`/code-review` §5.4, `/qa` §6.1 and §6.2, plus the two shaping-skill wordings.

**U5 — the release surfaces and the journal.** saga 0.167.0 across the plugin manifest, the
marketplace, the changelog and the version literal in `tests/test_saga_plugin.py`; two `LEARNINGS`
entries and three `DECISIONS` entries.

## Two findings worth carrying out of the build

**A bug the tests found in the matcher, not in the plan.** A recorded next step is ordinarily
written "run /work on the plan" — which names two commands if you match bare words over the whole
sentence, and so read as ambiguous and produced silence in every realistic case. The fix reads the
slash form first: exactly one distinct `/name` wins, and only when there is none does a bare-word
match apply. `test_the_slash_form_wins_over_a_command_word_in_the_rest_of_the_step` pins it.

**An unborn branch has no `rev-parse --abbrev-ref HEAD`.** The first branch-resolution test failed
against a freshly initialized repository with no commit. `symbolic-ref --short HEAD` answers there;
`rev-parse` does not, and on a detached head it prints the bare word `HEAD`, which is not a branch
name. Both are handled.
