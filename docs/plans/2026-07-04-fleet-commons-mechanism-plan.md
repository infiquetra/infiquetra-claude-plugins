---
title: Fleet-Commons Distribution Mechanism — Name the Import Path for Cross-Plugin Shared Primitives
type: feat
status: active
date: 2026-07-04
origin: infiquetra/infiquetra-claude-plugins#463 (exploration, requirements-ready; absorbs ideation survivor G-negative-space-3)
---

# Fleet-Commons Distribution Mechanism — Name the Import Path for Cross-Plugin Shared Primitives

Decide and build where cross-plugin shared primitives live and how a sibling plugin resolves them at
install time. Deliverable is a merged decision (`DECISIONS.md` entry) **plus** the proving build: a
new `fleet-core` plugin hosting the canonical commons, a vendored resolution shim, the tier palette
migrated as first mover and imported through the shim from two plugins (saga, mission-control), and
an install-time integration test that proves resolution outside the repo checkout.

## Problem statement (carried from issue #463)

The fleet is 8 independently versioned, independently installed marketplace plugins. The marketplace
install is a bare per-plugin, per-version file copy under
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` — no repo root, no siblings inside the
copy, no pip/venv step (verified live on this machine, 2026-07-04). Cross-plugin `import` therefore
has no resolvable path at install time; it only works inside this monorepo because pytest puts
repo-root paths on `sys.path`. Roughly two dozen ideation survivors presuppose a shared-primitive
home that does not exist; unresolved, each will ship as a hand-copy, the same failure mode as the
`validate_card_body` drift incident (343 "clean" cards, incident #222).

## Grounding verification (plan-time, 2026-07-04)

| Claim | Verified against | Result |
|---|---|---|
| 8-plugin fleet map | `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12` | Matches, except saga is now 0.52.0 (brief froze 0.51.0 pre-#399) — use live versions in the DECISIONS entry |
| Survivor record `G-negative-space-3` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json` | Present, verbatim match to issue body |
| Issue-map source path | Issue cites `.../issue-map/issue-map-final.json`; actual file is `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map-final.json` (no `issue-map/` subdir) | **Citation drift** — corrected here |
| "28 pool ideas" census | `pool-final.json` (796 ideas) + `survivors/*.json` | **Not reproducible**: keyword census yields 10–21 (pool) or 19 (survivors) depending on the net; no artifact enumerates 28 ids. See KTD6 |
| Install layout | `~/.claude/plugins/{marketplaces,cache}/infiquetra-plugins/`, `installed_plugins.json` (schema `version: 2`) | Marketplace dir is a full repo git clone; cache is per-plugin per-version subtree copies; `installed_plugins.json` maps `<plugin>@<marketplace>` → exact `installPath` |
| Version skew is real | `installed_plugins.json` vs repo | saga installed 0.49.0, cache holds through 0.51.0, repo ships 0.52.0; team-execution installed 2.8.0 vs repo 2.9.0 |
| Tier palette location and consumers | `plugins/saga/scripts/execution_spec.py:52-68` (`MODELS`, `EFFORTS`, `_CHEAP_MODELS`, `PASS_RULES`, `ENGINE_INTENTS`, ordering contract) | Sole existing definition; imported by 4 saga modules (`team_emitter.py`, `manifest_store.py`, `outcome_spec.py`, `outcome_dispatcher.py`) — all intra-saga |
| No second genuine consumer exists today | grep across all 8 plugins' Python for tier vocabulary; cross-plugin path references | Zero cross-plugin references anywhere in the fleet; mission-control/team-execution/agy/deploy/home-lab-ops/unifi/redis-channel carry no Claude-tier vocabulary in code |
| 429 handling is NOT a hand-copy pair | `unifi_network_client.py:152-159` (HTTP response erroring) vs `sdlc_manager.py:589-592` (gh-CLI stderr → typed exceptions) | Different shapes; nothing to relocate — #348 builds new, it does not deduplicate |
| Binding decisions | grounding brief §2 (`{#plugin-portfolio-groom-17-to-7}`, `{#worker-cache-scheduling}`) | Present at `2026-07-03-plugin-fleet-grounding-brief.md:47,52` |

## Requirements

