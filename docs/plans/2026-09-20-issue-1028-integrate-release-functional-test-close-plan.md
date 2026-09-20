---
title: Issue 1028 — integrate, release, functional test, close, and retro capture as automatic steps
type: feat
status: active
date: 2026-09-20
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Issue 1028 — integrate, release, functional test, close, and retro capture as automatic steps

## Summary

This plan makes the last third of a saga run automatic: after a code review is accepted, the
merging worker takes a merge turn recorded in the run record, the Release Worker merges the parent
through the pull-request path and hands a deployment to the deploy plugin, a functional tester runs
the plan's scenarios, the issue closes with a comment carrying the lifecycle repository's required
links, and the journal entries ship in the same commit as the change.

Alongside those steps it moves the board writing into one thin module. Saga has written none of the
lifecycle repository's allowed board moves since two releases ago; the orchestrate plugin carries
about 900 lines of board-writeback machinery that issue 1025 deliberately left standing for this
card to remove once the writes move into saga.

Two ledgers go with it. Two others cannot go yet, and this plan says so rather than quietly
widening its own scope.

## Problem Frame

The lifecycle repository (`infiquetra/infiquetra-sdlc`, pinned at revision `5efc869f` for this whole
parent) describes a run that ends by itself. The plugins do not implement that ending.

Three gaps, each with a named source:

**The merge turn has no home.** `docs/process/parent-branch-integration.md` says exactly one worker
holds the merge turn at a time, that the turn is ordinary execution state and never a lock service,
that the merging worker resolves ordinary conflicts, and that the Release Worker executes the merge
to the main branch and the deployment that follows. Orchestrate implements this for its own driver
(`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:4847` `merge_turn_holder`,
`:4889` `main_regression_files`, `:4968` `cmd_merge`), but saga — the plugin that runs a single
issue — has no merge turn at all.

**The board moves are named and never made.** `docs/process/saga-board-write-authority.md` and
`lifecycle_field_mutation.allowed_submissions` in the schema list six `(Stage, Status)` pairs a
caller may submit through Mission Control's constrained mutation. Nothing in this repository reads
that list: `grep -rn "allowed_submissions" --include=*.py plugins/ tests/` returns zero hits. Saga's
`plugins/saga/scripts/board_progression.py` is 864 lines of certificate gate, idempotency ledger and
bounded retry with no notion of a lifecycle boundary, and the one board move a skill actually makes
is spelled out in prose in `plugins/saga/skills/work/SKILL.md:239`.

**The ledgers outlived their readers.** Issue 1023 shipped the run record
(`plugins/saga/scripts/run_record.py`, `plugins/saga/references/run-record.md`) as the single place
run state belongs, and its own "What this record replaces" table names four ledgers this card is
asked to remove. Two of them still have live importers in modules that issue 1030 deletes.

## Admission answers

The repository's own admission step ran before planning:
`uv run python plugins/saga/scripts/admission.py --issue 1028`. The dry run filled twelve of the
thirteen run-configuration parameters and asked eight questions; the real run recorded every answer
and left no pending question. The record is at
`<primary checkout>/.claude/saga/runs/issue-1028.json`.

`AskUserQuestion` is unavailable in this session, so each answer came from a written source rather
than from a live prompt. The answer, and where it came from:

| Question | Answer | Source |
|---|---|---|
| `risk_tier` | `high`, "it merges, deploys, and writes the board; every step is dry-runnable and the deploy uses the existing handoff" | the card's own Risk section, verbatim |
| `approval_scope` | all seven boundaries granted `none` | the operator's standing list for this run: production, destructive actions, credentials, permissions, billing, external commitments, process authority, and plan-review or code-review overrides all stop and ask |
| `destination` | `pr` | the run driver's `plan_pre_answers.v1` carrier, validated at intake |
| `staffing_overrides` | `none` | the run driver's instruction; the staffing component's defaults stand |
| `lens_declaration` | the four always-on lenses plus six conditional ones | the lens catalogue at the pin (see below) |
| `repair_allowances` | 3 standard, 2 escalated | the lifecycle default at the pin (`docs/lifecycle/run-model.md`, decision item C3) |
| `unfinished_testing_response` | continue repair toward the prescribed tests | chosen; see the reason below |
| `change_shape` | `code` | the card's "Files expected to change" — six Python modules and three skill documents |

**The lenses, and why.** Always on, and never deselectable: architecture-maintainability,
correctness, security, testing. Conditional and selected, each against the catalogue's own
condition: **deployment-infrastructure** (the release step deploys and the card changes rollout
order), **reliability** (merge turns, conflict recovery, a refused board write, retries),
**api-contract** (two command-line contracts change and four modules lose or gain importers),
**adversarial** (a gate, a policy, a lifecycle state machine, a deployment, an external integration
with GitHub Projects, and a large diff), **documentation-clarity** (three skill documents and the
run-record reference change), **agent-usability** (the skills and commands an agent operates).
Conditional and left out, with the reason each: performance (no latency, throughput, query, memory,
caching or monetary-cost surface; each added step runs once per boundary), privacy (no personal or
sensitive data), accessibility-human-usability (the added surfaces are agent-invoked command steps
inside an automatic run; the dry-run output is a report, not a human-operated interactive surface),
experience (no user-facing product surface), previous-comments (the parent pull request carries no
prior review comments at plan time; it is selected at review if it does).

