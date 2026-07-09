---
title: Issue #454 Blind External-Engine Divergent Generator Plan
type: feat
status: active
date: 2026-07-09
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json
---

# Issue #454 Blind External-Engine Divergent Generator Plan

## Summary

Add one external-engine divergent-generator lane to `/ideate` Phase 2. The lane uses the same frame-agent
prompt contract as the Claude frame agents, merges into the same candidate pool with `engine-generated`
provenance, and remains advisory: if dispatch is unavailable, `/ideate` proceeds with the existing
Claude-only frame set.

## Problem Frame

Issue #454 is requirements-ready from survivor `T1-F1-2`, which asks for a merged PR where `/ideate`
produces engine-authored candidates tagged `engine-generated` and proves those candidates receive no
convergence exemption. The live issue keeps the scope narrow: one additive Phase 2 lane, no Phase 3 gate
redesign, no new external-engine executor kind.

Current `/ideate` Phase 2 dispatches the N adaptive frame agents on the inherited model at
`plugins/saga/skills/ideate/SKILL.md:414-419`, defines the verbatim frame-agent prompt at
`plugins/saga/skills/ideate/SKILL.md:445-502`, and merges returned candidates only after frame-agent
generation completes at `plugins/saga/skills/ideate/SKILL.md:503-520`. Phase 3 already has the hard
basis gate at `plugins/saga/skills/ideate/references/convergence-and-partnership.md:29-31` and basis
strength scoring at `plugins/saga/skills/ideate/references/convergence-and-partnership.md:44-46`.

The binding external-engine decisions matter here. External engines never become gatekeepers
(`docs/engineering-journal/DECISIONS.md:3005-3016`), and team-execution's external-engine model is
chaperone dispatch, not a second executor kind (`docs/engineering-journal/DECISIONS.md:3041-3059`).
The new lane must follow those boundaries without turning provenance into a second survival rule.

## Requirements

R1. `/ideate` Phase 2 attempts one additional external-engine frame-agent dispatch alongside the N Claude
frame agents selected by Phase 0.4.

R2. The external-engine lane uses the same substituted frame-agent prompt contract as the Claude frame
agents: frame, grounding summary, topic axes, per-agent target, user seeds, constraint/background split,
and tactical-scope flag.

R3. The lane remains blind during generation. It must not receive other frame agents' in-flight raw
candidates, and Claude frame agents must not receive the external-engine lane's in-flight candidates.

R4. External-engine candidates merge into the same master pool and carry `engine-generated` provenance.
The tag is audit/provenance only.

R5. Phase 3 convergence applies the existing basis contract and categorical-kill gate to
`engine-generated` candidates with no tag-conditional exemption, relaxed basis requirement, separate
threshold, or alternate survivor path.

R6. External-engine dispatch failure or unavailability degrades to the existing Claude-only run and does
not block `/ideate`.

R7. Saga release surfaces stay synchronized in the same PR: `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, and version assertions.

## Key Technical Decisions

KTD1. Treat the markdown skill and references as the runtime surface. `/ideate` is markdown-driven, so
the implementation should update the Phase 2 and Phase 3 contracts directly and pin them with structural
tests. Do not add a Python helper solely to make the markdown look executable.

KTD2. Use direct chaperone-dispatch language for this lane, not the generic stage-offer default.
`surface_intent_defaults.yaml` currently defaults `ideate` to judgment-shaped `second-opinion` at
`plugins/saga/references/surface_intent_defaults.yaml:17-21`; this issue is explicitly a generator lane
using `offload` / `sonnet-medium`.

KTD3. Preserve Phase 2 blindness by ordering and data contract, not by adding shared state. The external
lane receives only the same prompt inputs the Claude frame agents receive. All raw outputs meet for the
first time at the existing merge boundary.

KTD4. Record `engine-generated` as provenance, not a scoring signal. The tag may appear in raw candidates,
survivors, and co-ideation/provenance logs, but Phase 3 rejection and scoring criteria stay keyed to basis,
grounding, novelty, value, and overlap.

KTD5. Graceful degradation is the only failure behavior for the lane. Missing CLI, credentials, timeout,
or dispatch error becomes a non-blocking note and the run continues with the existing Claude frame-agent
set.

## High-Level Technical Design

Phase 2 becomes:

```text
Phase 0.4 chooses N Claude frame agents
Phase 2 dispatches those N agents as today
Phase 2 also attempts one chaperoned external-engine generator lane
  target: offload / sonnet-medium
  prompt: the same frame-agent prompt contract, with no candidate-pool backchannel
