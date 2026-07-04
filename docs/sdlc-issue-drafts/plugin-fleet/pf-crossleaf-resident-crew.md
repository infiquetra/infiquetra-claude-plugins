---
title: "capability: cross-leaf resident crew and crew-pairing — warm workers across the /outcome DAG, evidence-gated overlap pairing"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: moonshot
wave: wave-3
objective: "Make cache economics an engineered, measured win"
slug: pf-crossleaf-resident-crew
---

# capability: cross-leaf resident crew and crew-pairing — warm workers across the /outcome DAG, evidence-gated overlap pairing

### Objective

Make cache economics an engineered, measured win.

### Intent

`worker-cache-scheduling` (`docs/engineering-journal/DECISIONS.md:1950-1971`, `{#worker-cache-scheduling}`)
settled residency to a single team-execution run: saga derives (segment + agent-id + tier), team-execution
resides (named teammate + `SendMessage` reuse), with segment boundary = plugin directory (KTD2). That decision
also named its own escape hatch and left it unfired: "Named-teammate residency proves insufficient (revisit
warm-pool / crew-pairing)" (`DECISIONS.md:1970`-1971). This issue fires that revisit-when across a boundary
`worker-cache-scheduling` never crossed — the `/outcome` DAG, where sibling leaves are dispatched as
independent team-execution runs rather than units inside one run.

This merges three absorbed ideation facets from theme T4 into one gated change set:

1. **Cross-leaf resident-crew registry** (`T4-F2-6`, primary) — a per-segment registry, keyed on plugin
   directory, that survives across an `/outcome` DAG's ready frontier so a sibling leaf on the same segment
   reuses the prior leaf's named worker and carried segment summary instead of spawning cold.
2. **Crew-pairing multi-leg re-briefing protocol** (`T4-F5-3`, facet) — a paired-agent-id convention (worker +
   reviewer) threaded through `team_emitter.py`, documented in `consensus-protocol.md`, so review/remediation
   cycles re-engage the same crew across consensus legs instead of re-warming context per teammate per leg.
3. **Context-overlap crew-pairing mode** (`T4-F3-3`, facet) — an explicitly *gated* fallback that reframes
   residency scheduling around a context-overlap graph over `Unit.files` rather than the coarser
   plugin-directory proxy, shipped only if a named A/B benchmark (`T4-F3-6`) shows plugin-directory residency
   underperforming its potential reuse.

These three compound: the registry is the mechanism that makes cross-leaf reuse possible at all; crew-pairing
is the same registry's identity convention extended to the reviewer role; the overlap-graph mode is a strictly
better residency-key function that only pays for itself once the benchmark proves the cheaper proxy
insufficient — building it unconditionally would silently re-cross the same revisit-when this issue is
carefully engaging.

## Problem Frame

