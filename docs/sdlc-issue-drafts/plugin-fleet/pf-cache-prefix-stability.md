---
title: "enhancement: cache-prefix stability — silent-invalidator lint, stable-first context-package primitive, and CI byte-stability regression guard"
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
objective: "Make cache economics an engineered, measured win"
slug: pf-cache-prefix-stability
---

# enhancement: cache-prefix stability — silent-invalidator lint, stable-first context-package primitive, and CI byte-stability regression guard

### Objective
Make cache economics an engineered, measured win.

### Intent
Prompt-cache reuse in this repo currently depends on prefix byte-stability that nothing checks,
nothing enforces at assembly time, and nothing regression-guards. This issue merges three
absorbed ideation facets from theme T4 (cache-aware prompt architecture) into one structural
change set that makes cache-prefix stability an engineered property instead of an accident:

1. **A silent-invalidator lint** (`T4-F1-4`, primary) that statically scans injected
   `SKILL.md` files, references, and context-assembly sites for a volatile token (timestamp,
   run-id, UUID, unsorted-JSON) placed ahead of stable prose, and fails CI on any hit.
2. **A shared stable-first context-package primitive** (`T4-F4-5`, facet) so the three existing
   hand-rolled prompt-assembly call sites — cross-segment summary handoff, reviewer delta
   re-engagement, and chaperone dispatch — build their worker prompts through one assembler that
   always emits stable content before volatile content, instead of each risking its own ordering
   bug.
3. **A CI byte-stability regression guard** (`T4-F6-8`, facet) that snapshots the resident-prefix
   bytes for a fixture `ExecutionSpec` and fails CI the moment a refactor silently reorders or
   injects content ahead of that prefix, with a documented "this was intentional" bump path.

None of these three exists today. All three protect the same underlying mechanism — prompt-cache
hit rate is governed entirely by longest-byte-identical-prefix matching — so shipping them
together, rather than as three separate issues, means the lint and the regression guard both
validate the same primitive the second change introduces, and none of the three is a no-op
without the others (a lint with nothing enforcing ordering at assembly time just re-flags the
same class of bug the assembler was built to prevent).

## Problem Frame

Resident-worker cache reuse (the `worker-cache-scheduling` decision —
`docs/engineering-journal/DECISIONS.md:1950`) only pays off if the prompt prefix handed to a
reused worker is byte-identical across re-engagements. Today nothing in this repo checks that
property, enforces it at assembly time, or regression-guards it, even though three independent
prompt-assembly call sites already depend on it and prompts in this repo are edited freely with
no cache-awareness (grounding brief, section 1).

