---
title: "exploration: prove the cache claim — residency A/B benchmark and warm-reuse benefit regression guard"
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: quick-win
wave: wave-2
objective: "Make cache economics an engineered, measured win"
slug: pf-residency-evidence
---

# exploration: prove the cache claim — residency A/B benchmark and warm-reuse benefit regression guard

### Objective
Make cache economics an engineered, measured win.

### Intent
The `worker-cache-scheduling` decision (`docs/engineering-journal/DECISIONS.md:1950`) ships a
resident-worker cache-reuse protocol on the strength of an unverified belief: that keeping
same-segment workers resident meaningfully lowers tokens. No controlled measurement has ever
isolated residency-ON from residency-OFF on a fixed recon fan-out, so the repo's own Validation
Discipline mandate ("never assert without checking") is currently being violated by the very
theme that mandate is supposed to govern. This issue merges two absorbed ideation facets from
theme T4 (cache-aware prompt architecture) into one exploration that closes that gap:

1. **A residency A/B benchmark** (`T4-F3-6`, primary) — a one-shot, non-permanent harness that
   runs one representative read-only recon fan-out twice, once with contiguous residency
   (current shipped behavior) and once with positional `worker-{i}` (the pre-KTD3 baseline), and
   reads the `cache_read`/input split to produce a decision-grade verdict: either
   `worker-cache-scheduling` is confirmed as-shipped, or its documented revisit-when has fired.
2. **A warm-reuse-benefit regression guard** (`T4-F1-6`, facet) — a standing assertion over the
   run ledger that flags any segment tagged `warm-reuse` whose observed re-engagement cost is
   indistinguishable from a cold-spawn cost (the ledger analog of `cache_read_input_tokens`
   staying at zero across identical-prefix requests), so a silent invalidator creeping in later
   does not quietly convert every future "warm" spawn back into a full cold-cost spawn while
   still reporting reuse.

These two facets ship together because the guard has nothing to assert against until the
benchmark exists to produce a real cache_read/input split to reason about, and the benchmark
alone is a one-shot proof with no standing protection against the exact silent-regression class
this repo's journal already documents as its dominant failure mode (delegation/bridge no-ops
that keep "succeeding" while doing nothing).

## Problem Frame

Cache economics in this repo currently rest on an asserted number, not a measured one.

- **The headline number is an anecdote, not a decomposed measurement.** The 350–450k
  tokens-in-under-20-minutes figure for read-only recon fan-outs
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:145`) is cited repeatedly across this
  ideation wave as the cache-economics baseline, but nothing in the repo decomposes it into
  `cache_read` / `cache_creation` / uncached-input tokens per segment, and nothing attributes any
  fraction of it to residency actually working versus residency being irrelevant to that run's
  shape.
- **The core architectural premise is asserted, not checked.** `worker-cache-scheduling`
  (`docs/engineering-journal/DECISIONS.md:1950`) ships KTD3 (stable agent id replacing positional
  `worker-{i}`, specifically because residency needs a durable `SendMessage` handle) and KTD4
  ("behavioral residency is markdown protocol... validated by `/doc-review` + operator runs +
  headroom telemetry" — `docs/engineering-journal/DECISIONS.md:1965`-`1967`). No controlled
  before/after comparison backs KTD3's cost claim; "operator runs + headroom telemetry" is
  observational, not a controlled A/B. This is a direct violation of this repo's own stated
  posture: never assert a system-state or performance claim without verifying it from a current,
  direct source.
- **The decision's own revisit-when is currently untestable.** `docs/engineering-journal/DECISIONS.md:1970`-`1971`
  names an explicit revisit condition ("Named-teammate residency proves insufficient... or a
  single team-execution run shows enough internal idle-poll to justify a formal within-run wave
  queue"), but nothing today can determine whether that condition has fired, because no A/B
  measurement exists to compare against.
- **Warm-reuse claims have no regression protection.** Anthropic's own prompt-caching guidance
  states the exact silent-invalidator symptom to watch for: `cache_read_input_tokens` staying at
  zero across identical-prefix requests signals a silent invalidator at work (this repo's
  `claude-api` skill, `shared/prompt-caching.md`). This repo's run ledger has no analog of that
  check today — a segment could be tagged `warm-reuse` in the ledger while paying full cold-spawn
  cost every cycle, and nothing would flag it, echoing this repo's own dominant recorded failure
  class of silent no-ops in delegation and dead wiring (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99`-`102`,
  section 6 item 1).

## Key Decisions

These framing choices carry forward from the ideation survivors and constrain scope below.

