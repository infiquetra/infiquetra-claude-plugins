---
title: "capability: machine-readable standards index — llms.json sidecar, per-topic loader, staleness hashes, fleet-local index"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Enforce context-library standards at authoring time
wave: wave-2
---

# capability: machine-readable standards index — llms.json sidecar, per-topic loader, staleness hashes, fleet-local index

### Intent

Turn the fleet's `llms.txt` standards index from prose into a consumption contract that both humans
and agents can check and load deterministically. This repository (`infiquetra-claude-plugins`) has no
standards index at all today: `find . -iname llms.txt -o -iname context_census.py` returns nothing.
The sister `infiquetra-context-library` repo already runs the pattern this issue extends —
`validate.yml` CI runs `check_docs.py` (schema/frontmatter/link lint + promotion-ledger checks) plus
`context_census.py --check`, which keeps that repo's `llms.txt` honest
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77-80`). The grounding brief states the org
convention plainly: "schema-validate-in-CI + self-describing index, not runtime-injected blobs"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:79-80`), and separately notes the consumption
shape that convention has to serve — `llms.txt` (~1-2KB) is whole-injectable, per-topic READMEs
(8-12KB) load on demand, and whole-library injection is infeasible because `platform-specs` dominates
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:84-85`). Section 4 also names what is
currently absent: "any pull of the library into `mission-control:issue` / `saga:plan` creation; any
ADR↔code-pattern lint; any reference to the library from this repo's CI"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:82-83`).

