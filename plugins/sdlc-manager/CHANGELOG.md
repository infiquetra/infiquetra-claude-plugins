# Changelog — sdlc-manager

## Unreleased

### Changed
- Synced `sdlc-issues` template guidance with canonical issue forms in `infiquetra-sdlc`, including current Hermes actionable labels and required card sections.
- Added a deterministic template documentation generator plus drift guard tests for `templates-reference.md`.

## [1.4.0] — 2026-05-04

### Migration notes
- **No breaking changes.** The `sdlc-operator` Claude Code subagent (`agents/sdlc-operator.md`) was rewritten to reflect 2026-05-04 reality (Phase C minimum-viable + foundation + interactive flow are all merged). Operators using the prior subagent will see the same trigger phrases but newer command examples.

### Changed (Phase C deferred — sdlc-operator subagent rewrite)
- **`agents/sdlc-operator.md`** — full rewrite. The previous version was authored before Phase C; it referenced removed concepts:
  - Beads/Dolt CLI (`bd ready`, `bd claim`, etc. — removed in PR #114; coordination is now Redis pub/sub + GitHub Projects v2 + Discord per-card threads)
  - "2 project boards" (Strategic Direction + Mount Olympus — Strategic Direction was dropped in PR #16 from `infiquetra-sdlc`; Mount Olympus is the only board)
  - `labels sync-fields` command (deprecated — Initiative/Objective are project fields, not labels per PR #16 in `infiquetra-sdlc`. The command itself still exists in the script for back-compat; `flow set-field` is the canonical mechanism. Removing the command is queued for a follow-up after a deprecation cycle.)
  - `initiative:*` / `objective:*` colon-prefixed labels (anti-pattern; removed in PR #11)
- **The rewrite reflects the cumulative Phase C work** — references the `flow` subcommand group (PR #114), per-user defaults file + typed exceptions (PR #115), the sub-issue-first interactive `issue create` flow (PR #116). Each workflow pattern (full issue lifecycle, board grooming, new initiative/objective setup, objective tracking, blueprint-driven batch creation, triage) updated to use the canonical `flow set-field` / `flow link-sub-issue` / `flow verify-label` / `flow validate-card` helpers.
- The `Today's reality (2026-05-04)` callout is repeated in the agent's docstring + the issue-create workflow section — an operator using the agent learns immediately that today only `Status` is a single-select field on the Olympus board, and the `flow` helpers will silently skip prompts for the other fields until they're created via the runbook.

Plugin manifest: 1.3.0 → 1.4.0. **All deferred Phase C items are now closed.**

## [1.3.0] — 2026-05-04

### Migration notes
- **No breaking changes.** Existing `issue create --repo X --type Y` invocations work identically; new behavior is additive.
- The new flow is interactive by default. Pass `--skip-metadata` for the prior thin-wrapper behavior (just open browser, no post-create work).
- Operators who ran `config init-defaults` (Phase C foundation) get personalized prompt defaults automatically.

### Added (Phase C deferred — Interactive `issue create` rewrite)

The `issue create` subcommand was rewritten as a sub-issue-first, per-project-schema-aware, defaults-driven, capability-adaptive interactive flow. Replaces the previous thin wrapper that just deferred to `gh issue create --web`.

The 10-step flow:
1. Determine type (decision-tree prompt if `--type` not set; default from `~/.claude/sdlc-defaults.json` if present)
2. **Sub-issue-first prompt**: every new card has a parent by default. Operator pastes a `repo#N` ref or types `no` for free-floating
3. Discover which project the repo maps to (per-user `default_project` preferred, else first match)
4. **Per-project schema discovery**: for each candidate field (Initiative, Objective, Status, plus capability-adaptive ones), check if the project actually exposes the field. Silently skip prompts for fields that don't exist
5. Prompt for field values, defaults seeded from `~/.claude/sdlc-defaults.json` (e.g., `default_initiative`, `default_objective`)
6. **Capability-adaptive fields**: for `capability` or `objective` types only, AND only when the project exposes them, prompt for `Capability Size`, `Business Value`, `Technical Risk`, `Target Quarter`
7. Open `gh issue create --repo X --template <type>.yml --web` in the browser; operator fills the body
8. Operator pastes back the issue number (URL or bare integer accepted); skip post-create metadata if blank
9. **Apply post-create metadata**, each step isolated:
   - `hermes-task` for actionable types / `hermes-not-actionable` for objective
   - `board add` to the project board
   - `flow set-field` for each gathered field value
   - `flow link-sub-issue` if a parent was set
10. **Paired-card prompt** (opt-in, default no): create a sibling card on a different repo with the same parent. Useful for cross-service capabilities (backend + Flutter app)

### New CLI flags
- `--parent-ref <repo#N>`: pre-supply the parent ref (skips the sub-issue prompt — useful for batch-create scripts)
- `--skip-metadata`: skip steps 2-10 entirely, just open the browser. Returns to the prior thin-wrapper UX

### New helpers (composable for tests + scripts)
- `_select_issue_type(default=None)` — decision-tree prompt with EOF-safe fallback
- `_prompt_parent_issue()` — sub-issue-first prompt; parses `repo#N` or `yes` followed by ref
- `_project_field_options(project_name, field_name)` — per-project schema discovery; returns None if field doesn't exist (caller skips silently)
- `_prompt_choice(label, options, default)` — generic field-value prompt with options listed + default + `-` to skip
- `_open_gh_issue_create_web(repo, issue_type)` — browser launch helper
- `_prompt_issue_number(repo)` — captures URL or bare int from operator
- `_apply_post_create_metadata(...)` — orchestrates label / board / fields / sub-issue link with per-step error isolation
- `_prompt_paired_card(repo, issue_number)` — opt-in paired-card prompt; returns target/title/body deltas or None

### Tests
- 23 new tests in `tests/test_issue_create_interactive.py` covering each helper in isolation:
  - `_select_issue_type`: typed choice, default-on-blank, garbage-fallback, EOF-safe
  - `_prompt_parent_issue`: direct ref, yes-then-ref, blank-then-ref, no, garbage-warns, EOF
  - `_prompt_choice`: skip-when-no-field, valid option, default-on-blank, dash-skip, invalid-warns
  - `_prompt_paired_card`: default-no, yes-collects-deltas, yes-empty-target-aborts
  - `_apply_post_create_metadata`: hermes-task for actionable, hermes-not-actionable for objective, label-failure-doesnt-abort-others, no-project-skips-fields-but-keeps-link
  - `_PARENT_REF_RE`: realistic refs accepted; `#42`, `repo-only`, garbage rejected
- Total: **92 / 92 passing**

## [1.2.0] — 2026-05-04

### Migration notes
- **No breaking changes.** Existing CLI invocations work identically.
- **Recommended one-time setup**: run `python3 sdlc_manager.py config init-defaults` after upgrading to seed `~/.claude/sdlc-defaults.json` with your gh login + project defaults. Future Phase C PRs will read these as suggestion values in the interactive `issue create` flow.
- **External override still wins**: if you have `$INFIQUETRA_SDLC_PATH/config/project-mappings.json`, it continues to take precedence over the new vendored copy.
- **Exception class names changed (PEP 8 / N818)**: `ApiNotFound` → `ApiNotFoundError`, `ApiAlreadyExists` → `ApiAlreadyExistsError`, `ApiRateLimited` → `ApiRateLimitedError`. Backward-compat aliases retained for the old names; can be removed in a follow-up after a deprecation cycle.

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
