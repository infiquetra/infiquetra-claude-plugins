# agy

Antigravity-backed teammate delegation for Claude Code.

The plugin exposes:

- `/agy:delegate` as the direct operator command.
- `agy-coder` as the Bash-only coding bridge agent.
- `agy-reviewer` as the Bash-only review bridge agent.

All command and agent surfaces route through the shared wrapper:

```bash
python3 plugins/agy/scripts/agy_delegate.py
```

## Current Status

- Version `0.1.0` is registered in `.claude-plugin/marketplace.json`.
- The command, skill, reference, two bridge-agent prompts, wrapper, and harness audit are packaged.
- Every launched run writes a local evidence bundle under `.claude/agy/runs/<run-id>/`.
- Live Claude Code harness proof is recorded in `docs/harness-proof.md`.

## Write Modes

- `no-write`: reviewer default. The wrapper runs `agy` in foreground print mode with `--sandbox`.
- `patch-only`: derives and preserves `diff.patch`; it never applies to the live tree.
- `auto-if-clean`: applies only when the live repo is clean, the write-set is explicit, real `agy`
  provenance is proven, changed paths are in scope, required verification passes, and `git apply`
  produces only expected changes.

## Packaged Surfaces

```text
agy/
├── .claude-plugin/plugin.json
├── agents/
│   ├── agy-coder.md
│   └── agy-reviewer.md
├── commands/
│   └── delegate.md
├── docs/
│   └── harness-proof.md
├── skills/
│   └── agy-delegate/
│       ├── SKILL.md
│       └── references/
│           └── delegation-contract.md
├── scripts/
│   ├── agy_delegate.py
│   └── audit_harness_transcript.py
├── README.md
└── CHANGELOG.md
```

## Harness Proof

The v0.1.0 release gate ran one packaged `agy-reviewer` no-write flow and one packaged
`agy-coder` `auto-if-clean` write flow in scratch repos. The transcript audit proved both agents
invoked `plugins/agy/scripts/agy_delegate.py`, launched real `agy`, and avoided Claude file-edit
tools. The coder proof applied `target.txt` through the wrapper gate.
