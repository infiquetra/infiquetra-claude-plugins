# Changelog — sdlc-manager

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
