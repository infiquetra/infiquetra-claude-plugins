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

Both operator rulings requested by cycle 1 have been made, so all four units are dispatchable. Cycle 2
revised this document against an independent Plan Document Review that returned no blocker and eleven
majors; every one is dispositioned in the Review dispositions section.

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

## Operator rulings applied

Both rulings requested by cycle 1 are settled and are applied throughout this document.

**Ruling 1 — settled decision P-D4 does not stand. The telemetry is retained.** Its premise was false:
`plugins/saga/scripts/override_rate_reader.py` exists and `/retro` runs it as a required pass. Nothing
is removed, no replacement emission path is added because none is needed, and issue 922's acceptance
criterion asserting the removal is withdrawn. Requirement R7 below states the retention. No unit
deletes code, tests, or references on account of P-D4.

**Ruling 2 — issue 925 is decomposed as the emitter-only split, and unit P4 stays in Wave 1.** The new
plugin owns `workflow_emitter.py`, the workflow-script emitter path inside `execution_spec.py`, the
Workflow protocol prose, and the generated artifacts. Saga keeps `execution_spec.py`'s spec schema,
validation and tier resolution, `team_emitter.py`, and the typed integration contract. The
spec-substrate split is explicitly not this run's work.

**The seam this creates is a typed spec contract, not a clean severance.** The extracted plugin still
reads the spec shape Saga owns, because `team_emitter.py` emits the team-execution protocol from that
same schema and moving it would take team-execution and `/outcome` with it. Requirement R23 is written
to that boundary, and nothing in this plan should be read as claiming the new plugin is independent of
Saga's spec shape.

---

## Preflight findings

Every line reference below was re-resolved from source at the launch base `3b2b7083`, then re-verified
in cycle 2. The findings that change the shape of the work are marked.

### Corpus observation — dated, and never a test constant

Observed at `3b2b7083`: `docs/plans/` held 136 top-level `.md` documents, of which 4 carried
`backend:`, all saying `inline`; 25 of the 136 failed the marker triple; and 202 files sat under the
directory in total.

**These integers are a dated observation satisfying issue 922's preflight-recount criterion. They are
not constants and must never be pinned by a test.** This plan document is itself a new top-level
`docs/plans/*.md` carrying `backend:`, so both counts changed the moment it was committed. Every unit
that needs a count derives it:

```bash
ls docs/plans/*.md | wc -l
grep -lE '^backend:' docs/plans/*.md | wc -l
```

The qualitative findings behind those numbers are what the units act on: a substantial minority of the
corpus fails the marker triple, several of the failures are not plan documents at all, and
`docs/plans/` holds generated Workflow artifacts alongside plans.

### The issue 923 routing defect is REAL

The disagreement exists, and both sides are in the repository at the launch base. The independent
review reached the same conclusion on the same evidence.

**Producer side.** `plugins/saga/skills/plan/SKILL.md:567-618` (Phase 5.3) emits two `save` variants
and neither passes `--phase-status`. `plugins/saga/references/saga-spec.md:498` states the `/plan`
writes contract as `lifecycle_phase=plan`, `plan_path`, `destination`, `deploy_autonomy`, `adr_refs` —
`phase_status` is absent. An omitted `--phase-status` is `None` at
`plugins/saga/scripts/saga.py:1511`, resolves to `pending` through `_SAVE_SCALAR_DEFAULTS` at
`plugins/saga/scripts/saga.py:1406`, and is excluded from `explicit_fields` at `:1423`, so `_merge` at
`plugins/saga/scripts/saga.py:645` writes `pending` on a new saga or silently carries the prior tick
forward on an existing one.

**Router side.** `plugins/saga/skills/loop/references/dispatch-table.md:73-74`:

| Saga `lifecycle_phase` | `phase_status` | Next command |
|---|---|---|
| `plan` | `complete` | `/doc-review` |
| `plan` | `pending` / `in_progress` | `/plan` (finish the plan) |

`plugins/saga/skills/loop/SKILL.md:273` and
`plugins/saga/skills/loop/references/drive-and-resume.md:85` route from the restored
`lifecycle_phase` and `phase_status` through that table, and no Python dispatcher overrides it.

**Consequence.** A finished `/plan` writes `lifecycle_phase=plan` with `phase_status=pending`, and a
later `/loop` matches the second row and dispatches back to `/plan`. Plan's own Phase 5.4 still
recommends `/doc-review` on exit, so the loop-back happens on `/loop` re-entry rather than at Plan's
own hand-off.

**Which side is wrong: the producer.** `plugins/saga/references/saga-spec.md:176-178` declares
`phase_status` authoritative for whether the phase is done. Every other phase-owning writer already
sets it explicitly — `/work` at `plugins/saga/skills/work/SKILL.md:297`, `:648` and `:854`, and
`/loop` on every routing tick at `plugins/saga/skills/loop/SKILL.md:332`. `/plan` is the only one that
omits it. `plugins/saga/references/saga-spec.md:192` mapping `lifecycle_phase=plan` to `plan-ready` is
a third consumer that already treats a plan-phase saga as finished — corroboration, not a rule to add.

**The load-bearing axis is `lifecycle_phase` plus `phase_status`, not `next_phase`.** Cycle 1 cited
`_next_phase` at `plugins/saga/scripts/saga.py:593-594` as corroboration. That helper operates on the
numeric `phase` counter, `/loop` does not read it, and the observation is true but irrelevant. It is
dropped from the plan's reasoning and from U2's tests.

**This plan changes the producer and leaves the dispatch table exactly as it is.** No third
reconciling rule is added, and the `_SAVE_SCALAR_DEFAULTS` value stays `pending`.

### FINDING — the `#808` pin tests forbid a naive deletion of the recommendation branches

Issue 925 asks for the deletion of unreachable "if the helper recommends it" branches. Two existing
tests turn that into a red gate if done literally, and the independent review and the coordinator both
confirmed it.

`tests/test_saga_plugin.py:714` (`test_plan_and_work_cc_workflows_explicit_invocation_only`) asserts
`"do not pre-select" or "never pre-select"` appears in `plan/SKILL.md` and `work/SKILL.md`.
`tests/test_saga_plugin.py:742` (`test_backend_offer_contract_docs_pin_explicit_invocation`) asserts
`"do not pre-select"` appears in `operator-choice.md` and `execution-strategy.md`.

