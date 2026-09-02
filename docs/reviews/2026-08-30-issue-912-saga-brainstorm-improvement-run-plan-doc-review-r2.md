# Document review — issue 912 Saga Brainstorm improvement run plan (round 2)

The repaired plan is ready to drive the serial OpenCode worker. The three blocking findings from
round 1 are genuinely repaired, not papered over. Two leftover P2 inconsistencies remain; neither
stops a worker who follows each unit's Approach and Test scenarios.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan.md` |
| reviewed revision | working tree on `work/cp912-brainstorm-improvement` at base `3b2b7083fdda8e39e213b5f4acf9f8301d60dd52`; plan is uncommitted (1,372 lines) |
| prior review | `docs/reviews/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan-doc-review.md` (round 1; not overwritten) |
| blocked status | **no** — no P0 or P1 finding remains |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-30-issue-912-saga-brainstorm-improvement-run-plan-doc-review-r2.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#912](https://github.com/infiquetra/infiquetra-claude-plugins/issues/912) |
| linked children | #913 (B1), #914 (B2), #915 (B3), #916 (B4) |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

A single OpenCode worker can execute B1 → B2 → B3 → B4 from this plan without inventing the
continuity, judgment, evidence, or maintenance design.

Round-1 D1, D2, and D3 are closed by ordered rules, an id-set marker census, and a named
pre-existing Shaping inventory — not by softer prose. The four coordinator rulings remain
implemented. Preflight F1–F5 still match the live 0.148.0 tree. `brainstorm/SKILL.md` custody is
still serial. Nothing planned introduces a visible checklist, questionnaire, persisted score, or
live completeness gate during exploration.

The D6 repair is sound. Putting only the claim verifier in the in-scope table, recording the
Explore scout outside that class, and adding `tests/test_sandbox_spawn_sites.py` to B2's owned
files is the right rejection of a class-contract rewrite. Two leftover verification phrases still
say "two new rows"; follow the Approach, not those phrases.

## Remaining findings by priority

| id | priority | status | claim |
| --- | --- | --- | --- |
| D1 | P2 | open | U2 verification still talks as if D6 added two in-scope rows |
| D2 | P2 | open | U4 Shaping "nothing further" misses `office-hours/references/frame-diagnostic.md` |
| D3 | P3 | open | U1 and U2 verification counts were not updated when tests were added |
| D4 | P3 | open | The planned scout subsection overclaims that Explore "structurally cannot write" |

Round-1 D1–D9 are not reopened as P1s. Their disposition is audited below.

## Round-1 closure — D1, D2, D3

**D1 is repaired.** U1 Phase 0.1 is now an ordered three-tier rule: exact `topic`+`capability`
match, then files lacking producer facts as legacy inference, then start-fresh only after both
earlier tiers find nothing. Resume Phase 0 repeats the same order. A file missing `capability` is
explicitly a legacy artifact, never a miss. That is the control flow round 1 required.

**D2 is repaired.** U1 states an authoritative post-B1 census of three markers — interrogation
repointed, handoff-routing untouched, scope-confirmation added — and splits the old "exactly two"
telemetry test into a no-`saga.py save` assertion plus an id-set census. The live file still has
exactly two markers today (lines 52 and 356). The plan no longer treats that pre-B1 count as the
post-B1 expectation.

**D3 is repaired on the load-bearing point.** "Exactly once" now means one new saga-spec
statement. `plan/SKILL.md` §0.6 is a named, expected mention B4 must not edit. Office Hours'
three SKILL.md lowercase uses are named and expected. The test asserts those are present rather
than forbidden. That is what made the old check impossible.

## D6 judgment — the rejected fix

The planner rejected rewriting the in-scope table's class contract. That rejection is correct.

The live table's contract is verify/review-class spawns carrying `saga:readonly-verifier` plus
`isolation: "worktree"`. `tests/test_sandbox_spawn_sites.py::test_in_scope_skills_reference_readonly_verifier`
enforces that for each listed skill. Filing an Explore scout there would make the inventory lie,
and the shared contract four other skills depend on would be diluted for one new helper.

The delivered split is the smaller change that keeps the inventory truthful:

- one in-scope row for the Phase 1.1 claim verifier, work-shape `judgment`, no line reference
- the Explore scout in its own subsection beside the ad-hoc spawn rule, not worktree-isolated,
  with no `read-only-survey` table row
- Brainstorm added to `IN_SCOPE_SKILLS` so both existing assertions cover the new row

Adding the guard file to B2's owned list is what stops the row from being decorative. After that
edit, the inventory must name the skill and its path, and `brainstorm/SKILL.md` must reference
`readonly-verifier` — which the helper-policy edit supplies for the verifier. The scout stays
outside that enforcement, which is the point.

