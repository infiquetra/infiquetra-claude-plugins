---
title: Durable delegation audit store, write-once draft snapshots, and /delegation-audit reconciliation
type: feat
status: active
date: 2026-07-12
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json
---

# Durable delegation audit store, write-once draft snapshots, and /delegation-audit reconciliation

## Summary

Add a durable, teardown-exempt delegation audit store (`~/.claude/delegation-audit` by default) that
`agy_delegate.py` and `engine_dispatch.py` mirror every receipt and provenance manifest into, a
write-once pre-fix draft snapshot in the chaperone-dispatch path, and a `/delegation-audit`
reconciliation surface that flags a delegation as a no-op when its disposition claims real execution
but its receipt does not back that claim. Implements infiquetra/infiquetra-claude-plugins#396, leaf
`sub-396` of outcome `evidence-integrity` (depends on #398/PR #567, merged, and #383
`bridge_receipt.v1`, closed).

## Problem Frame

Delegation evidence lives entirely inside disposable storage today. `agy_delegate.py:279`
(`create_validation_bundle`) and `create_supervised_bundle` write every run's `envelope.json` /
`result.json` (embedding the `bridge_receipt.v1` when the run launched) under
`repo_root/.claude/agy/runs/<run_id>` — inside the working tree, not exempt from worktree teardown.
`engine_dispatch.record_dispatch_manifest` writes the equivalent `saga.manifest.v1` under the
git-common-dir cache (`manifest_store.py`), which is shared across worktrees of one checkout but still
dies with the checkout itself. The chaperone-dispatch protocol
(`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` §5 "Verify")
reads an external engine's raw returned patch, reviews it, and only then applies a fix — nothing
retains the pre-fix bytes, so no fix-delta measurement corpus exists. And no query anywhere reconciles
a claimed disposition (`ran-as-requested`) against what actually ran; `docs/engineering-journal/
LEARNINGS.md` records five-plus silent-no-op incidents this would have caught.

## Requirements

- **R1. `--audit-store` on `agy_delegate.py` (default `~/.claude/delegation-audit`).** Every bundle
  mirrors its result payload (and embedded receipt, when present) to the durable store, resolvable by
  `run_id` alone, independent of whether the originating bundle directory still exists.
- **R2. `engine_dispatch.py`'s dispatch-manifest write path mirrors symmetrically.**
  `record_dispatch_manifest` and `adjudicate_manifest` mirror the provenance manifest — and the raw
  `bridge_receipt.v1` when the dispatched evidence carries one — to the same durable store, keyed by
  `execution_id`.
- **R3. Write-once pre-fix draft snapshot in the chaperone-dispatch path.** The chaperone's Verify step
  (`external-engine-workers.md` §5 step 1, before `verified_by_claude = True` and before Apply) snapshots
  the engine's raw returned patch/output keyed by run id; a second snapshot attempt for the same id is
  rejected, never silently overwritten.
- **R4. `/delegation-audit` reconciliation.** A skill (or CLI, co-located with the audit-store code)
  reads the durable store for a session/repo and flags exactly the delegations whose disposition claims
  real execution (`RAN_AS_REQUESTED` / agy `agy_launched`) but whose receipt shows a Claude-fallback or
  no proof of launch — never flagging a delegation that genuinely ran.
- **R5. No test writes to a real developer home directory.** Every existing and new test that drives
  `agy_delegate.py`'s CLI (`main()`) or calls the mirroring library functions directly isolates the
  audit-store root explicitly; none silently inherits the real `~/.claude/delegation-audit` default.
- **R6. Full suite, lint, and types stay green; release surfaces ship in the same PR** — `uv run
  pytest`, `ruff format --check`, `ruff check`, `mypy plugins/ scripts/ tests/
  --ignore-missing-imports`, plus `plugin.json` / `marketplace.json` / `CHANGELOG.md` / drift-guard
  tests for every plugin whose behavior changed.

## Key Technical Decisions