Mapping each of the six counterfactual branches against a surviving unconditional pin in the same
file:

| File | Counterfactual branch to delete | Unconditional pin that survives | Safe? |
|---|---|---|---|
| `plugins/saga/skills/plan/SKILL.md` | `:304-306` | `:297` "Never pre-select `cc-workflows-ultracode`." | Yes |
| `plugins/saga/references/operator-choice.md` | `:57-58` | `:199` "Do not pre-select `cc-workflows-ultracode`." | Yes |
| `plugins/saga/skills/work/SKILL.md` | `:53` and `:275-276` | **none** | **No — the file loses every pin phrase** |
| `plugins/saga/skills/work/references/execution-strategy.md` | `:158-159` and `:203-204` | **none** | **No — the file loses every pin phrase** |

Unit U4-A is therefore written to delete only the counterfactual `if recommended is
cc-workflows-ultracode` condition and to leave, in every one of the four files, an unconditional
never-pre-select sentence the existing tests still match. In `work/SKILL.md` and
`execution-strategy.md` that means rewriting one branch into an unconditional statement rather than
removing it.

The branches are genuinely counterfactual: `recommend_execution_backend` at
`plugins/saga/scripts/lifecycle_state.py:207-210` and `:291-296` assigns `recommended` only `inline`
or `team-execution` and lists `cc-workflows-ultracode` solely under `alternatives`.

### Custody corrections to filed paths

Four filed paths are stale. The parent already instructs re-resolution, so these are corrections, not
stop conditions.

- Issue 923 files the `phase_status` default in `plugins/saga/skills/plan/SKILL.md`. The symbol does
  not appear in that file. Custody is `plugins/saga/references/saga-spec.md:498` and the Phase 5.3
  `save` block at `plugins/saga/skills/plan/SKILL.md:567-618`.
- Issue 922 files the marker-triple definition in `plugins/saga/references/saga-spec.md`. It is not
  there. It is declared at `plugins/saga/skills/plan/SKILL.md:224-226` and consumed at
  `plugins/saga/skills/doc-review/SKILL.md:39`.
- Issue 925 counts three unreachable recommendation branches. There are six, across four files, listed
  in the table above.
- Cycle 1 cited `plugins/saga/skills/plan/SKILL.md:371` and `:441` as the default-path
  model-and-effort confirmation. Both lines sit inside section 5.2a, the ExecutionSpec authoring path
  entered only after explicit Workflow invocation. Settled decision P-D5's retention is therefore
  honoured by not editing section 5.2a and by adding no confirmation prompt to the default path, not
  by preserving those two lines on a path they are not on.

### Where the plan-artifact contract actually lives

The frontmatter contract is split across two files that disagree.

`plugins/saga/skills/plan/references/plan-sections.md:173-197` is the full contract. It already
declares `backend:` in the template, but line 185 lists only `title`, `type`, `status` and `date` as
required, and line 191 ends the `backend:` note with "Omit it and `/work` behaves exactly as it did
before." That sentence is what makes the field optional.

`plugins/saga/skills/plan/SKILL.md:212-222` restates the frontmatter block inline and omits `backend:`
and `deepened:` entirely. Phase 3 tells the author to follow `plan-sections.md`, so the inline block
contradicts the reference it points at. That drift is the mechanism behind so few plans carrying the
field.

The two files also disagree about `origin:`. `plan/SKILL.md:224` states it "MUST be emitted"
unconditionally, while `plan-sections.md:194-196` permits omission when no upstream document exists.
Closing that contradiction is part of the same one-contract repair, and it is why this document omits
the field rather than inventing a path.

`plugins/saga/references/saga-spec.md` defines the saga **tick envelope** and does not define the
plan-document contract at all. That is correct and must stay correct: the tick schema and the plan-doc
schema are different artifacts, and unit U1 adds a distinct subsection rather than extending the
envelope field table.

Work's legacy compatibility is already in place and needs no change:
`plugins/saga/skills/work/SKILL.md:262-269` honours the field when present, and line 270 offers only
when it is absent.

### The structured pre-answer workaround this run replaces

`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:107-113` appends literal sentences to
the task string telling Plan the backend is already decided and not to ask. The comment at `:138`
states that this pre-answers one question, and `:154` names the family of four the same technique
could cover: destination, execution backend, scope class, resume-versus-mint. That prose injection is
the only mechanism that exists today, and unit U3 replaces the Saga-side half of it.

---

## Requirements

### Unit P1 — plan-artifact contract (issue 922)

- **R1.** `backend:` is a required plan-doc frontmatter field on newly created plans, with a value from
  the enum `inline | team-execution | cc-workflows-ultracode`, and the two frontmatter declarations
  agree on the required field set and on `origin:`.
- **R2.** A legacy plan lacking `backend:` still passes through Work's attended offer unrejected and
  unrewritten, and no existing plan document is edited by this unit.
- **R3.** One conformance check evaluates the declared frontmatter fields and the marker triple in a
  single pass over `docs/plans/`, so a document cannot satisfy one contract and silently fail the
  other.
- **R4.** The conformance check distinguishes legacy documents from newly created ones by the rule
  KTD3 states, and does not fail the build on the legacy corpus.
- **R5.** The check recurses into subdirectories of `docs/plans/`, and any document under that path
  that fails the marker triple is reported, so the path tie-breaker at
  `plugins/saga/skills/doc-review/SKILL.md:45-46` is no longer silently load-bearing.
- **R6.** The marker triple's definition is unchanged in content and is pinned as a contract test, so
  a later edit to `plan/SKILL.md:224-226` cannot silently redefine what makes a document a plan.
- **R7.** The recommended-versus-chosen backend telemetry is **retained unchanged** under operator
  ruling 1. No instruction, field, reader, test, or reference is removed on account of settled
  decision P-D4, and no replacement emission path is added because none is needed.
- **R8.** Plan's phases 0–2 and 4 gain no question, checklist, questionnaire, or fixed sequence.

### Unit P2 — state correctness (issue 923)

