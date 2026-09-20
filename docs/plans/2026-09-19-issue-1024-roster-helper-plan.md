---
title: "Roster helper: stand up and tear down role sessions in herdr"
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Roster helper: stand up and tear down role sessions in herdr

## Source and descent

This plan implements GitHub issue 1024 in `infiquetra/infiquetra-claude-plugins`, a child of the
saga-simplification parent, issue 1018. Its shape is fixed by section A6 of
`docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md` and by recommendation R13 of
`docs/analysis/2026-09-19-saga-simplification-review.md`. The bounded wait that card 891 asked for
lands here. The three cards this one depends on — issues 1021, 1022, and 1023 — are already merged
onto the integration branch this work builds from.

## Summary

One new script, `plugins/agent-launcher/skills/agent-launcher/scripts/roster.py`, reads an issue's
run record, creates one named herdr terminal pane per staffed role, prompts each pane from the roles
library, waits for each pane to settle within a caller timeout, and later closes exactly the panes
it recorded creating — and nothing else.

It creates nothing by hand: every pane is created through the existing verified launcher
(`launcher.py launch`), which already owns the pane-write rule, the ownership receipt, and the
close path. The helper's own contribution is the mapping from a staffing plan to a set of role
sessions, the record of what it created, and the refusal to close anything that record does not
name.

## Problem Frame

Today the coordinator prompt in the `infiquetra-agent-operations` repository
(`docs/operations/single-issue-delivery.md`) tells a person, in prose, to open one terminal session
per software-lifecycle role and brief each one. The live evidence captured on 2026-09-19
(`docs/analysis/2026-09-19-saga-simplification-inputs/herdr-live-evidence.md`) shows the result: 26
agent panes across seven agent kinds, with role-shaped titles, stood up and torn down by hand.

Three pieces that would make that mechanical have landed on this branch in the three sibling cards
this one depends on:

- Issue 1021 put a staffing resolver in `plugins/fleet-core/scripts/fleet_commons/staffing.py`: it
  answers "for this role, which vendor, which model, which effort".
- Issue 1022 put a prompt per role in `plugins/agent-launcher/roles/`: fifteen files plus an
  `index.json` that says how to slice the Lens Reviewer file per lens.
- Issue 1023 put one JSON run record per issue in `plugins/saga/scripts/run_record.py`, with a
  `roster` array reserved for exactly this purpose and a `run_configuration` block whose first
  parameter is the staffing plan.

What is missing is the piece that reads the staffing plan, creates the panes, and — the part that
actually needs a guard — takes them down again without touching the operator's other work. That is
this card.

## Requirements

**R1.** `roster.py up --record <path>` reads an issue's run record and creates one named herdr pane
per role named in `run_configuration.staffing_models_and_efforts`, using that entry's vendor, model,
and effort.

**R2.** `roster.py up --record <path> --dry-run` creates nothing and prints, for every role it would
staff: the pane name, the agent kind, the model, the effort, and the prompt text it would send.

**R3.** Every pane the helper creates is recorded in the run record's `roster` array before the
helper does anything else with it, with the pane identifier, the tab identifier, the agent name, and
the absolute path of the launcher receipt that proves ownership.

**R4.** `roster.py down --record <path>` closes exactly the panes the `roster` array records this
helper as having created, and refuses to issue a close for any other pane — including a live pane
whose role name matches, and including a recorded entry whose ownership receipt is missing or does
not prove ownership.

**R5.** Each role's prompt comes from the roles library. The Lens Reviewer's per-lens section is cut
using the slicing rule published in `plugins/agent-launcher/roles/index.json`, never a second copy
of that rule.

**R6.** `roster.py wait --record <path>` waits for each recorded pane to reach a settled state using
herdr's own settled-state default set, always under a caller-supplied timeout, and never waits
indefinitely.

**R7.** A role whose agent reports `blocked` is reported — role, pane identifier, and the tail of
that pane's output — and never answered, unblocked, or prompted again by the helper.

**R8.** Every subcommand refuses to run outside a herdr pane, with one line on standard error and a
named non-zero exit code.

**R9.** A role named in the staffing plan that cannot be resolved to both a staffing row and a roles
library prompt is a refusal that names the role, not a silently skipped pane.

