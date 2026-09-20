# Document review — issue 1027, the build loop with a written exit criterion

## Review-result contract

| Field | Value |
|---|---|
| Target path | `docs/plans/2026-09-20-issue-1027-build-loop-exit-criterion-plan.md` |
| Reviewed revision | **working tree** — the plan was not yet in a commit when this review ran, and it ships in the same commit as this artifact. The branch base is `87a5329e` (`origin/parent/1018`). |
| Classification | plan (path `docs/plans/`, `origin:` frontmatter, `Implementation Units`, `Key Technical Decisions`, a `U1` prefix) |
| Rubric phase run | `issue` — the document is issue-derived, planning issue 1027 |
| Blocked status | **not blocked** — no `P0` and no `P1` remains open |
| Findings | 3 × `P1`, 2 × `P2`, 3 × `P3` — all repaired in place |
| Applied fixes | 12 edits, listed below |
| Linked issue | infiquetra/infiquetra-claude-plugins#1027, child of #1018 |
| Linked plan | `docs/plans/2026-09-20-issue-1027-build-loop-exit-criterion-plan.md` |
| Override rationale | none — no override was used |
| Review artifact path | `docs/reviews/doc-review-issue-1027-2026-09-20.md` (this file) |

## Rubrics run

The engine at `plugins/saga/scripts/lifecycle_review.py` was run for the `issue` phase. All three
core rubrics applied, and all three conditional extras fired after their applicability conditions
were read.

| Rubric | Class | Applied | Verdict |
|---|---|---|---|
| `acceptance_criteria_clarity` | core | yes | REVISE → repaired (D4) |
| `devils_advocate_issue` | core | yes | REVISE → repaired (D2, D3) |
| `spec_fidelity` | core | yes | REVISE → repaired (D5); the card's four acceptance criteria all map to units, so no BLOCK |
| `context_completeness` | extra | yes — a code change in a non-trivial repository where layout and conventions matter | pass |
| `issue_sizing` | extra | yes — seven units across many components | REVISE → repaired (D6) |
| `prerequisite_mapping` | extra | yes — part of a multi-issue effort with three siblings in flight | pass |

No rubric failed to load, so nothing was dropped.

## Findings

Sorted by priority, then source anchor, then title, and keyed `D1..Dn` within this reviewed
revision.

### D1 — `P1` — the `requires_hard_test_gate` removal cascade was unmapped

**Where.** Unit U3's span statement and its verification line.

**What.** The plan proposed removing the risk-gated test prose and verified it with
`grep -n "requires_hard_test_gate" plugins/saga/skills/work/`. `requires_hard_test_gate` is not
prose: it is a function at `plugins/saga/scripts/lifecycle_state.py:111` named by eight files,
including `plugins/saga/commands/work.md:17`, `plugins/saga/skills/loop/SKILL.md:286`,
`plugins/saga/skills/loop/references/dispatch-table.md:151`, and two tests in
`tests/test_work_gate_integrity.py`. The proposed grep, scoped to the skill directory, would have
passed while leaving a command file, another skill, and a passing test suite all naming a gate the
card removes.

**Consequence if followed literally.** The card would merge with `/work`'s command file still
telling an operator the skill applies a hard test gate it no longer applies, and with a test
asserting that section 4.1 of the skill names a function the section no longer mentions — a red
suite discovered at the merge turn rather than at planning.

**Repaired.** U3 now carries a nine-row table mapping every file that names the function to one of
three groups: this card, this card's U5, or issue 1030. The verification widened to
`grep -rn "requires_hard_test_gate" plugins/saga/skills/work/ plugins/saga/commands/work.md`.

### D2 — `P1` — the functional checks and the scenario smoke had no producer

**Where.** "High-Level Technical Design", the criterion reader.

**What.** The plan said the reader takes the functional checks and the scenario smoke from the
unit's row, "written there by the plan". `grep -rn "functional_checks\|scenario_smoke" plugins/ tests/`
returns nothing: no card in this tree writes either key, and this card does not build the writer.

**Consequence if followed literally.** An implementer would write a reader for a key that is always
absent and would have to invent the absent-key behaviour on the spot, and a reader of a green
iteration could not tell "nothing was prescribed" from "three were prescribed and the loop lost
them".

**Repaired.** New KTD9 states the rule: absent reads as an empty list, recorded with the reason
`none-prescribed`, printed by the dry run, with the writer named as the Planner's step and
explicitly out of this card. A test scenario was added for it, and item 2 of the new "Follow-ups
this plan does not do" section names the card that would build the writer.

### D3 — `P1` — KTD7 contradicted its own action

**Where.** Key Technical Decision 7, the preview command.

