---
title: "Issue #620 — outcome board-sync plugin resolution"
type: fix
status: active
date: 2026-07-24
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/620
---

# Issue #620 — outcome board-sync plugin resolution

## Summary

Saga's outcome board-sync locates mission-control through monorepo-shaped paths, so every board
write fails when an outcome runs from any repo other than `infiquetra-claude-plugins`. This plan
promotes a generic, ladder-based plugin resolver into fleet-core and rewires the four affected call
sites onto it, converting an unresolvable plugin from a per-op retry storm into a single loud
cohort record.

## Problem Frame

An outcome-carrying consumer repo (the live failure: `campps-context-library`) advances its leaf
state correctly but cannot write the board. In one `advance` tick on 2026-07-18 that produced 24
failed `board_synced` records across two distinct errors, leaving board Status fields stale and
progress comments unposted while the coordinator worked around it by closing GitHub issues by hand.

The failure is fail-loud and ledgered — no silent skip and no data corruption — so the functional
severity is bounded. The campaign priority is not: this is leaf `sub-620` of outcome
`governed-execution-integrity` (Objective #639, live 5/9), it has zero dependencies, and it is the
sole remaining blocker on `sub-626` (#626), which is itself the last blocker on
`infiquetra-codex-plugins#45`. One leaf unblocks two.

### Mechanism — four call sites, one root cause

Every site assumes mission-control sits at a fixed offset from something saga knows. All four
verified live at `7e4d2db0`.

| Site | Location | Shape | Failure |
|---|---|---|---|
| S1 | `plugins/saga/scripts/board_progression.py:318` | `repo_root / "plugins" / "mission-control" / "scripts" / "sdlc_manager.py"` | Raises per op; drives the bounded-retry path |
| S2 | `plugins/saga/scripts/outcome_board_sync.py:116-123` | `Path(__file__).resolve().parents[2] / "mission-control" / "config" / "sdlc-schema.json"` | Resolution error → per-op `failed` record |
| S3 | `plugins/saga/scripts/pulse.py:84-86` | same as S1 | Soft failure with a `reason` string |
| S4 | `plugins/saga/scripts/outcome_reconcile.py:233` | calls `sync._default_schema_path()` | Non-fatal; the recover branch silently never fires |

S1 and S3 are `repo_root`-relative, and `outcome.py:2361` defaults `--repo-root` to `"."` — so
`repo_root` is the *consumer* repo, which by construction does not contain `plugins/`.

S2's reported "malformed" version-less path is arithmetic, not a typo. In the monorepo,
`plugins/saga/scripts/x.py` puts `parents[2]` at `plugins/`, where mission-control is a sibling. In
the installed-cache layout `<plugin>/<version>/scripts/x.py`, `parents[2]` lands at `saga/` — one
level short, because the cache inserts a version segment — producing exactly the reported
`~/.claude/plugins/cache/infiquetra-plugins/saga/mission-control/config/sdlc-schema.json`. The
`_default_schema_path` docstring records the module-file-relative choice as deliberate (#326 KTD3)
to keep test seams simple; it is correct for one layout and silently wrong for the other.

S4 is fixed for free by fixing S2's default, but is a distinct behavioral surface and needs its own
coverage.

## Requirements

R1–R4 and R7–R8 trace directly to the issue's "Expected" section ("resolve mission-control via the
installed-plugin registry … not via repo-root-relative or version-less cache paths").

**R5, R6, and R11 are an acknowledged extension beyond the issue's ask.** The issue observes the 24
failed records and credits the fail-loud posture without asking for the retry storm to be fixed;
this plan treats the storm and the new fleet-core coupling as in-scope because they are created or
aggravated by the fix itself. R10 is derived — the issue carries no acceptance-criteria section.

R1. Mission-control resolves through an ordered ladder with rung provenance, never through a
`repo_root`-relative or `__file__`-sibling path.

R2. `outcome advance` board writes succeed when the process cwd and `--repo-root` are a repo where
the rung-2 walk-up cannot match — that is, no ancestor holds both `.claude-plugin/marketplace.json`
and `plugins/mission-control/`. (A consumer repo that merely happens to have a `plugins/` directory
is not the discriminator.)

R3. Resolution succeeds under the installed-cache layout `<plugin>/<version>/scripts/`, with the
version segment intact — the S2 arithmetic bug cannot recur.

R4. The `sdlc_manager.py` CLI path and the `sdlc-schema.json` path derive from **one** resolved
mission-control root per tick; the two can never disagree about which installation they are using.

R5. An unresolvable mission-control produces exactly one loud, ledgered, actionable record per
reconcile pass — not `N` ops × `max_attempts` repetitions of the same terminal error. Fail-loud is
preserved; a silent skip is never introduced.

R6. Resolution is not retried. Unresolvable-plugin is terminal for the tick and distinct from a
transient op failure.

R7. Every driven board-sync record carries the resolved root and the rung that produced it, on both
the returned record AND the persisted `board-sync/*.json` ledger entry, so a stale resolution is
diagnosable after the fact by reading the durable ledger rather than by re-derivation. (The
unavailable-cohort record uses the same `board_sync_root`/`board_sync_rung` keys with null values —
there was no root.)

R8. `MISSION_CONTROL_ROOT` is the rung-1 escape hatch, so an operator can force a known-good
mission-control without editing any registry. An invalid value raises rather than falling through,
matching `FLEET_COMMONS_ROOT` semantics.

R9. Every new test fails against the pre-fix code (load-bearing-ness), and the existing 37 tests in
`tests/test_outcome_board_sync.py` plus 13 in `tests/test_board_progression.py` keep their current
injection seams.

R10. Live acceptance: an `outcome` board write is proven from an operator-designated repo outside
`infiquetra-claude-plugins` under armed hooks, with the resolved rung captured as evidence —
following the #615 R9 / #616 R8 / #617 R10 operator-gated pattern. The write targets a disposable
issue the operator names; no live campaign card is mutated to satisfy an acceptance criterion, and
the operator confirms the target before the write.

R11. A saga that resolves a fleet-core too old to carry `plugin_resolution` degrades to the R5
terminal record, not an uncaught exception. The record's reason names the resolved fleet-core root
and version and points at the #642 hand-repair.

## Key Technical Decisions

### KTD1 — The generic resolver lands in fleet-core's `fleet_commons/`, not in the frozen shim

A new `plugins/fleet-core/scripts/fleet_commons/plugin_resolution.py` exposes
`resolve_plugin_root(name, *, marker, env_var)` returning `(root, rung)`, loaded by consumers
through the existing `fleet_commons_shim.load("plugin_resolution")` seam.

The substrate is already universally present: `tests/test_fleet_commons_resolution.py:28-33` shows
the shim is vendored byte-identically into saga, mission-control, unifi (×2), agy, and codex. There
is no bootstrap gap to cross — mission-control is *already* a fleet-core consumer.

The bootstrap shim itself stays byte-identical, so the drift guard
(`test_vendored_shim_is_byte_identical_to_canonical`) and DECISIONS
`{#fleet-commons-mechanism-463}` ("keep this file minimal and rarely-changing — bootstrap code, not
a home for logic") are both honored. A new module inside the loaded package is exactly the
additive-only change fleet-core's 0.x compatibility contract permits, and that decision's own
"Revisit when" already anticipates promoting shared glue down into fleet-core.

**Rejected — A1, a second vendored `mission_control_shim.py`.** Duplicates ~120 lines of ladder and
doubles the byte-identity drift surface for a concern that is not bootstrap.

**Rejected — A2, parameterizing `fleet_commons_shim.resolve_root()` by plugin name.** Violates the
byte-freeze, forces a re-sync of seven vendored copies, and puts non-bootstrap logic in the one
file the decision record explicitly protects.

**Rejected — A3, a saga-local `plugin_resolution.py`.** Works, and honestly it would suffice for
this PR alone: every consumer the fix touches today (S1–S4) lives inside saga. A4's payoff is
therefore anticipatory, and that is the honest case for it — a saga-local copy would be the seventh
independent ladder implementation across a fleet where six plugins already vendor the shim, and
mission-control (the very plugin being resolved) is one of them. The `{#fleet-commons-mechanism-463}`
anti-sprawl argument applies verbatim: every primitive that lands in fleet-core is a hand-copy that
never gets made.

**The cost A4 introduces — a new cross-plugin version coupling — is real and is handled by KTD6.**

### KTD2 — Saga keeps reading `sdlc-schema.json` directly; only root resolution changes

Board-sync continues to read the schema file itself, at `<resolved-mc-root>/config/sdlc-schema.json`.
It does not ask mission-control for a resolved phase map.

`sdlc_manager._resolve_sdlc_schema` (`plugins/mission-control/scripts/sdlc_manager.py:339-367`)
resolves via **GitHub API first** (`repos/infiquetra/infiquetra-sdlc/contents/config/sdlc-schema.json?ref=main`),
then the vendored copy, then a local fallback, and returns `{}` when all three miss. Routing a
per-tick reconcile through it would trade a local file read for a network round-trip, degrade
offline behavior, and introduce a failure mode where an empty schema reads as a successful
resolution rather than a loud error.

It would also add a new mission-control CLI verb, a version bump, and its own drift pins for a pure
local read. Once the root is ladder-resolved, `<root>/config/sdlc-schema.json` *is* the vendored
copy — the same file `_VENDORED_SDLC_SCHEMA_PATH` (`sdlc_manager.py:289`) names. One resolver serves
both the CLI path and the schema path, satisfying R4 by construction.

**Known exposure, currently zero.** The vendored schema is `schema_version 2026-06-17` while
upstream `infiquetra-sdlc` main is `2026-07-18` — a month stale. Verified live this session: the
only slice saga reads, `saga_lifecycle.phase_board_map`, is **identical** between the two. So saga
reading vendored while mission-control writes from GitHub main is a latent split-brain with no
present divergence. Recorded as a risk and a deferred follow-up rather than solved here.

### KTD3 — Two distinct failure modes: unresolvable root withholds the cohort, unreadable schema keeps today's partial behavior

`reconcile_board` resolves the mission-control root once at the top of the pass and threads it to
both consumers. The two failure modes below it are **not** the same and must not be collapsed.

**Root unresolvable → withhold every candidate op, one record.** Verified: every op kind is driven
through the same resolved interpreter path — `board_progression.py:350` builds
`base = ["python3", sdlc]` and `set-field-status`, `sub-issue-close`, `sub-issue-reopen`,
`issue-progress-comment`, and `issue-label-add|remove` all extend that one `base`. So an unresolvable
root really does kill all of them, and withholding the cohort is correct rather than merely tidy.

**Root resolved but the schema file is unreadable → preserve the existing partial behavior.** Only
the status ops die. `outcome_board_sync.py:274-277` deliberately keeps the coalesced
`ISSUE_PROGRESS_COMMENT` for the same leaf flowing in that case ("the coalesced
ISSUE_PROGRESS_COMMENT for this same leaf is unaffected and proceeds below"). Withholding comments
here would be a regression introduced by the fix, so the existing per-op `failed` record for
`SET_FIELD_STATUS` stays exactly as it is.

The withholding shape already exists for the first mode: `outcome_board_sync.py:261-272` withholds a
whole issue's ops as `{"status": "drift-hold"}` on board↔saga drift. The new terminal reuses that
pattern with `{"status": "unavailable", "reason": <ladder message>}`, so the cohort-withholding
vocabulary stays consistent instead of growing a second idiom. Verified safe to add: no consumer
switches on board-sync record status values, so a new status string breaks no reader.

This preserves the property the issue explicitly praises — fail-loud and ledgered — while removing
the retry storm. The current schema resolution is already lazy and at-most-once per call
(`outcome_board_sync.py:224-234`); this extends the same discipline to the CLI path, which is today
resolved eagerly at writer construction and only discovered broken once per op.

### KTD4 — Rung order is inherited unchanged, with the asymmetry documented

The ladder stays: (1) env override, (2) repo walk-up, (3) `~/.claude/plugins/installed_plugins.json`,
(4) cache-sibling highest semver, (5) fail loud.

Preferring cache-sibling over the registry for a CLI is tempting — defect #642 has proven
four-for-four that no update path rewrites `installed_plugins.json`, so it goes stale after every
release. It is rejected for three reasons. Inverting the order for one consumer creates two
disagreeing ladders in the same fleet. The registry is authoritative for *what is installed*, while
highest-semver-in-cache may name a version the operator never installed. And the failure asymmetry
runs the other way from intuition: a stale **library** skews behavior silently, whereas a stale
**CLI** fails loud on an unknown verb — which makes the registry the *safer* first choice for
mission-control, not the riskier one.

The real mitigation is diagnosability (R7) plus the rung-1 escape hatch (R8), not a reordered
ladder.

### KTD5 — `pulse.py` (S3) is in scope; `outcome_reconcile.py` (S4) needs its own test

S3 is the same defect family and is small once the resolver exists — `default_sdlc_manager` swaps its
path arithmetic for a resolver call, with the caller at `pulse.py:604-621` adjusted for the
`(root, rung)` return. Excluding it would leave `/pulse` quietly reporting `sdlc_manager.py not found`
in exactly the repos where `/outcome` now works — an inconsistency that costs more to rediscover
later than to fix now. Its `--sdlc-manager` override means the test seam is already cut.

S4 is repaired implicitly by KTD2 because it calls `sync._default_schema_path()`, but implicit
repair without coverage is indistinguishable from luck. It gets an explicit test.

### KTD6 — A stale fleet-core degrades to the R5 terminal, never an uncaught exception

`fleet_commons_shim.load("plugin_resolution")` **raises** `RuntimeError` when the module is absent
at the resolved root (`fleet_commons_shim.py:154-158`). Because saga 0.114.0 requires a module that
only exists from fleet-core 0.23.0, and because #642 has proven four-for-four that the registry goes
stale after every release, the realistic post-release state is saga 0.114.0 resolving fleet-core
0.22.0 — where the import raises and board-sync dies harder than the bug being fixed.

Board-sync therefore catches that `RuntimeError` at the single per-tick resolution point and routes
it into KTD3's `unavailable` terminal. The shim's message already names the resolved root and
version, so the reason text is actionable without inventing diagnostics; the record additionally
points at the #642 hand-repair as the operator action.

**Rejected — a hard fleet-core floor assertion that aborts the tick.** Same information, worse
posture: it converts a degraded-but-recoverable board sync into a failed advance, and the leaf-state
machinery has no dependency on board writes.

**Rejected — vendoring `plugin_resolution` into saga to dodge the coupling.** That is A1/A3 by
another name and re-opens the duplication KTD1 rejected.

## Implementation Units

### U1. Generic plugin resolver in fleet-core

Add the ladder as a reusable fleet-commons primitive with per-plugin validity probing.

**Files:** `plugins/fleet-core/scripts/fleet_commons/plugin_resolution.py` (new).

**Signature:** `resolve_plugin_root(name, *, markers=(".claude-plugin/plugin.json",), env_var=None,
anchor=None) -> tuple[Path, int]`. `markers` is a **sequence** of repo-relative paths, all of which
must exist for a candidate root to be valid — not a single string. Mission-control passes
`("scripts/sdlc_manager.py", "config/sdlc-schema.json")`, so a root that resolves but cannot serve
both consumers is a rung miss rather than a success.

**Rung behavior:** Rung 1 reads `env_var` when given and **raises** on an invalid value rather than
falling through (matching `FLEET_COMMONS_ROOT` semantics); saga passes `env_var="MISSION_CONTROL_ROOT"`
(R8). Rung 2 walks up for an ancestor holding both `.claude-plugin/marketplace.json` and
`plugins/<name>/`. Rung 3 scans `installed_plugins.json` for the `<name>@` key prefix with per-record
tolerance — any shape surprise is a rung miss, never a crash. Rung 4 scans
`$CLAUDE_PLUGIN_ROOT/../../<name>/` for the highest semver. Rung 5 raises with an actionable message
naming every rung tried. `FLEET_COMMONS_DEBUG=1` also governs this module's provenance print — one
debug switch for the whole resolution substrate, not a second per-plugin variable to remember.

**Walk-up anchor (explicit, because the layouts disagree):** `anchor` defaults to
`Path(__file__)` — this module's own location inside fleet-core — matching the shim's precedent at
`fleet_commons_shim.py:110`. In the monorepo that walks `plugins/fleet-core/scripts/fleet_commons/`
up to the repo root and resolves the in-repo mission-control. Under the installed-cache layout it
finds no `marketplace.json` and correctly misses to rung 3. Callers do **not** pass their own
`__file__`; a saga-anchored walk-up would resolve differently from a fleet-core-anchored one in the
mixed case (saga from cache, cwd in the monorepo), and one substrate must have one answer.

**Test scenarios** (`tests/test_fleet_commons_plugin_resolution.py`, new): each rung resolves in
isolation with the correct rung number; an invalid env override raises rather than falling through;
a malformed registry record is skipped without poisoning the scan; the cache-sibling scan picks the
highest semver and skips non-semver directory names; a candidate satisfying only one of two `markers`
is rejected; the default anchor misses rung 2 under a simulated `<plugin>/<version>/scripts/` layout
and lands on rung 3; total failure raises naming all rungs; provenance output is emitted only when
`FLEET_COMMONS_DEBUG=1`.

### U2. Rewire saga board-sync onto the resolver

Replace S1, S2, and S4's defaults with one per-tick resolution and add the terminal cohort record.

**Files:** `plugins/saga/scripts/outcome_board_sync.py`, `plugins/saga/scripts/board_progression.py`,
`plugins/saga/scripts/outcome_reconcile.py`, and `plugins/saga/scripts/outcome.py`.

`outcome.py` is **not optional collateral**: `default_board_writer`'s signature changes, and
`outcome.py:798-812` re-exports it as `_default_board_writer` with two live callers at
`outcome.py:1032` and `outcome.py:2952`. Both must move to the resolved root in this unit or the
build breaks at the seam.

**Behavior:** `reconcile_board` resolves the mission-control root once, before the node loop, and
threads it to both the schema read and `default_board_writer`. `default_board_writer` accepts the
resolved root instead of deriving a path from `repo_root`. On an unresolvable root — including the
KTD6 stale-fleet-core `RuntimeError` — the pass emits a single
`{"status": "unavailable", "reason": ...}` record and withholds all candidate ops, and does not retry
(R6). A resolved root whose schema file is unreadable keeps today's per-op `failed` record for status
ops while comments continue to flow (KTD3). Every emitted record gains the resolved root and rung (R7).

**Seam preservation:** `reconcile_board`'s existing `schema_path` parameter
(`outcome_board_sync.py:181`) already overrides the schema location and stays the test injection
point unchanged; `default_board_writer`'s `runner` injection is untouched. The new root resolution
gets its own override parameter so tests never touch the real registry.

**Test scenarios** (`tests/test_outcome_board_sync.py`, `tests/test_board_progression.py`):
resolution succeeds with cwd and `repo_root` set to a directory where the rung-2 walk-up cannot
match; the installed-cache layout resolves with the version segment intact; an unresolvable
environment yields exactly one `unavailable` record for a multi-op multi-leaf spec (assert the count,
not just the presence); a shim `RuntimeError` from a stale fleet-core produces that same single
record with the fleet-core version in its reason (R11); no retry is attempted on either path; a
**resolved** root with an unreadable schema still yields the per-op `failed` status record *and* a
successful progress comment for the same leaf (the KTD3 non-regression); the schema path and CLI path
in one pass share a single resolved root; records carry root and rung; existing no-`schema_path`
tmp_path calls still pass unchanged. `tests/test_outcome_reconcile.py` gets the S4 case: the recover
branch fires from a non-monorepo cwd.

### U3. Rewire `/pulse` onto the resolver

Bring the telemetry path onto the same resolution so `/pulse` and `/outcome` agree in every repo.

**Files:** `plugins/saga/scripts/pulse.py`.

**Behavior:** `default_sdlc_manager` resolves through `resolve_plugin_root` instead of
`repo_root / "plugins" / ...`. The `--sdlc-manager` override keeps rung-1 precedence. The existing
soft-failure contract is preserved — an unresolvable mission-control still yields
`{"reason": ...}` rather than raising — but the reason text now names the ladder.

**Test scenarios** (`tests/test_pulse_telemetry.py`): resolution succeeds from a non-monorepo cwd;
`--sdlc-manager` still wins over the ladder; an unresolvable environment still fails soft with a
reason naming the rungs tried.

### U4. Release surfaces

Ship the installed-plugin metadata in the same PR so the diff and the installed fleet tell one story.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json` (0.22.0 → 0.23.0),
`plugins/saga/.claude-plugin/plugin.json` (0.113.0 → 0.114.0), `.claude-plugin/marketplace.json`,
`plugins/fleet-core/CHANGELOG.md`, `plugins/saga/CHANGELOG.md`, the version drift pins in
`tests/test_saga_plugin.py`, `tests/test_liveness_events.py`,
`tests/test_team_execution_liveness.py`, and a `docs/engineering-journal/DECISIONS.md` entry
`{#board-sync-plugin-resolution-620}` carrying KTD1–KTD6 with their rejected alternatives.

The journal entry lands here rather than at plan time, matching the repo practice of shipping the
decision record in the same commit as the change (as `{#registry-forward-compat-617}` did).

Mission-control is **not** bumped — KTD2 adds no verb and changes nothing on its side.

**Test expectation:** `python3 scripts/check_release_surface_parity.py` clean, and the drift pins
updated in the same commit. Re-check for sibling-PR version collisions at merge time; same-version
collisions have silently auto-merged three times in this repo's history.

## Risk Analysis & Mitigation

**The fix inherits #642 as its primary risk.** In the failing case — a consumer repo — rung 2 misses
by construction, so rung 3 governs, and rung 3 reads the one file verified four-for-four to go stale
after every release. A stale record resolves an older mission-control.

Mitigations, in order of load-bearing-ness: the failure is loud (an older CLI rejects an unknown verb
rather than silently mis-writing); R7 records the resolved root and rung so the resolution is
inspectable after the fact instead of re-derived; R8's rung-1 `MISSION_CONTROL_ROOT` override lets an
operator force a known-good root without touching the registry. Verified live this session that the
mechanism works today — the registry holds `mission-control@infiquetra-plugins` at 2.10.1 with the
matching cache directory present.

**The same staleness attacks the fix's own delivery**, which is the sharper edge of this risk: saga
0.114.0 needs a module that ships in fleet-core 0.23.0, and a stale registry resolves fleet-core
0.22.0, where `load("plugin_resolution")` raises. KTD6 converts that into the R5/R11 terminal record
instead of an uncaught exception. The rollout still carries the mandatory #642 hand-repair step, and
R11's test is the guard that the degraded path is real rather than assumed.

**The vendored-schema staleness (KTD2) is the second risk** and is currently inert: vendored
`2026-06-17` vs upstream `2026-07-18`, with the `phase_board_map` slice identical. It becomes real
the first time upstream changes that slice. Deferred, not solved.

**Pre-mortem — the most likely way this fails.** The resolver lands correctly and the unit tests
pass, but the live acceptance is run from a *worktree of the monorepo* rather than a genuinely
separate repo. Rung 2's walk-up then succeeds, the ladder never exercises rung 3, and R2 is
"verified" without ever testing the failing path. R10 must name a real non-monorepo repo and assert
the observed rung is 3 or 4, not merely that the write succeeded.

## Scope Boundaries

**Out of scope — true non-goals.** #642 (`installed_plugins.json` staleness) is a separate defect;
this plan states the interaction and depends on the registry, but does not fix it. #626 is a
downstream leaf. #635 (ship_ceremony `branch_delete` resolving from the saga's rolling branch field)
and the ship_ceremony `_saga_short_id` derived-id split-brain observed during the #617 ceremony are
the same unrelated family. No changes to the `fleet_commons_shim.py` bootstrap file. No changes to
mission-control.

**Deferred to follow-up work.** A drift check between the vendored `sdlc-schema.json` and upstream
`infiquetra-sdlc` main (KTD2's latent split-brain) — it needs a non-networked design to be
CI-appropriate, which is its own small piece of work. Promoting other plugins' bespoke path
resolution onto `resolve_plugin_root` beyond S1–S4.

## Alternatives Considered

| Alternative | Verdict | Reason |
|---|---|---|
| A1 — second vendored `mission_control_shim.py` | Rejected | ~120 duplicated lines; doubles the byte-identity drift surface for non-bootstrap code |
| A2 — parameterize the frozen shim by plugin name | Rejected | Violates the byte-freeze and `{#fleet-commons-mechanism-463}`; forces a 7-copy re-sync |
| A3 — saga-local resolver | Rejected | Works, but the next consumer re-implements the ladder |
| **A4 — generic resolver in `fleet_commons/`** | **Chosen** | Shim stays frozen; substrate already vendored by all six consumers; additive under fleet-core 0.x |
| B — ask mission-control for the phase map via a new CLI verb | Rejected | Its resolver hits the network first and returns `{}` on total failure; adds a verb + bump for a local read |
| C1 — keep per-op failures, just fix the paths | Rejected | Leaves the `N × max_attempts` retry storm on an unrecoverable condition |
| C2 — skip board ops silently when unresolvable | Rejected | Destroys the fail-loud property the issue explicitly credits |
| C3 — withhold the cohort on *any* resolution failure | Rejected | Regresses `outcome_board_sync.py:274-277`, where an unreadable schema still lets progress comments post |
| D — prefer cache-sibling over the registry for a CLI | Rejected | Two disagreeing ladders; registry is authoritative for installed state; CLI staleness fails loud anyway |
| E1 — hard fleet-core floor assertion that aborts the tick | Rejected | Turns a degraded board sync into a failed advance; leaf state does not depend on board writes |
| E2 — vendor `plugin_resolution` into saga to dodge the coupling | Rejected | A1/A3 by another name; re-opens the duplication KTD1 rejected |

## Acceptance Criteria

R1–R9 and R11 are satisfied by the unit test scenarios above. R10 is the operator-gated live leg, run
post-merge under armed hooks following the #617 R10 pattern: drive an `outcome advance` board write
from an operator-designated repo outside `infiquetra-claude-plugins` against a disposable issue the
operator names, capture the resolved root and rung from the ledger record, assert the rung is 3 or 4
(proving the walk-up did not silently rescue the test), and confirm the board Status field actually
moved. The operator confirms the target repo and issue before the write; no live campaign card is
mutated to satisfy an acceptance criterion.