**Why continued repair, for unfinished functional testing.** The lifecycle names a closed set of two
modes and no default: bring the result to the operator, or continue repair toward the prescribed
tests. The card's own objective sentence says a functional-test failure "re-enters the build loop
under the post-merge allowance", which is the continued-repair mode; choosing the operator mode
would contradict the card it implements. The mode is bounded: the post-merge loop keeps its own
counter of three standard and two escalated cycles and may take exactly one recorded extension
(`docs/lifecycle/run-model.md`, decision items C3 and D5).

## Questions answered from the card

The installed plan skill asks the operator four things. None was put to the operator; each was
answered from a written source and is recorded here.

| Question | Answer taken | Source |
|---|---|---|
| Handoff maturity and routing (skill §0.2) | `requirements-ready`; plan from the card and the objective plan | the card carries no `Handoff maturity` section (`parse_issue.py --issue 1028` reports an empty maturity), and the objective plan's section 1 states that new actionable cards under this parent enter at maturity `requirements-ready` |
| Scope class (skill §0.5) | Deep | the run driver's complexity triage: a new merge-turn module, a rewritten board module, three skills, a 900-line removal in orchestrate, four ledgers judged, tests and release surfaces |
| Destination (skill §5.1) | `pr` | the `plan_pre_answers.v1` carrier from the run driver, applied at intake by `plan_pre_answers.py` (exit 0, no stop) |
| Execution backend (skill §5.2) | `inline` | the same carrier; the two other backends are explicit-invocation only and the carrier never applies them |

No question in the production, destructive, credential, permission, billing, external-commitment or
process-authority categories arose, so none was invented.

<!-- gate-exempt: this plan records that operator questions were answered from written sources; it defines no gate site and opens no prompt. -->

**One thing does need the operator, and it is not a question this plan may answer.** The card's
fourth acceptance criterion names three Operations board statuses — `Implementing`, `Ready to
merge`, `Closeout` — and only the first is a move the lifecycle repository allows saga to submit.
See KTD2; the deviation is reported, not resolved.

## Requirements

**R1.** The merge turn is a field on the run record's `units` rows. Only the unit whose
`merge_state` is `merging`, and whose turn is provably still in flight, may merge; every other unit
is refused by name.

**R2.** The merge goes onto the parent issue branch or onto `main` according to the run record's
`admission.destination`, and never onto a branch the destination does not name.

**R3.** An ordinary conflict is resolved by the merging worker as normal work. A conflict that is
not mechanical is reported by kind and left for the role the lifecycle repository names.

**R4.** A merge that would take a file backwards relative to a freshly fetched `main` is refused,
and the refusal names every such file. The fetch happens first; a guard evaluated against a stale
remote-tracking reference is itself a refusal.

**R5.** After each merge, two re-integrations happen and both are reported. The destination branch
just advanced is merged into every surviving unit branch, so the lanes still running are working
against what landed. And where the destination is the parent issue branch, the freshly fetched
`main` is merged into that parent branch, which is itself a surviving branch. A branch where either
re-integration conflicts is named and left for the worker who owns it, never silently skipped and
never force-resolved.

**R6.** No lock, lease, reservation or receipt is introduced. If a merge-turn case would need one to
be correct, the work stops and reports.

**R7.** Each of the run's six lifecycle boundaries submits at most one board move, taken from
`lifecycle_field_mutation.allowed_submissions` in the vendored schema, through Mission Control's
constrained lifecycle-field mutation. Nothing else is written, and no status the Operations board
does not carry is ever submitted.

**R8.** `uv run python plugins/saga/scripts/board_progression.py --record <path> --boundary
<name> --dry-run` writes nothing and prints one line: the single move it would submit, or — at the
one boundary the allowed list does not cover — that no submission is allowed there (KTD2a).

**R9.** A refused or failed move is reported with the boundary, the pair, and Mission Control's
reason. It is never retried silently and never downgraded to a half-write.

**R10.** The Release Worker merges the parent pull request through this repository's pull-request
path, waits for the required checks on the exact head commit it merges, and then hands the merged
revision to the deploy plugin through `plugins/saga/scripts/deploy_handoff.py`.

**R11.** Where the repository profile's `nonproduction_destination` is `none`, the release step
records that there is no destination and deploys nothing. That is a recorded outcome, not an error.

**R12.** No production deployment exists anywhere in this card.

**R13.** The functional tester runs the plan's scenarios through `/qa` against the real environment,
reading the run record rather than any ledger. A failure re-enters the build loop and is counted
against the post-merge allowance.

**R14.** The closing comment carries the links `docs/process/terminal-outcomes.md` requires: the
delivered revision and environment where applicable, the acceptance results, the residual risks and
follow-ups, the documentation status, the cleanup confirmation, the GitHub closure reason and the
terminal disposition. Where a practice does not apply, its absence is recorded with a reason.

