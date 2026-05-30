---
date: 2026-05-30
topic: delegate-agent-plugin
focus: Codex and Antigravity delegation from Claude Code
status: ideation
---

# Ideation: Delegate Agent Plugin For Codex And Antigravity

## Executive Summary

Building a Claude Code plugin that delegates work to local Codex and Antigravity runtimes is
feasible, but the two backends are not equally mature.

Codex is the stronger first backend. This machine already has `codex-cli 0.135.0`, and
`codex exec` successfully completed a non-interactive probe using the local Codex login, with no
API key passed by the plugin or shell. The installed official OpenAI Claude Code plugin also proves
the shape: Claude Code command -> thin subagent -> Node companion script -> local `codex app-server`
thread or `codex exec`-style turn.

Antigravity is plausible for prompt-based read-only delegation today. The local `agy 1.0.3` CLI has
`--print`, conversation resume, workspace directory, sandbox, timeout, and plugin commands, and a
non-interactive prompt probe succeeded using local Antigravity auth/config. The risk is that the CLI
surface is not yet as clearly structured as Codex for job state, output schema, touched files, and
write-mode safety. Rich Antigravity delegation probably needs a focused SDK spike rather than only a
CLI shim.

The best first product is a separate `delegate-agents` plugin, not a direct rewrite of
`team-execution`. It should expose a provider-neutral agent contract:

```text
delegate-agent run --provider codex|antigravity --agent <agent.md> --prompt <task>
```

Then `team-execution` can opt into that runtime per worker, reviewer, or validator. Reviewer and
explorer agents are the right first use cases because they are read-only, evidence-oriented, and do
not require external CLIs to own file mutation. Coder agents should come later, ideally with isolated
worktrees or strict write ownership.

Follow-up note after reviewing MCP and app surfaces: the original recommendation was directionally
right but underweighted three paths. Codex App Server should be the preferred rich Codex integration,
not merely an optional later upgrade. MCP should be considered a compatibility/control-plane route,
especially for invoking Codex from MCP-native systems, but not the primary route when the plugin
needs Codex-specific session events, approvals, diff telemetry, and thread control. Antigravity 2.0
should be treated as more than `agy --print`: the installed desktop app and public SDK position it
as an agent platform with MCP and skills, so the Antigravity spike should explicitly compare CLI,
SDK, and any documented app/deep-link surface rather than only prompt mode.

## Grounding

### Local Repository

This repository already packages Claude Code plugins with:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `agents/*.md`
- `skills/<skill>/SKILL.md`
- `commands/*.md`
- `README.md`
- `CHANGELOG.md`
- root marketplace registration in `.claude-plugin/marketplace.json`
- contract tests under `tests/`

`team-execution` is a good integration target but not the right first implementation surface.
Its workers are plan rows orchestrated by the main agent. Its reviewers and validators are packaged
Claude Code agents selected by registry references. That means external delegates should be an
optional execution mode attached to selected roles, not an assumption baked into all team planning.

### Local Runtime Evidence

Codex:

- `which codex` resolved to `/opt/homebrew/bin/codex`.
- `codex --version` returned `codex-cli 0.135.0`.
- `codex exec --help` exposes non-interactive prompt/stdin mode, `--sandbox`, `--ephemeral`,
  `--json`, `--output-schema`, `--output-last-message`, `--model`, `--profile`, `--cd`, and
  `--add-dir`.
- `codex exec --ephemeral --sandbox read-only --output-last-message ... 'Reply with exactly:
  CODEX_OK'` succeeded when run with normal process permissions.
- In the Codex harness sandbox, nested `codex exec` initially failed with
  `failed to initialize in-process app-server client: Operation not permitted`. That is an
  environment constraint, not a product blocker, but the plugin must surface this class of failure.

Antigravity:

- `which agy` resolved to `/Users/jefcox/.local/bin/agy`.
- `agy --version` returned `1.0.3`.
- `agy --help` exposes `--print`, `--prompt`, `--prompt-interactive`, `--continue`,
  `--conversation`, `--sandbox`, `--add-dir`, `--print-timeout`, `--log-file`, and plugin
  management commands.
