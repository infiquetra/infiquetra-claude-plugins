---
name: agent-launcher
description: "Create coding-agent sessions with the local `agents` wrapper — one named tab in the current Herdr workspace, a crew, a machine or team view, a fleet layout, or a Hermes profile — including model, provider, permissions, working directory, and machine routing. Use when the user asks to launch, start, add, or open a Claude, Codex, Grok, Muse, OpenCode, Qwen, Agy, or Hermes session, or to open a machine/team/fleet view. Creation only: use the `herdr` skill for every interaction after the session exists. Do not use merely because a task could benefit from delegation or parallel work."
---

# Agent launcher

`agents` is a local wrapper at `~/.local/bin/agents` that creates agent sessions and Herdr views. It is a creation tool, not an interaction tool.

**Depends on:** the canonical `herdr` skill for every interaction after the session exists. This plugin does not ship a copy of that skill. After the creation command returns, switch to `herdr` and stay there.

**Scope boundary — this is the rule the whole skill hangs on:**

- `agents` **creates** a session: tab, pane, working directory, model, permissions, machine.
- `herdr` **operates** it: prompt, wait, read, send keys, close.

Never use `agents` to prompt, poll, read, or clean up an agent that already exists.

## Verified launch (preferred)

For one named tab that must be previewed, no-focus, directory-preserving, and receipt-recorded, use the plugin script rather than assembling `agents` by hand. Orchestrate uses this same file; there is no second implementation.

```bash
S="$CLAUDE_PLUGIN_ROOT/skills/agent-launcher/scripts/launcher.py"
[ -f "$S" ] || S=$(ls -d ~/.claude/plugins/cache/*/agent-launcher/*/skills/agent-launcher/scripts/launcher.py | sort -V | tail -1)

python3 "$S" preview --vendor <tool> --task <tab-name> --cwd "$PWD" --model <model> --effort <effort>
python3 "$S" launch  --vendor <tool> --task <tab-name> --cwd "$PWD" --model <model> --effort <effort> > receipt.json
python3 "$S" close --receipt-json receipt.json
```

`launch` always dry-runs first. It writes one JSON receipt to stdout (redirect it to `receipt.json` as above). It verifies live Herdr state (kind, pane, cwd, workspace, readiness) before any prompt is sent. Model stays `requested_only` because `herdr agent list` does not publish it; Herdr publishes no permission either, so the declared posture is confirmed against the launch argv instead and recorded under `permission_resolved` in the receipt, distinctly from the requested `permission` value. `close` reads `tab_id` and `owned` from that file. `owned` is true only when the receipt `tab_id` was **not** in the Herdr workspace tab set snapshotted immediately before the wrapper ran. The wrapper's `reused` bit means the *workspace* already existed, which is the common case inside Herdr, and is not tab ownership.

Permission is granted at launch and is not correctable in place: cycling a live session's permission control moves only through manual, accept-edits, plan and back to auto, so a session that came up in `auto` cannot be promoted to `bypass` afterwards and must be torn down and relaunched.

A session whose tab the launcher did not create (`owned` false in the receipt) has its input box inspected before any prompt is sent, because a prompt typed behind staged text concatenates onto it and can submit it. Staged text is a stop, not a clear: the launch refuses to prompt, and the text is recorded in the receipt and the unit note — nothing is discarded. A client's own placeholder (the dim hint a vendor draws in an empty box) is not staged text and does not stop the launch, and a box that cannot be read is recorded as `unreadable` in the receipt and prompted as today.

**Stop conditions (verbatim):**

- Stop before launch if the wrapper dry run does not resolve the requested working directory and current Herdr workspace.
- Stop before prompting if Herdr cannot verify the requested agent kind, model, effort, permissions, pane, and readiness. Fields Herdr does not publish are recorded as `requested_only` rather than invented; a disagreement on a field Herdr does publish is a stop.
- Stop rather than silently substituting an unavailable agent or launch setting.
- Stop cleanup if ownership of the target session cannot be proven (no `tab_id`, `tab_id` disagrees with the launch receipt, or `owned` is not true — the tab already existed in the pre-launch snapshot).

