---
title: The build loop with a written exit criterion
type: capability
status: active
date: 2026-09-20
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# The build loop with a written exit criterion

## Summary

Turn `/work` into a build loop whose finish line is written down before the first line of code, in
the run record, at admission. A worker takes one worktree and one branch per unit through the
orchestrate driver, implements, then runs a named set of checks: the mechanical baseline the
repository profile declares, the child-scoped functional checks the plan prescribed for that unit,
a branch preview deployment where the repository declares one, and the scenario smoke the plan
named. Each result is written into the unit's row in the run record. A failing check is a loop
iteration, never a refusal. When every check is green the loop hands the exact commit to
`/code-review`.

In the same change, the machinery the loop replaces goes: five ship-ceremony modules are deleted
with their tests, the risk-gated test prose leaves `/work` and its reference file, and the
confirmed-only ship ceremony leaves section 5.4. The repository's own pre-push gate stays, because
the repository's gate is the repository's rule and not saga's.

One new script, `plugins/saga/scripts/build_loop.py`, does the running and the recording. One new
reference document, `plugins/saga/references/mechanical-baseline.md`, writes down the check map,
where each entry comes from, and what the loop records.

## Problem Frame

**The finish line is a judgment today, and it is made after the fact.** `/work` Phase 3
(`plugins/saga/skills/work/SKILL.md:409-425`) is called "Test gates (hard on risk)". It asks the
worker to discover tests, judge scenario completeness, trace two levels out, and then applies
`requires_hard_test_gate(change_kinds)` — a rule that blocks pull-request readiness for six change
kinds and lets three others through "with an explicit rationale". Every one of those is a decision
the worker makes about its own work, at the end, with nothing written down beforehand to check
itself against. The simplification review's requirement R4 and the operator's answer to its
question 1 (the narrow reading, 2026-09-19) replace that judgment with a fact: the exit criterion
is written in the plan at admission, and "working software" becomes something the worker checks
rather than something it concludes.

**The checks that would make it a fact are scattered across three places that do not agree.** The
repository profile (`.saga-profile.json`) declares four commands as `mechanical_tool_baseline`. The
lifecycle repository's lens catalogue (`config/lens-catalogue.json` at revision `5efc869f`) names
four checks for Python — ruff, mypy in strict mode, bandit, and pytest coverage. The continuous
integration workflow (`.github/workflows/ci.yml`) runs twenty-four substantive steps across six
jobs. Nothing today reads the catalogue's map, nothing records which baseline command answers which
catalogue check, and nothing says out loud which catalogue checks this repository's baseline does
not cover. A worker cannot check itself against a criterion nobody has written out.

**Half of what `/work` does after the code is written is a ceremony nothing else uses.** Section
5.4 (`work/SKILL.md:750-786`) offers a pull request through `ship_ceremony.py run`, then, on a
later re-entry, five more `ship_ceremony.py run` invocations — merge, checkout main, pull, branch
delete, teardown. Behind those calls are five modules totalling 175,034 bytes of Python — 171
kilobytes — (`ship_ceremony.py`, `ceremony_hazards.py`, `ship_receipt.py`, `ship_teardown.py`,
`ship_undo.py`) and 5,854 lines of tests. Parent issue 1018's own count is that three unused
subsystems are 54 percent of saga's script code. The merge turn that replaces this ceremony is issue
1028's, and it is a field in the run record plus a merge onto the parent branch.

**A count in the card is already stale, and the plan uses the file rather than the card.** The card
and the objective plan's section A10 both describe `work/SKILL.md` as "1,121 lines today". On this
card's base commit `87a5329e` the file is **815** lines: issues 1026 and 938 each took prose out of
it before this card branched. Every line number this plan cites is read from the file at `87a5329e`,
not carried over from the card.

**The build loop has nowhere to write what it found.** Issue 1023 built the run record
(`run_record.v1`) and stated in `plugins/saga/references/run-record.md` that "the build loop" is one
of the steps that reads it rather than keeping state of its own. The `units` array's row already
carries "last mechanical-check result" in its description, but no consumer writes one and no
document says what the key is called or what shape it has. That is the gap this card fills.

## Requirements

Drawn from the card, the objective plan's section A10, the simplification review's requirement R4
and its answered question 1, and the lifecycle repository's run model at revision `5efc869f`.

**R1. The exit criterion is written, not judged.** The set of checks a unit must pass is readable
from the run record before implementation starts. Its parts: the mechanical baseline from
`run_configuration.mechanical_tool_baseline`, the plan's child-scoped functional checks, a branch
preview deployment where `admission.branch_preview` is true, and the plan's scenario smoke.

**R2. A failing check is a loop iteration.** Nothing in the loop refuses, blocks, or asks. A check
that fails is recorded and the worker implements again. This is the card's second non-goal, stated
as a property of the script: `build_loop.py` exits non-zero to say "not green yet", never to say
"stop".

**R3. Every result is recorded in the run record.** One entry per check per iteration, under the
unit's own row, naming the command, the catalogue check it answers, its status, and its exit code.
Three statuses, from the catalogue's own rule: an unexecutable check yields `could-not-execute`,
never a pass and never a fail.

**R4. An undeclared preview is recorded, never an error.** Where `branch_preview` is false the loop
writes a preview entry reading `no-preview-declared` and the criterion does not apply. This
repository declares none, so this is the path that runs here.

**R5. The loop hands to code review with the exact revision.** On the green iteration the loop
records the full forty-character commit identifier it reached green at. `/code-review` Phase 0.2
freezes exactly that revision, and its staleness rule counts commits since it.

**R6. The check map is documented with its sources.** `references/mechanical-baseline.md` states
which catalogue check each baseline command answers, which catalogue checks the baseline does not
cover and why, and which named scanners this repository has not configured.

**R7. One worktree and one branch per unit, through issue 1025's driver.** The loop does not create
worktrees. `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`'s `go` subcommand makes
a fresh worktree per launch, opens the unit's branch on the parent branch, and runs
`uv sync --locked --extra dev` in it before the session starts
(`orchestrate.py:2358` `DEFAULT_WORKTREE_SETUP`, applied at `:2422`).

