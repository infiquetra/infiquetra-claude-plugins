---
title: Integrated code review — issue 918 Wave 1
reviewed_revision: 5ec8ea7682706aa9f06e359c373cfd2032ee6ba9
base: bbac725a6ad162bfc32948872e612078ed2315b5
branch: work/cp918-saga-plan-improvement
plan: docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md
date: 2026-08-30
outcome: repairs_requested
mode: interactive
---

# Integrated code review — issue 918 Wave 1

One integrated review of the frozen Wave 1 revision in `infiquetra/infiquetra-claude-plugins`, not
four separate unit reviews. The revision merges four unit commits plus release centralization and a
base merge, and it was built against
`docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md` (requirements R1 through R33).

## Outcome

**`repairs_requested`** at revision `5ec8ea7682706aa9f06e359c373cfd2032ee6ba9`. Next action:
`dispatch_repairs`. This is cycle 1 of at most three.

The work is substantially built and the extraction is genuine, but three of the plan's own regression
guards do not guard what they claim, two shipped documents state behaviour the code does not have,
and one new path can select the Claude Code Workflow backend without an operator.

## Scope

| Item | Value |
|---|---|
| Target | branch `work/cp918-saga-plan-improvement` |
| Reviewed revision | `5ec8ea7682706aa9f06e359c373cfd2032ee6ba9` |
| Merge base | `bbac725a6ad162bfc32948872e612078ed2315b5` (`origin/main`) |
| Diff | 76 files, 4911 insertions, 1829 deletions |
| Working tree | clean; no untracked files excluded from review |
| Repository gate | green at this revision per the run record (25 steps, 0 blocking failures, 0 uncovered) — not re-run here |

Unit commits under review:

| Commit | Unit | Claim |
|---|---|---|
| `e0652062` | U1 | require `backend:` in plan-doc frontmatter; add a recursive conformance check |
| `23c25014` | U2 | surface plan-save failures naming the stranded document; stop a finished plan routing back into `/plan` |
| `3ca25ab0` | U3 | add the versioned structured pre-answer carrier |
| `439fdf30` | U4 | extract the Workflow emitter into a new `cc-workflows` plugin at a typed spec-contract seam |
| `a0df73b8` | U5 | centralize release surfaces; register the new plugin |

## Lens roster and approval

The caller supplied the roster, and under `selection_contract.caller_or_orchestrate_selection_is_approval`
in `plugins/saga/references/lens-roster.json` that selection **is** the approval record. It was
persisted through `review_consensus.resolve_lens_selection` against reviewed commit and cycle with
`source: caller` and `question_asked: false` — no operator question was asked, and none was owed.
Seven lenses ran, three workers at a time, at the account concurrency cap. No lens outside the
approved seven was launched.

## Scores

Acceptance is the roster's own rule: derived overall at or above 9.0 **and** every applicable
dimension at or above 7.0. The derived overall is the mean of the applicable dimension scores.

| Lens | Derived overall | Accepted | Dimensions below the 7.0 floor |
|---|---|---|---|
| correctness | 8.40 | no | none |
| api-contract | 7.50 | no | serialization-errors |
| security | 7.50 | no | none |
| architecture-maintainability | 7.43 | no | none |
| agent-usability | 6.00 | no | capability-parity-reachability, discoverability-invocation-schemas, context-constraints-acceptance-examples, machine-readable-output-actionable-errors |
| documentation-clarity | 6.00 | no | shipped-behavior-parity, completeness-audience-prerequisites, runbook-safety-rollback-links-generated-drift |
| testing | 5.60 | no | requirements-regression-coverage, behavior-sensitive-assertions, realistic-seams-mocks-integration-evidence |

Two lenses marked a dimension non-applicable with a stated cause rather than scoring it: security on
`secrets-cryptography-session-handling` (the diff introduces no secret material, credential, session,
token issuance, or encryption), and api-contract on `pagination-rate-limits` (no paging or throttling
surface exists in this repository).

Two lenses reported an overall differing from their own dimension mean — architecture reported 7.4
against a derived 7.43, testing reported 5 against a derived 5.6. The roster derives the overall from
the mean, so the derived figure governs; the difference is rounding, not disagreement.

## Independent gates

A failed independent gate blocks readiness even where numeric acceptance passes. It never changes a
dimension score.

| Gate | Result | Basis |
|---|---|---|
| repository-gate | pass | full 24-step gate green at this revision per the run record |
| release-surface-parity | pass | `sync_marketplace.py --check`, `validate_plugins.py` and `check_release_surface_parity.py` all exit 0; Saga 0.150.0 agrees across manifest, marketplace and version pin |
| built-vs-planned | **fail** | R1 unguarded, R3/R5 shipped inside a test file, R27 residual — detail below |
| contract-obligations | **fail** | obligations 3 and 5 violated, 7 partially violated, 10 partial |

`can_proceed: false`.

## The ten contract obligations

| # | Obligation | Verdict |
|---|---|---|
| 1 | Plan's phases 0, 1, 2 and 4 gained no new question, checklist, questionnaire, or fixed sequence | **satisfied** |
| 2 | No test asserts an exact Plan question, its wording, or the conversation order | **satisfied** |
| 3 | No test substitutes a fixture, mock, or monkeypatch for the behaviour it claims to prove | **violated** |
| 4 | Plan's board-move sentences are untouched | **satisfied** |
| 5 | The Workflow backend is still runnable and explicit-invocation-only | **violated on one clause** |
| 6 | The backend-override telemetry is retained, not removed | **satisfied** |
| 7 | No corpus integer is pinned in code or tests | **satisfied for integers; partially violated for file names** |
| 8 | No repository-level scanner, state store, daemon, registry, queue, or reconciliation pass | **satisfied** |
| 9 | The plan-document contract did not land in the saga tick envelope field table | **satisfied** |
| 10 | Built versus planned: every named requirement built or accounted for, no scope beyond the plan | **partial** |

### 1 — Plan's conversation gained no rigidity. Satisfied.

Phases 1, 2 and 4 are byte-identical to the merge base. This was established by splitting both
revisions of `plugins/saga/skills/plan/SKILL.md` on their phase headings and comparing the bodies —
a stronger check than a line count, because it also catches an equal-sized substitution. Phase 1 is
26 lines on both sides, Phase 2 is 21, Phase 4 is 17.

Phase 0's only addition is subsection 0.7 at `plugins/saga/skills/plan/SKILL.md:134-157`. It is one
framing paragraph plus four bullets keyed on carrier **states** — valid value, absence,
invalid-or-contradictory, unknown schema — with no numbering, no first-then ordering, and no
imperative the agent performs when no carrier is present. Against its neighbours it is the *less*
imperative shape: 0.1 and 0.2 command outright, while 0.7's siblings in voice are 0.4's rubric and
0.5's classification list.

It adds no question and removes one: its only conversational imperative is "Do not ask the operator
to repeat a settled decision" at `:145`. The clause "evaluate it once, at entry, before the first
question" orders the intake relative to the conversation and nothing within it — it is in fact the
mechanism that prevents rigidity, because a carrier read once cannot reach phases 1, 2 or 4 at all.
The suppression binds exactly two decisions, and none of phases 1, 2 or 4 asks either of them.
`plugins/saga/references/saga-spec.md` section 16 passes the same test and closes with an explicit
guard against rendering the carrier as a questionnaire, checklist, or fixed sequence.

### 2 — No test freezes the conversation. Satisfied.

Every new and changed test was grepped for question prose. The single question-adjacent assertion is
`tests/test_plan_pre_answers.py:246-266`, which asserts the **absence** of five rigidity tokens inside
the 0.7 subsection only — the inverse of a snapshot — and is correctly anchored so it cannot silently
match a different section. The eight re-anchored test files add no prose assertions at all.

### 3 — Harness substitution. Violated, in three places, each measured.

This is the review's most serious finding, and every part of it was proven by running the mutation
rather than argued.

**(a) Unit U1's shipped contract change is unguarded.** Reverting the required-`backend:` rule at
`plugins/saga/skills/plan/references/plan-sections.md:185` *and* deleting the sentence at
`plugins/saga/skills/plan/SKILL.md:250-251` left the entire suite green: 6447 passed, 0 failed. The
conformance test hardcodes its own `REQUIRED_FIELDS` tuple at
`tests/test_plan_artifact_conformance.py:38` and never reads the documents it exists to protect.

**(b) The check under test is defined by the test.** `split_frontmatter`, `check_document`,
`check_plan_corpus` and `corpus_exit` all live inside `tests/test_plan_artifact_conformance.py:65-145`,
and the file imports nothing from `plugins/`. All three mutation proofs the plan promises therefore
mutate the test rather than any shipped artifact; they hold, and they prove only that the test file is
internally consistent. No shipped artifact performs the single-pass check requirement R3 describes,
and the operator cannot run it.

**(c) The `#808` counterfactual-branch guard is vacuous for half the files it names.** The guard at
`tests/test_workflow_extraction.py:93-101` compares three flat literal strings against the lowered
file text with no whitespace normalisation. At the merge base the wording wrapped mid-phrase in two of
the four offer files — `plugins/saga/references/operator-choice.md` breaks the line after "value",
`plugins/saga/skills/work/references/execution-strategy.md` after "is" — so neither phrase can ever
match. Both branches were restored verbatim and the suite stayed green (65 passed each time), while
the same reintroduction in `plugins/saga/skills/work/SKILL.md`, where the phrase does not wrap,
correctly went red. Confirmed independently by reading the guard and the merge-base wording.

Everything else passed its mutation check. Unit U2 is the strong unit: it engineers a **real**
filesystem failure rather than monkeypatching the write, and both of its promised proofs plus the
exit-status pin went red under mutation.

One correction to the plan's own claim, recorded rather than charged as a finding: unit U4-A's stated
mutation proof does not exist as written. The plan says removing the explicit-only guard fails the
implicit-selection test, but that test exercises `recommend_execution_backend` in
`plugins/saga/scripts/lifecycle_state.py`, which this diff never touched — it passes identically at
the merge base. It is a legitimate anti-regression pin for requirement R24; it is not a mutation proof
for anything unit U4 changed.

### 4 — Board-move sentences untouched. Satisfied.

The two blocks were resolved at the merge base first, then located at the reviewed revision: they
shifted to different line numbers only because unit U3 inserted subsection 0.7 above them. Both diff
clean against the base. Filtering the diff to changed lines and grepping for the board vocabulary
returns nothing from either block. Child issue 927's custody is intact.

### 5 — Workflow backend runnable and explicit-invocation-only. Violated on one clause.

Three of the four clauses hold, and were verified rather than assumed:

- **Runnable.** Emission was run end to end through the extracted plugin at this revision and produced
  a full workflow script. Separately, emitting one real spec through the pre-extraction Saga and
  through the post-extraction delegation produced byte-identical output.
- **Not retired, removed, disabled, or paused.** Confirmed.
- **Never selected by recommendation.** `recommend_execution_backend` assigns `recommended` only
  `inline` or `team-execution`, and a 48-combination trigger matrix asserts the Workflow backend never
  appears as the recommendation while remaining a reachable alternative. All four offer files retain an
  unconditional never-pre-select sentence, no counterfactual condition survives anywhere, and both
  `#808` pin tests pass.