- `agy --print-timeout 10s --print 'Reply with exactly: AGY_OK'` succeeded.
- The first Antigravity probe emitted local config/log permission noise and created a repo-local
  `.antigravitycli/<uuid>.json` file. The plugin should treat Antigravity as a CLI that may create
  local project metadata and should document or redirect that state explicitly.
- `/Applications/Antigravity.app` is installed. Its `Info.plist` reports bundle identifier
  `com.google.antigravity`, version `2.0.10`, and URL scheme `antigravity`.

Desktop apps:

- `/Applications/Codex.app` is installed. Its `Info.plist` reports bundle identifier
  `com.openai.codex`, version `26.527.31326`, and URL scheme `codex`.
- `/Applications/Antigravity.app` is installed as noted above.
- Neither desktop app should be treated as the first automation target without a documented control
  API. The better route is to use the same lower-level surfaces the apps use or expose: Codex App
  Server for Codex, and Antigravity CLI/SDK/MCP configuration for Antigravity.

### Existing Delegation Patterns

The installed OpenAI Claude Code plugin is the closest reference implementation. Its manifest
describes the plugin as using Codex from Claude Code to review code or delegate tasks. Its
`/rescue` command invokes a `codex:codex-rescue` subagent, and that subagent is deliberately thin:
it forwards exactly one Bash call to `scripts/codex-companion.mjs`.

Key architectural details worth copying conceptually:

- Claude Code keeps orchestration and command UX.
- The subagent is a wrapper, not an independent problem solver.
- A companion script owns runtime flags, foreground/background mode, resume, output handling, and
  state.
- Codex app-server turns can run read-only or workspace-write based on the task.
- Background jobs and result retrieval are explicit commands, not hidden chat state.

The Compound Engineering `ce-work-beta` skill already has a simpler Codex delegation model:
Claude plans and orchestrates; implementation units can be delegated to `codex exec`; consent and
sandbox mode live in repo-local config. That is a good safety model for this repo to borrow.

### Additional Route Analysis: MCP, App Server, And Desktop Apps

#### Codex App Server

Codex App Server is the strongest rich Codex route. OpenAI's public App Server material says Codex
surfaces share the same harness, and the App Server is the first-class integration method for rich
clients. The local CLI confirms this surface exists:

```text
codex app-server [--listen stdio://|unix://|ws://IP:PORT|off]
codex app-server generate-ts --out DIR
codex app-server generate-json-schema --out DIR
```

This matters because a delegate plugin needs more than a final string. It needs thread creation,
turn start, streaming events, approvals, sandbox mode, model choice, cwd, interrupt, resume, and
evidence. App Server is built around those primitives.

Recommendation: use `codex exec` for the first minimal read-only spike, but design the Codex adapter
interface so App Server is the default rich implementation once the wrapper grows job state,
background mode, or write-capable delegates.

#### Codex MCP Server

Codex also exposes `codex mcp-server`. OpenAI documents it as an experimental MCP server interface
over stdio that can manage Codex threads, turns, accounts, config, models, and approvals. The local
CLI confirms the command exists:

```text
codex mcp-server
```

This route is worth considering, but its role is narrower:

- Best fit: an MCP-native orchestrator wants to call Codex as a tool.
- Good for: interoperability with systems that already load MCP servers.
- Poor fit as primary route: MCP tends to flatten provider-specific session semantics, and OpenAI's
  own App Server guidance says richer interactions such as diff updates may not map cleanly through
  MCP endpoints.

Recommendation: keep MCP as a secondary adapter candidate. It may be useful if `delegate-agents`
itself becomes an MCP server or if another Infiquetra orchestrator wants to call Codex through a
standard tool interface. Do not make MCP the first Codex implementation unless the target integration
is specifically MCP-native.

#### Codex Desktop App

The installed Codex desktop app is evidence that this machine has the richer Codex surface, but it
is probably not the right automation target. The app has a `codex://` URL scheme, but a URL scheme is
not the same as a stable agent-control API. Treat the desktop app as a user-facing client over Codex
harness/App Server, not as the delegate runtime.

Possible exception: a later UX command could open a Codex thread or result in the desktop app if
Codex documents a deep-link format. That is review/display UX, not the core delegation mechanism.

#### Antigravity 2.0 Desktop App

