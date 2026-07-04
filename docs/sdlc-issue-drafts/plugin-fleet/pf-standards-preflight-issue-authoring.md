---
title: "capability: standards preflight at issue-authoring time (mission-control:issue + saga:handoff)"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Enforce context-library standards at authoring time"
wave: wave-2
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: high, backend: inline, external_llm: none}
---

# capability: standards preflight at issue-authoring time (mission-control:issue + saga:handoff)

### Intent
Pull infiquetra-context-library standards into the issue-authoring moment instead of leaving
enforcement solely inside the library's own CI. Add a `standards_preflight.py` step, wired into
`mission-control:issue`'s drafting flow and `saga:handoff`, that (1) whole-injects the vendored
`llms.txt` index so a draft can be checked against it, (2) surfaces any binding `DECISIONS.md`
entry whose revisit-when condition the draft trips, and (3) validates any path cited in the
draft's `Context library links` field against that index — failing the card_validator preflight
when a cited path does not resolve.

## Problem / Motivation

- **Standards enforcement exists only inside the library, not at authoring time in this repo.**
  The grounding brief's standards/ADR-enforcement survey names the exact gap: infiquetra-context-library
  already runs `validate.yml` CI (`check_docs.py` schema/frontmatter/link lint plus
  promotion-ledger checks) and `context_census.py --check` to keep `llms.txt` honest — "org
  convention is schema-validate-in-CI + self-describing index, not runtime-injected blobs" — but
  "**Absent:** pull library into `mission-control:issue` / `saga:plan` creation; ADR↔code-pattern
  lint; reference library repo's CI" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4).
  Nothing today checks a drafted issue against the library's index or this repo's own binding
  decisions before the draft is created.
- **`Context library links` is a required field that is validated for presence, not resolution.**
  `plugins/mission-control/scripts/sdlc_manager.py`'s `validate_card_body_for_context` (function
  at `sdlc_manager.py:2589`) already enforces that a `Context library links` H3 section exists,
  is non-empty, and is not placeholder-only for prepared drafts — but it never resolves the cited
  path against any index; a fabricated or stale path currently passes. `plugins/mission-control/skills/issues/SKILL.md:89`
  states "`Context library links` is required for Hermes readiness; use `_none_` when no context
  applies," again with no resolution step behind it.
  This gap is the operator's original ask, preserved via `S-34` (dedup-merged into this issue):
  "Enforce ADRs/technical standards — in mission-control issue injection? always part of
  doc-review/code-review?" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`,
  id `S-34`).
- **A binding decision can be tripped by a new draft with nothing surfacing it.** The
  binding-decision register (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2) lists
  anchors with standing revisit-when conditions, e.g.
  `{#plugin-portfolio-groom-17-to-7}` (`docs/engineering-journal/DECISIONS.md:1031`) — "Plugin
  sprawl is an active concern — 'new plugin' ideas carry a consolidation burden of proof." Today
  an author drafting "let's add a new plugin for X" gets no prompt that this decision exists or
  that its burden-of-proof condition applies; the decision only surfaces if a reviewer happens to
  recall it.
- **`saga:handoff` routes into `mission-control:issue` with no standards checkpoint of its own.**
  `plugins/saga/skills/handoff/SKILL.md` builds an envelope and routes via `suggested_command` to
  `/issue --prepare --from <source> --maturity <maturity>` (handoff.md workflow steps 3 and 6),
  but the handoff boundary explicitly assigns "issue body sections… readiness checks… labels,
  project fields" to `mission-control`, so today neither side runs a standards check at the
  handoff moment itself — the preflight has no injection point on the `saga:handoff` side either.

## Definition of Done

Merged PR(s) delivering:

1. `plugins/mission-control/scripts/standards_preflight.py` — new script that (a) loads the
   vendored `llms.txt` index (whole-injectable at ~1-2KB per the grounding brief §4) from
   infiquetra-context-library's published copy, (b) resolves each path cited in a draft's
   `Context library links` section against that index, flagging any path not present, and (c)
   scans the draft body for binding-`DECISIONS.md`-anchor trigger terms and reports any tripped
   revisit-when condition alongside its anchor.
2. `plugins/mission-control/skills/issues/SKILL.md` wired to call the preflight during drafting
   (before `validate_card_body_for_context` gates the draft) and to surface its findings inline in
   the prepared draft's readiness output.
3. `plugins/saga/skills/handoff/SKILL.md` updated to invoke the same preflight step (or a thin
   call into `standards_preflight.py`) before routing its `suggested_command`, so a tripped
   revisit-when or an unresolved context-library link surfaces at handoff time, not only at
   `mission-control:issue` drafting time.
4. `validate_card_body_for_context` (`plugins/mission-control/scripts/sdlc_manager.py:2589`)
   extended so a `Context library links` entry that fails index resolution is reported as a
   blocking gap alongside its existing empty/placeholder checks (not a silent pass).
5. Release-surface updates (see checklist below) reflecting this as a behavior change to both
   `mission-control` and `saga`.

