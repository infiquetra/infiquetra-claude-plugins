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

- Version `0.1.0`: envelope schema (`codex.delegation.v1`), validation, and the
  `bridge_receipt.v1` emitter seam are packaged (U1 of
  `docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md`).
- The supervised `codex exec` runner, evidence-bundle writer, and diff-scan machinery land in
  follow-on units (U2/U3); until then the wrapper validates envelopes and exits nonzero rather
  than launching an unsupervised process.
- This plugin retires the upstream `openai-codex` marketplace plugin's `codex:codex-rescue` agent,
  whose fleet dispatch is session-scoped and cannot receipt (see the plan's Problem Frame). Once
  the retirement units land, uninstall the `openai-codex` marketplace plugin to avoid a `codex:`
  namespace collision.

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
