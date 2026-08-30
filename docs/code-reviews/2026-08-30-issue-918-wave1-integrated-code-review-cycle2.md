---
title: "Integrated Code Review — issue 918 Wave 1, cycle 2"
type: code-review
status: complete
date: 2026-08-30
reviewed_revision: 76533cbeba4007cb89e9acf5842027d24cda99de
merge_base: bbac725a
branch: work/cp918-saga-plan-improvement
issue_ref: infiquetra/infiquetra-claude-plugins#918
plan_path: docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md
prior_cycle_artifact: docs/code-reviews/2026-08-30-issue-918-wave1-integrated-code-review.md
outcome: repairs_requested
cycle: 2
---

# Integrated Code Review — issue 918 Wave 1, cycle 2

**The repair fixed what cycle 1 measured and broke three things cycle 1 could not have seen, so the
review returns `repairs_requested` a second time at `76533cbeba4007cb89e9acf5842027d24cda99de`.**
All three of cycle 1's harness substitutions are genuinely repaired — proven by mutations the testing
lens ran itself, not by the repair worker's claim. Against that, the repair replaced two working
literal paths in the Work skill with a shell variable that is out of scope where it is used, wrote a
recovery instruction that appends the duplicate tick it promises not to, and widened a
malformed-carrier stop until it halts Plan on two of this repository's own committed documents.

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `work/cp918-saga-plan-improvement`, merge base `bbac725a` (`origin/main`) |
| Reviewed revision | `76533cbeba4007cb89e9acf5842027d24cda99de` |
| Cycle | 2 of at most 3 |
| Prior cycle | `5ec8ea7682706aa9f06e359c373cfd2032ee6ba9`, outcome `repairs_requested`, 62 findings |
| Repair under review | `1e74b49a` (22 files, +1390 / −293), then artifact commit `76533cbe` |
| Schema | `review_result.v1` |
| Outcome | **`repairs_requested`** |
| Next action | `dispatch_repairs` |
| Allowed resume transition | `dispatch_repairs` |
| Lens findings | 67, across 51 distinct defects (12 at P1, 21 at P2, 18 at P3; none at P0) |
| Consolidated fix requests | 29 — 28 to `review-fixer`, 1 to `human`; 15 `manual`, 14 `safe_auto` |
| Round-trip | `ReviewResult.from_json()` returns `repairs_requested` |

## Method note — how cycle 2 was run

The lens roster was supplied by the caller, which under
`plugins/saga/references/lens-roster.json` `selection_contract.caller_or_orchestrate_selection_is_approval`
**is** the conditional-lens approval. No operator question was asked. The approval was persisted
through `review_consensus.resolve_lens_selection` against reviewed commit
`76533cbeba4007cb89e9acf5842027d24cda99de` and cycle 2, with `question_asked: false` and
`source: caller`. Because all seven lenses failed in cycle 1, `state.next_lenses` returned all seven,
so all seven were re-run and no delta check was required for a retained lens.

Every lens ran as `subagent_type: saga:readonly-verifier` with `isolation: "worktree"`, per
`plugins/saga/references/sandbox-spawn-sites.md`. At most three ran at once, the account-level
concurrency cap. The full 24-step repository gate was **not** re-run: it is green at this revision by
the caller's given state, and this review is not the place to re-derive it.

The criteria for this check were pre-registered at cycle 1 under
`docs/evidence/adhoc-cp918-saga-plan-improvement/criteria-code-review-5ec8ea7682706aa9f06e359c373cfd2032ee6ba9.json`.
Cycle 2 was adjudicated against those same criteria — the same scope rule, the same
`review_result.v1` blocking rule, the same policy source — and no second freeze was taken, on the
caller's instruction, so the pass/fail contract could not be redefined between cycles.

**Two corrections the controller owes.** First, the brief I gave the lens panel stated that this
repository's plugin manifests carry no dependency field at all. That was wrong:
`plugins/orchestrate/.claude-plugin/plugin.json` declares
`"dependencies": [{"name": "agent-launcher", "version": ">=1.0.0"}]`. The api-contract lens caught
it, and it changes the recommendation on the cross-plugin seam below. Second, cycle 1's finding F02
said the counterfactual guard was vacuous for two of four files; measured per file and per phrase, it
was vacuous for one — `plugins/saga/references/operator-choice.md`. The repair is right either way;
the correction is to the size of the hole, not to the fix.

## Consensus

Acceptance is the roster's rule and only the roster's rule: a derived overall of at least 9.0 **and**
every applicable dimension at 7.0 or better. Priority and confidence are metadata and decide nothing.
Scores are each lens's own; a gate result never rescores a lens.

| Lens | Derived | Accepted | Dimensions below the 7.0 floor |
|---|---|---|---|
| security | 7.50 | no | none |
| testing | 7.30 | no | behavior-sensitive-assertions |
| documentation-clarity | 6.92 | no | shipped-behavior-parity, terminology-cross-document-consistency, runbook-safety-rollback-links-generated-drift |
| correctness | 6.80 | no | intent-behavior-completeness, side-effects-errors-resource-lifecycle |
| api-contract | 6.58 | no | interface-contract-compatibility, serialization-errors, retry-idempotency-semantics, specification-documentation-parity |
| agent-usability | 6.00 | no | all five |
| architecture-maintainability | 4.93 | no | all seven |

Two dimensions were recorded non-applicable with a cause: security's
`secrets-cryptography-session-handling` (no secret material, credential, session issuance, or
cryptographic control is introduced; the one session-adjacent surface moved byte-identically) and
api-contract's `pagination-rate-limits` (no paged collection, cursor, quota, or throttled interface).

### Score regressions the engine recorded

`residual_summary.score_regressions` carries three, each on the identical dimension set both cycles
scored — so these are like-for-like, not an artefact of a different roster slice:

| Lens | Cycle 1 at `5ec8ea76` | Cycle 2 at `76533cbe` |
|---|---|---|
| architecture-maintainability | 7.43 | 4.93 |
| correctness | 8.40 | 6.80 |
| api-contract | 7.50 | 6.58 |

The engine forbids ranking scores across revisions, and this review does not: each cycle's score
stands on its own evidence. What the table does say plainly is that three lenses judged the repaired
revision more harshly than the revision it repaired, on the same dimensions, and each of the three
named the same drivers — the Work skill's unset shell variable, the false idempotency claim in the
save-failure recovery line, and the over-firing malformed-carrier stop.

## Independent gates

A failed independent gate blocks readiness even when numeric acceptance passes. It never changes a
dimension score.

| Gate | Result | Basis |
|---|---|---|
| repository-gate | **pass** | The 24-step gate is green at this revision by the caller's given state: 25 steps, 0 blocking failures, 0 uncovered. Not re-derived here |
| release-surface-parity | **pass** | Saga 0.150.0 in `plugins/saga/.claude-plugin/plugin.json` and at `plugins/saga/CHANGELOG.md:3`, with `## [0.149.0]` intact at line 46 and both bodies whole; `plugins/cc-workflows/.claude-plugin/plugin.json` at 1.0.0; fifteen plugins in `.claude-plugin/marketplace.json` at metadata 3.0.0; `python3 scripts/sync_marketplace.py --check` exits 0, so the registry is generated rather than hand-written |
| built-vs-planned | **fail** | The plan's requirement R33 — "No unit pins a corpus count, a corpus **file name**, or a launch-base integer in a test" — is violated by a pin unit U1 added at `tests/test_plan_artifact_conformance.py:272` and by a re-anchored floor at `tests/test_wave_file_conflicts.py:187`. Every other cycle-1 shortfall is closed, and no change lands outside the plan or the review |
| contract-obligations | **fail** | Obligation 3 is violated by one new harness substitution the repair introduced, and obligation 7 is violated on both halves |

`review_accepted: false` · `independent_gates_passed: false` · **`can_proceed: false`**

## The four independent verifications

### 1. The `#808` guard — repaired, and the hole was one file rather than two

Measured by the controller in-process against both revisions, per file, per counterfactual phrase:

| File | Counterfactual at merge base, flat match | At merge base, whitespace-collapsed | At `76533cbe` | Never-pre-select sentence |
|---|---|---|---|---|
| `plugins/saga/skills/plan/SKILL.md` | yes | yes | absent | present |
| `plugins/saga/skills/work/SKILL.md` | yes | yes | absent | present |
| `plugins/saga/references/operator-choice.md` | **no** | yes | absent | present |
| `plugins/saga/skills/work/references/execution-strategy.md` | yes | yes | absent | present |

The whitespace-collapse repair is correct and the guard now covers all four files in both tests. It
closed a hole that existed in exactly one file. At the merge base
`execution-strategy.md:203` carries "If `recommended` is `cc-workflows-ultracode`," complete on one
line, so the flat matcher did catch that file; the line break there falls inside "do not\npre-select",
which belongs to the other test — and that test matched flat in all four files at both revisions.

The testing lens then broke it from the other direction and confirmed the arming: the merge-base
branch restored verbatim into each of the four files, plus an artificially wrapped variant of each,
failed the guard **8 times out of 8**.

One residual, recorded as finding T05: the never-pre-select half is file-level rather than
sentence-level. `work/SKILL.md` carries both accepted phrasings, at lines 53 and 275, so corrupting
either one alone leaves the test green; only corrupting both turns it red. The other three files fail
on a single corruption.

### 2. Every claimed mutation proof, broken by someone else

The repair worker reported that findings F02, F01, F05, F03, F02u, F06t, F10a, F16, F18 and F17 each
cycled red then green. The testing lens re-ran them against the shipped code rather than the tests:

| Claim | Independent result |
|---|---|
| F02 — counterfactual guard armed | **holds**, 8 of 8 restorations fail the guard |
| F01 — required-backend contract guarded | **holds**. Reverting both declaration sites now fails exactly one test, against cycle 1's 6,447 passing; it also fails on either site alone |
| F06t — conformance check shipped, not test-local | **holds**. The test imports `plugins/saga/scripts/plan_artifact_conformance.py`, redefines none of its four functions, and four of five mutations to the shipped module turn tests red |
| F16 — shim ladder covered | **holds**, from 20 percent to 87 percent |
| F18 — write-path guard breadth | **holds** |
| F17 — stale-pointer inversion | **holds** |
| F10a — substrate surface pinned both ways | **fails**. `_agent_prompt` crosses the boundary undeclared; renaming it in Saga's `execution_spec.py` leaves all three surface tests green |
| F05 — save-failure prose | **fails**. The index branch's assertion is satisfied by the fixture's own filename, and the whole handler can be swapped out with all five tests still passing |
| F03, F02u | **hold** as behaviour; their prose surfaces do not (see the P1 table) |

The controller confirmed the `_agent_prompt` gap statically and independently: the emitter's four
`_ES.<attribute>` accesses are `_agent_prompt`, `_build_emission_routing_context`,
`max_concurrent_agents` and `resolved_concurrency`, and only `_agent_prompt` is absent from the
29-name tuple; the guard test walks only `ast.Assign` nodes inside `_bind_substrate`, so a qualified
access is structurally invisible to it. Three lenses reached the same conclusion by three different
routes.

### 3. The three previously violated obligations

- **Obligation 3 (harness substitution)** — still violated, but by one new instance rather than the
  three cycle 1 measured. All three old ones are genuinely fixed. The new one is
  `tests/test_saga_plan_save_and_routing.py:205`, where `assert "index" in err` is satisfied by the
  fixture path `docs/plans/2026-08-30-index-failure-plan.md` written at line 176; the error always
  interpolates that path, so the assertion passes whichever handler produced the message.
- **Obligation 5 (Workflow backend explicit-invocation-only)** — now satisfied. `tests/test_saga_plugin.py`
  passes 54 tests including both `#808` pins; the counterfactual branches are gone from all four offer
  files; the carrier stops on both richer backends; and the ruling was not widened — Plan Phase 5.2
  still names the three-value enum, still says the default offer is only `inline` and `team-execution`,
  and still carries "Never pre-select `cc-workflows-ultracode`" and the affirmative
  recommend-and-pre-select rule for the no-carrier path.
- **Obligation 7 (no pinned corpus value)** — still violated, and on both halves rather than one.
  Cycle 1 called the integer half satisfied; that was too generous. `tests/test_wave_file_conflicts.py:187`
  asserts `len(specs) >= 18` directly beneath a glob this change rewrote from `docs/plans/` to
  `docs/workflows/`, and `tests/test_plan_artifact_conformance.py:272` still asserts a named corpus
  document exists — while the test two positions below it carries the comment "never on a count or on
  a file name (R33)".

### 4. Unit U3's rigidity pin — unchanged

`tests/test_plan_pre_answers.py::test_phase0_intake_subsection_adds_no_rigidity_shapes` is
**byte-identical** between `5ec8ea76` and `76533cbe`. The repair adopted neither cycle 1's
recommendation — split both revisions on phase headings and assert phases 1, 2 and 4 byte-identical —
nor anything else. It remains a five-token keyword-absence check scoped to the 0.7 subsection.

The controller performed by hand what the pin does not do. Splitting
`plugins/saga/skills/plan/SKILL.md` on `## Phase N` headings at both revisions:

| Section | `bbac725a` | `76533cbe` | Identical |
|---|---|---|---|
| Preamble | `2ae76908` | `2ae76908` | yes |
| Phase 0 — Enter and warranted-gate | `927d0845` | `eefc7d55` | no — subsection 0.7 added |
| Phase 1 — Ground | `e0985f00` | `e0985f00` | yes |
| Phase 2 — Interrogate | `b65ed7dd` | `b65ed7dd` | yes |
| Phase 3 — Synthesize the plan artifact | `073ddf59` | `f091def4` | no — frontmatter block |
| Phase 4 — Deepen | `73ac2920` | `73ac2920` | yes |
| Phase 5 — Saga, route, operator-choice | `8357b9bf` | `cb737167` | no |

So obligation 1 holds at this revision as a measured fact. Nothing in the suite enforces it, and the
recommendation stands unchanged into cycle 3.

## Contract obligations — cycle 2 verdicts

| # | Obligation | Cycle 1 | Cycle 2 | Evidence |
|---|---|---|---|---|
| 1 | Plan phases 0, 1, 2, 4 gained no new question, checklist, questionnaire, or fixed sequence | satisfied | **satisfied** | Phases 1, 2 and 4 hash identically at both revisions (see verification 4). Phase 0 changed only by gaining subsection 0.7, whose five bullets are a rule table describing carrier semantics; it removes a question and adds none |
| 2 | No test asserts an exact Plan question, its wording, or the order of the conversation | satisfied | **satisfied** | The only question-adjacent assertion is `tests/test_plan_pre_answers.py:453`, an absence check. Both new test files open by stating the rule, at `tests/test_plan_artifact_conformance.py:9` and `tests/test_plan_pre_answers.py:5` |
| 3 | No test substitutes a fixture, mock, or monkeypatch for the behaviour it claims to prove | **violated** | **violated — one new instance** | All three cycle-1 instances are genuinely repaired and mutation-proven. The new one is `tests/test_saga_plan_save_and_routing.py:205`: swapping `except SagaTickIndexWriteError` for an unrelated exception leaves all five tests passing, because the asserted substring lives in the fixture's own filename |
| 4 | Plan's board-move sentences untouched | satisfied | **satisfied** | Both merge-base blocks — `### 0.6 The card moves to Shaping` and `### 5.0 The card moves to Ready` — are present verbatim at the reviewed revision |
| 5 | Workflow backend runnable and explicit-invocation-only (issue 808) | **violated on one clause** | **satisfied** | See verification 3. The carrier now stops on both richer backends, the pins pass, and the ruling was not widened into Plan's normal offer |
| 6 | Backend-override telemetry retained | satisfied | **satisfied** | `plugins/saga/scripts/override_rate_reader.py` is untouched by this change; its consumers live in the Retro and Optimize skills; `tests/test_override_rate.py` is present; `saga.py` retains six `orchestration_recommended` references. Nothing was deleted. Finding U06 is a related prose risk, not a deletion: Plan's new "skip the offer" parenthetical also skips the only instruction to call `recommend_execution_backend`, whose output the Phase 5.3 save template then demands |
| 7 | No corpus integer pinned in code or tests | satisfied for integers, partially violated for file names | **violated on both halves** | `tests/test_wave_file_conflicts.py:187` pins `len(specs) >= 18`; `tests/test_plan_artifact_conformance.py:272` pins a named corpus document. The plan's requirement R33 forbids both in exact words |
| 8 | No repository-level unreferenced-plan scanner, state store, daemon, registry, queue, or reconciliation pass | satisfied | **satisfied** | Neither new Saga module writes anything. `plan_pre_answers.py` reads only the text it is given; `plan_artifact_conformance.py` has no `write_text`, no state file, and no saga cross-reference — it is a read-only conformance pass with a command line |
| 9 | Plan-document contract kept out of the tick envelope field table | satisfied | **satisfied** | `plugins/saga/references/saga-spec.md` section 3.1 hashes identically at both revisions. The plan-doc contract is section 14, the carrier is section 15, and References moved to section 16, which also closes cycle 1's ordering defect |
| 10 | Built versus planned | partial | **partial** | Requirement R1 is now guarded, requirements R3 and R5 ship in a real module, and the R27 residual is fixed — at the cost recorded as finding D05/T03. R33 remains violated. No change lands outside the plan or the review: every file the repair touched traces to a named cycle-1 finding |

## Carried-forward items — reported, not re-filed as new defects

| Finding | Route | Status at `76533cbe` |
|---|---|---|
| F10 — the emitter binds eleven private names of Saga's module | downstream-resolver | Still open, and now measurably understated: the real count is twelve. See the P2 row for `emitter.py:1348` |
| F11 — a third hand-written copy of the plugin-root resolution ladder | downstream-resolver | Still open at `plugins/saga/scripts/execution_spec.py:2413` |
| F28 — a named corpus file pin | downstream-resolver | Still open at `tests/test_plan_artifact_conformance.py:272`, and it is the file-name half of obligation 7 |
| F25 — the plugin-root ladder matches any marketplace | advisory | Still open |
| F29 — a re-anchored conflict sentinel pinning a corpus count | advisory, pre-existing | Still open at `tests/test_wave_file_conflicts.py:187`, and it is the integer half of obligation 7 |
| F31 — the cross-plugin seam has no declared dependency | release, coordinator-owned | Still open. **It should not block.** See below |

### F31 — should it block, and what is proportionate

**No, it should not block.** The total-miss path is already loud and actionable:
`plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:118` raises carrying
`_FAIL_MESSAGE` from `:33-38`, which names both remedies, and
`plugins/cc-workflows/README.md:29-31` already states that the saga plugin, or a repo checkout
containing `plugins/saga/`, is a prerequisite. The api-contract lens also established backward
compatibility by parsing the saga 0.149.0 `execution_spec.py` at `origin/main`: all thirty declared
`SUBSTRATE_SURFACE` names plus `_agent_prompt` are present, so an older installed saga binds cleanly
rather than failing.

The proportionate fix is not version-negotiation machinery, which this repository does not want. It
is a four-line copy of a pattern already in the tree — `plugins/orchestrate/.claude-plugin/plugin.json`
declares `"dependencies": [{"name": "agent-launcher", "version": ">=1.0.0"}]` — added to
`plugins/cc-workflows/.claude-plugin/plugin.json` as `saga >=0.150.0`, plus one install sentence in
the Saga 0.150.0 changelog entry. Finding U07 is the same seam's agent-usability face and is separate:
declaring the dependency does not make Saga's own hard-block step executable when its command lives
only in the sibling plugin's skill.

## The four items awaiting a coordinator decision

| Item | Recommendation |
|---|---|
| The repair worker's reading of finding F04t (the validator has no caller) | **Accept it.** For a skills-based plugin the agent is the caller and the SKILL.md command block is the wiring, exactly as `saga.py` is invoked from prose. The repair went further and added real-subprocess proofs for both new command lines, at `tests/test_plan_pre_answers.py:378` and `tests/test_plan_artifact_conformance.py:101`, which is the right answer to this repository's own harness-substitution lesson. Nothing further is owed on F04t itself — but note findings T06 and U08: the conformance check still has no caller and no invocation prose anywhere outside its test |
| The unquoted `$CC_WORKFLOWS_SCRIPTS_DIR` | **Fix it, and it is larger than quoting.** The variable is assigned inside the fenced block spanning lines 346–363 of `plugins/saga/skills/work/SKILL.md` and consumed in two separate later blocks, 428–431 and 436–438, where it is unset — so the lease release and renew commands expand to `/workflow_emitter.py`. Both lines carried working literal paths at the merge base. Repeat the assignment in each block and quote all four expansions |
| The illustrative worked-example pointer | **Fix it, cheaply.** `plugins/saga/references/saga-spec.md:234` names `docs/workflows/2026-06-02-saga-foundation-spec.json`, which has never existed in any directory anywhere in this repository's history. The example is legitimately illustrative, but keeping it as written cost a permanent guard reduction. Point it at one of the forty-plus real artifacts under `docs/workflows/` and restore the markdown scan |
| Whether the review artifact should be tracked | **Yes, keep it tracked.** It matches cycle 1's own artifact, the evidence ledger's content-addressed copy is the custody record, and the human-readable copy travels with the branch. The `docs/reviews/` placement is correct rather than hazardous: `plugins/saga/scripts/handoff_envelope.py:78` and `:93` map that directory to maturity `plan-ready` and lifecycle phase `review`, which is what a plan-document review is, and the classifier runs only on an explicit source argument, never a directory sweep |

## Findings

Sixty-seven lens findings resolve to fifty-one distinct defects. Where several lenses reached the
same defect independently, the `#` column lists every identifier and the Reviewer column names every
lens; the route shown is the most conservative any reviewer assigned. The typed result keeps all
sixty-seven, each bound to the lens that scored it, because a routed finding the cycle controller
cannot reconcile against a scored one is refused.

Nine defects were reached by more than one lens. The strongest agreement is on the malformed-carrier
over-fire — security, correctness and api-contract found it separately, and the controller reproduced
it against two committed in-repo documents — and on the false idempotency claim in the save-failure
recovery line, which four lenses reproduced end to end against a real filesystem.

Confidence is anchored; every finding below sits at 100. Nothing was suppressed by the admission rule
this cycle: no lens reported below anchor 75.

### P1 — 12 distinct defects

| # | File | Issue | Reviewers | Confidence | Route |
|---|---|---|---|---|---|
| D02/P08 | `plugins/saga/CHANGELOG.md:9` | Changelog claims any supplied value is applied and narrated | api-contract, documentation | 100 | manual -> review-fixer |
| D01/U11 | `plugins/saga/CHANGELOG.md:11` | Changelog still says unknown schema token is refused whole | agent-usability, documentation | 100 | manual -> review-fixer |
| C03/P02/S01 | `plugins/saga/scripts/plan_pre_answers.py:170` | Any unrelated malformed json fence halts the Plan run | api-contract, correctness, security | 100 | manual -> review-fixer |
| C04/U04 | `plugins/saga/scripts/plan_pre_answers.py:331` | Contradiction rule unreachable through the runnable entry point | agent-usability, correctness | 100 | manual -> review-fixer |
| C01/D03/P01/U09 | `plugins/saga/scripts/saga.py:1688` | Index-failure recovery step falsely claims idempotence | agent-usability, api-contract, correctness, documentation | 100 | manual -> review-fixer |
| C02/D04 | `plugins/saga/scripts/saga.py:1700` | Envelope-failure message asserts no tick unconditionally | correctness, documentation | 100 | manual -> review-fixer |
| U03 | `plugins/saga/skills/plan/SKILL.md:145` | Phase 0.7's exit-code contract is wrong on both failure paths | agent-usability | 100 | manual -> review-fixer |
| U05 | `plugins/saga/skills/plan/SKILL.md:164` | Five rules omit the fence-info rule; a wrong fence drops silently | agent-usability | 100 | safe_auto -> review-fixer |
| U06 | `plugins/saga/skills/plan/SKILL.md:335` | Skip the offer leaves the recommend call and tick flag undefined | agent-usability | 100 | safe_auto -> review-fixer |
| A01/U01 | `plugins/saga/skills/work/SKILL.md:429` | Lease release and renew reference an unset shell variable | agent-usability, architecture | 100 | safe_auto -> review-fixer |
| T01 | `tests/test_saga_plan_save_and_routing.py:205` | Index-failure assertion satisfied by the fixture's own filename | testing | 100 | manual -> review-fixer |
| D05/T03 | `tests/test_workflow_extraction.py:223` | Dangling-pointer guard narrowed to Python, markdown unguarded | documentation, testing | 100 | manual -> review-fixer |

### P2 — 21 distinct defects

