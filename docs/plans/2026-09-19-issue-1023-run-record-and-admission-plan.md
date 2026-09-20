---
title: Issue 1023 — the saga run record and the admission questionnaire
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Issue 1023 — the saga run record and the admission questionnaire

## Summary

Saga keeps the state of a piece of work in six separate append-only stores. This plan replaces them
with one JSON file per issue — the run record — kept in the primary checkout's git-ignored
`.claude/saga/` store and referred to by absolute path, plus an admission step that fills every
answer it can from a repository profile and the staffing component and asks the operator once for
the rest.

Two things make this card the one every later child of the parent waits on: the schema is a written
contract before any consumer exists, and the file has to be readable from a worktree, which is where
the work actually happens.

## Problem frame

The software development lifecycle repository (hereafter "the lifecycle repository",
`infiquetra/infiquetra-sdlc`, pinned at revision `5efc869f` for this whole parent) already says what
has to be settled before a run starts: the card contract, the Risk tier, the seven approval
boundaries, the six issue-review checks, and thirteen run-configuration parameters. Nothing in the
plugins implements any of it. The operator answers those questions by hand, in prose, in a
coordinator prompt, every time.

Meanwhile saga stores run state in six places, none of which is the set of answers above:

| Store | File | Lines | What it holds |
|---|---|---|---|
| Run-fact ledger | `plugins/saga/scripts/run_ledger.py` | 416 | hash-chained telemetry records (`run_fact.v1`) |
| Evidence-custody ledger | `plugins/saga/scripts/evidence_ledger.py` | 704 | content-addressed custody log for verification evidence |
| Dispatch-settlement ledger | `plugins/saga/scripts/dispatch_settlement.py` | 2,066 | dispatch manifests, settlements, casualty reports |
| Effort ledger | `plugins/saga/scripts/effort_ledger.py` | 263 | per-unit planned-versus-actual effort escrow |
| Envelope tokens | `plugins/saga/scripts/envelope_token.py` | 825 | revocable merge-authorization credentials |
| Ship receipts | `plugins/saga/scripts/ship_receipt.py` | 291 | what the ship ceremony opened and closed |

That is 4,565 lines of storage for state that one file can hold, and none of those six files can
answer "what is the next step for issue 1023?".

There is a third problem, and it is the one that makes the store location a design decision rather
than a detail. Issue 886's fifth finding: the orchestrate plugin's `.orchestrate/` directory is
git-excluded, so it does not exist inside a unit's worktree, and a review session told to read a
repository-relative path there found nothing. Saga's `.claude/saga/` store has exactly the same
shape — `.gitignore:56` excludes `.claude/`, and `plugins/saga/scripts/saga.py:45` sets
`STATE_DIR = Path(".claude/saga")`, a relative path resolved against whatever directory the process
runs in. A worker in a worktree resolving that relative path gets an empty directory in its own
worktree, not the primary checkout's store.

## Requirements

**R1.** One JSON file per issue holds the whole state of that issue's run: the admission answers,
the thirteen run-configuration parameters, the roster with its pane identifiers, the units with
their worktree, branch and merge-turn state, the review results by cycle, and `next_step`.

**R2.** The file lives in the primary checkout's git-ignored `.claude/saga/` store and is addressed
by an absolute path, so a process running in any linked worktree reads and writes the same file as
a process running in the primary checkout.

**R3.** The record carries a version token in a named top-level field. Reading a record whose
version this saga does not know prints one line to standard error and exits 3 — never a Python
traceback. (Issue 975, finding F124: an unknown run-file contract in the orchestrate plugin printed
a six-frame traceback where every other refusal in the same file printed one line.)

**R4.** An unknown top-level field survives a read-and-write round trip unchanged, and is reported
by name on read. (Issue 989, finding F138: an unknown top-level key in the orchestrate run file was
dropped silently and destroyed on the next save, while an unknown unit-row key in the same file was
warned about by name.)

**R5.** The schema is a written reference document, `plugins/saga/references/run-record.md`, and a
test proves the document and the code agree, before any consumer of the record lands.

