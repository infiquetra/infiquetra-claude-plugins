---
name: blueprint-review
description: Review a blueprint section or ADR using the idea-phase rubric library
---

Run a multi-reviewer review of a blueprint section or ADR. Findings
get appended to the section's review log (or to the ADR's
peer-review folder).

## Usage

```
/blueprint-review [path-or-id] [--reviewers <slug,slug,...>] [--cores-only] [--dry-run]
```

## Arguments

- `path-or-id` — Path to a blueprint section file (e.g.
  `discovery/blueprint/04-market-analysis.md`), an ADR id (e.g.
  `adr-003`), or a section number (e.g. `section 4`). If omitted,
  the skill will ask.
- `--reviewers <slug,slug,...>` — Run only the named reviewers (skip
  the picker). Useful for targeted re-review.
- `--cores-only` — Run only the always-applicability cores; skip
  conditional extras.
- `--dry-run` — List which reviewers WOULD run, without scoring.

## Examples

```
/blueprint-review
/blueprint-review discovery/blueprint/04-market-analysis.md
/blueprint-review adr-003
/blueprint-review section 7 --cores-only
/blueprint-review adr-001 --reviewers prior_art_check,falsifiability
```

## What This Does

1. Loads the artifact (blueprint section or ADR) — auto-detects type.
2. Reads existing review-log entries to avoid repeating findings.
3. Runs the always-applicability **idea-phase cores**:
   `problem_framing`, `assumption_audit`, `devils_advocate_blueprint`,
   `internal_consistency`.
4. Picks 0–4 conditional extras based on artifact content (or uses
   user-specified `--reviewers` list).
5. Produces a summary table + per-reviewer findings with citations.
6. Appends each finding to the review log:
   - Blueprint sections → `<!-- review-log:start --> ... <!-- review-log:end -->` markers
   - ADRs → `adrs/reviews/<adr-id>/<date>-<reviewer>.md` files
7. Surfaces action items the user should address.

## Script Command

The skill invokes:

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  rubrics list-cores --phase idea
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  rubrics read --phase idea --slug <slug>
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  log append-section <file> --reviewer <slug> --score <N> --headline <headline>
# OR for ADRs:
python3 ~/.claude/plugins/cache/infiquetra-plugins/blueprint-reviewer/0.1.0/scripts/lifecycle_review.py \
  adr-review write <adr-path> --reviewer <slug> --score <N> --content-file <findings>
```

## Instructions

When the user invokes `/blueprint-review`:

1. If no path provided, ask which artifact.
2. Use the `blueprint-review` skill to drive the review procedure.
3. Output the summary table BEFORE per-reviewer details so the user
   can scan quickly.
4. Always end with action items + a list of files modified in the
   review log.

This is **advisory review** — do not auto-apply suggestions, do not
modify the artifact itself, do not commit. The human decides what
to act on.

## When NOT to use

- For PR review against the working repo (use the orchestrator's
  PR-review path or `/pr-review` if you have it)
- For the plan-phase agent review (the orchestrator handles that)
- For artifacts that aren't in the idea phase (use `/spec-review`
  for specs, `/issue-review` for GitHub issues)