**R8. The removals.** `ship_ceremony.py`, `ceremony_hazards.py`, `ship_receipt.py`,
`ship_teardown.py` and `ship_undo.py` are deleted with their tests, and every importer is repaired.
The risk-gated test prose and the confirmed-only ship ceremony leave `/work`. The repository's
pre-push gate stays.

**R9. The preservation contract survives.** Issue 1029 declared that the pull-request open, the
review request, and the merge stay explicitly confirmed. Whatever prose remains at the end of
`/work` says so.

**R10. One clause of the card is deliberately not met, and the plan says which.** The card's
Objective asks for "the security and dependency scanners as baseline entries: bandit, pip-audit,
gitleaks or detect-secrets, semgrep where configured". KTD1 measures why bandit is not promoted
here and the dry run reports all four rather than silently dropping them. None of the card's four
acceptance criteria is affected; the deviation is declared under "Operator questions this plan does
not answer" with a gate marker, and the widening is listed as a follow-up. Stating it here as a
requirement rather than only as a decision is what makes the requirement mapping complete: a reader
checking the card against this plan finds the gap named on the same page as the requirements it
sits beside.

## Key Technical Decisions

**KTD1. Bandit does not become a blocking baseline entry on this repository, and the plan says so
with a measurement.** The card asks for "the security and dependency scanners as baseline entries:
bandit, pip-audit, gitleaks or detect-secrets, semgrep where configured". Bandit is the only one of
the four this repository has. It is installed (`pyproject.toml:36`, `bandit>=1.7`) and continuous
integration runs it **advisory**: `.github/workflows/ci.yml:282` ends the bandit step with
`|| true`, so a finding has never blocked a merge here. Measured on this branch at base commit
`87a5329e`:

```
uv run python -m bandit -r plugins/ scripts/ tests/ tools/ -ll -q
  Total lines of code: 231188
  Medium: 136    High: 9    (exit 1)
```

Adding that command to `.saga-profile.json`'s `mechanical_tool_baseline` would make the build loop
unable to reach green on this repository on its first iteration and on every iteration after it,
for 145 findings that predate this card. A loop that can never go green is a refusal wearing a
loop's clothes, and the card's own second non-goal forbids exactly that. So this card does **not**
widen the profile's baseline. Instead `build_loop.py --dry-run` **names** each catalogue check the
baseline does not cover and why, so the gap is visible in the loop's own output rather than
silently absent. Widening the baseline is a `.saga-profile.json` edit and belongs in its own card,
listed under "Follow-ups this plan does not do".

The other three scanners are not configured in this repository at all — no `pip-audit`, no
`gitleaks`, no `detect-secrets`, no `semgrep` in `pyproject.toml`, in `.github/workflows/ci.yml`,
or in any configuration file. The card's clause is "where configured", so the dry run reports them
as not configured. That is the clause honoured, not a silent drop.

**KTD2. The loop records under the unit's row, and the record's version does not change.**
`run-record.md` states that a `units` row's key set is deliberately not fixed, "because a row is one
consumer's working state rather than a cross-consumer contract", and that issue 1025 added three
keys under that rule and documented them. This card follows the same path: one new key,
`build_loop`, on the unit's row. `run_record.v1` stays `run_record.v1`. The key is documented in
`references/mechanical-baseline.md` and cross-referenced from `run-record.md`'s units table, the
way issue 1025's three keys are, so the two cannot drift.

**KTD3. One invocation is one iteration; the skill owns the repetition.** `build_loop.py` runs the
criterion once, records what happened, and exits. It does not re-run the worker, it does not
implement, and it does not loop by itself. "Repeat until green" is an instruction in the skill
addressed to the worker, because the thing that changes between iterations is the code, and only
the worker can change that. A script that looped internally would either spin on an unchanged tree
or have to invoke an implementer, and neither is a thing a check runner should do.

**KTD4. `--record <path>` is the primary selector, `--issue <N>` the convenience.** The card's
first acceptance criterion names `--record <path> --dry-run`, so the path form is the one that must
exist. `--issue <N>` with the usual `--store-root` override resolves through `run_record.py`'s own
resolution for the ordinary in-loop call. Both reach the same loader, and the unknown-version
refusal and the exit codes are `run_record.py`'s, not a second set.

**KTD5. `merge_watcher.py` is not deleted by this card; issue 1030 inherits it.** Grepped over
`plugins/ tests/ scripts/ tools/`, the only files that name `merge_watcher` are the five modules
this card removes, `merge_watcher.py` itself, and four test files — `tests/test_merge_watcher.py`,
`tests/test_ship_ceremony.py`, `tests/test_ship_undo.py`, and
`tests/test_ship_teardown_reconciliation.py`. So removing the five orphans it. The card does not
name `merge_watcher.py`, and deleting a module this card does not name is exactly the situation
issue 1026 met with `execution_spec.py` and resolved by leaving it to issue 1030 (its KTD1). This
plan does the same: `merge_watcher.py` and `tests/test_merge_watcher.py` stay on this branch, the
orphaning is recorded here and in the engineering journal, and issue 1030 removes them with the
rest. `reversibility_certificate.py`, by contrast, is **not** orphaned — the whole `outcome_*`
family and `board_progression.py` use it, so it stays regardless.

**KTD6. The ceremony's removal and its replacement are two cards, and this one only removes.** The
card gives me the removal of the confirmed-only merge and the ship ceremony. Issue 1028 writes what
stands in their place: the merge turn, `merge_turn.py`, the six board moves. Issue 1028 edits
`work/SKILL.md` after the review-acceptance point and this card edits it up to the hand-off to code
review, so the two meet at exactly one seam, section 5.4. This plan's edit there is a removal plus
one sentence naming the merge turn as issue 1028's and restating issue 1029's preservation
contract. Whichever of the two cards lands second on the integration branch resolves the conflict.

**KTD7. The preview is invoked through a declared command, never a guessed one, and the key it is
declared in is written down.** Where `branch_preview` is true the loop needs something to run.
Nothing in `repository_profile.v1` names a preview command today, and nothing in the repository
names `branch_preview_command` — `grep -rn "branch_preview_command" plugins/ tests/` returns
nothing. So the loop reads an **optional** `branch_preview_command` from `.saga-profile.json`, and
this card adds one row for it to `plugins/saga/references/repository-profile.md`'s table. A key one
consumer reads and no document describes is the drift this repository has a test for; reading a key
without writing it down would be the same mistake in a new place. The key is optional, so an
existing profile without it stays valid and `repository_profile.v1` does not change.

