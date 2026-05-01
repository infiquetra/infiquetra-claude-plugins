# Changelog — blueprint-reviewer

## [0.1.0] — 2026-05-01

### Added

Initial release of the blueprint-reviewer plugin for Infiquetra's
upstream-of-PR review system.

**Phase A — rubric library** (24 markdown rubrics, organized by phase
and applicability tier):

- `rubrics/idea/` — 4 cores + 6 extras for blueprint sections + ADRs
- `rubrics/spec/` — 4 cores + 4 extras for implementation specs
- `rubrics/issue/` — 3 cores + 3 extras for GitHub issues

Each rubric carries YAML frontmatter declaring the phase(s) it fires
in and whether it's a core (always-runs) or LLM-picked conditional
extra.

Cross-cutting patterns:

- **Fidelity spine** — `blueprint_fidelity` (spec phase),
  `spec_fidelity` (issue phase) check artifact descent
- **Devils_advocate dynasty** — phase-tuned skeptics:
  `devils_advocate_blueprint`, `devils_advocate_spec`,
  `devils_advocate_issue`

**Phase B — manual-driven review skills**:

- `skills/blueprint-review/SKILL.md` — review blueprint sections + ADRs
- `skills/spec-review/SKILL.md` — review specs
- `skills/issue-review/SKILL.md` — review GitHub issues
- `commands/{blueprint,spec,issue}-review.md` — slash command entry points
- `scripts/lifecycle_review.py` — helper CLI with 8 subcommands
  (rubrics list/read, log append-section, ADR peer-review folder ops)

**Companion automation in home-lab orchestrator** (Phase C, not part of
this plugin) vendors these rubrics via
`home-lab/scripts/vendor_blueprint_rubrics.sh` and runs them
automatically on PR open against `*-blueprint` repos and on
issue-to-Backlog transitions on the Olympus project board. Both
manual + automated paths share the same rubric library so findings
are consistent.

### Conventions

- Section-embedded review log (blueprint sections, specs):
  `<!-- review-log:start --> ... <!-- review-log:end -->` markers
- Folder-of-peer-reviews (ADRs):
  `adrs/reviews/<adr-id>/<date>-<reviewer>.md`

See `docs/lifecycle/ideation-to-pr.md` in the `infiquetra-sdlc`
repository for the full lifecycle architecture.
