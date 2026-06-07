---
date: 2026-06-07
topic: saga-doc-readability
focus: visual formatting / scannability of saga-generated documents (issue 201)
scope: standard
repo: infiquetra-claude-plugins
issue: 201
maturity: idea-ready
---

# Ideation: Saga Document Readability (Issue 201)

This document is itself written in the format issue 201 asks for — short blank-line-separated
paragraphs, a lead-in one-liner per idea, a comparison table, and machine fields kept on a compact
distinct line. It doubles as an early reference for survivor #6.

## Grounding Context

**Repo:** `infiquetra-claude-plugins`. The `saga` plugin (`plugins/saga/`) has ~19 skills; ~8–10 of
them write durable markdown to the user's repo (ideate, plan, brainstorm, spec, strategy, retro,
doc-review, code-review, founder-review). Formatting is governed by per-skill
`references/*-template.md` / `*-sections.md` files. There is **no shared formatting reference** today.

**Verified pain:** `plugins/saga/skills/ideate/references/ideation-artifact.md` (lines 43–53) renders
each idea as a stack of consecutive bold-label lines (`**title:** … **basis:** … **rationale:** …
**confidence:** …`) with no blank lines. CommonMark collapses consecutive non-blank lines into one
paragraph — the operator's verbatim "all jumbled together." `**title:**` also duplicates the
`### N.` heading directly above it.

**Precedent:** `plugins/saga/skills/plan/references/plan-sections.md` (~line 107) already forces
implementation units to be `### U<N>` headings, not list items, "because flush-left per-unit fields
detach from list items in CommonMark renderers." A sibling of this exact bug was solved once and
never propagated.

**Validation finding (corrects an assumption in the templates):** nothing machine-parses the per-idea
schema fields. `parse_issue.py` parses *issue bodies* only. `handoff` routes by directory →
`idea-ready` and reads frontmatter `maturity:`; `brainstorm`/`plan` consume the doc as an LLM reader,
with the human naming the survivor by title or `R#`. So seed S2's "machine-parseable" is real, but the
"machine" is an LLM plus a human — a table or fenced block is **more** legible, not a parse hazard.

**CI:** `.github/workflows/ci.yml` has Tests (pytest, `--cov=plugins`, Py 3.12), Validate
(`scripts/validate_plugins.py` + `marketplace/validator/validate.py`), and Lint (`ruff`). A template
lint extends Validate or adds a pytest; it checks the in-repo templates, which is where the rules live.

**Context-libraries:** None consulted — repo-bound topic.

## Topic Axes

- **A1** — Schema/field rendering (engineer-facing fields visually distinct yet legible to LLM + human)
- **A2** — Narrative prose shape (paragraph length, blank-line separation, lead-in summaries, soft-wrap)
- **A3** — Comparative/ranked data presentation (tables/bullets vs prose walls)
- **A4** — Rule location & propagation (shared reference vs per-template; reaching all ~8 skills)
- **A5** — Enforcement & regression-prevention (CI lint, golden-file specimen)

## At a Glance

The six survivors map to the six decisions a plan will have to make.

| # | Survivor | Axis | Decision it settles | Confidence | Complexity |
|---|----------|------|---------------------|:----------:|:----------:|
| 1 | Shared `formatting-style.md` + DECISIONS entry | A4 | *Where* the rules live | 90 | Low |
| 2 | Per-idea schema → table / fenced block | A1 | *How* the schema renders (the S2 fork) | 88 | Low–Med |
| 3 | Prose rules: short paras + lead-in + soft-wrap | A2 | *What* the narrative rules are | 82 | Low |
| 4 | Ranked survivors → comparison table | A3 | *How* ranked/compared data renders | 80 | Low |
| 5 | Template-format lint in CI | A5 | *What stops* regression | 78 | Med |
| 6 | Canonical golden specimen (triple-duty) | A5/A2 | *What "good"* looks like | 72 | Med |

## Ranked Survivors

### 1. Single shared `formatting-style.md` + a DECISIONS entry

