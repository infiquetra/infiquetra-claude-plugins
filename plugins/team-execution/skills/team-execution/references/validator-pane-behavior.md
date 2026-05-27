# Validator Pane Behavior - team-execution

This reference describes tmux pane behavior for team-execution sessions. It is guidance for
display and navigation only; gate logic lives in validator criteria and execution order.

---

## Goals

- Keep worker panes grouped when several workers run concurrently.
- Keep reviewers readable during consensus.
- Keep validators easy to inspect without crowding the orchestrator pane.

---

## Suggested Layout

| Agent Type | Window/Panes |
|------------|--------------|
| Orchestrator | Main window |
| Workers | Shared `workers` window, up to 4 panes tiled |
| Reviewers | Solo windows named by reviewer |
| Scanners | `scanners` window, up to 4 panes tiled |
| Testers | `testers` window, up to 4 panes tiled |
| Monitors | `monitors` window, up to 4 panes tiled |
| Operational | Solo window named by agent |

---

## Bundled Assets

`/team-setup` may install:

- `docs/example_tmux.conf`
- `docs/agent-overflow.sh`

The overflow script routes panes by title. If the script cannot determine the agent type,
it leaves the pane in its current window and prints a warning.

---

## Manual Inspection

Useful tmux controls from the bundled config:

- Prefix + `w`: window tree.
- Prefix + `f`: find window.
- Prefix + `z`: zoom current pane.
- Prefix + arrow keys: move between panes.
