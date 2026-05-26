#!/usr/bin/env bash
# claude-channel — launch claude with a redis-channel session pre-configured.
#
# Thin wrapper around `claude`. Sets env vars + dev flags the plugin needs,
# then exec's claude. All standard claude flags (--bg, --print, --resume,
# --model, --remote-control, --worktree, etc.) pass straight through.
#
# Wrapper-owned flags:
#   --session-name NAME   exports CLAUDE_SESSION_NAME (regex-validated)
#   --endpoint NAME       exports CLAUDE_CHANNEL_ENDPOINT
#   --cwd PATH            cd before exec (load-bearing for auto-naming
#                         and Phase 5 programmatic spawn)
#   --help                show this help and exit
#
# Env knobs:
#   CLAUDE_BIN                  override claude binary path
#   CLAUDE_CHANNEL_PRODUCTION   if "1", omit --dangerously-* dev flags
#   CLAUDE_CHANNEL_PLUGIN_REF   override plugin ref for the dev-channel loader
#
# Backgrounding is claude's job: pass `--bg` to claude-channel and it goes
# straight to claude, which spawns a background agent and prints the agent
# ID + attach/logs/stop commands. Use `claude agents` to list and
# `claude attach <id>` to attach. The redis-channel session presence
# registry (cc-sessions:registry + hb keys) is the canonical discovery
# mechanism for external consumers (Phase 5+).
#
# Exit codes:
#   0  success (claude's exit code in foreground; claude --bg returns 0)
#   2  invalid wrapper argument (e.g., bad --session-name regex)
#   3  claude binary not found
#   4  internal error (cd failed, etc.)

set -uo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────

SESSION_NAME=""
ENDPOINT=""
CWD=""
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || true)}"
PLUGIN_REF="${CLAUDE_CHANNEL_PLUGIN_REF:-plugin:redis-channel@infiquetra-plugins}"
PRODUCTION="${CLAUDE_CHANNEL_PRODUCTION:-0}"

# Session-name regex matches session_id.py:_NAME_RE.
SESSION_NAME_RE='^[a-z0-9][a-z0-9_-]{0,63}$'

# Everything we don't claim passes through to claude.
PASSTHRU_ARGS=()

# ─── Helpers ────────────────────────────────────────────────────────────────

usage() {
    cat <<'EOF'
Usage: claude-channel [WRAPPER OPTS] [CLAUDE OPTS] [-- <claude args>]

Launch claude with a redis-channel session pre-configured. Sets the env
vars and dev flags the plugin needs, then exec's claude. Standard claude
flags (--bg, --print, --resume, --model, --remote-control, etc.) pass
straight through.

Wrapper options:
  --session-name NAME    Session name (regex: ^[a-z0-9][a-z0-9_-]{0,63}$).
                         Exports CLAUDE_SESSION_NAME. If omitted, the
                         plugin auto-generates <cwd-basename>-<8hex>.
  --endpoint NAME        Router endpoint name. Exports CLAUDE_CHANNEL_ENDPOINT.
                         If omitted, plugin resolves to registry's
                         default_endpoint.
  --cwd PATH             cd to PATH before exec. Load-bearing for
                         auto-naming and programmatic callers spawning
                         in a target dir.
  --help                 Show this help and exit.
  --                     Everything after passes verbatim to claude.

Env knobs:
  CLAUDE_BIN                Path to claude binary. Default: $(command -v claude).
  CLAUDE_CHANNEL_PRODUCTION If "1", omit dev-only --dangerously-* flags.
  CLAUDE_CHANNEL_PLUGIN_REF Override plugin ref for dev-channel loader.

Backgrounding: use claude's native --bg flag (just pass it as a claude
option). claude prints the background agent ID + attach/logs/stop
commands. `claude agents` lists running sessions.

Examples:
  # Foreground, named session
  claude-channel --session-name auth-feature

  # Background, named, in a specific dir
  claude-channel --session-name auth-feature --cwd ~/work/myrepo --bg

  # Production mode (no dev-only flags), one-shot prompt
  CLAUDE_CHANNEL_PRODUCTION=1 claude-channel --print "what's the status?"
EOF
}

die() {
    printf 'claude-channel: error: %s\n' "$*" >&2
    exit "${2:-2}"
}

require_claude_bin() {
    if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
        die "claude binary not found (set CLAUDE_BIN or put 'claude' in PATH)" 3
    fi
}

# Source HERMES_REDIS_PASSWORD from macOS keychain if not already set.
# Best-effort; the plugin's source-env.sh (sourced by .mcp.json) is the
# primary mechanism, but this fallback covers wrapper-initiated launches
# where the MCP server hasn't started yet.
source_keychain_password() {
    if [ "$(uname)" != "Darwin" ]; then
        return 0
    fi
    if [ -n "${HERMES_REDIS_PASSWORD:-}" ]; then
        return 0
    fi
    if ! command -v security >/dev/null 2>&1; then
        return 0
    fi
    local pwd
    pwd=$(security find-generic-password -s "hermes-redis-password" -w 2>/dev/null || true)
    if [ -n "$pwd" ]; then
        export HERMES_REDIS_PASSWORD="$pwd"
    fi
}

# ─── Argument parsing ───────────────────────────────────────────────────────

while [ $# -gt 0 ]; do
    case "$1" in
        --session-name)
            [ $# -ge 2 ] || die "--session-name requires a value"
            SESSION_NAME="$2"; shift 2 ;;
        --session-name=*)
            SESSION_NAME="${1#*=}"; shift ;;
        --endpoint)
            [ $# -ge 2 ] || die "--endpoint requires a value"
            ENDPOINT="$2"; shift 2 ;;
        --endpoint=*)
            ENDPOINT="${1#*=}"; shift ;;
        --cwd)
            [ $# -ge 2 ] || die "--cwd requires a value"
            CWD="$2"; shift 2 ;;
        --cwd=*)
            CWD="${1#*=}"; shift ;;
        --help|-h)
            usage; exit 0 ;;
        --)
            shift
            PASSTHRU_ARGS+=("$@")
            break ;;
        *)
            # Pass through everything we don't claim (flags AND positional).
            PASSTHRU_ARGS+=("$1"); shift ;;
    esac
done

# ─── Validation + env setup ─────────────────────────────────────────────────

if [ -n "$SESSION_NAME" ]; then
    if ! [[ "$SESSION_NAME" =~ $SESSION_NAME_RE ]]; then
        die "invalid session-name '$SESSION_NAME' (must match $SESSION_NAME_RE)"
    fi
    export CLAUDE_SESSION_NAME="$SESSION_NAME"
fi

if [ -n "$ENDPOINT" ]; then
    export CLAUDE_CHANNEL_ENDPOINT="$ENDPOINT"
fi

if [ -n "$CWD" ]; then
    cd "$CWD" || die "cannot cd to '$CWD'" 4
fi

require_claude_bin
source_keychain_password
export CLAUDE_CHANNEL_AUTO_CONNECT=1

# Compose claude argv: dev flags (unless production) + plugin-ref + passthru.
CLAUDE_ARGS=()
if [ "$PRODUCTION" != "1" ]; then
    CLAUDE_ARGS+=(--allow-dangerously-skip-permissions)
    CLAUDE_ARGS+=(--dangerously-load-development-channels "$PLUGIN_REF")
fi
CLAUDE_ARGS+=("${PASSTHRU_ARGS[@]}")

exec "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
