---
title: Saga Plan maintenance — issue 926 (unit P5, issue 918 Wave Two)
type: docs
status: active
date: 2026-09-04
backend: inline
---

# Saga Plan maintenance — issue 926 (unit P5, issue 918 Wave Two)

## Summary

Four documentation statements inside the Saga plugin describe a system that no longer exists, and two
cheap checks stop them coming back. Three of the four live in `plugins/saga/skills/plan/SKILL.md` (a
derived-state sentence that credits Plan with an artifact Work produces, a trigger clause that asserts
a commit Plan never makes, and an HTML comment saying resolved effort is emitted but never honored);
the fourth is a table row in `plugins/saga/references/saga-spec.md` that lists six of the ten fields
Plan's own save invocation writes. Nothing in this unit changes behaviour.

## Problem Frame

Two separate corrections left residue. The 0.145.0 rewrite that removed Plan's direct board writes
introduced prose describing the post-rewrite system inaccurately, and issue 927's submission-path
change rewrote the same paragraph without revisiting either claim. Separately, issue 363 shipped the
effort-honoring seam and closed, but the comment that predates it still tells a reader — human or
agent — that the effort half of every tier decision is decorative. That comment is the higher-cost
one: it is read by the agent executing Plan, and it argues against a control the operator actually
has.

The saga-spec row is drift of a third kind. Plan's Phase 5.3 prose at
`plugins/saga/skills/plan/SKILL.md:660-665` claims its flags "carry the `/plan` consumer row from
`references/saga-spec.md` §11". The row at `plugins/saga/references/saga-spec.md:513` does not carry
four of them. The skill asserts an agreement that does not hold, so a reader who trusts either
document is misled by the other.

---

## Preflight — what is still live at base commit c84af7ad

Every line number below was re-resolved against
`c84af7adc222bf3ecb60db34bc2cfdcba4073c68` in the worktree on branch
`work/cp918-p5-maintenance`. The line numbers filed on issue 926 are stale by construction and were
not inherited.

| Correction | Site at c84af7ad | Verdict |
|---|---|---|
| 1. Derived state names a Work artifact | `plugins/saga/skills/plan/SKILL.md:344-345` | **Live.** The sentence ends "the committed plan, the saga tick, and the work-session path." `plugins/saga/references/saga-spec.md:514` assigns `work_session_paths` to `/work`; the `/plan` row at `:513` does not list it. |
| 2. Plan does not guarantee a committed plan | `plugins/saga/skills/plan/SKILL.md:338` (Trigger) and `:344` (assertion) | **Live, and the sharper instance is not where the issue filed it.** See KTD1. |
| 3. Effort-emission comment is stale | `plugins/saga/skills/plan/SKILL.md:544-550` | **Live.** The comment names issue 363's `EFFORT_RIDER`/cascade as future work; it shipped and the issue is closed. `plugins/fleet-core/scripts/fleet_commons/effort_rider.py:77` defines `inject_effort(prompt, effort, spawn_kind)` and `plugins/fleet-core/references/effort-convention.md:47-66` documents the three spawn kinds. |
| 4a. Consumer row omits declared fields | `plugins/saga/references/saga-spec.md:513` | **Live.** The row names six writes; Plan's Phase 5.3 save blocks at `plugins/saga/skills/plan/SKILL.md:620-650` pass ten non-identity flags. Missing: `orchestration_mode`, `orchestration_recommended`, `orchestration_ref`, and `orchestration_operator_choice` (auto-derived, per `:657-658`). |
| 4b. Documentation card disagrees with the skill | `plugins/saga/references/saga-spec.md:646-676` (section 14) | **Already resolved — no repair needed.** See below. |

**Correction 4b was fixed by Wave One and needs no work here.** Issue 926 was filed before section 14
existed. `git log -S "Plan-document contract (distinct from the tick envelope)"` names one commit,
`1c1c04a9` ("Saga Plan Wave 1"), so the card is Wave One's own output. Compared field by field against
the skill it agrees on every point: section 14 delegates the required-field set to
`plugins/saga/skills/plan/references/plan-sections.md` rather than restating it (`:652-654`); its
`origin` rule at `:656-657` matches `plugins/saga/skills/plan/SKILL.md:306-308` and
`plan-sections.md:195-197`; its marker triple at `:664-666` matches `SKILL.md:309-310`; its `backend`
narrowing matches `plan-sections.md:186-194`. This plan asserts no disagreement it could not
demonstrate, and changes nothing in section 14.