Do not reopen the rejected alternative. The leftovers in D1 (this round) are cleanup of stale
"two rows" phrases, not a reason to put the scout back in the table.

## Disposition audit

The new "Document-review disposition" section maps all nine round-1 findings. It is mostly
accurate. It overclaims two closures.

| round-1 id | disposition claim | audit |
| --- | --- | --- |
| D1 | three-tier rule in U1 and Resume | **Accurate.** The order is in the Approach, not only in a note. |
| D2 | census of three plus split telemetry/census tests | **Accurate.** The old "exactly two" expectation is gone from the test scenarios. |
| D3 | redefine "exactly once"; name §0.6 and Office Hours' three uses; fix the grep | **Mostly accurate, incomplete.** The §0.6 hole is closed. The closed-world "nothing further" claim is still wrong: `plugins/saga/skills/office-hours/references/frame-diagnostic.md:153` is a live lowercase "shaping" hit under the verification grep's own paths. See this round's D2. |
| D4 | no plan change; coordinator correcting issue 913 | **Accurate enough.** Issue 913 has been amended: the marker is retained and repointed, and `handoff_envelope.py` is on the owned list. The card's verification grep still includes `gate-record`, which will match after B1. That leftover is on the card, not the plan. |
| D5 | scope §3.2 in the same commit as the §3.3 note | **Accurate.** U1 now requires both edits in one pass and says the §3.3 note alone does not repair §3.2. |
| D6 | verifier in table, scout outside, `IN_SCOPE_SKILLS` updated | **Accurate as a design repair.** The Approach and Test scenarios match. Verification and the commit message were not fully rewritten; see this round's D1. |
| D7 | consequence test orders idle questions only; must-probe test added | **Accurate.** The composition sentence is required in the skill, with a matching assertion. |
| D8 | authored case data vs captured transcripts | **Accurate.** Failure-mode cases may be authored; only a synthesized transcript labelled `captured` is forbidden. The runtime checkpoint says the same. |
| D9 | replace the topic-only resume sentence | **Accurate.** U1's section-contract bullet now requires topic-plus-capability and points leftover files at the D1 legacy tier. |

The header line "All nine are repaired here" is slightly loose. D4 was repaired on the child
card, not in the plan. D3 and D6 are repaired in design and still carry leftover verification
phrases.

## Issue-phase rubric review

Classification: issue-derived run plan under `docs/plans/`. Issue-phase rubrics apply. All three
core rubrics applied. All three extras applied.

Rubric findings are not reclassified as readiness findings. No rubric BLOCK criterion is met.

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 8/10 | Unit tests are named and the round-1 internal contradictions are gone. Leftover verification counts (this round D1, D3) keep it short of 9. |
| `devils_advocate_issue` | 9/10 | Four units plus one release commit still match the run contract. The D6 split is the smallest inventory change that stays truthful. |
| `spec_fidelity` | 9/10 | Descent is issue 912 D1–D7 plus children 913–916. Coordinator rulings are implemented. Issue 913's AC now matches OQ2. |
| `context_completeness` | 9/10 | Owned files, forbidden files, patterns, and per-unit tests are exact enough to start without grepping for the design. |
| `issue_sizing` | 8/10 | One integrated PR is the parent contract. Units stay independently commitable. |
| `prerequisite_mapping` | 9/10 | B1 → B2 → B3 → B4 → release is explicit. The post-B2 checkpoint is the named source of captured transcripts, not of authored failure-mode cases. |

## Triggered lenses

`/founder-review` remains a useful extra lens on the user-facing Brainstorm dialogue. It is not
required for this readiness pass. Security/ops and deployment lenses were not triggered.

## Spot-checks against the live tree

Verified at `3b2b7083`. Working tree has the uncommitted plan, the round-1 review artifact, and
this artifact.

- `brainstorm/SKILL.md` is 371 lines. Two `gate-record` markers at lines 52 and 356. Phase 1.3
  still requires one probe per found rigor gap (lines 216–217).
- `handoff_envelope.py:28-29` still maps any `docs/brainstorms/` path to `requirements-ready`.
- `sandbox-spawn-sites.md` still has four in-scope skill rows and no Brainstorm row.
  `IN_SCOPE_SKILLS` in `tests/test_sandbox_spawn_sites.py` is still the four existing skills.
- Lifecycle block membership is unchanged: ideate:15, loop:26, office-hours:27, plan:19.
- `plan/SKILL.md` §0.6 still states the Shaping derivation boundary. `saga-spec.md` still has no
  "shaping" string. Office Hours SKILL.md has three lowercase uses (lines 3, 19, 149).
  `office-hours/references/frame-diagnostic.md:153` is a fourth lowercase hit under
  `plugins/saga/skills/`.