When `branch_preview` is true and no command is declared, the loop records `could-not-execute` with
the reason "the profile declares a preview but names no command". That is the catalogue's own
unexecutable-check rule applied to the preview, and it keeps the failure legible instead of turning
it into a crash or a pass.

**KTD9. The functional checks and the scenario smoke have no producer yet, and the loop records
that fact rather than assuming one.** `grep -rn "functional_checks\|scenario_smoke" plugins/ tests/`
returns nothing: no card in this tree has built the step that writes the plan's child-scoped
functional checks or its scenario smoke onto a unit's row. The lifecycle repository's run model puts
them at step 2, written by the Planner, and issue 1026 made `/plan` continue into plan review but
did not add that write.

So the loop reads `functional_checks` and `scenario_smoke` from the unit's row, treats an absent key
as an empty list, and records the empty list **with the reason** `none-prescribed` rather than
silently showing nothing. The dry run prints `functional checks: none prescribed in the run record`
and the same for the scenario smoke. This card does **not** build the writer: that is the Planner's
step and it belongs to whichever card gives `/plan` the run-record write. Without this rule a
reader of a green iteration could not tell "the plan prescribed no functional checks" from "the
plan prescribed three and the loop lost them", and those are very different facts about the same
green.

**KTD8. The fourth acceptance criterion is proved against a temporary record with a fake preview
step, and the plan says why that is the honest proof available here.** The criterion asks that a
real unit reached code review with a green baseline, its functional checks, and a preview record in
the run record. This repository declares no preview (`.saga-profile.json`: `"branch_preview":
false`), so the live path here produces a `no-preview-declared` entry, which is the correct record
and not a preview record. The work stage proves the criterion by running the loop for this card's
own unit against a **copy** of issue 1027's record placed under a temporary directory, with
`branch_preview` set true and a fake preview command, and quotes the resulting record block. The
live proof for a genuinely declared preview belongs to a repository that has one, and this plan
says so rather than claiming it.

## High-Level Technical Design

Three moving parts and one document.

**The criterion reader.** Given a record and a unit, assemble the criterion: the baseline commands
from `run_configuration.mechanical_tool_baseline`, the functional checks and scenario smoke from
the unit's row (written there by the plan, keys `functional_checks` and `scenario_smoke`), and the
preview from `admission.branch_preview` plus the profile's optional `branch_preview_command`. The
reader never invents an entry and never drops one it does not understand.

**The check map.** A table, in code and in the reference document, from the lens catalogue's four
Python check identifiers (`ruff`, `mypy`, `bandit`, `pytest-coverage`) to the baseline commands that
answer them, matched by the tool name appearing in the command. A catalogue check with no matching
command is reported as uncovered with a stated reason. A baseline command matching no catalogue
check is reported as a repository-specific entry, not as an error.

**The runner and the recorder.** Each entry runs as a subprocess with a timeout; the status is
`pass` on exit zero, `fail` on any other exit, and `could-not-execute` when the program is missing
or the timeout expires. Every result appends to the unit row's `build_loop.iterations`. The
iteration carries the revision it ran at, so a reader can tell which commit each result describes.
On the iteration where everything is green, `build_loop.handed_to_code_review` is written with the
full forty-character commit identifier and the timestamp.

**The dry run.** Prints the criterion without running anything and without writing anything: each
baseline command with the catalogue check it answers, each uncovered catalogue check with its
reason, each scanner the card names that this repository has not configured, the functional checks,
the scenario smoke, and one line saying whether a preview is declared.

## Implementation Units

U1. The build-loop script
U2. The mechanical-baseline reference document
U3. `/work` becomes the build loop
U4. Remove the five ship-ceremony modules and repair their importers
U5. Tests
U6. Prove the fourth acceptance criterion
U7. Release surfaces and journal

### U1. The build-loop script

**Goal.** `plugins/saga/scripts/build_loop.py` reads the criterion, runs it, and records it.

**Files.** `plugins/saga/scripts/build_loop.py` (new).

**Approach.** A module in the house style the sibling cards use: pure functions plus a `main` that
catches its own refusals. It imports `run_record.py` from the same directory for loading, saving,
and store-root resolution, so the unknown-version refusal line and the exit codes stay one
implementation.

Command line:

```
uv run python plugins/saga/scripts/build_loop.py --record <path> --dry-run
uv run python plugins/saga/scripts/build_loop.py --issue <N> [--unit <id>] [--store-root <dir>]
uv run python plugins/saga/scripts/build_loop.py --record <path> --unit <id>
```

`--repo-root` locates `.saga-profile.json`, defaulting to the git top level. `--timeout` bounds one
check, defaulting to 1,800 seconds. Exit codes follow `run_record.py`'s table with one addition:

| Code | Meaning |
|---|---|
| 0 | green — every check passed, or `--dry-run` printed the criterion |
| 1 | an unexpected internal error |
| 2 | a refusal: an unresolvable store root, an unreadable record, no record for that issue, no such unit |
| 3 | an unknown record version |
| 4 | **not green yet** — the iteration ran and at least one entry is `fail` or `could-not-execute` |

Exit 4 is the card's "a failing check is a loop iteration, not a refusal" made mechanical: it is a
distinct code precisely so a caller cannot mistake it for a refusal, and the skill's instruction on
seeing it is "implement again and run it again", never "stop and ask".

**Execution note.** The runner must not shell out through a shell. The profile's baseline entries
are command strings (`"uv run ruff check ."`), so they are split with `shlex.split` and run as an
argument vector with `shell=False`. A profile entry that does not split into a runnable vector is
recorded `could-not-execute` with the parse error, not passed to a shell.

**Verification.** `uv run python plugins/saga/scripts/build_loop.py --record <path> --dry-run`
prints the four baseline commands with their catalogue checks, names bandit as an uncovered
catalogue check with the reason from KTD1, names pip-audit, gitleaks or detect-secrets, and semgrep
as not configured, and prints `branch preview: none declared`.

