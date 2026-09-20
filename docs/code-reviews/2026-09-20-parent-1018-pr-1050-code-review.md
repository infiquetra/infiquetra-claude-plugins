---
title: Code review — parent 1018, pull request 1050
reviewed_revision: c5e8129d46f92f9385f793e43a325080145748e1
base_revision: 1a29774ab89275caa70751a0199d46439ed08f28
target: pull request 1050, branch parent/1018 into main
date: 2026-09-20
cycles: 2
outcome: accepted
derived_overall: 9.3
cycle2_revision: d133cb3720bc02a286a483f1c0cfe6d267d6d825
---

# Code review — the saga simplification parent (issue 1018), pull request 1050

This is the single code review for the whole parent: fifteen cards, already planned,
document-reviewed, built with tests, and merged one at a time onto `parent/1018`. The pull request
takes `parent/1018` into `main`. The reviewed revision for cycle 1 is
`c5e8129d46f92f9385f793e43a325080145748e1`; the base is
`1a29774ab89275caa70751a0199d46439ed08f28`.

## How this review was run, and where it deviated

The operator set the parameters in advance: review the pull-request diff against the base, take the
recommended lens set, run the lens pass inline in the reviewing thread, spawn no subagents and no
lens sessions, never auto-run a fixer, and cap the review at two cycles.

Three deviations are worth naming, because each one changes what this review is evidence of.

1. **The lens pass ran inline.** The skill's default is one Lens Reviewer session per selected lens.
   The operator chose `inline`, so every lens was applied by the reviewing thread. There is no
   independent seat behind any finding below; cross-reviewer agreement is not evidence this review
   can offer.
2. **The roster is real; the generator's verdict is `refused`.** The lens set was resolved by the
   branch's own machinery — `plugins/saga/scripts/review_roster.py` invoking
   `tools/docs/gen_review_roster.py` from the `infiquetra/infiquetra-sdlc` checkout at
   `~/workspace/infiquetra/infiquetra-sdlc` — against a declaration built for this run. The
   generator returned `review_roster.v1` with hash
   `sha256:f5aa223b16d5861e09671dc3da5afb03571bb8e4d2d0ed79db60b04aa5f48be1`, ten of fifteen lenses
   selected, standard strictness throughout — and `status: refused` on its `verification_presence`
   check, because no scoring executor is assigned to any of the four always-on lenses. That is not
   a defect in this diff; see finding 11.
3. **The artifact is a plain file.** The skill writes its artifact through
   `plugins/saga/scripts/evidence_ledger.py`. Issue 1030 removed that script, so this artifact is
   written directly to `docs/code-reviews/`, the surviving convention in this repository.

The installed saga at review time is 0.161.0; the branch ships 1.0.0. The review therefore followed
the **branch's** `plugins/saga/skills/code-review/SKILL.md`, not the installed one, wherever the two
disagree.

## The lens set

Ten lenses, standard strictness (derived overall ≥ 9.0, every applicable dimension ≥ 7). The four
always-on lenses are scorable; the six conditionals resolve as advisory in this profile.

| Lens | Scorable | Why it applies |
|---|---|---|
| `architecture-maintainability` | yes | always on |
| `correctness` | yes | always on |
| `security` | yes | always on |
| `testing` | yes | always on |
| `api-contract` | advisory | the diff changes the public command surface, the `ORCHESTRATION_MODES` enum, and the marketplace registry |
| `documentation-clarity` | advisory | most of the diff is prose the plugin ships as its product |
| `agent-usability` | advisory | the shipped artifacts are instructions an agent executes |
| `deployment-infrastructure` | advisory | continuous-integration steps, hook registration and plugin release surfaces changed |
| `reliability` | advisory | new merge-turn, run-record and build-loop machinery runs against live git and a shared store |
| `privacy` | advisory | a new hook reads the operator's prompt text |

Five conditionals were declared not applicable with a recorded reason: `performance`, `adversarial`,
`previous-comments`, `accessibility-human-usability`, `experience`.

## What was read, and what was taken on trust

The diff is about 161,000 lines removed and 51,600 added across 667 files. The additions and the
severances of surviving modules were read. The pure deletions were taken as verified by the
importability guards and the suite rather than read line by line — which is the operator's
instruction and also the only affordable reading of a deletion of that size. Two consequences follow
honestly: a defect that exists only inside deleted code is out of scope by construction, and a
defect in what the deletion *left behind* is exactly what this review looked for, and found.

## Cycle 1 — `repairs_requested`

