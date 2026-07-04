---
title: "enhancement: rubber-stamp telemetry for operator gate decisions"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
objective: Build the fleet telemetry and ledger substrate
tier: quick-win
wave: wave-2
---

# enhancement: rubber-stamp telemetry for operator gate decisions

### Objective
Build the fleet telemetry and ledger substrate

### Intent
Give every operator-facing gate a recorded outcome — the recommendation or default offered, the
decision the operator actually made, and how long it took them — and surface a per-gate
divergence-rate summary at `/retro` so future arguments for widening the autonomous-progression
allowlist are backed by measured rubber-stamp rates instead of vibes. This is a measurement facet
only: it does not change what any gate does, does not add new gates, and does not itself widen any
allowlist. It produces the evidence a later widening decision would cite.

### Problem / motivation

**The fleet already has one narrow instance of exactly this measurement, and it proves the pattern
works but doesn't cover most gates.** `plugins/saga/scripts/override_rate_reader.py` computes an
override rate — the fraction of sagas where `orchestration_operator_choice`
(`plugins/saga/scripts/saga.py:174-175`) differs from `orchestration_recommended` — plus over/under-tier
skew, and is consumed read-only in `/retro` Phase 1.6
(`plugins/saga/skills/retro/SKILL.md:188-206`, wired since the R12 campaign). That reader answers one
question ("did the operator override the recommended execution backend?") for one gate. It has no
analog for the fleet's many *other* interactive decision gates — mode selection, fix-vs-diagnosis
choice, per-expansion opt-in, merge/deploy confirmation — each of which is currently just an
`AskUserQuestion` call with no recorded default-vs-answer pair anywhere.

**Those other gates are real and undermeasured.** `AskUserQuestion` is the named gate mechanism at
`plugins/saga/skills/brainstorm/SKILL.md:31`, `plugins/saga/skills/founder-review/SKILL.md:80-85`
(mode selection, execution-backend choice), `plugins/saga/skills/investigate/SKILL.md:91-98`
(fix-vs-diagnosis-vs-rethink), `plugins/saga/skills/loop/SKILL.md:72-74` (mode/destination), and
`plugins/saga/skills/outcome/SKILL.md:154-161` (coordinator-level decisions) — none of these record
whether the option pre-selected or recommended is the one the operator actually picked, or how long
they took to answer. Session-mining synthesis (workflow `wf_7e5d77a2-5c0`, 27 sessions, 175 findings)
independently ranks "gate-primitive unreliability" as the #2 recurring cross-repo pattern
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122-125`), and this repo's own binding-decision
register flags external-autonomy-widening as the fleet's hottest active frontier
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:107-108`, section 6 item 4). Any future
argument to auto-progress a currently-gated status needs the divergence evidence this issue produces;
today that argument has none for anything except the one orchestration-backend gate.

**A durable per-gate record is the natural place to hang this, and one already exists for a related
but distinct concern.** The `Saga` envelope carries `gate_verdicts`
(`plugins/saga/scripts/saga.py:217`, added per `plugins/saga/CHANGELOG.md:274-283`) — a full-snapshot
list of automated check-gate pass/fail states (test gate, review gate), consumed by
`status_card.py:253-276`. `gate_verdicts` answers "did the automated check pass," not "did the
operator's answer diverge from what was offered." This issue adds a sibling field for interactive
decision-gate telemetry rather than overloading `gate_verdicts` with a differently-shaped concern.

### Out-of-scope / non-goals
In scope:
- A gate-interaction telemetry record (gate id, recommendation/default offered, operator's actual
  answer, a divergence bit, and latency between offer and answer) appended to saga state at each
  operator gate interaction.
- A read-only `/retro` summary reporting, per gate id, the rubber-stamp rate (fraction where the
  answer matched the offered default/recommendation) across sagas, following the same
  `override_rate_reader.py` zero-data-contract pattern (report "no data yet," never a fabricated 0%).
