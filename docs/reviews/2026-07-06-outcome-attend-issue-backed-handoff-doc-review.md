# Doc Review — /outcome attend issue-backed handoff (#491)

**Target:** `docs/plans/2026-07-06-outcome-attend-issue-backed-handoff-plan.md`
**Reviewed revision:** working tree (2026-07-06)
**Linked issue:** infiquetra/infiquetra-claude-plugins#491
**Plan saga:** `issue-491` (git-ignored)
**Blocked:** No — no findings; ready to drive implementation.

## Readiness summary

Ready. The plan is small, fully grounded (every claim cites verified `path:line`), and its two
load-bearing claims were re-verified against code during this review. No safe fixes needed.

## Applied fixes

None.

## Verified, no finding

- **Scope is attend-only (claim upheld).** `outcome_report.py` never calls `outcome.attend` and never
  emits `leaf_saga_id` or a `/resume` handoff — `AttentionItem` carries only `subplot_id`, and
  `consolidated_prompt`/`report.md` render `subplot_id` + PR/issue evidence. The issue title's
  "attend/report" over-scopes; the sole defect site is `attend` (`outcome.py:955`). The plan correctly
  scopes the report out.
- **Version bump 0.72.0 is correct for this repo.** saga has done a minor bump every release
  (0.60.0 → 0.71.0, no patch bumps ever), so minor-per-change is the established convention; a
  semver-purist patch (0.71.1) would break the pattern.
- **The fix reuses landed primitives.** `outcome_github._parse_ref` (#495) extracts `N` from
  `owner/repo#N`; `f"issue-{N}"` mirrors `saga.derive_saga_id` (`saga.py:333`). KTD2's inline-not-import
  is a sound dependency-surface call for a one-line format string.

## Remaining findings

None (P0/P1/P2/P3 all clear).

## Residual risk

Low. The one behavioral edge — a non-issue-backed leaf — is covered by the raw-id fallback (R2/R3), and
the `sub_issue` (bare int) vs `issue` (`owner/repo#N`) dual source is covered by the U1 test scenarios.