### U2. The mechanical-baseline reference document

**Goal.** `plugins/saga/references/mechanical-baseline.md` is the contract for the check map and
the record block, the way `run-record.md` is the contract for the record.

**Files.** `plugins/saga/references/mechanical-baseline.md` (new); one row added to
`plugins/saga/references/run-record.md`'s units table naming the `build_loop` key; one row added to
`plugins/saga/references/repository-profile.md`'s table naming the optional
`branch_preview_command` key (KTD7).

**Approach.** The document states, in this order: where the baseline comes from (the repository
profile, which the lifecycle repository's run model lists as a Planner-chosen parameter filled from
the profile); the lens catalogue's check-to-dimension map at revision `5efc869f` and its six rules,
quoted rather than paraphrased; the check map for this repository with each divergence named — the
profile's mypy invocation is not `--strict` and the profile's pytest invocation carries no coverage
floor, both of which match what continuous integration runs and neither of which this card changes;
the scanners the card names and their state here; the `build_loop` record block field by field; the
preview rule, both branches; and the exit-code table.

**Verification.** `tests/test_build_loop.py` carries the drift guard: one test asserts that the key
set the code writes matches the key set `mechanical-baseline.md`'s record-block table names, and one
asserts that the exit codes the code returns match the document's exit-code table. That is the shape
`tests/test_run_record.py` uses to guard `run-record.md`, and putting the guard in this card's own
test file keeps the new document and the new module failing together.

### U3. `/work` becomes the build loop

**Goal.** The skill instructs a worker to run the written criterion and hand the exact revision to
code review, and stops instructing it to judge test adequacy or to run a ship ceremony.

**Files.** `plugins/saga/skills/work/SKILL.md`; `plugins/saga/skills/work/references/test-and-gates.md`;
`plugins/saga/skills/work/references/pr-continuation-loop.md`; `plugins/saga/commands/work.md`.

**The span this card owns**, stated plainly so the sibling card and the reviewer can both check it:
everything from the top of the file through the hand-off to `/code-review` — the frontmatter and
preamble, "Core principles", Phase 2, Phase 3, **section 4.1**, and sections 5.1 through 5.3.
Section 5.4 is the seam: this card removes the ship ceremony from it and leaves one sentence; issue
1028 writes the merge turn there. Section 5.5's hard boundary is edited only to drop the
ship-ceremony sentence. Phases 0 and 1, and sections 4.2 through 4.4, are untouched by this card.

**Why section 4.1 joins the span.** An earlier draft of this plan put Phase 4 wholly outside it.
That was wrong, and the code says so: `work/SKILL.md:436` inside section 4.1 requires the recorded
`change_kinds` value to be passed verbatim to `requires_hard_test_gate`, and
`tests/test_work_gate_integrity.py:198` asserts that section 4.1 names that function. Removing the
risk-gated gate from Phase 3 while leaving section 4.1 feeding it would leave the skill instructing
a worker to supply an input to a gate that no longer exists — a contradiction a reader would have
to resolve by guessing. So section 4.1's gate-input clause goes with the gate, and the test that
pins it is repaired in U5.

**Approach.** Phase 3 stops being "Test gates (hard on risk)" and becomes the build loop: read the
criterion from the record, run `build_loop.py`, and on exit 4 implement again and run it again. The
`requires_hard_test_gate` prose and the change-kind list leave `test-and-gates.md`; what stays there
is the review-staleness mechanism, which sections 5.1 through 5.3 still use. Core principle 3
("Test as you go, gate hard on risk") is rewritten as the written criterion. Section 5.4's
ship-ceremony steps and the five-invocation post-merge sequence leave, as does the matching block in
`pr-continuation-loop.md` under "Merge-watcher and hazards". Issue 1029's preservation contract —
that the pull-request open, the review request, and the merge stay explicitly confirmed — is stated
once, in what remains of 5.4.

**Execution note.** Issue 1029 lands on the integration branch before this card's merge turn and
adds an ending to section 5.4 that invokes the next step. Take issue 1029's version of that ending
when resolving, and keep this card's removal.

**The `requires_hard_test_gate` cascade, in full.** `requires_hard_test_gate` is not prose: it is a
function at `plugins/saga/scripts/lifecycle_state.py:111`, and eight files name it. They divide into
three groups, and the plan says which group each is in rather than leaving a grep to discover it
during implementation.

