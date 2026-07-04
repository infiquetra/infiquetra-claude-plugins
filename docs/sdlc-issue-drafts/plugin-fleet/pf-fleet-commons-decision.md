---
title: "exploration: name the import mechanism — where cross-plugin shared primitives live and how a plugin gets them"
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
slug: pf-fleet-commons-decision
---

# exploration: name the import mechanism — where cross-plugin shared primitives live and how a plugin gets them

### Objective
Establish single-source-of-truth for shared primitives.

### Intent
Decide and build the fleet-commons distribution mechanism: the concrete answer to "where does a
shared primitive that more than one plugin needs actually live, and how does a sibling plugin resolve
it at install time." Produce a `DECISIONS.md` entry naming the chosen mechanism (with the rejected
alternative recorded and a revisit-when condition) and ship the first real PR proving it: a resolution
shim plus one already-proposed shared primitive imported through it from two different plugins,
verified by an install-time integration test that proves resolution works outside the repo checkout
(i.e. the way a marketplace-installed plugin actually runs, not just inside this monorepo's working
tree).

This is an exploration-with-a-build-artifact, not a pure research memo: the `dod_sketch` for the
absorbed idea explicitly requires a merged decision doc *and* a working resolution shim *and* a real
imported consumer, not a recommendation alone.

## Problem / Motivation
The fleet is 8 independently versioned, independently installed marketplace plugins — saga 0.51.0,
team-execution 2.9.0, mission-control 2.4.0, agy 0.1.0, deploy 0.1.2, home-lab-ops 1.2.0,
redis-channel 0.5.0, unifi 1.1.0
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`). Each plugin's scripts live under its
own `skills/` tree; there is no shared Python package path and no marketplace-installed cross-plugin
import mechanism today. A plugin cannot `import` another plugin's code the way it could inside this
monorepo's own test suite, because the marketplace installs each plugin in isolation.

At least 28 pool ideas from the 2026-07-03 plugin-fleet ideation quietly assume this problem is already
solved. They each propose "a shared primitive every plugin/fan-out site imports" — among them the tier
palette (`T3-F4-1`), the concurrency resolver (`T13-F4-1`), the consensus kernel (`T5-F6-1`), the
liveness engine (`T6-F4-3`), the reclaim primitive (`T6-F4-1`), the delegation receipt (`T15-F4-1`),
and the posture primitive (`T4-F4-1`) — without naming where the shared code physically resides or how
a consuming plugin gets it (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`, id
`G-negative-space-3`, `idea` field). One companion idea, `H-F6-8`, circles the question at the contract
level ("the marketplace is the contract bus") but stops at the schema/version boundary — it never
answers the code-import question.