**R15.** Journal entries ship in the commit that ships the change, and `/retro` captures them with
the engine, ledger, spend and tier-efficacy readers removed.

**R16.** `plugins/saga/scripts/evidence_ledger.py` and `plugins/saga/scripts/effort_ledger.py` are
removed and every importer is repaired. `run_ledger.py` and `dispatch_settlement.py` are deferred to
issue 1030 with the reason recorded (see the removal inventory).

**R17.** The orchestrate plugin's board-writeback path is removed, and the resolver helpers its
run-record lookup shares stay.

**R18.** Every test uses a temporary store, a temporary run record, a temporary git repository and a
fake Mission Control runner. No test writes a live board, merges a live branch, or deploys.

## Key Technical Decisions

**KTD1 — the six boundaries map onto the lifecycle repository's six allowed submissions, and the map
is not one-to-one.** The card names six boundaries; the schema names six `(Stage, Status)` rows.
They line up like this, and the module carries this table rather than deriving it from prose:

| Boundary | Stage | Status | Live Operations option |
|---|---|---|---|
| admission exit | Planning | Designing | `Designing` |
| plan-review pass | Planning | Ready for Active | `Ready for Active` |
| build start | Active | Implementing | `Implementing` |
| review acceptance | — | — | no allowed submission |
| merge plus deploy | Verify | Awaiting verification | `Awaiting verification` |
| close (no retro trigger fired) | Verify | Ready to close | `Ready to close` |
| close (a retro trigger fired) | Retro | Ready to close | `Ready to close` |

Rationale: the schema's `allowed_submissions_note` calls that list "the single authority", and the
two prose chapters render it as a generated region so they cannot disagree with it. Review
acceptance has no row, so the module reports "no allowed submission at this boundary" and writes
the run record only — an honest nothing rather than an invented move. Close has two rows because
`retro_trigger.no_trigger_closure` says a run with no fired trigger closes from Verify and never
enters Retro; the module picks the row by that flag.

All seven option names above were read from the live Operations board with
`gh project field-list 3 --owner infiquetra --format json` and each is present, and the vendored
census at `plugins/mission-control/config/board-schema.json` carries the identical 26-option Status
set, so the cached schema and the live board agree today.

**KTD2 — `Ready to merge` and `Closeout` are live board options that saga never submits, and the
card's fourth acceptance criterion is restated rather than satisfied as written.** Both names exist
on the live Operations Status field. Neither appears in `allowed_submissions`. The lifecycle
repository is explicit that the allowed list is the whole set a caller may submit, so submitting
either would be saga inventing board authority it does not have.

What this plan does instead: the criterion is proved against the allowed vocabulary —
`Implementing` at build start, `Awaiting verification` at merge plus deploy, `Ready to close` at
close — and the discrepancy between the card's wording and the schema is reported to the operator as
a finding, with the two candidate repairs named (amend the card's wording, or amend the lifecycle
repository's allowed list) and neither taken here. This is not the card's stop condition: Mission
Control is not refusing a move the lifecycle repository allows; the card names moves it forbids.

**KTD2a — the card's first acceptance criterion names the one boundary that has no move, and it is
judged on what the dry run truthfully prints.** The criterion asks that
`board_progression.py --record <path> --boundary review-accepted --dry-run` "prints the single
mission-control move it would submit". Under KTD1 that boundary has no allowed submission, so there
is no single move to print and no honest way to make one appear.

The criterion is therefore judged as: the command exits 0 and prints, on one line, that no
submission is allowed at the review-acceptance boundary, naming the allowed list it consulted. The
same command at the other five boundaries prints exactly one pair, and the work stage quotes all six
outputs. The concrete repair this plan proposes to the operator, and does not take: add an
`Active` / `Ready to merge` row to `lifecycle_field_mutation.allowed_submissions` in the lifecycle
repository — the live Operations board already carries `Ready to merge`, and that row would give
review acceptance the move both the card and the board expect. Amending the lifecycle repository
happens on that repository's own amendment card (`infiquetra/infiquetra-sdlc#170`, named in the
parent issue), not here, and it is a process-authority decision that stops and asks.

**KTD3 — the regression guard is shared, not reimplemented.** Orchestrate's `fetch_default_branch`
(`orchestrate.py:4870`) and `main_regression_files` (`:4889`) already implement the
fetch-first, refuse-by-name rule card 875 asked for. They move into a small shared module in
fleet-core — `plugins/fleet-core/scripts/fleet_commons/merge_guard.py` — which both plugins reach
through the `fleet_commons_shim` they already use, and orchestrate's two functions become thin
re-exports so its existing tests keep binding the same behaviour. Alternatives rejected: saga
importing the 6,610-line orchestrate command-line script as a library (it is a command surface, not
a library, and the import would resolve differently per install tree); and saga writing its own
second copy of the guard (two implementations of one safety rule is the defect this card exists to
avoid).

