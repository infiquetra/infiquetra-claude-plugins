# agent-launcher

Create one verified coding-agent session in the current Herdr workspace. The installed
`agents` wrapper is the only creation path. Herdr is the only interaction path after
creation.

Orchestrate consumes this plugin's `skills/agent-launcher/scripts/launcher.py` as its
launch seam. An ordinary session uses the same script as a CLI, or follows
`skills/agent-launcher/SKILL.md`.

This plugin does not ship a copy of the `herdr` skill. After a session exists, use that
skill for prompt, wait, read, input, and cleanup.

## Quick start

```bash
S="$CLAUDE_PLUGIN_ROOT/skills/agent-launcher/scripts/launcher.py"
[ -f "$S" ] || S=$(ls -d ~/.claude/plugins/cache/*/agent-launcher/*/skills/agent-launcher/scripts/launcher.py | sort -V | tail -1)

python3 "$S" roster
python3 "$S" preview --vendor codex --task reviewer --cwd "$PWD" --model gpt-5.4 --effort xhigh
python3 "$S" launch  --vendor codex --task reviewer --cwd "$PWD" --model gpt-5.4 --effort xhigh --prompt "review the diff" > receipt.json
python3 "$S" close --receipt-json receipt.json
```

The launch line carries a real prompt: without one, the session never leaves idle and the command exits nonzero.

Standard library only, so `python3` — not `uv run`.

## Boundaries

- Preview with `--dry-run` before every creation. It confirms `cwd` and `herdr_workspace`; it does not confirm model, effort, or account. Stop if the working directory or Herdr workspace is wrong.
- Launch is no-focus. Do not steal the operator's pane.
- Do not silently substitute an unavailable vendor, model, effort, or topology.
- Close only a session whose `tab_id` matches the launch receipt.
- Do not invent a vendor/model roster. The live wrapper and Herdr remain authoritative.
