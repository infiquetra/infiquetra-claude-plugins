# Changelog

All notable changes to the `redis-bridge` plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 0 scaffold: directory layout, plugin manifest, README, CHANGELOG.
- `PROTOCOL.md` canonical wire-format spec for redis-bridge ↔ router.
- `docs/STATE_MACHINE.md` routing-target state machine spec (router-side).
- `server/protocol.py` pydantic models pinning the wire format + destructive-tool classifier.
- `server/__main__.py` stub entry point.
- `tests/test_protocol.py` covering all protocol models and the `is_destructive` classifier.
- Agent coach file `agents/redis-bridge-coach.md` (descriptive — actual AskUserQuestion handling is intercepted in the MCP server, not coached).
- Skill metadata `skills/redis-bridge/SKILL.md`.
- Slash command stubs for connect / disconnect / list / rename / configure / mode.

### Not implemented yet (planned for later phases)

- MCP server loop (Phase 1).
- Redis presence/heartbeat (Phase 1).
- Inbound stream consumer + `notifications/claude/channel` emission (Phase 2).
- `reply` MCP tool (Phase 2).
- Permission relay + AskUserQuestion interception + audit logging (Phase 4).
