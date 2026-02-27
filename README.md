# Infiquetra Claude Plugins

Claude Code plugins for Infiquetra development workflows.

## Available Plugins

| Plugin | Description | Category |
|--------|-------------|----------|
| [todoist-manager](plugins/todoist-manager/) | Full-featured Todoist integration for task and project management | Productivity |
| [pagerduty](plugins/pagerduty/) | PagerDuty incident management, on-call orchestration, and service CRUD | Operations |
| [slack](plugins/slack/) | Slack messaging and channel management | Communication |
| [splunk](plugins/splunk/) | Splunk log search and operational analysis | Operations |
| [identity-toolkit](plugins/identity-toolkit/) | Digital identity architecture (NIST 800-63, W3C VCs, custodial wallets) | Security |
| [test-suite](plugins/test-suite/) | Parallel Python quality checks: pytest, ruff, mypy, bandit | Development |
| [docs-generator](plugins/docs-generator/) | Automated README, API spec, and architecture documentation generation | Development |
| [python-toolkit](plugins/python-toolkit/) | Python patterns for serverless apps: Lambda Powertools, DynamoDB, error handling | Development |
| [sdk-lifecycle](plugins/sdk-lifecycle/) | SDK scaffolding, documentation, security review, and registry publishing | Development |

## Installation

### Option 1: Clone to Claude plugins directory
```bash
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git ~/.claude/plugins/infiquetra
```

### Option 2: Add marketplace to Claude settings
Add to `~/.claude/settings.json`:
```json
{
  "extraKnownMarketplaces": [
    {
      "name": "infiquetra-plugins",
      "url": "https://raw.githubusercontent.com/infiquetra/infiquetra-claude-plugins/main/.claude-plugin/marketplace.json"
    }
  ]
}
```

### Option 3: Symlink from local clone
```bash
ln -s /path/to/infiquetra-claude-plugins/plugins ~/.claude/plugins/infiquetra
```

## Usage Examples

### Todoist Manager
```bash
# Manage tasks via CLI
python3 plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py tasks list
python3 plugins/todoist-manager/skills/todoist-manage/scripts/todoist_client.py tasks add "Review PR" --project "Work"
```

### PagerDuty
Set environment variables first:
```bash
export PAGERDUTY_API_KEY="your-api-key"
export PAGERDUTY_DEFAULT_TEAM_ID="YOUR_TEAM_ID"
export PAGERDUTY_DEFAULT_ESCALATION_POLICY_ID="YOUR_POLICY_ID"
```

```bash
# List active incidents
python3 plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents list --status triggered

# Acknowledge an incident
python3 plugins/pagerduty/skills/pagerduty-incidents/scripts/pagerduty_client.py incidents acknowledge --id PXXXXX
```

### Test Suite
```bash
# Run all quality checks in parallel
python3 plugins/test-suite/skills/run-quality-checks/scripts/test_runner.py \
    --coverage 80 \
    --source-dir src \
    --test-dir tests
```

### Docs Generator
```bash
# Generate all documentation
python3 plugins/docs-generator/skills/generate-docs/scripts/docs_generator.py generate --all --service my-service
```

### Splunk
```bash
export SPLUNK_HOST="your-splunk-host"
export SPLUNK_TOKEN="your-token"

python3 plugins/splunk/skills/splunk-search/scripts/splunk_client.py search \
    "index=main level=ERROR earliest=-1h"
```

### Slack
```bash
export SLACK_BOT_TOKEN="xoxb-your-token"

python3 plugins/slack/skills/slack-messaging/scripts/slack_client.py message \
    --channel "#general" \
    --text "Deployment complete"
```

## Development

### Prerequisites
- Python 3.12+
- uv (recommended) or pip

### Setup
```bash
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git
cd infiquetra-claude-plugins

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .

# Run type checking
mypy plugins/
```

### Adding a New Plugin
```bash
# Use the scaffolding tool
./tools/create-plugin.sh my-new-plugin
```

See [docs/PLUGIN_SPEC.md](docs/PLUGIN_SPEC.md) for full plugin development guidelines.

## Plugin Structure

Plugins follow the Claude Code native plugin format:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json         # Plugin manifest
├── agents/                 # Agent definitions (optional)
│   └── agent-name.md
├── skills/                 # Skills (optional)
│   └── skill-name/
│       ├── SKILL.md        # Skill definition
│       ├── references/     # Reference documents
│       └── scripts/        # Implementation scripts
├── commands/               # Commands (optional)
│   └── command.md
├── README.md
└── CHANGELOG.md
```

## License

MIT
