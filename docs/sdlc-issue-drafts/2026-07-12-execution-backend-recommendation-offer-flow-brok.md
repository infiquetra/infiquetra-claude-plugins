---
title: Execution-backend recommendation + offer flow broken in /plan Phase 5.2
repo: infiquetra-claude-plugins
type: defect
team: campps
project: operations
status: Idea
labels: defect, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# Execution-backend recommendation + offer flow broken in /plan Phase 5.2

### Objective

Fix the `/plan` Phase 5.2 execution-backend recommendation and offer flow, which misfired in four
independent ways while planning #526 (2026-07-11, operator-directed: "both need fixed"), plus the
adjacent verify-panel tier gap surfaced in the same session. Source: repo QUEUED
`{#plan-backend-recommendation-broken}`, scheduled immediately after the ship-ceremony-hardening
outcome — which completed 2026-07-12 (objective #340, PRs #561/#562/#563/#564).

The four defects:

1. **Crude size signal.** `should_offer_team_execution`'s `file_count >= 8` trigger
   (`plugins/saga/scripts/lifecycle_state.py:77`, consumed by `recommend_execution_backend` at
   `lifecycle_state.py:100`) counted 6 one-line release-surface bumps (plugin.json,
   marketplace.json, CHANGELOGs, drift pins) toward a 9-file total and recommended
   `team-execution` for a single-script defect fix. The signal must weigh *functional* surface
   (feature-bearing files), not raw touched-file count — release bookkeeping is constant overhead
   on every PR in this repo.
2. **Workflows undersold.** The ultracode triggers are only `broad_independent_fanout` /
   `adversarial_confidence` / advisory-consensus. Operator: "workflows are more than breadth" —
   the Workflow tool's own doc names understand/design/research/migrate shapes that the
   recommender and `/plan` SKILL.md's Phase-5.2 framing cannot reach. The trigger vocabulary (and
   the skill prose mirroring it) needs widening.
3. **Availability trusted, not probed.** `workflow_available` is caller-asserted
   (`lifecycle_state.py:113`); in the live session the caller passed `False` unverified and the
   ultracode option vanished from the operator's offer entirely. Availability must be observably
   probed (ToolSearch for the Workflow tool) at offer time, and the recommender/skill contract
   must state so.
4. **Offer construction hid the alternative.** Even with `omit_ultracode: true`
   (`lifecycle_state.py:202`/`:210`), the `/plan` offer showed only two options with no note that
   a third backend existed — the operator had to ask. The offer must always name all three
   backends (inline / team-execution / cc-workflows-ultracode) and mark unavailable ones as such,
   never silently drop them.

Adjacent gap (same session): **verify panels cannot carry their own tier** — R4 binds every
verifier to the unit's tier unconditionally (single verifier-opts site in
`plugins/saga/scripts/execution_spec.py` ~1500-1517; the `Verify` dataclass at
`execution_spec.py:531` has no tier field), so the operator's request for an opus/high refute-3
panel on a sonnet/medium unit forced the whole unit up to opus/high.

### Intent

- `plugins/saga/scripts/lifecycle_state.py`: rework the size signal to weigh functional surface
  (a functional-file count or release-surface discount) instead of raw `file_count`; widen the
  ultracode trigger vocabulary beyond breadth/adversarial to the workflow shapes the tool doc
  names (understand / design / research / migrate); make the availability contract explicit —
  the recommender output carries how availability was determined (probed vs asserted) and the
  offer payload always enumerates all three backends with an availability/omission note.
- `plugins/saga/skills/plan/SKILL.md` Phase 5.2: offer flow presents all three backends every
  time, marking unavailable ones; prose mirrors the widened trigger vocabulary; availability line
  mandates a live ToolSearch probe before the offer.
- `plugins/saga/scripts/execution_spec.py`: optional per-panel tier on `Verify` (model/effort)
  defaulting to the unit tier; the single verifier-opts emit site uses the panel tier; the
  premium-tier receipts rule (`worth_it_because` / `cheaper_fallback`) applies when the panel
  tier is premium; `spend` accounts the panel tier. Specs without the field emit byte-identical
  output (R4 preserved).

### Out-of-scope / non-goals

- The separate QUEUED brainstorm/ideate convergence-bias entry that follows this one in
  `docs/engineering-journal/QUEUED.md` — different item, no code overlap.
- Backend execution mechanics themselves (team-execution internals, workflow emitter thunk
  shapes) beyond the `Verify` tier field.
- Board/mission-control surfaces.

### Files expected to change

- `plugins/saga/scripts/lifecycle_state.py`
- `plugins/saga/scripts/execution_spec.py`
- `plugins/saga/skills/plan/SKILL.md`
- `tests/test_lifecycle_state.py`
- `tests/test_execution_spec.py`
- `plugins/saga/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` +
  `plugins/saga/CHANGELOG.md` + `tests/test_saga_plugin.py` (release surfaces, same PR)

### Tests to add or update

- Regression test reproducing the #526 planning shape: functionally-small change with heavy
  release-surface bookkeeping (3 functional + 6 bookkeeping files) must NOT recommend
  `team-execution`.
- Trigger test: at least one non-breadth workflow shape (research/understand class) reaches the
  ultracode recommendation.
- Offer-payload contract test: `recommend_execution_backend` output enumerates all three backends
  with availability/omission reasons; no silent drop under `workflow_available=False`.
- `Verify` panel-tier tests: panel tier overrides unit tier at the verifier spawn site in emitted
  JS; omitted field emits byte-identical output to today; premium panel tier without receipts
  fails `validate --require-receipts`; `spend` reflects panel tier.

### Context library links

- `docs/engineering-journal/QUEUED.md` `{#plan-backend-recommendation-broken}` (canonical defect
  record with operator feedback verbatim)

### Acceptance criteria

- [ ] Release-surface-heavy/functionally-small shape no longer trips team-execution:
      `uv run pytest tests/test_lifecycle_state.py -k "release_surface or functional_surface" -q`
      passes with the #526-shape regression test collected (non-vacuous).
- [ ] Non-breadth ultracode trigger exists and is tested:
      `uv run pytest tests/test_lifecycle_state.py -k "workflow_shape or research or understand" -q`
      passes.
- [ ] Offer payload never silently drops a backend:
      `uv run pytest tests/test_lifecycle_state.py -k "three_backends or omission_reason" -q`
      passes, including the `workflow_available=False` case asserting all three backends named.
- [ ] `/plan` SKILL.md Phase 5.2 names all three backends, the ToolSearch availability probe, and
      the widened trigger vocabulary: `grep -n "ToolSearch" plugins/saga/skills/plan/SKILL.md`
      returns at least one Phase-5.2 hit.
- [ ] `Verify` carries an optional panel tier honored by the emitter, byte-identical emission
      when omitted, receipts enforced for premium panel tiers:
      `uv run pytest tests/test_execution_spec.py -k "panel_tier" -q` passes.
- [ ] Full battery green: `uv run pytest -q`, `uv run ruff check .`,
      `uv run ruff format --check .`,
      `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`.

### Verification

```bash
uv run pytest tests/test_lifecycle_state.py tests/test_execution_spec.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: repo QUEUED `{#plan-backend-recommendation-broken}` (docs/engineering-journal/QUEUED.md)
- Source type: local-file
- Source title: Fix the execution-backend recommendation + offer flow in `/plan` Phase 5.2

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/565
- Number: 565
- Created at: 2026-07-12T16:15:17.653716+00:00