**KTD4 — the merge turn is derived state, checked against git, with no lock.** A unit row left at
`merging` by a turn that died is released, not trusted: the turn is live only while its own merge
worktree is still a registered linked worktree and still holds an unfinished merge. That is
orchestrate's own rule (`stale_merge_turn`, `orchestrate.py:4823`) and the lifecycle repository's
"inspect the actual Git and worker state first" step. The parent issue forbids a new lock, lease,
reservation or receipt, and R6 carries its stop condition.

**KTD5 — `board_progression.py` is rewritten thin and keeps the submission seam.** The new module is
a boundary-to-pair table, a run-record reader, a dry-run printer and one call into the existing
constrained path. It keeps `default_board_writer` and `resolve_mission_control_root`, because
`docs/process/saga-board-write-authority.md` names `board_progression.default_board_writer` as the
submission primitive behind the boundary. What goes is the machinery that had no lifecycle meaning:
the merge-record phases, the comment-idempotency markers, and the certificate-gated op vocabulary
that let any caller name any operation. Rationale: the certificate still gates the write, but the
caller can no longer choose an arbitrary target state — it chooses a boundary, and the table chooses
the pair.

**KTD6 — the release step records an absent destination instead of failing.** This repository's
profile declares `nonproduction_destination: "none"` (`.saga-profile.json:5`). The release step
therefore merges the parent pull request, waits for the required checks on the exact merged head,
writes `no non-production destination is declared for this repository; nothing was deployed` into
the run record's release state, and stops. `deploy_handoff.offer` is not called, because an offer
with no destination is a baton handed to nobody. Rationale: the lifecycle's closeout rule forbids
fabricating a deployment record, and an error here would block every run in a repository that has
no lower environment, which is this one.

**KTD6a — the release step is a small module, not skill prose.** The card's file list names one new
module, and this plan adds a second: `plugins/saga/scripts/release_step.py`. The reason is
testability. R10, R11 and R14 are behaviour — wait for the required checks on the exact head, record
a deployment or record its declared absence, compose a closeout comment with every required link —
and behaviour that lives only in a skill document cannot be tested, which would leave three of this
card's requirements with no executable guard. The module is thin: it shells out to `gh` through an
injected runner, reads and writes the run record, and calls `deploy_handoff.offer` only when a
destination is declared. The alternative — folding it into `merge_turn.py` as a second subcommand —
was rejected because taking a merge turn and releasing a parent are different jobs with different
owners, and one module would have to hold both.

**KTD6aa — waiting for the checks means the server's own verdict, not a local one.** The release
step binds the merge to the head it checked with `gh pr merge --match-head-commit <head>`, which
GitHub rejects outright if the pull request is not mergeable, and it classifies a refusal from
`mergeStateStatus` (`behind` → re-integrate, `dirty` → conflict, `blocked` → keep waiting). It never
treats a watch command's exit status as proof. The repository's journal records both halves of this:
`DECISIONS.md:9485` — the server that owns the reference is the only place the compare-and-swap can
happen, because a local read-then-compare is a time-of-check-to-time-of-use race — and
`LEARNINGS.md:11001` — a pull request squash-merged while its merge state was `UNSTABLE`, on a
watch command's word.

**KTD6b — the release state records the reviewed head and the landed commit separately.** This
repository allows merge commits, squash merges and rebase merges
(`gh api repos/infiquetra/infiquetra-claude-plugins`: all three true), so the commit that lands on
the destination branch is not necessarily the head the required checks ran against. The release
state therefore carries both: the head the checks were waited on, and the commit the merge produced,
with the merge method that connects them. Recording one and calling it the other is how a closing
comment ends up linking a commit nothing ever checked.

**KTD7 — two ledgers are removed here and two are deferred to issue 1030.** The rule this plan
applies: remove a ledger when every importer can be *repaired*; defer it when removal would require
*deleting* modules this card does not name. Issue 1026 set that precedent for `execution_spec.py`.
The inventory below shows the counts each way.

**KTD8 — the span of the work skill this card owns is defined by lifecycle position, not document
order.** Issue 1027 rewrites `plugins/saga/skills/work/SKILL.md` up to the hand-off to code review.
This card owns everything after review acceptance. In today's document that is section 5.3's
`accepted` outcome onward (`:716`), section 5.4 (`:750`), section 5.5 (`:787`), and section 4.4
(`:533`) — which is titled "Post-merge board actions" and is therefore lifecycle-after-review even
though it sits in Phase 4. Section 1.3b (`:239`), the build-start board move, is inside issue
1027's span: this card supplies the module and the boundary name, issue 1027 places the call, and
whichever of the two lands second resolves the conflict. At the merge turn this card verifies the
build-start call survived that rewrite.

## High-Level Technical Design

### The merge turn

`plugins/saga/scripts/merge_turn.py` is a library plus a command line. It reads one run record, and
for a named unit it: refuses unless that unit holds the turn; resolves the destination branch from
`admission.destination` (`pr` and `merge` target the parent issue branch; a run with no parent
branch targets `main`); fetches the comparison branch and refuses if the fetch fails; merges in a
detached worktree created and removed inside the turn; refuses by name if the merge result would
take any file backwards relative to the fetched comparison reference; on success advances the unit
to `merged`, records the merged tip, and merges the comparison branch back into every surviving
unit branch, reporting each branch where that re-integration conflicts.