**R10.** `tests/test_roster.py` exercises R1 through R9 and R12 through R14 against an injected fake
command runner; no test in that file reaches a live herdr server, creates a pane, or closes one.

**R11.** The helper never creates a git worktree, never writes any run-record block other than
`roster`, and never exceeds the pane count that `run_configuration.concurrency_allocation` allows.
A staffing plan asking for more panes than that allocation is a refusal naming both numbers, not a
partial roster: a role session is long-lived, so there is no later turn in which the remaining
roles would be started.

**R12.** `up` is idempotent per role. A role already recorded in `roster` with a state other than
`closed` is skipped with a printed reason, so re-running `up` after an interrupted run repairs the
roster instead of doubling it.

**R13.** A launch whose prompt was not delivered — the launcher's staged-input stop, which records
`prompt_delivered: false` — is recorded with state `created` rather than `prompted`, reported, and
left alone. The helper never retries a prompt; `launcher.py redeliver` is an operator action taken
after the composer is cleared by hand.

**R14.** The helper refuses to close the pane it is itself running in, whatever the run record says:
a roster row whose `pane_id` equals the session's own `HERDR_PANE_ID` is a refusal.

**R15.** The release surfaces tell the same story as the change: `agent-launcher` and `saga` version
bumps, both changelogs, the marketplace registry, and the packaged-file assertion in
`tests/test_agent_launcher_plugin.py`.

## Key Technical Decisions

**KTD1. Panes are created through `launcher.py`, not through raw `herdr` calls.** The launcher at
`plugins/agent-launcher/skills/agent-launcher/scripts/launcher.py:354` already owns everything the
dangerous half of this card needs: a single door for pane writes (`PaneWriter`), a staged-input stop,
a launch receipt whose `owned` field is computed from a pre-launch tab snapshot, and a `close`
subcommand that refuses a receipt which does not prove ownership. Re-implementing pane creation with
`herdr tab create` plus `herdr agent start` would put a second, weaker copy of the ownership rule in
the repository, and the agent-launcher skill file states that rule is owned in one place
(`docs/engineering-journal/DECISIONS.md` `{#907-pane-writer-owns-the-write-rule}`). Rejected
alternative: direct `herdr` calls, which would be shorter to write and would lose the ownership
proof that R4 is built on.

**KTD2. The staffing role key and the roles library role identifier are different vocabularies, and
the mapping between them is an explicit table in `roster.py` guarded by a drift test.** The staffing
registry names seven roles in kebab case (`planner`, `plan-reviewer`, `worker`, `lens-reviewer`,
`functional-tester`, `release-worker`, `merging-worker`, from
`plugins/fleet-core/scripts/fleet_commons/staffing.json`). The roles library names fifteen roles by
a snake-case `role_id` (`planner`, `plan_reviewer`, `implementer`, `lens_reviewer`, and so on, from
`plugins/agent-launcher/roles/index.json`). They are not the same set and not the same spelling:
`worker` on one side is `implementer` on the other, and `merging-worker` has no prompt at all. The
mapping lives in `roster.py` as one named constant, and a test asserts every key resolves against
the live staffing registry and every value resolves against the live roles index, so a change on
either side fails the suite rather than silently producing a pane with no briefing. Rejected
alternative: adding a `staffing_role` key to `roles/index.json`, which would change the
`roles_index.v1` schema that issue 1022 just shipped and that `tests/test_roles_library.py` guards.

**KTD3. `merging-worker` is a refusal, not a guess.** The staffing registry has a row for it; the
roles library has no prompt for it, because the software-lifecycle role catalogue does not name it.
When a staffing plan asks for it, the helper stops and says so (R9). Inventing a briefing for a role
the lifecycle does not define is exactly the drift the roles library README forbids.

**KTD4. The prompt sent to a session is a short dispatch brief naming the role file by absolute
path, not the role file pasted into the composer.** A Lens Reviewer prompt is 15 KB; pasting that
into a terminal composer is the single riskiest write this helper performs, and the launcher's own
staged-input machinery exists because composer writes go wrong. Every agent kind the launcher can
start reads files. The brief carries the issue number, the absolute run-record path, the absolute
role-file path, the lens when there is one, and the instruction to read the role file first. The
role file is still the whole briefing; it simply arrives by path. Rejected alternative: inlining the
file, which the card's dry-run acceptance criterion would also satisfy, and which would put a
15 KB write through a composer on every launch.