**What.** The decision read "Rather than invent a schema field on another card's document, the loop
reads an optional `branch_preview_command` from the profile". Reading a key no document describes is
the same drift the sentence says it is avoiding, and `grep -rn "branch_preview_command" plugins/ tests/`
confirms nothing in the repository names it.

**Repaired.** KTD7 rewritten: the loop reads the optional key **and** this card adds one row for it
to `plugins/saga/references/repository-profile.md`, with the reasoning that a key one consumer reads
and no document describes is precisely the drift this repository keeps tests for. U2's file list and
the scope boundaries were updated to match. `repository_profile.v1` still does not change, because
the key is optional.

### D4 — `P2` — a verification named no artifact

**Where.** Unit U2's verification line: "A test asserts the document and the code agree".

**Repaired.** The guard is now named: two assertions in `tests/test_build_loop.py`, one over the
record-block key set and one over the exit-code table, in the shape `tests/test_run_record.py` uses
for `run-record.md`. Two matching scenarios were added to U5's list.

### D5 — `P2` — the card's scanner clause was deviated from without appearing in Requirements

**Where.** The Requirements section.

**What.** KTD1 declines to promote bandit to a blocking baseline entry, with a measurement behind
it, and the operator-question section declares the deviation with a gate marker. Requirements did
not mention it, so a reader mapping the card's Objective onto the plan's requirements would find a
clause with no requirement and have to hunt for its fate.

**Repaired.** New R10 names the deviation where the requirement mapping is read.

### D6 — `P3` — the sizing was above the guideline with no note, and the count was wrong

**Repaired.** "Prerequisites and what this unblocks" now carries an explicit sizing paragraph, and
the file count was corrected from "about eighteen" to about thirty-four, of which nine are deletions
and eight are one-line repairs.

### D7 — `P3` — two measured counts were wrong

**What.** The five modules were described as "about 181 kilobytes"; measured, they are 175,034
bytes, or 171 kilobytes. The bandit step in continuous integration was cited at
`.github/workflows/ci.yml:283`; it is at `:282`. Four cited test line ranges were each off by one
to three lines.

**Repaired.** All corrected against the files at `87a5329e`. A stale count in the card itself was
also caught and recorded: the card and the objective plan both call `work/SKILL.md` "1,121 lines
today", and on this base it is 815 lines, because issues 1026 and 938 each took prose out of it
first. The plan now says so and states that every line number it cites is read from the file at
`87a5329e`.

### D8 — `P3` — a broken internal reference

**What.** KTD1 pointed at a section called "Follow-ups this plan does not do" that the document did
not contain.

**Repaired.** The section was written, with four items.

## Readiness-skeptic pass, beyond the rubrics

- **Verification.** Every numeric and path claim in the plan was checked against the files at
  `87a5329e` or against the lifecycle repository at revision `5efc869f`. Three were wrong and are
  corrected (D7).
- **Adversarial: what breaks if an agent follows this literally.** The two that would have broken
  are D1 and D2, both now closed. The remaining literal-following risk is the section 5.4 seam with
  issue 1028, which the plan names as a seam with a stated conflict-resolution rule rather than
  pretending it is not one.
- **Deployment-readiness scrutiny** applies, because the document describes a preview deployment.
  The plan invokes no deployment on this repository (`branch_preview` is false), records the
  undeclared case rather than erroring, refuses to guess a preview command, and proves its fourth
  acceptance criterion against a copy of the record with a fake command. Nothing in the plan deploys
  anything anywhere.
- **Security and operations scrutiny** applies, because the loop executes commands read from a
  tracked configuration file. The plan requires `shlex.split` with `shell=False` and records an
  unsplittable entry as `could-not-execute` rather than handing it to a shell.
- **Open-choice pressure.** One choice is genuinely the operator's and is left open under a gate
  marker rather than defaulted silently: how the bandit gap should be closed. The plan proceeds on
  the recorded default and names the two alternatives.
- **No external reviewer seat was dispatched.** Issue 1027's run record carries no Orchestrate
  `external-reviewer` unit, so none was requested, expanded, or substituted.

## Cycle accounting

Three review cycles ran, within the run record's `standard_cycle_allowance` of 3. Cycle 1 produced
D1 through D8 and their repairs; cycle 2 produced the count corrections in D7; cycle 3 found nothing
further. The plan-artifact conformance lint
(`plugins/saga/scripts/plan_artifact_conformance.py docs/plans`) reports no finding against this
document, and the gate-absence contract lint
(`plugins/saga/scripts/lint_gate_absence_contract.py`) reports `VIOLATIONS: 0` with both of this
plan's gate records parsed.

## Verdict

**Ready to drive implementation.** No `P0`, no `P1` open. The two declared operator questions are
recorded with gate markers and neither blocks the work: each has a stated recorded default and the
reasoning behind it.
