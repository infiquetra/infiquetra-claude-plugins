---
date: 2026-06-07
review_of: docs/plans/2026-06-07-saga-doc-readability-plan.md
reviewed_revision: f6c87d4 (plan as merged) + safe fixes in this PR
issue: 201
type: doc-review
blocked: false
---

# Doc Review: Saga Document Readability Plan

## Readiness summary

The plan is ready to drive implementation — no P0/P1 findings, no blocking issues.

It carries a clear problem frame, stable R-IDs and U-IDs, ordered dependencies, repo-relative paths,
and per-unit test scenarios. The KTDs are settled with rationale and rejected alternatives.

The readiness-skeptic pass found five issues, all P2/P3, every one of them an over-statement or
mis-location the parallel ultracode fan-out would have tripped on. All five were evidence-backed and
fixed in place — none required inventing scope or resolving a product decision.

## Applied fixes (safe, in-place)

| id | priority | finding | fix |
|----|:--------:|---------|-----|
| F1 | P2 | Rollout over-stated: plan implied a uniform "fix the collapse" across all 9 skills, but only `ideation-artifact.md` has the bug (9 bold-label lines); the other 8 templates already use headings/prose/tables (verified: spec/strategy/brainstorm/retro/founder-review = 0 bold-label stacks; plan = headings; code-review already tables findings). | KTD5 rewritten to state the verified per-skill reality: ideate = real fix, others = link + light rules + regression-guard. |
| F2 | P2 | U5 pointed code-review's "render findings as a table" at `findings-schema.md`, which is the field *definition* (already a table) — not the render site. code-review already renders findings as a pipe-delimited table (`findings-schema.md:105`). | U5 approach corrected: code-review scope is link + narrative prose rules; do not re-table findings. |
| F3 | P2 | "Apply the soft-wrap rule" (U2-U5) could be read by the 4 parallel fan-out agents as "reflow the template's editorial source prose to no-hard-wrap," producing a huge whitespace-only diff against KTD3's intent. | Added an Execution guard under Implementation Units: "apply the rules" = encode prescriptions + render EXAMPLE blocks; never reflow template source. |
| F4 | P3 | U6's "each skill links the shared ref" did not say *where* (doc-review has no references dir). | U6 clarified: assert the link exists somewhere in the skill dir (template file, or `SKILL.md` for doc-review). |
| F5 | P3 | U6's markdown-only test adds no `plugins/` coverage; risk of a spurious coverage workaround. | U6 note added: no `--cov-fail-under` gate exists (`pyproject.toml:76` reports, does not gate) — no workaround needed. |

## Remaining findings

None. All five findings were resolved by safe in-place fixes.

## Verification performed

Each finding was confirmed against the repo, not inferred:

- `rg -c '^\*\*[a-z_]+:\*\*'` across all rollout-target templates → only `ideation-artifact.md` returns non-zero (9); the rest return 0 (F1).
- `findings-schema.md:9-18` is a field-definition table; `:105` specifies pipe-delimited findings output (F2).
- `pyproject.toml:75-76` → `testpaths = ["tests", "plugins/*/tests"]`, `addopts` has `--cov=plugins` with no `--cov-fail-under` (F5).
- `doc-review/SKILL.md` has no `references/` dir; report format lives in `SKILL.md` (F4).

## Residual risk from limited evidence

Low. The plan is a docs/templates change with one markdown-reading test; no runtime, auth, deploy, or
data surface. The main execution risk (parallel agents over-editing clean templates) is now addressed
by the Execution guard and the corrected KTD5.

## Result contract

- **Target:** `docs/plans/2026-06-07-saga-doc-readability-plan.md`
- **Reviewed revision:** `f6c87d4` (plan as merged) + safe fixes in this PR
- **Blocked:** no
- **Findings:** 5 total (3× P2, 2× P3) — all resolved by safe fixes; 0 remaining
- **Applied fixes:** F1–F5 (see table)
- **Review artifact:** `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`
- **Linked issue / plan:** #201 / `docs/plans/2026-06-07-saga-doc-readability-plan.md`

`/work` may proceed — no override needed (no unresolved P0/P1).
