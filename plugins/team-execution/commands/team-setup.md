---
name: team-setup
description: Validate and configure tmux + Claude settings for team-execution agent teams
argument-hint: "[reset]"
---

# Team Execution Setup Wizard

Run a full environment check for team-execution and guide the user through fixing any issues.

If `$ARGUMENTS` contains "reset", first clear the tmux dismissal:
```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.claude/team-execution.json')
if os.path.exists(path):
    with open(path) as f: d = json.load(f)
    d.pop('tmux_setup_dismissed', None)
    with open(path, 'w') as f: json.dump(d, f, indent=2)
    print('tmux setup checks re-enabled.')
else:
    print('No dismissal found — checks are already active.')
"
```

## Step 1: Run All Checks

Run every check and collect results:

```bash
echo "=== CLAUDE.md Handoff Rule ==="
grep -q "Team Execution Auto-Handoff" ~/.claude/CLAUDE.md 2>/dev/null && echo "handoff:OK" || echo "handoff:MISSING"

echo "=== tmux Environment ==="
command -v tmux >/dev/null 2>&1 && echo "tmux:OK:$(tmux -V)" || echo "tmux:MISSING"
[ -n "$TMUX" ] && echo "session:OK" || echo "session:MISSING"
[ -f ~/.tmux.conf ] && echo "config:OK" || echo "config:MISSING"
[ -x ~/.config/tmux/agent-overflow.sh ] && echo "overflow:OK" || echo "overflow:MISSING"

echo "=== Claude Settings ==="
cat ~/.claude.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('teammateMode','unset'); print(f'teammateMode:{m}')" 2>/dev/null || echo "teammateMode:unset"
cat ~/.claude/settings.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); v=d.get('env',{}).get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS','unset'); print(f'agentTeams:{v}')" 2>/dev/null || echo "agentTeams:unset"

echo "=== tmux Dismissal ==="
cat ~/.claude/team-execution.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('DISMISSED' if d.get('tmux_setup_dismissed') else 'ACTIVE')" 2>/dev/null || echo "ACTIVE"
```

## Step 2: Display Results

Show a clear summary:

```
Team Execution Environment Check
═══════════════════════════════════════════════════

Critical (required for skill to work):
  [✅ or ⚠️] CLAUDE.md auto-handoff rule

tmux Agent Teams (recommended):
  [✅ or ⚠️] tmux installed [version]
  [✅ or ⚠️] Running inside tmux session
  [✅ or ⚠️] ~/.tmux.conf configured
  [✅ or ⚠️] Overflow script (agent-overflow.sh)
  [✅ or ⚠️] teammateMode in ~/.claude.json
  [✅ or ⚠️] Agent teams feature flag

tmux checks: [active / dismissed]
═══════════════════════════════════════════════════
```

## Step 3: Offer Fixes for Each Issue

Walk through each failing check and offer to fix it. Ask the user for confirmation before each change.

### Fix: CLAUDE.md handoff rule missing

Offer to append the auto-handoff rule to `~/.claude/CLAUDE.md`:

```
The team-execution skill requires this rule in ~/.claude/CLAUDE.md to automatically
trigger TeamCreate when a plan with ## Team Structure exits plan mode.

Shall I add it to your ~/.claude/CLAUDE.md?
```

If yes, append:
```markdown

## Team Execution Auto-Handoff

When a plan exits plan mode and contains an explicit **## Team Structure** section with named agents:

1. **Your ONLY next action is TeamCreate** — no exceptions, no other actions first.
2. **Do NOT use the Agent tool** for any implementation work in this plan.
3. Parse the `## Team Structure` table for workers and reviewers.
4. Call TeamCreate immediately with those agents.
5. Then follow the Phase B orchestration protocol from `team-execution/skills/team-execution/SKILL.md`.

This rule takes **priority over any other agent-spawning or task-delegation behavior**. If you find yourself about to spawn a sub-agent for implementation work, stop — route it to a TeamCreate worker instead.
```

### Fix: tmux not installed

Show:
```
tmux is required for split-pane agent teams. Install it:

  macOS:  brew install tmux
  Ubuntu: sudo apt install tmux
  Fedora: sudo dnf install tmux
