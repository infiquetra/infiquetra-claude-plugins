---
title: "enhancement: Cheap chaperoning — batched same-engine dispatch, evidence-size-adaptive and verifiability-keyed chaperone tiers, acceptance sampling, content-addressed re-assembly"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Stand up the external-engine offload lane"
---

# enhancement: Cheap chaperoning — batched same-engine dispatch, evidence-size-adaptive and verifiability-keyed chaperone tiers, acceptance sampling, content-addressed re-assembly

### Objective
Stand up the external-engine offload lane

### Tier
structural

### Wave
wave-1

### Intent

The chaperone-dispatch protocol (`{#external-engine-chaperone-dispatch}`, #318) already settles the
shape: one resident Claude chaperone per external-engine unit, owning resolve → dispatch → verify →
apply → test → manifest end-to-end, with `evidence.verified_by_claude = True` hard-required before
`engine_dispatch.satisfy_gate()` (`plugins/saga/scripts/engine_dispatch.py:281-299`) will let advisory
evidence count toward a verdict. What the protocol does not yet make cheap is the *economics* of
running that chaperone at scale: today it is implicitly one chaperone, one context load, one unit —
there is no batching of same-engine units under a single context load, no signal that scales the
chaperone's own tier with how much evidence it has to review, no split between units whose output is
mechanically verifiable versus units where only full human-grade review can catch a defect, no
sampling discipline for high-volume low-risk batches, and no cache to stop `_assemble_payload`
(`plugins/saga/scripts/engine_resolver.py:313-330`) re-reading and re-assembling byte-identical
context on every re-dispatch. This work closes those five gaps as one coherent chaperone-economics
capability rather than five uncoordinated patches, because they share one seam (the chaperone's own
context-load and tier-selection path) and trade against each other (batching changes what "evidence
size" means for tier escalation; sampling only applies where verifiability allows it).

### Problem / motivation (grounded)

- **No batching of same-engine units under one context load.** The chaperone-dispatch contract
  (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:8-13`) already
  names the chaperone as "one resident Claude worker per engine" that "owns the engine's units
  end-to-end," but §1's context package (`external-engine-workers.md:25-37`) is scoped per unit — there
  is no path for N units targeting the same engine to share one context load and emit N distinct,
  independently verified manifests. Each unit today pays its own context-assembly cost even when the
  engine, protocol, and much of the context are identical across units.
- **Chaperone tier is fixed, not evidence-size-adaptive.** The plan-time tier table
  (`plugins/saga/skills/plan/SKILL.md:295-305`) locks a chaperone's `{model, effort}` at plan time from
  work-shape alone; nothing escalates the *chaperone's own* review tier when the evidence it must
  adjudicate (a batch, or a single unusually large diff) grows past what a fixed tier can responsibly
  review, and nothing surfaces that escalation to the operator — it would otherwise happen silently.
- **Tier keys off intent, not verifiability.** The same tier table treats every `intent=offload` unit
  identically (`sonnet/medium`, ratify-only chaperone review) regardless of whether the unit's output
  is mechanically test-gated (a failing test cannot silently pass review) or unverifiable by anything
  except the chaperone's own read (no test oracle exists). Collapsing both into one tier either
  overspends chaperone effort on units a test suite already gates, or underspends it on units where the
  chaperone is the *only* gate.
- **No acceptance-sampling discipline for high-volume batches.** Once batching (above) makes
  many-units-per-chaperone-load real, reviewing every unit at full depth defeats the economics batching
  was meant to buy, but reviewing none risks a silent defect. There is currently no rating-to-sample-
  fraction mapping, and no defined behavior when a sampled unit fails (does the batch stop, or silently
  continue?) — `satisfy_gate()`'s hard `verified_by_claude` requirement means an unsampled unit cannot
  be waved through without an explicit, auditable sampling decision.
- **`_assemble_payload` re-reads and re-assembles on every re-dispatch.** `engine_resolver.py:313-330`
  builds `payload = protocol_block + "\n" + context` fresh on every call to `_resolution_from_entry`
  (`engine_resolver.py:290-308`), including on retries and re-dispatches where the unit's declared
  `files`/context have not changed since the prior dispatch. There is no cache keyed on what actually
  determines the payload's identity (unit, protocol, context), and no test today proves that a cache hit
  would preserve `_assert_payload_preserved`'s byte-identity guarantee (`external-engine-workers.md:91`).

## Grounding References

| id | role | basis | what it contributes |
|---|---|---|---|
| `T1-F1-6` | primary | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (dod_sketch, uncompressed): "Merged PR adding a batched-chaperone context-package variant to `external-engine-workers.md` §1/§5; verified by a test that N same-engine offload units under one chaperone emit N distinct manifests each `verified_by_claude=True` from a single context load." | Establishes the batched-dispatch shape: one context load, N units, N independently gated manifests — batching must not collapse per-unit verification into one blanket sign-off. |
| `T1-F1-5` | facet | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` title: "Evidence-size-adaptive chaperone tier escalation (surfaced, not silent)"; reconstructed against `plugins/saga/skills/plan/SKILL.md:295-305`'s fixed work-shape → tier table and grounding-brief §5-6's chaperone-dispatch constraint (offload → sonnet/medium, second-opinion → opus/high, `{#external-engine-chaperone-dispatch}` #318) | Chaperone tier must escalate as evidence volume grows past a fixed tier's responsible review capacity, and the escalation must be a visible, recorded decision — never a silent re-tier. |
| `T1-F3-4` | facet | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` title: "Chaperone tier should key off verifiability, not just intent"; reconstructed against the same plan-time tier table and `engine_dispatch.satisfy_gate()`'s hard `verified_by_claude` requirement (`plugins/saga/scripts/engine_dispatch.py:281-299`) | Splits offload units into test-gated (mechanically verifiable — a passing test is itself evidence) and unverifiable (no test oracle — chaperone read is the only gate); only the former is eligible for a lighter ratify-only chaperone tier. |
| `T1-F5-4` | facet | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` title: "Acceptance-sampling verification for offload output"; reconstructed against `satisfy_gate()`'s hard-required `evidence.verified_by_claude` bit and the batching shape from `T1-F1-6` | Once batches exist, defines a WEAK/MODERATE/STRONG rating → sample-fraction mapping, plus the mandatory consequence that any sampled defect forces full review of the remaining batch — sampling never silently waves a batch through. |
| `T1-F2-7` | facet | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` dod_sketch (uncompressed): "Merged PR adding a content-addressed cache behind `_assemble_payload` keyed on `unit_id+protocol-hash+context-hash` with hit/miss provenance; verified by tests asserting identical inputs hit, changed context misses, and byte-preservation holds on a cache hit." Grounds directly to `plugins/saga/scripts/engine_resolver.py:290-330` (`_resolution_from_entry` / `_assemble_payload`). | Removes redundant re-assembly and re-reads on re-dispatch without weakening the byte-preservation guarantee `_assert_payload_preserved` already enforces (`external-engine-workers.md:91`). |

### Key decisions this capability must respect

- `{#external-engine-chaperone-dispatch}` (#318) — external engines in teams are chaperone dispatch
  only (`offload → sonnet/medium`, `second-opinion → opus/high`); never a second executor kind,
  residency slot, or git participant. Batching and tier escalation happen *within* the chaperone role,
  never by promoting the engine itself.
- `{#external-engines-never-gatekeepers}` (#283) — Claude is verifier-of-record on every gated
  decision; codex/agy remain generator/advisory-reviewer/non-gated worker only. Acceptance sampling
  (`T1-F5-4`) narrows *how much* the chaperone reads per unit, never *who* adjudicates — the chaperone
  still sets `verified_by_claude = True`, never the engine.
- `{#tier-vocab-ordering}` — `MODELS`/`EFFORTS` are ordered escalation ladders
  (`plugins/saga/scripts/execution_spec.py:52-53`); evidence-size-adaptive escalation (`T1-F1-5`) must
  move one rung at a time up this existing ladder, never to an arbitrary tier outside it.
- `{#worker-cache-scheduling}` — cache economics theme's settled architecture: derive
  (segment+agent+tier) saga-side, reside team-side, segment boundary = plugin directory. The
  content-addressed payload cache (`T1-F2-7`) is a narrower, unit-scoped cache and must not duplicate
  or conflict with this broader cache-residency architecture.

## Definition of Done

A merged PR that: (1) adds a batched-chaperone context-package variant to
`external-engine-workers.md` §1/§5 so N same-engine offload units resolve under one chaperone context
load while still emitting N distinct, independently `verified_by_claude=True` manifests; (2) adds
evidence-size-adaptive tier escalation to the chaperone's own review tier, surfaced as a recorded,
non-silent decision rather than a silent re-tier; (3) splits the offload tier row into a test-gated
(ratify-only, lighter chaperone review) and an unverifiable (full chaperone review) branch, keyed on
whether the unit carries a test oracle; (4) adds a WEAK/MODERATE/STRONG acceptance-sampling rating to
sample-fraction mapping for batched dispatch, with any sampled defect forcing full review of the
remaining batch; (5) adds a content-addressed cache behind `_assemble_payload` keyed on
`unit_id+protocol-hash+context-hash`, with hit/miss provenance and a preserved byte-identity guarantee
on cache hits. All five ship together because they share the chaperone's context-load and
tier-selection seam and trade against one another. Verified by the test suite in Acceptance criteria
below plus a full green run of `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/
tests/ --ignore-missing-imports`.

### Acceptance criteria
- [ ] N same-engine offload units dispatched under one chaperone context load each emit a distinct
  manifest with its own `verified_by_claude=True`, from a single shared context load (no per-unit
  re-read). Check: `uv run pytest tests/test_external_engine_workers.py -k batched_same_engine_dispatch`
  → passes, asserting `N` manifests, `N` independent `verified_by_claude` bits, and exactly one context
  load in the batch's trace. *(covers `T1-F1-6`)*
- [ ] Chaperone tier escalates one rung up the `MODELS`/`EFFORTS` ladder
  (`execution_spec.py:52-53`) when batch/unit evidence volume crosses a documented threshold, and the
  escalation is recorded on the manifest (never applied silently). Check: `uv run pytest
  tests/test_external_engine_workers.py -k evidence_size_escalation` → passes, asserting the escalated
  tier and its recorded reason both appear on the manifest. *(covers `T1-F1-5`)*
- [ ] A test-gated offload unit (carries a test oracle) resolves to a lighter ratify-only chaperone
  tier; a unit with no test oracle keeps the full chaperone-review tier. Check: `uv run pytest
  tests/test_external_engine_workers.py -k verifiability_keyed_tier` → passes for both branches.
  *(covers `T1-F3-4`)*
- [ ] A batch rated WEAK/MODERATE/STRONG resolves to its mapped sample fraction, and any defect found
  in the sampled subset forces full review of the remaining unsampled units in that batch (no
  silent pass-through). Check: `uv run pytest tests/test_external_engine_workers.py -k
  acceptance_sampling` → passes for a clean sample (partial review honored) and a defective sample
  (escalates to full review). *(covers `T1-F5-4`)*
- [ ] `_assemble_payload` cache hits on identical `unit_id+protocol-hash+context-hash`, misses when
  context changes, and preserves byte-identical payload on a cache hit (`_assert_payload_preserved`
  still holds). Check: `uv run pytest tests/test_engine_resolver.py -k
  assemble_payload_cache` → passes for hit, miss, and byte-preservation-on-hit cases. *(covers
  `T1-F2-7`)*
- [ ] Full suite, lint, and types stay green. Check: `uv run pytest && uv run ruff check . && uv run
  mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
- **In scope:** batched-chaperone context-package variant in `external-engine-workers.md` §1/§5;
  evidence-size-adaptive chaperone tier escalation with a recorded reason; a verifiability split on the
  offload tier row (test-gated vs. unverifiable); an acceptance-sampling rating-to-fraction mapping with
  a mandatory full-review escalation on any sampled defect; a content-addressed cache behind
  `_assemble_payload`.
- **Non-goals / explicitly out of scope:**
  - Changing who adjudicates — the chaperone remains the sole `verified_by_claude` setter; no
    engine gains gatekeeper status (`{#external-engines-never-gatekeepers}`, #283).
  - Introducing a new executor kind, engine residency slot, or engine git participation — batching
    stays within the existing chaperone role (`{#external-engine-chaperone-dispatch}`, #318).
  - The broader worker-cache-scheduling architecture (segment+agent+tier derivation, team-side
    residency) — the payload cache here is a narrower, unit-scoped cache and does not attempt to
    subsume or reimplement that settled architecture (`{#worker-cache-scheduling}`).
  - Building a run-fact cost ledger or standing calibration harness for sampling accuracy — sampling
    fractions here are a static rating-keyed table, not a measured, self-tuning system.
  - Retrofitting the plan-time unit-tier table's *initial* assignment mechanism — this capability
    changes what the chaperone does with a unit once dispatched, not `/plan`'s Step 1 authoring flow.

## Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** matches the source issue-map's executor profile (`sonnet/high`, `inline`, `none`).
  This is bounded, mechanical extension of an already-settled protocol (chaperone-dispatch, #318) — the
  batching shape, tier-escalation ladder, verifiability split, sampling-fraction table, and cache key
  are all fully specified by the absorbed ideas above; no open architectural or adversarial-review
  question remains that would justify opus-tier judgment.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` — batched
  context-package variant (§1), tier-escalation and verifiability-split guidance (§5), acceptance
  sampling guidance.
- `plugins/saga/skills/plan/SKILL.md` — offload tier row split (test-gated vs. unverifiable) in the
  Step 1 tier table (currently `SKILL.md:295-305`).
- `plugins/saga/scripts/engine_resolver.py` — content-addressed cache behind `_assemble_payload`
  (currently `engine_resolver.py:313-330`).
- `plugins/saga/scripts/engine_dispatch.py` — chaperone tier-escalation recording alongside existing
  manifest-recording paths (`engine_dispatch.py:124-161`).
- `tests/test_external_engine_workers.py` — new batching, tier-escalation, verifiability-split, and
  acceptance-sampling tests (repo-root collected).
- `tests/test_engine_resolver.py` — new payload-cache hit/miss/byte-preservation tests.

### Tests to add or update

- Batched dispatch: N same-engine units under one chaperone context load emit N distinct,
  independently `verified_by_claude=True` manifests from a single context load.
- Tier escalation: evidence volume crossing threshold escalates chaperone tier one rung up the
  `MODELS`/`EFFORTS` ladder, with the reason recorded on the manifest.
- Verifiability split: a test-gated unit resolves to a ratify-only tier; a no-oracle unit keeps full
  chaperone review.
- Acceptance sampling: WEAK/MODERATE/STRONG ratings resolve to their mapped sample fractions; a
  sampled defect forces full review of the remaining batch.
- Payload cache: identical `unit_id+protocol-hash+context-hash` hits; changed context misses;
  byte-identity is preserved on a cache hit.

### Verification

```bash
uv run pytest tests/test_external_engine_workers.py -v
uv run pytest tests/test_engine_resolver.py -k assemble_payload_cache -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; batching test shows N distinct manifests from one context load; cache test shows
a hit, a miss on changed context, and byte-identity preserved on the hit.

### Release-surface checklist (plugin behavior changes — required)

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump + description update
  reflecting the batched-chaperone context-package variant and new tier/sampling behavior.
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the offload tier-row split
  and the `_assemble_payload` cache addition.
- [ ] `.claude-plugin/marketplace.json` — both plugin entries' version/description kept in sync with
  the bumps above.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry documenting batched dispatch, evidence-size tier
  escalation, verifiability-keyed tiers, and acceptance sampling.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the offload tier-row split and the
  content-addressed payload cache.
- [ ] Version/metadata drift-guard tests (if present in `tests/`) updated or added to assert
  `plugin.json`/`marketplace.json`/`CHANGELOG.md` tell the same story as the diff.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json (ids: T1-F1-6, T1-F1-5,
  T1-F3-4, T1-F5-4, T1-F2-7)
- Source type: ideation issue-map
- Source title: Cheap chaperoning: batched same-engine dispatch, evidence-size-adaptive and
  verifiability-keyed chaperone tiers, acceptance sampling, content-addressed re-assembly

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/381
- Number: 381
- Created at: 2026-07-04T07:55:27.107838+00:00

