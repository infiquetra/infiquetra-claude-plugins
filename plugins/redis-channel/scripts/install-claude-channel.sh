#!/usr/bin/env bash
# install-claude-channel — symlink ~/bin/claude-channel → the cached plugin's wrapper.
#
# The plugin cache layout is versioned (per Claude Code's plugin loader), so
# the symlink target moves between plugin updates. This installer resolves
# the latest cached version of redis-channel and points ~/bin/claude-channel
# at its claude-channel.sh.
#
# Re-run this script after each plugin update (or set up a hook).

set -euo pipefail

PLUGIN_CACHE_GLOB="$HOME/.claude/plugins/cache/infiquetra-plugins/redis-channel"
BIN_DIR="$HOME/bin"
SYMLINK="$BIN_DIR/claude-channel"

# Find the latest version dir.
if [ ! -d "$PLUGIN_CACHE_GLOB" ]; then
    printf 'install-claude-channel: error: plugin cache not found at %s\n' \
        "$PLUGIN_CACHE_GLOB" >&2
    printf 'Install the redis-channel plugin via /plugin first.\n' >&2
    exit 1
fi

# Sort versions naturally (0.4.12 > 0.4.2 etc).
LATEST=$(find "$PLUGIN_CACHE_GLOB" -maxdepth 1 -mindepth 1 -type d \
    | sort -V \
    | tail -1)
if [ -z "$LATEST" ]; then
    printf 'install-claude-channel: error: no version dirs in %s\n' \
        "$PLUGIN_CACHE_GLOB" >&2
    exit 1
fi

TARGET="$LATEST/scripts/claude-channel.sh"
if [ ! -x "$TARGET" ]; then
    printf 'install-claude-channel: error: %s missing or not executable\n' \
        "$TARGET" >&2
    exit 1
fi

mkdir -p "$BIN_DIR"
ln -sf "$TARGET" "$SYMLINK"

printf '✓ %s -> %s\n' "$SYMLINK" "$TARGET"
printf '\nVerify with:\n  claude-channel --help\n'