- **One-shot experiment, not permanent machinery (the benchmark).** `T4-F3-6`'s harness is
  explicitly framed as a decision-grade measurement run, not a standing calibration ceremony —
  consistent with this repo's rejection of ceremony-shaped standing-measurement loops for a
  solo-operated toolset (the same posture that killed the S-6 spike-calibration shape elsewhere
  in this ideation wave). It produces one verdict and a dated journal entry, not a dashboard.
- **Standing guard, not a one-shot check (the regression guard).** `T4-F1-6`'s warm-reuse-benefit
  assertion is the opposite shape by design: a lightweight, repeatable check wired into the
  coordinator aggregator and `/retro`-consumable output, because silent cache regressions can
  recur at any future commit, unlike the one-time architectural question the benchmark answers.
- **Verdict is binary and consequential, not advisory.** The benchmark's output must explicitly
  state one of two outcomes — `worker-cache-scheduling` (KTD3/KTD4) confirmed as-shipped, or its
  documented revisit-when has fired — because a vague or hedged finding does not discharge the
  Validation Discipline obligation this issue exists to satisfy, and a fired revisit-when is the
  evidence gate a separate, gated ideation survivor (`T4-F3-3`, crew-pairing by context-overlap)
  is blocked on.
- **This issue does not build the full cache-economics ledger.** A separate, non-absorbed
  survivor (`T4-F3-5`, "make KTD4's named telemetry loop actually exist") proposes the durable
  per-run ledger substrate that harvests `headroom_stats` and rolls up `cache_read` /
  `cache_creation` / uncached-input by resident segment. This issue does not require that ledger
  to exist first: the benchmark (`T4-F3-6`) can read the split directly from whatever telemetry
  surface is available at implementation time (the headroom MCP `headroom_stats` surface, or a
  minimal per-run capture built only for this benchmark's fixture run), and the regression guard
  (`T4-F1-6`) operates over whatever run-ledger shape currently exists. If `T4-F3-5`'s ledger
  substrate lands first, this issue's benchmark and guard should consume it instead of
  duplicating capture logic — `/plan` decides the actual integration point.

## Requirements

**Residency A/B benchmark (T4-F3-6, primary)**

R1. A benchmark harness (proposed path: `tools/residency_ab_benchmark.py` or a `saga/scripts/`
equivalent) runs one representative, fixed read-only recon fan-out shape twice: once under
current shipped residency (contiguous, stable-agent-id workers per `worker-cache-scheduling`
KTD3), and once under the pre-KTD3 baseline (positional `worker-{i}`, no durable `SendMessage`
handle).

R2. Both runs use an identical fan-out definition (same segment/unit shape, same targets) so the
only varying factor between the two runs is residency on versus off.

R3. The harness captures and reports the `cache_read` / `cache_creation` / uncached-input token
split for both runs, from the best available telemetry surface at implementation time (headroom
MCP `headroom_stats`, or a minimal ad hoc capture scoped to this benchmark if no ledger
substrate exists yet).

R4. The harness emits an explicit, unambiguous verdict: either "`worker-cache-scheduling`
confirmed as-shipped" (residency measurably reduces token cost versus the positional baseline) or
"revisit-when fired" (residency shows no measurable benefit, or the observed idle-poll justifies
a formal wave queue, per `docs/engineering-journal/DECISIONS.md:1970`-`1971`).

R5. The run is documented as a dated `docs/engineering-journal/LEARNINGS.md` entry following this
repo's Evidence / Mechanism / Generalizable-rule format, recording the measured `cache_read`
split and the explicit verdict.

R6. The benchmark is explicitly one-shot: it is not wired into a scheduled harness or standing
calibration loop. It is re-run manually if the residency architecture changes materially in the
future.

**Warm-reuse-benefit regression guard (T4-F1-6, facet)**

R7. A guard (proposed integration point: the coordinator aggregator, or a `/retro`-consumable
check) inspects the run ledger's cold/warm dispositions and flags any segment tagged `warm-reuse`
whose observed re-engagement cost is statistically indistinguishable from that same segment's
(or an equivalent segment's) cold-spawn cost.

R8. On a trip, the guard surfaces the offending segment identifier and a likely-cause hint drawn
from the known invalidator classes (prefix drift, a below-cache-floor prefix, or a changed tool
set) — mirroring the diagnostic categories this repo's `claude-api` skill documents for the
Messages API cache-hit check.

R9. The guard does not assert *which* cause is responsible with certainty — it names the
observable symptom (warm-reuse-tagged segment behaving like a cold spawn) and the plausible
causes, consistent with this repo's existing pattern of not over-attributing an absence to a
single inferred cause (the same discipline used for `missing-output` classification elsewhere in
this ideation wave).

R10. A synthetic, prefix-drifted `warm-reuse`-tagged ledger segment trips the guard; a
synthetic, genuinely-cached `warm-reuse`-tagged segment (comparable re-engagement cost well below
its cold-spawn cost) passes.

### Out-of-scope / non-goals
- **In scope:** the one-shot A/B benchmark harness and its dated LEARNINGS entry; the warm-reuse
  regression guard and its wiring into the coordinator aggregator / `/retro`-consumable check
  path; the synthetic fixtures proving both the trip and pass cases of the guard.
- **Out of scope / non-goals:**
  - Building the full cache-economics ledger substrate (`T4-F3-5`) — this issue consumes
    whatever telemetry surface is available and does not duplicate a durable per-run ledger. If
    `T4-F3-5` ships first, a follow-up can re-point this issue's consumers at it.
  - Deciding or implementing crew-pairing by context-overlap (`T4-F3-3`) — this issue produces
    the evidence gate that survivor is blocked on; it does not implement the pairing change
    itself, regardless of which way the verdict lands.
  - A standing, scheduled measurement/calibration harness for the benchmark — R6 is explicit that
    this is a one-shot run, not permanent machinery.
  - Changing the `worker-cache-scheduling` protocol itself (segment boundary, derivation
    location, or the resident-worker runtime) — this issue measures and guards the existing
    protocol's economics; it does not redesign the protocol.
  - Any change to the `inline` execution backend — the resident-worker protocol this issue
    measures applies to `team-execution`, not the inline backend.

## Definition of Done

- A merged benchmark harness exists that runs a fixed recon fan-out shape under residency-on and
  residency-off and reports the measured `cache_read` / `cache_creation` / uncached-input split
  for both runs.
- A dated `docs/engineering-journal/LEARNINGS.md` entry (Evidence / Mechanism / Generalizable-rule)
  records that measured split and states an explicit verdict: `worker-cache-scheduling` confirmed
  as-shipped, or its revisit-when fired.
- A warm-reuse-benefit assertion exists over the run ledger, wired into the coordinator aggregator
  or a `/retro`-consumable check, that trips on a synthetic prefix-drifted `warm-reuse` segment and
  passes on a synthetic genuinely-cached `warm-reuse` segment.
- Full repo test/lint/type suite stays green with the new harness, guard, and tests included.

## Grounding References

- `T4-F3-6` (primary) — residency A/B benchmark. Basis: reasoned, from first principles —
  residency only saves tokens if same-segment spawns actually achieve `cache_read > 0`, and no
  repo artifact measures the on/off delta, so the architecture's core premise is currently
  asserted, not checked, directly conflicting with this repo's stated Validation Discipline norm.
  Consumes the ledger surface from `T4-F3-5` where available. The 350–450k recon-fan-out figure
  this benchmark reframes into a testable hypothesis is at
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:145`.
- `T4-F1-6` (facet) — warm-reuse-benefit regression guard. Basis: direct —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 6.1: silent no-ops are the
  dominant failure class in this repo's journal, and any bridge/delegation idea needs
  "did-it-actually-run/persist" verification (agy silent Claude-fallback, dead-wiring learnings).
  Operationalizes the verified cache-hit check documented in this repo's `claude-api` skill,
  `shared/prompt-caching.md`: "if `cache_read_input_tokens` is zero across repeated
  identical-prefix requests, a silent invalidator is at work."
- Binding decision this builds on: `worker-cache-scheduling`
  (`docs/engineering-journal/DECISIONS.md:1950`-`1971`) — the resident-worker cache-reuse protocol
  (derive segment/agent/tier saga-side, reside team-side; segment boundary = plugin directory)
  whose cost claim this issue measures and whose documented revisit-when this issue makes
  testable, without changing the protocol itself.
- Related, non-absorbed survivor referenced but not delivered by this issue: `T4-F3-5` (cache
  economics ledger substrate) and `T4-F3-3` (crew-pairing by context-overlap, gated on this
  issue's verdict) — both live in the same `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json`
  file.
- Consolidation rationale (issue map): the benchmark and the guard are one merged change set
  because the guard has no real cache_read/input split to assert against until the benchmark
  exists to produce one, and the benchmark alone is a one-shot proof with no standing protection
  against a later silent cache regression re-introducing the exact unverified-claim problem this
  issue closes.

## Recommended Executor Profile

- **Model:** Sonnet.
- **Effort:** Medium.
- **Backend:** Inline.
- **External LLM posture:** None.
- **Justification:** This is bounded measurement-and-guard engineering — one benchmark harness
  with a fixed fan-out shape and a documented verdict format, plus one ledger-based assertion with
  synthetic fixtures — with clear, testable acceptance criteria and no architectural ambiguity. It
  does not require Opus-level design judgment or an external-engine chaperone dispatch; Sonnet at
  medium effort, run inline, matches the shape. (Per company policy, any above-Sonnet tier would
  need explicit justification here; none applies.)

## Release-Surface Checklist

This issue adds new tooling but does not itself change any shipped plugin's user-facing behavior,
schema, command, or prompt surface (it measures and guards an existing protocol). If `/plan`
determines that the regression guard's integration point requires a `team-execution` or `saga`
plugin behavior change (e.g. wiring into the coordinator aggregator changes shipped skill
behavior), the release surface must be updated in the same PR:

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` (or `plugins/saga/.claude-plugin/plugin.json`,
  whichever plugin's aggregator the guard is wired into) — version bump if shipped behavior
  changes.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync if the above plugin's version
  changes.
- [ ] The affected plugin's `CHANGELOG.md` — entry documenting the new guard if it changes shipped
  behavior.
- [ ] Any version/metadata drift-guard tests — verified green with any version bump in place.
- [ ] If no shipped plugin behavior changes (the guard and benchmark live entirely in `tools/` /
  `tests/` / the engineering journal), this checklist is not applicable — record that explicitly
  in the PR description rather than silently skipping it.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `tools/residency_ab_benchmark.py` — new residency A/B benchmark harness (proposed path).
- `docs/engineering-journal/LEARNINGS.md` — new dated entry recording the measured split and
  verdict.
- A warm-reuse-benefit guard module (proposed path: `plugins/team-execution/skills/team-execution/scripts/warm_reuse_guard.py`
  or a `/retro`-consumable check under `plugins/saga/scripts/`) — new.
- `tests/test_residency_ab_benchmark.py` — new tests for the benchmark harness.
- `tests/test_warm_reuse_guard.py` — new tests for the regression guard (trip and pass cases).
- Release-surface files listed above, only if `/plan` determines shipped plugin behavior changes.

### Tests to add or update
- Benchmark: harness runs both residency-on and residency-off fan-outs against a fixed fixture
  shape and reports a `cache_read` / `cache_creation` / uncached-input split for each; emits one of
  the two defined verdict strings.
- Regression guard: trips on a synthetic prefix-drifted `warm-reuse`-tagged ledger segment; passes
  on a synthetic genuinely-cached `warm-reuse`-tagged segment.
- Release-surface drift-guard tests (existing repo tooling) stay green if any version bump is
  made.

### Acceptance criteria
- [ ] The benchmark harness runs a fixed recon fan-out shape under both residency-on and
  residency-off and reports the `cache_read` / `cache_creation` / uncached-input split for each
  run. Check: `uv run pytest tests/test_residency_ab_benchmark.py -k reports_split` → passes.
- [ ] The benchmark emits an explicit, unambiguous verdict (`confirmed` or `revisit-when fired`).
  Check: `uv run pytest tests/test_residency_ab_benchmark.py -k emits_verdict` → passes.
- [ ] A dated `docs/engineering-journal/LEARNINGS.md` entry records the measured split and the
  verdict, in Evidence / Mechanism / Generalizable-rule format. Check: `grep -n "residency"
  docs/engineering-journal/LEARNINGS.md | tail -5` → shows a dated entry matching the benchmark run.
- [ ] A synthetic prefix-drifted `warm-reuse`-tagged ledger segment trips the guard. Check:
  `uv run pytest tests/test_warm_reuse_guard.py -k prefix_drift_trips` → passes.
- [ ] A synthetic genuinely-cached `warm-reuse`-tagged segment passes the guard. Check:
  `uv run pytest tests/test_warm_reuse_guard.py -k genuine_cache_passes` → passes.
- [ ] If the guard's integration point changes shipped plugin behavior, release-surface artifacts
  are updated in the same PR (plugin.json version bump, marketplace.json sync, CHANGELOG entry);
  otherwise the PR description explicitly states no release-surface change applies. Check:
  `git diff --stat` for the PR either includes all three paths, or the PR description contains an
  explicit "no release-surface change" note.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Benchmark harness (fixture shape TBD by /plan)
python3 tools/residency_ab_benchmark.py --fixture recon-fanout-fixture

# Regression guard unit tests (trip + pass cases)
uv run pytest tests/test_warm_reuse_guard.py -v

# Benchmark harness unit tests
uv run pytest tests/test_residency_ab_benchmark.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the benchmark prints a `cache_read`/`cache_creation`/uncached-input split for
both residency-on and residency-off runs plus an explicit verdict line; the regression guard trips
on the seeded prefix-drifted fixture and passes on the seeded genuinely-cached fixture.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json (ids `T4-F3-6`, `T4-F1-6`)
- Source type: ideation survivor set
- Source title: Plugin-fleet ideation 2026-07-03 — theme T4 (cache-aware prompt architecture)

### Context library links

_none_