The failing clause is **"no path may select it implicitly or automatically."** The new carrier's
`BACKEND_ENUM` at `plugins/saga/scripts/plan_pre_answers.py:50` admits `cc-workflows-ultracode`, and
the carrier applies it from any caller with no provenance signal — `caller` is unauthenticated free
text. Phase 0.7 then suppresses the Phase 5.2 confirmation, the value is written to the plan
document's `backend:` field, and `/work` honours that field without asking. A machine caller therefore
reaches Workflow execution with no operator step anywhere on the path, which
`plugins/saga/references/operator-choice.md:57` reserves to the operator explicitly. This was
reproduced: a carrier naming that backend returns it as applied with no stop.

Two qualifications the operator should weigh. First, the plan authorized this enum deliberately —
KTD5 and saga-spec section 16 both specify all three values — so this is a plan-level design decision
conflicting with the run's own obligation, not a worker deviating from the plan. Second, no caller
exercises it today: Orchestrate is unchanged by this diff and still injects prose selecting `inline`.
The repair is a decision, not a defect fix, which is why it routes to a person.

Compounding it: the regression coverage protecting this boundary is itself half-armed, per obligation
3(c) above.

### 6 — Backend-override telemetry retained. Satisfied.

`plugins/saga/scripts/override_rate_reader.py` is byte-unchanged. Both live consumers survive —
`/retro` and `/optimize`. All five telemetry instructions the plan cited survive at moved line
numbers, and Work's copy survives too. The only telemetry-adjacent deletions are the two counterfactual
conditions unit U4-A was chartered to remove; the `--orchestration-recommended` instruction is retained
on both save variants. Operator ruling 1 is honoured.

### 7 — No corpus integer pinned. Satisfied for integers; partially violated for file names.

No corpus integer appears in any new test — not 136, 132, 202, or 25. The only length assertions in the
new files are a uniqueness check and a relative count, neither a corpus figure.

The partial violation is the file name. `tests/test_plan_artifact_conformance.py:47-49` pins a specific
corpus document and asserts at `:302` that it exists and at `:313` that it still fails the marker
triple. The plan permits naming this one document, so it is inside the plan — but asked to judge it,
the testing lens and I agree it should go. It is a corpus-membership assertion in all but name, over a
document the plan itself schedules for the deferred corpus pass, and it buys no detection power: under
the recursion mutation both it and the hermetic fixture test go red, so the hermetic one already proves
requirement R5. When the deferred pass runs, this test goes red for a reason having nothing to do with
recursion, and the diagnostic will point at recursion.

Separately, `tests/test_wave_file_conflicts.py:186` does pin a corpus count in a file this run
re-anchored, but the line predates the diff and was carried forward rather than created. Advisory.

### 8 — No repository-level machinery. Satisfied.

No scanner, state store, daemon, registry, queue, or reconciliation pass was added, confirmed
independently by two lenses. `_SAVE_SCALAR_DEFAULTS` is unchanged, satisfying requirement R14's second
clause. The three new Python modules perform zero writes. The conformance check is a pure function over
a directory tree that never inspects saga ticks and cannot fail the build on the corpus. The two
resolution ladders only read the pre-existing Claude Code plugin registry and create nothing. Settled
decision P-D7 is honoured.

### 9 — Plan-document contract kept out of the tick envelope. Satisfied.

It landed as a new section 15 in `plugins/saga/references/saga-spec.md`, with the pre-answer carrier as
section 16. The tick envelope field table is section 3.1 and is untouched by this diff. Section 15's
opening sentence states the separation explicitly: nothing in it belongs in the envelope field table,
and the two schemas never merge. The one other edit to that file adds `phase_status=complete` to the
`/plan` row of the section 11 consumer table — a different table, and required by requirement R13.

### 10 — Built versus planned. Partial.

No scope beyond the plan was found: every changed file falls inside a unit's declared file list, and
release-surface custody held — none of the four unit commits touched a Saga release surface, and all of
them plus the version pin landed in the integration commit as requirement R31 requires.

The shortfalls are three:

- **Requirement R1** is built in prose but unguarded, per obligation 3(a).
- **Requirements R3 and R5** are built inside a test file rather than as a shipped artifact, per
  obligation 3(b). Classified PARTIAL rather than DONE: the check exists and runs in continuous
  integration, but no shipped artifact performs it and its mutation proofs prove the test.
- **Requirement R27** has one residual. The conventions were changed and no generated artifact remains
  at the top level of `docs/plans/`, but `plugins/saga/references/saga-spec.md:234` still models
  `orchestration_ref` as a `docs/plans/<stem>-spec.json` path. That is the single hit the plan's own
  verification command returns, and it is the pointer KTD7 names as the one that *does* move. The
  guard cannot catch it because the guard iterates a six-file allowlist that omits this file.

Everything else is DONE, including the whole of unit U2, the counterfactual-branch removals, the
artifact migration itself (41 artifacts, set difference empty in both directions), and the release
centralization.

## The two things the coordinator asked to be verified rather than assumed

### A — the eight re-anchored test files. Upheld; I agree with the coordinator's read.

Unit U4 re-anchored eight existing test files because the emitter moved. The coordinator read every
diff and judged them honest. Checked independently and more aggressively, and no pin weakened:

- **Counts held.** Assertion and test-function counts are byte-identical across the merge base and the
  reviewed revision for all eight files — `tests/test_saga_execution_spec.py`, the highest-risk one,
  has 452 assertions and 192 tests on both sides. The single delta is one file gaining an added
  module-load guard and one equality assertion moving onto a continuation line when its call was
  wrapped. No assertion was dropped, softened from equality to substring, or broadened.
- **The safety pins are armed, not merely present.** Setting the verifier agent type to
  `general-purpose` in the moved emitter turns 9 tests red across two files. Setting the isolation
  constant to `none` turns 4 red, including one that exercises the *emitted script* rather than the
  constant. These are the `saga:readonly-verifier` and disposable-worktree pins the coordinator singled
  out, and they still bite.
- **No old behaviour was orphaned.** The constants exist in exactly one place after the move, so the
  re-anchor did not leave a second, unguarded definition behind.
- **Two re-anchors strengthen coverage.** One widens its source scan from Saga alone to Saga plus the
  new plugin, so Saga's remaining spawn sites stay scanned while the moved ones are added; another uses
  dictionary lookups that raise on a wrong path rather than passing vacuously.

The vacuous guard that does exist is in the **new** file `tests/test_workflow_extraction.py`, not in
any of the eight re-anchored ones.

### B — unit U3's narrowed rigidity pin. I agree with the narrowing, and it does not fully guard R29.

**The narrowing was right.** Asserting the absolute absence of the word "checklist" from Plan's phases
0 through 2 and 4 would fail on legitimate existing prose — Phase 1 and Phase 4 already use it — so a
pin scoped to the subsection the unit adds is the correct call, and I would have made the same one.

**But it does not guard what requirement R29 exists to guard**, for two reasons:

1. **Scope.** The pin covers only the 0.7 subsection. R29 binds all of phases 0 through 2 and 4, so a
   rigidity shape introduced anywhere else in those phases passes untouched. The plan scoped it this
   way deliberately, so this is a known gap rather than an error — but it is a gap.
2. **Mechanism.** The pin is a keyword-absence check over five listed tokens. A walk-through written
   without any of those five words passes. The guard cannot see shape, only vocabulary.

**A stronger guard is available at the same cost**, and it is the one this review performed by hand:
split both revisions of `plugins/saga/skills/plan/SKILL.md` on their phase headings and assert that the
bodies of phases 1, 2 and 4 are unchanged. That is mechanical, needs no keyword list, catches an
equal-sized substitution, and expresses R29 directly rather than by proxy. Phase 0 still needs the
keyword pin, because Phase 0 is where a subsection may legitimately be added. Recommended as a
follow-up, not as a blocker.

## Coverage and method

- **Suppressed findings:** none. Every reported finding sits at confidence anchor 75 or 100; the
  admission rule suppresses below 75 except a P0 at 50 or above, and no finding landed there.
- **Validator pass:** skipped, per the interactive-mode contract in which the operator is the
  per-finding validator. In place of it, the controller independently re-derived the highest-consequence
  claims from source: the save-path write ordering, the counterfactual guard's literal matching against
  the merge-base wording, the `#808` pins in all four files, the residual `docs/plans/` reference, and
  the reachability precedent the plan itself named.
- **Not verified, and stated rather than implied:** no end-to-end Claude Code Workflow tool launch was
  attempted — this environment cannot perform one, so the extraction evidence is emitted-bytes parity
  and a real emit run, not a runtime launch. Neither resolution ladder was exercised from a genuine
  installed-plugin cache layout; rungs three and four are reasoned from source and from simulated
  misses. The full repository gate was not re-run, per the brief.
- **Residual risks:** the cross-plugin resolution shim measures 20 percent covered with all four
  resolution rungs and the loud-failure path unexecuted, because every test short-circuits on the
  module cache. If a rung is wrong, the plugin breaks for an operator running from an installed layout
  while this repository's suite stays green.

## Cross-reviewer agreement

Four findings were raised independently by more than one lens, which is the strongest signal in the set:

| Finding | Lenses | Merged severity |
|---|---|---|
| The pre-answer validator has no runtime caller and no invocation surface | architecture, correctness, testing, agent-usability, documentation-clarity | P1 |
| Prose promises a whole-carrier refusal the family gate does not perform | correctness, api-contract, agent-usability, documentation-clarity | P1 |
| The save-failure message asserts a false fact on the index-write path | correctness, agent-usability, documentation-clarity | P1 |
| Eleven private Saga names bound across the plugin boundary | architecture, api-contract | P2 |

The stale `docs/plans/` reference at `plugins/saga/references/saga-spec.md:234` was found three ways:
by the controller through the plan's own verification command, by the testing lens through the guard's
allowlist gap, and by the documentation lens through a systematic path sweep.

Where lenses disagreed on severity, the more conservative route was kept. The carrier's admission of the
Workflow backend was P1 from security and P3 advisory from correctness; it is recorded at P1 with a
manual route to a person, because the security lens reproduced the applied value and the disagreement is
about consequence, not about fact.

## Findings

62 findings: 7 at P1, 33 at P2, 22 at P3. None at P0. Sorted by severity, then confidence anchor descending, then file, then line. `Route` is `autofix_class -> owner`. Findings are numbered stably; a finding keeps its number across cycles.


### P1 (7)

