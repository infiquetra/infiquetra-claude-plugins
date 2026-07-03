# Code review — verify-panel robustness for failed and non-applicable panel members (#293)

**Verdict: CLEAN, not blocked.** One P1 and four P2/P3 findings surfaced by the initial 7-agent
review fan-out; all five independently validated, then fixed and re-verified before this
artifact was finalized. One additional P2 candidate was rejected at Stage B validation
(technically accurate but an already-accepted, documented tradeoff) and is recorded under
Residual Risks rather than the findings table. Zero findings from the correctness and security
lenses; the built-vs-planned audit scored 15/15 DONE with independent re-verification of every
load-bearing claim.

## Review-result contract

- **Target:** branch `fix/293-verify-panel-robustness` vs `origin/main`
- **Reviewed revision (initial pass):** `a034bb9d4c3e19db96311ad09e789f865ac3a419`
- **Reviewed revision (post-fix):** `8072ed200803f138d19f91f4c7d2ae63d5e7ea4d` (see "Fix trail"
  below for why a fresh 7-lens fan-out was not re-run against this SHA)
- **Blocked:** no
- **Mode:** programmatic, called from `/work`'s pre-PR gate; lenses and validators run at
  Opus tier per explicit operator instruction for this `/work` invocation
- **Linked issue:** infiquetra/infiquetra-claude-plugins#293
- **Linked plan:** `docs/plans/2026-07-03-verify-panel-robustness-plan.md`
- **Linked readiness review:** `docs/reviews/2026-07-03-verify-panel-robustness-plan-readiness.md`
- **Linked work-session:** `docs/work-sessions/2026-07-03-verify-panel-robustness.md`

## Scope check

**CLEAN.** Intent (plan + 7 commit messages): implement the two-kinds contract (static
non-applicability vs. runtime failure) across Layer A (`execution_spec.py` emitted verify-panel
reconciliation) and Layer B (team-execution reviewer-consensus dimension scoring), per U1-U5.
Delivered: exactly that — 18 files, all inside the plan's stated scope (core fix, doc, tests,
release surfaces, journal). No scope creep, no missing requirement, per independent
built-vs-planned audit.

## Plan-completion audit (independent re-verification, not self-reported)

| Requirement | Status | Evidence |
|---|---|---|
| U1/R12 — shared reconciliation helper, behavior-preserving | DONE | `_emit_panel_reconciliation` (`execution_spec.py:909`); commit `177ca21`'s diff to `tests/test_workflow_emitter.py` is **empty** — verified via `git show`, not the commit message |
| U2/R1,R3,R4,R5 — recompute over reporters, floor, missing-log | DONE | `execution_spec.py:954-990`; 64 emitter tests pass incl. 7 new missing-verifier/floor/edge-case tests |
| R10 — no regression when all report | DONE | `Math.max(1,⌈n/2⌉) ≡ (n+1)//2` and `Math.max(1,n) ≡ n` verified by hand for n=1..7, not just the plan's n=3 example |
| R13 — `verifier-disagreement:` prefix pinned | DONE | Prefix intact at `execution_spec.py:990`; `completeness_gate.py`'s `classify()` (`:201-219`) confirmed to **not** parse throw messages, matching the plan's corrected claim (not the original, disproven one) |
| U3/R14 — verify-block contract doc | DONE | `execution-spec.md` "Missing verdicts" section traces to emitted code; new KTD7-KTD10 citations confirmed to not collide with the doc's own pre-existing KTD1-KTD6 |
| U4/R7-R9 — Layer B dimension exclusion | DONE | `architecture-reviewer.md`, `consensus-protocol.md`; fabricated `8.0` default removed (one remaining `8.0/10` is an unrelated worked example, confirmed not a residual pin) |
| U5/R15 — release surfaces | DONE | Both plugin versions, marketplace, changelogs, and both drift-guard pins agree (0.50.0 / 2.9.0); `git grep` on the branch found no stale live pin |
| Journal (LEARNINGS/DECISIONS) | DONE | Both entries present, cross-referenced |

**COMPLETION: 15/15 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE.**

## Findings

