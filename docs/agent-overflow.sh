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

            if [ -n "$target_id" ]; then
                tmux join-pane -d -s "$new_win_id" -t "$target_id"
                tmux select-layout -t "$target_id" tiled
            else
                tmux rename-window -t "$new_win_id" "workers"
            fi

        else
            # Reviewer / advocate / other: stays solo, named after the agent
            tmux rename-window -t "$new_win_id" "$title"
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
