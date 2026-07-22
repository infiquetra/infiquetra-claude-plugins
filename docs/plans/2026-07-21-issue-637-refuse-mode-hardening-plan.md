---
title: Issue #637 — harden refuse-mode lease admission and DispatcherError cause-branching
type: feat
status: active
date: 2026-07-21
origin: docs/sdlc-issue-drafts/2026-07-21-harden-refuse-mode-lease-admission-pid-liveness.md
---

# Issue #637 — harden refuse-mode lease admission and DispatcherError cause-branching

## Summary

Discharge the two validated P3 advisories from #627's CLEAN review: wire the broker's existing
pid-liveness (`_owner_state`) into refuse-mode admission so a crash-orphaned lease no longer
self-refuses re-dispatch for the full 300 s TTL, and branch the `except DispatcherError` arm in
`_reconcile_once` so permanent dispatcher faults abort the tick loudly while lease-lifecycle
transients keep #627's halt-and-continue. Three serialized units against `origin/main 47dacede`
(saga 0.107.0, fleet-core 0.17.0); destination merge.

## Problem Frame

#627 (merged `8882bdc2`) shipped opt-in refuse-mode admission and a DispatcherError
halt-and-continue arm with two operator-accepted tradeoffs, both validator-anchored in the review
envelope (`docs/evidence/issue-627/artifacts/`):

1. **Crash-orphan self-refusal.** The refuse gate
   (`plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2168-2178`, reached from
   `acquire_agent`) consults only `_expired` (TTL + boot-id). `owner_id` is deterministic per
   `(outcome_id, subplot_id)`, so after a SIGKILL skips the finally-release, the orphaned lease
   (`DEFAULT_TTL_SECONDS = 300`, `lease_broker.py:36`) refuses the same leaf's re-dispatch every
   tick until TTL expiry. The broker already computes pid-liveness — `_owner_state` at
   `lease_broker.py:3901` (boot-id, `process_exists`, process-start identity) — but wires it only
   into `sweep()` (`:3957`), never admission. `owner_pid` is recorded at acquire
   (`outcome_dispatcher.py:268`), so admission has the data.
2. **Permanent faults retried indefinitely.** `make_dispatcher`'s normalize arm
   (`plugins/saga/scripts/outcome_dispatcher.py:283-284`) collapses every admission-block failure
   — fleet-core shim/protocol failures (permanent) and refuse-mode `LeaseConflictError`
   (transient) alike — into one `DispatcherError`. The `except DispatcherError` arm in
   `_reconcile_once` (`plugins/saga/scripts/outcome.py:1589`) settles `SILENT_NOOP` and leaves the
   subplot ready, so a permanent misconfiguration re-enters the frontier every tick with no
   attempt cap — visible, but indefinite, where the pre-#627 behavior aborted loudly.

Both fixes are Claude-side. `infiquetra-codex-plugins#45` mirrors the semantics codex-natively;
landing #637 first means codex ports the hardened semantics once (its sequencing note).

## Requirements

- R1. A refuse-mode acquire whose conflicting prior lease has a provably **dead** owner admits
  (supersedes) immediately — no TTL wait. "Dead" is `_owner_state`'s existing definition: stale
  boot-id, missing pid, or process-start identity mismatch.
- R2. A **live** owner still refuses with `LeaseConflictError`, and an **unknown** owner state
  (absent `owner_pid` or unreadable process identity) also refuses — fail-closed; only proof of
  death admits.