**KTD5. The wait is `herdr agent wait` per pane, and the multi-pane event stream stays where it
already is.** `herdr agent wait <target> --timeout <ms>` matches idle, done, or blocked by default —
which is exactly the settled-state set R6 asks for — and it is a command, so the injected fake runner
in the tests covers it with no socket. A socket-level `events.subscribe` client already exists at
`plugins/orchestrate/skills/orchestrate/scripts/herdr_events.py:83` and belongs to the orchestrate
plugin; copying it into agent-launcher would create the second implementation this repository keeps
paying for. Card 891's requirement — a bounded wait on herdr's own agent state rather than a
hand-rolled polling sentinel — is met by the command path. Rejected alternative: a socket
subscription in `roster.py`, which would need a live socket or a socket fake in the tests and would
duplicate a working module.

**KTD6. Exit codes extend the run record's table rather than inventing a parallel one.**
`run_record.py` already publishes 0 success, 1 internal error, 2 refusal, 3 unknown record version
(`plugins/saga/references/run-record.md`). `roster.py` reuses all four — a record it cannot read
exits with the same code whichever script read it — and adds two: **4** for "not inside a herdr
pane" (R8) and **5** for "a role is blocked, or its wait timed out" (R6, R7). Rejected alternative:
reusing 2 for the outside-a-pane refusal, which would make the card's most important precondition
indistinguishable from a bad command line.

**KTD7. The injected runner has the launcher's `run` signature.** `roster.py` takes a callable of
the shape `(cmd: list[str], *, check: bool, timeout: float | None) -> CompletedProcess[str]`,
defaulting to a real subprocess call. That is the signature at `launcher.py:354`, so the fake in
`tests/test_roster.py` is one object that intercepts both the `launcher.py` invocations and the
`herdr` invocations, and the test file never needs a monkeypatch of `subprocess.run`.

**KTD8. A run record is read and written through `run_record.py`, never as raw JSON.** That module
preserves unknown top-level fields, warns about them by name, resolves the store root from the git
common directory so a worktree can reach the primary checkout's store, and writes atomically. The
helper touches only the `roster` array.

**KTD9. The launch receipts live beside the run record, not in the worktree.** `down` proves
ownership from the receipt the launcher wrote at `up` time, so if that file disappears between the
two calls the helper can no longer close what it created — and the panes leak. A receipt written
into a unit's worktree disappears the moment that worktree is removed, which is exactly what issue
1025's driver does at the end of a unit. The receipts therefore go to
`<run-record store root>/receipts/issue-<N>/<agent-name>.json`, derived from the record's own path,
which is the one location outside every worktree that the run record has already established as
reachable. Rejected alternative: a receipt beside the plan or in a temporary directory, both of
which outlive the launch by less than the roster does.

**KTD10. `--record` takes the record file's absolute path, and the issue number and store root are
derived from it.** The card's acceptance criterion is written as `--record <path>`, while
`run_record.py`'s own interface is a store root plus an issue number
(`record_path(store_root, issue)` at `plugins/saga/scripts/run_record.py:202`). Rather than pick
one and break the other, `roster.py` accepts `--record <absolute path>` — taking the store root as
the file's parent directory and the issue number from the `issue-<N>.json` stem, then loading
through `run_record.load` so the version check, the unknown-field warning, and the atomic write all
still apply — and additionally accepts `--issue <N>`, which resolves the store root through
`run_record.resolve_store_root()` the way every other saga consumer does. Passing both, or neither,
is a usage refusal.

## High-Level Technical Design

### What the helper reads from the run record

| Record path | Used for |
|---|---|
| `issue` | the pane name prefix and the dispatch brief |
| `repo` | the dispatch brief |
| `run_configuration.staffing_models_and_efforts.value` | the roles to staff, each with `vendor`, `model`, `effort` |
| `run_configuration.applicable_lenses.value` | one Lens Reviewer pane per applicable lens |
| `run_configuration.concurrency_allocation.value` | the ceiling on panes created in one `up` |

### What the helper writes to the run record

Only `roster`, as a list of entries of this shape:

