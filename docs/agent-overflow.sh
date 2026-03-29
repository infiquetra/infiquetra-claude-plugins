#!/bin/bash
# agent-overflow.sh — Claude Code agent team window router
# Called by tmux after-split-window hook.
#
# Two-phase routing:
#   Phase 1 (sync):  Break new pane out of orchestrator window immediately.
#   Phase 2 (async): After 2s, read pane title and route:
#     - worker-*   → join into existing "workers" window (2x2 tiled) or name solo
#     - *-reviewer → stay solo, window renamed to agent name
#     - *advocate  → stay solo, window renamed to agent name
#     - unknown    → stay solo (safe fallback — title not yet set)
#
# Window tab coloring (stored as @agent_color window option):
#   worker-*          → colour34  (green)
#   security-*        → colour208 (orange)
#   architecture-*    → colour141 (purple)
#   devils-advocate*  → colour196 (red)
#   infra-*           → colour27  (blue)
#   api-*             → colour46  (bright green)
#   testing-*         → colour226 (yellow)
#   code-quality-*    → colour51  (cyan)
#   clarity-*         → colour51  (cyan)
#   privacy-*         → colour201 (magenta)
#   ai-usefulness-*   → colour226 (yellow)
#   unknown           → (unset — tmux theme default applies)

agent_color() {
    local name="$1"
    case "$name" in
        security-*)       echo "colour208" ;;  # orange
        architecture-*)   echo "colour141" ;;  # purple
        devils-advocate*) echo "colour196" ;;  # red
        infra-*)          echo "colour27"  ;;  # blue
        testing-*)        echo "colour226" ;;  # yellow
        code-quality-*)   echo "colour51"  ;;  # cyan
        clarity-*)        echo "colour51"  ;;  # cyan
        privacy-*)        echo "colour201" ;;  # magenta
        ai-usefulness-*)  echo "colour226" ;;  # yellow
        api-*)            echo "colour46"  ;;  # bright green
        worker-*)         echo "colour34"  ;;  # green
        *)                echo ""          ;;  # no override
    esac
}

window_index=$(tmux display-message -p '#{window_index}')
pane_count=$(tmux list-panes | wc -l | tr -d ' ')

if [ "$window_index" = "1" ] && [ "$pane_count" -gt 1 ]; then
    # Phase 1: break new pane out of orchestrator, capture stable window ID
    new_win_id=$(tmux break-pane -d -P -F '#{window_id}')

    # Phase 2: background routing after pane title propagates
    (
        sleep 2
        title=$(tmux display-message -t "$new_win_id" -p '#{pane_title}' 2>/dev/null)

        # Bail if title not yet set — window stays solo with default name
        case "$title" in
            ""|"bash"|"zsh"|"sh") exit 0 ;;
        esac

        if echo "$title" | grep -q '^worker-'; then
            # Worker: find an existing "workers*" window with room (< 4 panes)
            target_id=""
            while IFS='|' read -r idx win_id panes name; do
                [ "$idx" = "1" ] && continue              # skip orchestrator
                [ "$win_id" = "$new_win_id" ] && continue # skip self
                [ "$panes" -ge 4 ] && continue            # skip full windows
                case "$name" in
                    workers*) target_id="$win_id"; break ;;
                esac
            done < <(tmux list-windows -F '#{window_index}|#{window_id}|#{window_panes}|#{window_name}' | sort -n)

            color=$(agent_color "$title")
            if [ -n "$target_id" ]; then
                tmux join-pane -d -s "$new_win_id" -t "$target_id"
                tmux select-layout -t "$target_id" tiled
                # Color already set when workers window was first created
            else
                tmux rename-window -t "$new_win_id" "workers"
                [ -n "$color" ] && tmux set-window-option -t "$new_win_id" @agent_color "$color"
            fi

        else
            # Reviewer / advocate / other: stays solo, named after the agent
            tmux rename-window -t "$new_win_id" "$title"
            color=$(agent_color "$title")
            [ -n "$color" ] && tmux set-window-option -t "$new_win_id" @agent_color "$color"
        fi
    ) &

    tmux select-layout tiled

elif [ "$pane_count" -gt 4 ]; then
    # Non-orchestrator window: overflow at 4 panes into a new window
    tmux break-pane -d
    tmux select-layout -t '{last}' tiled
    tmux select-layout tiled

else
    tmux select-layout tiled
fi
