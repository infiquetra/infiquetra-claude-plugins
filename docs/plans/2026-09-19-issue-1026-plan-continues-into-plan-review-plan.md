---
title: Plan continues into plan review
type: refactor
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Plan continues into plan review

## Summary

Make `/plan` finish the plan-review step itself instead of recommending it. `/plan` ends by
dispatching `/doc-review` to the Plan Reviewer — a herdr pane through the roster helper when the
run record staffs one, the same session in review-only mode when it does not — and then loops
review, repair, re-check until no `P0` or `P1` finding remains or the operator says one word. The
document-review floor gate in `/work` stays blocking exactly as it is today. In the same change,
the Claude Code Workflow and team-execution authoring prose leaves `/plan` and `/work` for a new
reference file, and two of the three named scripts are deleted with their tests.

## Problem Frame

Three separate problems land on the same three files, which is why one card carries all of them.

**The plan review does not happen unless a person remembers to ask for it.** `/plan` Phase 5.4
("Route", `plugins/saga/skills/plan/SKILL.md:758-766`) recommends `/doc-review` and stops. `/work`
§1.3 (`plugins/saga/skills/work/SKILL.md:260-268`) then blocks when the plan did not clear review.
So the gate is real but the review that feeds it is optional, and the operator is the transport
between them. The simplification review's requirement R3 and the operator's 2026-09-19 answer to
its question 4 settle the shape: the floor gate stays blocking, and it runs by itself.

**About half of `/plan`'s instructions describe a backend the repository does not use.** Phase 5.2
and 5.2a (`plan/SKILL.md:438-672`) are 235 of 772 lines — 30 percent of the file and, measured by
instruction text rather than raw lines, the 44.9 percent the simplification review reports — for
the `cc-workflows-ultracode` backend, which issue 808's recorded NARROW ruling already confined to
explicit invocation. `/work` §1.4 and §1.5 (`work/SKILL.md:306-674`) are the matching 369 lines, 32
percent of that file. The prose is not wrong; it is in the wrong place. Card 808's ruling says the
Workflow backend is a task-local mechanism reached only by explicit invocation, and a mechanism
reached that rarely belongs in a reference file the skill points at, not in the entry path every
run reads.

**Four document-review cards have been open since the Saga Document Review parent, each too small
to run alone, each landing in the same two files.** Card 931 (the operator-is-the-transport clause
and two prohibitions that name deleted scripts), card 932 (the rubric command that resolves
relative to the caller's directory and degrades silently when its rubric is missing), card 933 (no
bounded repair-and-recheck loop; a document the operator submits can be redirected), and card 934
(three descriptions of a lifecycle phase nothing writes, an undefined artifact-matching rule). They
are folded here because the edits collide, not because they are related in kind.

## Requirements

**R1.** `/plan` ends by dispatching `/doc-review` for the plan it just wrote, without the operator
typing a command. The dispatch target is the Plan Reviewer.

**R2.** The dispatch target is chosen by a written rule: a herdr pane through the roster helper
when the run record's staffing plan staffs `plan-reviewer` and the helper can run, the same session
in review-only mode otherwise. The choice and its reason are recorded in the run record.

**R3.** The review runs as a loop: review, repair, re-check, until no `P0` and no `P1` finding is
open. Each turn of the loop is recorded as one entry in the run record's `review_cycles`.

**R4.** The loop is bounded by the run record's recorded allowances — `standard_cycle_allowance`
and `escalated_cycle_allowance`, three and two for this run — and exhausting them stops and reports
rather than passing.

**R5.** The only way past an open `P0` or `P1` is one word from the operator, recorded with its
rationale. No condition in any skill may produce that override on its own.

**R6.** `/work`'s document-review floor gate still refuses to execute on an open `P0` or `P1`
without that recorded override. This requirement is a preservation requirement: its test must fail
if the gate is weakened.

**R7.** A document the operator submits by path is reviewed as given. `/doc-review` never
reclassifies a submitted path into a different target or routes it elsewhere.

**R8.** `/plan`'s instructions contain no Workflow-backend or team-execution-emission section. Both
bodies of prose live in `plugins/saga/references/workflow-backend.md`, which the two skills name.

**R9.** `/work`'s instructions keep only the explicit-invocation contract — what the backend is,
that it is reached only by explicit invocation, and where the protocol lives — and point at the
same reference file for the rest.

**R10.** `plugins/saga/scripts/team_emitter.py` and `plugins/saga/scripts/spec_table.py` are
deleted, together with the tests that exist only to test them, and every other importer is repaired
by name.

**R11.** The rubric command in `/doc-review` resolves from any working directory, proven by a test
that runs from a directory other than the repository root.

**R12.** A rubric that cannot be loaded stops the review and says so. No path substitutes a weaker
rubric for a missing one.

**R13.** The extras-rubric instructions present each rubric's applicability condition before the
step that selects on it.

**R14.** `--doc-review-fixes` exists on `issue_progress.py`'s argument parser and is forwarded from
`/work`'s Phase-4 command, so the applied fixes reach the issue comment.

**R15.** `/doc-review` carries the standalone operator-is-the-transport clause, and `/code-review`
carries the same clause. Neither prohibits any script by name; both use a general prohibition. A
test compares the two so they cannot drift.

