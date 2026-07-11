# codex

First-party, guarded, synchronous codex delegation bridge for Claude Code, mirroring the `agy`
wrapper's shape (`plugins/agy/scripts/agy_delegate.py`).

The plugin exposes:

- `/codex:delegate` as the direct operator command.
- `codex-coder` as the Bash-only coding bridge agent.
- `codex-reviewer` as the Bash-only review bridge agent.

All command and agent surfaces route through the shared wrapper:

```bash
python3 plugins/codex/scripts/codex_delegate.py
```

## Current Status

- Version `0.1.2` ships the full delegate surface
  (`docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md`, U1–U7): the
  `codex.delegation.v1` envelope schema with fail-loud validation, the supervised synchronous
  `codex exec` runner (timeout + no-output watchdogs, whole-tree kill with the kill outcome
  captured, SIGTERM/SIGINT die-clean across the whole bundle span, cumulative output byte cap),
  the evidence bundle under `.claude/codex/runs/<run-id>/` (all JSON written atomically),
  the enforced read-only reviewer diff-scan and coder disposable-clone modes, and
  `bridge_receipt.v1` emission for every launched run.
- Saga registry dispatch now selects explicit GPT-5.6 Sol, Terra, or Luna model/effort rows and
  forwards both values to `codex:delegate`. Direct envelopes may still omit them and use the local
  Codex configuration default. Registry and bridge provenance use the canonical
  `<model>-<effort>` identity.
- **Invoking the wrapper without `--validate-only`/`--dry-run` launches a live, supervised
  `codex exec` subprocess.** The validate-only path is opt-in, not the default.
- This plugin retires the upstream `openai-codex` marketplace plugin's `codex:codex-rescue` agent,
  whose fleet dispatch is session-scoped and cannot receipt (see the plan's Problem Frame).
  Uninstall the `openai-codex` marketplace plugin to avoid a `codex:` namespace collision (see
  the runbook below).

## Operator Runbook: Retiring the `openai-codex` Marketplace Plugin

This plugin is the first-party replacement for the upstream `openai-codex` marketplace
plugin's fleet-dispatch surface (former `codex:codex-rescue` agent and its
`codex:rescue` / `codex:status` / `codex:result` / `codex:cancel` / `codex:transfer` /
`codex:review` / `codex:adversarial-review` / `codex:setup` command family). That upstream
dispatch path is session-scoped: its jobs die when the launching session's process tree is
reaped, it cannot emit `bridge_receipt.v1` evidence, and reaped jobs stay recorded as
`running` forever. All in-repo callers (saga's engine registry and `engine_dispatch.py`)
have been rewired to `codex:delegate` — nothing in this repository dispatches to
`codex:codex-rescue` any longer.

**`codex:` namespace collision.** Both the `openai-codex` marketplace plugin and this
first-party `codex` plugin claim the `codex:` agent/command namespace prefix. With both
installed, agent/command resolution for `codex:*` is ambiguous and may resolve to the
retired marketplace copy instead of this plugin's `codex-coder` / `codex-reviewer` agents
and `/codex:delegate` command. **Uninstall the `openai-codex` marketplace plugin before
relying on this plugin's `codex:` surfaces.**

To uninstall the marketplace copy:

```bash
/plugin marketplace remove openai-codex   # or your marketplace's equivalent uninstall path
```

Then verify no `codex:` command other than this plugin's remains:

```bash
/help | grep '^codex:'
```

Only `codex:delegate` (this plugin) should be present. If any of the retired
`codex:rescue` / `codex:status` / `codex:result` / `codex:cancel` / `codex:transfer` /
`codex:review` / `codex:adversarial-review` / `codex:setup` commands still resolve, the
marketplace plugin is still installed — repeat the uninstall step.

Cross-repo retirement (removing `openai-codex` from fleet-standard install manifests in
other repos, e.g. home-lab-ops, infiquetra-context-library) is out of scope for this repo
and tracked as a separate ops follow-up.

## Modes

- `read-only`: reviewer default. Runs codex with `-s read-only`; no mutation is permitted.
- `task`: coder mode. Write-capable, but scoped to a disposable clone only (KTD5) — a run always
  preserves its patch in the evidence bundle and never applies to the live tree in v1.

## Packaged Surfaces

```text
codex/
├── .claude-plugin/plugin.json
├── agents/
│   ├── codex-coder.md
│   └── codex-reviewer.md
├── commands/
│   └── delegate.md
├── skills/
│   └── codex-delegate/
│       └── SKILL.md
├── scripts/
│   ├── codex_delegate.py
│   └── fleet_commons_shim.py
├── README.md
└── CHANGELOG.md
```
