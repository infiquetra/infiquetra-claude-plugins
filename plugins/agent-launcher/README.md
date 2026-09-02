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
# after a staged-input stop, once the composer is clear -- never a second launch:
python3 "$S" redeliver --vendor <tool> --task <tab-name> --cwd "$PWD" --prompt <text> --receipt-json receipt.json > receipt-retry.json
```

The launch line carries a real prompt: without one, the session never leaves idle and the command exits nonzero.

Standard library only, so `python3` — not `uv run`.

## Input-box receipt contract

The launch receipt records the last composer inspection under `input_box`. Every line that enters
a session — each setup slash command, the task, each resend, both picker keystrokes on OpenCode,
and every later prompt Orchestrate sends — goes through one door, `PaneWriter.write`, which
inspects the pane immediately before the write whenever the write could land behind staged text:
before the first write into a session the launcher did not create, and before every later write
into any session, owned or not, once the launcher has written into it. The only uninspected write
is the first one into a tab the launcher created seconds earlier. A fresh owned launch with no
setup lines whose first prompt was taken therefore made no inspection and its receipt carries no
`input_box` key; any session written to more than once carries it. Its complete value set is
`empty`, `staged`, `unclassifiable`, `not_found`, `unsupported_vendor`, `read_failed`, and
`read_timeout`. Only `staged` also carries `input_box_text_chars`: the visible length of what the
parser absorbed — visible characters after border stripping, rows joined without a separator, one
character short at each wrapped-row boundary, and a lower bound of the draft's true length when a
blank line inside the draft ends the absorption — never the text itself. Blank or indented rows
that cannot be distinguished from vendor chrome are `unclassifiable`, never affirmative `empty`;
the accepted asymmetry runs the other way too, where an unbordered indented row directly below the
marker with no separator row between is read as input, because no capture shows chrome there.

## Boundaries

- Preview with `--dry-run` before every creation. It confirms `cwd` and `herdr_workspace`; it does not confirm model, effort, or account. Stop if the working directory or Herdr workspace is wrong.
- Launch is no-focus. Do not steal the operator's pane.
- Do not silently substitute an unavailable vendor, model, effort, or topology.
- Close only a session whose `tab_id` matches the launch receipt.
- Do not invent a vendor/model roster. The live wrapper and Herdr remain authoritative.