| File and line | Group | What happens |
|---|---|---|
| `plugins/saga/skills/work/SKILL.md:50` (core principle 3) | this card | rewritten as the written criterion |
| `plugins/saga/skills/work/SKILL.md:420` (Phase 3 hard gate) | this card | removed with Phase 3's gate prose |
| `plugins/saga/skills/work/SKILL.md:436` (section 4.1's gate input) | this card | the gate-input clause goes with the gate |
| `plugins/saga/skills/work/SKILL.md:810` (reference-file summary) | this card | the summary line stops naming the rule |
| `plugins/saga/skills/work/references/test-and-gates.md:5`, `:59`, `:64` | this card | the hard-gate section leaves the file; the staleness mechanism stays |
| `plugins/saga/commands/work.md:17` | this card | the `/work` command file describes the skill this card rewrites, so its gate sentence goes too |
| `tests/test_work_gate_integrity.py:198` | this card, U5 | a prose assertion over section 4.1; repaired, not deleted — it becomes an assertion about the written criterion |
| `plugins/saga/skills/loop/SKILL.md:286`, `plugins/saga/skills/loop/references/dispatch-table.md:151` | **issue 1030** | `/loop` is one of the eleven commands issue 1030 removes; this card does not edit another command's skill |
| `plugins/saga/scripts/lifecycle_state.py:111` (the function) and `tests/test_work_gate_integrity.py:231-236` (its behaviour tests) | **issue 1030** | the card does not name `lifecycle_state.py`, so KTD5's precedent applies: the function and the tests that exercise it stay, and issue 1030 removes them with `/loop`'s references |

**Verification.** `grep -n "ship_ceremony" plugins/saga/skills/work/SKILL.md` prints nothing;
`grep -rn "requires_hard_test_gate" plugins/saga/skills/work/ plugins/saga/commands/work.md` prints
nothing; `grep -n "explicitly confirmed" plugins/saga/skills/work/SKILL.md` prints the preservation
sentence.

### U4. Remove the five ship-ceremony modules and repair their importers

**Goal.** The five modules and their tests are gone and nothing that remains calls them.

**Files removed.** `plugins/saga/scripts/ship_ceremony.py`, `ceremony_hazards.py`,
`ship_receipt.py`, `ship_teardown.py`, `ship_undo.py`; `tests/test_ship_ceremony.py`,
`tests/test_ceremony_hazards.py`, `tests/test_ship_teardown_reconciliation.py`,
`tests/test_ship_undo.py`.

**Files repaired.** The inventory is in "Removal inventory" below.

**Execution note.** `plugins/saga/hooks/hooks.json:27` is the only executable reference outside the
five modules: a hook invoking `ship_teardown.py reclaim --if-idle 24h --quiet`. That hook entry is
deleted with the module. Every other mention in `plugins/` is a comment or a docstring naming the
module as a precedent or a house pattern; those are reworded to stop citing a file that no longer
exists, not merely deleted, so the reason each pattern exists survives.

**Verification.** `test ! -f plugins/saga/scripts/ship_ceremony.py` and the same for the other four;
`grep -rn "ship_ceremony\|ceremony_hazards\|ship_receipt\|ship_teardown\|ship_undo" plugins/ tests/ scripts/ tools/`
prints nothing outside `plugins/saga/CHANGELOG.md`, which is history and is not rewritten.

### U5. Tests

**Goal.** `tests/test_build_loop.py` covers the card's three named test cases and the guards the
repository's linting expects; the tests that named the removed modules go with them; the tests that
asserted on the removed prose are repaired.

**Files.** `tests/test_build_loop.py` (new); `tests/test_work_prose_contracts.py`,
`tests/test_work_gate_integrity.py`, `tests/conftest.py`, `tests/test_saga_docs_coverage.py`
(repaired).

**The three repairs, named.** `tests/test_work_prose_contracts.py:34-64` asserts the post-merge
ceremony prose names all five `ship_ceremony.py` transitions; that test goes with the ceremony.
`tests/test_work_gate_integrity.py:187-203` asserts section 4.1 names `requires_hard_test_gate` and
passes it a verbatim list; it is rewritten to assert the same single-sourcing property about the
written criterion — that the criterion the record holds and the criterion the loop runs are one
list, not two derivations — so the protection survives the rule it was pinned to.
`tests/test_work_gate_integrity.py:222-237` exercises the function itself and is left alone, because
the function is issue 1030's. `tests/conftest.py:62` drops `test_ship_ceremony` from
`_GH_WRITE_TEST_MODULES`. `tests/test_saga_docs_coverage.py:121` stops citing `/ship --undo`.

**Test scenarios.**

- The baseline for a Python repository runs its commands and records each result in the record's
  `build_loop` block, in order, with the catalogue check each answers.
- A declared preview is invoked and its result recorded.
- An undeclared preview is skipped with a `no-preview-declared` entry and exit is unaffected.
- A declared preview with no declared command records `could-not-execute` with its reason.
- The loop exits 0 only when every entry is `pass`, and writes `handed_to_code_review` with the full
  forty-character revision on exactly that iteration.
- A failing entry exits 4, writes the iteration, and writes no `handed_to_code_review`.
- A missing program records `could-not-execute`, never `fail`.
- A record whose `schema` is not `run_record.v1` is refused on one line with exit 3.
- `--dry-run` writes nothing: the record's `updated_at` is unchanged after it.
- An unknown key already on the unit row survives an iteration write.
- A unit row with no `functional_checks` and no `scenario_smoke` records both as empty with the
  reason `none-prescribed`, and the iteration can still be green (KTD9).
- The record-block key set the code writes equals the key set `mechanical-baseline.md` names, and
  the exit codes the code returns equal the document's table (U2's drift guard).

**Execution note.** Every test passes `--store-root tmp_path` and a fake check runner injected at
the module boundary. No test touches the primary checkout's store, and no test runs a real
deployment. `tests/conftest.py:62`'s `_GH_WRITE_TEST_MODULES` set names `test_ship_ceremony`; that
entry goes with the module.

**Verification.** `uv run pytest tests/test_build_loop.py -q` passes.

### U6. Prove the fourth acceptance criterion

**Goal.** Quote a real run of the loop for this card's own unit, with a green baseline, its
functional checks, and a preview record.

**Approach.** Copy issue 1027's record into a temporary store root, set `branch_preview` true and a
fake preview command on the copy, run the loop against it, and quote the resulting `build_loop`
block. KTD8 says why this is the proof available in a repository that declares no preview.

**What this unit touches in the primary checkout: one read, no write.** It reads
`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1027.json`
and copies it out. Every subsequent operation is against the copy under a temporary directory. The
admission record written before planning remains this card's only write into the primary checkout,
and the fake preview command is a local no-op that deploys nothing anywhere.

**Verification.** The quoted block appears in the work-stage report and names a green baseline, the
functional checks, a preview entry with a status, and `handed_to_code_review` with a
forty-character revision.

### U7. Release surfaces and journal

**Goal.** The installed-plugin metadata tells the same story as the diff, and the durable learnings
are captured in the shipping commit.

**Files.** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `docs/engineering-journal/LEARNINGS.md`,
`docs/engineering-journal/DECISIONS.md`.

**Execution note.** The integration branch spans two dates and the journal's newest-first guard
measures against the merge base with `main`, so every entry this card files goes under the existing
`## 2026-09-20` heading at the top of each journal file. Sibling cards are bumping the same saga
version on the same integration branch; take the next free number at the merge turn rather than the
one chosen while the suite ran, as issue 1025 had to.

**Journal entries.** A `LEARNINGS.md` entry for the bandit measurement — that a scanner a repository
runs advisory cannot be promoted to a blocking loop entry without first measuring it, because the
promotion turns a loop into a refusal and nothing in the loop's own output would say so. A
`DECISIONS.md` entry for KTD5, the deferral of `merge_watcher.py` to issue 1030, with the
revisit-when condition being issue 1030's removal pass.