Reviewed revision `c5e8129d46f92f9385f793e43a325080145748e1`. The full suite was green at that
revision (`uv run pytest tests/ plugins/*/tests/`, exit 0), as were `ruff check`, `ruff format
--check`, `mypy plugins/ scripts/ tests/`, the release-surface parity check, the plugin validator
and the journal-order lint.

Two scoring lenses did not meet their pair.

| Lens | Derived overall | Met its pair? | What held it below |
|---|---|---|---|
| `architecture-maintainability` | 9.2 | yes | — |
| `correctness` | 8.6 | **no** | finding 1 (a live crash), finding 5's stale caller instructions |
| `security` | 9.6 | yes | — |
| `testing` | 8.4 | **no** | findings 2 and 3 (two guards that proved nothing), findings 12 and 13 (two guards pinning dangling references) |

Advisory lenses: `documentation-clarity` and `agent-usability` both well below their floor on
`shipped-behavior-parity` and `capability-parity-reachability` respectively — findings 4 through 10.

## Findings

Numbered once, stable across cycles. Every finding cites evidence on the reviewed revision.

Three repair commits carry them. `f8b1d28e` (*repair the P0 and P1 findings from the parent's code
review*) carries findings 1 through 19; `9946952c` (*retire the removed commands from the skills'
own routing prose*) carries 20, 21 and 22; `d133cb37` (*scrub the installed-plugin root so the suite
stops reading the environment*) carries 23. No commit carries an attribution trailer of any kind.

### P0

**1 — `recommend_execution_backend` raises `ValueError` whenever the Workflow tool is absent.**
`plugins/saga/scripts/lifecycle_state.py:305-307`. Issue 1030 narrowed the reachable-backend list to
`["inline"]` and left behind the line that removed `cc-workflows-ultracode` from it, so every call
passing `workflow_available=False` died with `ValueError: list.remove(x): x not in list`. That is
every call from a host that probed and found no Workflow tool — the case
`plugins/saga/skills/work/references/execution-strategy.md` instructs `/work` to produce, and the
case `lifecycle_state.py recommend-backend --no-workflow` produces from the command line. Reproduced
directly at the reviewed revision. The suite was green because no test passed the flag.
*Repaired* at `f8b1d28e` — the dead `remove` is gone and
`tests/test_saga_plugin.py::test_recommend_backend_survives_an_unavailable_workflow_tool` takes the
branch for both provenance values.

### P1

**2 — `tests/test_operator_choice_drift.py` collects zero tests.** All four of its assertions were
deleted by the issue 1030 sweeps; 72 lines of docstring, constants and private helpers remain.
`pytest` on that path prints `no tests ran` and exits 0. An audit of every `test_*.py` in the
repository found this to be the only such file. *Repaired*: rewritten to pin the document's enum
claim against `saga.py`, seven collected tests.

**3 — the `archived-orchestration-mode` canary could never run.** `tools/canary_registry.json`
quoted `ORCHESTRATION_MODES = ("inline", "cc-workflows-ultracode")` while
`plugins/saga/scripts/saga.py:85` reads `ORCHESTRATION_MODES = ("inline",)`.
`tools/wiring_canary.py:146-150` raises `CanaryError` on a missing anchor and `run_entry` records
`error`, so the entry proved nothing and `.github/workflows/mutation-canary.yml` would have reported
an error for it. *Repaired*: anchor corrected; `wiring_canary.py --target archived-orchestration-mode`
now prints `caught`.

**4 — the saga plugin's front door routes the reader to five removed commands.**
`plugins/saga/README.md` "Start Here" table rows for `/handoff`, `/resume`, `/pulse` and
`/fleet-doctor`; the count line "25 command files and 24 routable commands" against the fourteen and
thirteen that `tests/test_command_surface.py` pins; a paragraph describing `/outcome` across a
backend menu naming two archived plugins. The file was edited in this diff, so the staleness was in
scope. *Repaired.*

**5 — `references/operator-choice.md` asserts a three-value enum that is now one value.** Its §1 said
"there are exactly three recorded enum values … they match `ORCHESTRATION_MODES` in
`scripts/saga.py`" and listed `team-execution` as "plugin installed" — a plugin this diff deletes.
Thirty-three occurrences of `team-execution` remained. *Repaired*: §1 and §2 restated for one
backend, §3, §4 and §8 marked historical in their own text, and the rewritten drift guard enforces
the marking.

