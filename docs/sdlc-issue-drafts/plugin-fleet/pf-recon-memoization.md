---
title: "capability: kill the 400k-token recon fan-out — shared context pack, tree-hash memoization with $0 local fill, and a CI-maintained fact index"
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
objective: "Make cache economics an engineered, measured win"
slug: pf-recon-memoization
---

# capability: kill the 400k-token recon fan-out — shared context pack, tree-hash memoization with $0 local fill, and a CI-maintained fact index

### Objective
Make cache economics an engineered, measured win.

### Intent
Read-only recon fan-outs are the single largest measured token spend in this repo's cache
economics, and today the fleet re-derives them from scratch, in full, every single time. This
issue merges four absorbed ideation facets from theme T4 (cache-aware prompt architecture) into
one structural change set that attacks the same 350–450k-token pattern from three complementary
angles — redundancy, frequency, and demand — rather than shipping them as four separate issues:

1. **Shared recon-context-pack builder** (`T4-F2-7`, primary) — collapse N fan-out workers' N
   independent cold reads of the same repo survey into one pre-assembled shared prefix, so the
   fleet pays one cache-creation and N-1 cache-reads instead of N creations.
2. **Tree-hash-keyed recon memoization** (`H-F6-7`, facet) — commit survey outputs as artifacts
   keyed by the git tree hash of their input paths, so an unchanged tree returns the stored
   artifact instead of re-mining it, while any input change forces a correct miss.
3. **$0 local-model cache-miss filling** (`G-hybrids-9`, facet) — route a tree-hash miss to the
   $0 local-offload lane (read-only, mechanical summarization) instead of Claude, with Claude
   consuming only the distilled, receipt-bearing pack.
4. **CI-maintained repo fact index** (`H-F2-4`, facet) — a post-merge CI job regenerates a
   structured fact index as a committed artifact, so recon steps read the index first and fan
   out agents only for the residual questions the index cannot answer.

These four compound rather than duplicate: the fact index eliminates demand for recon that never
needed to run at all; tree-hash memoization bounds how often the residual recon runs; the shared
context pack bounds what each run of it costs per worker; and the $0 local-fill lane bounds what
a genuine miss costs before Claude ever sees it. Shipping them separately would leave the shared
pack with nothing memoizing repeat runs, the memoization layer with nothing making individual
runs cheap, and the fact index with no fallback path for the (residual) fan-outs it cannot
eliminate.

## Problem Frame

The grounding brief's session-mining synthesis names this as a singleton finding: **"350–450k
tokens in <20 min for read-only recon fan-outs (cache-economics number)"**
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:127`, section 7). That number is pure
re-derivation of facts that are deterministic functions of the repo tree at a given commit —
plugin inventory, agent-frontmatter maps, spawn-site enumerations, journal/seam files — recomputed
from scratch, cold, every session, by every fan-out worker independently.

- **No shared prefix exists across recon fan-out workers.** N read-only recon workers each cold-read
  a near-identical prefix (inventory, journal, seam files). Each spawn triggers its own full
  `cache_creation` of that prefix instead of one shared creation followed by N-1 `cache_read`s —
  a linear-to-constant reduction available under the existing 5-minute prompt-cache TTL that
  nothing in the fan-out dispatch path currently claims (`T4-F2-7` basis, reasoned from
  first-principles prompt-cache mechanics against the section-7 singleton).
- **Nothing memoizes recon output across sessions.** Survey outputs (plugin inventory,
  agent-frontmatter maps, spawn-site enumerations) are recomputed every session even when the
  underlying tree has not changed since the last recon. This is squarely the recurring-pain theme
  named in section 6, item 5 of the grounding brief: **"Derive-on-read over committed state —
  recurring rejected alternative"** — but the rejected alternative's staleness rationale does not
  apply here, because a tree-hash key makes staleness structurally impossible: any input change
  changes the key and forces a miss (`H-F6-7` basis, direct from grounding brief section 6 item 5
  plus the section 7 singleton). This is orthogonal to the settled
  `{#worker-cache-scheduling}` decision (`docs/engineering-journal/DECISIONS.md:1950`), which
  governs *prompt-cache residency inside a live worker*; this facet is artifact-level reuse
  *across* sessions where no worker survives.
- **Even a genuine cache miss pays full Claude-token price today.** Nothing routes a tree-hash
  miss to a cheaper engine even though read-only, mechanical repo summarization is exactly the
  WEAK-capability-tolerant work shape this repo already earmarks for local-model offload (intake
  section 5: "Ollama -> $0 offload target"). `G-hybrids-9`'s parents (`H-F6-7`, `T2-F6-4`,
  `T4-F2-7`) attack cost frequency, unit price, and redundancy separately; without the local-fill
  facet, a cold miss on this repo's fact surface still costs full Claude-token price with no
  cheaper lane available.