## Removal inventory

Each removal, the card that names it, and every importer repaired.

| Removed | Named by | Importers and references repaired |
|---|---|---|
| `plugins/saga/scripts/ship_ceremony.py` | card 1027, objective plan A10 | `plugins/saga/skills/work/SKILL.md` (U3); `plugins/saga/skills/work/references/pr-continuation-loop.md` (U3); `plugins/saga/references/saga-spec.md`; `plugins/saga/scripts/saga.py` comments at `:60`, `:80`, `:239`, `:822` and two argparse help strings at `:1689`, `:1695`; `plugins/saga/scripts/merge_watcher.py` docstrings at `:12`, `:28`, `:60`; `tests/conftest.py:62`; `tests/test_saga_saga.py:430` comment; `tests/test_work_prose_contracts.py` (the five-transition assertion) |
| `plugins/saga/scripts/ceremony_hazards.py` | card 1027, objective plan A10 | `tests/test_merge_watcher.py:3-4` docstring |
| `plugins/saga/scripts/ship_receipt.py` | card 1027, objective plan A10 | `plugins/saga/scripts/deploy_handoff.py` docstrings at `:16`, `:28`, `:31`, `:81`, `:583`; `plugins/saga/references/run-record.md`'s "What this record replaces" row; `tests/test_handoff_envelope.py:423` comment; `tests/test_roster.py:704` test name |
| `plugins/saga/scripts/ship_teardown.py` | card 1027, objective plan A10 | `plugins/saga/hooks/hooks.json:27` (the hook entry is deleted); `plugins/saga/scripts/deploy_handoff.py:81`, `:261`, `:496`; `plugins/saga/scripts/reversibility_certificate.py:76` |
| `plugins/saga/scripts/ship_undo.py` | card 1027, objective plan A10 | `plugins/saga/references/adjustment-envelope.md`; `plugins/saga/skills/work/SKILL.md` Phase 2's "For ceremony rollback use `/ship --undo`" line (U3); `plugins/saga/scripts/merge_watcher.py:77`; `tests/test_saga_docs_coverage.py:121` |
| `tests/test_ship_ceremony.py`, `tests/test_ceremony_hazards.py`, `tests/test_ship_teardown_reconciliation.py`, `tests/test_ship_undo.py` | with their modules | — |

**Deferred to issue 1030, not done here:** `plugins/saga/scripts/merge_watcher.py` and
`tests/test_merge_watcher.py`. Removing the five modules orphans them — after this card, nothing
outside `merge_watcher.py` itself and `tests/test_merge_watcher.py` names `merge_watcher` — but the
card does not name the module, and KTD5 applies issue 1026's `execution_spec.py` precedent rather
than widening this card's blast radius. `plugins/saga/CHANGELOG.md` is history and is appended to,
never rewritten.

## The check map for this repository

The lens catalogue at revision `5efc869f` names four checks for the `python` stack. This
repository's profile declares four commands. They line up like this, with every divergence stated.

| Catalogue check | Catalogue's statement of it | This repository's command | Source | Divergence |
|---|---|---|---|---|
| `ruff` | lint and format conformance for Python source | `uv run ruff check .` and `uv run ruff format --check .` | profile baseline; matches continuous integration | none |
| `mypy` | static type checking in **strict mode** | `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` | profile baseline; matches continuous integration | not `--strict`, and missing imports are ignored. Named, not changed: raising it is a repository-wide typing change and no card in this tree authorises one |
| `bandit` | static security analysis of Python source | none in the baseline | continuous integration runs it advisory (`|| true`) | uncovered. KTD1 measures why |
| `pytest-coverage` | measured statement coverage, the standard's 80 percent floor | `uv run pytest tests/ plugins/*/tests/ -q` | profile baseline | no coverage measurement in the command; continuous integration measures it and `scripts/gate.sh` compares against the workflow |

Scanners the card names that this repository has not configured, reported as such by the dry run and
invented by nothing: `pip-audit`, `gitleaks` or `detect-secrets`, `semgrep`.

The catalogue's pinned versions for every check read `UNKNOWN`, owned by the organisation context
library; this card cites them and does not re-declare them.

## The run-record block the loop writes

One key, `build_loop`, on the unit's row inside `units`. `run_record.v1` is unchanged (KTD2).

| Field | Type | Holds |
|---|---|---|
| `exit_criterion` | object | the criterion as it was read: `baseline` (the commands), `functional_checks`, `scenario_smoke`, `preview` (`declared` and the command or `null`) |
| `iterations` | array | one entry per invocation, in order |
| `handed_to_code_review` | object or absent | `{revision, at}`, written on the green iteration only; `revision` is the full forty-character commit identifier |

Each entry in `iterations`:

| Field | Type | Holds |
|---|---|---|
| `iteration` | integer | 1 upward |
| `revision` | string | the full forty-character commit identifier the iteration ran at |
| `started_at` / `finished_at` | string | ISO-8601 timestamps in UTC |
| `green` | boolean | every result is `pass` |
| `baseline` | array | `{command, catalogue_check, status, exit_code, duration_seconds}` |
| `functional_checks` | array | `{name, command, status, exit_code, duration_seconds}` |
| `preview` | object | `{declared, status, command, detail}` — `status` is `no-preview-declared` where the repository declares none |
| `scenario_smoke` | array | `{name, command, status, exit_code, duration_seconds}` |

`status` is one of `pass`, `fail`, `could-not-execute`, from the catalogue's rule that an
unexecutable check is never a pass and never a fail.

## Prerequisites and what this unblocks

**Depends on** issue 1023 (the run record and admission, on the base at `87a5329e`) and issue 1025
(the orchestrate run driver, on the same base). Both are merged onto `parent/1018` already.

**Meets** issue 1028 at `work/SKILL.md` section 5.4 and issue 1029 at the skill's ending (KTD6).

**Unblocks** issue 1030, which removes the eleven commands and inherits `merge_watcher.py`,
`lifecycle_state.py`'s `requires_hard_test_gate` function, and `/loop`'s two references to it.

