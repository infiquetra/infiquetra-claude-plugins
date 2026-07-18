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
        ├── lease_broker.py       # TTL admission, settlement, close CAS, release, and safe sweep
        ├── orphan_evidence.py    # closed evidence, bounded quarantine, read-only projection
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

## Lease authority

`lease_broker.py` is protocol version 2 and owns one runtime-neutral registry for separate `agent`
and `worktree` pools. Consumers reserve before spawn, bind provider identity after start, renew only
at cooperative boundaries, and release with their stored owner/token evidence. The default root is
`$INFIQUETRA_FLEET_STATE_DIR`, then an absolute safe XDG state root, then
`~/.local/state/infiquetra/fleet-leases`; Claude, Codex, and plugin cache directories are not
fallbacks.

Operators inspect the redacted view through `plugins/saga/scripts/lease_broker.py inspect` and run
the canonical dead-owner selection through `... sweep`. Do not hand-edit the registry or fabricate
tokens. Live owners, ambiguous children, and failed worktree reaps remain retained for the owning
coordinator. See Saga's
[`concurrency-spawn-sites.md`](../saga/references/concurrency-spawn-sites.md) for the complete
acquire, bind, renew, and release inventory.

Protected runtime output uses broker-owned `prepare_agent_settlement` then
`commit_agent_settlement`. `prepared`, `committing`, and `ambiguous` states retain authority across
TTL, sweep, and generic teardown. Only the final registry replacement embeds a canonical
`settlement_close.v1` and closes the generation. A retry must use `acquire_successor` with the exact
predecessor token and receipt digest; ordinary acquire cannot cross that close. `orphan_evidence.py`
preserves refused expired or late output in owner-only bounded quarantine and projects immutable
facts into read-only candidates. It never accepts output or executes reclamation.

## What belongs in commons — and what does not

**Belongs:** small, stdlib-only, fleet-wide vocabulary and pure helpers that would otherwise be
hand-copied — tier palettes, shared constants, tiny pure functions. Additive-only change within
0.x: a consumer never breaks because fleet-core updated.

**Does not belong:** anything with third-party dependencies (the marketplace install runs no
pip/venv step); plugin-specific business logic; anything that churns with a single plugin's
release cadence; contract mirrors (those are being abolished, not centralized).