**6 — the saga manual documents all eleven removed commands.** `plugins/saga/docs/commands.md`
carried a command card for each of `/handoff`, `/promote`, `/resume`, `/optimize`, `/loop`, `/tier`,
`/outcome`, `/engines`, `/pulse`, `/fleet-doctor` and `/undo`, and opened with the same wrong count.
`docs/README.md` linked `visuals.md` (deleted in this diff), gave a third count, ended the main chain
at `/handoff`, and named `tests/test_saga_docs_coverage.py`, which does not exist.
`docs/lifecycle.md`, `docs/scenarios.md` and `docs/state-readiness.md` routed to removed commands.
The README calls these pages "the maintained user-facing reference". *Repaired* across all six pages.

**7 — four manual pages embed diagrams this diff deleted.** `docs/lifecycle.md`,
`docs/boundaries.md`, `docs/commands.md` and `docs/state-readiness.md` referenced `assets/*.svg`
files removed in the same diff; `plugins/saga/README.md` had its own image removed and the sweep
stopped there. *Repaired.*

**8 — eight surviving skill surfaces offer an archived backend.** `/work` (SKILL.md §1.4 and
`references/execution-strategy.md`), `/plan` (SKILL.md §5.2 and `references/plan-sections.md`),
`/code-review`, `/founder-review`, `/retro` (SKILL.md and `references/self-edit-safety.md`) and
`/investigate` (SKILL.md and `references/methodology.md`) all instructed the reader to render an
offer presenting `inline` and `team-execution`. For a skills-based plugin this is not documentation
lag: the prose is what the agent executes. *Repaired* — each now states the backend rather than
asking for it.

**9 — `/work` Phase 1.5 is an unreachable step deferring to a missing document.** The step is
entered when `orchestration_mode == cc-workflows-ultracode`, which `saga.py` now refuses to write,
and its body deferred its whole contract to
`references/workflow-backend.md`, which does not exist in the tree. The same dead link was added by
this diff at three places in `plan/SKILL.md` and `work/SKILL.md`. *Repaired*: the step says it cannot
be entered; the three links are gone.

**20 — the surviving skills route the reader to removed commands, eighty-five times.** Beyond the
backend-offer prose of finding 8, the routing instructions themselves still named removed commands:
`/handoff` as the way to file an SDLC issue in `/brainstorm`, `/spec`, `/investigate`,
`/office-hours`, `/ideate`, `/founder-review`, `/retro` and their reference documents; `/loop` as the
router that reaches `/investigate`, `/spec`, `/plan`, `/strategy` and `/retro`; `/resume` as the
re-entry path in `/work` and `/retro`; `/tier` as a live mid-run lever in `/plan` and
`references/pr-continuation-loop.md`; `/outcome report` as a cost source in `/retro`. An agent
following any of these calls a command that is not installed. *Repaired*: `/handoff` becomes
`mission-control`, which is what it always meant; the rest are restated per sentence, because each
one meant something different where it stood.

**21 — `/plan` instructs the agent to resolve tiers through a deleted script.**
`plugins/saga/skills/plan/SKILL.md` said "resolve each work-shape through `scripts/tier_defaults.py`"
and named `resolve_tier_with_overlay` and `TierDefaultsError`; issue 1030 removed that module. The
implementation it delegated to survives as fleet-core's staffing component, whose own docstrings
(`plugins/fleet-core/scripts/fleet_commons/staffing.py:6`, `:228`, `:278`) still described
`tier_defaults` as a present caller, and `plugins/saga/scripts/lifecycle_state.py:449` and `:487`
named it as an importable module in `:mod:` references. *Repaired* — the skill points at
`staffing.load_overlay` / `staffing.resolve_shape`, and the four docstrings say the delegation ended.

### P2

**10 — `/qa` cites a deleted dispatch table.** `plugins/saga/skills/qa/SKILL.md:223` pointed at
`saga/skills/loop/references/dispatch-table.md`, removed in this diff. `plugins/saga/README.md`
linked the same path. *Repaired.*

**11 — the new review path cannot resolve an `ok` roster today.**
`plugins/saga/scripts/review_roster.py:386-392` documents that `_executors_from_staffing` is "Empty
by design today" because the lifecycle repository's executor-verification ledger has no entries.
Running the real generator against a declaration built for this repository returns `status: refused`
on `verification_presence` for all four always-on lenses. `review_roster.py` maps that to exit 1, a
run-setup fact rather than a crash, so the behaviour is as designed — but it means `/code-review` as
shipped resolves `refused` for every run until that ledger has entries. **Carried as a residual**:
the blocker is in `infiquetra/infiquetra-sdlc`, not in this diff, and no card here names it.

