# Changelog — sdlc-manager

## [1.1.0] — 2026-05-04

### Added
- New `flow` subcommand group — operator-facing GraphQL + REST helpers:
  - `flow set-field` — set a single-select project field on a card (Initiative, Objective, Status, etc.)
  - `flow field-options` — list current options for a project field (live discovery, IDs not cached)
  - `flow discover-project` — resolve which project a repo maps to
  - `flow link-sub-issue` — link child as native sub-issue of parent (cross-repo, idempotent)
  - `flow verify-label` — self-healing label create (404 → create, exists → no-op, other errors raise)
  - `flow validate-card` — pre-flight check an existing issue body against the card_validator schema
- New `validate_card_body()` Python helper — mirrors home-lab card_validator.py's high-leverage checks (6 required H3 headers, AC has ≥1 checklist, Verification has ≥1 fenced code block, Files-expected has ≥1 path-like line, no placeholder-only sections)
- New `sdlc-flow` skill (SKILL.md) describing the `flow` commands + idempotency contract + hard rules + integration with the blueprint-to-issue workflow
- 20 tests in `tests/test_card_validator.py` and `tests/test_flow_subcommands.py` covering: validator schema rules, idempotency contracts, error classification (404 vs auth vs server), live-discovery vs cached, helpful error messages with current options listed

### Changed
- Renamed `beads_config` config-key to `legacy_rollout_config` in `load_config` and downstream readers (`board_wip`, `rollout_status`, `rollout_update`, `config_show`). The underlying file (`beads-config.json`) was already removed from infiquetra-sdlc on 2026-04-26; the key now degrades gracefully to `{}` for back-compat. Comment in `load_config` documents the migration.

### Removed
- `beads` subcommand group (`ready`, `claim`, `update`, `complete`, `status`)
- `_bd` shell helper for invoking the `bd` CLI
- All `beads_*` Python functions
- The Beads/Dolt coordination layer was removed from Mount Olympus on 2026-04-26 (see `infiquetra-sdlc/docs/engineering-journal/narratives/2026-04-26-beads-dolt-removed.md`); the agent fleet now coordinates via Redis pub/sub + GitHub Projects v2 + Discord per-card threads. The plugin's `beads` commands targeted infrastructure that no longer exists.

### Migration notes
- Operators previously running `sdlc_manager.py beads <action>` will get an `argparse` error. There is no replacement — the underlying coordination has moved off Beads entirely. Use `gh` + the new `flow` commands for direct board operations.
- The `flow set-field` command is the canonical mechanism for Initiative + Objective assignment per the 2026-05-03 DECISION (see `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md`). The fields don't exist on the Olympus board today; create them via the operator runbook in `operational-reference.md` before using `flow set-field`.

## [1.0.0] — 2026-03-29

### Added
- Initial release of sdlc-manager plugin for the Mount Olympus agent team
- Adapted from vecu-sdlc-manager, made organization-agnostic for Infiquetra
- 6 skills: sdlc-board, sdlc-issues, sdlc-labels, sdlc-metrics, sdlc-milestones, sdlc-rollout
- 4 commands: /sdlc-board, /sdlc-create, /sdlc-metrics, /sdlc-triage
- 1 agent: sdlc-operator
- Python CLI: sdlc_manager.py (zero external dependencies, gh CLI wrapper)
- New: beads resource group for Beads/Dolt task coordination
- Removed: Rally sync, GHE hostname requirements, Chainproofers/Identifiers team split
- Coordination model: Beads-first with GitHub Issues as backing store
- Notifications: Discord (not Slack)
- 2 project boards: Strategic Direction + Mount Olympus Operations