## The binary is the authority

Command syntax changes. Read it live rather than trusting this file or memory:

```bash
agents --help
agents --recipes     # every recipe and layout name
agents --crews       # crews as they resolve on THIS machine
```

`--dry-run` previews any launch without executing it. Use it before every creation command.

Some real flags are absent from `--help`. `--herdr-control-only` is one of them — it is implemented in the wrapper and is the correct flag for the common case below. Do not "fix" it away because help does not list it.

## Ordering — the most common mistake

Launcher options must come **before** `<tool>`. Everything after `<tool>` is passed to that tool unchanged.

```bash
agents --dry-run claude     # previews the launch  (launcher flag)
agents claude --dry-run     # runs Claude with a --dry-run argument (tool flag)
```

Tool-native arguments — `--model`, `-c model_reasoning_effort=…`, `--yolo` — always go after the tool.

Never bypass the wrapper to create an interactive coding-agent session. In particular, OpenCode's interactive terminal user interface is the top-level `opencode` command. `opencode run` is the programmatic prompt command and requires an initial message or command even when `--interactive` is present. Launch OpenCode like this:

```bash
agents --dry-run --no-focus --current --herdr --herdr-control-only \
  --task <tab-name> --cwd "$PWD" \
  opencode --model deepseek/deepseek-v4-pro --agent plan
```

OpenCode 1.18.18 does not expose `--variant` on its top-level terminal user interface command. Do not switch to `opencode run -i` to work around that. The terminal user interface restores the selected per-model variant; use `/variants` inside OpenCode when it must change.

## Pick the topology deliberately

Do not substitute one shape for another. If the user asked for a tab, do not build a crew.

| Shape | Command | What it creates |
| --- | --- | --- |
| One named tab | `agents --herdr-control-only --task <name> <tool>` | A single tab in the **current** workspace; keeps focus |
| Crew | `agents --crew` | One workspace here: Terminal tab, orchestrator tab, one tab per worker |
| Ad-hoc crew | `agents --orchestrator claude --workers codex,agy` | Exactly those agents, no named crew |
| Machine view | `agents --recipe studio\|mac-mini\|laptop` | That one machine's canonical Herdr view |
| Team view | `agents --recipe mimir\|freya\|norns` | Reconciles that team's profiles, opens its view |
| Fleet | `agents --recipe fleet` | All machine views plus all three team views |
| Layout | `agents --recipe cockpit` (or `--herdr-layout <n>`) | One cmux workspace, a Herdr pane per machine |
| Hermes profile | `agents --profile <selector>` | Reconciles a profile workspace; owns its own routing |

Recipes take no tool, no `--task`, and no `--workspace`. Crews do take `--workspace`. Layout and fleet recipes create cmux workspaces, so they need cmux socket control (`automation.socketControlMode` in `~/.config/cmux/cmux.json`).

Re-running a crew adds only the tabs its workspace is missing — that is how you grow a crew you are already in.

## The common case: one named tab, no focus change

This is the workflow to reach for when the user says "add an agent" or "start a reviewer". Prefer the verified-launch script above. The equivalent wrapper command is:

1. **Inspect the current workspace first** with the `herdr` skill. Choose a task name that is not already a tab label there. If the label exists, the wrapper splits a new pane inside that existing tab instead of creating a tab — correct only when the user explicitly asked for a split.

2. **Choose the model and effort explicitly.** Inheriting is allowed only as a deliberate choice you state out loud before proceeding. Add `--yolo` (Codex) or other permission escalation only when the assigned scope genuinely needs it; never by default.

3. **Preview:**

   ```bash
   agents --dry-run --no-focus --current --herdr --herdr-control-only \
     --task <tab-name> --cwd "$PWD" \
     codex --model <model> -c model_reasoning_effort=<effort>
   ```

   Confirm two lines in the preview before going further:

   - `cwd=` is the exact absolute path requested.
   - `herdr_workspace=<current-terminal:<workspace-id>>` contains the workspace ID returned by `herdr pane current --current`, not merely another workspace with the same directory.

   Omit `--workspace` so the run inherits the caller's workspace. If either line is wrong, stop and resolve it — do not create anything.

