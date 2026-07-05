---
title: Doc review — ship_ceremony.py plan (#345)
type: docs
status: complete
date: 2026-07-04
target: docs/plans/2026-07-04-ship-ceremony-primitive-plan.md
---

# Doc review — ship_ceremony.py plan (#345)

**Target:** `docs/plans/2026-07-04-ship-ceremony-primitive-plan.md`
**Reviewed revision:** working tree (plan is a new, uncommitted file)
**Blocked status:** not blocked — no unresolved P0/P1 findings.
**Issue:** infiquetra/infiquetra-claude-plugins#345

## Readiness summary

The plan is ready to drive implementation. Every KTD was checked against the actual code it
claims to be consistent with or diverge from (`reversibility_certificate.py`'s scope
exclusion, `saga.py`'s existing optional-flag/carry-forward pattern, the absence of any
git-alias-installer precedent), and two real implementation-assumption gaps surfaced during
that verification were fixed in place rather than left for `/work` to discover mid-build.

## Applied fixes

| # | Section | Fix |
|---|---|---|
| 1 | U1 / U4 Approach | Corrected the claim that `saga.py scan` resolves a saga by branch — verified via `--help` that `scan` takes no branch filter; the plan now states `ship_ceremony.py` filters `scan`'s candidate list by matching `branch` itself. |
| 2 | U4 Test scenarios | Added a guard against `install` silently overwriting a pre-existing `alias.ship` unrelated to this primitive — now requires explicit `--force`, with a same-target case treated as an idempotent no-op. |
| 3 | U1 Test scenarios | Added an explicit ambiguous-match edge case: multiple `scan` candidates sharing the current branch name must produce a named error asking for `--issue-ref`, not a silent newest-wins guess. |
| 4 | KTD1 / U1 Goal / KTD1 cross-ref | Renamed the plan's local tier registry from `Tier` to `CeremonyTier` to avoid a symbol-name collision with `reversibility_certificate.Tier` in any test or module that imports both. |

## Remaining findings by priority

| Priority | Finding | Status |
|---|---|---|
| P0 | none | — |
| P1 | none remaining (both found during review were fixed above) | resolved |
| P2 | none | — |
| P3 | none | — |

## Review artifact path

`docs/reviews/2026-07-04-ship-ceremony-primitive-345-doc-review.md` (this file).

## Residual risk / limited evidence

None material. One judgment call worth naming explicitly for the implementer: KTD3's git-alias
installer has zero repo precedent (verified by search), so U4 is the plan's single highest-novelty
unit — the plan's design (local-scope `git config`, explicit force-guard on collision, idempotent
uninstall) is sound but should get extra scrutiny at code-review time precisely because there's no
existing pattern to compare it against.