**12 — a guard required `/qa` to cite the deleted dispatch table.**
`tests/test_saga_plugin.py::test_qa_functional_test_step_contract` asserted
`"loop/references/dispatch-table.md" in skill_doc`, so fixing finding 10 failed the suite. The
floor's real subject is that `/qa` does not restate the routing map. *Repaired*: retargeted to the
negative plus the positive half, with the deleted-path assertion inverted.

**13 — a guard required `/plan` and `/work` to cite the deleted reference file.**
`tests/test_doc_review_loop.py::test_the_skills_keep_the_explicit_invocation_contract_where_the_choice_is_made`
required `references/workflow-backend.md` in the backend-offer section, which is why finding 9's dead
links survived the removal card. *Repaired*: retargeted to the one-backend contract, plus a new case
asserting that neither skill points at the missing file.

**22 — a third guard required a skill to name a removed command.**
`tests/test_saga_plugin.py::test_intake_exit_saga_creates_no_issue` asserted `"/handoff" in
office_doc` and `"/handoff" in convergence_doc`, so repairing finding 20 failed the suite — the same
shape as findings 12 and 13, found only by running the full suite after the repair. *Repaired*: the
route loop pins the three routes that still resolve, and the boundary half the `/handoff` row really
carried — that Mission Control owns the issue — is asserted directly, which is a property rather
than a command name.

**23 (pre-existing) — two tests decide their verdict from the ambient environment, and they block
the push gate.** `tests/test_agent_launcher_plugin.py::test_a_launcher_that_fails_mid_file_binds_nothing`
and `tests/test_wiring_canary.py::test_plan_contract_guards_have_teeth` pass from a shell and fail
from the saga pre-push gate on the same commit. The gate's pytest child inherits
`CLAUDE_PLUGIN_ROOT`, which Claude Code sets for every plugin hook;
`plugins/orchestrate/.../orchestrate.py:1902` reads it and resolves the *installed* agent-launcher
instead of the deliberately broken one the test built in `tmp_path`, and the canary's subprocesses
inherit it and resolve fleet-core without the checkout root the mutation removes. Setting the
variable by hand reproduces the first failure in 0.18 seconds — at this branch **and at the clean
branch tip**, so it is not a regression from these repairs. *Repaired*: `tests/conftest.py` gains an
autouse fixture that scrubs `CLAUDE_PLUGIN_ROOT` and `AGENT_LAUNCHER_ROOT`, following the two
ambient-environment fixtures already there for the saga concurrency override and the
`INFIQUETRA_FLEET_` family. Both tests then pass with the variable set.

**14 — `references/operator-choice.md` §5.1 contained a fenced command with no command.** The edit
that removed `/outcome` deleted `python3 plugins/saga/scripts/outcome.py approve <outcome_id> \` and
left its continuation flags alone inside a ```bash block. Introduced by this diff. *Repaired.*

**19 — the QA strategy runner parses a command with `str.split` where its sibling uses
`shlex.split`.** `plugins/saga/scripts/qa_strategies.py:849` (reviewed revision) built the argument
vector with `command.split()`, so a profile command holding a quoted argument with a space —
`pytest -k "not slow"` — was cut into three arguments and the program was handed something the
operator never asked it to run, with no error anywhere. `plugins/saga/scripts/build_loop.py:379`
parses the same kind of value with `shlex.split`, so the release ships two different parsers for one
kind of value. The `except ValueError` around `command.split()` carried a `pragma: no cover` comment
saying "split never raises; kept for shape parity", which is the tell: the error handling of
`shlex.split` was copied without `shlex.split`. The repository's own `.saga-profile.json` commands
are simple enough not to trip it today. *Repaired*: both call sites now use `shlex.split` and refuse
an unparseable command by name rather than raising, with two cases in `tests/test_qa_strategies.py`.

**15 — `references/operator-choice.md` links two deleted scripts**, `../scripts/outcome_dispatcher.py`
and `../scripts/outcome_liveness.py`, in §8 and §9. *Repaired.*

### P3

**16 — three docstrings describe a ladder that no longer has rungs.**
`plugins/saga/scripts/saga.py`'s `_orchestration_rank` said "(inline < cc-workflows-ultracode)";
`lifecycle_state.py`'s `_ALL_BACKENDS` comment said the ladder "reads inline ->
cc-workflows-ultracode" over a one-element tuple; `ORCHESTRATION_TIERS`' comment said "the ladder is
now two rungs" over a one-element tuple; `recheck_orchestration_capability`'s docstring and the
`--fallback-mode` default both said `team-execution`. *Repaired*, including the argparse default,
which would have passed an unwritable value.

