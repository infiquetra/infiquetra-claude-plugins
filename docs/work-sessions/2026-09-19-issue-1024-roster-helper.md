# Work session: issue 1024, the roster helper

Date: 2026-09-19. Branch `issue/1024`, branched from `origin/parent/1018` at `0fa2ea32`.
Plan: `docs/plans/2026-09-19-issue-1024-roster-helper-plan.md`.
Document review: `docs/reviews/doc-review-issue-1024-2026-09-19.md`, not blocked, nothing open.

## What was built, by unit

**U1 — the module, the record read, the role resolution, and the in-pane precondition.**
`plugins/agent-launcher/skills/agent-launcher/scripts/roster.py`: the `up` / `wait` / `down`
command line, the exit-code table, the refusal outside a herdr pane, the staffing-to-roles mapping
constant, the Lens Reviewer slice driven by the roles index, and the dispatch-brief composer.

**U2 — `up`.** One `launcher.py launch` per seat with the staffing plan's vendor, model and effort,
the receipt written beside the run record, and a `roster_entry.v1` row appended and saved before the
next launch. Idempotent per role; an undelivered prompt is recorded, reported, and never retried.

**U3 — `wait`.** One `herdr agent wait` per recorded pane, always with `--timeout` and never with
`--until`, then `herdr agent get` to read the settled state. A blocked role is reported with its
output tail and exits 5.

**U4 — `down`.** `launcher.py close --receipt-json` per recorded row, skipping any row this helper
did not create, whose receipt is gone, which is already closed, or which is the pane the command is
running in.

**U5 — skills and release surfaces.** The agent-launcher skill gained "A whole roster from a run
record"; `/work` and `/code-review` gained short pointers, kept thin because the parent's later
cards rewrite both files. Versions, changelogs, marketplace registry and the two version-literal
guards moved together.

## The one decision taken during the build, not at plan time

The staffing plan carries a vendor, a model and an effort — tiers — and no account, so `roster.py`
originally passed no `--account` to the launcher. The launcher appends the company-account flag only
when an account is named (`launcher.py:563-569`), so every roster session would have launched on the
personal account while the coordinator ran on the company one. Found by preparing the live check,
not by reading the code. Fixed with an `--account` flag on `up`, overridable per role by a staffing
row that carries its own `account`, and three mutation-tested guards.

## change_kinds

`behavior` — a new executable that creates and closes terminal sessions on the operator's server.
`requires_hard_test_gate(["behavior"])` is true, and the gate is met by
`tests/test_roster.py` (33 tests) plus the live acceptance run below.

## Checks run

`ruff check` (clean), `ruff format --check` (564 files already formatted), `mypy plugins/ scripts/
tests/ --ignore-missing-imports` (375 files, no issues), `pytest tests/test_roster.py
tests/test_run_record.py tests/test_saga_plugin.py tests/test_agent_launcher_plugin.py
tests/test_roles_library.py` (495 passed, 3 skipped), release-surface parity, marketplace sync
check, marketplace validator (0 errors), journal-order lint (0 violations), plan-artifact
conformance (exit 0), gate-absence lint (0 violations).

Eighteen mutations were applied to `roster.py` one at a time — each guard reverted, its test run,
the file restored — and every one of them killed its test. The first pass found one guard that did
not fail when reverted (`down`'s `created_by` check was being caught by the missing-receipt check
instead), and that test was rewritten to isolate it.

## The live acceptance run, once

Before: 24 agents, none matching `issue-1024-acceptance-`. During: 27 agents, exactly two matching —
`issue-1024-acceptance-planner` on pane `w7C:p2Z` and `issue-1024-acceptance-worker` on pane
`w7C:p20`, both `claude`, `haiku`/`low`, on the **company** account, in workspace `w7C`. After
`down`: 25 agents, none matching, and this session's own pane `w7C:p2P` untouched.

The total delta is +3 then −2 rather than +2 then −2 because the operator's other workspaces (`w70`,
`w81`, `w82`) gained and lost agents during the run; the count of panes carrying the acceptance
prefix was exactly two throughout, which is the measurement that isolates this helper's effect.

`wait` found both sessions `blocked` on Claude's own file-read permission prompt, reported each with
its pane identifier and output tail, exited 5, and answered neither. That is the report-don't-answer
rule proven against a live agent rather than a fake.

## Next step

Merge `origin/parent/1018` into `issue/1024`, re-run the inner loop at the merged head, run the full
suite across both pytest roots, and return to the coordinator. No pull request and no per-card code
review: the parent pull request carries one review for the whole parent.