Four ideation-survivor mechanisms all converge on the same underlying gap — an index that exists only
as prose cannot be checked, cannot be loaded by topic, and cannot detect its own staleness. This issue
consolidates all four into one index-plumbing PR: (1) a fleet-local, census-checked `llms.txt` at the
`infiquetra-claude-plugins` root that maps each of the fleet's 8 plugins to authority-tiered
obligations and context-library anchors; (2) a machine-readable `llms.json` sidecar emitted by a
`context_census.py`-equivalent script (topic → byte-size → authority-rank → load-policy); (3) a
per-topic on-demand loader (`standards_resolve.py`) that maps a work context to the correct per-topic
README via the index, hosted beside existing skills rather than as a new plugin, per the fleet's
active portfolio-groom constraint (`{#plugin-portfolio-groom-17-to-7}`,
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`: "Plugin sprawl is an active concern —
'new plugin' ideas carry a consolidation burden of proof"); and (4) per-topic content hashes in the
index that let a consumer detect when a cached or quoted standard has gone stale relative to the live
topic README.

Without this, the fleet has no mechanical way to notice an unindexed plugin, an `llms.json` that has
drifted from `llms.txt`, a work context that resolves to the wrong (or no) standards doc, or a quoted
standard that has silently gone stale — exactly the class of authoring-time gap section 4 of the
grounding brief calls out as absent today.

### Requirements

R1. A fleet-local `llms.txt` (or `standards-index.md`) exists at the `infiquetra-claude-plugins` repo
root, mapping each of the fleet's 8 plugins (saga, team-execution, mission-control, agy, deploy,
home-lab-ops, redis-channel, unifi) to authority-tiered obligations and their corresponding
context-library anchors.

R2. A `context_census`-style script emits a machine-readable `llms.json` sidecar alongside `llms.txt`,
encoding per topic: byte-size, authority-rank, and load-policy (whole-inject vs. load-on-demand).

R3. The census script runs in `--check` mode and fails when `llms.json` drifts from `llms.txt` (new
topic added to one but not the other, byte-size or authority-rank mismatch, or a plugin present in the
fleet but absent from the index).

R4. `llms.json` records a per-topic content hash. A consumer-side staleness guard compares a
previously recorded hash for a topic against the topic's live content and flags a mismatch — this is
distinct from the load-policy field in R2/R3 and exists purely as a freshness guarantee.

R5. A `standards_resolve.py` script (hosted beside existing skills, not as a new plugin — see
`{#plugin-portfolio-groom-17-to-7}`) maps a work context (for example: "editing
`plugins/saga/scripts/*.py`") to the correct per-topic README path, using the `llms.txt`/`llms.json`
index plus skill references.

R6. `standards_resolve.py` fails loud (non-zero exit, named error) on an index miss — a work context
that cannot be mapped to any indexed topic — rather than silently returning nothing or a default.

R7. Adding a plugin to the fleet without adding a corresponding entry to `llms.txt` causes the
fleet-local census `--check` to fail (red), and adding the entry makes it pass (green) — this must be
demonstrated red-then-green, not just asserted.

R8. The whole-inject set (the topics marked whole-inject in `llms.json`'s load-policy) stays under a
2KB combined budget, consistent with the consumption shape documented in the grounding brief
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:84-85`).

### Key Flows

F1. **Fleet census check in CI.** Trigger: CI runs (or an operator runs) `context_census.py --check`.
The script parses `llms.txt`, regenerates the expected `llms.json`, and diffs it against the committed
file. Clean → exits zero. Drift (missing plugin, mismatched byte-size/authority-rank, stale hash) →
exits non-zero naming the offending topic. Covers R2, R3, R7.

F2. **Work-context resolution.** Trigger: an agent or operator needs the standards doc for a given work
context. `standards_resolve.py` looks up the context against the index and returns the per-topic
README path. A context that maps cleanly returns the path; an unindexed context fails loud with a
named miss. Covers R5, R6.

F3. **Staleness detection.** Trigger: a topic README's content changes (a standard is edited) without
its recorded hash in `llms.json` being refreshed. The staleness guard, run against any cached/quoted
standard, flags the mismatch rather than silently trusting the stale copy. Covers R4.

## Definition of Done

A fleet-local, census-checked `llms.txt`/`llms.json` pair exists at the `infiquetra-claude-plugins`
root covering all 8 plugins, with `context_census.py --check` passing on a clean index and failing
(red-then-green) on a drifted or unindexed plugin. `standards_resolve.py` maps a work context to the
correct per-topic README and fails loud on an index miss. The whole-inject topic set stays under the
2KB combined budget, and the new census/resolver tests in `tests/test_context_census.py` and
`tests/test_standards_resolve.py` all pass alongside the full repo gate (pytest, ruff, mypy).

### Acceptance criteria
- [ ] AC1. **Covers R1, R2.** Given the repository at HEAD, running the census script against `llms.txt`
  produces a valid `llms.json` enumerating all 8 fleet plugins with topic/byte-size/authority-rank/
  load-policy fields. Check: `uv run python scripts/context_census.py --write llms.json && python3 -c
  "import json; d=json.load(open('llms.json')); assert len(d['topics']) >= 8"` → succeeds.

- [ ] AC2. **Covers R3, R7.** Given `llms.json` deliberately edited to drift from `llms.txt` (a byte-size
  changed without updating `llms.txt`), running `context_census.py --check` exits non-zero and names
  the drifted topic. Check: `uv run pytest tests/test_context_census.py -k llms_json_drift_fails` →
  passes.

- [ ] AC3. **Covers R7.** Given a 9th plugin directory added under `plugins/` with no corresponding
  `llms.txt` entry, `context_census.py --check` fails (red); after adding the entry, the same check
  passes (green). Check: `uv run pytest tests/test_context_census.py -k unindexed_plugin_red_then_green`
  → passes.

- [ ] AC4. **Covers R4.** Given a topic README's content mutated after its hash was recorded in
  `llms.json`, the staleness guard flags the now-stale recorded hash. Check: `uv run pytest
  tests/test_context_census.py -k staleness_hash_mismatch_flagged` → passes.

- [ ] AC5. **Covers R5, R6.** Given a sample work context string that maps to a known indexed topic,
  `standards_resolve.py` resolves it to the expected per-topic README path; given a work context with
  no indexed match, it fails loud rather than defaulting silently. Check: `uv run pytest
  tests/test_standards_resolve.py -k sample_context_resolves and index_miss_fails_loud` → passes.

- [ ] AC6. **Covers R8.** The combined byte-size of all `llms.json` topics marked `load-policy:
  whole-inject` stays under 2KB. Check: `uv run pytest tests/test_context_census.py -k
  whole_inject_budget` → passes.

- [ ] AC7. **Covers R5.** `standards_resolve.py` is hosted beside an existing skill's scripts (not scaffolded
  as a new plugin directory under `plugins/`). Check: `find plugins -maxdepth 1 -type d | wc -l` →
  unchanged from pre-issue plugin count (still 8), confirming no new plugin directory was added.

### Out-of-scope / non-goals
- v1 indexes only the fleet's own 8 plugins and their existing context-library anchors; it does not
  attempt to index arbitrary non-plugin repo content (e.g. `docs/plans/`, `docs/sdlc-issue-drafts/`).
- v1 does not pull the standards index into `mission-control:issue` or `saga:plan` creation flows —
  that consumption integration (named as absent in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:82`) is a distinct follow-on, not this issue.
- v1 does not add any ADR↔code-pattern lint — also named absent in the same grounding-brief line, and
  out of scope here.
- v1 does not build a generic pluggable-validator framework for arbitrary future checkable-content
  classes; it is specifically the standards-index census, sidecar, loader, and staleness guard.
- `standards_resolve.py` is explicitly not a new plugin — it is hosted beside existing skills per
  `{#plugin-portfolio-groom-17-to-7}`. Any future decision to promote it to its own plugin carries its
  own consolidation-burden-of-proof review and is not decided by this issue.
- v1 does not implement a whole-library injection path for `infiquetra-context-library` itself — the
  grounding brief already establishes that is infeasible (`platform-specs` dominates,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:85`).

### Files expected to change

Indicative only — the exact set is `/plan`'s to determine.

- `llms.txt` — new fleet-local standards index at repo root.
- `llms.json` — new machine-readable sidecar, committed alongside `llms.txt`.
- `scripts/context_census.py` — new census script: emits `llms.json`, supports `--check`, computes
  per-topic hashes.
- `scripts/standards_resolve.py` (or hosted beside an existing skill's `scripts/` directory, per R5/AC7)
  — new work-context → README resolver.
- `.github/workflows/ci.yml` — wire `context_census.py --check` into the default `validate` job
  (non-opt-in).
- `tests/test_context_census.py` — new census/drift/staleness tests.
- `tests/test_standards_resolve.py` — new resolver tests.

### Tests to add or update

- Census: `llms.json` regenerates cleanly from `llms.txt` and enumerates all 8 plugins.
- Census: drift between `llms.txt` and `llms.json` (byte-size/authority-rank mismatch) fails `--check`.
- Census: an unindexed 9th plugin fails `--check` (red), and adding its entry passes (green).
- Staleness: a mutated topic README with a stale recorded hash is flagged by the guard.
- Resolver: a sample work context resolves to the expected per-topic README.
- Resolver: an unindexed work context fails loud (named error), not a silent default.
- Budget: the whole-inject topic set stays under the 2KB combined byte-size budget.

### Verification

```bash
# New census + resolver tests
uv run pytest tests/test_context_census.py tests/test_standards_resolve.py -v

# Census check (CI parity) — must exit 0 on a clean index
uv run python scripts/context_census.py --check

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; `context_census.py --check` exits 0 against the committed `llms.txt`/`llms.json`
pair; deliberately drifted or unindexed fixtures cause the corresponding test to fail as designed.

### Release-surface checklist

This issue adds new authoring-time/CI-enforced tooling (`llms.txt`, `llms.json`, census, resolver) but
does not change any existing plugin's runtime skill/agent/command behavior by itself. Confirm at merge:

- [ ] No `plugins/*/.claude-plugin/plugin.json` version bump required if `context_census.py` and
      `standards_resolve.py` live in repo-root `scripts/` (or a non-versioned location), not inside a
      versioned plugin package.
- [ ] If `standards_resolve.py` is instead hosted inside an existing plugin's `skills/*/scripts/`
      directory (per R5), that plugin's `plugin.json` version is bumped and
      `.claude-plugin/marketplace.json` is updated to match.
- [ ] If hosted inside a plugin: that plugin's `CHANGELOG.md` gets an entry describing the new
      resolver script and its dependency on the fleet-local `llms.txt`/`llms.json` index.
- [ ] Version/metadata drift-guard tests (matching this repo's existing parity-test pattern) are
      updated to cover the new index files if they are placed under a versioned plugin path.
- [ ] `llms.txt` and `llms.json` are committed at the location this issue's `/plan` settles on and
      reviewed as part of the PR diff — not generated-and-discarded or gitignored.

## Grounding References

- Absorbed idea `T9-F1-3` (role: primary) — "Fleet-local self-describing standards index
  (plugins-repo llms.txt)." Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`.
  DoD sketch: "Merged `/llms.txt` (or `standards-index.md`) at plugins-repo root mapping each of 8
  plugins to authority-tiered obligations + context-library anchors, plus a `context_census`-style CI
  `--check`; verified red-then-green by adding an unindexed plugin and watching the census fail."
  Covers R1, R7 / AC1, AC3.
- Absorbed idea `T9-F3-3` (role: facet) — "llms.json sidecar: make the index a machine-readable
  consumption contract." Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`. DoD
  sketch: "Merged `context_census.py` `llms.json` emission (topic→byte-size→authority-rank→load-policy)
  + a shared standards_index reader in this repo; verified by census `--check` failing when
  `llms.json` drifts from `llms.txt` and the reader's whole-inject set staying under a 2KB budget
  test." Covers R2, R3, R8 / AC1, AC2, AC6.
- Absorbed idea `T9-F4-7` (role: facet) — "Per-topic on-demand standards loader keyed off the
  llms.txt index." Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`. DoD sketch:
  "Merged `standards_resolve.py` (hosted beside existing skills, no new plugin per
  `{#plugin-portfolio-groom-17-to-7}`) mapping work context → correct per-topic README via the vendored
  `llms.txt` index + skill references + tests; verified by a sample context mapping to the expected doc
  and failing on an index miss." Covers R5, R6 / AC5, AC7.
- Absorbed idea `T9-F5-3` (role: facet) — "Schema-registry ETags: llms.txt as a staleness-detecting
  manifest with per-topic hashes." Basis:
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`. DoD sketch: "Merged
  `context_census.py` per-topic content hashes in `llms.txt` + a consumer-side If-None-Match staleness
  guard that flags any cached/quoted standard whose recorded hash no longer matches live; verified by
  mutating a topic README and asserting the guard flags the now-stale recorded hash. Distinct from
  F3-3 (load-policy) — this is the freshness guarantee." Covers R4 / AC4.
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77-80` (section 4) — binding
  convention this issue extends: "schema-validate-in-CI + self-describing index, not runtime-injected
  blobs," modeled on `infiquetra-context-library`'s existing `validate.yml` / `check_docs.py` /
  `context_census.py --check`.
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:82-83` (section 4) — names
  what is currently absent (`mission-control:issue`/`saga:plan` pull-in, ADR↔code-pattern lint, any
  CI reference to the library) — explicitly excluded from this issue's scope (see Scope Boundaries).
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:84-85` (section 4) — the
  consumption-shape constraint (`llms.txt` ~1-2KB whole-injectable, per-topic READMEs 8-12KB
  load-on-demand, whole-library injection infeasible) that R8/AC6 encode as a test.
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52` — binding decision
  `{#plugin-portfolio-groom-17-to-7}`: "Plugin sprawl is an active concern — 'new plugin' ideas carry
  a consolidation burden of proof," which R5/AC7 hold `standards_resolve.py` to.
- Confirmed absent at grounding time: `find . -iname llms.txt -o -iname context_census.py` returns no
  results in `infiquetra-claude-plugins` (verified during issue drafting).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** none
- **Justification:** Structural tier — this issue introduces a new cross-cutting contract (index +
  sidecar + loader + staleness guard) consumed by CI and, eventually, by authoring-time flows across
  all 8 plugins, so it carries more design surface than a single mechanical script (hence high effort
  and the team-execution backend for reviewer consensus on the index schema), but it is still a
  well-scoped, deterministic engineering task with no need for external-LLM generation or advisory
  review — sonnet is sufficient per the fleet's model-tiering guidance (elevated model reserved for
  judgment/design/adversarial review, not deterministic index plumbing).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (ids `T9-F1-3`, `T9-F3-3`,
  `T9-F4-7`, `T9-F5-3`)
- Source type: ideation survivor absorption (issue-map)
- Source title: Machine-readable standards index — llms.json sidecar, per-topic loader, staleness
  hashes, fleet-local index

### Context library links

_none_

### Objective

Enforce context-library standards at authoring time

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/408
- Number: 408
- Created at: 2026-07-04T08:04:00.373352+00:00