The original doc treated Antigravity mostly as `agy --print` plus a possible SDK. That is too narrow.
Antigravity 2.0 is installed locally, and public Google material describes it as a standalone
desktop app for managing agents, with skills and MCP server integration. The app also has an
`antigravity://` URL scheme.

The practical reading:

- `agy --print` is still the easiest probe path.
- The Antigravity SDK is likely the right route for rich nested-agent control, traces, and
  structured orchestration.
- MCP is important on the Antigravity side too, but likely as "tools available to Antigravity
  agents" rather than "Claude Code controls Antigravity agents through MCP" unless Google exposes an
  MCP server equivalent to Codex's.
- The desktop app may become useful for monitoring delegated work, but should not be assumed to
  provide a stable control API just because the app exists.

Recommendation: rename the Antigravity spike from "CLI adapter" to "Antigravity control-surface
spike" and compare three routes: CLI prompt mode, SDK runner, and any documented app/deep-link or MCP
control surface.

## Feasibility Matrix

| Capability | Codex | Antigravity |
|------------|-------|-------------|
| Local auth without plugin API keys | High | High |
| Non-interactive prompt execution | High | High |
| Read-only reviewer/explorer delegate | High | Medium-high |
| Structured final output | High via `--output-schema` or app-server handling | Medium, needs confirmation |
| Background/resume/job model | High via app-server or companion state | Medium, CLI has conversations but job control needs wrapper |
| Write-capable coder delegate | Medium-high with sandbox/worktree discipline | Medium-low until write semantics are proven |
| Touched-file/event telemetry | High through app-server path | Unknown through CLI; likely SDK needed |
| MCP-native control | Medium, experimental `codex mcp-server` exists | Unknown as control surface; MCP support appears stronger as tool integration |
| Desktop-app control | Low-medium; app exists but App Server is the better control API | Unknown; app exists, SDK likely better |
| Clean plugin packaging | High | Medium-high |
| Maintenance risk | Medium because app-server protocol can drift | Medium because CLI/SDK is young |

## Recommended Shape

Build a new `delegate-agents` plugin first. It should package:

- A slash command, for example `/delegate-agent`.
- One or more thin subagents, for example `delegate-runner`, `delegate-reviewer`,
  `delegate-explorer`.
- A skill documenting when to delegate and how to interpret results.
- A small runtime wrapper script that normalizes Codex and Antigravity invocation.
- A state directory for jobs, transcripts, result summaries, and evidence paths.
- Contract tests for manifest, command references, and wrapper prompt construction.

Do not copy the OpenAI plugin source wholesale. Use it as a local architecture reference. A source
copy would create avoidable upstream drift and licensing/maintenance questions. The safer route is
to implement a thin Infiquetra-specific adapter with explicit provider interfaces.

Suggested runtime contract:

```json
{
  "provider": "codex",
  "role": "reviewer",
  "agent_file": "plugins/delegate-agents/agents/security-reviewer.md",
  "workspace": "/path/to/repo",
  "mode": "read-only",
  "prompt": "Review this diff for auth regressions.",
  "output_schema": "review-finding-list-v1",
  "timeout_seconds": 900,
  "resume": false
}
```

The wrapper should render the actual delegate prompt from:

- the selected `agent.md` contents
- task prompt
- workspace path and repository summary
- allowed tools/mode
- expected output schema
- evidence requirements
- explicit instruction to avoid secrets and production data

Passing only `agent.md + prompt` is not enough. The wrapper also needs mode, timeout, output
contract, state path, resume behavior, and a safety policy.

## Ranked Ideas

### 1. Provider-Neutral `delegate-agents` Plugin

**Description.** Add a new plugin that exposes one common delegation contract and provider adapters
for Codex and Antigravity.

**Basis.** Codex and Antigravity both support local non-interactive prompt execution. Existing repo
conventions support plugins with commands, agents, skills, README, CHANGELOG, and tests.

**Why it is promising.** Keeps provider-specific volatility out of `team-execution`. Gives the team
a small surface to test before making delegation part of larger workflows.

**Downside.** Adds a new plugin and wrapper surface before the team-execution UX is fully known.

**Confidence.** High.

**Complexity.** Medium.