**R6.** An admission step runs the card validator against the issue. A card that fails stops the
step, names the missing fields, and writes no record.

**R7.** Admission fills every defaultable run-configuration parameter from a per-repository profile,
the lifecycle repository's decided defaults, and the staffing component from issue 1021, without
asking a question.

**R8.** Admission asks the operator, in one message, exactly for the answers that are not
defaultable: the Risk tier with its justification, the seven approval-boundary scopes, the
destination, staffing overrides, the lens declaration, the repair allowances, the response to
unfinished functional testing, whether the repository has a branch preview deployment, whether the
`main` branch is consumed directly, and whether the change is code, docs, or mixed.

**R9.** An answer already in the record is never asked again. `admission.py --issue N --dry-run`
prints the questions it would ask and the defaults it filled, and writes nothing.

**R10.** `run_record.py show <issue>` prints the record including `next_step`.

**R11.** The state engine `plugins/saga/scripts/saga.py` reads and writes the run record's
`next_step` alongside its own envelope, so the two never disagree about where the run is.

**R12.** Both spore hooks — `plugins/saga/hooks/precompact_spore_hook.py` and
`plugins/saga/hooks/compact_spore_session_hook.py` — freeze the run record at the compaction
boundary and re-inject it afterwards, and `next_step` is identical on both sides of that boundary.

**R13.** Nothing this card ships creates or modifies a file in the primary checkout's
`.claude/saga/` store during a test run. Every test resolves the store to a directory under
pytest's `tmp_path`.

**R14.** The plan names, for each of the six stores in the problem frame, whether this card replaces
it now or whether it stays until the removals child (issue 1030) deletes it.

**R15.** Release surfaces move with the change in the same pull request: the saga plugin's
`plugin.json` version, the marketplace registry entry, and the saga changelog.

## Key Technical Decisions

**KTD1 — the store root is the git common directory's parent, resolved at every call, never a
relative path.** `git rev-parse --git-common-dir`, resolved to an absolute path, returns
`<primary>/.git` from the primary checkout and the same `<primary>/.git` from every linked
worktree — that is the whole mechanism, and it is the call `resolve_common_dir` already makes. The
primary checkout root is that directory's parent, and the store is `<primary>/.claude/saga/`. The
repository already owns this mechanism: `plugins/saga/scripts/outcome_store.py:95`
`resolve_common_dir` does exactly this call, and the spore already keys its files off it
(`<git-common-dir>/saga-spores/`, DECISIONS at `docs/engineering-journal/DECISIONS.md:8831`). The
run record reuses `resolve_common_dir` rather than re-deriving it.

*Rejected:* keeping `STATE_DIR = Path(".claude/saga")` relative and asking callers to pass the right
working directory. That is the arrangement issue 886's fifth finding describes failing, and it fails
silently — the worktree read returns "no record", which is indistinguishable from "no run".

*Refusal, not a guess:* when the common directory is not named `.git` — a repository created with a
separate git directory, where the parent is not a checkout root — the module refuses with one line
naming the resolved common directory, rather than writing the record somewhere no reader will look.

**KTD2 — the version field is `schema`, its value is `run_record.v1`, and an unknown value exits 3
with one line.** This repository's machine-readable artifacts already carry their version in a
`schema` field holding a `<name>.v<N>` token: `plan_pre_answers.v1`
(`plugins/saga/scripts/plan_pre_answers.py`), `roles_index.v1` and `lifecycle_snapshot.v1`
(`plugins/agent-launcher/roles/index.json`, `lifecycle-snapshot.json`), `run_fact.v1`, and
`review_result.v2` in the simplification review. The record follows that convention rather than
saga.py's older `schema_version: "1.0"` float-shaped string, because the family token also names
*which* artifact the file is, which a bare version number does not.

The refusal text is one line, written to standard error, exit 3:

```
run_record: unknown record version 'run_record.v2' in /abs/path/.claude/saga/runs/issue-1023.json; this saga writes run_record.v1
```

