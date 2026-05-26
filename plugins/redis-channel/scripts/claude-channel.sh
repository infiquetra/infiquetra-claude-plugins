#!/usr/bin/env bash
# claude-channel — launch Claude Code with a redis-channel session configured.
#
# Provides:
#   - --session-name <name>  → exports CLAUDE_SESSION_NAME (validated)
#   - --endpoint <name>      → exports CLAUDE_CHANNEL_ENDPOINT
#   - --bg / --background    → detached launch with log file
#   - --cwd <path>           → cd before exec (load-bearing for Phase 5)
#   - --print-info           → emit JSON metadata for programmatic callers
#   - --help                 → usage
#
# Env knobs:
#   CLAUDE_BIN                Override claude binary path. Default: `command -v claude`.
#   CLAUDE_CHANNEL_PRODUCTION If "1", omit dev-only --dangerously-* flags.
#   CLAUDE_CHANNEL_PLUGIN_REF Override plugin ref for --dangerously-load-development-channels.
#                             Default: plugin:redis-channel@infiquetra-plugins.
#
# Designed for both human terminal use AND programmatic invocation by routers
# (e.g., Phase 5's hermes-claude-code-router LLM tool that spawns CC sessions
# on demand).
#
# Exit codes:
#   0  success (foreground: claude's exit code; background: spawned cleanly)
#   2  invalid argument (e.g., bad session-name regex)
#   3  claude binary not found
#   4  internal error (mkdir failed, etc.)

set -uo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────

SESSION_NAME=""
ENDPOINT=""
BACKGROUND=0
CWD=""
PRINT_INFO=0
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || true)}"
PLUGIN_REF="${CLAUDE_CHANNEL_PLUGIN_REF:-plugin:redis-channel@infiquetra-plugins}"
PRODUCTION="${CLAUDE_CHANNEL_PRODUCTION:-0}"

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude-channel/sessions"

# Session-name regex matches session_id.py:_NAME_RE.
SESSION_NAME_RE='^[a-z0-9][a-z0-9_-]{0,63}$'

# Collect pass-through args after --.
PASSTHRU_ARGS=()

# ─── Helpers ────────────────────────────────────────────────────────────────

usage() {
    cat <<'EOF'
Usage: claude-channel [OPTIONS] [-- <claude args>]

Launch Claude Code with a redis-channel session pre-configured.

Options:
  --session-name NAME    Session name (regex: ^[a-z0-9][a-z0-9_-]{0,63}$).
                         Exports CLAUDE_SESSION_NAME. If omitted, the
                         plugin auto-generates <cwd-basename>-<8hex>.
  --endpoint NAME        Router endpoint name. Exports CLAUDE_CHANNEL_ENDPOINT.
                         If omitted, plugin resolves to registry's
                         default_endpoint.
  --bg, --background     Detached launch. stdout+stderr go to log file under
                         ~/.cache/claude-channel/sessions/. Wrapper exits
                         after spawn.
  --cwd PATH             cd to PATH before exec/spawn. Load-bearing for
                         programmatic callers (auto-naming uses cwd).
  --print-info           Emit JSON {session_name, endpoint, log_path, pid,
                         cwd, mode} for programmatic callers. Foreground
                         prints to stderr; background prints to stdout.
  --help                 Show this help and exit.
  --                     Everything after is passed verbatim to claude.

Env knobs:
  CLAUDE_BIN                Path to claude binary. Default: $(command -v claude).
  CLAUDE_CHANNEL_PRODUCTION If "1", omit dev-only --dangerously-* flags.
  CLAUDE_CHANNEL_PLUGIN_REF Override plugin ref for dev-channel loader.

Examples:
  # Foreground, auto-named session
  claude-channel

  # Foreground, named session
  claude-channel --session-name auth-feature

  # Background launch with named session, print JSON metadata to stdout
  claude-channel --bg --session-name auth-feature --cwd ~/work/myrepo --print-info

  # Production mode (no dev-only flags)
  CLAUDE_CHANNEL_PRODUCTION=1 claude-channel --endpoint mimir
EOF
}

die() {
    printf 'claude-channel: error: %s\n' "$*" >&2
    exit "${2:-2}"
}

