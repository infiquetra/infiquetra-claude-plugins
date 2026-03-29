#!/bin/bash
# agent-overflow.sh — Claude Code agent team window router
# Called by tmux after-split-window hook.
#
# Two-phase routing:
#   Phase 1 (sync):  Break new pane out of orchestrator window immediately.
#   Phase 2 (async): After 1s, read pane title and route:
#     - worker-*   → join into existing "workers" window (2x2 tiled) or name solo
#     - *-reviewer → stay solo, window renamed to agent name
#     - *advocate  → stay solo, window renamed to agent name
#     - unknown    → stay solo (safe fallback — title not yet set)
#
# Race conditions: multiple workers spawn within the 1s window. Each script
# operates on its own $new_win_id. tmux join-pane is atomic — if a target
# fills to 4 before another worker joins, that worker stays solo and becomes
# a new "workers" window. Acceptable graceful degradation.

window_index=$(tmux display-message -p '#{window_index}')
pane_count=$(tmux list-panes | wc -l | tr -d ' ')

if [ "$window_index" = "1" ] && [ "$pane_count" -gt 1 ]; then
    # Phase 1: break new pane out of orchestrator, capture stable window ID
    new_win_id=$(tmux break-pane -d -P -F '#{window_id}')

    # Phase 2: background routing after pane title propagates (~1s)
    {
        sleep 1
        title=$(tmux display-message -t "$new_win_id" -p '#{pane_title}' 2>/dev/null)

        # Bail if title not yet set — window stays solo with default name
        case "$title" in
            ""|"bash"|"zsh"|"sh") exit 0 ;;
        esac

        if echo "$title" | grep -q '^worker-'; then
            # Worker: find an existing "workers*" window with room (< 4 panes)
            target_id=""
            while IFS=$'\t' read -r idx win_id panes name; do
                [ "$idx" = "1" ] && continue              # skip orchestrator
                [ "$win_id" = "$new_win_id" ] && continue # skip self
                [ "$panes" -ge 4 ] && continue            # skip full windows
                case "$name" in
                    workers*) target_id="$win_id"; break ;;
                esac
            done < <(tmux list-windows -F '#{window_index}\t#{window_id}\t#{window_panes}\t#{window_name}' | sort -n)

            if [ -n "$target_id" ]; then
                # Consolidate into existing workers window, re-tile
                tmux join-pane -d -s "$new_win_id" -t "$target_id"
                tmux select-layout -t "$target_id" tiled
            else
                # First worker (or all workers windows full) — name this window
                tmux rename-window -t "$new_win_id" "workers"
            fi

        else
            # Reviewer / advocate / other: stays solo, named after the agent
            tmux rename-window -t "$new_win_id" "$title"
        fi
    } &

    tmux select-layout tiled

elif [ "$pane_count" -gt 4 ]; then
    # Non-orchestrator window: overflow at 4 panes into a new window
    tmux break-pane -d
    tmux select-layout -t '{last}' tiled
    tmux select-layout tiled

else
    tmux select-layout tiled
fi