| # | File | Issue | Reviewer | Confidence | Route | Status |
|---|---|---|---|---|---|---|
| 1 | `plugins/saga/scripts/execution_spec.py:954` (`_emit_panel_reconciliation`) | A malformed-but-non-null verifier verdict (e.g. `{}`, no `.refuted` array) is counted in `reported` — inflating the recompute denominator and suppressing the UNDER-STRENGTH marker — while contributing zero to `refute_count`, so it reads as an implicit uphold. KTD1's stated reason for treating this as out of scope ("existing `completeness_gate.py` malformed-output territory") is **factually incorrect**: `classify()` and every `__gate` call site run only on the unit's own structured result, never on verifier panel verdicts — nothing in the system validates verdict shape. | adversarial | 75 | gated_auto → human | **fixed** (commit `45d46b5`) |
| 2 | `tests/test_workflow_emitter.py` (`test_missing_verifier_recording_emits_runtime_failure_log` and siblings) | No test pins that the refute-throw guard (`if ({refuted_var}) {`) is unconditional on the quorum floor (KTD4 "skeptical asymmetry"). A hypothetical regression gating refutation on the floor would still satisfy every current assertion. | testing | 75 | safe_auto → review-fixer | **fixed** (commit `45d46b5`) |
| 3 | `plugins/team-execution/agents/architecture-reviewer.md:79-124` | Dimension exclusion is honesty-only and, per Stage-B validation, **more** gameable than the fabricated-default it replaced: the old N/A→8.0 default was a headwind dragging the overall toward 8.0, while exclusion removes that headwind entirely — a would-be-blocking (<7.0) score can be made to vanish from the denominator rather than fail the gate, and exclusion is explicitly exempted from the re-review path. | adversarial | 75 | advisory → human | **resolved as accepted risk** — logged in `docs/engineering-journal/DECISIONS.md#layer-b-exclusion-honesty-gap-293` (commit `8072ed2`); no runtime enforcement exists to add without a larger design change than this issue's scope |
| 4 | `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:10-38` | The B3b wording change generalizes to "Reviewers" (plural, unscoped) but only `architecture-reviewer.md` was updated to honor it — the other 9 reviewer prompts still say "average of 5 dimensions" with no exclusion mechanism, and no test guards the drift. | api-contract | 75 | manual → author | **fixed** (commit `2a0b81a`) — language now explicitly scoped to "a reviewer whose prompt defines" a precondition-bearing dimension, naming architecture-reviewer as the current instance |
| 5 | `tests/test_team_execution_consensus.py:31,44` | Two drift-guard assertions use split-token checks instead of a contiguous phrase, and the only negative guards are two literal strings — a differently-worded fabricated default would satisfy every current assertion. | testing | 75 | safe_auto → review-fixer | **fixed** (commit `702e370`) |

No P0 findings. Finding #1 was the sole P1 and the hard-gate blocker per `/work`'s Phase 5.3;
it is now fixed and independently re-verified (see "Fix trail").

## Rejected at Stage B validation