Left unresolved, every one of those 28 survivors will independently reinvent an answer (most likely:
hand-copy the primitive into each consuming plugin's own tree), which is exactly the contract-mirror
failure mode this same ideation batch is elsewhere trying to cure — see the sibling issue
`pf-abolish-contract-mirrors`, grounded in a real incident where a hand-copied validator drifted silently
across 343 "clean" cards before a live contract change caught it
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 finding 1, incident `#222`). The grounding
brief independently names this as a recurring-pain theme: "release-surface drift persists despite
CLAUDE.md step 6" and "derive-on-read over committed state" are both symptoms of the fleet not having a
settled single-source-of-truth convention for anything shared
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99-109`).

This decision also intersects the fleet's active anti-sprawl posture directly: a new "fleet-core"
plugin is itself a new plugin, and "new plugin" ideas in this fleet carry a consolidation burden of
proof under the binding decision `{#plugin-portfolio-groom-17-to-7}`
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`). The chosen mechanism must engage that
decision explicitly rather than sidestep it — a fleet-commons home is only defensible if it *deletes*
future hand-copies rather than adding a ninth surface to maintain.

## Definition of Done
Merged, in one PR:
1. A `docs/engineering-journal/DECISIONS.md` entry that names the chosen distribution mechanism (see
   candidate list in Acceptance Criteria), records the rejected alternative(s) with why they were
   rejected, and states an explicit revisit-when condition.
2. A working resolution shim implementing the chosen mechanism.
3. One already-proposed shared primitive (e.g. the tier palette, `T3-F4-1`, or the concurrency
   resolver, `T13-F4-1` — whichever is cheapest to extract as a first mover) migrated to live in the
   commons location and imported through the shim from two different existing plugins.
4. An install-time integration test that proves cross-plugin resolution works from outside this
   repo's working tree — i.e. it does not merely pass because pytest's `sys.path` happens to include
   the monorepo root; it exercises the same resolution path a marketplace-installed plugin would use.
5. Every one of the 28 "shared primitive" pool ideas identified during ideation is annotated (in the
   issue tracker or a follow-up note) with the mechanism it must now build against, so future issues
   stop independently re-deciding this question.

### Verification
```bash
# The new resolution shim and its unit tests
uv run pytest tests/test_fleet_commons_resolution.py -v

# Install-time integration test: prove resolution works outside the repo checkout
# (e.g. via a throwaway venv/tmp install root that does not have this repo's
# working-tree paths on sys.path)
uv run pytest tests/test_fleet_commons_install_time.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

# DECISIONS.md entry present and well-formed
grep -n "fleet-commons" docs/engineering-journal/DECISIONS.md
```
Expected: all green; the install-time test fails if run against a checkout where only the repo-root
`sys.path` trick is available, and passes against the shim's real resolution path.

### Acceptance criteria
- [ ] **AC1 (every candidate mechanism has a stated failure mode).** The `DECISIONS.md` entry
  evaluates at least the candidates already surfaced during ideation — (a) a `fleet-core` plugin whose
  `scripts/` is the canonical home, resolved by sibling plugins via marketplace-installed path
  discovery plus a vendored-fallback shim, and (b) a real Python package published from this repo that
  CLI plugins declare as a dependency — and states, in prose, the concrete way each candidate can fail
  (e.g. "vendored-fallback shim silently drifts from its source the same way `validate_card_body` did"
  or "a published package adds a release/versioning surface the fleet does not currently have
  tooling for"). Check: `grep -A5 "### Rejected" docs/engineering-journal/DECISIONS.md` (or equivalent
  entry heading) shows a named failure mode per rejected candidate.
- [ ] **AC2 (recommendation names its revisit-when condition).** The chosen mechanism's entry states an
  explicit, checkable revisit-when condition (not "if it doesn't work out"). Check: the `DECISIONS.md`
  entry contains a line beginning `Revisit when:` naming a concrete trigger.
- [ ] **AC3 (resolution shim exists and resolves a real primitive from two plugins).** At least one
  primitive already proposed as fleet-shared (tier palette or concurrency resolver) is relocated to the
  commons location and imported through the new shim from two distinct existing plugins (not two call
  sites in the same plugin). Check: `grep -rl "fleet_commons\|fleet-core" plugins/*/skills plugins/*/scripts`
  (or the shim's actual import name) shows hits in at least two different `plugins/<name>/` directories.
- [ ] **AC4 (install-time integration test proves it works outside the checkout).** A test exercises
  the resolution path the way a marketplace-installed plugin would encounter it — not via the
  monorepo's own `sys.path`/`pytest.ini` conveniences. Check:
  `uv run pytest tests/test_fleet_commons_install_time.py -v` passes, and inspection of the test shows
  it constructs or simulates an install root distinct from the repo's working-tree layout.
- [ ] **AC5 (pending single-source-of-truth issues annotated with the chosen mechanism).** The 28
  pool ideas identified during ideation as depending on this decision (tier palette `T3-F4-1`,
  concurrency resolver `T13-F4-1`, consensus kernel `T5-F6-1`, liveness engine `T6-F4-3`, reclaim
  primitive `T6-F4-1`, delegation receipt `T15-F4-1`, posture primitive `T4-F4-1`, and the remaining 21)
  are annotated with the chosen mechanism, either as a tracked follow-up note in
  `docs/engineering-journal/QUEUED.md` or as a comment/label update on each corresponding issue once
  filed. Check: a single artifact (e.g. `docs/engineering-journal/QUEUED.md` or a tracking table in the
  `DECISIONS.md` entry itself) lists all 28 by id with the mechanism name against each.
- [ ] **AC6 (engages the anti-sprawl binding decision, doesn't dodge it).** If the chosen mechanism is
  a new `fleet-core` plugin, the `DECISIONS.md` entry explicitly engages
  `{#plugin-portfolio-groom-17-to-7}` and states the consolidation argument (a shared home deletes
  future hand-copies rather than adding a ninth uncoordinated surface). Check: the entry's text
  contains the anchor `{#plugin-portfolio-groom-17-to-7}` and a sentence framing the new surface as
  consolidation, not sprawl.
- [ ] **AC7 (grounded, not extrapolated).** Every claim in the `DECISIONS.md` entry about current fleet
  layout or lack of an import path cites the specific file or grounding-brief line it is verified
  against (e.g. `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12` for the 8-plugin map);
  no "likely"/"probably" language about how the marketplace installs plugins today. Check: manual
  review of the entry finds a citation attached to each verifiable claim.
- [ ] **AC8 (full suite, format, lint, and types stay green).** Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Out-of-scope / non-goals
**In scope:** deciding and documenting the distribution mechanism; building the resolution shim;
migrating exactly one primitive as the proof case; the install-time integration test; annotating the
28 dependent pool ideas with the chosen mechanism.

**Non-goals (explicitly out of scope for this issue):**
- Migrating all 28 dependent primitives onto the new mechanism — this issue proves the mechanism with
  one primitive; the remaining 27 are follow-up issues that build *against* the now-settled decision,
  not part of this issue's build surface.
- Standing up a full package-publishing/release pipeline if the Python-package mechanism is chosen —
  if selected, this issue ships the minimum viable dependency declaration and resolution; a full
  publishing pipeline (PyPI, private index, versioned release cadence) is a distinct follow-up.
- Redesigning the marketplace's contract/schema-versioning story (`H-F6-8`'s "marketplace is the
  contract bus" framing) — that is a schema/versioning question distinct from this issue's code-import
  question; do not conflate the two in the same PR.
- Touching `plugins/mission-control/scripts/sdlc_manager.py`'s hand-copied validator or any other
  concrete contract-mirror instance — that is the separate, already-scoped `pf-abolish-contract-mirrors`
  issue; this issue only settles the mechanism those migrations will use.
- Any change to the fleet's model/effort dispatch vocabulary or tier tables — unrelated surface.

### Grounding References
- **Absorbed idea** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`, id
  `G-negative-space-3`, role: primary) — "Name the import mechanism: where cross-plugin shared
  primitives actually live and how a plugin gets them." `basis_type: reasoned`, `verdict: survive`,
  `tier_tag: structural`. Basis (verbatim from the survivor file): "First-principles: grounding brief
  §1 lists 8 independently versioned plugins; the marketplace installs each in isolation, so 'X.py
  every plugin imports' has no resolvable import path today — verified by the repo layout (each
  plugin's scripts live under its own skills/ tree, tests import via repo-root paths that do not exist
  at install time). 28 pool ideas (jq census on 'shared primitive'/'imports') depend on this unnamed
  mechanism; if unresolved, each ships as a hand-copy, which the 4-repo contract-mirror-drift evidence
  (grounding §3 finding 1) shows will drift. Engages `{#plugin-portfolio-groom-17-to-7}`: a fleet-core
  home is consolidation, not sprawl — it deletes future copies rather than adding a surface."
  `dod_sketch` (verbatim): "Merged: DECISIONS.md distribution-mechanism entry (rejected alt recorded) +
  resolution shim + one primitive imported through it from two plugins; verified by an install-time
  integration test proving cross-plugin resolution works outside the repo checkout."
- **Consolidation rationale** (issue-map, verbatim): "At least 28 pool ideas presuppose a
  shared-primitive home that does not exist; this decision doc must settle the mechanism before the
  single-source issues multiply ad-hoc answers."
- **Binding decisions this issue builds on and must not violate**
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2):
  - `{#plugin-portfolio-groom-17-to-7}` — "Plugin sprawl is an active concern — 'new plugin' ideas
    carry a consolidation burden of proof." A `fleet-core` mechanism choice must engage this directly
    (see AC6), framing itself as consolidation.
  - `{#worker-cache-scheduling}` — settled architecture ties primitive residency to "segment boundary =
    plugin directory"; the chosen commons mechanism must not contradict that boundary definition without
    engaging its own revisit-when.
- **Consumer-side evidence** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 finding 1):
  the 343-clean-cards contract-mirror incident (`#222`) is the load-bearing proof that unresolved
  shared-primitive questions decay into silent hand-copy drift — the same failure this issue's decision
  is meant to prevent for the 28 pending primitives.