- R3. No same-owner bypass: a live holder refuses even when `owner_id` matches the requester
  (cross-runtime exclusion is the point of refuse mode; #627 KTD1 unchanged).
- R4. The dispatcher seam exposes a **typed transient/permanent contract**: lease-lifecycle
  transients (admission `LeaseConflictError`, mid-flight renew failure, lost lease authority — the
  set #627's arm comment already names as transient at `outcome.py:1590-1592`) raise a typed
  `DispatcherError` subclass; every other cause stays plain `DispatcherError`. `outcome.py` never
  imports fleet-core types to branch.
- R5. The transient branch in `_reconcile_once` is byte-preserving in behavior: release the
  per-subplot lease, append the reducer-visible `(dispatch, halt)` record (spread-first,
  literal-last, `receipt_kind` preserved), settle `SILENT_NOOP`, continue the tick. Existing #627
  pins — including `test_advance_records_lease_refusal_as_halt_and_continues` — stay green
  unmodified.
- R6. A non-transient `DispatcherError` **re-raises and aborts the tick loudly** (pre-#627 posture
  for permanent faults). No backoff state, no new ledger classification. Named consequence: the
  per-subplot `dispatch-{sid}` store lock is left held and self-heals via `acquire_lease`'s
  stale-reclaim after the 900 s store-lock TTL (`DEFAULT_LEASE_TTL`, `outcome.py:66`; reclaim
  semantics at `outcome_store.py:612`) — the coordinator lock is released by the existing
  `finally` (`outcome.py:1072-1073`), so an aborted tick never wedges the coordinator.
- R7. Halt-record shape and the closed `LEDGER_CLASSIFICATIONS` vocabulary gain no members; #627
  KTD3/KTD4 shapes unchanged.
- R8. Release surfaces move in the same PR: fleet-core 0.17.0 → 0.18.0, saga 0.107.0 → 0.108.0,
  `.claude-plugin/marketplace.json`, both CHANGELOGs, drift-guard version pins; DECISIONS entry for
  the two adjudicated calls; `python3 scripts/check_release_surface_parity.py` in parity.
- R9. Full battery green: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`, `uv run bandit -r plugins/` (no
  new non-LOW findings).

## Key Technical Decisions

- **KTD1 — pid-liveness at the refuse gate, tri-state fail-closed** (operator-adjudicated
  2026-07-21): in `_drop_superseded_resource_lease`'s refuse branch, a live-unexpired prior lease
  is additionally checked with `_owner_state(prior_lease)`; `dead` → fall through to supersede,
  `live` **and** `unknown` → refuse. Rationale: removes the crash-orphan window rather than
  shrinking it (rejected: shorter dispatch TTL — bounded window remains, and a too-short TTL
  expires live slow dispatches); `unknown` must refuse or a cross-host/identity-blind peer could
  be superseded while alive. In-repo precedent: the recovery path already enforces exactly this
  posture — `lease_broker.py:4202` refuses recovery unless the original owner is provably dead.
- **KTD2 — typed subclass at the dispatcher seam, cause-classified where raised**: a
  `DispatcherLeaseTransientError(DispatcherError)` (name final at implementation; exported from
  `outcome_dispatcher.py`) is raised at exactly the lease-lifecycle sites — the normalize arm when
  `isinstance(cause, LeaseConflictError)` (checked against the shim-loaded authority class inside
  `outcome_dispatcher`, which already holds the `authority` handle), the renew-failure raise
  (`:292-296`), and the lost-authority raises (`:290`, and the settlement-cleanup sites `:303/:316/:325`
  reviewed site-by-site in U2 against the #627 comment's transient set). `outcome.py` branches with
  one `isinstance` on the dispatcher's own exported type. Rationale: classification lives where the
  cause is in hand; outcome code stays free of fleet-core imports (rejected: `__cause__`
  isinstance-checking in `outcome.py` — drags broker types across the seam).
- **KTD3 — permanent faults abort the tick loudly** (operator-adjudicated 2026-07-21): the
  non-transient branch re-raises. Rationale: protocol skew and fleet-core resolution failures are
  environmental — they would hit every leaf, so continuing the tick buys nothing, and loud abort
  restores the pre-#627 page-the-operator posture with zero new state (rejected: capped backoff —
  durable attempt state for no real coverage gain; rejected: per-subplot quarantine — needs a new
  reducer-visible blocking state, larger blast radius than a P3 hardening warrants).
- **KTD4 — #627's settled decisions are inviolate**: opt-in refuse default (KTD1), halt-record
  shape + `SILENT_NOOP` settlement (KTD3/KTD4), guard exemption predicate, supersede-mode
  behavior for every non-dispatcher consumer, and the byte-frozen `outcome_compat` seam are all
  untouched — this plan hardens strictly inside them, so no codex re-freeze is forced (codex#45
  mirrors semantics separately).

## Implementation Units

### U1. Pid-liveness at the refuse-mode admission gate

**Goal:** a dead holder no longer blocks re-dispatch; live/unknown holders still refuse.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (refuse branch at
`:2168-2178`; `_owner_state` reuse), `tests/test_fleet_lease_broker.py`.

**Approach:** inside the `on_conflict == "refuse"` branch, when the prior lease is live-unexpired,
consult `self._owner_state(prior_lease)`; refuse only for `live`/`unknown`. Keep the
settlement-retained and canonically-closed precedence arms strictly above the liveness gate
(unchanged order). Update the refuse-gate docstring honestly (it currently says "one liveness
gate" meaning `_expired` — say what is now checked). `_owner_state` itself is unmodified — its
existing consumers (`sweep()` at `:3957`, the recovery gate at `:4202`) see no behavior change;
U1 only adds a call site.

**Test scenarios** (`tests/test_fleet_lease_broker.py`):
- Crash-orphan recovery: refuse-mode acquire; holder recorded with a dead pid (provider fake) →
  re-acquire same resource admits without TTL wait; registry supersession matches supersede-mode
  byte-behavior.
- Live holder refuses: same scenario with a live process identity → `LeaseConflictError`, zero
  registry mutation (the #627 two-broker pin stays green).
- Unknown refuses: prior lease with `owner_pid=None`, and separately with unreadable process
  identity → refuse (fail-closed pin).
- Same-owner live still refuses (R3).
- Stale boot-id counts as dead (reboot recovery without TTL wait).
- Supersede-mode call sites byte-unchanged (`test_retry_supersedes_at_full_capacity` untouched).

### U2. Typed transient contract + loud-abort branch in `_reconcile_once`

**Goal:** lease-lifecycle transients keep halt-and-continue; every other `DispatcherError` aborts
the tick loudly.

**Files:** `plugins/saga/scripts/outcome_dispatcher.py` (new exported subclass; raise-site
classification at `:283-284`, `:290`, `:292-296`, cleanup sites `:303/:316/:325` site-by-site;
check the `:822` consumer stays coherent), `plugins/saga/scripts/outcome.py` (`:1589` arm),
`tests/test_outcome_dispatcher.py`, `tests/test_outcome_command.py`.

**Approach:** add `DispatcherLeaseTransientError(DispatcherError)`; the normalize arm classifies on
the in-hand cause (`authority.LeaseConflictError` → transient; anything else → plain). The
`outcome.py` arm catches `DispatcherError`, and non-transient instances re-raise before any
lease-release/ledger work; the transient path is the existing #627 body, moved under the
`isinstance` check without behavioral change. Update the arm's #627 comment to describe the branch
(keep the two TTLs distinct in the rewritten comment: 900 s is the store-lock TTL
(`DEFAULT_LEASE_TTL`, `outcome.py:66`), 300 s the broker dispatch lease (`lease_broker.py:36`)).

**Test scenarios:**
- `tests/test_outcome_dispatcher.py`: admission `LeaseConflictError` → transient subclass; shim
  load/protocol-skew failure → plain `DispatcherError`; renew failure → transient subclass.
- `tests/test_outcome_command.py`: existing pin
  `test_advance_records_lease_refusal_as_halt_and_continues` green unmodified; new
  permanent-fault pin — a dispatcher raising plain `DispatcherError` aborts `advance()` loudly
  (typed error surfaces, no `SILENT_NOOP` settle, no halt record for that subplot; per R6 the
  `dispatch-{sid}` lock stays held for TTL stale-reclaim — assert no release — while the
  coordinator lock is released by the outer `finally`); transient renew-failure flavor still
  halts-and-continues.

### U3. Release surfaces, journal, drift-guard pins

**Goal:** installed-plugin metadata tells the same story as the diff, in the same PR.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json` (0.18.0),
`plugins/saga/.claude-plugin/plugin.json` (0.108.0), `.claude-plugin/marketplace.json`,
`plugins/fleet-core/CHANGELOG.md`, `plugins/saga/CHANGELOG.md`, drift-guard version pins
(`tests/test_saga_plugin.py` and any release-triad pins that assert versions),
`docs/engineering-journal/DECISIONS.md` (commit the staged `{#refuse-liveness-and-loud-abort-637}`
entry; do not duplicate), `docs/engineering-journal/LEARNINGS.md` only if implementation surfaces
a non-obvious mechanism.

**Test expectation:** none beyond the drift guards — release-surface parity is checked by
`python3 scripts/check_release_surface_parity.py` (R8) and the existing version-pin tests.

## Scope Boundaries

Out of scope (true non-goals): redesigning #627's KTD1/KTD3/KTD4; the guard-walk TOCTOU advisory
(`audit_store.py:194` area — separate future fd-walk item); supersede-mode and every
non-dispatcher lease consumer; cross-clone settlement coordination (#627 R7 boundary); any change
to the byte-frozen `outcome_compat` seam.

Deferred to follow-up work: codex-side mirroring of both semantics (owned by
`infiquetra-codex-plugins#45`, which should plan against this issue's merge SHA); any acceptance
re-run of the cross-runtime harness (also codex#45).

## Verification

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/check_release_surface_parity.py
```