- **R9.** A failing plan save surfaces an error that names the plan document left without a tick, so
  the operator sees which file is unreferenced rather than only that a write failed.
- **R10.** Phase 5.3 checks the save's exit status and stops rather than walking into Phase 5.4 on a
  failure.
- **R11.** After a successful plan, the saga tick resolves to the written document.
- **R12.** A completed plan phase routes onward and never back into `/plan`.
- **R13.** The `/plan` write contract and the `/loop` dispatch row agree on what a finished plan phase
  looks like, pinned so they cannot drift apart again.
- **R14.** No repository-level orphan scanner, state store, queue, daemon, or reconciliation pass is
  added, and `_SAVE_SCALAR_DEFAULTS` is not changed.
- **R8** also binds this unit: no new question is added to Plan's conversation.

### Unit P3 — structured pre-answers (issue 924)

- **R15.** Plan accepts a versioned structured pre-answer carrier admitting exactly two decision
  fields: `backend` and `destination`, each validated against its declared enum.
- **R16.** A valid supplied value is applied and visibly narrated together with the caller that
  supplied it.
- **R17.** A missing carrier, or a carrier omitting a field, follows the normal adaptive conversation;
  absence is not an error.
- **R18.** An invalid value, or one contradicting something already established, stops and surfaces the
  conflict and never becomes a silent default.
- **R19.** A carrier declaring an unknown schema token is refused whole; no field from it is applied.
- **R20.** Direct `/plan` invocation with no carrier applies nothing, narrates nothing, and stops
  nothing.
- **R21.** Model-and-effort confirmation is retained by leaving section 5.2a unedited and adding no
  confirmation prompt to the default path, and the carrier is not rendered as a questionnaire,
  checklist, or fixed sequence.

### Unit P4 — Workflow extraction, emitter-only boundary (issue 925)

- **R22.** A new plugin owns `workflow_emitter.py`, the workflow-script emitter path currently inside
  `execution_spec.py`, the Workflow protocol prose, and the generated Workflow artifacts, following
  the `plugins/team-execution/` precedent for structure and release surface.
- **R23.** Saga retains `execution_spec.py`'s spec schema, validation and tier resolution,
  `team_emitter.py`, and a typed integration contract that recognises the backend, records the
  explicit selection, validates availability, invokes the extracted emitter, and consumes its
  structured result. The seam is a typed spec contract; the new plugin still reads Saga's spec shape.
- **R24.** The Workflow backend remains runnable and explicit-invocation-only; nothing retires,
  removes, disables, or pauses it, and no path selects it implicitly, automatically, or by
  recommendation.
- **R25.** The six counterfactual recommendation conditions are removed, and every one of the four
  affected files retains an unconditional never-pre-select sentence that the existing `#808` pin tests
  match.
- **R26.** No documentation claims Workflow enforces a stronger sandbox than inline execution.
- **R27.** The live write-path conventions that direct generated Workflow artifacts into `docs/plans/`
  are changed to a named directory, and the artifacts those conventions produced are moved there
  atomically with their live pointers.
- **R28.** `plan_path` values and live inbound references survive the migration unchanged.

### Run-level

- **R29.** No test added by any unit asserts an exact Plan question, its wording, the order of the
  conversation, or that the conversation is unchanged.
- **R30.** No unit edits Plan's `Shaping` or `Ready` board-move sentences at
  `plugins/saga/skills/plan/SKILL.md:123-133` and `:252-261`; child 927 under parent 919 owns them.
- **R31.** No worker touches `plugins/saga/.claude-plugin/plugin.json`,
  `plugins/saga/CHANGELOG.md`, `.claude-plugin/marketplace.json`, or the Saga version pin at
  `tests/test_saga_plugin.py:48`; those are centralized at integration.
- **R32.** `bash scripts/gate.sh` exits 0 at the integrated wave revision, with every Plan-related
  module green together rather than each unit green in isolation.
- **R33.** No unit pins a corpus count, a corpus file name, or a launch-base integer in a test.

---

## Key Technical Decisions

**KTD1: The producer changes, the router does not.** `phase_status` is spec-declared authoritative for
phase completion and every other phase owner already writes it explicitly. Making `/plan` assert
`--phase-status complete` on a written plan is a one-line repair at the single site that is wrong.
Rejected alternative: changing the dispatch table, which would teach the router to treat a genuinely
unfinished plan as finished. Rejected alternative: changing `_SAVE_SCALAR_DEFAULTS` to `complete`,
which would mis-assert completion for a new ideation saga.

**KTD2: A named failure, not a transaction.** The plan document and the saga tick are written two
phases apart by an agent following prose, so there is no transaction to make atomic. An `OSError` from
`plugins/saga/scripts/saga.py:828` or `:673-677` already escapes as a traceback with a non-zero exit,
so the failure is not silent today — what is missing is that the error does not name the plan document
now stranded, and that Phase 5.3 does not check the exit before continuing. Those two are the repair.
Rejected alternative: writing the tick before the document, which trades an unreferenced document for a
tick pointing at a file that does not exist.

**KTD3: Legacy is the absence of `backend:`, and nothing else.** A document that lacks the field is
legacy, reported and non-failing. A document that carries it is new-contract and is held to the full
frontmatter and marker contract. There is no date list, no state file, and no corpus enumeration.
Proving the "new document with a missing required field" case therefore needs a **fixture** authored
as a new-contract document and then stripped of the field, because that class cannot exist in the real
corpus by construction.

**KTD4: The pre-answer carrier is data Plan reads, not a phase Plan runs.** It is intake, evaluated
once before the conversation begins, and its only visible effect is narration plus the absence of a
question that would otherwise have been asked. Rejected alternative: a pre-answer confirmation prompt,
which reintroduces exactly the question the contract exists to remove.

**KTD5: The carrier is a JSON object read from the invocation context, validated by a named helper.**
It follows the repository's own typed-envelope precedent (`plugins/saga/scripts/intent_envelope.py`
and the `<name>.v1` schema tokens across `plugins/saga/scripts/`). Concretely:

```json
{
  "schema": "plan_pre_answers.v1",
  "caller": "orchestrate",
  "backend": "inline",
  "destination": "plan-only"
}
```

