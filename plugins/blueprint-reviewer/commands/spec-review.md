---
name: spec-review
description: Review a specification using the spec-phase rubric library
---

Run a multi-reviewer review of an implementation spec. Findings get
appended to the spec's section-embedded review log.

## Usage

```
/spec-review [path] [--reviewers <slug,slug,...>] [--cores-only] [--dry-run]
```

## Arguments

- `path` — Path to a spec file (e.g.
  `campps-context-library/specs/registration/spec.md`). If omitted, the
  skill will ask.
- `--reviewers <slug,slug,...>` — Run only named reviewers.
- `--cores-only` — Skip conditional extras.
- `--dry-run` — List which reviewers WOULD run, without scoring.

## Examples

```
/spec-review
/spec-review specs/testing/testing-strategy.md
/spec-review specs/registration/spec.md --cores-only
/spec-review specs/onboarding/spec.md --reviewers blueprint_fidelity,outcome_clarity
```

## What This Does

1. Loads the spec.
2. Loads the parent blueprint section (if cited) so
   `blueprint_fidelity` can check actual descent.
3. Reads existing review-log entries to avoid repeating findings.
4. Runs the always-applicability **spec-phase cores**:
   `outcome_clarity`, `acceptance_testability`, `blueprint_fidelity`,
   `devils_advocate_spec`.
5. Picks 0–4 conditional extras based on spec content.
6. Produces a summary table + per-reviewer findings.
7. Appends each finding to the spec's review log markers.
8. Surfaces action items.

## Script Command

The skill invokes:

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  rubrics list-cores --phase spec
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  rubrics read --phase spec --slug <slug>
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  log append-section <spec-file> --reviewer <slug> --score <N> --headline <headline>
```

## Instructions

When the user invokes `/spec-review`:

1. If no path provided, ask.
2. Use the `spec-review` skill to drive the procedure.
3. **Critical:** find and read the parent blueprint section. If
   missing, that's a `blueprint_fidelity` finding — note it
   explicitly.
4. Output summary table first, details after.
5. End with action items + review-log changes.

This is **advisory review** — don't auto-apply, don't modify the
spec, don't commit. Human decides.

## Cross-phase note

If `blueprint_fidelity` finds a contradiction with the parent
blueprint, the right answer is rarely "fix the spec alone." It's
either:

1. Update the spec to comply, OR
2. Update the blueprint (with its own review cycle), OR
3. Add an ADR-supersession step.

Surface the trade-off; don't silently pick option 1.
