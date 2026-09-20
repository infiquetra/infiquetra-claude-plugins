---
title: Issue 938 — Remove Work's in-process external-engine second-opinion offer and its feature-private machinery
type: refactor
status: active
date: 2026-09-20
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Issue 938 — Remove Work's in-process external-engine second-opinion offer and its feature-private machinery

## Summary

The Saga Work skill in this repository still offers to ask an outside engine for a second opinion
when the same test fails three times, and one Python module, `plugins/saga/scripts/second_opinion.py`
(2,076 lines), carries everything behind that offer. This plan removes the offer and that module,
keeps the external-content trust boundary and every shared component that still has a real caller,
and proves both halves with tests.

## Problem Frame

Work carries a narrower, older way to get an outside opinion than the one the operator actually
uses. The operator's model is a named review session run by the Orchestrate plugin; Work's model is
an in-process function call that prepares a request, reserves a claim, calls a runner, and writes a
sidecar file beside the work-session note. Issue #776 retired the transport that older path once
launched through, and kept Saga's ownership of review *policy*; it did not decide the fate of this
evidence mechanism. Issue #1001 removed the review side — the code-review skill's "External
whole-diff advisory seat" and the two classes behind it — and deliberately left Work's offer and
`second_opinion.py` for this card, because neither file appears in issue #1001's own list of files
and nothing goes that a card does not name.

What is left is a feature nobody reaches. The review panel's call sites are gone. The module's
remaining importers are its own two test files. Its offer line is still printed by Work's prose, so
the feature is live in the only sense that matters for a prompt surface: an agent reading the skill
will still try to run it.

**The risk of this card is removing one component too many.** The external-content trust boundary —
the rule that an outside engine's text is data and never a command, a path, or a gate token — is
cited by three places that have nothing to do with Work's offer. Removing it would break all three.
Every component this plan removes is shown to have no caller; every component it keeps is named with
the caller that still needs it and the test that proves that caller passes.

## Admission answers

<!-- gate-record: id=issue-938-admission-card-risk-section absence=HALT transport=ask-user-question -->

**The repository's own admission step refused to run, twice, and wrote nothing.** Both the dry run
and the real run exited 2 with one line on standard error:

```text
admission: the card is not ready and admission writes nothing: Missing required H3 sections: ['Risk']
```

The refusal is correct and is not a defect in the admission script. Issue 938 was filed before the
card template gained its three late sections; its body carries eight level-three headings
(`Objective`, `Intent`, `Out-of-scope / non-goals`, `Files expected to change`, `Tests to add or
update`, `Context library links`, `Acceptance criteria`, `Verification`) and none of them is `Risk`.
Its sibling card, issue 1001, carries eleven headings including `Risk`, `Failure modes / pre-mortem`
and `Stop conditions`, which is why admission ran for that card and not for this one. Because the
card validator is the first thing `plugins/saga/scripts/admission.py` runs, no run record exists for
issue 938 and there is no record path to quote.

The operator question this raises — amend the card body on GitHub so admission can run, or let this
card proceed on a recorded refusal — is not one this driver may answer for itself: editing a card on
the board is board authority, and the run's standing approval list stops at process authority. It is
carried to the operator, and planning continued so the stage still returns.

The answers below are therefore recorded here, in the plan, rather than in a run record. Each names
its source.