### 2. Read-Only Reviewer And Explorer Delegates First

**Description.** Start with roles that inspect, summarize, and produce evidence: reviewer,
explorer, issue-triage, spec-review, architecture-risk, dependency-risk.

**Basis.** These roles map well to both `codex exec --sandbox read-only` and `agy --print` with
workspace context.

**Why it is promising.** Read-only delegation gives useful signal while avoiding cross-agent file
ownership problems.

**Downside.** It does not immediately solve parallel implementation throughput.

**Confidence.** High.

**Complexity.** Low-medium.

### 3. Codex Adapter With Three Modes

**Description.** Support a simple `codex exec` adapter first, then add App Server as the preferred
rich adapter, with `codex mcp-server` as a secondary MCP-native option.

**Basis.** `codex exec` is documented and already provides output files, JSONL events, schemas,
sandbox selection, and cwd control. The installed OpenAI plugin proves the app-server path for
background/resume/touched-file tracking. OpenAI also documents `codex mcp-server` as an
experimental MCP route.

**Why it is promising.** The simple adapter is easy to test. App Server matches the eventual needs
of delegate agents: thread state, turn events, approvals, cwd, sandbox, interrupts, and structured
runtime state. MCP gives a standards-based fallback for MCP-native orchestrators.

**Downside.** `codex exec` alone may not provide the same polished job lifecycle as the official
plugin. App Server integration takes more client code. MCP is experimental and may lose
Codex-specific detail.

**Confidence.** High for `exec`; high for App Server feasibility; medium for MCP as primary route.

**Complexity.** Low for `exec`; medium-high for App Server; medium for MCP.

### 3a. MCP Bridge As Compatibility Layer

**Description.** Let `delegate-agents` optionally expose or consume MCP: expose a local MCP server so
Claude Code or other orchestrators can invoke `delegate.run`, and/or consume Codex through
`codex mcp-server`.

**Basis.** This repo already has MCP plugin patterns through `redis-channel`; Codex has an
experimental MCP server; Antigravity 2.0 material emphasizes MCP server integration.

**Why it is promising.** MCP gives a common control surface across tools and could make delegation
usable outside Claude Code. It also aligns with Antigravity's plugin/tool ecosystem.

**Downside.** MCP is a lowest-common-denominator shape for agents. It is good at tool calls, weaker
at rich agent session semantics unless the MCP surface explicitly models threads, approvals,
interrupts, and streaming events.

**Confidence.** Medium.

**Complexity.** Medium.

### 4. Antigravity Control-Surface Spike

**Description.** Compare three Antigravity routes: `agy --print`, Antigravity SDK, and any
documented desktop app/deep-link or MCP control surface.

**Basis.** Local `agy --print` worked. The CLI supports conversation IDs and workspace dirs. The
installed desktop app is Antigravity 2.0.10, and public Google material describes Antigravity 2.0,
the CLI, SDK, skills, and MCP server integration as parts of one agent platform.

**Why it is promising.** It gives immediate access to Antigravity as a second independent reviewer
or explorer, while keeping the door open to the richer SDK/app route if prompt mode is too thin.

**Downside.** Structured output, file mutation, job telemetry, SDK packaging, and desktop-app control
need proof. Antigravity may write project metadata such as `.antigravitycli/`.

**Confidence.** Medium.

**Complexity.** Low-medium for CLI; medium-high for SDK/app integration.

### 5. Antigravity SDK Spike For Rich Agent Control

**Description.** Prototype a tiny SDK-backed runner only after the CLI adapter proves useful.

**Basis.** Public Antigravity material describes async agents, sub-agent delegation, and nested run
trees in the SDK. That sounds closer to the desired reviewer/coder/explorer agent model than bare
CLI print mode.

**Why it is promising.** The SDK is likely the right path for nested agents, structured traces, and
multi-agent delegation.

**Downside.** It may require a separate TypeScript or Python runtime, more dependencies, and a
different packaging story from current simple plugins.

**Confidence.** Medium.

**Complexity.** Medium-high.

### 6. Team-Execution Optional Delegation Roster

**Description.** Extend `team-execution` later with a role-level runtime choice:

