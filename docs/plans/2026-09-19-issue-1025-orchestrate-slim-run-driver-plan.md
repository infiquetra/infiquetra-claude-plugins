---
title: Orchestrate slims to the run driver — fresh worktrees, one record per issue, parent branches
type: refactor
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Orchestrate slims to the run driver — fresh worktrees, one record per issue, parent branches

## Summary

The orchestrate plugin's driver script (`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`,
6,450 lines) keeps the half of its behaviour the operator actually wants — a git worktree and a branch
for each unit of work, launching an agent session through the agent-launcher plugin, sending that unit
its command, waiting for it, merging its branch back, and cleaning up — and loses the protective layer
built around that half.

Six subsystems go: the fixed-path run file, the landing-worktree recovery machinery, the `redrive`
recovery command and its state machine, the board-writeback failure records, the `collect` path that
merges a run branch into whatever the operator has checked out, and the companion-plugin version
floor's refusal to run. Six behaviours arrive in their place: a fresh worktree on every launch, a
virtual-environment step inside the worktree helper, an immediately persisted launch, a parent branch
that children merge onto by merge turn, cleanup that runs for every unit and names what it could not
remove, and one repair owner recorded per shared blocker.

State moves to the run record that issue 1023 already shipped (`plugins/saga/scripts/run_record.py`,
`run_record.v1`): one file per issue, so two issues can be driven in one repository at the same time.

## Problem Frame

Orchestrate already implements the execution model the operator wants over herdr, the terminal
multiplexer that hosts agent sessions. Its open defect list is almost entirely in the protective layer
rather than in that model, and the five collisions the record actually contains each map to one simple
line of repair rather than to a mechanism:

| Recorded collision | Where it is recorded | The simple line that answers it |
|---|---|---|
| Two workers repairing the same thing | simplification review section 8, cluster A | one repair owner per shared blocker, as a record field (U7) |
| A shared file written by several writers | simplification review section 8, cluster B | one record per issue, not one file per repository (U1) |
| A relaunch landing in a stale worktree | issue 886, findings 1 and 3 | a fresh worktree on every launch (U2) |
| A remote branch that cannot be deleted because a worktree holds it | issue 876; pull requests 867, 869, 872 | release the worktree at the merge turn (U5) |
| A unit whose worktree has no virtual environment | issue 876 discussion; observed on this run | a virtual-environment step in the worktree helper (U2) |

None of the five needs a lock, a lease, a reservation, or a receipt, and the parent issue 1018 forbids
adding one. The stop condition on the card says to stop and report if the fresh-worktree and
immediate-persist behaviours cannot be proven without a reservation, or if a merge-turn rule cannot
express the guard against reverting a newer `main`. **Neither condition fires** — KTD2 and KTD6 below
give the reservation-free mechanism for each, and the residual each one leaves is named rather than
papered over.

### What was read to ground this plan

- The whole driver script, 6,450 lines, and its event-socket sibling `herdr_events.py` (133 lines).
- The 26 orchestrate test modules under `tests/`, 17,953 lines in total.
- The run record issue 1023 shipped: `plugins/saga/scripts/run_record.py` (468 lines) and its contract
  document `plugins/saga/references/run-record.md` (244 lines).
- The roster helper issue 1024 shipped:
  `plugins/agent-launcher/skills/agent-launcher/scripts/roster.py` (917 lines), and
  `launcher.py` (2,182 lines) beside it.
- The software-development-lifecycle repository's parent-branch chapter at its pinned revision
  `5efc869f`, `docs/process/parent-branch-integration.md`.
- Issue 1025, its parent 1018, and its ten children: 874, 876, 879, 891, 901, 944, 960, 979, 990, 991.

## Admission answers

The repository's own admission step ran before planning
(`uv run python plugins/saga/scripts/admission.py --issue 1025`). It filled twelve of the thirteen
run-configuration parameters without asking and wrote
`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1025.json`.
The eight questions it put, the answer given, and where each answer came from:

| Question | Answer | Source of the answer |
|---|---|---|
| Risk tier | `high` — it rewrites the driver that launches every unit; the guard is the card's test list, each test tied to a recorded collision or an open child card | issue 1025's own `### Risk` section, verbatim |
| The seven approval boundaries | `none — stop and ask the operator` in every one of the seven categories; the seventh also records that a plan-review or code-review override stops and asks | the operator's standing list for this run, relayed in the coordinator's instruction |
| Destination | `pr` | the coordinator's instruction, and the `plan_pre_answers.v1` carrier in the invocation |
| Staffing overrides | `none` — the staffing component's defaults stand | the coordinator's instruction |
| Lens declaration | the four always-on lenses, plus `reliability`, `api-contract`, `adversarial`, `documentation-clarity`, and `agent-usability`; `deployment-infrastructure`, `performance`, `privacy`, `previous-comments`, `accessibility-human-usability`, and `experience` left out with a reason each | the lens catalogue read live through fleet-core's staffing component, matched against this card's change to concurrency, git, and cleanup behaviour |
| Repair allowances | three standard cycles and two escalated | the lifecycle repository's decided default at `5efc869f`, operator decision D6 of 2026-09-06 |
| Response to unfinished functional testing | `continued-goal-driven-repair` | **the lifecycle has no default here.** `RC-unfinished-testing-response` at `5efc869f` says the value is "chosen per run from a closed set of two" and names no default. The mode chosen matches parent issue 1018's build-until-it-works loop, and this repository's non-production destination is `none`, so the prescribed testing is the test suite. The mode is bounded: one recorded extension, four early-stop conditions, and on exhaustion the run returns to the operator anyway |
| Change shape | `code` | the card's "Files expected to change" list, which is four source files, the test modules, and the release surfaces |