4. **Run the identical command without `--dry-run`.** The control-only path creates the tab, starts the requested agent, prints JSON, and exits without attaching, prompting, or taking over your terminal.

Note that the preview's `command=` line ends in `&& exec herdr`. That tail is what a normal launch would do; `--herdr-control-only` exits before it. The preview shows the unfiltered command, so do not read that tail as a focus steal.

## Verify, then hand off

The creation command prints one JSON object. Keep these keys:

```
agent  agent_name  pane_id  reused  session  tab_id  tab_name  workspace_id
```

The wrapper's `reused` bit refers to the **workspace**, not the tab — `true` means an existing workspace was joined, which is normal inside Herdr. Tab ownership is the launcher's `owned` field: the receipt `tab_id` was absent from `herdr tab list` immediately before launch. `agent_name` is uniquified by the wrapper if it collides, so read it back rather than assuming the name you asked for. Never close a tab with `owned` false or missing.

Then use the `herdr` skill against those exact IDs to confirm the agent reports the requested kind, tab, absolute working directory, permissions, and the selected model and effort — and that it is ready for input. Herdr returning success from its start path is the readiness evidence; confirm state before sending work.

From that point on: `herdr agent prompt`, `herdr agent wait`, `herdr agent read`, and Herdr's own cleanup commands. Never reach back for `agents`. Close only a session this launch owns; prove ownership from the receipt `owned` field (tab was not preexisting).

## Providers and models

`claude-muse`, `claude-ollama`, `claude-ollama-local`, `claude-ollama-cloud`, and `claude-deepseek` are all the same Claude CLI pointed at a different host that speaks the Anthropic Messages protocol. Every `claude` option still works.

The provider flag and `--model` are **not** the same thing. `--model` keeps its Claude Code meaning and passes straight through; the provider flag selects the model that provider serves and validates it against that provider's catalog before launching:

```bash
agents --task "..." claude --deepseek=deepseek-v4-flash
agents --task "..." claude --ollama-cloud=kimi-k3:cloud
```

List what is actually available by running these directly — they print and exit, so do not wrap them in `agents`:

```bash
cmux-claude --list-providers
cmux-claude --ollama-cloud --list-models
```

Ollama names normalize to the `:cloud` form, valid on both routes; a bare name works against ollama.com but 404s against the local daemon. `--lean` trims tools and MCP config for slow models and composes with any provider. Credentials come from the environment, or from the login keychain under service `com.jefcox.shell-env`.

Per-provider defaults are set by the `claude_launcher` Ansible role in the home-lab repo and overridable per run via `CLAUDE_<PROVIDER>_MODEL` / `CLAUDE_<PROVIDER>_BASE_URL`.

This plugin does not keep a private vendor or model roster. `python3 launcher.py roster` intersects the vendors the script knows how to flag with what the wrapper lists in `Tools:` on this machine, asked every time.

## Machine routing

`--mac-studio` (`--studio`), `--mac-mini` (`--mini`), `--laptop`, `--norns`, or `--remote <host>` run the launch over SSH on that box, using that host's own `~/.local/bin/herdr`. Transport is `--plain-ssh` by default; `--cmux-ssh` uses cmux's managed transport.

Not every host runs every tool — the default crew resolves per machine so it only offers agents that host can actually run. Check with `agents --crews` on the target rather than assuming parity.

## Safety rules

- Preview with `--dry-run` before any creation command. Confirm `cwd` and `herdr_workspace`.
- Use `--no-focus` unless the user asked to switch context.
- Honor the requested agent kind and topology exactly. Do not silently upgrade a tab into a crew or a machine view into a fleet.
- Do not add `--new`, `--recipe`, `--crew`, or a pane split unless asked for that shape.
- Escalate permissions only when the assigned scope requires it, and say so when you do.
- One creation command, then hand off to `herdr`. If you find yourself typing `agents` a second time for the same session, you are in the wrong tool.
- Do not close a session whose ownership you cannot prove from the launch receipt.
