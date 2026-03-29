#!/bin/bash
# agent-overflow.sh — auto-break to new window when pane count exceeds MAX_PANES
# Called by tmux after-split-window hook.
#
# MAX_PANES is dynamic:
#   - Main window (index 1): MAX_PANES=1 — agents always overflow to their own window
#   - Agent overflow windows: MAX_PANES=4 — pack up to 4 agents per window

window_index=$(tmux display-message -p '#{window_index}')
if [ "$window_index" = "1" ]; then
    MAX_PANES=1
else
    MAX_PANES=4
fi

pane_count=$(tmux list-panes | wc -l | tr -d ' ')

if [ "$pane_count" -gt "$MAX_PANES" ]; then
    tmux break-pane -d
    tmux select-layout -t '{last}' tiled
    tmux select-layout tiled
else
    tmux select-layout tiled
fi
