# Claude Configuration for Infiquetra Claude Plugins

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

**Examples**: `identity-toolkit`, `python-toolkit`, `sdk-lifecycle`, `docs-generator`, `test-suite`

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

**Examples**: `pagerduty`, `slack`, `splunk`, `todoist-manager`

## Plugin Development Guidelines

### Naming Conventions
- Plugin directories: `kebab-case` (e.g., `python-toolkit`)
- Python files: `snake_case` (e.g., `splunk_client.py`)
- Classes: `PascalCase` (e.g., `SplunkClient`)
- Skill names in frontmatter: `kebab-case` (e.g., `splunk-search`)

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
6. Submit PR for review

## Running Quality Checks

```bash
# Run all checks
pytest

# Run specific test file
pytest tests/test_pagerduty_client.py -v

# Run linting
ruff check .

# Run type checking
mypy plugins/

# Run security scan
bandit -r plugins/
```

## Scaffold New Plugin

```bash
./tools/create-plugin.sh my-new-plugin
```
