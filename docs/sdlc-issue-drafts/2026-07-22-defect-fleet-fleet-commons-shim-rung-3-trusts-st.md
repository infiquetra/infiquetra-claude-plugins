---
title: defect(fleet): fleet_commons_shim rung 3 trusts stale installed_plugins.json, silently resurrecting an old fleet-core broker
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
handoff_maturity: requirements-ready
risk: medium
---

# defect(fleet): fleet_commons_shim rung 3 trusts stale installed_plugins.json, silently resurrecting an old fleet-core broker

### Objective

## Summary

`fleet_commons_shim` resolves the fleet-core root through a four-rung ladder in which rung 3 —
`~/.claude/plugins/installed_plugins.json` — outranks the cache-sibling highest-semver scan
(rung 4). The Claude Code harness no longer keeps that registry current: `/plugin marketplace
update` downloads new plugin versions into `~/.claude/plugins/cache/` and `/reload-plugins`
hot-reloads hooks, but **neither rewrites the install records**, and `claude plugin update`
reports "already at the latest version" without touching the file either. The result: after any
saga/fleet-core release, every consumer that resolves through the shim silently loads the OLD
fleet-core broker even though the new one is on disk in the cache.

## Evidence (live incident, 2026-07-22)

Hit while running the #615 R9 armed-hooks acceptance canary in session
`a2c17e16-6a69-4ff8-a9f6-dc347823861a`:

- saga 0.110.0 hooks (freshly reloaded) resolved fleet-core **0.17.0** via rung 3, because the
  registry records were still pinned to the pre-#641 install paths.
- Symptom: workflow children were refused with "no live provisional reservation" despite a valid
  attested batch — 0.17.0's `claim()` predates the unstamped-batch-claim fix that shipped in
  fleet-core 0.19.0 (PR #641, merge `ab84003b`).
- Provenance confirmed with `FLEET_COMMONS_DEBUG=1` (prints `rung=<n> (<name>) root=<path>`):
  rung 3 → `.../fleet-core/0.17.0`.
- Recovered by hand-editing the two records' `installPath`/`version` in
  `installed_plugins.json` (backup taken first); hook subprocesses re-read the registry per
  event, so the fix took effect without a session restart.

The shim's vendored copy lives at `plugins/fleet-core/scripts/fleet_commons_shim.py` (ladder
documented in the module docstring; rung ordering in `resolve_root()`).

## Why it matters

The skew is silent and fail-plausible: hooks stay armed and enforce, but against the wrong
broker version. Version-dependent contract changes (claim semantics, settlement, write-fence
behavior) reappear as ghost regressions after every release until someone hand-edits an
undocumented internal registry. This will re-trigger on the next fleet-core bump — #616/#617
both edit `lease_broker.py`.

## Candidate fixes (design call for the plan)

1. **Reorder or cross-check rungs**: prefer the cache-sibling highest-semver scan (rung 4) over
   the registry, or use the registry only when its recorded version is >= the best cache
   sibling. Tradeoff: the registry exists to honor explicit installs/pins; blind preference for
   "highest on disk" may resurrect a rolled-back version.
2. **Staleness guard at rung 3**: validate the record's `installPath` version against the cache
   catalog for the same marketplace; on mismatch, fall through to rung 4 and emit a one-line
   warning.
3. **Doctor check**: a `fleet-core` doctor/parity script (run in CI or by the release ceremony)
   that compares `installed_plugins.json` records against the newest cache version and tells the
   operator exactly what to fix.

Option 2 (fall-through with warning) plus option 3 (doctor visibility) preserves explicit-pin
semantics while eliminating the silent-skew failure mode; option 1 alone changes pin semantics.

## Constraints

- The shim is bootstrap code, byte-identical vendored into consumer plugins with a drift-guard
  test (`DECISIONS {#fleet-commons-mechanism-463}`) — any change ships to the canonical file plus
  every vendored copy, with release-surface bumps for each carrying plugin.
- `installed_plugins.json` is an undocumented harness-internal file (schema `version: 2`); the
  shim must keep treating shape surprises as a rung miss, never a crash.

## Related