**On sizing.** Seven units and about thirty-four files — of which nine are deletions and eight are
one-line or one-row repairs — is well above the "3 to 8 file changes is typical" guideline a
right-sizing check applies, and the honest answer is that the card is a capability the
operator filed as one piece and the parent pull request carries one review for the whole parent. The
seam that would ordinarily justify a split is already taken: the merge turn is issue 1028's, the
removals are issue 1030's, and the continuation mechanics are issue 1029's. What is left is one
loop, the document that defines it, and the ceremony it replaces — splitting those three would ship
a loop with no exit criterion or a removal with no replacement.

## Test Strategy

Unit tests only, with temporary stores and fake runners, per the card and the driver's rules.

- Every test passes `--store-root tmp_path`; none touches
  `/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/`.
- Check execution is injected at a seam, so no test runs ruff, mypy, pytest or a deployment inside a
  test.
- The repository's test-shape lint (`scripts/lint_test_shape.py`) rejects a fake-only suite, so
  `tests/test_build_loop.py` loads the real `build_loop` module at module scope and fakes only the
  runner, which is the shape issue 1025's learning entry named.
- The inner loop is `uv run pytest tests/test_build_loop.py -q`; the card is not done until the
  whole suite has run, because issue 1025's learning is that a card-scoped inner loop proves the
  card and nothing else.

## Lens applicability declaration

Recorded at admission and repeated here so the plan carries it. Four always-on lenses:
architecture-maintainability, correctness, security, testing.

Six conditional lenses selected, with the catalogue condition each meets:

- **documentation-clarity** — a new reference document ships and the heaviest skill's instructions
  are rewritten.
- **agent-usability** — a skill and a machine-readable result an agent must discover and operate.
- **api-contract** — a new command-line contract and a new file-format contract inside the record.
- **adversarial** — a lifecycle change, a policy change, and a large diff.
- **reliability** — failure handling: what a failing check does, and what an unexecutable one does.
- **deployment-infrastructure** — the loop introduces the preview deployment into the exit criterion
  and changes how deployed state is verified before review.

Five left out, each with its reason: **performance** (no new hot path, query, cache or capacity
behaviour); **privacy** (no personal or sensitive data anywhere in the loop or its record block);
**previous-comments** (no prior review comments on this card); **accessibility-human-usability**
(the only human-operated surface is one plain-text dry run); **experience** (no user-facing surface
changes).

## Preflight evidence

The three checks `.saga-profile.json` declares as `preflight_checks`.

- **The plan cleared `/doc-review` with nothing above P3 open** — performed at the end of this
  stage; the verdict is recorded in the stage's return.
- **The work branch exists and is not the default branch** — `issue/1027`, created from
  `origin/parent/1018` at `87a5329e`; `git status -sb` confirms it tracks the integration branch and
  not `main`.
