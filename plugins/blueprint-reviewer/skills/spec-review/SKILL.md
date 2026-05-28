---
name: spec-review
description: |
  Review a specification using the spec-phase rubric library. Runs core
  reviewers (outcome_clarity, acceptance_testability, blueprint_fidelity,
  devils_advocate_spec) and LLM-picked conditional extras. Findings
  appended to the spec file's section-embedded review log.
when_to_use: |
  Use this skill when the user wants to:

  Direct invocation:
  - "review this spec"
  - "review specs/testing/testing-strategy.md"
  - "/spec-review path/to/spec.md"

  Active iteration:
  - "I drafted a spec for the registration outcome — review it"
  - "what's the cheapest way to defeat this spec?"
  - "is the measurement plan adequate?"

  Pre-PR review:
  - "before I open the PR for this new spec, review it"

  Targeted reviewer:
  - "run blueprint_fidelity on this spec — does it descend cleanly?"
  - "I want only the cores; skip extras"

  Surveying:
  - "what reviewers fire on the spec phase?"
  - "what does outcome_clarity actually check?"
---

# Spec Review

Run the spec-phase reviewer panel against an implementation spec,
producing scored findings and appending them to the spec's
section-embedded review log.

## Script Location

```
~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py
```

(During development, also at:
`~/workspace/infiquetra/infiquetra-claude-plugins/plugins/blueprint-reviewer/scripts/lifecycle_review.py`)

## Procedure

### 1. Identify the spec

If the user pointed at a path, use it. Otherwise ask: "which spec
should I review?" Specs live at:

- `<blueprint-repo>/specs/<area>/<spec>.md`

E.g. `campps-context-library/specs/testing/testing-strategy.md`.

### 2. Read the spec + its parent blueprint section

Read the spec content. Critically: **find and read the parent
blueprint section the spec descends from**. The spec should cite
its source. If it doesn't, that's already a `blueprint_fidelity`
finding.

Common patterns for finding the parent:
- Spec frontmatter `source:` field pointing at a blueprint section
- Inline cite: "Source: [Section X.Y of blueprint](...)"
- README in the parent specs/ directory naming the source

Reading the parent enables `blueprint_fidelity` to check actual
descent (terminology, decision alignment, scope subset).

Read existing review-log entries in the spec (look for
`<!-- review-log:start -->` markers). Don't repeat findings already
addressed.

### 3. Determine which reviewers run

**Always:** all spec-phase cores. Get the list:

```bash
python3 <SCRIPT> rubrics list-cores --phase spec
```

Today returns: `outcome_clarity`, `acceptance_testability`,
`blueprint_fidelity`, `devils_advocate_spec`.

**Conditionally:** pick 0-4 extras:

```bash
python3 <SCRIPT> rubrics list-extras --phase spec
```

Picking heuristics:

- Spec defines a measurable outcome but no measurement plan section →
  `measurement_plan`
- Spec title has conjunctions ("and", "&", "with") OR ACs serve
  multiple distinct outcomes → `scope_unity`
- Spec depends on (or unblocks) other in-flight work → `dependency_mapping`
- Spec proposes an experiment, MVP, pilot, or phased rollout →
  `ramp_down_criteria`

### 4. Run each selected reviewer

For each reviewer:

```bash
python3 <SCRIPT> rubrics read --phase spec --slug <slug>
```

Apply the rubric to the spec. Score, verdict, findings, required
changes. Same shape as blueprint review (see the blueprint-review
skill for the structured-finding template).

Notes specific to spec-phase reviewers:

- **outcome_clarity** is strict — score down for direction-without-
  threshold or output-instead-of-outcome ACs.
- **acceptance_testability** is the strictest version of "ACs are
  clear" — applied at spec time, where fuzz can still be removed
  cheaply. Imagine reading just the AC text with no context.
- **blueprint_fidelity** requires the parent blueprint section to be
  read. If it wasn't found, score down and explain in findings.
- **devils_advocate_spec** specifically asks: cheapest way to defeat
  this? Worst version that still satisfies ACs? Predecessor failures
  cited?

### 5. Aggregate + present to user

Same summary-table-first format as blueprint review. Example:

```
## Review summary — campps-context-library/specs/registration/spec.md

| Reviewer | Score | Verdict | Headline |
|---|---|---|---|
| outcome_clarity | 9.0 | PROCEED | outcome measurable; window specified |
| acceptance_testability | 8.0 | REVISE | AC #4 needs methodology |
| blueprint_fidelity | 9.5 | PROCEED | clean descent from §4 |
| devils_advocate_spec | 7.5 | REVISE | "feature-engagement-conditional" metric loophole |
| measurement_plan (extra) | 8.5 | PROCEED | baseline cited; instrumentation in scope |
```

### 6. Append to review log

```bash
python3 <SCRIPT> log append-section <spec-file> \
  --reviewer <slug> \
  --score <score> \
  --pr-url <url-if-any> \
  --headline "<one-line summary>"
```

For each reviewer with a finding worth recording. PR-url is included
when invoked from a PR context.

### 7. Surface action items

End with:

- **Action items** (REVISE/BLOCK)
- **Optional improvements** (PROCEED nits)
- **Review log changes** — files modified

## Important: human-in-the-loop

Same as blueprint review: surface findings, append to review log,
**don't** apply changes or move the spec. Human decides.

## Targeted invocations

```
/spec-review path/to/spec.md --reviewers outcome_clarity,blueprint_fidelity
/spec-review path/to/spec.md --cores-only
/spec-review path/to/spec.md --dry-run
```

## Score-band notes (spec phase calibration)

Spec phase is more concrete than idea phase, so expect tighter scores:

- **9.0+** is healthy. Specs should be sharper than blueprints.
- **8.0–8.9** is normal during active iteration; one or two REVISE
  items.
- **<7.5** likely needs work before issues descend.
- **<6.0** suggests the spec is premature — kick it back to the
  drafter for sharpening, OR escalate questions back to the parent
  blueprint.

These are advisory; the human still decides what to address.

## Cross-phase note: when blueprint_fidelity blocks

If `blueprint_fidelity` finds a contradiction with the parent
blueprint, the right answer is rarely to fix the SPEC alone — it's
either:

1. Update the SPEC to comply with the blueprint, OR
2. Update the BLUEPRINT (with its own review cycle) to authorize
   the spec's direction, OR
3. Add an ADR-supersession step to formally override.

Surface this trade-off; don't silently pick option 1.
