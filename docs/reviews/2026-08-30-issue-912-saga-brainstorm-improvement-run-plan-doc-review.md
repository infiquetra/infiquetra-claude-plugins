# Document review — issue 912 Saga Brainstorm improvement run plan

The plan is not ready to drive the serial OpenCode worker: three unit-level contradictions would
make B1 or B4 fail their own definition of done, or force the worker to invent a missing rule.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan.md` |
| reviewed revision | working tree on `work/cp912-brainstorm-improvement` at base `3b2b7083fdda8e39e213b5f4acf9f8301d60dd52`; plan is uncommitted (1,207 lines) |
| blocked status | **yes** — three P1 findings remain. `/work` blocks until they are repaired or explicitly overridden. |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan-doc-review.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#912](https://github.com/infiquetra/infiquetra-claude-plugins/issues/912) |
| linked children | #913 (B1), #914 (B2), #915 (B3), #916 (B4) |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

A single OpenCode worker cannot execute B1 → B2 → B3 → B4 from this plan without inventing a
decision or shipping a self-failing test.

The plan correctly implements the four binding coordinator rulings (mechanical lifecycle check,
keep-and-repoint the interrogation marker, `handoff_envelope.py` in B1, session-scoped
`--plugin-dir`). It does not reopen them. Preflight F1–F5 match the live 0.148.0 tree. Custody of
`brainstorm/SKILL.md` is genuinely serial. Nothing in the planned skill edits introduces a visible
checklist, questionnaire, persisted score, or live completeness gate during exploration.

Three P1 defects remain. B1's telemetry test requires exactly two `gate-record` markers after B1
also adds a third. B1's resume rule and its legacy-inference rule are both required and do not
compose. B4's Shaping "exactly once" check cannot pass against `plan/SKILL.md` §0.6, which B4 is
forbidden to edit.

## Remaining findings by priority

| id | priority | status | claim |
| --- | --- | --- | --- |
| D1 | P1 | open | B1 resume match and legacy inference do not compose |
| D2 | P1 | open | B1 requires exactly two `gate-record` markers and also adds a third |
| D3 | P1 | open | B4 Shaping "exactly once" fails against live `plan/SKILL.md` §0.6 |
| D4 | P2 | open | Issue 913 still requires deleting the gate-record marker that OQ2 keeps |
| D5 | P2 | open | B1's artifact `maturity` contradicts saga-spec §3.2 unless that sentence is qualified |
| D6 | P2 | open | B2 puts an Explore scout into the readonly-verifier in-scope table |
| D7 | P2 | open | B2 adds a question-selection rule beside the live must-probe-every-gap rule |
| D8 | P2 | open | U3 forbids synthesized transcripts the post-B2 checkpoint does not produce |
| D9 | P3 | open | U1 does not update the section-contract resume key after matching on capability |

## Issue-phase rubric review

Classification: issue-derived run plan under `docs/plans/`. Issue-phase rubrics apply. All three
core rubrics applied. All three extras applied: this is a multi-unit code-change campaign in a
non-trivial repo with a named serial dependency graph.

Rubric findings are not reclassified as readiness findings. D2 independently meets the
acceptance-criteria BLOCK criterion (internal AC contradiction) and is also a readiness P1.

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 6/10 | Load-bearing unit tests are named, but U1's telemetry count contradicts the declared-gate add, and U4's Shaping "exactly once" cannot pass. Rubric BLOCK criterion for internal AC contradiction is met by D2; readiness treats it as P1, not a separate rubric finding. |
| `devils_advocate_issue` | 8/10 | Four behavioural units plus one release commit match the run contract. No hidden refactor. Helper-inventory class mismatch is a smell, not unbounded scope. |
| `spec_fidelity` | 8/10 | Descent is issue 912 D1–D7 plus children 913–916, not a spec.md. Coordinator rulings are implemented, not reopened. Child 913's marker-removal AC is the remaining fidelity drift (D4). |
| `context_completeness` | 9/10 | Owned files, forbidden files, patterns, commit messages, and verification commands are exact enough to start. The three P1s are missing composition rules, not missing paths. |
| `issue_sizing` | 8/10 | One integrated PR is the parent contract. Units are independently commitable. B3 is the largest slice and is still one evidence unit. |
| `prerequisite_mapping` | 9/10 | B1 → B2 → B3 → B4 → release is explicit. The post-B2 checkpoint is the named B3 transcript source. |

## Triggered lenses

Founder-review is a useful extra lens on the user-facing Brainstorm dialogue, not a substitute for
this readiness pass. Security/ops and deployment lenses were not triggered.

## Spot-checks against the live tree

Verified at `3b2b7083`, working tree otherwise clean except this uncommitted plan and this artifact.

- `plugins/saga/skills/brainstorm/SKILL.md` is 371 lines. Telemetry paragraph is lines 46–50. Two
  `gate-record` markers exist, at lines 52 and 356. Phase 1.3 still requires one probe per found
  rigor gap (lines 216–217). Parallel Explore scan is unbounded at lines 17 and 139–140.
- `handoff_envelope.py:28-29` maps any `docs/brainstorms/` path to `requirements-ready`.
- `sandbox-spawn-sites.md` has four in-scope skill rows (code-review, qa, investigate, resume) and
  no Brainstorm row. Preamble still says "Each of these four skills" and that each names
  `saga:readonly-verifier`. `read-only-survey` and `judgment` are live registry keys.
- Lifecycle block `/ideate` / `/brainstorm` / `/plan` answers sits in ideate:15, loop:26,
  office-hours:27, plan:19. founder-review:30 is a variant with no `/ideate` line. strategy has
  inline mentions only.
- `plan/SKILL.md` §0.6 already states that Shaping is a board move through Mission Control, not a
  Saga write. `saga-spec.md` has no "shaping" string. Office Hours uses lowercase "discovery /
  shaping" at lines 3, 19, and 149.
- `saga-spec.md` §3.2 says maturity is derived and never stored in frontmatter. §3.3 and §4 exist
  as named targets.
- `requirements-sections.md` Metadata lists `maturity: requirements-ready` and names `topic` as
  the resume-detection key. Adding fields is allowed.
- `tests/test_lint_gate_absence_contract.py` `MIGRATED_SKILLS` already includes Brainstorm and does
  not key on a gate id.
- `tests/test_orchestrate_review_transport.py` `STAGE_SKILLS` includes Brainstorm at line 30.
- `tests/test_sandbox_spawn_sites.py` hardcodes the four existing skills only; extra inventory
  rows would not fail it.
- Saga version is 0.148.0. `gate-divergence-instrumentation.md:65` still names
  `brainstorm-<decision>`. `commands/brainstorm.md` is 13 lines.

## Decisions taken without asking

1. Do not edit the plan. The brief forbids it.
2. Do not reopen OQ1, OQ2, OQ4, or OQ6. Review whether the plan implements them.
3. No external-reviewer panel. The operator asked for one broad review, not a cross-engine pass.
4. Report-only second-opinion: D1–D9 are assigned; no `external_opinion` is recommended.
5. Write this artifact because a formal rubric review ran.

---

### D1 — B1 resume match and legacy inference do not compose

**Priority:** P1

**Where:** plan U1 Approach, Phase 0.1 (lines 342–348) and Legacy artifacts (lines 372–375);
issue 913 legacy and resume acceptance criteria.

**What is wrong.** Phase 0.1 matches on `topic` plus `capability` and treats zero matches as
"start fresh". The legacy paragraph requires inferred, operator-confirmed provenance for artifacts
that lack producer facts. Live and historical `docs/brainstorms/` files have no `capability`
field, so they cannot satisfy the new match rule.

**Why it matters.** A worker who implements Phase 0.1 literally will never reach the legacy path
issue 913 requires. A worker who invents a fallback order is deciding a load-bearing resume rule
the plan left open. Either way B1 cannot be marked done from evidence.

**Fix.** State the control flow in U1: exact `topic`+`capability` match first; files that exist
but lack producer facts enter the labelled-inference path; only a true empty scan starts fresh.
Say the same in Resume Phase 0.

### D2 — B1 requires exactly two `gate-record` markers and also adds a third

**Priority:** P1

**Where:** plan U1 Approach, Phase 2.5 (lines 350–355) and U1 Test scenarios, Telemetry
(lines 445–447). Live file: `plugins/saga/skills/brainstorm/SKILL.md:52` and `:356`.

**What is wrong.** The live skill has exactly two markers: `brainstorm-interrogation-choice` and
`brainstorm-handoff-routing`. B1 keeps and repoints the first (KTD2 / OQ2) and adds
`brainstorm-scope-confirmation` above Path B. The telemetry test then requires the finished file
to contain exactly two `gate-record` markers.

**Why it matters.** After B1 the file has three markers. The declared-gate test and the telemetry
count cannot both pass. This is an internal acceptance contradiction, not a wording nit.

**Fix.** Change the telemetry expectation to exactly three markers (repointed interrogation,
handoff routing, new scope confirmation), or name the two that must survive and the one that must
be added.

### D3 — B4 Shaping "exactly once" fails against live `plan/SKILL.md` §0.6

**Priority:** P1

**Where:** plan U4 Approach (lines 903–909), Test scenarios (lines 962–965), Verification
(lines 977–978). Live file: `plugins/saga/skills/plan/SKILL.md:123-132`. U4 must-not-touch list
(lines 857–858).

**What is wrong.** U4 adds the Shaping distinction to `saga-spec.md` §4 and says to state it once
and nowhere else. Its test and verification grep expect exactly one authoritative distinction
across `plugins/saga/references/` and `plugins/saga/skills/`, plus Office Hours' lowercase
generic uses. `plan/SKILL.md` §0.6 already states the same distinction — Mission Control writes
Shaping; Saga does not. B4 is forbidden to edit that file. `saga-spec.md` currently has no
"shaping" string, so the verification recipe is already wrong before the new paragraph is added.

**Why it matters.** A worker who implements the test as specified will fail it on the live tree.
A worker who ignores `plan/SKILL.md` §0.6 writes a vacuous check. KTD6 forbids the edit that
would make "exactly once" true.

**Fix.** Define the assertion as one new saga-spec statement, and treat `plan/SKILL.md` §0.6 as a
pre-existing derivation-boundary mention the test must name rather than forbid. Update the
verification grep the same way.

### D4 — Issue 913 still requires deleting the gate-record marker that OQ2 keeps

**Priority:** P2

**Where:** issue 913 files list, telemetry acceptance criterion, and verification grep
(`saga.py save|gate-divergence|gate-record`); plan F3, KTD2, OQ2.

**What is wrong.** The plan correctly keeps and repoints the marker per the binding OQ2 ruling.
Issue 913 still asks for the marker's removal and greps `gate-record` as a forbidden string.
Parent issue 912 still says each child's own acceptance criteria must be met.

**Why it matters.** The worker following the plan will keep the marker. A later reviewer or
close-out using issue 913 as the oracle will fail B1. This is review friction, not an execution
block, because the plan is explicit.

**Fix.** Amend issue 913's files list, telemetry AC, and verification grep to match OQ2
(repoint, do not delete). Do not change the plan's KTD2 behaviour.

### D5 — B1's artifact `maturity` contradicts saga-spec §3.2 unless that sentence is qualified

**Priority:** P2

**Where:** plan U1 The spec (lines 391–395); live `plugins/saga/references/saga-spec.md:183-184`.

**What is wrong.** §3.2 says maturity is derived, never stored, and that no `maturity` key ever
appears in frontmatter. B1 stores `maturity: pending-confirmation` or `requirements-ready` on the
brainstorm artifact and adds a §3.3 note distinguishing saga ticks from off-chain artifacts. The
approach does not tell the worker to qualify the absolute §3.2 sentence.

**Why it matters.** After B1 the spec will say both "never stored" and "artifacts declare
maturity" unless the worker also edits §3.2. That edit is in-scope (U1 owns the file) but not
instructed, so it is an open choice.

**Fix.** In the U1 spec bullet, require the §3.2 sentence to be scoped to saga-tick frontmatter
in the same edit as the §3.3 note.

### D6 — B2 puts an Explore scout into the readonly-verifier in-scope table

**Priority:** P2

**Where:** plan KTD4 (lines 195–200) and U2 spawn-site inventory (lines 572–578); live
`plugins/saga/references/sandbox-spawn-sites.md:21-25`.

**What is wrong.** The in-scope table's definition is: these skills spawn verify/review-class
helpers as `subagent_type: saga:readonly-verifier` with `isolation: "worktree"`. B2 adds two
Brainstorm rows there, including a Phase 1.1 grounding scout named as `Explore`. The only
authorized preamble edit is changing "Each of these four skills" to "Each of these skills".
`tests/test_sandbox_spawn_sites.py` will not fail — it only checks the existing four skills —
so the contradiction would ship.

**Why it matters.** After B2 the inventory and the helper policy disagree. An agent reading the
inventory will treat Brainstorm helpers as readonly-verifier sites; the skill will spawn Explore
for the scout, with no worktree isolation specified.

**Fix.** Either put only the claim-verifier row in the in-scope table and record the Explore
scout outside that class, or rewrite the table contract so mixed spawn types are allowed and
only the verifier row carries the readonly-verifier profile.

### D7 — B2 adds a question-selection rule beside the live must-probe-every-gap rule

**Priority:** P2

**Where:** plan U2 Question selection (lines 550–555); live
`plugins/saga/skills/brainstorm/SKILL.md:216-217`.

**What is wrong.** Live Phase 1.3 says probe every found rigor gap, one probe per gap, and that
Phase 1 cannot end with an un-probed gap. B2 adds "ask only when the answer could materially
change scope, acceptance, safeguards, or route" and does not say whether that replaces or
filters the must-probe rule.

**Why it matters.** Shipping both leaves the skill with two question policies. Reading them as
"still ask every found gap, but pick the order by consequence" is plausible and would not
create a visible checklist. Reading them as a new filter would drop probes the current skill
requires. The worker should not have to choose.

**Fix.** One sentence in the U2 Phase 1.3 bullet: the new rule orders and filters *idle*
questions; a rigor gap Phase 1.2 actually found is still probed, one at a time.

### D8 — U3 forbids synthesized transcripts the post-B2 checkpoint does not produce

**Priority:** P2

**Where:** plan Runtime checkpoint (lines 1094–1095), U3 grader/transcript boundary
(lines 718–724), U3 required cases (lines 711–713). OQ5 is settled and not reopened.

**What is wrong.** The checkpoint records seven continuity and judgment observables. U3's
scenario set still needs premature-convergence, missed-material-gap, consequence-calibration,
and checklist-overengineering cases, graded from "captured evidence from real Brainstorm runs,
not synthesized fixtures." The plan says U3 must not synthesize substitutes.

**Why it matters.** OQ5 correctly says the offline layer proves machinery, not conversational
quality. A literal worker can still halt at U3 for lack of failure-mode transcripts, or
synthesize them and violate the hard constraint.

**Fix.** Say that `scenarios.json` / `calibration.json` are authored data, that checkpoint
transcripts exercise `grade()` where they exist, and that missing failure-mode transcripts do
not block the offline shape, gating, and calibration-machinery tests.

### D9 — U1 does not update the section-contract resume key after matching on capability

**Priority:** P3

**Where:** live `plugins/saga/skills/brainstorm/references/requirements-sections.md:70`; plan U1
The section contract (lines 377–381) and Phase 0.1 (lines 342–345).

**What is wrong.** The section contract today says `topic` is the resume-detection key. B1
changes matching to `topic` plus `capability` and extends Metadata, but does not update that
sentence.

**Why it matters.** After B1 the section contract and the skill would disagree about how resume
finds a file. Small, and repairable in the same U1 edit.

**Fix.** In the U1 section-contract bullet, replace the topic-only resume sentence with
topic-plus-capability, and point leftover topic-only files at the legacy path from D1.

## Residual risk

Line citations were checked at `3b2b7083`. The design record in
`infiquetra/infiquetra-agent-operations` was treated as discussion authority only, per the plan
and issue 912, and was not re-read as source.

No child was executed. Runtime-checkpoint observability was judged from the plan text, not from
a live `/saga:brainstorm` session.

`/founder-review` remains available as an extra ambition lens on the user-facing dialogue. It is
not required to repair D1–D3.