| # | File | Issue | Reviewer | Conf | Route |
|---|---|---|---|---|---|
| F03 | `plugins/saga/scripts/plan_pre_answers.py:50` | Carrier admits the Workflow backend with no operator gate | security | 100 | manual -> human |
| F02u | `plugins/saga/skills/plan/SKILL.md:138` | Pre-answer validator has no runnable invocation for an agent | agent-usability | 100 | manual -> human |
| F07d | `plugins/saga/skills/plan/SKILL.md:151` | Unknown-schema refusal is false for a foreign token | documentation-clarity | 100 | manual -> review-fixer |
| F05d | `plugins/saga/skills/plan/SKILL.md:594` | Save-failure prose asserts no tick when a tick exists | documentation-clarity | 100 | manual -> review-fixer |
| F01 | `tests/test_plan_artifact_conformance.py:38` | U1 required-backend contract change is unguarded | testing | 100 | manual -> review-fixer |
| F06t | `tests/test_plan_artifact_conformance.py:98` | Entire U1 conformance check lives inside its own test file | testing | 100 | manual -> human |
| F02 | `tests/test_workflow_extraction.py:93` | Counterfactual-branch guard vacuous for two of four files | testing | 100 | manual -> review-fixer |

### P2 (33)

| # | File | Issue | Reviewer | Conf | Route |
|---|---|---|---|---|---|
| F13 | `docs/engineering-journal/DECISIONS.md:1` | No engineering-journal entry for a new plugin and a new seam | architecture-maintainability | 100 | manual -> review-fixer |
| F13d | `docs/engineering-journal/DECISIONS.md:3` | No engineering-journal entry for a fifteenth plugin and new seam | documentation-clarity | 100 | manual -> review-fixer |
| F20d | `plugins/cc-workflows/README.md:20` | Three resolution env overrides documented in no markdown file | documentation-clarity | 100 | manual -> review-fixer |
| F33 | `plugins/cc-workflows/skills/cc-workflows/SKILL.md:3` | cc-workflows skill description carries no trigger conditions | agent-usability | 100 | safe_auto -> review-fixer |
| F19d | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:14` | Emitter docstring claims no import-time I/O; three lines below it does | documentation-clarity | 100 | safe_auto -> review-fixer |
| F10 | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:58` | Extracted emitter binds eleven private names of Saga's module | architecture-maintainability | 100 | manual -> downstream-resolver |
| F10a | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:74` | Eleven private Saga names bound across the plugin boundary | api-contract | 100 | manual -> review-fixer |
| F11 | `plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:1` | Third hand-written copy of the plugin-root resolution ladder | architecture-maintainability | 100 | manual -> downstream-resolver |
| F31 | `plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:42` | Cross-plugin seam has no version negotiation or declared dependency | api-contract | 100 | manual -> release |
| F16 | `plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:94` | Cross-plugin resolution shim at 20 percent, ladder never executed | testing | 100 | manual -> review-fixer |
| F09 | `plugins/saga/references/execution-spec.md:399` | Validate/emit protocol duplicated across the extraction seam | architecture-maintainability | 100 | manual -> review-fixer |
| F09d | `plugins/saga/references/saga-spec.md:234` | Worked envelope example escapes the unit's own docs/plans guard | documentation-clarity | 100 | safe_auto -> review-fixer |
| F06 | `plugins/saga/references/saga-spec.md:667` | Required-field set stated in three documents plus a test constant | architecture-maintainability | 100 | manual -> review-fixer |
| F07a | `plugins/saga/references/saga-spec.md:712` | Shipped docs claim whole-refusal the family gate does not deliver | api-contract | 100 | manual -> review-fixer |
| F39 | `plugins/saga/references/sandbox-spawn-sites.md:36` | sandbox-spawn-sites.md still attributes moved symbols to Saga | documentation-clarity | 100 | safe_auto -> review-fixer |
| F04 | `plugins/saga/scripts/plan_pre_answers.py:1` | Pre-answer validator has no caller and no CLI | architecture-maintainability | 100 | manual -> review-fixer |
| F14a | `plugins/saga/scripts/plan_pre_answers.py:50` | Backend enum triplicated with no drift pin to ORCHESTRATION_MODES | api-contract | 100 | gated_auto -> review-fixer |
| F08 | `plugins/saga/scripts/plan_pre_answers.py:61` | Any fenced block accepted; conflicting carriers resolved silently | security | 100 | manual -> review-fixer |
| F08a | `plugins/saga/scripts/plan_pre_answers.py:90` | First carrier wins silently when two disagree | api-contract | 100 | manual -> review-fixer |
| F15 | `plugins/saga/scripts/plan_pre_answers.py:92` | Duplicate JSON keys silently apply the last value | security | 100 | safe_auto -> review-fixer |
| F30 | `plugins/saga/scripts/plan_pre_answers.py:93` | Malformed carrier JSON indistinguishable from no carrier | api-contract | 100 | manual -> review-fixer |
| F07u | `plugins/saga/scripts/plan_pre_answers.py:98` | Non-family schema token silently ignored, contradicting both contracts | agent-usability | 100 | manual -> review-fixer |
| F02c | `plugins/saga/scripts/plan_pre_answers.py:184` | Pre-answer validator has no runtime caller | correctness | 100 | gated_auto -> review-fixer |
| F04t | `plugins/saga/scripts/plan_pre_answers.py:184` | Pre-answer validator has no caller anywhere in the repository | testing | 100 | manual -> human |
| F05 | `plugins/saga/scripts/saga.py:1656` | Save error falsely claims the plan lost its tick | correctness | 100 | manual -> review-fixer |
| F05u | `plugins/saga/scripts/saga.py:1657` | Save-failure message asserts a false fact on the index-write path | agent-usability | 100 | manual -> review-fixer |
| F02d | `plugins/saga/skills/plan/SKILL.md:138` | plan_pre_answers validator has no runnable invocation | documentation-clarity | 100 | manual -> review-fixer |
| F07 | `plugins/saga/skills/plan/SKILL.md:151` | Docs promise a refusal the validator does not perform | correctness | 100 | manual -> review-fixer |
| F32 | `plugins/saga/skills/plan/SKILL.md:155` | Phase 0.7 omits two rules the validator enforces | agent-usability | 100 | manual -> review-fixer |
| F34 | `plugins/saga/skills/plan/SKILL.md:522` | Approval-table obligation left Saga behind a descriptive pointer | agent-usability | 100 | manual -> review-fixer |
| F12 | `plugins/saga/skills/work/SKILL.md:356` | Cross-plugin commands hardcode a repo-relative path | architecture-maintainability | 100 | manual -> review-fixer |
| F18 | `tests/test_workflow_extraction.py:164` | docs/plans write-path guard misses saga-spec.md via its allowlist | testing | 100 | gated_auto -> review-fixer |
| F17 | `tests/test_workflow_extraction.py:198` | Moved-artifact pointer test verifies one of forty-one artifacts | testing | 100 | manual -> review-fixer |

### P3 (22)

| # | File | Issue | Reviewer | Conf | Route |
|---|---|---|---|---|---|
| F20 | `plugins/cc-workflows/README.md:1` | Three new environment variables documented nowhere | architecture-maintainability | 100 | manual -> review-fixer |
| F35 | `plugins/cc-workflows/skills/cc-workflows/SKILL.md:42` | cc-workflows authoring protocol says four steps, starts at Step 2 | agent-usability | 100 | safe_auto -> review-fixer |
| F35d | `plugins/cc-workflows/skills/cc-workflows/SKILL.md:45` | cc-workflows authoring protocol starts at Step 2 with no Step 1 | documentation-clarity | 100 | safe_auto -> review-fixer |
| F19 | `plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py:14` | Emitter docstring claims no import-time I/O while doing it | architecture-maintainability | 100 | safe_auto -> review-fixer |
| F25 | `plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py:59` | Plugin-root ladder matches any marketplace and any int-parsable dirname | security | 100 | advisory -> downstream-resolver |
| F40 | `plugins/saga/references/saga-spec.md:660` | New spec sections appended after the References section | documentation-clarity | 100 | safe_auto -> review-fixer |
| F06d | `plugins/saga/references/saga-spec.md:666` | Required-field set triplicated with no drift pin | documentation-clarity | 100 | manual -> review-fixer |
| F22 | `plugins/saga/references/sandbox-spawn-sites.md:130` | Reference still attributes a moved helper to execution_spec.py | correctness | 100 | safe_auto -> review-fixer |
| F14 | `plugins/saga/scripts/plan_pre_answers.py:51` | Destination enum copied from saga.py with no drift pin | correctness | 100 | gated_auto -> review-fixer |
| F21 | `plugins/saga/scripts/plan_pre_answers.py:73` | Outcome docstring states a caller invariant the code breaks | correctness | 100 | safe_auto -> review-fixer |
| F21a | `plugins/saga/scripts/plan_pre_answers.py:73` | Outcome docstring misstates caller on an empty carrier | api-contract | 100 | safe_auto -> review-fixer |
| F23 | `plugins/saga/scripts/plan_pre_answers.py:98` | Near-miss schema token ignored instead of refused whole | security | 100 | gated_auto -> review-fixer |
| F24 | `plugins/saga/scripts/plan_pre_answers.py:160` | Refusal message echoes unbounded caller-supplied value | security | 100 | safe_auto -> review-fixer |
| F36 | `plugins/saga/scripts/plan_pre_answers.py:194` | Outcome conflates no-carrier with nothing-omitted | agent-usability | 100 | safe_auto -> review-fixer |
| F41 | `plugins/saga/skills/plan/SKILL.md:529` | Undefined internal code P-D3 leaks into shipped skill prose | documentation-clarity | 100 | safe_auto -> review-fixer |
| F26 | `tests/test_plan_artifact_conformance.py:263` | KTD3 constructed fixture duplicates the legacy test it extends | testing | 100 | safe_auto -> review-fixer |
| F28 | `tests/test_plan_artifact_conformance.py:302` | Named corpus file pin is brittle against the plan's own deferred pass | testing | 100 | manual -> downstream-resolver |
| F27 | `tests/test_plan_artifact_conformance.py:343` | Two tautological assertions in the marker-triple contract pin | testing | 100 | safe_auto -> review-fixer |
| F29 | `tests/test_wave_file_conflicts.py:186` | Re-anchored conflict sentinel still pins a corpus count *(pre-existing)* | testing | 100 | advisory -> downstream-resolver |
| F38 | `plugins/saga/scripts/execution_spec.py:3082` | emit to docs/workflows raises an uncaught FileNotFoundError | agent-usability | 75 | safe_auto -> review-fixer |
| F03c | `plugins/saga/scripts/plan_pre_answers.py:50` | Carrier admits the Workflow backend without operator confirmation | correctness | 75 | advisory -> human |
| F37 | `plugins/saga/skills/plan/SKILL.md:291` | Question-suppression rule stated at intake, absent at point of use | agent-usability | 75 | safe_auto -> review-fixer |

## Fix routing

`consolidate_fix_requests` produced 29 consolidated fix requests from the active, non-advisory, non-pre-existing findings. `/code-review` hands these back; it never applies them. The author or `/work` owns every repair change.

| Route | Count |
|---|---|
| gated_auto | 2 |
| manual | 19 |
| safe_auto | 8 |

| Owner | Count |
|---|---|
| downstream-resolver | 3 |
| human | 3 |
| release | 1 |
| review-fixer | 22 |

The three requests owned by a person are the ones that need a decision rather than an edit: whether the carrier may name the Workflow backend at all, whether the conformance check moves out of its test file, and whether the pre-answer validator gains a runnable entry point.


## Next action

`dispatch_repairs`. The structured fix requests go back to `/work`; resubmit only after they land. This is cycle 1 of at most three, and the seven failing lenses are what cycle 2 would attempt.


## Recommended repair order

Ordered by what protects the most, not by severity alone:

1. **Arm the `#808` guard** (finding F02). It is the cheapest fix here and it currently leaves half the explicit-invocation boundary unprotected. Collapse whitespace before matching.
2. **Decide the carrier's backend enum** (finding F03). This is an operator decision, not an edit, and findings F07d and F07u partly depend on where it lands.
3. **Pin unit U1's contract change** (finding F01) and **move the conformance check out of its test file** (finding F06t). Together these turn the plan's three promised mutation proofs into proofs of shipped code.
4. **Reconcile the two false prose claims** (findings F07d and F05d) — the whole-carrier refusal and the save-failure message. Both are stated on four surfaces each, including the changelog.
5. **Give the validator a runnable entry point** (finding F02u), which closes the divergence the reachability cluster describes.
6. Everything else at P2 and P3, including the residual `docs/plans/` reference and the missing engineering-journal entries.


