---
title: Doc review — Give the refute-N verify panel a severity axis (#686)
type: doc-review
date: 2026-08-03
target: docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/686
blocked: false
---

# Doc review — issue #686 verify-panel severity axis

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-plan.md` |
| Reviewed revision | working tree (plan is untracked); repo `HEAD` = `aa09fcbe`; saga `0.122.0` |
| Cross-repo evidence | `infiquetra-codex-plugins` `origin/main` = `790477c`, fetched 2026-08-03 |
| Blocked | **No** — no unresolved P0 or P1 remains |
| Findings | 4 raised (2×P1, 2×P2) — all 4 fixed in place |
| Applied fixes | 6 edits to the plan, 2 to the spec, 1 harness re-emit |
| Linked issue | #686 |
| Spec | `docs/plans/2026-08-02-issue-686-verify-panel-severity-axis-spec.json` |
| Harness | `docs/plans/2026-08-02-issue-686-verify-panel-severity-axis.workflow.js` |

## Readiness summary

**The plan can drive implementation.** Every line citation in it is accurate, and the two defects
that would have produced silently-wrong work are fixed.

Verification was unusually cheap here because a working reference implementation exists: the
hand-patched harness committed at `infiquetra-codex-plugins` `origin/main` already implements the
exact contract this plan specifies. Checking the plan against that harness — rather than against its
own internal consistency — is what surfaced both P1s.

All eleven `execution_spec.py` line citations were confirmed against the file at `HEAD`. The
verbatim-port source (`1327c31`, lines 265-300) exists, is an ancestor of the downstream repo's
`origin/main`, and contains the VERDICT CONTRACT block as described. `saga` is at `0.122.0` as
claimed. The downstream committed spec carries four verify panels, so U3 is a real check rather than
a vacuous one.

## Findings

| # | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | U1's site list never says where `__advisories` is populated | Fixed in place |
| D2 | P1 | U3's acceptance check is unsatisfiable as written, and the unit is told to HALT on failure | Fixed in place |
| D3 | P2 | The plan never states that `refuted` is renamed rather than supplemented, or that `upheld` survives | Fixed in place |
| D4 | P2 | The Python prompt surface had no wording source, while the JS one was pinned "verbatim" | Fixed in place |

### D1 (P1) — the advisory accumulator is declared and returned, but never filled

U1's **Sites** list named `_WORKFLOW_RESERVED_IDENTIFIERS` (reserve the identifiers), `:3549`
(declare the array), and `:3691` (return it). It never named the place that pushes into it.

An agent working that list literally produces a harness where `advisory_corrections` is `[]` on every
run. R4 — "non-gating corrections reach the driving session" — fails silently, and the plan's own
Risk Analysis already names "advisories silently vanish" as the failure mode of a naive fix. The
document contained the trap it warned about.

The reference implementation settles both the call and its position:
`__logAdvisory("U1", U1_reported)` sits immediately after `const U1_refuted = ...` and before the
missing-verifier block. That position is load-bearing. `_emit_panel_reconciliation` **returns early**
on the `#364` unattended-climb path, at the `if (<var>_refuted) {` line — so a call appended after
that point would emit for the one-shot panel and the iterate loop but silently never for climb units.

**Fix:** the Sites list is now a numbered 1-8 sequence with the call site as site 4, giving the exact
line (`:2762`), the exact position, and the reason the position matters. A new test scenario asserts
that an `escalate_on_signal` unit still emits its `__logAdvisory` call — the only scenario that
catches a placement error on that path.

### D2 (P1) — U3 would HALT and file a false defect against U1

U3's verification diffed all `refuted|advisory` lines of a re-emitted harness against the committed
hand patch, and its escalation read "HALT and report as a U1 defect if the regenerated harness
differs behaviorally from the hand patch."

Measured 2026-08-03: that diff can never be empty. The committed harness carries prompt corrections
hand-authored *during* the codex run — `CORRECTED PREMISE …`, `MANDATORY AFTER THE RE-RENDER …` —
which appear in **zero** of the committed spec's seven unit prompts. Re-emitting the spec cannot
reproduce text that was never in the spec. Run against today's unfixed emitter the diff returns 87
lines, exactly 1 of which is unit-prompt text; that one line survives any correct fix.

So a correctly-implemented U1 would have produced a U3 that halts the run and reports a defect that
does not exist.

**Fix:** U3 is now four independent behavioral checks with an explicit pass condition — the legacy
gate count must be `0`, and the predicate / gate-arithmetic / `__logAdvisory` counts must match
across both files — followed by a residual-diff check that filters unit-prompt lines. The measured
87-line / 1-prompt-line result is recorded in the plan so the executing agent recognizes the expected
noise instead of investigating it. The commands now read both downstream files from `origin/main` via
`git show` after an explicit `git fetch`, rather than from a checkout this work does not commit to.

### D3 (P2) — "two buckets, both required" left the legacy key's fate open

`_verifier_schema()` today requires `refuted` and `upheld`. The plan's site entry read
"`_verifier_schema()` `:2575-2604` (two buckets, both required)", which is equally consistent with
*adding* two keys and leaving `refuted` in place. That would half-complete KTD2's hard cutover:
verifiers would still be required to emit a key nothing reads.

**Fix:** the site now states the exact target key set — `refuted_deliverable`,
`advisory_corrections`, `upheld`, `verifier_identity`, `fallback_depth`, `examined_sha`, all six
required — and says explicitly that `refuted` is renamed, disappearing from both `properties` and
`required`, while `upheld` survives unchanged.

### D4 (P2) — one prompt surface was pinned verbatim, the other was left to paraphrase

KTD6 correctly insists both prompt surfaces change, and the plan's top pre-mortem is that a vague
bucket boundary makes verifiers over-gate. But only the JavaScript block had a cited source. The
Python `_verifier_prompt()` and the `:707` visibility clause were named as sites with no wording
given — inviting exactly the paraphrase the plan forbids elsewhere.

**Fix:** all three passages now cite a line in the reference harness — 265-300 for the VERDICT
CONTRACT block, 263 for the visibility clause, and line 330's prompt string for the Python surface —
with the relevant sentences quoted inline. The plan also now notes that the reference is a
*hand-patched* harness, so it is a wording source only and its non-prompt text is not an emitter
target.

## Checks that passed — no finding raised

- **KTD5's claim that one predicate change fixes all three panel forms "for free" is true.** A sweep
  for every emitted consumer of the refuted boolean found exactly one occurrence of
  `v.refuted.length > 0`, at `:2749-2750` inside `_emit_panel_reconciliation`, feeding `refuted_var`
  at `:2762`. The `#364` climb reads that variable rather than recomputing. R2's "must not survive
  anywhere" is achievable with a single edit.
- **KTD4's `units` map is safe in every harness shape.** Both emission paths bind unit results at
  module scope — a lone unit as `const U1 = await agent(...)`, a parallel wave as destructuring
  `const [U2, U3] = ...` — so a final `return { units: { U1: U1, … } }` cannot reference an
  out-of-scope binding. This also independently validates KTD3: a module-level `__advisories` is
  reachable from inside a thunk where a per-unit binding would not be.
- **KTD8 is correct.** `:438` and `:2372` are sets of emitted JavaScript variable names used for
  binding-collision detection, unrelated to the verdict field of the same spelling.
- **KTD7 is honored by the spec.** None of this plan's three units carries a `verify` panel, so no
  unit is gated by the pre-fix arithmetic it exists to replace.

## Residual risk

The engine offer resolved from a stored preference (`prompt_required: false`), so no external-engine
second opinion was dispatched. No cross-family panel ran; every finding above is Claude-owned and was
verified against local repository evidence or the downstream repo's `origin/main`.

U3 remains a cross-repo probe with no test in this repo backing it. Its pass condition is now
explicit and mechanical, but it is still a one-shot manual check rather than a regression guard — if
the downstream spec or harness changes again, nothing in CI notices.
