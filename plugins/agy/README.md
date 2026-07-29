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

- Version `0.5.0` is registered in `.claude-plugin/marketplace.json`.
- The command, skill, reference, two bridge-agent prompts, wrapper, and harness audit are packaged.
- Every launched run writes a local evidence bundle under `.claude/agy/runs/<run-id>/`.
- Live Claude Code harness proof is recorded in `docs/harness-proof.md`.

## Write Modes

No mode writes the live tree. Every run happens in a disposable, remotes-stripped clone and hands
back a patch for the caller to apply, matching the codex plugin's contract.

- `no-write`: reviewer default. The wrapper runs `agy` in foreground print mode with `--sandbox`.
- `patch-only`: coder default. Derives and preserves `diff.patch`, scores changed paths against the
  declared write-set, and runs any declared verification commands inside the clone.

Verification is terminal only when `verification.required` is set: a required command that fails
yields `checks_failed`, while an unrequired one is recorded in `checks.json` and leaves the run
`patch_ready`.

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

That gate ran against the v0.1.0 contract. `auto-if-clean` was retired in 0.6.0 (#671), so the
coder half is not reproducible as written — `docs/harness-proof.md` is kept as the dated record of
what was proven at the time, not as a runnable procedure.