warn() {
    printf 'claude-channel: warning: %s\n' "$*" >&2
}

# Pre-flight: claude binary present?
require_claude_bin() {
    if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
        die "claude binary not found (set CLAUDE_BIN or put 'claude' in PATH)" 3
    fi
}

# Source HERMES_REDIS_PASSWORD (or whatever the deployment uses) from keychain
# on macOS — best-effort. The actual env var name is per-deployment; the
# plugin's source-env.sh handles it. But to keep this wrapper useful even when
# the user hasn't set up source-env.sh, we offer a macOS-keychain fallback for
# the common case (hermes-redis-password keychain item exporting
# HERMES_REDIS_PASSWORD).
source_keychain_password() {
    if [ "$(uname)" != "Darwin" ]; then
        return 0
    fi
    if [ -n "${HERMES_REDIS_PASSWORD:-}" ]; then
        return 0  # already set; respect caller
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
        --bg|--background)
            BACKGROUND=1; shift ;;
        --cwd)
            [ $# -ge 2 ] || die "--cwd requires a value"
            CWD="$2"; shift 2 ;;
        --cwd=*)
            CWD="${1#*=}"; shift ;;
        --print-info)
            PRINT_INFO=1; shift ;;
        --help|-h)
            usage; exit 0 ;;
        --)
            shift
            PASSTHRU_ARGS+=("$@")
            break ;;
        --*)
            # Unknown long flag → pass through to claude
            PASSTHRU_ARGS+=("$1"); shift ;;
        *)
            PASSTHRU_ARGS+=("$1"); shift ;;
    esac
done

# ─── Validation ─────────────────────────────────────────────────────────────

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

# ─── JSON emit helper ───────────────────────────────────────────────────────

emit_info() {
    # $1 = mode ("foreground"|"background"), $2 = pid, $3 = log_path (may be empty)
    local mode="$1"
    local pid="$2"
    local log_path="$3"
    # Escape JSON strings minimally — values we control don't contain quotes
    # or backslashes given the regex on SESSION_NAME and the safe values we
    # accept for ENDPOINT/CWD. printf with %s is fine here.
    local json
    json=$(printf '{"session_name":"%s","endpoint":"%s","log_path":"%s","pid":%s,"cwd":"%s","mode":"%s"}' \
        "${SESSION_NAME}" "${ENDPOINT}" "${log_path}" "${pid}" "$(pwd)" "${mode}")
    if [ "$mode" = "foreground" ]; then
        # Foreground: don't pollute claude's stdout. Send to stderr.
        printf '%s\n' "$json" >&2
    else
        printf '%s\n' "$json"
    fi
}

# ─── Launch ─────────────────────────────────────────────────────────────────

if [ "$BACKGROUND" -eq 1 ]; then
    mkdir -p "$CACHE_DIR" || die "mkdir -p '$CACHE_DIR' failed" 4
    NAME_FOR_LOG="${SESSION_NAME:-auto-$(date +%s)}"
    LOG_PATH="${CACHE_DIR}/${NAME_FOR_LOG}-$(date +%s).log"

    # POSIX-portable detach (no setsid on macOS): subshell + nohup + redirect
    # + disown. Subshell isolates from parent process group.
    (
        nohup "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}" >"$LOG_PATH" 2>&1 </dev/null &
        echo $! >"${LOG_PATH}.pid"
        disown
    )
    # Read the PID we just wrote.
    sleep 0.1
    PID=$(cat "${LOG_PATH}.pid" 2>/dev/null || echo 0)
    rm -f "${LOG_PATH}.pid"

    if [ "$PRINT_INFO" -eq 1 ]; then
        emit_info "background" "$PID" "$LOG_PATH"
    else
        printf 'claude-channel: spawned pid=%s log=%s\n' "$PID" "$LOG_PATH"
    fi
    exit 0
else
    # Foreground: replace wrapper with claude. PID stays the same.
    if [ "$PRINT_INFO" -eq 1 ]; then
        emit_info "foreground" "$$" ""
    fi
    exec "$CLAUDE_BIN" "${CLAUDE_ARGS[@]}"
fi
