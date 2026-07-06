---
title: Persisted tier preferences — per-repo defaults + remembered overrides + issue-carried bands
type: feat
status: active
date: 2026-07-06
origin: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
---

# Persisted tier preferences — per-repo defaults, remembered overrides, issue-carried bands

## Summary

Stop tier judgment evaporating at the end of every run. Two persistence mechanisms, one precedence
rule: (1) a **committed per-repo `.saga/tier-defaults.json` overlay** that layers repo-pinned
work-shape→tier defaults over the shared `tier_policy.json` registry, plus **remembered-override
write-back** so the next `/plan` proposes the accreted preference; and (2) an **issue-carried
`recommended-tier-band`** that `mission-control:issue` stamps at creation and `/plan` pre-fills its
tier table from. Precedence (AC7): **repo overlay > issue band > shared registry**. Full DoD (all 8
ACs) in one saga + mission-control PR (operator decision 2026-07-06).

## Problem Frame

The fleet's only operator-facing tier lever is `/plan`'s per-unit tier table, re-derived cold from
`tier_policy.json` (`judgment→opus/high`, `mechanical→sonnet/medium`, `read-only-survey→sonnet/low`,
…) on every run. A repo that has already tuned its tiers pays the same full-derivation cost on run N
as run 1 (grounding brief pattern 6, 3 repos). No persistence hook exists today (verified: no
`tier-defaults` loader in `execution_spec.py`; `.saga/` is not git-ignored, so an overlay file there
is committed and shared).

## Requirements (acceptance criteria)

AC1. A `.saga/tier-defaults.json` repo-pinned tier for a work-shape resolves to that tier, overriding
     the shared registry default for that shape.

AC2. Confirming a tier override during `/plan` persists it into `.saga/tier-defaults.json` under the
     work-shape key, without clobbering other keys.

AC3. A second `/plan` run in a repo with a prior confirmed override proposes that override for the
     unchanged work-shape (scripted two-invocation fixture, not a live session).

AC4. A missing overlay falls back cleanly to the registry (no error); a malformed one fails loud with
     a named error (halt-not-degrade).

AC5. `mission-control:issue` writes a `recommended-tier-band` field into a created issue body, derived
     from a type/label→band mapping (defect-investigation→`opus/high`, mechanical→`sonnet/medium`,
     read-only survey→`sonnet/low`); the card validator recognizes it.

AC6. Given a fixture issue carrying a `recommended-tier-band`, `/plan` pre-fills its tier table from
     that band instead of deriving cold.

AC7. When both a repo `.saga/tier-defaults.json` override and an issue band exist for the same
     work-shape, the **repo override wins** (closest to execution) — documented and tested.

AC8. Repo-wide gates stay green (pytest, ruff, mypy, bandit).

## Key Technical Decisions

KTD1 — **`.saga/tier-defaults.json` is a committed, per-repo file** (`.saga/` is not git-ignored —
verified). Schema: `{"<work-shape>": {"model": str, "effort": str}}`. A saga-side module
`tier_defaults.py` owns load/resolve/write-back. Values validated against the palette + registry
work-shapes (never invent a tier or an unknown shape; `{#tier-vocab-ordering}`).

KTD2 — **The overlay is saga-side; `fleet_commons` is untouched.** `tier_defaults.py` reads the repo
overlay and layers it over `tier_resolver.load_policy()`, passing the merged registry to
`resolve(..., policy=overlaid)`. The shared resolver keeps a single registry contract; the per-repo
overlay is a saga concern (and additive — no `fleet_commons` change, no additive-only-contract risk).
Because `.saga/tier-defaults.json` is committed, a write-back (AC2) dirties a **tracked** file — that
is intended (the repo accretes tier judgment); the operator/work flow commits it like any other change.

KTD3 — **Write-back is read-merge-write, override-only.** `write_tier_default(work_shape, model,
effort, root)` reads the existing file, sets one key, writes back — never clobbering unrelated keys.
Every persisted override originates from an explicit operator confirmation in `/plan` (non-goal:
silent auto-promotion).

KTD4 — **Malformed fails loud (AC4).** A `.saga/tier-defaults.json` that is not valid JSON, or carries
an unknown work-shape / off-palette / unrunnable tier, raises a named `TierDefaultsError` — the same
halt-not-degrade discipline as the rest of the tier system. Missing file → clean empty overlay.

KTD5 — **Precedence is one resolver: repo overlay > issue band > registry (AC7).**
`resolve_tier_for_plan(work_shape, issue_band, root)` returns the repo override if present, else the
issue band if present, else the registry default. The repo override is closest to execution, so it
wins the coarser issue-time band. This one function is the tested precedence contract. The issue band
is a single `{model, effort}` that seeds the per-work-shape default when no repo override exists; the
operator still confirms/adjusts per unit in `/plan` (non-goal: silent auto-selection).

