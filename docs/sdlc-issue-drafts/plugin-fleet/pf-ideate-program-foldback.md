---
title: "enhancement: fold the plugin-fleet ideation program's architecture back into saga:ideate"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
objective: Make the backlog and lifecycle self-improving
tier: structural
wave: wave-3
---

# enhancement: fold the plugin-fleet ideation program's architecture back into saga:ideate

### Objective
Make the backlog and lifecycle self-improving

### Tier
structural

### Wave
wave-3

### Intent
The plugin-fleet ideation program run on 2026-07-03 (this repo's own `docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md` and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`) is a hand-built, bespoke pipeline: a multi-source grounding stage (repo scan, journal-learnings, named-repo reads, context-library reads, issue clustering, web — `plugins/saga/skills/ideate/SKILL.md:178-360`, "Phase 1: Grounding"), ~72 Opus 4.8 frame agents across 12 themes, 6 Fable-5 novelty hunters run **blind to the Opus pool** (intake brief lines 66-76: "Fleet-wide novelty hunters ... Blind to the Opus fleet; hunt only what an obvious pass won't find"), a terminal **gap-synthesis** pass that is the only stage allowed to read the merged pool (intake brief lines 143-151, pre-mortem 4: "Novelty anchoring — hunters seeing the Opus pool would converge toward it. Mitigation: hunters run blind; only gap-synthesis reads the pool, and only after dedup"), and a global concurrency cap of 3 to avoid rate-limit blowout (intake brief lines 66-76, pre-mortem 3).

`saga:ideate`'s registered description already claims this genus ("multi-agent divergent→convergent engine," `plugins/saga/skills/ideate/SKILL.md:3`) and its Phase 2 frame-agent contract already carries a `basis` field with `direct:` / `external:` / `reasoned:` tagging (`plugins/saga/skills/ideate/SKILL.md` Phase 2 per-idea contract) — but verified absent from the skill today: any blind-hunter lane, any terminal gap-synthesis pass, and any cap-aware batch dispatch across frame agents (Phase 2 dispatches "N frame agents ... in parallel" with no stated concurrency cap). Grounded in survivor `G-negative-space-12` (theme T10, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json`): "This program is running on a hand-built pipeline ... None of it lives in `saga:ideate` ... will evaporate once this backlog ships. No pool idea proposes capturing it: 17 `/ideate`-adjacent hits are all engine-lane offers *into* `/ideate`, not upgrades to `/ideate`'s own architecture."

This issue promotes the proven elements of the one-off pipeline into `saga:ideate` as declared, reusable skill machinery: an explicit grounding-brief stage pattern, a `basis_type` contract on every emitted idea (formalizing the existing `direct`/`external`/`reasoned` tags used informally by this program's survivor records, e.g. `T10.json`'s `"basis_type":"direct"`), an optional blind-hunter lane, a terminal gap-synthesis pass, and cap-aware batch dispatch — so the next large divergence run is an invocation, not a two-day bespoke pipeline build.

### Out-of-scope / non-goals
- Re-running or re-grounding the plugin-fleet ideation program itself — this issue only generalizes its *machinery* into the skill.
- Building a standing multi-repo grounding-brief automation — the grounding-brief stage becomes an optional documented pattern within Phase 1, not a new scheduled process.
- Adding new external-LLM providers beyond the Fable tier already referenced in the skill's model guidance.
- Backfilling `basis_type` onto historical ideation artifacts already persisted under `docs/ideation/`.
- Changing the six-frame Phase 2 frame taxonomy or the Phase 0 grounding-fit gate — this is additive machinery, not a redesign of existing phases.
- Any change to `/office-hours`, `/brainstorm`, or `/plan` — the fold-back is scoped to `saga:ideate` alone.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/skills/ideate/SKILL.md` — Phase 1 gains a documented grounding-brief stage option; Phase 2's per-idea contract gains an explicit `basis_type` enum field; dispatch gains a stated concurrency cap.
- `plugins/saga/skills/ideate/references/convergence-and-partnership.md` — gap-synthesis pass (post-merge, pool-reading) documented alongside existing Phase 3 critique.
- `plugins/saga/skills/ideate/references/ideation-artifact.md` — artifact schema gains `basis_type` field and (when used) blind-hunter and gap-synthesis provenance tags.
- `plugins/saga/skills/ideate/references/blind-hunter-lane.md` — new reference (proposed path) documenting the optional Fable-tier blind-hunter mode and its anti-anchoring rule (hunters never read the merged pool; only gap-synthesis does).
- `plugins/saga/CHANGELOG.md` — new entry for the minor version bump.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — matching version bump for the `saga` plugin entry.

### Tests to add or update
- A scaled-down `/ideate` invocation (small frame count, tactical scope) exercises the upgraded skill end-to-end and produces ideas that conform to the new `basis_type` contract (every survivor idea carries one of `direct` / `external` / `reasoned`).
- A dry-run or documented walkthrough of the blind-hunter lane demonstrates hunters received no merged-pool content in their dispatch prompt, while the gap-synthesis prompt did.
- A drift-guard test (or manual check folded into existing plugin-metadata tests) confirms `plugins/saga/.claude-plugin/plugin.json` version matches the `saga` entry in `.claude-plugin/marketplace.json`.
- `plugins/saga/CHANGELOG.md` has a dated entry matching the new version.

## Definition of Done
`saga:ideate`'s `SKILL.md` and references gain a documented grounding-brief stage, an explicit `basis_type` contract, an optional blind-hunter lane, and a pool-reading gap-synthesis pass, with dispatch stating its concurrency cap. `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`'s `saga` entry, and `plugins/saga/CHANGELOG.md` carry a matching version bump. A scaled-down `/ideate` invocation exercises the upgraded skill end-to-end and produces ideas conforming to the new `basis_type` contract.

### Acceptance criteria
- [ ] `saga:ideate`'s Phase 2 per-idea contract includes an explicit `basis_type` field (enum: `direct` / `external` / `reasoned`) that every emitted idea must carry, and an idea with no articulated basis does not surface (already-stated rule in `SKILL.md`, now backed by a named, checkable field). Check: `grep -n "basis_type" plugins/saga/skills/ideate/SKILL.md plugins/saga/skills/ideate/references/ideation-artifact.md` → both files contain the term.
- [ ] Phase 1 documents a grounding-brief stage pattern (multi-source: repo scan, journal-learnings, named-repo, context-library, issue cluster, web — mirroring this program's five-source grounding brief) as an available mode for large/cross-repo runs. Check: `grep -n "grounding.brief\|grounding brief" plugins/saga/skills/ideate/SKILL.md` → at least one match under the Phase 1 section.
- [ ] An optional blind-hunter lane is documented: a Fable-tier pass that never receives the merged frame-agent pool in its dispatch prompt. Check: `grep -rn "blind" plugins/saga/skills/ideate/` → matches in `SKILL.md` or the new `blind-hunter-lane.md` reference describing the hunter's dispatch prompt excludes the merged pool.
- [ ] A terminal gap-synthesis pass is documented as the only stage permitted to read the merged, deduped candidate pool, producing cross-cutting hybrids the frame agents and blind hunters didn't surface. Check: `grep -n "gap.synthesis\|gap synthesis" plugins/saga/skills/ideate/references/convergence-and-partnership.md` → at least one match, with prose stating it is post-merge/post-dedup.
- [ ] Frame-agent (and, when used, blind-hunter) dispatch states a concurrency cap consistent with the source program's rate-limit mitigation (global cap of 3). Check: `grep -n "concurrency cap\|cap of 3\|capped batch" plugins/saga/skills/ideate/SKILL.md` → at least one match in the Phase 2 dispatch section.
- [ ] A scaled-down `/ideate` invocation (small tactical run) produces at least one survivor idea whose `basis_type` is populated and matches one of the three declared values. Check: run `/ideate` in tactical scope against a throwaway topic and inspect the persisted artifact under `docs/ideation/` for a `basis_type` field on each surviving idea; manually confirm no idea lacks the field.
- [ ] Hunters are demonstrably blind to the merged pool: the blind-hunter dispatch prompt (as documented/templated in the skill) contains no reference to, or embedded content from, the merged frame-agent candidate list; only the gap-synthesis dispatch prompt does. Check: inspect the two dispatch prompt templates side by side in the reference file(s) — the hunter template has no `{merged_candidates}`-equivalent placeholder, the gap-synthesis template does.
- [ ] Release-surface parity: `plugins/saga/.claude-plugin/plugin.json` version, `.claude-plugin/marketplace.json`'s `saga` entry version, and `plugins/saga/CHANGELOG.md`'s newest dated entry all agree. Check: `python3 -c "import json; a=json.load(open('plugins/saga/.claude-plugin/plugin.json'))['version']; b=[e for e in json.load(open('.claude-plugin/marketplace.json'))['plugins'] if e['name']=='saga'][0]['version']; assert a==b, (a,b); print(a)"` → prints the shared version with no assertion error.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# Confirm the new contract/lane/pass/cap language landed
grep -n "basis_type" plugins/saga/skills/ideate/SKILL.md plugins/saga/skills/ideate/references/ideation-artifact.md
grep -rn "blind" plugins/saga/skills/ideate/
grep -n "gap.synthesis\|gap synthesis" plugins/saga/skills/ideate/references/convergence-and-partnership.md
grep -n "concurrency cap\|cap of 3\|capped batch" plugins/saga/skills/ideate/SKILL.md

# Release-surface parity
python3 -c "import json; a=json.load(open('plugins/saga/.claude-plugin/plugin.json'))['version']; b=[e for e in json.load(open('.claude-plugin/marketplace.json'))['plugins'] if e['name']=='saga'][0]['version']; assert a==b, (a,b); print(a)"

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all greps find matches in the expected files; the version-parity script prints a single shared version string with no assertion error; the full gate is green.

A scaled-down `/ideate` invocation is a manual verification step (not scriptable in CI) — run it against a small throwaway topic in tactical scope and confirm the persisted artifact under `docs/ideation/` shows every surviving idea carrying a populated `basis_type`.

### Recommended executor profile
- **Model:** Sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is a self-contained documentation/skill-text upgrade — no new runtime code, no cross-repo coordination, no adversarial or architectural judgment call beyond what the source plan briefs already settled. The machinery to promote (grounding stages, basis contract, blind-hunter lane, gap-synthesis pass, cap-aware batching) is fully specified in the two dated plan briefs; the work is transcription and skill-text authoring, which does not warrant Opus-tier judgment or an external-LLM (Fable) pass. Medium effort reflects touching four skill/reference files plus the release-surface checklist, not deep design work.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json (idea `G-negative-space-12`)
- Source type: ideation-survivor
- Source title: Fold this ideation program's architecture back into /ideate: blind hunters, gap synthesis, basis contract, and capped batching as reusable skill machinery

## Grounding References
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json` — absorbed idea `G-negative-space-12` (role: primary; verdict: survive; tier: structural).
- `docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md:66-76` — Phase D layer table: Opus wide net, Fable blind novelty hunters, gap synthesis, convergent critique; global concurrency cap of 3.
- `docs/plans/2026-07-03-plugin-fleet-ideation-intake-brief.md:143-151` — pre-mortem 4, "Novelty anchoring," the binding rationale for hunters running blind and gap-synthesis being the sole pool-reading stage.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` sections 5-6 — the five-source grounding-brief pattern (pre-existing seeds, recurring-pain themes) this issue generalizes into Phase 1.
- `plugins/saga/skills/ideate/SKILL.md:3` — the skill's existing "multi-agent divergent→convergent engine" description, which this issue makes true in mechanism, not just genus.
- `plugins/saga/skills/ideate/SKILL.md` Phase 2 per-idea contract — existing informal `direct:`/`external:`/`reasoned:` basis tagging, formalized here into a named `basis_type` field.
- `issue-map-final.json` consolidation rationale: "Self-contained skill upgrade; the machinery (blind hunters, gap synthesis, basis contract, capped batching) is documented in the two dated plan briefs and just needs to become durable skill text."

**Absorbed ideas:** G-negative-space-12

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/440
- Number: 440
- Created at: 2026-07-04T08:14:51.214996+00:00