```json
{
  "schema": "roster_entry.v1",
  "role": "plan-reviewer",
  "role_id": "plan_reviewer",
  "lens": null,
  "prompt_file": "plan-reviewer.md",
  "vendor": "claude",
  "model": "opus",
  "effort": "high",
  "agent_name": "issue-1024-plan-reviewer",
  "pane_id": "w7C:p2P",
  "tab_id": "w7C:t2G",
  "workspace_id": "w7C",
  "receipt_path": "/abs/path/.claude/saga/runs/receipts/issue-1024/issue-1024-plan-reviewer.json",
  "created_by": "roster.py",
  "created_at": "2026-09-19T00:00:00Z",
  "state": "created",
  "closed_at": null
}
```

`state` moves through `created`, `prompted`, `settled`, `blocked`, and `closed`. `down` acts only on
entries whose `created_by` is `roster.py`, whose `receipt_path` exists, and whose `state` is not
already `closed`.

### The herdr surface the helper depends on

Read live from `herdr 0.9.0` on 2026-09-19, not from memory:

| Command | Shape the helper relies on |
|---|---|
| `herdr agent list` | `{"id": ..., "result": {"agents": [...]}}`; each row carries `agent`, `agent_status`, `pane_id`, `tab_id`, `workspace_id`, `name`, `terminal_title` |
| `herdr agent wait <target> [--until <state>] [--timeout <ms>]` | without `--until` it matches `idle`, `done`, or `blocked`; without `--timeout` it waits forever, so the helper always passes one |
| `herdr agent get <target>` | one agent row, used to read `agent_status` after a wait returns |
| `herdr agent read <target> --source recent --lines <n>` | the output tail quoted when a role is reported blocked |
| `herdr pane close <pane_id>` | reached only through `launcher.py close`, never called directly by the helper |

Two facts worth writing down because they shape the code: there is no `herdr agent close`
subcommand — closing is a pane or tab operation — and `herdr agent prompt` rejects a submission to
an already-blocked agent with `agent_blocked` before sending any input, which is the behavior R7
depends on.

### How a pane is named, and why it matters

A pane name is `issue-<N>-<role>` for a single-seat role, and `issue-<N>-lens-<lens id>` for a Lens
Reviewer, because a run applies several lenses and every one of them is the same role. The
distinction is not cosmetic. The agent-launcher skill states that when the requested tab label
already exists in the workspace, the wrapper splits a new pane inside that existing tab instead of
creating a tab — so two seats asking for the same name would silently land in one tab rather than
failing. The helper therefore builds a name that is unique per seat, and refuses before any launch
when two seats in one staffing plan would resolve to the same name.

### Being inside a pane

The session's environment carries `HERDR_ENV=1`, `HERDR_PANE_ID`, `HERDR_TAB_ID`,
`HERDR_WORKSPACE_ID`, `HERDR_SOCKET_PATH`, and `HERDR_BIN_PATH`. The precondition is `HERDR_ENV=1`
and a non-empty `HERDR_PANE_ID` — the card's own verification line tests the first, and the second is
what makes the pane identifiable. Failing it prints one line and exits 4.

## Implementation Units

### U1. The module, the record read, the role resolution, and the in-pane precondition

**Summary:** the skeleton every other unit hangs on — read the record, resolve each staffed role to a
vendor, a model, an effort, and a prompt file, and refuse early when the preconditions do not hold.

**Files:** `plugins/agent-launcher/skills/agent-launcher/scripts/roster.py` (new).

**Scope:** the command-line surface (`up`, `wait`, `down`, with `--record`, `--issue`, `--dry-run`,
`--timeout`), the record resolution from KTD10, the exit-code table from KTD6, the in-pane precondition from R8, the staffing-to-roles
mapping constant from KTD2, the Lens Reviewer slice driven by `index.json`, and the dispatch-brief
composer from KTD4. No pane is created in this unit; `--dry-run` is the only path that produces
output.

**Test scenarios** (`tests/test_roster.py`):

- A two-role staffing plan renders a dry run naming both panes, their kinds, their models, their
  efforts, and their prompts; nothing is passed to the runner.