```markdown
| Role | Agent | Runtime | Mode | Provider |
|------|-------|---------|------|----------|
| reviewer | security-reviewer | delegate | read-only | codex |
| explorer | api-contract-explorer | delegate | read-only | antigravity |
| worker | docs-worker | local | workspace-write | claude |
```

**Basis.** `team-execution` already selects reviewers, validators, workers, and gates by context.

**Why it is promising.** It preserves current consensus and validator gates while allowing selected
roles to run outside Claude Code's backend.

**Downside.** It must not obscure who changed files or which gate produced which evidence.

**Confidence.** Medium-high.

**Complexity.** Medium.

### 7. Coder Delegates In Isolated Worktrees

**Description.** Allow write-capable delegates only in separate git worktrees or tightly scoped
file ownership batches.

**Basis.** External CLIs can mutate the same working tree. Parallel write agents can step on each
other unless each owns a workspace or a disjoint file set.

**Why it is promising.** This is the path to real parallel implementation throughput.

**Downside.** Worktree lifecycle, patch import, conflict handling, and test attribution are
nontrivial.

**Confidence.** Medium.

**Complexity.** High.

## Proposed Phase Plan

### Phase 0: Spike And Contracts

- Define `delegate-run-v1` JSON request and result shapes.
- Probe `codex exec` with `--output-schema`, `--json`, read-only, and workspace-write.
- Probe Codex App Server with generated JSON schema and one `thread/start` plus `turn/start`
  read-only run.
- Probe `codex mcp-server` with an MCP inspector or minimal MCP client to verify which thread/turn
  controls are actually available through MCP.
- Probe `agy --print` with required JSON output, `--conversation`, `--sandbox`, `--add-dir`, and
  `--log-file`.
- Probe Antigravity SDK basics against one read-only reviewer task.
- Check whether Antigravity 2.0 documents a stable deep-link, local app API, or MCP control surface
  for starting or monitoring agent tasks.
- Decide where provider state lives and how to keep it ignored.
- Write a short security/consent note.

Exit criteria:

- Both providers can run a read-only reviewer prompt and return parseable results.
- Codex route choice is explicit: `exec` for minimal v1, App Server for rich v1, or MCP only if the
  target caller is MCP-native.
- Antigravity route choice is explicit: CLI-only, SDK-backed, or app-mediated.
- Failure modes are captured as structured errors.
- The Antigravity metadata behavior is understood.

### Phase 1: New Plugin

- Add `plugins/delegate-agents/`.
- Add manifests, README, CHANGELOG, command, skill, and thin subagent.
- Implement a minimal wrapper script with `codex` and `antigravity` provider adapters.
- Add tests for manifest, marketplace entry, prompt rendering, and command references.

Exit criteria:

- `/delegate-agent --provider codex --agent reviewer --prompt ...` works.
- `/delegate-agent --provider antigravity --agent explorer --prompt ...` works in read-only mode.
- Results are written to predictable state paths.

### Phase 2: Team-Execution Integration

- Add optional `.team-execution.json` keys for delegate preferences.
- Add delegation columns to generated team plans only when configured or explicitly requested.
- Route selected reviewers/explorers through `delegate-agents`.
- Keep validators and gates unchanged.

Exit criteria:

- Existing team-execution plans are unchanged by default.
- Explicit delegation requests produce role-level delegate assignments.
- Reviewer consensus can include delegated reviewer evidence.

### Phase 3: Coder Delegates

- Add worktree-per-coder support or strict file-set ownership.
- Require explicit consent for write-capable delegates.
- Require post-delegate diff review by Claude Code before tests or commit.

Exit criteria:

- A delegated coder can produce a patch without overwriting unrelated user work.
- The orchestrator can attribute files, tests, and remediation loops.

## Rejected Or Deferred Ideas

### Copy The OpenAI Codex Plugin Source Wholesale

Reject for now. It proves the design, but copying it would import upstream implementation details
and create drift. Prefer a small adapter that uses stable CLI surfaces first.

### Drive Codex Through The Desktop App UI

Reject for core delegation. Codex Desktop is installed and likely useful to inspect or resume work,
but the stable automation target is App Server, not GUI automation or an undocumented `codex://`
deep link.

### Replace Claude Code Subagents Entirely