Two further answers the coordinator named were not asked, because the tracked repository profile
`.saga-profile.json` already settles them: branch preview is `false`, and `main` is not consumed
directly (`main_consumed_directly: false`). Admission recorded both with source `profile`.

One parameter remains unset: `per_lens_score_threshold`. The lens catalogue that fleet-core's staffing
component returns carries neither a `strictness_ladder` nor a `thresholds` key, so
`admission._resolve_catalogue` finds nothing to fill it with and leaves its source at `unset`. That is
an observation about the catalogue, not a defect this card repairs; it is recorded here so the gap is
found by reading rather than by a later surprise.

## Questions answered from the card

The installed plan skill asks the operator a question at three points. Each was answered from the card,
the run record, the lifecycle repository at its pin, or the code, and none was invented:

| Skill phase | Question | Answer taken | Where the answer came from |
|---|---|---|---|
| 0.4 | Is a plan document warranted? | Yes | The card carries eleven acceptance criteria across six subsystems and ten child cards; it is the opposite of atomic |
| 0.5 | Scope class | Deep | 6,450 lines lose six subsystems and gain six behaviours; the card's own complexity note says large |
| 5.1 | Destination | `pr` | The `plan_pre_answers.v1` carrier, validated by `plan_pre_answers.py`, which applied `destination: pr` and `backend: inline` and printed `"stop": null` |
| 5.2 | Execution backend | `inline` | The same carrier. The two other backends are explicit-invocation only and the carrier never applies them |

One question is **not** answered here and is put to the operator instead — see "Operator question" below.

## Requirements

**R1.** Orchestrate reads and writes issue 1023's `run_record.v1` for one issue, resolved through
`run_record.resolve_store_root()`, and never writes `.orchestrate/run.json`. Two issues driven in one
repository have two records and never contend for one file.

**R2.** Every launch creates a worktree at a path no previous launch used, checked out on the unit's
own branch, and never reuses an existing path.

**R3.** The worktree helper runs a virtual-environment step in the new worktree, and a failure of that
step is named on the unit rather than swallowed.

**R4.** A launch is persisted to the record before the launcher is called and the wrapper identity is
persisted the moment the session exists, so a repeated `go` in the launch window launches the unit
once.

**R5.** The width number in the record's `concurrency_allocation` bounds how many units are live at
once across repeated `go` calls; `--limit` remains a per-call slice and its help says so.

**R6.** A parent issue with children gets a parent branch; children merge onto it one merge turn at a
time, and the turn is ordinary execution state in the record, never a lock, lease, or reservation.

**R7.** A merge that would revert a file `main` carries more recently is refused, naming the files.

**R8.** A unit's worktree is released at its merge turn, refusing on dirty or unpushed state and naming
what is at risk, so the branch becomes deletable.

**R9.** Cleanup runs for every unit in scope even when one path cannot be removed, names every
leftover, and its exit status says cleanup was incomplete. The reporting runs even when an exception is
unwinding.

**R10.** `clean` retires the herdr workspaces this run created — ownership read from the record, never
from a name pattern — and reports a managed worktree with no live session.

**R11.** A plan can be validated completely without creating a worktree, a branch, a tab, an agent
session, or a record, running the same assertions `start` runs and reporting the same failures; making
the validation path write anything fails a test.

**R12.** `redrive`, `collect`, and `land` are gone as subcommands. `plan-check`, `start`, `go`, `merge`,
and `clean` exist.

**R13.** A companion agent-launcher plugin below the declared version floor produces a warning and the
command continues; a missing or unusable companion still refuses, because there is nothing to call.

**R14.** The protected-reference check strips whitespace and casefolds before peeling any
`refs/heads/` prefix, and the same normalisation applies to the parent-branch, resolved-branch, and
base comparisons; an ordinary unit branch stays deletable.

**R15.** The launcher's close-failure record survives: the launch handler appends to a unit's note
rather than replacing it, and the cleanup sweep consumes the close return rather than reporting a live
session as closed.

**R16.** The record carries one repair owner per shared blocker, so two units never both repair the
same thing.

**R17.** A wait over several units records every settlement it observes into the record's unit rows,
under a caller timeout, and reports a blocked session rather than answering it.

**R18.** Every test runs against a temporary git repository under pytest's `tmp_path` and a fake
launcher. No test touches a live herdr, this repository's own worktrees, or the primary checkout's
record store.

**R19.** The orchestrate plugin's release surfaces move to version 5.0.0 in the same pull request, and
the changelog names every removed subcommand.

## Key Technical Decisions

**KTD1 — The run record replaces the run file, and the issue number replaces the run identifier.**
`Run` and `Unit` become views over a `run_record.v1` document rather than over
`.orchestrate/run.json`. Each mutating subcommand takes `--issue <N>`, resolves the store root through
`run_record.resolve_store_root()` (which reads the git *common* directory, so a unit's own worktree
sees the same file the coordinator does), and loads the record for that issue. The run's identity is
the issue number, so two issues coexist as `issue-1025.json` and `issue-1026.json` by construction
rather than by a naming convention. *Rejected:* keeping a second orchestrate-owned file beside the
record, which reintroduces exactly the two-authorities problem the record exists to end; and keeping
the fixed path with a `--run` selector, which is what card 878 asked for before the record existed.
*Consequence:* the task-spill mechanism goes with the run file. A unit's task lives in the record's
unit row; the spill existed because the fixed-path file was rewritten whole on every save, and the
record is one issue's state rather than a whole campaign's.

