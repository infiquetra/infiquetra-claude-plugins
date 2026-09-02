---
kind: doc-review
target: docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md
classification: plan, issue-derived
reviewed_revision: a0e343799beea2e47414cafbcd83f22a5328c836
reviewed_revision_plan_sha256: 1cfa8b55f9d9e18d9d0d3a5051f7cf426eda745534f56ea6bdc5d63e8c349fcb
authoritative_artifact: docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/907
blocked: true
outcome: not-ready
applied_fixes: none
pass: broad
---

# Document review — issue 907 terminal-validation repair plan

The plan is not ready to drive implementation. Three units that exist to prevent the last two mirror-image repairs still specify one-sided proofs.

| field | value |
|-------|-------|
| target path | `docs/plans/2026-09-01-issue-907-terminal-validation-repair-plan.md` |
| reviewed revision | `a0e343799beea2e47414cafbcd83f22a5328c836` (clean tree; the commit that records the plan) |
| plan SHA-256 | `1cfa8b55f9d9e18d9d0d3a5051f7cf426eda745534f56ea6bdc5d63e8c349fcb` |
| frozen source revision the plan repairs | `dd3593ab7263541ef1ad87e69f2366f64a724d33` |
| classification | Plan, under `docs/plans/`, issue-derived from 907. Issue-phase rubrics applied. |
| review type | One broad Saga Document Review. No external-reviewer panel. Report-only; no dispatch. |
| linked issue | [infiquetra/infiquetra-claude-plugins#907](https://github.com/infiquetra/infiquetra-claude-plugins/issues/907) |
| authoritative findings artifact | `docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json` |
| blocked status | **yes** — three P1 findings remain |
| applied fixes | none. Operator contract forbade editing the plan. |
| review artifact path | `docs/reviews/2026-09-01-issue-907-terminal-validation-repair-plan-document-review.md` |
| readiness verdict | `not-ready` |
| override rationale | n/a |

## Applied fixes

None. Safe in-place edits were disabled by the review brief.

## Readiness summary

Not ready. U3, U4 and U6 each name a both-sides invariant and then specify a test, a runbook step, or a retry that only holds on one side.

The ledger arithmetic the coordinator already verified is accepted and was not re-counted. Root causes for the composer rule, the resend dead store, the `already has tab` wedge, and the floor-then-exec ingest are real causes, not restated symptoms. Duplicate-of grouping did not merge two distinct defects into one unrepaired row. U11 through U14 may omit root-cause and mutation sections.

What is not safe to implement is the launch-path contract those three units would write next.

## Remaining findings

| id | priority | status | title | plan anchor |
|---|---|---|---|---|
| D1 | P1 | open | U3 owned-prompt guard count contradicts KTD4 | plan:268 |
| D2 | P1 | open | U4 reproducer and one-read counter-case cannot both hold | plan:294 |
| D3 | P1 | open | U6 retry through `launch()` orphans the created tab | plan:371 |
| D4 | P2 | open | U6 mermaid says clean leaves every staged tab open | plan:147 |
| D5 | P2 | open | U9 notice names a writing version the unit forbids storing | plan:492 |
| D6 | P3 | open | TEST-10 and TEST-11 close under one unit while landing in three | plan:438 |
| D7 | P3 | open | Independence sentence lets U8 start before U6 and U7 | plan:656 |
| D8 | P3 | open | KTD10 understates the merge-first cost | plan:99 |

### D1 — U3 owned-prompt guard count contradicts KTD4

The direction-not-fixed scenario will drive an owned first-send inspection that KTD4 and U4 both forbid.

U3's happy path is right: owned plus a first send that typed into the pane inspects on resend. The next bullet is not. It asks for an owned first send that went through `herdr agent prompt`, a second send that is unguarded, and "guard call count one, from nowhere; the loop makes zero calls" (plan:268). At `dd3593ab`, `launch()` skips the guard on an owned first send (`launcher.py:1394-1396`) and on an owned resend (`launcher.py:1419`). `used_pane` is assigned at `launcher.py:1408` and `1421` and never read. Owned plus agent-prompt is zero guard calls today and zero after KTD4's disjunction.

The mutation list at plan:272 says `if True:` must fail the owned-agent-prompt test. That kill only works if the test expects zero calls. A worker who implements the "count one" sentence will add an owned first-send inspection, fail U4's "owned session: zero inspections before the first send" (plan:309), and rebuild the last resend swap in the other direction.

**Suggested fix:** State the owned-agent-prompt expectation as zero guard calls, total and in the loop. Keep the `if True:` mutant as the proof that the unused direction stays unused.

### D2 — U4 reproducer and one-read counter-case cannot both hold

U4's evidence-before-edit cannot pass under the move that its own counter-cases require.

The stated reproducer is a pane-read sequence that is empty then staged, with send refused (plan:294). `verify_unit_identity` does not read the composer; it reads `herdr agent list` (`launcher.py:1150-1200`). On the non-OpenCode path the frozen `launch()` performs one composer inspection, before preflight (`launcher.py:1394-1408`). A sequence stub therefore yields one empty read and a write, both before and after a move of that single inspection.

Adding a second inspection makes the sequence refuse, and breaks `test_empty_reused_box_is_prompted_exactly_as_today` at `test_launcher_contract.py:619-633`, which asserts exactly one `herdr pane read --format ansi`. U4 names every `_prepare_guard_launch` test as a counter-case that must pass unchanged, "one read, one send, same receipt values" (plan:302).

Goal text says the permitting read is taken after preflight (a move). Approach text says add an inspection before send (an add). Those are different repairs. The worker cannot satisfy the failing proof and the unchanged one-read counter-case from the unit as written.

This is also the acceptance-criteria-clarity BLOCK: one unit requires two reads and forbids a second read.

**Suggested fix:** Make the evidence-before-edit an ordering assertion (guard after preflight, still one Claude read). Keep empty-then-staged only if the unit explicitly adds a second inspection and rewrites the one-read test in the same unit.

### D3 — U6 retry through `launch()` orphans the created tab

The wedge reproducer is real. The retry that is supposed to satisfy both handoff 4-C invariants is not.

At `dd3593ab`, `cmd_go` keeps identifiers on `StagedInputError` (`orchestrate.py:2697-2700`) and then skips any unit with a `tab_id` (`orchestrate.py:2681-2683`). `test_staged_input_stop_returns_the_unit_to_retryable_pending` at `tests/test_orchestrate_launch_and_land.py:426` never attempts the second `go`. Lifting that skip is the right repair for invariant (2).

Invariant (1) is the prior-validation artifact's REL-03: a session the wrapper created must stay reachable by `clean`. U6 forbids changing the launcher (plan:377). `launch()` always runs the wrapper create (`launcher.py:1350-1359`) and then overwrites `unit.tab_id` from the new receipt. The evidence-before-edit stubs `launch` (plan:371), so two launch calls stay green while a real second create drops the first owned tab off the unit.

U3's resend stop is the owned path U6 says it relies on (plan:270). After that stop, "clear the composer and rerun `go`" (plan:373) only makes sense if retry targets the same tab. A second `launch()` does not. The first created tab is then beyond `clean`, which is the mirror image this unit exists to prevent.

**Suggested fix:** Name one retry mechanism and bind both sides. Either `cmd_go` closes an owned tab before calling `launch()` again, or it re-prompts the existing tab through a named launcher entry that this plan is allowed to add. The evidence-before-edit must drive the real create path, or a test double that records whether create ran, and must assert the first owned tab is still on the unit or was closed.

### D4 — U6 mermaid says clean leaves every staged tab open

The state diagram will steer U7 toward leaking an owned staged-input tab.

The mermaid's clean transition is "tab reported left open, not closed" for every `PENDING_staged` unit (plan:147). U6's own invariant (1) and U7's invariant require an owned tab to be closeable and, on success, closed (plan:369, plan:409). The runbook sentence is more careful (unowned tabs left open) and should be the diagram.

### D5 — U9 notice names a writing version the unit forbids storing

The unknown-key notice will invent a run-file field KTD9 just refused.

U9 tells `read_unit` to drop unknown keys "with a one-line notice naming the key and the writing version" (plan:492). The same unit forbids a run-file version field (plan:496). The notice needs a stated source: Orchestrate's own running version is enough. Anything that writes a version into `.orchestrate/run.json` is a new key and repeats API-05.

### D6 — TEST-10 and TEST-11 close under one unit while landing in three

The terminal-artifact findings TEST-10 and TEST-11 each name more than one unbound line. The ledger gives each a single `repair-unit` (U9 and U3). The unit bodies split the work correctly (U5/U7/U9 and U3/U8). A worker who closes a row when its disposition unit merges will leave the other slice unproven. Say "split; remaining slice in U*" on those two ledger rows.

### D7 — Independence sentence lets U8 start before U6 and U7

The dependency table is right: U8's matrix must exercise the final `clean` (plan:648). The sentence under the table says U1, U3, U6 and U8 "could be built in any order" (plan:656). That sentence is the one a parallel worker will follow.

### D8 — KTD10 understates the merge-first cost

KTD10 says the other merge order "changes only the position of U11" (plan:99). U11 itself says every evidence-before-edit must be re-run on the merged tree (plan:552). Decision 4's cost table is the accurate one.

## Rubric review (issue phase)

Cores applied. Extras applied: the artifact is a code-change plan in a convention-heavy repo, spans fourteen units, and sits in a multi-issue run.

| rubric | score | note |
|---|---|---|
| acceptance_criteria_clarity | 6 BLOCK | U4's evidence-before-edit and one-read counter-case contradict (D2). Other unit ACs are observer-testable. |
| devils_advocate_issue | 8 | One serial repair run is what the handoff asked for. U10 and U13 stay gated on operator decisions. No speculative multi-tenant controls. |
| spec_fidelity | 7 | Descent is the planner handoff, not a spec. Defects A–H and Decisions 1–4 are represented. D3 is a fidelity miss against handoff section 4-C invariant (1). |
| context_completeness | 9 | Files, symbols, fixtures, live-capture provenance, and test homes are named. U4's missing read-count fact is the thin pointer. |
| issue_sizing | 8 | Fourteen commits in one run is large and is the requested shape. |
| prerequisite_mapping | 9 | Decisions 1–4, the `origin/main` merge, and proposed follow-up custody are explicit. The worker is told not to resolve the decisions. |

Unresolved rubric BLOCK is D2. It is not a second finding.

## What counting cannot settle — adjudicated

Root causes that hold: `_is_continuation` requiring a leading border no capture draws (`composer.py:193`); `used_pane` assigned and unread (`launcher.py:1408`, `:1419`, `:1421`); `cmd_go` keeping `tab_id` then skipping it (`orchestrate.py:2681-2700`); ingest recording a floor fault and still `exec`'ing (`orchestrate.py:1667-1678`); `close_run_session` returning `None` for an unowned tab (`launcher.py:898-900`) while `reap` treats `None` as success (`orchestrate.py:4132-4146`).

Invariants that bind both directions as written: U1's row table plus the named counter-cases (KTD2's footer-after-spacer stays `unclassifiable`; live Claude captures stay `empty`); U2's count definition; U5's named stop; U7's one close owner and unowned-not-closed; U8's command-by-state matrix (eighteen registered subcommands; `--help` tested separately); U9's snapshot restore.

