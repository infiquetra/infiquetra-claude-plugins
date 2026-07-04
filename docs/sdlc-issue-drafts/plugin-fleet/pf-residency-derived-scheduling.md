---
title: "capability: derived residency scheduling — emitted boundary actions, dependency-preserving reorder, context-GC, residency manifest, TTL-aware batching"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Make cache economics an engineered, measured win"
slug: pf-residency-derived-scheduling
---

# capability: derived residency scheduling — emitted boundary actions, dependency-preserving reorder, context-GC, residency manifest, TTL-aware batching

### Objective
Make cache economics an engineered, measured win.

### Intent
The resident-worker cache-reuse architecture (`worker-cache-scheduling`,
`docs/engineering-journal/DECISIONS.md:1965-1970` — "derive saga-side, reside team-side;
segment boundary = plugin directory") shipped its residency primitive but left five settled,
named refinements as prose or entirely unshipped. This issue merges five absorbed ideation
facets from theme T4 (cache-aware prompt architecture / segment-residency scheduling) into one
structural change set that turns "residency is a markdown protocol" into a derived, emitted,
machine-readable schedule:

1. **Emitted per-segment boundary action** (`T4-F2-2`, primary) — saga's segmentation
   derivation stamps each worker row with an explicit `reuse` / `summary-handoff` / `shed`
   action instead of leaving that judgment to a resident worker reading markdown prose at
   runtime.
2. **Dependency-preserving segment reordering** (`T4-F4-3`, facet) — a saga-side reorder pass
   that, where dependencies already permit it, collapses non-contiguous same-key units into one
   resident instead of paying a cold-restart cost for every interleaved re-appearance.
3. **Context-GC for resident teammates** (`T4-F6-6`, facet) — ships the previously unshipped
   KTD5 context-shedding step: after a unit completes, the resident sheds completed-unit context
   to a bounded summary before pulling the next unit, keeping the warm prefix stable.
4. **Residency manifest** (`T4-F3-7`, facet) — emits the already-structured `Segment` mapping as
   a derived-on-read JSON manifest so `/outcome` frontier dispatch and saga verify-panels (not
   just team-execution) can read the schedule instead of getting zero residency benefit.
5. **TTL-aware batch scheduling** (`T4-F6-7`, facet) — clusters same-segment units into adjacent
   dispatch batches so the 5-minute prompt-cache TTL and the 3-way concurrency cap coexist
   instead of fighting, with a surfaced "cache will expire in Xs" signal when the serial queue
   can't keep up.

None of these five exists today in machine-readable form. All five extend the same settled
`worker-cache-scheduling` seam (derive saga-side, reside team-side) rather than crossing it, and
they compound: the boundary action and reorder pass are useless to non-team-execution consumers
without the manifest that exposes them, and TTL-aware batching only has something worth
clustering once the reorder pass has already collapsed interleaved segments.

## Problem Frame

`worker-cache-scheduling` (`docs/engineering-journal/DECISIONS.md:1965-1970`) settled the
derive/reside split and named two explicit gaps at ship time:

- **KTD4** — "behavioral residency is markdown protocol; testable surface is saga-side
  plumbing only." The A7 worker table in
  `plugins/team-execution/skills/team-execution/SKILL.md:226-230` (`Agent | Units | Tier | Mode |
  Depends-on | Engine | Intent`) has no column for the reuse/summary-handoff/shed decision a
  resident worker must currently infer from prose (R11, R8 in the ideation basis). This is a
  manual, untestable runtime judgment call for exactly the kind of thing saga's segmentation
  derivation already computes elsewhere.
- **KTD5** — "R15a context-GC excluded — no harness lever (Messages-API-only)." Named as an
  explicitly unshipped residency refinement at decision time
  (`docs/engineering-journal/DECISIONS.md:1965-1970`), while
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:57` already
  re-engages the same named reviewer via `SendMessage` — so a long-lived resident accretes
  transcript with nothing shedding it.
- **Revisit-when, already triggered.** The decision's own revisit clause — "Named-teammate
  residency proves insufficient (revisit warm-pool / crew-pairing)" — is engaged by direct
  evidence in `plugins/saga/scripts/execution_spec.py:1405-1421`: a non-contiguous
  re-appearance of the same engine or plugin-directory boundary key opens a fresh resident
  (`worker-agy-2`) that re-pays the full cold context/cache cost even when the same segment key
  returns inside the 5-minute TTL.
- **Derived schedule has one consumer.** `segment_units()`
  (`plugins/saga/scripts/execution_spec.py:1384`) already returns a structured `list[Segment]`
  saga-side, but because KTD4 renders residency as markdown protocol, no other dispatcher can
  read it — `/outcome` frontier dispatch and saga verify-panels (which spawn up to
  `VERIFY_N_CAP=7` same-type readonly-verifiers sharing a byte-identical prefix,
  `plugins/saga/scripts/execution_spec.py:114`) get zero residency benefit even though they fan
  out the same-agent-type workers residency is meant to help.
- **TTL and the concurrency cap fight.** With the operator's max-3-concurrent cap, a wide ready
  frontier dispatches as sequential batches; if batch N+1 lands more than 300 seconds after batch
  N warmed the shared prefix, the cache has expired and every worker in that batch pays a cold
  miss. Nothing today orders batches with the TTL in mind.

This is the repo's next dominant untested gap in cache economics: the derive-side primitive
exists, but the decision points that turn it into an actual reuse win — the boundary action, the
reorder pass, the context ceiling, the cross-consumer manifest, and TTL-aware batch order — are
either prose-only, unshipped, or single-consumer.

## Key Decisions

These framing choices carry forward from the ideation survivors and constrain scope below.

- **Extend `worker-cache-scheduling`, do not revisit it.** All five facets stay inside the
  settled derive-saga-side/reside-team-side seam. The reorder pass explicitly engages the
  decision's own revisit-when clause with the cheapest form named in it first (a saga-side pure
  reorder transform) before reaching for the heavier warm-pool/crew-pairing alternative also
  named in that clause; warm-pool is documented as a fallback for dependency-blocked cases, not
  built in v1.
- **Derive-on-read, never persisted.** The residency manifest is a producer/consumer widening
  (more consumers reading a saga-side derived artifact), not a new committed status field. It is
  recomputed at dispatch time, consistent with `/outcome`'s derived-on-read rule — this is the
  same rule already binding board status, applied to the residency schedule.
- **Boundary action and context-GC are additive to existing prose, not replacements.** The A7
  table gains a column; `consensus-protocol.md`'s existing re-engagement path gains a shedding
  step after artifact-pointer emit. Neither changes the underlying reuse/re-engage mechanism,
  only makes its shed/keep decision explicit and its context bounded.
- **TTL-aware batching is a scheduler heuristic over already-emitted segments**, not a new
  primitive — it orders existing batches by boundary key so same-segment units land inside one
  TTL window; it does not change the 3-way concurrency cap itself.
- **Five facets ship together.** Per the issue map's consolidation, the boundary action
  (primary) and the four facets (reorder, context-GC, manifest, TTL batching) are one merged
  change set: the manifest is what makes the boundary action and reorder pass visible to
  non-team-execution consumers, and TTL-aware batching has nothing worth clustering without the
  reorder pass already having collapsed interleaved segments.

## Requirements

**Emitted boundary action (T4-F2-2, primary)**

R1. Saga's segmentation derivation stamps each emitted worker row with an explicit boundary
action of `reuse`, `summary-handoff`, or `shed`, threaded through the team emitter.

R2. The A7 worker table format documented in
`plugins/team-execution/skills/team-execution/SKILL.md:226-230` gains a `Boundary` column, and
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` is updated
to reflect it.

R3. A `team_emitter` round-trip test asserts the derived boundary action for a segment matches
the expected reuse/summary-handoff/shed classification.

**Dependency-preserving segment reordering (T4-F4-3, facet)**

R4. A reorder step runs in or ahead of `segment_units()`
(`plugins/saga/scripts/execution_spec.py:1384`): among units whose declared dependencies already
permit it, a stable sort by boundary key groups same-key units contiguously so they collapse
into one resident.

R5. Where reordering is dependency-blocked, the residency prose documents the warm-pool /
crew-pairing fallback named in `worker-cache-scheduling`'s revisit-when clause
(`docs/engineering-journal/DECISIONS.md:1970`) as the next escalation, not built in v1.

R6. A pytest fixture with interleaved plugin-directory units asserts the resident count drops
from 3 to 2 after reordering, with no dependency edge violated by the new ordering.

**Context-GC for resident teammates (T4-F6-6, facet)**

R7. A context-shedding step is added to
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md` immediately
after a unit's artifact-pointer emit: the resident's completed-unit working context is compacted
to a bounded summary before the next unit is pulled, leaving the stable warm prefix unchanged.

R8. A shed-summary helper implements the compaction; it does not touch the stable prefix content
that keeps the resident's cache-hit eligibility intact.

R9. A two-unit resident run (test or fixture) shows the volatile tail reset to a bounded summary
between units while the stable prefix bytes are unchanged.

**Residency manifest (T4-F3-7, facet)**

R10. `segment_units()`'s structured `Segment` mapping is additionally emitted as a JSON
residency manifest (proposed emission point: `plugins/saga/scripts/execution_spec.py`),
alongside the existing prose A7 table — the derive side is widened to a second consumer format,
the producer is not changed.

R11. `/outcome` frontier dispatch consumes the manifest to cluster same-segment ready leaves
into consecutive warm-dispatch windows.

R12. Saga verify-panel spawn (`plugins/saga/scripts/execution_spec.py:114`,
`VERIFY_N_CAP=7`) consumes the manifest to prime-then-fill same-type verifiers in
segment-clustered order.

R13. A pytest asserts the manifest round-trips the segmentation produced by `segment_units()`
with no information loss.

R14. A doc-review confirms the manifest is derive-on-read (recomputed at dispatch time, never
persisted as committed status), consistent with `/outcome`'s existing derived-on-read rule.

**TTL-aware batch scheduling (T4-F6-7, facet)**

R15. The frontier/emit scheduler (team emitter and/or `/outcome` frontier dispatch) groups
same-segment units into adjacent batches ordered to land inside the 5-minute (300s) prompt-cache
TTL window, using the residency manifest (R10) as its input.

R16. When the serial batch queue cannot keep the inter-batch gap under the TTL, the scheduler
surfaces a "cache will expire in Xs" signal in the emitted plan (a `cache-expiry-risk` note),
without automatically changing posture or concurrency.

R17. A test emitting a specification with more than 3 units across multiple segments asserts the
resulting batch order is segment-contiguous (same-segment units land in adjacent batches) under
the existing concurrency cap.

### Out-of-scope / non-goals
- **In scope:** the emitted boundary-action column and its team-emitter threading; the
  dependency-preserving reorder pass in/ahead of `segment_units()`; the context-GC shedding step
  in `consensus-protocol.md`; the JSON residency manifest and its two named new consumers
  (`/outcome` frontier dispatch, saga verify-panel spawn); TTL-aware batch grouping in the
  frontier/emit scheduler; and the associated tests and doc-review.
- **Out of scope / non-goals:**
  - Building a formal warm-pool / crew-pairing residency mode — this issue implements the
    cheaper reorder-first escalation from `worker-cache-scheduling`'s revisit-when clause and
    documents warm-pool only as the next fallback for dependency-blocked cases; it does not ship
    warm-pool itself.
  - A standing telemetry/measurement loop tracking cache-hit rate over time — the manifest and
    TTL-expiry signal are computed and surfaced at dispatch/emit time, not via a scheduled
    monitoring harness (consistent with this repo's prior rejection of ceremony-shaped standing
    measurement loops for a solo-operated toolset).
  - Changing the segment-boundary definition itself (`plugin directory`, KTD2) or the
    derive-saga-side/reside-team-side split — this issue extends the schedule derived from that
    boundary, it does not redefine the boundary or move where residency lives.
  - Automatically adjusting spend posture or the 3-way concurrency cap in response to the
    TTL-expiry signal (R16) — the signal is informational in v1; posture/cap changes are a
    separate, later decision.
  - Retrofitting the manifest into every possible dispatch site across the fleet — only the two
    named consumers (`/outcome` frontier dispatch, saga verify-panel spawn) are wired in v1.

## Definition of Done

- The A7 worker table format (`SKILL.md`) and `external-engine-workers.md` document a `Boundary`
  column, and the team emitter threads a derived `reuse`/`summary-handoff`/`shed` action per
  segment through to it.
- `segment_units()` (or a wrapper ahead of it) performs a dependency-preserving reorder that
  collapses non-contiguous same-key units where dependencies permit, with the warm-pool fallback
  documented (not built) for the blocked case.
- `consensus-protocol.md` documents and a shed-summary helper implements a context-shedding step
  after artifact-pointer emit, bounding a resident's accreted context between units.
- A JSON residency manifest is emitted from the saga-side `Segment` mapping and consumed by both
  `/outcome` frontier dispatch and saga verify-panel spawn for segment-clustered scheduling.
- The frontier/emit scheduler groups same-segment units into TTL-adjacent batches and surfaces a
  cache-expiry-risk note when the batch queue cannot keep pace with the 300s TTL.
- All five facets' tests pass (team_emitter round-trip, reorder pytest, context-GC two-unit run,
  manifest round-trip pytest, TTL-adjacency emit test); a doc-review confirms the manifest is
  derive-on-read.
- Full repo test/lint/type suite stays green with the new code paths included.

## Grounding References

- `T4-F2-2` (primary) — emitted boundary action. Basis: direct —
  `docs/engineering-journal/DECISIONS.md:1965-1968` (KTD4/KTD5: "behavioral residency is
  markdown protocol... R15a context-GC excluded — no harness lever"); A7 worker table at
  `plugins/team-execution/skills/team-execution/SKILL.md:226-230` has no shed/boundary column
  today; plan R11 (shed at boundary expected to exceed ~5-min TTL) and R8 (segment-dep collapse)
  are derivable saga-side.
- `T4-F4-3` (facet) — dependency-preserving reorder. Basis: direct —
  `plugins/saga/scripts/execution_spec.py:1405-1421` comment: "a non-contiguous re-appearance of
  the same engine (e.g. interleaved with a Claude unit) opens a new resident (`worker-agy-2`)."
  Explicitly engages `worker-cache-scheduling`'s revisit-when clause — "Named-teammate residency
  proves insufficient (revisit warm-pool / crew-pairing)"
  (`docs/engineering-journal/DECISIONS.md:1970`).
- `T4-F6-6` (facet) — context-GC for resident teammates. Basis: direct — `worker-cache-scheduling`
  KTD5 names "context-GC (Messages-API-only)" as an unshipped residency refinement
  (`docs/engineering-journal/DECISIONS.md:1965-1970`);
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:57` ("RE-ENGAGE
  the same named reviewer via `SendMessage`") is the residency seam being extended, not crossed.
- `T4-F3-7` (facet) — residency manifest. Basis: direct — `segment_units()`
  (`plugins/saga/scripts/execution_spec.py:1384`) already returns structured `list[Segment]`
  saga-side, but KTD4 states "behavioral residency is markdown protocol" so no non-team-execution
  dispatcher can read it; `/outcome` verify-panels spawn up to `VERIFY_N_CAP=7` same-type
  readonly-verifiers (`plugins/saga/scripts/execution_spec.py:114`) sharing a byte-identical
  prefix.
- `T4-F6-7` (facet) — TTL-aware batch scheduling. Basis: reasoned — prompt-cache TTL is 5
  minutes (300s); the operator's concurrency cap of 3 forces a wide ready frontier into serial
  batches; if inter-batch latency exceeds the TTL the warm prefix is evicted and `cache_read`
  drops to zero, so batch ordering that clusters same-segment units within one TTL window is the
  only way to preserve cache reuse under the cap.
- Binding decision this builds on: `worker-cache-scheduling`
  (`docs/engineering-journal/DECISIONS.md:1965-1970`) — derive segment/agent/tier saga-side,
  reside team-side; segment boundary = plugin directory; revisit-when named-teammate residency
  proves insufficient (engaged by `T4-F4-3`) or idle-poll justifies a formal wave queue (not
  engaged here).
- Also grounded against the `/outcome` campaign's binding constraint (derived-on-read status,
  never committed status fields; `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`,
  section 2) — the residency manifest follows the same derive-on-read rule.
- Consolidation rationale (issue map): the boundary action, reorder pass, context-GC, manifest,
  and TTL batching are one merged theme-T4 change set because the manifest is the only thing
  that makes the boundary action and reorder pass visible outside team-execution, and TTL-aware
  batching has nothing to cluster without the reorder pass having already collapsed interleaved
  segments — none of the five is a complete win alone.

## Recommended Executor Profile

- **Model:** Sonnet.
- **Effort:** High. — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution.
- **External LLM posture:** None.
- **Justification:** This is a coordinated five-facet change touching saga's derivation core
  (`execution_spec.py`), the team-execution worker table and consensus protocol, and two new
  `/outcome`-side consumers — enough cross-cutting surface and dependency-preserving-reorder
  subtlety (must not violate existing dependency edges while collapsing segments) to warrant
  high effort and the team-execution backend's coordination/review-loop machinery, but the work
  is mechanical extension of an already-settled architecture, not judgment-laden design, so
  Sonnet rather than Opus is sufficient.

## Release-Surface Checklist

This issue changes plugin behavior in both `saga` (`segment_units()`, the residency manifest
emit) and `team-execution` (the A7 table format, `consensus-protocol.md`), so the release
surface must be updated in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new residency
  manifest emit and reorder-pass behavior in `segment_units()`.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
  `Boundary` column, the context-GC shedding step, and the manifest-driven TTL-aware batching.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for both `saga` and
  `team-execution` if their plugin versions change.
- [ ] `plugins/saga/CHANGELOG.md` and `plugins/team-execution/CHANGELOG.md` — entries documenting
  the boundary action, reorder pass, context-GC, manifest, and TTL-aware batching respectively.
- [ ] Any version/metadata drift-guard tests (marketplace/plugin.json consistency tests) —
  verified green with both version bumps in place.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/execution_spec.py` — dependency-preserving reorder pass ahead of
  `segment_units`; residency-manifest JSON emit.
- `plugins/saga/scripts/team_emitter.py` — threads the derived boundary action per segment.
- `plugins/team-execution/skills/team-execution/SKILL.md` — A7 table gains a `Boundary` column.
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` — updated
  worker-table documentation reflecting the `Boundary` column.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` —
  context-shedding step after artifact-pointer emit; shed-summary helper reference.
- `/outcome` frontier-dispatch module (proposed: within `plugins/saga/scripts/` `/outcome`
  campaign code) — consumes the residency manifest for segment-clustered dispatch; TTL-aware
  batch grouping.
- Saga verify-panel spawn code (`plugins/saga/scripts/execution_spec.py`, near
  `VERIFY_N_CAP`) — consumes the manifest for prime-then-fill same-type verifier ordering.
- `tests/test_execution_spec.py` (or new `tests/test_residency_manifest.py`) — round-trip,
  reorder, and TTL-adjacency tests.
- `tests/test_consensus_protocol.py` (or equivalent) — context-GC two-unit run test.
- `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`,
  `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface updates.

### Tests to add or update
- `team_emitter` round-trip test asserting the derived boundary action
  (`reuse`/`summary-handoff`/`shed`) per segment.
- Reorder pytest fixture with interleaved plugin-directory units: resident count drops from 3 to
  2, no dependency edge violated.
- Context-GC test: a two-unit resident run shows the volatile tail reset to a bounded summary
  between units while the stable prefix is unchanged.
- Manifest round-trip pytest: the JSON manifest round-trips the segmentation produced by
  `segment_units()` with no information loss.
- TTL-adjacency emit test: a >3-unit multi-segment spec produces a segment-contiguous batch
  order under the existing concurrency cap.
- Release-surface drift-guard tests (existing repo tooling) stay green with both version bumps
  in place.

### Acceptance criteria
- [ ] A `team_emitter` round-trip test asserts the derived boundary action for a segment.
  Check: `uv run pytest tests/ -k team_emitter_boundary_action` → passes.
- [ ] The A7 worker table format includes a `Boundary` column. Check: `grep -n "Boundary"
  plugins/team-execution/skills/team-execution/SKILL.md
  plugins/team-execution/skills/team-execution/references/external-engine-workers.md` → both
  files reference it.
- [ ] Interleaved plugin-directory units collapse from 3 residents to 2 with no dependency edge
  violated. Check: `uv run pytest tests/ -k segment_reorder_collapse` → passes.
- [ ] A two-unit resident run shows the volatile tail reset to a bounded summary while the
  stable prefix is unchanged. Check: `uv run pytest tests/ -k context_gc_two_unit` → passes.
- [ ] The residency manifest round-trips the segmentation produced by `segment_units()`. Check:
  `uv run pytest tests/ -k residency_manifest_roundtrip` → passes.
- [ ] A doc-review confirms the manifest is derive-on-read (recomputed, never persisted). Check:
  `docs/reviews/<date>-residency-manifest-derived-on-read.md` (or equivalent doc-review artifact)
  exists and states the derive-on-read verdict.
- [ ] `/outcome` frontier dispatch and saga verify-panel spawn both consume the manifest for
  segment-clustered ordering. Check: `grep -rn "residency_manifest\|segment_units" <outcome
  frontier-dispatch module path> <verify-panel spawn module path>` (exact paths per `/plan`) →
  both reference the manifest consumer.
- [ ] A >3-unit multi-segment spec emits a segment-contiguous batch order under the concurrency
  cap. Check: `uv run pytest tests/ -k ttl_aware_batch_contiguous` → passes.
- [ ] Release-surface artifacts updated in the same PR: both plugins' `plugin.json` version
  bumps, `.claude-plugin/marketplace.json` sync, both `CHANGELOG.md` entries. Check: `git diff
  --stat` for the PR includes all five paths.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Boundary action + reorder + context-GC + manifest + TTL-batching unit tests
uv run pytest tests/ -k "team_emitter_boundary_action or segment_reorder_collapse or
  context_gc_two_unit or residency_manifest_roundtrip or ttl_aware_batch_contiguous" -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the reorder test shows resident count 3→2 with no dependency-edge
violation; the manifest round-trip test shows no information loss; the TTL-batching test shows
segment-contiguous batch order for a multi-segment spec.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json (ids `T4-F2-2`,
  `T4-F4-3`, `T4-F6-6`, `T4-F3-7`, `T4-F6-7`)
- Source type: ideation survivor set
- Source title: Plugin-fleet ideation 2026-07-03 — theme T4 (segment-residency scheduling /
  cache-aware prompt architecture)

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/360
- Number: 360
- Created at: 2026-07-04T07:49:30.606817+00:00