- Wiring this telemetry into the gate sites that currently offer a recommendation or pre-selected
  default and are reachable from saga skills today (the `AskUserQuestion` sites cited above, plus the
  existing orchestration-backend gate).

Out of scope (non-goals):
- Changing `override_rate_reader.py`'s existing orchestration-backend-choice logic or its consumption
  in `/retro` Phase 1.6 — this issue adds a separate, broader reader; it does not fold the
  orchestration-backend gate's existing fields into the new one or vice versa.
- Building the durable gate-record / pluggable-transport / absence-behavior primitive
  (`H-F3-3`/`H-F6-5`, tracked separately as `pf-durable-gate-records`). That issue defines what a gate
  *is* structurally, including no-answer behavior; this issue only adds a telemetry field to whatever
  gate-firing event already exists (today, an `AskUserQuestion` call site) and does not depend on that
  primitive shipping first — it can be layered onto the current ad hoc gate sites and re-pointed at
  the durable record later if/when that issue lands.
- Widening any autonomous-progression allowlist. This issue produces the divergence evidence such a
  decision would cite; it does not itself move any status transition from gated to autonomous.
- Modifying `gate_verdicts` or its automated-check-gate semantics
  (`plugins/saga/scripts/saga.py:217`, `status_card.py:253-276`) — a distinct, already-shipped concern.
- A new UI or notification surface for the `/retro` summary; it renders as a table in the existing
  retro Phase-1 evidence block, following the `override_rate_reader.py --json` precedent.

## Definition of Done

A merged PR that adds:
1. A `gate_divergence` (or equivalently named) full-snapshot list field on the `Saga` envelope
   (`plugins/saga/scripts/saga.py`), following the existing `gate_verdicts`/`orchestration_recommended`
   field pattern — each entry records gate id, offered default/recommendation, operator's answer, a
   derived divergence bit, and the offer-to-answer latency.
2. A write helper invoked at each currently-instrumented gate site (the `AskUserQuestion` call sites
   cited above) that appends a `gate_divergence` entry before the gate's decision is acted on.
3. A read-only telemetry reader (proposed: `plugins/saga/scripts/gate_divergence_reader.py`, modeled
   on `override_rate_reader.py`'s pure-function/injectable-root house pattern) that scans saga
   envelopes and reports, per gate id, the rubber-stamp rate and a zero-data "no data yet" state when
   no interactions are recorded yet.
4. A `/retro` Phase-1 evidence wiring (`plugins/saga/skills/retro/SKILL.md`) that runs the new reader
   read-only alongside the existing override-rate reader and includes its output verbatim in the
   evidence block.
5. Tests proving: a gate interaction appends a `gate_divergence` entry with a correct divergence bit
   when the answer differs from the offered default and a false bit when it matches; latency is
   recorded; the reader reports "no data yet" with zero recorded interactions and a correct per-gate
   rate once data exists; the reader never writes to disk.
6. Release-surface updates: `plugins/saga/CHANGELOG.md` entry, `plugins/saga/.claude-plugin/plugin.json`
   version bump, root `.claude-plugin/marketplace.json` version sync, and the existing version-parity
   drift-guard test passing with the bump reflected.

### Acceptance criteria
- [ ] **(Facet — each gate interaction records recommendation, decision, and latency.)** A gate
  interaction wired to the new helper appends a `gate_divergence` entry containing the gate id, the
  offered default/recommendation, the operator's actual answer, and a latency value between offer and
  answer. Check: `uv run pytest tests/test_gate_divergence.py -k records_interaction` → passes.
- [ ] **(Divergence bit is derived correctly.)** An entry where the answer differs from the offered
  default carries a divergence bit of `true`; an entry where the answer matches carries `false`. Check:
  `uv run pytest tests/test_gate_divergence.py -k divergence_bit` → passes.
- [ ] **(Full-snapshot round-trip.)** `gate_divergence` round-trips through `Saga.save`/`parse_envelope`
  without dropping entries or corrupting fields, matching the existing `gate_verdicts` full-snapshot
  semantics. Check: `uv run pytest tests/test_gate_divergence.py -k roundtrip` → passes.
- [ ] **(Facet — a summary shows per-gate rubber-stamp rate over a run.)** The reader, run against a
  fixture set of sagas with recorded `gate_divergence` entries across at least two distinct gate ids,
  reports a rubber-stamp rate (1 − divergence rate) per gate id. Check:
  `python3 plugins/saga/scripts/gate_divergence_reader.py --root tests/fixtures/gate_divergence_sagas --json` →
  exit `0`, output contains a per-gate-id rate keyed by gate id.
- [ ] **(Zero-data contract.)** Run against a root with no recorded `gate_divergence` data reports "no
  data yet" per gate id, never a fabricated `0%`/`0.0` rate. Check:
  `uv run pytest tests/test_gate_divergence_reader.py -k zero_data_reports_no_data_yet` → passes.
- [ ] **(Read-only.)** The reader never writes to the saga store or filesystem it scans. Check:
  `uv run pytest tests/test_gate_divergence_reader.py -k reader_is_read_only` → passes.
- [ ] **(`/retro` wiring.)** `/retro` Phase 1.6 (or an adjacent numbered step) runs the new reader
  alongside the existing `override_rate_reader.py` call and includes its output in the evidence block.
  Check: `grep -n "gate_divergence_reader" plugins/saga/skills/retro/SKILL.md` → at least one match.
- [ ] **(Non-goal respected — orchestration-backend reader unchanged.)** `override_rate_reader.py`'s
  existing fields and CLI surface are untouched by this change. Check:
  `uv run pytest tests/test_override_rate_reader.py` → passes, no diff in
  `plugins/saga/scripts/override_rate_reader.py`'s public function signatures.
- [ ] **(Release surface.)** `plugins/saga/.claude-plugin/plugin.json` version, root
  `.claude-plugin/marketplace.json` version, and `plugins/saga/CHANGELOG.md` all reflect this change in
  the same PR. Check: the repo's existing version-parity drift-guard test (e.g.
  `uv run pytest tests/test_marketplace_drift.py`, or equivalent) → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