Evidence-before-edit that will fail today: U1's Codex three-row truncation, CORR-02 `unclassifiable`, the deleted test absent from the tree and present at `2fe7c954`; U3's owned typed-resend (three writes, zero guards, `DELIVERY_RESENDS = 2`); U6's second `cmd_go` printing `already has tab`. U4's empty-then-staged sequence is not a frozen-revision reproducer of a moved guard (D2). U10's dispatch test is a description, but it is specific enough to write and should fail: `say` is the default sender at `orchestrate.py:1387` and `:1492`.

Mutation lists: U1's C18 is killable once the live Claude fixtures exist, because dropping the rule class lets a `─` row fall into `bordered` and swallow the status footer. U3's `if True:` kill is only sound after D1. U6's "restore identity clearing" kill binds invariant (1) at the stop, not after retry (D3).

Counter-cases: U1 restores the test the last round deleted and keeps last-block selection. U3 keeps the two unowned resend tests that the handoff proved pass under the defect. Sufficient once D1 and D2 stop rewriting those counts.

Duplicate-of grouping: API-01 / CORR-03 / REL-10 onto REL-01 are the same wedge. CORR-09 onto SEC-01 is the same condition swap. REL-09 onto SEC-02 is the same two `say` sites. The ARCH-02 message cluster is one remediation string. TEST-12 onto ARCH-12 keeps three documentation-parity tests as parity tests, which is the right remaining shape. No two distinct defects were merged such that one will go unrepaired. TEST-10 and TEST-11 are split repairs with a single ledger disposition (D6), not a wrong merge.

