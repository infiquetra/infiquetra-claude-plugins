# blueprint-reviewer

Multi-phase artifact review for the Infiquetra SDLC. Extends the
review system upstream of PR/plan into the earlier lifecycle phases
where mistakes are cheapest to fix.

## The expanded lifecycle

```
IDEATION ─► BLUEPRINT ─► SPECIFICATION ─► ISSUE ─► PLAN ─► PR
              repo:        spec.md         GH       (today's   (today's
              campps-      outcome doc     issue    review)    review)
              blueprint
              mimir-
              blueprint
```

Each transition is where things go wrong. This plugin contributes
**rubrics** for the three new phases (idea, spec, issue) plus the
**fidelity spine** that connects them. The plan and PR phases are
already covered by reviewers in the home-lab orchestrator.

## What's in this plugin

### Rubrics

The canonical rubric library lives under `rubrics/`. Each rubric is a
markdown file with YAML frontmatter declaring which phase(s) it fires
in and whether it's an always-runs core or an LLM-picked extra.

| Phase | Cores (always run) | Extras (LLM-picked conditional) |
|---|---|---|
| **Idea** (blueprints) | problem_framing, assumption_audit, devils_advocate_blueprint, internal_consistency | alternatives_explored, prior_art_check, falsifiability, binding_constraint, stakeholder_coverage, incentive_audit |
| **Spec** | outcome_clarity, acceptance_testability, blueprint_fidelity, devils_advocate_spec | measurement_plan, scope_unity, dependency_mapping, ramp_down_criteria |
| **Issue** | devils_advocate_issue, spec_fidelity, acceptance_criteria_clarity | issue_sizing, context_completeness, prerequisite_mapping |

### Two consumers

1. **Manual review skill** (this plugin's `skills/blueprint-review/`) —
   for ad-hoc deep-dive review of a blueprint section, spec, or issue.
   Used during active iteration when the human is in the loop.

2. **Home-lab orchestrator** (vendors rubrics from this repo) — for
   automated PR-driven review of changes to blueprint repos
   (`*-blueprint`), spec PRs in those repos, and issue review on
   transition to `Backlog` on the Olympus project board.

The two paths share the same rubric library so there's a single
source of truth for "what does a good blueprint section look like?"
and equivalent questions for specs and issues.

## The fidelity spine

A reviewer at every transition checks whether the artifact descends
faithfully from its parent:

| Reviewer | Phase | Question |
|---|---|---|
| `blueprint_fidelity` | spec | Does this spec descend from a blueprint? |
| `spec_fidelity` | issue | Does this issue serve a spec? |
| `plan_fidelity` | pr | Does this PR implement the plan? *(home-lab, existing)* |

This is the connective tissue that catches scope drift across phases.

## The devils_advocate dynasty

Every phase has a phase-tuned skeptic:

- `devils_advocate_blueprint` — challenge the framing
- `devils_advocate_spec` — challenge the outcome definition
- `devils_advocate_issue` — challenge the work definition
- `devils_advocate` *(home-lab, existing)* — challenge the plan

Each one shares the role ("argue the opposite, find the cracks") but
with a phase-specific rubric calibrated to that artifact's failure
modes.

## Review log convention

Reviews accumulate as provenance. Two patterns depending on artifact:

**Section-embedded** (blueprint sections, specs):

```markdown
## Section: <name>

(content here)

<!-- review-log:start -->
### Review log
- 2026-05-01 — problem_framing v1 (8.5) — [comment](url) — "..."
- 2026-05-08 — devils_advocate_blueprint v2 (7.0) — [comment](url) — "..."
<!-- review-log:end -->
```

**Folder-of-reviews** (ADRs, where reviews are formal artifacts):

```
adrs/
  adr-001-flutter-application-platform.md
  reviews/
    adr-001/
      2026-05-01-devils_advocate_blueprint.md
      2026-05-01-prior_art_check.md
      2026-05-08-assumption_audit.md
```

## Status

Phase A foundation: rubrics + plugin skeleton in place. Phase B
(manual skill) and Phase C (automated PR review in home-lab) are
the next layers.

## See also

- Lifecycle architecture: `infiquetra-sdlc/docs/lifecycle/ideation-to-pr.md`
- Home-lab orchestrator (plan/PR phase reviewers + vendoring): `home-lab/ansible/roles/hermes_orchestrator/`
- Sister plugin (SDLC management — board, issues, labels): `plugins/sdlc-manager/`