**In one line:** One referenced file holds every formatting rule, so all ~8 doc-writing skills — and
the next new one — inherit it instead of each reinventing it.

The cost of having no shared reference is already visible: `plan` discovered the
headings-not-list-items rule, but `ideate` regressed into the run-on stack because the lesson never
propagated. One edit to a shared file improves every skill at once.

Pair it with a `DECISIONS.md` entry recording *why* (the CommonMark collapse, the consumer contract)
so a future maintainer does not quietly revert it.

- **axis:** A4
- **basis:** `direct:` `plan-sections.md:105-108` solved a sibling bug in isolation; grounding "no shared ref exists" + seed S1
- **rationale:** Highest leverage, lowest risk — the lesson was already paid for once; sharing it stops re-discovery and centralizes the rules so they cannot drift per template
- **downsides:** A linked reference is still per-run discretion until #5 gives it teeth
- **confidence:** 90 · **complexity:** Low · **status:** Unexplored

### 2. Render each idea's schema as a table (primary) or fenced block (alternative)

**In one line:** Move the compact engineer fields (basis-tag / confidence / complexity / axis /
status) into a two-column table or fenced block, keep the narrative fields as prose, and drop the
redundant `**title:**` row.

Tables never collapse in CommonMark and give a rigid, scannable, stable-key grid — satisfying "schema
visually distinct" and "comparative data as a table" at once. The validation finding makes this
low-risk: the consumer is an LLM plus a human, so a table reads better than the run-on stack.

Long prose fields (rationale, downsides) stay as prose paragraphs; only the compact fields tabularize.

- **axis:** A1
- **basis:** `direct:` `ideation-artifact.md:44-53` run-on stack + `:43-44` title duplication; verified no field-level parser exists
- **rationale:** A single native markdown construct solves the render-collapse, the legibility goal, and seed S2 simultaneously — no new code path required
- **downsides:** Prose-heavy fields read badly in table cells — must split compact fields (tabular) from narrative fields (prose)
- **confidence:** 88 · **complexity:** Low–Med · **status:** Unexplored

### 3. Narrative prose rules: short paragraphs + lead-in one-liner + soft-wrap

**In one line:** Codify ≤3-sentence blank-line-separated paragraphs, a required plain-language
one-liner opening every idea/section, and an explicit soft-wrap policy.

The lead-in one-liner restores — at item granularity — the readable Executive-Summary instinct the
current template dropped.

Soft-wrap is the one rule here with a genuine tradeoff: one-sentence-per-line (semantic line breaks)
fixes the "viewers jumble hard-wrapped lines" complaint and gives cleaner git diffs, but looks unusual
in a raw editor; "no hard wrap at all" is the simpler alternative.

- **axis:** A2
- **basis:** `direct:` issue 201 acceptance criteria + the historical dropped `## Executive Summary` block
- **rationale:** A consistent summary-first shape trains both human skimmers and any future summarizer to find the gist at a fixed position
- **downsides:** The soft-wrap choice (semantic line breaks vs no wrap) is a real tradeoff the plan must settle
- **confidence:** 82 · **complexity:** Low · **status:** Unexplored

### 4. Ranked survivors as a comparison table + a comparative-data rule

**In one line:** Put an at-a-glance survivor table up top (rank / confidence / complexity / axis /
one-liner) and reserve full prose for the few ideas that warrant a deep dive.

The artifact is backwards today — it already tables its *rejects* and co-ideation log but walls its
*winners* in prose stacks. Generalize the rule: any ranked, scored, or comparative content renders as
a table or bullets, never a prose wall.

- **axis:** A3
- **basis:** `direct:` `ideation-artifact.md:63-67` + `:81-86` already table non-survivor data; issue 201 AC requires comparative data as tables
- **rationale:** A reader scans confidence/complexity across all survivors in one glance instead of hunting bold labels down N prose blocks
- **downsides:** Table-as-index plus prose-as-detail can duplicate content — keep the table terse and the prose for depth only
- **confidence:** 80 · **complexity:** Low · **status:** Unexplored

