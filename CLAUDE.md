# Claude Configuration for Infiquetra Claude Plugins

## 📓 Engineering journal — auto-maintain

Living journal at [`docs/engineering-journal/`](docs/engineering-journal/) (`LEARNINGS.md` / `DECISIONS.md` / `QUEUED.md` / `ARCHIVE.md` / `narratives/`). Follow the [shared engineering-journal practice](https://github.com/infiquetra/infiquetra-sdlc/blob/main/docs/process/engineering-journal.md) for the full pattern, and maintain it without being asked — capture durable learnings and decisions in the same commit that ships the change.

Repo-specific signals worth a `LEARNINGS.md` entry: marketplace registry drift, hook timing races, skill-activation gotchas, MCP env propagation, build-tool surprises. Plugin-pattern choices (skills-based vs CLI-based, version-bump strategy, hook event choice) belong in `DECISIONS.md`.

Any verify/review-class Agent-tool spawn made outside a saga skill must pass `subagent_type: saga:readonly-verifier` + `isolation: "worktree"` — see `plugins/saga/references/sandbox-spawn-sites.md` for the full spawn-site inventory and rationale. If `saga:readonly-verifier` is unavailable in the session, use the fallback ladder documented in that file's "Fallback when `saga:readonly-verifier` is unavailable" section — never fail the spawn outright or revert to unsandboxed.

## Repository Information

- **Repository**: infiquetra-claude-plugins
- **Purpose**: Claude Code plugins for Infiquetra development workflows
- **Organization**: Infiquetra

## Plugin Types

This repository contains two types of Claude Code plugins:

### Skills-based Plugins
Markdown-driven plugins that provide Claude with knowledge, patterns, and agent definitions. No Python scripts required.

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── agent-name.md       # Agent system prompt + trigger conditions
├── skills/
│   └── skill-name/
│       ├── SKILL.md        # Skill definition with frontmatter
│       └── references/     # Supporting reference documents (.md)
├── README.md
└── CHANGELOG.md
```

**Examples**: `saga`, `home-lab-ops`. Note: `team-execution` is primarily skills-based but is now
**hybrid** — it also carries a CLI script (`skills/team-execution/scripts/artifact_pointer.py`) beside
its skills/agents; see DECISIONS `{#artifact-pointer-ktds-291}`.

### CLI-based Plugins
Python CLI scripts wrapped as Claude skills/commands for interacting with external services.

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── agent-name.md
├── skills/
│   └── skill-name/
│       ├── SKILL.md
│       └── scripts/
│           └── service_client.py   # CLI implementation
├── commands/
│   └── command.md
├── README.md
└── CHANGELOG.md
```

**Examples**: `mission-control`, `unifi`, `deploy`, `redis-channel`

## Plugin Development Guidelines

### Naming Conventions
- Plugin directories: `kebab-case` (e.g., `redis-channel`)
- Python files: `snake_case` (e.g., `unifi_network_client.py`)
- Classes: `PascalCase` (e.g., `UnifiNetworkClient`)
- Skill names in frontmatter: `kebab-case` (e.g., `unifi-network`)

### Code Quality Standards
- Python 3.12+ required
- Type hints enforced with mypy
- Ruff linting with 100-character line limit
- Minimum 80% test coverage
- Security scanning with bandit

### Testing Requirements
- Unit tests for all CLI-based plugins (in `tests/` at repo root)
- Test files named `test_<plugin_client>.py`
- Use pytest as the test framework
- Add shared fixtures to `tests/conftest.py`

### plugin.json Required Fields
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Clear description of what the plugin does",
  "author": {
    "name": "Infiquetra",
    "email": "hello@infiquetra.com"
  },
  "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
  "keywords": ["relevant", "tags"]
}
```

## Development Workflow

1. Scaffold plugin: `./tools/create-plugin.sh my-plugin`
2. Implement in appropriate structure (skills-based or CLI-based)
3. Write tests in `tests/` for CLI plugins
4. Document in README.md
5. Add entry to `.claude-plugin/marketplace.json`
6. For every plugin behavior, schema, command, prompt, or user-facing guidance change, update the
   plugin release surfaces in the same PR: `plugins/<plugin>/.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json`, `plugins/<plugin>/CHANGELOG.md`, and any version/metadata
   drift guard tests. Do not treat code/tests as PR-ready until installed-plugin metadata tells the
   same story as the diff.
7. Submit PR for review

## Running Quality Checks

**Before pushing, run the whole gate — not a subset:**

```bash
# Supported long-run background invocation:
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
```

The full 24-step gate is expected to exceed common foreground tool timeouts (such as the default 10-minute / 600-second limit). Background the run and inspect progress or completion via the log file or the stable result marker:

```bash
# Poll progress
tail -5 /tmp/gate.log

# Read final status once complete (or interrupted)
cat /tmp/gate-run/result.txt
```

The marker is cleared when a run starts, so while the gate is in flight `result.txt` does not exist
yet — absence means "still running or killed outright", never "green".

### Safe Re-entry Rule (Duplicate-Run Protection)

If a previous gate run timed out (e.g. killed at 600s with exit 143), was interrupted, or is suspected to be already running:

1. **Check if already running**: `pgrep -fl "scripts/gate.sh"`
2. **Terminate the stale process**: kill the pid step 1 named — `kill <pid>`. Avoid
   `pkill -f "scripts/gate.sh"` unless you mean it: it kills every gate on the machine, including
   live gate runs in your other worktrees.
3. **Clean state & re-enter**: Ensure the log directory is clean or specify a new `GATE_LOG_DIR=/tmp/gate-run`, then restart the backgrounded gate run.

Exit codes: `0` green · `1` a blocking step failed · `2` coverage is short of `ci.yml` · `3` precondition failed (missing dev dependencies, missing Node/npm for the Mermaid syntax check, or an unwritable log directory).

### Gate Coverage Contract

CI runs **twenty-four** substantive pre-merge steps across six jobs. This file used to
document four of them, and the gap was patched one command at a time as each drift was
discovered ("CI runs BOTH ruff commands", "match CI's mypy scope") — which is a losing
race, because a hand-maintained list falls behind silently and a shortfall in coverage
reports green.

`scripts/gate.sh` runs all twenty-four and **checks its own coverage against
`.github/workflows/ci.yml`**. Add a step to the workflow and the gate fails with
`GATE INCOMPLETE` until the step is covered. That property is the point of the script;
do not weaken it. In particular, never mark a step advisory to make the gate pass —
advisory status is reserved for steps CI itself does not block on (a trailing
`|| true`, or a live-gated check the runner cannot perform).

Individual commands, for a fast inner loop only — **a clean run of these is not a
green gate**:

```bash
# One test file
uv run pytest tests/test_deploy_plugin.py -v

# Lint (CI runs BOTH — a check-clean tree can still fail the format gate)
uv run ruff check .
uv run ruff format --check .

# Types (match CI scope — plugins/ scripts/ tests/, not just plugins/)
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

## Scaffold New Plugin

```bash
./tools/create-plugin.sh my-new-plugin
```