**KTD2 — An immediately persisted launch replaces the launch reservation.** In the launch loop the
unit row is written with `status = running` and a `launch_started_at` stamp and saved *before* the
launcher is called, and the wrapper identity (`tab_id`, `pane_id`, `agent_name`) is persisted through a
callback the launcher invokes the moment the session exists, rather than after delivery returns. The
whole launch window is wrapped so that a `BaseException` — which is what a keyboard interrupt is, and
what neither existing `except SystemExit` clause catches — saves the record and re-raises.
Eligibility reads only `pending` units, so a second `go` in the window finds the unit `running` and
does not pick it. *Rejected:* a durable claim written before launch with an owner and an expiry, which
is a reservation by another name and which parent issue 1018 forbids.
*Residual, stated rather than hidden:* two `go` processes that read the record at the same instant can
both see `pending`. The collision actually recorded is a repeated call by one polling driver, which is
sequential, and that is what the test expresses. The *harm* card 900 names — two sessions in one
worktree — is separately impossible after KTD3, because the second launch would build its own fresh
worktree.

**KTD3 — A fresh worktree on every launch, and the branch is the unit's identity.** The worktree helper
takes the canonical path `<repository parent>/orch-<issue>-<unit>` and, when that path exists on disk
or is registered with git, uses the lowest unused numbered sibling instead. It never prints "worktree
already there" and never checks out into an existing directory. The unit's *branch* is reused when it
exists, because the branch holds that unit's history and a relaunch must continue it; only the working
directory is new. The worktree is created with `git worktree add <fresh path> <branch>` for an existing
branch and `-b <branch> <parent branch>` for a new one. *Rejected:* fast-forwarding or refusing a
reused worktree, which is what card 886 proposed before the simplification decided that a fresh
directory removes the question.

**KTD4 — The virtual-environment step is declared, not guessed.** After the worktree is created, the
helper runs a setup command in it: the value of `ORCHESTRATE_WORKTREE_SETUP` when set, otherwise
`uv sync --locked --extra dev` when a `uv.lock` file exists at the worktree root, otherwise nothing.
A failure is recorded on the unit's note and the unit is not launched, because a session in a worktree
with no environment produces confident work that cannot run its own tests. A repository with no
`uv.lock` and no override gets no step and one printed line saying so. *Rejected:* copying or
symlinking the primary checkout's `.venv`, which produces a virtual environment whose recorded paths
point at another directory.

**KTD5 — The parent branch is named from the issue, and its shape is recorded once.** `start` names the
run's shared branch `parent/<N>` when issue `N` has sub-issues and `issue/<N>` when it does not, reads
the sub-issue count once through `gh` at `start`, records the chosen name in the record, and never asks
again. When `gh` cannot answer, the name falls back to `issue/<N>` and the line printed says which
branch was chosen and why. An explicit `--branch` overrides both. This is the naming this repository's
own live work already uses (`parent/1018`, `issue/1025`). *Rejected:* deriving the shape on every
command, which makes a network failure change behaviour mid-run.

**KTD6 — The merge turn is record state, and it carries the `main` regression guard.** Each unit row
gains `merge_state`, one of `ready`, `merging`, `merged`. `merge` refuses to open a second turn while
any unit is `merging` and names that unit; it writes `merging` before the merge and `merged` or `ready`
after. There is no expiry, no owner token, and no release ceremony — it is the "ordinary execution
state" the lifecycle repository's parent-branch chapter describes, and that chapter explicitly rejects
a lock service for it.

