# Changelog

## [1.2.0] - 2026-06-21

### Changed
- `homelab-sre` agent: pin `model: opus` in frontmatter (R1/R2a tiering; judgment-heavy SRE
  diagnosis warrants the richest model).

## [1.1.0] - 2026-06-01

### Added
- `team-scaffold` skill — stands up a new infiquetra agent-team repo end-to-end
  (context-library-compliant skeleton + Discord/GitHub identity gates + split-vault
  wiring + Ansible deploy harness). Promotes the polyrepo-migration generators
  (`gen_harness.py`, `vault_split.py`) into a tested `team_scaffold` Python package
  with a golden test that reproduces all 12 live `infiquetra/team-*` repos
  byte-for-byte, plus a `team_profiles.yml` validator calibrated against every
  live team config. Closes acceptance criterion #7 of the home-lab polyrepo migration.

## [1.0.0] - 2026-03-17

### Added
- `ansible-preflight` skill with `common-mistakes.md` reference — catalog of fix patterns extracted from home-lab commit history
- `proxmox-operations` skill with `proxmox-cli-quirks.md`, `ceph-operations.md`, `vm-lifecycle.md` references — PVE 9.x and Ceph Squid 19.x operational knowledge
- `inventory-sync` skill with `inventory-schema.md` reference — hardware change checklists and variable dependency map
- `monitoring-guard` skill with `metric-registry.md` reference — exporter metric names and dashboard validation
- `vault-helper` skill with `vault-patterns.md` reference — Ansible Vault workflows and secret scaffolding
- `homelab-sre` agent — cross-cutting SRE investigation agent combining all skills