**KTD1 — Shared primitives live in fleet-core, not saga.** New module
`plugins/fleet-core/scripts/fleet_commons/audit_store.py`, loaded by every consumer via
`fleet_commons_shim.load("audit_store")` — the same install-boundary rationale `bridge_receipt.py`
already documents (a saga-local module imported by agy breaks at install time). Three plugins
(agy, saga, team-execution) need symmetric access; fleet-core is the existing home for exactly this
shape of cross-plugin primitive (precedent: `{#external-engine-*}` decisions, issue #463).

**KTD2 — Duplicate the tiny atomic-write / write-once / safe-name primitives inside `audit_store.py`
rather than importing `plugins/saga/scripts/outcome_store.py`.** Cross-plugin import would reintroduce
the exact install-time break `bridge_receipt.py`'s own docstring calls out. The duplicated surface is
~25 lines (temp+`os.replace`, temp+`os.link`, a traversal guard) — the same primitive
`outcome_store.py` originally defined standalone, now re-defined once more inside fleet-core's install
boundary rather than reached across it.

**KTD3 — Machine-local, uncommitted store root — the deliberate opposite of `evidence_ledger.py`'s
KTD1.** `evidence_ledger.py` (#398) chose a **committed**, per-saga home
(`docs/evidence/<saga-id>/`) because a fresh clone on a different machine must be able to verify a
custody chain that belongs in PR history. This issue's requirement is the opposite shape: delegation
evidence must survive **worktree teardown on the same machine**, never needs to reach a different
developer's clone, and committing raw diffs/receipts to every PR would bloat history for no reader.
`~/.claude/delegation-audit` (machine-local, git-ignored by construction — it is outside any repo)
is the correct answer to a different question than evidence-ledger answered, not a divergence from
its precedent.

**KTD4 — New module name and file, distinct from the existing `fleet_commons/delegation_audit.py`
(#384).** That module already classifies transcripts and corroborates *live* bundle roots
(`.claude/agy/runs`, `.claude/codex/runs`) — exactly the disposable location this issue exists to
escape. `audit_store.py` owns the durable store's read/write primitives; `delegation_audit.py` gains
one new function (`reconcile_store`) that reconciles the durable store instead of a live bundle root,
reusing its existing `REAL` / `FALLBACK_SUSPECTED` vocabulary rather than inventing a parallel one.
Two files, two concerns, no name collision, no duplicated algorithm.

**KTD5 — The real-world "on by default" behavior lives at the outermost entry point that has one;
every underlying function defaults to `None` (skip).** `agy_delegate.py`'s CLI `main()` resolves
`~/.claude/delegation-audit` when `--audit-store` is omitted (R1's literal requirement) and passes
the resolved `Path` into `create_validation_bundle` / `create_supervised_bundle`, whose own
`audit_store_root: Path | None = None` parameter mirrors only when given a value. `engine_dispatch.py`
has no CLI layer, so its default-on behavior lives in the **documented call site**
(`worker-manifest.md`), which shows the chaperone passing the resolved default explicitly — mirroring
the existing explicit-construction pattern `manifest_store.Store.for_saga(...)` already uses. This
keeps every unit test that constructs these functions directly from ever touching a real home
directory unless it asks to.

**KTD6 — Existing subprocess-driven CLI tests for `agy_delegate.py` must isolate `--audit-store`
explicitly.** `tests/test_agy_delegate_contract.py` (3 call sites), `tests/test_agy_run_lease.py`
(2, via its `_run_wrapper` helper plus one direct call), and `tests/test_agy_apply_policy.py` (2, same
shape) invoke `main()` via `subprocess.run` with no `--audit-store` flag today. Left alone, R1's CLI
default would make every one of those tests write into the real `~/.claude/delegation-audit` on every
local test run. Every call site gets an explicit `--audit-store <tmp_path>/audit-store` argument —
named here so it is not an implicit landmine a later contributor discovers by finding stray files in
their home directory.

**KTD7 — `.delegation-drafts/` lives under the audit-store root, not the repo/worktree tree.** The
issue names the directory but not its root; a repo-local `.delegation-drafts/` would suffer the exact
teardown loss this issue exists to fix, since chaperone-dispatched units run inside the same disposable
worktrees as agy. Store it at `<audit_store_root>/delegation-drafts/<run_id>/raw.diff` — the more
conservative, teardown-safe reading of an underspecified DoD detail, made explicit rather than assumed
silently.

**KTD8 — One key namespace: `run_id` and `execution_id` name the same identity.** agy's bundles use
`run_id`; the chaperone-dispatch protocol uses `execution_id`. The durable store treats both as the
same string key under `runs/<id>/` — a given delegation has one identity regardless of which caller
names it, and nothing in the codebase today needs both a `run_id` and a distinct `execution_id` for
one delegation.

**KTD9 — Store layout.**

| Path (under `audit_store_root`) | Written by | Content |
|---|---|---|
| `runs/<id>/receipt.json` | agy (from `result_payload["receipt"]`), engine_dispatch (from `evidence.runner_receipt`) | raw `bridge_receipt.v1`, when the run produced one |
| `runs/<id>/result.json` | agy only | full `result_payload` snapshot (status, `agy_launched`, summary) — resolvable even when no receipt exists |
| `runs/<id>/manifest.json` | engine_dispatch (`record_dispatch_manifest` / `adjudicate_manifest`) | `saga.manifest.v1`, carries `disposition` |
| `delegation-drafts/<id>/raw.diff` | team-execution chaperone (write-once) | the engine's raw pre-fix returned patch/output |

## Implementation Units

### U1. Shared durable audit-store primitives (fleet-core)

**Goal:** `plugins/fleet-core/scripts/fleet_commons/audit_store.py` — `Store` (root resolution,
default `~/.claude/delegation-audit`, KTD9 layout), `mirror_receipt`, `mirror_result`,
`mirror_manifest`, `resolve_receipt`, `resolve_result`, `resolve_manifest`, `list_runs`,
`write_once_draft` / `draft_path`, `AuditStoreError`. Duplicates the small atomic-write / write-once /
safe-name primitives per KTD2; no I/O at import.

**Files:** `plugins/fleet-core/scripts/fleet_commons/audit_store.py` (new), `tests/test_audit_store.py`
(new), `tests/test_delegation_audit.py` (extended: new `audit_store` fixture +
`test_draft_snapshot_write_once_guard`).

**Test scenarios:** `tests/test_audit_store.py` — `test_mirror_receipt_resolvable_by_run_id_alone`,
`test_mirror_result_resolvable_when_no_receipt`, `test_mirror_manifest_resolvable_by_id`,
`test_default_root_resolves_under_home_dot_claude_delegation_audit`,
`test_run_id_path_traversal_rejected` (e.g. `run_id="../../etc"` raises `AuditStoreError`).
`tests/test_delegation_audit.py` — `test_draft_snapshot_write_once_guard` (first
`write_once_draft` succeeds; a second call for the same `run_id` raises `AuditStoreError` and the
first snapshot's bytes are unchanged) — the literal DoD acceptance check
(`-k draft_snapshot_write_once_guard`).

**Depends on:** none.

### U2. `/delegation-audit` reconciliation core (fleet-core)

**Goal:** Extend `plugins/fleet-core/scripts/fleet_commons/delegation_audit.py` with
`reconcile_store(store, run_ids=None) -> list[NoOpFlag]`: for each run, derive the claimed
disposition (manifest's `disposition`, or agy's `result.json["agy_launched"]`/`status`) and the
observed proof (`receipt.json` present and schema-valid per `bridge_receipt.validate_receipt`); flag a
no-op exactly when claimed-real and NOT observed-real. Degrades to "no signal" rather than raising on
a missing/corrupt file (matches `corroborate()`'s existing never-raise ethos).

**Files:** `plugins/fleet-core/scripts/fleet_commons/delegation_audit.py`,
`tests/test_delegation_audit.py`.

**Test scenarios:** `test_flags_forced_fallback_only` (seed two runs — one with a manifest claiming
`ran-as-requested` plus a valid receipt; one claiming `ran-as-requested` with no receipt/an invalid
one — assert the flagged set is exactly the second run_id) — the literal DoD acceptance check
(`-k flags_forced_fallback_only`). `test_reconcile_store_degrades_on_corrupt_manifest` (malformed
`manifest.json` → run treated as unproven, never raises).

**Depends on:** U1.

### U3. agy `--audit-store` CLI + bundle mirroring

**Goal:** Add `--audit-store` to `agy_delegate.py`'s parser (default `None`; `main()` resolves
`audit_store.Store.for_root(args.audit_store).root` when omitted — R1/KTD5). Add
`audit_store_root: Path | None = None` to `create_validation_bundle` and `create_supervised_bundle`;
mirror `result_payload` (and its `receipt` sub-object, when present) after each bundle write, at every
return point of both functions (KTD9). Update every existing subprocess-driven CLI test to pass an
isolated `--audit-store` (KTD6).

**Files:** `plugins/agy/scripts/agy_delegate.py`, `tests/test_agy_delegate_contract.py` (new test +
isolate its 3 existing `subprocess.run` call sites), `tests/test_agy_run_lease.py` (isolate its
`_run_wrapper` helper and one direct call), `tests/test_agy_apply_policy.py` (isolate its
`_run_wrapper` helper and one direct call).

**Test scenarios:** `test_audit_store_survives_bundle_deletion` (build a supervised bundle with a
receipt, `shutil.rmtree` the bundle directory, assert `audit_store.resolve_receipt` still returns the
receipt by `run_id` alone) — the literal DoD acceptance check
(`-k audit_store_survives_bundle_deletion`). `test_validation_bundle_mirrors_result_without_receipt`
(a validation-only bundle mirrors `result.json` with no `receipt.json`, since no launch ever occurred).

**Depends on:** U1.

### U4. saga `engine_dispatch.py` mirror wiring

**Goal:** Add `audit_store_root: Path | None = None` to `record_dispatch_manifest` and
`adjudicate_manifest`; when given, mirror the manifest via `audit_store.mirror_manifest` and, when
`evidence.runner_receipt` is present, `audit_store.mirror_receipt` — both keyed by `execution_id`
(KTD8). Update `worker-manifest.md`'s documented call snippet to pass the resolved default explicitly
(KTD5).

**Files:** `plugins/saga/scripts/engine_dispatch.py`,
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
`tests/test_saga_engine_dispatch.py`.

**Test scenarios:** `test_record_dispatch_manifest_mirrors_to_audit_store` (pass
`audit_store_root=tmp_path`; assert `audit_store.resolve_manifest` and `resolve_receipt` return the
mirrored data independent of `manifest_store`'s own tree). `test_adjudicate_manifest_updates_mirror`
(adjudicating a manifest re-mirrors the updated version, mirroring `manifest_store.write_manifest`'s
own "never write-once, overwrite in place" contract).

**Depends on:** U1.

### U5. `/delegation-audit` skill + CLI query surface

**Goal:** `plugins/saga/scripts/delegation_audit_query.py` — a thin CLI (`--audit-store <root>`,
default the same home path) that lists runs via `audit_store.list_runs`, calls
`delegation_audit.reconcile_store`, and prints a JSON reconciliation report (flagged no-ops + clean
runs). `plugins/saga/skills/delegation-audit/SKILL.md` — the `/delegation-audit` skill wrapping this
CLI, documenting scope (repo/session query, read-only, advisory — never a gate) and its position
beside the existing Stop-hook tripwire (`delegation_stop_audit_hook.py`, a different, always-on
mechanism this skill does not replace).

**Files:** `plugins/saga/scripts/delegation_audit_query.py` (new),
`plugins/saga/skills/delegation-audit/SKILL.md` (new), `tests/test_delegation_audit_query.py` (new).

**Test scenarios:** `test_cli_reports_no_ops_and_clean_runs` (drive `main()` via subprocess against a
seeded tmp audit-store; assert the JSON output names the flagged run and the clean run distinctly).
`test_cli_handles_empty_store` (no `runs/` directory yet → empty report, exit 0, never a crash).

**Depends on:** U1, U2.

### U6. team-execution write-once draft snapshot wiring

**Goal:** Document the snapshot hook in `external-engine-workers.md` §5 step 1 ("Verify") — before
`evidence.verified_by_claude = True`, the chaperone calls
`audit_store.write_once_draft(store, run_id=evidence.execution_id, content=evidence.evidence)`
(KTD7/KTD8), so the raw pre-fix patch/output is captured before any adjudication or apply. Cross-link
from `worker-manifest.md`'s evidence-adjudication description.

**Files:** `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`,
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
`tests/test_team_execution_chaperone.py` (new).

**Test scenarios:** `test_draft_snapshot_matches_fix_delta` (write the raw draft via
`write_once_draft`; compute the chaperone's own recorded fix-delta as
`difflib.unified_diff(raw, final_applied)`; assert diffing the stored snapshot against the same final
content reproduces that identical delta) — the literal DoD acceptance check
(`-k draft_snapshot_matches_fix_delta`).

**Depends on:** U1.

### U7. Release surfaces + full CI gate

**Goal:** Version bumps for every plugin whose behavior changed, matched to each plugin's own observed
CHANGELOG cadence (verified against each plugin's actual history, not a uniform rule) —
**fleet-core** 0.8.4 → 0.8.5 (patch: precedent is 0.8.2/0.8.3, both "Added: new module" entries bumped
at the patch digit, not minor), **agy** 0.2.1 → 0.2.2 (patch: 0.2.1 itself patch-bumped a comparably
substantial non-breaking "Added" change; agy reserves a minor bump for an explicitly BREAKING change,
e.g. 0.1.2 → 0.2.0), **saga** 0.81.0 → 0.82.0 (minor: matches the immediately-preceding evidence-ledger
addition, 0.80.0 → 0.81.0, a comparably substantial new-module-plus-skill-wiring change), **team-execution**
2.14.4 → 2.14.5 (patch: this unit is reference-doc-only within team-execution itself — no new `.py` file
lands in `skills/team-execution/scripts/`, matching the doc-only "Changed" precedent at 2.13.1/2.14.1–4
rather than the "Added" precedent at 2.14.0, which shipped a new script alongside its doc changes).
Regenerate `.claude-plugin/marketplace.json` via `scripts/sync_marketplace.py`. `CHANGELOG.md` entries
for all four plugins. This corrects the issue's own release-surface checklist, which named only
agy/saga/team-execution and omitted fleet-core — fleet-core is genuinely gaining a new module and an
extended one, so it ships too.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/agy/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/fleet-core/CHANGELOG.md`, `plugins/agy/CHANGELOG.md`,
`plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`. Three drift-guard tests hardcode
the current version literal and must be edited in lockstep or CI reds on the bump itself, not just on a
plugin.json/marketplace.json mismatch: `tests/test_agy_plugin.py` (`test_agy_metadata_is_marketplace_registered`
asserts `plugin_json["version"] == "0.2.1"` verbatim, `tests/test_agy_plugin.py:38`),
`tests/test_saga_plugin.py`, and `tests/test_team_execution_plugin.py` (same hardcoded-literal shape,
confirmed present via `grep -l` for each plugin's current version string across `tests/*.py`). No
equivalent `test_fleet_core_plugin.py` exists today, so the fleet-core bump has no hardcoded-literal
test to update — verified absent, not merely assumed.

**Test expectation:** none for the bookkeeping edits themselves; the three drift-guard tests above are
existing tests whose hardcoded literal must be updated as part of this unit (not new coverage) — a
version bump without updating them fails the existing suite, it is not merely "covered" passively.
`tests/test_sync_marketplace.py` / `tests/test_marketplace_hook.py` cover the marketplace-regeneration
consistency; the full-suite run (R6) is the final check.

**Depends on:** U1–U6.

### U8. Engineering journal entries

**Goal:** `docs/engineering-journal/DECISIONS.md` — the machine-local-vs-committed store-root choice
(KTD3) and the fleet-core module split (KTD1/KTD4). `docs/engineering-journal/LEARNINGS.md` — the
non-obvious mechanism: a CLI flag whose default resolves under `Path.home()` silently pollutes a real
developer's home directory on every subprocess-driven test run unless every call site isolates it
explicitly (KTD6), with the evidence (this PR, the specific files touched) and the generalizable rule.

**Files:** `docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`.

**Test expectation:** none — journal entries, written in the same commit as the mechanism they record.

**Depends on:** U1–U7.

## Execution prerequisites

**Backend: inline, chosen over the mechanical recommendation.**
`lifecycle_state.recommend_execution_backend()` (workflow availability probed, per operator-choice.md
§5.2) returns `team-execution` for this plan's raw shape (`functional_file_count≈13 >= 8` and
`phase_count=6 >= 4` — U1–U6's code-bearing units), on the size/risk axis alone; no consensus,
security, infra, cross-repo, or deployment signal is present (`needs_consensus=False`,
`has_security=False`, `has_infra=False`, `cross_repo=False`, `deployment_sensitive=False`). That
axis is an explicitly-documented **output-blind volume proxy**
(`should_offer_team_execution`'s own docstring: "volume and sequencing, not governance"), not a
governance signal — this change stays inside one already-reviewed repo, needs no reviewer-CONSENSUS
gate, no named scanners, and no guarded deploy. The issue's own recommended executor profile
(Model: sonnet, Effort: medium, Backend: inline — "no open design ambiguity requiring opus-tier
judgment") and sibling leaf #398 in this same outcome (5 units, `phase_count=5 >= 4` by the identical
heuristic, also chose inline — `docs/plans/2026-07-12-evidence-ledger-plan.md` "Execution
prerequisites") both independently land on inline for a comparably-shaped plumbing change. Overriding
to inline here, recording `--orchestration-recommended team-execution` alongside
`--orchestration-mode inline` on the saga tick (R12 override-rate telemetry) so the divergence is
visible, not silently dropped.

**Pause before `/work`.** Do not start `/work` until the session is running at the issue's
recommended executor tier (Sonnet / medium); surface this at route time.

**Branch and merge target.** Leaf work branches from `main` (e.g. `work/396-delegation-audit-store`);
the PR merges to `main`. The outcome branch `outcome/evidence-integrity` holds only the spec — the
outcome coordinator harvests sub-396 completion from the merged PR.

## Confidence pass

This is a Deep plan (cross-cutting four plugins), so a deepening pass is warranted (Phase 4). Grounding
was already thorough before writing a single requirement: `agy_delegate.py`'s two bundle-creation
functions and every return point were read in full; `engine_dispatch.py`'s `record_dispatch_manifest`
/ `adjudicate_manifest` and the `AdvisoryEvidence` shape; `bridge_receipt.py`'s full schema;
`fleet_commons/delegation_audit.py`'s existing classify/corroborate/reconcile algorithm and its
existing tests; `evidence_ledger.py` (the immediate sibling leaf, #398/PR #567) end to end for its
house pattern and its own KTD1 (the precedent this plan deliberately diverges from, with rationale);
`outcome_store.py`'s atomic-write primitives; `worker-manifest.md` and `external-engine-workers.md`'s
exact Verify → Apply sequence (the issue's own quoted line numbers had drifted since ideation — the
concept was located by content, not by stale line numbers); and every existing test file that invokes
`agy_delegate.py` via subprocess, to find the home-directory pollution risk (KTD6) before it became a
regression. No additional `Explore` dispatch is needed beyond this direct reading — the sections above
already carry `path:line` grounding rather than a generic checklist.

## Scope Boundaries

Out of scope (from the issue, binding):

- Redefining or hardening `bridge_receipt.v1` itself (schema, `AdvisoryEvidence` gating, the
  `receipt_emitter` registry key) — that landed already as #383; this capability consumes it as-is.
- Any standing/scheduled audit cadence or dashboard — `/delegation-audit` is on-demand only.
- Changing the chaperone-dispatch executor model or granting external engines gating authority —
  `{#external-engines-never-gatekeepers}` (#283) and `{#external-engine-chaperone-dispatch}` (#318)
  stay exactly as they are; this capability only makes evidence durable and auditable.
- Backfilling durability onto historical runs already reclaimed before this capability ships.
- Building a new bridge or onboarding a third external engine.

Deferred to follow-up work (not non-goals):

- A dedicated dashboard or long-running watcher over the durable store — `/delegation-audit` stays a
  point-in-time query.
- Cross-machine aggregation of the audit store (it is deliberately machine-local, KTD3); a future issue
  could add an explicit export/sync step if multi-machine reconciliation becomes a real need.
- Retention/pruning policy for `~/.claude/delegation-audit` — out of scope for this issue; the store
  grows unbounded today, matching the equally-unbounded `.claude/agy/runs/` it mirrors. This also
  extends the *lifetime* (not the trust boundary) of raw draft/result content that already exists
  briefly in the disposable bundle today — `bridge_receipt.v1` itself carries no secrets by contract
  (`bridge_receipt.py`'s own docstring), but `result.json` and `.delegation-drafts/*/raw.diff` mirror
  whatever the engine actually returned, now retained indefinitely on the same machine. No new
  exposure surface is created (same machine, same operator), but an unbounded-growth follow-up should
  weigh this when it lands.