A sixth candidate (adversarial lens): "under-strength accept has no machine-detectable signal,
only `log()`" (`execution_spec.py:974-986`). The validator confirmed the technical claim —
there genuinely is no throw/return/FailureClass signal on the under-strength accept path — but
**rejected it as a reportable finding**: the plan's own Scope Boundaries (R4, plan line 389)
already knowingly accepts exactly this tradeoff ("no re-spawn / operator-escalation /
inconclusive state in v1"), and a `log()` line is a strict improvement over the prior
zero-signal state (before this diff, missing verifiers produced no signal at all). This is an
already-documented, eyes-open residual risk, not an undisclosed defect. Retained below under
Residual Risks rather than in the findings table.

## Coverage

- **Suppressed count:** 1 — a maintainability-lens observation (confidence 50, P3) that
  `plugins/saga/scripts/execution_spec.py`'s own inline comments mixed two independent KTD
  numbering namespaces (the pre-existing campaign-level scheme and this diff's plan-level
  scheme, both using the same numbers for different decisions within the same file — the exact
  pattern already caught and fixed in `execution-spec.md` during authoring, but missed inside
  `execution_spec.py` itself). Below the confidence-75 report gate; **fixed anyway** in commit
  `45d46b5` (new citations prefixed "plan KTDn" to disambiguate from the file's own
  longer-running scheme) since it was cheap and the fix pass touched the same lines regardless.
- **Residual risks (non-gating):**
  - Under-strength silent accept (rejected finding, above) — plan-accepted tradeoff, KTD2/R4.
  - `log()`'s actual operator-visibility is a harness-level property this repo cannot verify
    (security lens) — noted, not actionable here.
  - Raw `unit_id` interpolation into emitted JS template literals/comments without `_js_string`
    escaping (security lens, confidence ~40, suppressed): pre-existing pattern (the old throw
    already interpolated `unit_id` raw), and `unit_id` originates from the trusted
    execution-spec authoring process, not external/attacker input — no attacker-controllability
    established.
- **Testing gaps:** #2 and #5 above; both are additive (new assertions), neither requires
  behavior change.

## Lenses run

correctness, security, testing, maintainability/conventions (4 always-on) + api-contract
(message-format contract change + two plugin version bumps) + adversarial/red-team (≈200-line
core diff to a consensus/trust-gating mechanism) — all spawned as `saga:readonly-verifier` +
`isolation: worktree` at `model: opus` per this session's explicit operator instruction. A
dedicated built-vs-planned audit ran in parallel with the lenses (not sequentially), same tier
and sandboxing. All 5 Stage-B-eligible findings were independently validated by a fresh
`saga:readonly-verifier` agent (also Opus) with no access to the original lens's reasoning; 5 of
6 candidates confirmed, 1 rejected with recorded rationale.

## Fix trail

Operator chose "fix now, same PR" for the P1 and "fix all four, batched" for the P2/P3s over
deferral, given the fixes were small and mechanically localized to surfaces this PR already
touches.

- **#1** — broadened the missing-detection predicate in the one shared
  `_emit_panel_reconciliation` helper from `v == null` to
  `v == null || !Array.isArray(v.refuted)`; a malformed verdict is now excluded from `reported`,
  recorded in `missing_idx`, and can no longer inflate the recompute denominator. KTD1 corrected
  in place in the plan and `DECISIONS.md`, with the pre-correction version preserved in
  `ARCHIVE.md` as superseded. New test:
  `test_malformed_verdict_treated_as_missing_not_implicit_uphold`.
- **#2** — two new tests (`test_refute_throw_guard_is_unconditional_on_quorum_floor`,
  `test_iterate_throw_at_max_iterations_is_unconditional_on_quorum_floor`) pin the throw guard's
  literal shape so a floor-gated regression would fail them.
- **#3** — no code change; logged as an accepted-risk `DECISIONS.md` entry
  (`#layer-b-exclusion-honesty-gap-293`) with a revisit-when condition, since Layer B has no
  scoring engine to add counter-pressure to without a design change beyond this issue's scope.
- **#4** — `consensus-protocol.md`'s B3b block and opening paragraph now explicitly scope the
  exclusion mechanism to "a reviewer whose prompt defines" a precondition-bearing dimension,
  naming architecture-reviewer as the current instance.
- **#5** — tightened the two split-token assertions to the contiguous `"avg of 4 applicable"`
  phrase and added a regex guard (`N/A\s*\(\d`) against a reworded fabricated numeric default.

**Verification approach.** Rather than re-running the full 7-agent lens fan-out against the
post-fix SHA, a single dedicated verification agent (Opus, `saga:readonly-verifier`) was
dispatched to falsify each fix directly: re-derive the n=3 malformed-verdict scenario by hand
under the new predicate, confirm the two new throw-guard tests would actually fail against the
hypothetical regressed guard text they're meant to catch, trace the tightened regex against a
reworded fabricated-default string, and confirm the KTD1/DECISIONS/ARCHIVE cross-references
resolve and are internally consistent. All five findings independently confirmed closed
(`{"refuted": [], "upheld": ["F1","F2","F4","F5","docs"]}`). Full suite (1835 tests), `ruff`,
and `mypy` re-ran clean post-fix. This is treated as equivalent-or-stronger evidence to a fresh
lens pass for this fix set — bounded to the findings the first pass already scoped precisely,
with no new surface area introduced by the fixes themselves.