- **No demand-elimination layer exists ahead of any of this.** The org's own convention —
  "schema-validate-in-CI + self-describing index, not runtime-injected blobs" (grounding brief
  section 4, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77`) — has no analogue for
  code-repo facts. A post-merge CI job that regenerates a structured fact index (plugin
  inventory, agent-frontmatter matrix, script entry points, registry/vocabulary tuples, test map)
  would let recon-class steps in saga read a file before ever considering a fan-out
  (`H-F2-4` basis, direct from the section 7 singleton plus section 4).

This is the repo's single highest-leverage, directly-measured cache-economics number, and today
nothing in the recon/ideation fan-out dispatch path attacks redundancy, frequency, unit price, or
demand for it.

## Key Decisions

These framing choices carry forward from the ideation survivors and constrain scope below.

- **Demand elimination, scheduling, and memoization are three distinct, composable layers — not
  competing designs.** The CI fact index (`H-F2-4`) removes recon demand upstream of any
  scheduling question; the shared context pack (`T4-F2-7`) changes only the per-worker cost of a
  fan-out that is still decided to run; tree-hash memoization (`H-F6-7`) governs whether a run
  happens again at all. None contradicts the settled `{#worker-cache-scheduling}` architecture
  (derive segment/agent/tier saga-side, reside team-side) — that decision's revisit-when (residency
  insufficient / idle-poll cost) is untouched because all four facets here operate upstream of or
  orthogonal to worker residency, not inside it.
- **The fan-out spend decision itself is out of scope.** Under the repo's attended-run posture,
  choosing to spin a recon fan-out at all stays a spend-increasing choice requiring explicit
  operator yes (per `T4-F2-7`'s own framing). This issue changes what a chosen fan-out costs and
  how often it must run, not whether or when the fan-out decision fires.
- **Content-addressed keying, not committed status.** The memoization layer is keyed by a
  sorted-path tree hash so staleness is structurally impossible (any input change forces a miss),
  which is why it does not re-open the `derive-on-read` rejection — that rejection concerns
  operator-writable/committed *status* fields that can silently drift, not content-addressed,
  input-derived cache keys.
- **Local-fill respects the external-engine trust boundary.** The $0 local-model miss-filling
  lane (`G-hybrids-9`) is advisory, read-only summarization consumed only by Claude — it never
  holds a gated verdict and never touches `{#external-engines-never-gatekeepers}`
  (`docs/engineering-journal/DECISIONS.md`, #283). A local-engine dispatch on miss must carry a
  receipt (what ran, on what input, what engine) so a miss-fill is distinguishable from a
  fabricated or silently-skipped one — consistent with this repo's recurring pain theme of
  silent no-ops in delegation (grounding brief section 6, item 1).
- **Four facets ship together because they are jointly, not individually, sufficient.** Per the
  issue map's consolidation: the shared context pack with nothing memoizing repeat runs still
  re-pays its shared-creation cost every session; the memoization layer with nothing making a
  genuine miss cheap still pays full Claude price on every tree change; and the fact index
  reduces but does not eliminate all recon (residual questions the index cannot answer still fan
  out, and now the fan-out that does run benefits from the shared pack, memoization, and
  local-fill facets underneath it).

## Requirements

**Shared recon-context-pack builder (T4-F2-7, primary)**

R1. A shared recon-context-pack builder pre-assembles the common repo-survey content (inventory,
journal, seam files) once per dispatch, so every recon/ideation fan-out worker receives an
identical stable prefix instead of independently cold-reading the same content.

R2. The recon/ideation fan-out dispatch path (saga workflow-emitter and/or team-execution
dispatch, per `/plan`'s determination) is wired to hand every worker this shared pack rather than
each worker separately reading the source files.

R3. A ledger-instrumented before/after run on a real recon fan-out shows a single
`cache_creation` for the shared-pack block and `N-1` `cache_read`s across the N workers, where
today's baseline shows N independent `cache_creation`s.

**Tree-hash-keyed recon memoization (H-F6-7, facet)**

R4. A recon-cache helper computes a cache key from the sorted-path tree hash of a survey's
declared input paths plus a survey id, and checks a committed artifact store for a key match
before dispatching any fan-out.

R5. On a key match (cache hit), the helper returns the stored artifact without dispatching any
new recon work.

R6. On no key match (cache miss), the helper dispatches the recon fan-out (through the shared
context pack from R1–R2 where applicable) and commits the resulting artifact under the new key.

R7. One high-traffic survey (the agent-frontmatter/model inventory, per the survivor's proving
case) is converted to run through this cache-check helper as the first adopter.

R8. A repeat-run test on an identical tree hash shows zero re-mining (the cached artifact is
returned, no fan-out dispatched); the same test with any input path changed shows a cache miss
(fan-out dispatched, new artifact committed under the new key).

**$0 local-model cache-miss filling (G-hybrids-9, facet)**

R9. On a tree-hash cache miss (R6), the recon-cache helper offers a route to a $0 local-model
offload lane for read-only, mechanical repo summarization, rather than defaulting Claude-token
spend on every miss.

R10. Every local-engine dispatch on miss carries a receipt (engine identity, input tree hash,
what ran) attached to the committed artifact, so a miss-fill is distinguishable from a
fabricated, stubbed, or silently-skipped one.

R11. The local-fill output is advisory only: Claude consumes the distilled artifact but no gated
decision (merge, deploy, or verdict) is satisfied by raw local-engine output without a
subsequent Claude-side check, consistent with `{#external-engines-never-gatekeepers}`.

R12. Where the local-offload registry row this facet depends on (`T2-F6-4`) is not yet merged at
implementation time, the local-fill route is stubbed behind the same receipt-bearing interface
(so R10's receipt contract is exercised and testable against a fake/mock local engine) rather
than blocking this issue on that dependency landing first.

**CI-maintained repo fact index (H-F2-4, facet)**

R13. A new `scripts/generate_fact_index.py` produces a structured fact index (plugin inventory,
agent-frontmatter matrix, script entry points, registry/vocabulary tuples, test map) as a
committed artifact under `docs/fact-index/`.

R14. A post-merge CI job runs `generate_fact_index.py` and commits the regenerated
`docs/fact-index/` artifact on merge, following the org's existing
"schema-validate-in-CI + self-describing index" convention (grounding brief section 4).

R15. Recon-class steps in saga (at minimum the recon/scan step guidance referenced by `/plan`,
`/investigate`, or equivalent) are instructed to read `docs/fact-index/` first and fan out agents
only for questions the index cannot answer.

R16. A before/after token measurement on one real recon task is recorded in
`docs/engineering-journal/LEARNINGS.md`, showing the reduction from a full fan-out to an
index-read-plus-targeted-miss shape.

## Key Flows

F1. **Fact-index-first recon.** Trigger: a saga recon/scan step needs repo facts. The step reads
`docs/fact-index/` first (R15); if the index answers the question, no fan-out is dispatched.
Covers R13–R16.

F2. **Residual fan-out, cache-checked.** Trigger: the fact index cannot answer the question, or
the recon step is not yet index-aware. The recon-cache helper computes the tree-hash key (R4); on
a hit, the stored artifact is returned with zero new dispatch (R5, R8); on a miss, the fan-out
runs through the shared context pack (R1–R2, R6) and either Claude or the $0 local-fill lane
performs the miss-fill (R9–R12), with the result committed under the new key. Covers R1–R12.

F3. **Repeat run, identical tree.** Trigger: the same recon question is asked again with no
intervening tree changes. The tree-hash key matches; the cached artifact is returned; zero
re-mining occurs. Covers R8.

### Out-of-scope / non-goals
- **In scope:** the shared recon-context-pack builder and its wiring into the recon/ideation
  fan-out dispatch path; the tree-hash-keyed recon-cache helper and one converted proving-case
  survey; the receipt-bearing local-fill route on cache miss (stubbed against a fake local engine
  if `T2-F6-4` has not yet landed); `generate_fact_index.py`, its post-merge CI job, and the
  index-first instruction in the saga recon step guidance; the LEARNINGS.md before/after
  measurement.
- **Out of scope / non-goals:**
  - Deciding whether or when a recon fan-out should be spun up at all — the attended-run,
    explicit-yes posture for spend-increasing fan-out decisions is unchanged; this issue only
    changes per-worker cost, repeat-run cost, and miss cost of a fan-out that is still explicitly
    chosen.
  - Building or merging the `T2-F6-4` Ollama/local-offload registry row itself — this issue
    consumes that interface where available and stubs it otherwise (R12); building the registry
    row's own dispatch adapter is a separate issue's scope.
  - Retrofitting every survey across the fleet onto the memoization helper — v1 converts one
    high-traffic proving case (R7); a broader migration is a fast-follow, not blocked by this
    issue but also not delivered by it.
  - Changing `{#worker-cache-scheduling}`'s resident-worker scheduling protocol (segment
    derivation, residency) — this issue's shared-pack and memoization layers operate upstream of
    or alongside that protocol, not inside it.
  - Standing/scheduled cache-hit-rate telemetry or a live dashboard — R3, R8, and R16's
    measurements are one-time before/after proofs recorded in LEARNINGS.md, not a continuous
    monitoring system, consistent with this repo's rejection of standing-ceremony measurement
    loops for a solo-operated toolset.
  - Full backfill or hardening of the fact index against every possible recon question — v1
    ships the index and the index-first instruction; questions the index cannot answer correctly
    fall through to the fan-out path (F2) by design, not as a defect.

## Definition of Done

- A shared recon-context-pack builder exists and is used by the recon/ideation fan-out dispatch
  path; a ledger-instrumented before/after run shows one `cache_creation` and N-1 `cache_read`s on
  the shared block, replacing N independent `cache_creation`s.
- A tree-hash-keyed recon-cache helper exists (key = sorted-path tree hash + survey id); one
  high-traffic survey (agent-frontmatter/model inventory) is converted to use it; a repeat-run
  test shows zero re-mining on an identical tree hash and a correct miss on any input change.
- The cache-miss path offers a receipt-bearing $0 local-engine fill route (stubbed against a fake
  local engine if the `T2-F6-4` registry row is not yet available), with local-fill output
  consumed only advisorially by Claude.
- `scripts/generate_fact_index.py` exists, is wired into a post-merge CI job that commits
  `docs/fact-index/`, and the saga recon step guidance instructs an index-first read before any
  fan-out.
- A before/after token measurement on one real recon task is recorded in
  `docs/engineering-journal/LEARNINGS.md`.
- All new tests pass on `HEAD`; full repo test/lint/type suite stays green with the new scripts,
  tests, and CI wiring included.

## Grounding References

- `T4-F2-7` (primary) — shared recon-context-pack builder. Basis: reasoned, from first-principles
  prompt-cache mechanics against the section-7 singleton ("350-450k tokens in <20min recon
  fan-out": recon workers share a near-identical read-only prefix; N separate spawns each trigger
  a full `cache_creation` of that prefix, whereas one pre-assembled shared prefix under the 5-min
  TTL converts N-1 of them to `cache_read`).
- `H-F6-7` (facet) — tree-hash-keyed recon memoization. Basis: direct, from grounding brief
  section 7 singleton plus section 6 item 5 ("Derive-on-read over committed state — recurring
  rejected alternative"), whose staleness rationale is explicitly engaged and defeated via
  content-addressed keying; orthogonal to `{#worker-cache-scheduling}`
  (`docs/engineering-journal/DECISIONS.md:1950`), which governs prompt-cache residency in workers,
  not artifact-level reuse across sessions.
- `G-hybrids-9` (facet) — $0 local-model cache-miss filling, parents `H-F6-7`, `T2-F6-4`,
  `T4-F2-7`. Basis: direct, from the section 7 singleton plus intake section 5 ("Ollama -> $0
  offload target"). Respects `{#external-engines-never-gatekeepers}` (#283) — advisory-only
  summarization, no gated decision consumes raw engine output.
- `H-F2-4` (facet) — CI-maintained repo fact index. Basis: direct, from grounding brief section 7
  singleton combined with section 4 ("the org convention is schema-validate-in-CI +
  self-describing index, not runtime-injected blobs"). Demand elimination, not scheduling — does
  not contradict `{#worker-cache-scheduling}`, whose scope (how residual agent work is scheduled)
  this facet leaves untouched.
- Binding decisions this builds on: `{#worker-cache-scheduling}`
  (`docs/engineering-journal/DECISIONS.md:1950`) — the resident-worker cache-reuse protocol
  (derive segment/agent/tier saga-side, reside team-side) that all four facets here compose with
  rather than modify; `{#external-engines-never-gatekeepers}` (#283,
  `docs/engineering-journal/DECISIONS.md`) — constrains the local-fill facet to advisory-only
  output.
- Consolidation rationale (issue map): the shared context pack, tree-hash memoization, $0
  local-fill, and CI fact index are one merged theme-T4 change set because they jointly attack
  redundancy, frequency, unit price, and demand for the same measured 350–450k-token recon-fan-out
  number — none of the four is sufficient alone to make the number go away.

## Recommended Executor Profile

- **Model:** Sonnet.
- **Effort:** High. — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution.
- **External LLM posture:** offload.
- **Justification:** This is mechanical, well-scoped survey/infrastructure work (a shared
  prefix-builder, a content-addressed cache-check helper, a CI job generating a fact index, and a
  receipt-bearing dispatch stub) rather than an architectural judgment call — it composes with,
  and does not revisit, the settled `{#worker-cache-scheduling}` architecture. High effort
  reflects the four-facet surface area (dispatch-path wiring, cache-key correctness, CI wiring,
  and a stubbed external-engine interface) rather than any need for Opus-level judgment.
  Miss-filling is explicitly the $0 offload target named in this repo's intake rule, so the
  local-fill facet's implementation work is an offload candidate; the survey/glue work across the
  other three facets suits team-execution's parallelizable, mechanical work shape.

## Release-Surface Checklist

This issue changes saga's recon-step guidance and adds new committed tooling/CI surfaces, so the
release surface must be updated in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the changed recon-step
  guidance (index-first instruction) and any new recon-cache/shared-context-pack scripts added
  under `plugins/saga/scripts/`.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for `saga` (and `team-execution`
  if the shared context pack or local-fill dispatch stub lands there) if plugin versions change.
- [ ] `plugins/saga/CHANGELOG.md` (and `plugins/team-execution/CHANGELOG.md` if applicable) —
  entries documenting the shared context-pack builder, the tree-hash memoization helper, the
  local-fill miss route, and the fact-index-first recon instruction.
- [ ] Any version/metadata drift-guard tests (marketplace/plugin.json consistency tests) —
  verified green with the version bumps in place.
- [ ] New CI wiring for `generate_fact_index.py`'s post-merge job is included in this PR's
  workflow config, not deferred to a follow-up.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/recon_context_pack.py` — new shared recon-context-pack builder (proposed
  path).
- `plugins/saga/scripts/recon_cache.py` — new tree-hash-keyed recon-cache helper with receipt-bearing
  local-fill dispatch stub (proposed path).
- `scripts/generate_fact_index.py` — new CI-maintained fact-index generator (proposed path).
- `docs/fact-index/` — new committed fact-index artifact directory.
- `.github/workflows/*.yml` (or repo-equivalent) — new post-merge CI job committing
  `docs/fact-index/`.
- `plugins/saga/skills/*/references/*.md` (recon/scan step guidance, e.g. `investigate` or
  `resume` methodology references) — index-first instruction added.
- `tests/test_recon_context_pack.py`, `tests/test_recon_cache.py` — new tests (proposed paths).
- `docs/engineering-journal/LEARNINGS.md` — before/after token-measurement entry.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates.

### Tests to add or update
- Shared context pack: a ledger-instrumented (or mocked-ledger) test asserting one
  `cache_creation` and N-1 `cache_read`s across N simulated workers on the shared block.
- Recon-cache helper: repeat-run test showing zero re-mining on an identical tree hash; a
  separate test showing a cache miss when an input path changes.
- Local-fill: a test asserting a miss-fill dispatch carries the required receipt fields (engine
  identity, input tree hash, what ran) against a fake/mock local engine.
- Fact index: a test asserting `generate_fact_index.py` produces the expected structured sections
  (plugin inventory, agent-frontmatter matrix, script entry points, registry/vocabulary tuples,
  test map) for a fixture repo state.
- Release-surface drift-guard tests (existing repo tooling) stay green with the version bumps in
  place.

### Acceptance criteria
- [ ] A ledger-instrumented before/after run on a real recon fan-out shows one `cache_creation`
  and N-1 `cache_read`s on the shared block, where the baseline showed N independent
  `cache_creation`s. Check: `uv run pytest tests/test_recon_context_pack.py -k
  shared_prefix_cache_ledger` → passes.
- [ ] A repeat run on an identical tree hash shows zero re-mining. Check: `uv run pytest
  tests/test_recon_cache.py -k repeat_run_no_remining` → passes.
- [ ] Any input change to the memoized survey's declared paths produces a cache miss. Check: `uv
  run pytest tests/test_recon_cache.py -k input_change_forces_miss` → passes.
- [ ] A cache-miss fill carries a proof-of-execution receipt (engine identity, input tree hash,
  what ran). Check: `uv run pytest tests/test_recon_cache.py -k
  miss_fill_receipt_present` → passes.
- [ ] `generate_fact_index.py` produces the expected structured fact-index sections for a fixture
  repo state. Check: `uv run pytest tests/test_generate_fact_index.py -k
  fact_index_sections_present` → passes.
- [ ] A before/after token measurement on one real recon task is recorded in
  `docs/engineering-journal/LEARNINGS.md`. Check: `grep -n "recon.*token\|fact-index" 
  docs/engineering-journal/LEARNINGS.md` → entry present with before/after numbers.
- [ ] Release-surface artifacts updated in the same PR: `plugins/saga/.claude-plugin/plugin.json`
  version bump, `.claude-plugin/marketplace.json` sync, `plugins/saga/CHANGELOG.md` entry. Check:
  `git diff --stat` for the PR includes all three paths.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Shared context-pack + recon-cache unit tests
uv run pytest tests/test_recon_context_pack.py tests/test_recon_cache.py -v

# Fact-index generator test
uv run pytest tests/test_generate_fact_index.py -v

# Manual before/after ledger run on a real recon task (recorded in LEARNINGS.md)
python3 plugins/saga/scripts/recon_cache.py --measure --survey agent-frontmatter-inventory

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the recon-cache repeat-run test shows zero re-mining and the input-change
test shows a correct miss; the measured before/after run is recorded in
`docs/engineering-journal/LEARNINGS.md` with actual token numbers from that run, not estimates.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json (ids `T4-F2-7`,
  `H-F6-7`, `G-hybrids-9`, `H-F2-4`)
- Source type: ideation survivor set
- Source title: Plugin-fleet ideation 2026-07-03 — theme T4 (cache-aware prompt architecture)

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/432
- Number: 432
- Created at: 2026-07-04T08:11:58.004691+00:00