## Grounding References

- **Absorbed idea `H-F1-10`** (theme T7, frame F1, axis `gate-rent-audit`, tier: quick-win, survive) —
  "Rubber-stamp telemetry: measure whether each gate ever changes the path before deciding
  auto-progression." `dod_sketch`: gate-firing telemetry (gate id, default offered, answer given,
  divergence bit) appended to saga state plus a `/retro` report ranking gates by divergence rate and
  flagging rubber-stamp gates as auto-progression candidates. `ac_sketch`: "Each gate interaction
  records recommendation, decision, and latency"; "A summary shows per-gate rubber-stamp rate over a
  run." No `body`/`basis` field was recorded on this survivor entry (a thin seed); intent is
  reconstructed here from the `dod_sketch`/`ac_sketch` above plus the grounding brief's gate-primitive
  and autonomy-widening context (sections 5–6, cited below), and grounded further against this repo's
  existing `override_rate_reader.py` precedent found during drafting.
- **Existing precedent this issue extends**: `plugins/saga/scripts/override_rate_reader.py` (R12
  telemetry reader — override rate, over/under-tier skew, zero-data contract), consumed in
  `plugins/saga/skills/retro/SKILL.md:188-206`. This issue generalizes the same reader shape from one
  gate (orchestration-backend choice) to the fleet's interactive decision gates broadly, without
  modifying the existing reader.
- **Existing but distinct field this issue does not touch**: `Saga.gate_verdicts`
  (`plugins/saga/scripts/saga.py:217`, `plugins/saga/CHANGELOG.md:274-283`) — automated check-gate
  pass/fail state, consumed by `status_card.py:253-276`. Different shape and different question
  ("did the check pass" vs. "did the operator's answer diverge").
