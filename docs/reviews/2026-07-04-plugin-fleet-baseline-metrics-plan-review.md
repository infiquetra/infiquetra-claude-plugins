---
title: Doc Review — Plugin-Fleet Baseline Metrics Plan
date: 2026-07-04
target: docs/plans/2026-07-04-plugin-fleet-baseline-metrics-plan.md
reviewed_revision: working tree
blocked: false
---

# Doc Review — Plugin-Fleet Baseline Metrics Plan

**Verdict: not blocked.** The plan is ready to drive `/work`. Four safe fixes were applied
in place across two review passes; zero findings remain.

## Target and scope

- Target: `docs/plans/2026-07-04-plugin-fleet-baseline-metrics-plan.md`
- Reviewed revision: working tree (uncommitted)
- Classification: plan document (content-shape signals — `origin:`, `Implementation Units`,
  `Key Technical Decisions`, `U1` — plus path tie-breaker `docs/plans/`). Not routed to the
  idea/issue/spec rubric engine; this is an implementation plan derived from
  requirements-ready issue #461, not the issue-phase artifact itself.
- Linked issue: infiquetra/infiquetra-claude-plugins#461
- Linked saga: `issue-461` (plan phase, active, destination `merge`, backend `inline`)

## Applied fixes

| # | Fix | Evidence supporting the change |
|---|---|---|
| 1 | `origin:` frontmatter changed from `N/A (...)` to a repo-relative issue reference plus its cited source docs | The plan-doc schema requires `origin:` to trace the plan back to its source for the review phase; a bare `N/A` breaks that traceback even though prose elsewhere in the plan already names the real sources (issue #461, the grounding brief, the ideation survivor JSON) |
| 2 | U2's metric selection changed from hedged "e.g., metric 1 ... e.g., metric 7" to a firm, pinned choice | Both metrics were already the plan's own suggested examples with fully-specified recipes; pinning removes an open choice `/work` would otherwise have to resolve itself, consistent with the "agent-consumable, no re-asking the operator" principle |
| 3 | Metric 3's conditional secondary recipe replaced with a confirmed `gh api graphql` command against the live Operations board, labeled as a liveness check rather than a re-derivation | `gh api graphql -f query='{ organization(login: "infiquetra") { projectV2(number: 3) { title, items(first: 1) { totalCount } } } }'` was run live during this review and returned `"totalCount":165` successfully |
| 4 | Metric 5's conditional secondary recipe ("whatever session-mining artifact path the grounding brief names") struck entirely; metric 5 now relies on its primary recipe alone | Re-grepped the grounding brief for any artifact identifier near the 219-dark-codex-sessions claim (§7) — the only identifier present is a different mining run's workflow ID (`wf_7e5d77a2-5c0`), not a path for this claim; naming one would have been invention, which doc-review's safe-fix rules forbid |

## Readiness-skeptic pass

**Verification.** All eight evidence citations were independently re-grepped against
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` during this review (not trusted from
the plan's prose) and all eight line numbers hold exactly: `:72`, `:101`, `:115`, `:119`,
`:122`, `:126`, `:129`, `:145`. KTD1's claim — that the plan's citations are correct while
issue #461's own citations have drifted — is independently confirmed, not just asserted.

**Assumptions.** No stale or unverified assumptions found in the core path (U1/U2/U3). The
optional secondary-recipe language in U1 for metrics 3 and 5 assumes resources ("a live
board", "whatever session-mining artifact path the grounding brief names") that may not
exist or may not be named precisely enough to act on — see P3 findings below.

**Requirement mapping.** All ten of issue #461's acceptance criteria map cleanly onto the
plan's R1–R6 and the closeout section: AC1→R1, AC2→R2, AC3→R3, AC4/AC5/AC6/AC7/AC8→R4 (via
the eight-metric table), AC9→R5, AC10→R6. No gaps, no orphaned criteria.

**Completeness.** Closeout section correctly identifies that no release-surface files
change (issue #461's own checklist agrees — this is docs-only) and correctly identifies the
optional `QUEUED.md` line as a no-op (verified live: `grep -n "negative-space-10"
docs/engineering-journal/QUEUED.md` returns zero matches).

**Open-choice pressure.** Resolved by applied fix #2 above.

**Adversarial failure modes.** Checked whether a literal `/work` execution could go wrong:
the en dash character in "350–450k" (U+2013, not a hyphen) is preserved correctly in both
the plan's table and its fenced recipe — confirmed via `cat -A`, so a copy-pasted recipe
will match the source file byte-for-byte. No P0/P1 risk found.

## Remaining findings

None. Both `P3`s from the first pass are resolved:

| Priority | Finding | Resolution |
|---|---|---|
| P3 | Metric 3's optional secondary recipe was conditional on unverified board availability | Verified live: `gh api graphql` against `infiquetra` org project #3 returns `totalCount` successfully. Plan now carries the confirmed command and labels it correctly as a liveness check on the query path, not a re-derivation of the historical 375-item snapshot. |
| P3 | Metric 5's optional secondary recipe pointed at an unnamed session-mining artifact path | Re-checked the grounding brief: the only artifact identifier near that claim is a different mining run's workflow ID (§7, `wf_7e5d77a2-5c0`), not a path tied to the 219 dark codex sessions. Inventing one would violate the plan's own KTD1 discipline, so the vague conditional language was struck; metric 5 now relies solely on its primary grep recipe, which already satisfies every acceptance criterion. |

No P0, P1, or P2 findings.

## Review artifact

This file: `docs/reviews/2026-07-04-plugin-fleet-baseline-metrics-plan-review.md`

## Residual risk from limited evidence

None material. The two P3 findings are about optional, non-blocking recipe language, not
about the plan's core path (U1's eight required recipes, U2's verification, U3's checklist
line and journal entry).