**Correction 2's own framing, decided.** The brief asked whether the `Trigger:` clause at
`plugins/saga/skills/plan/SKILL.md:338` already satisfies issue 926's acceptance criterion. It
partly does and partly does not, and the two halves need different treatment — KTD1 records the
reasoning and the resulting split.

**Both corrected sentences are prose issue 927 wrote.** `git blame` attributes
`plugins/saga/skills/plan/SKILL.md:337-345` to commit `5a3691cf` ("fix(saga): re-aim the
zero-direct-write guard and submit the five board moves (#927 U1,U2)"). That does not put them out of
bounds, but it narrows what may be touched to the byte — KTD2.

---

## Requirements

R1. `plugins/saga/skills/plan/SKILL.md` no longer names the work-session path among what Plan
durably produces.

R2. `plugins/saga/skills/plan/SKILL.md` no longer asserts that Plan produced a *committed* plan.

R3. The `Trigger:` clause at `plugins/saga/skills/plan/SKILL.md:338` no longer contains the phrase
"exists, is committed", so issue 926's `grep -nEi "exists and is committed"` verification returns
nothing.

R4. The board-move sentence at `plugins/saga/skills/plan/SKILL.md:338-341` beginning `**Move:**`,
and the `reconcile_controller.py reconcile` invocation block at `:348-354`, are byte-identical to
their content at `c84af7ad`.

R5. Section 0.6's `Move:` sentence at `plugins/saga/skills/plan/SKILL.md:125-127` and its
invocation block at `:141-146` are byte-identical to their content at `c84af7ad`.

R6. The `EFFORT-EMISSION MARKER` comment at `plugins/saga/skills/plan/SKILL.md:544-550` no longer
claims effort is unconsumed, unhonored, or awaiting a mechanism, and no longer describes issue 363's
work as future.

R7. The replacement comment names the single honoring seam
(`fleet_commons.effort_rider.inject_effort`), distinguishes the two real-knob spawn kinds
(`workflow`, `external-engine`) from the one labeled-proxy spawn kind (`agent`), and points at
`plugins/fleet-core/references/effort-convention.md` as the canonical description.

R8. The replacement comment cites no line number in any other file.

R9. Plan's model-and-effort confirmation is unchanged. Specifically
`plugins/saga/skills/plan/SKILL.md:492`, `:514`, and `:538-542` are byte-identical to their content
at `c84af7ad`.

R10. The `/plan` row at `plugins/saga/references/saga-spec.md:513` names every field Plan's Phase
5.3 save blocks write, and names no field they do not.

R11. Every field name the corrected row uses exists in the envelope field table at
`plugins/saga/references/saga-spec.md:98-160`.

R12. The corrected row's parseable field set is exactly the flag set of Phase 5.3's save blocks
minus the two identity flags `--kind` and `--id`. Any other content in the cell — a condition, a
cross-reference, an explanatory aside — sits inside parentheses so the parse does not see it.

R13. A test fails when any Markdown file under `plugins/saga/` claims resolved effort is emitted but
not consumed, honored, dispatched, or enforced. It matches the claim class, not one literal string.

R14. R13's check does not fire on the two legitimate uses of "unconsumed" already in the tree:
`plugins/saga/references/envelope-token.md:12` and
`plugins/saga/scripts/bridge_signatures.py:112`.

R15. A test derives the `/plan` consumer row's expected field set from Plan's Phase 5.3 save blocks
and compares it to the row. It maintains no second hardcoded list of field names.

R16. R15's check fails if a flag is added to a Phase 5.3 save block without the row being updated,
and fails if a field is added to the row without a corresponding flag.

R17. Both tests are selected by `uv run pytest tests/ -q -k "saga_spec or plan_docs or consumer_row"`.

R18. No file outside `plugins/saga/skills/plan/SKILL.md`, `plugins/saga/references/saga-spec.md`,
and one new file under `tests/` is modified by the worker.

R19. `bash scripts/gate.sh` exits 0.

---

## Key Technical Decisions

KTD1. **Split correction 2 by grammatical role: the assertion is the defect, the trigger is a
precondition — repair both, differently.** The brief asked whether `Trigger:` framing already
satisfies the acceptance criterion. Two clauses carry the word "committed" and they are not the same
kind of statement. At `:344` the sentence reads "derived from what this skill durably produced: the
committed plan, …" — that is an assertion about Plan's own output, and it is false, because Plan
writes a file and never runs `git commit`; grep confirms Plan's SKILL.md instructs a commit nowhere
(the only near-hit, `:389`, describes why the plan document is the right home for the backend
decision, not an action Plan takes). At `:338` the clause reads "**Trigger:** the plan exists, is
committed, and has cleared review" — that is a *precondition* for submitting the board move, and a
precondition is not a claim about what Plan produced. Read alone it is defensible. It is still
repaired, for two reasons that have nothing to do with truth: issue 926's acceptance criterion names
the phrase explicitly, and its verification block greps for it, so leaving it fails the unit on its
own terms. The rejected alternative was to leave `:338` untouched and argue the framing in the review
— rejected because a criterion the reviewer can grep is not worth contesting for one clause. The
repair at `:338` is therefore minimal and preserves the precondition's force: the plan document
exists and has cleared review. The repair at `:344-345` is the substantive one.

KTD2. **Freeze the board-move bytes with a test, not with care.** Issue 927 authored the entire
paragraph containing both corrections, and issue 926 forbids editing the board-move sentences. Those
two facts collide inside one paragraph, and a boundary that depends on the worker's attention is the
boundary most likely to fail. The unit therefore pins the exact protected spans — section 0.6's
`Move:` sentence and invocation block, section 5.0's `Move:` sentence and invocation block — as
byte-identical assertions the worker records in the unit evidence (R4, R5). The alternative,
predeclaring only prose boundaries, was rejected: this unit's whole risk is a two-line edit landing
one line too far.

KTD3. **The negative check parses HTML comment blocks and prose sentences separately, because the
stale claim spans lines.** A line-oriented grep splits "This is emission only: /plan" at
`plugins/saga/skills/plan/SKILL.md:546` from "dispatch mechanism honors it yet" at `:548`, so no
single line carries the whole claim and a line-by-line check would miss it while appearing to work.
The check therefore reads each file whole, extracts every `<!-- ... -->` block plus every sentence,
normalizes internal whitespace, and applies the claim pattern to each normalized span. Rejected: a
whole-file regex with `re.DOTALL`, which matches an effort mention in one section against a negation
in another and produces false positives across a 700-line file.

KTD4. **The negative check's pattern requires an effort token AND a not-honored token in the same
span — the conjunction is what makes it a class check rather than a string check.** Two legitimate
uses of "unconsumed" already live under `plugins/saga/`
(`references/envelope-token.md:12`, "previously-unconsumed engine loophole", and
`scripts/bridge_signatures.py:112`, "launched-unconsumed"), so any pattern keyed on that word alone
is red on arrival. Requiring an effort token in the same span excludes both, and requiring only a
*class* of negation — `no|not|never|lacks|awaits|yet` near
`consum|honor|honour|dispatch|enforc|read`, plus the standalone idiom `emission only` — means a
reworded relapse is caught too. Rejected: pinning the exact sentence, which prevents nothing.

KTD5. **The positive check derives the expected field set from Phase 5.3's fenced save blocks,
because those blocks are already a pinned parse.** `tests/test_saga_plan_save_and_routing.py:398-403`
extracts Phase 5.3 by its `### 5.3` / `### 5.4` heading boundary and at `:453-458` pulls flags out of
the fenced blocks containing `saga.py save` — a parse the repo already depends on and already
protects. Reusing its shape means the new check inherits a stable substrate rather than inventing
one. The expected set is the **union** across both save variants, since the inline variant omits
`--orchestration-ref` and the ultracode variant omits `--deploy-autonomy`; an intersection would
under-specify the row. Rejected: parsing `saga.py`'s `argparse` declarations, which describe every
field any command may write, not the ones Plan writes.

KTD6. **The row's parse rule is "backticked identifiers outside parentheses", and the row is
rewritten to satisfy it.** The cell today contains `` `destination=nonprod-deploy` `` inside an aside
about `deploy_autonomy`, so a naive token scan double-counts `destination`; and
`orchestration_operator_choice` is written by Plan but has no flag, so an exact-equality check would
reject it. Stripping parenthesized spans before tokenizing solves both: conditions and
cross-references live inside parentheses and are invisible to the parse, field names live outside it.
The auto-derived `orchestration_operator_choice` is therefore named inside a parenthetical on
`orchestration_mode`, which is also where it belongs semantically. The parse rule is stated in the
spec beside the row so a future editor knows the convention exists. Rejected: an allowlist of
derived-but-flagless fields, which is the second hardcoded list issue 926 explicitly refuses.

KTD7. **Both checks ship in one new test file, `tests/test_saga_spec_consumer_row.py`.** The file
name matches two of the three `-k` filter terms (`saga_spec`, `consumer_row`) and the negative test
function carries the third (`plan_docs`), so issue 926's verification command selects both without
the filter being changed. They share one subject — drift between Saga's Plan skill and Saga's
specification — and one set of path constants. Rejected: two files, which duplicates the constants
for no separation that matters here.

KTD8. **Leave the team-execution copy of the stale comment alone and file a follow-up.** See the
disposition below.

---

## Disposition — the duplicate stale comment in team-execution

**Recommendation: a follow-up issue, not this unit.**

A second copy of the same stale claim sits at
`plugins/team-execution/skills/team-execution/SKILL.md:234-240`. Its wording differs — "#362 adds no
dispatch-time honoring of the `effort` half; the Agent tool has no effort knob yet" — and one half of
that is still true: the native Agent-tool path genuinely has no effort knob, which is exactly why
`inject_effort`'s `agent` branch prepends a labeled proxy. What is false is the present-tense claim
that no dispatch-time honoring exists, and the framing of issue 363 as pending.

Three reasons it stays out of this unit:

1. **It expands custody to a second plugin and a second release surface.** `SKILL.md` text is
   agent-facing guidance, so correcting it triggers the repository's same-PR release-surface rule
   (`CLAUDE.md`, Development Workflow item 6): a `team-execution` version bump, a `team-execution`
   CHANGELOG entry, and a second `.claude-plugin/marketplace.json` edit. This unit is the smallest,
   last-in-lane maintenance sweep; doubling its integration surface for a two-line comment inverts
   its purpose. Issue 926's own stop boundary names custody expansion first.
2. **Issue 926's expected-files list does not include it, and its negative test is scoped to Saga
   files.** The scope is deliberate, not an oversight.
3. **The follow-up is genuinely small and loses nothing by waiting.** The comment misleads an agent
   reading Team Execution's worker table; it does not misroute execution.

**What this unit does instead of ignoring it:** R13's check is scoped to `plugins/saga/`, and the
test file states in a docstring that a known duplicate lives in `team-execution` under a named
follow-up issue. The scoping is then visible and tracked rather than accidental — the failure mode
worth avoiding is a check that looks repository-wide and quietly is not.

**Cost of overruling this:** roughly one extra hour and one extra release surface. If the operator
prefers a single sweep, folding it in is a two-line edit plus the `team-execution` bump, and R13's
scope widens from `plugins/saga/` to `plugins/`.

---

## Implementation Units

One unit, one worker, serial, inline backend. The corrections all land in two files that fully
collide, so there is no parallel decomposition to find; the lettered steps below are execution order
within the single unit, not separable units.

### U1. Correct the four stale statements and add the two drift checks

Fix three sentences and one table row, then add one test file that stops each class of drift
recurring.

**Goal** — every documentation statement in the Saga plugin about what Plan produces, and about
whether resolved effort is honored, is true at merge; and two cheap checks make the next relapse a
red test rather than a reader's problem.

**Requirements** — R1 through R19.

**Dependencies** — none. Issue 927 and its parent issue 919 shipped and closed; that dependency is
satisfied at the base commit.

**Files**

- `plugins/saga/skills/plan/SKILL.md` — modify (steps A, B, C)
- `plugins/saga/references/saga-spec.md` — modify (step D)
- `tests/test_saga_spec_consumer_row.py` — create (steps E, F)

**Approach**

*Step A — the derived-state sentence (R1, R2).* At `plugins/saga/skills/plan/SKILL.md:344-345` the
sentence currently ends "derived from what this skill durably produced: the committed plan, the saga
tick, and the work-session path." Drop the two false items and keep the true one, so it names the
plan document and the saga tick. Do not touch the sentence before it or the invocation block after
it.

*Step B — the trigger clause (R3).* At `plugins/saga/skills/plan/SKILL.md:338` remove "is
committed," from the trigger's list while preserving the precondition's force — the plan document
exists and has cleared review. The edit is confined to line 338; the `**Move:**` text beginning on
line 339 is not touched (R4).

*Step C — the effort comment (R6, R7, R8).* Replace the body of the `EFFORT-EMISSION MARKER` comment
at `plugins/saga/skills/plan/SKILL.md:544-550`. Keep the marker's first clause about the cell being a
`<model>/<effort>` pair sourced verbatim from the resolver — that is still accurate and other
documents cross-reference the marker. Replace the "emission only" claim with the current mechanism:
one honoring seam, `fleet_commons.effort_rider.inject_effort(prompt, effort, spawn_kind)`; the
`workflow` and `external-engine` spawn kinds carry effort on a real control; the `agent` spawn kind
prepends an `EFFORT_RIDER` directive, a labeled proxy rather than a native knob, because the Agent
tool has no per-call effort parameter. Point at
`plugins/fleet-core/references/effort-convention.md` for the canonical description and cite no line
numbers (R8) — a line citation in a comment is the same drift class this unit is repairing.

*Step D — the consumer row (R10, R11, R12).* Rewrite the Writes cell of the `/plan` row at
`plugins/saga/references/saga-spec.md:513` so its backticked identifiers outside parentheses are
exactly: `lifecycle_phase`, `phase_status`, `plan_path`, `destination`, `deploy_autonomy`, `adr_refs`,
`decisions`, `orchestration_mode`, `orchestration_recommended`, `orchestration_ref`. Conditions and
asides move inside parentheses — the `nonprod-deploy` condition on `deploy_autonomy`, the
ultracode-only condition on `orchestration_ref`, the note that `orchestration_operator_choice`
auto-derives from `orchestration_mode`, and the note that `decisions` renders as the tick's
`## Decisions` section. Add one sentence below the table stating the parse convention so a future
editor keeps field names out of parentheses and prose citations inside them.

*Step E — the negative drift check (R13, R14, R17).* In `tests/test_saga_spec_consumer_row.py`, read
every `*.md` under `plugins/saga/`. From each, extract the spans described in KTD3 — every
`<!-- ... -->` block and every sentence — normalize runs of whitespace to single spaces, and assert
no span matches the claim pattern of KTD4. On failure, report the file, the offending span, and which
pattern half matched, so the reader sees why rather than only that.

*Step F — the positive derived check (R15, R16, R17).* In the same file, extract Phase 5.3 of
`plugins/saga/skills/plan/SKILL.md` by its `### 5.3` / `### 5.4` boundary, collect the union of
`--flag` tokens across every fenced block containing `saga.py save`, normalize each to a field name
(strip the leading dashes, hyphens to underscores), and drop the two identity flags `kind` and `id`.
Parse the `/plan` row's Writes cell per KTD6 — strip parenthesized spans, then collect backticked
`[a-z][a-z_]*` tokens, taking the part before any `=`. Assert the two sets are equal, and report both
directions of the difference by name on failure.

**Patterns to follow**

- `tests/test_saga_plan_save_and_routing.py:32-37` for the module path constants
  (`ROOT`, `PLUGIN_ROOT`, `PLAN_SKILL`, `SAGA_SPEC`).
- `tests/test_saga_plan_save_and_routing.py:398-403` (`_plan_phase_53`) for the section extraction.
- `tests/test_saga_plan_save_and_routing.py:453-458` for pulling flags out of the fenced save blocks.
- `tests/test_saga_plan_save_and_routing.py:434-441` (`_spec_plan_write_phase_status`) for locating
  the `| **/plan**` row.
- `tests/test_saga_plan_save_and_routing.py:444-451` for the docstring convention that states the
  mutation proof — what edit makes this test fail.

**Test scenarios**

*Negative drift check.*

- Happy path — input: the tree as merged. Action: run the check. Expected: passes, because no span
  under `plugins/saga/` pairs an effort token with a not-honored token.
- Mutation proof — input: the pre-repair comment text restored into
  `plugins/saga/skills/plan/SKILL.md`. Action: run the check. Expected: fails, naming that file and
  the comment span. The worker runs this before declaring the unit done; a check that cannot fail is
  the defect class this repository has hit before.
- Rewording proof — input: a temporary span reading "the effort half is surfaced but nothing honors
  it". Action: run the check. Expected: fails, proving the pattern catches the class and not the
  original wording.
- Multi-line proof — input: a temporary comment splitting "emission only" and "no dispatch mechanism
  honors it" across two source lines. Action: run the check. Expected: fails, proving KTD3's
  whole-file span extraction works where a line-oriented grep would not.
- False-positive guard — input: the tree as merged, including
  `plugins/saga/references/envelope-token.md:12`. Action: run the check. Expected: passes; the
  "previously-unconsumed engine loophole" phrase carries no effort token in its span.

*Positive derived check.*

- Happy path — input: the tree as merged. Action: run the check. Expected: passes; the ten derived
  field names equal the ten row tokens.
- Drift-from-the-skill proof — input: a temporary `--orchestration-downgrade` flag added to a Phase
  5.3 save block. Action: run the check. Expected: fails, naming `orchestration_downgrade` as present
  in the skill and absent from the row.
- Drift-from-the-row proof — input: `orchestration_recommended` temporarily deleted from the row.
  Action: run the check. Expected: fails, naming it as present in the skill and absent from the row.
- Union-across-variants edge case — input: the tree as merged, in which `--deploy-autonomy` appears
  only in the inline save block and `--orchestration-ref` only in the ultracode block. Action: run
  the check. Expected: passes, proving the union is taken rather than the intersection.
- Parse-stability edge case — input: the corrected row, whose parentheses contain
  `destination=nonprod-deploy` and `orchestration_operator_choice`. Action: run the check. Expected:
  passes, proving parenthesized content is excluded and does not inflate the row's field set.
- Error path — input: `plugins/saga/references/saga-spec.md` with the `| **/plan**` row absent.
  Action: run the check. Expected: fails with a message naming the missing row, not an
  `IndexError` or a silent pass on an empty set. An empty expected set must never be treated as
  agreement.

**Verification**

- `grep -nEi "work-session|work session" plugins/saga/skills/plan/SKILL.md` returns nothing.
- `grep -nEi "exists and is committed" plugins/saga/skills/plan/SKILL.md` returns nothing.
- `grep -rnEi "no dispatcher|emission only|not consumed|unconsumed" plugins/saga/` returns only the
  two known-legitimate hits in `references/envelope-token.md` and `scripts/bridge_signatures.py`.
- `git diff HEAD -- plugins/saga/skills/plan/SKILL.md` shows changes confined to the derived-state
  sentence, the trigger clause, and the effort comment — no `Move:` line and no
  `reconcile_controller.py` invocation appears in the diff.
- `git diff HEAD --stat` names exactly three paths.
- `uv run pytest tests/ -q -k "saga_spec or plan_docs or consumer_row"` selects the two new tests
  alongside the existing plan-artifact conformance tests, and passes.
- Each mutation proof above was run and observed to fail before the unit is declared done.
- `GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh` and `cat /tmp/gate-run/result.txt` report green.

---

## Predeclared Saga Code Review lenses

The always-on four run without approval; the two conditionals below are the ones this diff makes
applicable, each with its reason. `previous-comments` is not applicable — this unit has no prior
review cycle.

| Lens | Class | Why it applies to this unit |
|---|---|---|
| `architecture-maintainability` | always-on | Auto-run; the derived check introduces a parse contract two documents now depend on. |
| `correctness` | always-on | Auto-run; the whole unit is a truth claim about what the code does, so a wrong replacement sentence is the primary defect mode. |
| `security` | always-on | Auto-run; expected to find nothing — no credential, boundary, or input path is touched. |
| `testing` | always-on | Auto-run; the two new checks are the unit's only executable output and each carries a mutation proof to audit. |
| `documentation-clarity` | conditional | Every changed byte outside `tests/` is documentation read by an agent at runtime; this lens is the unit's subject matter. |
| `agent-usability` | conditional | The corrected effort comment and the corrected consumer row are both read by agents executing Plan, so a replacement that is accurate but unclear still fails the unit's purpose. |

---

## Scope Boundaries

**Non-goals — out of scope for this unit and for its follow-ups.**

- Removing, weakening, or caveating Plan's model-and-effort confirmation. Decision P-D5 settled that
  it stays; R9 pins the specific lines.
- Editing any board-move sentence or submission invocation in sections 0.6 and 5.0. Issue 927 owns
  that prose; R4 and R5 pin the bytes.
- Consolidating the duplicated lifecycle-position prose. Decision P-D7 rejects it.
- Any behaviour change. No script, schema, enum, or command surface is modified.
- Touching the Workflow prose. The Wave One extraction unit owns all 590 lines.
- Adding a question, checklist, or fixed sequence to Plan's conversation.
- Renumbering or reformatting sections the corrections do not touch.
- Editing anything under `docs/code-reviews/`, `docs/evidence/`, or `docs/reviews/`.
- Reopening Wave One's carried residual findings. They were terminalized under the three-cycle
  best-available ruling.
- Repairing correction 4b. Section 14 agrees with the skill at the base commit; this plan asserts no
  disagreement it could not demonstrate.

**Not the worker's to write — the integrator's.** Saga's release surfaces are updated once at
integration, by the integrator: `plugins/saga/.claude-plugin/plugin.json`,
`plugins/saga/CHANGELOG.md`, `.claude-plugin/marketplace.json`, and the hard version pin at
`tests/test_saga_plugin.py:48`. **Recommended bump: `0.155.0` to `0.156.0`** — a minor bump. The
change is documentation plus two tests with no behaviour change, which reads like a patch, but the
plugin's recent history is unbroken minor bumps for exactly this shape of work (`0.151.0` through
`0.155.0` are all small documentation and test corrections; the last patch release was `0.142.1`).
Consistency with the installed-version story the operator reads is worth more here than semantic
precision on a plugin with no external consumers.

### Deferred to Follow-Up Work

- **The duplicate stale effort comment in Team Execution.** Correct
  `plugins/team-execution/skills/team-execution/SKILL.md:234-240` the same way step C corrects Saga's
  copy, and widen the negative check's scope from `plugins/saga/` to `plugins/`. Carries a
  `team-execution` version bump, a CHANGELOG entry, and a `.claude-plugin/marketplace.json` edit.
  Reasoning in the disposition section above.

---

## Open Questions

**One question for the operator, not blocking.** This plan takes the most defensible option and
records why; the operator may overrule either at review.

1. **Should the Team Execution duplicate be folded into this unit?** This plan says no and defers it,
   because correcting it drags a second plugin's release surfaces into the smallest, last-in-lane
   unit of the wave — reasoning and the cost of overruling are in the disposition section. The
   operator's call is cheap either way and does not block the worker: if folded in, step C gains two
   lines, R13's scope widens to `plugins/`, and the integrator bumps two plugins instead of one.

Correction 2's framing question, which the brief also raised, is **not** left open — KTD1 decides it
and states the reasoning.

---

## Sources / Research

All line numbers resolved against `c84af7adc222bf3ecb60db34bc2cfdcba4073c68`.

- `plugins/saga/skills/plan/SKILL.md:338` — the trigger clause (correction 2).
- `plugins/saga/skills/plan/SKILL.md:344-345` — the derived-state sentence (corrections 1 and 2).
- `plugins/saga/skills/plan/SKILL.md:544-550` — the `EFFORT-EMISSION MARKER` comment (correction 3).
- `plugins/saga/skills/plan/SKILL.md:620-650` — Phase 5.3's two save blocks; the derived check's
  source of truth.
- `plugins/saga/skills/plan/SKILL.md:660-665` — the prose claiming the flags carry the consumer row.
- `plugins/saga/references/saga-spec.md:513` — the `/plan` consumer row (correction 4a).
- `plugins/saga/references/saga-spec.md:514` — the `/work` row, which owns `work_session_paths`.
- `plugins/saga/references/saga-spec.md:121-125` — the envelope field table entries for the four
  orchestration fields.
- `plugins/saga/references/saga-spec.md:646-676` — section 14, checked and found already correct
  (correction 4b).
- `plugins/fleet-core/references/effort-convention.md:47-66` — the honoring seam and its three spawn
  kinds; the canonical replacement text for step C.
- `plugins/fleet-core/scripts/fleet_commons/effort_rider.py:77-95` — `inject_effort`'s implementation.
- `plugins/team-execution/skills/team-execution/SKILL.md:234-240` — the duplicate stale comment.
- `plugins/saga/references/envelope-token.md:12` and `plugins/saga/scripts/bridge_signatures.py:112`
  — the two legitimate "unconsumed" uses the negative check must not fire on.
- `tests/test_saga_plan_save_and_routing.py:398-469` — the parse the derived check reuses.
- `plugins/saga/references/lens-roster.json` — the always-on four and the conditional catalog.
- Issue 926 (child of issue 918) — the authoritative contract for this unit.