| # | File | Issue | Reviewers | Confidence | Route |
|---|---|---|---|---|---|
| D06 | `docs/engineering-journal/LEARNINGS.md:39` | Journal entry records a fix that did not happen | documentation | 100 | manual -> review-fixer |
| A08 | `plugins/cc-workflows/skills/cc-workflows/SKILL.md:68` | New plugin's own commands hardcode a repo-relative Saga path | architecture | 100 | manual -> review-fixer |
| A05 | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:41` | A second Saga module is imported wholesale outside the declared seam | architecture | 100 | manual -> review-fixer |
| A04/C05/P03/T04 | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` | A private Saga name crosses the boundary outside SUBSTRATE_SURFACE | api-contract, architecture, correctness, testing | 100 | manual -> review-fixer |
| D07 | `plugins/saga/CHANGELOG.md:7` | No test pins any carrier prose surface to the code | documentation | 100 | manual -> review-fixer |
| U07 | `plugins/saga/references/execution-spec.md:399` | HARD BLOCK step points across plugins for Saga's own command | agent-usability | 100 | safe_auto -> review-fixer |
| A03 | `plugins/saga/references/execution-spec.md:400` | Saga's reference cites another plugin's step numbers, unpinned | architecture | 100 | manual -> review-fixer |
| A02 | `plugins/saga/references/execution-spec.md:401` | Single-source claim is false in its own file | architecture | 100 | manual -> review-fixer |
| U08 | `plugins/saga/references/saga-spec.md:672` | Conformance checker has no invocation prose and an undocumented exit 2 | agent-usability | 100 | safe_auto -> review-fixer |
| D08 | `plugins/saga/references/saga-spec.md:700` | Case-differing v1 token is refused but prose says only non-v1 is | documentation | 100 | manual -> review-fixer |
| C06 | `plugins/saga/scripts/plan_artifact_conformance.py:79` | Broken YAML reclassifies a new-contract plan as legacy | correctness | 100 | manual -> review-fixer |
| T02 | `plugins/saga/scripts/plan_artifact_conformance.py:122` | Backend-enum rule in the shipped check has no positive test | testing | 100 | safe_auto -> review-fixer |
| A09 | `plugins/saga/scripts/plan_pre_answers.py:45` | Validator docstring claims no file reads while the new CLI reads one | architecture | 100 | safe_auto -> review-fixer |
| P07 | `plugins/saga/scripts/plan_pre_answers.py:161` | A well-formed carrier in a JSON fence vanishes without a stop | api-contract | 100 | manual -> review-fixer |
| S02 | `plugins/saga/scripts/plan_pre_answers.py:220` | Two refusal paths echo caller key names raw and unbounded | security | 100 | safe_auto -> review-fixer |
| C10/P05 | `plugins/saga/scripts/plan_pre_answers.py:328` | Both new entry points exit outside their documented contract | api-contract, correctness | 100 | manual -> review-fixer |
| P06 | `plugins/saga/scripts/plan_pre_answers.py:335` | Validator report is labelled with the carrier's schema token | api-contract | 100 | manual -> review-fixer |
| A12/P04 | `plugins/saga/scripts/saga.py:852` | New OSError subclasses carry no errno, strerror, or filename | api-contract, architecture | 100 | safe_auto -> review-fixer |
| A06 | `plugins/saga/scripts/saga.py:1705` | Generic OSError branch misattributes a read failure as a write | architecture | 100 | manual -> review-fixer |
| A07 | `plugins/saga/skills/plan/SKILL.md:253` | Required-field pin misses the template agents actually copy | architecture | 100 | manual -> review-fixer |
| U02 | `plugins/saga/skills/work/SKILL.md:350` | Shell comment claims resolution parity the shell does not have | agent-usability | 100 | manual -> review-fixer |

### P3 — 18 distinct defects

| # | File | Issue | Reviewers | Confidence | Route |
|---|---|---|---|---|---|
| D09 | `docs/engineering-journal/DECISIONS.md:17` | Undefined code P-D3 migrated from skill prose into the journal | documentation | 100 | safe_auto -> review-fixer |
| S04 | `plugins/cc-workflows/README.md:34` | Documented ladder omits the sys.modules short-circuit above rung 1 | security | 100 | safe_auto -> review-fixer |
| A10 | `plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:130` | Documented command line loads and executes execution_spec twice | architecture | 100 | manual -> review-fixer |
| D10 | `plugins/saga/CHANGELOG.md:29` | Changelog says docs/plans is reserved for plan documents | documentation | 100 | safe_auto -> review-fixer |
| S06 | `plugins/saga/references/operator-choice.md:59` | Carrier exception to the ALWAYS-surface rule is undocumented | security | 100 | safe_auto -> review-fixer |
| U10 | `plugins/saga/references/saga-spec.md:699` | Family match is case-insensitive but the token check is not | agent-usability | 100 | safe_auto -> review-fixer |
| A11 | `plugins/saga/scripts/execution_spec.py:1676` | Producer carries no marker for nine of eleven bound private names | architecture | 100 | advisory -> downstream-resolver |
| C12 | `plugins/saga/scripts/plan_artifact_conformance.py:121` | Empty backend field reported as the Python literal None | correctness | 100 | safe_auto -> review-fixer |
| T06 | `plugins/saga/scripts/plan_artifact_conformance.py:163` | Shipped conformance check has no caller outside its test | testing | 100 | manual -> human |
| C07 | `plugins/saga/scripts/plan_pre_answers.py:84` | A stray triple backtick silently drops the carrier | correctness | 100 | manual -> review-fixer |
| C08 | `plugins/saga/scripts/plan_pre_answers.py:175` | Valid non-object JSON slips past the malformed-carrier stop | correctness | 100 | manual -> review-fixer |
| S03 | `plugins/saga/scripts/plan_pre_answers.py:233` | caller accepts any string and is narrated verbatim | security | 100 | safe_auto -> review-fixer |
| C09 | `plugins/saga/scripts/plan_pre_answers.py:260` | Invocation-only stop masks a genuine established conflict | correctness | 100 | manual -> review-fixer |
| C11 | `plugins/saga/skills/plan/SKILL.md:351` | Phase 5.2 lost the explicit ultracode pre-select fallback | correctness | 100 | advisory -> human |
| S05 | `plugins/saga/skills/work/SKILL.md:359` | Unquoted script-dir variable in four copy-and-run command lines | security | 100 | safe_auto -> review-fixer |
| T07 | `tests/test_plan_pre_answers.py:432` | Drift pin matches shipped source text instead of importing | testing | 100 | safe_auto -> review-fixer |
| T08 | `tests/test_wave_file_conflicts.py:187` | Corpus integer survives the re-anchored conflict sentinel | testing | 100 | advisory -> downstream-resolver |
| T05 | `tests/test_workflow_extraction.py:107` | Never-pre-select guard is file-level, not sentence-level | testing | 100 | safe_auto -> review-fixer |

## Finding detail

Every finding below cites evidence the reviewer personally checked. Where a lens ran a mutation, the
command and its result are quoted; where the controller confirmed a lens independently, that is said
so.

### P1

**U01 — Release and renew blocks lose the scripts-dir variable** · `plugins/saga/skills/work/SKILL.md:429` · lens `agent-usability` · dimension `safe-bounded-idempotent-resumable-context-cost`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

CC_WORKFLOWS_SCRIPTS_DIR is assigned only in the pre-submit block at line 352, so the later release block at :429 and renew block at :437 -- separate fenced blocks an agent runs in a new shell after the Workflow tool returns -- expand it to empty and the protocol never closes.

Evidence:

- plugins/saga/skills/work/SKILL.md:352 assigns without export; :429 and :437 consume
- lens run of line 429 verbatim in a fresh shell: can't open file '/workflow_emitter.py', exit 2; with the scripts dir hand-resolved it still fails on the equally unbound $WORKFLOW_LEASE_METADATA
- the lease-metadata half is pre-existing; the scripts-dir variable is new in this change
- controller confirmation of the fenced-block boundaries: 346-363 holds the assignment, 428-431 and 436-438 are separate blocks with none
- independently found by the architecture lens as its highest-impact item

Suggested fix: Repeat the three assignments (WORKFLOW_INVOCATION_ID, WORKFLOW_LEASE_METADATA, CC_WORKFLOWS_SCRIPTS_DIR) at the head of the release and renew blocks, or tell the agent to re-derive them from the saga tick.

**U03 — Phase 0.7's exit-code contract is wrong on both failure paths** · `plugins/saga/skills/plan/SKILL.md:145` · lens `agent-usability` · dimension `machine-readable-output-actionable-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Phase 0.7 tells the agent that exit 2 always carries a stop to surface exactly, but a usage error also exits 2 with no JSON at all, and an unreadable invocation file exits 1 with a raw traceback -- an undocumented code the prose never mentions.

Evidence:

- plugins/saga/skills/plan/SKILL.md:145-146
- lens runs: --invocation-file /tmp/does-not-exist.txt gave a FileNotFoundError traceback and exit 1; an unrecognised argument gave exit 2 with empty stdout
- source: plan_pre_answers.py:327-328 reads the file with no guard; :344 returns 2 only for a stop
- independently found by the correctness and api-contract lenses

Suggested fix: Catch OSError in main() and emit the same JSON shape with a stop naming the unreadable path, and state in Phase 0.7 that a usage error also exits 2 without a stop.

**U04 — Contradiction rule unreachable through the runnable entry point** · `plugins/saga/scripts/plan_pre_answers.py:331` · lens `agent-usability` · dimension `capability-parity-reachability`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Phase 0.7's third rule stops on a value contradicting one already established in the thread, but the command line calls evaluate(text) with no established mapping and offers no flag to supply one, so the agent must hand-implement the rule the runnable validator was added to remove.

Evidence:

- plan_pre_answers.py:331; argparse at :316-326 exposes only --invocation-file, confirmed by the usage line
- the established parameter exists at :198 and :274-285 and has no production caller -- only tests/test_plan_pre_answers.py
- the rule is stated at plugins/saga/skills/plan/SKILL.md:158-160
- independently found by the correctness and api-contract lenses and by the controller

Suggested fix: Add repeatable --established backend=<v> / --established destination=<v> options and pass them through to evaluate, then show them in Phase 0.7's command.

**U05 — Five rules omit the fence-info rule; a wrong fence drops silently** · `plugins/saga/skills/plan/SKILL.md:164` · lens `agent-usability` · dimension `context-constraints-acceptance-examples`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The validator only scans blocks whose fence info string is exactly json, so a carrier fenced with an uppercase JSON info string is ignored with no stop and no narration -- the settled decisions vanish and the conversation re-asks -- yet none of Phase 0.7's five rules states the fence requirement.

Evidence:

- plugins/saga/skills/plan/SKILL.md:161-167 carries the two schema rules and the malformed-carrier rule but no fence rule; plan_pre_answers.py:161 skips any other info string
- lens run: a carrier fenced with an uppercase JSON info string carrying destination pr and backend inline returned applied {}, stop null, exit 0
- the rule exists in plugins/saga/references/saga-spec.md:715-716 but not in the skill the agent executes
- the api-contract lens found the same silent drop from the code side

Suggested fix: Add to the malformed-carrier bullet: the fence info string must be exactly lowercase json; any other info string is not a carrier and is ignored.

**U06 — Skip the offer leaves the recommend call and tick flag undefined** · `plugins/saga/skills/plan/SKILL.md:335` · lens `agent-usability` · dimension `context-constraints-acceptance-examples`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Phase 5.2's carrier parenthetical says to skip the offer, but the skipped paragraph is the only place that tells the agent to call recommend_execution_backend, and Phase 5.3's save template then demands --orchestration-recommended with that output -- a placeholder the agent cannot fill, and passing an empty value aborts the save.

Evidence:

- plugins/saga/skills/plan/SKILL.md:335-337 (skip), :349-353 (the only recommend_execution_backend instruction, bundled with the offer), :572 and :589 (save templates requiring its output)
- lens run: saga.py save with --orchestration-recommended "" gave 'invalid choice', exit 2, no tick written; plugins/saga/scripts/saga.py:1556-1561 restricts the flag to the enum
- the controller independently flagged the same ambiguity as a risk to the operator ruling 2 telemetry before this lens returned

Suggested fix: Extend the parenthetical: skip only the operator-facing question; still call recommend_execution_backend, still record --orchestration-recommended and --orchestration-mode inline, and still write the plan-doc backend field.

**U09 — Index-failure recovery line asserts a false idempotency** · `plugins/saga/scripts/saga.py:1688` · lens `agent-usability` · dimension `safe-bounded-idempotent-resumable-context-cost`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The repaired message tells the agent the re-run is idempotent and appends no duplicate tick, but each re-run allocates a new envelope file and fails again while the cause persists, so an agent following the recovery line loops and inflates the tick log.

Evidence:

- saga.py:1684-1689; envelope allocation at :660-667 mints a new sequence file per save
- lens reproduction in a throwaway repository: clean save gave 1 envelope; forcing the index write to fail printed the documented message with exit 2 and 2 envelopes; re-running the identical save gave exit 2 again and 3 envelopes
- independently reproduced by the correctness and api-contract lenses

Suggested fix: Say the re-run rewrites the index only once the underlying write failure is cleared, and that it appends another tick envelope; drop the idempotency claim.

**P01 — Index-failure remedy promises idempotence, duplicates the tick** · `plugins/saga/scripts/saga.py:1688` · lens `api-contract` · dimension `retry-idempotency-semantics`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The operator-facing error tells the operator to re-run the save and asserts the re-run is idempotent and appends no duplicate tick, but _allocate_envelope_path allocates a fresh filename every call, so the re-run writes a second envelope and the saga history gains a phantom tick.

Evidence:

- plugins/saga/scripts/saga.py:1688 (message) and :697 (the same claim in the SagaTickIndexWriteError docstring)
- lens reproduction: pre-created .claude/saga/state.json as a directory, ran save -> rc 2 with the quoted message and one envelope; removed the blocker, re-ran the identical argv -> rc 0 and two envelopes; saga.py ticks then reported count: 2
- both sentences were INTRODUCED by the cycle-1 repair commit 1e74b49a
- the guard test tests/test_saga_plan_save_and_routing.py:157-209 narrates the duplicate-tick problem in its docstring but never re-runs the save
- independently reproduced by the correctness lens

Suggested fix: Delete the idempotence clause from saga.py:1688 and :697, or make it true by having save reuse an existing envelope whose rendered content is byte-identical before allocating a new path.

**P02 — Any unparseable json fence halts /plan with no carrier present** · `plugins/saga/scripts/plan_pre_answers.py:170` · lens `api-contract` · dimension `interface-contract-compatibility`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

scan_carriers applies the malformed-carrier stop to every fenced block whose info string is json, before it ever checks whether the block declares the plan_pre_answers family, so invocation text containing an illustrative or truncated JSON example and no carrier at all stops the run -- contradicting the closing promise of both shipped documents.

Evidence:

- plan_pre_answers.py:160-174 returns the stop at :170-174 before the family test at :177
- the contradicted promises are plugins/saga/references/saga-spec.md:734 and plugins/saga/skills/plan/SKILL.md:169, both saying a Brainstorm document with no carrier stops nothing
- lens scan with the module's own _FENCE_RE: 3 of 19 json fences under docs/brainstorms/, docs/plans/ and plugins/saga/skills/ do not parse; running the shipped entry point against two of them returned exit 2 with the malformed-carrier stop
- the only malformed-block test at tests/test_plan_pre_answers.py:333-341 uses a block that carries the schema token, so the non-carrier case is untested
- independently reproduced by the security lens, the correctness lens, and the controller against two committed in-repo documents

Suggested fix: In scan_carriers, raise the malformed stop only for a block that is carrier-shaped -- re-scan the raw block text for the plan_pre_answers family token; leave a json fence with no family token as a non-candidate, exactly as a foreign schema already is.

**A01 — Lease release and renew reference an unset shell variable** · `plugins/saga/skills/work/SKILL.md:429` · lens `architecture-maintainability` · dimension `conventions-portability-configuration`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The F12 repair replaced two working literal paths with $CC_WORKFLOWS_SCRIPTS_DIR, which is assigned only in the launch block at line 352 and is not in scope in the later release and renew blocks, so the lease is never released.

Evidence:

- assigned (not exported) at plugins/saga/skills/work/SKILL.md:352; consumed at :429 and :437, which run after the Workflow tool returns
- controller confirmation of block boundaries: the fenced blocks in that file run 346-363 (holds the assignment at :352 and the consumers at :359, :361), then a separate block 428-431 holding :429, then a separate block 436-438 holding :437 -- neither later block carries the assignment
- lens reproduction: bash -c 'python3 $CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py renew /dev/null' -> can't open file '/workflow_emitter.py', exit 2
- git show 1e74b49a shows both lines previously carried the literal path, so this is a regression the repair introduced
- grep -rn CC_WORKFLOWS_SCRIPTS_DIR tests/ returns nothing, so the gate cannot see it

Suggested fix: Repeat the CC_WORKFLOWS_SCRIPTS_DIR="${CC_WORKFLOWS_SCRIPTS_DIR:-plugins/cc-workflows/skills/cc-workflows/scripts}" assignment at the top of the release block and the renew block, and quote the expansion.

**C03 — Any unrelated malformed json fence halts the Plan run** · `plugins/saga/scripts/plan_pre_answers.py:163` · lens `correctness` · dimension `intent-behavior-completeness`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

scan_carriers parses every json-fenced block and returns a stop before it ever checks the family schema, so a JSON-with-comments config sample pasted into a /plan request halts the whole run with 'pre-answer carrier refused' even though no carrier is present.

Evidence:

