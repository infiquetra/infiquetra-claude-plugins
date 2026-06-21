# Changelog

## 0.1.2 - 2026-06-21

- `release-orchestrator` agent: pin `model: sonnet` in frontmatter (R1/R2a tiering;
  release coordination is structured/procedural — Sonnet is the right cost-quality tier).

## 0.1.0 - 2026-05-29

- Add Infiquetra tag-promotion deploy commands and deploy-state skill.
- Add release orchestrator guidance for rollback, hotfix, status, and release notes.
- Add deterministic helpers for tag naming, deployment status drift, and release-note preview.
- Preserve VECU deploy safety mechanics source-neutrally: version inference, hotfix refs,
  rollback tags, existing-tag rejection, dry-run protection, and unhealthy snapshot quarantine.
