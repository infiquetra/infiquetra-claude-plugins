#!/bin/bash
# agent-overflow.sh — auto-break to new window when pane count exceeds MAX_PANES
# Called by tmux after-split-window hook.

MAX_PANES=4
pane_count=$(tmux list-panes | wc -l | tr -d ' ')

if [ "$pane_count" -gt "$MAX_PANES" ]; then
    tmux break-pane -d
    tmux select-layout -t '{last}' tiled
    tmux select-layout tiled
else
    tmux select-layout tiled
fi
