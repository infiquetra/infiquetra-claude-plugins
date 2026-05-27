#!/usr/bin/env bash
set -euo pipefail

pane_id="${1:-}"

if [ -z "$pane_id" ]; then
  echo "agent-overflow: missing pane id" >&2
  exit 2
fi

title="$(tmux display-message -p -t "$pane_id" '#{pane_title}' 2>/dev/null || true)"

case "$title" in
  worker-*) target_window="workers" ;;
  *-scanner) target_window="scanners" ;;
  *-tester) target_window="testers" ;;
  *-monitor) target_window="monitors" ;;
  deploy-watcher) target_window="deploy-watcher" ;;
  *-reviewer|devils-advocate) target_window="$title" ;;
  *)
    echo "agent-overflow: leaving pane in place; unknown agent title '$title'" >&2
    exit 0
    ;;
esac

if [ "$target_window" = "$title" ]; then
  tmux break-pane -d -t "$pane_id" -n "$target_window"
  exit 0
fi

if ! tmux list-windows -F '#W' | grep -Fxq "$target_window"; then
  tmux new-window -d -n "$target_window"
fi

tmux join-pane -d -s "$pane_id" -t "$target_window"
tmux select-layout -t "$target_window" tiled >/dev/null