**R16.** The `external_opinion` and `claude_adjudication` cross-reference in `/doc-review` resolves
to a target that exists, and its guarding test asserts the target's existence rather than a path
string.

**R17.** No Saga document describes `review` as a lifecycle phase that Document Review enters or
writes, and no write path to that phase is added.

**R18.** "The latest matching artifact" is defined, and both filename conventions the
`docs/reviews/` corpus already uses are written down, with ambiguity between them surfaced rather
than guessed.

**R19.** The "safe fixes are enabled by default" wording either honours a report-only request or
drops the word "default".

**R20.** A review artifact for a committed plan records a real commit SHA rather than `working
tree`.

**R21.** Every release surface moves in the same pull request: `plugins/saga/.claude-plugin/plugin.json`,
`plugins/saga/CHANGELOG.md`, `.claude-plugin/marketplace.json`, and any version drift-guard test.

**R22.** A real `/plan issue <N>` run against this branch's copy of the skill ends in a plan-review
pass or a named `P0`/`P1`, with no `/doc-review` typed by the operator, and the run is recorded.

## Key Technical Decisions

**KTD1. `execution_spec.py` is not deleted by this card; issue 1030 deletes it.** The card's second
acceptance criterion asks for `test ! -f plugins/saga/scripts/execution_spec.py`. On this branch
that file has seven live importers inside saga — `spend_receipt.py:38`, `spend_estimate.py:44`,
`spend_retro.py:37`, `manifest_store.py:54`, `tier_efficacy.py:29`, `engine_dispatch.py:27`, and
`outcome_dispatcher.py:39` — plus roughly thirty test modules and a detection path in the
cc-workflows plugin. Every one of those seven modules is already on issue 1030's removal list (the
spend readers, the ceremony and receipt family, the ratings machinery migrating to the staffing
component, the engine registry family, and the outcome coordinator). Deleting the file here means
deleting those seven modules and the commands that call them, which is issue 1030's whole job
pulled into a card scoped as three skills and two scripts. Deleting it in issue 1030 instead
reaches the identical end state with none of that risk, because nothing survives 1030 that imports
it. The rationale for choosing the later card is sequencing, not reluctance. **This changes a
written acceptance criterion, so it is an operator question, recorded below under "Operator
questions this plan does not answer" and not decided here.**

**KTD2. The dispatch target is chosen from the run record, never from the environment.** The rule
is: read `<primary checkout>/.claude/saga/runs/issue-<N>.json`; if its `roster` array already holds
a live row whose role is `plan-reviewer`, dispatch to that pane; else if
`run_configuration.staffing_models_and_efforts` names `plan-reviewer` and the roster helper can run
here, run `roster.py up --issue <N>` and dispatch to the pane it records; else review in this
session in review-only mode. The reason for choosing the record over a live probe is that the same
run continues in other sessions and on other machines, and a rule that reads the environment gives
a different answer in each of them. The roster helper refuses outside a herdr pane with exit 4 and
reports a blocked role with exit 5 (`roster.py:117-118`); exit 4 is the ordinary case for a
background driver and falls through to review-only mode, and exit 5 is reported, never answered.

