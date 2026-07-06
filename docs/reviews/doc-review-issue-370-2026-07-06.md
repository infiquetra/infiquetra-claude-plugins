# Doc Review — Single-source tier palette (#370)

**Target:** `docs/plans/2026-07-06-tier-vocab-single-source-plan.md`
**Reviewed revision:** working tree (plan uncommitted on `main`)
**Reviewer:** `/doc-review` (readiness-skeptic pass; plan-phase artifact)
**Blocked:** **NO** — all P1 findings resolved via in-place safe fix; residual findings are P2/P3, non-blocking.
**Linked:** issue #370 · plan `docs/plans/2026-07-06-tier-vocab-single-source-plan.md` · saga `issue-370` · outcome leaf `sub-370` (`tier-effort-first-class`)

## Readiness summary

The plan is ready to drive implementation. Its core strength is that it **reconciled #370's pre-#362/#363
letter against the merged tree** rather than transcribing it — that reconciliation is verified correct
against real line numbers. The review's value-add was pressure-testing the reconciliation's own claims:
one ("AC9 done") was an overclaim against the AC's literal grep, and one (AC1's "zero bare literals") is
unachievable as literally worded against 205 real Python occurrences. Both were pinned in place.

## Applied fixes (in place)

| # | Fix | Evidence |
|---|---|---|
| 1 | Reconciliation table AC9 row: **DONE → "intent met, literal check off"** | grep `^MODELS = ` matches the re-export alias `execution_spec.py:61-62` |
| 2 | U1: added effort-ceiling anchor (haiku=high, others=xhigh default) + verify-at-build note | AC5/AC6 canonical example is `haiku`/`xhigh` |
| 3 | U1: added AC9 resolution instruction (tighten grep to tuple-literal, or record re-export as compliant) | AC9 verification command vs re-export form |
| 4 | U4: pinned scan surface to **Python dispatch-logic / tier-value literals**, excluded `.md` frontmatter | 205 `.py` occurrences + 33 deferred `.md` frontmatters verified |
| 5 | U6 + KTD6: corrected saga-bump from conditional to **unconditional** (U2/U3 change `execution_spec.py`) | `segment_units` + `Tier.validate` are saga scripts |

## Findings by priority

| ID | Pri | Finding | Status |
|---|---|---|---|
| A | P1 | **AC1/U4 bare-literal guard is unachievable as literally worded.** "Zero bare model-literal strings outside the module" collides with ~205 legitimate Python occurrences (e.g. `team_emitter.py:53-56` uses model names as work-shape dict keys) + 33 deferred `.md` agent frontmatters. Scan surface + exception rule were undefined. | **Fixed in place** — scoped to Python dispatch-logic / tier-value literals, `.md` excluded, AC1 reinterpreted, anchored on the `execution_spec.py` example. Exact predicate is now an explicit, forcing-function-guarded U4 build decision (red-before/green-after), not a hidden gap. |
| H | P2 | **AC9 "done" overclaim.** The re-export satisfies AC9's intent (no inline tuple) but AC9's grep `^MODELS = ` matches the alias line, so the AC's own verification reports a match. | **Fixed in place** — reconciliation corrected; U1 instructed to tighten the check or document the re-export as compliant. |
| C | P2 | **models.json effort-ceiling values unspecified.** Only `haiku`/`xhigh` is implied by the issue; opus/sonnet/fable ceilings undefined. | **Fixed in place** — anchor added (haiku=high, others=xhigh default) with a build-time verification note; not invented as settled fact. |
| E | P2 | **Release-surface conditionality wrong.** U6/KTD6 said saga bumps "only if" — but U2/U3 modify `execution_spec.py` behavior, so saga bumps unconditionally. | **Fixed in place.** |
| B | P2 | **R8/KTD5 team-execution vocabulary guard target is genuinely ambiguous.** The `/plan` table is already guarded; the team-execution "worker table" is an illustrative template, so exactly which tokens the guard checks is a real design call. | **Residual** — bounded by KTD5's fallback ("guard the displayed vocabulary tokens"); implementer resolves the exact predicate at build. Non-blocking. |
| G | P3 | **AC8 CLI `--check` vs test.** #370 names `tier_catalog --check`; a pytest (`-k tier_catalog_check`) satisfies AC8 with no new CLI. | **Residual** — plan already permits "a `--check` mode or CI test". |

## Residual risk from limited evidence

- **B** and the U4 exact predicate (**A**'s residual) are the two spots where the implementer still exercises
  judgment. Both are scoped and guarded by a failing-first test, so the forcing function catches a
  wrong call — but they are the areas `/work` and the eventual `/code-review` should scrutinize hardest.
- The effort-ceiling values (**C**) are factual data about model capabilities the plan cannot invent; the
  anchor (haiku=high) is issue-sourced, the rest is a default to confirm at build.

## Verdict

**Not blocked.** The one P1 was a real requirement-wording defect (AC1) plus an overclaim (AC9), both caught
by verifying the plan's claims against the repo rather than trusting them — now pinned in place. `/work #370`
may proceed; carry findings **A** (U4 scan predicate) and **B** (team-execution guard target) as the two
build-time decisions to nail, and honor the AC1/AC9 reinterpretations rather than the issue's literal
verification commands.
