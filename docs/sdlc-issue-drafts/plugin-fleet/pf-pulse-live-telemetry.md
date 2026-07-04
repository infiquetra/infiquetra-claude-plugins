---
title: "capability: Pulse live-telemetry component — board/agent/run state rendered from real signals"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: "Build the fleet telemetry and ledger substrate"
---

# capability: Pulse live-telemetry component — board/agent/run state rendered from real signals

### Objective

Build the fleet telemetry and ledger substrate (`wave-2`).

## Problem / Motivation

There is no live view of what the fleet is actually doing. `docs/engineering-journal/QUEUED.md:73`
("`{#pulse-live-telemetry-component}`") records this as a standing open item: a `/pulse`
continuous live-telemetry component, sourced from CE's `ce-product-pulse` engine, was
explicitly carved OUT of the `/founder-review` port rather than built — `/founder-review`
only stole `ce-product-pulse`'s "no-false-precision" posture (cite numbers, let the operator
judge; no hardcoded thresholds), staying qualitative with no live data
(DECISIONS `#founder-review-engine-rebuild`). The full read-only analytics/usage report shape
was deliberately "parked" for a separate job (`docs/engineering-journal/QUEUED.md:73`), and the
lifecycle-engine-merge-campaign closer explicitly named `/pulse` as one of the items that
"remains SEPARATE, open, queued" even after all 13 command rebuilds shipped
(`docs/engineering-journal/QUEUED.md:26`).

