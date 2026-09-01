# Document review — WK2–WK4 gate-integrity, tiers, and maintenance plan (issues #928, #929, #930)

The plan is not ready to drive `cp919-worker-2`. The mutation-proof restore step as written will wipe uncommitted unit work, and U2's no-inheritance proof cannot run against the live spawn surface.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-30-saga-work-928-930-gate-integrity-tiers-maintenance-plan.md` |
| reviewed revision | working tree on `work/cp919-saga-work-improvement` at base `1c1c04a9`; plan is uncommitted (602 lines) |
| blocked status | **yes** — two P1 findings remain. `/work` blocks until they are repaired or explicitly overridden. |
| applied fixes | none. The review brief forbids editing the plan. |
| review artifact path | `docs/reviews/2026-08-30-saga-work-928-930-gate-integrity-tiers-maintenance-plan-doc-review.md` |
| linked issues | [infiquetra/infiquetra-claude-plugins#928](https://github.com/infiquetra/infiquetra-claude-plugins/issues/928), [#929](https://github.com/infiquetra/infiquetra-claude-plugins/issues/929), [#930](https://github.com/infiquetra/infiquetra-claude-plugins/issues/930) |
| linked parent | [infiquetra/infiquetra-claude-plugins#919](https://github.com/infiquetra/infiquetra-claude-plugins/issues/919) |
| pass | 2 of 2 (this document only) |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

A worker can serialize U1 then U2 then U3, keep custody on `work/SKILL.md`, leave the cc-workflows seam and second-opinion block alone, and name the three W-D6 pins. That is not enough.

Two load-bearing proofs cannot be executed as written. The three-step mutation protocol requires a clean `git diff` against the pre-mutation state and does not say to commit or stash the implementation first, so a `git restore` on this Muse Spark Build Auto worker wipes the feature. U2 then asks pytest to set a host session tier and observe dispatched `Agent`/`Task` options against a spawn path that is skill prose only, with no Python module on the file list.

OQ2's default is correct and matches the just-amended W-D7. OQ1 and OQ4 have followable defaults. OQ3 is safe against invention and unsafe against issue #930's "all six corrected or removed" AC. This review does not answer OQ1–OQ4.

## Remaining findings by priority

| id | priority | status | claim |
| --- | --- | --- | --- |
| D1 | P1 | open | Mutation-proof restore via clean `git diff` is not safely achievable as written |
| D2 | P1 | open | U2's no-inheritance test and mutation proof have no live spawn surface |
| D3 | P2 | open | OQ3's default can leave #930's six-item AC unmet, and the unlocated command stub can walk into §1.5 |
| D4 | P2 | open | U2's premium-choice happy path has no Work spawn-site trigger |
| D5 | P2 | open | U1's `change_kinds` "real derivation" test has no Python derivation to assert against |
| D6 | P2 | open | R14 and U3's file list are wider and narrower than #930's actual refs |
| D7 | P2 | open | U3's `TRANSITIONS` derivation does not name the post-merge slice |
| D8 | P2 | open | U3's first-time-move mutation is in the test scenarios but not in the protocol's named list |
| D9 | P2 | open | R1's clean CLI refusal is not how `main()` handles a raw `ValueError` today |
| D10 | P3 | open | `performance` on U2 stretches that lens's trigger |
| D11 | P3 | open | Preflight still says #919 lists the nonexistent `artifact_pointer.py` path; the just-amended parent no longer does |

## Issue-phase rubric review

Classification: issue-derived plan under `docs/plans/`, origin #928/#929/#930, parent #919. Issue-phase rubrics apply. All three core rubrics applied. All three extras applied: three serialized units, named file custody, and a hard predecessor (#927).

Rubric findings are not reclassified as readiness findings. D2 independently meets the acceptance-criteria REVISE criterion (the no-inheritance AC names a host-tier assertion the tree cannot host). Readiness treats the same gap as P1.

| rubric | score | note |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 7/10 | Named tests and four protocol mutations are reviewer-testable on paper. U2's host-tier assertion and OQ3 versus #930's six-item AC are not. |
| `devils_advocate_issue` | 8/10 | No hidden refactor. Serialization and the refused second worktree are correct. U2 overclaims a dispatch function the tree does not have. |
| `spec_fidelity` | 8/10 | Descent is #919 W-D3/W-D5/W-D6/W-D7 plus #928/#929/#930. OQ2 aligns with the just-amended W-D7. R14 expands #930's saga-scoped path fix. |
| `context_completeness` | 8/10 | U1 pins and line numbers match `1c1c04a9`. U2 names no Python module. U3 leaves three of six sentences unlocated and omits `resume/SKILL.md`. |
| `issue_sizing` | 8/10 | Three units, one contended file, no false parallel worktree. Right-sized as a serialized lane. |
| `prerequisite_mapping` | 8/10 | WK1 → U1 → U2 → U3 is explicit. U2's data dependence on U1's work-session field is real. U3 depends on WK1 for the `/loop` sentence. |

## Unit boundaries, custody, proofs, lenses, pins, questions

**Boundaries.** U1 → U2 → U3 matches #919. U2 really depends on U1: KTD8 records the resolved tier in the work-session field U1 adds. U3 correctly refuses a second worktree because it still edits `work/SKILL.md`. No unit is authorized to start before #927 merges.

**Custody.** U1's paths and line numbers match the live tree: `parse_gate_verdict` at `saga.py:1324`, the unvalidated assignment at `:1527`, dual `--doc-review-override` at `work/SKILL.md:243` and `:889-890`, `issue_progress.py:85` and `:134`. U2's file list is only `work/SKILL.md`, `execution-strategy.md`, a new test, and release surfaces — no spawn helper. U3 cites `:913-918`, `:820`, `:258`, and `loop/SKILL.md:188` correctly, and omits `resume/SKILL.md`, which the just-amended #930 files list names.

**Mutation proofs.** The issue-named targets are the right code: delete the `parse_gate_verdict` call, delete the `raise` in `_override_line`, remove the tier resolution step. The protocol that wraps those targets is not safely executable (D1). U2's named mutation has no single code location (D2). U3 adds a teardown mutation the issue did not require, and a first-time-move mutation that is not on the protocol list (D8).

**Lenses.** Every named id exists in `lens-roster.json`. The always-on four are listed. The union table for one integrated Code Review matches #919. `previous-comments` as `~` matches that lens's trigger. `performance` on U2 is the only stretch (D10).

**Anti-regression pins.** The three W-D6 behaviours are the right ones. Merge confirmation is `--operator-confirmed` on `merge` and `branch_delete` at `work/SKILL.md:914-916`, with the hard boundary at `:929-931`. The four typed outcomes are already pinned by `tests/test_work_review_contract.py:54`. Programmatic-review-writes-nothing lives at `code-review/SKILL.md` §5.7 (`:535-555`). Extending the existing Work contract test to also read that section is achievable.

**Forbidden surfaces.** The plan does not schedule edits to `work/SKILL.md` §1.5 (`:317`), the second-opinion block (`:90-126`), `config/sdlc-schema.json`, or `infiquetra-sdlc`. Phase 3 (`:677-691`) is not expanded. `AUTO_CORRECT_OP_KINDS` is not re-widened. `tier_policy.json` is read-only. `engine-registry.yaml` is not deleted. Residual risk is OQ3's unlocated command stub versus §1.5 (D3).

**Open-question defaults.** OQ1 (`mechanical`) is stated and followable; the "least costly in both directions" claim is overstated because under-tiering is one of #929's two failure modes. OQ2 (assert nothing) matches the just-amended W-D7 and is safe. OQ3 (preflight, record non-findings) is safe against invention and not safe against #930's AC (D3). OQ4 (keep `--doc-review-override`) is the safe compatibility default.

**Operator-verified facts, not re-derived.** W-D7 was corrected because `binds nothing` has zero occurrences under `plugins/saga/`, and the Workflow-prose trigger already fired when #925 closed. OQ2 caught this and was right. The executing worker is `cp919-worker-2` on OpenCode Go, Muse Spark 1.2 Contributor, Extra High, Build Auto. The plan names that binding at lines 62 and 68–71.

## Triggered lenses

Security/ops scrutiny applies: U1 changes a merge-gate input and a waiver path. No secrets or new credentials are in scope. Founder-review was not triggered. Deployment readiness was not triggered; Verify remains post-merge plus deploy-or-artifact per W-D2, and this plan does not touch that contract.

## Spot-checks against the pinned tree

Verified in `/Users/jefcox/workspace/infiquetra/orch-claude-plugins-919` at `1c1c04a9`.

- `parse_gate_verdict` is at `saga.py:1324` and raises `ValueError` for a missing colon, one colon, or a state outside `{done, in-progress, blocked, failed, halted, not-reached}`. It splits on the first two colons, so a ref with colons survives.
- `_build_save_saga` assigns `list(args.gate_verdict)` at `:1527` with no parse call. `save()` writes the envelope first, then `state.json`. Validating inside `_build_save_saga` before `save()` is the right placement.
- `main()` (`saga.py:1683-1690`) catches `SagaSaveError` and `SagaTickIndexWriteError`, not a raw `ValueError` from the parser.
- `status_card.py:278-279` swallows `ValueError` from the parser. `work/SKILL.md:722-726` describes that silent drop. Deferred, correctly.
- Dual flag: `:243` (doc-review gate) and `:889-890` (code-review/staleness gate) both use `--doc-review-override`. `issue_progress.py:85` renders `doc review override`. The flag is at `:134`.
- No `Agent(`, `Task(`, or `model:` appears in `work/SKILL.md`. Phase 2 dispatch (`:644-648`) is prose. There is no Python Work build-unit spawn function.
- Premium-choice / worth-it lives in `plan/SKILL.md` and `execution_spec.py` (`validate(require_receipts=True)`). No "premium" in `work/SKILL.md`.
- `requires_hard_test_gate` is at `lifecycle_state.py:111` and only consumes a list. Derivation is prose in `test-and-gates.md:73-74`. No Python derives `change_kinds`.
- `execution-strategy.md:81` hardcodes the mechanical executor to haiku. That is a different mapping from KTD7's undeclared build unit → `mechanical` → sonnet/medium in `tier_policy.json`.
- Ceremony prose `:913-918` names `merge`, `checkout_main`, `pull`, `branch_delete` and omits `teardown`. `ship_ceremony.TRANSITIONS` (`:153-162`) is eight items; the post-merge tail is the last five.
- `loop/SKILL.md:188-189` still says the first-time forward move belongs to `/work`. `work/SKILL.md:258` is the "Skip silently" line under §1.3b. `:819-822` is the gated-versus-allowlisted conflation. `AUTO_CORRECT_OP_KINDS` is empty at `reconcile_controller.py:90`.
- Certificate comment at `:754` (`issue-progress-comment`, tier `additive`, `always_operator=False`) is accurate against `reversibility_certificate.py`. Do not "correct" it.
- Bare `artifact_pointer.py` in saga skills: `work/SKILL.md:730`. `resume/SKILL.md:185-186` and `:199` use the bare name; `:190` already has the full path. `CLAUDE.md:39` and `canary_registry.json:44` already use the true path. No file exists at `plugins/saga/scripts/artifact_pointer.py`.
- Four typed outcomes at `work/SKILL.md:860`. `tests/test_work_review_contract.py` reads only `work/SKILL.md`. It also forbids `P0`/`P1` tokens in that file (`:102`).
- §1.5 starts at `:317`. Second-opinion starts at `:90`. Phase 3 is `:677-691`.

## Decisions taken without asking

1. Do not edit the plan. The brief forbids it.
2. Do not answer OQ1–OQ4. Assess whether each stated default is safe.
3. Do not re-derive W-D7 or the worker binding. The operator already verified both.
4. Do not write the board, commit, or push.
5. No external-reviewer panel. The brief asked for one installed document review, not a cross-engine pass.
6. Report-only second-opinion: D1–D11 are assigned; no `external_opinion` is recommended.
7. Write this artifact because a formal rubric review ran and P1 findings remain.

---

### D1 — Mutation-proof restore via clean `git diff` is not safely achievable as written

**Priority:** P1

**Where:** plan Mutation-proof protocol (lines 499–510).

**What is wrong.** Step 2 requires restoring the mutation exactly, verified by a clean `git diff` against the pre-mutation state. The plan never says to commit or stash the implementation first. On an uncommitted unit, `git restore` / `git checkout --` returns the file to `HEAD` (`1c1c04a9` plus WK1), which deletes the feature. The subsequent `git diff` is clean for the wrong reason.

**Why it matters.** The executor is Muse Spark 1.2 Contributor at Extra High in Build Auto. A literal reading of the protocol destroys U1's parser call and `_override_line` helper, U2's resolution prose, and U3's `teardown` sentence. The named mutations are the right targets; the restore step is not mechanical as written.

**Suggested repair.** Require a commit or a named stash of the implementation before the mutation, then restore to that ref, then require `git diff` against that ref — not against `HEAD` from before the unit. Keep the three named issue mutations. Do not leave the restore command implicit.

### D2 — U2's no-inheritance test and mutation proof have no live spawn surface

**Priority:** P1

**Where:** plan U2 Approach and Test scenarios (lines 339–361); Files (lines 325–331); issue #929 Tests / AC.

**What is wrong.** R8 and the no-inheritance scenario require setting a host tier different from the plan tier and the policy default, then asserting the dispatched tier. The mutation is "removing the resolution step." Phase 2 dispatch is LLM prose at `work/SKILL.md:644-648`. There is no `Agent(` / `Task(` / `model:` in that skill, and no Python Work spawn function. U2's file list has no module that could accept a host argument and ignore it.

**Why it matters.** A pytest cannot set the host session model or observe an `Agent` dispatch. The worker will invent a resolver (new file, not in Files, and #929 forbids rebuilding tier machinery), write a grep pin that does not prove no-inheritance, or fail. "Positively rather than by inspection" contradicts what the tree allows. Existing Work contract tests (`test_work_review_contract.py`) read skill text.

**Suggested repair.** Name the testable seam before implementation: either a small existing-chain wrapper on the U2 file list whose signature accepts and ignores a host, or an explicit prose-contract pin that #929's AC is willing to accept. Do not describe a host-session experiment pytest cannot run.

### D3 — OQ3's default can leave #930's six-item AC unmet, and the unlocated command stub can walk into §1.5

**Priority:** P2

**Where:** plan OQ3 (lines 575–579); R13 (lines 161–162); U3 Files (lines 381–383); issue #930 AC.

**What is wrong.** Issue #930 requires the `/qa` preamble, the gated/allowlisted conflation, the stale certificate comment, the command stub, and the skip-silently line all corrected or removed. The plan locates three and leaves three unnamed. The default is: repair what can be evidenced, record the rest as non-findings. Parent #919 requires each child's own AC. A worker who records three non-findings can ship with the child AC unmet. The unlocated "command stub" has no §1.5 exclusion; that section starts at `:317` and is full of bash blocks.

**Why it matters.** OQ3 is safe against inventing a false correction. It is not safe against closing #930, and it is the one place this plan can still touch the cc-workflows driver seam W-D5 forbids rewriting.

**Suggested repair.** Keep the no-invention default. Gate #930 close on either named sentences or an operator-accepted non-finding list. Add an explicit "do not edit §1.5 while hunting the command stub" line to U3 Files.

### D4 — U2's premium-choice happy path has no Work spawn-site trigger

**Priority:** P2

**Where:** plan R10 (line 151); U2 test scenarios (line 359).

**What is wrong.** The premium-choice / worth-it boundary fires in `/plan` and `execution_spec.py` under `validate(require_receipts=True)`. Work's Phase 2 path has none. A test looking for a Work trigger will invent one or pin absence while calling it a happy path.

**Why it matters.** R10 is "keep the boundary where it fires today." That is an anti-edit of `plan/SKILL.md` and `execution_spec.py`, not a new Work assertion. A Muse worker who treats the scenario as a Work spawn test will add a questionnaire or a receipt check #929 forbids.

**Suggested repair.** Rewrite the scenario as a negative: U2's diff does not touch `execution_spec.py` or `/plan`'s worth-it step, and `validate(require_receipts=True)` still fails the same premium inputs. Do not ask Work to fire the boundary.

### D5 — U1's `change_kinds` "real derivation" test has no Python derivation to assert against

**Priority:** P2

**Where:** plan R3 (lines 130–131); U1 Approach (lines 283–285); U1 test scenarios (line 301); issue #928 Tests.

**What is wrong.** `requires_hard_test_gate` only consumes a sequence (`lifecycle_state.py:111`). Derivation is skill/reference prose (`test-and-gates.md:73-74`). No Python function produces `change_kinds`. "Asserted against the real derivation rather than a fixture" and "Nothing derives it a second time" together forbid the only two ways a pytest could check equality.

**Why it matters.** The record-in-the-writeup requirement is implementable. The proof as specified is either tautological (`f(x)==f(x)`) or a new helper #928's "no new validation machinery" and R16 would have to stretch to cover.

**Suggested repair.** Pin the writeup field and that the same list is what the skill says to pass into `requires_hard_test_gate`. Drop "real derivation rather than a fixture," or add a named existing function to the file list if one is intended.

### D6 — R14 and U3's file list are wider and narrower than #930's actual refs

**Priority:** P2

**Where:** plan R14 (line 164); U3 Files (lines 385–386); issue #930 Files expected / Verification.

**What is wrong.** Just-amended #930 says the bare refs to repair live in `work/SKILL.md` (1) and `resume/SKILL.md` (3), and that `resume/SKILL.md:190` is already the full path. Live tree: bare name at `work/SKILL.md:730` and at `resume/SKILL.md:185-186` and `:199`. U3's file list does not name `resume/SKILL.md`. R14 says "everywhere it is named," which includes `canary_registry.json`, team-execution docs, CHANGELOG, and tests that already use the true path or the bare filename on purpose.

**Why it matters.** A worker following Files can leave resume's bare names in place and fail #930's `plugins/saga/` grep. A worker following R14 can edit team-execution and tests this unit does not own.

**Suggested repair.** Put `plugins/saga/skills/resume/SKILL.md` on the U3 file list. Bound R14 to `plugins/saga/`, matching #930's verification grep. Do not edit `canary_registry.json` or team-execution.

### D7 — U3's `TRANSITIONS` derivation does not name the post-merge slice

**Priority:** P2

**Where:** plan KTD9 (lines 234–238); U3 test scenarios (line 414).

**What is wrong.** KTD9 correctly names the post-merge tail of five: `merge`, `checkout_main`, `pull`, `branch_delete`, `teardown`. The test scenario says the expected set is derived from `ship_ceremony.TRANSITIONS` and not written literally. `TRANSITIONS` is eight items (`ship_ceremony.py:153-162`). `set(TRANSITIONS)` against prose that only names the tail is a self-failing test.

**Why it matters.** A Muse worker will either hard-code the five names (the drift KTD9 forbids) or assert the whole tuple and fail a correct prose edit.

**Suggested repair.** Say `TRANSITIONS[-5:]` or "the post-merge tail after `request_review`" in the test scenario. Keep the "no hand-maintained list" rule.

### D8 — U3's first-time-move mutation is in the test scenarios but not in the protocol's named list

**Priority:** P2

**Where:** plan U3 test scenarios (line 417); Mutation-proof protocol (lines 508–510).

**What is wrong.** The protocol names four mutations: parser call, `_override_line` raise, resolution step, teardown sentence. U3's test scenarios also require reinstating the first-time-move claim. Issue #930 does not require a mutation proof. The protocol says it is mandatory for every new regression guard.

**Why it matters.** A worker who follows the protocol list will skip a guard the test scenarios treat as load-bearing. A worker who follows the test scenarios will run a fifth mutation the restore protocol still does not make safe (D1).

**Suggested repair.** Either add the first-time-move mutation to the named list and give it the same commit-first restore rule as D1, or drop it from the test scenarios and keep the negative grep only.

### D9 — R1's clean CLI refusal is not how `main()` handles a raw `ValueError` today

**Priority:** P2

**Where:** plan R1 (lines 125–126); U1 Approach (lines 276–279); `saga.py:1683-1690`.

**What is wrong.** R1 wants the parser's own error text, a non-zero exit, and no envelope or index write. Calling `parse_gate_verdict` inside `_build_save_saga` before `save()` does prevent writes. `main()` does not catch `ValueError`. An unwrapped raise is a traceback and exit 1, not the `error: …` / exit 2 shape every other save refusal uses.

**Why it matters.** The worker must wrap `ValueError` as `SagaSaveError` (or catch it in `main()`) to surface the parser text cleanly. The plan never says that. A traceback still refuses the write, so this is not a correctness hole, but it is an unstated CLI contract change.

**Suggested repair.** Say: catch the parser's `ValueError` in `_build_save_saga` or `main()` and re-raise or print it as `SagaSaveError` so the existing exit-2 path carries the parser message verbatim.

### D10 — `performance` on U2 stretches that lens's trigger

**Priority:** P3

**Where:** plan lens table (line 446); `lens-roster.json` `performance` trigger.

**What is wrong.** The plan applies `performance` because tier choice is spend and #929 names cost outcomes. That lens's trigger is latency, throughput, and computational cost of the changed path, not model-spend policy.

**Why it matters.** An integrated Code Review that launches `performance` on a policy-default change will mark the lens non-applicable or score the wrong dimension.

**Suggested repair.** Drop `performance` from U2. Keep `adversarial` and `agent-usability` for the no-inheritance guarantee. The always-on four still run.

### D11 — Preflight still says #919 lists the nonexistent `artifact_pointer.py` path

**Priority:** P3

**Where:** plan Preflight (lines 103–107); issue #919 Files expected, amended 2026-08-30.

**What is wrong.** The just-amended parent now lists `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` and records the old saga path as a correction. The plan's preflight still says the parent lists the nonexistent path. The action (do not create that file; correct refs to the true path) is still right.

**Why it matters.** A worker who treats the preflight sentence as current authority may "fix" the parent issue or recreate the missing saga path. The live parent no longer needs that correction.

**Suggested repair.** Re-pin the preflight sentence to the amended #919 row. Keep "do not create `plugins/saga/scripts/artifact_pointer.py`."

## Residual risk from limited evidence

The design record in `infiquetra-agent-operations` was not re-read. Issues #919, #928, #929, and #930, as they stood when fetched in this session, were treated as authoritative. The three unlocated #930 sentences (`/qa` preamble, stale certificate comment, command stub) were not hunted beyond the plan's own citations; this review does not name them.

`tests/test_work_review_contract.py:102` forbids `P0` / `P1` tokens in `work/SKILL.md`. U1–U3 edits that introduce those tokens will fail an existing pin. That is an implementation hazard, not a plan defect.

This review did not run `scripts/gate.sh`. Line numbers are from `1c1c04a9` and will move after #927 merges; the plan already requires U3 to re-resolve.
