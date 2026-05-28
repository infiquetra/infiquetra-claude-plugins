---
name: blueprint-review
description: |
  Review a blueprint section or ADR using the idea-phase rubric library.
  Runs always-applicability core reviewers (problem_framing, assumption_audit,
  devils_advocate_blueprint, internal_consistency) and LLM-picked conditional
  extras. Findings appended to the review log: section-embedded markers for
  blueprint sections, peer-review folder for ADRs.
when_to_use: |
  Use this skill when the user wants to:

  Direct invocation:
  - "review this blueprint section"
  - "review section 4 of campps-context-library"
  - "review adr-001"
  - "review the executive-summary section"
  - "/blueprint-review path/to/file.md"

  Active iteration:
  - "I just rewrote the market-analysis section, can you review it?"
  - "what would devils_advocate_blueprint say about this draft?"
  - "what assumptions am I making in this technology-architecture section?"

  Pre-commit / pre-PR:
  - "before I commit, run a quick review on this blueprint change"
  - "this ADR is ready for review — can you run the rubrics?"

  Targeted reviewer:
  - "run only problem_framing on section 5"
  - "I want devils_advocate_blueprint and prior_art_check on this draft"

  Surveying scope:
  - "what reviewers fire on the idea phase?"
  - "what's in the binding_constraint rubric?"
---

# Blueprint Review

Run the idea-phase reviewer panel against a blueprint section or ADR,
producing scored findings with file:line citations and appending them
to the review log so provenance accumulates over time.

## Script Location

```
~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py
```

(During development, also at:
`~/workspace/infiquetra/infiquetra-claude-plugins/plugins/blueprint-reviewer/scripts/lifecycle_review.py`)

## Procedure

### 1. Identify the artifact

If the user pointed at a specific file, use it. Otherwise ask:
"which blueprint section or ADR should I review?" and accept either:

- A filesystem path (e.g. `discovery/blueprint/04-market-analysis.md`)
- An ADR id (e.g. `adr-003`) — search adjacent `adrs/` directories
  for `adr-003-*.md`
- A section number (e.g. `section 4`) — search for `04-*.md` under
  `discovery/blueprint/`

Determine artifact type:

- File under `adrs/` and matches `adr-NNN-*.md` → **ADR** (use peer-
  review folder convention)
- File under `discovery/blueprint/` or any blueprint section → **section**
  (use embedded review-log markers)

### 2. Read the artifact

Use the Read tool. If the section has existing review-log entries
(check for `<!-- review-log:start -->` markers), READ THEM TOO — the
review history is part of the context. Don't repeat findings that
were already raised + addressed in earlier reviews.

For ADRs: also list existing peer-reviews:

```bash
python3 <SCRIPT> adr-review list <adr-path>
```

### 3. Determine which reviewers run

**Always:** all idea-phase cores. Get the list:

```bash
python3 <SCRIPT> rubrics list-cores --phase idea
```

Today returns: `problem_framing`, `assumption_audit`,
`devils_advocate_blueprint`, `internal_consistency`.

**Conditionally:** pick 0-4 extras from the available list:

```bash
python3 <SCRIPT> rubrics list-extras --phase idea
```

You (the agent) pick. Read the artifact content, consider what kind
of decisions/claims it makes, and pick the extras whose questions
actually apply. Do not pick everything. Do not pick none if there are
clearly applicable ones.

Picking heuristics:

- Artifact contains directional decisions (tech, business model,
  go-to-market) without an explicit alternatives section →
  `alternatives_explored`
- Artifact reads as if the problem-space is novel → `prior_art_check`
- Artifact makes big predictions without falsification criteria →
  `falsifiability`
- Artifact discusses multiple constraints without naming a binding one →
  `binding_constraint`
- Artifact addresses 1 stakeholder when others clearly matter →
  `stakeholder_coverage`
- Artifact involves multi-party value flow → `incentive_audit`

If user specified specific reviewers, use only those (skip the picker).

### 4. Run each selected reviewer

For each reviewer:

