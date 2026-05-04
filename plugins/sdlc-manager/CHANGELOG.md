# Changelog — sdlc-manager

## [1.2.0] — 2026-05-04

### Added (Phase C deferred — Foundation)

- **Typed exception classes** (`GhApiError`, `ApiNotFound`, `ApiAlreadyExists`, `ApiRateLimited`, `ApiAuthError`, `CardValidationError`). `_gh` now raises the appropriate subclass via `_classify_gh_error` instead of bare `RuntimeError` with a stringy message. Replaces the fragile `"422" in str(e)` substring matching pattern. Downstream callers catch by type:
  ```python
  try:
      _rest_post(...)
  except ApiAlreadyExists:
      # idempotent re-run — treat as success
  ```
  The `flow_link_sub_issue` and `flow_verify_label` helpers were refactored to use this pattern. `flow_verify_label` also now handles a real race (two operators creating the same label simultaneously) via `ApiAlreadyExists` on POST.
- **Per-user defaults file** at `~/.claude/sdlc-defaults.json`. Stores: `assignee` (gh login from `gh api user --jq .login` — *not* OS `$USER`), `default_project`, `default_status`, `default_priority`, `default_initiative`, `default_objective`, `preferred_repos`. Sticky across CLI invocations; future interactive flows read defaults as suggestion values.
  - `load_user_defaults()` / `save_user_defaults()` helpers (atomic write via tempfile + rename; tolerant of missing file + malformed JSON)
  - `get_default(key)` convenience reader
  - New subcommands:
    - `config show-defaults` — display current per-user defaults
    - `config init-defaults [--non-interactive]` — first-run wizard. Interactive by default; `--non-interactive` seeds from `gh api user` + auto-detects `default_project` if exactly one project is mapped (no guessing on multi-project orgs).
- **Vendored `project-mappings.json`** at `plugins/sdlc-manager/config/project-mappings.json`. The plugin now works without an external `infiquetra-sdlc` checkout for canonical Infiquetra projects.
  - New `_resolve_project_mappings(sdlc_path)` helper implements the documented resolution order: external override (`$INFIQUETRA_SDLC_PATH/config/project-mappings.json`) → vendored canonical → remote `gh api` fallback.
  - Project node IDs captured in the vendored file are best-effort + verified 2026-05-04. Field/option IDs are NEVER cached; always fetched live.

### Tests
- 33 new tests across 3 new test files:
  - `test_typed_exceptions.py` (15 tests) — status-code parsing (404/401/403/429/422 disambiguation), 422-already-exists vs 422-validation-failure distinction, integration with `flow_link_sub_issue` + `flow_verify_label` (including race detection)
  - `test_user_defaults.py` (13 tests) — read-side (missing file, malformed JSON, non-object root, unset key), write-side (atomic via tmpfile+rename, parent-dir auto-create, round-trip), `--non-interactive` wizard (gh-login seeded, multi-project no-guess, preserves unknown future keys)
  - `test_project_mappings_resolution.py` (5 tests) — override wins over vendored, vendored used when no override, remote fallback when neither, empty dict on all-three failure, vendored file declares expected canonical state
- Updated 3 PR #114 tests in `test_flow_subcommands.py` to use typed exceptions instead of bare `RuntimeError` with string-matching (the old pattern was testing the old implementation; new tests test the new contract).
- Total: **64 / 64 passing** locally.

## [1.1.0] — 2026-05-04

### Fixed (during PR #114 review)
- **`validate_card_body` header text**: was `"Out-of-scope or non-goals"` (with "or"); home-lab card_validator.py and ALL actionable issue templates use `"Out-of-scope / non-goals"` (with "/"). Every real card would have failed validation with a phantom missing-section error. Corrected to match home-lab exactly. Same iteration also corrects `_PATH_LINE_RE` (now accepts plain filenames + bullet-prefixed paths matching home-lab) and `_CHECKLIST_RE` (now requires `\S` after `[ ]` and accepts `*` bullets matching home-lab).
- **Drift-guard test**: added `test_required_headers_match_actual_issue_templates` that loads the real issue templates and verifies every `_REQUIRED_H3_HEADERS` entry has a matching `label:` in capability/enhancement/defect.yml. This is the test that would have caught the original "or" vs "/" bug.
- **Pre-existing test breakage**: `tests/test_sdlc_manager.py` had a `TestBeadsClaim` class referencing the deleted `beads_claim` function. Class deleted; CHANGELOG note added in the test file.
- **WIP-limits test fixture**: was using the old `beads_config` config-key (which now degrades to `{}`); the override test passed only by coincidence. Renamed fixture to `legacy_rollout_config`; tightened assertion to verify the OVERRIDDEN column (Ready) renders with the override limit, not just any column happening to have a "5" in its render.
- **`flow_validate_card` exit-code path**: was calling `sys.exit(1)` directly, bypassing main()'s formatted-error path and breaking programmatic callers. Now raises `CardValidationError` (RuntimeError subclass) which main() catches; preserves the standard CLI exit code behavior + lets future callers inspect the failure.
- **`_resolve_project_field` error message**: now includes a hint pointing at the field-creation runbook in `infiquetra-sdlc/docs/operations/operational-reference.md` when a field doesn't exist.
- **Stale `# BEADS` banner**: removed (Beads removal had left an empty banner in the argparse section).
- **Duplicate `import re`**: removed (validator block had a redundant import; top-level `import re` at line 61 already covers it).
- **Unused `project_id_check` variable**: replaced with `_, items = ...` discard idiom (consistent with `board_wip` pattern).
- **README.md**: removed the "Beads coordination" capability bullet + stale `bd` CLI prerequisite + stale `Beads Operations` section + stale `config/beads-config.json` row. Added `Flow Operations` section with the 6 new commands.

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