- **Fleet map** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`): 8 plugins, each
  independently versioned and independently installed — the structural fact that makes "shared
  primitive" currently unresolvable without this decision.

### Recommended Executor Profile
- **Model:** opus
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** second-opinion (advisory only; Claude remains verifier-of-record per
  `{#external-engines-never-gatekeepers}` (#283) — an external engine may propose a candidate mechanism
  or critique the chosen one, but does not gate the decision).
- **Justification (required — profile is above sonnet):** this is an architectural decision that
  shapes at least 28 downstream issues across the fleet; getting the mechanism wrong is expensive to
  reverse once several plugins have imported through it. The decision is judgment-shaped (weighing
  packaging complexity, marketplace-install constraints, and the fleet's stated anti-sprawl posture
  against each other) rather than mechanical scaffolding, and benefits from a second opinion that Claude
  reconciles rather than defers to.

### Release-Surface Checklist
This issue changes plugin behavior — it introduces a new cross-plugin resolution path and migrates a
shared primitive's canonical location — so update in the same PR:
- [ ] `plugins/<chosen-commons-home>/.claude-plugin/plugin.json` — new plugin manifest (if the
  `fleet-core` mechanism is chosen) or version bump on the two existing plugins now consuming the
  shim.
- [ ] `.claude-plugin/marketplace.json` — entry added (new plugin) or version fields synced (existing
  plugins), matching whichever `plugin.json` changes are made.