- #615 / PR #641 — the release whose rollout surfaced the skew (fleet-core 0.19.0, saga 0.110.0).
- #617 — registry schema-skew hardening in `lease_broker.py` (adjacent but distinct layer: that
  is lease-state schema, this is plugin-install resolution).

### Intent
Make fleet-core resolution immune to a stale `~/.claude/plugins/installed_plugins.json`: a
release that lands in the plugin cache must never be silently shadowed by an outdated install
record, and any remaining skew must be operator-visible instead of failing as a ghost broker
regression.

### Out-of-scope / non-goals
- Fixing the harness itself (the registry is Claude Code internal; we harden our side only).
- Lease-state schema-skew hardening inside `lease_broker.py` — that is #617's layer.
- Changing lease enforcement semantics, claim ordering, or the write-fence (#616).
- Auto-editing `installed_plugins.json` from the shim (report/fall-through only; mutation of a
  harness-internal file stays a deliberate operator action).

### Files expected to change
- `plugins/fleet-core/scripts/fleet_commons_shim.py` (canonical ladder)
- vendored byte-identical copies in consumer plugins, e.g. `plugins/saga/scripts/fleet_commons_shim.py` (enumerate via the drift-guard test)
- `tests/` shim resolution tests + drift-guard pins
- release surfaces for every carrying plugin: `plugins/*/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, per-plugin `CHANGELOG.md`
- `docs/engineering-journal/DECISIONS.md` (rung-ordering decision) and `LEARNINGS.md` (registry-skew mechanism)

### Tests to add or update
- Shim unit tests: rung-3 record pointing at an older version while a newer valid cache sibling
  exists → resolution must not silently pick the stale root (exact behavior per the chosen fix);
  registry absent/malformed still degrades to rung 4; explicit `FLEET_COMMONS_ROOT` (rung 1) and
  repo walk-up (rung 2) precedence unchanged.
- Doctor/parity check test (if option 3 ships): stale record detected and reported with the
  exact records to fix; clean state reports clean.
- Existing vendored-copy drift-guard test keeps passing with the updated shim.

### Context library links
- `plugins/fleet-core/scripts/fleet_commons_shim.py` module docstring (resolution ladder + `FLEET_COMMONS_DEBUG`)
- `docs/engineering-journal/DECISIONS.md` `{#fleet-commons-mechanism-463}` (byte-identical vendoring contract)
- PR #641 / merge `ab84003b` (the release whose rollout surfaced the skew)

### Acceptance criteria
- [ ] With a stale rung-3 record (older `installPath`) and a newer valid cache sibling on disk, `FLEET_COMMONS_DEBUG=1 python3 -c "import fleet_commons_shim; fleet_commons_shim.resolve_root()"` resolves the newer root (or fails loud per the chosen design) — it never silently returns the stale root.
- [ ] Skew is operator-visible: the chosen mechanism (fall-through warning and/or doctor check) prints the stale record and the corrective action; verified by its unit test in `uv run pytest -q`.
- [ ] `uv run pytest -q` passes including the vendored-copy drift-guard test (all shim copies byte-identical after the change).
- [ ] Release-surface parity clean: `python3 scripts/check_release_surface_parity.py` (version bumps for every plugin carrying the shim).

### Verification
Reproduce the incident shape hermetically, then confirm the fix:

```bash
# unit-level: stale registry + newer cache sibling fixture
uv run pytest -q tests/ -k "fleet_commons_shim"

# live provenance check (after a release): must NOT resolve an older version than the cache max
FLEET_COMMONS_DEBUG=1 python3 - <<'EOF'
import sys; sys.path.insert(0, "plugins/fleet-core/scripts")
import fleet_commons_shim as s
print(s.resolve_root(), s.resolved_version())
EOF

# full gates
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: live incident during the #615 R9 armed-hooks acceptance canary, 2026-07-22 (session `a2c17e16-6a69-4ff8-a9f6-dc347823861a`)
- Source type: incident-report
- Source title: fleet_commons_shim rung-3 stale-registry skew (fleet-core 0.17.0 resurrected post-0.19.0 release)

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/642
- Number: 642
- Created at: 2026-07-22T23:01:36.811661+00:00