Unit order: the table is sound (U2 after U1; U4 after U3; U7 after U6; U8 after U7; U9 after U8; U13 after U11). U10's dependency on U3, U4 and U8 is declared. The independence sentence under the table is the only order defect (D7). U5's compile-site comment in `orchestrate.py` sits in a function U8 and U9 rewrite; loss of that comment is residual, not a finding.

Overreach: U1's prohibited list (no continuation cap, no new `ComposerState`, no last-block change) is the right refusal of CORR-07 speculation. U8's allowlist is a matrix, not a new admission-control plane. U9's unknown-key tolerance is API-05, not a version scheme, until D5 is fixed. No unit asks for defence in depth.

### U11–U14 omission of root cause, invariant, and mutation

Defensible for each, for different reasons.

U11 is a merge commit. Its proof is `git log HEAD..origin/main` empty. `origin/main` is 42 commits ahead of `a0e34379`, which matches the handoff count. A mutation section would be theatre.

U12 is journal text. The drift test and the not-reproducible wording test are the behavioural proof; a formal mutation list would only rename those tests.

U13 is two sentences gated on Decision 2. The skill-contract assertion that the documents no longer contain `nothing verifies them` / `no code checks` is enough.

U14 is the release triad plus the gate, and the repository already forbids bumping before the last code unit. The bump guard reads committed state; committing before the gate is the invariant.

## Residual risk

CORR-01's styled-wrap shape remains constructed, not live, as the plan already records. Grok, Agy and Qwen still have no capture; KTD1's accepted asymmetry and U12's residual are the honest leftover. Decision 1 left open means R5 is incomplete until the operator answers; that is declared, not a silent gap.

Identifiers in this review are this document-review's `D1`–`D8`. They are not the terminal-validation `finding_id` values. Where a terminal-validation identifier is cited above, the artifact is `docs/code-reviews/2026-08-31-issue-907-terminal-validation-result.v1.json` unless the prior-validation artifact is named in the same sentence.

No product file, plan file, review JSON, cycle state, or evidence-ledger entry was modified.
