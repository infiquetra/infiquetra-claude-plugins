---
issue: infiquetra/infiquetra-claude-plugins#808
plan: docs/plans/2026-08-25-improve-claude-plugins-run-plan.md
branch: orch/orch-2026-08-25-814-u-808-evidence
status: phase-A
orchestration: inline
---

# Work session — #808 Claude Code Workflow backend decision (U10 phase A)

## Scope

Execute **only** plan section U10 phase A of
`docs/plans/2026-08-25-improve-claude-plugins-run-plan.md`. Evidence-gathering and
decision record. The operator's G1 ruling is NARROW and binding
(issuecomment-5405414716). This session validates and documents that ruling. It does
not re-present keep / narrow / replace / retire as an open menu, and it does not
implement Phase B skill-text edits (`plugins/saga/skills/plan/SKILL.md`,
`plugins/saga/skills/work/SKILL.md`, `execution_spec.py`) — those serialize after
lane S2 (#776).

## First action

`git fetch origin && git merge origin/main` — already up to date. Pin:
`58ce3079` on this branch; `origin/main` `ebe476d4` is an ancestor.

## Backend and engine

Plan frontmatter is `backend: inline`. Honoured; not re-offered.
`engine_offer.py offer --stage work --repo-root . --attended` returned stored
preference `intent: none`. No prompt.

## What was built (U10 phase A)

- Inventory of every producer, executor, generated artifact, and committed spec the
  leaf sweep surfaces, plus the pin re-count of specs and verify panels.
- Quantified unique findings, false halts, retries, token/session cost, and
  operational failures, each with a durable work-session or LEARNINGS link.
- Decision entry
  `docs/engineering-journal/DECISIONS.md`
  `{#cc-workflows-backend-narrow-808}` validating the recorded NARROW ruling.
- Contradiction check: no HALT. The narrowed shape is implementable. Residual is
  Phase B (stop offering this backend as a default/automatic third choice).

## Pin counts

| Measure | Leaf baseline | Pin (`58ce3079`) |
| --- | --- | --- |
| Committed `*-spec.json` | 16 | 20 |
| Verify blocks `n=3` / majority | 37 | 37 (still all `n=3`; 0 engine-routed) |
| Generated `*.workflow.js` | (unstated) | 21 |
| Sweep hit lines / files | (unstated) | 750 / 136 |

The extra four specs have no verify block. Sixteen specs still carry the 37 panels.

## Checks run

Substituted documentation checks (leaf named `python3 scripts/check_docs.py`, which
does not exist): `python3 scripts/lint_journal_order.py`;
`uv run python scripts/changelog_heading_lint.py` where applicable;
`git diff --check`. Plus
`uv run pytest tests/test_saga_execution_spec.py tests/test_saga_plugin.py -q`.

`gh issue view 787 --json state -q .state` → `CLOSED`; twenty children remain
`CLOSED`.

`gh issue list --search "cc-workflows in:title,body" --state open` named #808
(Phase B still open), #708 (G3 follow-up), and parent #814.

## Key decisions

- Do not close #808 from this PR. Phase B implements the narrowed shape.
- Do not write the project board (orchestrate single-writer is the parent session).
- Do not run Saga Code Review here (the run's review unit owns the frozen head).
- Do not touch #787 or its children.

## Files modified

- `docs/engineering-journal/DECISIONS.md`
- `docs/work-sessions/2026-08-25-issue-808-cc-workflows-backend-decision.md`

## Next step

Phase B of #808, after lane S2 (#776) lands: make plan/work skill text state that
explicit invocation is the only path to a Claude Code Workflow.
