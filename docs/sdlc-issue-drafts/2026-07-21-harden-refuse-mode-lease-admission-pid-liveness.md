---
title: Harden refuse-mode lease admission: pid-liveness at admission + LeaseConflictError cause-branching
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# Harden refuse-mode lease admission: pid-liveness at admission + LeaseConflictError cause-branching

### Objective

Discharge the two validated P3 hardening advisories from `infiquetra-claude-plugins#627`'s CLEAN
code review (envelope at `docs/evidence/issue-627/artifacts/`): close the crash-orphan
self-refusal window in refuse-mode lease admission, and stop the reconcile loop from treating
permanent dispatcher faults as indefinitely retriable.

### Intent

`#627` (merged as `8882bdc2`, saga 0.107.0 + fleet-core 0.17.0) shipped opt-in refuse-mode lease
admission and a `DispatcherError` halt-and-continue arm in the reconcile loop. Both landed with
deliberate, operator-accepted tradeoffs; this issue is the follow-up hardening the review's
Stage-B validators anchored:

1. **Crash-orphan self-refusal window.** Refuse-mode admission
   (`LeaseBroker.acquire_agent`, `plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2173`)
   has no same-owner or liveness exemption. `owner_id` is deterministic per
   `(outcome_id, subplot_id)`, so after a SIGKILL skips the finally-release, the orphaned lease
   (`DEFAULT_TTL_SECONDS = 300`) refuses the same leaf's re-dispatch every tick until TTL expiry —
   a bounded but real recovery-latency regression vs the prior supersede-and-proceed behavior.
   The validator confirmed the broker already has pid-liveness state (`_owner_state`) but wires it
   only into `sweep()`, never the admission path. Hardening: consult pid-liveness at the refuse
   gate (dead holder → admit instead of refuse), or alternatively shorten the dispatch-lease TTL;
   the pid-liveness route is preferred because it removes the window rather than shrinking it.

2. **`LeaseConflictError` cause-branching in the reconcile arm.** `make_dispatcher` normalizes
   ALL admission exceptions into `DispatcherError`
   (`plugins/saga/scripts/outcome_dispatcher.py:283-284`), including permanent faults
   (protocol-version skew, fleet-core resolution failure). The `except DispatcherError` arm in
   `_reconcile_once` (`plugins/saga/scripts/outcome.py:1589`) leaves the subplot
   `settled=False/state=ready`, so a permanent misconfiguration re-enters the frontier every tick
   with no backoff or attempt cap — a visible-but-indefinite halt-and-retry loop where the
   pre-#627 behavior aborted loudly. Hardening: branch on `LeaseConflictError` (genuinely
   transient — keep halt-and-continue) vs other `DispatcherError` causes (escalate: abort the
   tick, or cap attempts with backoff), preserving the reducer-visible halt record shape.

Both fixes are Claude-side (`lease_broker.py` / `outcome.py`), which is why they are filed here
and not folded into `infiquetra-codex-plugins#45` (the codex re-freeze of the #627 seam).

### Out-of-scope / non-goals

- Redesigning #627's settled decisions (KTD1 opt-in refuse default, KTD3 halt-record shape and
  `SILENT_NOOP` settlement, KTD4 guard exemption predicate) — this hardens within them.
- The pre-existing guard-walk TOCTOU advisory (finding 3 of the same review,
  `audit_store.py:194`) — an fd-based walk is a separate future item, not this issue.
- Supersede-mode behavior and every non-dispatcher lease consumer — refuse mode is opt-in and
  only `make_dispatcher` opts in; nothing else changes.