- **The release surfaces named in `CLAUDE.md` move in the same pull request** — U7 moves
  `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and
  `plugins/saga/CHANGELOG.md` together.

## Admission answers

Answered without a live operator: `AskUserQuestion` is unavailable in this session, so each answer
below is taken from a named source and recorded with it. The dry run filled twelve of thirteen
parameters and asked eight questions; the recorded run filled thirteen of thirteen and reports
"Questions to answer: none". The record is at
`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1027.json`.

<!-- gate-record: id=plan-1027-admission-answers-without-a-live-operator absence=HALT transport=ask-user-question -->

| Question | Answer | Source |
|---|---|---|
| Risk tier and why | `medium` — "it rewrites the heaviest skill; the repository gate and the code review still stand behind it." | the card's own Risk section, verbatim |
| The seven approval boundaries | `none` granted in all seven: production changes, destructive operations, secrets or credential changes, IAM or permission changes, billing or cost-impacting actions, external commitments, major team or process authority changes | the operator's standing list for this run: all seven stop and ask, and so do plan-review and code-review overrides |
| Destination | `pr` | the run driver's carrier, `plan_pre_answers.v1`, validated clean |
| Staffing overrides | `none` — the defaults from the staffing component stand | the run driver's instruction |
| Lens declaration | the four always-on plus six conditional, five left out with reasons | the lens catalogue's conditions at revision `5efc869f`, matched against this change; written out under "Lens applicability declaration" |
| Repair allowances | 3 standard, 2 escalated | the lifecycle's default at the pin (`run-model.md`, the run-configuration table) |
| Response to unfinished functional testing | bring the result to the operator | the lifecycle names two modes as a closed set with no default (`run-model.md:163`), so this plan chooses and says why: the fourth acceptance criterion's proof here uses a fake preview against a temporary record, so an unfinished functional test means the claim about a genuinely declared preview is unproven, and that is a judgment for the operator rather than a repair loop |
| Change shape | `mixed` | the diff is Python, skill prose, a reference document and tracked configuration |

## Questions answered from the card

Questions the installed `/plan` would have put to the operator, and the answer each took.

| Question | Answer taken | Where it came from |
|---|---|---|
| Is a plan document warranted (Phase 0.4)? | yes | seven units, eight key technical decisions, five module removals and a new cross-consumer record block — not atomic by any of the rubric's four tests |
| Scope depth (Phase 0.5) | deep | the run driver's complexity triage says large; the work is cross-cutting and touches the heaviest skill, one new script, five removals, a new reference, tests and release surfaces |
| Resume an existing saga (Phase 0.3)? | mint a new one | `saga.py scan` returned `{"candidates": [], "count": 0}` |
| Handoff routing (Phase 0.2) | plan from the card directly | `parse_issue.py --issue 1027` returns an empty `handoff` object with `can_plan` false; the card carries no handoff section, so the card body and the objective plan's section A10 are the input |
| Destination (Phase 5.1) | `pr` | the carrier, applied and narrated; `plan_pre_answers.py` exited 0 with `stop: null` |
| Execution backend (Phase 5.2) | `inline` | the carrier; `team-execution` and `cc-workflows-ultracode` are never applied from a carrier, and parent 1018 archives team-execution at issue 1030 |
| Does bandit join the blocking baseline? | no | KTD1, from a measurement on this branch, not from a preference |
| Does `merge_watcher.py` go with the five? | no — issue 1030 inherits it | KTD5, following issue 1026's `execution_spec.py` precedent |

**Phase 1's parallel `Explore` dispatch was not used.** The run driver forbids this card from
spawning subagents, so the grounding reads were done directly in this session: the card and its
parent, the objective plan's sections 1 and A10, the simplification review's R4 and question 1, the
lifecycle repository at revision `5efc869f`, the four sibling artefacts on the base, the whole of
`work/SKILL.md`, and a `grep -rn` over `plugins/ tests/ scripts/ tools/ docs/` for each of the five
modules. Nothing in the plan rests on a read that did not happen.

## Operator questions this plan does not answer

<!-- gate-record: id=plan-1027-bandit-not-promoted-to-a-blocking-baseline-entry absence=HALT transport=ask-user-question -->

**Should `.saga-profile.json`'s `mechanical_tool_baseline` widen to include bandit, and on what
scope?** KTD1 takes the recorded default of leaving it out, with a measurement behind it, because
promoting a scanner that reports 145 medium-or-high findings would make the loop unable to reach
green and the card's own non-goal forbids a refusal. What this plan cannot settle is the operator's
preference between three futures: leave bandit advisory as continuous integration does; promote it
whole after a clean-up card; or scope it to the unit's own diff, which needs a profile field that
`repository_profile.v1` does not have and that belongs to issue 1023's document. This plan proceeds
on the first and names the other two.

## Follow-ups this plan does not do

Named here so that "not in this card" is a record rather than a silence. None blocks this card.

1. **Widen `.saga-profile.json`'s `mechanical_tool_baseline`** to cover the catalogue's bandit
   check, on whichever of the three scopes the operator picks (KTD1 and the operator question
   above). A prerequisite for the second and third of those scopes is a clean-up of the 145
   medium-or-high bandit findings measured on this branch.
2. **Give `/plan` the run-record write** that puts the child-scoped functional checks and the
   scenario smoke on a unit's row (KTD9). Until that exists the loop records both as
   `none-prescribed`.
3. **Add a `pip-audit` dependency-audit entry**, and a secrets scanner, if the operator wants the
   card's scanner clause met on this repository; none of the three is configured here today.
4. **Raise the profile's mypy invocation to `--strict`** and give its pytest invocation a coverage
   floor, so the profile's baseline and the catalogue's check statement agree. Both are
   repository-wide changes no card in this tree authorises.

## Scope Boundaries

**In scope:** `build_loop.py`; `references/mechanical-baseline.md`; one row each in
`references/run-record.md` and `references/repository-profile.md`; `work/SKILL.md` from the top
through the hand-off to code review, including section 4.1's gate-input clause, plus the removal
half of section 5.4 and the ship-ceremony sentence in 5.5; `references/test-and-gates.md` and
`references/pr-continuation-loop.md`; `plugins/saga/commands/work.md`; the five module removals with
their tests and importers; `tests/test_build_loop.py` and the repairs the removals force
(`test_work_prose_contracts.py`, `test_work_gate_integrity.py`, `conftest.py`,
`test_saga_docs_coverage.py`); the release surfaces and the two journal entries.

**Out of scope:** any deployment anywhere, including the non-production destination, which is issue
1028's; the merge turn, `merge_turn.py`, `board_progression.py`, `qa/SKILL.md`, `retro/SKILL.md` and
the four ledgers, all issue 1028's; the eleven command removals and `merge_watcher.py`, issue
1030's, together with `lifecycle_state.py`'s `requires_hard_test_gate` function and `/loop`'s two
references to it; the spore-hook and skill-ending changes, issue 1029's; `plugins/team-execution/`,
which parent 1018 archives at issue 1030 and which this card reads for naming only and does not
touch; the four items under "Follow-ups this plan does not do"; `scripts/gate.sh`, which this card
must not run.

## Risk Analysis and Mitigation

**The loop becomes a refusal by the back door.** The way this fails is a baseline entry that cannot
pass, which is exactly what KTD1's measurement caught before it shipped. Mitigation: exit 4 is a
separate code from every refusal code, the skill's instruction on 4 is to implement again, and the
dry run prints the criterion so a worker can see what it must clear before it writes a line.

**The two cards meeting at section 5.4 lose each other's half.** Issue 1028 rewrites that section
after the review-acceptance point while this card removes the ceremony from it. Mitigation: KTD6
names the seam, this card's edit there is a removal plus one sentence, and whichever lands second
resolves the conflict with both halves in front of it.

**The record block drifts from its document.** `run-record.md` earned a test for exactly this.
Mitigation: U2's test asserts the document and the code agree about the key set and the exit codes.

**The removals take something still wired.** Mitigation: the removal inventory is built from a
`grep -rn` over `plugins/ tests/ scripts/ tools/ docs/` for each module, the one executable
reference outside the five is named (`hooks.json:27`), and the whole suite runs before the merge
turn rather than the card's own test file alone.

**The release-surface guard demands a second version bump.** Three sibling cards are bumping saga on
the same integration branch and the diff-aware guard is pull-request-only, so `scripts/gate.sh` can
never catch it. Mitigation: U7 takes the next free version at the merge turn, not at authoring time.

## Alternatives Considered

**Let `build_loop.py` loop internally until green.** Rejected: the only thing that changes between
iterations is the code, so an internal loop either spins on an unchanged tree or has to invoke an
implementer, and a check runner that implements is a different program (KTD3).

**Bump the run record to `run_record.v2` for the build-loop block.** Rejected: `run-record.md` says
in terms that a unit row's key set is not fixed and that a consumer may add a key without a version
bump, and issue 1025 already added three keys under that rule. A version bump would force every
reader of every record to move for a key only one consumer reads (KTD2).

**Delete `merge_watcher.py` here and carry the cascade.** Rejected for sequencing, not for
correctness: the card does not name it, issue 1030 is the removals card, and issue 1026 set the
precedent with `execution_spec.py` (KTD5).

**Add bandit to the baseline and let the first iteration be red.** Rejected on the measurement: 145
medium-or-high findings that predate this card would make the loop unable to reach green on any
iteration, which turns the loop into the refusal the card's non-goal forbids (KTD1).

**Invent a preview command when the profile declares a preview without one.** Rejected: guessing a
deployment command is the one class of guess that can do real damage. The loop records
`could-not-execute` with the reason instead (KTD7).