The module raises a named exception; the command-line entry point is the only place that catches it,
prints the line, and returns 3. No command-line path calls a loader outside that catch — which is
the precise defect issue 975 reported (`main` called `args.func(args)` bare and every subcommand
opened with a load).

*Exit-code table, stated once:* 0 success; 1 an unexpected internal error; 2 a refusal that is not a
version mismatch (a card that fails the validator, an unresolvable store root, a malformed answers
file); 3 an unknown record version. Only 3 is pinned by the card; the rest are stated here so the
later children do not each invent one.

**KTD3 — unknown top-level fields are preserved in an `extra` mapping and reported by name on
read.** `plugins/saga/scripts/saga.py:261` already solves this problem for the saga envelope with an
`extra: dict[str, Any]` field that "preserves any unknown frontmatter keys read off disk so a
round-trip never drops a field a newer writer added". The run record uses the same shape. On read,
each unknown top-level key produces one warning line naming the key, the record path, and this
saga's version — which is the treatment issue 989 says the orchestrate run file already gave unknown
*unit-row* keys while dropping unknown *top-level* keys silently. Preserving without warning would
satisfy the letter of the acceptance criterion and leave the operator unable to tell a newer writer
from a typo.

**KTD4 — the thirteen run-configuration parameters are the run model's thirteen, not the run setup
contract's thirteen.** There are two sets of thirteen in the lifecycle repository at revision
`5efc869f` and they are different sets. The card's citation is `docs/lifecycle/run-model.md` lines
129 to 156, the "Run configuration — what is chosen before the work starts" table: nine chosen by
the Delivery Manager at orchestration setup and four by the Planner during planning. The other
thirteen are the `required_fields` of the `orchestrator-to-controller` contract, which is a handoff
*message* shape (it carries `roster_hash`, `executors_and_topology`, `session_reset_authority` —
none of which appear in the run model's table). The record's `run_configuration` block uses the run
model's set, with these keys:

| # | Key | Chosen by | Default source |
|---|---|---|---|
| 1 | `staffing_models_and_efforts` | Delivery Manager | staffing component (issue 1021) |
| 2 | `concurrency_allocation` | Delivery Manager | repository profile |
| 3 | `standard_cycle_allowance` | Delivery Manager | lifecycle default, 3 |
| 4 | `escalated_cycle_allowance` | Delivery Manager | lifecycle default, 2 |
| 5 | `escalation_trigger` | Delivery Manager | lifecycle default |
| 6 | `nonproduction_destination` | Delivery Manager | repository profile |
| 7 | `unfinished_testing_response` | Delivery Manager | asked (closed set of two) |
| 8 | `applicable_lenses` | Planner | asked, proposal from the lens catalogue |
| 9 | `per_lens_score_threshold` | Planner | lens catalogue strictness ladder |
| 10 | `mechanical_tool_baseline` | Planner | repository profile |
| 11 | `lens_execution_recovery` | Delivery Manager | lifecycle default |
| 12 | `repair_custody` | Delivery Manager | lifecycle default |
| 13 | `preflight_checks` | Planner | repository profile |

Each value is an object `{"value": …, "chosen_by": "delivery_manager"|"planner", "source":
"profile"|"staffing"|"lifecycle-default"|"operator"}`, so a later reader can tell an answer the
operator gave from one a default filled. The run setup contract's shape is what issue 1024's roster
helper and issue 1028's close step will *emit* from this block; it is not the block's own key set.

**KTD4a — the record's top-level key set, fixed here so no later child invents one.** Twelve keys,
in this order, and nothing else at the top level except an unknown key preserved under KTD3. (The
first draft of this plan said eleven because the table below put `created_at` and `updated_at` on
one row; the code writes twelve and the guard test pins twelve.)

| Key | Holds |
|---|---|
| `schema` | the version token, `run_record.v1` (KTD2) |
| `issue` | the issue number, an integer |
| `repo` | `owner/name` of the repository the issue belongs to |
| `created_at` | ISO-8601 timestamp in UTC, set once at the first write |
| `updated_at` | ISO-8601 timestamp in UTC, refreshed on every write |
| `admission` | the questionnaire: `card_validation`, `answers` (each with its question id, value, source and timestamp), `pending_questions`, and the answers R8 names that are not run-configuration parameters — the Risk tier with its justification, the branch-preview fact, whether `main` is consumed directly, and the code/docs/mixed shape |
| `run_configuration` | KTD4's thirteen parameters, each `{value, chosen_by, source}` |
| `approval_scope` | the seven categories of the lifecycle repository's escalations chapter, each with the scope the operator granted or `none` |
| `roster` | one entry per staffed role: role id, the pane identifier, and the session's state |
| `units` | one entry per work unit: unit id, worktree path, branch, merge-turn state, and the last mechanical-check result |
| `review_cycles` | one entry per cycle: cycle number, the result, and the findings reference |
| `next_step` | one string naming the step the run is at |

**Two things called "destination", kept apart.** R8's "destination" is saga's own four-value routing
intent — `plan-only`, `pr`, `merge`, `nonprod-deploy` — the enum at
`plugins/saga/scripts/saga.py:78`, and it lives in `admission.answers` as `destination`. KTD4's row 6
`nonproduction_destination` is the lifecycle repository's parameter for *which lower environment* a
run deploys to, and it lives in `run_configuration`. They are different questions with the same
English word, and conflating them is the easiest mistake in this schema.

A missing key on read is filled with its empty default rather than refused — absence is how a record
written before its consumer landed presents, and refusing it would make every later child's first
read fail on a record this card wrote.

**KTD4b — one writer at a time, atomic replace, no lock.** The record is written by
`_atomic_write`'s pattern — write a sibling temporary file, then `os.replace` — exactly as
`plugins/saga/scripts/saga.py:673` does. There is no lock, no lease and no reservation: the parent
issue 1018's non-goals forbid adding one, and its stop conditions say to stop and report if a child
needs one to pass its own tests. The run's shape is what makes that safe rather than lucky — one
coordinator owns a run record and the roles it dispatches report back to it, so simultaneous writers
are not the normal case. A reader that needs to know it has the newest copy re-reads; `updated_at`
is what it compares.

**KTD5 — the repository profile is a tracked file at the repository root,
`.saga-profile.json`.** The existing per-repository tier overlay lives at `.saga/tier-defaults.json`
(`plugins/saga/scripts/tier_defaults.py`), and `.gitignore:70` excludes `.saga/` in this repository.
A profile that a fresh clone or a fresh worktree cannot see would make admission ask questions that
are already answered — the same failure the record itself is designed around. So the profile is
tracked, at the repository root, and travels with the checkout.

*Rejected:* `.saga/repository-profile.json`, rejected for the reason above; and putting the profile
inside the saga plugin, rejected because it is per-repository data and the plugin is shared.

**KTD6 — the admission module never prompts; it emits a question set and consumes an answers
file.** `admission.py --issue N --dry-run` prints what it would ask and what it filled.
`admission.py --issue N` writes the record's front section with the defaults filled and the
unanswered questions listed under `admission.pending_questions`, and prints the question set.
`admission.py --issue N --answers <file.json>` records the answers and clears them from
`pending_questions`. Asking the operator the one message is the `/plan` skill's job, because the
skill is what has a conversation; the module stays free of interactive input, which is what makes
"the operator is asked exactly once" a testable property rather than a manual observation.

**KTD7 — admission reaches the card validator through the plugin-resolution ladder, not a
path guess.** The validator is `validate_card_body` at
`plugins/mission-control/scripts/sdlc_manager.py:4079`. Saga already locates the mission-control
plugin through `fleet_commons.plugin_resolution.resolve_plugin_root`, at
`plugins/saga/scripts/board_progression.py:87`, precisely because the earlier
`<repo_root>/plugins/mission-control/` guess was correct only inside this monorepo. Admission calls
the same helper with the same markers. A resolution failure is a refusal (exit 2) naming the rungs
tried, never a skipped validation.

**KTD8 — the spore carries the run record additively; the outcome block stays until issue 1030
removes it.** `plugins/saga/scripts/saga_spore.py` freezes the outcome directed acyclic graph and
the active saga box today, and both hooks are thin shells over it. This card adds a run-record block
to the frozen payload and re-injects it, and does not delete the outcome block — the `/outcome`
command still exists on this branch and its removal is issue 1030's work. The card's non-goal "no
second store" is about storage, and it is honoured: the spore writes no state of its own about the
record; it freezes a copy and re-injects it.

**KTD8a — the run record's `next_step` is authoritative; the saga envelope's is a mirror.** Both
carry a field of that name (`plugins/saga/scripts/saga.py:179`), so an implementer needs to be told
which one wins when they disagree. The record wins: it is the one file every role reads, and the
envelope log is an append-only history whose older ticks are *meant* to hold stale values. `saga.py`
writes the record's `next_step` whenever a tick sets one, and reads the record's value back when it
is asked where the run is. Nothing reconciles in the other direction, so a stale envelope tick can
never move a run backwards.

**KTD9 — every test resolves the store root through an injected parameter.** Each filesystem
function takes the store root as an argument, the way `plugins/saga/scripts/saga.py` takes `root`
as its first argument throughout. Tests pass `tmp_path`. A test that resolved the store from the
ambient git checkout would write into the primary checkout's live store, which is both a side effect
and a source of flakes when several card drivers run at once on this machine.

## Requirements to units

Every requirement lands in a named unit, so a unit can be checked off against something.

| Unit | Requirements it satisfies |
|---|---|
| U1 the record module | R1, R2, R3, R4, R10 |
| U2 the schema and profile reference documents | R5 |
| U3 admission and the repository profile | R6, R7, R8, R9 |
| U4 the state engine and the two spore hooks | R11, R12 |
| U5 admission at the start of `/plan issue` | R8 (the one message is the skill's, per KTD6) |
| U6 release surfaces | R15 |
| every unit | R13 (no test touches the live store), R14 (stated in its own section below) |

## Implementation Units

### U1. The run record module

**What:** `plugins/saga/scripts/run_record.py` — the schema constant, the store-root resolution, the
read and write seam, the unknown-version refusal, the unknown-field round trip, and a command-line
entry point with `show` and `path` subcommands.

**Shape:** a frozen dataclass for the record with an `extra` mapping, pure functions over an explicit
`store_root: Path` first argument, and `now` injectable, mirroring the house pattern in `saga.py`
and `outcome_store.py`. The command-line entry point is the only place that catches the version
error and maps it to exit 3.

**Test scenarios** (`tests/test_run_record.py`):

- An unknown top-level key read from disk is present, unchanged, in the file after a write.
- That same read emits one warning line naming the key.
- A record whose `schema` is `run_record.v2` makes `show` exit 3 with exactly one line on standard
  error and nothing on standard output.
- The same record read through the module API raises the named exception rather than exiting.
- The resolved record path is absolute.
- The resolved record path from a linked worktree equals the path resolved from the primary
  checkout, proved in a temporary repository built with `git init` plus `git worktree add`, never
  against this repository.
- A common directory not named `.git` refuses with one line naming it.
- A round trip of a fully populated record — every one of KTD4a's twelve top-level keys, with all
  thirteen parameters of KTD4's table filled — is byte-identical on the second write.
- The module's top-level key set is exactly KTD4a's twelve, failing with the differing names
  printed.
- A record missing an optional key reads back with that key's empty default and no refusal.
- Two writes in sequence leave no `.tmp` sibling behind and the second write's content wins.

### U2. The schema reference document and the profile reference

**What:** `plugins/saga/references/run-record.md` (the schema: every block, every field, the version
token, the refusal text, the exit-code table, the unknown-field rule) and
`plugins/saga/references/repository-profile.md` (what the profile file holds and which parameters it
defaults).

**Why it is its own unit, landing with U1:** every later child of the parent reads this record, so
the contract has to be readable before a consumer exists. The card's Risk section says so directly.

**Test scenarios** (`tests/test_run_record.py`, guard class):

- The thirteen parameter keys named in `plugins/saga/references/run-record.md` are exactly the
  thirteen the module writes — same names, same count, failing with the differing names printed.
- The twelve top-level keys named in the document are exactly the twelve the module writes.
- The version token in the document is the module's `SCHEMA` constant.
- The refusal line in the document is the string the module prints, character for character.

**Guard discipline:** each guard names what it guards in both places — the test id contains
`run_record`, the document section heading contains `run_record.v1`, and the test is watched failing
(seed a fourteenth parameter, a changed token, a reworded refusal) before it is allowed to pass.

### U3. The admission module and this repository's profile

**What:** `plugins/saga/scripts/admission.py` and a tracked `.saga-profile.json` at the repository
root.

**Arguments:** `--issue N` is required. `--repo owner/name` defaults to the `origin` remote of the
checkout the command runs in, so the common case needs no flag and a cross-repository run is still
expressible. `--store-root` overrides KTD1's resolution and exists for the tests (KTD9).

**Behaviour:** read the issue with `gh issue view --json`; run the card validator through KTD7's
ladder; on failure print the missing fields and exit 2 having written nothing; on success fill every
defaultable parameter from the profile, the staffing component and the lifecycle defaults, and write
the record's `admission` and `run_configuration` blocks with each value's `source`; print the
question set for the non-defaultable answers. `--dry-run` prints and writes nothing. `--answers`
records answers and clears them from `pending_questions`.

**Test scenarios** (`tests/test_admission.py`):

- A card missing `### Acceptance criteria` stops the step, names that field in the message, exits 2,
  and leaves no file in the temporary store.
- With a profile present, every one of the thirteen parameters carries a non-null value and a
  `source`, and the printed question set contains none of them except the ones R8 names.
- The printed question set is exactly R8's ten items on a fresh record.
- After `--answers` records them, a second run prints an empty question set and does not re-ask.
- `--dry-run` on a fresh issue prints the question set and the filled defaults and creates no file.
- `--dry-run` on an issue whose record already holds every answer prints an empty question set.
- The staffing component is called for `staffing_models_and_efforts` rather than a local table,
  proved by a fake that records its calls.

### U4. The state engine and the two spore hooks

**What:** `plugins/saga/scripts/saga.py` reads and writes the run record's `next_step`;
`plugins/saga/scripts/saga_spore.py` freezes the record into the payload;
`plugins/saga/hooks/precompact_spore_hook.py` and
`plugins/saga/hooks/compact_spore_session_hook.py` carry it across the compaction boundary.

**Boundary:** additive. Nothing existing is deleted here (KTD8).

**Test scenarios** (`tests/test_run_record.py`, continuity class; and the existing spore tests
extended):

- A saga tick that sets `next_step` leaves the record's `next_step` equal to it.
- When the envelope's newest tick and the record disagree, the value the state engine reports is the
  record's (KTD8a), and the record is not rewritten from the envelope.
- Freezing a record with a `next_step`, then re-injecting it, yields the same `next_step`.
- A frozen payload that names a record path outside the resolved store root is rejected by the
  existing repository-root mismatch guard rather than read.
- Both hooks still exit 0 and print nothing when no record exists.

### U5. Admission at the start of `/plan issue`

**What:** `plugins/saga/skills/plan/SKILL.md` gains admission as the first step of `/plan issue`:
run `admission.py --issue N --dry-run`, put the printed question set to the operator as one message,
record the answers with `--answers`, and carry on. The one message is the skill's, per KTD6.

**Test expectation:** the skill document is prose; the runnable half is U3's. The guard is the
existing documentation-lint step in the gate, plus one test asserting the skill names
`admission.py` and the record path so a rename cannot leave the instruction dangling.

### U6. Release surfaces

**What:** `plugins/saga/.claude-plugin/plugin.json` version bump, the matching
`.claude-plugin/marketplace.json` entry, `plugins/saga/CHANGELOG.md`, and the journal entries this
repository's instructions require in the shipping commit — a `DECISIONS.md` entry for KTD1, KTD2,
KTD4 and KTD5, and a `LEARNINGS.md` entry for the two-sets-of-thirteen trap in KTD4.

**Test expectation:** the repository's existing version and metadata drift guards.

## What this card replaces, and what waits for issue 1030

R14's answer, store by store. Nothing in this list is deleted by this card: the record becomes the
place the state belongs, and issue 1030 ("The removals: eleven commands and their families,
team-execution archived, hooks…") deletes the modules once every reader has moved.

| Store | Replaced by | Deleted by |
|---|---|---|
| Run-fact ledger (`run_ledger.py`) | the record's `units` and `review_cycles` blocks | issue 1030 |
| Evidence-custody ledger (`evidence_ledger.py`) | the record's `review_cycles` and functional-test blocks | issue 1030 |
| Dispatch-settlement ledger (`dispatch_settlement.py`) | the record's `roster` block with its pane identifiers | issue 1030 |
| Effort ledger (`effort_ledger.py`) | the record's `run_configuration.staffing_models_and_efforts` | issue 1030 |
| Envelope tokens (`envelope_token.py`) | the record's top-level `approval_scope` block and the merge-turn field in `units` | issue 1030 |
| Ship receipts (`ship_receipt.py`) | the record's `units` merge and release state | issue 1030 |

Two things stay and are not replaced at all: the saga envelope log under `.claude/saga/sagas/`,
which is the append-only history the record's single mutable file deliberately does not keep, and
the spore file under `<git-common-dir>/saga-spores/`, which is a transport across one compaction
boundary and not a store.

## Scope boundaries

**Out of scope.**

- No board write. Issue 1028 submits the six board moves through mission-control.
- No roster creation. Issue 1024's roster helper stands up the herdr sessions; this card only
  defines the `roster` block they write into.
- No second store. The spore hooks freeze and re-inject this record and nothing else of their own.
- No deletion of any of the six stores in the table above.
- No change to `/work`, `/code-review`, or the build loop; those are issues 1026, 1001 and 1027.
- Only the first of the lifecycle repository's six issue-review checks runs here. Check one is the
  card validator, which is mechanical and is what the card asks admission to run. Checks two
  through six — the product content is complete and testable, the technical claims are spot-checked,
  no `UNKNOWN` is outstanding, the approval boundaries are named per category, and `### Risk` carries
  a real tier with its justification — are the Issue Reviewer role's judgment, and no role is staffed
  for them until issue 1024's roster helper exists. Admission records whether each was performed and
  by whom, and fills `not_performed` where none was.

**Deferred to follow-up work.**

- The lens proposal, the finding dedupe and the severity flag from the typed-judgment model are
  issue B3's, and the record's `applicable_lenses` block is shaped to carry a proposal with its
  provenance so that card needs no schema change.
- A record for an issue in another repository: the schema carries `repo`, but this card's admission
  is exercised against this repository only.

## Risk analysis and mitigation

**The schema ripples.** Every later child reads this record, so a field renamed after they land is a
cross-card change. Mitigation: the schema is a written document with a guard test binding it to the
code (U2), landing with U1 and before any consumer.

**The two sets of thirteen.** The most likely silent error in this card is writing the run setup
contract's thirteen field names instead of the run model's thirteen parameters — both are thirteen,
both are in the same repository at the same pin, and both look right. Mitigation: KTD4 states the
distinction, U2's guard pins the names, and the journal learns it.

**A test that writes into the live store.** Several card drivers share this machine and the primary
checkout's `.claude/saga/` store is live state. Mitigation: R13, KTD9, and the store root as an
injected first argument everywhere.

**A worktree that reads an empty record.** If the store resolution regresses to a relative path, the
failure presents as "no run record", which reads like "no run" rather than like a bug. Mitigation:
the path-equality test in U1 runs in a temporary repository with a real linked worktree, so the
regression fails a test rather than a run.

## Questions answered from the card

The `AskUserQuestion` tool is unavailable in this stage, so every question the plan skill would have
asked is answered from the card, the lifecycle repository at revision `5efc869f`, or the code. Each
answer names its source.

| # | Question | Answer | Source |
|---|---|---|---|
| 1 | Pre-answer carrier (skill §0.7) | Applied: `destination` = `pr`, `backend` = `inline`, from caller "improve-claude-plugins run driver". Validator exit 0, no stop. | `plan_pre_answers.py` run on the invocation text |
| 2 | Handoff maturity (§0.2) | `requirements-ready` — a shaped capability card with a full contract, not a plan. Planning proceeds. | Issue 1023's body; objective plan section 1 ("new actionable cards enter at the Shaping stage … maturity `requirements-ready`") |
| 3 | Resume an existing saga? (§0.3) | No candidate. `saga.py scan` returned `{"candidates": [], "count": 0}`. Mint a new saga. | The scan run in this worktree |
| 4 | Is a plan document warranted? (§0.4) | Yes. Six units, twelve load-bearing technical decisions, a schema every later child reads. | Skill §0.4 rubric against the card's file list |
| 5 | Scope class (§0.5) | Deep. Two new modules, two reference documents, the state engine, both spore hooks, a skill, and release surfaces; every later child depends on the result. | Card's "Files expected to change"; driver's triage "medium-to-large" |
| 6 | Destination (§5.1) | `pr`. Not re-asked — the carrier applied it. | Carrier, question 1 |
| 7 | Deploy autonomy (§5.1 follow-up) | Not asked. The follow-up fires only when the destination is `nonprod-deploy`. | Skill §5.1 |
| 8 | Execution backend (§5.2) | `inline`. Not re-asked — the carrier applied it. The recommender is still called and recorded. | Carrier, question 1; skill §5.2 |
| 9 | Gated or advisory consensus (§5.2 KTD4) | Not reached. That interrogation runs only when a consensus or multi-reviewer signal is present; by the operator's 2026-09-19 decision this card gets no per-card code review at all. | Driver's stage instruction; skill §5.2 |
| 10 | Author an execution specification (§5.2a)? | No. §5.2a is entered only on an explicit `cc-workflows-ultracode` invocation, which did not happen. | Skill §5.2a |
| 11 | Which set of thirteen parameters? | The run model's table at `docs/lifecycle/run-model.md` lines 129 to 156, not the run setup contract's `required_fields`. | Card's own citation; both sets read at the pin |
| 12 | Where does the record live? | `<primary checkout>/.claude/saga/runs/issue-<N>.json`, resolved from the git common directory. | Card's Objective; issue 886 fifth finding; `outcome_store.resolve_common_dir` |
| 13 | What is the version field called? | `schema`, holding `run_record.v1`. | House convention in `plan_pre_answers.v1`, `roles_index.v1`, `lifecycle_snapshot.v1` |
| 14 | Which exit code for an unknown version? | 3, as the card's acceptance criterion pins. | Card's acceptance criteria |
| 15 | Where does the repository profile live? | A tracked `.saga-profile.json` at the repository root. | `.gitignore:70` excludes `.saga/`; KTD5's reasoning |
| 16 | Does this card delete any ledger? | No. It replaces what they hold; issue 1030 deletes them. | Card's Intent; parent 1018's child list |
| 17 | Board move at §0.6 | Submitted and landed: `Stage` = `Planning`, `Status` = `Designing`, record `field: Stage+Status`, `status: written`. | `reconcile_controller.py reconcile` output |

No question in this set was a production, destructive, credential, permission, billing,
external-commitment, or process-authority decision, so none was answered on the operator's behalf.

## Verification

```bash
uv run python plugins/saga/scripts/admission.py --issue 1023 --dry-run
uv run python plugins/saga/scripts/run_record.py show 1023
uv run pytest tests/test_run_record.py tests/test_admission.py -q
```

The card's third acceptance criterion — that a worktree created by `git worktree add /tmp/wt` can
read the record by the absolute path admission printed — is proved by U1's path-equality test in a
temporary repository, never against this repository's primary checkout (R13).

Note what the first two commands do when an operator runs them by hand. `--dry-run` writes nothing.
Dropping `--dry-run` writes a real record for issue 1023 into this machine's primary checkout store
at `<primary>/.claude/saga/runs/issue-1023.json`, which is the intended behaviour and is git-ignored,
but it is a real write and not a rehearsal.