- plan_pre_answers.py:163-177 -- the json.JSONDecodeError and _DuplicateKeyError returns precede the _is_family_schema test at line 177
- lens reproduction: a json fence holding {"name":"x", // a comment, "port":8080} plus prose returned the malformed-carrier stop; a fence holding {"a":1,"a":2} returned the duplicate-keys stop; a valid carrier later in the same text is discarded
- independently reproduced by the security lens as its own finding, and by the controller against two committed in-repo documents

Suggested fix: Parse leniently first -- on a parse or duplicate-key failure, only stop when the raw block text contains the plan_pre_answers family token; otherwise treat the block as unrelated prose.

**D01 — Changelog still says unknown schema token is refused whole** · `plugins/saga/CHANGELOG.md:11` · lens `documentation-clarity` · dimension `shipped-behavior-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

A release reader is told any unrecognised schema token is refused, so a typo or renamed envelope silently returns the identical no-carrier outcome and the caller believes a decision was handed over.

Evidence:

- plugins/saga/CHANGELOG.md:11-12 against plan_pre_answers.py:114-124
- lens run: a carrier declaring a foreign family with backend inline returned applied {}, stop null, exit 0 -- ignored, not refused
- saga-spec.md:699-702 and plan/SKILL.md:161-163 both carry the corrected two-case rule; the changelog alone was left behind
- independently found by the controller and the api-contract and agent-usability lenses

Suggested fix: Replace the clause with the two-case rule already shipped on the other two surfaces: a non-v1 token inside the plan_pre_answers family is refused whole; a foreign schema family is not a carrier and is ignored.

**D02 — Changelog claims any supplied value is applied and narrated** · `plugins/saga/CHANGELOG.md:9` · lens `documentation-clarity` · dimension `shipped-behavior-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The changelog omits the operator ruling entirely, so an integrator building a carrier with backend team-execution expects it applied and instead gets a hard stop with no caller returned.

Evidence:

- plugins/saga/CHANGELOG.md:9-10 against the enforcement at plan_pre_answers.py:260-273
- lens run: a carrier with backend team-execution gave exit 2, applied {}, caller null, and the invocation-only stop
- the ruling IS stated at saga-spec.md:705-710 and plan/SKILL.md:151-155

Suggested fix: Add the inline-only qualification to the changelog bullet -- the carrier applies only inline automatically; team-execution and cc-workflows-ultracode are legal plan values that stop and surface.

**D03 — Index-failure recovery step falsely claims idempotence** · `plugins/saga/scripts/saga.py:1687` · lens `documentation-clarity` · dimension `runbook-safety-rollback-links-generated-drift`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The prescribed recovery -- re-run the same save -- writes a second tick envelope, so an operator following the message silently doubles the append-only tick log while being told it cannot.

Evidence:

- saga.py:1687-1689, repeated at plugins/saga/skills/plan/SKILL.md:616-617 and docs/engineering-journal/LEARNINGS.md:39
- lens reproduction in a sandbox repository: the index fault gave exit 2 with one envelope; removing the fault and re-running the identical command gave exit 0 and a SECOND envelope, identical except updated_at
- mechanism at saga.py:660-670 -- _allocate_envelope_path always picks a non-colliding filename, so a re-run cannot overwrite
- the regression test at tests/test_saga_plan_save_and_routing.py never checks the idempotence claim, so the green gate cannot see it
- independently reproduced by the correctness, api-contract and agent-usability lenses

Suggested fix: Say what the re-run does -- it rebuilds the index and appends one additional tick carrying the same state -- or make the index-only re-run reuse the existing envelope path.

**D04 — Envelope-failure message asserts no tick unconditionally** · `plugins/saga/scripts/saga.py:1700` · lens `documentation-clarity` · dimension `shipped-behavior-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

When any earlier tick already recorded the plan path -- the normal case, since Plan saves at Phase 0 and again at Phase 5.3 -- the message tells the agent the plan is stranded while restore returns it, producing a false halt on fully tracked work.

Evidence:

- saga.py:1700-1701 states the claim with no guard on prior state; echoed at plugins/saga/skills/plan/SKILL.md:613-615
- lens reproduction: after a successful save recording the plan path, making the saga directory read-only and re-running gave exit 2 with 'now has NO saga tick referencing it', while saga.py restore then returned that same plan_path with found true
- the regression test at tests/test_saga_plan_save_and_routing.py:150-154 asserts restore(...) is None but only on a first save, never with a prior tick present
- independently reproduced by the correctness lens; this is cycle-1 finding F05d surviving on the sibling branch

Suggested fix: Condition the claim on whether a prior tick exists -- check restore, or the prior value already computed at saga.py:781 -- and say this save's tick was not written while naming the plan's last recorded tick when one is there.

**D05 — Dangling-pointer guard narrowed to Python, markdown unguarded** · `tests/test_workflow_extraction.py:223` · lens `documentation-clarity` · dimension `runbook-safety-rollback-links-generated-drift`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Every plugin markdown file may now name a docs/workflows spec that does not exist without any test noticing, so the reference migration this move owed has no ongoing guard on the prose side.

Evidence:

- tests/test_workflow_extraction.py:218-230 scans plugins/**/*.py; the prior scan was plugins/**/*.md plus the two script directories
- lens mutation: appending a nonexistent docs/workflows reference to saga-spec.md left 12 passed; restored
- the test comment cites the worked example as the reason for the narrowing; that example names two non-existent paths, neither of which has ever been added in repository history
- independently confirmed by the testing lens and by the controller

Suggested fix: Restore the markdown scan and exempt the one illustrative block by fence or by an explicit allowlist of example stems, rather than dropping markdown coverage wholesale.

**S01 — Any unparseable json fence halts Plan and suppresses a carrier** · `plugins/saga/scripts/plan_pre_answers.py:170` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

scan_carriers returns the malformed-carrier stop for ANY ```json block before checking whether the block declares the plan_pre_answers family, so an unrelated JSON example in an issue body or Brainstorm document halts Phase 0.7 -- and, placed earlier in the text, silently overrides a well-formed carrier that follows.

Evidence:

- plan_pre_answers.py:170-174 (except json.JSONDecodeError) and :164-169 (duplicate-key path) both fire before the family gate at :177
- controller reproduction: python3 plugins/saga/scripts/plan_pre_answers.py --invocation-file docs/brainstorms/2026-08-12-orchestrate-codex-phase-requirements.md -> exit 2, stop set, on a document with no carrier
- controller reproduction: an unparseable non-carrier json fence placed before a valid {"schema":"plan_pre_answers.v1","backend":"inline"} carrier -> applied={}, stop set
- controller measurement: 3 committed documents under docs/ carry a json fence that fails json.loads; 2 of them (docs/brainstorms/2026-08-12-orchestrate-codex-phase-requirements.md, docs/plans/2026-07-13-459-earned-ratings-plan.md) are documents /plan legitimately receives as input
- contradicts plugins/saga/skills/plan/SKILL.md:168 'Direct /plan -- an issue, a prompt, or a Brainstorm document, no carrier -- is unchanged: nothing applied, nothing narrated, nothing stopped'

Suggested fix: Gate both stops on carrier shape: treat an unparseable or duplicate-key json block as a malformed carrier only when its raw text contains the plan_pre_answers family token; otherwise skip it as before. The multi-carrier stop at :179 is already correctly scoped and shows the intended shape.

**T01 — Index-failure assertion satisfied by the fixture's own filename** · `tests/test_saga_plan_save_and_routing.py:205` · lens `testing` · dimension `behavior-sensitive-assertions`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The whole SagaTickIndexWriteError handler can be deleted and the test that claims to prove it still passes, so the cycle-1 F05 repair is unguarded -- a new harness substitution the repair introduced.

Evidence:

- assert "index" in err at tests/test_saga_plan_save_and_routing.py:205; the fixture plan is docs/plans/2026-08-30-index-failure-plan.md, so the substring is satisfied by the path
- lens mutation: changing except SagaTickIndexWriteError to except NotImplementedError at plugins/saga/scripts/saga.py:1678 left 5 passed, 0 failed
- coverage under that mutation shows saga.py:1683-1692 and :1697-1704 unexecuted while the generic except OSError at :1705 runs

Suggested fix: Rename the fixture to a path containing no 'index', and assert the handler's own words: 'rewrite the saga state.json index' and 'IS still referenced by the'.

### P2

**U02 — Shell comment claims resolution parity the shell does not have** · `plugins/saga/skills/work/SKILL.md:350` · lens `agent-usability` · dimension `capability-parity-reachability`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The comment says the shell resolves the scripts directory the same way the Python seam does, but the Python seam has four rungs and the shell has two, so outside a checkout of this repository the shell falls back to a working-directory-relative path that does not exist while Python would resolve.

Evidence:

- plugins/saga/skills/work/SKILL.md:350-352 against the ladder at plugins/saga/scripts/execution_spec.py:2413-2469
- the lens read both resolution paths and did not test an installed-plugin session

Suggested fix: Drop the parity claim and say the fallback assumes the working directory is a checkout of this repository; otherwise set CC_WORKFLOWS_SCRIPTS_DIR first.

**U07 — HARD BLOCK step points across plugins for Saga's own command** · `plugins/saga/references/execution-spec.md:399` · lens `agent-usability` · dimension `capability-parity-reachability`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Step 2 of Saga's own flow is a hard block whose command is only in another plugin's SKILL file, with no fallback if cc-workflows is absent -- even though the command runs a Saga script that the same document already prints thirty lines further down.

Evidence:

- plugins/saga/references/execution-spec.md:399-401 points at plugins/cc-workflows/skills/cc-workflows/SKILL.md Step 4
- the target at :65-69 gives the Saga command; the same command, differing only in runner, sits at plugins/saga/references/execution-spec.md:429
- the pointer path is repo-relative, so it does not resolve in an installed-plugin session

Suggested fix: Keep the cross-reference for rationale but restate the one-line validate command inline, and name the HALT when cc-workflows is not installed.

**U08 — Conformance checker has no invocation prose and an undocumented exit 2** · `plugins/saga/references/saga-spec.md:672` · lens `agent-usability` · dimension `discoverability-invocation-schemas`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

No shipped skill or reference tells an agent when or how to run the new conformance checker -- the spec only calls it runnable -- and its own docstring documents exits 0 and 1 while main also returns 2 for a bad root.

Evidence:

- plugins/saga/references/saga-spec.md:671-675; grep for plan_artifact_conformance across plugins/saga/skills/ returned nothing
- lens runs: on docs/plans a JSON report and exit 0; on a nonexistent root a one-key JSON error and exit 2, against the docstring at plan_artifact_conformance.py:18-20
- the testing lens found the same absence of any caller outside the test

Suggested fix: Add a Phase 5-side step in plan/SKILL.md with the literal command and the three exit codes, and add the 2 case to the module docstring.

**P03 — Twelfth private name crosses the boundary undeclared** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` · lens `api-contract` · dimension `interface-contract-compatibility`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The emitter calls _ES._agent_prompt on the unattended climb-retry emission path, but _agent_prompt is absent from SUBSTRATE_SURFACE, so the bind guard never tests for it and a substrate lacking it binds cleanly, then dies with an AttributeError at emit time.

Evidence:

- the access is emitter.py:1348; the declared tuple at :48-77 does not contain it; the guard is at :103
- lens proof: a stub carrying every SUBSTRATE_SURFACE name and nothing else passed _bind_substrate with no error, leaving hasattr(_ES,'_agent_prompt') False
- tests/test_cc_workflows_emitter_surface.py:44-62 parses only ast.Assign nodes inside _bind_substrate, so no _ES.<attr> call site is reachable by it; the file reports 3 passed with the gap present
- independently confirmed by the correctness lens (rename mutation), the architecture lens, and controller static analysis

Suggested fix: Add _agent_prompt to SUBSTRATE_SURFACE and bind it like the others, and extend the guard test's name collection to also walk ast.Attribute nodes whose value is Name(id='_ES').

**P04 — New OSError subclasses carry no errno, strerror, or filename** · `plugins/saga/scripts/saga.py:852` · lens `api-contract` · dimension `serialization-errors`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Both new exceptions are constructed from a formatted string, so errno, strerror and filename are all None on the raised object; a handler that branches on exc.errno -- the standard machine-actionable contract, and the shape this repository's own _safe_oserror reads -- silently takes the None path.

Evidence:

- saga.py:852 and :857-859
- lens check: constructing the class from str(OSError(ENOSPC, ...)) yields errno None, strerror None, filename None while str() still reads the full message
- the repository's existing convention that depends on those fields is plugins/saga/scripts/fleet_doctor.py:81-88
- no current caller of saga.save() inspects errno -- the only production caller is scaffold_checkpoint.py:91 -- so nothing breaks today; the contract does

Suggested fix: raise SagaTickEnvelopeWriteError(exc.errno, exc.strerror, exc.filename) from exc, and for the index variant set errno and filename from the cause after constructing it with the annotated message.

**P05 — Both new entry points exit outside their documented contract** · `plugins/saga/scripts/plan_pre_answers.py:328` · lens `api-contract` · dimension `serialization-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The carrier validator's shipped contract is exactly two codes, yet an unreadable --invocation-file exits 1 with a raw traceback and no JSON; the conformance script crashes on a non-UTF-8 document with exit 1, the same code its docstring reserves for a real conformance failure, so a consumer cannot tell a failure from a crash.

Evidence:

- plan_pre_answers.py:328 reads the file unguarded, against plugins/saga/skills/plan/SKILL.md:145-146
- lens run: --invocation-file /nope/missing.txt gave FileNotFoundError and exit 1
- plan_artifact_conformance.py:102 reads unguarded while its docstring at 18-19 declares 0 or 1; a scratch root holding one file with a 0xff byte gave UnicodeDecodeError, exit 1, no stdout
- that same main() already models the correct shape one branch earlier -- a missing root prints a one-key JSON error and exits 2, which the docstring also fails to mention

Suggested fix: Wrap the file read in plan_pre_answers.main and the per-document read in check_document so an unreadable path emits the same one-key JSON error object and exit 2 the conformance script already uses for a bad root, and add exit 2 to both docstrings.

**P06 — Validator report is labelled with the carrier's schema token** · `plugins/saga/scripts/plan_pre_answers.py:335` · lens `api-contract` · dimension `serialization-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

main stamps its outcome document with schema plan_pre_answers.v1 although the document's shape is applied/omitted/stop/caller, so one version token names two incompatible objects, and the report is refused by the very evaluator that emitted it; no shipped surface documents the report shape at all.

Evidence:

- plan_pre_answers.py:332-343
- lens round-trip: the exact stdout document, re-fenced as json and fed back to evaluate, returned 'pre-answer carrier refused: applied, omitted, stop are not admitted'
- the only prose describing the output is plugins/saga/skills/plan/SKILL.md:145 ('It prints the outcome as JSON'), which names no field

Suggested fix: Emit a distinct token for the report -- plan_pre_answers_outcome.v1 -- and document its four fields in plugins/saga/references/saga-spec.md section 15 beside the carrier shape.

**P07 — A well-formed carrier in a JSON fence vanishes without a stop** · `plugins/saga/scripts/plan_pre_answers.py:161` · lens `api-contract` · dimension `serialization-errors`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The fence info string is compared case-sensitively while the schema token is matched case-insensitively for the express purpose of catching near-misses loudly, so a caller writing an uppercase JSON fence has a fully valid settled decision discarded with an outcome field-for-field identical to no carrier.

Evidence:

- plan_pre_answers.py:161 against :123-124 and the module docstring's own principle at :42-43
- lens run: evaluate on an uppercase-JSON-fenced valid carrier returned applied {} omitted ('backend','destination') caller None stop None, byte-identical to the no-fence result
- the fence tests at tests/test_plan_pre_answers.py:302-315 cover a yaml fence and an info-less fence, never a case variant of json

Suggested fix: Either lowercase the info string before comparison at line 161, or keep the strict match and stop when a non-json fence contains a parseable object declaring the plan_pre_answers family.

**P08 — Shipped 0.150.0 entry contradicts the carrier the code performs** · `plugins/saga/CHANGELOG.md:9` · lens `api-contract` · dimension `specification-documentation-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The changelog is the surface an integrating caller reads first, and it states two things the code does not do -- that a supplied value is applied, and that an unknown schema token is refused whole -- while omitting the operator ruling that makes two of the three backend values stop.

Evidence:

- plugins/saga/CHANGELOG.md:9 against plan_pre_answers.py:260-273 -- a carrier with backend cc-workflows-ultracode returns a stop, not an apply
- plugins/saga/CHANGELOG.md:12 against plan_pre_answers.py:114-124 and :177 -- a carrier with schema other_tool.v9 returns stop=None, applied={}, ignored rather than refused
- the repair corrected both points in the other two surfaces (saga-spec.md:699-706 and plan/SKILL.md:154-163), which is why cycle-1 F07a is partial rather than not-fixed
- independently found by the controller before this lens returned

Suggested fix: Rewrite the 0.150.0 bullet at CHANGELOG.md:8-14 to say inline and any valid destination are applied while team-execution and cc-workflows-ultracode stop and surface, and to state the two-case schema rule rather than a blanket whole-refusal.

**A02 — Single-source claim is false in its own file** · `plugins/saga/references/execution-spec.md:401` · lens `architecture-maintainability` · dimension `simplicity-abstraction-duplication-changeability`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The repair deleted one copy of the validate/emit command pair and wrote that the commands live with the capability, single source, but the same file still carries the pair 25 lines below and a third copy sits in a Saga command, so the deduplication did not happen.

Evidence:

- the parenthetical claim at plugins/saga/references/execution-spec.md:401-402
- surviving copies at plugins/saga/references/execution-spec.md:429 and :432 under the CLI heading at :425, and at plugins/saga/commands/tier.md:48-49
- a fourth at plugins/cc-workflows/skills/cc-workflows/SKILL.md:68,78; a repo-wide grep returns three live command-pair sites, down from four at 5ec8ea76 -- not one

Suggested fix: Either delete the parenthetical single-source claim, or make the CLI section and commands/tier.md point at the same place the flow steps now point at.

**A03 — Saga's reference cites another plugin's step numbers, unpinned** · `plugins/saga/references/execution-spec.md:400` · lens `architecture-maintainability` · dimension `dependency-direction`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Saga's own document now describes a Saga command-line tool by pointing at a positional step number in a file owned by a different plugin, with no drift pin and no declared dependency, so renumbering the other plugin's skill silently misdirects the reader.

Evidence:

- plugins/saga/references/execution-spec.md:400 cites cc-workflows SKILL.md Step 4 and :404 cites Step 5
- those steps at plugins/cc-workflows/skills/cc-workflows/SKILL.md:66 and :74 invoke plugins/saga/scripts/execution_spec.py and plugins/saga/scripts/spec_table.py -- both Saga scripts
- grep for 'Step 4'/'Step 5' across tests/*.py returns nothing, so no test binds the pointer; neither plugin manifest declares a dependency (carried finding F31)

Suggested fix: Cite the step by its stable heading text rather than its number and add a literal-consistency pin in tests/test_workflow_extraction.py, the same shape as the readonly-verifier agent-type guard.

**A04 — A private Saga name crosses the boundary outside SUBSTRATE_SURFACE** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` · lens `architecture-maintainability` · dimension `separation-of-concerns`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_ES._agent_prompt is reached at the call site rather than through _bind_substrate, so the declared 29-name surface and its two-way guard do not cover it, and the exact failure the F10a repair claimed to close still ships.

Evidence:

- emitter.py:1348 calls _ES._agent_prompt(spec, retry_unit); _agent_prompt is absent from SUBSTRATE_SURFACE at :48-77
- lens mutation: renaming _agent_prompt throughout plugins/saga/scripts/execution_spec.py left tests/test_cc_workflows_emitter_surface.py at 3 passed, while tests/test_workflow_emitter.py went to 1 failed / 81 passed with AttributeError at emitter.py:1348; restored
- independently confirmed by the correctness lens and by controller static analysis: of the emitter's four _ES.<attr> accesses only _agent_prompt is undeclared, and the guard test walks only ast.Assign nodes inside _bind_substrate
- the DECISIONS entry claiming the private surface is 'declared in SUBSTRATE_SURFACE and pinned both ways' is therefore inaccurate

Suggested fix: Add _agent_prompt to SUBSTRATE_SURFACE and bind it in _bind_substrate, and extend the guard's name collection to also read _ES.<name> attribute accesses across the whole module, not only assignments inside _bind_substrate.

**A05 — A second Saga module is imported wholesale outside the declared seam** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:41` · lens `architecture-maintainability` · dimension `separation-of-concerns`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The emitter imports concurrency_governor, which exists only under plugins/saga/scripts/, resolving purely by the sys.path side effect of the spec shim -- a whole-module cross-plugin dependency that the declared surface, the fail-loud bind, and the plugin's boundary documentation all omit.

Evidence:

- emitter.py:41 imports it and :916 calls concurrency_governor.ordered_chunks; the module lives at plugins/saga/scripts/concurrency_governor.py and not in the plugin's own scripts directory
- plugins/cc-workflows/README.md:22-26 states the seam is the typed execution spec and names only execution_spec.py
- the import at :41 precedes _bind_substrate(_ES) at :151, so a foreign execution_spec in sys.modules yields a ModuleNotFoundError before the fail-loud check can report the real cause

Suggested fix: Name concurrency_governor in the README's boundary section and in the DECISIONS seam entry, and move the import below the _bind_substrate(_ES) call so the actionable failure fires first.

**A06 — Generic OSError branch misattributes a read failure as a write** · `plugins/saga/scripts/saga.py:1705` · lens `architecture-maintainability` · dimension `readability-naming-error-contracts`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The new fallback is reachable via restore() reading the prior tick, but it prints 'failed to write the saga tick' when nothing was written, and prescribes saga.py restore -- a command that fails with the same error.

Evidence:

- saga.py:1705-1714; the reachable read is restore(root, saga.saga_id) at :798, inside the try at :1671
- lens reproduction: chmod 000 on the existing envelope then saga.py save -> 'error: failed to write the saga tick: [Errno 13] Permission denied ... check whether a tick envelope was written ... (saga.py restore)', exit 2; running the prescribed saga.py restore on the same tree gave a bare PermissionError traceback, exit 1

Suggested fix: Reword the fallback to 'failed during the saga save' and drop the saga.py restore prescription, or wrap restore() in its own named error so the read case is diagnosed separately.

**A07 — Required-field pin misses the template agents actually copy** · `plugins/saga/skills/plan/SKILL.md:253` · lens `architecture-maintainability` · dimension `architectural-fit-ownership-single-sources`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The drift pin binds REQUIRED_FIELDS to the prose bullet in plan-sections.md but not to the YAML frontmatter template in plan/SKILL.md, so dropping a required key from the template an authoring agent copies leaves the whole conformance suite green and every new plan failing the shipped check.

Evidence:

- pin at tests/test_plan_artifact_conformance.py:324-349 parses only the plan-sections.md:185 bullet plus a single sentence at plan/SKILL.md:265; the template is at plugins/saga/skills/plan/SKILL.md:253-262
- lens mutation: deleting the 'status: active' line from the template left uv run pytest tests/test_plan_artifact_conformance.py at 11 passed; restored
- by contrast the backend enum IS pinned -- dropping team-execution from plan_artifact_conformance.py:45 gave 1 failed, 36 passed

Suggested fix: Extend test_required_field_set_is_pinned_to_both_declarations to parse the YAML frontmatter block in plan/SKILL.md and assert its keys are a superset of REQUIRED_FIELDS.

**A08 — New plugin's own commands hardcode a repo-relative Saga path** · `plugins/cc-workflows/skills/cc-workflows/SKILL.md:68` · lens `architecture-maintainability` · dimension `conventions-portability-configuration`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The plugin documents SAGA_SPEC_ROOT and a four-rung resolver, then invokes Saga by a bare repo-relative path in the two steps Saga's reference now defers to, so an operator with the plugin installed from the marketplace rather than a repo checkout cannot run either step.

Evidence:

- plugins/cc-workflows/skills/cc-workflows/SKILL.md:68 (validate), :78 (emit), :86 (spec_table.py) -- none honours SAGA_SPEC_ROOT, which plugins/cc-workflows/README.md:34 documents as rung 1
- this is cycle-1 finding F12's defect class, unrepaired on the new plugin's side of the seam; plugins/saga/skills/work/SKILL.md:352 shows the intended variable form

Suggested fix: Add SAGA_SPEC_ROOT="${SAGA_SPEC_ROOT:-plugins/saga}" at the top of the Step 4 block and invoke "$SAGA_SPEC_ROOT"/scripts/execution_spec.py, repeating the assignment in each fenced block that uses it.

**A09 — Validator docstring claims no file reads while the new CLI reads one** · `plugins/saga/scripts/plan_pre_answers.py:45` · lens `architecture-maintainability` · dimension `significant-decision-documentation`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The F04 repair added a --invocation-file entry point but left the 'reads no file' purity claim standing in both the module docstring and the spec, reintroducing exactly the defect class cycle-1 F19 raised against the emitter and that the same commit fixed there.

Evidence:

- plan_pre_answers.py:45 reads 'Pure functions: reads the text it is given, writes nothing, reads no file (KTD5)'; :327-328 reads args.invocation_file.read_text(encoding='utf-8')
- plugins/saga/references/saga-spec.md:720-721 repeats 'runnable; reads the text it is given, writes nothing, reads no file'; plugins/saga/skills/plan/SKILL.md:142 documents the file-reading invocation

Suggested fix: Change both sentences to 'the evaluation functions are pure; the command line reads only the invocation file it is given and writes nothing', mirroring the wording already applied to the emitter docstring.

**C01 — Index-failure remedy falsely promises no duplicate tick** · `plugins/saga/scripts/saga.py:1690` · lens `correctness` · dimension `side-effects-errors-resource-lifecycle`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The index-only error tells the operator the re-run is idempotent and appends no duplicate tick, but re-running the same save allocates a second envelope, so the tick chain /resume replays gains a duplicate -- the repair swapped one false durable-state claim for another.

Evidence:

- saga.py:1685-1690 emits the sentence; _allocate_envelope_path at saga.py:660-670 always picks a fresh name
- lens measurement in a scratch repo: pre-created .claude/saga/state.json.tmp as a directory, ran saga.py save -> rc 2 with that message and one envelope 20260830-221521.md; removed the blocker, re-ran the identical command -> rc 0 and envelopes ['20260830-221521.md','20260830-221529.md']; saga.py ticks then reported 2 ticks with identical content
- the new test tests/test_saga_plan_save_and_routing.py:158-213 never re-runs the save, so the claim is unpinned

Suggested fix: Drop 'the re-run is idempotent and appends no duplicate tick' -- say the re-run rebuilds the index and appends a second, identical tick, harmless to restore but visible to saga.py ticks.

**C02 — Envelope-failure branch claims no tick when prior ticks exist** · `plugins/saga/scripts/saga.py:1701` · lens `correctness` · dimension `side-effects-errors-resource-lifecycle`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The envelope-write branch says the plan document now has NO saga tick referencing it unconditionally, but a saga whose earlier ticks already record the same plan_path still references it, so the operator is told the document is stranded when it is not -- the exact cycle-1 F05 defect, left standing on the sibling branch.

Evidence:

- saga.py:1694-1703
- lens measurement: first save wrote tick 20260830-221601.md with plan_path docs/plans/p.md; chmod 500 on the saga dir made the next envelope write fail -> rc 2 and 'the plan document docs/plans/p.md now has NO saga tick referencing it', while saga.py ticks still returned 1 tick carrying that same plan_path
- the guarding test at tests/test_saga_plan_save_and_routing.py:108-154 only asserts restore(...) is None, i.e. the first-tick case

Suggested fix: Condition the stranded sentence on latest_envelope_for(root, saga_id) being absent, exactly as cycle-1 F05's suggested fix stated; otherwise say the newest tick failed and the prior tick still references the document.

**C04 — Runnable validator cannot produce the documented conflict stop** · `plugins/saga/scripts/plan_pre_answers.py:331` · lens `correctness` · dimension `caller-enum-consumer-completeness`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

main calls evaluate(text) with no established mapping and the parser exposes no flag for one, so the contradiction stop that both saga-spec.md rule 3 and Plan Phase 0.7 promise can never be emitted by the entry point the prose tells the agent to run.

Evidence:

- plan_pre_answers.py:316-331 exposes only --invocation-file, confirmed with --help
- against plugins/saga/references/saga-spec.md:726-728 and plugins/saga/skills/plan/SKILL.md:157-159
- controller check: the established parameter has no producer anywhere in the repository outside tests/test_plan_pre_answers.py

Suggested fix: Add --established backend=<v>,destination=<v> (or a JSON file) and pass it into evaluate, or narrow both documents to say the contradiction check is a caller-side responsibility the command line does not perform.

**C05 — SUBSTRATE_SURFACE omits _agent_prompt, which the emitter calls** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` · lens `correctness` · dimension `caller-enum-consumer-completeness`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The emitter calls _ES._agent_prompt on the escalate-on-signal retry path but never declares it in SUBSTRATE_SURFACE, so _bind_substrate binds happily against a substrate lacking it and the failure surfaces later as an AttributeError at emit time -- precisely the failure the guard's docstring says it prevents.

Evidence:

- lens mutation: renaming def _agent_prompt( to def _agent_prompt_RENAMED( in plugins/saga/scripts/execution_spec.py:2199 left uv run pytest tests/test_cc_workflows_emitter_surface.py at 3 passed; mutation reverted
- lens proof: _bind_substrate(stub) with all 29 declared names set and no _agent_prompt SUCCEEDS
- controller static confirmation: the emitter's four _ES.<attr> accesses are _agent_prompt, _build_emission_routing_context, max_concurrent_agents, resolved_concurrency, and only _agent_prompt is absent from the 29-name tuple; the guard test at tests/test_cc_workflows_emitter_surface.py:45-61 walks only ast.Assign nodes inside _bind_substrate, so _ES.-qualified access is structurally invisible to it

Suggested fix: Add '_agent_prompt' to SUBSTRATE_SURFACE (making the private surface twelve, not eleven) and extend the guard's name collection to also walk _ES.<attr> accesses so qualified use is pinned too.

**C06 — Broken YAML reclassifies a new-contract plan as legacy** · `plugins/saga/scripts/plan_artifact_conformance.py:79` · lens `correctness` · dimension `state-data-invariants-transactions-concurrency`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

split_frontmatter swallows a yaml.YAMLError and returns empty fields, so a plan document that does declare backend: inline but has any YAML syntax error is classified legacy-no-backend, reported non-failing, and passes the gate -- violating the module's own rule that legacy is the absence of backend and nothing else.

Evidence:

- plan_artifact_conformance.py:79-85 and the classification at line 104
- lens execution: check_document on a document declaring backend: inline plus an unclosed 'tags: [a, b' produced legacy-no-backend | legacy=True | failing=False | 'no backend: -- legacy document', and corpus_exit returned 0

Suggested fix: Distinguish the two cases -- emit a failing unparseable-frontmatter finding when yaml.safe_load raises, instead of collapsing it into the legacy bucket.

**D06 — Journal entry records a fix that did not happen** · `docs/engineering-journal/LEARNINGS.md:39` · lens `documentation-clarity` · dimension `runbook-safety-rollback-links-generated-drift`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The durable learning tells future maintainers the duplicate-tick remedy was the OLD defect and that the new path re-runs idempotently, so the surviving falsehood is now recorded as resolved and will not be re-found.

Evidence:

- docs/engineering-journal/LEARNINGS.md:38-39, disproved by the two-envelope reproduction recorded against finding D03
- :39 also states 'All four prose surfaces corrected in the same commit' -- three of the four carry the replacement false claim

Suggested fix: Correct the Fix and Mechanism lines to state that the re-run appends one additional tick, and add a Validation line naming a test that pins it.

**D07 — No test pins any carrier prose surface to the code** · `plugins/saga/CHANGELOG.md:7` · lens `documentation-clarity` · dimension `runbook-safety-rollback-links-generated-drift`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Three documents state one contract and none is bound to plan_pre_answers.py, which is exactly how the changelog kept two false claims through a repair that corrected the other two surfaces.

Evidence:

- tests/test_plan_pre_answers.py:439-448 is the only prose check and it asserts the ABSENCE of rigid question shapes, never a parity claim
- a grep for the contract phrases across tests/ returns only assertions against the runtime stop string, never against the changelog, the spec, or the skill
- contrast tests/test_plan_artifact_conformance.py:324-349, which binds the shipped REQUIRED_FIELDS constant to the markdown declaration -- the lens mutation-proved it and restored

Suggested fix: Add a parity pin in the shape of test_required_field_set_is_pinned_to_both_declarations: parse the two-case schema sentence and the inline-only sentence from all three surfaces and bind them to SCHEMA_FAMILY and CARRIER_AUTO_APPLY_BACKENDS.

**D08 — Case-differing v1 token is refused but prose says only non-v1 is** · `plugins/saga/references/saga-spec.md:700` · lens `documentation-clarity` · dimension `shipped-behavior-parity`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

Both shipped surfaces say family matching is case-insensitive and that only a non-v1 token is refused, so a caller writing an uppercase version token expects it applied and instead gets a stop calling its own version token unrecognised.

Evidence:

- saga-spec.md:699-702 and plan/SKILL.md:161-163 state the two-case rule as non-v1-inside-family versus foreign-family
- lens run: an uppercase version token gave exit 2 with 'refused whole: unrecognised schema token'
- mechanism: plan_pre_answers.py:124 lowercases for family membership while :207 compares the token exactly; the module docstring at :117-119 names this case correctly, neither shipped surface does
- independently found by the agent-usability lens

Suggested fix: State it on both surfaces -- the token itself is matched exactly, so any casing other than the canonical token is inside the family and refused whole.

**S02 — Two refusal paths echo caller key names raw and unbounded** · `plugins/saga/scripts/plan_pre_answers.py:220` · lens `security` · dimension `confidentiality-logs-errors-egress`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The unknown-key listing and the duplicate-key stop interpolate caller-supplied key names directly with f-strings, bypassing _echo, so a refusal message Plan is instructed to reproduce verbatim can be arbitrarily long and can carry unescaped newlines and fence delimiters -- the defect _ECHO_LIMIT was added to close.

Evidence:

- plan_pre_answers.py:220 joins unknown keys with an f-string and never calls _echo; :167 interpolates the joined duplicate key names from :103
- lens measurement: one 50,000-character unknown key produced a 50,162-character stop string; 2,000 unknown keys produced 18,159; 1,000 duplicate keys produced 7,087; the _echo-guarded paths measured 154-209
- the comment at :86-88 claims a refusal message can never be inflated by unbounded input; tests/test_plan_pre_answers.py:361 asserts that only for the schema-token path

Suggested fix: Route both through _echo -- ', '.join(_echo(key) for key in unknown) at :220 and _echo(str(exc)) at :167 -- and extend test_refusal_messages_echo_bounded_values_only to cover all four refusal paths.

**T02 — Backend-enum rule in the shipped check has no positive test** · `plugins/saga/scripts/plan_artifact_conformance.py:122` · lens `testing` · dimension `requirements-regression-coverage`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The U1 contract's backend enum can be silently stopped enforcing and nothing goes red, because no fixture ever carries an out-of-enum backend value.

Evidence:

- lens mutation: 'if value not in BACKEND_ENUM:' -> 'if False:' at plan_artifact_conformance.py:122 left 11 passed, 0 failed
- KIND_BACKEND_NOT_IN_ENUM appears in the test file only at tests/test_plan_artifact_conformance.py:201 as a negative assertion
- control mutations DO go red: dropping backend from REQUIRED_FIELDS -> 1 failed; emptying the loop -> 1 failed; deleting the marker half -> 4 failed; rglob -> glob -> 2 failed

Suggested fix: Add a tmp_path fixture whose frontmatter carries an out-of-enum backend value and assert a KIND_BACKEND_NOT_IN_ENUM finding with corpus_exit == 1.

**T03 — Guard narrowed to Python leaves markdown pointers unresolved** · `tests/test_workflow_extraction.py:223` · lens `testing` · dimension `requirements-regression-coverage`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

A dangling docs/workflows pointer in live plugin markdown is now caught by nothing, and the narrowing was forced by a dangling pointer this very change created.

Evidence:

- the scan at tests/test_workflow_extraction.py:223 was narrowed from markdown plus both scripts directories to plugins/**/*.py only
- lens mutation: a nonexistent docs/workflows pointer added to a plugin markdown file left 12 passed; the same string in emitter.py gave 1 failed
- lens necessity check: re-running the pre-narrowing scan over plugins/**/*.md today yields exactly one dangling hit, docs/workflows/2026-06-02-saga-foundation-spec.json at plugins/saga/references/saga-spec.md:234, which this change rewrote from a docs/plans path; neither prefix ever named a file that exists
- independently confirmed by the controller: the same single dangling pointer, and the file never existed anywhere in repository history

Suggested fix: Keep markdown in the scan and exempt the illustrative envelope by name, or point the worked example at an artifact that exists under docs/workflows/.

**T04 — SUBSTRATE_SURFACE under-declares the real plugin boundary** · `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:1348` · lens `testing` · dimension `realistic-seams-mocks-integration-evidence`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_agent_prompt crosses the plugin seam through a qualified _ES. call but is absent from the declared surface, so the list a reader trusts to describe the boundary is wrong.

Evidence:

- the access is at emitter.py:1348; of the four parsed _ES.<attr> uses only _agent_prompt is missing from the 29-name tuple at :48-78
- lens mutation: renaming the definition in execution_spec.py left tests/test_cc_workflows_emitter_surface.py at 3 passed, 0 failed
- the guard IS armed for the names it parses: binding an undeclared name -> 1 failed; declaring an unbound name -> 2 failed; renaming a declared name -> 1 failed, 1 error
- repo-wide the same rename breaks 130 tests in the execution_spec suites, so the risk is a wrong declaration rather than an undetected break
- the comment at emitter.py:43-47 claiming the boundary cannot grow silently in either direction overstates what an assignments-only parse can see

Suggested fix: Add _agent_prompt to SUBSTRATE_SURFACE and extend the guard's name collection to also walk ast.Attribute accesses on the _ES name, so qualified call sites count as boundary crossings.

### P3

**U10 — Family match is case-insensitive but the token check is not** · `plugins/saga/references/saga-spec.md:699` · lens `agent-usability` · dimension `discoverability-invocation-schemas`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The contract tells a carrier-authoring agent the schema family is matched case-insensitively, so it predicts an uppercase v1 token is applied; the code compares the token case-sensitively and refuses the whole carrier.

Evidence:

- plugins/saga/references/saga-spec.md:699-701 and plan_pre_answers.py:114-124 against :207
- lens run: a carrier declaring an uppercase family token returned 'refused whole: unrecognised schema token', exit 2

Suggested fix: State that the version token is compared exactly; only family membership is case-insensitive.

**U11 — Release note keeps the blanket unknown-schema claim the code refutes** · `plugins/saga/CHANGELOG.md:11` · lens `agent-usability` · dimension `discoverability-invocation-schemas`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The 0.150.0 entry still says a carrier declaring an unknown schema token is refused whole, which the skill and spec were repaired to split into two cases, so a caller agent reading the release surface expects a loud refusal where a foreign family is silently ignored.

Evidence:

- plugins/saga/CHANGELOG.md:11-12 versus the repaired two-case wording at plugins/saga/skills/plan/SKILL.md:161-163
- lens run: a carrier declaring a foreign family returned applied {}, stop null, exit 0
- independently found by the controller and the api-contract lens

Suggested fix: Mirror the two-case sentence into the changelog entry.

**A10 — Documented command line loads and executes execution_spec twice** · `plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:130` · lens `architecture-maintainability` · dimension `dependency-direction`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_SELF_MODULE is captured under __main__ when the module runs as the documented command line, but the shim only looks for sys.modules['execution_spec'], so a second full copy of the 3099-line module is resolved and executed on every emit, contradicting the shim's own 'always one set' guarantee.

Evidence:

- plugins/saga/scripts/execution_spec.py:3096 versus the cache check at saga_spec_shim.py:135, whose docstring at :130-133 claims the spec classes in play are always one set
- lens reproduction: SAGA_SPEC_DEBUG=1 on a real emit printed 'cc-workflows: saga-spec rung=2 (repo-walk-up)'; a run_path probe then reported execution_spec registered separately
- emission stays correct only because the delegation re-binds via _bind_substrate(owner)

Suggested fix: Have load_execution_spec() also accept sys.modules['__main__'] when it exposes the substrate names, or have execution_spec.main() register itself under sys.modules.setdefault('execution_spec', _SELF_MODULE) before delegating.

**A11 — Producer carries no marker for nine of eleven bound private names** · `plugins/saga/scripts/execution_spec.py:1676` · lens `architecture-maintainability` · dimension `dependency-direction`  
Route `advisory -> downstream-resolver` · confidence 100 · pre-existing: no

The declared surface lives only in the consuming plugin, so a Saga maintainer refactoring an underscore-prefixed name sees no local signal that another plugin binds it, and the pin that would catch it is a repo test that does not exist for an installed plugin pair.

Evidence:

- the 'Emission substrate retained by Saga' banner at plugins/saga/scripts/execution_spec.py:2156 covers only _js_var (:2161) and _unit_script_symbols (:2173)
- the other nine declared private names are scattered outside it, at :352, :434, :1229, :1240, :1676, :1718, :1725, :1922, :2650; execution_spec.py declares no __all__

Suggested fix: Add a one-line '# cc-workflows SUBSTRATE_SURFACE' comment above each of the nine definitions, or gather them under the existing banner.

**A12 — Re-raised tick errors drop errno and filename** · `plugins/saga/scripts/saga.py:852` · lens `architecture-maintainability` · dimension `readability-naming-error-contracts`  
Route `advisory -> review-fixer` · confidence 100 · pre-existing: no

Both new classes are constructed with a single string argument, so errno and filename come back None on the raised exception and any future caller distinguishing a full disk from a permission failure sees nothing; isinstance(exc, OSError) still holds, so existing catchers are unaffected.

Evidence:

- saga.py:852 and :857-859
- lens probe: the wrapped exception reported errno None and filename None while the original carried errno 28 and its path; isinstance(wrapped, OSError) was True
- no current caller inspects .errno on a save, and plugins/saga/scripts/scaffold_checkpoint.py:91 calls save() with no except at all

Suggested fix: Construct as SagaTickEnvelopeWriteError(exc.errno, str(exc), exc.filename) and give both classes a shared SagaTickWriteError(OSError) base so a caller can catch either without naming both.

**C07 — A stray triple backtick silently drops the carrier** · `plugins/saga/scripts/plan_pre_answers.py:84` · lens `correctness` · dimension `boundary-types-serialization-numeric-time`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

_FENCE_RE pairs fence markers left to right with no odd-count handling, so one stray inline triple backtick before the carrier shifts the pairing, the carrier fence is never matched, and the caller's settled decision is discarded with no stop -- the silent resolution the carrier discipline exists to forbid.

Evidence:

- plan_pre_answers.py:84 and :160-161
- lens execution: a stray inline triple backtick followed by a well-formed json carrier returned applied={} stop=None, whereas the identical carrier alone returned applied={'backend':'inline'}; a four-backtick wrapper also yields applied={} stop=None

Suggested fix: Match fences on a line anchor with a backtick-count-aware closer so an unpaired or longer fence cannot offset the scan.

**C08 — Valid non-object JSON slips past the malformed-carrier stop** · `plugins/saga/scripts/plan_pre_answers.py:175` · lens `correctness` · dimension `boundary-types-serialization-numeric-time`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The isinstance(parsed, dict) guard silently skips any json fence holding a scalar or array, so a carrier a caller wrapped in a JSON array is dropped as no carrier -- indistinguishable from absence, which the carrier discipline declares a stop.

Evidence:

- plan_pre_answers.py:175-176 against the module docstring at lines 42-43
- lens execution: four json fences -- 42, a bare schema string, null, and a one-element array wrapping a valid carrier -- every one returned applied={} omitted=('backend','destination') stop=None

Suggested fix: Stop rather than continue when a json fence parses to a non-object whose serialized text contains the plan_pre_answers family token; keep continue only for blocks with no family token at all.

**C09 — Invocation-only stop masks a genuine established conflict** · `plugins/saga/scripts/plan_pre_answers.py:260` · lens `correctness` · dimension `side-effects-errors-resource-lifecycle`  
Route `manual -> review-fixer` · confidence 100 · pre-existing: no

The invocation-only backend check returns before the established comparison, so a carrier trying to escalate from an operator-settled inline to cc-workflows-ultracode is reported as requiring explicit invocation instead of naming the contradiction, hiding that a caller tried to override a settled cheaper tier.

Evidence:

- plan_pre_answers.py:260-285
- lens execution: evaluate(<ultracode carrier>, {'backend':'inline'}) stopped on the invocation-only reason with no mention of the established inline; both orders stop and apply nothing, so the outcome is safe and only the diagnosis is wrong

Suggested fix: Run the established comparison first and, when both apply, emit one stop naming the contradiction and the invocation-only rule together.

**C10 — Validator has an undocumented third exit with no JSON** · `plugins/saga/scripts/plan_pre_answers.py:327` · lens `correctness` · dimension `side-effects-errors-resource-lifecycle`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

args.invocation_file.read_text is unguarded, so a missing file exits 1 with a bare traceback and empty stdout, while an argparse error exits 2 with no stop field -- and Plan's prose instructs the agent that exit 2 always carries a stop reason to surface verbatim.

Evidence:

- plan_pre_answers.py:327-331; the docstring at 310-314 documents only 0 and 2, as does plugins/saga/skills/plan/SKILL.md:145-146
- lens execution: --invocation-file /nonexistent/x.txt returned rc 1, empty stdout, and a FileNotFoundError traceback on stderr

Suggested fix: Catch OSError around the read and print the same JSON shape with a stop naming the unreadable file, so every non-zero exit carries a surfaceable reason.

**C11 — Phase 5.2 lost the explicit ultracode pre-select fallback** · `plugins/saga/skills/plan/SKILL.md:351` · lens `correctness` · dimension `intent-behavior-completeness`  
Route `advisory -> human` · confidence 100 · pre-existing: no

The change deleted Plan's normal-offer instruction for what to pre-select when the recommender returns cc-workflows-ultracode, which the operator ruling placed out of scope; the prohibition survives so behaviour is intact, but the ruling's scope boundary was crossed.

Evidence:

- git diff bbac725a 76533cbe removes the sentence 'If recommended is cc-workflows-ultracode, do not pre-select it -- pre-select team-execution when a gated size/risk/consensus trigger fired, otherwise inline'
- the guard 'Never pre-select cc-workflows-ultracode. Never launch a Workflow because recommend_execution_backend() returned it.' survives at plugins/saga/skills/plan/SKILL.md:345-346, and line 350-351 still says to recommend only inline or team-execution
- the deletion came from 5ec8ea76, not the repair commit

Suggested fix: Operator call -- restore the deleted fallback sentence, or record that the surviving prohibition is deliberately the whole rule now.

**C12 — Empty backend field reported as the Python literal None** · `plugins/saga/scripts/plan_artifact_conformance.py:121` · lens `correctness` · dimension `boundary-types-serialization-numeric-time`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

str(fields.get('backend','')) returns 'None' when the key is present with a null value, so the operator is told 'backend: None is not one of ...' rather than that the field is empty, and the same document also produces a redundant missing-required-field finding.

Evidence:

- plan_artifact_conformance.py:121-130
- lens execution: check_document on frontmatter carrying a bare 'backend:' line produced both missing-required-field and 'backend: None is not one of inline | team-execution | cc-workflows-ultracode'

Suggested fix: Use str(fields.get('backend') or '') and skip the enum finding when the required-field finding already fired for backend.

**D09 — Undefined code P-D3 migrated from skill prose into the journal** · `docs/engineering-journal/DECISIONS.md:17` · lens `documentation-clarity` · dimension `terminology-cross-document-consistency`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

The code is expanded nowhere in the repository, so a maintainer reading the decision entry cannot learn which settled decision the extraction served.

Evidence:

- docs/engineering-journal/DECISIONS.md:17; a repository grep finds the code only there, at tests/test_workflow_extraction.py:160, in the plan at :619 which uses it without defining it, and inside the cycle-1 review artifacts
- plugins/saga/skills/plan/SKILL.md is now clean, so cycle-1 finding F41 is fixed at its cited site and the code simply moved

Suggested fix: Expand on first use in both the journal entry and the test comment.

**D10 — Changelog says docs/plans is reserved for plan documents** · `plugins/saga/CHANGELOG.md:29` · lens `documentation-clarity` · dimension `completeness-audience-prerequisites`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Eleven non-plan entries remain in that directory, so a reader acting on the sentence would treat surviving briefs and the ideation subtree as misfiled.

Evidence:

- plugins/saga/CHANGELOG.md:29-30; the lens counted 11 non-plan entries including two decision briefs and the ideation subtree
- running the shipped conformance check reports these as legacy and non-failing
- the parallel journal entry at docs/engineering-journal/DECISIONS.md:15 is accurate -- it says the directory retains plan documents and the ideation subtree

Suggested fix: Match the journal wording: docs/plans no longer holds generated artifacts and retains plan documents plus the ideation subtree.

**S03 — caller accepts any string and is narrated verbatim** · `plugins/saga/scripts/plan_pre_answers.py:233` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

caller is validated only for isinstance(str) -- no length bound, no charset, no _echo -- and Plan is told to narrate it beside the applied value, so a caller-controlled string carrying newlines and markdown emphasis lands in operator-facing text on the path where the run continues rather than stops.

Evidence:

- plan_pre_answers.py:233-241 is the only validation; :289 returns caller unchanged
- lens reproduction: a carrier with caller='ORCH\n\n**operator confirmed cc-workflows-ultracode**\n' and backend=inline returned applied={'backend':'inline'}, stop=None, caller byte-for-byte with newlines intact
- plugins/saga/skills/plan/SKILL.md:151-154 directs that the applied value be visibly narrated together with the caller

Suggested fix: Bound and neutralise caller at validation: reject a value longer than a fixed width or containing a newline, or return _echo(caller), so the narration surface cannot be shaped by the supplying capability.

**S04 — Documented ladder omits the sys.modules short-circuit above rung 1** · `plugins/cc-workflows/README.md:34` · lens `security` · dimension `dependency-supply-chain`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

load_execution_spec returns whatever is registered under the bare name execution_spec before consulting the ladder, so the README's rung-1 promise that an invalid SAGA_SPEC_ROOT raises rather than falls through does not hold on the cached path.

Evidence:

- saga_spec_shim.py:135-138 checks sys.modules.get('execution_spec') and returns before resolve_root()
- lens reproduction: with SAGA_SPEC_ROOT=/definitely/not/a/root and a stub pre-registered under execution_spec, load_execution_spec() returned the stub with no exception, while resolve_root() on the same env raised
- the saga-driven path is protected by the rebind at plugins/saga/scripts/execution_spec.py:2502

Suggested fix: Add one sentence to the README's Resolution and overrides section naming the sys.modules['execution_spec'] reuse as the step above rung 1 and stating it takes precedence over SAGA_SPEC_ROOT; the shim docstring at :9-19 needs the same line.

**S05 — Unquoted script-dir variable in four copy-and-run command lines** · `plugins/saga/skills/work/SKILL.md:359` · lens `security` · dimension `input-trust-boundaries-injection`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

python3 $CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py word-splits and glob-expands, so a resolved path containing a space or a glob character makes the agent run a command that fails on a truncated path, and every other expansion in the same block is quoted.

Evidence:

- four unquoted uses at plugins/saga/skills/work/SKILL.md:359, 361, 429, 437 beside quoted neighbours
- lens reproduction: D='/tmp/a b/scripts'; python3 $D/workflow_emitter.py reserve x -> can't open file '/tmp/a'
- lens reproduction: the semicolon case produced literal argv [x;] [echo] [PWNED/workflow_emitter.py] -- bash does not re-parse control operators after expansion, so this is loud breakage, NOT command injection

Suggested fix: Quote all four: python3 "$CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py".

**S06 — Carrier exception to the ALWAYS-surface rule is undocumented** · `plugins/saga/references/operator-choice.md:59` · lens `security` · dimension `authentication-authorization-tenant-isolation`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

operator-choice.md is the authority Plan Phase 5.2 defers to and it states the backend offer is ALWAYS surfaced, but Plan now skips that offer when a carrier applied backend: inline, and the decision contract carries no mention of the carrier.

Evidence:

- plugins/saga/references/operator-choice.md:59 'ALWAYS surface the Saga choice' against the new parenthetical at plugins/saga/skills/plan/SKILL.md:336-338
- grep for pre_answers/pre-answer across plugins/saga/references/*.md returns hits only in saga-spec.md
- the privilege direction is downward -- the suppressed offer resolves to the cheapest backend -- so this is contract consistency, not escalation

Suggested fix: Add one bullet to operator-choice.md section 2 naming the Phase 0.7 carrier as the single exception to the ALWAYS-surface rule, scoped to backend: inline, cross-referencing saga-spec.md section 15.

**T05 — Never-pre-select guard is file-level, not sentence-level** · `tests/test_workflow_extraction.py:107` · lens `testing` · dimension `behavior-sensitive-assertions`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

Corrupting the sentence the test is named for in work/SKILL.md leaves the test green, because an unrelated phrase elsewhere in the same file satisfies the substring check.

Evidence:

- lens per-file mutation: corrupting the sentence in plan/SKILL.md, operator-choice.md and execution-strategy.md each gave 1 failed, but work/SKILL.md alone stayed green because that file carries both 'never pre-select' (:53) and 'do not pre-select' (:275); only corrupting both turns it red
- the counterfactual half is fully armed for all four files: the merge-base branch restored verbatim, plus artificially wrapped variants, failed 8 times out of 8

Suggested fix: Require the sentence in the same clause as the backend it governs, asserting a collapsed-text regex binding the pre-select prohibition to cc-workflows-ultracode.

**T06 — Shipped conformance check has no caller outside its test** · `plugins/saga/scripts/plan_artifact_conformance.py:163` · lens `testing` · dimension `requirements-regression-coverage`  
Route `manual -> human` · confidence 100 · pre-existing: no

Cycle-1 F06t made the check callable but nothing calls it, so the contract is still enforced only when pytest runs -- the condition F06t was filed against.

Evidence:

- grep across scripts/ and .github/ returns nothing; no skill file carries a runnable command block for it, only prose mentions at plugins/saga/references/saga-spec.md:672-673
- contrast the sibling repair: plugins/saga/skills/plan/SKILL.md:142 gives plan_pre_answers.py an explicit runnable command block
- the only executor is the subprocess at tests/test_plan_artifact_conformance.py:101-118

Suggested fix: Either add a gate step in scripts/gate.sh running the conformance check over docs/plans, or give Plan Phase 5.3 a runnable command block the way Phase 0.7 has one.

**T07 — Drift pin matches shipped source text instead of importing** · `tests/test_plan_pre_answers.py:432` · lens `testing` · dimension `determinism-isolation-diagnostics-maintainability`  
Route `safe_auto -> review-fixer` · confidence 100 · pre-existing: no

A formatter reflow or a reordering of the enum tuple breaks the pin without any contract changing, and a semantically equivalent redefinition slips past it.

Evidence:

- the assertion at tests/test_plan_pre_answers.py:432 reads plan_artifact_conformance.py as text at :429-431
- the same file already imports the module properly for every other assertion, and tests/test_plan_artifact_conformance.py:75 binds BACKEND_ENUM from the module

Suggested fix: Load the module and assert conformance.BACKEND_ENUM == pre_answers.BACKEND_ENUM.

**T08 — Corpus integer survives the re-anchored conflict sentinel** · `tests/test_wave_file_conflicts.py:187` · lens `testing` · dimension `requirements-regression-coverage`  
Route `advisory -> downstream-resolver` · confidence 100 · pre-existing: yes

Contract obligation 7 and the plan's own requirement R33 forbid a pinned corpus count, and this change re-anchored the glob under the floor without retiring it.

Evidence:

- assert len(specs) >= 18 at tests/test_wave_file_conflicts.py:187, immediately under a glob this change rewrote from docs/plans/ to docs/workflows/
- lens scan of the seven touched test files found this as the only pinned corpus integer; named-path pins remain at tests/test_plan_artifact_conformance.py:272 and tests/test_workflow_extraction.py:215

Suggested fix: Drop the floor and assert the relation only -- every spec in the glob has zero wave conflicts -- since an empty glob is already caught by the population assertions in test_artifacts_moved_and_plans_directory_retained.

## Coverage

- **Suppressed by the confidence-admission rule:** none. No lens reported a finding below anchor 75.
- **Pre-existing, not charged to this diff:** one — finding T08, the `len(specs) >= 18` floor at
  `tests/test_wave_file_conflicts.py:187`. The floor predates this change; the change re-anchored the
  glob above it and left the floor standing, which is why it appears under obligation 7 as well.
- **Testing gaps named by the lenses:** the shipped conformance check has no caller outside its own
  test and no invocation prose (findings T06, U08); the backend-enum rule inside that check has no
  positive test, so disabling it leaves eleven tests green (finding T02); no test binds any carrier
  prose surface to the code, which is the mechanism by which the changelog kept two false claims
  through a repair that corrected the other two surfaces (finding D07); and no test references
  `CC_WORKFLOWS_SCRIPTS_DIR` at all, which is why the gate cannot see the Work skill regression.
- **Residual risk:** the cross-plugin seam remains a two-way import between
  `plugins/saga/scripts/execution_spec.py` and the extracted emitter, with a second Saga module —
  `concurrency_governor` — crossing wholesale outside the declared surface, and the documented
  command line loading the substrate twice. None of this breaks emission today, because the
  delegation re-binds each instance; all of it is undeclared.
- **Not verified here:** the full 24-step repository gate, which the caller supplied as green and
  which this review did not re-derive; and three test files that fail to import in a lens worktree
  for environment reasons unrelated to this change, which that lens disclosed and excluded from its
  full-suite runs.

## Fix routing

Twenty-nine consolidated fix requests, all unresolved: 28 owned by `review-fixer` and 1 by `human`;
15 classed `manual` and 14 `safe_auto`. `consolidate_fix_requests` groups only active,
non-pre-existing, non-advisory findings that share an owner, a class, and overlapping paths, so
disjoint path sets stayed separate and can be routed to different Work workers.

Suggested order for cycle 3, cheapest-decisive first:

1. `plugins/saga/skills/work/SKILL.md` — repeat the three assignments in the release and renew blocks
   and quote all four expansions. This is the only defect in the set that stops a shipped protocol
   from completing, and it is a four-line edit.
2. `plugins/saga/scripts/plan_pre_answers.py` — gate the malformed-carrier stop on carrier shape.
   One condition; it un-breaks Plan on two committed documents.
3. `plugins/saga/scripts/saga.py` — delete the idempotency clause and condition the stranded-document
   claim on whether a prior tick exists.
4. `plugins/saga/CHANGELOG.md` — mirror the two-case schema rule and the inline-only ruling that the
   spec and the skill already carry.
5. `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py` and its guard test — add
   `_agent_prompt` and teach the guard to see qualified accesses.
6. `tests/test_saga_plan_save_and_routing.py` — rename the fixture and assert the handler's own words.
7. `tests/test_workflow_extraction.py` — restore the markdown scan and fix the worked example instead.

## Boundary

This review mutated no reviewed source. `git diff 76533cbe HEAD -- plugins/ tests/ scripts/
.claude-plugin/` is empty. No version or release surface changed. Nothing was pushed, no pull request
was opened or updated, no merge was performed, and no GitHub issue, comment, label, or project field
was touched. The only durable writes are this artifact and its evidence-ledger copy.

## Typed result

The complete `review_result.v1` payload follows. `outcome` is its only decision field; the
independent-gate state above is carried alongside it, not folded into it.

```json
{
  "attempted_lenses": [
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "api-contract",
    "agent-usability",
    "documentation-clarity"
  ],
  "best_available_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
  "collection_operation": {
    "operation": "collect",
    "schema": "review_result.v1"
  },
  "cycle_history": [
    {
      "attempted_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "cycle": 1,
      "delta_checks": [],
      "failing_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "lens_results": [
        {
          "accepted": false,
          "applicable_dimensions": {
            "architectural-fit-ownership-single-sources": 7.0,
            "conventions-portability-configuration": 7.5,
            "dependency-direction": 7.5,
            "readability-naming-error-contracts": 8.5,
            "separation-of-concerns": 7.5,
            "significant-decision-documentation": 7.0,
            "simplicity-abstraction-duplication-changeability": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 7.428571428571429,
          "failing_dimensions": [],
          "lens_id": "architecture-maintainability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "F04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "F06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "F09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "F10",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "simplicity-abstraction-duplication-changeability",
              "finding_id": "F11",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "F12",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "significant-decision-documentation",
              "finding_id": "F13",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "F19",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "F20",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "boundary-types-serialization-numeric-time": 9.0,
            "caller-enum-consumer-completeness": 8.0,
            "intent-behavior-completeness": 8.0,
            "side-effects-errors-resource-lifecycle": 8.0,
            "state-data-invariants-transactions-concurrency": 9.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 8.4,
          "failing_dimensions": [],
          "lens_id": "correctness",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "F02c",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 75,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "F03c",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "F05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "F07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "F14",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "F21",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "F22",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "authentication-authorization-tenant-isolation": 7.0,
            "confidentiality-logs-errors-egress": 8.0,
            "dependency-supply-chain": 8.0,
            "input-trust-boundaries-injection": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [],
          "lens_id": "security",
          "non_applicable_dimensions": {
            "secrets-cryptography-session-handling": "the diff introduces no secret material, credential, session, token issuance, or encryption; the only primitive is hashlib.sha256 used as a content digest for spec identity, moved byte-identically from the merge base and not a security control"
          },
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "authentication-authorization-tenant-isolation",
              "finding_id": "F03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "F08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "F15",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "F23",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "confidentiality-logs-errors-egress",
              "finding_id": "F24",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-supply-chain",
              "finding_id": "F25",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "behavior-sensitive-assertions": 4.0,
            "determinism-isolation-diagnostics-maintainability": 7.0,
            "negative-edge-state-concurrency-time": 8.0,
            "realistic-seams-mocks-integration-evidence": 4.0,
            "requirements-regression-coverage": 5.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 5.6,
          "failing_dimensions": [
            "requirements-regression-coverage",
            "behavior-sensitive-assertions",
            "realistic-seams-mocks-integration-evidence"
          ],
          "lens_id": "testing",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "F01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "F04t",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "F06t",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "F16",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F17",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "F18",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F26",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "F27",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "determinism-isolation-diagnostics-maintainability",
              "finding_id": "F28",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "F29",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "interface-contract-compatibility": 7.0,
            "retry-idempotency-semantics": 9.0,
            "sdk-generated-client-impact": 9.0,
            "serialization-errors": 6.0,
            "specification-documentation-parity": 7.0,
            "versioning-deprecation": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [
            "serialization-errors"
          ],
          "lens_id": "api-contract",
          "non_applicable_dimensions": {
            "pagination-rate-limits": "no HTTP paging or throttling surface exists in this repository; the nearest analogue, agent-spawn concurrency, moved with the emitter and its drift guard followed it"
          },
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "F07a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "F08a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "F10a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "F14a",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "F21a",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "F30",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "versioning-deprecation",
              "finding_id": "F31",
              "priority": "P2",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "capability-parity-reachability": 4.0,
            "context-constraints-acceptance-examples": 6.0,
            "discoverability-invocation-schemas": 6.0,
            "machine-readable-output-actionable-errors": 6.0,
            "safe-bounded-idempotent-resumable-context-cost": 8.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 6.0,
          "failing_dimensions": [
            "capability-parity-reachability",
            "discoverability-invocation-schemas",
            "context-constraints-acceptance-examples",
            "machine-readable-output-actionable-errors"
          ],
          "lens_id": "agent-usability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "F02u",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "F05u",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "F07u",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "F32",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "F33",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "F34",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "F35",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "F36",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 75,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "F37",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 75,
              "critical": false,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "F38",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "completeness-audience-prerequisites": 6.0,
            "runbook-safety-rollback-links-generated-drift": 5.0,
            "runnable-examples-actionability": 7.0,
            "shipped-behavior-parity": 4.0,
            "structure-navigation": 7.0,
            "terminology-cross-document-consistency": 7.0
          },
          "cycle": 1,
          "delta_check": null,
          "derived_overall": 6.0,
          "failing_dimensions": [
            "shipped-behavior-parity",
            "completeness-audience-prerequisites",
            "runbook-safety-rollback-links-generated-drift"
          ],
          "lens_id": "documentation-clarity",
          "non_applicable_dimensions": {},
          "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runnable-examples-actionability",
              "finding_id": "F02d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "F05d",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "F06d",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "F07d",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "F09d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "F13d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "F19d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "F20d",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "structure-navigation",
              "finding_id": "F35d",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "F39",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "structure-navigation",
              "finding_id": "F40",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "F41",
              "priority": "P3",
              "resolved": false
            }
          ]
        }
      ],
      "revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "unresolved_fix_ids": [
        "fix-cdedfbeff16d",
        "fix-47d14d72de14",
        "fix-30b14aa8860e",
        "fix-1e32f8de29bc",
        "fix-14dcdc14fb95",
        "fix-d4838903cdba",
        "fix-f6635448f785",
        "fix-ea8359027302",
        "fix-c77fb632f03a",
        "fix-07564e57d245",
        "fix-f21fbcdde228",
        "fix-4da2d62e8302",
        "fix-1ae49b5c69f0",
        "fix-0e28b4be689a",
        "fix-7bbe44049715",
        "fix-a2b3dcd68eb8",
        "fix-1a0d08a0aa66",
        "fix-3d055db303b8",
        "fix-4d72b7bf33e2",
        "fix-176784886a82",
        "fix-e28b316be7df",
        "fix-a6614db521d4",
        "fix-682af25ab42f",
        "fix-0ddffb195d12",
        "fix-0dd7e9a29e05",
        "fix-f1f46aac5b08",
        "fix-16799de10934",
        "fix-59c7c02e9c83",
        "fix-fb69a7a42548"
      ]
    },
    {
      "attempted_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "cycle": 2,
      "delta_checks": [],
      "failing_lenses": [
        "architecture-maintainability",
        "correctness",
        "security",
        "testing",
        "api-contract",
        "agent-usability",
        "documentation-clarity"
      ],
      "lens_results": [
        {
          "accepted": false,
          "applicable_dimensions": {
            "architectural-fit-ownership-single-sources": 5.5,
            "conventions-portability-configuration": 4.5,
            "dependency-direction": 4.0,
            "readability-naming-error-contracts": 5.0,
            "separation-of-concerns": 5.0,
            "significant-decision-documentation": 6.0,
            "simplicity-abstraction-duplication-changeability": 4.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 4.928571428571429,
          "failing_dimensions": [
            "architectural-fit-ownership-single-sources",
            "separation-of-concerns",
            "dependency-direction",
            "simplicity-abstraction-duplication-changeability",
            "readability-naming-error-contracts",
            "conventions-portability-configuration",
            "significant-decision-documentation"
          ],
          "lens_id": "architecture-maintainability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "A01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "simplicity-abstraction-duplication-changeability",
              "finding_id": "A02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "A03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "A04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "separation-of-concerns",
              "finding_id": "A05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "A06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "architectural-fit-ownership-single-sources",
              "finding_id": "A07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "conventions-portability-configuration",
              "finding_id": "A08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "significant-decision-documentation",
              "finding_id": "A09",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "A10",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-direction",
              "finding_id": "A11",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "readability-naming-error-contracts",
              "finding_id": "A12",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "boundary-types-serialization-numeric-time": 7.0,
            "caller-enum-consumer-completeness": 7.0,
            "intent-behavior-completeness": 6.5,
            "side-effects-errors-resource-lifecycle": 6.0,
            "state-data-invariants-transactions-concurrency": 7.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.8,
          "failing_dimensions": [
            "intent-behavior-completeness",
            "side-effects-errors-resource-lifecycle"
          ],
          "lens_id": "correctness",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C01",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "C03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "C04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "caller-enum-consumer-completeness",
              "finding_id": "C05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "state-data-invariants-transactions-concurrency",
              "finding_id": "C06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "C07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "C08",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C09",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "side-effects-errors-resource-lifecycle",
              "finding_id": "C10",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "intent-behavior-completeness",
              "finding_id": "C11",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "boundary-types-serialization-numeric-time",
              "finding_id": "C12",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "authentication-authorization-tenant-isolation": 8.5,
            "confidentiality-logs-errors-egress": 7.5,
            "dependency-supply-chain": 7.0,
            "input-trust-boundaries-injection": 7.0
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 7.5,
          "failing_dimensions": [],
          "lens_id": "security",
          "non_applicable_dimensions": {
            "secrets-cryptography-session-handling": "no secret material, credential, session issuance or cryptographic control is introduced; the only primitive is hashlib.sha256 as a spec-identity content digest, and the one session-adjacent surface (--session-id threaded into reserve/attest) is a byte-identical move writing only to git-ignored .saga/"
          },
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "S01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "confidentiality-logs-errors-egress",
              "finding_id": "S02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "S03",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "dependency-supply-chain",
              "finding_id": "S04",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "input-trust-boundaries-injection",
              "finding_id": "S05",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "authentication-authorization-tenant-isolation",
              "finding_id": "S06",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "behavior-sensitive-assertions": 6.5,
            "determinism-isolation-diagnostics-maintainability": 7.5,
            "negative-edge-state-concurrency-time": 8.0,
            "realistic-seams-mocks-integration-evidence": 7.5,
            "requirements-regression-coverage": 7.0
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 7.3,
          "failing_dimensions": [
            "behavior-sensitive-assertions"
          ],
          "lens_id": "testing",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "T01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "realistic-seams-mocks-integration-evidence",
              "finding_id": "T04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "behavior-sensitive-assertions",
              "finding_id": "T05",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T06",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "determinism-isolation-diagnostics-maintainability",
              "finding_id": "T07",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "requirements-regression-coverage",
              "finding_id": "T08",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "interface-contract-compatibility": 6.5,
            "retry-idempotency-semantics": 6.0,
            "sdk-generated-client-impact": 7.5,
            "serialization-errors": 6.0,
            "specification-documentation-parity": 6.0,
            "versioning-deprecation": 7.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.583333333333333,
          "failing_dimensions": [
            "interface-contract-compatibility",
            "serialization-errors",
            "retry-idempotency-semantics",
            "specification-documentation-parity"
          ],
          "lens_id": "api-contract",
          "non_applicable_dimensions": {
            "pagination-rate-limits": "the change adds no paged collection, cursor, quota or throttled interface; the one collection surface (check_plan_corpus, a sorted rglob over a local directory) is deterministic, complete, and has no client-visible ordering or limit contract"
          },
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "retry-idempotency-semantics",
              "finding_id": "P01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "P02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "interface-contract-compatibility",
              "finding_id": "P03",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P04",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P05",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "serialization-errors",
              "finding_id": "P07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "specification-documentation-parity",
              "finding_id": "P08",
              "priority": "P2",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "capability-parity-reachability": 6.0,
            "context-constraints-acceptance-examples": 6.5,
            "discoverability-invocation-schemas": 6.0,
            "machine-readable-output-actionable-errors": 6.0,
            "safe-bounded-idempotent-resumable-context-cost": 5.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.0,
          "failing_dimensions": [
            "capability-parity-reachability",
            "discoverability-invocation-schemas",
            "context-constraints-acceptance-examples",
            "machine-readable-output-actionable-errors",
            "safe-bounded-idempotent-resumable-context-cost"
          ],
          "lens_id": "agent-usability",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "U01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "U02",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "machine-readable-output-actionable-errors",
              "finding_id": "U03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "U04",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "U05",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "context-constraints-acceptance-examples",
              "finding_id": "U06",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "capability-parity-reachability",
              "finding_id": "U07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "U08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
              "finding_id": "U09",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "U10",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "discoverability-invocation-schemas",
              "finding_id": "U11",
              "priority": "P3",
              "resolved": false
            }
          ]
        },
        {
          "accepted": false,
          "applicable_dimensions": {
            "completeness-audience-prerequisites": 7.5,
            "runbook-safety-rollback-links-generated-drift": 5.5,
            "runnable-examples-actionability": 8.0,
            "shipped-behavior-parity": 5.5,
            "structure-navigation": 8.5,
            "terminology-cross-document-consistency": 6.5
          },
          "cycle": 2,
          "delta_check": null,
          "derived_overall": 6.916666666666667,
          "failing_dimensions": [
            "shipped-behavior-parity",
            "terminology-cross-document-consistency",
            "runbook-safety-rollback-links-generated-drift"
          ],
          "lens_id": "documentation-clarity",
          "non_applicable_dimensions": {},
          "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
          "score_accepted": false,
          "scoring_findings": [
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D01",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D02",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D03",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D04",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": true,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D05",
              "priority": "P1",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D06",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "runbook-safety-rollback-links-generated-drift",
              "finding_id": "D07",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "shipped-behavior-parity",
              "finding_id": "D08",
              "priority": "P2",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "terminology-cross-document-consistency",
              "finding_id": "D09",
              "priority": "P3",
              "resolved": false
            },
            {
              "confidence": 100,
              "critical": false,
              "dimension_id": "completeness-audience-prerequisites",
              "finding_id": "D10",
              "priority": "P3",
              "resolved": false
            }
          ]
        }
      ],
      "revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "unresolved_fix_ids": [
        "fix-8f87c9f3fa94",
        "fix-c77192119e7b",
        "fix-a34ff0c91932",
        "fix-35e0c83d365a",
        "fix-222ac29adc40",
        "fix-9a088bef2da2",
        "fix-8e3aec8e83c2",
        "fix-f0a36e7e26f8",
        "fix-a69fd443ef72",
        "fix-c1ecbf4f719a",
        "fix-9818846b9df7",
        "fix-2e198411f792",
        "fix-170084318624",
        "fix-3c9e1cd3a093",
        "fix-1db694550386",
        "fix-f03ab7a6f650",
        "fix-f78699abc585",
        "fix-ac87c3d71a22",
        "fix-4c0030371644",
        "fix-8a63bd53812c",
        "fix-5d21ac319010",
        "fix-9e055d1381da",
        "fix-64c523292cb9",
        "fix-1dca06ef0b96",
        "fix-cbe0f53498e0",
        "fix-b6525c38e39a",
        "fix-c4fbecfc8247",
        "fix-6cffb84cfd8a",
        "fix-8cc4f3f1ff3c"
      ]
    }
  ],
  "evidence_ledger": {
    "criteria": "docs/evidence/adhoc-cp918-saga-plan-improvement/criteria-code-review-5ec8ea7682706aa9f06e359c373cfd2032ee6ba9.json"
  },
  "external_advisory_reviews": [],
  "failing_lenses": [
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "api-contract",
    "agent-usability",
    "documentation-clarity"
  ],
  "findings": [
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "plugins/saga/CHANGELOG.md:9-10 against the enforcement at plan_pre_answers.py:260-273",
        "lens run: a carrier with backend team-execution gave exit 2, applied {}, caller null, and the invocation-only stop",
        "the ruling IS stated at saga-spec.md:705-710 and plan/SKILL.md:151-155"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "D02",
      "lens_id": "documentation-clarity",
      "line": 9,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add the inline-only qualification to the changelog bullet -- the carrier applies only inline automatically; team-execution and cc-workflows-ultracode are legal plan values that stop and surface.",
      "title": "Changelog claims any supplied value is applied and narrated",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "The changelog omits the operator ruling entirely, so an integrator building a carrier with backend team-execution expects it applied and instead gets a hard stop with no caller returned."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "plugins/saga/CHANGELOG.md:11-12 against plan_pre_answers.py:114-124",
        "lens run: a carrier declaring a foreign family with backend inline returned applied {}, stop null, exit 0 -- ignored, not refused",
        "saga-spec.md:699-702 and plan/SKILL.md:161-163 both carry the corrected two-case rule; the changelog alone was left behind",
        "independently found by the controller and the api-contract and agent-usability lenses"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "D01",
      "lens_id": "documentation-clarity",
      "line": 11,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Replace the clause with the two-case rule already shipped on the other two surfaces: a non-v1 token inside the plan_pre_answers family is refused whole; a foreign schema family is not a carrier and is ignored.",
      "title": "Changelog still says unknown schema token is refused whole",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "A release reader is told any unrecognised schema token is refused, so a typo or renamed envelope silently returns the identical no-carrier outcome and the caller believes a decision was handed over."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "intent-behavior-completeness",
      "evidence": [
        "plan_pre_answers.py:163-177 -- the json.JSONDecodeError and _DuplicateKeyError returns precede the _is_family_schema test at line 177",
        "lens reproduction: a json fence holding {\"name\":\"x\", // a comment, \"port\":8080} plus prose returned the malformed-carrier stop; a fence holding {\"a\":1,\"a\":2} returned the duplicate-keys stop; a valid carrier later in the same text is discarded",
        "independently reproduced by the security lens as its own finding, and by the controller against two committed in-repo documents"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "C03",
      "lens_id": "correctness",
      "line": 163,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Parse leniently first -- on a parse or duplicate-key failure, only stop when the raw block text contains the plan_pre_answers family token; otherwise treat the block as unrelated prose.",
      "title": "Any unrelated malformed json fence halts the Plan run",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "scan_carriers parses every json-fenced block and returns a stop before it ever checks the family schema, so a JSON-with-comments config sample pasted into a /plan request halts the whole run with 'pre-answer carrier refused' even though no carrier is present."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "plan_pre_answers.py:160-174 returns the stop at :170-174 before the family test at :177",
        "the contradicted promises are plugins/saga/references/saga-spec.md:734 and plugins/saga/skills/plan/SKILL.md:169, both saying a Brainstorm document with no carrier stops nothing",
        "lens scan with the module's own _FENCE_RE: 3 of 19 json fences under docs/brainstorms/, docs/plans/ and plugins/saga/skills/ do not parse; running the shipped entry point against two of them returned exit 2 with the malformed-carrier stop",
        "the only malformed-block test at tests/test_plan_pre_answers.py:333-341 uses a block that carries the schema token, so the non-carrier case is untested",
        "independently reproduced by the security lens, the correctness lens, and the controller against two committed in-repo documents"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "P02",
      "lens_id": "api-contract",
      "line": 170,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "In scan_carriers, raise the malformed stop only for a block that is carrier-shaped -- re-scan the raw block text for the plan_pre_answers family token; leave a json fence with no family token as a non-candidate, exactly as a foreign schema already is.",
      "title": "Any unparseable json fence halts /plan with no carrier present",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "scan_carriers applies the malformed-carrier stop to every fenced block whose info string is json, before it ever checks whether the block declares the plan_pre_answers family, so invocation text containing an illustrative or truncated JSON example and no carrier at all stops the run -- contradicting the closing promise of both shipped documents."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "plan_pre_answers.py:170-174 (except json.JSONDecodeError) and :164-169 (duplicate-key path) both fire before the family gate at :177",
        "controller reproduction: python3 plugins/saga/scripts/plan_pre_answers.py --invocation-file docs/brainstorms/2026-08-12-orchestrate-codex-phase-requirements.md -> exit 2, stop set, on a document with no carrier",
        "controller reproduction: an unparseable non-carrier json fence placed before a valid {\"schema\":\"plan_pre_answers.v1\",\"backend\":\"inline\"} carrier -> applied={}, stop set",
        "controller measurement: 3 committed documents under docs/ carry a json fence that fails json.loads; 2 of them (docs/brainstorms/2026-08-12-orchestrate-codex-phase-requirements.md, docs/plans/2026-07-13-459-earned-ratings-plan.md) are documents /plan legitimately receives as input",
        "contradicts plugins/saga/skills/plan/SKILL.md:168 'Direct /plan -- an issue, a prompt, or a Brainstorm document, no carrier -- is unchanged: nothing applied, nothing narrated, nothing stopped'"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "S01",
      "lens_id": "security",
      "line": 170,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Gate both stops on carrier shape: treat an unparseable or duplicate-key json block as a malformed carrier only when its raw text contains the plan_pre_answers family token; otherwise skip it as before. The multi-carrier stop at :179 is already correctly scoped and shows the intended shape.",
      "title": "Any unparseable json fence halts Plan and suppresses a carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "scan_carriers returns the malformed-carrier stop for ANY ```json block before checking whether the block declares the plan_pre_answers family, so an unrelated JSON example in an issue body or Brainstorm document halts Phase 0.7 -- and, placed earlier in the text, silently overrides a well-formed carrier that follows."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "capability-parity-reachability",
      "evidence": [
        "plan_pre_answers.py:331; argparse at :316-326 exposes only --invocation-file, confirmed by the usage line",
        "the established parameter exists at :198 and :274-285 and has no production caller -- only tests/test_plan_pre_answers.py",
        "the rule is stated at plugins/saga/skills/plan/SKILL.md:158-160",
        "independently found by the correctness and api-contract lenses and by the controller"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "U04",
      "lens_id": "agent-usability",
      "line": 331,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add repeatable --established backend=<v> / --established destination=<v> options and pass them through to evaluate, then show them in Phase 0.7's command.",
      "title": "Contradiction rule unreachable through the runnable entry point",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "Phase 0.7's third rule stops on a value contradicting one already established in the thread, but the command line calls evaluate(text) with no established mapping and offers no flag to supply one, so the agent must hand-implement the rule the runnable validator was added to remove."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "saga.py:1687-1689, repeated at plugins/saga/skills/plan/SKILL.md:616-617 and docs/engineering-journal/LEARNINGS.md:39",
        "lens reproduction in a sandbox repository: the index fault gave exit 2 with one envelope; removing the fault and re-running the identical command gave exit 0 and a SECOND envelope, identical except updated_at",
        "mechanism at saga.py:660-670 -- _allocate_envelope_path always picks a non-colliding filename, so a re-run cannot overwrite",
        "the regression test at tests/test_saga_plan_save_and_routing.py never checks the idempotence claim, so the green gate cannot see it",
        "independently reproduced by the correctness, api-contract and agent-usability lenses"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "D03",
      "lens_id": "documentation-clarity",
      "line": 1687,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Say what the re-run does -- it rebuilds the index and appends one additional tick carrying the same state -- or make the index-only re-run reuse the existing envelope path.",
      "title": "Index-failure recovery step falsely claims idempotence",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The prescribed recovery -- re-run the same save -- writes a second tick envelope, so an operator following the message silently doubles the append-only tick log while being told it cannot."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "retry-idempotency-semantics",
      "evidence": [
        "plugins/saga/scripts/saga.py:1688 (message) and :697 (the same claim in the SagaTickIndexWriteError docstring)",
        "lens reproduction: pre-created .claude/saga/state.json as a directory, ran save -> rc 2 with the quoted message and one envelope; removed the blocker, re-ran the identical argv -> rc 0 and two envelopes; saga.py ticks then reported count: 2",
        "both sentences were INTRODUCED by the cycle-1 repair commit 1e74b49a",
        "the guard test tests/test_saga_plan_save_and_routing.py:157-209 narrates the duplicate-tick problem in its docstring but never re-runs the save",
        "independently reproduced by the correctness lens"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "P01",
      "lens_id": "api-contract",
      "line": 1688,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Delete the idempotence clause from saga.py:1688 and :697, or make it true by having save reuse an existing envelope whose rendered content is byte-identical before allocating a new path.",
      "title": "Index-failure remedy promises idempotence, duplicates the tick",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The operator-facing error tells the operator to re-run the save and asserts the re-run is idempotent and appends no duplicate tick, but _allocate_envelope_path allocates a fresh filename every call, so the re-run writes a second envelope and the saga history gains a phantom tick."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
      "evidence": [
        "saga.py:1684-1689; envelope allocation at :660-667 mints a new sequence file per save",
        "lens reproduction in a throwaway repository: clean save gave 1 envelope; forcing the index write to fail printed the documented message with exit 2 and 2 envelopes; re-running the identical save gave exit 2 again and 3 envelopes",
        "independently reproduced by the correctness and api-contract lenses"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "U09",
      "lens_id": "agent-usability",
      "line": 1688,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Say the re-run rewrites the index only once the underlying write failure is cleared, and that it appends another tick envelope; drop the idempotency claim.",
      "title": "Index-failure recovery line asserts a false idempotency",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The repaired message tells the agent the re-run is idempotent and appends no duplicate tick, but each re-run allocates a new envelope file and fails again while the cause persists, so an agent following the recovery line loops and inflates the tick log."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "saga.py:1700-1701 states the claim with no guard on prior state; echoed at plugins/saga/skills/plan/SKILL.md:613-615",
        "lens reproduction: after a successful save recording the plan path, making the saga directory read-only and re-running gave exit 2 with 'now has NO saga tick referencing it', while saga.py restore then returned that same plan_path with found true",
        "the regression test at tests/test_saga_plan_save_and_routing.py:150-154 asserts restore(...) is None but only on a first save, never with a prior tick present",
        "independently reproduced by the correctness lens; this is cycle-1 finding F05d surviving on the sibling branch"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "D04",
      "lens_id": "documentation-clarity",
      "line": 1700,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Condition the claim on whether a prior tick exists -- check restore, or the prior value already computed at saga.py:781 -- and say this save's tick was not written while naming the plan's last recorded tick when one is there.",
      "title": "Envelope-failure message asserts no tick unconditionally",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "When any earlier tick already recorded the plan path -- the normal case, since Plan saves at Phase 0 and again at Phase 5.3 -- the message tells the agent the plan is stranded while restore returns it, producing a false halt on fully tracked work."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "machine-readable-output-actionable-errors",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:145-146",
        "lens runs: --invocation-file /tmp/does-not-exist.txt gave a FileNotFoundError traceback and exit 1; an unrecognised argument gave exit 2 with empty stdout",
        "source: plan_pre_answers.py:327-328 reads the file with no guard; :344 returns 2 only for a stop",
        "independently found by the correctness and api-contract lenses"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "U03",
      "lens_id": "agent-usability",
      "line": 145,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Catch OSError in main() and emit the same JSON shape with a stop naming the unreadable path, and state in Phase 0.7 that a usage error also exits 2 without a stop.",
      "title": "Phase 0.7's exit-code contract is wrong on both failure paths",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Phase 0.7 tells the agent that exit 2 always carries a stop to surface exactly, but a usage error also exits 2 with no JSON at all, and an unreadable invocation file exits 1 with a raw traceback -- an undocumented code the prose never mentions."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:161-167 carries the two schema rules and the malformed-carrier rule but no fence rule; plan_pre_answers.py:161 skips any other info string",
        "lens run: a carrier fenced with an uppercase JSON info string carrying destination pr and backend inline returned applied {}, stop null, exit 0",
        "the rule exists in plugins/saga/references/saga-spec.md:715-716 but not in the skill the agent executes",
        "the api-contract lens found the same silent drop from the code side"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "U05",
      "lens_id": "agent-usability",
      "line": 164,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add to the malformed-carrier bullet: the fence info string must be exactly lowercase json; any other info string is not a carrier and is ignored.",
      "title": "Five rules omit the fence-info rule; a wrong fence drops silently",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The validator only scans blocks whose fence info string is exactly json, so a carrier fenced with an uppercase JSON info string is ignored with no stop and no narration -- the settled decisions vanish and the conversation re-asks -- yet none of Phase 0.7's five rules states the fence requirement."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:335-337 (skip), :349-353 (the only recommend_execution_backend instruction, bundled with the offer), :572 and :589 (save templates requiring its output)",
        "lens run: saga.py save with --orchestration-recommended \"\" gave 'invalid choice', exit 2, no tick written; plugins/saga/scripts/saga.py:1556-1561 restricts the flag to the enum",
        "the controller independently flagged the same ambiguity as a risk to the operator ruling 2 telemetry before this lens returned"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "U06",
      "lens_id": "agent-usability",
      "line": 335,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Extend the parenthetical: skip only the operator-facing question; still call recommend_execution_backend, still record --orchestration-recommended and --orchestration-mode inline, and still write the plan-doc backend field.",
      "title": "Skip the offer leaves the recommend call and tick flag undefined",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Phase 5.2's carrier parenthetical says to skip the offer, but the skipped paragraph is the only place that tells the agent to call recommend_execution_backend, and Phase 5.3's save template then demands --orchestration-recommended with that output -- a placeholder the agent cannot fill, and passing an empty value aborts the save."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "conventions-portability-configuration",
      "evidence": [
        "assigned (not exported) at plugins/saga/skills/work/SKILL.md:352; consumed at :429 and :437, which run after the Workflow tool returns",
        "controller confirmation of block boundaries: the fenced blocks in that file run 346-363 (holds the assignment at :352 and the consumers at :359, :361), then a separate block 428-431 holding :429, then a separate block 436-438 holding :437 -- neither later block carries the assignment",
        "lens reproduction: bash -c 'python3 $CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py renew /dev/null' -> can't open file '/workflow_emitter.py', exit 2",
        "git show 1e74b49a shows both lines previously carried the literal path, so this is a regression the repair introduced",
        "grep -rn CC_WORKFLOWS_SCRIPTS_DIR tests/ returns nothing, so the gate cannot see it"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "A01",
      "lens_id": "architecture-maintainability",
      "line": 429,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Repeat the CC_WORKFLOWS_SCRIPTS_DIR=\"${CC_WORKFLOWS_SCRIPTS_DIR:-plugins/cc-workflows/skills/cc-workflows/scripts}\" assignment at the top of the release block and the renew block, and quote the expansion.",
      "title": "Lease release and renew reference an unset shell variable",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The F12 repair replaced two working literal paths with $CC_WORKFLOWS_SCRIPTS_DIR, which is assigned only in the launch block at line 352 and is not in scope in the later release and renew blocks, so the lease is never released."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
      "evidence": [
        "plugins/saga/skills/work/SKILL.md:352 assigns without export; :429 and :437 consume",
        "lens run of line 429 verbatim in a fresh shell: can't open file '/workflow_emitter.py', exit 2; with the scripts dir hand-resolved it still fails on the equally unbound $WORKFLOW_LEASE_METADATA",
        "the lease-metadata half is pre-existing; the scripts-dir variable is new in this change",
        "controller confirmation of the fenced-block boundaries: 346-363 holds the assignment, 428-431 and 436-438 are separate blocks with none",
        "independently found by the architecture lens as its highest-impact item"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "U01",
      "lens_id": "agent-usability",
      "line": 429,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Repeat the three assignments (WORKFLOW_INVOCATION_ID, WORKFLOW_LEASE_METADATA, CC_WORKFLOWS_SCRIPTS_DIR) at the head of the release and renew blocks, or tell the agent to re-derive them from the saga tick.",
      "title": "Release and renew blocks lose the scripts-dir variable",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "CC_WORKFLOWS_SCRIPTS_DIR is assigned only in the pre-submit block at line 352, so the later release block at :429 and renew block at :437 -- separate fenced blocks an agent runs in a new shell after the Workflow tool returns -- expand it to empty and the protocol never closes."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "assert \"index\" in err at tests/test_saga_plan_save_and_routing.py:205; the fixture plan is docs/plans/2026-08-30-index-failure-plan.md, so the substring is satisfied by the path",
        "lens mutation: changing except SagaTickIndexWriteError to except NotImplementedError at plugins/saga/scripts/saga.py:1678 left 5 passed, 0 failed",
        "coverage under that mutation shows saga.py:1683-1692 and :1697-1704 unexecuted while the generic except OSError at :1705 runs"
      ],
      "file": "tests/test_saga_plan_save_and_routing.py",
      "finding_id": "T01",
      "lens_id": "testing",
      "line": 205,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Rename the fixture to a path containing no 'index', and assert the handler's own words: 'rewrite the saga state.json index' and 'IS still referenced by the'.",
      "title": "Index-failure assertion satisfied by the fixture's own filename",
      "touched_paths": [
        "tests/test_saga_plan_save_and_routing.py"
      ],
      "why_it_matters": "The whole SagaTickIndexWriteError handler can be deleted and the test that claims to prove it still passes, so the cycle-1 F05 repair is unguarded -- a new harness substitution the repair introduced."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "tests/test_workflow_extraction.py:218-230 scans plugins/**/*.py; the prior scan was plugins/**/*.md plus the two script directories",
        "lens mutation: appending a nonexistent docs/workflows reference to saga-spec.md left 12 passed; restored",
        "the test comment cites the worked example as the reason for the narrowing; that example names two non-existent paths, neither of which has ever been added in repository history",
        "independently confirmed by the testing lens and by the controller"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "D05",
      "lens_id": "documentation-clarity",
      "line": 223,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Restore the markdown scan and exempt the one illustrative block by fence or by an explicit allowlist of example stems, rather than dropping markdown coverage wholesale.",
      "title": "Dangling-pointer guard narrowed to Python, markdown unguarded",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "Every plugin markdown file may now name a docs/workflows spec that does not exist without any test noticing, so the reference migration this move owed has no ongoing guard on the prose side."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "docs/engineering-journal/LEARNINGS.md:38-39, disproved by the two-envelope reproduction recorded against finding D03",
        ":39 also states 'All four prose surfaces corrected in the same commit' -- three of the four carry the replacement false claim"
      ],
      "file": "docs/engineering-journal/LEARNINGS.md",
      "finding_id": "D06",
      "lens_id": "documentation-clarity",
      "line": 39,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Correct the Fix and Mechanism lines to state that the re-run appends one additional tick, and add a Validation line naming a test that pins it.",
      "title": "Journal entry records a fix that did not happen",
      "touched_paths": [
        "docs/engineering-journal/LEARNINGS.md"
      ],
      "why_it_matters": "The durable learning tells future maintainers the duplicate-tick remedy was the OLD defect and that the new path re-runs idempotently, so the surviving falsehood is now recorded as resolved and will not be re-found."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "conventions-portability-configuration",
      "evidence": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md:68 (validate), :78 (emit), :86 (spec_table.py) -- none honours SAGA_SPEC_ROOT, which plugins/cc-workflows/README.md:34 documents as rung 1",
        "this is cycle-1 finding F12's defect class, unrepaired on the new plugin's side of the seam; plugins/saga/skills/work/SKILL.md:352 shows the intended variable form"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/SKILL.md",
      "finding_id": "A08",
      "lens_id": "architecture-maintainability",
      "line": 68,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add SAGA_SPEC_ROOT=\"${SAGA_SPEC_ROOT:-plugins/saga}\" at the top of the Step 4 block and invoke \"$SAGA_SPEC_ROOT\"/scripts/execution_spec.py, repeating the assignment in each fenced block that uses it.",
      "title": "New plugin's own commands hardcode a repo-relative Saga path",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md"
      ],
      "why_it_matters": "The plugin documents SAGA_SPEC_ROOT and a four-rung resolver, then invokes Saga by a bare repo-relative path in the two steps Saga's reference now defers to, so an operator with the plugin installed from the marketplace rather than a repo checkout cannot run either step."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "separation-of-concerns",
      "evidence": [
        "emitter.py:41 imports it and :916 calls concurrency_governor.ordered_chunks; the module lives at plugins/saga/scripts/concurrency_governor.py and not in the plugin's own scripts directory",
        "plugins/cc-workflows/README.md:22-26 states the seam is the typed execution spec and names only execution_spec.py",
        "the import at :41 precedes _bind_substrate(_ES) at :151, so a foreign execution_spec in sys.modules yields a ModuleNotFoundError before the fail-loud check can report the real cause"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "A05",
      "lens_id": "architecture-maintainability",
      "line": 41,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Name concurrency_governor in the README's boundary section and in the DECISIONS seam entry, and move the import below the _bind_substrate(_ES) call so the actionable failure fires first.",
      "title": "A second Saga module is imported wholesale outside the declared seam",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The emitter imports concurrency_governor, which exists only under plugins/saga/scripts/, resolving purely by the sys.path side effect of the spec shim -- a whole-module cross-plugin dependency that the declared surface, the fail-loud bind, and the plugin's boundary documentation all omit."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "separation-of-concerns",
      "evidence": [
        "emitter.py:1348 calls _ES._agent_prompt(spec, retry_unit); _agent_prompt is absent from SUBSTRATE_SURFACE at :48-77",
        "lens mutation: renaming _agent_prompt throughout plugins/saga/scripts/execution_spec.py left tests/test_cc_workflows_emitter_surface.py at 3 passed, while tests/test_workflow_emitter.py went to 1 failed / 81 passed with AttributeError at emitter.py:1348; restored",
        "independently confirmed by the correctness lens and by controller static analysis: of the emitter's four _ES.<attr> accesses only _agent_prompt is undeclared, and the guard test walks only ast.Assign nodes inside _bind_substrate",
        "the DECISIONS entry claiming the private surface is 'declared in SUBSTRATE_SURFACE and pinned both ways' is therefore inaccurate"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "A04",
      "lens_id": "architecture-maintainability",
      "line": 1348,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add _agent_prompt to SUBSTRATE_SURFACE and bind it in _bind_substrate, and extend the guard's name collection to also read _ES.<name> attribute accesses across the whole module, not only assignments inside _bind_substrate.",
      "title": "A private Saga name crosses the boundary outside SUBSTRATE_SURFACE",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "_ES._agent_prompt is reached at the call site rather than through _bind_substrate, so the declared 29-name surface and its two-way guard do not cover it, and the exact failure the F10a repair claimed to close still ships."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "lens mutation: renaming def _agent_prompt( to def _agent_prompt_RENAMED( in plugins/saga/scripts/execution_spec.py:2199 left uv run pytest tests/test_cc_workflows_emitter_surface.py at 3 passed; mutation reverted",
        "lens proof: _bind_substrate(stub) with all 29 declared names set and no _agent_prompt SUCCEEDS",
        "controller static confirmation: the emitter's four _ES.<attr> accesses are _agent_prompt, _build_emission_routing_context, max_concurrent_agents, resolved_concurrency, and only _agent_prompt is absent from the 29-name tuple; the guard test at tests/test_cc_workflows_emitter_surface.py:45-61 walks only ast.Assign nodes inside _bind_substrate, so _ES.-qualified access is structurally invisible to it"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "C05",
      "lens_id": "correctness",
      "line": 1348,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add '_agent_prompt' to SUBSTRATE_SURFACE (making the private surface twelve, not eleven) and extend the guard's name collection to also walk _ES.<attr> accesses so qualified use is pinned too.",
      "title": "SUBSTRATE_SURFACE omits _agent_prompt, which the emitter calls",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The emitter calls _ES._agent_prompt on the escalate-on-signal retry path but never declares it in SUBSTRATE_SURFACE, so _bind_substrate binds happily against a substrate lacking it and the failure surfaces later as an AttributeError at emit time -- precisely the failure the guard's docstring says it prevents."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "the access is emitter.py:1348; the declared tuple at :48-77 does not contain it; the guard is at :103",
        "lens proof: a stub carrying every SUBSTRATE_SURFACE name and nothing else passed _bind_substrate with no error, leaving hasattr(_ES,'_agent_prompt') False",
        "tests/test_cc_workflows_emitter_surface.py:44-62 parses only ast.Assign nodes inside _bind_substrate, so no _ES.<attr> call site is reachable by it; the file reports 3 passed with the gap present",
        "independently confirmed by the correctness lens (rename mutation), the architecture lens, and controller static analysis"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "P03",
      "lens_id": "api-contract",
      "line": 1348,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add _agent_prompt to SUBSTRATE_SURFACE and bind it like the others, and extend the guard test's name collection to also walk ast.Attribute nodes whose value is Name(id='_ES').",
      "title": "Twelfth private name crosses the boundary undeclared",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The emitter calls _ES._agent_prompt on the unattended climb-retry emission path, but _agent_prompt is absent from SUBSTRATE_SURFACE, so the bind guard never tests for it and a substrate lacking it binds cleanly, then dies with an AttributeError at emit time."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "realistic-seams-mocks-integration-evidence",
      "evidence": [
        "the access is at emitter.py:1348; of the four parsed _ES.<attr> uses only _agent_prompt is missing from the 29-name tuple at :48-78",
        "lens mutation: renaming the definition in execution_spec.py left tests/test_cc_workflows_emitter_surface.py at 3 passed, 0 failed",
        "the guard IS armed for the names it parses: binding an undeclared name -> 1 failed; declaring an unbound name -> 2 failed; renaming a declared name -> 1 failed, 1 error",
        "repo-wide the same rename breaks 130 tests in the execution_spec suites, so the risk is a wrong declaration rather than an undetected break",
        "the comment at emitter.py:43-47 claiming the boundary cannot grow silently in either direction overstates what an assignments-only parse can see"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "T04",
      "lens_id": "testing",
      "line": 1348,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add _agent_prompt to SUBSTRATE_SURFACE and extend the guard's name collection to also walk ast.Attribute accesses on the _ES name, so qualified call sites count as boundary crossings.",
      "title": "SUBSTRATE_SURFACE under-declares the real plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "_agent_prompt crosses the plugin seam through a qualified _ES. call but is absent from the declared surface, so the list a reader trusts to describe the boundary is wrong."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "tests/test_plan_pre_answers.py:439-448 is the only prose check and it asserts the ABSENCE of rigid question shapes, never a parity claim",
        "a grep for the contract phrases across tests/ returns only assertions against the runtime stop string, never against the changelog, the spec, or the skill",
        "contrast tests/test_plan_artifact_conformance.py:324-349, which binds the shipped REQUIRED_FIELDS constant to the markdown declaration -- the lens mutation-proved it and restored"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "D07",
      "lens_id": "documentation-clarity",
      "line": 7,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a parity pin in the shape of test_required_field_set_is_pinned_to_both_declarations: parse the two-case schema sentence and the inline-only sentence from all three surfaces and bind them to SCHEMA_FAMILY and CARRIER_AUTO_APPLY_BACKENDS.",
      "title": "No test pins any carrier prose surface to the code",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "Three documents state one contract and none is bound to plan_pre_answers.py, which is exactly how the changelog kept two false claims through a repair that corrected the other two surfaces."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "specification-documentation-parity",
      "evidence": [
        "plugins/saga/CHANGELOG.md:9 against plan_pre_answers.py:260-273 -- a carrier with backend cc-workflows-ultracode returns a stop, not an apply",
        "plugins/saga/CHANGELOG.md:12 against plan_pre_answers.py:114-124 and :177 -- a carrier with schema other_tool.v9 returns stop=None, applied={}, ignored rather than refused",
        "the repair corrected both points in the other two surfaces (saga-spec.md:699-706 and plan/SKILL.md:154-163), which is why cycle-1 F07a is partial rather than not-fixed",
        "independently found by the controller before this lens returned"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "P08",
      "lens_id": "api-contract",
      "line": 9,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Rewrite the 0.150.0 bullet at CHANGELOG.md:8-14 to say inline and any valid destination are applied while team-execution and cc-workflows-ultracode stop and surface, and to state the two-case schema rule rather than a blanket whole-refusal.",
      "title": "Shipped 0.150.0 entry contradicts the carrier the code performs",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "The changelog is the surface an integrating caller reads first, and it states two things the code does not do -- that a supplied value is applied, and that an unknown schema token is refused whole -- while omitting the operator ruling that makes two of the three backend values stop."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "capability-parity-reachability",
      "evidence": [
        "plugins/saga/references/execution-spec.md:399-401 points at plugins/cc-workflows/skills/cc-workflows/SKILL.md Step 4",
        "the target at :65-69 gives the Saga command; the same command, differing only in runner, sits at plugins/saga/references/execution-spec.md:429",
        "the pointer path is repo-relative, so it does not resolve in an installed-plugin session"
      ],
      "file": "plugins/saga/references/execution-spec.md",
      "finding_id": "U07",
      "lens_id": "agent-usability",
      "line": 399,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Keep the cross-reference for rationale but restate the one-line validate command inline, and name the HALT when cc-workflows is not installed.",
      "title": "HARD BLOCK step points across plugins for Saga's own command",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ],
      "why_it_matters": "Step 2 of Saga's own flow is a hard block whose command is only in another plugin's SKILL file, with no fallback if cc-workflows is absent -- even though the command runs a Saga script that the same document already prints thirty lines further down."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "dependency-direction",
      "evidence": [
        "plugins/saga/references/execution-spec.md:400 cites cc-workflows SKILL.md Step 4 and :404 cites Step 5",
        "those steps at plugins/cc-workflows/skills/cc-workflows/SKILL.md:66 and :74 invoke plugins/saga/scripts/execution_spec.py and plugins/saga/scripts/spec_table.py -- both Saga scripts",
        "grep for 'Step 4'/'Step 5' across tests/*.py returns nothing, so no test binds the pointer; neither plugin manifest declares a dependency (carried finding F31)"
      ],
      "file": "plugins/saga/references/execution-spec.md",
      "finding_id": "A03",
      "lens_id": "architecture-maintainability",
      "line": 400,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Cite the step by its stable heading text rather than its number and add a literal-consistency pin in tests/test_workflow_extraction.py, the same shape as the readonly-verifier agent-type guard.",
      "title": "Saga's reference cites another plugin's step numbers, unpinned",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ],
      "why_it_matters": "Saga's own document now describes a Saga command-line tool by pointing at a positional step number in a file owned by a different plugin, with no drift pin and no declared dependency, so renumbering the other plugin's skill silently misdirects the reader."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "simplicity-abstraction-duplication-changeability",
      "evidence": [
        "the parenthetical claim at plugins/saga/references/execution-spec.md:401-402",
        "surviving copies at plugins/saga/references/execution-spec.md:429 and :432 under the CLI heading at :425, and at plugins/saga/commands/tier.md:48-49",
        "a fourth at plugins/cc-workflows/skills/cc-workflows/SKILL.md:68,78; a repo-wide grep returns three live command-pair sites, down from four at 5ec8ea76 -- not one"
      ],
      "file": "plugins/saga/references/execution-spec.md",
      "finding_id": "A02",
      "lens_id": "architecture-maintainability",
      "line": 401,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Either delete the parenthetical single-source claim, or make the CLI section and commands/tier.md point at the same place the flow steps now point at.",
      "title": "Single-source claim is false in its own file",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ],
      "why_it_matters": "The repair deleted one copy of the validate/emit command pair and wrote that the commands live with the capability, single source, but the same file still carries the pair 25 lines below and a third copy sits in a Saga command, so the deduplication did not happen."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "plugins/saga/references/saga-spec.md:671-675; grep for plan_artifact_conformance across plugins/saga/skills/ returned nothing",
        "lens runs: on docs/plans a JSON report and exit 0; on a nonexistent root a one-key JSON error and exit 2, against the docstring at plan_artifact_conformance.py:18-20",
        "the testing lens found the same absence of any caller outside the test"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "U08",
      "lens_id": "agent-usability",
      "line": 672,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a Phase 5-side step in plan/SKILL.md with the literal command and the three exit codes, and add the 2 case to the module docstring.",
      "title": "Conformance checker has no invocation prose and an undocumented exit 2",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "No shipped skill or reference tells an agent when or how to run the new conformance checker -- the spec only calls it runnable -- and its own docstring documents exits 0 and 1 while main also returns 2 for a bad root."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "saga-spec.md:699-702 and plan/SKILL.md:161-163 state the two-case rule as non-v1-inside-family versus foreign-family",
        "lens run: an uppercase version token gave exit 2 with 'refused whole: unrecognised schema token'",
        "mechanism: plan_pre_answers.py:124 lowercases for family membership while :207 compares the token exactly; the module docstring at :117-119 names this case correctly, neither shipped surface does",
        "independently found by the agent-usability lens"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "D08",
      "lens_id": "documentation-clarity",
      "line": 700,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "State it on both surfaces -- the token itself is matched exactly, so any casing other than the canonical token is inside the family and refused whole.",
      "title": "Case-differing v1 token is refused but prose says only non-v1 is",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "Both shipped surfaces say family matching is case-insensitive and that only a non-v1 token is refused, so a caller writing an uppercase version token expects it applied and instead gets a stop calling its own version token unrecognised."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "state-data-invariants-transactions-concurrency",
      "evidence": [
        "plan_artifact_conformance.py:79-85 and the classification at line 104",
        "lens execution: check_document on a document declaring backend: inline plus an unclosed 'tags: [a, b' produced legacy-no-backend | legacy=True | failing=False | 'no backend: -- legacy document', and corpus_exit returned 0"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "C06",
      "lens_id": "correctness",
      "line": 79,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Distinguish the two cases -- emit a failing unparseable-frontmatter finding when yaml.safe_load raises, instead of collapsing it into the legacy bucket.",
      "title": "Broken YAML reclassifies a new-contract plan as legacy",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "split_frontmatter swallows a yaml.YAMLError and returns empty fields, so a plan document that does declare backend: inline but has any YAML syntax error is classified legacy-no-backend, reported non-failing, and passes the gate -- violating the module's own rule that legacy is the absence of backend and nothing else."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "lens mutation: 'if value not in BACKEND_ENUM:' -> 'if False:' at plan_artifact_conformance.py:122 left 11 passed, 0 failed",
        "KIND_BACKEND_NOT_IN_ENUM appears in the test file only at tests/test_plan_artifact_conformance.py:201 as a negative assertion",
        "control mutations DO go red: dropping backend from REQUIRED_FIELDS -> 1 failed; emptying the loop -> 1 failed; deleting the marker half -> 4 failed; rglob -> glob -> 2 failed"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "T02",
      "lens_id": "testing",
      "line": 122,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a tmp_path fixture whose frontmatter carries an out-of-enum backend value and assert a KIND_BACKEND_NOT_IN_ENUM finding with corpus_exit == 1.",
      "title": "Backend-enum rule in the shipped check has no positive test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "The U1 contract's backend enum can be silently stopped enforcing and nothing goes red, because no fixture ever carries an out-of-enum backend value."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "significant-decision-documentation",
      "evidence": [
        "plan_pre_answers.py:45 reads 'Pure functions: reads the text it is given, writes nothing, reads no file (KTD5)'; :327-328 reads args.invocation_file.read_text(encoding='utf-8')",
        "plugins/saga/references/saga-spec.md:720-721 repeats 'runnable; reads the text it is given, writes nothing, reads no file'; plugins/saga/skills/plan/SKILL.md:142 documents the file-reading invocation"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "A09",
      "lens_id": "architecture-maintainability",
      "line": 45,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Change both sentences to 'the evaluation functions are pure; the command line reads only the invocation file it is given and writes nothing', mirroring the wording already applied to the emitter docstring.",
      "title": "Validator docstring claims no file reads while the new CLI reads one",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The F04 repair added a --invocation-file entry point but left the 'reads no file' purity claim standing in both the module docstring and the spec, reintroducing exactly the defect class cycle-1 F19 raised against the emitter and that the same commit fixed there."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:161 against :123-124 and the module docstring's own principle at :42-43",
        "lens run: evaluate on an uppercase-JSON-fenced valid carrier returned applied {} omitted ('backend','destination') caller None stop None, byte-identical to the no-fence result",
        "the fence tests at tests/test_plan_pre_answers.py:302-315 cover a yaml fence and an info-less fence, never a case variant of json"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "P07",
      "lens_id": "api-contract",
      "line": 161,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Either lowercase the info string before comparison at line 161, or keep the strict match and stop when a non-json fence contains a parseable object declaring the plan_pre_answers family.",
      "title": "A well-formed carrier in a JSON fence vanishes without a stop",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The fence info string is compared case-sensitively while the schema token is matched case-insensitively for the express purpose of catching near-misses loudly, so a caller writing an uppercase JSON fence has a fully valid settled decision discarded with an outcome field-for-field identical to no carrier."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "confidentiality-logs-errors-egress",
      "evidence": [
        "plan_pre_answers.py:220 joins unknown keys with an f-string and never calls _echo; :167 interpolates the joined duplicate key names from :103",
        "lens measurement: one 50,000-character unknown key produced a 50,162-character stop string; 2,000 unknown keys produced 18,159; 1,000 duplicate keys produced 7,087; the _echo-guarded paths measured 154-209",
        "the comment at :86-88 claims a refusal message can never be inflated by unbounded input; tests/test_plan_pre_answers.py:361 asserts that only for the schema-token path"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "S02",
      "lens_id": "security",
      "line": 220,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Route both through _echo -- ', '.join(_echo(key) for key in unknown) at :220 and _echo(str(exc)) at :167 -- and extend test_refusal_messages_echo_bounded_values_only to cover all four refusal paths.",
      "title": "Two refusal paths echo caller key names raw and unbounded",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The unknown-key listing and the duplicate-key stop interpolate caller-supplied key names directly with f-strings, bypassing _echo, so a refusal message Plan is instructed to reproduce verbatim can be arbitrarily long and can carry unescaped newlines and fence delimiters -- the defect _ECHO_LIMIT was added to close."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:328 reads the file unguarded, against plugins/saga/skills/plan/SKILL.md:145-146",
        "lens run: --invocation-file /nope/missing.txt gave FileNotFoundError and exit 1",
        "plan_artifact_conformance.py:102 reads unguarded while its docstring at 18-19 declares 0 or 1; a scratch root holding one file with a 0xff byte gave UnicodeDecodeError, exit 1, no stdout",
        "that same main() already models the correct shape one branch earlier -- a missing root prints a one-key JSON error and exits 2, which the docstring also fails to mention"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "P05",
      "lens_id": "api-contract",
      "line": 328,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Wrap the file read in plan_pre_answers.main and the per-document read in check_document so an unreadable path emits the same one-key JSON error object and exit 2 the conformance script already uses for a bad root, and add exit 2 to both docstrings.",
      "title": "Both new entry points exit outside their documented contract",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The carrier validator's shipped contract is exactly two codes, yet an unreadable --invocation-file exits 1 with a raw traceback and no JSON; the conformance script crashes on a non-UTF-8 document with exit 1, the same code its docstring reserves for a real conformance failure, so a consumer cannot tell a failure from a crash."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "plan_pre_answers.py:316-331 exposes only --invocation-file, confirmed with --help",
        "against plugins/saga/references/saga-spec.md:726-728 and plugins/saga/skills/plan/SKILL.md:157-159",
        "controller check: the established parameter has no producer anywhere in the repository outside tests/test_plan_pre_answers.py"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "C04",
      "lens_id": "correctness",
      "line": 331,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add --established backend=<v>,destination=<v> (or a JSON file) and pass it into evaluate, or narrow both documents to say the contradiction check is a caller-side responsibility the command line does not perform.",
      "title": "Runnable validator cannot produce the documented conflict stop",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "main calls evaluate(text) with no established mapping and the parser exposes no flag for one, so the contradiction stop that both saga-spec.md rule 3 and Plan Phase 0.7 promise can never be emitted by the entry point the prose tells the agent to run."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:332-343",
        "lens round-trip: the exact stdout document, re-fenced as json and fed back to evaluate, returned 'pre-answer carrier refused: applied, omitted, stop are not admitted'",
        "the only prose describing the output is plugins/saga/skills/plan/SKILL.md:145 ('It prints the outcome as JSON'), which names no field"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "P06",
      "lens_id": "api-contract",
      "line": 335,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Emit a distinct token for the report -- plan_pre_answers_outcome.v1 -- and document its four fields in plugins/saga/references/saga-spec.md section 15 beside the carrier shape.",
      "title": "Validator report is labelled with the carrier's schema token",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "main stamps its outcome document with schema plan_pre_answers.v1 although the document's shape is applied/omitted/stop/caller, so one version token names two incompatible objects, and the report is refused by the very evaluator that emitted it; no shipped surface documents the report shape at all."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "saga.py:852 and :857-859",
        "lens check: constructing the class from str(OSError(ENOSPC, ...)) yields errno None, strerror None, filename None while str() still reads the full message",
        "the repository's existing convention that depends on those fields is plugins/saga/scripts/fleet_doctor.py:81-88",
        "no current caller of saga.save() inspects errno -- the only production caller is scaffold_checkpoint.py:91 -- so nothing breaks today; the contract does"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "P04",
      "lens_id": "api-contract",
      "line": 852,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "raise SagaTickEnvelopeWriteError(exc.errno, exc.strerror, exc.filename) from exc, and for the index variant set errno and filename from the cause after constructing it with the annotated message.",
      "title": "New OSError subclasses carry no errno, strerror, or filename",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "Both new exceptions are constructed from a formatted string, so errno, strerror and filename are all None on the raised object; a handler that branches on exc.errno -- the standard machine-actionable contract, and the shape this repository's own _safe_oserror reads -- silently takes the None path."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "saga.py:1685-1690 emits the sentence; _allocate_envelope_path at saga.py:660-670 always picks a fresh name",
        "lens measurement in a scratch repo: pre-created .claude/saga/state.json.tmp as a directory, ran saga.py save -> rc 2 with that message and one envelope 20260830-221521.md; removed the blocker, re-ran the identical command -> rc 0 and envelopes ['20260830-221521.md','20260830-221529.md']; saga.py ticks then reported 2 ticks with identical content",
        "the new test tests/test_saga_plan_save_and_routing.py:158-213 never re-runs the save, so the claim is unpinned"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "C01",
      "lens_id": "correctness",
      "line": 1690,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Drop 'the re-run is idempotent and appends no duplicate tick' -- say the re-run rebuilds the index and appends a second, identical tick, harmless to restore but visible to saga.py ticks.",
      "title": "Index-failure remedy falsely promises no duplicate tick",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The index-only error tells the operator the re-run is idempotent and appends no duplicate tick, but re-running the same save allocates a second envelope, so the tick chain /resume replays gains a duplicate -- the repair swapped one false durable-state claim for another."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "saga.py:1694-1703",
        "lens measurement: first save wrote tick 20260830-221601.md with plan_path docs/plans/p.md; chmod 500 on the saga dir made the next envelope write fail -> rc 2 and 'the plan document docs/plans/p.md now has NO saga tick referencing it', while saga.py ticks still returned 1 tick carrying that same plan_path",
        "the guarding test at tests/test_saga_plan_save_and_routing.py:108-154 only asserts restore(...) is None, i.e. the first-tick case"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "C02",
      "lens_id": "correctness",
      "line": 1701,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Condition the stranded sentence on latest_envelope_for(root, saga_id) being absent, exactly as cycle-1 F05's suggested fix stated; otherwise say the newest tick failed and the prior tick still references the document.",
      "title": "Envelope-failure branch claims no tick when prior ticks exist",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The envelope-write branch says the plan document now has NO saga tick referencing it unconditionally, but a saga whose earlier ticks already record the same plan_path still references it, so the operator is told the document is stranded when it is not -- the exact cycle-1 F05 defect, left standing on the sibling branch."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "saga.py:1705-1714; the reachable read is restore(root, saga.saga_id) at :798, inside the try at :1671",
        "lens reproduction: chmod 000 on the existing envelope then saga.py save -> 'error: failed to write the saga tick: [Errno 13] Permission denied ... check whether a tick envelope was written ... (saga.py restore)', exit 2; running the prescribed saga.py restore on the same tree gave a bare PermissionError traceback, exit 1"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "A06",
      "lens_id": "architecture-maintainability",
      "line": 1705,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Reword the fallback to 'failed during the saga save' and drop the saga.py restore prescription, or wrap restore() in its own named error so the read case is diagnosed separately.",
      "title": "Generic OSError branch misattributes a read failure as a write",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The new fallback is reachable via restore() reading the prior tick, but it prints 'failed to write the saga tick' when nothing was written, and prescribes saga.py restore -- a command that fails with the same error."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "architectural-fit-ownership-single-sources",
      "evidence": [
        "pin at tests/test_plan_artifact_conformance.py:324-349 parses only the plan-sections.md:185 bullet plus a single sentence at plan/SKILL.md:265; the template is at plugins/saga/skills/plan/SKILL.md:253-262",
        "lens mutation: deleting the 'status: active' line from the template left uv run pytest tests/test_plan_artifact_conformance.py at 11 passed; restored",
        "by contrast the backend enum IS pinned -- dropping team-execution from plan_artifact_conformance.py:45 gave 1 failed, 36 passed"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "A07",
      "lens_id": "architecture-maintainability",
      "line": 253,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Extend test_required_field_set_is_pinned_to_both_declarations to parse the YAML frontmatter block in plan/SKILL.md and assert its keys are a superset of REQUIRED_FIELDS.",
      "title": "Required-field pin misses the template agents actually copy",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The drift pin binds REQUIRED_FIELDS to the prose bullet in plan-sections.md but not to the YAML frontmatter template in plan/SKILL.md, so dropping a required key from the template an authoring agent copies leaves the whole conformance suite green and every new plan failing the shipped check."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "capability-parity-reachability",
      "evidence": [
        "plugins/saga/skills/work/SKILL.md:350-352 against the ladder at plugins/saga/scripts/execution_spec.py:2413-2469",
        "the lens read both resolution paths and did not test an installed-plugin session"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "U02",
      "lens_id": "agent-usability",
      "line": 350,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Drop the parity claim and say the fallback assumes the working directory is a checkout of this repository; otherwise set CC_WORKFLOWS_SCRIPTS_DIR first.",
      "title": "Shell comment claims resolution parity the shell does not have",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "The comment says the shell resolves the scripts directory the same way the Python seam does, but the Python seam has four rungs and the shell has two, so outside a checkout of this repository the shell falls back to a working-directory-relative path that does not exist while Python would resolve."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "the scan at tests/test_workflow_extraction.py:223 was narrowed from markdown plus both scripts directories to plugins/**/*.py only",
        "lens mutation: a nonexistent docs/workflows pointer added to a plugin markdown file left 12 passed; the same string in emitter.py gave 1 failed",
        "lens necessity check: re-running the pre-narrowing scan over plugins/**/*.md today yields exactly one dangling hit, docs/workflows/2026-06-02-saga-foundation-spec.json at plugins/saga/references/saga-spec.md:234, which this change rewrote from a docs/plans path; neither prefix ever named a file that exists",
        "independently confirmed by the controller: the same single dangling pointer, and the file never existed anywhere in repository history"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "T03",
      "lens_id": "testing",
      "line": 223,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Keep markdown in the scan and exempt the illustrative envelope by name, or point the worked example at an artifact that exists under docs/workflows/.",
      "title": "Guard narrowed to Python leaves markdown pointers unresolved",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "A dangling docs/workflows pointer in live plugin markdown is now caught by nothing, and the narrowing was forced by a dangling pointer this very change created."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "terminology-cross-document-consistency",
      "evidence": [
        "docs/engineering-journal/DECISIONS.md:17; a repository grep finds the code only there, at tests/test_workflow_extraction.py:160, in the plan at :619 which uses it without defining it, and inside the cycle-1 review artifacts",
        "plugins/saga/skills/plan/SKILL.md is now clean, so cycle-1 finding F41 is fixed at its cited site and the code simply moved"
      ],
      "file": "docs/engineering-journal/DECISIONS.md",
      "finding_id": "D09",
      "lens_id": "documentation-clarity",
      "line": 17,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Expand on first use in both the journal entry and the test comment.",
      "title": "Undefined code P-D3 migrated from skill prose into the journal",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ],
      "why_it_matters": "The code is expanded nowhere in the repository, so a maintainer reading the decision entry cannot learn which settled decision the extraction served."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "dependency-supply-chain",
      "evidence": [
        "saga_spec_shim.py:135-138 checks sys.modules.get('execution_spec') and returns before resolve_root()",
        "lens reproduction: with SAGA_SPEC_ROOT=/definitely/not/a/root and a stub pre-registered under execution_spec, load_execution_spec() returned the stub with no exception, while resolve_root() on the same env raised",
        "the saga-driven path is protected by the rebind at plugins/saga/scripts/execution_spec.py:2502"
      ],
      "file": "plugins/cc-workflows/README.md",
      "finding_id": "S04",
      "lens_id": "security",
      "line": 34,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add one sentence to the README's Resolution and overrides section naming the sys.modules['execution_spec'] reuse as the step above rung 1 and stating it takes precedence over SAGA_SPEC_ROOT; the shim docstring at :9-19 needs the same line.",
      "title": "Documented ladder omits the sys.modules short-circuit above rung 1",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ],
      "why_it_matters": "load_execution_spec returns whatever is registered under the bare name execution_spec before consulting the ladder, so the README's rung-1 promise that an invalid SAGA_SPEC_ROOT raises rather than falls through does not hold on the cached path."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "dependency-direction",
      "evidence": [
        "plugins/saga/scripts/execution_spec.py:3096 versus the cache check at saga_spec_shim.py:135, whose docstring at :130-133 claims the spec classes in play are always one set",
        "lens reproduction: SAGA_SPEC_DEBUG=1 on a real emit printed 'cc-workflows: saga-spec rung=2 (repo-walk-up)'; a run_path probe then reported execution_spec registered separately",
        "emission stays correct only because the delegation re-binds via _bind_substrate(owner)"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py",
      "finding_id": "A10",
      "lens_id": "architecture-maintainability",
      "line": 130,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Have load_execution_spec() also accept sys.modules['__main__'] when it exposes the substrate names, or have execution_spec.main() register itself under sys.modules.setdefault('execution_spec', _SELF_MODULE) before delegating.",
      "title": "Documented command line loads and executes execution_spec twice",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ],
      "why_it_matters": "_SELF_MODULE is captured under __main__ when the module runs as the documented command line, but the shim only looks for sys.modules['execution_spec'], so a second full copy of the 3099-line module is resolved and executed on every emit, contradicting the shim's own 'always one set' guarantee."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "plugins/saga/CHANGELOG.md:11-12 versus the repaired two-case wording at plugins/saga/skills/plan/SKILL.md:161-163",
        "lens run: a carrier declaring a foreign family returned applied {}, stop null, exit 0",
        "independently found by the controller and the api-contract lens"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "U11",
      "lens_id": "agent-usability",
      "line": 11,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Mirror the two-case sentence into the changelog entry.",
      "title": "Release note keeps the blanket unknown-schema claim the code refutes",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "The 0.150.0 entry still says a carrier declaring an unknown schema token is refused whole, which the skill and spec were repaired to split into two cases, so a caller agent reading the release surface expects a loud refusal where a foreign family is silently ignored."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "completeness-audience-prerequisites",
      "evidence": [
        "plugins/saga/CHANGELOG.md:29-30; the lens counted 11 non-plan entries including two decision briefs and the ideation subtree",
        "running the shipped conformance check reports these as legacy and non-failing",
        "the parallel journal entry at docs/engineering-journal/DECISIONS.md:15 is accurate -- it says the directory retains plan documents and the ideation subtree"
      ],
      "file": "plugins/saga/CHANGELOG.md",
      "finding_id": "D10",
      "lens_id": "documentation-clarity",
      "line": 29,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Match the journal wording: docs/plans no longer holds generated artifacts and retains plan documents plus the ideation subtree.",
      "title": "Changelog says docs/plans is reserved for plan documents",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ],
      "why_it_matters": "Eleven non-plan entries remain in that directory, so a reader acting on the sentence would treat surviving briefs and the ideation subtree as misfiled."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "authentication-authorization-tenant-isolation",
      "evidence": [
        "plugins/saga/references/operator-choice.md:59 'ALWAYS surface the Saga choice' against the new parenthetical at plugins/saga/skills/plan/SKILL.md:336-338",
        "grep for pre_answers/pre-answer across plugins/saga/references/*.md returns hits only in saga-spec.md",
        "the privilege direction is downward -- the suppressed offer resolves to the cheapest backend -- so this is contract consistency, not escalation"
      ],
      "file": "plugins/saga/references/operator-choice.md",
      "finding_id": "S06",
      "lens_id": "security",
      "line": 59,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add one bullet to operator-choice.md section 2 naming the Phase 0.7 carrier as the single exception to the ALWAYS-surface rule, scoped to backend: inline, cross-referencing saga-spec.md section 15.",
      "title": "Carrier exception to the ALWAYS-surface rule is undocumented",
      "touched_paths": [
        "plugins/saga/references/operator-choice.md"
      ],
      "why_it_matters": "operator-choice.md is the authority Plan Phase 5.2 defers to and it states the backend offer is ALWAYS surfaced, but Plan now skips that offer when a carrier applied backend: inline, and the decision contract carries no mention of the carrier."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "plugins/saga/references/saga-spec.md:699-701 and plan_pre_answers.py:114-124 against :207",
        "lens run: a carrier declaring an uppercase family token returned 'refused whole: unrecognised schema token', exit 2"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "U10",
      "lens_id": "agent-usability",
      "line": 699,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "State that the version token is compared exactly; only family membership is case-insensitive.",
      "title": "Family match is case-insensitive but the token check is not",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "The contract tells a carrier-authoring agent the schema family is matched case-insensitively, so it predicts an uppercase v1 token is applied; the code compares the token case-sensitively and refuses the whole carrier."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "dependency-direction",
      "evidence": [
        "the 'Emission substrate retained by Saga' banner at plugins/saga/scripts/execution_spec.py:2156 covers only _js_var (:2161) and _unit_script_symbols (:2173)",
        "the other nine declared private names are scattered outside it, at :352, :434, :1229, :1240, :1676, :1718, :1725, :1922, :2650; execution_spec.py declares no __all__"
      ],
      "file": "plugins/saga/scripts/execution_spec.py",
      "finding_id": "A11",
      "lens_id": "architecture-maintainability",
      "line": 1676,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a one-line '# cc-workflows SUBSTRATE_SURFACE' comment above each of the nine definitions, or gather them under the existing banner.",
      "title": "Producer carries no marker for nine of eleven bound private names",
      "touched_paths": [
        "plugins/saga/scripts/execution_spec.py"
      ],
      "why_it_matters": "The declared surface lives only in the consuming plugin, so a Saga maintainer refactoring an underscore-prefixed name sees no local signal that another plugin binds it, and the pin that would catch it is a repo test that does not exist for an installed plugin pair."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "boundary-types-serialization-numeric-time",
      "evidence": [
        "plan_artifact_conformance.py:121-130",
        "lens execution: check_document on frontmatter carrying a bare 'backend:' line produced both missing-required-field and 'backend: None is not one of inline | team-execution | cc-workflows-ultracode'"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "C12",
      "lens_id": "correctness",
      "line": 121,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Use str(fields.get('backend') or '') and skip the enum finding when the required-field finding already fired for backend.",
      "title": "Empty backend field reported as the Python literal None",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "str(fields.get('backend','')) returns 'None' when the key is present with a null value, so the operator is told 'backend: None is not one of ...' rather than that the field is empty, and the same document also produces a redundant missing-required-field finding."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "grep across scripts/ and .github/ returns nothing; no skill file carries a runnable command block for it, only prose mentions at plugins/saga/references/saga-spec.md:672-673",
        "contrast the sibling repair: plugins/saga/skills/plan/SKILL.md:142 gives plan_pre_answers.py an explicit runnable command block",
        "the only executor is the subprocess at tests/test_plan_artifact_conformance.py:101-118"
      ],
      "file": "plugins/saga/scripts/plan_artifact_conformance.py",
      "finding_id": "T06",
      "lens_id": "testing",
      "line": 163,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Either add a gate step in scripts/gate.sh running the conformance check over docs/plans, or give Plan Phase 5.3 a runnable command block the way Phase 0.7 has one.",
      "title": "Shipped conformance check has no caller outside its test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ],
      "why_it_matters": "Cycle-1 F06t made the check callable but nothing calls it, so the contract is still enforced only when pytest runs -- the condition F06t was filed against."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "boundary-types-serialization-numeric-time",
      "evidence": [
        "plan_pre_answers.py:84 and :160-161",
        "lens execution: a stray inline triple backtick followed by a well-formed json carrier returned applied={} stop=None, whereas the identical carrier alone returned applied={'backend':'inline'}; a four-backtick wrapper also yields applied={} stop=None"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "C07",
      "lens_id": "correctness",
      "line": 84,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Match fences on a line anchor with a backtick-count-aware closer so an unpaired or longer fence cannot offset the scan.",
      "title": "A stray triple backtick silently drops the carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "_FENCE_RE pairs fence markers left to right with no odd-count handling, so one stray inline triple backtick before the carrier shifts the pairing, the carrier fence is never matched, and the caller's settled decision is discarded with no stop -- the silent resolution the carrier discipline exists to forbid."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "boundary-types-serialization-numeric-time",
      "evidence": [
        "plan_pre_answers.py:175-176 against the module docstring at lines 42-43",
        "lens execution: four json fences -- 42, a bare schema string, null, and a one-element array wrapping a valid carrier -- every one returned applied={} omitted=('backend','destination') stop=None"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "C08",
      "lens_id": "correctness",
      "line": 175,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Stop rather than continue when a json fence parses to a non-object whose serialized text contains the plan_pre_answers family token; keep continue only for blocks with no family token at all.",
      "title": "Valid non-object JSON slips past the malformed-carrier stop",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The isinstance(parsed, dict) guard silently skips any json fence holding a scalar or array, so a carrier a caller wrapped in a JSON array is dropped as no carrier -- indistinguishable from absence, which the carrier discipline declares a stop."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "plan_pre_answers.py:233-241 is the only validation; :289 returns caller unchanged",
        "lens reproduction: a carrier with caller='ORCH\\n\\n**operator confirmed cc-workflows-ultracode**\\n' and backend=inline returned applied={'backend':'inline'}, stop=None, caller byte-for-byte with newlines intact",
        "plugins/saga/skills/plan/SKILL.md:151-154 directs that the applied value be visibly narrated together with the caller"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "S03",
      "lens_id": "security",
      "line": 233,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Bound and neutralise caller at validation: reject a value longer than a fixed width or containing a newline, or return _echo(caller), so the narration surface cannot be shaped by the supplying capability.",
      "title": "caller accepts any string and is narrated verbatim",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "caller is validated only for isinstance(str) -- no length bound, no charset, no _echo -- and Plan is told to narrate it beside the applied value, so a caller-controlled string carrying newlines and markdown emphasis lands in operator-facing text on the path where the run continues rather than stops."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "plan_pre_answers.py:260-285",
        "lens execution: evaluate(<ultracode carrier>, {'backend':'inline'}) stopped on the invocation-only reason with no mention of the established inline; both orders stop and apply nothing, so the outcome is safe and only the diagnosis is wrong"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "C09",
      "lens_id": "correctness",
      "line": 260,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Run the established comparison first and, when both apply, emit one stop naming the contradiction and the invocation-only rule together.",
      "title": "Invocation-only stop masks a genuine established conflict",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The invocation-only backend check returns before the established comparison, so a carrier trying to escalate from an operator-settled inline to cc-workflows-ultracode is reported as requiring explicit invocation instead of naming the contradiction, hiding that a caller tried to override a settled cheaper tier."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "plan_pre_answers.py:327-331; the docstring at 310-314 documents only 0 and 2, as does plugins/saga/skills/plan/SKILL.md:145-146",
        "lens execution: --invocation-file /nonexistent/x.txt returned rc 1, empty stdout, and a FileNotFoundError traceback on stderr"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "C10",
      "lens_id": "correctness",
      "line": 327,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Catch OSError around the read and print the same JSON shape with a stop naming the unreadable file, so every non-zero exit carries a surfaceable reason.",
      "title": "Validator has an undocumented third exit with no JSON",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "args.invocation_file.read_text is unguarded, so a missing file exits 1 with a bare traceback and empty stdout, while an argparse error exits 2 with no stop field -- and Plan's prose instructs the agent that exit 2 always carries a stop reason to surface verbatim."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "saga.py:852 and :857-859",
        "lens probe: the wrapped exception reported errno None and filename None while the original carried errno 28 and its path; isinstance(wrapped, OSError) was True",
        "no current caller inspects .errno on a save, and plugins/saga/scripts/scaffold_checkpoint.py:91 calls save() with no except at all"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "A12",
      "lens_id": "architecture-maintainability",
      "line": 852,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Construct as SagaTickEnvelopeWriteError(exc.errno, str(exc), exc.filename) and give both classes a shared SagaTickWriteError(OSError) base so a caller can catch either without naming both.",
      "title": "Re-raised tick errors drop errno and filename",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "Both new classes are constructed with a single string argument, so errno and filename come back None on the raised exception and any future caller distinguishing a full disk from a permission failure sees nothing; isinstance(exc, OSError) still holds, so existing catchers are unaffected."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "intent-behavior-completeness",
      "evidence": [
        "git diff bbac725a 76533cbe removes the sentence 'If recommended is cc-workflows-ultracode, do not pre-select it -- pre-select team-execution when a gated size/risk/consensus trigger fired, otherwise inline'",
        "the guard 'Never pre-select cc-workflows-ultracode. Never launch a Workflow because recommend_execution_backend() returned it.' survives at plugins/saga/skills/plan/SKILL.md:345-346, and line 350-351 still says to recommend only inline or team-execution",
        "the deletion came from 5ec8ea76, not the repair commit"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "C11",
      "lens_id": "correctness",
      "line": 351,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Operator call -- restore the deleted fallback sentence, or record that the surviving prohibition is deliberately the whole rule now.",
      "title": "Phase 5.2 lost the explicit ultracode pre-select fallback",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The change deleted Plan's normal-offer instruction for what to pre-select when the recommender returns cc-workflows-ultracode, which the operator ruling placed out of scope; the prohibition survives so behaviour is intact, but the ruling's scope boundary was crossed."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "four unquoted uses at plugins/saga/skills/work/SKILL.md:359, 361, 429, 437 beside quoted neighbours",
        "lens reproduction: D='/tmp/a b/scripts'; python3 $D/workflow_emitter.py reserve x -> can't open file '/tmp/a'",
        "lens reproduction: the semicolon case produced literal argv [x;] [echo] [PWNED/workflow_emitter.py] -- bash does not re-parse control operators after expansion, so this is loud breakage, NOT command injection"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "S05",
      "lens_id": "security",
      "line": 359,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Quote all four: python3 \"$CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py\".",
      "title": "Unquoted script-dir variable in four copy-and-run command lines",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "python3 $CC_WORKFLOWS_SCRIPTS_DIR/workflow_emitter.py word-splits and glob-expands, so a resolved path containing a space or a glob character makes the agent run a command that fails on a truncated path, and every other expansion in the same block is quoted."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "determinism-isolation-diagnostics-maintainability",
      "evidence": [
        "the assertion at tests/test_plan_pre_answers.py:432 reads plan_artifact_conformance.py as text at :429-431",
        "the same file already imports the module properly for every other assertion, and tests/test_plan_artifact_conformance.py:75 binds BACKEND_ENUM from the module"
      ],
      "file": "tests/test_plan_pre_answers.py",
      "finding_id": "T07",
      "lens_id": "testing",
      "line": 432,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Load the module and assert conformance.BACKEND_ENUM == pre_answers.BACKEND_ENUM.",
      "title": "Drift pin matches shipped source text instead of importing",
      "touched_paths": [
        "tests/test_plan_pre_answers.py"
      ],
      "why_it_matters": "A formatter reflow or a reordering of the enum tuple breaks the pin without any contract changing, and a semantically equivalent redefinition slips past it."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "assert len(specs) >= 18 at tests/test_wave_file_conflicts.py:187, immediately under a glob this change rewrote from docs/plans/ to docs/workflows/",
        "lens scan of the seven touched test files found this as the only pinned corpus integer; named-path pins remain at tests/test_plan_artifact_conformance.py:272 and tests/test_workflow_extraction.py:215"
      ],
      "file": "tests/test_wave_file_conflicts.py",
      "finding_id": "T08",
      "lens_id": "testing",
      "line": 187,
      "owner": "downstream-resolver",
      "pre_existing": true,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Drop the floor and assert the relation only -- every spec in the glob has zero wave conflicts -- since an empty glob is already caught by the population assertions in test_artifacts_moved_and_plans_directory_retained.",
      "title": "Corpus integer survives the re-anchored conflict sentinel",
      "touched_paths": [
        "tests/test_wave_file_conflicts.py"
      ],
      "why_it_matters": "Contract obligation 7 and the plan's own requirement R33 forbid a pinned corpus count, and this change re-anchored the glob under the floor without retiring it."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "lens per-file mutation: corrupting the sentence in plan/SKILL.md, operator-choice.md and execution-strategy.md each gave 1 failed, but work/SKILL.md alone stayed green because that file carries both 'never pre-select' (:53) and 'do not pre-select' (:275); only corrupting both turns it red",
        "the counterfactual half is fully armed for all four files: the merge-base branch restored verbatim, plus artificially wrapped variants, failed 8 times out of 8"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "T05",
      "lens_id": "testing",
      "line": 107,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Require the sentence in the same clause as the backend it governs, asserting a collapsed-text regex binding the pre-select prohibition to cc-workflows-ultracode.",
      "title": "Never-pre-select guard is file-level, not sentence-level",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "Corrupting the sentence the test is named for in work/SKILL.md leaves the test green, because an unrelated phrase elsewhere in the same file satisfies the substring check."
    }
  ],
  "fix_requests": [
    {
      "autofix_class": "manual",
      "finding_ids": [
        "T06"
      ],
      "fix_id": "fix-8f87c9f3fa94",
      "owner": "human",
      "requires_verification": false,
      "summary": "Shipped conformance check has no caller outside its test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "D06"
      ],
      "fix_id": "fix-c77192119e7b",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Journal entry records a fix that did not happen",
      "touched_paths": [
        "docs/engineering-journal/LEARNINGS.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "A08"
      ],
      "fix_id": "fix-a34ff0c91932",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "New plugin's own commands hardcode a repo-relative Saga path",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "A04",
        "A05",
        "P03",
        "T04"
      ],
      "fix_id": "fix-35e0c83d365a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "A private Saga name crosses the boundary outside SUBSTRATE_SURFACE; A second Saga module is imported wholesale outside the declared seam; Twelfth private name crosses the boundary undeclared; SUBSTRATE_SURFACE under-declares the real plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "A10"
      ],
      "fix_id": "fix-222ac29adc40",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Documented command line loads and executes execution_spec twice",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "D01",
        "D02",
        "D07",
        "P08"
      ],
      "fix_id": "fix-9a088bef2da2",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Changelog still says unknown schema token is refused whole; Changelog claims any supplied value is applied and narrated; No test pins any carrier prose surface to the code; Shipped 0.150.0 entry contradicts the carrier the code performs",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "A02",
        "A03"
      ],
      "fix_id": "fix-8e3aec8e83c2",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Single-source claim is false in its own file; Saga's reference cites another plugin's step numbers, unpinned",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "D08"
      ],
      "fix_id": "fix-f0a36e7e26f8",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Case-differing v1 token is refused but prose says only non-v1 is",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "C06"
      ],
      "fix_id": "fix-a69fd443ef72",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Broken YAML reclassifies a new-contract plan as legacy",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "C03",
        "C04",
        "C07",
        "C08",
        "C09",
        "P02",
        "P05",
        "P06",
        "P07",
        "S01",
        "U04"
      ],
      "fix_id": "fix-c1ecbf4f719a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Any unrelated malformed json fence halts the Plan run; Runnable validator cannot produce the documented conflict stop; A stray triple backtick silently drops the carrier; Valid non-object JSON slips past the malformed-carrier stop; Invocation-only stop masks a genuine established conflict; Any unparseable json fence halts /plan with no carrier present; Both new entry points exit outside their documented contract; Validator report is labelled with the carrier's schema token; A well-formed carrier in a JSON fence vanishes without a stop; Any unparseable json fence halts Plan and suppresses a carrier; Contradiction rule unreachable through the runnable entry point",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "A06",
        "C01",
        "C02",
        "D03",
        "D04",
        "P01"
      ],
      "fix_id": "fix-9818846b9df7",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Generic OSError branch misattributes a read failure as a write; Index-failure remedy falsely promises no duplicate tick; Envelope-failure branch claims no tick when prior ticks exist; Index-failure recovery step falsely claims idempotence; Envelope-failure message asserts no tick unconditionally; Index-failure remedy promises idempotence, duplicates the tick",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "A07",
        "U03"
      ],
      "fix_id": "fix-2e198411f792",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Required-field pin misses the template agents actually copy; Phase 0.7's exit-code contract is wrong on both failure paths",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "U02"
      ],
      "fix_id": "fix-170084318624",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Shell comment claims resolution parity the shell does not have",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "T01"
      ],
      "fix_id": "fix-3c9e1cd3a093",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Index-failure assertion satisfied by the fixture's own filename",
      "touched_paths": [
        "tests/test_saga_plan_save_and_routing.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "D05",
        "T03"
      ],
      "fix_id": "fix-1db694550386",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Dangling-pointer guard narrowed to Python, markdown unguarded; Guard narrowed to Python leaves markdown pointers unresolved",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "D09"
      ],
      "fix_id": "fix-f03ab7a6f650",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Undefined code P-D3 migrated from skill prose into the journal",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "S04"
      ],
      "fix_id": "fix-f78699abc585",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Documented ladder omits the sys.modules short-circuit above rung 1",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "C05"
      ],
      "fix_id": "fix-ac87c3d71a22",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "SUBSTRATE_SURFACE omits _agent_prompt, which the emitter calls",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "D10",
        "U11"
      ],
      "fix_id": "fix-4c0030371644",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Changelog says docs/plans is reserved for plan documents; Release note keeps the blanket unknown-schema claim the code refutes",
      "touched_paths": [
        "plugins/saga/CHANGELOG.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "U07"
      ],
      "fix_id": "fix-8a63bd53812c",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "HARD BLOCK step points across plugins for Saga's own command",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "S06"
      ],
      "fix_id": "fix-5d21ac319010",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Carrier exception to the ALWAYS-surface rule is undocumented",
      "touched_paths": [
        "plugins/saga/references/operator-choice.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "U08",
        "U10"
      ],
      "fix_id": "fix-9e055d1381da",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Conformance checker has no invocation prose and an undocumented exit 2; Family match is case-insensitive but the token check is not",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "C12",
        "T02"
      ],
      "fix_id": "fix-64c523292cb9",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Empty backend field reported as the Python literal None; Backend-enum rule in the shipped check has no positive test",
      "touched_paths": [
        "plugins/saga/scripts/plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "A09",
        "C10",
        "S02",
        "S03"
      ],
      "fix_id": "fix-1dca06ef0b96",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Validator docstring claims no file reads while the new CLI reads one; Validator has an undocumented third exit with no JSON; Two refusal paths echo caller key names raw and unbounded; caller accepts any string and is narrated verbatim",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "P04",
        "U09"
      ],
      "fix_id": "fix-cbe0f53498e0",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "New OSError subclasses carry no errno, strerror, or filename; Index-failure recovery line asserts a false idempotency",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "U05",
        "U06"
      ],
      "fix_id": "fix-b6525c38e39a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Five rules omit the fence-info rule; a wrong fence drops silently; Skip the offer leaves the recommend call and tick flag undefined",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "A01",
        "S05",
        "U01"
      ],
      "fix_id": "fix-c4fbecfc8247",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Lease release and renew reference an unset shell variable; Unquoted script-dir variable in four copy-and-run command lines; Release and renew blocks lose the scripts-dir variable",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "T07"
      ],
      "fix_id": "fix-6cffb84cfd8a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Drift pin matches shipped source text instead of importing",
      "touched_paths": [
        "tests/test_plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "T05"
      ],
      "fix_id": "fix-8cc4f3f1ff3c",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Never-pre-select guard is file-level, not sentence-level",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ]
    }
  ],
  "lens_results": [
    {
      "accepted": false,
      "applicable_dimensions": {
        "architectural-fit-ownership-single-sources": 5.5,
        "conventions-portability-configuration": 4.5,
        "dependency-direction": 4.0,
        "readability-naming-error-contracts": 5.0,
        "separation-of-concerns": 5.0,
        "significant-decision-documentation": 6.0,
        "simplicity-abstraction-duplication-changeability": 4.5
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 4.928571428571429,
      "failing_dimensions": [
        "architectural-fit-ownership-single-sources",
        "separation-of-concerns",
        "dependency-direction",
        "simplicity-abstraction-duplication-changeability",
        "readability-naming-error-contracts",
        "conventions-portability-configuration",
        "significant-decision-documentation"
      ],
      "lens_id": "architecture-maintainability",
      "non_applicable_dimensions": {},
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "conventions-portability-configuration",
          "finding_id": "A01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "simplicity-abstraction-duplication-changeability",
          "finding_id": "A02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "dependency-direction",
          "finding_id": "A03",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "separation-of-concerns",
          "finding_id": "A04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "separation-of-concerns",
          "finding_id": "A05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "readability-naming-error-contracts",
          "finding_id": "A06",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "architectural-fit-ownership-single-sources",
          "finding_id": "A07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "conventions-portability-configuration",
          "finding_id": "A08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "significant-decision-documentation",
          "finding_id": "A09",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "dependency-direction",
          "finding_id": "A10",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "dependency-direction",
          "finding_id": "A11",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "readability-naming-error-contracts",
          "finding_id": "A12",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "boundary-types-serialization-numeric-time": 7.0,
        "caller-enum-consumer-completeness": 7.0,
        "intent-behavior-completeness": 6.5,
        "side-effects-errors-resource-lifecycle": 6.0,
        "state-data-invariants-transactions-concurrency": 7.5
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 6.8,
      "failing_dimensions": [
        "intent-behavior-completeness",
        "side-effects-errors-resource-lifecycle"
      ],
      "lens_id": "correctness",
      "non_applicable_dimensions": {},
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "side-effects-errors-resource-lifecycle",
          "finding_id": "C01",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "side-effects-errors-resource-lifecycle",
          "finding_id": "C02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "intent-behavior-completeness",
          "finding_id": "C03",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "caller-enum-consumer-completeness",
          "finding_id": "C04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "caller-enum-consumer-completeness",
          "finding_id": "C05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "state-data-invariants-transactions-concurrency",
          "finding_id": "C06",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "boundary-types-serialization-numeric-time",
          "finding_id": "C07",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "boundary-types-serialization-numeric-time",
          "finding_id": "C08",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "side-effects-errors-resource-lifecycle",
          "finding_id": "C09",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "side-effects-errors-resource-lifecycle",
          "finding_id": "C10",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "intent-behavior-completeness",
          "finding_id": "C11",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "boundary-types-serialization-numeric-time",
          "finding_id": "C12",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "authentication-authorization-tenant-isolation": 8.5,
        "confidentiality-logs-errors-egress": 7.5,
        "dependency-supply-chain": 7.0,
        "input-trust-boundaries-injection": 7.0
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 7.5,
      "failing_dimensions": [],
      "lens_id": "security",
      "non_applicable_dimensions": {
        "secrets-cryptography-session-handling": "no secret material, credential, session issuance or cryptographic control is introduced; the only primitive is hashlib.sha256 as a spec-identity content digest, and the one session-adjacent surface (--session-id threaded into reserve/attest) is a byte-identical move writing only to git-ignored .saga/"
      },
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "S01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "confidentiality-logs-errors-egress",
          "finding_id": "S02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "S03",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "dependency-supply-chain",
          "finding_id": "S04",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "input-trust-boundaries-injection",
          "finding_id": "S05",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "authentication-authorization-tenant-isolation",
          "finding_id": "S06",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "behavior-sensitive-assertions": 6.5,
        "determinism-isolation-diagnostics-maintainability": 7.5,
        "negative-edge-state-concurrency-time": 8.0,
        "realistic-seams-mocks-integration-evidence": 7.5,
        "requirements-regression-coverage": 7.0
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 7.3,
      "failing_dimensions": [
        "behavior-sensitive-assertions"
      ],
      "lens_id": "testing",
      "non_applicable_dimensions": {},
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "behavior-sensitive-assertions",
          "finding_id": "T01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "T02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "T03",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "realistic-seams-mocks-integration-evidence",
          "finding_id": "T04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "behavior-sensitive-assertions",
          "finding_id": "T05",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "T06",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "determinism-isolation-diagnostics-maintainability",
          "finding_id": "T07",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "requirements-regression-coverage",
          "finding_id": "T08",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "interface-contract-compatibility": 6.5,
        "retry-idempotency-semantics": 6.0,
        "sdk-generated-client-impact": 7.5,
        "serialization-errors": 6.0,
        "specification-documentation-parity": 6.0,
        "versioning-deprecation": 7.5
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 6.583333333333333,
      "failing_dimensions": [
        "interface-contract-compatibility",
        "serialization-errors",
        "retry-idempotency-semantics",
        "specification-documentation-parity"
      ],
      "lens_id": "api-contract",
      "non_applicable_dimensions": {
        "pagination-rate-limits": "the change adds no paged collection, cursor, quota or throttled interface; the one collection surface (check_plan_corpus, a sorted rglob over a local directory) is deterministic, complete, and has no client-visible ordering or limit contract"
      },
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "retry-idempotency-semantics",
          "finding_id": "P01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "interface-contract-compatibility",
          "finding_id": "P02",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "interface-contract-compatibility",
          "finding_id": "P03",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "P04",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "P05",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "P06",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "serialization-errors",
          "finding_id": "P07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "specification-documentation-parity",
          "finding_id": "P08",
          "priority": "P2",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "capability-parity-reachability": 6.0,
        "context-constraints-acceptance-examples": 6.5,
        "discoverability-invocation-schemas": 6.0,
        "machine-readable-output-actionable-errors": 6.0,
        "safe-bounded-idempotent-resumable-context-cost": 5.5
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 6.0,
      "failing_dimensions": [
        "capability-parity-reachability",
        "discoverability-invocation-schemas",
        "context-constraints-acceptance-examples",
        "machine-readable-output-actionable-errors",
        "safe-bounded-idempotent-resumable-context-cost"
      ],
      "lens_id": "agent-usability",
      "non_applicable_dimensions": {},
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
          "finding_id": "U01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "capability-parity-reachability",
          "finding_id": "U02",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "machine-readable-output-actionable-errors",
          "finding_id": "U03",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "capability-parity-reachability",
          "finding_id": "U04",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "context-constraints-acceptance-examples",
          "finding_id": "U05",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "context-constraints-acceptance-examples",
          "finding_id": "U06",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "capability-parity-reachability",
          "finding_id": "U07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "discoverability-invocation-schemas",
          "finding_id": "U08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
          "finding_id": "U09",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "discoverability-invocation-schemas",
          "finding_id": "U10",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "discoverability-invocation-schemas",
          "finding_id": "U11",
          "priority": "P3",
          "resolved": false
        }
      ]
    },
    {
      "accepted": false,
      "applicable_dimensions": {
        "completeness-audience-prerequisites": 7.5,
        "runbook-safety-rollback-links-generated-drift": 5.5,
        "runnable-examples-actionability": 8.0,
        "shipped-behavior-parity": 5.5,
        "structure-navigation": 8.5,
        "terminology-cross-document-consistency": 6.5
      },
      "cycle": 2,
      "delta_check": null,
      "derived_overall": 6.916666666666667,
      "failing_dimensions": [
        "shipped-behavior-parity",
        "terminology-cross-document-consistency",
        "runbook-safety-rollback-links-generated-drift"
      ],
      "lens_id": "documentation-clarity",
      "non_applicable_dimensions": {},
      "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "score_accepted": false,
      "scoring_findings": [
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "shipped-behavior-parity",
          "finding_id": "D01",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "shipped-behavior-parity",
          "finding_id": "D02",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "runbook-safety-rollback-links-generated-drift",
          "finding_id": "D03",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "shipped-behavior-parity",
          "finding_id": "D04",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": true,
          "dimension_id": "runbook-safety-rollback-links-generated-drift",
          "finding_id": "D05",
          "priority": "P1",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "runbook-safety-rollback-links-generated-drift",
          "finding_id": "D06",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "runbook-safety-rollback-links-generated-drift",
          "finding_id": "D07",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "shipped-behavior-parity",
          "finding_id": "D08",
          "priority": "P2",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "terminology-cross-document-consistency",
          "finding_id": "D09",
          "priority": "P3",
          "resolved": false
        },
        {
          "confidence": 100,
          "critical": false,
          "dimension_id": "completeness-audience-prerequisites",
          "finding_id": "D10",
          "priority": "P3",
          "resolved": false
        }
      ]
    }
  ],
  "next_action": "dispatch_repairs",
  "outcome": "repairs_requested",
  "residual_summary": {
    "final_lens_scores": {
      "agent-usability": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.0,
        "failing_dimensions": [
          "capability-parity-reachability",
          "discoverability-invocation-schemas",
          "context-constraints-acceptance-examples",
          "machine-readable-output-actionable-errors",
          "safe-bounded-idempotent-resumable-context-cost"
        ],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      "api-contract": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.583333333333333,
        "failing_dimensions": [
          "interface-contract-compatibility",
          "serialization-errors",
          "retry-idempotency-semantics",
          "specification-documentation-parity"
        ],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      "architecture-maintainability": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 4.928571428571429,
        "failing_dimensions": [
          "architectural-fit-ownership-single-sources",
          "separation-of-concerns",
          "dependency-direction",
          "simplicity-abstraction-duplication-changeability",
          "readability-naming-error-contracts",
          "conventions-portability-configuration",
          "significant-decision-documentation"
        ],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      "correctness": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.8,
        "failing_dimensions": [
          "intent-behavior-completeness",
          "side-effects-errors-resource-lifecycle"
        ],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      "documentation-clarity": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.916666666666667,
        "failing_dimensions": [
          "shipped-behavior-parity",
          "terminology-cross-document-consistency",
          "runbook-safety-rollback-links-generated-drift"
        ],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      "security": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 7.5,
        "failing_dimensions": [],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      },
      "testing": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 7.3,
        "failing_dimensions": [
          "behavior-sensitive-assertions"
        ],
        "reviewed_revision": "76533cbeba4007cb89e9acf5842027d24cda99de"
      }
    },
    "review_incomplete_reason": null,
    "score_regressions": [
      {
        "current_overall": 4.928571428571429,
        "current_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
        "cycle": 2,
        "lens_id": "architecture-maintainability",
        "previous_overall": 7.428571428571429,
        "previous_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      {
        "current_overall": 6.8,
        "current_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
        "cycle": 2,
        "lens_id": "correctness",
        "previous_overall": 8.4,
        "previous_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      {
        "current_overall": 6.583333333333333,
        "current_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
        "cycle": 2,
        "lens_id": "api-contract",
        "previous_overall": 7.5,
        "previous_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      }
    ],
    "unresolved_fix_ids": [
      "fix-8f87c9f3fa94",
      "fix-c77192119e7b",
      "fix-a34ff0c91932",
      "fix-35e0c83d365a",
      "fix-222ac29adc40",
      "fix-9a088bef2da2",
      "fix-8e3aec8e83c2",
      "fix-f0a36e7e26f8",
      "fix-a69fd443ef72",
      "fix-c1ecbf4f719a",
      "fix-9818846b9df7",
      "fix-2e198411f792",
      "fix-170084318624",
      "fix-3c9e1cd3a093",
      "fix-1db694550386",
      "fix-f03ab7a6f650",
      "fix-f78699abc585",
      "fix-ac87c3d71a22",
      "fix-4c0030371644",
      "fix-8a63bd53812c",
      "fix-5d21ac319010",
      "fix-9e055d1381da",
      "fix-64c523292cb9",
      "fix-1dca06ef0b96",
      "fix-cbe0f53498e0",
      "fix-b6525c38e39a",
      "fix-c4fbecfc8247",
      "fix-6cffb84cfd8a",
      "fix-8cc4f3f1ff3c"
    ]
  },
  "resume_transitions": [
    "dispatch_repairs"
  ],
  "revision_binding": {
    "best_available_revision": "76533cbeba4007cb89e9acf5842027d24cda99de",
    "lens_revisions": {
      "agent-usability": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "api-contract": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "architecture-maintainability": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "correctness": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "documentation-clarity": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "security": "76533cbeba4007cb89e9acf5842027d24cda99de",
      "testing": "76533cbeba4007cb89e9acf5842027d24cda99de"
    }
  },
  "schema": "review_result.v1",
  "selected_lenses": [
    "architecture-maintainability",
    "correctness",
    "security",
    "testing",
    "api-contract",
    "agent-usability",
    "documentation-clarity"
  ],
  "unresolved_fix_ids": [
    "fix-8f87c9f3fa94",
    "fix-c77192119e7b",
    "fix-a34ff0c91932",
    "fix-35e0c83d365a",
    "fix-222ac29adc40",
    "fix-9a088bef2da2",
    "fix-8e3aec8e83c2",
    "fix-f0a36e7e26f8",
    "fix-a69fd443ef72",
    "fix-c1ecbf4f719a",
    "fix-9818846b9df7",
    "fix-2e198411f792",
    "fix-170084318624",
    "fix-3c9e1cd3a093",
    "fix-1db694550386",
    "fix-f03ab7a6f650",
    "fix-f78699abc585",
    "fix-ac87c3d71a22",
    "fix-4c0030371644",
    "fix-8a63bd53812c",
    "fix-5d21ac319010",
    "fix-9e055d1381da",
    "fix-64c523292cb9",
    "fix-1dca06ef0b96",
    "fix-cbe0f53498e0",
    "fix-b6525c38e39a",
    "fix-c4fbecfc8247",
    "fix-6cffb84cfd8a",
    "fix-8cc4f3f1ff3c"
  ]
}
```