```

### Fix: Not running inside tmux

Show:
```
You're not currently inside a tmux session. Agent teams need tmux for split panes.

Start a session and relaunch claude:
  tmux new -s agents
  claude
```

### Fix: ~/.tmux.conf missing

The team-execution plugin ships an optimized tmux config. Offer to install it:

```
The team-execution plugin includes an optimized tmux config for agent teams:
  - Auto-overflow: max 4 panes per window, auto-breaks to new window
  - Prefix+hjkl pane navigation (Ctrl+h/l stays free for iTerm2)
  - Green-on-black theme with agent names in pane borders
  - Hybrid tile+zoom layout

Shall I install it?
```

If yes:
```bash
# Find the plugin's docs directory
PLUGIN_DIR=$(find ~/.claude/plugins -path "*/team-execution/docs/example_tmux.conf" 2>/dev/null | head -1 | xargs dirname)
if [ -z "$PLUGIN_DIR" ]; then
  PLUGIN_DIR=$(find . -path "*/team-execution/docs/example_tmux.conf" 2>/dev/null | head -1 | xargs dirname)
fi

if [ -n "$PLUGIN_DIR" ]; then
  cp "$PLUGIN_DIR/example_tmux.conf" ~/.tmux.conf
  echo "Installed ~/.tmux.conf"
else
  echo "Could not find example_tmux.conf in plugin directory."
  echo "Manual install: cp docs/example_tmux.conf ~/.tmux.conf"
fi
```

### Fix: agent-overflow.sh missing

```bash
PLUGIN_DIR=$(find ~/.claude/plugins -path "*/team-execution/docs/agent-overflow.sh" 2>/dev/null | head -1 | xargs dirname)
if [ -z "$PLUGIN_DIR" ]; then
  PLUGIN_DIR=$(find . -path "*/team-execution/docs/agent-overflow.sh" 2>/dev/null | head -1 | xargs dirname)
fi

if [ -n "$PLUGIN_DIR" ]; then
  mkdir -p ~/.config/tmux
  cp "$PLUGIN_DIR/agent-overflow.sh" ~/.config/tmux/agent-overflow.sh
  chmod +x ~/.config/tmux/agent-overflow.sh
  echo "Installed ~/.config/tmux/agent-overflow.sh"
else
  echo "Could not find agent-overflow.sh in plugin directory."
  echo "Manual install: cp docs/agent-overflow.sh ~/.config/tmux/ && chmod +x ~/.config/tmux/agent-overflow.sh"
fi
```

### Fix: teammateMode not set

Show:
```
Claude Code's teammateMode controls how agent teammates are displayed.
For split-pane agent teams, it should be set to "tmux".

Shall I set it? This writes to ~/.claude.json.
```

If yes:
```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.claude.json')
d = {}
if os.path.exists(path):
    with open(path) as f: d = json.load(f)
d['teammateMode'] = 'tmux'
with open(path, 'w') as f: json.dump(d, f, indent=2)
print('Set teammateMode to tmux in ~/.claude.json')
"
```

### Fix: Agent teams feature flag not set

Show:
```
The experimental agent teams feature needs to be enabled in Claude settings.

Shall I enable it? This writes to ~/.claude/settings.json.
```

If yes:
```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.claude/settings.json')
d = {}
if os.path.exists(path):
    with open(path) as f: d = json.load(f)
if 'env' not in d: d['env'] = {}
d['env']['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'] = '1'
with open(path, 'w') as f: json.dump(d, f, indent=2)
print('Enabled CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS in settings.json')
"
```

## Step 4: Reload (if changes were made)

If any tmux config was installed or modified:
```bash
[ -n "$TMUX" ] && tmux source ~/.tmux.conf && echo "tmux config reloaded"
```

## Step 5: Offer tmux Dismissal

If all tmux checks pass or the user doesn't want tmux:
```
All checks complete. Would you like to:
  A) Keep tmux checks active (will check on next /team-execute)
  B) Dismiss tmux checks (won't ask again — run /team-setup reset to re-enable)
```

If B:
```bash
mkdir -p ~/.claude && echo '{"tmux_setup_dismissed": true}' > ~/.claude/team-execution.json
```