A conflict on the unit's own merge leaves the parent branch untouched, releases the turn, and names
the conflict. A conflict the merging worker cannot resolve mechanically is reported by kind —
behaviour question, product question, plan change — exactly as
`docs/process/parent-branch-integration.md` routes them, and nothing is decided at the merge.

### The board move

`plugins/saga/scripts/board_progression.py` gains a `--record <path> --boundary <name>` interface
over the boundary table in KTD1. `--dry-run` prints the single move and exits; without it the move
goes through the same constrained path the reconcile controller already uses. Six boundary names
are accepted (`admission-exit`, `plan-review-pass`, `build-start`, `review-accepted`,
`merge-and-deploy`, `close`) and any other name is refused with the list. The `review-accepted`
boundary prints, and submits, nothing.

The submission itself keeps the path that already works and was exercised twice by this plan: the
boundary command hands the resolved pair to `plugins/saga/scripts/reconcile_controller.py`, which
owns the certificate gate, the idempotency key and the live drift re-read, and which in turn drives
`board_progression.default_board_writer` into Mission Control's `flow set-field` path. Nothing new
is invented between saga and Mission Control; the only new thing is that a caller now names a
lifecycle boundary instead of naming a target status of its own choosing.

Both halves of the pair go in one submission and both are checked: a record whose `field` reads a
bare `Status` is a half-write and is reported as a failure, because `Designing` is a legal Status on
its own and a half-write otherwise looks like success.

### The release, the functional test, and the close

The Release Worker's step: merge the parent pull request through `gh pr merge` on the repository's
configured path; read the merged head; wait for the required checks on that exact commit; record
the pull-request and merge links in the run record; then the destination branch of KTD6. The
functional tester reads the run record — never a ledger — runs the plan's scenarios through `/qa`,
and records each scenario's terminal state. The close step posts the closeout comment with the
links R14 lists, then closes with the disposition and the GitHub reason
`docs/process/terminal-outcomes.md` maps to it.

## Removal inventory

Each removal, the card that names it, and what happens to every importer. Importer counts are from
`grep -rn` over `plugins/ tests/ scripts/ tools/` for Python import sites, run at base commit
`87a5329e`.

| Module | Named by | Production importers | Test importers | Decision |
|---|---|---|---|---|
| `plugins/saga/scripts/effort_ledger.py` (263 lines) | this card, and issue 1023's replacement table | none | 1 (`tests/test_effort_ledger.py`) | **Removed here.** The test of the removed module is deleted with it; four documentation references are repaired |
| `plugins/saga/scripts/evidence_ledger.py` (704 lines) | this card, and its own acceptance criterion `test ! -f …` | 2 — `review_consensus.py` (8 sites), `closure_gate.py` (1) | 8 | **Removed here.** `review_consensus.py` survives issue 1030 (it is "the consensus scorer") and is repaired to write its cycle state to the run record's `review_cycles`; `closure_gate.py` is deleted by issue 1030 but exists today, so its single import site is repaired in place rather than the module deleted. `tests/test_evidence_ledger.py` is deleted with the module; the other seven test files lose their ledger assertions |
| `plugins/saga/scripts/run_ledger.py` (416 lines) | this card | 16 — the engine family (`engine_benchmark`, `engine_calibration`, `engine_dispatch`, `engine_promotion`, `engine_registry_cli`, `engine_stale_report`), `outcome.py`, `pulse.py`, `provider_control_chart.py`, `capability_elo.py`, `liveness_events.py`, `lifecycle_state.py`, `reconcile.py`, `team_teardown.py`, `dispatch_settlement.py`, and `hooks/team_teardown_hook.py` | 10 | **Deferred to issue 1030.** Fifteen of the sixteen importers are modules issue 1030 deletes outright; repairing them would be work thrown away, and removing them here would mean deleting modules this card does not name. Same shape as issue 1026's deferral of `execution_spec.py` |
| `plugins/saga/scripts/dispatch_settlement.py` (2,066 lines) | this card | 3 — `outcome.py`, `outcome_compat.py`, `plugins/cc-workflows/.../emitter.py`, plus `plugins/team-execution/.../dispatch_settlement_adapter.py` | 5 | **Deferred to issue 1030.** The outcome coordinator and the team-execution plugin are both removed or archived by issue 1030; the module also imports `run_ledger`, so it cannot outlive that deferral either |
| The orchestrate board-writeback path | this card (issue 1025 left it standing) | `orchestrate.py:2586`–`:3490` less the shared resolver helpers, plus `cmd_announce` (`:5249`) and its sub-parser registration (`:6529`) and the two call sites in `cmd_merge` (`:5147`) — about 850 of those 905 lines | `tests/test_orchestrate_board_writeback.py` (1,278 lines) deleted; `test_orchestrate_status_map_contract.py`, `test_orchestrate_merge.py` and `test_saga_no_direct_write.py` repaired | **Removed here.** `_version_rank` (`:2594`), `_newest_first` (`:2617`) and `_install_candidates` (`:2652`) stay: the run-record resolver at `:960`–`:965` uses them |