| Admission question | Answer | Source |
|---|---|---|
| Risk tier | `medium` | The card names no `Risk` section. The run's standing rule sets `medium` in that case, because the risk the card states in its own Intent is "removing one component too many". |
| Approval-boundary scopes | Production, destructive actions, credentials, permissions, billing, external commitments, process authority, and any plan-review or code-review override all stop and ask the operator. Nothing else does. | The operator's standing list for this run, carried in the coordinator's instruction. |
| Destination | `pr` | The structured pre-answer carrier, schema `plan_pre_answers.v1`, from the run driver; the validator applied it and exited 0. The pull request is the single one issue 1030 opens for the integration branch `parent/1018`. |
| Staffing overrides | None; take the defaults. | The coordinator's instruction for this card. |
| Lens declaration | The four always-on lenses plus four conditional ones. See the table below. | `plugins/saga/skills/code-review/references/lens-execution.md:44-66`, the catalogue's own list. |
| Repair allowances | Three standard cycles and two escalated. | The lifecycle defaults pinned in `plugins/saga/scripts/admission.py:59-70` (`standard_cycle_allowance: 3`, `escalated_cycle_allowance: 2`). |
| Response to unfinished functional testing | Bring the result to the operator. | The lifecycle pins no default for this one. Chosen because this card's product *is* a set of tests that prove an absence; a test that could not finish leaves the central claim unproven, and continuing repair toward it would be repairing against an unknown. |
| Repository has a branch preview deployment | No | This repository ships Claude Code plugins through a marketplace file; there is no deployed branch preview anywhere in it. |
| Repository's main branch is consumed directly | Yes | Installed plugins resolve from the marketplace registry that tracks `main`; a merge to `main` is what an installation sees. |
| Change class | Code | The card's own "Files expected to change" list is led by a Python module removal and a skill file edit. |

**The lens declaration.** Four always-on: `architecture-maintainability`, `correctness`, `security`,
`testing`. Four conditional lenses apply, each with the catalogue condition that selects it:

| Conditional lens | Why it applies here |
|---|---|
| `adversarial` | The change is a large removal that touches a policy and a gate: 2,076 lines of module go, and one of the two call sites the trust-boundary guard scans goes with them. |
| `api-contract` | A Python module that other code and prose name by its exported function names is deleted; that is an exported-contract change. |
| `documentation-clarity` | Two prompt surfaces and one contract document are edited — Work's skill, its continuation reference, and the trust-boundary document's source table. |
| `agent-usability` | The thing being removed is a capability an agent discovers and operates from the Work skill's prose. |

Seven conditional lenses are left out, one recorded line each:
`deployment-infrastructure` — nothing deployed, migrated or rolled out changes.
`reliability` — no failure handling, concurrency, retry or recovery path outside the removed module changes.
`performance` — no latency, throughput, query, memory or cost path is touched; deleted code has no runtime cost.
`privacy` — no personal or sensitive data collection, retention, telemetry or residency is involved.
`previous-comments` — no pull request with prior review threads exists for this card yet.
`accessibility-human-usability` — no human-operated visual or interactive surface is affected.
`experience` — no user-facing surface and no path a person takes through one changes.

**The card's operator-approval sentence is already satisfied.** The card says the removal "needed the
operator's approval to proceed". That approval exists: the card is filed, it sits on the Operations
board under the `improve-claude-plugins` Objective, and it falls inside the operator's standing
instruction to work every card in this tree. It is not re-asked.

## Questions answered from the card

The installed plan skill puts five questions to an operator. `AskUserQuestion` is unavailable in this
session, so each was answered from the card, the code, or a runnable script, and each answer is
recorded here.

| Question the skill asks | Answer taken | Where the answer came from |
|---|---|---|
| Is a plan document warranted (Phase 0.4)? | Yes | The work has unit boundaries (a prose edit, a module deletion, a guard narrowing, a test suite, release surfaces), and it carries load-bearing decisions about what survives. It is not atomic. |
| Scope class (Phase 0.5) | Standard, five units | The coordinator set complexity triage to medium; the work is a bounded removal with a consumer inventory, not a cross-cutting design. |
| Resume or mint a saga (Phase 0.3)? | Mint | `saga.py scan` returned `{"candidates": [], "count": 0}` — no existing saga matches this thread. |
| Destination (Phase 5.1) | `pr` | Applied at intake from the `plan_pre_answers.v1` carrier supplied by the run driver; the skill's own rule is to skip the question when the carrier applied it. |
| Execution backend (Phase 5.2) | `inline`, chosen; `team-execution`, recommended | The carrier applied `inline`. The recommender was still called, as the skill requires: `lifecycle_state.py recommend-backend --file-count 12 --phase-count 5` returned `team-execution` with the rationale "size/risk or consensus signal". The carrier never applies the other two backends. |

No question touching production, destruction, credentials, permissions, billing, an external
commitment, or process authority was answered here. The one question that does touch process
authority — whether to amend card 938's body so the admission step can run — is carried to the
operator above, unanswered.

