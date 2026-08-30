---
title: Saga Plan improvement — issue 918 Wave 1 (units P1–P4)
type: feat
status: active
date: 2026-08-30
backend: inline
---

# Saga Plan improvement — issue 918 Wave 1 (units P1–P4)

## Summary

This plan covers all four Wave 1 units of parent issue 918 in `infiquetra/infiquetra-claude-plugins`:
the plan-artifact contract (issue 922), two Saga Plan correctness defects (issue 923), a versioned
structured pre-answer contract (issue 924), and the Claude Code Workflow plugin extraction (issue 925).

Three of the four units are plannable and dispatchable as filed. The fourth, the Workflow extraction,
trips its own declared stop condition and needs an operator decomposition ruling before dispatch. One
requirement inside the plan-artifact unit rests on a factual premise this planning pass disproved from
source, and it needs an operator ruling of its own.

## Problem Frame

Saga Plan (`/saga:plan`) turns an issue, a prompt, or a Brainstorm document into a durable plan under
`docs/plans/`. Three programs parse its output: Saga Work reads the `backend:` frontmatter field,
Document Review recognises a plan by a three-part section marker, and `/loop` routes on the saga tick
Plan writes.

The governing principle splits inside one file. Plan's dialogue half (phases 0–2 and 4) must not gain
rigidity. Plan's artifact half inverts that: every field with a named consumer is a strict contract.

The upstream design record is `docs/operations/saga-plan-evidence-package.md` in
`infiquetra/infiquetra-agent-operations`, which is discussion authority only and is an uncommitted
working file in another repository. No repo-relative upstream artifact exists, so `origin:` is omitted
from this document's frontmatter under the plan-frontmatter contract's no-upstream-document clause.

---

## Preflight findings

Every line reference below was re-resolved from source at the launch base `3b2b7083`. The three
findings that change the shape of the work are marked.

### Corpus recount

`docs/plans/` holds 136 top-level `.md` documents, of which 4 carry `backend:`, all saying `inline`.
The four are the run-plan documents dated 2026-08-19, 2026-08-24, 2026-08-25 and 2026-08-26. This
confirms the coordinator's figure and supersedes the parent's "4 of 137".

