# Infiquetra Claude Plugins

Claude Code plugins for Infiquetra development workflows.

## Available Plugins

| Plugin | Description | Category |
|--------|-------------|----------|
| [deploy](plugins/deploy/) | Tag-promotion deploy, status, rollback, hotfix, and release-note workflows | Operations |
| [home-lab-ops](plugins/home-lab-ops/) | Proxmox VE cluster ops, Ansible pre-flight, Ceph, monitoring guard, and vault helper | Infrastructure |
| [mission-control](plugins/mission-control/) | SDLC workflow manager: boards, prepared issues, project fields, labels, metrics, milestones | Development |
| [redis-channel](plugins/redis-channel/) | Claude Code channel bridging sessions to external systems over Redis Streams | Development |
| [saga](plugins/saga/) | Engineering lifecycle: Think, Plan & execute, Hand off, Review, and Improve & route | Development |
| [team-execution](plugins/team-execution/) | Two-phase plan execution with reviewer consensus, validator gates, and nonprod automation | Development |
| [unifi](plugins/unifi/) | UniFi Network & Protect CLI: devices, clients, VLANs, firewall, cameras, PTZ, motion events | Infrastructure |

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

### Infiquetra Deploy
```bash
python3 plugins/deploy/scripts/mint_tag.py \
    --env nonprod \
    --version 1.2.3 \
    --dry-run
```

### Infiquetra Lifecycle
Commands carry work through five lifecycle phases:

- **Think:** `/office-hours`, `/ideate`, `/brainstorm`, `/strategy`
- **Plan & execute:** `/plan`, `/work`, `/qa`, `/retro`, `/resume`
- **Hand off:** `/handoff` → `mission-control`
- **Review:** `/founder-review`, `/ceo-review`, `/doc-review`, `/code-review`
- **Improve & route:** `/optimize`, `/loop`

Use `/loop` to route work to plan only, PR, merge, or nonprod deploy. Durable artifacts live in
repo docs such as `docs/plans/`, `docs/work-sessions/`, and `docs/engineering-journal/`; raw
runtime state stays under ignored `.claude/saga/`.

## Development

### Prerequisites
- Python 3.12+
- uv

### Setup
```bash
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git
cd infiquetra-claude-plugins

# Install dependencies
uv sync --locked --extra dev

# Run tests
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy plugins/
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