### 5. Template-format lint in CI

**In one line:** A check in the Validate job (or a pytest) fails the build on the known-fatal pattern —
2+ consecutive `**label:**` lines with no blank line — plus a few structural rules.

This is what makes the fix stick: the plan→ideate recurrence proves prose conventions decay without
enforcement. It only needs to check the in-repo templates, which is exactly where the rules live.

Start narrow (the collapse pattern) to avoid false positives, then widen to "section opens with a
summary" and "ideas/units are headings."

- **axis:** A5
- **basis:** `direct:` `ci.yml` Validate job + issue 201 "rules encoded in templates not per-run discretion"
- **rationale:** Enforcement that compounds — once it exists, the ninth skill is blocked at PR time until its template conforms, with no human reviewer needed to remember the rule
- **downsides:** Structural markdown linting has false-positive risk — start minimal and widen deliberately
- **confidence:** 78 · **complexity:** Med · **status:** Unexplored

### 6. One canonical golden specimen, triple-duty

**In one line:** A single fully-rendered exemplar doc serves three jobs — the few-shot the templates
show the model, the human "what good looks like" reference, and the CI regression oracle.

"Match this shape" is a stronger forcing-function on an LLM than "follow these rules," because it
imitates layout it can see. The same file answers "what should a clean saga doc look like?" for humans
and pins the format against drift for CI.

- **axis:** A5 (with A2)
- **basis:** `reasoned:` few-shot-by-specimen beats per-field instruction; golden-file testing is the A5 enforcement variant offered in grounding
- **rationale:** One artifact serves documentation, onboarding, and the test oracle at once — leverage in three directions
- **downsides:** Goldens need upkeep when the format legitimately evolves — pair with #5 so the golden is not the only guard
- **confidence:** 72 · **complexity:** Med · **status:** Unexplored

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids and can be revived by
re-entering the Phase 3 filter with new evidence. Never renumber on a status change.

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Two-file `.fields.yaml` sidecar | Split human `.md` from a machine YAML file | Solves a parser that does not exist (verified); doubles artifacts + breaks the one-doc model — scope overrun | rejected |
| R2 | Full serializer generates docs | Render docs from structured data, no hand-formatting | Saga docs are LLM-authored prose, not data — cannot author narrative; too expensive as a full replacement (narrow version lives inside #2) | rejected |
| R3 | Auto-*derived* executive summary | Generate the summary mechanically from survivors | In a template-only fix the LLM authors both — not separately actionable without R2; folds into #3 | rejected |
| R4 | Kill `**title:**` as its own idea | Remove the field duplicating the heading | Correct but mechanical, below the meeting-test alone — absorbed into #2 | rejected |

**Rejection shape:** the two bold "range wide" swings (R1, R2) both died on the same verified fact —
there is no field-level parser to please, so heavyweight machine/human splits buy nothing the cheaper
render shapes do not. All five axes have surviving ideas.

## Co-ideation log

Records partnership provenance: operator seeds vs frame-agent ideas, and how each seed fared under the
identical critique.

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | S1 — single shared `formatting-style.md` | survived as #1 (built on by frames 1 & 4) |
| user-seed | Phase 0 | S2 — machine block stays parseable | constraint embodied in #2; refined by validation (consumer is LLM + human, no regex) |
| user-seed | Phase 0 | "range wide / surprise me" | produced the bold swings R1/R2, kept visible in the revivable cut |
| frame-agent | Phase 2 | table render of the schema | survived as #2 (independently surfaced by frames 1, 2, 3, 4) |
| frame-agent | Phase 2 | CI lint + golden specimen | survived as #5 and #6 |

## Suggested plan shape

Decisions #1 + #3 + #4 set the rules; #2 is the central render decision; #5 + #6 make it stick. #2 and
#5 carry the only real complexity — #1/#3/#4 are mostly mechanical once written. Sequence: write the
shared reference first (#1), encode the render + prose + table rules into it (#2/#3/#4), produce the
golden specimen (#6), then add the lint that checks against it (#5).
