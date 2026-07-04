---
title: capability: one committed IntentEnvelope for run-start posture across the plugin fleet
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Ship run-start intent envelope for lifecycle autonomy
---

# capability: one committed IntentEnvelope for run-start posture across the plugin fleet

### Objective

Ship run-start intent envelope for lifecycle autonomy.

### Tier / Type / Wave

- Tier: structural
- Type: capability
- Wave: wave-1

## Problem / Motivation

Run-start posture — attended vs. unattended, spend appetite, which ceremony gates apply — is
asked (or silently assumed) independently at five-plus sites across the fleet today, with no
shared schema and no single interview:

- `plugins/saga/scripts/execution_spec.py:52-53` defines the fleet's only operator-facing
  model/effort vocabulary (`MODELS`, `EFFORTS`), consumed solely by `/plan`'s per-unit tier table
  (`plugins/saga/skills/plan/SKILL.md:296-352`). Every agent frontmatter across all 8 plugins
  hardcodes `model:` with zero `effort:` fields and no dispatch-time override lever outside
  saga's readonly-verifier per-call pattern (grounding brief §1) — there is no shared posture
  primitive any of them import.
- `plugins/saga/scripts/outcome_spec.py:352-430` (`OutcomeSpec`) has no posture, autonomy, or
  ceremony-gate field at all — `/outcome start` has nowhere to read a committed run-start
  decision from, so every run either re-interrogates the operator or silently defaults.
- The grounding brief's negative-space finding (`G-negative-space-1`, survivors/T12.json)
  independently derives the same conclusion from theme-mining: five parallel per-theme posture
  envelopes exist across the ideation corpus with no shared schema and no single run-start
  interview — a fleet-wide drift risk if each consumer keeps inventing its own posture question.