- [ ] `plugins/<affected-plugin>/CHANGELOG.md` — entry on every plugin whose primitive location or
  import path changed, documenting the migration.
- [ ] Any existing version/metadata drift-guard tests (e.g. plugin.json vs marketplace.json parity
  tests) updated and passing against the new/bumped versions.
- [ ] `docs/engineering-journal/DECISIONS.md` — the distribution-mechanism entry itself (this is the
  primary deliverable, not just a release-surface formality).

### Files Expected to Change
Indicative only — the exact set is `/plan`'s to determine.
- `docs/engineering-journal/DECISIONS.md` — new distribution-mechanism entry.
- `docs/engineering-journal/QUEUED.md` — tracking table annotating the 28 dependent pool ideas with
  the chosen mechanism.
- New commons location (path TBD by the decision — e.g. `plugins/fleet-core/scripts/` or a new
  top-level Python package) — the resolution shim and the one migrated primitive.
- Two existing consuming plugins (e.g. `plugins/saga/` and one other) — updated imports through the
  new shim.
- `tests/test_fleet_commons_resolution.py` (new) — shim unit tests.
- `tests/test_fleet_commons_install_time.py` (new) — install-time integration test.
- Release-surface files per the checklist above.

### Tests to Add or Update
- Resolution shim: resolves the migrated primitive correctly when invoked from each of the two
  consuming plugins; fails loud (not silently) when the commons location is missing or malformed.
- Install-time integration: constructs or simulates an install root distinct from this repo's
  working-tree layout and proves resolution still succeeds — the test must fail if only the
  monorepo's own `sys.path` convenience is exercised.
- Drift-guard: plugin.json/marketplace.json version parity tests updated to reflect the new/bumped
  plugin(s), all passing.

### Context library links
- _none_

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan once the mechanism candidates above are reviewed.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`, slug
  `pf-fleet-commons-decision`, absorbing `G-negative-space-3` (primary)
- Source type: ideation survivor (issue-map)
- Source title: Name the import mechanism — where cross-plugin shared primitives live and how a
  plugin gets them

### Files expected to change

- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/engineering-journal/DECISIONS.md`
- `docs/engineering-journal/QUEUED.md`
- `plugins/mission-control/scripts/sdlc_manager.py`
- `.claude-plugin/marketplace.json`
- `tests/test_fleet_commons_resolution.py`
- `tests/test_fleet_commons_install_time.py`

### Tests to add or update

- `tests/test_fleet_commons_install_time.py`
- `tests/test_fleet_commons_resolution.py`

### Inputs inventory

- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/engineering-journal/DECISIONS.md`
- `docs/engineering-journal/QUEUED.md`
- `plugins/mission-control/scripts/sdlc_manager.py`
- `.claude-plugin/marketplace.json`
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