- **Recurring-pain grounding**: session-mining synthesis ranks "gate-primitive unreliability" #2 by
  repo spread (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122-125`); the binding-decision
  register names external-autonomy-widening as the hottest active frontier
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:107-108`); pre-existing repo seeds carry
  forward related asks (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:90-97`, section 5).
- **Binding decision — derive-on-read, never committed status (`/outcome` campaign)**
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`) — this telemetry is a full-snapshot
  append to saga state (matching `gate_verdicts`'/`orchestration_*`'s existing append pattern), and the
  `/retro` summary is computed on read from that state, not a separately committed status field.
- **Sibling, non-duplicate issue**: `pf-durable-gate-records` (absorbing `H-F3-3`/`H-F6-5`) builds the
  durable gate-record primitive with pluggable transports and a declared absence-behavior contract.
  This issue's telemetry is complementary and independent: it can be wired against today's ad hoc
  `AskUserQuestion` call sites now and re-pointed at that primitive's record schema later without
  rework, since the divergence-telemetry fields (recommendation, answer, latency) are a strict subset
  of information any gate-record mechanism would carry.

### Files expected to change

Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/saga.py` — new `gate_divergence` full-snapshot list field on the `Saga`
  dataclass, following the existing `gate_verdicts`/`orchestration_recommended` pattern.
- `plugins/saga/scripts/gate_divergence_reader.py` — new read-only telemetry reader (proposed path).
- `plugins/saga/skills/retro/SKILL.md` — Phase-1 evidence wiring alongside the existing
  `override_rate_reader.py` call.
- The `AskUserQuestion` gate call sites currently offering a recommendation/default (e.g.
  `plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/skills/founder-review/SKILL.md`,
  `plugins/saga/skills/investigate/SKILL.md`, `plugins/saga/skills/loop/SKILL.md`,
  `plugins/saga/skills/outcome/SKILL.md`) — instrumented to call the new write helper.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version sync.
- `plugins/saga/CHANGELOG.md` — entry for this change.
- `tests/test_gate_divergence.py` — new record/round-trip tests (repo-root collected).
- `tests/test_gate_divergence_reader.py` — new reader tests, including zero-data and read-only checks.
- `tests/fixtures/gate_divergence_sagas/` — fixture saga envelopes with recorded interactions.

### Tests to add or update
- Record: a gate interaction appends a correctly-shaped `gate_divergence` entry (gate id, offered
  default, answer, divergence bit, latency); round-trips through save/parse without loss.
- Divergence bit: `true` when answer differs from offered default, `false` when it matches.
- Reader: per-gate-id rubber-stamp rate computed correctly against a multi-saga fixture; reports "no
  data yet" with zero recorded interactions rather than a fabricated rate; never writes to disk.
- Regression: `override_rate_reader.py`'s existing public functions and CLI output are unchanged.
- Release-surface drift-guard test (plugin.json/marketplace.json version parity) still passes.

### Context library links
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md

### Recommended executor profile
- **Model:** Sonnet
- **Effort:** low
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** This is a small, self-contained, fully-specified measurement facet — one new
  saga envelope field, one reader module modeled directly on an existing house-pattern precedent
  (`override_rate_reader.py`), and a handful of call-site instrumentation edits. No architectural
  judgment call is required beyond following the precedent already in the repo, so sonnet at low
  effort, run inline, matches the mechanical shape of the work; it does not warrant team-execution
  fan-out or an opus-tier review lens.

### Verification
```bash
# New gate-divergence record + round-trip tests
uv run pytest tests/test_gate_divergence.py -v
# Reader: per-gate rate + zero-data contract + read-only
uv run pytest tests/test_gate_divergence_reader.py -v
python3 plugins/saga/scripts/gate_divergence_reader.py --root tests/fixtures/gate_divergence_sagas --json
# Existing orchestration-backend reader unaffected
uv run pytest tests/test_override_rate_reader.py
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the reader reports "no data yet" against an empty fixture root and a correct
per-gate rubber-stamp rate against the populated fixture; no diff in `override_rate_reader.py`.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: grounding-brief
- Source title: Plugin Fleet Ideation 2026-07-03 — Grounding Brief

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/399
- Number: 399
- Created at: 2026-07-04T08:01:25.864264+00:00

