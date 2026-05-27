---
name: team-setup
description: Validate and configure team-execution handoff, tmux panes, and local validator state
argument-hint: "[reset]"
---

# Team Execution Setup Wizard

Run a full environment check for team-execution and guide the user through fixing any issues.
Ask before writing user-level files.

If `$ARGUMENTS` contains `reset`, first clear the tmux dismissal:

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
    print('No dismissal found; checks are already active.')
"
```

## Step 1: Run Checks

```bash
echo "=== Handoff Rule ==="
grep -q "Team Execution Auto-Handoff" ~/.claude/CLAUDE.md 2>/dev/null && echo "handoff:OK" || echo "handoff:MISSING"

echo "=== tmux Environment ==="
command -v tmux >/dev/null 2>&1 && echo "tmux:OK:$(tmux -V)" || echo "tmux:MISSING"
[ -n "$TMUX" ] && echo "session:OK" || echo "session:MISSING"
[ -f ~/.tmux.conf ] && echo "config:OK" || echo "config:MISSING"
[ -x ~/.config/tmux/agent-overflow.sh ] && echo "overflow:OK" || echo "overflow:MISSING"

echo "=== Bundled Assets ==="
[ -f ./plugins/team-execution/docs/example_tmux.conf ] && echo "example_tmux:OK" || echo "example_tmux:MISSING"
[ -f ./plugins/team-execution/docs/agent-overflow.sh ] && echo "agent_overflow_asset:OK" || echo "agent_overflow_asset:MISSING"

echo "=== Validator State ==="
git check-ignore -q .claude && echo "claude_ignore:OK" || echo "claude_ignore:MISSING"

echo "=== tmux Dismissal ==="
cat ~/.claude/team-execution.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('DISMISSED' if d.get('tmux_setup_dismissed') else 'ACTIVE')" 2>/dev/null || echo "ACTIVE"
```

## Step 2: Display Results

Show a concise summary:

```text
Team Execution Environment Check

Critical:
  [OK/WARN] CLAUDE.md auto-handoff rule

tmux panes:
  [OK/WARN] tmux installed
  [OK/WARN] Running inside tmux
  [OK/WARN] ~/.tmux.conf configured
  [OK/WARN] ~/.config/tmux/agent-overflow.sh installed
  [OK/WARN] Bundled docs/example_tmux.conf exists
  [OK/WARN] Bundled docs/agent-overflow.sh exists

Validator state:
  [OK/WARN] .claude/ ignored for .claude/team-execution/validators/
```

## Step 3: Fix Handoff Rule

If the handoff rule is missing, offer to append this to `~/.claude/CLAUDE.md`:

```markdown

## Team Execution Auto-Handoff

When a plan exits plan mode and contains an explicit **## Team Structure** section:

1. Parse workers, reviewers, validators, reference files, and execution gates.
2. Follow Phase B from `team-execution/skills/team-execution/SKILL.md`.
3. Workers complete changes before reviewers run.
4. Reviewer consensus gates validators unless the user explicitly overrides.
5. Scanner/tester hard-fail findings block automation and completion.
```

## Step 4: Fix tmux Asset Setup

If `~/.tmux.conf` is missing, offer to install the bundled config.

```bash
PLUGIN_DIR=$(find ~/.claude/plugins -path "*/team-execution/docs/example_tmux.conf" 2>/dev/null | head -1 | xargs dirname)
if [ -z "$PLUGIN_DIR" ]; then
  PLUGIN_DIR=$(find . -path "*/team-execution/docs/example_tmux.conf" 2>/dev/null | head -1 | xargs dirname)
fi

if [ -n "$PLUGIN_DIR" ]; then
  cp "$PLUGIN_DIR/example_tmux.conf" ~/.tmux.conf
  echo "Installed ~/.tmux.conf from docs/example_tmux.conf"
else
  echo "Could not find docs/example_tmux.conf in plugin directory."
  echo "Manual install: cp docs/example_tmux.conf ~/.tmux.conf"
fi
```

If `~/.config/tmux/agent-overflow.sh` is missing, offer to install the bundled script.

```bash
PLUGIN_DIR=$(find ~/.claude/plugins -path "*/team-execution/docs/agent-overflow.sh" 2>/dev/null | head -1 | xargs dirname)
if [ -z "$PLUGIN_DIR" ]; then
  PLUGIN_DIR=$(find . -path "*/team-execution/docs/agent-overflow.sh" 2>/dev/null | head -1 | xargs dirname)
fi

if [ -n "$PLUGIN_DIR" ]; then
  mkdir -p ~/.config/tmux
  cp "$PLUGIN_DIR/agent-overflow.sh" ~/.config/tmux/agent-overflow.sh
  chmod +x ~/.config/tmux/agent-overflow.sh
  echo "Installed ~/.config/tmux/agent-overflow.sh from docs/agent-overflow.sh"
else
  echo "Could not find docs/agent-overflow.sh in plugin directory."
  echo "Manual install: cp docs/agent-overflow.sh ~/.config/tmux/ && chmod +x ~/.config/tmux/agent-overflow.sh"
fi
```

If tmux config changed and a tmux session is active:

```bash
[ -n "$TMUX" ] && tmux source ~/.tmux.conf && echo "tmux config reloaded"
```

## Step 5: Fix Validator State Safety

If `.claude/` is not ignored in the target repository, show:

```text
Validator state defaults to .claude/team-execution/validators/.
Add .claude/ to .gitignore before using repo-local validator state, or use:

  ~/.claude/team-execution/state/<repo>/
```

Do not create repo-local validator state until the user confirms `.claude/` is ignored or
chooses the user-local fallback.

## Step 6: Dismiss tmux Checks

If the user does not want tmux setup checks:

```bash
mkdir -p ~/.claude && echo '{"tmux_setup_dismissed": true}' > ~/.claude/team-execution.json
```