- **R1.** A `docs/engineering-journal/DECISIONS.md` entry names the chosen mechanism, records every
  evaluated candidate's concrete failure mode (AC1), states a checkable `Revisit when:` condition
  (AC2), engages `{#plugin-portfolio-groom-17-to-7}` with the consolidation argument (AC6), and cites
  a verified source for every layout/behavior claim, no "likely/probably" (AC7).
- **R2.** A working resolution shim: stdlib-only, fail-loud when fleet-core is absent or malformed,
  and reporting which resolution rung succeeded (provenance) so tests can prove the path taken.
- **R3.** The tier palette relocated to the commons home and imported through the shim from two
  distinct plugins: saga (existing consumer, rewired) and mission-control (new, genuinely warranted
  consumer — executor-profile lint) (AC3).
- **R4.** An install-time integration test proving resolution from outside the repo working tree —
  it must fail if only the monorepo `sys.path` convenience is exercised (AC4).
- **R5.** The dependent ideation survivors are enumerated by a recorded, deterministic census and
  annotated with the chosen mechanism in a single tracking artifact (`QUEUED.md` table), with the
  delta from the issue's "28" figure documented (AC5, adapted per KTD6).
- **R6.** All release surfaces updated in the same PR (fleet-core manifest + marketplace entry;
  saga and mission-control bumps + CHANGELOGs; drift-guard tests), full gate green (AC8).
- **R7.** Scope guards honored: do not touch `validate_card_body` or any contract mirror
  (`pf-abolish-contract-mirrors` scope); no publishing pipeline; exactly one primitive migrated;
  no change to tier vocabulary *content* or dispatch semantics.

## Key Technical Decisions

**KTD1 — Commons home is a new `fleet-core` plugin (operator-confirmed 2026-07-04).**
Canonical primitives live at `plugins/fleet-core/scripts/fleet_commons/` (a plain directory of
stdlib-only modules, loaded by path — not an installed Python package). Rejected: (a) hosting the
commons inside saga — avoids a ninth plugin but couples every consumer to the fleet's
fastest-churning surface (14 cached versions; the one plugin observed version-skewed on this machine
right now), maximizing stale-commons risk; (b) a published Python package — the marketplace install
runs no pip/venv step (verified: bare file copy; fleet scripts run under system `python3`,
stdlib-only convention), so the dependency would be user-managed, and it adds a
publish/index/versioning surface the fleet has no tooling for; (c) the marketplace git clone as
commons root — the clone tracks marketplace HEAD, not the versions the user actually has installed
and enabled, so consumers would resolve code ahead of (or behind) everything else they run.
Anti-sprawl engagement (AC6): fleet-core is consolidation, not sprawl — every future shared
primitive that lands there is a hand-copy that never gets made; the alternative is ~2 dozen
independent copies drifting the `validate_card_body` way.

**KTD2 — Resolution is a vendored micro-shim with a five-rung ladder and rung provenance.**
Each consuming plugin vendors one file, `scripts/fleet_commons_shim.py` (stdlib-only, small —
target ≤ ~120 lines), byte-identical to the canonical copy in fleet-core, guarded by a repo test
that fails on any byte difference. The shim resolves the fleet-core root by the first rung that
succeeds:

1. `FLEET_COMMONS_ROOT` environment override (tests, unusual layouts).
2. Repo-checkout walk-up from the shim's own `__file__`: an ancestor containing both
   `.claude-plugin/marketplace.json` and `plugins/fleet-core/` (covers monorepo dev and the
   marketplace git clone).
3. `~/.claude/plugins/installed_plugins.json` lookup of any key with prefix `fleet-core@`
   (marketplace-agnostic — do not hardcode `infiquetra-plugins`) → `installPath` (the
   authoritative installed location; immune to cache-version skew).
4. Cache-sibling scan: `$CLAUDE_PLUGIN_ROOT/../../fleet-core/<highest semver>/` (last-resort
   fallback if the installed-plugins registry moves or changes shape).