- Running any subcommand with `HERDR_ENV` unset prints one line and exits 4.
- A staffing plan naming `merging-worker` exits with a refusal naming that role (KTD3).
- A record whose `schema` is not `run_record.v1` exits 3, with no traceback.
- `--record` and `--issue` passed together, and neither passed, are both usage refusals (KTD10); a
  `--record` path resolves to the same record `--issue` resolves to through the store root.
- The mapping constant's keys all resolve in the live staffing registry and its values all resolve in
  the live roles index (the drift guard for KTD2).
- A Lens Reviewer entry for lens `security` composes a brief carrying that lens, and the slice is
  taken with the rule from `index.json`, not a literal in the test.
- A plan applying three lenses yields three distinct pane names, and a staffing plan whose seats
  would collide on one name is refused before any launch.

### U2. `up` creates panes through the launcher and records what it created

**Summary:** one pane per staffed role, created through `launcher.py launch`, recorded in the run
record's `roster` array before anything else happens to it.

**Files:** `roster.py`.

**Scope:** for each resolved role, invoke `launcher.py launch --vendor <vendor> --task <pane name>
--cwd <repo root> --model <model> --effort <effort> --prompt <brief>` through the injected runner, parse the receipt, write the receipt to the run record's receipt directory, and
append the `roster_entry.v1` row. The pane count is capped at `concurrency_allocation`. A launch that
fails leaves the earlier rows recorded and stops, so a later `down` can still clean up what did get
created.

**Test scenarios:**

- Two roles produce two launcher invocations carrying the staffing plan's vendor, model, and effort,
  and two roster rows with the pane and tab identifiers from the fake receipts.
- The roster rows are written before the wait or any second launcher call, proved by the fake
  runner's call order.
- A staffing plan with five roles and a concurrency allocation of two refuses naming both numbers,
  rather than creating five panes or a partial roster (R11).
- A launcher invocation that exits non-zero leaves the already-created rows in the record and returns
  a non-zero exit.
- Running `up` twice against the same record produces two launcher invocations in total, not four:
  the second run skips both roles with a printed reason (R12).
- A launcher receipt carrying `prompt_delivered: false` records the row with state `created`, reports
  the stop, and issues no retry, no second launch, and no `redeliver` (R13).
- The receipt path recorded on each row sits under the run record's store root, not inside the
  working directory the launch ran in (KTD9).

### U3. The bounded wait, the read, and the blocked report

**Summary:** wait for each recorded pane to settle under a caller timeout; report a blocked role
rather than answering it.

**Files:** `roster.py`.

**Scope:** `roster.py wait --record <path> --timeout <ms>` issues `herdr agent wait <agent_name>
--timeout <ms>` per recorded pane with no `--until` flag, so herdr's own settled-state default set
applies (KTD5). After each wait returns, `herdr agent get` reads the state: `idle` or `done` sets the
row to `settled`; `blocked` sets the row to `blocked`, quotes the tail from `herdr agent read
--source recent`, and exits 5. A wait that times out also exits 5 and names the role.

**Test scenarios:**

- Every wait invocation the fake runner sees carries a `--timeout` and no `--until`.
- A role whose fake state is `blocked` is reported with its role name, pane identifier, and output
  tail, the run record row reads `blocked`, and no prompt or key-send is issued for that pane.
- A wait the fake reports as timed out exits 5 naming the role, and leaves the other roles' rows
  untouched.
- Two settled roles set both rows to `settled` and exit 0.

### U4. `down` closes only what the record says this helper created

**Summary:** the guard the card is really about.

**Files:** `roster.py`.

**Scope:** `roster.py down --record <path>` iterates the `roster` array, and for each row whose
`created_by` is `roster.py`, whose `receipt_path` exists, and whose `state` is not `closed`, invokes
`launcher.py close --receipt-json <receipt_path>` and sets the row to `closed`. Every other row is
skipped with a printed reason. No pane identifier from `herdr agent list` is ever the input to a
close; the record is.

**Test scenarios:**

- Two recorded rows produce exactly two close invocations, each carrying its own recorded receipt
  path.
- A live agent list holding eight panes, two of them the recorded ones, still produces exactly two
  close invocations; the argument of every close invocation is a recorded receipt path.
- A row whose `receipt_path` does not exist is skipped with a named reason and produces no close
  invocation.
