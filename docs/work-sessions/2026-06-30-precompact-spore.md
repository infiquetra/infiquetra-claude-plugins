---
issue: infiquetra/infiquetra-claude-plugins#281
branch: feat/281-precompact-spore
plan: docs/plans/2026-06-30-precompact-spore-rehydration-plan.md
date: 2026-06-30
status: PR-ready (code-review CLEAN; awaiting merge confirmation)
---

# Work session — PreCompact spore (#281)

Built the two-hook PreCompact spore so a continuing session re-grounds on structured saga facts after
a mid-run auto-compaction, per the plan. Six units, six commits + a P3-fix commit on
`feat/281-precompact-spore`.

## Built (by U-ID)

| Unit | What | Owner | Commit |
|---|---|---|---|
| U1 | `saga_spore.py` core (resolve saga/outcome, freeze DAG, ≤9k serialize, dump/load seam) + 22 tests | Claude | `6e19dae` |
| U2 | `precompact_spore_hook.py` (SIGALRM 1.5s deadline, atomic write, orphan sweep, exit 0) | agy Pro (High) | `443739d` |
| U3 | `compact_spore_session_hook.py` (load+validate, unlink-before-emit, emit additionalContext) | agy Pro (High) | `64eba16` |
| U4 | `hooks.json` wiring (PreCompact auto\|manual + SessionStart compact) + registration test | Claude | `844003e` |
| U5 | `test_spore_seam_roundtrip.py` (6 real-subprocess seam scenarios) | agy Pro (High) | `a809194` |
| U6 | release surfaces (0.43.0) + CHANGELOG + saga-spec note + journal | Claude | `b97e0a9` |
| — | two P3 code-review fixes (.tmp reclaim; test docstring honesty) | Claude | `6f50d14` |

## Key decisions / outcomes

- Backend `inline` with agy as a delegated `patch-only` coder (Gemini 3.1 Pro High) for U2/U3/U5;
  Claude sole committer/verifier. **agy dogfood: n=3, all genuine Pro (High), contained, functionally
  correct on first apply** — only cosmetic Claude fixes (lint + two test-vocab slips). Recorded in
  LEARNINGS `#agy-pro-high-coder-dogfood-281`.
- Doc-review READY (`docs/reviews/2026-06-30-…-doc-review.md`); code-review CLEAN, 0 P0/P1/P2, 2 P3 fixed
  (`docs/code-reviews/2026-06-30-feat-281-precompact-spore-code-review.md`).
- saga 0.42.0 → 0.43.0; DECISIONS `#precompact-spore-two-hook`.

## Checks

Full suite 1530 passed (1 deselected = local-only `.claude`-leak false positive from this issue's own
saga; green in CI). ruff check + format + mypy clean. Both JSON surfaces valid; drift guard updated.

## Process note

Mid-build I wrongly reassigned U5 (an agy-delegated unit) to myself "for reliability"; the operator
corrected it. Lesson captured in memory `feedback-dogfood-find-the-edges`: follow the agreed plan
split, de-risk delegations by specification not confiscation, and the edges are the point of a dogfood.

## Next step

Open PR (done) → squash-merge to main under operator confirmation → `/qa` (clean code-review routes to
ship-readiness).
