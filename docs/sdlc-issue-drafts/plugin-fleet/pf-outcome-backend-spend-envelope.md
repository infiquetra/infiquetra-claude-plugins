---
title: "enhancement: run-start intent envelope — backend/degrade posture + spend ceiling captured once, enforced at the /outcome dispatch seam"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Ship run-start intent envelope for lifecycle autonomy"
wave: wave-1
---

# enhancement: run-start intent envelope — backend/degrade posture + spend ceiling captured once, enforced at the /outcome dispatch seam

## Objective

Ship run-start intent envelope for lifecycle autonomy (`Objective: Ship run-start intent
envelope for lifecycle autonomy`, wave-1).

## Problem / motivation

Today the `/outcome` engine's backend-and-degrade posture and its spend ceiling are each
decided **per leaf, at dispatch time**, not captured once at run start:

- `plugins/saga/scripts/outcome_dispatcher.py:1-60` documents the existing per-leaf
  mechanism precisely: `resolve_available` exposes the full host-conditional backend menu
  (`ALWAYS_AVAILABLE = ("inline", "team-execution", "manual")` plus `HOST_DEPENDENT =
  frozenset({"fork", "subagent", "cc-workflows-ultracode", "goal"})`), and
  `degrade_decision` implements the presence-conditional degrade policy: an unavailable
  backend HALTs when the operator is attending, or the leaf is guarantee-bearing, or
  already side-effected; otherwise it degrades **exactly one rung** down
  `DEGRADE_LADDER = ("cc-workflows-ultracode", "team-execution", "inline")`
  (`outcome_dispatcher.py:53`, `DispatcherError`/`BackendHaltError` at the top of the same
  file). This is real, working machinery — but it is re-resolved at every dispatch call
  rather than authored once as an explicit, inspectable run-start decision.
- `plugins/saga/scripts/outcome_dispatcher.py:97-140` (the `resolve_available`/`HaltReceipt`
  path) is what actually raises `BackendHaltError` when the coordinator's production loop
  (`outcome._reconcile_once`) hands a restricted backend set to a caller that HALTs instead
  of degrading — but there is no single place upstream where an operator or a resumed run
  can see *the posture that was decided*, only the mechanism that enforces whatever posture
  happened to be resolved this call.
- Spend gating does not exist at all yet at the dispatch seam: `outcome.py:1067-1070`
  imports `outcome_costs` and calls `outcome_costs.materialize(spec, store)` to roll up
  **actual** leaf-produced cost after the fact (R24's cost rollup, mirrored in
  `OutcomeSpec.cost_rollup` at `outcome_spec.py:369-371`), but nothing reads that rollup
  *before* dispatch to authorize or block a tier-escalating/over-ceiling leaf. A run can
  silently accumulate spend past any implicit ceiling because there is no explicit ceiling
  to check against.