## Requirements

R1. Work offers no in-process external-engine second opinion by any route: not in
`plugins/saga/skills/work/SKILL.md`, not in `plugins/saga/skills/work/references/pr-continuation-loop.md`,
and not through any module a reader of those files could reach.

R2. No feature-private dispatch, sidecar, streak, or state module for the removed feature survives. A
test fails if `plugins/saga/scripts/second_opinion.py` is still importable or still on disk.

R3. Every retained shared component is named with a live consumer and the passing test that proves
that consumer works. The inventory is explicit and enumerated, never "the module imports".

R4. The external-content trust boundary survives. Its document,
`plugins/saga/references/engine-output-trust-boundary.md`, is not deleted, and its three consumers
still pass.

R5. Work's merge confirmation, its typed review outcomes, and the rule that a programmatic code
review writes nothing durable are unchanged, pinned by an anti-regression test.

R6. The deferred external-seat claim lifecycle (the code-review parent's decision C-D10) is recorded
as moot in `docs/engineering-journal/DECISIONS.md` rather than built.

R7. The Saga Document Review parent is notified by an issue comment that its deferral trigger has
fired. No prose in that parent's skill is changed by this card.

R8. Release surfaces stay aligned in the same change:
`plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`, and
`.claude-plugin/marketplace.json`.

R9. Mutation proof: re-adding the offer line to Work's skill makes the no-offer test fail. The
failure is observed, not asserted.

R10. Tests write only under `tmp_path`. Nothing in this card writes to the primary checkout's saga
store.

## Key Technical Decisions

**KTD1 — Delete the whole module, not part of it.** Every public name in
`plugins/saga/scripts/second_opinion.py` was checked for callers outside itself. Thirteen exported
names were counted across `plugins/`, `tests/`, `scripts/` and `tools/`, excluding the module itself
and changelog files. **Ten have zero outside references.** The three that have any are all inside
sites this card itself removes: `FindingSnapshot` and `SourceExcerpt` appear once each, both in
`tests/test_work_second_opinion.py`, which U2 deletes; `WorkAttempt` appears three times — once in
Work's own prose, which U1 removes, once in `tests/test_work_second_opinion.py`, and once in the
`tests/test_saga_plugin.py` test that U1 removes. There is no surviving fragment worth keeping, so
the file goes whole rather than being hollowed out.

**KTD2 — The trust boundary is a document and a guard, not a module, so it survives the deletion
untouched in substance.** This is the fact the card warns about, and it was verified rather than
assumed. The boundary is `plugins/saga/references/engine-output-trust-boundary.md` plus
`tests/test_engine_output_trust_boundary.py`, whose guard scans a tuple of exactly two Python files
(`tests/test_engine_output_trust_boundary.py:41`): `engine_dispatch.py` and `second_opinion.py`.
Removing the second file narrows the scanned tuple to one entry. The document, the guard, the
adversarial fixture, and the two team-execution references are all untouched by the deletion itself.
The parent card's claim was correct.

**KTD3 — The document's source table is corrected, never trimmed.** One row of the trust-boundary
document names `plugins/saga/scripts/second_opinion.py` as a source of untrusted text
(`plugins/saga/references/engine-output-trust-boundary.md:11`). After the deletion that file name is
wrong. The row itself must stay: the guard asserts the anchor `external_opinion.findings[].content`
is present in the document, and Document Review's skill still defines that field. So the row keeps
its field and its required handling, and only its Source cell changes to name the surviving carrier —
the enriched review artifact — with the deleted script's name dropped. Deleting the row would remove
a piece of the boundary and break the guard, which is precisely the failure this card is warned
about.

**KTD4 — `tests/test_saga_second_opinion.py` is rewritten, not deleted.** Five tests live in it. Two
are about the deleted module and go with it. Three are about things that survive and must keep
passing: the review skills halt rather than naming a launch command line, the operator-absence gate
record survives, and an advisory reviewer or panel can never satisfy a gate
(`engine_dispatch.NON_GATING_ROLE_KINDS`). The file drops its import of the deleted module, loads
`engine_dispatch.py` directly, keeps those three, and gains the on-disk absence assertion for the
deleted file — which places the module's own tombstone beside the transport tombstones already
there.

**KTD5 — The no-offer test reads the shipped prose, because prose is the feature.** Work's offer is
not a function an agent calls; it is a line an agent is told to print. So the negative test asserts
over the text of `plugins/saga/skills/work/SKILL.md` and its continuation reference: the exact offer
line is absent, the section heading is absent, and no name exported by the deleted module appears.
Asserting that a Python import fails would not catch a skill that still tells an agent to do it by
hand.

**KTD6 — The retained-component test enumerates, it does not sample.** R3 says "named live consumer
whose test passes". The test therefore carries a table of retained component to consumer to proving
test, and runs each proving test's file as a real dependency assertion — a component whose named
consumer disappears fails the test by name, which is what makes the inventory a safety net rather
than a comment.

**KTD7 — Work's file is edited narrowly, because a sibling card edits the same file.** Issue 1029
rewrites the ending of every lifecycle skill, including
`plugins/saga/skills/work/SKILL.md`. This card touches only the offer's own prose and its routing:
the `## Second-opinion triggers` section in its entirety, and the one sentence inside
`## Reviewer-session transport` that points at it ("The second-opinion trigger below never
replaces..."). Nothing else in that file is edited by this card. Whichever of the two cards lands
second resolves the conflict, as the card itself says.

**KTD8 — The saga version is taken at merge time, not at plan time.** The base commit `b98e94ea`
carries saga 0.166.0. Sibling card 1025 lands before this one and takes 0.167.0, so this card takes
0.168.0. Sibling version collisions on this integration branch have landed silently before, so the
version is re-checked and re-bumped at the merge turn rather than trusted from planning.

**KTD9 — The journal entries ship with the change, not with this plan.** The plan skill records key
technical decisions to `docs/engineering-journal/DECISIONS.md` at planning time. This repository's own
rule is narrower and wins here: a journal entry lands "in the same commit that ships the change". So
the entries are authored in U5, in the work stage. The practical reason is ordering — the repository
runs a journal-order lint on pull requests, and sibling cards are writing to the same two journal
files in parallel, so an entry written a stage early is an entry that has to be rewritten at the
merge turn.

## Implementation Units

### U1. Remove the offer from Work's prose and its continuation reference

**What:** Delete the `## Second-opinion triggers` section of
`plugins/saga/skills/work/SKILL.md` — everything from that heading up to, but not including, the
`---` rule that precedes `## Phase 0 — Enter, scan the saga, triage, detect round-N` — and the single
sentence in `## Reviewer-session transport` that refers forward to it ("The second-opinion trigger
below never replaces `/work`'s backend choice and never satisfies a gate."). Delete the
`## Repeated-failure second-opinion sidecar` section of
`plugins/saga/skills/work/references/pr-continuation-loop.md`, from that heading up to but not
including `## Between-rounds tier escalation proposal`. Nothing else in either file changes.

**Locate both sections by heading, never by line number.** On the base commit `b98e94ea` they begin
at `plugins/saga/skills/work/SKILL.md:113` and
`plugins/saga/skills/work/references/pr-continuation-loop.md:49`, but sibling card 1029 edits the
first of those files, so a line number recorded here may be stale by the time this unit runs. The
headings are stable; the offsets are not.

**Why it is safe:** neither section contains an `AskUserQuestion` mention or a gate marker, so the
gate-absence lint's baseline count of 3 for `plugins/saga/skills/work/SKILL.md` is unaffected. The
three mentions it counts all live in the `## Interaction method` section, which this unit does not
touch.

**Also in this unit:** remove `test_work_second_opinion_trigger_contract_is_operator_confirmed_and_non_gating`
from `tests/test_saga_plugin.py` — it is the test that asserts the offer exists, so it cannot survive
the offer. Leave `test_document_review_second_opinion_contract_is_intact` in place: it pins Document
Review's half, which this card must not touch.

**Test scenarios:** `tests/test_work_second_opinion_removed.py` — the exact offer line
("Second opinion available: {target} failed after 3 fix attempts; dispatch an advisory second
opinion?") is absent from both files; the heading `Second-opinion triggers` is absent; none of the
deleted module's exported names (`WorkAttempt`, `load_work_second_opinion_state`,
`save_work_second_opinion_state`, `record_work_attempt`, `accept_work_offer`,
`prepare_second_opinion`, `dispatch_second_opinion`, `record_work_dispatch_outcome`,
`complete_second_opinion`) appears in either file; and the string `saga.work-second-opinion.v1`
appears nowhere under `plugins/saga/skills/work/`.

### U2. Delete the module and its two dedicated test files

**What:** Delete `plugins/saga/scripts/second_opinion.py` (2,076 lines) and
`tests/test_work_second_opinion.py`. Rewrite `tests/test_saga_second_opinion.py` per KTD4: drop its
module load and its two module-specific tests, load `engine_dispatch.py` directly for the surviving
non-gating assertion, keep the three surviving tests, and add the deleted file's on-disk absence to
the tombstone assertions already in `test_second_opinion_module_does_not_import_retired_transport`.
Rename that test to say what it now covers.

**Why it has no consumer:** counted on the base commit, excluding the module itself and changelog
files, thirteen exported names have zero references anywhere in `plugins/`, `tests/`, `scripts/` or
`tools/` except inside the two test files this unit removes or rewrites and Work's prose that U1
removes. `SecondOpinionClaimStore`, the claim state machinery, is referenced only from within
`second_opinion.py` itself.

**Test scenarios:** `tests/test_work_second_opinion_removed.py` — importing
`plugins/saga/scripts/second_opinion.py` by file path raises because the file does not exist; no file
named `second_opinion.py` exists anywhere under `plugins/`; no sidecar-state schema string
`saga.work-second-opinion.v1` appears anywhere under `plugins/` outside `CHANGELOG.md`; and no Python
file under `plugins/` imports a module named `second_opinion`.

### U3. Keep the trust boundary: narrow the guard, correct the document's source row

**What:** In `tests/test_engine_output_trust_boundary.py`, drop `SECOND_OPINION_SCRIPT` from the
`PYTHON_CALL_SITES` tuple and from the module constants, so the lint scans the one surviving call
site. Keep `test_lint_catches_second_opinion_content_interpolation` — its fixture is a literal source
string with an `item.content` attribute and does not depend on the deleted file; rename it so it
describes the rule rather than the departed module. In
`plugins/saga/references/engine-output-trust-boundary.md`, change only the Source cell of the
`external_opinion.findings[].content` row to name the enriched review artifact, dropping the deleted
script. The field name, the required handling, every forbidden sink, and every other row are
untouched.

**Test scenarios:** the existing file's own tests, unchanged in intent and re-run:
`test_contract_document_names_untrusted_fields_and_forbidden_sinks` still finds all nine anchors
including `external_opinion.findings[].content`; `test_team_execution_references_point_to_trust_boundary_contract`
still passes; `test_lint_passes_clean_code` passes over the narrowed tuple; the three seeded-unsafe
fixtures still turn the guard red; and `test_adversarial_fixture_renders_as_data` still proves a
booby-trapped payload stays inert through the bound reconciliation gate.

### U4. The retained-component inventory, the anti-regression pin, and the mutation proof

**What:** Add `tests/test_work_second_opinion_removed.py` in full. Beyond the negatives U1 and U2
specify, it carries three positive bodies.

The **retained-component enumeration** asserts each row of the inventory in the section below, one
explicit assertion per row, never a loop over a directory. Each row asserts three things: the
retained component's file exists; the named consumer file exists and still contains the reference
that makes it a consumer (the cited path string, import, or symbol); and the proving test file exists
and still defines the named test function. It does **not** run pytest inside pytest — the proving
tests pass by being in the same suite, and this test's job is to make a vanished consumer or a
renamed proving test fail loudly by name rather than disappear quietly.

The **anti-regression pin** asserts that `plugins/saga/skills/work/SKILL.md` still contains the
merge-confirmation sentence ("PR-open, review-request, and merge are each explicitly confirmed"), the
typed review outcome token `review_result.v1` with its gate heading "Outcome-driven review gate",
and the programmatic-review rule ("writes nothing durable" together with "the caller owns
persistence"). These are the three behaviours the card forbids this change from touching, and this
card edits that file, so the pin is required rather than decorative.

The **mutation proof** is a test that copies Work's skill into `tmp_path`, appends the exact offer
line back into the copy, runs the no-offer predicate against the copy, and asserts it fails. The
predicate is a module-level function in the test file so both the real assertion and the mutant call
the same code — a proof that pins a separate copy of the rule proves nothing.

**Watch it fail before it passes:** the no-offer test is written and run against the unmodified tree
first, and must fail there, before U1 and U2 remove the offer. The observed red — the command, its
failure output, and the commit it ran against — is recorded in the work-session note at
`docs/work-sessions/2026-09-20-issue-938-remove-work-second-opinion-offer.md`.

**Test scenarios:** all of the above live in `tests/test_work_second_opinion_removed.py`. Its name
matches what it guards — the removal of Work's second-opinion offer — in the file name, the test
names, and the failure messages.

### U5. Journal, release surfaces, and the Document Review notification

**What:** Add a `docs/engineering-journal/DECISIONS.md` entry recording that the external seat's
deferred claim lifecycle (the code-review parent's C-D10) is now moot: its two triggers were a first
standalone use and an observed duplicate launch, and with the surrounding machinery deleted neither
can occur, so the lifecycle collapses to nothing and is recorded rather than built. Add a
`docs/engineering-journal/LEARNINGS.md` entry with the evidence, the mechanism, and the one-line
generalizable rule for the finding that a trust boundary held as a document plus a scanning guard
survives the deletion of one scanned call site, where a boundary held as a shared module would not
have.

Correct the one forward-pointing cross-reference this card's landing makes stale. The code-review
skill's findings schema, `plugins/saga/skills/code-review/references/findings-schema.md:242-244`,
currently tells the reader that removing Work's offer "is **issue 938**, not this card". Once this
card lands, that sentence points at work already done. Rewrite it in the past tense, naming this card
as the one that did it and keeping issue 1001's reason for having left it alone. This is a one-line
prose correction inside a file this card is otherwise not editing, and it is here because a stale
forward pointer is exactly the drift the engineering journal exists to catch.

Bump `plugins/saga/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to the next
saga version and add the matching `plugins/saga/CHANGELOG.md` entry, re-checking the number at the
merge turn per KTD8.

Post one comment on the live parent of the Document Review children telling it the deferral trigger
has fired. **The parent to notify is issue 1026, "Plan continues into plan review"** — verified
through the GitHub sub-issue graph: it is the current parent of issues 931, 932 and 934, the three
open Document Review cards. The original Document Review parent named by the card, issue 920, is
closed and superseded by the simplification tree, so it is named in the comment for traceability but
is not the notification target. The comment states plainly that Document Review's skill still
describes a claim, a runner owner and a pending-collection path whose only carrier was the module
this card deleted, and that resolving that prose is issue 1026's to schedule, not this card's.

**Test expectation:** none for the issue comment — it is a one-time GitHub action with no durable
repository artifact to assert. The journal entries and the release surfaces are covered by the
repository's existing journal-order and release-surface-parity tests, which run in the gate.

## Component inventory

### Removed, each with proof it has no live consumer

| Component | What it is | Proof of no consumer |
|---|---|---|
| `plugins/saga/scripts/second_opinion.py` | The whole module: dispatch, claim store, sidecar, streak detector, typed projections | Thirteen exported names counted across `plugins/`, `tests/`, `scripts/`, `tools/` excluding the module and changelog files: ten have zero outside references; the three that appear at all (`WorkAttempt`, `FindingSnapshot`, `SourceExcerpt`) appear only in Work's prose and the test files this card removes |
| The dispatch machinery: `prepare_second_opinion`, `dispatch_second_opinion`, `collect_second_opinion`, `complete_second_opinion`, `abandon_pending_second_opinion`, `reconcile_second_opinion` | Feature-private dispatch | Zero references outside the module and its own tests |
| The claim state machinery: `SecondOpinionClaimStore`, `RequestClaim`, `ClaimResult`, `PreparedSecondOpinion` | Feature-private state | Every reference to `claim_store` in the repository is inside `second_opinion.py` |
| The sidecar machinery: `work_second_opinion_sidecar`, `load_work_second_opinion_state`, `save_work_second_opinion_state`, `WorkSecondOpinionState`, schema `saga.work-second-opinion.v1` | Feature-private sidecar | Named only by Work's prose (U1 removes it) and `tests/test_work_second_opinion.py` (U2 removes it) |
| The streak machinery: `record_work_attempt`, `_target_failure_streak`, `WorkAttempt`, `WorkAttemptRecord`, `WorkOffer`, `accept_work_offer`, `set_work_offer_disposition`, `render_work_offer_line` | Feature-private streak and offer state | Same two sites; no other caller |
| The typed projections: `external_opinion_projection`, `claude_adjudication_projection`, `adjudicate_finding`, `is_blocking_finding`, `append_reconciliation_once` | Typed evidence with no surviving consumer | Zero references each. `is_blocking_finding` is explicitly disclaimed as unrelated to the brainstorm rule of the same name at `plugins/saga/references/brainstorm-evidence-model.md:98` |
| `tests/test_work_second_opinion.py` | The removed feature's own test file | Tests only the deleted module |
| Work's offer prose and routing | `plugins/saga/skills/work/SKILL.md` §Second-opinion triggers; `pr-continuation-loop.md` §Repeated-failure second-opinion sidecar | The prose is the feature; nothing else refers to these sections |
| `test_work_second_opinion_trigger_contract_is_operator_confirmed_and_non_gating` in `tests/test_saga_plugin.py` | The test that pins the offer's existence | It asserts the removed prose |

### Retained, each with its named live consumer and the test that proves it passes

| Retained component | Named live consumer | Proving test |
|---|---|---|
| `plugins/saga/references/engine-output-trust-boundary.md` — the external-content trust boundary | The team-execution advisory validator: `plugins/team-execution/skills/team-execution/references/validator-registry.md:104` and `validator-criteria.md:6` both cite it by path | `tests/test_engine_output_trust_boundary.py::test_team_execution_references_point_to_trust_boundary_contract` |
| The same document, as a gate-behaviour contract | The review panel's gate surface, `engine_dispatch.satisfy_gate` and `engine_dispatch.NON_GATING_ROLE_KINDS`, which is what keeps an advisory reviewer or a panel from satisfying a gate | `tests/test_engine_output_trust_boundary.py::test_adversarial_fixture_renders_as_data` and the rewritten `tests/test_saga_second_opinion.py::test_advisory_reviewer_and_panel_remain_non_gating` |
| The same document, as the Orchestrate seats' rule | Orchestrate refuses a retired-runner fallback for a reviewer seat at `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:1232` and `:1242` | `tests/test_saga_second_opinion.py::test_review_skills_halt_instead_of_naming_a_launch_cli` |
| `plugins/saga/scripts/engine_dispatch.py` (2,328 lines) | Ten Saga scripts import it, among them `engine_resolver.py`, `reconcile.py`, `ship_ceremony.py` and `capability_elo.py`; seventeen test files exercise it | `tests/test_saga_engine_dispatch.py` |
| `plugins/saga/scripts/reconcile.py` | `outcome_reconcile.py`, `capability_elo.py`, `engine_dispatch.py` | `tests/test_reconcile.py` |
| `plugins/saga/scripts/run_ledger.py` | Eighteen Saga scripts, among them `pulse.py`, `outcome.py`, `execution_spec.py` and `lifecycle_state.py` | `tests/test_run_ledger.py` |
| `plugins/saga/scripts/engine_resolver.py` | `engine_registry_conformance.py`, `execution_spec.py`, `engine_dispatch.py` | `tests/test_saga_engine_resolver.py` |
| Document Review's second-opinion prose in `plugins/saga/skills/doc-review/SKILL.md` | The Document Review skill itself; this card is forbidden from resolving it and notifies instead | `tests/test_saga_plugin.py::test_document_review_second_opinion_contract_is_intact` and `tests/test_doc_review_transport.py` |

### One residual, named and not removed

`plugins/saga/scripts/engine_recommend.py` is imported today by exactly two files:
`second_opinion.py` and `tests/test_engine_recommend.py`. After this card lands its only importer is
its own test. It is **not removed here** — the card names the offer and its dispatch, sidecar, streak
and state machinery, and nothing goes that a card does not name. It is recorded as a follow-up for
the parent to schedule.

## Scope Boundaries

**Out of scope, and these are true non-goals:**

- The external-content trust boundary is not removed, and no row of its document is deleted.
- Work's merge confirmation, its typed review outcomes, and the programmatic-review-writes-nothing
  rule are not changed.
- The transport question settled by issue #776 is not re-opened.
- Document Review's second-opinion prose is not resolved here; the parent is notified.
- The Workflow prose and the board-move sentences in Work's skill are not touched.
- The external seat's claim lifecycle is not built.
- No part of the primary checkout is written, and no pull request is opened by this card's own
  stage; the parent pull request for issue 1030 carries the whole integration branch.

**Deferred to follow-up work, distinct from the above:**

- Removing `plugins/saga/scripts/engine_recommend.py`, whose last non-test importer disappears with
  this card, belongs to a card that names it.
- Correcting Document Review's prose, now that its deferral trigger has fired, is issue 1026's to
  schedule.
- Amending card 938's body with a `Risk` section so the repository's admission step can run for it is
  an operator decision, carried above.

## Risk Analysis and Mitigation

| Risk | How it would show up | Mitigation |
|---|---|---|
| One component too many goes with the module | The trust-boundary document loses a row, or the guard stops scanning anything, and nothing fails | KTD3 keeps the row and changes only its Source cell; U3 keeps every existing guard test running against the narrowed tuple, including the three seeded-unsafe fixtures that must still turn it red |
| The no-offer test passes vacuously | It asserts over a path that no longer exists, so absence is trivially true | The test asserts the two skill files exist first, then asserts the offer is absent from their text, and the mutation proof in U4 shows the predicate can fail |
| A sibling card's edit to Work's skill collides | Issue 1029 rewrites the same file's ending | KTD7 confines this card's edit to the offer's own section and the one forward-pointing sentence; the card's own rule is that whichever lands second resolves it |
| The version number collides at merge | Two sibling cards bump saga to the same number and the collision merges silently | KTD8 re-checks and re-bumps at the merge turn rather than trusting the planning-time number |
| Removing the test that pins the offer looks like weakening the suite | A reviewer sees a deleted test and reads it as lost coverage | The deleted test is replaced by a stronger one in the opposite direction, and U1 states the exchange explicitly |

## Verification

```bash
uv run pytest tests/test_work_second_opinion_removed.py -q
uv run pytest tests/test_engine_output_trust_boundary.py tests/test_saga_second_opinion.py -q
uv run pytest tests/ -q -k "trust or external_content or validator or panel"
uv run pytest tests/ -q -k "work or code_review or second_opinion or doc_review"
uv run pytest tests/ -q
```

The full gate is run by the coordinator at the integration branch, not from this worktree.

**Reading the card's own first verification command correctly.** The card offers this grep:

```bash
grep -rnEi "second opinion|second-opinion|external engine|external_opinion" plugins/saga/ | head -20
```

**It will still return matches after this card lands, and that is the correct outcome, not a
failure.** Three families of match survive by design, and an agent that reads a non-empty result as
a failed removal will either declare the card unfinished or delete something the card forbids
touching:

1. **Document Review's prose** — `plugins/saga/skills/doc-review/SKILL.md` keeps its
   `## Second-opinion point-out` section and its `external_opinion` field definition. Resolving it is
   the notified parent's work, explicitly not this card's.
2. **The trust-boundary document** — `plugins/saga/references/engine-output-trust-boundary.md` keeps
   the `external_opinion.findings[].content` row. Deleting it would break the boundary the card most
   warns about.
3. **`plugins/saga/CHANGELOG.md`** — release history is a record of what happened and is never
   rewritten to hide a removed feature.

The removal's real test is the negative suite in `tests/test_work_second_opinion_removed.py`, which
scopes its assertions to the two Work files and to the absence of the module, rather than to a
repository-wide word search.