**Where the `test ! -f plugins/saga/scripts/evidence_ledger.py` criterion is judged.** In this
card's own unit tests and in the repository gate at the merge commit on `parent/1018`, not at the
parent pull request — the file is deleted by U4 and nothing later re-creates it. The two deferred
ledgers have no such criterion on this card, and issue 1030 carries them.

## Run-record fields this card reads and writes

Read: `admission.destination` (which branch a merge targets), `admission.risk_tier`,
`run_configuration.nonproduction_destination` (KTD6), `run_configuration.unfinished_testing_response`
and the two repair allowances (the post-merge loop's budget), `units[].branch`,
`units[].worktree`, `units[].merge_state`, `review_cycles` (whether a review was accepted), and
`next_step`.

Written: `units[].merge_state` (`ready` → `merging` → `merged`), `units[].merge_worktree`, a new
per-unit `merged_tip`, a run-level release state (the pull-request link, the merged head, the
required-check result, and the deployment record or its recorded absence), a run-level
functional-test state (per scenario: `passed`, `failed` or `blocked` with its cause), the post-merge
cycle counter, and `next_step` at each boundary.

Every new key is added inside an existing block, which the run-record contract permits without a
version bump; no top-level key is added, so `run_record.v1` stays the version token.

Two boundaries with a neighbouring card. This card writes the *value* of `next_step` at each of its
own boundaries; issue 1029 owns how that value is continued — the skill ending that invokes the next
step, and the session-start injection. Neither card changes the field's meaning, and the run record
remains the authority over the envelope log, as `run-record.md` already states.

One rule governs every importer repair in U4, so a repair cannot quietly become a deletion: an
importer that survives issue 1030 is repaired properly, onto the run record. An importer that issue
1030 deletes has only its ledger use neutralized — the smallest edit that keeps it importable — and
the module itself is left standing for that card. If any importer cannot be kept importable without
deleting a module this card does not name, that ledger's removal joins the deferral list rather than
widening this card.

## Implementation Units

### U1. The shared merge guard in fleet-core

**What:** move `fetch_default_branch` and `main_regression_files` out of orchestrate into
`plugins/fleet-core/scripts/fleet_commons/merge_guard.py`, and leave thin re-exports behind so
orchestrate's callers and tests bind the same behaviour.

**Why first:** both U2 and U3 depend on there being exactly one implementation of the refusal.

**Test scenarios** (`tests/test_merge_guard.py`, new): a failed fetch returns a refusal naming the
branch and the guard it blocks; a merge result that is an ancestor of the comparison reference
reverts nothing; a merge touching a file the comparison reference changed since they diverged is
reported by that file's name; a merge that is merely behind the comparison reference, touching no
file it changed, is not refused. Plus one binding test that orchestrate's two names resolve to the
shared implementation.

### U2. `merge_turn.py`

**What:** the module and command line of "The merge turn" above, over the run record.

**Depends on:** U1.

**Test scenarios** (`tests/test_merge_turn.py`, new — the card names this file): only the holder
merges, and a non-holder is refused by name; a row left at `merging` whose worktree is gone is
released and reported, not trusted; a merge that would revert a newer `main` file is refused and the
refusal names the file; a conflicting merge leaves the destination branch at its previous tip and
releases the turn; after a successful merge every surviving unit branch has the comparison branch
merged in, and a branch where that conflicts is reported; the destination branch is the parent issue
branch for `pr` and `main` for a run with no parent branch; and both re-integrations of R5 happen —
the advanced destination branch reaches every surviving unit branch, and the fetched `main` reaches
the parent branch — with a conflicting re-integration reported by branch name and left unresolved.
Every scenario runs in a temporary git repository with a temporary store root.

### U3. `board_progression.py` rewritten thin

**What:** the boundary table of KTD1, the `--record/--boundary/--dry-run` interface, the pair check,
the refusal reporting, and the deletion of the merge-record and comment-marker machinery. The
submission primitive and the Mission Control resolution stay.

**Depends on:** nothing in this plan; it reads the run record only.

**Test scenarios** (`tests/test_board_progression.py`, extended — the card names this file): each of
the six boundaries prints exactly its one allowed pair under `--dry-run` and writes nothing;
`review-accepted` prints that no submission is allowed at that boundary and writes nothing; an
unknown boundary name is refused and the six names are listed; `close` picks the Verify row with no
fired retro trigger and the Retro row with one; a fake Mission Control runner receives exactly one
invocation carrying both assignments; a runner returning a bare `Status` field is reported as a
half-write failure; a refused move is reported once and never retried; no pair outside
`allowed_submissions` can be submitted, including `Ready to merge` and `Closeout`.

### U4. The ledger removals and their importer repairs

**What:** delete `effort_ledger.py` and `evidence_ledger.py`; repair `review_consensus.py` and
`closure_gate.py`; strip the ledger assertions from the seven affected test files and delete the two
tests of the removed modules; repair the documentation references. Record the two deferrals in
`plugins/saga/references/run-record.md`'s replacement table so the next reader sees which ledgers
are gone and which wait for issue 1030.

**Depends on:** nothing.

**Test scenarios** (`tests/test_ledger_removal.py`, new): neither removed module is importable;
`review_consensus` records a cycle to a temporary run record and reads it back; `closure_gate` runs
its own path with no ledger present; the two deferred modules are still importable, so a premature
removal fails this test rather than silently passing issue 1030's work into this card.

### U5. The orchestrate board-writeback removal

**What:** remove the path named in the inventory, keep the three resolver helpers, delete
`cmd_announce` and its sub-parser, and remove the two call sites in `cmd_merge` together with the
writeback exit statuses 2 and 4 that no longer have a source.

**Depends on:** U3 (the board writes must already have a home in saga before orchestrate loses its
own).

**Test scenarios** (`tests/test_orchestrate_merge.py`, repaired; `tests/test_orchestrate_board_writeback.py`,
deleted): `merge` still merges, still refuses a regression by name, and no longer attempts any board
write; the run-record resolver still finds a run record through the retained helpers; the command
surface no longer carries `announce`; `tests/test_saga_no_direct_write.py` still passes with saga's
one remaining writer.

### U6. The three skills

**What:** in `plugins/saga/skills/work/SKILL.md`, inside the span KTD8 defines: the merge turn, the
release step, the functional-test hand-off, the close step and the four board moves those boundaries
submit, replacing section 4.4's reconcile-controller prose. In `plugins/saga/skills/qa/SKILL.md`:
read the run record instead of the evidence ledger in sections 5.1 and 6.1/6.2, and nothing else —
`/qa`'s content is issue 1039's card. In `plugins/saga/skills/retro/SKILL.md`: the journal capture,
with the engine-benchmark, calibration, staleness, capability-Elo, control-chart, ledger, spend and
tier-efficacy readers removed from Phase 1.

**Depends on:** U2, U3, U4.

**Test scenarios** (`tests/test_saga_skill_surfaces.py`, extended): the work skill names each of the
four post-review boundaries exactly once and names no status outside the allowed list; the QA skill
contains no reference to `evidence_ledger`; the retro skill contains no reference to the removed
readers; none of the three skills composes a board write itself.

### U7. Release surfaces and the journal

**What:** version bumps and changelog entries for saga, orchestrate and fleet-core; the marketplace
registry; the drift-guard tests; a `DECISIONS.md` entry for KTD1, KTD2 and KTD7; a `LEARNINGS.md`
entry for the allowed-submissions finding, with evidence, mechanism and a generalizable rule. Every
journal entry files under the `## 2026-09-20` heading at the top of each file.

**Depends on:** U1 through U6 and U8; it is the last unit to land.

**Test expectation:** the repository's existing release-surface parity and journal-order guards
cover this unit; no new test is added.

### U8. `release_step.py` — the release, the functional-test hand-off, and the close

**What:** the module of KTD6a. Three commands over one run record: `release` merges the parent pull
request through the repository's configured merge method, waits for the required checks on the exact
head it merges, and records the reviewed head, the landed commit, the merge method and either the
deployment record or its declared absence (KTD6, KTD6b). `functional-test` records each scenario's
terminal state and increments the post-merge cycle counter on a failure. `close` composes the
closeout comment from the run record with every link R14 requires, and refuses to compose one that
would fabricate an environment, a deployment or an acceptance result.

**Depends on:** U3 (the merge-plus-deploy and close boundaries submit their moves from here).

**Test scenarios** (`tests/test_release_step.py`, new): with `nonproduction_destination` set to
`none` the release records the absence with its reason, exits 0, and never calls the deploy handoff;
with a destination declared in a temporary profile it calls an injected handoff stub exactly once; a
required check still pending leaves the release unfinished and reports which check; a check that
failed on the exact head refuses the release by that check's name; a squash merge records a landed
commit different from the reviewed head, and both appear in the record; a functional-test failure
increments the post-merge counter and is refused once the allowance and its single extension are
spent; the closeout comment carries every required link and names the absence of each practice that
does not apply; a closeout that would state an environment the record does not carry is refused.
Every scenario uses a temporary store, a temporary run record and a fake `gh` runner; nothing merges
a live branch and nothing deploys.

## Scope Boundaries

**Out of scope, and staying out.**

- Saga writing a board field itself. Every move goes through Mission Control's constrained mutation.
- Any production deployment, and any deployment at all in this repository, whose profile declares no
  non-production destination.
- `/qa`'s content and its redesign as prescribed testing strategies — that is issue 1039.
- Any new lock, lease, reservation or receipt.
- Any status name the Operations board does not carry, and any pair outside `allowed_submissions`.
- The work skill before review acceptance — issue 1027's span.
- The eleven command removals and the team-execution archive — issue 1030's card.

**Deferred to follow-up work.**

- `run_ledger.py` and `dispatch_settlement.py`, to issue 1030, for the reasons in the inventory.
- The mismatch between the card's fourth acceptance criterion and the lifecycle repository's allowed
  submissions, reported to the operator under KTD2 and left unresolved here.
- The card's fourth acceptance criterion itself, which needs a real run across a real merge, a real
  deployment boundary and a real close. Those boundaries occur at the parent pull request issue 1030
  opens, not on this card's own branch. What the work stage proves instead: every one of the six
  boundaries quoted from its own dry run, and one real `build start` move submitted on this card's
  own board row through the new module.

## Risk Analysis and Mitigation

| Risk | How it shows | Mitigation |
|---|---|---|
| A board move lands at the wrong boundary and misfiles a card | a card sits in a stage its work has not reached | the boundary table is data, the dry run prints the single move, and Mission Control's all-boards-or-none write means a wrong move is at least consistent and visible |
| The half-write: `Stage` lands and `Status` does not | the card looks moved and is not | both halves ride one submission, and the record's `field` is checked for `Stage+Status` before any move is reported as made |
| Issue 1027 and this card collide in the work skill | a merge conflict in `SKILL.md` | the spans are disjoint by lifecycle position (KTD8) and whichever lands second resolves; this card verifies the build-start call survived |
| Removing `evidence_ledger` breaks a module issue 1030 keeps | `review_consensus` loses its cycle state | the repair moves that state to the run record's `review_cycles`, which issue 1023 built for it, and U4's test reads it back |
| The shared merge guard changes orchestrate's behaviour | a regression the orchestrate driver's own campaign hits | the extraction is a move plus re-export, and orchestrate's existing merge tests bind the same names |
| The gate cannot stay green | a removed module's test fails | tests are deleted with their modules and repaired where the module survives; no step is ever marked advisory |

## Board moves submitted by this plan

| Boundary | Pair | Result |
|---|---|---|
| planning starts (skill §0.6) | `Stage` = Planning, `Status` = Designing | `written`, `field` = `Stage+Status`, one attempt |
| the plan is ready (skill §5.0) | `Stage` = Planning, `Status` = Ready for Active | submitted after the document review passes |

## Stop conditions

Carried verbatim from the card. Stop and report if a merge-turn case would need a lock to be
correct, or if Mission Control refuses a move the lifecycle repository allows. Neither has fired at
plan time.

## Amendments made during the work stage

The plan is the contract, so where the build departed from it the departure is recorded here rather
than left for a reader to find in a diff. Four, each with what the code found.

**KTD3 — orchestrate keeps its own copy of the guard, with an equivalence test instead of a
re-export.** The plan said orchestrate's two guard functions would become thin re-exports of
fleet-core's shared module. The code says otherwise: `orchestrate.py` carries a comment block at its
plugin resolver explaining why it must not take a resolution dependency on another plugin for
something it needs when that plugin is absent, and a safety guard is precisely that — an orchestrate
on a machine without fleet-core would fail at import rather than degrade. So the shared module is
fleet-core's, saga imports it, orchestrate keeps its own pair, and `tests/test_merge_guard.py`
drives both through one case table and fails if they diverge. One rule, two homes, one test.

**KTD5 — `board_progression.py` gains the boundary layer rather than being gutted.** "Rewritten
thin" meant removing the merge-record phases and the comment-idempotency machinery. Both still have
live callers: `outcome_merge.py` uses `record_envelope_authorized_merge`, and `default_board_writer`
uses the comment markers for the progress-comment operation. Removing them would mean deleting or
rewriting modules this card does not name — the same test the ledger deferrals apply. What changed
instead is the caller-facing surface: a caller now names a lifecycle boundary and cannot name a
target state of its own, and any pair outside the allowed list is refused. The primitives go with
the outcome coordinator, on issue 1030.

**KTD7 / U4 — `evidence_ledger.py` is deferred too, and the card's second criterion is not met.**
The plan expected two removals and two deferrals. Parsing imports rather than grepping names (see
the learning entry `{#1028-field-named-after-a-module}`) showed `review_consensus.py` never imported
the module at all — its eight hits are a dataclass field of the same name. The module's sole
production importer is `closure_gate.py` (310 lines), whose whole subject is that ledger and which
has two further production dependents, `intent_envelope.py` and `outcome_orchestrator.py`, plus five
test modules. Removing the ledger therefore means deleting `closure_gate.py`, which this card does
not name and issue 1030 does, or rewriting it and its dependents onto the run record, which is issue
1030's work done early and thrown away. So `test ! -f plugins/saga/scripts/evidence_ledger.py`
**fails on this branch**, deliberately, and is reported rather than forced. `effort_ledger.py` was
removed as planned.

**U5 — `tests/test_orchestrate_status_map_contract.py` is deleted as well.** The plan named one test
module to delete with the writeback. This second one pins the vocabulary of the removed functions
(`stage_statuses`, `live_rungs`, `normalize_rung`); with them gone its whole subject is gone. Its 10
test names are recorded with the other 56 in the work-session notes.
