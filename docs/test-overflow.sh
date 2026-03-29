#!/bin/bash
# test-overflow.sh — simulate Claude Code agent team spawning to test window routing
#
# Replicates exactly what TeamCreate does:
#   - tmux split-window targeting window 1 (orchestrator)
#   - pane title set via \033]2;NAME\033\\ escape sequence
#
# Run this from window 1 in a tmux session.
# Usage: bash docs/test-overflow.sh [--cleanup]

set -e

SLEEP_BETWEEN=3  # seconds between spawns (allow routing to complete)

cleanup() {
    echo ""
    echo "Cleaning up test panes..."
    # Kill all panes running 'sleep 300' (our test sentinels)
    for pane in $(tmux list-panes -a -F '#{pane_id}:#{pane_current_command}' | grep ':sleep$' | cut -d: -f1); do
        tmux kill-pane -t "$pane" 2>/dev/null || true
    done
    # Remove windows that are now empty
    echo "Cleanup done. Remaining windows:"
    tmux list-windows -F '  W#{window_index}: #{window_name} (#{window_panes} panes)'
}

if [ "$1" = "--cleanup" ]; then
    cleanup
    exit 0
fi

current_window=$(tmux display-message -p '#{window_index}')
if [ "$current_window" != "1" ]; then
    echo "ERROR: Must run from window 1 (orchestrator). Currently in window $current_window."
    exit 1
fi

# Clear previous log
> /tmp/overflow.log

echo "=== agent-overflow routing test ==="
echo "Start layout:"
tmux list-windows -F '  W#{window_index}: #{window_name} (#{window_panes} panes)'
echo ""

# Spawn agents exactly as Claude Code does via TeamCreate:
# tmux split-window -t :1 "<command that sets title and stays alive>"
for name in worker-alpha worker-beta worker-gamma worker-delta worker-epsilon worker-zeta worker-eta security-reviewer architecture-reviewer; do
    echo "Spawning $name..."
    # Split in window 1, set pane title, then sleep (sentinel process)
    tmux split-window -t :1 "printf '\033]2;${name}\033\\'; sleep 300"
    sleep "$SLEEP_BETWEEN"
done

echo ""
echo "=== Result ==="
tmux list-windows -F 'W#{window_index}: #{window_name} (#{window_panes} panes)'

echo ""
echo "=== Window colors (@agent_color) ==="
while IFS='|' read -r idx win_id name; do
    color=$(tmux show-window-option -t "$win_id" -v @agent_color 2>/dev/null || echo "(unset)")
    printf "  W%s %-28s %s\n" "$idx" "$name" "$color"
done < <(tmux list-windows -F '#{window_index}|#{window_id}|#{window_name}')

echo ""
echo "=== Debug log ==="
cat /tmp/overflow.log

echo ""
echo "=== Expected ==="
echo "  W1: (orchestrator) — 1 pane,  color: (unset)"
echo "  workers — 4 panes,             color: colour34  (green)"
echo "  workers — 3 panes,             color: colour34  (green)"
echo "  security-reviewer — 1 pane,    color: colour208 (orange)"
echo "  architecture-reviewer — 1 pane, color: colour141 (purple)"
echo ""
echo "To clean up test panes: bash docs/test-overflow.sh --cleanup"
