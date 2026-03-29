# Changelog — team-execution

All notable changes to this plugin are documented here.

---

## [1.2.0] — 2026-03-29

### Added
- **Step A0: Environment Pre-flight** in SKILL.md — checks CLAUDE.md handoff rule, tmux environment, and Claude settings before Phase A begins
- **`/team-setup` command** — standalone setup wizard that validates environment, offers to install tmux config + overflow script, configures Claude settings, and manages CLAUDE.md handoff rule
- tmux checks are opt-out: users can dismiss permanently, re-enable with `/team-setup reset`
- Checks Claude `settings.json` for `teammateMode` and `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`

## [1.1.0] — 2026-03-29

### Changed
- Phase A now calls `ExitPlanMode` itself (new Step A5) — plan is a single atomic artifact
- Added Critical Constraints block at Phase B entry: TeamCreate is the ONLY permitted first action
- Strengthened CLAUDE.md auto-handoff rule with explicit prohibitions against Agent tool usage

## [1.0.0] — 2026-03-25

### Added
- Initial release of the `team-execution` plugin (ported from vecu-team-execution v2.0.0, made organization-agnostic)
- Two-phase execution model: Phase A during plan mode, Phase B orchestrated directly by Claude
- `team-execution` skill: Phase A team planning + Phase B orchestration protocol
- `/team-execute` slash command
- 3 base reviewers always present:
  - `devils-advocate-reviewer` (red): challenges assumptions, edge cases, failure modes
  - `security-reviewer` (orange): OWASP/secrets/auth/PII coverage
  - `architecture-reviewer` (purple): design patterns, separation of concerns, convention adherence
- 7 optional reviewers triggered by keyword detection:
  - `infra-reviewer` (blue): CDK/AWS/Lambda/DynamoDB
  - `api-reviewer` (green): API design/versioning/deprecation
  - `testing-reviewer` (yellow): test coverage/patterns
  - `code-quality-reviewer` (cyan): DRY/SOLID/complexity/naming
  - `privacy-reviewer` (pink): privacy by design/PII/GDPR
  - `clarity-reviewer` (teal): docs readability/structure/understandability
  - `ai-usefulness-reviewer` (gold): AI-consumability of specs/issues
- Reference files:
  - `reviewer-registry.md`: keyword trigger map for optional reviewers
  - `review-criteria.md`: scoring rubrics for all reviewer types
  - `consensus-protocol.md`: 3-iteration process, scoring thresholds, escalation
- Plan triage escape hatch for trivial config-only changes
- Plan type classification: code vs docs/specs vs mixed
- Claude acts as orchestrator directly — no separate execution-lead agent needed

### Changed from vecu-team-execution v2.0.0
- Removed `execution-lead` agent — Claude orchestrates directly
- Replaced `adr-reviewer` with `architecture-reviewer` (project-agnostic pattern/convention review)
- Removed all organization-specific ADR path dependencies
- Removed hardcoded ADR references (ADR-005, ADR-006, ADR-013, ADR-027)
- Updated all file paths to `team-execution/` prefix
- Updated author and repository metadata to Infiquetra
