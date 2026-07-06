---
title: Work session — persisted tier preferences (#368)
issue: infiquetra/infiquetra-claude-plugins#368
plan: docs/plans/2026-07-06-persisted-tier-preferences-plan.md
branch: feat/368-persisted-tier-preferences
date: 2026-07-06
---

# Work session — persisted tier preferences (#368)

**Built all 8 ACs (operator chose full scope, then re-confirmed AC5 push-through when its
draft-flow cost surfaced mid-build).** Cross-plugin (saga + mission-control); full repo gate green;
three commits.

## What was built (by U-ID)

- **U1+U2 — saga `tier_defaults.py` (AC1-AC4, AC6, AC7)** — commit `0ddfdc7`. Committed
  `.saga/tier-defaults.json` overlay: `load_tier_defaults` (missing→`{}`, malformed→loud
  `TierDefaultsError`), `resolve_tier_with_overlay` (repo>registry), `write_tier_default`
  (read-merge-write, confirmed-override-only), and the one precedence contract
  `resolve_tier_for_plan` (**repo overlay > issue band > shared registry**). 6 tests.
- **U3 — mission-control band production (AC5)** — commit `ea43d09`. `derive_tier_band(issue_type)`
  (defect/capability→`opus/high`, enhancement/context-update→`sonnet/medium`,
  exploration→`sonnet/low`, objective→none) + idempotent `_append_tier_band` stamp on the
  `_source_to_issue_body` **wrapper** (every compiled body carries it; a future call site can't
  miss the stamp). Contained path held: card validator, sha256/parity generated contract, and
  cross-repo canonical templates all untouched — the band rides the Lifecycle Origin
  auto-populate discipline. Saga consumer `parse_tier_band(body)` + a cross-plugin roundtrip test
  pinning the stamp/parse format contract.
- **U4 — docs + release surface (AC8)** — commit `ea43d09`. saga 0.66.0→0.67.0, mission-control
  2.5.1→2.6.0, marketplace sync, CHANGELOGs, `/plan` SKILL Step 1 (resolve→confirm→write-back
  loop), mission-control issues SKILL (auto-stamped field note), both version-pin tests,
  DECISIONS `{#tier-defaults-368}` (KTD1-KTD6).

## Adversarial gate — 1 P1 + 1 P2 found by execution, both fixed

Round 1: `saga:readonly-verifier` (worktree) CONFIRMED by probe that both sides matched the header
text naively — a code-fence or prose mention of `### Recommended Tier Band` (1) parsed as an
authoritative band and (2) silently suppressed the compile-time stamp, contradicting the module's
own halt-not-degrade claim. **Fix `d4fc73c`**: fence-aware header detection on both sides
(`_unfenced_lines` / `_has_tier_band_section`, mirrored), duplicate real headers fail loud
("expected one"), regression tests pin fenced/prose mentions, mixed real+fenced, and duplicates.

Round 2 (re-verify of the fix, same agent resumed): P1 probes all SAFE; one **new P2** CONFIRMED —
an unclosed fence anywhere before end-of-body swallowed the stamped band into perceived code text
(silently unparseable; degrades to "no band," not a wrong tier). **Fix `40372bf`**:
`_open_fence_closer` closes a fence still open at end-of-body — render-neutral per CommonMark (an
unclosed fence runs to end-of-document anyway) — before appending, so the stamped band is always a
real, parseable section; the closer matches the opening flavor (``` vs `~~~`). Stamp→parse
roundtrip tests on unclosed-fence bodies pin it on both sides.

## Gates

- `uv run pytest` — 2254 passed, 1 skipped (full suite, post both fixes).
- `ruff format --check` + `ruff check` — clean. `mypy` (CI scope) — clean. `bandit -ll` on changed
  scripts — clean.
- Prepare→compile→approve→create round-trips unchanged (282 mission-control + saga tier tests).

## Follow-ups

- None filed. The band becoming author-visible in the canonical templates (then entering the
  generated contract properly) is the recorded "revisit when" in DECISIONS.