- The binding decision register for the `/outcome` campaign
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:47`, row "`/outcome` campaign
  (U1–U11)") is explicit: "Derived-on-read status, never committed status fields;
  HALT-not-degrade; backend menu off-by-default with host-conditional degrade; cost ledger
  = leaf-produced fact." This issue must engage — not contradict — that decision: the
  envelope described below is captured **once at run start** but the HALT/degrade
  *decision itself* stays derived at dispatch time from that captured posture, exactly as
  `outcome_dispatcher.py` already does it for backend menu.
- `docs/engineering-journal/DECISIONS.md:347` (`{#capability-sandbox-plan-stance}`, #287)
  set the precedent this issue mirrors for a different axis: a two-axis envelope
  (`mutation_policy` × `workspace_isolation`) captured once on `Unit`/`Node` and enforced
  by native harness primitives, with an explicit halt rather than a silent substitution.
  The absorbed facet T8-F6-8 explicitly engages "mirroring #287."
- The fleet's model/effort reality section
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:8-17`) notes the fleet has
  exactly one operator-facing lever for tier/spend decisions today — saga `/plan`'s unit
  tier table (`plugins/saga/skills/plan/SKILL.md:296-352`) — and no dispatch-time
  authorization check anywhere reads a captured ceiling before a leaf executes at an
  escalated tier.

Net effect: an operator resuming a long-running `/outcome` cannot answer "what backend and
degrade posture did this run start with?" or "what is this run's spend ceiling?" without
re-deriving it from scattered per-call state, and there is no gate that stops a leaf from
silently escalating past a ceiling that was never made explicit in the first place.

## Definition of Done

A merged PR that:

1. Adds an `Intent` dataclass (or extends `OutcomeSpec`, `outcome_spec.py:350-371`, if the
   plan phase determines that is the right seam) carrying three run-start fields:
   - `backends_permitted: tuple[str, ...]` — the host-conditional backend set captured once
     at run start (superset drawn from `ALWAYS_AVAILABLE` ∪ available `HOST_DEPENDENT`
     entries at `outcome_dispatcher.py`'s existing constants), off-by-default per KTD9
     (coordinator cannot self-probe host availability).
   - `degrade_policy` — the captured presence-conditional posture (operator-attending /
     guarantee-bearing / already-side-effected → HALT; otherwise degrade one rung per
     `DEGRADE_LADDER`), expressed so it is inspectable without re-deriving from call-site
     state.
   - `spend_envelope` — a tier ceiling and/or cost ceiling, checked against
     `outcome_costs`'s leaf-produced actuals (the `outcome_costs.materialize` path at
     `outcome.py:1067-1070`).
2. Adds a pre-dispatch authorization check at the `outcome_dispatcher.py` seam that reads
   the captured `spend_envelope` against `outcome_costs` before a leaf dispatches, gating
   tier-escalating or over-ceiling leaves.
3. Is verified by tests asserting the acceptance criteria below.
4. Does not change the existing per-leaf backend-menu HALT/degrade mechanism in
   `outcome_dispatcher.py` — this issue captures the posture explicitly at run start and
   feeds it into the existing mechanism; it does not replace `resolve_available` /
   `degrade_decision`.

### Acceptance criteria
- [ ] **AC1 (T8-F6-8, primary).** An `Intent`/spec-carried `backends_permitted` +
      `degrade_policy` pair is captured once at `/outcome` run start and consumed by the
      existing dispatch-seam mechanism (`outcome_dispatcher.py`) rather than re-derived ad
      hoc per call. Test: starting a run with an explicit host-conditional posture and then
      dispatching a leaf whose backend is unmet reads that captured posture.
- [ ] **AC2 (T8-F6-8).** When a leaf's host prerequisite is unmet, the run HALTs by default.
      Test: unmet prerequisite with no degrade posture set → `BackendHaltError` (mirrors the
      existing `outcome_dispatcher.py` HALT path).
- [ ] **AC3 (T8-F6-8).** When the captured posture permits degrade (not operator-attending,
      not guarantee-bearing, not already side-effected), the run degrades **exactly one
      rung** down `DEGRADE_LADDER` and never more — verified by a test asserting a
      two-rung-unavailable scenario still only degrades one rung and then HALTs, never
      silently cascading.
- [ ] **AC4 (T8-F5-7, primary facet).** A `spend_envelope` (tier ceiling + cost ceiling) is
      captured once at run start and enforced by a pre-dispatch authorization check that
      reads `outcome_costs`'s leaf-produced actuals. Test: a dispatch attempt under the
      ceiling is checked against a fixture spend envelope and passes the gate.
- [ ] **AC5 (T8-F5-7).** An under-ceiling dispatch clears silently (no operator interrupt,
      no HALT). Test: leaf cost + rollup stays under `spend_envelope` → dispatch proceeds
      without a halt/receipt.
- [ ] **AC6 (T8-F5-7).** A tier-escalating or over-ceiling dispatch HALTs for step-up
      authorization and never silently degrades the spend gate (distinct code path from the
      backend-menu degrade in AC3 — spend-gating is HALT-only, per the absorbed facet's
      explicit "never silent degrade"). Test: a leaf whose tier or cost exceeds the captured
      envelope raises a typed halt requiring explicit step-up, and no test observes it
      falling through to a lower tier automatically.
- [ ] **AC7.** The new envelope's presence is optional/backward-compatible: an existing
      `OutcomeSpec`/run with no captured `Intent` continues to behave exactly as today (full
      menu, existing HALT/degrade-only mechanism, no spend gate) — no forced migration.
      Test: a fixture spec lacking the new fields round-trips and dispatches unchanged.

### Out-of-scope / non-goals
- **In scope:** the `Intent`/envelope dataclass fields, the run-start capture point, the
  pre-dispatch spend-authorization check, and tests for the HALT/degrade/spend-gate
  interactions described above.
- **Out of scope / non-goals:**
  - Changing `resolve_available` / `degrade_decision` / `DEGRADE_LADDER` semantics — this
    issue feeds them a captured posture, it does not redesign backend-menu degrade.
  - Building a new cost-accounting mechanism — `outcome_costs.materialize` already produces
    the leaf-actuals this issue's spend gate reads; this issue adds the pre-dispatch read,
    not a new ledger.
  - Any UI/CLI surface for an operator to *set* the envelope interactively — this issue is
    the data model + enforcement seam; an operator-facing authoring flow (e.g. via
    `/outcome start`) can be a fast-follow.
  - Any change to `ENGINE_INTENTS` (`execution_spec.py:68`, `"offload"`/`"second-opinion"`)
    — that is a distinct, already-shipped concept (per-unit external-engine chaperone
    intent) and must not be confused with this issue's run-start `Intent` envelope.
  - `/plan`'s per-unit `{model, effort}` tier table (`plan/SKILL.md:296-352`) is unaffected;
    this issue's spend ceiling is a run-start `/outcome` gate, not a replacement for that
    authoring-time table.

## Grounding References

- **T8-F6-8** (primary) — "Capture backend + degrade posture once, host-conditional, HALT
  when unsatisfiable" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json`).
  DoD sketch: "Merged PR adding `backends_permitted` + `degrade_policy` to the Intent
  dataclass consumed at the dispatch seam; verified by a test where an unmet host
  prerequisite HALTs by default and degrades exactly one rung only when the captured
  posture permits (mirroring #287). Engages backend-menu-off-by-default + HALT-not-degrade."
- **T8-F5-7** (facet) — "Pre-authorized credit line: a spend envelope set once, step-up auth
  on overage" (same survivors file). DoD sketch: "Merged PR adding a `spend_envelope` (tier
  ceiling + cost ceiling) + a pre-dispatch authorization check reading `outcome_costs`;
  verified by tests asserting an under-ceiling dispatch clears silently and a
  tier-escalating/over-ceiling dispatch HALTs for step-up (never silent degrade). Distinct
  from posture envelope: spend-gating dispatch."
- **Binding decisions engaged (must not be contradicted):**
  - `/outcome` campaign (U1–U11) register row
    (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:47`): derived-on-read status,
    HALT-not-degrade, backend menu off-by-default with host-conditional degrade, cost
    ledger = leaf-produced fact.
  - `{#capability-sandbox-plan-stance}` (#287, `docs/engineering-journal/DECISIONS.md:347`)
    — the two-axis envelope-captured-once-and-enforced pattern this issue mirrors for a
    different axis (backend/degrade/spend rather than mutation/isolation).
  - `{#tier-vocab-ordering}` (grounding brief §2) — tier tuples (`DEGRADE_LADDER` included)
    are ordered escalation ladders, not closed sets; the one-rung-only degrade in AC3 must
    respect that ordering, not jump ranks.
- **Existing mechanism this issue extends** (not replaces):
  `plugins/saga/scripts/outcome_dispatcher.py:1-60` (module docstring: dispatcher seam,
  `resolve_available`, `degrade_decision`, `DispatcherError`, `BackendHaltError`),
  `outcome_dispatcher.py:97-140` (`HaltReceipt`/halt-raise path),
  `plugins/saga/scripts/outcome.py:1067-1070` (`outcome_costs.materialize` call site),
  `plugins/saga/scripts/outcome_spec.py:350-371` (`OutcomeSpec` dataclass, existing
  `cost_rollup` field this issue's spend gate reads from).

## Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** mechanical dataclass extension + a pre-dispatch conditional check
  against an existing, well-documented seam (`outcome_dispatcher.py`); no novel design
  judgment beyond following the #287 precedent already recorded in `DECISIONS.md`. Does not
  warrant opus/high — this is bounded, spec-following work with a clear existing mechanism
  to extend, not an architectural decision.

## Release-Surface Checklist

This changes `/outcome` runtime behavior (new spec fields, new dispatch-seam gate) inside
the `saga` plugin, so the same PR must also update:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — matching version/metadata for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new `Intent` envelope
      (`backends_permitted`, `degrade_policy`, `spend_envelope`) and the pre-dispatch
      spend-authorization check.
- [ ] Any version/metadata drift-guard tests in `tests/` that assert plugin.json /
      marketplace.json / CHANGELOG stay in lockstep — confirm they pass with the bump.

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/outcome_spec.py` — new `Intent` fields or dataclass.
- `plugins/saga/scripts/outcome_dispatcher.py` — pre-dispatch spend-authorization check,
  consuming the captured `backends_permitted`/`degrade_policy`.
- `plugins/saga/scripts/outcome_costs.py` (or wherever `outcome_costs.materialize` lives) —
  read path for the pre-dispatch spend check, if not already exposed.
- `tests/test_outcome_dispatcher.py` (or equivalent) — HALT/degrade/spend-gate tests.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface bump per checklist above.

### Tests to add or update
- Test: run-start `Intent` capture round-trips through `OutcomeSpec` serialization
  (`to_dict`/`from_dict`) byte-identical for existing specs lacking the new fields (AC7).
- Test: unmet host prerequisite with no permissive degrade posture → `BackendHaltError`
  (AC2).
- Test: unmet host prerequisite with a permissive captured posture → degrades exactly one
  `DEGRADE_LADDER` rung, never more (AC3).
- Test: under-ceiling dispatch against a fixture `spend_envelope` clears with no halt/receipt
  (AC5).
- Test: over-ceiling or tier-escalating dispatch against a fixture `spend_envelope` raises a
  typed halt requiring step-up, with no fallthrough to a degraded tier (AC6).

### Verification
```bash
uv run pytest tests/test_outcome_dispatcher.py -v
uv run pytest tests/test_outcome_spec.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the new spend-gate and posture-capture tests pass alongside the full
existing `/outcome` dispatcher suite (no regression to `resolve_available`/`degrade_decision`
behavior for specs without a captured `Intent`).

## Handoff maturity

requirements-ready

## Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` (ids `T8-F6-8`,
  `T8-F5-7`) and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`.
- Source type: ideation issue-map (`issue-map-final.json`, slug
  `pf-outcome-backend-spend-envelope`).
- Source title: Backend + degrade posture and spend envelope captured once, enforced at the
  dispatch seam.

### Intent

Today the `/outcome` engine's backend-and-degrade posture and its spend ceiling are each decided **per leaf, at dispatch time**, not captured once at run start:

### Context library links

_none_

### Objective

"Ship run-start intent envelope for lifecycle autonomy"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/373
- Number: 373
- Created at: 2026-07-04T07:53:10.705301+00:00