- Cross-clone settlement coordination (#627 R7 boundary).
- Codex-side mirroring — sequencing note below.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — wire `_owner_state` pid-liveness
  into refuse-mode admission (or adjust dispatch-lease TTL if that route is chosen at plan time).
- `plugins/saga/scripts/outcome.py` — branch the `except DispatcherError` arm on
  `LeaseConflictError` vs other causes.
- `plugins/saga/scripts/outcome_dispatcher.py` — only if cause preservation through the
  `DispatcherError` normalization needs an explicit `__cause__`/attribute contract.
- `tests/test_lease_broker.py`, `tests/test_outcome_command.py` (or the suites that pinned #627's
  refuse-mode and reconcile-arm scenarios) — new crash-then-retry and permanent-fault scenarios.
- Release surfaces in the same PR: `plugins/fleet-core/.claude-plugin/plugin.json`,
  `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, both
  `CHANGELOG.md`s, and any version drift-guard test pins.
- `docs/engineering-journal/DECISIONS.md` — record the chosen liveness-at-admission and
  escalation-policy calls.

### Tests to add or update

- Crash-orphan recovery: acquire in refuse mode, simulate holder death (dead pid in
  `_owner_state`), re-dispatch same `(outcome_id, subplot_id)` — admission succeeds without
  waiting out the TTL; a live holder still refuses.
- Same-owner-live conflict still refuses (no blanket same-owner bypass that would defeat
  cross-runtime exclusion).
- `LeaseConflictError` in the reconcile loop: halt record written, lease released, attempt
  settled `SILENT_NOOP`, tick continues (existing #627 pin stays green).
- Non-conflict `DispatcherError` (e.g. protocol skew): escalation path taken — loud abort or
  capped retries per the plan's decision — instead of indefinite per-tick retry.
- Halt-record shape unchanged for the transient branch (reducer/report visibility pins from #627
  stay green).

### Context library links

- source_context: docs/work-sessions/2026-07-20-issue-627-lease-seam-guard-scope.md

### Sequencing note (codex seam)

This issue changes `lease_broker.py` / `outcome.py`, which are NOT part of the byte-frozen
`outcome_compat` seam, so it does not by itself force a codex re-freeze. But
`infiquetra-codex-plugins#45` mirrors the refuse-mode admission and `DispatcherError` arm
semantics codex-natively — if this issue lands before codex#45 is planned, codex#45 should mirror
the hardened semantics (one port instead of two); if after, a small codex follow-up inherits it.
Coordinate at codex#45 plan time; upstream-first discipline (#627 KTD5) applies either way.

### Acceptance criteria

- [ ] A crash-orphaned refuse-mode lease no longer blocks re-dispatch for the full TTL: the
      crash-then-retry scenario test passes with admission granted on a dead holder. Check:
      `uv run pytest -q -k "refuse"` green including the new scenarios.
- [ ] Live-holder conflicts still refuse (cross-runtime exclusion preserved). Check: existing
      #627 refuse-mode pins plus the new live-holder test pass unchanged.
- [ ] The reconcile loop escalates non-conflict `DispatcherError` causes instead of retrying
      indefinitely, while `LeaseConflictError` keeps halt-and-continue. Check: new
      permanent-fault escalation test + existing
      `test_advance_records_lease_refusal_as_halt_and_continues` both green.
- [ ] Release surfaces move in the same PR. Check:
      `python3 scripts/check_release_surface_parity.py` reports all plugins in parity.
- [ ] Full battery green. Check: `uv run pytest -q` 0 failures; `uv run ruff check .` and
      `uv run ruff format --check .` clean; `uv run mypy plugins/ scripts/ tests/
      --ignore-missing-imports` exit 0; `uv run bandit -r plugins/` no new non-LOW findings.

### Verification

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/check_release_surface_parity.py
```

### Handoff maturity

requirements-ready

### Suggested next action

Use `saga:plan` on this issue — the one genuine design decision is the finding-1 route
(pid-liveness at admission vs shorter dispatch TTL) and the finding-2 escalation policy
(loud abort vs capped backoff); both advisories carry validator-confirmed anchors, so the plan
should be small.

### Source context

- Source: docs/work-sessions/2026-07-20-issue-627-lease-seam-guard-scope.md
- Source type: work-session
- Source title: Work session — issue #627 lease-seam and guard-scope defects

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/637
- Number: 637
- Created at: 2026-07-21T22:52:42.746011+00:00