```bash
python3 <SCRIPT> rubrics read --phase idea --slug <slug>
```

The output is the rubric. Apply it to the artifact:

1. Read the rubric's "What to look for" section
2. Walk through each item; cite specific lines/sections from the
   artifact
3. Score per the rubric's "Scoring" anchors (10 / 9 / 8 / 7 / ≤6)
4. Determine verdict: PROCEED (no required action), REVISE (specific
   changes named), or BLOCK (hard-stop reasons in rubric's "BLOCK
   only for")
5. Produce a structured finding:

```
Reviewer: <slug>
Score: X.X
Verdict: PROCEED | REVISE | BLOCK
Headline: <one-line summary suitable for review log>
Findings:
- <section/line>: <claim>
- <section/line>: <claim>
Required changes (if REVISE/BLOCK):
- <specific addition or fix>
```

### 5. Aggregate + present to user

Print a summary table FIRST, then per-reviewer details. Example:

```
## Review summary — discovery/blueprint/04-market-analysis.md

| Reviewer | Score | Verdict | Headline |
|---|---|---|---|
| problem_framing | 8.5 | PROCEED | framing solid; one assumption needs naming |
| assumption_audit | 7.0 | REVISE | 3 untracked assumptions in §4.2 |
| devils_advocate_blueprint | 8.0 | PROCEED | strong skepticism, but missing failure-mode for cohort-X |
| internal_consistency | 9.0 | PROCEED | clean |
| prior_art_check (extra) | 7.5 | REVISE | competitor Y's failure should be engaged |

## Detailed findings

### problem_framing (8.5, PROCEED)

...details with citations...

### assumption_audit (7.0, REVISE)

...details with citations...
```

### 6. Append to review log

For each reviewer that produced a finding, append to the review log.

**For blueprint sections:**

```bash
python3 <SCRIPT> log append-section <file> \
  --reviewer <slug> \
  --score <score> \
  --pr-url <url-if-any> \
  --headline "<one-line summary>"
```

**For ADRs:**

Write findings to a temp file first, then:

```bash
python3 <SCRIPT> adr-review write <adr-path> \
  --reviewer <slug> \
  --score <score> \
  --content-file <tmp-file> \
  --verdict <PROCEED|REVISE|BLOCK>
```

If invoked as part of a PR review (the user provided a PR URL or the
review is happening via a PR comment), pass `--pr-url`. Otherwise
omit and the entry will just have the headline + score.

### 7. Surface what's actionable

End your response with:

- **Action items** — REVISE/BLOCK findings that the user should
  address
- **Optional improvements** — PROCEED-with-nit findings (low priority)
- **What changed in the review log** — list of files updated

If user asked to skip the log update ("just review, don't write
anything"), omit step 6.

## Important: human-in-the-loop

This is an advisory review. **Do not move the artifact**, do not
auto-apply suggested changes, do not commit anything. Surface findings
+ append to review log; the human decides what to act on.

If the user wants you to APPLY a specific finding's REVISE suggestion,
that's a separate request — don't bundle apply with review.

## Targeted invocations

**Specific reviewers only:**
```
/blueprint-review path/to/section.md --reviewers problem_framing,prior_art_check
```
Skip the picker; run only the named reviewers.

**Cores only (skip extras):**
```
/blueprint-review path/to/section.md --cores-only
```

**Dry run (read rubrics, identify which would fire, but don't run them):**
```
/blueprint-review path/to/section.md --dry-run
```
List the reviewers that would fire + their headlines (no scoring).

## Score-band notes (idea phase calibration)

Idea-phase scores are NOT held to the 9.0 PROCEED floor that PR review
uses. Blueprints are inherently fuzzier:

- **8.0+** is healthy. Most well-formed blueprint sections will be in
  the 7.5–9.0 range.
- **<7.0** is a real concern; the reviewer's findings should be
  considered before downstream specs descend.
- **<6.0** suggests the section needs significant rework before it
  can be a basis for spec.

These are advisory anchors; the human integrates findings according
to their judgment.