**KTD3. The loop's bound comes from the run record, not from a number written in the skill.** The
allowances are already recorded per run (`standard_cycle_allowance` 3, `escalated_cycle_allowance`
2, from the lifecycle repository's defaults at revision `5efc869f`). Writing a literal three into
the skill would put a second copy of a settled number where nobody would think to change it.

**KTD4. The override is one word from the operator and nothing else.** No skill sentence, no
finding count, no cycle exhaustion, and no unattended-mode condition produces it. Exhausting the
allowances stops and reports; it does not pass. The test for this is written as a negative: a
review result carrying an open `P0` and no operator word must not reach execution.

**KTD5. The relocated prose moves verbatim where it is still true, and the skills keep a pointer
paragraph, not a summary.** A summary of a backend contract is a second source that drifts from the
first. The skills keep exactly what a reader needs to decide whether to go to the reference file:
the backend's name, that it is reached only by explicit invocation under issue 808's NARROW ruling,
and the file's path.

**KTD6. Two tests currently pin the prose in place and are repaired, not deleted.**
`tests/test_workflow_extraction.py:280` asserts `"execution_spec.py settlement" in work_skill` and
`tests/test_saga_plugin.py:120-140` asserts a ten-item ordered list of the same command text. Both
are real contracts — they exist so the driver-side seam cannot silently lose its settlement step —
so each is retargeted at `plugins/saga/references/workflow-backend.md`, which is where the seam
now lives. Deleting them would remove the protection along with the location.

**KTD7. The rubric invocation is repaired in the skill, and the loud failure replaces a sentence,
not an accident.** `lifecycle_review.py:57-59` already anchors `RUBRICS_DIR` to `Path(__file__)`,
so the rubric directory was never the problem. What is caller-relative is the invocation
`python3 ../../scripts/lifecycle_review.py` at `doc-review/SKILL.md:56-72`. And the silent
degradation is an instruction the skill gives itself at `doc-review/SKILL.md:78-79` ("If the rubric
engine or its rubrics are unavailable, say so clearly and continue with the readiness review where
safe"), so the fix replaces that sentence as well as the path.

**KTD8. Card 934's phase-write question is recorded, not decided.** Whether `/doc-review` should
write `lifecycle_phase=review` so the stored state matches the lifecycle chapter is an operator
decision with a live contradiction on both sides — the lifecycle repository's `docs/process/gates.md`
says the doc-review gate advances the phase, and card 920's non-goal forbids giving Document Review
saga-state write authority. This plan corrects the three descriptions to say the phase is declared
and not written, and files the decision as its own follow-up.

## High-Level Technical Design

Three seams change, and nothing else in the lifecycle moves.

**The first seam is the end of `/plan`.** Today Phase 5.4 prints four recommended next commands.
After this change Phase 5.4 runs the review: it resolves the reviewer by KTD2's rule, dispatches,
reads the result, applies repairs to the plan document, and re-dispatches, recording one
`review_cycles` entry per turn. It exits on a clean result, on the operator's override word, or on
exhausted allowances — and only the first of those three is a pass.

**The second seam is `/doc-review`'s own shape.** It gains the loop contract on its consuming side:
what a re-check means (the same reviewer, the same rubric, the revision it is bound to), and the
rule that a submitted path is reviewed as given. Its rubric invocation and its failure behaviour
are repaired in the same edit.

**The third seam is `/work` §1.3.** It does not change behaviour — that is requirement R6 — but it
gains one sentence saying where the review result now comes from (the run record's `review_cycles`,
or the same-session output, or the latest matching `docs/reviews/` artifact, in that order) so the
gate reads the durable record first rather than falling back to chat memory after a resume.

Where the skill's *ending* lives matters for the card that follows this one. Issue 1029
(continuation mechanics: every skill ends by invoking the next step, and the run record's
`next_step` field carries it) will edit exactly these endings. In this plan the ending of `/plan`
is **Phase 5.4, the section headed "Route"**, which this card renames and rewrites; the ending of
`/doc-review` is its **final section, "Output Shape"**; and the ending of `/work` is **§5.4, "Reach
PR-ready and present continuation routing"**. Issue 1029 should look there and nowhere else in
these three files.

## Implementation Units

**Why nine units for one card.** Five of them exist because the card folds four previously separate
child cards into itself, and each folded card has to stay separately traceable to its own
acceptance criteria — U5 is card 932, U6 is card 931, U7 is card 934, and U2 through U4 are card
933. The remaining four are the card's own work. The unit count measures the folding, not the
size: the change touches fourteen files, which is inside the ordinary range for one pull request,
and every unit is independently landable.

### U1. Move the Workflow-backend and team-execution prose into a reference file

**What:** Create `plugins/saga/references/workflow-backend.md` holding, verbatim where still true,
`plan/SKILL.md` §5.2 and §5.2a (lines 438-672) and `work/SKILL.md` §1.4's backend-offer half and
§1.5 in full (lines 306-674). Replace each removed region with a short pointer paragraph per KTD5.
`/plan` Phase 5.1's destination question and Phase 5.3's generated save-example regions stay in the
skill — the generated regions are rendered from `references/plan-save-contract.yaml` and guarded by
`tests/test_saga_spec_consumer_row.py`, so moving them would break a generator contract this card
does not own.

**Cards:** 808 (the relocation the NARROW ruling's implementation left behind), 1026.

**Patterns to follow:** the existing reference files under `plugins/saga/references/` —
`execution-spec.md` and `operator-choice.md` are the two nearest neighbours and should be
cross-linked from the new file rather than duplicated.

**Execution note:** move text; do not rewrite contracts while moving them. A wording change made
in the same commit as a move is invisible in the diff.

**Test scenarios:**
- `tests/test_workflow_extraction.py` — a new case asserting `grep -c -i "workflow backend"` over
  `plan/SKILL.md` is zero and that `plugins/saga/references/workflow-backend.md` exists and names
  the backend.
- `tests/test_workflow_extraction.py:270-289` — the existing case retargeted per KTD6 so the
  settlement, lease, reserve, attest, and release steps are asserted against the reference file.
- `tests/test_saga_plugin.py::test_work_skill_wires_driver_owned_workflow_settlement` — retargeted
  the same way, ordering assertions preserved.

**Verification:** `grep -c -i "workflow backend" plugins/saga/skills/plan/SKILL.md` prints `0`;
`test -f plugins/saga/references/workflow-backend.md`.

### U2. `/plan` ends by dispatching the plan review

**What:** Rewrite `plan/SKILL.md` Phase 5.4 from a routing recommendation into the dispatch and the
loop. State KTD2's resolution rule and KTD3's bound. Record one `review_cycles` entry per turn and
the reviewer choice with its reason. Keep the `/brainstorm` step-back route, which is a different
exit and not a review outcome.

**Cards:** 1026, 933.

**Patterns to follow:** `work/SKILL.md:83-101` ("Role sessions: the roster helper") is the written
form of a roster dispatch already in the repository; follow it rather than composing launcher calls.
The dispatch text is `roster.py`'s `dispatch_brief` (`roster.py:452-475`), which names the role
prompt by absolute path — `plugins/agent-launcher/roles/plan-reviewer.md` — rather than pasting it.

**Execution note:** the run record for this issue records an empty `roster` array and a staffing
plan that does staff `plan-reviewer` at `claude`/`opus`/`high`. Both branches of KTD2's rule are
therefore reachable and both must be written, not just the one this run takes.

**Test scenarios:**
- `tests/test_doc_review_loop.py::test_plan_dispatches_review_without_an_operator_command` — the
  plan skill's Phase 5.4 contains a dispatch and no sentence recommending the operator run
  `/doc-review`.
- `tests/test_doc_review_loop.py::test_reviewer_resolution_names_both_branches` — the section
  states the roster-pane branch and the same-session review-only branch, and names the run record
  as the source of the choice.
- `tests/test_doc_review_loop.py::test_loop_bound_reads_the_run_record` — the section names
  `standard_cycle_allowance` and `escalated_cycle_allowance` and carries no literal cycle count.

### U3. `/doc-review` becomes the repair loop, and an explicit submission is always reviewed

**What:** Add the loop contract to `doc-review/SKILL.md`: what one cycle is (one review result
followed by one repair batch, matching the lifecycle repository's definition at revision
`5efc869f`), that a re-check is bound to the revision it read, and that a path the operator submits
is reviewed as given and never redirected. Rewrite the "Loop And Work Integration" section, which
currently says `/doc-review` is explicit by default and `/work` should ask whether to run it.

**Cards:** 933, 1026.

**Patterns to follow:** the P0-P3 priority table already in `doc-review/SKILL.md:176-186` matches
the lifecycle repository's `docs/reviewers/plan-review.md` table at the pin; do not restate it,
reference it.

**Test scenarios:**
- `tests/test_doc_review_loop.py::test_submitted_path_is_reviewed_as_given` — the target-resolution
  section states that a supplied path is reviewed and names no redirect.
- `tests/test_doc_review_loop.py::test_cycle_definition_matches_the_lifecycle_pin` — the cycle
  definition in the skill is the pin's wording.

### U4. The floor gate in `/work` stays blocking, and reads the durable record first

**What:** Edit `work/SKILL.md` §1.3 to name the order of evidence (run record `review_cycles`, then
same-session output, then the latest matching `docs/reviews/` artifact) and to restate the refusal
in terms of the recorded override. Behaviour does not change. Carry a gate-record marker on the
section in the exact three-attribute form `plugins/saga/scripts/lint_gate_absence_contract.py`
documents in its own module docstring (an identifier, an absence behaviour, and a transport), with
the absence behaviour `HALT` — the same form `plan/SKILL.md` §0.1b already carries for the
admission questionnaire.

**Cards:** 933, 1026.

**Execution note:** this is the preservation unit. Write the test before the edit and watch it pass
against the unedited file, then watch it fail against a deliberately weakened copy. A guard that
has only ever been seen passing is not a guard.

**Test scenarios:**
- `tests/test_doc_review_loop.py::test_work_refuses_on_an_open_p0_without_the_override` — the §1.3
  text blocks on an open `P0` or `P1`, and names the recorded override as the only way past.
- `tests/test_doc_review_loop.py::test_work_gate_has_no_automatic_override` — no sentence in §1.3
  produces an override from a condition rather than from the operator.
- Mutation proof: deleting the refusal sentence must fail the first of these.

### U5. The rubric command resolves from anywhere and fails loud

**What:** In `doc-review/SKILL.md:56-79`, replace the caller-relative invocation
`python3 ../../scripts/lifecycle_review.py` with a repository-root-relative form, and replace the
"continue with the readiness review where safe" sentence with a stop. Reorder the extras-rubric
steps so each rubric's applicability condition is read before the step that selects on it. Add
`--doc-review-fixes` to `plugins/saga/scripts/issue_progress.py`'s argument parser (the parameter
already exists at line 75 and is rendered at line 129, with no flag to populate it) and forward it
from `/work`'s Phase-4 command.

**Cards:** 932.

**Execution note:** card 932's out-of-scope list forbids adding a durable applied-or-skipped lens
record or a lens census; lens selection stays adaptive.

**Test scenarios:**
- `tests/test_doc_review_rubric_resolution.py::test_invocation_resolves_from_a_non_root_directory`
  — run the invocation form the skill prints from a temporary directory and assert it lists the
  cores. A test that only ever runs from the repository root cannot catch this defect.
- `tests/test_doc_review_rubric_resolution.py::test_a_missing_rubric_stops_the_review` — with the
  rubric directory made unreadable, the command fails and the skill text names a stop, not a
  fallback.
- `tests/test_doc_review_rubric_resolution.py::test_no_weaker_rubric_is_substituted` — no code path
  and no skill sentence offers a substitute.
- `tests/test_doc_review_rubric_resolution.py::test_extras_conditions_precede_selection` — the
  condition step's line number is below the selection step's in the skill.
- `tests/test_saga_issue_progress_is_posted.py` — `--doc-review-fixes` parses and reaches the
  rendered comment. That is the existing file's real name; there is no
  `tests/test_saga_issue_progress.py`.
- Mutation proof: restoring the caller-relative path fails the first test; restoring the fallback
  sentence fails the second.

### U6. Finish issue 776's Document Review half

**What:** In `doc-review/SKILL.md`, add the standalone operator-is-the-transport clause, copying
the sentence `code-review/SKILL.md:131` already carries; replace the by-name prohibitions of
`engine_session_runner.py` and `engine_offer.py` at `doc-review/SKILL.md:124-125` with a general
prohibition; repair the `external_opinion` / `claude_adjudication` cross-reference at lines
141-142, which points at `../code-review/references/findings-schema.md` — a file that exists and
contains neither string, confirmed by `grep -c` returning zero at this branch; and rewrite the
"External-reviewer panel (opt-in)" section (lines 105-120), which instructs a dispatch through
`engine_resolver.resolve_role(...)` "via agy" that issue 776 retired and that contradicts the
transport section one line below it. Do not delete
`plugins/saga/references/engine-registry.yaml`; describe it as capability metadata.

**Cards:** 931.

**What this unit does not edit, and the question that leaves open.** Card 931 also asks that
`code-review/SKILL.md` carry the same clause naming no script. On this branch that file still
prohibits both dead scripts by name at lines 120-121 — one line of edit. But
`plugins/saga/skills/code-review/` is issue 1001's directory and this run's driver is instructed
not to touch it, so this unit edits `doc-review/SKILL.md` only and the one line in
`code-review/SKILL.md` is raised to the coordinator rather than taken. The cross-file agreement
test below therefore has two possible states, and the plan says which is which rather than leaving
the worker to guess: if issue 1001's rewrite has already replaced the by-name prohibition, the test
passes as written; if it has not, the test fails, and **the card does not merge on a red test** —
the worker asks the coordinator, makes the one-line edit under the answer, and only then merges.
The alternative, shipping the test skipped or the assertion softened, is the failure this whole
card exists to stop.

**Test scenarios:**
- `tests/test_doc_review_transport.py::test_both_capabilities_carry_the_same_transport_clause` —
  the operator-is-the-transport sentence is present in both `doc-review/SKILL.md` and
  `code-review/SKILL.md` and reads identically, so the two cannot drift.
- `tests/test_doc_review_transport.py::test_no_script_is_prohibited_by_name` — neither file names a
  script in its prohibition. This is the test whose second half depends on the coordinator's answer
  above.
- `tests/test_doc_review_transport.py::test_cross_reference_target_exists` — the test resolves the
  referenced target file and fails when it is absent. Prove it against a deliberately missing
  target so a string-only assertion cannot pass.
- `tests/test_doc_review_transport.py::test_engine_registry_survives` —
  `plugins/saga/references/engine-registry.yaml` exists and its readers still resolve.

### U7. The maintenance sweep

**What:** Correct two of the three descriptions of the `review` lifecycle phase — `work/SKILL.md:27`
and `references/saga-spec.md:195` — to say the phase is declared in `saga.py:75`'s
`LIFECYCLE_PHASES` and written by nothing, which a repository-wide search for
`lifecycle_phase=review` confirms at this branch. The third description, `loop/SKILL.md:29`, is
**not** edited: issue 1030 deletes `plugins/saga/skills/loop/` entirely, so repairing a sentence in
a file a sibling removes is wasted work and a merge conflict on the integration branch. Define "the
latest matching
artifact" (`doc-review/SKILL.md:217`, `work/SKILL.md:243`) by writing down the two filename
conventions the `docs/reviews/` corpus already uses, with the rule that an ambiguity between them
surfaces as a finding rather than being resolved by preference. Resolve the "safe fixes are enabled
by default" wording at `doc-review/SKILL.md:154` by dropping "default" unless a report-only switch
is defined in the same edit. Record a real commit SHA rather than `working tree` when the plan is
committed (`doc-review/SKILL.md:201`).

**Cards:** 934, in part — see the follow-up map.

**Execution note:** card 934's cleanup amendment reports that the rubric-engine docstring's "wrong
path" and "stale dispatch-table line count" could not be located in `lifecycle_review.py`; a read
of its lines 1-43 at this branch confirms the docstring names a by-convention path and carries no
line count. That item is dropped as not present, which is what the amendment instructs. Do not
consolidate the six copies of the lifecycle-position prose, and do not give Document Review
saga-state write authority.

**Test scenarios:**
- `tests/test_doc_review_maintenance.py::test_no_file_describes_review_as_a_phase_entered` —
  neither `work/SKILL.md` nor `references/saga-spec.md` describes `review` as a phase Document
  Review enters or writes. `loop/SKILL.md` is excluded by name with the reason, so the exclusion is
  a recorded decision rather than an omission.
- `tests/test_doc_review_maintenance.py::test_no_write_path_to_the_review_phase_was_added` — no
  saga script writes `lifecycle_phase=review`.
- `tests/test_doc_review_maintenance.py::test_latest_matching_artifact_is_defined` — both
  conventions are written down and the ambiguity rule is stated.
- `tests/test_doc_review_maintenance.py::test_committed_plan_records_a_sha` — the artifact contract
  names a commit SHA for a committed plan.

### U8. Delete `team_emitter.py` and `spec_table.py`

**What:** Delete `plugins/saga/scripts/team_emitter.py` (407 lines) and
`plugins/saga/scripts/spec_table.py` (321 lines). Delete `tests/test_team_emitter.py` and
`tests/test_spec_table.py`, which exist only to test them. Repair the three other importers by
name: `execution_spec.py:2664` loads `team_emitter` lazily by file path and that branch is removed
with the team-emission path it serves; `tests/test_workflow_extraction.py:293` loads
`team_emitter` and its case is deleted with the module; and
`tests/test_fleet_core_execution_classes.py:144` loads `team_emitter.py` as a consumer fixture and
is retargeted at a surviving fleet-core consumer. `spec_table.py`'s only importer besides its own
test is `work/SKILL.md:400`, which U1 moves into the reference file, where the line is deleted
rather than relocated because the script it invokes will not exist.

**Cards:** 1026, and 808 for the prose the deleted commands appeared in.

**Execution note:** `execution_spec.py` is not touched beyond removing the one lazy-load branch —
see KTD1 and the operator question below.

**Test scenarios:**
- `tests/test_saga_script_surface.py::test_removed_modules_are_not_importable` — neither
  `team_emitter` nor `spec_table` imports, and no surviving file under `plugins/` or `tests/`
  names either.
- Mutation proof: restoring either file's name in a surviving importer fails that test.

### U9. Release surfaces

**What:** Bump `plugins/saga/.claude-plugin/plugin.json` from `0.164.0` to `0.165.0`, add the
matching `plugins/saga/CHANGELOG.md` entry, update `.claude-plugin/marketplace.json`, and update
any version drift-guard test that names the version.

**Cards:** 1026.

**Execution note:** this card ships onto the integration branch `parent/1018` alongside siblings
that also bump saga. If a sibling lands the same version first, re-bump at merge time rather than
editing the sibling's entry — the release-surface diff guard compares against the pull request's
base, so a split release can require a second bump.

**Test expectation:** none — release metadata, covered by the repository's existing drift-guard
tests.

## Prerequisites and what this unblocks

**Upstream, already merged into this card's base `parent/1018` at `4e951f0e`:** issue 1023's run
record and admission questionnaire (`plugins/saga/scripts/run_record.py`,
`plugins/saga/scripts/admission.py`, `plugins/saga/references/run-record.md`), which this plan's
KTD2 and KTD3 read; and issue 1024's roster helper
(`plugins/agent-launcher/skills/agent-launcher/scripts/roster.py`) with issue 1022's roles library
(`plugins/agent-launcher/roles/plan-reviewer.md`), which U2 dispatches through. Nothing here waits
on an unmerged card.

**In flight beside this card, and the one line of contact with each:** issue 1001 rewrites
`plugins/saga/skills/code-review/` — see U6's open question; issue 1025 rewrites
`plugins/orchestrate/`, which this card does not touch at all.

**Downstream, unblocked by this merge:** issue 1029 (continuation mechanics) edits the endings of
the same three skills and the design section above names where each ending is; issue 1030 (the
removals) inherits `execution_spec.py` per KTD1.

## Test Strategy

No file matching `tests/test_doc_review*.py` exists at this branch, so the card's third acceptance
criterion matches nothing today and is satisfied by the four files this plan creates —
`test_doc_review_loop.py`, `test_doc_review_rubric_resolution.py`, `test_doc_review_transport.py`,
and `test_doc_review_maintenance.py`. The `tests/test_plan*.py` half of that glob matches two
existing files, `test_plan_artifact_conformance.py` and `test_plan_pre_answers.py`, which must stay
green.

Every test above runs against a temporary store and never touches a live herdr session, a live
board, or the primary checkout's run-record directory. The roster helper is exercised through its
module-level functions with a constructed record, never by calling `up`, because `up` creates panes.

The card's fourth acceptance criterion — a real `/plan issue <N>` run ending in a plan-review pass
or a named `P0`/`P1` without the operator typing `/doc-review` — is proved in the work stage
against **this branch's** copy of `plugins/saga/skills/plan/SKILL.md`, not the installed plugin at
`~/.claude/plugins/cache/infiquetra-plugins/saga/0.159.2/`, which does not carry the change. The
proof is: pick an issue with a written card, run the repository's copy of the skill through to its
new Phase 5.4, and record the result — the reviewer chosen, the branch of KTD2's rule taken, the
`review_cycles` entries written, and the verdict — in that issue's run record and in the work
session writeup. A run that ends in a named `P0` satisfies the criterion exactly as a pass does;
what must not happen is the operator typing a command to make the review occur.

## Child card map

| Card | What it asks for | Where it lands | Closes on this merge? |
|---|---|---|---|
| 931 | Finish issue 776's Document Review half: the operator-is-the-transport clause, a general prohibition replacing two dead script names, the dangling cross-reference, the retired external-reviewer dispatch | U6 | Yes on the Document Review side; its one `code-review/SKILL.md` line waits on the coordinator's answer in U6 |
| 932 | The rubric command resolves from any working directory, fails loud, extras conditions before selection, `--doc-review-fixes` | U5 | Yes |
| 933 | The plan-review loop is the repair protocol; an explicit submission is always reviewed | U2, U3, U4 | Yes |
| 934 | The never-written `review` phase, artifact-matching conventions, the default-mode wording, the commit SHA | U7 | No — see below |
| 808 | Relocate the Workflow-backend prose to a reference file | U1, U8 | Already closed (2026-08-25, pull request 833); this card completes the relocation its NARROW ruling implied |

**Card 934 does not close on this merge.** Its descriptions, conventions, wording, and commit-SHA
items are all done in U7, but it carries one unresolved operator decision — whether `/doc-review`
or `/work` should write `lifecycle_phase=review` so the stored state matches the lifecycle
chapter. Two authorities point opposite ways (the lifecycle repository's `docs/process/gates.md`
says the doc-review gate advances the phase; card 920's non-goal forbids giving Document Review
that write authority), and this plan has no authority to choose between them. The follow-up is a
one-question card: *does the run record's phase advance at plan review, and which step writes it?*

**Files this card removes, and the card that names each:**

| File | Named by |
|---|---|
| `plugins/saga/scripts/team_emitter.py` | 1026 (its "Files expected to change"), 933 |
| `plugins/saga/scripts/spec_table.py` | 1026, 933 |
| `tests/test_team_emitter.py` | implied by 1026's removal of the module it tests |
| `tests/test_spec_table.py` | implied the same way |
| `plugins/saga/scripts/execution_spec.py` | 1026 and 1030 both name it; **this plan leaves it to 1030** per KTD1 |

**Importers repaired rather than removed:** `plugins/saga/scripts/execution_spec.py:2664` (the lazy
`team_emitter` load), `tests/test_workflow_extraction.py:280,293`,
`tests/test_fleet_core_execution_classes.py:144`, `tests/test_saga_plugin.py:120-140`,
`plugins/saga/skills/work/SKILL.md:400`.

## Lens applicability declaration

Every lens in the lifecycle repository's catalogue at revision `5efc869f`, with one line each.

| Lens | Applies | Reason |
|---|---|---|
| architecture-maintainability | Yes | Always-on; no declaration may deselect it. |
| correctness | Yes | Always-on. |
| security | Yes | Always-on. |
| testing | Yes | Always-on. |
| documentation-clarity | Yes | The change rewrites operator-facing instructions and creates a reference document. |
| agent-usability | Yes | The change alters skills and prompts an agent consumes. |
| api-contract | Yes | Deleting two scripts removes command-line contracts other callers invoke. |
| deployment-infrastructure | No | No infrastructure, deployment configuration, migration, or rollout order changes. |
| reliability | No | No failure handling, asynchronous work, concurrency, retries, or recovery code changes. |
| performance | No | Prose and script removal; no latency, throughput, query, or memory behaviour changes. |
| adversarial | No | No money, no mutation of external state, no external integration; the one authority boundary is the operator's override word and is unchanged in kind. |
| privacy | No | No personal or sensitive data is collected, used, shared, retained, or deleted. |
| previous-comments | No | This card carries no prior pull-request review comments. |
| accessibility-human-usability | No | No visual or interactive surface changes; the command-surface change is covered by agent-usability and documentation-clarity. |
| experience | No | No user-facing product surface and no change to the path a person takes through one. |

## Preflight evidence

| Check | Environment | Time | Observed by | Outcome | Validity |
|---|---|---|---|---|---|
| The card passes the mission-control validator | this worktree | 2026-09-19 | admission | passed | stable for the run |
| The base is `parent/1018` at `4e951f0e` | this worktree | 2026-09-19 | the driver | confirmed | stable for the run |
| The pinned development dependencies install | this worktree | 2026-09-19 | `uv sync --locked --extra dev` | succeeded | environment-bound |
| The lifecycle repository is reachable at revision `5efc869f` | local checkout at `../infiquetra-sdlc` | 2026-09-19 | `git show 5efc869f:docs/reviewers/plan-review.md` | resolved | stable for the run |
| The run record wrote to the primary checkout's store | `/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1026.json` | 2026-09-19 | `admission.py` | written | stable for the run |
| A herdr pane is available for a Plan Reviewer seat | this session | 2026-09-19 | the driver | **deferred** — checked at dispatch by `roster.py`, which returns exit 4 outside a pane; the fallback branch is written and tested | deferred to the work stage, run by the implementing worker |

## Admission answers

<!-- gate-record: id=plan-1026-admission-answers-without-a-live-operator absence=HALT transport=ask-user-question -->

Every answer below was taken from a named source, because `AskUserQuestion` was not available in
this session. The record is at
`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1026.json`.

| Parameter | Answer | Source |
|---|---|---|
| Risk tier | `medium` — it changes the entry of every run; the floor gate's blocking behaviour is preserved and tested | the card's own Risk section |
| Approval-boundary scopes | All seven scopes granted as `none`; production, destructive actions, credentials, permissions, billing, external commitments, process authority, and any plan-review or code-review override stop and ask the operator | the operator's standing list for this run, relayed in the driver's assignment |
| Destination | `pr` — the parent branch `parent/1018`, whose single pull request is issue 1030 | the driver's assignment and the pre-answer carrier |
| Staffing overrides | none | the driver's assignment |
| Lens declaration | four always-on plus documentation-clarity, agent-usability, api-contract | the lifecycle repository's `config/lens-catalogue.json` at revision `5efc869f`, applied to this change |
| Repair allowances | 3 standard, 2 escalated | the lifecycle repository's `config/run-model.json` at revision `5efc869f`, items `RC-standard-phase-cycle-allowance` and `RC-expert-phase-cycle-allowance` |
| Unfinished functional testing | bring the result to the operator | the lifecycle repository's `RC-unfinished-testing-response` closed set, first option |
| Branch preview | none | filled by the repository profile, not asked |
| `main` consumed directly | no | filled by the repository profile, not asked |
| Change shape | mixed — skill prose and scripts removed | the card's "Files expected to change" |

The thirteenth run-configuration parameter, `per_lens_score_threshold`, is the one admission left
unfilled; it belongs to code review and is issue 1001's to set.

## Questions answered from the card

| Question the skill would ask | Answer taken | Source |
|---|---|---|
| Phase 0.4, is a plan document warranted? | Yes | Nine units, eight key technical decisions, four folded child cards — none of the skip conditions holds. |
| Phase 0.5, scope class? | Deep | The change is cross-cutting: three skills, two plugins' tests, and a sequencing decision against a sibling card. |
| Phase 5.1, destination? | `pr` | The pre-answer carrier, validated by `plan_pre_answers.py` (exit 0, applied `destination: pr`). Admission had already recorded it. |
| Phase 5.2, execution backend? | `inline` | The same carrier, applied and narrated. The Workflow backend is never pre-selected and was not offered. |
| Phase 5.2, is the Workflow tool available? | Not probed | No explicit Workflow invocation is made, so the probe's precondition does not arise. |
| Phase 0.2, handoff maturity? | `requirements-ready`, `can_plan: true` | `parse_issue.py --issue 1026`. |
| Phase 0.3, resume an existing saga? | No — mint | `saga.py scan` returned zero candidates. |

No question about production, destructive operations, credentials, permissions, billing, external
commitments, or process authority arose, and none was answered on the operator's behalf.

## Operator questions this plan does not answer

<!-- gate-record: id=plan-1026-execution-spec-sequencing absence=HALT transport=ask-user-question -->

**One question stops rather than defaulting: does `execution_spec.py` get deleted by this card or
by issue 1030?** The evidence for issue 1030 is in KTD1 — seven live saga importers, every one of
them already on 1030's removal list, plus about thirty test modules. This plan is written for the
issue-1030 answer, which means the card's second acceptance criterion
(`test ! -f plugins/saga/scripts/execution_spec.py`) does not pass on this card's merge and should
be amended to name 1030. If the operator prefers this card to delete it, unit U8 grows to include
the seven importers, their commands, and roughly thirty test modules, and the card's risk tier
should be raised from medium. The plan does not take either answer on the operator's behalf.

## Scope Boundaries

**Out of scope, and staying out:**

- The review rubric's content and its severities. This card changes when review runs, never what it
  looks for.
- Any automatic override of an open `P0` or `P1`. The operator's word is the only way past.
- `plugins/saga/references/engine-registry.yaml`, which stays as capability metadata with its
  readers intact.
- Document Review's single-pass behaviour within one cycle. The loop is around the review, not
  inside it.
- A durable applied-or-skipped lens record and any lens census; card 932's settled decision D-D4
  defers both.
- Saga-state write authority for Document Review.
- The six hand-maintained copies of the lifecycle-position prose; card 934's settled decision D-D6
  rejects consolidating them.
- `plugins/saga/skills/code-review/` entirely, which issue 1001 owns; the one line card 931 wants
  changed there is raised to the coordinator in U6, not taken.
- `plugins/orchestrate/`, which issue 1025 owns.
- The endings of these three skills as a continuation mechanism; issue 1029 owns that and this plan
  names where each ending is so it can find them.

**Deferred to follow-up work:**

- `plugins/saga/scripts/execution_spec.py`'s deletion, to issue 1030, pending the operator question
  above.
- Card 934's phase-write decision, to a new one-question card.

## Risk Analysis and Mitigation

| Risk | How it shows up | Mitigation |
|---|---|---|
| The floor gate is weakened while being described | `/work` executes on an open `P0` and nobody notices until a bad plan ships | U4's test is written first and watched failing against a deliberately weakened copy before it is trusted |
| The relocated prose is edited while being moved | A contract changes invisibly inside a large move diff | KTD5: move verbatim, and the two retargeted tests assert the same ordered command list at the new location |
| A sibling card edits the same file first | Issue 1001 rewrites `code-review/SKILL.md` while U6 edits one clause in it | U6 adopts whichever general prohibition landed first and asserts the match rather than writing a second version |
| The card's acceptance criterion cannot pass as written | The merge is judged red on criterion two | Raised as an operator question rather than silently redefined |
| The plan-review loop runs away | A review and repair cycle repeats without converging | The bound comes from the run record's recorded allowances, and exhaustion stops and reports rather than passing |

## Alternatives Considered

**Delete `execution_spec.py` here and carry the cascade.** Rejected for sequencing, not for
principle: it pulls seven modules and about thirty test files out of issue 1030 into a card scoped
as three skills, and reaches an end state issue 1030 reaches anyway. Recorded as the operator's
alternative in the question above.

**Leave the Workflow prose in place and only add the review loop.** Rejected because the card and
the simplification review both name the relocation, and because the two changes touch the same two
sections of `/work`; splitting them would mean editing `work/SKILL.md` §1.3 to §1.5 twice.

**Summarize the relocated prose in the skills rather than pointing at the reference file.**
Rejected: a summary of a contract is a second source, and second sources drift. KTD5.

**Make the plan-review loop a new script.** Rejected: the loop is a sequence of skill steps with
its state already carried by the run record's `review_cycles`; a script would add a module whose
only caller is a prompt.
