# Doc-review: team-execution external-engine workers plan (U12 from #283)

**Target:** `docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md`
**Reviewed revision:** working tree (untracked file; repo HEAD `e901ae1`)
**Classification:** plan (`docs/plans/` tie-breaker) — readiness-skeptic pass, run inline
**Blocked status:** **NOT blocked** — no P0/P1 remains after safe fixes; `/work 318` may proceed
**Linked:** issue #318 · saga `issue-318` · origin `docs/plans/2026-07-01-external-engine-capability-routing-plan.md`

## Readiness summary

Ready to drive implementation. Every evidence citation in the grounded seam table was re-verified
against the working tree and held (resolver role kinds, dispatch adapters, dispositions, selector
validation, emitter tier-only rendering, worker-manifest reserved language, empty validator-registry
engine slot, all four named test anchors). Two would-have-been-P1 defects were found and fixed in
place: U2 targeted a tier-confirmation step that does not exist in team-execution SKILL.md (the tier
table lives in saga `/plan` SKILL.md:295-305), and U3's "default tier when unspecified" contradicted
the schema (`tier` is a required Unit field, `execution_spec.py:428`). The initial pass left two P2s
and one P3; all three were fixed in an operator-directed follow-up round the same day (see below).

## Applied fixes (all evidence-backed, edited in place)

| # | Where | Fix | Evidence |
|---|---|---|---|
| 1 | KTD1 | Corrected `resolve()` call shape — role_kind rides in the request dict; `registry` required | `engine_resolver.py:79`, `MODES` `:17` |
| 2 | KTD4 | Grounded the `substituted-engine` trigger (run-time capability resolution differs from plan-time preview — the only reachable path; named engines halt per R26); noted the chaperone builds `provenance_manifest.Manifest` directly since `build_dispatch_manifest` maps only two dispositions | `engine_dispatch.py:143-153`; resolver halt path `:234` |
| 3 | KTD4 | Cited the identity format precedent (`<engine>/<variant>`) | `engine_dispatch.py:153` |
| 4 | KTD6 + Scope | Annotated "ideation-R14 sandbox profile" with issue #287 (disambiguates the three R14s: brainstorm R14, #285-plan R14 leg, ideation seed R14) | `gh issue view 287` (OPEN, sandbox capability); requirements doc AE7 |
| 5 | U2 | Re-pointed the KTD2 intent→tier rule at the real tier table — saga `/plan` SKILL.md tier-derivation step; U2 now explicitly touches that file | `plugins/saga/skills/plan/SKILL.md:295-305,340-341`; team-execution SKILL.md has no tier step (Steps A0–A7 verified) |
| 6 | U3 | Dropped the schema-level tier default (`tier` is required in `from_dict`); KTD2 default is a plan-time heuristic row; replaced the corresponding test scenario | `execution_spec.py:428` |
| 7 | U3 + Risks | Corrected the emitter-oracle claim: no existing test asserts the 5-column shape, so U3 must **add** column-shape oracles rather than update existing ones | `tests/test_team_emitter.py:123,146-150,307,338` — id/tier/heading presence only |
| 8 | U4 | Fixed disposition-trigger cross-ref (KTD4, not KTD7) | plan-internal structure |

## Remaining findings

None. All three findings from the initial pass were resolved in a follow-up fix round
(operator-directed, same day):

| Priority | Finding | Resolution |
|---|---|---|
| P2 | Resident naming for **capability-selected** units was unspecified. | **Fixed** — KTD3 now sets the naming rule: `worker-<engine-key>` / Engine `<key>` for explicit selectors, `worker-<capability-key>` / Engine `cap:<key>` for capability routes (plan previews only what is knowable at plan time); U3 goal + test scenarios updated to match. |
| P2 | Issue #318 body drifted from the corrected plan. | **Fixed** — draft file and live issue body patched via `gh issue edit 318` (files list gains `plugins/saga/skills/plan/SKILL.md`; "tier defaulting" dropped; capability naming added to tests + acceptance criteria); verified on the live body. |
| P3 | `substituted-engine` detection was underspecified. | **Fixed** — the substitution baseline is the plan-time resolution preview recorded in the tier-table recommendation row (U2); the coordinator forwards it in the context package (U1), and the chaperone compares the run-time resolution against it (KTD4). |

## Verification notes

- KTD2 vocabulary valid: `sonnet`/`opus`/`fable` ∈ `MODELS`, `medium`/`high`/`xhigh` ∈ `EFFORTS` (`execution_spec.py:52-53`).
- Requirements mapping R10/R11/R12/R13/R14/R15/R23/R24/R26 verified verbatim against
  `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md:121-188`.
- Step B0 parse path exists (team-execution SKILL.md:269); Workers table header at `:226`.
- Both named drift-guard tests exist (`test_team_execution_plugin.py:55,78`; `test_saga_plugin.py:42`).
- `Unit.engine`/`Unit.capability` already exist (`execution_spec.py:392-393`) — U3 adds only `engine_intent`.

## Residual risk / limited evidence

The saga `/plan` SKILL.md touch added to U2 widens the change surface to a second plugin's skill
file; the U6 release-surface unit already bumps saga, so no new release surface is introduced.
Verified in the fix round: no test pins the `/plan` SKILL.md tier-table prose (the only test
referencing that path, `tests/test_marketplace_hook.py:181`, uses it as a hook-payload fixture).
