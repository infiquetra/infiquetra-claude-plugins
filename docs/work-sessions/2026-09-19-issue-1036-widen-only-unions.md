# Work session — issue 1036, widen-only unions for the flags and the journal nudge

Executed `docs/plans/2026-09-19-issue-1036-widen-only-unions-plan.md` inline, on branch `issue/1036` in a worktree, from `origin/main` at `866d3670`.

## What was built, by unit

**U1 — the widen-only union primitive.** `plugins/fleet-core/scripts/fleet_commons/jev_widen.py`. One function, `widen(state, verb, floors, ...)`, asks a verb's yes/no questions in one request and returns per key the floor, the probability, the union (`floor or probability >= threshold`) and which side produced it. Every failure path returns the caller's floors unchanged with a reason in `note` and writes no verdict. `ask` defaults to `typesafe_client.ask` and is a parameter, which is what makes "no test touches the network" a mechanism rather than a promise.

**U2 — two verbs in the registry.** `issue-flags` (twelve yes/no questions: the five keyword flags plus the seven approval boundaries, at a confidence floor of 0.70) and `journal-nudge` (one question at 0.60). Both become `jev` subcommands automatically, because the tool builds its subcommands from the registry.

**U3 — `--flags` and `--issue` in `parse_issue.py`.** `extract()` is untouched, so the default invocation is byte-identical and carries no fleet-core import. `--flags` adds `flags_detail`, `approval_boundaries` and `judgment` to the JSON, with the five flag keys now holding the union under their existing names. `--issue <N>` reads the body with `gh`.

**U4 — the widened journal nudge.** The hook asks only when the `feat`/`fix` floor did not already nudge and every existing precondition holds. It reads HEAD's real commit message rather than re-parsing the shell command, sends nothing but that message and the changed file list, asks once with a two-second timeout inside a three-second deadline, and prints nothing on any failure. `INFIQUETRA_TYPESAFE_JOURNAL_NUDGE=off` skips the call.

**U5 — documents, release surfaces, journal.** Section 5 of `plugins/fleet-core/references/typesafe.md`; a one-line note at each of the four saga call sites; saga 0.159.3 to 0.160.0 and fleet-core 0.26.0 to 0.27.0 across the plugin manifests, the marketplace registry, both changelogs and the four version literals in tests; two `DECISIONS.md` entries and two `LEARNINGS.md` entries.

## Key decisions taken during execution

The code-file precondition in the hook is deliberately **not** widened. The model widens which *message* earns an entry, not which *kind of file* does — which keeps documentation commits, the bulk of this repository, off the wire and the widen to one dimension.

A `feat`/`fix` commit never asks. The floor already nudges, so a question could only agree and would cost a request on every such commit.

An autouse fixture defaults the judgment **off** for the whole of `tests/test_journal_nudge_hook.py`. Widening a decision moves the early exit later, so tests written against a wholly local function suddenly reach the network; recorded as a learning.

## change_kinds

`behavior|api|docs`

`requires_hard_test_gate(["behavior", "api", "docs"])` is true, and the gate is satisfied: 16 new tests for the primitive, 13 for the flag union, 20 added to the hook's existing file, 4 added to the verb registry's. Each new guard was watched failing before it passed — the union expression, the `--flags` union and the hook's widen branch were each mutated in turn and the naming test died, then the mutation was reverted.

## Checks run

`pytest|ruff|ruff-format|mypy|release-surface-parity|release-surface-diff-guard|marketplace-sync|marketplace-validator`

## Files modified

`plugins/fleet-core/scripts/fleet_commons/jev_widen.py` (new), `plugins/fleet-core/scripts/fleet_commons/jev_verbs.py`, `plugins/fleet-core/references/typesafe.md`, `plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/fleet-core/CHANGELOG.md`, `plugins/saga/scripts/parse_issue.py`, `plugins/saga/hooks/journal_nudge_hook.py`, `plugins/saga/skills/plan/SKILL.md`, `plugins/saga/skills/work/SKILL.md`, `plugins/saga/skills/work/references/test-and-gates.md`, `plugins/saga/skills/loop/SKILL.md`, `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`, `.claude-plugin/marketplace.json`, `tests/test_jev_widen.py` (new), `tests/test_parse_issue_flags.py` (new), `tests/test_jev_cli.py`, `tests/test_journal_nudge_hook.py`, `tests/test_saga_plugin.py`, `tests/test_liveness_events.py`, `tests/test_team_execution_liveness.py`, `docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`.

## Choices answered by the run coordinator, not asked

The operator question tool was unavailable; each of these came from the coordinator's instruction for this stage.

| Choice | Answer taken |
|---|---|
| Saga | Resume `issue-1036`; never mint a second |
| Branch | Stay on `issue/1036` |
| Execution backend | `inline`, matching the plan's `backend:` frontmatter; no other backend offered or entered |
| Doc-review gate | Passed, one accepted P3; no override needed or permitted |
| Complexity triage | The documented default for the shape: small-medium, a task list built from the five U-IDs |
| Round-N detection | Fresh build; the saga carried no `pr_refs` |
| Front-loaded ceremony start | Declined; the coordinator opens the pull request with `gh pr create` at the end of the stage |
| Board moves | Submitted as documented: Planning/Designing, Planning/Ready for Active, Active/Implementing — all three recorded `field: Stage+Status`, `status: written` |
| Gate | `scripts/gate.sh` not run by instruction; the inner loop plus the full suite, with the pull request's own checks as the gate |
| Versions | saga 0.160.0, fleet-core 0.27.0, re-derived from `origin/main` at `866d3670` immediately before the bump |
| Merge | Not offered; the coordinator merges after the required checks pass |

## Next step

Open the pull request to `main` and hand the number back to the run coordinator.