- `requirements-sections.md:70` still names `topic` as the resume-detection key. `maturity` at
  line 71 is already a stored artifact field, which is why the §3.2 qualification is needed.
- Saga version is 0.148.0.

## Decisions taken without asking

1. Do not edit the plan.
2. Do not reopen OQ1, OQ2, OQ4, or OQ6.
3. Do not reopen the rejected D6 alternative.
4. No external-reviewer panel.
5. Write a new artifact; leave the round-1 file untouched.

---

### D1 — U2 verification still talks as if D6 added two in-scope rows

**Priority:** P2

**Where:** plan U2 Resolver routing (line 709), Verification (lines 723–726), Commit message
(lines 748–749). Contrast KTD4 and U2 Approach (lines 641–664) and Test scenarios (lines 696–706).

**What is wrong.** After the D6 repair, B2 adds one in-scope table row and one prose subsection.
The Approach and the spawn-site tests say that. Three leftovers still say "two new rows",
"exactly the two new rows", or "both sites … with resolver work-shapes". The scout has no
resolver work-shape. The run-level pytest `-k` filter also omits `sandbox_spawn_sites`, the
module B2 now owns so the row is not decorative.

**Why it matters.** A worker who treats the verification grep as the definition of done could add
a second in-scope row and undo D6. The Approach is the authority; the leftover phrases are not.
The existing resolver test will pass with one new table row.

**Fix.** Say "one new in-scope row plus the scout subsection". Drop "resolver work-shapes" from
the scout. Add `sandbox_spawn_sites` to the run-level `-k` filter. Count the judgment
assertions as twelve, not nine.

### D2 — U4 Shaping "nothing further" misses a live hit

**Priority:** P2

**Where:** plan U4 Approach (lines 1035–1043), Test scenarios (lines 1096–1104), Verification
(lines 1116–1120). Live file: `plugins/saga/skills/office-hours/references/frame-diagnostic.md:153`.

**What is wrong.** The load-bearing D3 repair is in place. The verification grep over
`plugins/saga/references/` and `plugins/saga/skills/` still claims the only pre-existing hits
are `plan/SKILL.md` §0.6 and Office Hours' three SKILL.md uses. `frame-diagnostic.md` is a
fourth lowercase "discovery / shaping" heading under those same paths. B4 cannot delete it
(not owned) and must not treat it as a new mention B4 added.

**Why it matters.** A closed-world test that inventories every "shaping" hit under those
directories will fail on the live tree. A test that only asserts the named files will pass.
This is the same class of miss as round-1 D3, one file further down.

**Fix.** Name `office-hours/references/frame-diagnostic.md` as another expected generic use, or
scope the closed-world check to `SKILL.md` files plus `saga-spec.md` rather than every file
under `skills/`.

### D3 — U1 and U2 verification counts were not updated when tests were added

**Priority:** P3

**Where:** plan U1 Verification (line 528); U2 Verification (line 723).

**What is wrong.** U1 lists twelve continuity scenarios after the marker-census split and still
says "eleven continuity assertions". U2 lists twelve judgment scenarios after D6 and D7 and
still says "all nine judgment assertions".

**Why it matters.** The lists are the contract. The numbers are leftover. A worker following the
lists will write the right tests.

**Fix.** Count the listed scenarios, or drop the numerals.

### D4 — The planned scout subsection overclaims that Explore "structurally cannot write"

**Priority:** P3

**Where:** plan U2 Approach, spawn-site inventory (lines 648–651). Contrast KTD4 (lines 195–199)
and live `sandbox-spawn-sites.md:80-81`.

**What is wrong.** KTD4 correctly says Explore lacks `Edit`/`Write`/`NotebookEdit` and retains
`Bash`. The planned scout subsection says the scout "structurally cannot write". That is the
claim the inventory already refuses for Explore.

**Why it matters.** Writing the overclaim into `sandbox-spawn-sites.md` would document a false
guarantee next to the fallback ladder that names the Bash residual.

**Fix.** In the subsection, say read-only by omission of Edit/Write/NotebookEdit, with the same
Bash residual the Explore rung already documents. Do not say "structurally cannot write".

## Residual risk

Line citations were checked at `3b2b7083`. Issue 913's amendment matches OQ2 and OQ4; its
verification grep still includes `gate-record` and will match after B1. That is a card leftover,
not a plan defect.

No child was executed. Runtime-checkpoint observability was judged from the plan text.

Round-1 D4 on the child card is substantially closed. Do not treat the remaining grep as a
reason to delete the marker.