- **Schema token:** `plan_pre_answers.v1`, in a `schema` key. An unrecognised token is refused whole.
- **Decision fields:** `backend` from `inline | team-execution | cc-workflows-ultracode`, and
  `destination` from `plan-only | pr | merge | nonprod-deploy` — the enum Phase 5.1 already uses at
  `plugins/saga/skills/plan/SKILL.md:264-265`. Either may be omitted; both omitted is a valid empty
  carrier.
- **`caller` is envelope metadata, not a decision field.** It names the supplying capability for
  narration and is outside the two-field admission limit R15 sets.
- **Transport:** a fenced JSON block in the `/plan` invocation text. No file, no CLI flag, no daemon,
  no state. This is the same seam Orchestrate already writes prose into at
  `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:107-113`, which is what makes it a
  replacement rather than a second channel.
- **Validator:** `plugins/saga/scripts/plan_pre_answers.py`, a small pure-function module shaped like
  `intent_envelope.py`, returning applied values, omitted fields, and a stop with its reason.

Rejected alternative: a prose-only contract in `plan/SKILL.md` with grep-based tests. Issue 924's
acceptance criteria demand behaviours — refused whole, stops rather than defaults — that only code can
prove, and a typed surface with no type checker is prose. This adds one file beyond issue 924's filed
list, and the addition is recorded in the Review dispositions section.

**KTD6: Serialization resolves the `plan/SKILL.md` section 5.2 overlap, and P1 does not enter it.**
With ruling 1 retaining the telemetry, P1 has no reason to touch `:300-305`; that range belongs to U4-A
alone. P1's `plan/SKILL.md` custody is `:212-226` and `:283-290` only. Because U4 runs after U1 and U3
and rebases onto their result, the section 5.2 boundary is never a concurrent edit.

**KTD7: `plan_path` is safe in the migration; `orchestration_ref` is not.** `plan_path` points at
`docs/plans/<date>-<topic>-plan.md`, and plan documents do not move. `orchestration_ref` points at
`docs/plans/<date>-<topic>-spec.json`, which does. Saga ticks are git-ignored and machine-local, so
this run cannot migrate ticks on other machines; U4-B's commit states that limit explicitly rather than
implying every pointer was fixed.

**KTD8: The migration destination is `docs/workflows/`, and the write-path conventions change first.**
Moving artifacts without changing the conventions that produce them refills `docs/plans/` on the next
`/plan` run. The convention change is therefore the first step of U4-B and the move is the second.
Stems are preserved, so `docs/plans/<stem>-spec.json` becomes `docs/workflows/<stem>-spec.json`.

---

## Implementation Units

Four implementation units and one integration step. Every unit produces a child-scoped commit on its
own branch; no unit opens a pull request, and no unit changes a version or release surface.

Order, with the dependency reason on each edge:

`U1 + U2 concurrently --> U3 (needs U1's settled frontmatter contract) --> U4 (needs U1 and U3 settled) --> U5 integration`

Custody, so the concurrent pair cannot collide and the serial chain cannot invalidate its predecessors:

| Unit | Owns | Shares | Must not touch |
|---|---|---|---|
| U1 | `plan/SKILL.md:212-226` and `:283-290`; `plan-sections.md:173-197`; a new `saga-spec.md` plan-document subsection; a new conformance test | `saga-spec.md` — new subsection only | `plan/SKILL.md:300-566`; the saga envelope field table |
| U2 | `scripts/saga.py` save path; `plan/SKILL.md:567-618`; `saga-spec.md:498` | `saga-spec.md` — the `/plan` consumer row only | `dispatch-table.md`; `_SAVE_SCALAR_DEFAULTS`; `loop/SKILL.md` (read-only) |
| U3 | A new Phase 0 intake subsection in `plan/SKILL.md`; a new `saga-spec.md` pre-answer section; `scripts/plan_pre_answers.py` | — | Phase 3, Phase 5.2, Phase 5.2a, Phase 5.3 |
| U4 | `plan/SKILL.md` section 5.2a and the `:300-306` guard; `work/SKILL.md` section 1.5; `operator-choice.md`; `execution-strategy.md`; the new plugin; the write-path lines listed in U4-B | — | U1's required-field sentences; U2's `--phase-status complete` lines; U3's Phase 0 subsection |

U1 and U2 share only `plugins/saga/references/saga-spec.md`, in different regions: U1 adds a new
plan-document subsection, U2 edits the `/plan` consumer row at line 498. Nothing else overlaps, and
neither reformats the file.

### U1. Make the plan artifact a strict contract

Close the frontmatter drift, require `backend:` on new plans, and add one recursive conformance check
covering declared fields and the marker triple together.

**Requirements:** R1, R2, R3, R4, R5, R6, R7, R8, R33.

**Files:** `plugins/saga/skills/plan/references/plan-sections.md`,
`plugins/saga/skills/plan/SKILL.md`, `plugins/saga/references/saga-spec.md`,
`tests/test_plan_artifact_conformance.py` (new).

**Steps:** Add `backend:` to the required-field sentence at `plan-sections.md:185` and replace the
"Omit it and `/work` behaves exactly as it did before" clause at `:191` with the required-on-new,
compatible-on-legacy statement. Reconcile `origin:` between `plan-sections.md:194-196` and
`plan/SKILL.md:224`, keeping the reference's conditional form. Bring the inline frontmatter block at
`plan/SKILL.md:212-222` into agreement with the reference by adding `backend:` and `deepened:`, keeping
the block a restatement rather than deleting it. Add a **new subsection** to
`plugins/saga/references/saga-spec.md` describing the plan-document contract, clearly separated from
the tick envelope, and add nothing to the envelope field table. Write the conformance test.

**Deliberately not changed:** `plugins/saga/skills/work/SKILL.md:262-270` already honours the field
when present and offers only when absent, which is exactly R2. Touching it would be the rejection P-D6
forbids. The telemetry instructions at `plan/SKILL.md:304`, `:583`, `:599`, `:607` and `:614` stay
under ruling 1.

**Test scenarios** in `tests/test_plan_artifact_conformance.py`:

Positive — a fixture carrying every required frontmatter field, a `backend:` value from the enum, and
all three markers passes with no findings.

