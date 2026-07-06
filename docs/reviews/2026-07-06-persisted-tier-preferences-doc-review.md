---
title: Doc-review — persisted tier preferences plan
target: docs/plans/2026-07-06-persisted-tier-preferences-plan.md
reviewed_revision: working tree
blocked: false
date: 2026-07-06
linked_issue: infiquetra/infiquetra-claude-plugins#368
---

# Doc-review — persisted tier preferences

**Readiness: READY, not blocked.** Three findings, all fixed in place. The important one was a
grounding gap on the mission-control side (AC5) — resolved by discovering the *contained* build path.

## Applied fixes

| # | Priority | Finding | Fix |
|---|----------|---------|-----|
| 1 | P1 | U3 (AC5) glossed the mission-control card-contract machinery: the card contract's source of truth is home-lab's `card_validator.py`, vendored into a **generated, sha256-pinned, parity-gated** `issue_contract_data.py`. My plan implied a plain template edit. | Grounded: `validate_card_body` only checks *required* sections and **does not reject extra ones**, so `recommended-tier-band` as an optional/auto-populated field is already "recognized." Rewrote U3 to the **contained path** (`derive_tier_band` + issue-create stamping, no home-lab change) with an explicit fiddly-risk flag if `templates-reference.md` is fully generated (then contract regen + sha256 + parity). |
| 2 | P2 | The issue-band precedence semantics were ambiguous (single tier vs per-shape). | Clarified: the band is a single `{model, effort}` seeding the per-work-shape default when no repo override exists; the operator still confirms per unit. |
| 3 | P2 | Write-back (AC2) dirties a **tracked** file (`.saga/` is committed) — unstated. | Noted: intended (the repo accretes tier judgment); committed like any change. |

## Verification performed

- `.saga/` is **not** git-ignored (only `.saga-worktrees/`) → the overlay is a committed per-repo file.
- `tier_policy.json` work-shapes confirmed (`judgment→opus/high`, `mechanical→sonnet/medium`,
  `read-only-survey→sonnet/low`, …) — the overlay + band targets.
- `sdlc_manager.validate_card_body` checks required H3 sections only; extra sections pass — so AC5's
  "recognizes it" is satisfied without a validator change.
- The card contract is a generated + `.sha256`-pinned + parity-tested artifact
  (`config/generated/issue_contract_data.py`) with source of truth in home-lab — flagged as the one
  place AC5 can grow costly; the plan keeps it contained to mission-control.

## Residual risk

Moderate — this is a Deep, cross-plugin (saga + mission-control) build. The saga side (AC1-AC4, AC6,
AC7) is clean loader/precedence work over proven primitives. The mission-control side (AC5) is
contained but the generated/sha256/parity contract is the fiddliest surface; `/work` should verify
whether `templates-reference.md` is generated before choosing the optional-field vs contract-data path.