Reject. Claude Code's Agent tool and plugin model are still useful for routing, UX, orchestration,
and local policy. Delegates should supplement the current system.

### Make Delegation The Default In Team-Execution

Reject for now. Delegation sends prompts and repository context through other local agent accounts.
It needs explicit opt-in, local consent, and clear state paths before becoming a default.

### Use Antigravity As A Write-Capable Coder Backend Immediately

Defer. The prompt mode works, but write behavior, structured output, and state management need a
separate proof.

### Treat MCP As The Only Abstraction

Reject for now. MCP should be supported where it helps interoperability, but making it the only
abstraction would hide provider-specific strengths such as Codex App Server event streams,
approvals, diff telemetry, and thread control.

### One Universal Prompt Shim With No State

Reject. It is tempting, but insufficient. Useful delegation needs job IDs, transcripts, result
files, resume or rerun behavior, timeouts, and evidence paths.

## Open Questions

1. Does `agy --print` reliably honor strict JSON instructions across realistic review prompts?
2. Can Antigravity redirect or suppress `.antigravitycli/` project metadata, or should the plugin
   document and ignore it?
3. Which Antigravity SDK language/runtime fits this repository if richer agent control is needed?
4. Does Antigravity 2.0 expose a documented control surface for starting or monitoring tasks outside
   the app UI, or is the SDK the only supported rich route?
5. Should Codex app-server integration depend on the user's installed `codex` plugin, or should this
   repo implement only `codex exec` at first?
6. Should `delegate-agents` expose its own MCP server so non-Claude orchestrators can call the same
   provider-neutral delegation contract?
7. What consent model should apply when a delegate can see proprietary code, issue context, or
   secrets in config files?
8. How should delegated findings participate in `team-execution` consensus: equal reviewer vote,
   supporting evidence, or advisory signal?

## Recommendation

Proceed with a two-step feasibility build:

1. Create a small `delegate-agents` spike that supports read-only Codex and Antigravity delegates
   with structured results.
2. In that spike, treat Codex App Server as the likely rich Codex backend, Codex MCP as a secondary
   MCP-native backend, and Antigravity SDK/app-surface research as a first-class branch alongside
   `agy --print`.
3. After that works, update `team-execution` to optionally route reviewer/explorer roles through
   the new plugin.

Do not start with coder delegates and do not start by editing the main `team-execution` protocol.
That would couple a still-uncertain runtime layer to the most operationally sensitive plugin in this
repo. The right sequence is provider adapter first, read-only value second, team-execution
integration third, write-capable delegation last.

## References

Local:

- `plugins/team-execution/README.md`
- `plugins/team-execution/skills/team-execution/SKILL.md`
- `docs/PLUGIN_SPEC.md`
- `/Users/jefcox/.claude/plugins/cache/openai-codex/codex/1.0.4/`
- `/Users/jefcox/.codex/plugins/cache/compound-engineering-plugin/compound-engineering/3.9.3/skills/ce-work-beta/`
- `/Users/jefcox/.codex/plugins/cache/compound-engineering-plugin/compound-engineering/3.9.3/skills/ce-optimize/`

External:

- Claude Code plugins: <https://code.claude.com/docs/en/plugins>
- Claude Code subagents: <https://docs.anthropic.com/en/docs/claude-code/sub-agents>
- Codex CLI: <https://developers.openai.com/codex/cli>
- Codex non-interactive mode: <https://developers.openai.com/codex/noninteractive>
- Codex app-server: <https://developers.openai.com/codex/app-server>
- Codex App Server source README: <https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md>
- Codex MCP interface: <https://github.com/openai/codex/blob/main/codex-rs/docs/codex_mcp_interface.md>
- OpenAI App Server architecture: <https://openai.com/index/unlocking-the-codex-harness/>
- Antigravity CLI getting started: <https://antigravity.google/docs/cli-getting-started>
- Antigravity CLI plugins: <https://antigravity.google/docs/cli-plugins>
- Antigravity 2.0 overview: <https://www.antigravity.google/docs/overview>
- Antigravity SDK announcement: <https://antigravity.google/blog/introducing-google-antigravity-sdk>
- Antigravity SDK product page: <https://antigravity.google/product/antigravity-sdk?app=antigravity>