Positive — the check evaluates frontmatter and markers in one pass, proven by a fixture that satisfies
the frontmatter contract and fails the marker triple and is reported by the same call that validated
the frontmatter.

Negative — a fixture with no `backend:` is classified legacy, reported, and does not fail the run,
whatever else it contains.

Negative — a fixture authored as a new-contract document and then stripped of `backend:` is the "new
document, missing required field" case. Because KTD3 makes absence the legacy signal, this fixture is
constructed to carry the new-contract marker the check keys on, and the test asserts the check reports
it without failing the run rather than asserting a corpus membership.

Negative — the check recurses: a fixture in a subdirectory of the scanned root that fails the marker
triple is reported. The real corpus run is asserted to include
`docs/plans/plugin-fleet-ideation-2026-07-03/gate-g-verification-report.md` as a reported finding,
which is the nested instance the launch receipt assigned to this unit.

Contract pin — the marker triple's three tokens as declared at `plan/SKILL.md:224-226` are asserted
unchanged, so a later edit cannot silently redefine plan recognition. This is a definition pin, not a
classification test: Document Review's recognition lives in `doc-review/SKILL.md` prose, this unit does
not own that file, and no home-grown classifier stands in for it.

Negative — the whole real corpus produces a report and a zero exit; the assertion is on the exit and on
the report being non-empty, never on a count or on a file name.

Mutation proof — deleting the required-field rule fails the first positive test; deleting the marker
half of the check fails the single-pass test; deleting the recursion fails the nested-report test.

**Acceptance mapping:** issue 922's criteria 1, 2, 3, 4, 7, 8 map to the steps and tests above.
Criterion 5 is withdrawn under ruling 1. Criterion 6 is satisfied by this document's Preflight
findings and is not a code step. Criterion 9 is U5.

### U2. Stop producing unreferenced plans and fix the finished-plan routing loop

Name the stranded document when a save fails, make Phase 5.3 check the exit, and make `/plan` assert
the completion its own dispatch row requires.

**Requirements:** R8, R9, R10, R11, R12, R13, R14, R33.

**Files:** `plugins/saga/scripts/saga.py`, `plugins/saga/skills/plan/SKILL.md:567-618`,
`plugins/saga/references/saga-spec.md:498`, `tests/test_saga_plan_save_and_routing.py` (new).
`plugins/saga/skills/loop/SKILL.md` is **read-only for this unit** — it is listed in issue 923's file
list, but the dispatch row lives in `loop/references/dispatch-table.md:73-74` and this unit changes
neither file.

**Steps, routing half:** Add `--phase-status complete` to both `save` variants at
`plugins/saga/skills/plan/SKILL.md:567-618`, and add `phase_status=complete` to the `/plan` writes
column at `plugins/saga/references/saga-spec.md:498`. The dispatch table is correct and is not edited.

**Steps, save half:** `plugins/saga/scripts/saga.py:1646` catches only `SagaSaveError`; a filesystem
failure from `envelope_path.write_text` at `:828` or `_atomic_write` at `:673-677` escapes as a
traceback. Catch the filesystem failure and, when `plan_path` is set, name that path in the surfaced
error so the operator sees exactly which document now has no tick. Add an instruction to Phase 5.3 to
check the save's exit status and stop rather than continuing to Phase 5.4.

**Deliberately not built:** no scanner, no state store, no queue, no daemon, no reconciliation pass,
and no change to `_SAVE_SCALAR_DEFAULTS`.

**Test scenarios** in `tests/test_saga_plan_save_and_routing.py`:

Negative — a save whose envelope write raises `OSError` with `plan_path` set produces a surfaced error
containing that path, asserted on the raised failure and the non-zero exit. The precondition asserted
is the **absence of the path in the message**, not that the failure is silent — it is not silent today.

Positive — after a successful save carrying `--plan-path`, `restore` resolves to that document.

Contract pin — the Phase 5.3 block's `--phase-status` value and the value the dispatch table's `plan`
row requires for `/doc-review` are read from the two documents and asserted equal. Removing
`--phase-status complete` from Phase 5.3 fails this test, which makes it the mutation proof that
matches KTD1.

Contract pin — Phase 5.3 carries an exit-status check instruction; deleting it fails the test.

Mutation proof — restoring the unnamed-path error fails the surfaced-error test; removing
`--phase-status complete` fails the agreement pin.

**Struck from cycle 1:** the `next_phase > phase` assertion. It passes at today's revision without any
Phase 5.3 edit, so it proves `saga.py` arithmetic rather than `/plan`'s write or `/loop`'s routing, and
it operates on the numeric `phase` counter rather than the `lifecycle_phase` axis the defect lives on.

**Acceptance mapping:** issue 923's criteria 1 through 7 map to the steps and tests above; criterion 4's
"default" is read as the value Phase 5.3 writes, not `_SAVE_SCALAR_DEFAULTS`, per KTD1; criterion 6 maps
to R8; criterion 8 is U5.

### U3. Versioned structured pre-answer contract

Give Plan a typed carrier for a decision a caller already settled, narrate it, and stop on a conflict.

**Requirements:** R8, R15, R16, R17, R18, R19, R20, R21, R29.

**Files:** `plugins/saga/skills/plan/SKILL.md` Phase 0 (a new subsection),
`plugins/saga/references/saga-spec.md` (a new pre-answer contract section),
`plugins/saga/scripts/plan_pre_answers.py` (new), `tests/test_plan_pre_answers.py` (new).

**Steps:** Implement the carrier exactly as KTD5 specifies — schema token `plan_pre_answers.v1`, two
decision fields with their declared enums, `caller` as envelope metadata. `plan_pre_answers.py` parses
the block and returns applied values, omitted fields, or a stop carrying its reason; it writes nothing
and reads no file. Add the saga-spec section defining the carrier. Add a Phase 0 subsection, written in
the same voice as today's Phase 0, describing the four evaluator rules as prose rather than as a
walk-through: apply and narrate with the caller named, fall through on absence, stop and surface on an
invalid or contradictory value, refuse an unknown schema token whole.

