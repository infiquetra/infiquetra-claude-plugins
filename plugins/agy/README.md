# agy

Dormant scaffold for Infiquetra Antigravity-backed teammate delegation.

The plugin will expose:

- `/agy:delegate` as the direct operator command.
- `agy-coder` as the Bash-only coding bridge agent.
- `agy-reviewer` as the Bash-only review bridge agent.

All command and agent surfaces route through the future shared wrapper:

```bash
python3 plugins/agy/scripts/agy_delegate.py
```

This scaffold is intentionally not registered in `.claude-plugin/marketplace.json` yet. Marketplace
registration, release readiness claims, and live harness proof land after the wrapper, evidence
contract, patch gate, prompt contracts, and harness audit are implemented.

## Current Status

- Plugin metadata exists at `.claude-plugin/plugin.json`.
- The command, skill, reference, and two bridge-agent prompt shells are packaged.
- The wrapper path is documented but not implemented in U1.
- No marketplace entry should exist for `agy` during this dormant phase.

## Packaged Surfaces

```text
agy/
├── .claude-plugin/plugin.json
├── agents/
│   ├── agy-coder.md
│   └── agy-reviewer.md
├── commands/
│   └── delegate.md
├── skills/
│   └── agy-delegate/
│       ├── SKILL.md
│       └── references/
│           └── delegation-contract.md
├── README.md
└── CHANGELOG.md
```

## Readiness Gate

Do not advertise this plugin as ready until the wrapper exists, direct wrapper tests pass, and a
live packaged Claude Code harness proves the agents invoke `plugins/agy/scripts/agy_delegate.py`
and the external `agy` process instead of solving locally.
