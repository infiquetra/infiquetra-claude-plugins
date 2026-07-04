---
title: "context-update: freeze the before picture — fleet baseline pain metrics"
repo: infiquetra-claude-plugins
type: context-update
team: campps
project: operations
status: Idea
labels: context-update, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
tier: quick-win
objective: "Build the fleet telemetry and ledger substrate"
wave: wave-2
absorbed_ids: [G-negative-space-10]
---

# context-update: freeze the before picture — fleet baseline pain metrics

### Intent
Commit a single baseline document, before any wave-1 fleet-telemetry fix lands, that
freezes today's fleet pain in ~8 named metrics. Each metric must carry (a) an evidence
source already recorded in this repo's engineering journal or grounding brief, and (b) an
executable recipe an agent can re-run later to re-derive the same number from scratch.
Without this, "the fleet got better" after wave-1/wave-2 land is an assertion nobody can
falsify — there is no committed pre-state to diff against, and the Validation Discipline
this org runs under ("I don't have time for lies and guesses") has no artifact to point
at.

This is a documentation-only context-update: it does not fix any of the underlying pain
points, it only freezes the numbers so later fixes can prove they moved something.

## Problem Frame

The plugin-fleet ideation pass (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`)
surfaced a set of recurring, independently-corroborated pain patterns with numbers
attached, but those numbers live scattered across a grounding brief, session-mining
output, and journal entries — not in one committed, re-derivable baseline:

- Manual ship ceremony (commit→PR→merge→checkout-main→pull→cleanup by raw git/gh) recurs
  across 8 repos even where saga/mission-control is installed
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:112` item 1).
- Gate-primitive unreliability — `AskUserQuestion` silently auto-proceeding on timeout,
  treated as consent — recurs across 6 repos
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:114` item 2).
- mission-control board/field drift, including item-list pagination silently truncating
  at 200 of 375 items, recurs across 4 repos
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:117` item 3).
- Rate-limit fan-out kills ("6 of 7 agents failed on rate-limiting") recur across 3 repos
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119` item 4).
- 219 codex sessions ran in the scan window with zero mining substrate feeding `/retro`
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:151`, section 7).
- The cross-repo promote ledger has never fired a single genuine ≥3-repo transcendent
  cluster — zero learnings promoted despite the loop existing
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:63` section 3, item 5).
- Read-only recon fan-outs burn 350–450k tokens in under 20 minutes, a recorded
  cache-economics singleton (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:151`
  section 7 singletons).
- Silent no-ops in delegation and dead wiring recur across 5+ distinct journal learnings
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99` section 6, item 1).

Each of these is currently a prose claim. None of them has a committed number with a
recipe for re-measuring it later, so a future "did wave-1/wave-2 help" retro has nothing
authoritative to diff against — exactly the "stale claim asserted as fact" failure mode
this same grounding brief flags as a recurring pain
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:100` section 6, item 2).

This issue absorbs one source idea from the ideation pass, `G-negative-space-10`
("Baseline before wave: freeze today's pain metrics so 'the fleet got better' is
measurement, not vibe" — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`,
id `G-negative-space-10`, theme `T10`, frame `gap-negative-space`, verdict `survive`).
Its `idea` and `basis` text fields were headroom-compressed in the ideation transcript and
have since expired past retrieval (`hash=8bfcfb0dd295`, `hash=8a624c1347cb`,
`hash=0034b78afba2` — headroom_retrieve returned "Content not found... expired"); this
issue reconstructs its intent from its `dod_sketch`/`tier_guess` fields (still present in
`issue-map-final.json` and `T10.json`) plus grounding-brief sections 5–6, per the
program's fallback rule for expired/thin seeds.

### Out-of-scope / non-goals
**In scope:**
- One new committed Markdown document under `docs/plans/` capturing ~8 baseline metrics.
- For each metric: a one-line definition, its evidence source (a specific journal/brief
  citation), and an executable re-measurement recipe (a shell command, script invocation,
  or grep/query an agent can run cold).
- A `/retro` re-run checklist line so future retros know to re-derive and diff against
  this baseline.

**Out of scope / non-goals:**
- Fixing any of the underlying pain points (ship ceremony, gate unreliability, board
  drift, rate-limit kills, mining substrate, promote ledger, recon token cost, silent
  no-ops). Those are separate wave-1/wave-2 issues; this issue only freezes the "before"
  numbers.
- Building any new telemetry-collection tooling, dashboards, or automated metric
  pipelines. All recipes in this baseline are manually-runnable one-offs (grep, `gh`
  query, journal citation count) — no new scripts unless a metric is literally
  un-recoverable without one, and even then the script must be trivial (a single grep
  wrapper), not a service.
- Changing `/retro`'s SKILL.md behavior beyond adding the one checklist line referencing
  this baseline document.
- Any plugin runtime behavior change. This is a docs-only context-update; no
  `plugin.json`/`marketplace.json`/`CHANGELOG.md` changes are expected (see Release-surface
  checklist below, included for completeness per repo convention).

## Definition of Done

A new file `docs/plans/<date>-plugin-fleet-baseline-metrics.md` is committed containing
at minimum 8 metrics, each with: (1) a one-line definition, (2) an evidence-source
citation to an existing journal/brief/repo artifact, (3) an executable re-measurement
recipe. The document ends with a `/retro` checklist line. Verification: two of the eight
metrics are independently re-derived from scratch by re-running their recipes, and the
re-derived values match what the grounding brief already reports for them.