5. Fail loud: raise with an actionable message naming the fix ("install fleet-core from the
   infiquetra-plugins marketplace").

The shim exposes `resolve_root() -> (path, rung)` and `load(module) -> ModuleType`
(`importlib`-by-path from `<root>/scripts/fleet_commons/`), and never silently falls through to a
wrong rung — provenance is part of the return value, which is what makes AC4's "prove it didn't
just use the repo `sys.path`" assertable. For subprocess-boundary tests where the return value is
not observable, the shim honors `FLEET_COMMONS_DEBUG=1` by printing one line to stderr —
`fleet-commons: rung=<n> (<name>) root=<path>` — which U5 asserts. Why vendoring is safe where `validate_card_body` was not:
that incident was an *unguarded, growing* hand-copy of active business logic; the shim is minimal,
rarely-changing bootstrap code with a byte-identity drift guard in CI.

**KTD3 — First-mover primitive is the tier palette, migrated with a re-export seam.**
`plugins/fleet-core/scripts/fleet_commons/tier_palette.py` becomes canonical for `MODELS`,
`EFFORTS`, `CHEAP_MODELS`, `ENGINE_INTENTS`, and the ordering contract — exactly T3-F4-1's
enumeration; `PASS_RULES` stays in `execution_spec.py` (refute-N vocabulary, not tier vocabulary)
(strongest-first models / weakest-first efforts — ordering is load-bearing per
`{#tier-vocab-ordering}` and `execution_spec.py:45-50`'s upgrade-only merge). saga's
`execution_spec.py` imports these through the shim and **re-exports the same names**, so its four
intra-saga importers and the existing test suite are untouched — the migration's blast radius inside
saga is one file. Vocabulary content does not change (R7).

**KTD4 — Second consumer is a new mission-control executor-profile lint (operator-confirmed
2026-07-04).** No plugin besides saga genuinely consumes Claude-tier vocabulary today (verified —
see grounding table), so AC3's second consumer must be built, not found. The least-artificial site:
every program issue body carries a `Recommended Executor Profile` block (Model/Effort/Backend) with
a rule — "Justification (required — profile is above sonnet)" — that no code enforces. New module
`plugins/mission-control/scripts/executor_profile_lint.py`: parses a profile block from an issue
body (`--body-file` or stdin), validates model/effort membership against the palette resolved
through the shim, and enforces the above-sonnet-requires-justification rule using the palette's
ordering. Standalone module with its own CLI entry — deliberately **not** threaded into
`sdlc_manager.py`'s 5,373-line internals and kept clear of the `validate_card_body` mirror (R7).
Rejected: team-execution as second consumer (chaperone tiers exist only as SKILL.md prose; no Python
execution surface to consume from — the consumer would be scaffolding awaiting a future issue).

**KTD5 — Compatibility contract: additive-only primitives, versioned host, observable resolution.**
fleet-core ships at 0.1.0. Commons primitives promise additive-only change within 0.x (a consumer
never breaks because fleet-core updated); the shim exposes the resolved fleet-core version (read
from the resolved root's `.claude-plugin/plugin.json`) for diagnostics. `installed_plugins.json` is
an undocumented Claude Code internal (schema `version: 2` observed) — rung 3 treats parse failure
as rung-miss (fall to rung 4), never a crash.

**KTD6 — AC5's "28" is redefined as a recorded deterministic census (grounding correction).**
The "28 pool ideas" figure is not reproducible: no artifact enumerates 28 ids, and keyword censuses
over `pool-final.json` (796 ideas) and `survivors/*.json` yield 10–21 and 19 respectively depending
on the net. The plan substitutes a deterministic census: a recorded query over the survivor files
(the ideas that become issues — dead pool ideas need no annotation), unioned with the 7 ids the
issue names (`T3-F4-1`, `T13-F4-1`, `T5-F6-1`, `T6-F4-3`, `T6-F4-1`, `T15-F4-1`, `T4-F4-1`). The
resulting set — whatever its count — is annotated in a `QUEUED.md` tracking table, and the DECISIONS
entry documents both the query and the delta from "28". This satisfies AC5's intent (future issues
stop re-deciding the mechanism) without pretending an unreproducible number is exact.
Operator-acknowledged 2026-07-04 (doc-review P2 resolution); `/work` still surfaces the final
census count alongside AC5.

## Implementation Units

### U1 — fleet-core plugin scaffold + canonical tier palette

Scaffold `plugins/fleet-core/` via `./tools/create-plugin.sh fleet-core` and adapt: `plugin.json`
(0.1.0, required fields per repo CLAUDE.md), README (what belongs in commons, what does not),
CHANGELOG. Add `scripts/fleet_commons/tier_palette.py` — constants moved verbatim from
`execution_spec.py:52-68` plus the ordering-contract docstring and two pure helpers
(`model_rank()`, `effort_rank()`) for consumers that need ordering without index arithmetic.
`_CHEAP_MODELS` is renamed public `CHEAP_MODELS` at the canonical home (saga's re-export keeps the
private alias). fleet-core is a scripts-only library plugin — no skills, commands, or agents; the
repo's CI validator imposes nothing on this shape (`scripts/validate_plugins.py` only globs
top-level `plugins/*.md`, of which there are none), and `claude plugin validate` accepts it
(verified 2026-07-04 against a minimal scripts-only probe plugin: "Validation passed", exit 0).
This unit still runs `claude plugin validate plugins/fleet-core` as a cheap gate; fallback if
full install ever rejects a contentless plugin is one minimal docs-only skill describing the
commons.

**Test expectation:** palette content/ordering regression tests in
`tests/test_fleet_commons_resolution.py` (same file as U2's tests; palette values byte-match the
pre-migration tuples).

**Depends on:** nothing.

### U2 — resolution shim (canonical + vendored copies) + resolution unit tests

Canonical `plugins/fleet-core/scripts/fleet_commons_shim.py` implementing KTD2's ladder with rung
provenance and fail-loud. Vendored byte-identical copies at `plugins/saga/scripts/fleet_commons_shim.py`
and `plugins/mission-control/scripts/fleet_commons_shim.py`. Byte-identity drift-guard test compares
every vendored copy to the canonical file.

**Test expectation:** `tests/test_fleet_commons_resolution.py` — one test per rung (env override;
repo walk-up; installed_plugins.json lookup against a fixture file; cache-sibling scan with mixed
versions picking highest semver), fail-loud when nothing resolves (actionable message asserted),
malformed `installed_plugins.json` falls through to rung 4 rather than crashing, and the
byte-identity drift guard.

**Depends on:** U1.

### U3 — rewire saga (consumer 1)

`execution_spec.py` imports the palette through the vendored shim and re-exports `MODELS`,
`EFFORTS`, `_CHEAP_MODELS`, `ENGINE_INTENTS` under their existing names (KTD3); `PASS_RULES`
stays defined in place. No other saga file changes.

**Test expectation:** the existing saga suite (`tests/test_saga_engine_dispatch.py`,
`tests/test_outcome_spec.py`, `tests/test_team_emitter.py`, `tests/test_workflow_emitter.py`,
`tests/test_manifest_store.py`, `tests/test_outcome_dispatcher.py`, and the rest) passes unchanged —
that is the regression evidence that the re-export seam holds. One new test asserts
`execution_spec.MODELS is` the shim-loaded palette's `MODELS` (proves the import path, not a copy).

**Depends on:** U2.

### U4 — mission-control executor-profile lint (consumer 2)

New `plugins/mission-control/scripts/executor_profile_lint.py` (KTD4): parse a
`Recommended Executor Profile` block (Model / Effort / Backend lines) from `--body-file` or stdin;
exit non-zero with a named finding when (a) model or effort is not in the palette, or (b) model
ranks above sonnet and no `Justification` line is present. Resolves the palette through the vendored
shim. Pure stdlib; no gh calls in this unit (callers pipe `gh issue view -q .body` in).

**Test expectation:** `tests/test_executor_profile_lint.py` — valid profile passes; unknown model
fails; above-sonnet-without-justification fails; above-sonnet-with-justification passes;
missing/absent profile block is a distinct, named outcome (not a crash); palette arrives via shim
(asserted by rung provenance under `FLEET_COMMONS_ROOT`).

**Depends on:** U2.

### U5 — install-time integration test

`tests/test_fleet_commons_install_time.py` (AC4/R4): build a fake install root under `tmp_path` —
`fake_home/.claude/plugins/cache/infiquetra-plugins/fleet-core/0.1.0/` (copy of the plugin subtree,
mimicking the observed bare-copy install), **mission-control's cache copy as the consumer**, and an
`installed_plugins.json` fixture (schema `version: 2` as observed live). Run the consumer end to
end in a `subprocess` — `python3 <fake cache>/mission-control/<v>/scripts/executor_profile_lint.py
--body-file <sample>` — with `HOME=fake_home`, cwd outside the repo, and a scrubbed `PYTHONPATH`,
then assert (a) the lint runs and the palette loads, and (b) with `FLEET_COMMONS_DEBUG=1` set, the
shim's stderr provenance line reports rung 3 (`installed_plugins.json`) — **not** rung 2 — which is
what proves the monorepo walk-up was not the path taken. Negative case: same
layout minus fleet-core → loud, actionable failure. Version-skew case: cache holds 0.1.0 and a
decoy 0.2.0 directory while `installed_plugins.json` pins 0.1.0 → shim resolves 0.1.0.

**Test expectation:** the file itself (this unit is a test).

**Depends on:** U2 (shim), U1 (plugin subtree to copy).

### U6 — decision record, census annotation, release surfaces, closeout

1. `docs/engineering-journal/DECISIONS.md` entry `{#fleet-commons-mechanism-463}`: chosen mechanism,
   per-candidate failure modes (KTD1's three rejections, in prose), `Revisit when:` (first breaking
   change needed in a commons primitive; or `installed_plugins.json` schema departs from `version: 2`;
   or a primitive needs non-stdlib dependencies), `{#plugin-portfolio-groom-17-to-7}` engagement,
   citations per AC7, census query + delta per KTD6.
2. Census run (KTD6) + `QUEUED.md` tracking table: each dependent survivor id annotated
   "builds against fleet-core + vendored shim".
3. Release surfaces: `.claude-plugin/marketplace.json` gains the fleet-core entry; saga
   0.52.0 → 0.53.0 and mission-control 2.4.0 → 2.5.0 (`plugin.json`, `CHANGELOG.md`, marketplace
   sync); `tests/test_saga_plugin.py`'s version literal; release-triad / drift-guard tests updated
   for the new plugin (check `tests/test_release_triad.py` fixture expectations).
4. Tick Phase 0 row 3 in `docs/plans/2026-07-04-plugin-fleet-execution-order.md`.

**Test expectation:** full gate green — `uv run pytest && uv run ruff format --check . &&
uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`; plus
`grep -n "fleet-commons" docs/engineering-journal/DECISIONS.md` non-empty (issue's verification
block).

**Depends on:** U1–U5.

## Scope boundaries

**In scope:** the mechanism decision + DECISIONS entry; fleet-core plugin with shim + tier palette;
saga and mission-control as the two consumers; install-time test; census annotation; release
surfaces.

**Out of scope (from the issue, binding):** migrating the remaining dependent primitives (follow-up
issues build against the decision); any publishing pipeline; the marketplace contract/schema story
(`H-F6-8`); touching `validate_card_body` or any contract mirror (`pf-abolish-contract-mirrors`);
any change to tier vocabulary content or model/effort dispatch semantics.

**Deferred follow-up (distinct from non-goals):** wiring `executor_profile_lint` into an automated
program-pipeline check; a `concurrency.py` commons primitive (T13-F4-1, lands with its own issue);
#348's retry/backoff primitive as the second real commons migration.

## Risk analysis

- **Vendored shim drift** — the failure mode the issue names explicitly. Mitigated structurally:
  byte-identity CI guard (U2) + the shim's deliberate minimalism; the DECISIONS entry records this
  as the accepted residual risk with its guard named.
- **`installed_plugins.json` is an internal contract** — Claude Code may reshape it. Mitigated: rung
  3 degrades to rung 4 on parse failure; KTD5 revisit-when trigger names the schema change.
- **Re-export seam misses a name** — a saga importer reaching for a symbol execution_spec no longer
  defines. Mitigated: U3 changes one file and the whole existing saga suite is the regression net.
- **Install-time test passes for the wrong reason** — the classic AC4 trap. Mitigated: rung
  provenance is asserted, not just import success; PYTHONPATH scrubbed; negative + skew cases
  included.
- **New-plugin objections at review** — anti-sprawl. Pre-answered in KTD1/AC6: consolidation
  argument recorded in the DECISIONS entry itself.

## Closeout

After merge: advance the operations-board Status for #463, mark the saga tick done, and note in the
work-session summary which follow-up issues (#348, #401, #341 et al.) now build against the settled
mechanism. `/qa 463` remains advisory.
