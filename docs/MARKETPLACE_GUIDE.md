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
# Check deploy
python3 ~/.claude/plugins/infiquetra/deploy/scripts/mint_tag.py --help

# Check unifi
python3 ~/.claude/plugins/infiquetra/unifi/skills/unifi-network/scripts/unifi_network_client.py --help
```

## Using Plugins

Each plugin documents its own usage in its `README.md`. Two quick examples:

### Deploy

```bash
# Preview a tag-promotion release (dry run)
python3 ~/.claude/plugins/infiquetra/deploy/scripts/mint_tag.py \
    --env nonprod \
    --version 1.2.3 \
    --dry-run
```

### UniFi Network

```bash
# Discover available commands (dry-run by default)
python3 ~/.claude/plugins/infiquetra/unifi/skills/unifi-network/scripts/unifi_network_client.py --help
```

For the saga lifecycle commands (`/plan`, `/work`, `/code-review`, …) and the other plugins, see each plugin's README.

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
uv sync --locked --extra dev
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

# Deploy: mint a tag-promotion release
alias deploy-tag='python3 ~/.claude/plugins/infiquetra/deploy/scripts/mint_tag.py'

# UniFi network client
alias unifi-net='python3 ~/.claude/plugins/infiquetra/unifi/skills/unifi-network/scripts/unifi_network_client.py'
```

Then use:

```bash
deploy-tag --env nonprod --version 1.2.3 --dry-run
unifi-net --help
```

## Support

For issues or questions:

1. Check the plugin's README for usage details
2. Review the [PLUGIN_SPEC.md](PLUGIN_SPEC.md) for development guidelines
3. Open an issue on GitHub
