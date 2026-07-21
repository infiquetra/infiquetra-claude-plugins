---
title: Lease seam and guard-scope defects — refuse-mode admission, DispatcherError arm, universal ancestor walk, visible halt records
type: fix
status: active
date: 2026-07-20
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/627
---

# Lease seam and guard-scope defects — refuse-mode admission, DispatcherError arm, universal ancestor walk, visible halt records

## Summary

Discharge the four validated upstream routings from the codex PA-2 review (#627) against
`origin/main` `83a170ff` (saga 0.106.1, fleet-core 0.16.0): give the outcome dispatch lease an
opt-in refuse-on-live-conflict admission mode, catch `DispatcherError` on the reconcile hot path,
make the ancestor guards walk every path component fail-closed, and make receipt-spread halt
records visible to the reducer and the consolidated report. The codex side re-freezes and
re-ports after merge — that follow-up issue (re-freeze + the COR3 worktree-lease port unit) is
defined here and filed at close.

## Problem frame

The PA-2 programmatic review of the codex seam activation validated three findings and
discovered a fourth against code shared with or byte-identical to this repo. Per the
upstream-first discipline (acceptance plan KTD7), root causes land here first. Grounding at
`83a170ff` (2026-07-20, three read-only surveys) re-verified every mechanism and corrected the
issue's stale anchors; corrections are folded into the units below.

**Grounding corrections to the issue text** (authoritative for implementation):

- `DispatchRequest` **does** carry `dispatch_id`/`attempt` (`plugins/saga/scripts/outcome.py:109-110`);
  the `getattr` fallback in `outcome_dispatcher.py:216-220` is defensive duck-typing, not a hole.
  `dispatch_id` is content-derived and deterministic
  (`dispatch_settlement.py:1525`: `outcome:{sha256(outcome)[:32]}:frontier:{roster_digest}`), so
  cross-runtime races over the same leaf **do** collide on one lease resource digest. Conflict
  detection is sound; only the admission response is at issue.
- Claude has exactly **one** `make_dispatcher` site (`outcome.py:2515-2518`), not two ("both
  sites" is codex topology). A second `default_lease_authority()` consumer exists at
  `outcome.py:2571` (`outcome_decompose.prune`), untouched by this plan.
- Post-#628, an uncaught `DispatcherError` does **not** wedge the leaf behind the
  "intent already exists without an acknowledgement" halt (that halt fires only for codex-native
  `outcome.dispatch.v2` intents — pinned by `test_live_native_intent_reads_in_flight_not_redriven`).
  The real current behavior is worse in the quiet direction: the legacy
  `kind: dispatch, phase: intent` record matches **no** reducer branch, so the orphaned intent is
  invisible, the per-subplot lease leaks until TTL (900 s), and the leaf silently re-dispatches.
  No halt, no operator page.
- Supersede-on-acquire is **documented intended behavior** for retries (#356:
  LEARNINGS `{#lease-settlement-window-356}`, DECISIONS "a newer retry either supersedes the
  stale panel before any append or waits"; pinned by
  `tests/test_fleet_lease_broker.py:734` `test_retry_supersedes_at_full_capacity`). A blanket
  refuse would break that design — hence the opt-in mode (KTD1).
- The current line anchors: rate-limit/halt arms at `outcome.py:1519`/`:1547`; the three
  colliding halt appends at `outcome.py:1314`/`:1383`/`:1552`; guards at
  `outcome_compat.py:1154-1189` and `audit_store.py:147-177`; the defect is self-acknowledged in
  source at `outcome_dispatcher.py:632-634`.

## Requirements

- R1. A live, unexpired lease on the same resource digest refuses a second `acquire_agent` when
  the caller selects the refuse admission mode; the default mode preserves today's supersede
  semantics unchanged for every existing consumer. Expired or canonically-settled priors behave
  exactly as today in both modes.
- R2. The outcome dispatcher (`make_dispatcher`) acquires with the refuse mode, so a
  cross-runtime overlap surfaces at admission as a typed `DispatcherError`, not as the loser's
  later `renew` failure.
- R3. `_reconcile_once` catches `DispatcherError` on the dispatch hot path: release the
  per-subplot lease, append a durable **reducer-visible** halt record, settle the attempt, and
  continue the tick. No abort, no TTL-leaked lock, no invisible orphaned intent.
- R4. Every receipt-spread halt append stores a final `"kind": "dispatch"` so
  `reduce_dispatch_ledger`'s halt arm and `outcome_report._halted_subplots` both see it; a halted
  leaf appears in the consolidated report's ambiguity tier end-to-end.
- R5. Both ancestor guards walk **every existing component of the candidate path regardless of
  location**, refusing symlinked, world-writable-non-sticky, and uninspectable components; the
  only mode exemption is world-writable AND sticky (the system-temp shape). Stock macOS roots
  (`/`, `/Users`, `/opt` at 0755; `/private/tmp` at 1777 sticky) pass. NFS/SMB mode-divergent
  homes and FAT32/exFAT world-writable non-sticky volumes are **refused** (fail closed, KTD2)
  with typed halts carrying relocate/remount guidance.
- R6. Group-writable ancestors remain accepted (the #624 pinned boundary — explicitly out of
  scope); the compat suite gains the acceptance twin test it currently lacks.
- R7. Prose tells the truth: no "covers every caller" claim survives in source
  (`grep -rn 'covers every caller' plugins/ --include='*.py'` is empty; the historical
  fleet-core `CHANGELOG.md:19` release note stays untouched as history — U5's new entry
  corrects the record instead); dispatcher comments and both CHANGELOGs
  describe the seam as admission exclusion for the outcome-dispatch resource class + per-clone
  settlement, and the cross-clone sequential boundary is documented (settlement ledger is
  per-`git-common-dir` by design; the lease covers the dispatch-preparation window only).
- R8. Release surfaces move in the same PR (saga → 0.107.0, fleet-core → 0.17.0,
  `marketplace.json`, both CHANGELOGs, drift-guard pins), and the codex follow-up issue
  (re-freeze `outcome_compat.py` byte-faithful to the merged SHA + the COR3 worktree-lease-layer
  port unit) is filed via mission-control and linked on #627 before close.
- R9. Full battery green: `uv run pytest`, `ruff check` + `format --check`,
  `mypy plugins/ scripts/ tests/`, `bandit -r plugins/`, release-surface parity.

## Key Technical Decisions

- KTD1 — **Refusal is an explicit opt-in admission mode, not a broker-default flip** (operator
  decision, 2026-07-20): `acquire_agent` grows an `on_conflict` parameter
  (`"supersede"` default | `"refuse"`); only the outcome dispatcher passes `"refuse"`. Rationale:
  #356's retry-supersede design and its pinned test stay intact for every other consumer; the
  cross-runtime seam gets real admission exclusion in the overlap window. Rejected: blanket
  refuse (breaks retry design, widest blast radius); prose-only documentation (leaves
  double-preparation in the overlap window).
- KTD2 — **Fail closed on NFS/SMB and FAT32/exFAT** (operator decision, 2026-07-20): no
  filesystem-type detection, no exemption list beyond world-writable+sticky. A store ancestor
  that lstats world-writable non-sticky has the unsafe property regardless of why the mount made
  it so. Costs pinned by test: an exFAT `/Volumes/External` clone cannot host a store. Rejected:
  `statfs f_fstypename` exemptions (reintroduces an accepted-unsafe class inside a byte-frozen
  cross-runtime seam).
- KTD3 — **The `DispatcherError` arm is transient-retriable with a durable visible halt**: model
  the lock-release/continue mechanics on the `BackendRateLimitError` arm (`outcome.py:1519`), but
  additionally append a reducer-visible `(dispatch, halt)` record — codex COR1 parity
  (`test_advance_records_lease_refusal_as_halt_and_continues` is the reference pin, including its
  "never an ack" constraint: the reducer's ack arms settle; a refusal must not). A later tick
  retries once the holder releases.
- KTD4 — **`kind` survives the spread as `"dispatch"`** at all three sites
  (`{**receipt, "kind": "dispatch"}` — spread first, literal last), the shape codex's new arm
  already ships with an in-code constraint comment. The receipt's own `kind` (`halt`/`spend-halt`)
  moves to a non-colliding field (`receipt_kind`) so no receipt data is lost.
- KTD5 — **Upstream-first byte-freeze discharge**: `outcome_compat.py` changes here break byte
  identity with codex on purpose; the acceptance harness's `contract_digests` will halt
  (`port-digest`) until the codex follow-up re-freezes from the merged SHA. That follow-up's
  scope (re-freeze + COR3 `outcome_worktrees` lease-authority threading port, ~46 references at
  Claude `794b4da6`) is defined in U5 and filed at close — never fixed codex-side first.
- KTD6 — **`dispatch_identity` adjudicated sound, pinned not redesigned**: the deterministic
  content-derived `dispatch_id` gives cross-runtime collision on the same attempt; add a
  determinism pin test instead of changing the resource-key shape.

## Implementation Units

### U1. Refuse-mode lease admission + dispatcher wiring

**Goal:** `_drop_superseded_resource_lease` learns liveness; `acquire_agent(on_conflict="refuse")`
raises a typed conflict error for a live unexpired prior on the same digest; the outcome
dispatcher opts in; prose de-overclaimed.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py`,
`plugins/saga/scripts/outcome_dispatcher.py`.

**Design constraints:** liveness = not `self._expired(...)` (`lease_broker.py:1804` predicate,
same monotonic/boot-id inputs as `renew`); refusal raises a dedicated typed error (subclass of
`LeaseOwnershipError` so existing broad handlers keep working) whose message names the holder's
`owner_id`; the settlement-retained (`registry.settlements`) and canonically-closed
(`close_receipt`) arms at `lease_broker.py:2122-2134` keep their existing precedence *above* the
new liveness check in both modes; `make_dispatcher` maps the refusal into
`DispatcherError` (existing normalize arm at `outcome_dispatcher.py:275-276` already does) with
the admission-refused message intact.

**Test scenarios** (`tests/test_fleet_lease_broker.py`, `tests/test_outcome_dispatcher.py`):
two brokers over one state dir — B's refuse-mode acquire on A's live lease raises the typed
conflict, A's lease untouched (zero-mutation assert on registry bytes); same shape with A's lease
expired → B acquires (reclaim preserved); default-mode call sites unchanged —
`test_retry_supersedes_at_full_capacity` stays green unmodified; dispatcher-level: refuse-mode
propagates as `DispatcherError` naming admission refusal; determinism pin — two
`DispatchRequest`s for the same outcome/subplot/attempt produce one resource digest (KTD6).

### U2. `DispatcherError` arm on the reconcile hot path

**Goal:** a mid-tick lease refusal (admission or renew) releases the per-subplot lease, writes a
durable reducer-visible halt record, settles the attempt, and continues the tick.

**Files:** `plugins/saga/scripts/outcome.py` (`_reconcile_once`, new arm beside
`outcome.py:1519`/`:1547`), `tests/test_outcome_command.py`.

**Design constraints:** arm order — `DispatcherError` after the two existing typed arms (it is
the broadest); release via `outcome_store.release_lease(store, f"dispatch-{sid}", holder)`
exactly as the siblings; halt record reducer-visible per KTD4 (`{**receipt, "kind": "dispatch"}`,
`phase: "halt"`, same `key` as the intent append at `outcome.py:1447` so the orphaned-intent lane
is paired, never an ack — KTD3); settle the attempt (`dispatch_settlement.settle_attempt`) as
`SILENT_NOOP` — the classification vocabulary is closed
(`LEDGER_CLASSIFICATIONS`, `dispatch_settlement.py:38`) and must not grow a member; the
`BackendHaltError` arm's no-backend-effect precedent applies since no work was dispatched;
append `sid` to `halted` (surfaced
in the same tick's return) — not `retriable` — so the operator sees the conflict while a later
tick still re-attempts after the holder releases.

**Test scenarios:** dispatcher raising `DispatcherError` mid-advance → lock released (next
`acquire_dispatch` succeeds without TTL wait), durable halt present,
`reduce_dispatch_ledger` derives `halted=True, settled=False`, tick continues (a second ready
leaf still dispatches in the same advance), attempt settled; renew-failure flavor
(`lease expired before settlement`) takes the same arm; mirror of the codex pin name for
cross-runtime greppability.

### U3. Halt-record visibility (Finding 4)

**Goal:** the three receipt-spread halt appends store `kind="dispatch"`; halted leaves reach the
consolidated report's ambiguity tier from a fresh read.

**Files:** `plugins/saga/scripts/outcome.py` (`:1314`, `:1383`, `:1552` — spread-first
literal-last per KTD4), `plugins/saga/scripts/outcome_dispatcher.py` (retire the
`outcome_dispatcher.py:632-634` self-acknowledgment), `tests/test_outcome_report.py`,
`tests/test_outcome_command.py`.

**Design constraints:** preserve the receipt payload under `receipt_kind`; do not touch the three
`settlement-halt` sites (`:1219`/`:1423`/`:1489` — different lane, no collision); update the
`tests/test_outcome_report.py:74` `_halt` fixture to the real production shape (spread a real
`HaltReceipt.to_dict()`) so the fixture can never mask this class again.

**Test scenarios:** end-to-end — forced `BackendHaltError` through `advance()` →
`reduce_dispatch_ledger(...)[sid]["halted"] is True` AND
`outcome_report._halted_subplots(store) == {sid}` AND the consolidated report renders the
ambiguity item on a fresh store read; same end-to-end for a spend halt (`SpendHaltError` site)
and the backend-menu halt site; halt-then-recovered still non-sticky
(existing `test_halt_then_recovered_is_not_a_sticky_ambiguity` green against the new shape).

### U4. Universal fail-closed ancestor walk (Finding 3)

**Goal:** both guards walk every existing component from the filesystem root, refusing symlinked
/ world-writable-non-sticky / uninspectable components anywhere; sticky world-writable exempt;
honest docstrings.

**Files:** `plugins/saga/scripts/outcome_compat.py` (`_refuse_unsafe_handoff_ancestors`,
`outcome_compat.py:1154-1189`), `plugins/fleet-core/scripts/fleet_commons/audit_store.py`
(`_refuse_unsafe_ancestors`, `audit_store.py:147-177`),
`tests/test_outcome_cross_runtime_contract.py`, `tests/test_audit_store.py` (the repo-root file
carries the #624 pins; `plugins/fleet-core/tests/` exists only in the codex repo).

**Design constraints:** keep `lstat`, never resolve inside the walk; drop the
under-`$HOME` early return; exemption predicate is `(mode & 0o002) and (mode & stat.S_ISVTX)` —
sticky world-writable passes, plain world-writable refuses (macOS `/private/tmp` 1777 passes,
exFAT 0o777 refuses); a symlink surviving post-resolve is a genuine time-of-check signal — refuse
it (LEARNINGS `{#resolve-disarms-symlink-guards-624}` rule: test through the real entry points);
`FileNotFoundError` early-return and `PermissionError` typed-halt arms keep their semantics;
both docstrings rewritten to the real scope, deleting `audit_store.py:157`'s
"covers every caller"; the two modules stay import-free of each other (ported twins — the compat
copy is the frozen cross-runtime seam, KTD5). Watch the blast radius: the #624 test
`test_ensure_private_dir_exempts_paths_outside_home` pins the *opposite* of the new behavior and
flips to a refusal pin.

**Test scenarios** (both suites, kept twinned): symlinked home component onto another volume —
driven through the REAL entry points (`Store.for_root(...).ensure()` and
`outcome_store.resolve_common_dir`-derived `_write_once`), the #624 probe shape
(`~/.bp-XXXX/local -> wwroot 0o777 non-sticky`) now refused; out-of-home clone under a 0o777
non-sticky ancestor refused (FAT32/exFAT shape, KTD2 pin); 1777 sticky ancestor accepted;
stock-root walk passes (`/`, `/Users`-shaped 0755 components); group-writable 0o770 accepted in
BOTH suites (R6 twin added to the compat suite); uninspectable component typed halt; receipt
still leaks no absolute path; fresh-subtree creation 0o700 unchanged.

### U5. Release surfaces, journal, codex follow-up definition

**Goal:** ship the version story and the durable records in the same PR; define the codex
follow-up issue.

**Files:** `plugins/saga/.claude-plugin/plugin.json` (0.107.0),
`plugins/fleet-core/.claude-plugin/plugin.json` (0.17.0), `.claude-plugin/marketplace.json`,
both `CHANGELOG.md`s, `tests/test_saga_plugin.py` / fleet-core drift pins,
`docs/engineering-journal/LEARNINGS.md` + `DECISIONS.md`,
`docs/sdlc-issue-drafts/2026-07-20-codex-627-refreeze-and-worktree-lease-port.md`.

**Design constraints:** CHANGELOG language mirrors codex's honest seam description and states the
new refuse mode, the guard-scope change (with the FAT32/exFAT fail-closed boundary), and the
halt-visibility fix; the new fleet-core entry explicitly corrects the 0.16.x-era
"covers every caller" claim (the historical line itself stays — R7); DECISIONS entry mirrors KTD1/KTD2 with revisit-when conditions; the codex
follow-up draft carries: re-freeze `outcome_compat.py` byte-faithful to the merged SHA
(`RUNTIME_LABEL` sole divergence), re-port `audit_store` guard, mirror the refuse-mode admission
+ arm semantics, port-manifest frozen-range update, inventory rebuild, release surfaces — plus
the COR3 unit: `outcome_worktrees` lease-authority threading (`prune`/`reap_worktree`/`advance`
parameters; ~46 references at Claude `794b4da6`, re-verified at the merged SHA). Filed via
mission-control at ship ceremony (never by /plan).

**Test expectation:** drift-guard pins updated in-commit (version bump discipline from #631);
`check_release_surface_parity.py` green. No new feature tests — release/journal unit.

## Scope Boundaries

**Out of scope (true non-goals):**

- The group-writable ancestor boundary (SEC3 advisory) — deliberately pinned in #624; no change.
- Codex-side changes of any kind — the follow-up issue owns them post-merge (KTD5).
- `discover`/`handoff`/`attach` semantics; the `outcome_decompose.prune` lease-authority consumer
  at `outcome.py:2571`; acceptance-harness work (#605, closed).
- The legacy-intent reducer-visibility asymmetry beyond what U2's paired halt record fixes (a
  full legacy-`phase: intent` reducer lane is #628-adjacent redesign — if review wants it, it is
  a new issue, not scope creep here).

**Deferred to follow-up work:**

- Codex re-freeze + COR3 worktree-lease-layer port (the U5-defined issue).
- Any cross-clone settlement-scope *mechanism* (shared ledger or fleet-doctor cross-clone probe):
  R7 documents the boundary; building coordination across clones is future work.

## Risk analysis

- **Broker semantics blast radius**: `acquire_agent` has 11+ consumer suites. Mitigation: the
  default mode is byte-for-byte today's behavior; only one production caller opts in; the
  refuse-mode tests assert zero registry mutation on refusal.
- **Guard-scope regressions on developer machines**: the universal walk newly inspects
  components outside home (CI runners, `/private/var/folders` tmp trees). Mitigation: sticky
  exemption covers system temp; the full battery runs the real suites on macOS + CI Linux before
  merge; stock-root pin test.
- **Byte-freeze window**: between this merge and the codex follow-up, a real cross-runtime
  acceptance run halts at `port-digest` by design. Mitigation: KTD5 documents it; the follow-up
  is filed at close; no acceptance run is scheduled in the window.
- **Reducer interplay** (#631 lesson): U2/U3 touch the same reduction seam that bit twice.
  Mitigation: injected-callable truth sets treated as contract; end-to-end pins from `advance()`
  through fresh-read report, not synthetic fixtures.

## Verification

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
grep -rn 'covers every caller' plugins/ --include='*.py'   # must return nothing (R7; historical fleet-core CHANGELOG line exempt)
```

Acceptance criteria from #627 apply verbatim, with the grounding corrections above controlling
where the issue's line anchors or mechanism descriptions have drifted.