The 2026-07-03 grounding brief reconfirms this seed is still live and still un-scheduled: it is
listed among the pre-existing `QUEUED.md` seeds carried into ideation Phase D
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:90-97`, entry
`{#pulse-live-telemetry-component}`). Ideation's own survivor pass (`S-8`,
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`) kept the seed exactly as
queued — a "direct" basis citing the same brief section 5 anchor — with only a thin
`dod_sketch` and no elaborated body, because the underlying requirement has not changed since
it was queued: build a live-telemetry surface (board/agent/run state) rendered from *real*
signals, not a stub, and prove it by driving an actual run and observing the surface update.

The reconciler that produced the final issue map placed this seed downstream of the run-fact
ledger, not standalone, because a live telemetry surface has nothing real to read until a
run-fact ledger exists to read from: "a live telemetry surface is a read-side consumer of the
run-fact ledger substrate; belongs with the telemetry objective, sequenced after the ledger
spine" (`issue-map-final.json`, `pf-pulse-live-telemetry` → `consolidation_rationale`). The
sibling issue `pf-run-fact-ledger` (same objective, same wave) is the write-side counterpart
this issue reads from; `pf-fleet-baseline-metrics` and `pf-spend-observability-reports` are the
other read-side consumers of the same substrate. This issue is scoped narrowly to the
live-telemetry surface itself — it does not build the ledger, and it does not build the bounded
experiment loop (`/optimize`, already SHIPPED 0.18.0, is explicitly the *other* half of a
settled boundary: `/pulse` = continuous "what is the product doing live?"; `/optimize` = bounded
experiment with target/baseline/budget that runs and stops —
`docs/engineering-journal/QUEUED.md:73`, DECISIONS `#optimize-engine-rebuild`).

Today, the fleet's only board-state consumer is `mission-control:board`
(`plugins/mission-control/skills/board/SKILL.md`), which is a point-in-time CLI query, not a
live surface, and `/outcome`'s status is explicitly derived-on-read from ticks rather than a
committed field (binding decision, `/outcome` campaign U1–U11, echoed in the brief's
binding-decision register: "Derived-on-read status, never committed status fields" —
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`). Pulse must honor that same
derived-on-read discipline for run state rather than introducing a second, competing notion of
status.

## Definition of Done

A merged live-telemetry surface exists that renders board state, agent/run state, and (once
`pf-run-fact-ledger` lands) ledger-sourced run facts from real signals — not from mocked or
hardcoded data. "Real signals" means: board reads go through the existing
`mission-control:board`/`flow` read paths (or their underlying GraphQL/REST calls), and run
state reads come from the run-fact ledger produced by `pf-run-fact-ledger` (or, if that issue has
not yet landed when this one is worked, from `saga.py`'s existing derived-on-read tick history as
an interim source, explicitly documented as such and flagged for re-pointing once the ledger
ships).

Verification is behavioral, per the seed's own `dod_sketch`
(`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`, id `S-8`): drive an actual
in-flight run (a real `/work` or `/outcome` execution against a disposable saga/board state) and
observe the telemetry surface reflect that run's state changing in real time or on refresh — not
a static screenshot, not a fixture. The merged artifact ships with an automated test that asserts
the surface's rendered output changes when the underlying ledger/board state changes (i.e., a
before/after diff keyed to a real state transition), plus a documented manual verification
recipe for a human to reproduce the same drive-a-run check.

### Acceptance criteria
- [ ] AC1 (component exists, reads real board state). The telemetry component queries live board
  state through the existing `mission-control` board/flow read paths — no hardcoded or
  fixture-only board data. Check: an integration test seeds a real (or realistic sandboxed) board
  item, drives the component's board-read path, and asserts the rendered state matches the
  seeded item, not a fixture.
- [ ] AC2 (component exists, reads real agent/run state). The telemetry component reads run/agent
  state from the run-fact ledger (`pf-run-fact-ledger`) or, until that lands, from `saga.py`'s
  derived-on-read tick history — never from a hardcoded or mocked run object. Check: a test drives
  a real (or disposable-worktree) saga run through at least two lifecycle ticks and asserts the
  component's rendered run state reflects each tick transition.
- [ ] AC3 (derived-on-read, not committed status). The component does not introduce or read a
  second, independently-committed "status" field; it derives displayed status from the same
  tick/ledger facts `/outcome` already treats as source of truth. Check: a test asserts the
  component's status output changes when the underlying ticks/ledger change, with no
  component-owned status field written anywhere in `saga.py` or the ledger schema.
- [ ] AC4 (end-to-end proof, not a stub). Per the seed's own verification language
  (`docs/engineering-journal/QUEUED.md:73`; `survivors/seeds.json` id `S-8`), a real in-flight run
  is driven and the surface is observed to update — a stub or fixture-only demo does not satisfy
  this criterion. Check: `uv run pytest tests/test_pulse_telemetry.py -k drives_real_run` (or
  equivalently named test file/marker established during `/plan`) passes and asserts a
  state-transition diff, not merely that the component renders without error.
- [ ] AC5 (no ledger available yet, degrade explicitly, not silently). If this issue is worked before
  `pf-run-fact-ledger` merges, the component must explicitly label its interim data source (e.g.
  a visible "reading tick history — ledger pending" indicator) rather than silently presenting
  ledger-quality data from a weaker source. Check: a test with the ledger source stubbed as
  unavailable asserts the component emits/renders the interim-source label rather than failing
  silently or fabricating ledger-shaped output.
- [ ] AC6 (scope boundary vs `/optimize` respected). The component does not implement or duplicate
  `/optimize`'s bounded experiment loop (target/baseline/budget/stop); it is a continuous
  read-only view only. Check: code review / `/plan` review confirms no experiment-loop
  primitives (target, budget cap, stop condition) are introduced by this component; `/optimize`'s
  existing `optimize/SKILL.md` is untouched by this change.

### Out-of-scope / non-goals
In scope: a single live-telemetry component (surface, not a new orchestration engine) that reads
board state + run/agent state from existing or newly-shipped real sources and renders them;
the automated + manual verification described above; the interim-source degrade path in AC5.

Non-goals (explicitly deferred, per `docs/engineering-journal/QUEUED.md:73`):
- Building the run-fact ledger itself — that is `pf-run-fact-ledger`. This issue is a downstream
  consumer, sequenced after it.
- Any bounded experiment/optimization loop — that is `/optimize` (SHIPPED 0.18.0) and stays
  out of scope; the settled `/pulse` vs `/optimize` boundary
  (continuous-view vs bounded-experiment) is not to be revisited by this work.
- Usage/conversion/retention/cost analytics beyond what the ledger substrate already produces —
  full product-analytics telemetry was explicitly parked as "not worth it" until Infiquetra has a
  live product with real usage data (`docs/engineering-journal/QUEUED.md:73`: "Infiquetra is
  currently pre-revenue greenfield — no product data yet"); this issue builds the *rendering*
  substrate only, not new metric sources beyond board/ledger.
- Committing a new, independently-owned "status" field anywhere in `saga.py` or the ledger —
  status stays derived-on-read (binding decision, `/outcome` campaign U1–U11).
- A standing/scheduled calibration harness for the telemetry surface itself — out of scope; this
  mirrors the already-settled rejection of standing calibration ceremony elsewhere in the fleet
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`, `{#tier-vocab-ordering}`
  region; and the completeness-gate precedent of on-demand-only self-test, not scheduled
  harnesses).

## Grounding References

- `docs/engineering-journal/QUEUED.md:73` — `{#pulse-live-telemetry-component}`: the original
  P2/P3 queued item, its CE `ce-product-pulse` engine source, its explicit "parked, separate job"
  status, and the settled `/pulse` vs `/optimize` boundary.
- `docs/engineering-journal/QUEUED.md:26` — lifecycle-engine-merge-campaign closer, naming
  `/pulse` as one of the items remaining separate and open after all 13 command rebuilds shipped.
- `docs/engineering-journal/DECISIONS.md` `#founder-review-engine-rebuild` — records that
  `/founder-review` stole only `ce-product-pulse`'s no-false-precision posture and deliberately
  did NOT build the full live telemetry artifact.
- `docs/engineering-journal/DECISIONS.md` `#optimize-engine-rebuild` — the settled
  bounded-experiment-vs-continuous-view boundary this issue must not cross.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:90-97` (section 5, pre-existing seeds) —
  reconfirms `{#pulse-live-telemetry-component}` as a live carried-forward seed for this
  ideation pass.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52` (section 2, binding-decision
  register) — the derived-on-read status binding decision this component must honor, and the
  general "new-plugin/new-component ideas carry consolidation burden proof"
  `{#plugin-portfolio-groom-17-to-7}` constraint this issue's narrow scope satisfies.
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`, id `S-8` — the survived
  seed record: title, `basis` (direct cite to brief §5), `dod_sketch` with its explicit
  drive-a-run verification language.
- `/private/tmp/.../issue-map/issue-map-final.json`, entry `pf-pulse-live-telemetry` — the final
  reconciler placement (`absorbed: [{"id":"S-8","role":"primary"}]`), its
  `consolidation_rationale` (sequenced after the ledger spine), and `ac_sketch`.
- Sibling issues in the same objective/wave for sequencing: `pf-run-fact-ledger` (the ledger this
  component reads from — build/land first), `pf-fleet-baseline-metrics` and
  `pf-spend-observability-reports` (other read-side consumers of the same ledger substrate).
- `plugins/mission-control/skills/board/SKILL.md` — the existing board-read surface this
  component's board-state reads should reuse rather than re-implement.

## Recommended Executor Profile

- Model: **sonnet**
- Effort: **medium**
- Backend: **inline**
- External LLM: **none**

Justification: this is a bounded, well-precedented capability (a read-only rendering component
consuming two already-defined data sources) with no architectural ambiguity left to resolve —
the hard sequencing and scope-boundary decisions are already settled in the grounding brief and
`DECISIONS.md`. It does not warrant opus-tier judgment or an external-LLM posture above the
fleet's default advisory-only stance (`{#external-engines-never-gatekeepers}`,
`{#external-engine-chaperone-dispatch}`). Escalate to opus/high only if `/plan` surfaces a
genuine design ambiguity in how ledger-vs-tick-history interim sourcing should degrade (AC5).

## Release-Surface Checklist

This changes user-facing plugin behavior (a new component/command surface), so the following
must land in the same PR as the code change:

- [ ] `plugins/<owning-plugin>/.claude-plugin/plugin.json` — version bump + description update
      reflecting the new telemetry component/command.
- [ ] `.claude-plugin/marketplace.json` — matching version/description entry for the owning
      plugin.
- [ ] `plugins/<owning-plugin>/CHANGELOG.md` — dated entry describing the new live-telemetry
      surface, its data sources, and the interim-source degrade behavior (AC5).
- [ ] Any version/metadata drift-guard test (e.g. a marketplace/plugin.json consistency test
      already present in `tests/`) updated or confirmed still green against the bumped version.
- [ ] `docs/engineering-journal/QUEUED.md:73` (`{#pulse-live-telemetry-component}`) updated to
      SHIPPED status with a ship record in `docs/engineering-journal/ARCHIVE.md`, mirroring the
      pattern used for every other engine-rebuild campaign item.

Note: the owning plugin (new standalone `pulse` plugin vs. a component inside an existing
plugin such as `mission-control` or `saga`) is a `/plan`-time decision, not settled here — the
checklist above applies to whichever plugin ends up owning the surface.

## Tier / Type / Objective / Wave

- Tier: structural
- Type: capability
- Objective: Build the fleet telemetry and ledger substrate
- Wave: wave-2

### Suggested next action

Use `/plan <issue>` to create an implementation plan once `pf-run-fact-ledger` has landed or its
interim tick-history fallback (AC5) is agreed during planning.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (id `S-8`)
- Source type: ideation survivor (seed)
- Source title: Pulse live-telemetry component

### Intent

There is no live view of what the fleet is actually doing. `docs/engineering-journal/QUEUED.md:73` ("`{#pulse-live-telemetry-component}`") records this as a standing open item: a `/pulse` continuous live-telemetry component, sourced from CE's `ce-product-pulse` engine, was explicitly carved OUT of the `/founder-review` port rather than built — `/founder-review` only stole `ce-product-pulse`'s "no-false-precision" posture (cite numbers, let the operator judge; no hardcoded thresholds), staying qualitative with no live data (DECISIONS `#founder-review-engine-rebuild`). The full read-only analytics/usage report shape was deliberately "parked" for a separate job (`docs/engineering-journal/QUEUED.md:73`), and the lifecycle-engine-merge-campaign closer explicitly named `/pulse` as one of the items that "remains SEPARATE, open, queued" even after all 13 command rebuilds shipped (`docs/engineering-journal/QUEUED.md:26`).

### Context library links

_none_

### Files expected to change

- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/mission-control/skills/board/SKILL.md`
- `survivors/seeds.json`
- `optimize/SKILL.md`
- `docs/engineering-journal/DECISIONS.md`
- `/private/tmp/.../issue-map/issue-map-final.json`
- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/ARCHIVE.md`

### Tests to add or update

- `tests/test_pulse_telemetry.py`

### Verification

```bash
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/400
- Number: 400
- Created at: 2026-07-04T08:01:42.493054+00:00