### Acceptance criteria
- [ ] AC1. The baseline document exists at a `docs/plans/*.md` path and contains at least
  8 distinct metrics, each with its own subsection or table row.
  Check: `grep -c '^### ' docs/plans/*-plugin-fleet-baseline-metrics.md` (or equivalent
  heading/row count) returns `>= 8`.
- [ ] AC2. Each metric cites a concrete evidence source (a `file:line` or named section) —
  not a vague "seen in journal" claim.
  Check: manual read confirms every metric subsection contains a markdown citation
  matching `` `docs/... :\d+` `` or a named section reference (e.g. "grounding brief
  §6 item 1").
- [ ] AC3. Each metric carries an executable re-measurement recipe (a fenced shell/grep/gh
  command), not prose-only description.
  Check: `grep -c '^```' docs/plans/*-plugin-fleet-baseline-metrics.md` shows a fenced
  code block paired with every metric subsection (count of code fences >= count of
  metrics).
- [ ] AC4 (absorbed facet — manual ship ceremony). The baseline includes a metric for
  ship-ceremony rate (repos performing raw git/gh commit→PR→merge→cleanup instead of
  saga/mission-control tooling), citing
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:112`.
- [ ] AC5 (absorbed facet — rate-limit fan-out kills / "429 kill rate"). The baseline
  includes a metric counting fan-out runs with partial agent failure due to rate
  limiting, citing `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119`.
- [ ] AC6 (absorbed facet — recon token cost). The baseline includes a metric for
  read-only recon fan-out token spend, citing the "350–450k tokens in <20 min" singleton
  in `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 7.
- [ ] AC7 (absorbed facet — promote-ledger firings). The baseline includes a metric for
  cross-repo promote-ledger firings (currently zero), citing
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:63` section 3 item 5.
- [ ] AC8 (absorbed facet — stale worktrees / dead wiring). The baseline includes a metric
  for silent-no-op / dead-wiring incident count, citing
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:99` section 6 item 1.
- [ ] AC9. Two of the eight metrics are re-derived from scratch by an independent agent
  running only the committed recipes (no access to this issue's drafting context), and
  the re-derived values match the grounding brief's reported values.
  Check: manually re-run two chosen recipes' fenced commands and diff output against the
  brief's cited numbers — must match (exact count or documented tolerance).
- [ ] AC10. The document ends with a `/retro` re-run checklist line instructing future
  retros to re-derive this baseline and diff against it.
  Check: `grep -i 'retro' docs/plans/*-plugin-fleet-baseline-metrics.md` returns a line
  referencing re-running the baseline.

## Grounding References

- Absorbed idea `G-negative-space-10` (theme `T10`, frame `gap-negative-space`, verdict
  `survive`) — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`. Basis:
  the program needs a committed "before" so post-wave comparison is measurement, not
  vibe; original `idea`/`basis` prose fields expired from headroom cache
  (hashes `8bfcfb0dd295`, `8a624c1347cb`, `0034b78afba2`) — reconstructed here from the
  surviving `dod_sketch` field plus grounding-brief sections 5–6.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` sections 3, 6, and 7 — the
  source of every metric's evidence citation in this issue.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 5 (pre-existing
  `QUEUED.md` seeds) — confirms this baseline predates and is independent of the
  wave-1 fix seeds it will later be diffed against.
- Binding decision `{#operator-choice-framework}` and the fleet's stated preference for
  derive-on-read over committed state (grounding brief section 6 item 5) — this issue
  is the one deliberate exception: a *committed* baseline is required precisely because
  "before" state cannot be derived-on-read after wave-1 lands and changes the fleet.

## Recommended Executor Profile

- **Model:** Sonnet
- **Effort:** low
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is a documentation-transcription task — pulling already-known
  numbers from an existing grounding brief and journal into one committed file with
  recipes. No architectural judgment, no code change, no ambiguity requiring Opus-level
  reasoning. Matches the org's model-tiering guidance (mechanical/deterministic work →
  Sonnet or Haiku).

## Release-Surface Checklist

Not applicable — this issue changes no plugin behavior, schema, command, or user-facing
guidance. No `plugin.json`, `marketplace.json`, `CHANGELOG.md`, or drift-guard test
changes are required. (Checklist included per repo convention to make the "not
applicable" determination explicit and reviewable.)

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-baseline-metrics.md` — new baseline document (exact
  filename/date TBD by `/plan`).
- `docs/engineering-journal/QUEUED.md` — optional: mark the absorbed seed as addressed if
  it was tracked there.

### Tests to add or update

- No automated tests — this is a docs-only artifact. Verification is the manual
  re-derivation described in AC9.

### Verification

```bash
# Confirm the baseline document exists and has at least 8 metric sections
grep -c '^### ' docs/plans/*-plugin-fleet-baseline-metrics.md

# Confirm every metric has a paired executable recipe (fenced code block)
grep -c '^```' docs/plans/*-plugin-fleet-baseline-metrics.md

# Re-derive one metric from scratch and diff against the brief's reported number, e.g.:
grep -n "Manual ship ceremony" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```
Expected: metric count >= 8, code-fence count >= metric count, and manually re-run
recipes reproduce the numbers already cited in the grounding brief.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` (id
  `G-negative-space-10`) and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  sections 5–6
- Source type: ideation survivor + grounding brief
- Source title: "Freeze the before picture: baseline pain metrics with executable
  re-measurement recipes"

**Absorbed ideas:** G-negative-space-10

### Context library links

_none_

### Objective

"Build the fleet telemetry and ledger substrate"