KTD6 — **The issue band is a mission-control field + a type→band map.** `recommended-tier-band` is an
optional issue-body field the card validator recognizes; `mission-control:issue` derives it from the
issue type/labels at creation. `/plan` reads it via `resolve_tier_for_plan`. No new plugin
(`{#plugin-portfolio-groom-17-to-7}`); fields added to two existing plugins.

## Implementation Units

### U1. `tier_defaults.py` — overlay loader + write-back (AC1-AC4)

`plugins/saga/scripts/tier_defaults.py`: `load_tier_defaults(root)` (missing→{}, malformed→raise
`TierDefaultsError`), `resolve_tier_with_overlay(work_shape, root)` (repo overlay over
`load_policy()`), `write_tier_default(work_shape, model, effort, root)` (read-merge-write, validated).

**Test scenarios** (`tests/test_tier_defaults.py`):
- `test_tier_defaults_overlay_precedence` (AC1) — a pinned `mechanical→opus/high` overrides the
  registry's `sonnet/medium`.
- `test_tier_defaults_writeback` (AC2) — writing one work-shape leaves other keys intact.
- `test_tier_defaults_second_run_reuse` (AC3) — a persisted override is returned by a fresh
  `resolve_tier_with_overlay` (the two-invocation contract).
- `test_tier_defaults_malformed` (AC4) — missing → registry fallback; bad JSON / unknown shape /
  off-palette → named `TierDefaultsError`.

### U2. Precedence resolver — repo overlay > issue band > registry (AC6, AC7)

`resolve_tier_for_plan(work_shape, issue_band, root)` in `tier_defaults.py`, applying KTD5 precedence.

**Test scenarios** (`tests/test_tier_defaults.py`):
- `test_tier_band_prefill_from_issue` (AC6) — with no repo override, an issue band pre-fills the tier
  (over the registry default).
- `test_tier_defaults_vs_issue_band_precedence` (AC7) — with both present, the repo override wins.

### U3. mission-control `recommended-tier-band` field (AC5)

The card validator (`sdlc_manager.validate_card_body`) only checks that **required** H3 sections are
present — it does **not** reject extra sections (verified), so a `### Recommended Tier Band` optional
section is already "recognized" (accepted). So AC5 is: (a) a `derive_tier_band(issue_type)` helper
(defect-investigation→`opus/high`, mechanical→`sonnet/medium`, read-only→`sonnet/low`), and (b) the
issue-create path in `sdlc_manager.py` stamps the derived band as an **auto-populated** field
(mirroring `lifecycle_origin`).

**Contained-path preference:** ship it as a stamped optional field + `derive_tier_band`, minimizing
changes to the **sha256-pinned, parity-gated generated contract**
(`config/generated/issue_contract_data.py`). The home-lab `card_validator.py` REQUIRED contract stays
untouched (the field is optional/auto-populated, not required). **Fiddly-risk flag:** if
`templates-reference.md` is fully generated from that contract (verify first in `/work`), the field
must go into the contract's `auto_populated_fields` and the generated data + `.sha256` pins +
`test_issue_contract_parity` regenerated — this is the single place AC5 can grow costly; keep it
contained to mission-control and do not touch home-lab.

**Test scenarios** (`plugins/mission-control/tests/test_card_validator.py`):
- `test_recommended_tier_band_field` (AC5) — `validate_card_body` accepts a card carrying the field,
  and `derive_tier_band` yields `opus/high` (defect), `sonnet/medium` (mechanical), `sonnet/low`
  (read-only).

### U4. Docs + release surface (both plugins) (AC8)

`plugins/saga/skills/plan/SKILL.md` Step 1: document the overlay + write-back + band prefill +
precedence. `plugins/mission-control/skills/issues/references/templates-reference.md`: the new field.
Bump saga + mission-control plugin.json + CHANGELOGs, sync `.claude-plugin/marketplace.json`, update
drift-guard version pins + docs-coverage counts, record KTD1-KTD6 in `DECISIONS.md`.

## Scope Boundaries

**Out of scope (true non-goals, from the issue):**
- Any change to the shared `tier_policy.json` registry defaults or the `MODELS`/`EFFORTS` vocabulary —
  this issue only adds an overlay in front of it.
- Automatic (non-confirmed) tier changes — every persisted override originates from an explicit
  operator confirmation.
- A cross-repo / org-level tier-preference store — `.saga/tier-defaults.json` is per-repo v1.
- Extending team-execution per-teammate effort or agent `model:` frontmatter.
- Spend-increase confirmation UX — that is #367/#365's territory, assumed as a parallel gate.