The directory also holds 66 further files: 21 `.workflow.js`, 20 top-level `-spec.json`, one nested
`.md` verification report, and 24 `.json` files under
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/`. 202 files in total.

Of the 136 top-level documents, 25 (18 percent) fail the marker triple, and 17 carry no YAML
frontmatter at all. Several of the 25 are not plans — a decision brief, a grounding brief, an intake
brief — which are themselves instances of the reserved-directory decision.

### The issue 923 routing defect is REAL

The disagreement exists, and both sides are in the repository at the launch base.

**Producer side.** `plugins/saga/skills/plan/SKILL.md:567-618` (Phase 5.3) emits the saga `save`
command, and neither of its two variants passes `--phase-status`.
`plugins/saga/references/saga-spec.md:498` states the `/plan` writes contract as `lifecycle_phase=plan`,
`plan_path`, `destination`, `deploy_autonomy`, `adr_refs` — `phase_status` is absent from it. An
omitted `--phase-status` becomes `None` at `plugins/saga/scripts/saga.py:1511`, resolves to `pending`
through `_SAVE_SCALAR_DEFAULTS` at `plugins/saga/scripts/saga.py:1406`, and is excluded from
`explicit_fields`, so `_merge` at `plugins/saga/scripts/saga.py:645` writes `pending` for a new saga
or silently carries the prior tick's value for an existing one.

**Router side.** `plugins/saga/skills/loop/references/dispatch-table.md:73-74` holds the two rows that
disagree with it:

| Saga `lifecycle_phase` | `phase_status` | Next command |
|---|---|---|
| `plan` | `complete` | `/doc-review` |
| `plan` | `pending` / `in_progress` | `/plan` (finish the plan) |

**Consequence.** A `/plan` run that finishes writes `lifecycle_phase=plan` with `phase_status=pending`,
and `/loop` matches the second row and dispatches back to `/plan`. The derived `next_phase` at
`plugins/saga/scripts/saga.py:593-594` also never advances, because it advances only on `complete`.

**Which side is wrong: the producer.** `plugins/saga/references/saga-spec.md:176-178` declares
`phase_status` "authoritative for is the phase done". A finished `/plan` that leaves it `pending`
asserts a falsehood about its own work. Every other phase-owning writer already sets it explicitly —
`/work` at `plugins/saga/skills/work/SKILL.md:297`, `:648` and `:854`, and `/loop` on every routing
tick at `plugins/saga/skills/loop/SKILL.md:332`. `/plan` is the only one that omits it. Corroboration:
the maturity derivation at `plugins/saga/references/saga-spec.md:192` already maps
`lifecycle_phase=plan` to `plan-ready`, which routes to `/work` — a third path that already treats a
plan-phase saga as finished.

**This plan changes the producer and leaves the dispatch table exactly as it is.** No third
reconciling rule is added.

### FINDING — issue 922's telemetry premise is false at the launch base

Issue 922 states that the recommended-versus-chosen backend telemetry has no reader and that "no
current consumer reads or acts on that measurement." Settled decision P-D4 rests on that premise.

At the launch base there is a live consumer chain:

- `plugins/saga/scripts/override_rate_reader.py` is 353 lines and computes override rate, over-tier
  and under-tier counts directly from `orchestration_recommended` versus
  `orchestration_operator_choice`.
- `plugins/saga/skills/retro/SKILL.md:184-210` (section 1.6) invokes that reader as a required
  read-only telemetry pass and instructs `/retro` to include its output verbatim in the Phase 1
  evidence block.
- `plugins/saga/skills/optimize/SKILL.md:223` names the same reader as the complementary
  operator-override-rate signal.
- `tests/test_override_rate.py:472` is `test_real_saga_save_feeds_override_rate_reader`, an end-to-end
  test asserting the real save path feeds the reader.

Removing Plan's obligation to pass `--orchestration-recommended` would not break the reader, because
`/work` also passes it at `plugins/saga/skills/work/SKILL.md:281` and the reader's documented zero-data
contract excludes sagas with an empty recommendation. It would starve the metric at the primary
decision point instead, and `/retro`'s section 1.6 would report progressively less data with no
statement anywhere that this was intended.

The removal target itself is real and locatable: `plugins/saga/skills/plan/SKILL.md:304`, `:583`,
`:599`, `:607` and `:614`. What is false is the stated justification for removing it. **This is an
operator ruling, not a planning decision** — see requirement R7 and the Operator rulings section.

### FINDING — issue 925 cannot be delivered as one bounded unit

Issue 925 declares its own stop condition: if the extraction cannot be delivered bounded, stop and
surface for a decomposition ruling rather than expanding silently. It fires.

Issue 925 scopes the unit as 590 lines of prose. That figure is accurate as far as it goes —
`plugins/saga/skills/plan/SKILL.md` sections 5.2 and 5.2a span lines 283-566, exactly 284 lines, and
`plugins/saga/skills/work/SKILL.md` section 1.5 spans lines 317-563, exactly 247 lines. What the figure
omits is the machinery a plugin that "owns defining, generating, validating and executing dynamic
workflows" would have to own:

| Surface | Size | Ownership |
|---|---|---|
| `plugins/saga/scripts/execution_spec.py` | 4,588 lines, 81 top-level symbols | **Shared** — only 5 symbols are Workflow-named; the spec schema, validation, tier resolution and unit graph feed team-execution and `/outcome` too |
| `plugins/saga/scripts/workflow_emitter.py` | 214 lines | Workflow-only |
| `plugins/saga/references/execution-spec.md` | 448 lines | Shared — its own first paragraph says one spec, two emitters |
| Python modules importing either | 50 files across `plugins/` and `tests/`, including `plugins/fleet-core/` | Shared |
| Committed docs referencing `.workflow.js` or `-spec.json` | 98 markdown files | Migration blast radius |

`plugins/saga/scripts/team_emitter.py` emits the team-execution protocol from the same
`execution_spec.py` schema, so the spec substrate cannot follow the Workflow emitter out of Saga
without taking team-execution and `/outcome` with it. Leaving it behind means the new plugin depends on
Saga's internals, which is the opposite of "Saga keeps only a small typed integration contract."

**This plan therefore gates unit U4 behind an operator decomposition ruling** and plans it only to the
boundary the ruling settles. Two candidate shapes are recorded in the Operator rulings section.

### Custody corrections to filed paths

Three filed paths are stale. The parent already instructs re-resolution, so these are corrections, not
stop conditions.

- Issue 923 files the `phase_status` default in `plugins/saga/skills/plan/SKILL.md`. The symbol does
  not appear in that file. Custody is `plugins/saga/references/saga-spec.md:498` and the Phase 5.3
  `save` block at `plugins/saga/skills/plan/SKILL.md:567-618`.
- Issue 922 files the marker-triple definition in `plugins/saga/references/saga-spec.md`. It is not
  there. It is declared at `plugins/saga/skills/plan/SKILL.md:224-226` and consumed at
  `plugins/saga/skills/doc-review/SKILL.md:39`.
- Issue 925 counts three unreachable "if the helper recommends it" branches. There are six, and they
  span four files: `plugins/saga/skills/plan/SKILL.md:304`,
  `plugins/saga/skills/work/SKILL.md:53` and `:275`,
  `plugins/saga/references/operator-choice.md:57`, and
  `plugins/saga/skills/work/references/execution-strategy.md:158` and `:203`. They are genuinely
  unreachable: `recommend_execution_backend` at `plugins/saga/scripts/lifecycle_state.py:183-330`
  assigns `recommended` only `inline` or `team-execution`, and lists `cc-workflows-ultracode` solely
  under `alternatives`.

### Where the plan-artifact contract actually lives

The frontmatter contract is split across two files that disagree.

`plugins/saga/skills/plan/references/plan-sections.md:173-197` is the full contract. It already
declares `backend:` in the template, but line 185 lists only `title`, `type`, `status` and `date` as
required, and line 191 ends the `backend:` note with "Omit it and `/work` behaves exactly as it did
before." That sentence is what makes the field optional.

`plugins/saga/skills/plan/SKILL.md:212-222` restates the frontmatter block inline and omits `backend:`
and `deepened:` entirely. Phase 3 tells the author to follow `plan-sections.md`, so the inline block
contradicts the reference it points at. That drift is the mechanism behind 4 of 136.

The two files also disagree about `origin:`. `plan/SKILL.md:224` states it "MUST be emitted"
unconditionally, while `plan-sections.md:194-196` permits omission when no upstream document exists.
Closing that contradiction is part of the same one-contract repair, and it is why this document omits
the field rather than inventing a path.

Work's legacy compatibility is already in place and needs no change:
`plugins/saga/skills/work/SKILL.md:262-269` honours the field when present, and line 270 offers only
when it is absent.

---

## Requirements

### Unit P1 — plan-artifact contract (issue 922)

- **R1.** `backend:` is a required plan-doc frontmatter field on newly created plans, with a value from
  the enum `inline | team-execution | cc-workflows-ultracode`, and the two frontmatter declarations
  agree on the required field set.
- **R2.** A legacy plan lacking `backend:` still passes through Work's attended offer unrejected and
  unrewritten, and no existing plan document is edited by this unit.
- **R3.** One conformance check evaluates the declared frontmatter fields and the marker triple in a
  single pass over `docs/plans/`, so a document cannot satisfy one contract and silently fail the
  other.
- **R4.** The conformance check distinguishes legacy documents from newly created ones and does not
  fail the build on the legacy corpus.
- **R5.** A document inside `docs/plans/` that fails the marker triple is reported by the check, so the
  path tie-breaker at `plugins/saga/skills/doc-review/SKILL.md:45-46` is no longer silently
  load-bearing.
- **R6.** A document that satisfies the marker triple outside `docs/plans/` is still recognised as a
  plan; the marker triple itself is unchanged in content.
- **R7.** *(Gated on an operator ruling — see Operator rulings.)* The recommended-versus-chosen backend
  telemetry obligation is removed from Plan with no replacement emission path, **or** P-D4 is amended
  and the obligation is retained with the stale claim corrected.
- **R8.** Plan's phases 0–2 and 4 gain no question, checklist, questionnaire, or fixed sequence.

### Unit P2 — state correctness (issue 923)

- **R9.** A failing plan save surfaces an error the operator sees; the failure is never silent.
- **R10.** A failed save leaves no plan document that no tick references, or the failure explicitly
  names the orphaned path.
- **R11.** After a successful plan, the saga tick resolves to the written document.
- **R12.** A completed plan phase routes onward and never back into `/plan`.
- **R13.** The `/plan` write contract and the `/loop` dispatch row agree on what a finished plan phase
  looks like, pinned so they cannot drift apart again.
- **R14.** No repository-level orphan scanner, state store, queue, daemon, or reconciliation pass is
  added.

### Unit P3 — structured pre-answers (issue 924)

- **R15.** Plan accepts a versioned structured pre-answer carrier admitting exactly two fields:
  execution backend and destination.
- **R16.** A valid supplied value is applied and visibly narrated together with the caller that
  supplied it.
- **R17.** A missing value follows the normal adaptive conversation; absence is not an error.
- **R18.** An invalid value, or one contradicting something already established, stops and surfaces the
  conflict and never becomes a silent default.
- **R19.** A pre-answer set declaring an unknown contract version is refused outright rather than
  partially applied.
- **R20.** Direct `/plan` invocation with no pre-answers is behaviourally unchanged.
- **R21.** Model-and-effort confirmation is retained, and the pre-answer set is not rendered as a
  questionnaire, checklist, or fixed sequence.

### Unit P4 — Workflow extraction (issue 925, gated)

- **R22.** *(Gated.)* A separate plugin owns the Claude Code Workflow protocol and machinery, at the
  boundary the operator's decomposition ruling sets, following the `plugins/team-execution/` precedent
  for structure and release surface.
- **R23.** *(Gated.)* Saga retains only the typed integration contract: recognise the backend, record
  the explicit selection, validate availability, invoke, consume the structured result.
- **R24.** The Workflow backend remains runnable and explicit-invocation-only; nothing retires,
  removes, disables, or pauses it, and no path selects it implicitly, automatically, or by
  recommendation.
- **R25.** All six unreachable recommendation branches are deleted from the four files that carry them.
- **R26.** No documentation claims Workflow enforces a stronger sandbox than inline execution.
- **R27.** `docs/plans/` contains only Plan documents; every relocated artifact moves atomically with
  its reference updates, and every inbound reference still resolves afterwards.
- **R28.** `plan_path` values and engineering-journal links survive the migration unchanged.

### Run-level

- **R29.** No test added by any unit asserts an exact Plan question, its wording, or the order of the
  conversation.
- **R30.** No unit edits Plan's `Shaping` or `Ready` board-move sentences at
  `plugins/saga/skills/plan/SKILL.md:123-133` and `:252-261`; child 927 under parent 919 owns them.
- **R31.** No unit touches `plugins/saga/.claude-plugin/plugin.json`,
  `plugins/saga/CHANGELOG.md`, or `.claude-plugin/marketplace.json`; those are centralized at
  integration.
- **R32.** `bash scripts/gate.sh` exits 0 at the integrated wave revision, with every Plan-related
  module green together rather than each unit green in isolation.

---

## Key Technical Decisions

**KTD1: The producer changes, the router does not.** `phase_status` is spec-declared authoritative for
phase completion and every other phase owner already writes it explicitly. Making `/plan` assert
`--phase-status complete` on a written plan is a one-line repair at the single site that is wrong;
changing the dispatch table would instead teach the router to treat an unfinished-looking plan as
finished, which breaks the genuinely-unfinished case. Rejected alternative: changing the `Saga`
dataclass default from `pending` — that default is correct for a new saga at ideation and changing it
would mis-assert completion for every phase.

**KTD2: Loudness before atomicity.** The plan document and the saga tick are written two phases apart
by an agent following prose, so there is no transaction to make atomic in the ordinary sense. The
smallest repair that satisfies the evidenced need is to make the save's success or failure a checked,
surfaced outcome that names the written document path when it fails. Rejected alternative: a
write-tick-then-document reordering, which trades an unreferenced document for a tick pointing at a
file that does not exist.

**KTD3: The conformance check is a test, not a scanner.** R3's single-pass check lives under `tests/`
as a deterministic test over the real corpus. It reports rather than blocks on legacy documents, which
is what keeps it a contract check and not the repository-level scanner P-D7 rejects. The
legacy-versus-new boundary is the presence of `backend:` in the document's own frontmatter, which needs
no external date list or state file.

**KTD4: The pre-answer carrier is data Plan reads, not a phase Plan runs.** It is intake, evaluated
once before the conversation begins, and its only visible effect is narration plus the absence of a
question that would otherwise have been asked. Nothing about it may appear as a step the operator walks
through. Rejected alternative: a pre-answer confirmation prompt, which reintroduces exactly the
question the contract exists to remove.

**KTD5: Serialization resolves the `plan/SKILL.md` section 5.2 overlap.** P1 owns the `backend:`
frontmatter sentences at lines 283-290 and 300-305; P4 owns section 5.2a entirely and the
Workflow-specific guards inside 5.2. Because P4 runs strictly after P1 and P3 and rebases onto their
result, the overlap never becomes a concurrent edit. P4 must not revert P1's frontmatter work while
reducing the Workflow prose around it.

**KTD6: `plan_path` is safe in the migration; `orchestration_ref` is not.** `plan_path` points at
`docs/plans/<date>-<topic>-plan.md`, and plan documents do not move. `orchestration_ref` points at
`docs/plans/<date>-<topic>-spec.json`, which does. Saga ticks are git-ignored and machine-local, so
this run cannot migrate ticks on other machines; the migration must therefore be planned as a
reference update across the 98 committed markdown files plus an explicit statement of the
machine-local ticks it cannot reach.

---

## Implementation Units

Four implementation units and one integration step. Every unit produces a child-scoped commit on its
own branch; no unit opens a pull request, and no unit changes a version or release surface.

Order, with the dependency reason on each edge:

`U1 + U2 concurrently --> U3 (needs U1's settled frontmatter contract) --> U4 (needs U1 and U3 settled, and an operator ruling) --> U5 integration`

Custody, so the concurrent pair cannot collide:

| Unit | Owns | Shares |
|---|---|---|
| U1 | `plan/SKILL.md` lines 212-226 and 283-290, `plan/references/plan-sections.md` lines 173-197, a new conformance test | `saga-spec.md` — declared-field rows only |
| U2 | `scripts/saga.py` save path, `plan/SKILL.md` Phase 5.3 (lines 567-618), `loop/SKILL.md` | `saga-spec.md` — the `/plan` consumer row at line 498 only |
| U3 | A new pre-answer intake section in `plan/SKILL.md` Phase 0, `saga-spec.md` pre-answer contract section | — |
| U4 | `plan/SKILL.md` section 5.2a, `work/SKILL.md` section 1.5, `operator-choice.md`, `execution-strategy.md`, the new plugin, the artifact migration | — |

U1 and U2 share only `plugins/saga/references/saga-spec.md`, in different sections: U1 edits the
declared-field table around lines 110-135, U2 edits the `/plan` consumer row at line 498. Nothing else
overlaps.

### U1. Make the plan artifact a strict contract

Close the frontmatter drift, require `backend:` on new plans, and add one conformance check covering
declared fields and the marker triple together.

**Requirements:** R1, R2, R3, R4, R5, R6, R8, and R7 only if the operator rules that P-D4 stands.

**Files:** `plugins/saga/skills/plan/references/plan-sections.md`,
`plugins/saga/skills/plan/SKILL.md`, `plugins/saga/references/saga-spec.md`,
`tests/test_plan_artifact_conformance.py` (new).

**Steps:** Add `backend:` to the required-field sentence at `plan-sections.md:185` and replace the
"Omit it and `/work` behaves exactly as it did before" clause at `:191` with the required-on-new,
compatible-on-legacy statement. Bring the inline frontmatter block at `plan/SKILL.md:212-222` into
agreement with the reference by adding `backend:` and `deepened:`, keeping the block a restatement
rather than deleting it. Record the marker triple and the declared field set in the saga spec's
declared-field rows so the contract has one machine-readable home. Write the conformance test.

**Deliberately not changed:** `plugins/saga/skills/work/SKILL.md:262-270` already honours the field
when present and offers only when absent, which is exactly R2. Touching it would be the rejection P-D6
forbids.

**Test scenarios** in `tests/test_plan_artifact_conformance.py`:

Positive — a document carrying all required frontmatter fields with a `backend:` value from the enum
and all three markers passes the check with no findings.

Positive — the check evaluates frontmatter and markers in one pass, asserted by a fixture document
that satisfies the frontmatter contract and fails the marker triple, which must be reported by the
same call that validated the frontmatter.

Negative — a document missing `backend:` is reported, and the report classifies it as legacy when the
document is one of the existing 132 and as new when the document declares the field set introduced by
this unit.

Negative — a document under `docs/plans/` that fails the marker triple is reported, and the assertion
runs against the real corpus so the currently-failing 25 are named rather than hidden by the path
tie-breaker.

Positive — a document outside `docs/plans/` that satisfies the marker triple is still classified as a
plan.

Negative — the real corpus of 136 top-level documents produces a report and a zero exit; the legacy
corpus never fails the build.

Mutation proof — deleting the required-field rule fails the first positive test; deleting the marker
half of the check fails the single-pass test.

**Acceptance mapping:** issue 922's criteria 1, 2, 3, 4, 6, 7, 8 map to the steps and tests above;
criterion 5 is R7 and is gated; criterion 9 is U5.

### U2. Stop producing unreferenced plans and fix the finished-plan routing loop

Make the plan save's failure loud and named, and make `/plan` assert the completion its own dispatch
row requires.

**Requirements:** R9, R10, R11, R12, R13, R14.

**Files:** `plugins/saga/scripts/saga.py`, `plugins/saga/skills/plan/SKILL.md` Phase 5.3,
`plugins/saga/references/saga-spec.md` line 498, `plugins/saga/skills/loop/SKILL.md`,
`tests/test_saga_plan_save_and_routing.py` (new).

**Steps, routing half:** Add `--phase-status complete` to both `save` variants at
`plugins/saga/skills/plan/SKILL.md:567-618`, and add `phase_status=complete` to the `/plan` writes
column at `plugins/saga/references/saga-spec.md:498`. The dispatch table at
`plugins/saga/skills/loop/references/dispatch-table.md:73-74` is correct and is not edited.

**Steps, save half:** Make the save path's failure surface name the plan document that is now
unreferenced. `plugins/saga/scripts/saga.py:1646` currently catches only `SagaSaveError`; an `OSError`
from `envelope_path.write_text` at `:828` or from `_atomic_write` at `:673-677` escapes as a traceback.
Catch the filesystem failure, and when `plan_path` is set, name that path in the error so the operator
sees exactly which document has no tick. Add the matching instruction to Phase 5.3 to check the save's
exit status and surface a failure rather than continuing to the route step.

**Deliberately not built:** no scanner, no state store, no queue, no daemon, no reconciliation pass.
The document and the tick are written two phases apart by an agent, so there is no transaction to make
atomic; the repair is a named, checked failure, which is what R10's second branch permits.

**Test scenarios** in `tests/test_saga_plan_save_and_routing.py`:

Negative — a save whose envelope write raises `OSError` produces a surfaced error naming the
`plan_path`, asserted on the raised failure and the non-zero exit, not on a log line.

Negative — that same failure path does not leave a plan document silently unreferenced; the error text
names the orphaned path.

Positive — after a successful save carrying `--plan-path`, `restore` resolves to that document.

Positive — a `save` with `--lifecycle-phase plan --phase-status complete` yields `next_phase` greater
than `phase`, so the completed phase advances.

Negative — the `/plan` write contract and the `/loop` dispatch row are pinned together: the test reads
the `phase_status` value the Phase 5.3 block writes and the value the dispatch table's `plan` row
requires for `/doc-review`, and fails if they differ. This is a contract-agreement assertion over the
two documents, not an assertion about any Plan question.

Mutation proof — restoring the silent failure path fails the surfaced-error test; removing
`--phase-status complete` from Phase 5.3 fails the agreement test.

**Acceptance mapping:** issue 923's criteria 1 through 7 map to the steps and tests above; criterion 8
is U5.

### U3. Versioned structured pre-answer contract

Give Plan a typed way to receive a decision a caller already settled, narrate it, and stop on a
conflict.

**Requirements:** R15, R16, R17, R18, R19, R20, R21.

**Files:** `plugins/saga/skills/plan/SKILL.md` Phase 0 intake,
`plugins/saga/references/saga-spec.md` (a new pre-answer contract section),
`tests/test_plan_pre_answers.py` (new).

**Steps:** Define the carrier in the saga spec with an explicit version marker and exactly two admitted
fields, execution backend and destination, each with its declared enum. Add a Phase 0 intake paragraph
to `plan/SKILL.md` describing the four behaviours: apply and narrate with the caller named, fall
through to the normal conversation on absence, stop and surface on an invalid or contradictory value,
and refuse an unknown version outright without partial application. The narrated line names the field,
the value, and the supplying caller.

**Why the carrier replaces prose injection:** `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:107-113`
appends literal sentences to the task string telling Plan not to ask about the backend, and the comment
at `:138` states that this pre-answers one question out of the four named at `:154`. That workaround is
the only mechanism that exists today. This unit ships Saga's typed surface only; Orchestrate's side is
not implemented here.

**Deliberately unchanged:** direct `/plan` with no pre-answers. Phases 0–2 and 4 gain no question, and
the model-and-effort confirmation at `plugins/saga/skills/plan/SKILL.md:371` and `:441` stays exactly
as it is, per settled decision P-D5.

**Test scenarios** in `tests/test_plan_pre_answers.py`:

Positive — a pre-answer set declaring the current version and a valid backend records the applied
value and the supplying caller in the narration, asserted on both the value and the caller identity.

Positive — an empty pre-answer set leaves the normal conversation path intact and produces no
narration.

Negative — a backend value outside the declared enum stops and surfaces the conflict; the assertion is
on the stop, and a fallback to any default fails the test.

Negative — a supplied backend contradicting a value already established stops rather than silently
preferring either side.

Positive — a pre-answer set declaring an unknown version is refused whole; no field from it is applied.

Positive — direct invocation with no carrier present is behaviourally identical to the pre-unit
contract.

Negative — only backend and destination are admitted; a third field is rejected rather than ignored.

Mutation proof — removing the conflict stop fails the invalid-value test; removing the narration
requirement fails the caller-recorded test.

**Acceptance mapping:** issue 924's criteria 1 through 9 map to the steps and tests above; criterion 10
is U5.

### U4. Workflow extraction — GATED on an operator decomposition ruling

Extract the Claude Code Workflow capability into its own plugin at the boundary the operator sets, and
move generated Workflow artifacts out of `docs/plans/`.

**Requirements:** R24, R25, R26, R27, R28 unconditionally; R22 and R23 only at the boundary the ruling
sets.

**Dispatch gate:** this unit does not start until the operator rules on the decomposition question
recorded below. The evidence is in the Preflight findings section. Dispatching it as filed would mean
either moving a 4,588-line shared spec substrate that team-execution and `/outcome` also depend on, or
creating a plugin that reaches into Saga's internals — and issue 925 names silent expansion as the
failure mode to avoid.

**Sub-part A, bounded and ready now.** Delete the six unreachable recommendation branches at
`plugins/saga/skills/plan/SKILL.md:304`, `plugins/saga/skills/work/SKILL.md:53` and `:275`,
`plugins/saga/references/operator-choice.md:57`, and
`plugins/saga/skills/work/references/execution-strategy.md:158` and `:203`. Confirm no file claims
Workflow enforces a stronger sandbox than inline, and correct any that does. Neither touches the
extraction boundary, and both are unconditional under R25 and R26.

**Sub-part B, the artifact migration, bounded and ready now.** Move the 21 `.workflow.js` files, the 20
top-level `-spec.json` files, the nested `gate-g-verification-report.md`, and the 24
`survivors/*.json` files out of `docs/plans/` in one commit with their reference updates across the 98
committed markdown files that name them. `plan_path` values are unaffected because plan documents do
not move. `orchestration_ref` values in machine-local saga ticks point at the moving spec files and
cannot be migrated by this run; the commit must state that explicitly rather than imply the pointers
were fixed everywhere.

**Sub-part C, the extraction itself, gated.** Scope set by the operator's ruling.

**Deliberately unchanged:** the backend stays runnable and explicit-invocation-only under issue 808;
Orchestrate keeps pre-answering `inline`; the `team-execution` precedent is followed for structure and
release surface, not redesigned; and P1's frontmatter work inside section 5.2 is preserved while the
Workflow prose around it is reduced.

**Test scenarios** in `tests/test_workflow_extraction.py` (new):

Positive — the Workflow backend is still selectable and still runs when explicitly invoked. This is the
anti-regression pin for issue 808 and is the most important test in the unit.

Negative — no path selects the backend implicitly, automatically, or by recommendation; asserted
against `recommend_execution_backend`'s real return value across the trigger matrix, not a fixture.

Negative — no Saga file contains an "if the recommender suggests `cc-workflows-ultracode`" branch.

Negative — no documentation in Saga or the new plugin claims Workflow enforces a stronger sandbox than
inline.

Positive — every relocated artifact's inbound references resolve, asserted against the real files.

Negative — `docs/plans/` contains only Plan documents after the move.

Mutation proof — removing the explicit-only guard fails the implicit-selection test.

**Acceptance mapping:** issue 925's criteria 2, 5, 6, 7, 8, 9 map to sub-parts A and B and the tests
above; criteria 1, 3, 4 map to sub-part C and are gated; criterion 10 is the gate itself, and this plan
records that it fired; criterion 11 is U5.

### U5. Integration — release surfaces and the wave gate

Centralize every version and release-surface change at integration, after all four units settle.

**Requirements:** R31, R32.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, plus the new plugin's own release surfaces if sub-part C lands.

**Steps:** Freeze the integrated wave revision. Bump the Saga version once from 0.148.0 for all landed
units, serialized against the open issue 912 which also touches these files. Write one CHANGELOG entry
per landed unit. Run the full gate in the background per this repository's `CLAUDE.md`, and read
`/tmp/gate-run/result.txt` — the marker is cleared at start, so its absence means still running or
killed, never green.

**Test expectation:** none — this unit changes only metadata, and the existing version and metadata
drift guards cover it.

---

## Scope Boundaries

### Out of scope

- Plan's `Shaping` and `Ready` board-move sentences. Child 927 under parent 919 owns them.
- Any re-decision of the Claude Code Workflow backend's fate. Issue 808 settled it.
- Any removal or caveat of model-and-effort confirmation. Settled decision P-D5 settled it from source.
- A repository-level unreferenced-plan scanner. Settled decision P-D7 rejects it.
- Consolidation of the duplicated lifecycle-position prose. No two copies disagree yet.
- Any bulk rewrite, migration, or reformat of existing plan documents to add `backend:`.
- Orchestrate's side of the pre-answer contract. U3 ships Saga's typed surface only.
- Unit P5, issue 926. It is out of Wave 1 entirely; its gate, issue 927, is open.
- Any state store, daemon, registry, scoring system, or multi-tenant, internet-scale, high-availability,
  or regulatory machinery.

### Deferred to Follow-Up Work

- Orchestrate's adoption of the U3 pre-answer carrier in place of the prose injection at
  `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:107-113`.
- Admitting further fields to the pre-answer carrier beyond backend and destination. The version marker
  exists so this can happen without breaking older callers.
- The 25 corpus documents that fail the marker triple. U1 reports them; repairing them is not this
  wave's work, and several are not plans at all.
- Migrating `orchestration_ref` pointers in saga ticks on machines this run cannot reach.

---

## Operator rulings required

Two rulings block work. Neither is a planning decision.

**Ruling 1 — does settled decision P-D4 stand, given that its premise is false?** Issue 922 justifies
removing the recommended-versus-chosen telemetry on the grounds that nothing reads it. There is a
353-line reader, a `/retro` section that invokes it as a required pass, an `/optimize` cross-reference,
and an end-to-end test. Three options: remove the obligation anyway and accept a knowingly starved
`/retro` metric; retain the obligation and correct the false claim in issue 922; or remove it and also
retire `override_rate_reader.py` and its `/retro` and `/optimize` call sites, which is a larger change
than issue 922 scopes. R7 is blocked until this is answered; every other U1 requirement proceeds.

**Ruling 2 — how is issue 925 decomposed?** The extraction as filed cannot be bounded, because the
Workflow emitter's spec substrate is shared with team-execution and `/outcome`. Two candidate shapes,
both preserving issue 808:

| Shape | New plugin owns | Saga keeps | Cost |
|---|---|---|---|
| Emitter-only | `workflow_emitter.py`, the workflow-script emitter path in `execution_spec.py`, the Workflow protocol prose, generated artifacts | The spec schema, validation, tier resolution, the typed integration contract | Small and bounded; the new plugin still reads Saga's spec shape, so the seam is a typed spec contract rather than a clean severance |
| Spec-substrate split | The whole `execution_spec.py` spec substrate plus both emitters | Only the integration contract | Clean severance, but it moves `/outcome` and team-execution machinery too and touches 50 importing modules — a multi-unit campaign, not one child |

The emitter-only shape is the one that fits Wave 1. The spec-substrate split is a separate campaign.
U4 sub-parts A and B are ready to dispatch under either ruling; sub-part C waits.

---

## Verification

```bash
# Corpus figures, re-derived rather than inherited
ls docs/plans/*.md | wc -l                      # 136 at the launch base
grep -lE '^backend:' docs/plans/*.md | wc -l     # 4 at the launch base

# The routing contract must agree end to end
grep -n "phase-status" plugins/saga/skills/plan/SKILL.md
grep -n "phase_status" plugins/saga/references/saga-spec.md | grep -n "/plan"
sed -n '69,80p' plugins/saga/skills/loop/references/dispatch-table.md

# The conversation must not have gained rigidity
grep -nEi "checklist|questionnaire|answer each|in order, ask" plugins/saga/skills/plan/SKILL.md

# The backend must remain runnable and explicit-only
grep -rnEi "if the helper recommends|recommended\` is \`cc-workflows" plugins/saga/

# Board-move sentences must be untouched by this run
git diff main -- plugins/saga/skills/plan/SKILL.md | grep -nE "Shaping|Ready for Planning"

uv run pytest tests/ -q -k "plan_artifact or plan_save or pre_answer or workflow_extraction"
uv run ruff check plugins/saga tests/
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
cat /tmp/gate-run/result.txt
```
