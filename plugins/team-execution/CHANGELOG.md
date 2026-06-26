# Changelog - team-execution

All notable changes to this plugin are documented here.

---

## [2.2.0] - 2026-06-26

### Changed
- **R8 reshape to a native-agent-teams wrapper.** Removed every tmux reference **in this plugin** (the
  validators run as native agent-team subagents, not tmux panes): deleted `commands/team-setup.md` (the
  entire `/team-setup` command), `docs/example_tmux.conf`, `docs/agent-overflow.sh`, and
  `skills/.../references/validator-pane-behavior.md`. No tmux reference remains in this plugin outside
  this CHANGELOG's history notes. (Pre-existing repo-root tmux dev-tooling under `docs/` is unrelated
  to team-execution and out of R8's plugin-scoped charter.)
- **Re-homed the `.claude/`-git-ignored validator-state safety check** into the execution skill's
  pre-execution phase (new Step B0a preflight) so it survives the `/team-setup` deletion — it now runs
  in BOTH Phase A planning (Step A5) and Phase B preflight. `validator-evidence-state.md` remains the
  state-location contract.
- **First real backend behind the OutcomeOrchestrator dispatcher seam** (R5/R6): team-execution is
  dispatchable as a leaf backend with a return channel; an unavailable backend emits a visible
  HALT-not-degrade receipt rather than silently substituting (R23). (Coordinator wiring lives in the
  saga plugin's `outcome_dispatcher.py`.)
- Replaced the `test_team_setup_references_existing_assets` guard with
  `test_team_setup_and_tmux_assets_are_removed` (KTD13 — the deletion's own guard).

---

## [2.1.0] - 2026-06-20

### Changed
- Teammate agents now run on role-appropriate models instead of all inheriting the
  session model: the 10 reviewers on **Opus** (deep judgment), the 8 testers on
  **Sonnet**, and the 7 scanners/monitors on **Haiku** (mechanical tool-running).
  Set per agent via the `model:` frontmatter; any agent can be returned to `inherit`
  to track the session model. Reasoning effort is unchanged (session-level).

---

## [2.0.0] - 2026-05-27

### Added
- Validators are now a first-class umbrella alongside workers and reviewers.
- Added scanner, tester, monitor, and operational validator roster:
  `deploy-watcher`, `security-scanner`, `iac-cost-scanner`, `api-compat-scanner`,
  `dependency-scanner`, `smoke-tester`, `scenario-tester`, `api-contract-tester`,
  `sdk-regression-tester`, `event-flow-tester`, `ui-regression-tester`,
  `performance-tester`, `concurrency-tester`, `github-actions-monitor`, and
  `runtime-monitor`.
- Added validator reference docs for registry, criteria, execution order, evidence/state
  format, spawn quirks, and pane behavior.
- Added optional `.team-execution.json` guidance for `required_validators`,
  `disabled_validators`, `nonprod_workflows`, `scenario_hints`, and `smoke_targets`.
- Added guarded nonprod automation rules for Infiquetra repositories.
- Added `appsec-audit` skill for URL/input trust-boundary review, SSRF-style risk,
  redirects, metadata endpoints, allowlists, and evidence-backed findings.
- Added packaged `/team-setup` tmux assets:
  `docs/example_tmux.conf` and `docs/agent-overflow.sh`.

### Changed
- Phase A now derives a team plan from repo type, changed files, workflows, contracts,
  docs, tests, and optional `.team-execution.json`.
- Phase B order is now workers, reviewer consensus, scanners, PR/CI/nonprod coordination,
  testers, monitors, then completion.
- Reviewer non-consensus blocks validators unless the user explicitly overrides.
- Hard-fail scanner/tester findings block auto-merge, nonprod deploy, and completion.
- Remediation is capped at 3 loops before escalation.
- Plugin and marketplace metadata bumped to `2.0.0`.

### Removed
- Removed stale migration notes from the initial release entry.

---

## [1.5.0] - 2026-03-29

### Fixed
- Workers pack into 2x2 grids, while reviewers get solo windows.
- Shift+Down and Shift+Up require the tmux prefix, preserving terminal-app behavior.
- Window creation bells are silenced.
- Windows are named after agents.
- Window management with many agents adds prefix+w and prefix+f helpers.

### Changed
- Overflow routing uses a stable tmux window ID and delayed pane-title routing.
- tmux configuration documents the window layout model.

---

## [1.4.0] - 2026-03-29

### Fixed
- Workers no longer prompt the user for permissions; review cycles enforce quality.
- Agent overflow treats the main window differently from agent overflow windows.

### Changed
- Worker rows use `bypassPermissions` mode.
- Step B1 is the worker kickoff step.

---

## [1.3.0] - 2026-03-29

### Changed
- Skill auto-suggests during plan mode for non-trivial plans.
- Natural-language triggers include agent-team phrasing.
- The user can decline team planning for the current session.

---

## [1.2.0] - 2026-03-29

### Added
- Environment pre-flight checks for the handoff rule, tmux environment, and settings.
- `/team-setup` wizard for setup validation and guided fixes.
- Dismissible tmux checks.

---

## [1.1.0] - 2026-03-29

### Changed
- Phase A submits the plan as one atomic artifact.
- Phase B entry constraints require the team handoff as the first action.

---

## [1.0.0] - 2026-03-25

### Added
- Initial release of the `team-execution` plugin.
- Two-phase execution model: Phase A during planning, Phase B direct orchestration.
- `team-execution` skill.
- `/team-execute` slash command.
- 3 base reviewers always present:
  - `devils-advocate-reviewer`: assumptions, edge cases, failure modes.
  - `security-reviewer`: OWASP, secrets, auth/authZ, and PII coverage.
  - `architecture-reviewer`: design patterns, separation of concerns, and conventions.
- 7 optional reviewers triggered by context:
  - `infra-reviewer`: cloud infrastructure.
  - `api-reviewer`: API design, versioning, and deprecation.
  - `testing-reviewer`: test coverage and patterns.
  - `code-quality-reviewer`: DRY, complexity, naming, and patterns.
  - `privacy-reviewer`: privacy by design and PII handling.
  - `clarity-reviewer`: documentation clarity.
  - `ai-usefulness-reviewer`: AI-consumability of specs and issues.
- Reference files for reviewer registry, review criteria, and consensus protocol.
- Plan triage escape hatch for trivial config-only changes.
- Plan type classification for code, docs/specs, and mixed plans.