Verify: a draft mentioning "new plugin" surfaces the `{#plugin-portfolio-groom-17-to-7}` anchor
and its revisit-when text; a draft citing a real `llms.txt`-indexed path passes; a draft citing a
fabricated path fails `validate_card_body_for_context` with a named unresolved-link error; the
same preflight fires identically whether entered via `mission-control:issue` or via
`saga:handoff`'s routed command.

### Acceptance criteria
- [ ] **AC1 (T9-F3-1, primary).** A draft body mentioning "new plugin" surfaces the
  `{#plugin-portfolio-groom-17-to-7}` anchor and its revisit-when text in the preflight's output.
  Check: `uv run pytest tests/test_standards_preflight.py -k plugin_portfolio_groom_surfaced` →
  passes; a draft with no plugin-adding language produces no such surfaced anchor in the same run.
- [ ] **AC2 (T9-F4-1, facet).** A draft body citing a `Context library links` path that does not exist
  in the vendored `llms.txt` index fails `validate_card_body_for_context`, naming the unresolved
  path. Check: `uv run pytest tests/test_standards_preflight.py -k nonindex_path_fails` → passes.
- [ ] **AC3 (T9-F4-1, facet).** A draft body citing a `Context library links` path that does exist in
  the index passes both the preflight and `validate_card_body_for_context`. Check:
  `uv run pytest tests/test_standards_preflight.py -k index_path_passes` → passes.
- [ ] **AC4 (T9-F3-1 / S-34, primary).** The preflight is invoked from both `mission-control:issue`'s
  drafting flow (`plugins/mission-control/skills/issues/SKILL.md`) and `saga:handoff`'s routing
  step (`plugins/saga/skills/handoff/SKILL.md`), not only one of the two — resolving `S-34`'s
  original "issue injection vs doc/code-review, where?" question as "both authoring-time entry
  points, ahead of doc/code-review." Check: `grep -rln "standards_preflight" plugins/mission-control/skills/issues/SKILL.md
  plugins/saga/skills/handoff/SKILL.md` → both files match.
- [ ] **AC5.** `_none_` remains a valid, non-failing value for `Context library links` (unchanged
  behavior for issues with no applicable context) — the new resolution check does not fire when
  the field is the existing none-marker. Check: `uv run pytest tests/test_standards_preflight.py
  -k none_marker_still_passes` → passes.

### Out-of-scope / non-goals
**In scope:** the `standards_preflight.py` script; its two injection points
(`mission-control:issue` drafting, `saga:handoff` routing); the `llms.txt`-index resolution check
folded into `validate_card_body_for_context`; the binding-`DECISIONS.md`-anchor surfacing check;
release-surface updates on `mission-control` and `saga`.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Whole-library injection of per-topic READMEs — the grounding brief §4 notes these run 8-12KB
  and load on demand; only `llms.txt` (the ~1-2KB self-describing index) is whole-injected here.
- Reworking infiquetra-context-library's own `validate.yml`/`check_docs.py`/`context_census.py`
  enforcement — that CI already exists and stays untouched; this issue only consumes its published
  `llms.txt` output, it does not modify the library's build.
- Any ADR↔code-pattern lint against touched source files (as opposed to link/anchor checks against
  drafted issue text) — that is separate follow-on scope named in the same grounding-brief gap and
  is not this issue's mechanism.
- Automatically resolving or fixing a tripped revisit-when condition — the preflight surfaces the
  anchor and its text for the author to act on; it does not block issue creation outright or
  auto-edit `DECISIONS.md`.
- Changing `mission-control:issue`'s or `saga:handoff`'s ownership boundary — `mission-control`
  keeps owning issue body sections and readiness checks; `saga` keeps owning envelope/routing; the
  preflight is a shared check both sides call, not a boundary change.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T9-F3-1` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged mission-control standards_preflight.py + wire-in to issues/SKILL.md (+ saga:handoff) that whole-injects llms.txt and surfaces any binding DECISION whose revisit-when the draft trips; verified by a test asserting a draft mentioning 'new plugin' surfaces the `{#plugin-portfolio-groom-17-to-7}` anchor and its revisit-when.") | primary |
| `S-34` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (id `S-34`, `basis_type`: "direct", `basis`: "operator statement 'enforce ADRs/technical standards — in mission-control issue injection? always part of doc-review/code-review?'") — dedup-merged into `T9-F3-1` per the issue-map's consolidation rationale: "T9-F3-1 is the keeper for the seed's enforce-ADRs-where question." Resolved by AC4: both authoring-time entry points, ahead of doc/code-review. | dedup-merged |
| `T9-F4-1` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged resolver step in issues/SKILL.md + sdlc_manager.py validate_card_body that resolves entered 'Context library links' against the vendored llms.txt index; verified by a red/green test where a body citing a non-index path fails validation and one citing a real llms.txt anchor passes.") | facet |

**Binding decisions this issue builds on / must not contradict:**
- Standards/ADR-enforcement org convention (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §4): schema-validate-in-CI + self-describing index, not runtime-injected blobs. This issue's
  preflight consumes the published `llms.txt` index and reads `DECISIONS.md` text directly; it
  does not stand up a new runtime blob-injection mechanism or duplicate the library's own CI.
