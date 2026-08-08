# fleet-core

Canonical home for cross-plugin shared primitives in the Infiquetra plugin fleet, plus the
canonical copy of the resolution shim that sibling plugins vendor to reach it. Decision record:
`docs/engineering-journal/DECISIONS.md` `{#fleet-commons-mechanism-463}` (issue #463).

This is a **scripts-only library plugin** — no skills, commands, agents, or hooks. Installing it
contributes nothing to a Claude Code session directly; it exists so other installed plugins can
resolve shared code at a single canonical location instead of hand-copying it (the
`validate_card_body` drift incident, #222, is the failure mode this prevents).

## Layout

```
fleet-core/
├── .claude-plugin/plugin.json
└── scripts/
    ├── fleet_commons_shim.py     # canonical shim — consumers vendor a byte-identical copy
    └── fleet_commons/            # the primitives, one stdlib-only module each
        └── tier_palette.py       # MODELS / EFFORTS / CHEAP_MODELS / ENGINE_INTENTS + ranks
```

## How a consumer plugin uses it

1. Vendor `scripts/fleet_commons_shim.py` into your plugin's `scripts/` directory,
   byte-identical (a repo drift-guard test compares every vendored copy to the canonical file).
2. Resolve and load:

   ```python
   import fleet_commons_shim

   tier_palette = fleet_commons_shim.load("tier_palette")
   tier_palette.model_rank("sonnet")
   ```

The shim resolves the fleet-core root by the first rung that succeeds — `FLEET_COMMONS_ROOT`
env override → repo-checkout walk-up → `~/.claude/plugins/installed_plugins.json` lookup →
cache-sibling scan — and fails loud with an actionable message when none does. Set
`FLEET_COMMONS_DEBUG=1` to print the resolution provenance
(`fleet-commons: rung=<n> (<name>) root=<path>`) to stderr.

## What belongs in commons — and what does not

**Belongs:** small, stdlib-only, fleet-wide vocabulary and pure helpers that would otherwise be
hand-copied — tier palettes, shared constants, tiny pure functions. Additive-only change within
0.x: a consumer never breaks because fleet-core updated.

**Does not belong:** anything with third-party dependencies (the marketplace install runs no
pip/venv step); plugin-specific business logic; anything that churns with a single plugin's
release cadence; contract mirrors (those are being abolished, not centralized).