`worker-cache-scheduling`'s residency lives inside one team-execution run. Across an `/outcome` DAG, sibling
leaves that touch the same plugin-directory segment each spawn a fresh worker on their own team-execution
invocation, re-paying full context creation per leaf — this is the exact condition the decision's own
revisit-when clause anticipated but did not resolve (`DECISIONS.md:1970`-1971: "Named-teammate residency
proves insufficient (revisit warm-pool / crew-pairing)").

Grounding: `/outcome` leaf dispatch is a real decomposition path where each leaf currently spawns
independently (grounding brief §1 corrections, item (h)); segment boundary = plugin directory is KTD2
(`DECISIONS.md:1962`, "Single monorepo; VECU's repo-change proxy never fires"). Review/remediation consensus
cycles separately re-pay per-teammate re-briefing cost each time a reviewer or worker is re-engaged
(`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:57`, "RE-ENGAGE the same
named reviewer via `SendMessage`") — that re-engagement has no paired-identity convention today, so worker and
reviewer residency are tracked independently even when they cycle together.

The honest limit that must stay visible: raw prompt-cache hits decay past the 5-minute TTL between leaves, so
what this ships is *worker reuse* (a warm teammate carrying a segment summary forward), not a guarantee of a
`cache_read` hit — a win in re-briefing and context-reconstruction cost, not a TTL-defying trick.

## Key Decisions

- **Extend `worker-cache-scheduling`, engage its revisit-when explicitly, do not re-derive it.** The registry
  and crew-pairing protocol stay inside the settled derive-saga-side/reside-team-side seam; they widen its
  scope from "one team-execution run" to "the `/outcome` DAG's ready frontier," which is precisely what the
  clause names.
- **Registry key stays plugin directory (KTD2) unless benchmarked otherwise.** The overlap-graph crew-pairing
  mode is explicitly gated behind `T4-F3-6`'s A/B benchmark result. It does not ship by default, and does not
  ship at all unless the benchmark shows the plugin-directory proxy underperforming its potential reuse. This
  is a hard gate, not a soft preference — the PR for facet 3 does not land until that evidence exists and is
  recorded.
- **Reuse carries a segment summary, not a memory claim.** Leaf N inherits leaf N-1's warm context via a
  carried segment summary handed through the registry, not via an assumption that the underlying prompt cache
  is still warm. TTL decay is a known, documented limit, not a silent gap.
- **Crew-pairing is an identity convention, not a new scheduling primitive.** Paired agent-ids (worker +
  reviewer) are emitted alongside each other per segment; this makes an existing re-engagement pattern
  (`consensus-protocol.md:57`) explicit and reusable across legs, it does not introduce a second scheduler.

## Requirements

**Cross-leaf resident-crew registry (T4-F2-6, primary)**

R1. The `/outcome` dispatch spec maintains a per-segment (plugin-directory-keyed) resident-crew registry that
persists across the DAG's ready frontier, derived on read at dispatch time — never a committed status field,
consistent with `/outcome`'s existing derived-on-read rule.

R2. When two sibling leaves on the same segment are dispatched in sequence, the second leaf's dispatch looks
up the registry and reuses the first leaf's worker id rather than requesting a fresh spawn.

R3. The reused worker receives the carried segment summary from the prior leaf, not a cold-context rebuild.

R4. A test asserts: two sibling leaves on the same segment produce one worker id across both dispatches.

**Crew-pairing multi-leg re-briefing protocol (T4-F5-3, facet)**

R5. `team_emitter.py` threads a paired agent-id (worker id + reviewer id) per segment through the emitted team
structure, so a consensus cycle's reviewer role carries the same paired-identity convention as the worker
role.

R6. `consensus-protocol.md` documents the crew-pairing residency protocol: how a paired reviewer is
re-engaged via `SendMessage` across consensus legs using the same identity convention as worker residency.

R7. A test asserts: a paired reviewer id is emitted alongside its worker id for a given segment.

R8. `/doc-review` confirms the crew-pairing protocol documentation is implementation-ready before `/plan`
picks it up.

**Context-overlap crew-pairing mode (T4-F3-3, facet — explicitly gated)**

R9. This facet does not ship unconditionally. It ships only if `T4-F3-6`'s A/B benchmark demonstrates that
flat plugin-directory residency underperforms its potential reuse (i.e., units in the same plugin directory
but touching disjoint files share little warm context, while units in different plugin directories reading
shared references would share a lot).

R10. If and only if the gate in R9 passes, an overlap-graph pairing mode is added behind a resolver flag in
`execution_spec.py` (`segment_units` mode), computing residency pairing from a context-overlap graph over
`Unit.files` rather than the plugin-directory proxy.

R11. Landing R10 requires a `DECISIONS.md` addendum on `{#worker-cache-scheduling}` recording the revisit
trigger (the benchmark result) that justified crossing KTD2's plugin-directory default.

R12. A pytest suite exercises the overlap-graph pairing mode against synthetic file-overlap fixtures, asserting
that high-overlap units pair onto one resident and low-overlap units do not.

### Acceptance criteria
- [ ] Two sibling leaves on the same segment produce one worker id across both dispatches (R4).
- [ ] A paired reviewer id is emitted alongside its worker id for a given segment (R7).
- [ ] The overlap-graph pairing mode ships only if `T4-F3-6`'s benchmark evidence exists and shows
  plugin-directory residency underperforming; absent that evidence, the PR ships facets 1 and 2 only, with
  facet 3 explicitly noted as blocked-on-evidence (R9).
- [ ] Full repo test/lint/type suite stays green with the new code paths included.

### Out-of-scope / non-goals
- **In scope:** the cross-leaf resident-crew registry in the `/outcome` dispatch spec; the crew-pairing
  paired-agent-id convention in `team_emitter.py` and `consensus-protocol.md`; the gated overlap-graph pairing
  mode, conditional strictly on the `T4-F3-6` benchmark; associated tests and the `DECISIONS.md` addendum for
  the gated facet.
- **Out of scope / non-goals:**
  - Building the overlap-graph pairing mode (R10-R12) unconditionally or ahead of the `T4-F3-6` benchmark
    result — it is a gated fallback, not a default.
  - Running the `T4-F3-6` benchmark itself as part of this issue — that benchmark is a prerequisite input to
    this issue's gated facet, not a deliverable of it. If the benchmark has not run, R9-R12 stay unimplemented
    and the issue ships facets 1 and 2 only.
  - Changing the segment-boundary default (plugin directory, KTD2) outside the gated path.
  - Formal warm-pool residency (a distinct escalation named in the same revisit-when clause) — this issue
    implements the registry and crew-pairing escalations named in the clause, not warm-pool.
  - Any change to `/outcome`'s existing derived-on-read status-field rule — the registry follows it, does not
    modify it.
  - Cross-repo residency (registry stays scoped to this monorepo's `/outcome` DAG, consistent with KTD2's
    "single monorepo" basis).

## Definition of Done

- The `/outcome` dispatch spec carries a merged per-segment cross-leaf resident-crew registry (derived on
  read, keyed on plugin directory) that two sibling leaves on the same segment demonstrably reuse.
- The crew-pairing protocol (paired agent-ids emitted per segment) is documented in `consensus-protocol.md`
  and implemented in `team_emitter.py`, with a passing test asserting the paired reviewer id is emitted
  alongside its worker id.
- The context-overlap crew-pairing mode ships only if the `T4-F3-6` benchmark evidence exists and shows
  plugin-directory residency underperforming; if that evidence is absent at PR time, the PR ships facets 1 and
  2 only and explicitly notes facet 3 as blocked-on-evidence, not silently dropped.
- Each of the three facets has a `DECISIONS.md` entry (or a shared addendum to `{#worker-cache-scheduling}`)
  recording the revisit-when firing and, for the gated facet, the benchmark trigger.
- Full repo test/lint/type suite stays green with the new code paths included.

## Grounding References

- `T4-F2-6` (primary) — cross-leaf resident crew. Basis: direct —
  `docs/engineering-journal/DECISIONS.md:1970`-1971 revisit-when ("Named-teammate residency proves
  insufficient (revisit warm-pool / crew-pairing)"); grounding brief §1 corrections item (h): `/outcome` leaf
  dispatch is a real decomposition path where each leaf currently spawns independently; segment boundary =
  plugin directory is KTD2 (`DECISIONS.md:1962`).
- `T4-F5-3` (facet) — crew-pairing multi-leg re-briefing. Basis: direct — same revisit-when clause
  (`DECISIONS.md:1970`-1971), read against
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:57` ("RE-ENGAGE the same
  named reviewer via `SendMessage`") as the existing re-engagement seam being made explicit, not replaced.
- `T4-F3-3` (facet, gated) — context-overlap crew-pairing mode. Basis: direct — KTD2 (`DECISIONS.md:1962`,
  "Single monorepo; VECU's repo-change proxy never fires" grounds segment=plugin-directory) plus the
  doc-review addendum's added `Unit.files` field as the substrate for overlap computation; this facet crosses
  KTD2 and is therefore explicitly gated on `T4-F3-6`'s A/B benchmark showing flat plugin-directory residency
  underperforming its potential reuse.
- `S-21` (dedup-merged seed) — "Decomposition tuned for cache-reads vs throughput (which?)." Operator
  statement, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (id `S-21`). Its
  cache-vs-throughput tradeoff question is folded into this issue's registry/crew-pairing tradeoff framing:
  the registry pursues cache-reuse locality; nothing here changes throughput-oriented fan-out defaults
  elsewhere in the fleet.
- `S-30` (dedup-merged seed) — "Group agent activity into same worker to maximize cache reads." Operator
  statement, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (id `S-30`), constrained by
  `{#worker-cache-scheduling}`. This is the single-run version of the same idea this issue extends across
  `/outcome` leaves; the resident-crew registry is its DAG-scoped generalization.
- Binding decision this issue builds on: `worker-cache-scheduling`
  (`docs/engineering-journal/DECISIONS.md:1950`-1971) — derive segment/agent/tier saga-side, reside
  team-side; segment boundary = plugin directory (KTD2); revisit-when named-teammate residency proves
  insufficient (engaged directly by this issue's facets 1 and 2; facet 3 engages KTD2 itself, gated).
- Consolidation rationale (issue map, `pf-crossleaf-resident-crew` entry): all three facets sit on the same
  named revisit-when clause and the same registry substrate — the registry (facet 1) is the mechanism, crew
  identity (facet 2) is the same mechanism applied to the reviewer role, and the overlap-graph key (facet 3)
  is a strictly better residency key that only pays for itself once benchmarked, so shipping it unconditionally
  would re-cross KTD2 silently.

## Recommended Executor Profile

- **Model:** Opus.
- **Effort:** High. — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution.
- **External LLM posture:** Second-opinion (advisory).
- **Justification:** This issue crosses a binding decision through its own named revisit-when clause
  (`{#worker-cache-scheduling}`), and its gated facet (T4-F3-3) additionally crosses that decision's KTD2
  segment-boundary default conditional on benchmark evidence. Deciding how a resident-crew registry
  generalizes residency semantics across DAG leaves, and how a paired-identity convention threads through an
  existing re-engagement seam without duplicating it, is architectural judgment about residency semantics,
  not mechanical extension — this warrants Opus over Sonnet, plus an advisory second opinion on the
  registry/crew-pairing design before it lands, given the moonshot tier and the risk of quietly re-deriving a
  settled decision instead of engaging its revisit-when as written.

## Release-Surface Checklist

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump for the `/outcome` dispatch spec's registry
  addition.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump for `team_emitter.py` crew-pairing
  threading and `consensus-protocol.md` protocol changes.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for both `saga` and `team-execution`.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the cross-leaf resident-crew registry (and, if shipped,
  the gated overlap-graph pairing mode).
- [ ] `plugins/team-execution/CHANGELOG.md` — entry documenting the crew-pairing paired-agent-id convention.
- [ ] Release-surface / version-metadata drift-guard tests — verified green with both version bumps in place.
- [ ] `docs/engineering-journal/DECISIONS.md` — addendum(s) to `{#worker-cache-scheduling}` recording the
  revisit-when firing for facets 1 and 2, and (if shipped) the benchmark-trigger addendum for facet 3.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/execution_spec.py` — `/outcome` dispatch-spec resident-crew registry; gated
  overlap-graph `segment_units` mode behind a resolver flag (facet 3 only, conditional on benchmark evidence).
- `plugins/saga/scripts/team_emitter.py` — paired agent-id (worker + reviewer) threading per segment.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — crew-pairing residency
  protocol documentation for multi-leg re-briefing.
- `docs/engineering-journal/DECISIONS.md` — addendum(s) to `{#worker-cache-scheduling}`.
- `tests/test_execution_spec.py` (or new `tests/test_resident_crew_registry.py`) — cross-leaf reuse test,
  gated overlap-graph pairing test against synthetic file-overlap fixtures.
- `tests/test_team_emitter.py` — paired reviewer-id emission test.
- `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`,
  `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface updates.

### Tests to add or update

- Cross-leaf reuse: two sibling leaves on the same segment produce one worker id across both dispatches.
- Crew-pairing emission: a paired reviewer id is emitted alongside its worker id for a given segment.
- Gated overlap-graph pairing (facet 3, conditional on benchmark evidence): high-overlap units (per
  `Unit.files`) pair onto one resident; low-overlap units in the same plugin directory do not, over synthetic
  file-overlap fixtures.
- Release-surface drift guard: version/metadata consistency across both plugins' `plugin.json` and the
  marketplace manifest.

### Verification

```bash
# Cross-leaf registry + crew-pairing unit tests
uv run pytest tests/ -k "resident_crew_registry or crew_pairing_emission" -v

# Gated overlap-graph pairing test (only if T4-F3-6 benchmark evidence exists and facet 3 shipped)
uv run pytest tests/ -k "overlap_graph_pairing" -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the cross-leaf reuse test shows one worker id across two sibling-leaf dispatches on the
same segment; the crew-pairing test shows a paired reviewer id emitted alongside its worker id; the gated
overlap-graph test (if applicable) shows high-overlap units pairing onto one resident.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan. Note: before planning facet 3 (T4-F3-3), confirm whether
`T4-F3-6`'s A/B benchmark has run and recorded its result — if not, plan facets 1 and 2 only and leave facet 3
explicitly blocked-on-evidence in the plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json (ids `T4-F2-6`, `T4-F5-3`, `T4-F3-3`);
  docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json (ids `S-21`, `S-30`, dedup-merged)
- Source type: ideation survivor set
- Source title: Plugin-fleet ideation 2026-07-03 — theme T4 (segment-residency scheduling / cache-aware
  prompt architecture)

### Context library links

_none_

### Inputs inventory

- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/team-execution/CHANGELOG.md`
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

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/438
- Number: 438
- Created at: 2026-07-04T08:14:16.902627+00:00