**Deliberately unchanged:** direct `/plan`; section 5.2a and its model-and-effort confirmation; and
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`. This unit ships Saga's typed surface
only, and a worker must not "finish" the Orchestrate side.

**Test scenarios** in `tests/test_plan_pre_answers.py`, all against `plan_pre_answers.py` unless marked
as a contract pin:

Positive — a carrier declaring `plan_pre_answers.v1` with a valid `backend` returns that value as
applied together with the `caller` string, asserted on both.

Positive — a carrier omitting `destination` returns it as omitted, with no stop and no applied value
for that field.

Negative — absence of any carrier returns nothing applied, nothing omitted-with-error, and no stop.

Negative — a `backend` value outside the enum returns a stop carrying the conflict; a fallback to any
default fails the test.

Negative — a supplied value contradicting an already-established value returns a stop rather than
preferring either side.

Negative — an unrecognised schema token returns a whole-carrier refusal with no field applied, asserted
field by field.

Negative — a third field beyond `backend` and `destination` is rejected rather than ignored; `caller`
is accepted as metadata and is not counted against the admission limit.

Contract pin — `plan/SKILL.md` phases 0 through 2 and phase 4 contain no `AskUserQuestion`, no
checklist, no questionnaire, and no "in order, ask" sentence introduced by this unit. This is the
rigidity guard, asserted as the absence of new prose shapes rather than as any statement about the
conversation.

**Struck from cycle 1:** the "leaves the normal conversation path intact" and "behaviourally identical
to the pre-unit contract" tests. Neither can be asserted without snapshotting Plan's questions, wording,
or order, which R29 forbids whether or not the test passes. The four assertions replacing them — nothing
applied, no stop, nothing narrated, and no new rigidity prose — cover the same criteria without touching
the conversation.

**Acceptance mapping:** issue 924's criteria 1, 3, 4, 6, 7, 9 map to the runtime tests; criterion 2 maps
to the absence test; criterion 5 maps to the absence test plus the rigidity pin; criterion 8 maps to R21
and the untouched section 5.2a; criterion 10 is U5.

### U4. Workflow extraction at the emitter-only boundary

Delete the counterfactual recommendation conditions without breaking the `#808` pins, move generated
Workflow artifacts to a directory the conventions actually write to, and extract the emitter into its
own plugin.

**Requirements:** R22, R23, R24, R25, R26, R27, R28.

#### Sub-part A — the counterfactual conditions

**Steps:** In each of the four files, delete the `if recommended is cc-workflows-ultracode` condition
and leave an unconditional never-pre-select sentence standing. `plan/SKILL.md:297` and
`operator-choice.md:199` already carry one, so `:304-306` and `:57-58` can be deleted outright. In
`work/SKILL.md` (`:53`, `:275-276`) and `execution-strategy.md` (`:158-159`, `:203-204`) no
unconditional pin survives the deletion, so one branch in each file is **rewritten** into an
unconditional statement rather than removed. Confirm no file claims Workflow enforces a stronger
sandbox than inline, and correct any that does — at this revision none does, so this step is a
confirm, not a write.

**Files:** `plugins/saga/skills/plan/SKILL.md:300-306`,
`plugins/saga/skills/work/SKILL.md:53` and `:275-276`,
`plugins/saga/references/operator-choice.md:57-58`,
`plugins/saga/skills/work/references/execution-strategy.md:158-159` and `:203-204`.

**Test scenarios:** `tests/test_saga_plugin.py:714` and `:742` must both stay green; they are the
regression pins and this unit does not edit them. Add, in `tests/test_workflow_extraction.py`, a
negative assertion that no file contains an "if the recommender suggests `cc-workflows-ultracode`"
condition, and a positive assertion against `recommend_execution_backend`'s real return across the
trigger matrix that `cc-workflows-ultracode` never appears as `recommended`. The mutation proof is that
removing the explicit-only guard fails the implicit-selection test.

#### Sub-part B — the artifact location split

Scoped to the smallest change that serves settled decision P-D3: change the conventions that write new
artifacts, move what those conventions produced, update live pointers only.

**Steps, in order.** First change every live write-path convention to `docs/workflows/`:

