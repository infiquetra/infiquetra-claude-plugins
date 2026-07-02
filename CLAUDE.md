# Claude Configuration for Infiquetra Claude Plugins

## 📓 Engineering journal — auto-maintain

Living journal at [`docs/engineering-journal/`](docs/engineering-journal/) (`LEARNINGS.md` / `DECISIONS.md` / `QUEUED.md` / `ARCHIVE.md` / `narratives/`). Follow the [shared engineering-journal practice](https://github.com/infiquetra/infiquetra-sdlc/blob/main/docs/process/engineering-journal.md) for the full pattern, and maintain it without being asked — capture durable learnings and decisions in the same commit that ships the change.

Repo-specific signals worth a `LEARNINGS.md` entry: marketplace registry drift, hook timing races, skill-activation gotchas, MCP env propagation, build-tool surprises. Plugin-pattern choices (skills-based vs CLI-based, version-bump strategy, hook event choice) belong in `DECISIONS.md`.

Any verify/review-class Agent-tool spawn made outside a saga skill must pass `subagent_type: saga:readonly-verifier` + `isolation: "worktree"` — see `plugins/saga/references/sandbox-spawn-sites.md` for the full spawn-site inventory and rationale.

## Repository Information

- **Repository**: infiquetra-claude-plugins
- **Purpose**: Claude Code plugins for Infiquetra development workflows
- **Organization**: Infiquetra

## Plugin Types

This repository contains two types of Claude Code plugins:

### Skills-based Plugins
Markdown-driven plugins that provide Claude with knowledge, patterns, and agent definitions. No Python scripts required.

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── agent-name.md       # Agent system prompt + trigger conditions
├── skills/
│   └── skill-name/
│       ├── SKILL.md        # Skill definition with frontmatter
│       └── references/     # Supporting reference documents (.md)
├── README.md
└── CHANGELOG.md
```

**Examples**: `saga`, `home-lab-ops`, `team-execution`

### CLI-based Plugins
Python CLI scripts wrapped as Claude skills/commands for interacting with external services.

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── agent-name.md
├── skills/
│   └── skill-name/
│       ├── SKILL.md
│       └── scripts/
│           └── service_client.py   # CLI implementation
├── commands/
│   └── command.md
├── README.md
└── CHANGELOG.md
```

**Examples**: `mission-control`, `unifi`, `deploy`, `redis-channel`

## Plugin Development Guidelines

### Naming Conventions
- Plugin directories: `kebab-case` (e.g., `redis-channel`)
- Python files: `snake_case` (e.g., `unifi_network_client.py`)
- Classes: `PascalCase` (e.g., `UnifiNetworkClient`)
- Skill names in frontmatter: `kebab-case` (e.g., `unifi-network`)

### Code Quality Standards
- Python 3.12+ required
- Type hints enforced with mypy
- Ruff linting with 100-character line limit
- Minimum 80% test coverage
- Security scanning with bandit

### Testing Requirements
- Unit tests for all CLI-based plugins (in `tests/` at repo root)
- Test files named `test_<plugin_client>.py`
- Use pytest as the test framework
- Add shared fixtures to `tests/conftest.py`

### plugin.json Required Fields
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Clear description of what the plugin does",
  "author": {
    "name": "Infiquetra",
    "email": "hello@infiquetra.com"
  },
  "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
  "keywords": ["relevant", "tags"]
}
```

## Development Workflow

1. Scaffold plugin: `./tools/create-plugin.sh my-plugin`
2. Implement in appropriate structure (skills-based or CLI-based)
3. Write tests in `tests/` for CLI plugins
4. Document in README.md
5. Add entry to `.claude-plugin/marketplace.json`
6. For every plugin behavior, schema, command, prompt, or user-facing guidance change, update the
   plugin release surfaces in the same PR: `plugins/<plugin>/.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json`, `plugins/<plugin>/CHANGELOG.md`, and any version/metadata
   drift guard tests. Do not treat code/tests as PR-ready until installed-plugin metadata tells the
   same story as the diff.
7. Submit PR for review

## Running Quality Checks

```bash
# Run all checks
uv run pytest

# Run specific test file
uv run pytest tests/test_deploy_plugin.py -v

# Run linting
uv run ruff check .

# Run type checking
uv run mypy plugins/

# Run security scan
uv run bandit -r plugins/
```

## Scaffold New Plugin

```bash
./tools/create-plugin.sh my-new-plugin
```
