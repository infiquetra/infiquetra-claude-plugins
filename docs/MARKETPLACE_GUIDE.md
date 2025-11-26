# Marketplace Installation Guide

How to install and use plugins from the Infiquetra Claude Plugins marketplace.

## Installation Methods

### Option 1: Clone to Claude Plugins Directory (Recommended)

Clone the repository directly to Claude's plugins directory:

```bash
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git ~/.claude/plugins/infiquetra
```

**Pros**:
- Simple setup
- Easy to update (`git pull`)
- Works offline after initial clone

**Cons**:
- Manual updates required

### Option 2: Add Marketplace to Claude Settings

Add the marketplace to your Claude settings file:

```bash
# Edit ~/.claude/settings.json
```

Add the following:

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

**Note**: For private repositories, you'll need to configure GitHub authentication.

### Option 3: Symlink from Local Clone

If you have the repository cloned elsewhere:

```bash
# Clone to your preferred location
git clone git@github.com:infiquetra/infiquetra-claude-plugins.git ~/code/infiquetra-claude-plugins

# Symlink to Claude plugins directory
ln -s ~/code/infiquetra-claude-plugins/plugins ~/.claude/plugins/infiquetra
```

**Pros**:
- Keep code in your preferred directory structure
- Easy development and testing

## Verifying Installation

After installation, verify the plugins are available:

```bash
# Check parallel-test-runner
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py --help

# Check docs-generator
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py --help
```

## Using Plugins

### Parallel Test Runner

Run all quality checks in parallel:

```bash
# Basic usage
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py

# With options
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py \
    --coverage 80 \
    --source-dir src \
    --test-dir tests \
    --verbose

# JSON output for CI/CD
python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py \
    --output json \
    --output-file results.json
```

### Documentation Generator

Generate project documentation:

```bash
# Generate all docs
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate \
    --all \
    --service my-service

# Generate specific doc type
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py generate \
    --type readme \
    --service my-service

# Validate existing docs
python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py validate \
    --output docs
```

## Updating Plugins

### If Cloned Directly

```bash
cd ~/.claude/plugins/infiquetra
git pull origin main
```

### If Using Marketplace

Plugins update automatically when you restart Claude or refresh the marketplace.

## Troubleshooting

### Plugin Not Found

Check the installation path:

```bash
ls -la ~/.claude/plugins/
```

### Permission Denied

Make scripts executable:

```bash
chmod +x ~/.claude/plugins/infiquetra/*/src/*.py
```

### Missing Dependencies

Install plugin dependencies:

```bash
cd ~/.claude/plugins/infiquetra
uv pip install -e ".[dev]"
```

### Python Version

Ensure Python 3.12+ is available:

```bash
python3 --version
```

## Creating Aliases

Add convenient aliases to your shell configuration:

```bash
# Add to ~/.zshrc or ~/.bashrc

# Parallel test runner
alias ptest='python3 ~/.claude/plugins/infiquetra/parallel-test-runner/src/test_runner.py'

# Docs generator
alias docgen='python3 ~/.claude/plugins/infiquetra/docs-generator/src/docs_generator.py'
```

Then use:

```bash
ptest --coverage 80 --verbose
docgen generate --all --service my-service
```

## Support

For issues or questions:

1. Check the plugin's README for usage details
2. Review the [PLUGIN_SPEC.md](PLUGIN_SPEC.md) for development guidelines
3. Open an issue on GitHub