**A `merging` row is checked against git, never trusted on its own.** A turn whose process died leaves
the row at `merging` with nothing to clear it, and with no expiry that would block every later turn
forever — which is card 992's failure shape (a failed recovery leaving a unit in the one state its own
door cannot act on) reappearing in a new place. So the refusal is derived on read: before refusing,
`merge` asks git whether a merge is actually in progress on the parent branch (`MERGE_HEAD` present in
the turn's worktree, or that worktree still registered). When git says no merge is in flight, the row is
reset to `ready` with a line saying the previous turn did not finish, and the new turn proceeds. Only a
turn git confirms is live refuses the next one. This is the "inspect the actual Git and worker state
first" step the lifecycle repository's own merge-turn flowchart names for an unknown outcome.

The guard against reverting a newer `main` is a rule of the turn, evaluated before the parent branch
pointer advances. The turn first refreshes the remote-tracking ref (`git fetch origin main`) and
**refuses the turn when that fetch fails**, rather than comparing against a stale `origin/main` —
a guard that reads an out-of-date ref passes silently, which is the same quiet failure card 875
reported. Then, if `origin/main` is not an ancestor of the merge result, the set of files the merge
changes is intersected with the files `origin/main` changed since their merge base; a non-empty
intersection refuses the turn and names every file in it. This is card 875's guard restated for a
per-unit merge onto a parent branch rather than for the `collect` path that this card removes.
*Rejected:* refusing any merge whose parent branch is behind `main`, which would make ordinary parallel
work unmergeable; and comparing against a local `main`, which is whatever the operator last pulled.

**KTD7 — Cleanup is total and its reporting is exception-proof.** The sweep iterates every unit in
scope and continues past a failure rather than returning on the first one; every failure is collected
with its path and git's own message; the report runs from a `finally` block that contains no command
that can itself raise, so a leftover is named even when an exception is unwinding. The exit status
distinguishes "everything cleaned" from "merges landed, cleanup incomplete". This closes issue 960 (the
reap skipped entirely when one path could not be cleaned), issue 979 (a removal failure recorded into a
list nobody read), and the ordering half of issue 876. *Rejected:* raising on the first cleanup failure,
which is how issue 960 happened.

**KTD8 — Test failures are injected, never induced from the operating system.** The cleanup-failure
tests drive a fake command runner that returns a non-zero result for a named `git worktree remove`
invocation, so every machine exercises the same code path and nothing undeletable is left on disk. This
replaces the three-way host-dependent mechanism (`chflags uchg`, `chattr +i`, `git worktree lock`) that
issue 991 reports. Every orchestrate test builds its repository under pytest's `tmp_path` and passes a
fake launcher, so no test reaches a live herdr or the primary checkout's record store. *Rejected:*
keeping a real filesystem-permission failure behind a platform marker, which leaves the defect provable
on one platform only.

**KTD9 — The plan validator is the first half of `start`, not a copy of it.** `cmd_start` splits into
`validate_plan(plan)` — which runs `assert_no_engine_prefs`, `assert_safe_path_component`,
`assert_safe_unit_names`, `assert_dependencies_reachable`, `assert_vendors_available`,
`assert_saga_reachable`, and the agent-launcher availability check, and returns the parsed units — and
`create_run_resources(...)`, which creates the branch and the record. `plan-check` calls only the
first. One code path stays the source of truth, so a validator cannot agree with a `start` it no longer
matches. *Rejected:* a `--dry-run` flag on `start`, which puts the non-mutating path inside the
mutating door.

**One claim in issue 879 is stale and the implementer must not act on it.** That card says
`assert_review_transport` "is **not** among" the assertions `start` runs, and warns that a validator
aiming to match `start` "must not silently add it" (verified there against `origin/main` on
2026-08-28). At this card's base commit `4e951f0e` that is no longer true:
`assert_review_transport(units)` is called at `orchestrate.py:1103`, inside `plan_units`, and
`cmd_start` calls `plan_units(plan)` at `orchestrate.py:3441`. So `start` runs it today by way of the
plan parser, and the validator reaches it for the same reason — nothing is added, and the warning is
satisfied by leaving the call exactly where it is. The U4 test scenario that expects a bad review
transport to be reported follows the code, not the stale sentence.

**KTD10 — The width number is the only concurrency bound, and it is one shared budget.** `go` launches
at most `concurrency_allocation − live` units this call, taking the value from
`run_configuration.concurrency_allocation.value` in the record (10 for this repository, from the
profile). `--limit` keeps its meaning as a slice of one call and its help text says it is not a cap.

**`live` counts role sessions as well as units.** The roster helper already refuses to stand up more
role panes than the same number allows (`roster.py` reads `concurrency_allocation` and raises when the
seat count exceeds it). If orchestrate counted only its own units, a run with six role panes and ten
units would put sixteen agent sessions on one account against a number that exists for the account's
rate limit. So `live` is the count of units recorded `running` plus the count of the record's `roster`
rows whose state is not `closed`. When that sum already meets the width, `go` launches nothing this
call and says which two counts add up to the bound.

*Rejected:* a separate orchestrate-owned ceiling, which would be the second authority for a number the
record already carries; and counting units alone, for the reason above.

**KTD11 — A shared blocker records its one repair owner, and orchestrate only reads it.** The record's
unit rows gain `shared_blockers`, a list of `{blocker_id, owner_unit, note}`. Orchestrate does **not**
diagnose blockers — it has no view of what a session is stuck on — so it is not the producer of these
rows. The producer is whoever notices the blocker: the coordinator, or a role session writing through
the record. Orchestrate's whole part is the read: when a unit's row names a blocker whose `owner_unit`
is a different unit, the driver reports it by name instead of letting that unit take a merge turn for
it. That is the "duplicate repairs" collision answered by a field and one refusal, rather than by a
protocol. *Rejected:* having orchestrate infer a shared blocker from two units touching one file, which
is a guess that is wrong in both directions.

**KTD12 — The companion floor warns; a missing companion still refuses.** The floor check prints one
line naming the installed version, the required floor, and the update command, then continues. The
distinction that survives is between *stale* and *absent*: a below-floor launcher still has every name
orchestrate calls, so the call can be made; a launcher that was never ingested, or that is missing a
required name, has nothing to call and still refuses with the install remedy. *Rejected:* dropping the
floor entirely, which removes the operator's only signal that the companion is behind.

**KTD13 — Nothing is removed that the card or one of its ten children does not name.** The removal
inventory in U8 lists each removal beside the card that names it. Everything else in the driver stays,
including the board-writeback path, the typed review-result routing, `park`, `resume`, `expand`,
`adopt`, `check`, `diff`, `status`, `settle`, `wait`, `roster`, `saga`, and `announce`. Two of those
have a live question over them, put to the operator below rather than decided here.

## Implementation Units

Units are dependency-ordered. U1 lands first because every later unit reads the record; U8 lands last
because it deletes what the earlier units stopped using.

### U1. The run record replaces the fixed-path run file

**What:** Rewrite `Run.load` / `Run.save` and `read_unit` as a view over `run_record.v1`. Add
`--issue <N>` to every subcommand that touches state. Resolve the store root through
`run_record.resolve_store_root()`. Delete `RUN_FILE`, `TASK_DIR`, the task-spill helpers,
`RUN_FILE_CONTRACT`, `KNOWN_RUN_FILE_CONTRACTS`, `RunFileContractError`, and
`ensure_local_run_state_excluded`.

**`start` requires the record; it never creates one.** The record is written by the repository's
admission step (`plugins/saga/scripts/admission.py`), which is what fills the thirteen
run-configuration parameters and the seven approval boundaries. `start` reading a missing record
refuses with exit 2 and names the admission command, rather than minting a record with an empty
admission block that every later reader would have to treat as "not asked yet" — which is the shape
the record's own contract document calls a refusal case. `start` adds the unit rows and the parent
branch name to a record that already exists.

**Record fields read:** `schema`, `issue`, `repo`, `admission.destination`,
`run_configuration.concurrency_allocation.value`, `run_configuration.staffing_models_and_efforts.value`,
`units`, `next_step`. **Written:** `units` rows and `next_step` only. `admission`, `approval_scope`,
`run_configuration`, `review_cycles`, and `roster` are never written by orchestrate — the roster rows
belong to `roster.py`, which is their one writer.

**Two different things are called "roster" and the plan never conflates them.** The record's `roster`
key holds one row per staffed *role session*, written by `roster.py`. Orchestrate's `roster`
subcommand lists the *agent vendors* this machine can launch and touches no record at all. The
subcommand keeps its name because nothing names it for removal; it is unrelated to the record key.

**Unit-row keys this card adds to the record's free-form `units` array** (the record's contract
document lists the row's content as "unit id, worktree, branch, merge-turn state, last mechanical-check
result" and does not fix a key set, so these are additions within `run_record.v1`, not a version bump):
`merge_state`, `launch_started_at`, `shared_blockers`. The contract document
`plugins/saga/references/run-record.md` gains a short section naming them, in this same pull request,
so the document and the code do not drift.

**Test scenarios** — `tests/test_orchestrate_record.py` (new):
- Two issues are started in one temporary repository; each gets its own record path and neither read
  sees the other's units.
- A record whose `schema` is not `run_record.v1` produces the one-line refusal and exit 3, never a
  traceback.
- An unknown top-level field in the record survives an orchestrate read-modify-write unchanged and is
  named on standard error once.
- A subcommand run with no record for that issue refuses with exit 2 and names the path it looked at.
- `start` with no record refuses with exit 2 and names the admission command; nothing is created.
- `start` with a record adds unit rows and the parent branch name and leaves `admission`,
  `approval_scope`, `run_configuration`, `review_cycles`, and `roster` byte-identical.
- A unit row written by orchestrate round-trips through `run_record.load` with every added key intact.

**Depends on:** nothing.

### U2. A fresh worktree on every launch, with a virtual-environment step

**What:** Rewrite `make_worktree` per KTD3 and KTD4. Add `fresh_unit_worktree_path(canonical)` beside
the existing registration reader (`registered_worktree_paths`). Add `prepare_worktree_environment(path)`
per KTD4. In the cleanup sweep, keep the existing order — remove the worktree, and only then delete the
branch — and make it explicit that a failed removal keeps the branch and names both.

**Test scenarios** — `tests/test_orchestrate_worktree.py` (new):
- A unit launched twice gets two different worktree paths, and the second path is not the first.
- The second launch checks out the unit's existing branch rather than creating a second branch.
- A path that exists on disk but is not registered with git is still skipped, and the numbered sibling
  is used.
- The setup step runs in the new worktree when `uv.lock` is present; its command is recorded.
- `ORCHESTRATE_WORKTREE_SETUP` overrides the default command.
- A failing setup step leaves the unit unlaunched with its note naming the failure.
- A repository with no `uv.lock` and no override runs no setup step and says so.
- Branch deletion does not run when worktree removal failed, and both the branch and the path are
  named.

**Depends on:** U1.

### U3. The launch is persisted immediately, and the width number bounds it

**What:** Rewrite the launch loop per KTD2 and KTD10. Persist `status = running` and
`launch_started_at` before calling the launcher; persist the wrapper identity through a launcher
callback at session creation; wrap the window so a `BaseException` saves and re-raises. Count live units
from the record and launch at most `concurrency_allocation − live`. Reword `--limit`'s help.

**Test scenarios** — `tests/test_orchestrate_launch_persist.py` (new):
- A second `go` invoked after the first has persisted its launch does not launch the unit again and
  says the unit is already running.
- A keyboard interrupt raised inside the fake launcher after the identity callback fires leaves the
  unit's `tab_id`, `pane_id`, and `agent_name` on disk, and the unit is not relaunched.
- A launcher that raises before the identity callback leaves the unit back at `pending` with its note
  naming the failure, and the next `go` gets a fresh worktree.
- Three `go` calls with a width of two never have more than two units `running`.
- `--limit 1` with a width of two launches one unit, and the next call launches the second.
- The width is read from the record, so a record edited to width one bounds the next call to one.
- A record carrying open roster rows counts them: with a width of three and two roster rows not yet
  closed, one unit launches and the message names both counts.
- A roster row whose state is `closed` does not count against the width.

**Depends on:** U1, U2.

### U4. `plan-check`: a plan is validated without mutation

**What:** Split `cmd_start` per KTD9 and add the `plan-check` subcommand. Exit 0 for a valid plan, 2
for an invalid one, with the same message `start` would print.

**Test scenarios** — `tests/test_orchestrate_plan_check.py` (new):
- A valid plan validates clean and creates nothing: no worktree, no branch, no tab, no record, and the
  working tree is byte-identical afterwards.
- Each assertion is reachable and reports the same failure `start` gives: an unreachable dependency, an
  unavailable vendor, an unsafe unit name, an unreachable saga capability, a retired engine-preferences
  key, and a bad review transport.
- Validation with an active run present leaves that run's record untouched, compared by its
  `updated_at`.
- Exit status is 0 for valid and 2 for invalid, so the command is usable as a gate step.
- **Mutation proof:** the validator runs with a command runner that raises on any git command that
  writes, and on any record save; a seeded write inside the validation path fails the test.

**Depends on:** U1.

### U5. `merge`: the merge turn, the parent branch, and the `main` regression guard

**What:** Rename `land` to `merge` and reduce it. Remove the landing-worktree recovery machinery:
`resolved_retained_land`, `fresh_landing_worktree_path`, `landing_worktree_paths`,
`live_linked_worktree_at`'s landing callers, `Run.conflict_worktree`, and the preserved-path
bookkeeping. Add the merge-turn state per KTD6, the `main` regression guard per KTD6, and the worktree
release per R8. Remove `cmd_collect` and its subcommand.

**Where the merge actually happens.** A turn creates one detached worktree on the parent branch's tip,
merges the unit's branch there, advances the parent branch reference, and removes that worktree at the
end of the turn. The *plain worktree* stays; what this card removes is the bookkeeping wrapped around
it — the `conflict_worktree` pointer that survived an invocation, the numbered-sibling fallback and
its preserved-path reporting, and the retained-merge recovery that inspected a worktree from an earlier
run and decided whether to publish it. That bookkeeping is what "landing reservations" names. A
conflicting merge now aborts the merge in the turn's own worktree, removes it, leaves the unit at
`ready` with the conflict named, and leaves the parent branch untouched: recovery is the worker
re-merging on its next turn, which is what the lifecycle repository's chapter assigns to the merging
worker anyway.

**Unit and child issue are not the same thing, and the plan means unit.** Orchestrate's `units` are
rows in a plan; the lifecycle repository's "children" are child issues. One child issue may be
delivered by several units. The merge turn is taken by a *unit*, because a unit is what owns a branch;
a child issue is finished when every unit that carries it has merged. Nothing in this card maps units
to child issues, and nothing should invent that mapping.

**Test scenarios** — `tests/test_orchestrate_merge.py` (new):
- A unit merges onto the parent branch and the parent branch's tip is the merge commit.
- A second turn is refused while one unit is `merging` **and git confirms a merge is in flight**, and
  the refusal names that unit.
- A unit left at `merging` by a turn that died, with no merge in flight, is reset to `ready` with a
  line saying the previous turn did not finish, and the new turn proceeds. **Mutation proof:** trusting
  the row without asking git makes this test hang the run forever.
- A turn whose `git fetch origin main` fails is refused, and the refusal says the guard could not be
  evaluated against a current `origin/main`.
- A merge whose result does not contain a newer `main` commit touching the same file is refused, and
  every such file is named in the refusal.
- A merge that touches files `main` has not changed since the merge base proceeds even though the
  parent branch is behind `main`.
- A unit's worktree is removed at its successful merge turn, and its branch is then deletable.
- Release is refused when the unit's worktree is dirty, naming the modified paths.
- Release is refused when the unit's branch has commits not on its remote, naming the count.
- A conflicting merge leaves the unit at `ready`, names the conflict, and does not advance the parent
  branch.

**Depends on:** U1, U2, U3.

### U6. `clean`: cleanup runs for every unit and names every leftover

**What:** Rewrite the sweep and `cmd_clean` per KTD7 and KTD8. Retire the herdr workspaces this run
created, with ownership taken from the record's unit and roster rows rather than from a name pattern,
refusing a workspace that still holds a live agent or a tab this run does not own. Add the one useful
check from the retired fleet-doctor command: a managed worktree with no live session is reported by
path. Rewrite the cleanup-failure tests to inject the failure.

**`merge` keeps `--clean`.** The flag reaps exactly the units that turn merged, with the same meaning
it has today, and it is the path card 960 reports: an unremovable path must not skip the reap for
every unit the invocation merged, and the output must say so. The behaviour is U6's because the sweep
is U6's; the flag lives on `merge`.

**Test scenarios** — `tests/test_orchestrate_clean.py` (new). It takes over the cleanup assertions
currently in `tests/test_orchestrate_land_clean.py` (1,631 lines) and
`tests/test_orchestrate_land_worktree.py` (1,027 lines); those two modules are deleted in U8, after
every assertion in them is either carried here or belongs to a subsystem U8 removes:
- One unit whose worktree cannot be removed does not stop the sweep: every other unit is still cleaned,
  the leftover is named with git's own message, and the exit status says cleanup was incomplete.
- A cleanup failure raised while an exception is unwinding is still reported, and the report runs from
  a block containing no command that can raise.
- The failure is injected through a fake runner, so the same path runs on every machine and no
  directory survives the test.
- A workspace this run created and whose tabs are all closed is retired, and a read-back shows it gone.
- A workspace still holding a live agent is not retired, and the refusal names the agent.
- A workspace this run did not create is not retired even when it is empty.
- A managed worktree with no live session is reported by path.
- Repeated cleanup is idempotent and reports an already-absent workspace or worktree cleanly.
- `merge --clean` on a turn that merged two units with one unremovable path still reaps the other
  unit, names the leftover, and the exit status says cleanup was incomplete.
- **Mutation proof:** removing the ownership check fails the refuse-to-retire test, and removing the
  continue-past-failure behaviour fails the total-sweep test.

**Depends on:** U1, U2, U5.

### U7. The four bounded guards and the shared-blocker owner

**What:** Four small repairs and one field.

1. **Protected-reference normalisation (R14, issue 874).** Rewrite `is_protected_remote_branch` to
   strip whitespace, casefold the whole name, and only then peel a `refs/heads/` prefix in any case,
   applying the same normalisation to the parent-branch, resolved-branch, and base comparisons.
2. **The close-failure record survives (R15, issue 944).** The launch handler appends to the unit's
   note rather than replacing it; the sweep consumes `close_run_session`'s return and does not report a
   unit closed when its close failed.
3. **The wait records every settlement (R17, issue 891).** `cmd_wait` writes each settlement it
   observes into the record's unit rows before returning, rather than returning on the first one, under
   the existing caller timeout, and reports a blocked session rather than answering it.
4. **One repair owner per shared blocker (R16, KTD11).** Add `shared_blockers` to the unit row and a
   `merge`-time check that a blocker another unit owns is reported, not repaired.

**Test scenarios** — `tests/test_orchestrate_guards.py` (new):
- `is_protected_remote_branch` is parametrised over `main`, `MAIN`, `refs/heads/main`, `  main  `,
  `" refs/heads/main"`, `refs/HEADS/main`, `Refs/Heads/main`, and `"\trefs/heads/main"`, and every one
  is protected.
- The same normalisation applies to the parent-branch, resolved-branch, and base comparisons, not only
  to the literal denylist.
- An ordinary unit branch such as `orch/1025-u1` is not protected, so cleanup still works.
- **Mutation proof:** restoring the peel-before-strip ordering fails the parametrised assertions.
- A failing close drives through orchestrate and the operator-visible record names the failure; the
  unit is not reported closed. **Mutation proof:** restoring either discard fails this test.
- A two-unit run whose fake event stream settles both units records both settlements in the record.
- A wait that reaches its timeout with a unit still working says so and returns without recording a
  settlement for it.
- A blocked session is reported with its identity, and no reply is sent to it.
- A blocker owned by unit A is reported rather than repaired when unit B meets it, naming A.

**Depends on:** U1, U3, U5.

### U8. Removals, documentation, and release surfaces

**What:** Delete what the earlier units stopped using, update the two documentation surfaces, and move
the release surfaces. The removal inventory, each line with the card that names it:

| Removed | Named by | Note |
|---|---|---|
| `RUN_FILE`, `Run.load`/`Run.save` against it, `read_unit`'s spill path, `TASK_DIR`, `task_spill_marker`, `parse_task_spill_marker`, `strip_task_spill_marker`, `resolve_task_file`, `check_can_spill_unit`, `spill_unit`, `TASK_SPILL_THRESHOLD` | card 1025, "the fixed-path run record" | Landed by U1 |
| `RUN_FILE_CONTRACT`, `KNOWN_RUN_FILE_CONTRACTS`, `RunFileContractError`, `ensure_local_run_state_excluded`, `LOCAL_RUN_STATE_EXCLUDE` | card 1025, same clause | The record owns version refusal and unknown-field preservation |
| `resolved_retained_land`, `fresh_landing_worktree_path`, `landing_worktree_paths`, `worktree_registration_exists`'s landing callers, `Run.conflict_worktree`, `_report_landing_cleanup_failures`'s landing-path form | card 1025, "landing reservations"; children 979, 991 | Landed by U5 and U6 |
| `cmd_redrive`, the `redrive` subcommand, `PROMPT_UNDELIVERED`, `_staged_input_stop`'s redrive route | card 1025, "`redrive` and its state machine" | Recovery is a relaunch from the unit's branch |
| `record_writeback_outcome`, `_report_outstanding_writebacks`, `Run.writeback_failed`, `Unit.launch_receipt` as a persisted record | card 1025, "the receipt and writeback records" | The unit row's identity fields replace the receipt |
| `cmd_collect`, the `collect` subcommand, `landed()`'s collect framing | card 1025, "the `collect` path that can regress `main`"; child 875 by way of the merge-turn rule | Landed by U5 |
| `_LauncherFloorFailure`'s refusal path in `assert_agent_launcher_available` | card 1025, "the companion version floor's refusal of mutating subcommands (warn instead)" | Landed as KTD12 |
| `cmd_land` and the `land` subcommand name | card 1025's acceptance criterion, which requires `merge` and forbids `land` | Renamed, not deleted, by U5 |

**A verified note on the card's grep criterion.** The card asks that
`grep -c -E "reserved_landing_paths|launch_reservation|record_writeback_outcome"` print 0. Two of the
three names do not appear in the current file at all — checked against the working tree at base commit
`4e951f0e`. Only `record_writeback_outcome` is present, at line 3389 and its two call sites. The
criterion is therefore satisfied by U1 and this unit together, and the two absent names are recorded
here so a later reader does not go looking for code that was never there.

**Test modules deleted, and the rule that governs the deletion.** A module is deleted only when every
assertion in it has been carried into a new module or belongs to a subsystem this card removes. Four
modules go on that rule, 4,090 lines in total:

| Module | Lines | Why it goes |
|---|---|---|
| `tests/test_orchestrate_land_clean.py` | 1,631 | Its cleanup assertions move to `tests/test_orchestrate_clean.py` (U6) and its protected-reference assertions to `tests/test_orchestrate_guards.py` (U7); the rest tests the landing bookkeeping U5 removes |
| `tests/test_orchestrate_land_worktree.py` | 1,027 | Tests the landing-worktree recovery machinery U5 removes; its cleanup-failure assertion is re-authored with an injected failure in U6 (issue 991) |
| `tests/test_orchestrate_land_announce.py` | 521 | Tests the writeback records U1 and this unit remove; the announce path that stays keeps its coverage in `tests/test_orchestrate_board_writeback.py`, which is not deleted |
| `tests/test_orchestrate_launch_and_land.py` | 2,131 | Split: the launch assertions move to `tests/test_orchestrate_launch_persist.py` (U3) and the land assertions to `tests/test_orchestrate_merge.py` (U5) |

Every other orchestrate test module survives and is updated in place where the record replaces the run
file. Before any deletion, the implementer lists that module's test function names and records, per
name, where the assertion went — carried forward, or removed with its subsystem, naming which. A name
that fits neither is not a deletion; it is a finding.

**What stays, because nothing names it for removal:** `roster`, `saga`, `expand`, `review-result` and
the whole typed review-routing family, `status`, `settle`, `wait`, `announce` and the board-writeback
path, `check`, `diff`, `adopt`, `park`, and `resume`.

**Documentation:** `plugins/orchestrate/skills/orchestrate/SKILL.md` (573 lines) and
`plugins/orchestrate/commands/orchestrate.md` (538 lines) are rewritten to describe the slim
subcommand set, the record, the parent branch, and the merge turn. Every removed subcommand is removed
from both.

**Release surfaces:** `plugins/orchestrate/.claude-plugin/plugin.json` moves from 4.5.0 to **5.0.0**;
`.claude-plugin/marketplace.json` matches; `plugins/orchestrate/CHANGELOG.md` gains a 5.0.0 entry whose
`### Removed` section names `redrive`, `collect`, and `land` by name, and whose `### Changed` section
names the run-record move as the breaking change it is. The declared `saga` dependency floor rises to
the version that carries `run_record.py`.

**Test scenarios** — `tests/test_orchestrate_surface.py` (new):
- `--help` lists no `redrive`, `collect`, or `land`, and does list `plan-check`, `start`, `go`,
  `merge`, and `clean`.
- The driver source contains no match for
  `reserved_landing_paths|launch_reservation|record_writeback_outcome`.
- A below-floor companion warns and the command continues; a missing companion still refuses.
- The plugin manifest version, the marketplace entry, and the newest changelog heading agree on 5.0.0.

**Depends on:** U1 through U7.

## Scope Boundaries

**Out of scope — true non-goals.**

- No lock, lease, reservation, or receipt, whatever a test would like. Parent issue 1018 forbids one and
  its stop condition says to report rather than add one.
- No concurrency cap beyond the width number the record carries.
- No change to the agent-launcher plugin's pane-write door, its launch receipt shape, or its ownership
  proof.
- No change to the saga run record's `schema` token or its twelve top-level keys. This card adds keys
  inside the free-form `units` rows, which `run_record.v1` does not fix, and documents them.
- No reconnect-with-catch-up on the herdr event socket. The event client dropped it deliberately when
  it was salvaged, and re-running a wait is the cheaper recovery. Issue 891 does not ask for it.
- No change to the typed code-review result contract or its routing. Issue 1027 owns the code review.

**Deferred to follow-up work.**

- The board-writeback path's future — see the operator question below.
- `per_lens_score_threshold` stays unset until the lens catalogue carries a strictness ladder under a
  key `admission._resolve_catalogue` reads. Observed, not repaired here.

**Which children this card's merge closes outright, and which need their own follow-up.**

| Child | Unit that satisfies it | Closed by this merge? |
|---|---|---|
| 874 — protected-reference denylist casefold and strip | U7 | Yes |
| 876 — release empty lane workspaces and worktrees at merge | U5 (release at the merge turn) and U6 (workspace retirement) | Yes |
| 879 — non-mutating plan validator | U4 | Yes |
| 891 — bounded wait on herdr events | U7. Largely landed already by issue 1024's roster helper, which waits per role with `herdr agent wait --timeout` and reports a blocked agent rather than answering it. What remained in orchestrate is that the unit wait returns on the *first* settlement; U7 records every settlement it observes | Yes |
| 901 — the width number bounds concurrent launches | U3 | Yes |
| 944 — keep the launcher's close-failure record | U7 | Yes |
| 960 — `land --clean` skips reaping | U6 | Yes |
| 979 — landing worktree removal failure during unwinding | U6 (and U5, which removes the landing worktree entirely) | Yes |
| 990 — wrapper identity persisted between session create and go | U3 | Yes |
| 991 — landing-cleanup-failure test proves a different path each run | U6 | Yes |

All ten close outright. None needs its own follow-up card; the residuals this plan carries are named in
KTD2 and in "Deferred to follow-up work" above, and neither belongs to one of the ten.

## Risk Analysis and Mitigation

| Risk | Likelihood | What it looks like | Mitigation |
|---|---|---|---|
| A removed protection was load-bearing for a case not in the record | Medium | A run fails in a way none of the five recorded collisions describes | The card's own instruction: add the simplest mechanism that covers the demonstrated case, not the layer back. Each removal is tied to a named card so the reasoning is recoverable |
| The merge-turn guard is too strict and blocks ordinary parallel work | Medium | Two children touching the same file cannot both merge | The guard compares against `origin/main`, not against sibling children; a sibling conflict stays an ordinary merge conflict the merging worker resolves |
| The record's `units` rows grow a de-facto schema nothing checks | Medium | A later reader trusts a key orchestrate stopped writing | U1 documents the added keys in `plugins/saga/references/run-record.md` in the same pull request, beside the keys the record already documents |
| Two `go` processes race at the same instant | Low | Two worktrees, two sessions, one unit | Named in KTD2 rather than hidden. The harm — two sessions in one worktree — is impossible after KTD3 |
| The rewrite loses a behaviour the 17,953 lines of existing tests covered | High | A test module is deleted with its subsystem and takes a live assertion with it | Each new test module names the module whose assertions it takes over; U8 is the only unit that deletes a test file, and it deletes a module only after every assertion in it is carried forward or belongs to a subsystem this card removes |

## Operator question

<!-- gate-record: id=orchestrate-1025-board-writeback absence=HALT transport=ask-user-question -->

**Does the board-writeback path stay in orchestrate for this release?**

The card names "the receipt and writeback records" for removal, and this plan removes exactly those:
`record_writeback_outcome`, the persisted `writeback_failed` map, and the outstanding-writeback report.
It does **not** remove the writeback path itself — roughly 1,000 lines spanning `announce_units`, the
board vocabulary resolver, the reconcile-controller shell-out, and the `announce` subcommand — because
the card does not name it and the instruction binding this work is that nothing unnamed is deleted.

The simplification review's recommendation R19 moves the six board moves into saga, and the card that
implements R19 is issue 1028 ("integrate, release, functional test, close"), which depends on this one.
If the operator wants the writeback path to leave orchestrate in the same release, it belongs in this
card's removal inventory; if it should leave with issue 1028, it stays here untouched and this plan is
already correct.

**On silence this halts** rather than choosing: removing it without a decision deletes a working path
the card does not name, and keeping it without a decision may leave two writers for one board move.
The plan as written takes the keep-it reading, so the work can proceed while the question is open, and
the answer changes only U8's inventory.

## Success signals

- `uv run python plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py --help` lists no
  `redrive`, `collect`, or `land`, and does list `plan-check`, `start`, `go`, `merge`, `clean`.
- `grep -c -E "reserved_landing_paths|launch_reservation|record_writeback_outcome"` over the driver
  prints 0.
- `uv run pytest tests/test_orchestrate*.py -q` passes with the new modules present.
- Two issues are started in one temporary repository at once and each has its own record.
- The full gate is green at the release commit, and the orchestrate manifest, the marketplace entry,
  and the changelog all read 5.0.0.