- **No static check exists.** `plugins/saga/scripts/execution_spec.py` and every
  `plugins/*/skills/**/SKILL.md` / reference file can have a volatile token (a timestamp, a
  run-id, an unsorted `json.dumps`) interpolated ahead of stable prose with nothing catching it.
  Anthropic's own prompt-caching guidance (referenced in this repo's `claude-api` skill,
  `shared/prompt-caching.md`) documents this exact failure class: a volatile value early in the
  prefix silently invalidates the cache for everything after it, and the only symptom is
  `cache_read_input_tokens` staying at zero across identical-prefix requests — which nobody in
  this repo is watching. The org's own precedent for this shape of check —
  `check_docs.py` schema/frontmatter/link linting wired into `validate.yml` CI
  (grounding brief, section 4, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`) — has
  no analogue for cache-prefix ordering.
- **No shared assembly primitive exists.** Three call sites each hand-concatenate a worker
  prompt today, and none of them is written with a stable-first ordering contract:
  - Cross-segment summary handoff (R4),
    `plugins/team-execution/skills/team-execution/SKILL.md:305` ("Cross-Segment Summary-Handoff
    (R4): When a dependent segment requires the result of a prior segment, seed the dependent
    segment's fresh worker with a short summary...").
  - Reviewer delta-only re-engagement,
    `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:207` ("When
    re-engaging reviewers in Step B3e (Re-engagement, Iteration N >= 2), send a message carrying
    only the delta context...").
  - Chaperone dispatch,
    `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` section
    1 ("Context package (coordinator → chaperone)" — the field table assembled at residency
    spawn).

  Each site independently decides ordering; any one of them placing a volatile field (a delta, a
  timestamp, prior output) before a stable field (the plan pointer, the segment brief, the
  standards) silently voids that site's cacheable prefix with no test failure, because nothing
  functional breaks — only token spend goes up.
- **No regression guard exists.** `segment_units()`
  (`plugins/saga/scripts/execution_spec.py:1384`) derives the resident-prefix-determining
  segmentation from an `ExecutionSpec`, and the agent-prompt content in `plugins/*/agents/*.md`
  is also prefix-determining. Both change routinely with no cache-awareness (grounding brief,
  section 1), and a benign refactor to either can reorder a prefix and quietly convert every
  future re-engagement from a cache hit to a cache miss — invisible until a token bill spikes,
  because prompt caching has zero functional test signal on drift.

This is the repo's stated dominant untested failure class for cache economics: the mechanism
degrades silently, with no static check, no shared enforcement point, and no regression alarm.

## Key Decisions

These framing choices carry forward from the ideation survivors and constrain scope below.

- **Static lint, not a runtime guard.** The invalidator check runs in CI over source files
  (`SKILL.md`, references, assembly modules), matching the existing `check_docs.py` schema-lint
  shape rather than adding a runtime instrumentation layer. Where a relocation is
  mechanically safe (the volatile token can move after the last stable block without changing
  meaning), the lint fixes it; otherwise it reports the site and fails.
- **One assembler, three adopters — not three independent fixes.** `T4-F4-5`'s
  `context_package.py` primitive is adopted by all three existing call sites (cross-segment
  handoff, reviewer re-engagement, chaperone dispatch) rather than patching each site's ordering
  bug locally. This is the compounding win named in the survivor: a single well-ordered
  assembler lifts cache reuse across every current and future reuse site at once.
- **Golden-snapshot regression test, not a live-metrics dashboard.** `T4-F6-8` is a committed
  fixture-based golden snapshot of resident-prefix bytes, not a standing measurement/telemetry
  system — consistent with this repo's rejection of ceremony-shaped standing-measurement loops
  for a solo-operated toolset (the same "on-demand, not scheduled" framing used elsewhere in this
  ideation wave). An intentional prefix change is a documented, reviewed CONTRIBUTING bump, not a
  silently-updated snapshot.
- **Three facets ship together.** The lint (primary) and the two facets (assembler, regression
  guard) are one merged change set per the issue map's consolidation, because the lint alone
  cannot enforce ordering at assembly time, and the regression guard alone cannot explain *why*
  a drift happened without the assembler's documented ordering contract to check against.

## Requirements

**Silent-invalidator lint (T4-F1-4, primary)**

R1. A new lint script under `tools/` scans `plugins/*/skills/**` (`SKILL.md` and referenced
`.md` files) and known context-assembly modules for a volatile-token pattern (timestamp,
run-id, UUID, unsorted `json.dumps`/dict-interpolation) appearing ahead of stable prose in the
same injected block.

R2. The lint is wired into CI following the `check_docs.py` precedent (fails the build on any
finding; does not silently warn).

R3. Where a finding is mechanically relocatable (the volatile token can be moved after the last
stable block with no semantic change), the lint proposes or applies the relocation; otherwise it
reports the exact file and line.

R4. A seeded volatile-token-before-stable-prose fixture fails the lint; the same fixture with the
token relocated after the stable block passes.

**Stable-first context-package primitive (T4-F4-5, facet)**

R5. A new `context_package.py` module (proposed path:
`plugins/team-execution/skills/team-execution/scripts/context_package.py`) partitions assembled
prompt content into a `stable` block and a `volatile` block and serializes stable-first, always.

R6. The three existing hand-concatenation sites — cross-segment summary handoff
(`SKILL.md:305`), reviewer delta re-engagement (`consensus-protocol.md:207`), and chaperone
dispatch (`external-engine-workers.md` context-package table) — are switched to call this
primitive instead of assembling their own prompt string.

R7. The stable-first ordering contract is documented in `consensus-protocol.md` (or the
assembler's own docstring/reference doc) so future reuse sites adopt the same contract rather
than re-inventing ordering.

R8. A unit test asserts that two calls to the assembler differing only in the volatile block
produce a byte-identical stable prefix.

**CI byte-stability regression guard (T4-F6-8, facet)**

R9. A new test module (proposed path: `tests/test_cache_prefix_stability.py`) computes the
resident-prefix bytes for a fixture `ExecutionSpec` via `segment_units()`
(`plugins/saga/scripts/execution_spec.py:1384`) and compares them against a committed golden
snapshot.

R10. The test passes on `HEAD` and fails when the fixture's prompt prefix is perturbed (a
reordering or an early injected token), proving the guard actually detects drift rather than
trivially passing.

R11. A `CONTRIBUTING.md` (or equivalent) note documents the process for an intentional
prefix-bump: regenerate the snapshot, note why in the PR, no silent snapshot regeneration in CI
itself.

### Out-of-scope / non-goals
- **In scope:** the lint (`tools/`), the shared assembler and its three call-site adoptions
  (`plugins/team-execution/skills/team-execution/`), the golden regression test
  (`tests/`), and the CI wiring for both the lint and the regression test.
- **Out of scope / non-goals:**
  - Any runtime cache-hit telemetry or dashboard — this issue is static/CI-time enforcement
    only, not a live measurement system (consistent with rejecting standing-ceremony
    measurement loops for a solo-operated toolset).
  - Retrofitting every existing prompt-assembly site across the whole plugin fleet — only the
    three sites named in `T4-F4-5` (cross-segment handoff, reviewer re-engagement, chaperone
    dispatch) are switched to the shared primitive in v1. A fourth or future reuse site adopting
    it is a fast-follow, not blocked by this issue, but also not delivered by it.
  - Changing `segment_units()`'s segmentation logic or the resident-worker scheduling protocol
    itself (`worker-cache-scheduling`, `docs/engineering-journal/DECISIONS.md:1950`) — this issue
    only guards and enforces prefix stability around the existing protocol, it does not redesign
    it.
  - Auto-fixing every lint finding — R3 auto-relocates only mechanically-safe cases; ambiguous
    findings are reported, not silently rewritten.
  - Any change to the `inline` execution backend — none of the three facets touch it; the
    resident-worker/cache-reuse protocol this issue guards applies to `team-execution`
    (and, for `segment_units`, the saga execution spec), not the inline backend.

## Definition of Done

- `tools/` gains a new volatile-token lint script wired into CI (matching the `check_docs.py`
  precedent), scanning `plugins/*/skills/**` and context-assembly modules.
- `context_package.py` (stable/volatile partition, stable-first serialize) exists and is adopted
  by all three named call sites: cross-segment summary handoff, reviewer delta re-engagement, and
  chaperone dispatch — replacing their current hand-concatenation.
- `tests/test_cache_prefix_stability.py` exists with a committed golden snapshot of resident
  prefix bytes for a fixture `ExecutionSpec`, plus a CONTRIBUTING note on the intentional-change
  bump process.
- All new tests pass on `HEAD`; the lint's own red/green self-check (seeded finding fails,
  relocated fixture passes) is demonstrated in CI or a local run; the regression test's own
  red/green self-check (perturbed fixture fails) is demonstrated the same way.
- Full repo test/lint/type suite stays green with the new lint and tests included.

## Grounding References

- `T4-F1-4` (primary) — silent-invalidator lint. Basis: external — Anthropic prompt-caching
  silent-invalidator audit table (this repo's `claude-api` skill, `shared/prompt-caching.md`:
  `datetime.now()`/UUID/unsorted `json.dumps`/per-request IDs early in the prefix each break
  caching; "if `cache_read_input_tokens` is zero across identical-prefix requests, a silent
  invalidator is at work"). Lint shape mirrors `check_docs.py`
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`).
- `T4-F4-5` (facet) — stable-first context-package primitive. Basis: reasoned, from
  first-principles prompt-cache mechanics (longest byte-identical prefix keys the hit). Grounded
  at the three real call sites: `plugins/team-execution/skills/team-execution/SKILL.md:305`,
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:207`,
  `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (context
  package table).
- `T4-F6-8` (facet) — CI byte-stability regression guard. Basis: reasoned — prompt caching is
  prefix-exact, so cache economics have no protecting signal unless prefix bytes are explicitly
  pinned. Grounded at `plugins/saga/scripts/execution_spec.py:1384` (`segment_units`) and
  `plugins/*/agents/*.md` as the prefix-determining inputs that change routinely with no
  cache-awareness (grounding brief, section 1).
- Binding decision this builds on: `worker-cache-scheduling`
  (`docs/engineering-journal/DECISIONS.md:1950`) — the resident-worker cache-reuse protocol
  (derive segment/agent/tier saga-side, reside team-side; segment boundary = plugin directory)
  that all three facets protect the economics of, without changing.
- Consolidation rationale (issue map): the lint, the shared assembler, and the regression guard
  are one merged theme-T4 change set because they jointly convert cache-prefix stability from an
  unverified assumption into an engineered, CI-enforced, regression-guarded property — none of
  the three is sufficient alone.

## Recommended Executor Profile

- **Model:** Sonnet.
- **Effort:** Medium.
- **Backend:** Inline.
- **External LLM posture:** None.
- **Justification:** This is well-scoped mechanical engineering work (a lint script, a
  refactor to route three existing call sites through one new assembler module, and a golden
  snapshot test) with clear, testable acceptance criteria and no architectural ambiguity — it does
  not require Opus-level judgment or an external-engine chaperone dispatch. Sonnet at medium
  effort, run inline, matches the shape.

## Release-Surface Checklist

This issue changes plugin behavior (`team-execution`'s prompt-assembly call sites) and adds new
CI-enforced tooling, so the release surface must be updated in the same PR:

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
  `context_package.py` script and the changed assembly behavior at the three call sites.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for `team-execution` if its
  plugin version changes.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry documenting the new stable-first assembler
  and its adoption at the three call sites.
- [ ] Any version/metadata drift-guard tests (e.g. `tools/gate-manifest.json`-driven checks,
  marketplace/plugin.json consistency tests) — verified green with the new script and version
  bump in place.
- [ ] If the new `tools/` lint or `tests/test_cache_prefix_stability.py` needs to be referenced
  from repo-level CI config (e.g. `.github/workflows/*.yml` or `validate.yml`-equivalent), that
  wiring is included in this PR, not deferred.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `tools/cache_prefix_lint.py` — new volatile-token-before-stable-prose lint (proposed path).
- `plugins/team-execution/skills/team-execution/scripts/context_package.py` — new stable-first
  assembly primitive (proposed path).
- `plugins/team-execution/skills/team-execution/SKILL.md` — cross-segment summary-handoff call
  site switched to the new assembler.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — reviewer
  delta re-engagement call site switched to the new assembler; ordering contract documented here.
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` —
  chaperone dispatch context-package call site switched to the new assembler.
- `tests/test_cache_prefix_stability.py` — new golden-snapshot regression test (repo-root
  collected).
- `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates.
- `CONTRIBUTING.md` (or repo-equivalent) — intentional prefix-bump note.

### Tests to add or update
- Lint: fails on a seeded volatile-token-before-stable-prose fixture; passes once the fixture is
  relocated (or after the lint's own auto-relocation).
- Assembler: unit test asserting two calls differing only in the volatile block produce a
  byte-identical stable prefix.
- Regression guard: `tests/test_cache_prefix_stability.py` passes on `HEAD` against the committed
  golden snapshot; fails when a fixture prompt prefix is perturbed.
- Release-surface drift-guard tests (existing repo tooling) stay green with the version bump in
  place.

### Acceptance criteria
- [ ] A seeded volatile-token-before-stable-prose fixture fails the new lint; a version with the
  token relocated after the stable block passes. Check: run the lint against both fixtures locally
  or in CI → seeded fixture exits non-zero, relocated fixture exits `0`.
- [ ] `context_package.py` is adopted by all three named call sites (cross-segment handoff,
  reviewer re-engagement, chaperone dispatch) in place of their prior hand-concatenation. Check:
  `grep -rn "context_package" plugins/team-execution/skills/team-execution/SKILL.md
  plugins/team-execution/skills/team-execution/references/consensus-protocol.md
  plugins/team-execution/skills/team-execution/references/external-engine-workers.md` → each file
  references the shared assembler.
- [ ] Two assembler calls differing only in the volatile block produce a byte-identical stable
  prefix. Check: `uv run pytest tests/ -k context_package_stable_prefix` → passes.
- [ ] `tests/test_cache_prefix_stability.py` passes on `HEAD` against the committed golden
  snapshot. Check: `uv run pytest tests/test_cache_prefix_stability.py -k golden_snapshot_head` →
  passes.
- [ ] `tests/test_cache_prefix_stability.py` fails when a fixture prompt prefix is perturbed.
  Check: `uv run pytest tests/test_cache_prefix_stability.py -k golden_snapshot_perturbed` → fails
  as expected (asserted via a wrapper that expects the failure, or documented as a manual
  before/after run in the PR description).
- [ ] A CONTRIBUTING note documents the intentional prefix-bump process. Check:
  `grep -n "cache.prefix" CONTRIBUTING.md` (or repo-equivalent doc) → present.
- [ ] Release-surface artifacts updated in the same PR: `plugins/team-execution/.claude-plugin/plugin.json`
  version bump, `.claude-plugin/marketplace.json` sync, `plugins/team-execution/CHANGELOG.md`
  entry. Check: `git diff --stat` for the PR includes all three paths.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# New lint's own red/green self-check (fixture paths TBD by /plan)
python3 tools/cache_prefix_lint.py --self-test

# Assembler + regression guard unit tests
uv run pytest tests/test_cache_prefix_stability.py -v
uv run pytest tests/ -k context_package -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the lint's self-test reports the seeded finding caught and the relocated
fixture clean; the regression guard passes on `HEAD` and is demonstrated (in the PR) to fail on a
perturbed fixture.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json (ids `T4-F1-4`,
  `T4-F4-5`, `T4-F6-8`)
- Source type: ideation survivor set
- Source title: Plugin-fleet ideation 2026-07-03 — theme T4 (cache-aware prompt architecture)

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/359
- Number: 359
- Created at: 2026-07-04T07:49:09.499606+00:00