if external dispatch fails, continue Claude-only
after all available generators return, merge and dedupe into one pool
tag external-lane candidates engine-generated
Phase 3 critiques the merged pool under the existing basis gate
```

No production test should require a live external engine. The behavior is proven by static and structural
tests over the skill/reference contracts, plus release-surface parity checks.

## Implementation Units

### U1. Add the Phase 2 External-Engine Lane Contract

Document the additive lane where `/ideate` defines divergent generation.

**Goal:** Make Phase 2 attempt one external-engine generator lane using the same frame-agent prompt
contract and graceful degradation semantics.

**Requirements:** R1, R2, R3, R6.

**Files:** `plugins/saga/skills/ideate/SKILL.md`, `tests/test_ideate_engine_lane.py`.

**Approach:** Insert a compact "External-engine generator lane" block after the frame-agent prompt and
before "After frame agents return." State that the lane uses chaperone-dispatch `offload` /
`sonnet-medium`, receives the identical substituted frame-agent prompt contract, sees no in-flight
candidate pool, and is skipped non-blockingly when unavailable.

**Test scenarios:** Happy path: `dispatch_contract` proves the Phase 2 contract names one extra
external-engine lane and the identical prompt inputs. Edge case: `blind_isolation` proves the lane is
defined before the merge boundary and explicitly forbids in-flight candidate sharing. Error path:
`graceful_degrade` proves unavailable/failed dispatch is documented as Claude-only continuation, not a
halt. Integration: the test checks the contract lives in `SKILL.md`, the active runtime surface.

**Verification:** `uv run pytest tests/test_ideate_engine_lane.py -k "dispatch_contract or blind_isolation or graceful_degrade" -v`.

### U2. Add Engine-Generated Provenance at Merge and Artifact Surfaces

Record external-lane output as provenance without changing candidate scoring.

**Goal:** Ensure merged candidates and persisted survivors can carry `engine-generated` provenance.

**Requirements:** R4.

**Files:** `plugins/saga/skills/ideate/SKILL.md`,
`plugins/saga/skills/ideate/references/ideation-artifact.md`, `tests/test_ideate_engine_lane.py`.

**Approach:** Update the Phase 2 merge step to tag external-lane candidates `engine-generated` while
keeping existing frame attribution for Claude outputs. Update the ideation artifact template to allow an
optional provenance/source row that includes `engine-generated` alongside existing `frame-agent`,
`user-seed`, and `interview` sources.

**Test scenarios:** Happy path: `tag_application` proves merge text applies `engine-generated` to
external-lane candidates. Edge case: the same test proves non-engine candidates keep ordinary frame or
user provenance. Integration: artifact-template text accepts `engine-generated` so survivors can expose
the tag without a separate section.

**Verification:** `uv run pytest tests/test_ideate_engine_lane.py -k tag_application -v`.

### U3. Pin the No-Exemption Convergence Contract

Make the Phase 3 contract explicit that `engine-generated` is not a special gate category.

**Goal:** Prevent future edits from turning external-generator provenance into a privileged survival path.

**Requirements:** R5.

**Files:** `plugins/saga/skills/ideate/references/convergence-and-partnership.md`,
`tests/test_ideate_engine_lane.py`.

**Approach:** Add a short note under the Phase 3 rejection/scoring rules: provenance, including
`engine-generated`, is informational only. The hard basis gate and survivor scoring apply identically to
all candidates. The note should not add new criteria or a second external-engine review path.

**Test scenarios:** Happy path: `no_gate_exemption` proves the convergence contract states identical
basis treatment for `engine-generated`. Error path: the test gathers every line that mentions
`engine-generated` and asserts each occurrence belongs to an allowlisted provenance-only or
identical-treatment sentence; non-allowlisted occurrences fail with the offending line. Integration: the
test checks the same reference loaded immediately after Phase 2.

**Verification:** `uv run pytest tests/test_ideate_engine_lane.py -k no_gate_exemption -v`.

### U4. Update Release Surfaces and Journal

Ship the Saga behavior change as an installable plugin version.

**Goal:** Keep installed-plugin metadata and durable decision history aligned with the changed `/ideate`
behavior.

**Requirements:** R7.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`.

**Approach:** Bump Saga from `0.75.11` to `0.75.12`, add a changelog entry for issue #454, update the
Saga version assertion, and keep marketplace metadata synchronized with the plugin manifest. The
decision entry records that the lane is additive, direct chaperone-dispatch, provenance-only, and
non-gating.

**Test scenarios:** Happy path: Saga plugin metadata and marketplace versions match. Error path:
release-surface parity fails if plugin metadata and marketplace drift. Integration: changelog and
decision entry name the new lane and its non-gating boundary.

**Verification:** `uv run python scripts/sync_marketplace.py --check`, `uv run python scripts/check_release_surface_parity.py`, `uv run pytest tests/test_saga_plugin.py -v`.

## Scope Boundaries

This issue does not add external-engine lanes to `/brainstorm`, `/work`, `/doc-review`, or
`/code-review`.

This issue does not redesign Phase 0 adaptive frame-count logic; the new lane is additive to the N
chosen Claude frames.

This issue does not change Phase 3 rejection criteria, basis-strength ordering, survivor scoring, or the
revival state machine.

This issue does not require a live external engine in tests.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Static tests over markdown miss runtime drift. | Test the exact skill/reference files that are the runtime contract and keep assertions structural rather than only phrase presence. |
| `engine-generated` becomes a second scoring axis later. | U3 adds a convergence note and allowlisted-occurrence test for provenance-only language. |
| Generic stage-offer helper conflicts with required `offload` target. | KTD2 explicitly avoids `ideate`'s judgment-shaped default for this generator lane. |
| External-engine unavailability blocks ideation. | U1 documents graceful skip and tests that the skill keeps continuation language. |

## Deferred Follow-Up Work

External-engine lanes for `/brainstorm`, `/work`, `/doc-review`, and `/code-review` remain separate
issues.

A future runtime helper for structured frame-agent dispatch is acceptable only if a real reusable caller
emerges; it is not required to land this markdown-driven `/ideate` lane.

## Sources

- `docs/sdlc-issue-drafts/plugin-fleet/pf-ideate-engine-lane.md:91-112` - requirements R1-R5.
- `docs/sdlc-issue-drafts/plugin-fleet/pf-ideate-engine-lane.md:182-213` - definition of done and test expectations.
- `plugins/saga/skills/ideate/SKILL.md:414-520` - current divergent generation prompt and merge boundary.
- `plugins/saga/skills/ideate/references/convergence-and-partnership.md:29-46` - current basis gate and basis-strength scoring.
- `plugins/saga/skills/ideate/references/ideation-artifact.md:57-64` and `plugins/saga/skills/ideate/references/ideation-artifact.md:91-99` - persisted survivor fields and current source values.
- `docs/engineering-journal/DECISIONS.md:3005-3059` - external-engine non-gatekeeper and chaperone-dispatch decisions.