- Pre-existing seed `S-22` (docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json,
  carried from this repo's `QUEUED.md`, grounding brief §5) already records the operator's
  standing ask: "`/outcome` should interrogate autonomy + which lifecycle steps, with
  recommendations from the prompt/issue" — today `/outcome` does neither.
- Binding decision `{#operator-choice-framework}` (grounding brief §2) already settles that
  operator-choice is doc-only and CLI-driven, not a runtime-injected mechanism — this envelope
  must be the single doc-plus-schema surface that decision anticipates, not a new competing one.

Without a shared envelope, every plugin that needs a spend/autonomy decision (saga `/plan`,
saga `/outcome`, team-execution's ceremony gates, mission-control's issue capture) either grows
its own bespoke posture question (drift, inconsistent defaults, re-asking the operator who
already answered once on the issue) or silently assumes a posture with no record of why.

## Definition of Done

A merged `intent_envelope.py` module (proposed path: `plugins/saga/scripts/intent_envelope.py`,
mirroring the `execution_spec.py` / `outcome_spec.py` pattern already established there) that:

1. Defines the canonical `IntentEnvelope` schema: `run_mode` (`attended` | `unattended`),
   `ceremony_gates` (`reviews_required`, `merge`, `deploy_nonprod` — each `gate` | `auto`,
   defaulting to `gate` when unset), and a computed-defaults hook keyed on `(work_shape,
   run_mode)`.
2. Implements one composed run-start posture interview (the single asker) plus a
   `recommend_tier(work_shape, run_mode)` helper and a `spend_posture(run_mode)` resolver
   returning `(default_posture, approval_rule)`.
3. Round-trips through `to_dict` / `from_dict` and seeds per-unit defaults on `ExecutionSpec`
   and `OutcomeSpec` consumers.
4. Ships consumption shims so `/outcome`, `/work`, `/plan`, and team-execution's Step B1 posture
   check all resolve through the envelope registry instead of asking their own question.
5. Ships a fleet-wide drift-guard test asserting no consumer defines a posture question outside
   the envelope registry (grep-based or AST-based guard, committed under `tests/`).
6. Ships mission-control issue-capture wiring so a ship-policy envelope authored at intent
   capture on the GitHub issue is read by `/outcome start`, which skips the interview when a
   valid envelope is already present.

Verified by: the drift-guard test passing, `execution_spec.py`/`outcome_spec.py` round-trip
tests passing, and the acceptance criteria below all green under `uv run pytest`.

### Acceptance criteria
One per absorbed facet, at minimum:

- [ ] **Single interview, drift-guarded** (`G-negative-space-1`): there is exactly one run-start
  posture interview in the fleet. Check: `uv run pytest tests/test_intent_envelope.py -k
  drift_guard` passes, asserting no other module defines a posture-shaped prompt/question
  outside `intent_envelope.py`'s registry.
- [ ] **Round-trip and per-unit seeding** (`T12-F1-2`): the posture field round-trips through
  `to_dict`/`from_dict` and seeds per-unit tier defaults. Check: `uv run pytest
  tests/test_intent_envelope.py -k round_trip_seeds_defaults` passes.
- [ ] **Mode-keyed spend posture is machinery, not prose** (`T12-F3-7`): `spend_posture(run_mode)`
  returns `(default_posture, approval_rule)`; unattended resolves to cache-tight/silent,
  attended resolves to ask-on-spend-increase without an approval token. Check: `uv run pytest
  tests/test_intent_envelope.py -k spend_posture_unattended_silent` and `-k
  spend_posture_attended_requires_token` both pass.
- [ ] **Data-backed posture prompt** (`T4-F4-2`): the interview prompt shows computed
  `parallel_width` and `critical_path_estimate` (reusing `critical_path_wall` per the emitter's
  existing A7-table logic), not prose guesswork. Check: `uv run pytest
  tests/test_intent_envelope.py -k posture_prompt_shows_stakes` over a known
  independent-vs-chained fixture asserts both numbers appear.
- [ ] **Mode-aware tier recommendation** (`T12-F6-7`): `recommend_tier(work_shape, run_mode)`
  recommends a cheaper default tier under `unattended` than under `attended` for the same
  `work_shape`. Check: `uv run pytest tests/test_intent_envelope.py -k
  recommend_tier_cheaper_unattended` passes.
- [ ] **Shared posture primitive with a real consumer** (`T4-F4-1`): `intent_envelope.py`'s
  resolver is imported by at least one wired fan-out consumer (team-execution Step B1); the
  attended+spend-increase path raises `PostureError` without an approval token, the unattended
  path returns cache-tight silently. Check: `uv run pytest
  tests/test_intent_envelope.py -k posture_error_without_token` and `-k
  posture_unattended_silent_path` both pass.
- [ ] **Envelope round-trips issue → envelope → consumer** (`G-hybrids-4`): a ship-policy
  envelope authored at mission-control issue capture survives to a saga consumer unchanged, and
  re-prompting is drift-guarded (no consumer re-asks a question the envelope already answers).
  Check: `uv run pytest tests/test_intent_envelope.py -k
  issue_to_consumer_round_trip_no_reprompt` passes.
- [ ] **`intent` dataclass on `OutcomeSpec`** (`T8-F1-3`): an `intent` field added to
  `OutcomeSpec` round-trips through `to_dict`/`from_dict`/`validate` (mirroring the existing
  `decision_trail`/`cost_rollup` field pattern at `plugins/saga/scripts/outcome_spec.py:352-372`),
  and `reviews_required` (nested under `ceremony_gates`) gates a leaf `done` transition. Check:
  `uv run pytest tests/test_outcome_spec.py -k intent_round_trip` and `-k
  reviews_required_gates_done` both pass.
- [ ] **Ceremony gates default to gate, not auto** (`T7-F3-2`): the `ceremony_gates` block
  (`reviews_required`, `merge`, `deploy_nonprod`) is a pre-declared envelope field, not an
  interactive re-ask; an unset field defaults to `gate`. Check: `uv run pytest
  tests/test_intent_envelope.py -k ceremony_gates_default_to_gate` passes, and the field
  round-trips through save/load.
- [ ] **Issue-capture wiring skips the interview when present** (`T7-F6-7`, `H-F2-9`,
  `S-22`): mission-control issue capture writes the ship-policy envelope onto the issue body
  (schema-validated, not prose); `/outcome start` reads it and skips the run-start interview
  when a valid envelope is already present, and only falls back to asking when it is absent or
  invalid. Check: `uv run pytest tests/test_intent_envelope.py -k
  outcome_start_skips_interview_when_envelope_present` and `-k
  outcome_start_asks_when_envelope_absent` both pass.
- [ ] **Challenge-response manifest shape** (`T1-F5-8`): the interview is structured as a
  bounded challenge-response manifest (fixed question set, typed answers), not free-form prose
  capture, so it is machine-parseable end to end. Check: `uv run pytest
  tests/test_intent_envelope.py -k manifest_is_typed_not_freeform` passes.
- [ ] **Mode→intent default matrix** (`T1-F6-8`): unattended runs select their own posture
  defaults from the same `(work_shape, run_mode)` matrix used by `recommend_tier`, without
  requiring an interactive answer. Check: `uv run pytest tests/test_intent_envelope.py -k
  unattended_run_self_selects_posture` passes.

### Out-of-scope / non-goals
In scope:
- One new `intent_envelope.py` module (schema + interview + resolvers) under
  `plugins/saga/scripts/`.
- Minimal consumption shims in `/outcome`, `/work`, `/plan`, and team-execution Step B1 — read
  from the envelope registry, do not duplicate posture logic.
- One mission-control issue-capture wiring point that writes/reads the envelope on the issue.
- The drift-guard test.

Out of scope (non-goals):
- Rewriting or restructuring `/plan`'s existing tier table UX (`plugins/saga/skills/plan/SKILL.md:296-352`)
  beyond wiring it to read defaults from the envelope — the table itself, its operator-override
  flow, and the `VERIFY_N_CAP` mechanics stay as-is.
- Any change to team-execution's existing proceed-best-available iteration cap — this issue
  adds a posture *read*, not a change to iteration/consensus behavior.
- Building `T7-F6-7`'s full "self-shipping issue executable ship-policy" runtime — this issue
  ships the `ceremony_gates` schema fields the ship-policy would consume, not an executor that
  autonomously ships. Full self-shipping execution is a moonshot-tier follow-on (see
  `T7-F6-7`'s `tier_tag: moonshot` in the survivor corpus) and is explicitly deferred.
- Backfilling posture defaults onto every existing agent frontmatter's hardcoded `model:` field
  fleet-wide — this issue delivers the shared primitive and one wired consumer
  (team-execution Step B1); fleet-wide backfill is a separate follow-on with its own blast
  radius.
- Any change to the `MODELS`/`EFFORTS` vocabulary itself (`execution_spec.py:52-53`) — the
  envelope consumes that vocabulary, it does not redefine it.

## Grounding References

- `G-negative-space-1` (primary; docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json)
  — "One fleet intent envelope: merge the five parallel per-theme posture envelopes into a
  single shared schema and a single run-start interview." Direct basis; `dod_sketch`: merged
  `intent_envelope.py` (schema + composed run-start interview) + consumption shims in
  `/outcome`, `/work`, `/plan`, team-execution; verified by a drift-guard test.
- `T12-F1-2` (facet; T12.json) — "Run-start tier posture asked once, seeding the per-unit table
  instead of per-unit interrogation." `dod_sketch`: merged posture field + run-start posture
  step on `ExecutionSpec`/plan, verified by an `execution_spec` test asserting posture seeds
  per-unit defaults and round-trips.
- `T12-F3-7` (facet; T12.json) — "Encode the mode→posture mapping as machinery, not prose
  buried in an intake brief." `dod_sketch`: merged `spend_posture.py` returning
  `(default_posture, approval_rule)` keyed on run-mode.
- `T12-F6-7` (facet; T12.json) — "Mode-aware recommender: attended recommends throughput,
  unattended recommends cheapest-defensible." `dod_sketch`: merged `recommend_tier(work_shape,
  run_mode)` helper + plan Step-1 mode-conditioned rows.
- `T4-F4-1` (facet; T4.json) — "Shared run-posture primitive (`execution_posture.py`) every
  fan-out site imports." `dod_sketch`: resolver + `PostureError` + one wired consumer
  (team-execution Step B1); attended+spend-increase raises without an approval token,
  unattended returns cache-tight silently; release-surface bump.
- `T4-F4-2` (facet; T4.json) — "Data-backed posture prompt: emitter computes parallel-width vs
  critical-path depth." `dod_sketch`: emitter emits `parallel_width` +
  `critical_path_estimate` (reusing `critical_path_wall`) into the A7 table and posture-prompt
  copy.
- `H-F2-9` (dedup-merged; T8.json, thin seed — title only, no `idea`/`basis`/`dod_sketch` body
  survived): "Ask-once intent envelope: capture autonomy answers on the issue, so `/outcome
  start` never re-interrogates." Reconstructed from title + theme T8 (intent-dialog-design) +
  grounding brief §5 seed `S-22`'s framing of `/outcome` needing to interrogate autonomy with
  recommendations from the prompt/issue.
- `T1-F5-8` (dedup-merged; T1.json, thin seed): "Challenge-response run-start intent manifest."
  Reconstructed from title + theme T1 (operator-ergonomics) — a typed, bounded question/answer
  manifest rather than free-form capture.
- `T1-F6-8` (dedup-merged; T1.json, thin seed): "Mode→intent default matrix: unattended runs
  pick their own posture." Reconstructed from title + theme T1 (operator-ergonomics), consistent
  with `T12-F6-7`'s mode-aware recommender facet.
- `S-22` (dedup-merged; docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json) — seed
  carried from this repo's `QUEUED.md` (grounding brief §5): "`/outcome` should interrogate
  autonomy + which lifecycle steps with recommendations from the prompt/issue." Basis type:
  direct, operator statement.
- `G-hybrids-4` (primary; T8.json, thin seed): "One committed IntentEnvelope from issue handoff
  to every spend and autonomy gate." Reconstructed from title + theme T8
  (intent-envelope-spine) — the cross-plugin spine this whole issue is named for.
- `T8-F1-3` (facet; T8.json): "Canonical `intent` envelope: capture the mandated start-time
  posture questions once." `dod_sketch` (partially readable): an `intent` dataclass on
  `OutcomeSpec` round-trips `to_dict`/`from_dict`/`validate`; `reviews_required` gates a leaf
  `done` transition.
- `T7-F3-2` (facet; T7.json): "Ceremony gates are pre-declared envelope fields, not interactive
  re-asks." `dod_sketch`: merged `ceremony_gates` block (`reviews_required`, `merge`,
  `deploy_nonprod`) in the intent-capture envelope schema; drift-guard test asserts the field
  round-trips through save/load and an unset field defaults to gate.
- `T7-F6-7` (facet; T7.json, thin seed, `tier_tag: moonshot`): "Self-shipping issue — an
  executable ship policy authored at intent capture." Reconstructed from title + theme T7
  (ship-verb) — this issue ships the schema fields (`ceremony_gates`) the moonshot would consume;
  the executable ship-policy runtime itself is explicitly out of scope (see Non-Goals).

Binding decisions this issue builds on (grounding brief §2):
- `{#operator-choice-framework}` — operator-choice stays doc-only and CLI-driven; this envelope
  is the single doc-plus-schema surface, not a new runtime-injected mechanism.
- `{#tier-vocab-ordering}` — the `MODELS`/`EFFORTS` tuples are ordered escalation ladders; the
  envelope's `recommend_tier` must respect that ordering, not just treat them as closed sets.
- `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an active concern; this issue
  consolidates five parallel posture envelopes into one shared primitive rather than adding a
  sixth.

Fleet-map facts this issue is grounded against (grounding brief §1): saga 0.51.0 is the sole
home of the `MODELS`/`EFFORTS` vocabulary (`execution_spec.py:52-53`); zero `effort:` fields
exist across all 8 plugins' agent frontmatter; no dispatch-time override lever exists outside
saga's readonly-verifier per-call pattern — this issue is the first fleet-wide posture primitive.

## Recommended Executor Profile

- Model: `opus`
- Effort: `high` — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: `team-execution`
- External LLM posture: `second-opinion`

Justification (required — profile is above sonnet): this is a cross-plugin schema consumed by
every autonomy and spend gate in the fleet (saga `/plan`, `/outcome`, `/work`, team-execution
ceremony gates, mission-control issue capture). A design mistake here — wrong default direction,
a posture question left un-consolidated, a drift-guard with a hole — propagates to every
consumer and is expensive to unwind once wired. The architectural blast radius and the
adversarial-verification value of a second opinion (per `{#external-engine-chaperone-dispatch}`:
second-opinion routes to opus/high, never a second executor/git participant) both justify Opus
plus an advisory second opinion rather than a Sonnet default.

## Release-Surface Checklist

This issue changes plugin behavior (a new schema module, a fleet-wide consumption contract, and
an issue-capture wiring point), so update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (from `0.51.0`) reflecting the
  new `intent_envelope.py` module and `OutcomeSpec.intent` schema addition.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump (from `2.9.0`)
  reflecting the Step B1 posture-check consumption shim.
- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump (from `2.4.0`)
  reflecting the issue-capture ship-policy envelope wiring.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for saga, team-execution, and
  mission-control entries.
- [ ] `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`,
  `plugins/mission-control/CHANGELOG.md` — entries describing the new shared posture primitive
  and each plugin's consumption point.
- [ ] Drift-guard test (this issue's own AC) doubles as the metadata drift guard for "no
  consumer defines its own posture question" — confirm it is wired into `uv run pytest`'s
  default collection, not opt-in.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine:

- `plugins/saga/scripts/intent_envelope.py` — new module (schema, interview, `recommend_tier`,
  `spend_posture`, `PostureError`).
- `plugins/saga/scripts/outcome_spec.py` — add `intent` field to `OutcomeSpec`
  (`to_dict`/`from_dict`/`validate`).
- `plugins/saga/scripts/execution_spec.py` — wire per-unit tier defaults to read from the
  envelope.
- `plugins/saga/skills/outcome/SKILL.md` — `/outcome start` reads the envelope, skips interview
  when present.
- `plugins/saga/skills/plan/SKILL.md` — Step 1 tier table reads posture defaults from the
  envelope.
- `plugins/team-execution/skills/team-execution/references/` — Step B1 posture-check consumer.
- `plugins/mission-control/` — issue-capture wiring writing the ship-policy envelope.
- `tests/test_intent_envelope.py` — new test module (all AC checks above).
- `tests/test_outcome_spec.py` — `intent` round-trip and `reviews_required` gate tests.

### Tests to add or update

- `tests/test_intent_envelope.py` — drift guard, round-trip/seed defaults, `spend_posture`
  (unattended silent / attended requires token), posture-prompt stakes fixture,
  `recommend_tier` mode comparison, `PostureError` path, issue-to-consumer round trip,
  ceremony-gates default-to-gate, outcome-start skip/ask branches, manifest typed-not-freeform,
  unattended self-selection.
- `tests/test_outcome_spec.py` — `intent` field round-trip; `reviews_required` gates a leaf
  `done` transition.

### Verification

```bash
uv run pytest tests/test_intent_envelope.py -v
uv run pytest tests/test_outcome_spec.py -k intent -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; drift-guard test asserts no consumer outside `intent_envelope.py` defines
a posture question.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/issue-map/issue-map-final.json
  (slug `pf-runstart-intent-envelope`)
- Source type: ideation issue-map
- Source title: One committed IntentEnvelope: run-start posture interview, issue-carried ship
  policy, shared posture primitive consumed by every autonomy and spend gate

### Intent

Run-start posture — attended vs. unattended, spend appetite, which ceremony gates apply — is asked (or silently assumed) independently at five-plus sites across the fleet today, with no shared schema and no single interview:

### Context library links

_none_

### Inputs inventory

- `plugins/saga/scripts/intent_envelope.py`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `plugins/mission-control/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/380
- Number: 380
- Created at: 2026-07-04T07:55:12.796618+00:00