## Linked artifacts

| Artifact | Path |
|---|---|
| Plan | `docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md` |
| Pre-registered criteria | `docs/evidence/adhoc-cp918-saga-plan-improvement/criteria-code-review-5ec8ea7682706aa9f06e359c373cfd2032ee6ba9.json` |
| Parent issue | 918 (Wave 1); children 922, 923, 924, 925 |
| Work-thread saga | none found — `saga.py scan` returned zero candidates, so no tick was written and none was minted |

## The typed result

Schema `review_result.v1`. `outcome` is its only decision field. A consumer must load it with `ReviewResult.from_json()` so an unknown schema or an undefined resume transition fails closed; that round-trip was verified against this payload.

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
  "best_available_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
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
      "dimension_id": "authentication-authorization-tenant-isolation",
      "evidence": [
        "plugins/saga/scripts/plan_pre_answers.py:50 BACKEND_ENUM includes cc-workflows-ultracode",
        "Executed: a carrier with backend cc-workflows-ultracode returns applied with no stop",
        "plugins/saga/references/operator-choice.md:57 -- a Workflow is entered only when the operator explicitly invokes it",
        "plugins/saga/skills/plan/SKILL.md:318 /work honours the field and does not ask again"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F03",
      "lens_id": "security",
      "line": 50,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Restrict the carrier enum to inline and team-execution and stop on cc-workflows-ultracode naming the #808 ruling, or require an explicit operator-confirmed marker.",
      "title": "Carrier admits the Workflow backend with no operator gate",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "BACKEND_ENUM admits cc-workflows-ultracode and the carrier applies it from any caller with no provenance signal; Phase 0.7 then suppresses the Phase 5.2 confirm and /work honours the recorded field without asking, so a machine caller can enter the explicit-invocation-only Workflow backend with no operator step anywhere on the path."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "capability-parity-reachability",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:138 names the validator with no invocation",
        "plugins/saga/scripts/plan_pre_answers.py has no argparse, no main, no __main__",
        "Controller check: the plan's named precedent intent_envelope.py has a CLI at :200,:250,:259 and ten production importers",
        "Found independently by architecture, correctness, testing and agent-usability"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F02u",
      "lens_id": "agent-usability",
      "line": 138,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add an argparse main reading invocation text on stdin and printing PreAnswerOutcome as JSON, then put the literal command in Phase 0.7.",
      "title": "Pre-answer validator has no runnable invocation for an agent",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Phase 0.7 names the validator but gives no command, import, or return shape, and the module has no CLI and no importer outside its own test. An executing agent must re-implement the four rules from prose, and a prose re-implementation diverges from the shipped module on at least four inputs, so two runs on identical text can take opposite paths."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "plugins/saga/skills/plan/SKILL.md:151, saga-spec.md:712 and :732, CHANGELOG.md:11-12 all state the blanket rule",
        "plugins/saga/scripts/plan_pre_answers.py:98 gates on schema.startswith(SCHEMA_FAMILY)",
        "Executed: a carrier declaring orchestrate_pre_answers.v1 returns the no-carrier outcome; plan_pre_answers.v2 returns a stop",
        "tests/test_plan_pre_answers.py:135-145 pins the silent path, so the gate can never surface the divergence"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F07d",
      "lens_id": "documentation-clarity",
      "line": 151,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "State the two-case rule on all four surfaces: a non-v1 token inside the family is refused whole; a foreign family is not a carrier and is ignored.",
      "title": "Unknown-schema refusal is false for a foreign token",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Four prose surfaces promise a carrier declaring any other schema token is refused in its entirety; the code refuses only tokens inside the plan_pre_answers family, so a typo or a renamed envelope returns the identical all-empty no-stop outcome as no carrier. The caller believes a decision was handed over and nothing is surfaced."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "plugins/saga/scripts/saga.py:828 writes the envelope, :830 rewrites the index",
        "plugins/saga/scripts/saga.py:987-990 restore never opens state.json",
        "Reproduced: with state.json blocked the CLI exited 2 with the NO-saga-tick message while a tick sat on disk and restore returned it",
        "plugins/saga/CHANGELOG.md:38-40 repeats the claim to release readers"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F05d",
      "lens_id": "documentation-clarity",
      "line": 594,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Split the message on which write failed, and correct plan/SKILL.md:594 and the changelog to match.",
      "title": "Save-failure prose asserts no tick when a tick exists",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The skill and the runtime message both assert a non-zero save exit means no tick was written; that is false when only the state.json index rewrite fails, because the envelope is written first and restore reads it directly. The agent halts and reports a stranded document that is fully tracked."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "MUTATION RUN: reverted plan-sections.md:185 and deleted plan/SKILL.md:250-251 -> 6447 passed, 0 failed",
        "tests/test_plan_artifact_conformance.py:38 REQUIRED_FIELDS is a test-local constant"
      ],
      "file": "tests/test_plan_artifact_conformance.py",
      "finding_id": "F01",
      "lens_id": "testing",
      "line": 38,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Add a definition pin that parses the required-field bullet from plan-sections.md and plan/SKILL.md and asserts both name backend, matching the marker-triple pin at :328.",
      "title": "U1 required-backend contract change is unguarded",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ],
      "why_it_matters": "Reverting the required-backend rule in both declaration sites leaves the whole 6447-test suite green; the check tests its own hardcoded REQUIRED_FIELDS tuple and never reads the documents it protects."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "realistic-seams-mocks-integration-evidence",
      "evidence": [
        "tests/test_plan_artifact_conformance.py:65-145 defines the whole check; the file imports nothing from plugins/",
        "git diff --name-only bbac725a 5ec8ea76 -- plugins/saga/scripts/ shows no conformance module"
      ],
      "file": "tests/test_plan_artifact_conformance.py",
      "finding_id": "F06t",
      "lens_id": "testing",
      "line": 98,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Move check_document/check_plan_corpus/corpus_exit into a runnable module under plugins/saga/scripts/ with a __main__ entry and have the test import it.",
      "title": "Entire U1 conformance check lives inside its own test file",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ],
      "why_it_matters": "R3 requires one conformance check over docs/plans/; no shipped artifact performs it. split_frontmatter, check_document, check_plan_corpus and corpus_exit are all defined in the test module, so the plan's three promised mutation proofs mutate the test rather than any shipped code, and the operator cannot run the check."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "MUTATION RUN: restored the merge-base branch into operator-choice.md:55-57 -> 65 passed, 0 failed",
        "MUTATION RUN: same for execution-strategy.md:158-159 -> 65 passed, 0 failed",
        "CONTROL: same for work/SKILL.md:53 -> FAILED, so the guard works only where the phrase does not wrap",
        "Controller confirmed by inspection: tests/test_workflow_extraction.py:93-101 compares three flat literals against lowered text"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "F02",
      "lens_id": "testing",
      "line": 93,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P1",
      "status": "active",
      "suggested_fix": "Collapse whitespace runs in the file text before matching, or match a regex tolerant of the line wrap.",
      "title": "Counterfactual-branch guard vacuous for two of four files",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "The #808 explicit-invocation guard is a literal-substring blacklist with no whitespace normalisation; the merge-base wording wraps mid-phrase in two of the four offer files, so those branches can be restored verbatim and the suite stays green."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "significant-decision-documentation",
      "evidence": [
        "No docs/engineering-journal file changed in any of the six commits",
        "The preceding issue-912 wave touched DECISIONS.md and LEARNINGS.md in every unit commit"
      ],
      "file": "docs/engineering-journal/DECISIONS.md",
      "finding_id": "F13",
      "lens_id": "architecture-maintainability",
      "line": 1,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add one entry for the extraction boundary and one for the docs/workflows convention.",
      "title": "No engineering-journal entry for a new plugin and a new seam",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ],
      "why_it_matters": "The repository's CLAUDE.md requires a same-commit DECISIONS.md entry for plugin-pattern and tooling decisions; this diff makes four and records none, while the preceding wave recorded one per unit commit."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "completeness-audience-prerequisites",
      "evidence": [
        "No docs/engineering-journal file changed in any of the six commits",
        "The preceding wave added a DECISIONS.md entry in each of four shipping commits",
        "The plan document assigns the obligation to no unit"
      ],
      "file": "docs/engineering-journal/DECISIONS.md",
      "finding_id": "F13d",
      "lens_id": "documentation-clarity",
      "line": 3,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add entries for the extraction seam, the docs/workflows convention, and the versioned carrier.",
      "title": "No engineering-journal entry for a fifteenth plugin and new seam",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ],
      "why_it_matters": "CLAUDE.md makes a same-commit DECISIONS.md entry an obligation for plugin-pattern and tooling decisions; this diff makes four and records none, so the rationale and rejected alternatives live only in a plan document that will be archived."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "completeness-audience-prerequisites",
      "evidence": [
        "Zero markdown hits for SAGA_SPEC_ROOT, SAGA_SPEC_DEBUG, CC_WORKFLOWS_SCRIPTS_DIR",
        "saga_spec_shim.py:36 and execution_spec.py:2467 instruct the operator to set them",
        "fleet-core/README.md:36-40 documents the analogue; saga_spec_shim.py:4 names that file as its model"
      ],
      "file": "plugins/cc-workflows/README.md",
      "finding_id": "F20d",
      "lens_id": "documentation-clarity",
      "line": 20,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a resolution paragraph mirroring the fleet-core README and state the saga prerequisite.",
      "title": "Three resolution env overrides documented in no markdown file",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ],
      "why_it_matters": "Both directions of the seam fail loud with a message telling the operator to set an environment variable, and no document names any of the three; an operator running from a non-repo checkout has only the runtime error to go on."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "cc-workflows/SKILL.md:3-9 has no trigger clause",
        "24 skills in the repo carry activation phrasing; cc-workflows is absent from that list"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/SKILL.md",
      "finding_id": "F33",
      "lens_id": "agent-usability",
      "line": 3,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Append a trigger clause naming the situations that should select it.",
      "title": "cc-workflows skill description carries no trigger conditions",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md"
      ],
      "why_it_matters": "Skill selection is driven by the frontmatter description; this is the only skill added by the diff and it has no Triggers-on or Use-when clause, while its second sentence reads to a selector as a reason not to activate, so the skill that now owns Steps 2 to 5 may never surface."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "shipped-behavior-parity",
      "evidence": [
        "emitter.py:14 vs :29, :36, :38",
        "The I/O chain runs through saga_spec_shim.py:42, :55, :85, :149 and can raise at :118",
        "Contrast execution_spec.py:2472 which loads lazily and says so"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "F19d",
      "lens_id": "documentation-clarity",
      "line": 14,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Replace the line with a true statement about the one import-time side effect.",
      "title": "Emitter docstring claims no import-time I/O; three lines below it does",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The new plugin's central module states pure functions with no I/O at import as its contract line, but importing it mutates sys.path, stats a four-rung ladder, reads the installed-plugins registry, and execs another plugin's Python, and can raise before any function is called."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "dependency-direction",
      "evidence": [
        "emitter.py:58-101 binds 29 names; 11 are private",
        "execution_spec.py declares no __all__",
        "Confirmed independently by api-contract at emitter.py lines 74,75,81,82,83,89,90,91,92,93,98"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "F10",
      "lens_id": "architecture-maintainability",
      "line": 58,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Publish the substrate under non-underscore aliases or a named tuple, and assert every bound name exists.",
      "title": "Extracted emitter binds eleven private names of Saga's module",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "_bind_substrate copies 29 attributes out of Saga's execution_spec, 11 underscore-prefixed, with a hand-maintained list and no completeness guard, so an ordinary Saga refactor breaks the extracted plugin."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "Independently counted 11 bindings at emitter.py lines 74,75,81,82,83,89,90,91,92,93,98",
        "execution_spec.py has no __all__; its seam comment at :2401-2410 names none of them",
        "In-repo mitigation: tests/test_workflow_extraction.py:226-233 imports the emitter"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "F10a",
      "lens_id": "api-contract",
      "line": 74,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Declare the permitted surface explicitly and assert every bound name is a member.",
      "title": "Eleven private Saga names bound across the plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The underscore prefix is Python's own marker for private-may-change, execution_spec.py declares no __all__, and the seam comment names no bound symbol, so the cross-plugin contract is an undocumented set of implementation details."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "simplicity-abstraction-duplication-changeability",
      "evidence": [
        "113 of saga_spec_shim.py's 153 stripped lines are identical to fleet_commons_shim.py (difflib ratio 0.702)",
        "execution_spec.py:2413-2470 inlines the same ladder a third time"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py",
      "finding_id": "F11",
      "lens_id": "architecture-maintainability",
      "line": 1,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Parameterize the ladder once in fleet-core and have both new call sites use it.",
      "title": "Third hand-written copy of the plugin-root resolution ladder",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ],
      "why_it_matters": "The extraction added two new implementations of the same four-rung resolver alongside fleet_commons_shim.py, so a rung-order change must be fixed in three places."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "versioning-deprecation",
      "evidence": [
        "saga_spec_shim.py:41-42 is existence-only; execution_spec.py:2413-2467 mirrors it",
        "cc-workflows plugin.json has no dependencies key; orchestrate's plugin.json:22-27 declares one",
        "Verified: a saga-only tree raises an actionable RuntimeError at emission time"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py",
      "finding_id": "F31",
      "lens_id": "api-contract",
      "line": 42,
      "owner": "release",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Declare a saga dependency with a >=0.150.0 floor and add an install sentence to the changelog entry.",
      "title": "Cross-plugin seam has no version negotiation or declared dependency",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ],
      "why_it_matters": "Two independently versioned plugins load each other by path resolution alone, validating only that a file exists, and the new plugin declares no dependencies key although the repository already uses that mechanism; the Saga changelog announcing the move gives no install instruction."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "realistic-seams-mocks-integration-evidence",
      "evidence": [
        "MEASURED coverage: saga_spec_shim.py 92 stmts, 74 miss, 20%; emitter.py 97% in the same run",
        "saga_spec_shim.py:135-137 returns the cached module",
        "grep for saga_spec_shim in tests/ returns nothing"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py",
      "finding_id": "F16",
      "lens_id": "testing",
      "line": 94,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a shim test popping sys.modules and covering each rung plus the all-miss RuntimeError.",
      "title": "Cross-plugin resolution shim at 20 percent, ladder never executed",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ],
      "why_it_matters": "Every test short-circuits on the sys.modules cache before resolve_root runs, so all four rungs and the loud-failure path ship untested; if rung 3 or 4 is wrong the plugin breaks for the installed operator while this suite stays green."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "separation-of-concerns",
      "evidence": [
        "execution-spec.md:399-412 vs cc-workflows/SKILL.md:61-79",
        "plan/SKILL.md:519-531 shows the intended pointer shape"
      ],
      "file": "plugins/saga/references/execution-spec.md",
      "finding_id": "F09",
      "lens_id": "architecture-maintainability",
      "line": 399,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Replace execution-spec.md steps 2 and 3 with a pointer to the cc-workflows skill.",
      "title": "Validate/emit protocol duplicated across the extraction seam",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ],
      "why_it_matters": "Saga's execution-spec.md still carries the validate and emit steps with byte-identical command lines that the new plugin also owns, so the protocol has two owners in two plugins."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "saga-spec.md:234 is the only surviving such reference under plugins/ outside CHANGELOG.md",
        "tests/test_workflow_extraction.py:163-175 scans six files and saga-spec.md is not among them",
        "Executing the guard's own regex against saga-spec.md returns the stale path",
        "Found independently by the controller via the plan's own verification grep"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "F09d",
      "lens_id": "documentation-clarity",
      "line": 234,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Repoint to docs/workflows/ and add saga-spec.md to the guard's file tuple.",
      "title": "Worked envelope example escapes the unit's own docs/plans guard",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "The canonical worked example still points a generated spec at docs/plans/, the directory this diff reserved for plan documents, and the unit's own drift guard does not scan this file, so the drift reports green forever."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "architectural-fit-ownership-single-sources",
      "evidence": [
        "saga-spec.md:666-667, plan-sections.md:185, plan/SKILL.md:242-253, tests/test_plan_artifact_conformance.py:38"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "F06",
      "lens_id": "architecture-maintainability",
      "line": 667,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Extend the marker-triple pin to parse the required-field bullet from both markdown declarations.",
      "title": "Required-field set stated in three documents plus a test constant",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "U1 reconciled two contradicting declarations then added a third and a fourth; only the marker triple has a drift pin, so three of four can go stale with the gate green."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "specification-documentation-parity",
      "evidence": [
        "saga-spec.md:712, plan/SKILL.md:151, plan_pre_answers.py:22-23 vs :87-88",
        "Executed: a hyphenated token and a null token both return stop None; v2 returns a stop"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "F07a",
      "lens_id": "api-contract",
      "line": 712,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Pick one reading and make all four sites state it.",
      "title": "Shipped docs claim whole-refusal the family gate does not deliver",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "Three shipped documents state the unrecognised-token refusal without qualification while the code refuses only the plan_pre_answers family, and the module's own two docstrings contradict each other on the same point."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "runbook-safety-rollback-links-generated-drift",
      "evidence": [
        "sandbox-spawn-sites.md:35-37 and :129-130",
        "_emit_verify_loop_singleton, _emit_verify_panel and render_fallback_tier_marker now live only in emitter.py at :1114, :1173, :703",
        "concurrency-spawn-sites.md:59-60 was repointed in this same diff"
      ],
      "file": "plugins/saga/references/sandbox-spawn-sites.md",
      "finding_id": "F39",
      "lens_id": "documentation-clarity",
      "line": 36,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Repoint both lines to the emitter, matching the sibling file.",
      "title": "sandbox-spawn-sites.md still attributes moved symbols to Saga",
      "touched_paths": [
        "plugins/saga/references/sandbox-spawn-sites.md"
      ],
      "why_it_matters": "This is the document the repository's CLAUDE.md orders every agent to consult before a verify-class spawn, and it names symbols in a file that no longer contains them; the sibling inventory was repointed in the same commit, so this is an incomplete sweep."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "architectural-fit-ownership-single-sources",
      "evidence": [
        "No __main__/argparse/def main in the module",
        "Only importer is tests/test_plan_pre_answers.py"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F04",
      "lens_id": "architecture-maintainability",
      "line": 1,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a main(argv) and a runnable command in Phase 0.7.",
      "title": "Pre-answer validator has no caller and no CLI",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The 195-line module is shipped, typed and tested, but nothing in the repository can run it, so the four evaluation rules are enforced at run time only by Plan's prose."
    },
    {
      "autofix_class": "gated_auto",
      "confidence": 100,
      "dimension_id": "interface-contract-compatibility",
      "evidence": [
        "saga.py:79 canonical; plan_pre_answers.py:50 and tests/test_plan_artifact_conformance.py:37 are literal copies",
        "The only enum pin knows nothing of the two new copies"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F14a",
      "lens_id": "api-contract",
      "line": 50,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Import the canonical tuple, or assert both new copies equal their sources.",
      "title": "Backend enum triplicated with no drift pin to ORCHESTRATION_MODES",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The spec declares in two places that the value comes from ORCHESTRATION_MODES, but neither new copy imports it or asserts equality, so the documentation asserts a single-source relationship nothing enforces."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "_FENCE_RE at :61 accepts any info string",
        "Executed: the same body under text/bash/diff/python fences each applied",
        "Executed: two disagreeing carriers resolved to the first with stop None"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F08",
      "lens_id": "security",
      "line": 61,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Require the info string to be exactly json and stop when more than one carrier is present.",
      "title": "Any fenced block accepted; conflicting carriers resolved silently",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The fence info-string group matches any language, so pasted content containing a matching JSON object becomes a live decision, and the first of two disagreeing carriers wins by document position with no stop."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:90-100 returns on the first match",
        "Executed: a stale block preceding the live one wins with stop None",
        "saga-spec.md:698-699 states no precedence rule"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F08a",
      "lens_id": "api-contract",
      "line": 90,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Collect every matching block and stop when more than one is present, or document first-wins explicitly.",
      "title": "First carrier wins silently when two disagree",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "When the invocation text carries more than one carrier the first is applied and the rest discarded with no stop, so a stale pasted carrier silently overrides the live one; the spec describes the transport in the singular and states no precedence rule."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "Executed: backend EVIL followed by backend inline returns applied inline with no stop",
        "Executed: backend inline followed by backend cc-workflows-ultracode applies the latter",
        "plan_pre_answers.py:92 has no object_pairs_hook"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F15",
      "lens_id": "security",
      "line": 92,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Pass an object_pairs_hook that raises on a repeated key and convert it to a whole-carrier stop.",
      "title": "Duplicate JSON keys silently apply the last value",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "json.loads keeps the last occurrence, so a carrier can present one value and apply another: an out-of-enum value paired with a later duplicate never reaches the enum check, and the narration that is the operator's only defence shows the wrong value."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "serialization-errors",
      "evidence": [
        "plan_pre_answers.py:92-94 swallows JSONDecodeError with continue",
        "Executed: a trailing-comma carrier and the no-carrier input return identical values",
        "saga-spec.md section 16 documents no malformed case"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F30",
      "lens_id": "api-contract",
      "line": 93,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Distinguish a carrier-shaped block that fails to parse from no carrier, and document it as a fifth rule.",
      "title": "Malformed carrier JSON indistinguishable from no carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "A truncated or unparseable carrier returns an outcome field-for-field identical to no carrier supplied, so the settled decision evaporates with no signal and Plan re-asks the question the carrier exists to remove."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plan_pre_answers.py:98 vs plan/SKILL.md:151 and saga-spec.md:732",
        "Executed: foo.v1 returns applied empty with stop None; plan_pre_answers.v2 returns a stop",
        "tests/test_plan_pre_answers.py:188-205 covers only the same-family case"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F07u",
      "lens_id": "agent-usability",
      "line": 98,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Widen extract_carrier to return any block carrying a schema key, or narrow both prose contracts.",
      "title": "Non-family schema token silently ignored, contradicting both contracts",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "Phase 0.7 rule 4 and saga-spec rule 4 both say any other schema token is refused entirely; the module refuses only the plan_pre_answers family, so a one-character typo drops the caller's settled decision with no signal while an agent implementing the prose would halt."
    },
    {
      "autofix_class": "gated_auto",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "Repo-wide grep finds only prose, the module and its test",
        "The plan's named precedent intent_envelope.py carries main()/__main__ and is invoked from skill prose"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F02c",
      "lens_id": "correctness",
      "line": 184,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add a thin main(argv) and one runnable line in Phase 0.7.",
      "title": "Pre-answer validator has no runtime caller",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "Every reference outside the test file is prose; nothing tells the agent to run it and the module exposes no CLI, so the proven behaviours never execute at run time."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "realistic-seams-mocks-integration-evidence",
      "evidence": [
        "No main/argparse/__main__; no importer outside the test",
        "The named precedent intent_envelope.py has a __main__ block and eight in-repo importers"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F04t",
      "lens_id": "testing",
      "line": 184,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Give the module a main() and invoke it from Phase 0.7 so a test can drive it as a real subprocess.",
      "title": "Pre-answer validator has no caller anywhere in the repository",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "Eleven runtime tests exercise the module and nothing in the shipped product calls any of them, so the tests prove a library's arithmetic rather than Plan's conduct."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "side-effects-errors-resource-lifecycle",
      "evidence": [
        "saga.py:828-830 write ordering; :981-989 restore path",
        "Reproduced with state.json.tmp pre-created as a directory: exit 2 with the false message while restore returned phase_status complete",
        "Controller confirmed the ordering by inspection"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "F05",
      "lens_id": "correctness",
      "line": 1656,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Condition the stranded-document sentence on the envelope actually being absent.",
      "title": "Save error falsely claims the plan lost its tick",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The handler treats every OSError as no-tick-written, but the envelope is written before the index rewrite and restore reads the envelope directly, so an index-only failure reports a false durable-state fact and the prescribed remedy appends a duplicate tick."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "machine-readable-output-actionable-errors",
      "evidence": [
        "saga.py:830-832 write ordering; :981-989 restore never reads state.json",
        "Idempotency measured: two identical saves produced identical derived state and one state.json"
      ],
      "file": "plugins/saga/scripts/saga.py",
      "finding_id": "F05u",
      "lens_id": "agent-usability",
      "line": 1657,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Word the message to the failure that actually occurred and correct plan/SKILL.md:594.",
      "title": "Save-failure message asserts a false fact on the index-write path",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ],
      "why_it_matters": "The downstream agent behaviour is a false halt: the run stops and the operator is told the plan is stranded when it is not. The prescribed remedy is idempotent, so the cost is a spurious halt and a redundant write, not corruption."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "runnable-examples-actionability",
      "evidence": [
        "plan/SKILL.md:138 with no command block anywhere in :134-156",
        "No __main__, argparse or main in the module; the only importer is its test",
        "Every other cited script ships a copy-pasteable block that exits 0 when run verbatim"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F02d",
      "lens_id": "documentation-clarity",
      "line": 138,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add an argparse entry point and the one-line command block in Phase 0.7.",
      "title": "plan_pre_answers validator has no runnable invocation",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Phase 0.7 names the validator but no document shows how to call it and the module has no CLI, so an agent driving through Bash must evaluate the carrier by reading prose, which is the path that reproduces the family-prefix divergence."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "intent-behavior-completeness",
      "evidence": [
        "plan_pre_answers.py:98 is the only admission gate",
        "Executed: a plan_preanswers.v1 carrier returns the no-carrier outcome",
        "tests/test_plan_pre_answers.py:135-145 pins the fall-through"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F07",
      "lens_id": "correctness",
      "line": 151,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Narrow the prose or widen the family gate; the two are pinned to opposite contracts.",
      "title": "Docs promise a refusal the validator does not perform",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "Both contract documents state the unknown-token refusal unconditionally; the implementation refuses only the plan_pre_answers family, so a mistyped family falls through silently instead of surfacing."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plan_pre_answers.py:124-137 unknown-key stop; :139-147 non-string caller stop",
        "Executed: a third key returns applied empty with a refusal stop",
        "plan/SKILL.md:142-152 covers neither; saga-spec.md:722 carries the extra-key rule Phase 0.7 drops"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F32",
      "lens_id": "agent-usability",
      "line": 155,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Add one clause to Phase 0.7's fourth bullet covering an unadmitted key and a malformed caller.",
      "title": "Phase 0.7 omits two rules the validator enforces",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The module stops on an unadmitted third key and on a non-string caller; Phase 0.7 states neither, and because the module is unreachable Phase 0.7 IS the implementation for an executing agent, so the agent applies what the module refuses."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "plan/SKILL.md:522-531 is descriptive, not imperative",
        "cc-workflows/SKILL.md:93-96 holds the obligation text",
        "The obligation text is gone from all four Saga offer files"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F34",
      "lens_id": "agent-usability",
      "line": 522,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Make the pointer imperative and keep the one safety sentence in Saga.",
      "title": "Approval-table obligation left Saga behind a descriptive pointer",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The rule never to ask an operator to approve a backend without showing its enforceability rows now exists only in the new plugin; Saga's replacement names spec_table.py inside a descriptive sentence with no invocation and no imperative to load that file."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "conventions-portability-configuration",
      "evidence": [
        "work/SKILL.md:356,:358,:426,:434",
        "plugins/team-execution/skills/team-execution/SKILL.md:339 is the established form"
      ],
      "file": "plugins/saga/skills/work/SKILL.md",
      "finding_id": "F12",
      "lens_id": "architecture-maintainability",
      "line": 356,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Introduce a resolved variable honouring the env var the Python seam already reads.",
      "title": "Cross-plugin commands hardcode a repo-relative path",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ],
      "why_it_matters": "Four runnable commands reach into the sibling plugin by a literal repo-relative path that resolves only inside a checkout of this repository, while team-execution's precedent uses a CLAUDE_PLUGIN_ROOT fallback for exactly this case."
    },
    {
      "autofix_class": "gated_auto",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "tests/test_workflow_extraction.py:164-171 lists six files; saga-spec.md is absent",
        "plugins/saga/references/saga-spec.md:234 still carries the retired convention",
        "Controller found the same residual independently via the plan's own verification grep"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "F18",
      "lens_id": "testing",
      "line": 164,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Replace the six-path tuple with a recursive scan of plugins/**/*.md excluding CHANGELOG.md, and fix saga-spec.md:234.",
      "title": "docs/plans write-path guard misses saga-spec.md via its allowlist",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "The guard iterates a hand-written six-file allowlist mirroring the plan's inventory, so a file the inventory missed is invisible to the test; one such file still documents orchestration_ref as a docs/plans path."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "MEASURED: rerunning the test's own scan and regex yields 1 distinct reference",
        "MEASURED move size: 41 artifacts, set diff empty in both directions"
      ],
      "file": "tests/test_workflow_extraction.py",
      "finding_id": "F17",
      "lens_id": "testing",
      "line": 198,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P2",
      "status": "active",
      "suggested_fix": "Raise the guard to a floor reflecting the real pointer count, or invert the test to assert no docs/plans reference resolves to a moved artifact.",
      "title": "Moved-artifact pointer test verifies one of forty-one artifacts",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ],
      "why_it_matters": "U4-B moved 41 artifacts; the regex requires a literal filename so it finds exactly one match, and the assert-references guard written to catch scan drift is satisfied by that single hit."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "conventions-portability-configuration",
      "evidence": [
        "Zero markdown hits repo-wide for all three names",
        "plugins/fleet-core/README.md:36 documents the analogous override"
      ],
      "file": "plugins/cc-workflows/README.md",
      "finding_id": "F20",
      "lens_id": "architecture-maintainability",
      "line": 1,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a resolution-and-overrides section to the new plugin README.",
      "title": "Three new environment variables documented nowhere",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ],
      "why_it_matters": "SAGA_SPEC_ROOT, SAGA_SPEC_DEBUG and CC_WORKFLOWS_SCRIPTS_DIR are the only escape hatch when resolution misses and the failure messages tell the operator to set them, but no markdown file mentions any of the three."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "discoverability-invocation-schemas",
      "evidence": [
        "cc-workflows/SKILL.md:42-45",
        "plan/SKILL.md:398, :484, :503 hold Steps 1, 1b, 1c"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/SKILL.md",
      "finding_id": "F35",
      "lens_id": "agent-usability",
      "line": 42,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add one sentence naming where Step 1 lives.",
      "title": "cc-workflows authoring protocol says four steps, starts at Step 2",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md"
      ],
      "why_it_matters": "The section announces four steps and the first heading is Step 2; Steps 1, 1b and 1c live in Saga's skill and are never named, so a reader cannot tell whether a step is missing from the file or lives elsewhere."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "structure-navigation",
      "evidence": [
        "cc-workflows/SKILL.md:42-43 then :45, :55, :61, :71",
        "Step 1 is at plan/SKILL.md:398",
        "execution-spec.md:391-427 numbers the same two commands 2 and 3"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/SKILL.md",
      "finding_id": "F35d",
      "lens_id": "documentation-clarity",
      "line": 45,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Name where Step 1 lives, and add the reverse pointer in protocol.md.",
      "title": "cc-workflows authoring protocol starts at Step 2 with no Step 1",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md"
      ],
      "why_it_matters": "The skill announces four steps then presents Steps 2 to 5; Step 1 lives in a different plugin's skill and is never named, and a Saga reference numbers the identical activity differently, so the two documents disagree on what Step 4 means."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "readability-naming-error-contracts",
      "evidence": [
        "emitter.py:14 vs :29 and :36",
        "Reproduced: importing with SAGA_SPEC_ROOT=/nonexistent raises at import"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py",
      "finding_id": "F19",
      "lens_id": "architecture-maintainability",
      "line": 14,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Name the one import-time side effect in the docstring.",
      "title": "Emitter docstring claims no import-time I/O while doing it",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ],
      "why_it_matters": "The module header states pure functions with no I/O at import; sixteen lines later it mutates sys.path and loads another plugin's Python, and can raise before any function is called."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "dependency-supply-chain",
      "evidence": [
        "saga_spec_shim.py:59 startswith saga@; :48 bare int()",
        "Executed: int(' 5')==5, int('+9')==9, int('1_0')==10, and (99999,) > (0,149,0)",
        "Precedent: fleet_commons_shim.py:48 and :62 carry the identical shapes"
      ],
      "file": "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py",
      "finding_id": "F25",
      "lens_id": "security",
      "line": 59,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Match the exact registry key and fullmatch the version before int() conversion.",
      "title": "Plugin-root ladder matches any marketplace and any int-parsable dirname",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ],
      "why_it_matters": "Rung 3 matches a saga plugin from any installed marketplace and rung 4's bare int() accepts whitespace, a leading plus, underscores and non-ASCII digits, producing variable-length tuples that sort lexicographically; the precondition already implies compromise, and both shapes mirror the established house pattern."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "structure-navigation",
      "evidence": [
        "saga-spec.md:632 is section 14; :660 is 15; :691 is 16; the file ends at :736",
        "The diff hunk is a pure append with no move of section 14"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "F40",
      "lens_id": "documentation-clarity",
      "line": 660,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Move the References section to the end of the file.",
      "title": "New spec sections appended after the References section",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "Sections 15 and 16 were appended after section 14 References, so the reference list sits 100 lines from the end with two normative sections below it; a reader who scrolls to the references never sees the two sections this diff added."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "terminology-cross-document-consistency",
      "evidence": [
        "plan-sections.md:185, saga-spec.md:666-667, tests/test_plan_artifact_conformance.py:38 agree",
        "Source of truth is declared once, at saga-spec.md:670-671; plan/SKILL.md names no authority",
        "One wording gap: plan-sections.md:197 permits omitted or left empty where the others say only omitted"
      ],
      "file": "plugins/saga/references/saga-spec.md",
      "finding_id": "F06d",
      "lens_id": "documentation-clarity",
      "line": 666,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a definition pin for the field set and reduce the other copies to pointers.",
      "title": "Required-field set triplicated with no drift pin",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ],
      "why_it_matters": "The five required fields are stated normatively in three documents plus the checker and only the sibling half of the contract, the marker triple, has a definition pin; the three copies agree today."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "sandbox-spawn-sites.md:130 vs emitter.py:703",
        "concurrency-spawn-sites.md:60 was repointed in the same commit"
      ],
      "file": "plugins/saga/references/sandbox-spawn-sites.md",
      "finding_id": "F22",
      "lens_id": "correctness",
      "line": 130,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Repoint to the emitter, matching the sibling file.",
      "title": "Reference still attributes a moved helper to execution_spec.py",
      "touched_paths": [
        "plugins/saga/references/sandbox-spawn-sites.md"
      ],
      "why_it_matters": "render_fallback_tier_marker moved to the new plugin and the sibling reference was repointed in the same commit; this one was not, so the containment runbook sends a reader to a symbol that is gone."
    },
    {
      "autofix_class": "gated_auto",
      "confidence": 100,
      "dimension_id": "caller-enum-consumer-completeness",
      "evidence": [
        "plan_pre_answers.py:50-51 vs saga.py:78-79",
        "tests/test_saga_saga.py:1834 pins ORCHESTRATION_MODES but nothing pins DESTINATIONS"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F14",
      "lens_id": "correctness",
      "line": 51,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Assert both new enums equal their canonical sources.",
      "title": "Destination enum copied from saga.py with no drift pin",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "DESTINATION_ENUM re-literals saga.py's DESTINATIONS and the spec asserts they are the same enum, but nothing pins it, so a fifth destination becomes a hard stop on a legitimate value."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "boundary-types-serialization-numeric-time",
      "evidence": [
        "plan_pre_answers.py:73-74 vs the executed result for a carrier omitting caller"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F21",
      "lens_id": "correctness",
      "line": 73,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Correct the docstring or require caller whenever a decision field is supplied.",
      "title": "Outcome docstring states a caller invariant the code breaks",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The docstring says caller is None when nothing is applied, implying a non-empty applied always carries a caller for R16's narration; a carrier omitting caller yields applied with caller None."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "specification-documentation-parity",
      "evidence": [
        "plan_pre_answers.py:73-74 and :181",
        "Executed: a carrier with only schema and caller returns applied empty with caller set"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F21a",
      "lens_id": "api-contract",
      "line": 73,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Reword to describe what the code returns.",
      "title": "Outcome docstring misstates caller on an empty carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "A consumer told caller is None when nothing is applied would treat a non-None caller as proof something was applied; a valid empty carrier returns a caller string with an empty applied mapping."
    },
    {
      "autofix_class": "gated_auto",
      "confidence": 100,
      "dimension_id": "input-trust-boundaries-injection",
      "evidence": [
        "Executed: Plan_Pre_Answers.v1 returns no refusal",
        "Executed: a near-miss first block hands the decision to a later carrier"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F23",
      "lens_id": "security",
      "line": 98,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Casefold or match the family on a token boundary so a near-miss produces the documented stop.",
      "title": "Near-miss schema token ignored instead of refused whole",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The family gate is a case-sensitive startswith, so a typo or a prefixed token is not recognised as a carrier at all and the loop continues to the next fenced block; the contract promises a loud refusal."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "confidentiality-logs-errors-egress",
      "evidence": [
        "Executed: a 30,000-deep nested array yields a 60,168-character stop string"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F24",
      "lens_id": "security",
      "line": 160,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Truncate the interpolated value to a fixed width with an ellipsis marker.",
      "title": "Refusal message echoes unbounded caller-supplied value",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "The enum-violation stop interpolates the value with no length cap, so a single malformed carrier can blow up the surfaced reason arbitrarily; repr does neutralise newlines, so this is length only, not injection."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "machine-readable-output-actionable-errors",
      "evidence": [
        "plan_pre_answers.py:192-195 vs :180",
        "Executed: no carrier yields omitted empty; an empty valid carrier yields both names"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F36",
      "lens_id": "agent-usability",
      "line": 194,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Return the full decision-field tuple on the no-carrier path.",
      "title": "Outcome conflates no-carrier with nothing-omitted",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "evaluate returns omitted empty when there is no carrier and both decision names for a valid empty carrier, though both mean the same thing to a consumer; a consumer branching on omitted gets the wrong answer on the commonest path."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "terminology-cross-document-consistency",
      "evidence": [
        "plan/SKILL.md:529 and :534",
        "grep for P-D[0-9] across plugins/ returns only those two lines"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F41",
      "lens_id": "documentation-clarity",
      "line": 529,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Drop the parenthetical or replace it with the plain reason.",
      "title": "Undefined internal code P-D3 leaks into shipped skill prose",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The code appears twice in prose an agent executes, as the justification for the artifact-location rule, and is defined nowhere the agent can reach."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "tests/test_plan_artifact_conformance.py:102 is the only classification rule",
        "The assertion at :278 duplicates the one at :241",
        "The real missing-required-field coverage is at :207-215"
      ],
      "file": "tests/test_plan_artifact_conformance.py",
      "finding_id": "F26",
      "lens_id": "testing",
      "line": 263,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Rewrite the comment to state what is true and cross-reference the incomplete-plan fixture.",
      "title": "KTD3 constructed fixture duplicates the legacy test it extends",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ],
      "why_it_matters": "Stripping backend: from a new-contract document leaves it classification-identical to an ordinary legacy plan, because presence of backend: is the only new-contract signal; the test's comment asserts otherwise and its assertion duplicates the legacy test twenty lines above."
    },
    {
      "autofix_class": "manual",
      "confidence": 100,
      "dimension_id": "determinism-isolation-diagnostics-maintainability",
      "evidence": [
        "tests/test_plan_artifact_conformance.py:47-49, :302, :313",
        "The plan defers the fleet-ideation tree and its nested verification report",
        "Under the rglob->glob mutation both this and the tmp_path test go red, so it adds no detection power"
      ],
      "file": "tests/test_plan_artifact_conformance.py",
      "finding_id": "F28",
      "lens_id": "testing",
      "line": 302,
      "owner": "downstream-resolver",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Assert the shape (a reported finding more than one component below the root) rather than the named member.",
      "title": "Named corpus file pin is brittle against the plan's own deferred pass",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ],
      "why_it_matters": "The test hard-asserts a specific corpus document exists and still fails the marker triple, over a file the plan explicitly schedules for the deferred corpus pass; the recursion property it claims is already proven hermetically twelve lines above."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 100,
      "dimension_id": "behavior-sensitive-assertions",
      "evidence": [
        "tests/test_plan_artifact_conformance.py:31-32 define the constants; :343-344 assert them equal to those literals",
        "The useful half is armed: rewriting the declaration made the test fail"
      ],
      "file": "tests/test_plan_artifact_conformance.py",
      "finding_id": "F27",
      "lens_id": "testing",
      "line": 343,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Delete the two tautologies or bind the constants to the declaration text.",
      "title": "Two tautological assertions in the marker-triple contract pin",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ],
      "why_it_matters": "The last two assertions compare module constants against the same literals used to define them fourteen lines earlier, so they can never fail; the comment promises the pin guards both sides and it guards only the declaration side."
    },
    {
      "autofix_class": "advisory",
      "confidence": 100,
      "dimension_id": "requirements-regression-coverage",
      "evidence": [
        "tests/test_wave_file_conflicts.py:185-186",
        "The merge-base version globbed docs/plans with the identical floor",
        "Current count is 20, so the floor holds"
      ],
      "file": "tests/test_wave_file_conflicts.py",
      "finding_id": "F29",
      "lens_id": "testing",
      "line": 186,
      "owner": "downstream-resolver",
      "pre_existing": true,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": null,
      "title": "Re-anchored conflict sentinel still pins a corpus count",
      "touched_paths": [
        "tests/test_wave_file_conflicts.py"
      ],
      "why_it_matters": "R33 forbids pinning a corpus count and this asserts len(specs) >= 18; U4-B re-anchored the glob directly above it without revisiting the floor. The same line existed at the merge base, so it is carried forward rather than created here."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 75,
      "dimension_id": "safe-bounded-idempotent-resumable-context-cost",
      "evidence": [
        "execution_spec.py:3081-3083 writes with no parent mkdir; :3077-3079 catches only two types",
        "plan/SKILL.md:532-534 and cc-workflows/SKILL.md:71-76 name the destination with no mkdir step"
      ],
      "file": "plugins/saga/scripts/execution_spec.py",
      "finding_id": "F38",
      "lens_id": "agent-usability",
      "line": 3082,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a parent mkdir before the write.",
      "title": "emit to docs/workflows raises an uncaught FileNotFoundError",
      "touched_paths": [
        "plugins/saga/scripts/execution_spec.py"
      ],
      "why_it_matters": "The new artifact destination gets no mkdir and the enclosing except catches only SpecError and CostWeightsError, so a missing directory surfaces as a raw traceback; the directory exists here but Saga is used to build in other repositories and no new prose says to create it."
    },
    {
      "autofix_class": "advisory",
      "confidence": 75,
      "dimension_id": "intent-behavior-completeness",
      "evidence": [
        "plan_pre_answers.py:50",
        "saga-spec.md:717-719 records the applied value without re-offering",
        "Security reported the same mechanics at P1"
      ],
      "file": "plugins/saga/scripts/plan_pre_answers.py",
      "finding_id": "F03c",
      "lens_id": "correctness",
      "line": 50,
      "owner": "human",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Operator decision: restrict the enum or accept the path.",
      "title": "Carrier admits the Workflow backend without operator confirmation",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ],
      "why_it_matters": "Reported as a contract tension with issue 808's explicit-invocation rule rather than a deviation: the plan and saga-spec specify this enum deliberately and no caller exercises it today."
    },
    {
      "autofix_class": "safe_auto",
      "confidence": 75,
      "dimension_id": "context-constraints-acceptance-examples",
      "evidence": [
        "plan/SKILL.md:291-293 unchanged by this diff",
        "plan/SKILL.md:145 is the only statement of the rule",
        "LEARNINGS.md records a prior incident of the same shape"
      ],
      "file": "plugins/saga/skills/plan/SKILL.md",
      "finding_id": "F37",
      "lens_id": "agent-usability",
      "line": 291,
      "owner": "review-fixer",
      "pre_existing": false,
      "requires_verification": false,
      "severity": "P3",
      "status": "active",
      "suggested_fix": "Add a carrier-aware parenthetical at Phase 5.1 and 5.2.",
      "title": "Question-suppression rule stated at intake, absent at point of use",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ],
      "why_it_matters": "The do-not-re-ask rule appears once in Phase 0.7 while Phase 5.1 and 5.2 still read unconditionally, hundreds of lines later; an agent whose context has rolled past Phase 0 re-asks the question the carrier settled."
    }
  ],
  "fix_requests": [
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F10"
      ],
      "fix_id": "fix-cdedfbeff16d",
      "owner": "downstream-resolver",
      "requires_verification": false,
      "summary": "Extracted emitter binds eleven private names of Saga's module",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F11"
      ],
      "fix_id": "fix-47d14d72de14",
      "owner": "downstream-resolver",
      "requires_verification": false,
      "summary": "Third hand-written copy of the plugin-root resolution ladder",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F28"
      ],
      "fix_id": "fix-30b14aa8860e",
      "owner": "downstream-resolver",
      "requires_verification": false,
      "summary": "Named corpus file pin is brittle against the plan's own deferred pass",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F03",
        "F04t"
      ],
      "fix_id": "fix-1e32f8de29bc",
      "owner": "human",
      "requires_verification": false,
      "summary": "Carrier admits the Workflow backend with no operator gate; Pre-answer validator has no caller anywhere in the repository",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F02u"
      ],
      "fix_id": "fix-14dcdc14fb95",
      "owner": "human",
      "requires_verification": false,
      "summary": "Pre-answer validator has no runnable invocation for an agent",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F06t"
      ],
      "fix_id": "fix-d4838903cdba",
      "owner": "human",
      "requires_verification": false,
      "summary": "Entire U1 conformance check lives inside its own test file",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F31"
      ],
      "fix_id": "fix-f6635448f785",
      "owner": "release",
      "requires_verification": false,
      "summary": "Cross-plugin seam has no version negotiation or declared dependency",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ]
    },
    {
      "autofix_class": "gated_auto",
      "finding_ids": [
        "F02c",
        "F14",
        "F14a",
        "F23"
      ],
      "fix_id": "fix-ea8359027302",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Pre-answer validator has no runtime caller; Destination enum copied from saga.py with no drift pin; Backend enum triplicated with no drift pin to ORCHESTRATION_MODES; Near-miss schema token ignored instead of refused whole",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "gated_auto",
      "finding_ids": [
        "F18"
      ],
      "fix_id": "fix-c77fb632f03a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "docs/plans write-path guard misses saga-spec.md via its allowlist",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F13",
        "F13d"
      ],
      "fix_id": "fix-07564e57d245",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "No engineering-journal entry for a new plugin and a new seam; No engineering-journal entry for a fifteenth plugin and new seam",
      "touched_paths": [
        "docs/engineering-journal/DECISIONS.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F20",
        "F20d"
      ],
      "fix_id": "fix-f21fbcdde228",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Three new environment variables documented nowhere; Three resolution env overrides documented in no markdown file",
      "touched_paths": [
        "plugins/cc-workflows/README.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F10a"
      ],
      "fix_id": "fix-4da2d62e8302",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Eleven private Saga names bound across the plugin boundary",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F16"
      ],
      "fix_id": "fix-1ae49b5c69f0",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Cross-plugin resolution shim at 20 percent, ladder never executed",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/saga_spec_shim.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F09"
      ],
      "fix_id": "fix-0e28b4be689a",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Validate/emit protocol duplicated across the extraction seam",
      "touched_paths": [
        "plugins/saga/references/execution-spec.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F06",
        "F06d",
        "F07a"
      ],
      "fix_id": "fix-7bbe44049715",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Required-field set stated in three documents plus a test constant; Required-field set triplicated with no drift pin; Shipped docs claim whole-refusal the family gate does not deliver",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F04",
        "F07u",
        "F08",
        "F08a",
        "F30"
      ],
      "fix_id": "fix-a2b3dcd68eb8",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Pre-answer validator has no caller and no CLI; Non-family schema token silently ignored, contradicting both contracts; Any fenced block accepted; conflicting carriers resolved silently; First carrier wins silently when two disagree; Malformed carrier JSON indistinguishable from no carrier",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F05",
        "F05u"
      ],
      "fix_id": "fix-1a0d08a0aa66",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Save error falsely claims the plan lost its tick; Save-failure message asserts a false fact on the index-write path",
      "touched_paths": [
        "plugins/saga/scripts/saga.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F02d",
        "F05d",
        "F07",
        "F07d",
        "F32",
        "F34"
      ],
      "fix_id": "fix-3d055db303b8",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "plan_pre_answers validator has no runnable invocation; Save-failure prose asserts no tick when a tick exists; Docs promise a refusal the validator does not perform; Unknown-schema refusal is false for a foreign token; Phase 0.7 omits two rules the validator enforces; Approval-table obligation left Saga behind a descriptive pointer",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F12"
      ],
      "fix_id": "fix-4d72b7bf33e2",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Cross-plugin commands hardcode a repo-relative path",
      "touched_paths": [
        "plugins/saga/skills/work/SKILL.md"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F01"
      ],
      "fix_id": "fix-176784886a82",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "U1 required-backend contract change is unguarded",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ]
    },
    {
      "autofix_class": "manual",
      "finding_ids": [
        "F02",
        "F17"
      ],
      "fix_id": "fix-e28b316be7df",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Counterfactual-branch guard vacuous for two of four files; Moved-artifact pointer test verifies one of forty-one artifacts",
      "touched_paths": [
        "tests/test_workflow_extraction.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F33",
        "F35",
        "F35d"
      ],
      "fix_id": "fix-a6614db521d4",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "cc-workflows skill description carries no trigger conditions; cc-workflows authoring protocol says four steps, starts at Step 2; cc-workflows authoring protocol starts at Step 2 with no Step 1",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/SKILL.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F19",
        "F19d"
      ],
      "fix_id": "fix-682af25ab42f",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Emitter docstring claims no import-time I/O while doing it; Emitter docstring claims no import-time I/O; three lines below it does",
      "touched_paths": [
        "plugins/cc-workflows/skills/cc-workflows/scripts/emitter.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F09d",
        "F40"
      ],
      "fix_id": "fix-0ddffb195d12",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Worked envelope example escapes the unit's own docs/plans guard; New spec sections appended after the References section",
      "touched_paths": [
        "plugins/saga/references/saga-spec.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F22",
        "F39"
      ],
      "fix_id": "fix-0dd7e9a29e05",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Reference still attributes a moved helper to execution_spec.py; sandbox-spawn-sites.md still attributes moved symbols to Saga",
      "touched_paths": [
        "plugins/saga/references/sandbox-spawn-sites.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F38"
      ],
      "fix_id": "fix-f1f46aac5b08",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "emit to docs/workflows raises an uncaught FileNotFoundError",
      "touched_paths": [
        "plugins/saga/scripts/execution_spec.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F15",
        "F21",
        "F21a",
        "F24",
        "F36"
      ],
      "fix_id": "fix-16799de10934",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Duplicate JSON keys silently apply the last value; Outcome docstring states a caller invariant the code breaks; Outcome docstring misstates caller on an empty carrier; Refusal message echoes unbounded caller-supplied value; Outcome conflates no-carrier with nothing-omitted",
      "touched_paths": [
        "plugins/saga/scripts/plan_pre_answers.py"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F37",
        "F41"
      ],
      "fix_id": "fix-59c7c02e9c83",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "Question-suppression rule stated at intake, absent at point of use; Undefined internal code P-D3 leaks into shipped skill prose",
      "touched_paths": [
        "plugins/saga/skills/plan/SKILL.md"
      ]
    },
    {
      "autofix_class": "safe_auto",
      "finding_ids": [
        "F26",
        "F27"
      ],
      "fix_id": "fix-fb69a7a42548",
      "owner": "review-fixer",
      "requires_verification": false,
      "summary": "KTD3 constructed fixture duplicates the legacy test it extends; Two tautological assertions in the marker-triple contract pin",
      "touched_paths": [
        "tests/test_plan_artifact_conformance.py"
      ]
    }
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
          "machine-readable-output-actionable-errors"
        ],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      "api-contract": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 7.5,
        "failing_dimensions": [
          "serialization-errors"
        ],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      "architecture-maintainability": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 7.428571428571429,
        "failing_dimensions": [],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      "correctness": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 8.4,
        "failing_dimensions": [],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      "documentation-clarity": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 6.0,
        "failing_dimensions": [
          "shipped-behavior-parity",
          "completeness-audience-prerequisites",
          "runbook-safety-rollback-links-generated-drift"
        ],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      "security": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 7.5,
        "failing_dimensions": [],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      },
      "testing": {
        "accepted": false,
        "delta_check": null,
        "derived_overall": 5.6,
        "failing_dimensions": [
          "requirements-regression-coverage",
          "behavior-sensitive-assertions",
          "realistic-seams-mocks-integration-evidence"
        ],
        "reviewed_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
      }
    },
    "review_incomplete_reason": null,
    "score_regressions": [],
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
  "resume_transitions": [
    "dispatch_repairs"
  ],
  "revision_binding": {
    "best_available_revision": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
    "lens_revisions": {
      "agent-usability": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "api-contract": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "architecture-maintainability": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "correctness": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "documentation-clarity": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "security": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9",
      "testing": "5ec8ea7682706aa9f06e359c373cfd2032ee6ba9"
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
}
```