- `{#mission-control-issue-contract-consumer-sync}` (#222,
  `docs/engineering-journal/DECISIONS.md`): the existing boundary that generated contract data
  (the 6 required H3 headers, regexes, placeholder set) is vendored from `infiquetra-sdlc` and the
  algorithm stays hand-maintained in `mission-control`. This issue's extension to
  `validate_card_body_for_context` follows the same shape — it adds an algorithm-side resolution
  check, it does not fork or duplicate the vendored contract data.
- `{#plugin-portfolio-groom-17-to-7}` (`docs/engineering-journal/DECISIONS.md:1031`): "Plugin
  sprawl is an active concern — 'new plugin' ideas carry a consolidation burden of proof." AC1 is
  this issue's direct verification that this specific binding decision surfaces at draft time.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** this is a bounded, mechanical injection-point wiring task (new script, two
  call-site edits into existing skill flows, one extension to an existing validator function, plus
  index-resolution and anchor-surfacing tests) over already-structured inputs (`llms.txt`,
  `DECISIONS.md` headings) — not novel design or adversarial judgment. Sonnet/high matches the
  fleet's own work-shape heuristic for bounded mechanical transforms with real cross-file
  correctness risk (both `mission-control:issue` and `saga:handoff` must call the preflight
  identically). No external-LLM chaperone dispatch is warranted.

## Release-Surface Checklist

This issue changes both `mission-control`'s and `saga`'s skill-consumed drafting/routing behavior
and adds a new `mission-control` script, so the following must update in the same PR:
- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump reflecting the new
      `standards_preflight.py` script and its wiring into `issues/SKILL.md`.
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting `handoff/SKILL.md`'s new
      preflight call.
- [ ] `.claude-plugin/marketplace.json` — both `mission-control` and `saga` entries'
      versions/descriptions kept in sync with their respective `plugin.json` bumps.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry describing `standards_preflight.py` and the
      `Context library links` index-resolution check.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the `saga:handoff` preflight call.
- [ ] Drift-guard/version-metadata tests (repo's existing marketplace/plugin-metadata drift tests)
      updated or confirmed still green against both version bumps.

## Files Expected to Change

- `plugins/mission-control/scripts/standards_preflight.py` — new script.
- `plugins/mission-control/scripts/sdlc_manager.py` — `validate_card_body_for_context`
  (around `sdlc_manager.py:2589`) extended with index-resolution error reporting.
- `plugins/mission-control/skills/issues/SKILL.md` — wired to call the preflight during drafting.
- `plugins/saga/skills/handoff/SKILL.md` — wired to call the preflight before routing.
- `tests/test_standards_preflight.py` — new tests.
- `plugins/mission-control/.claude-plugin/plugin.json`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/mission-control/CHANGELOG.md`,
  `plugins/saga/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_standards_preflight.py::test_plugin_portfolio_groom_surfaced` — a draft mentioning
  "new plugin" surfaces `{#plugin-portfolio-groom-17-to-7}` and its revisit-when text.
- `tests/test_standards_preflight.py::test_nonindex_path_fails` — a `Context library links` entry
  citing a path absent from `llms.txt` fails `validate_card_body_for_context` with a named error.
- `tests/test_standards_preflight.py::test_index_path_passes` — a `Context library links` entry
  citing a real `llms.txt`-indexed path passes.
- `tests/test_standards_preflight.py::test_none_marker_still_passes` — the existing `_none_`
  marker remains valid and non-failing.
- `tests/test_standards_preflight.py::test_wired_at_both_entry_points` — the preflight is called
  from both `issues/SKILL.md` and `handoff/SKILL.md`.

### Verification
```bash
# New standards-preflight suite
uv run pytest tests/test_standards_preflight.py -v

# Extended card validator still passes existing suite
uv run pytest tests/test_sdlc_manager.py -k card_body -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; a draft body citing a fabricated `Context library links` path turns
`test_nonindex_path_fails` red until the path is corrected or removed; a draft mentioning "new
plugin" reliably surfaces the `{#plugin-portfolio-groom-17-to-7}` anchor in preflight output.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (ids `T9-F3-1`,
  `T9-F4-1`), `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (id `S-34`)
- Source type: ideation survivors + issue-map consolidation
- Source title: Standards preflight at issue-authoring time (mission-control:issue + saga:handoff)

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/mission-control/scripts/sdlc_manager.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/saga/skills/handoff/SKILL.md`
- `plugins/mission-control/scripts/standards_preflight.py`
- `plugins/mission-control/skills/issues/SKILL.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json`
- `docs/engineering-journal/DECISIONS.md`

### Tests to add or update

- `tests/test_sdlc_manager.py`
- `tests/test_standards_preflight.py`

### Objective

"Enforce context-library standards at authoring time"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/409
- Number: 409
- Created at: 2026-07-04T08:04:16.837521+00:00