- A row already marked `closed` produces no second close invocation.
- A record with an empty `roster` array closes nothing and exits 0.
- A roster row whose `pane_id` equals the session's own `HERDR_PANE_ID` is refused, and no close is
  issued for it (R14) — the helper cannot close the pane it is running in.
- A negative-control assertion: across the whole test module, no invocation the fake runner receives
  is a bare `herdr pane close` or `herdr tab close`.

### U5. The skill files and the release surfaces

**Summary:** say where the helper lives and what it is for, in the three skill files that will call
it, and bump the two plugins that changed.

**Files:** `plugins/agent-launcher/skills/agent-launcher/SKILL.md`,
`plugins/saga/skills/work/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md`,
`plugins/agent-launcher/.claude-plugin/plugin.json` (1.6.0 to 1.7.0),
`plugins/agent-launcher/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json` (0.163.0 to
0.164.0), `plugins/saga/CHANGELOG.md`, `.claude-plugin/marketplace.json`,
`tests/test_agent_launcher_plugin.py`.

**Scope:** the agent-launcher skill gains a short section naming `roster.py`, its three subcommands,
its exit codes, and the rule that it is the only path from a staffing plan to a set of role sessions.
The two saga skills gain a short pointer, deliberately thin: issue 1030's code-review rewrite and the
build-loop card rewrite both of these files, so a long section here would be written to be deleted.
The packaged-file assertion in `tests/test_agent_launcher_plugin.py` gains the new script path.

**Test scenarios:**

- `tests/test_agent_launcher_plugin.py` asserts `skills/agent-launcher/scripts/roster.py` is present.
- The release-surface parity and triad tests pass with both version bumps and both changelog entries.

## The card's acceptance criteria, mapped

Each of issue 1024's three acceptance criteria, the unit that satisfies it, and the command that
proves it.

| Card acceptance criterion | Unit | Proving command |
|---|---|---|
| `roster.py up --record <path> --dry-run` prints the panes, kinds, models, and prompts it would create | U1 | `uv run python plugins/agent-launcher/skills/agent-launcher/scripts/roster.py up --record <path> --dry-run` |
| Inside a herdr pane, `up` for a two-role plan creates two named panes visible in `herdr agent list`, and `down` removes exactly those two | U2, U4 | the live check in the test strategy below, run once |
| `uv run pytest tests/test_roster.py -q` passes | U1 through U4 | `uv run pytest tests/test_roster.py -q` |

## Verification

