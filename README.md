# Infiquetra Claude Plugins

Claude Code plugins for Infiquetra development workflows.

## Available Plugins

| Plugin | Description | Category |
|--------|-------------|----------|
| [parallel-test-runner](plugins/parallel-test-runner/) | Run pytest, ruff, mypy, bandit in parallel (4x faster) | Development |
| [docs-generator](plugins/docs-generator/) | Generate README, API specs, architecture docs | Development |

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

## Usage

### Parallel Test Runner
```bash
# Run all quality checks in parallel
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py

# With options
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py \
    --coverage 80 \
    --source-dir src \
    --test-dir tests \
    --verbose
```

### Docs Generator
```bash
# Generate all documentation
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate --all --service my-service

# Generate specific doc type
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate --type readme --service my-service
```

## Development

### Prerequisites
- Python 3.12+
- uv (recommended) or pip

### Setup
```bash
# Clone repository
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git
cd infiquetra-claude-plugins

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest
```

### Adding a New Plugin
See [docs/PLUGIN_SPEC.md](docs/PLUGIN_SPEC.md) for plugin development guidelines.

## License

MIT