**17 — `references/intent-envelope.md` shows `"backends_permitted": ["inline", "team-execution"]`**
in an example payload, and names `/outcome` verbs throughout. *Repaired by framing*: the file now
opens with a banner saying the `/outcome` coordinator it was captured for is removed and that it is
a record of a schema, not a set of commands. The example payload is left as written, because it is a
record of what a real envelope held.

**18 (pre-existing) — `plugins/saga/references/rubrics/spec/core/blueprint_fidelity.md` contains a
`](link)` placeholder.** Present at the base revision. Not this diff's defect; reported for honesty.
**Carried as a residual.**

## Cycle 2 — `accepted`

Reviewed revision `d133cb3720bc02a286a483f1c0cfe6d267d6d825`, the head of `parent/1018` after three
repair commits and a merge of the branch tip that had moved under the review
(`994443ea` dropped two continuous-integration steps whose scripts issue 1030 removed; `61a08b10`
pinned a herdr-pane environment variable in one roster test). The scoring below was taken at
`9946952c`, before the third commit, which carries only finding 23's conftest fixture, its journal
entry and its changelog line; the full suite is green at both. The repairs were made by this
reviewer, which the operator directed for this run; the ordinary custody rule — the reviewer hands
findings back and does not author the fix — did not apply here, and that is the largest deviation in
this document.

### Re-verification, finding by finding

Each repaired finding was re-checked against the repaired head, not assumed from the edit.

| # | How it was re-verified |
|---|---|
| 1 | `recommend_execution_backend(workflow_available=False)` returns rather than raises, for both provenance values, at the function and at `lifecycle_state.py recommend-backend --no-workflow` |
| 2 | `pytest tests/test_operator_choice_drift.py` collects and passes seven cases; an abstract-syntax-tree audit of every `test_*.py` in the repository reports no file with zero collected tests |
| 3 | `wiring_canary.py --target archived-orchestration-mode` prints `caught` |
| 4, 6, 7, 20 | a grep for each of the eleven removed command names across `plugins/saga/{skills,commands,docs,references}` and `README.md`, excluding sentences that record the removal, returns nothing outside three deliberate history banners |
| 5, 14, 15 | `operator-choice.md` §1 states one selectable value and matches `ORCHESTRATION_MODES`; the orphaned fenced block is replaced by a sentence describing the approval, since the command it quoted is gone; both deleted script links are gone |
| 9, 13 | a relative-markdown-link scan over `plugins/**/*.md` reports one broken link, the pre-existing `](link)` placeholder of finding 18 |
| 10, 12, 22 | `tests/test_saga_plugin.py` passes, including the two floors that had pinned a removed command's name |
| 16, 21 | the four docstrings and the argparse default no longer name a removed module or an unwritable value |
| 19 | `tests/test_qa_strategies.py` passes, including the new case asserting `pytest -k "not slow"` stays four arguments |

### Scores

| Lens | Derived overall | Met its pair? |
|---|---|---|
| `architecture-maintainability` | 9.2 | yes |
| `correctness` | 9.3 | yes |
| `security` | 9.6 | yes |
| `testing` | 9.2 | yes |

Every selected scoring lens met its threshold pair, so the typed outcome is **`accepted`** and the
derived overall across the four is **9.3**, above the operator's acceptance bar of 8.

Independent gates at the reviewed head: the full suite (`uv run pytest tests/ plugins/*/tests/`),
`ruff check`, `ruff format --check`, `mypy plugins/ scripts/ tests/`, the release-surface parity
check, the release-surface diff guard against the base, the plugin validator, the changelog heading
lint, the journal-order lint and the gate-absence contract lint. The built-versus-planned audit is
`CLEAN` for the repairs themselves: every change traces to a finding in this document, and nothing
was deleted that the fifteen cards do not name.

### Residuals

| # | Priority | Why it is carried |
|---|---|---|
| 11 | P2 | the lens roster resolves `refused` until the lifecycle repository's executor-verification ledger has entries; the blocker is in `infiquetra/infiquetra-sdlc` and no card here names it |
| 17 | P3 | the intent-envelope example payload still names `team-execution`; the file's new banner frames the whole document as a record, which is the honest fix for an example of what a real envelope held |
| 18 | P3 | the `](link)` placeholder in `references/rubrics/spec/core/blueprint_fidelity.md` predates the base revision |
| — | P3 | `references/saga-spec.md`, `references/intent-envelope.md` and `operator-choice.md` §§5–8 still describe removed commands as writers and consumers. Each now carries a banner saying so, which is the honest fix for a storage contract and a history; rewriting them to erase the removed commands would destroy the only record of what a pre-1.0.0 saga tick's fields meant |