```bash
# the fake-runner suite, and the two sibling suites this card must not break
uv run pytest tests/test_roster.py tests/test_agent_launcher_plugin.py tests/test_roles_library.py -q

# the dry run, which creates nothing
uv run python plugins/agent-launcher/skills/agent-launcher/scripts/roster.py \
  up --record "$(uv run python plugins/saga/scripts/run_record.py path 1024)" --dry-run

# the release surfaces
uv run pytest tests/test_release_surface_parity.py tests/test_release_triad.py -q

# lint and types, at the scope CI uses
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

## Test strategy

Every test in `tests/test_roster.py` runs against an injected fake command runner. Nothing in that
file starts a herdr server, creates a pane, closes a pane, or reads the operator's live agent list.
The fake records every invocation it is handed and returns canned receipts and canned agent rows, so
the assertions are about the argument vectors the helper produced, which is where the guards actually
live.

The one live check belongs to the work stage, is run **once**, and only after the fake-runner tests
pass:

1. Read the live agent count first: `herdr agent list | jq '.result.agents | length'`.
2. Run `roster.py up` for a two-role plan whose pane names are prefixed `issue-1024-acceptance-`.
3. Confirm those two names, and only those two, are new in `herdr agent list`.
4. Run `roster.py down --record <path>` and confirm the count returns to its starting value.

No close is ever issued for a pane the helper did not create, in the test suite or in the live check.
The operator's 24 other live agent panes are the reason the guard in U4 is written as a
negative-control assertion and not only as a positive one.

## Scope Boundaries

**Out of scope, as the card states:**

- No git worktree creation. Issue 1025's slim orchestrate driver does that per unit.
- No closing of a pane the helper did not create, under any flag or option.
- No control of a herdr session from outside a herdr pane.

**Out of scope, decided here:**

- No socket-level event subscription in this plugin (KTD5); the existing one in orchestrate stays.
- No write to any run-record block other than `roster`.
- No change to the `roles_index.v1` schema or to any roles library prompt (KTD2).
- No new role, and no invented briefing for `merging-worker` (KTD3).

**Deferred to follow-up work:**

- A crew-shaped `up` that creates a whole workspace through `agent-herdr crew` in one call. The card
  names it as an option; one pane per role through the verified launcher is the shape that carries an
  ownership receipt per pane, which R4 needs, so the crew path is not built here.
- Re-prompting a settled role for a second cycle. The build loop and the code-review cards own the
  cycle; this helper stands sessions up, waits, and takes them down.

## Questions answered from the card

<!-- gate-exempt: this section records decisions taken from the card, the lifecycle documents, and the code during planning; it is not a gate site and opens no operator prompt. -->

The operator-question widget was unavailable in this session, so each question the plan skill would
have asked was answered from the card, the objective plan, the sibling code on this branch, or the
documented default, and every one is recorded here.

| Question | Answer | Where the answer came from |
|---|---|---|
| Routing destination | `pr` | the structured pre-answer carrier, validated clean by `plan_pre_answers.py`, caller `improve-claude-plugins run driver` |
| Execution backend | `inline` | the same carrier. The recommender returned `team-execution` for this file count; the carrier's `inline` stands, and the divergence is recorded rather than hidden — `team-execution` is being archived by the removals card, so routing this work through it would be routing it through a plugin that will not exist at release |
| Scope class | Standard | five units, one new script, no cross-repository surface |
| Is a plan document warranted | Yes | eight load-bearing technical decisions, two vocabularies to reconcile, and a destructive operation (closing panes) that needs its guard written down |
| Which exit code for refusing outside a pane | 4 | KTD6; 2 and 3 are already spoken for by the run record's table |
| Create panes directly or through the launcher | Through `launcher.py` | KTD1; the ownership receipt R4 depends on exists only there |
| Wait by command or by socket subscription | By `herdr agent wait` | KTD5; a working socket client already exists in the orchestrate plugin |
| Paste the role prompt or point at it | Point at it, by absolute path | KTD4 |
| What to do about `merging-worker` | Refuse, naming the role | KTD3 |
| Where the staffing-to-roles mapping lives | A constant in `roster.py` with a drift test | KTD2; the alternative changes a schema issue 1022 just shipped |

**Not answered here, and not invented.** The plan skill's board move — setting the card's Stage and
Status fields through Mission Control — was not submitted. This driver's stage is plan and document
review inside its own worktree; a write to the operator's live project board is the coordinator's to
make for the whole parent, and guessing at it from a card driver is a process-authority decision, not
a default. It is reported back to the coordinator rather than taken.

## Risk Analysis and Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| The helper closes a pane belonging to the operator's other work | low, high impact | `down` reads only the run record; `launcher.py close` independently refuses a receipt that does not prove ownership; a negative-control test asserts no bare pane or tab close is ever issued |
| A staffing plan names a role with no prompt and the helper creates a briefingless session | medium | R9 makes it a refusal, and the KTD2 drift test fails the suite when either vocabulary moves |
| The wait hangs forever | medium | R6 always passes `--timeout`; herdr's own documentation states an absent timeout waits indefinitely |
| A blocked role is "helped" by an automated answer | low, high impact | R7; the helper has no prompt or key-send path after launch at all |
| A re-run of `up` after an interruption doubles the panes | medium | R12 makes `up` idempotent per role, with a test that two runs produce two launches, not four |
| A receipt is lost with its worktree and `down` can no longer prove ownership, leaking panes | medium | KTD9 puts receipts under the run-record store root, outside every worktree |
| The helper closes the coordinator's own pane and ends the run | low, high impact | R14 refuses a row whose pane identifier is the session's own |
| The live acceptance check leaks panes | low | the panes carry an `issue-1024-acceptance-` prefix, the count is read before and after, and the check runs once after the fake-runner tests pass |

## Risk tier

Medium. The helper creates and closes terminal panes on the operator's running server, alongside 24
live agent panes that belong to other work. The guards are the record of what it created, the
ownership receipt the launcher computes, and the rule that nothing else is ever closed.
