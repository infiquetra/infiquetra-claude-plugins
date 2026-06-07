---
title: Saga Document Readability — Formatting Contract Across All Doc-Writing Skills
type: docs
status: active
date: 2026-06-07
origin: docs/ideation/2026-06-07-saga-doc-readability-ideation.md
---

# Saga Document Readability — Formatting Contract Across All Doc-Writing Skills

## Summary

Make readable formatting a first-class, enforced property of every durable document the `saga` plugin
generates (issue #201).

The fix is one shared formatting reference that all nine doc-writing skills link to, a render contract
that keeps the machine-facing schema legible without collapsing, and a pytest gate so the rules cannot
silently regress.

This is a documentation/templates change — no product behavior, no Python beyond one test.

## Problem Frame

Saga docs stack dense bold-label field runs with no blank lines, which CommonMark collapses into one
paragraph — the operator's verbatim "all jumbled together."

The root cause is structural, not editorial: there is no shared formatting reference, so each skill
reinvents its output format. `plan` independently learned "use headings, not list-item fields, because
they detach in CommonMark" (`plan-sections.md:105-108`), but `ideate` never got that lesson and
regressed into the run-on stack.

The ideation pass (`docs/ideation/2026-06-07-saga-doc-readability-ideation.md`) also surfaced a
correction that de-risks the whole effort: nothing machine-parses the per-idea schema fields. The
consumers are `handoff` (directory → maturity + frontmatter) and an LLM reading the doc, so a table or
block is *more* legible to the consumer, not a parse hazard.

## Requirements

R1. Generated saga docs use short paragraphs (≤3 sentences), separated by blank lines — no 4+ sentence blocks.

R2. Each ranked idea / section opens with a one-line plain-language summary before any schema fields.

R3. Comparative or ranked data (tradeoffs, options, survivors, findings) renders as a table or bullets, never a prose wall.

R4. The machine-facing schema (`basis` / `confidence` / `complexity` and equivalents) stays present but visually distinct from narrative, and remains legible to the LLM + human consumer.

R5. Generated prose is soft-wrapped — no hard wrap within a paragraph, paragraphs separated by blank lines.

R6. The formatting rules live in one shared reference (`saga/references/formatting-style.md`) that all nine doc-writing skills link to, so output is consistent across runs and not left to per-run discretion.

R7. The redundant `**title:**` field is removed wherever a heading already carries the title.

R8. A pytest in the existing harness fails on the known-fatal collapse pattern (2+ consecutive `**label:**` lines with no blank line) plus the checkable structural rules, across every saga template.

R9. A canonical worked example (the golden specimen) lives in the shared reference, demonstrates the target format, and is asserted by the test.

## Key Technical Decisions

KTD1 — Shared-reference home is `saga/references/formatting-style.md`: the plugin-level `references/` dir already exists (next to `operator-choice.md`, `saga-spec.md`), and skills already link `saga/references/...` by path (`doc-review/SKILL.md:58`, `spec/SKILL.md:141`). Rejected: a new `_shared` skill (unnecessary ceremony); per-template duplication (drifts — the plan→ideate recurrence is the proof).

KTD2 — Schema render is a table for compact/comparable fields (`basis`-tag, `confidence`, `complexity`, `axis`, `status`), with narrative fields (`rationale`, `downsides`, `description`) kept as prose; prose-heavy per-unit fields (e.g. plan units' Goal/Files/Approach) stay as blank-line-separated bold labels under `###` headings. Rationale: tables never collapse, scan at a glance, and — since the consumer is an LLM + human with no regex (verified) — read better than the run-on stack. Rejected: fenced-block-for-all (loses compact-field scannability); blank-separated-bold-only (verbose, no at-a-glance read).

KTD3 — Soft-wrap is "no hard wrap within a paragraph + mandatory blank lines between paragraphs" for generated output. Rationale: fixes viewer-jumbling most simply and avoids the unusual one-sentence-per-line raw look. Rejected: semantic line breaks (unusual in raw editors); ~100-char wrap (residual jumble risk). Note: this is a generated-output prescription — the pytest does NOT enforce no-hard-wrap on hard-wrapped template *source* (templates stay editor-friendly).

KTD4 — Enforcement is a pytest, `tests/test_saga_doc_formatting.py`, in the existing Tests job; no new top-level script. Rationale: matches the recent "zero new top-level Python" saga pattern and reuses the harness. Rejected: a new `scripts/validate_doc_formatting.py` in the Validate job (adds a script); deferring enforcement (risks drift in the gap).

KTD5 — Rollout covers all nine doc-writing skills (ideate, plan, brainstorm, spec, strategy, retro, doc-review, code-review, founder-review). Rejected: ideate-only exemplar (leaves the recurrence unsolved elsewhere); the seven issue-named skills only (code-review and founder-review also produce jumbled review docs).

KTD6 — The golden specimen is a worked EXAMPLE block embedded in `formatting-style.md`, not a separate fixture file. Rationale: one artifact serves as the few-shot the templates point to, the human reference, and the test oracle — nothing extra to drift.

KTD7 — The journal `DECISIONS.md` / `LEARNINGS.md` entries land in the shipping commit (via `/work`), not at plan time. Rationale: reconciles the plan engine's "record KTDs to the journal" with the global rule that journal entries ship in the same commit as the change. The plan doc holds the KTDs in the interim.

KTD8 — The `saga` plugin version bumps minor, 0.19.0 → 0.20.0 (additive shared reference + format rules across skills). The `plugin.json` version and a new `CHANGELOG.md` entry are part of the work; the missing 0.19.0 CHANGELOG entry is backfilled in the same pass. The `marketplace.json` metadata version (2.4.0) bumps only if the marketplace validator requires it.

## High-Level Technical Design

The contract is one reference plus a link from each skill, gated by one test.

**The shared reference** (`saga/references/formatting-style.md`) is the single source of truth. It states each rule (R1–R7) in prose, gives a when-to-use decision for table vs prose vs bold-labels (KTD2), and ends with one fully-rendered worked example (R9 / KTD6) that the skills point to as a few-shot and the test asserts against.

**Each doc-writing skill** links the shared reference from its template/present-phase file (the `saga/references/...`-by-path convention already in use) and applies the rules to its own artifact shape. Skills with compact ranked schemas (ideate ideas, code-review findings) adopt the field table; skills with prose-heavy per-unit fields (plan) keep headings + blank-separated labels.

**The pytest gate** (`tests/test_saga_doc_formatting.py`) scans the in-repo templates for the fatal collapse pattern and the checkable structural rules, asserts every doc-writing skill links the shared reference, and asserts the specimen conforms. It runs in the existing Tests job — no CI wiring change.

```text
saga/references/formatting-style.md  (rules + when-to-use + golden specimen)
        ▲ linked by path
        ├── skills/ideate/references/{ideation-artifact,convergence-and-partnership}.md
        ├── skills/plan/references/plan-sections.md
        ├── skills/brainstorm/references/requirements-sections.md
        ├── skills/spec/references/spec-template.md
        ├── skills/strategy/references/strategy-template.md
        ├── skills/retro/references/retro-report.md
        ├── skills/doc-review/SKILL.md  (report format; no references dir)
        ├── skills/code-review/references/findings-schema.md
        └── skills/founder-review/references/review-modes.md
        ▼ gated by
tests/test_saga_doc_formatting.py  (collapse pattern + structural rules + link presence + specimen)
```

## Implementation Units

### U1. Author the shared formatting reference + golden specimen

- **Goal:** Create `saga/references/formatting-style.md` — the single source of truth for R1–R7 plus the worked example (R9).
- **Requirements:** R1, R2, R3, R4, R5, R6, R7, R9.
- **Dependencies:** none (foundation).
- **Files:** `plugins/saga/references/formatting-style.md` (new).
- **Approach:** State each rule as a short prose paragraph with a tiny before/after. Add a when-to-use decision for table (compact/comparable fields) vs prose (narrative) vs blank-separated bold labels under `###` (prose-heavy per-unit fields). Encode the no-hard-wrap soft-wrap rule and the kill-redundant-title rule. End with one fully-rendered specimen idea + a specimen ranked-comparison table that the templates reference as a few-shot and U6 asserts against.
- **Patterns to follow:** `plugins/saga/references/operator-choice.md` and `saga-spec.md` for plugin-level reference tone/structure; `plan-sections.md:105-108` for the headings-not-list-items rule to fold in.
- **Test scenarios:** `Test expectation: none -- reference content; structurally validated by U6 (specimen-conforms assertion).`
- **Verification:** The file exists, states R1–R7, and contains a specimen block that passes U6.

### U2. ideate — fix the triggering exemplar

- **Goal:** Rewrite ideate's artifact + present-phase to the contract (this is the issue's triggering case).
- **Requirements:** R1, R2, R3, R4, R5, R7; link R6.
- **Dependencies:** U1.
- **Files:** `plugins/saga/skills/ideate/references/ideation-artifact.md`, `plugins/saga/skills/ideate/references/convergence-and-partnership.md`, `plugins/saga/skills/ideate/SKILL.md` (add the shared-ref link).
- **Approach:** Convert the SURVIVOR SCHEMA from the consecutive bold-label stack to a lead-in one-liner + prose (description/rationale/downsides) + a compact field table (basis-tag/confidence/complexity/axis/status); drop the redundant `**title:**` row (the `### N.` heading carries it). Apply the same to the Phase 4 "present the survivors" shape in `convergence-and-partnership.md`. Keep the existing non-survivor and co-ideation tables.
- **Patterns to follow:** `saga/references/formatting-style.md` specimen (U1); the existing tables at `ideation-artifact.md:63-67` and `:81-86`.
- **Test scenarios:** `Test expectation: none -- template content; validated by U6 + manual regen per issue #201 verification block.`
- **Verification:** A regenerated ideation doc leads each survivor with a one-liner, renders the schema as a table, and has no consecutive bold-label collapse.

### U3. plan — align the already-near-compliant template

- **Goal:** Bring `plan-sections.md` fully onto the contract and link the shared reference.
- **Requirements:** R2, R5, R6; preserve existing R7-style heading rule.
- **Dependencies:** U1.
- **Files:** `plugins/saga/skills/plan/references/plan-sections.md`, `plugins/saga/skills/plan/SKILL.md` (shared-ref link).
- **Approach:** Add the lead-in one-liner rule for units/sections and the soft-wrap rule; link the shared reference as the canonical formatting authority; confirm the per-unit fields stay as blank-separated bold labels under `### U<N>` headings (already correct — KTD2's prose-heavy branch). No render change to units.
- **Patterns to follow:** the shared reference (U1); the existing `### U<N>` heading rule at `plan-sections.md:105-108`.
- **Test scenarios:** `Test expectation: none -- template content; validated by U6.`
- **Verification:** `plan-sections.md` links the shared ref and U6 passes against it.

### U4. brainstorm + spec + strategy — the WHAT/direction templates

- **Goal:** Apply the contract to the three requirements/direction templates and link the shared reference.
- **Requirements:** R1, R2, R3, R5, R6.
- **Dependencies:** U1.
- **Files:** `plugins/saga/skills/brainstorm/references/requirements-sections.md`, `plugins/saga/skills/spec/references/spec-template.md`, `plugins/saga/skills/strategy/references/strategy-template.md`, and each skill's `SKILL.md` (shared-ref link).
- **Approach:** Add lead-in summaries per section, blank-line-separated short paragraphs, table/bullets for any comparative or enumerated data, and the soft-wrap rule; link the shared reference. Preserve each artifact's required section markers and frontmatter contracts.
- **Patterns to follow:** the shared reference (U1).
- **Test scenarios:** `Test expectation: none -- template content; validated by U6.`
- **Verification:** All three templates link the shared ref and U6 passes.

### U5. retro + doc-review + code-review + founder-review — the review/retro outputs

- **Goal:** Apply the contract to the review and retro output formats and link the shared reference.
- **Requirements:** R1, R2, R3, R4, R5, R6.
- **Dependencies:** U1.
- **Files:** `plugins/saga/skills/retro/references/retro-report.md`, `plugins/saga/skills/doc-review/SKILL.md` (the findings/readiness report format, ~lines 128-156 — no references dir), `plugins/saga/skills/code-review/references/findings-schema.md`, `plugins/saga/skills/founder-review/references/review-modes.md`, plus each skill's `SKILL.md` shared-ref link where the format lives elsewhere.
- **Approach:** Render findings (severity/priority/confidence/location) as a table per KTD2; lead each report section with a one-liner; apply short-paragraph + soft-wrap rules; link the shared reference. Keep the P0–P3 priority semantics and findings-schema field names intact.
- **Patterns to follow:** the shared reference (U1); the existing findings table conventions in `code-review/references/findings-schema.md`.
- **Test scenarios:** `Test expectation: none -- template/format content; validated by U6.`
- **Verification:** All four outputs link the shared ref and U6 passes.

### U6. The pytest enforcement gate

- **Goal:** Add `tests/test_saga_doc_formatting.py` so the rules cannot regress.
- **Requirements:** R8, R9.
- **Dependencies:** U1, U2, U3, U4, U5 (the templates must conform before the gate goes green).
- **Files:** `tests/test_saga_doc_formatting.py` (new); `tests/conftest.py` (only if a shared fixture helps).
- **Approach:** Enumerate the saga template/format files; assert none contains 2+ consecutive `**label:**` lines with no intervening blank line (the fatal collapse pattern); assert each of the nine doc-writing skills links `saga/references/formatting-style.md`; assert the `formatting-style.md` specimen block itself passes the collapse check; where cheaply checkable, assert ranked-survivor/findings sections use a table. Do NOT assert no-hard-wrap on template source (KTD3).
- **Patterns to follow:** `tests/test_saga_plugin.py`, `tests/test_saga_saga.py` for harness/style; ruff 100-char, pytest.
- **Test scenarios:**
  - **Happy path:** all conforming templates → test passes.
  - **Collapse detection:** a fixture string with 2+ consecutive `**x:**` lines, no blanks → flagged.
  - **Link presence:** a skill missing the shared-ref link → flagged; all nine present → passes.
  - **Specimen self-check:** the `formatting-style.md` example block passes the same collapse rule.
  - **Edge:** templates with legitimate single bold-label lines separated by blanks → not flagged (no false positive).
- **Verification:** `uv run pytest tests/test_saga_doc_formatting.py -v` passes; deliberately reintroducing the run-on stack in a template makes it fail.

### U7. Record — journal, changelog, version

- **Goal:** Land the durable record and the version bump with the shipping commit (KTD7).
- **Requirements:** supports R6 (durability of the convention).
- **Dependencies:** U1–U6.
- **Files:** `docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`, `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json` (only if the marketplace validator requires a metadata bump).
- **Approach:** DECISIONS entry for the formatting contract (rationale, CommonMark collapse, consumer = LLM+human, the table + no-hard-wrap choices, revisit-when). LEARNINGS entry for the validation finding (the templates claimed a field-parser contract that does not exist). Bump `plugin.json` 0.19.0 → 0.20.0; add a 0.20.0 CHANGELOG entry and backfill the missing 0.19.0 entry. Validate `marketplace.json` with `python3 -m json.tool` if touched.
- **Patterns to follow:** existing DECISIONS/LEARNINGS entry format; `plugins/saga/CHANGELOG.md` style; the marketplace.json editing guard (read the array end first; validate after).
- **Test scenarios:** `Test expectation: none -- docs/config; validated by existing validate_plugins.py + marketplace validator + ruff in CI.`
- **Verification:** CI Validate + Lint + Tests stay green; the journal carries both entries.

## Scope Boundaries

**Out of scope (non-goals, per issue #201):**

- Changing analytical content or the divergent→convergent engine — only how output is presented.
- Removing the structured idea-ready / findings schema — only visually separating it.
- A vocabulary / plain-language rewrite — that is a separate concern; this is strictly visual structure.

**Deferred to follow-up work:**

- A richer markdownlint / CI-Validate integration beyond the targeted pytest (add if the pytest proves too narrow).
- Any live-preview or `/pulse`-style rendering of saga docs.

## Risks & Dependencies

- **Risk — table render misapplied to prose-heavy fields.** Mitigation: KTD2's explicit when-to-use guidance plus worked examples in the shared reference (U1); plan units explicitly stay in the prose/heading branch.
- **Risk — pytest false-positives on legitimate template prose.** Mitigation: the gate checks only the fatal structural patterns (consecutive bold-label collapse, link presence, specimen), not soft-wrap; start narrow and widen deliberately.
- **Risk — format drift across the nine skills under parallel fan-out.** Mitigation: every skill links the one shared reference and points to the single golden specimen; U6 gates all of them.
- **Dependency — ordering.** U2–U5 depend on U1; U6 depends on U1–U5; U7 depends on all. The nine-skill edits (U2–U5) are mutually independent and parallelizable (the cc-workflows-ultracode fan-out).

## Alternatives Considered

- **Two-file `.fields.yaml` sidecar** (ideation R1) — rejected: there is no field-level parser to serve, and it doubles artifacts while breaking the one-doc model.
- **Full serializer that generates docs from structured data** (ideation R2) — rejected: saga docs are LLM-authored narrative, not pure data, so a serializer cannot author the prose; too expensive as a full replacement. The narrow idea (render only the machine block deterministically) is unnecessary given KTD2's table.

## Success Metrics

The issue #201 acceptance criteria, restated as the done-bar:

- A regenerated ideation/plan/review doc shows ≤3-sentence blank-separated paragraphs, a one-line lead-in per ranked item/section, comparative data as a table, and the schema visually distinct (R1–R5).
- The rules live in `saga/references/formatting-style.md` and all nine skills link it (R6).
- `tests/test_saga_doc_formatting.py` passes and fails on a reintroduced collapse (R8); the specimen conforms (R9).

## Sources / Research

- `docs/ideation/2026-06-07-saga-doc-readability-ideation.md` — the origin ideation (six survivors, the validation finding).
- `plugins/saga/skills/ideate/references/ideation-artifact.md:43-53` — the verified collapse; `:63-67`, `:81-86` — existing tables.
- `plugins/saga/skills/plan/references/plan-sections.md:105-108` — the headings-not-list-items precedent.
- `plugins/saga/references/` — the shared-reference home; `doc-review/SKILL.md:58`, `spec/SKILL.md:141` — the `saga/references/...`-by-path link convention.
- `plugins/saga/scripts/parse_issue.py` — parses issue bodies only (no ideation-field parsing); `handoff/SKILL.md:53-57` — directory → maturity routing.
- `.github/workflows/ci.yml` — Tests / Validate / Lint jobs (the pytest lands in Tests).
