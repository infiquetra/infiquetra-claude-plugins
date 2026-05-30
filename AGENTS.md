# Codex Configuration for Infiquetra Claude Plugins

## 📓 Engineering journal — AUTO-MAINTAIN

Living documentation at [`docs/engineering-journal/`](docs/engineering-journal/) — pattern adopted from `infiquetra/home-lab/docs/engineering-journal/`. The directory IS the engineering journal; the files inside are its sections.

| File | Purpose |
|------|---------|
| [LEARNINGS.md](docs/engineering-journal/LEARNINGS.md) | Empirical findings + mechanisms + fixes + validations |
| [DECISIONS.md](docs/engineering-journal/DECISIONS.md) | ADR-style records of plugin-pattern / convention / tooling choices, with rationale + revisit conditions |
| [QUEUED.md](docs/engineering-journal/QUEUED.md) | Future-work items by priority with "worth it when" triggers |
| [ARCHIVE.md](docs/engineering-journal/ARCHIVE.md) | Shipped + rejected + superseded items |
| [narratives/](docs/engineering-journal/narratives/) | Self-contained, longer-form companion docs (plugin design walkthroughs, multi-PR post-mortems, migration write-ups) — readable cold by an outside reader |

**Maintenance rules (Codex: follow these without being asked):**

1. **After fixing a plugin bug or shipping a feature where the mechanism wasn't obvious** (marketplace registry drift, hook timing race, skill activation gotcha, MCP env propagation, build-tool surprise) → add a dated entry to `LEARNINGS.md`. Include the **evidence** (PR / commit / file:line) and the **mechanism** (why it happened, not just what), and a **Generalizable rule** line stripping the lesson from the specific incident.

2. **After committing a plugin-pattern decision** (skills-based vs CLI-based, line length, lockfile choice, marketplace category, version bump strategy, hook event choice, naming convention) → add an entry to `DECISIONS.md` with rationale + rejected alternatives + "revisit when" condition. Include the commit hash.

3. **Whenever a promising idea surfaces but we don't build it right now** (new plugin idea, CI guard, refactor, test improvement) → add to `QUEUED.md` with priority (P0/P1/P2/P3/Maybe), concrete "worth it when" trigger, and rough effort estimate. Don't skip this step — undocumented good ideas decay into forgotten good ideas.

4. **When a QUEUED item ships** → move its entry to `ARCHIVE.md` as SHIPPED with the commit hash + date. Remove it from `QUEUED.md`.

5. **When a QUEUED item is rejected** (we decide it's not worth doing) → move to `ARCHIVE.md` as REJECTED with the reason + revisit conditions. Remove from `QUEUED.md`.

6. **When a prior LEARNING or DECISION is invalidated** (new evidence contradicts the old claim) → update the original entry inline with the correction AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED. Never silently overwrite history.

7. **When something needs a longer write-up than fits in an entry** (full plugin design narrative, multi-PR post-mortem, migration write-up, rejected-design memo) → create `docs/engineering-journal/narratives/YYYY-MM-DD-short-slug.md` and link to it from the relevant LEARNINGS / DECISIONS entry. The four core files stay scannable; long-form companion lives next door.

**Entry format.** Each of the four core files has a block-quote intro at the top spelling out its format. New entries use these subheaders where applicable: **Context / Evidence / Mechanism / Fix (or queued) / Validation / What surprised / Generalizable rule / Refs**. Not every entry needs every subheader, but the **Generalizable rule** line is the highest-value field — without it, future-Codex has to re-derive the lesson from the evidence each time.

**Don't wait to be asked.** When any of these triggers fire in a session, update the files as part of the same commit that ships the change. The whole point of these files is that they maintain themselves.

## Repository Information

- **Repository**: infiquetra-claude-plugins
- **Purpose**: Claude Code plugins for Infiquetra development workflows
- **Organization**: Infiquetra

## Plugin Types

This repository contains two types of Claude Code plugins:

### Skills-based Plugins
Markdown-driven plugins that provide Codex with knowledge about Claude Code plugin structure,
patterns, and agent definitions. No Python scripts required.

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
Python CLI scripts wrapped as Claude Code skills/commands for interacting with external services.

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
uv run pytest

# Run specific test file
uv run pytest tests/test_pagerduty_client.py -v

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