| File | Lines |
|---|---|
| `plugins/saga/skills/plan/SKILL.md` | `:513`, `:523-524`, `:530`, `:564-565` |
| `plugins/saga/skills/plan/SKILL.md` (Phase 5.3, U2's range) | `:600` |
| `plugins/saga/skills/work/SKILL.md` | `:350`, `:420`, `:471` |
| `plugins/saga/references/operator-choice.md` | `:274` |
| `plugins/saga/references/execution-spec.md` | `:400`, `:407-408`, `:421` |

`plan/SKILL.md:600` sits inside U2's Phase 5.3 range and `work/SKILL.md:471` inside Work's own prose;
both are U4-owned **for this commit only**, and U4 must change the path on those lines and nothing else
about them. U4 must not alter U1's required-field sentences, U2's `--phase-status complete` lines, or
U3's Phase 0 subsection while doing so.

Second, move the generated artifacts those conventions produced — the `.workflow.js` and `-spec.json`
files at the top level of `docs/plans/` — into `docs/workflows/` with their stems preserved, in the
same commit as the convention change.

Third, update live pointers only. Live means a path a program or a current instruction resolves.
Historical citations in `docs/reviews/`, `docs/work-sessions/`, `docs/sdlc-issue-drafts/` and
`CHANGELOG.md` record what a path was at the time and are not rewritten.

**Explicitly deferred, not moved by this unit:** the fleet-ideation tree under
`docs/plans/plugin-fleet-ideation-2026-07-03/` — its `survivors/*.json` seeds, its sibling JSON files,
and its nested verification report — and the top-level non-plan markdown documents (the briefs, the
prompt, the workflow-design and metrics documents, the execution-order and autonomous-driver documents,
and the two orchestrate documents). None are Workflow outputs, so parking them in a Workflow-owned tree
would be a custody error. They join the marker-failing documents in the deferred corpus pass.

**Consequently R27 is scoped to the artifacts this unit moves.** `docs/plans/` will not contain only
Plan documents when U4-B lands, and this plan does not claim it will. What U4-B delivers is that no
*new* Workflow artifact lands there and that the ones the conventions produced are gone. The remaining
non-plan content is named above and deferred.

**Test scenarios** in `tests/test_workflow_extraction.py`:

Negative — no live write-path convention in the files listed above names `docs/plans/` for a
`.workflow.js` or `-spec.json` artifact.

Negative — no `.workflow.js` or `-spec.json` file exists at the top level of `docs/plans/`.

Positive — every moved artifact's live inbound references resolve, asserted against the real files
rather than a fixture.

Mutation proof — restoring a `docs/plans/` write-path convention fails the first negative test.

#### Sub-part C — the emitter extraction

**Steps:** Create the new plugin following `plugins/team-execution/`'s structure. Move
`plugins/saga/scripts/workflow_emitter.py` and the workflow-script emitter path from
`plugins/saga/scripts/execution_spec.py` (`emit_workflow_script` at `:3769` and its Workflow-named
helpers at `:968`, `:972`, `:3609`, `:3698`) into it, together with the Workflow protocol prose from
`plan/SKILL.md` section 5.2a and `work/SKILL.md` section 1.5. Leave in Saga the spec schema,
validation, tier resolution, `team_emitter.py`, and the typed integration contract that recognises the
backend, records the explicit selection, validates availability, invokes the extracted emitter, and
consumes its structured result.

**Files:** a new plugin directory with its own skill, references, tests and release surfaces;
`plugins/saga/scripts/execution_spec.py`; `plugins/saga/scripts/workflow_emitter.py` (removed);
`plugins/saga/skills/plan/SKILL.md` section 5.2a; `plugins/saga/skills/work/SKILL.md` section 1.5;
`plugins/saga/references/execution-spec.md`.

**Test scenarios:**

Positive — the Workflow backend is still selectable and still emits a script from a spec, pinned
against the extracted emitter's real emit path. This is the anti-regression pin for issue 808. It does
not claim an end-to-end Workflow tool launch, which this continuous-integration environment cannot
perform; the existing `tests/test_workflow_emitter.py` and `tests/test_saga_workflow_emitter.py`
already cover emit and must stay green against the new location.

Positive — Saga's retained integration contract recognises the backend, records the explicit selection,
validates availability, and consumes the structured result, with the detailed protocol absent from
Saga's skill files.

Positive — `team_emitter.py` and `/outcome` still resolve the spec schema from Saga after the move, so
the shared substrate is proven not to have followed the emitter out.

**Deliberately unchanged:** the backend stays runnable and explicit-invocation-only under issue 808;
`plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` and its `BACKEND_NOTES` are not edited,
so Orchestrate keeps pre-answering `inline`; `plugins/team-execution/` is a precedent to follow, not to
redesign; and the spec-substrate split is out of scope entirely.

**Acceptance mapping:** issue 925's criteria 1 and 3 map to sub-part C; criterion 2 maps to sub-part C's
first test and sub-part A's implicit-selection test; criterion 4 maps to sub-part C's prose moves;
criterion 5 to sub-part A; criterion 6 to sub-part A's confirm step; criterion 7 to the non-steps above;
criterion 8 to sub-part B as scoped; criterion 9 to sub-part A's mutation proof; criterion 10 is
satisfied by operator ruling 2, which decomposed the unit rather than letting it expand silently;
criterion 11 is U5.

### U5. Integration — release surfaces and the wave gate

Centralize every version and release-surface change at integration, after all four units settle.

**Requirements:** R31, R32.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, `tests/test_saga_plugin.py:48` (the Saga version pin, which asserts
`0.148.0` and must move with the bump), plus the new plugin's own release surfaces and its
marketplace entry.

**Steps:** Freeze the integrated wave revision. Bump the Saga version once from 0.148.0 for all landed
units, serialized against the open issue 912 which also touches these files. Move the version pin in
the same commit. Add the new plugin's marketplace entry, validating the JSON after the edit. Write one
CHANGELOG entry per landed unit. Run the full gate in the background per this repository's
`CLAUDE.md`, and read `/tmp/gate-run/result.txt` — the marker is cleared at start, so its absence means
still running or killed, never green.

**Test expectation:** none — this unit changes only metadata, and the existing version and metadata
drift guards cover it.

### Coordinator-owned gate between U1/U2 and U3

The approved run amendment requires a first runnable checkpoint after P1 and P2: a disposable Claude
workspace proving a referenced plan with markers and `backend:`, a visible save failure naming the
stranded document, and completed-plan forward routing. **This is a coordinator gate, not unit work.**
It uses the isolated source candidate and must not replace the shared installed Saga runtime, which
issue 912 depends on. No worker may refresh the shared install to "help".

---

## Scope Boundaries

### Out of scope

- Plan's `Shaping` and `Ready` board-move sentences. Child 927 under parent 919 owns them.
- Any re-decision of the Claude Code Workflow backend's fate. Issue 808 settled it.
- Any removal or caveat of model-and-effort confirmation. Settled decision P-D5 settled it.
- A repository-level unreferenced-plan scanner. Settled decision P-D7 rejects it.
- Consolidation of the duplicated lifecycle-position prose. No two copies disagree yet.
- Any bulk rewrite, migration, or reformat of existing plan documents to add `backend:`.
- Orchestrate's side of the pre-answer contract, and any edit to
  `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`.
- Unit P5, issue 926. It is out of Wave 1 entirely; its gate, issue 927, is open.
- Any state store, daemon, registry, scoring system, or multi-tenant, internet-scale, high-availability,
  or regulatory machinery.

### Deferred to Follow-Up Work

- **The spec-substrate split.** Moving `execution_spec.py`'s schema, validation and tier resolution out
  of Saga would take `team_emitter.py` and `/outcome` with it and touch the 50 modules that import it.
  Operator ruling 2 places it outside this run.
- **The corpus pass.** The documents under `docs/plans/` that fail the marker triple, the fleet-ideation
  tree, and the top-level non-plan markdown documents named in U4-B. U4-B moves only the generated
  Workflow artifacts its own conventions produced.
- **Orchestrate's adoption of the U3 carrier** in place of the prose injection at
  `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py:107-113`.
- **Admitting further fields to the carrier** beyond `backend` and `destination`. The schema token
  exists so this can happen without breaking older callers.
- **Migrating `orchestration_ref` pointers in saga ticks on machines this run cannot reach.**

---

## Review dispositions — cycle 2

Every major from the independent Plan Document Review, and the minors worth recording, with where the
change landed.

| Finding | Disposition |
|---|---|
| P4-A deletes phrases `test_saga_plugin.py:714-770` pins | **Accepted.** Verified from source: `work/SKILL.md` and `execution-strategy.md` retain no unconditional pin after a naive deletion. Sub-part A now rewrites one branch per file instead of deleting both |
| P1 plan-doc contract in the saga envelope table | **Accepted.** U1 adds a separate saga-spec subsection; the envelope field table is on U1's must-not-touch list |
| P1 legacy-versus-new contradicts KTD3 | **Accepted.** KTD3 restated as absence-is-legacy; the "new document missing the field" case is now a constructed fixture |
| Do not pin 136 / 132 / 25 | **Accepted.** All corpus integers removed from requirements and tests; R33 forbids pinning any of them; the preflight recount is kept as a dated observation with derivation commands |
| P1 check must say recursive-or-not | **Accepted.** R5 declares recursion; the nested verification report is named as an expected finding |
| P1 R6 substitutes a classifier for Document Review | **Accepted.** R6 rewritten as a definition pin; the "classified as a plan" wording is gone and `doc-review/SKILL.md` stays outside U1 |
| P2 `next_phase` test proves nothing | **Accepted.** Struck, and the `_next_phase` corroboration removed from the preflight reasoning as the wrong axis |
| P3 carrier transport / version / caller unspecified | **Accepted.** KTD5 specifies the JSON shape, the `plan_pre_answers.v1` token, the invocation-context transport, both enums, and `caller` as envelope metadata |
| P3 two tests would freeze the conversation | **Accepted.** Both struck and replaced by four assertions on nothing-applied, no-stop, no-narration, and no new rigidity prose |
| P3 helper unnamed | **Accepted.** `plugins/saga/scripts/plan_pre_answers.py` named and added to U3's file list; the runtime-versus-contract-pin split is stated per test |
| P4-B no destination, no write-path change | **Accepted.** KTD8 names `docs/workflows/`; the convention change is step one and all eleven write-path lines are listed |
| P4-B inventory wrong | **Accepted.** Re-derived: 17 files under `survivors/`, 7 sibling JSON files in the ideation directory, and ten top-level non-plan markdown documents. The "only Plan documents" claim is retracted and replaced by a scoped claim |
| P4-B larger than the evidenced need | **Accepted.** Scoped to convention change, the artifacts those conventions produced, and live pointers only; the ideation tree and non-plan markdown are deferred |
| P4-B serial custody expansion | **Accepted.** U4's must-not-touch column names U1's required-field sentences, U2's `--phase-status complete` lines, and U3's Phase 0 subsection; `plan/SKILL.md:600` and `work/SKILL.md:471` are U4-owned for that commit only |
| U2 lists `loop/SKILL.md` with no edit | **Accepted.** Marked read-only with the reason |
| KTD5-versus-custody on `:300-305` | **Accepted.** With ruling 1 retaining the telemetry, P1 has no reason to enter that range; KTD6 gives it to U4-A alone |
| First runnable checkpoint unnamed | **Accepted.** Added as a coordinator-owned gate with the no-shared-install-refresh rule |
| Issue 923 criterion 6 not on U2's requirements | **Accepted.** R8 added to U2 |
| Issue 925 criterion 7 has no explicit non-step | **Accepted.** Not editing `orchestrate.py` is now an explicit non-step in U3 and U4 and an out-of-scope line |
| U5 omits the version pin test | **Accepted.** `tests/test_saga_plugin.py:48` added to U5's files and to R31 |
| `OSError` is already a traceback, not silent | **Accepted.** KTD2 and R9 restated: the repair is the named path and the Phase 5.3 exit check, and the test asserts the missing path rather than a silence that does not exist |
| U4 "still runs" pin needs a named surface | **Accepted.** Pinned to emit-from-spec against the extracted emitter, with an explicit statement that no end-to-end Workflow launch is claimed |
| Cycle 1 cited `:371` and `:441` as default-path confirmation | **Accepted as a correction.** Both are inside section 5.2a; P-D5 is honoured by not editing 5.2a and adding no default-path prompt |

One addition beyond a filed file list is recorded rather than assumed: **U3 adds
`plugins/saga/scripts/plan_pre_answers.py`, which issue 924 does not list.** Issue 924's criteria demand
a whole-carrier refusal and a stop-not-default, which prose plus grep cannot prove, and every comparable
typed envelope in this repository has a validator module. If the operator would rather ship U3 as a
document contract with grep pins only, that is a smaller unit and this plan can be trimmed to it.

---

## Verification

```bash
# Corpus figures, derived at run time — never pinned
ls docs/plans/*.md | wc -l
grep -lE '^backend:' docs/plans/*.md | wc -l

# The routing contract must agree end to end
grep -n "phase-status" plugins/saga/skills/plan/SKILL.md
grep -n "phase_status" plugins/saga/references/saga-spec.md | grep "/plan"
sed -n '69,80p' plugins/saga/skills/loop/references/dispatch-table.md

# The conversation must not have gained rigidity
grep -nEi "checklist|questionnaire|answer each|in order, ask" plugins/saga/skills/plan/SKILL.md

# The 808 pins must survive unit U4-A
uv run pytest tests/test_saga_plugin.py -q -k "cc_workflows_explicit_invocation_only or backend_offer_contract_docs_pin"
grep -rniE "never pre-select|do not pre-select" plugins/saga/skills/plan/SKILL.md plugins/saga/skills/work/SKILL.md plugins/saga/references/operator-choice.md plugins/saga/skills/work/references/execution-strategy.md

# No live write-path may still send an artifact into docs/plans/
grep -rn "docs/plans" plugins/saga/skills plugins/saga/references | grep -E "workflow\.js|spec\.json"

# Board-move sentences must be untouched by this run
git diff main -- plugins/saga/skills/plan/SKILL.md | grep -nE "Shaping|Ready for Planning"

uv run pytest tests/ -q -k "plan_artifact or plan_save or pre_answer or workflow_extraction"
uv run ruff check plugins/saga tests/
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
cat /tmp/gate-run/result.txt
```
