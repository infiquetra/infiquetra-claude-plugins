# Work session — issue #358 non-skippable teardown and reclamation

- **Branch:** `work/358-non-skippable-teardown` from `origin/main` `77f56894` (merged
  post-#357 base), worktree `.claude/worktrees/issue-358-teardown`
- **Plan:** `docs/plans/2026-07-15-issue-358-non-skippable-teardown-reclamation-plan.md`
- **Ceremony:** operator-approved cc-workflow candidate, anchor
  `04cf1694e1d1cc94c8e414fcfdfaec129a2b080d275485fc4283f51057e77c51` (approval recorded in
  `docs/reviews/2026-07-18-issue-358-plan-refresh-delta-doc-review.md`)
- **Saga thread:** `issue-358` (outcome leaf `sub-358` of `lease-safe-runtime-continuity`,
  dispatched attempt 1, leaf saga id `leaf-lease-safe-runtime-continuity-sub-358`)

## Built (by unit)

- **U1** `638b770a` — fleet-core monotonic `close_owner_admission` under the authority
  lock (all seven admission paths refuse a closed owner; leases stay inspectable and
  releasable; no reopen; generation from the one fencing sequence, bounded map with
  documented lowest-generation eviction). Saga `run_fact.v1` gains the closed
  `kind=teardown` event family with transition validation under the ledger's exclusive
  lock, stable action keys, and the derived `team_teardown.v1` projection.
- **U2** `2f40a94f` — the idempotent `reclaim_all` B8 driver (close → verified snapshot →
  crash-orphan reconcile → typed actions → re-reconcile → still-closed generation recheck
  → zero-open receipt), `request` (intent-only, the SessionEnd shape), `recover` (budgeted
  expired-only). team-execution B0 opens the bounded run, B7 is draft-only, B8 is the
  terminal state machine; `lease_protocol.py` resolves Saga's canonical CLI with a closed
  verb surface; contract in `references/teardown-reclamation.md`.
- **U3** `cf2dd81b` — typed adapters: terminal-receipt-gated resident release,
  exact-identity process stop (PID/start/boot/ownership, TERM-first, KILL only under the
  lease-recorded `term-then-kill` class, absence proof without signaling), canonical #356
  worktree sweep, identity-checked lease release; `register_subprocess` records identity +
  policy on the lease at spawn.
- **U4** `39ab2ca0` — `authorize_resident_stop` (only #357 `confirmed-stalled` with
  `team-reping-confirmed` authority, or explicit segment shed, against current ownership);
  `team_teardown_hook.py` SessionEnd (5 s, request-only) + SessionStart `startup|resume`
  (15 s, `recover --expired-only --max-actions 4`); kill-mid-run acceptance test.
- **U5** `3cd0e527` — hermetic CI leak invariant (temp repo, planted unledgered worktree
  red → production register/reclaim green; missing-path, out-of-scope, live-owner,
  red-then-green retry, no-write dry-run census) + source-aware conformance (unregistered
  spawn and B8-bypassing completion fail) + `references/teardown-consumer-sites.md`.
- **U6** `737ccaf8` — fleet-core 0.15.0 / saga 0.102.0 / team-execution 2.21.0 across
  manifests, marketplace, changelogs, minimum-fleet-core pin (now 0.15.0), and every
  version drift guard.
- Pre-work `653832d8` — the pre-push gate's pytest step outgrew its hard 300-second hook
  timeout (suite measured 303.7 s green); the gate now runs `-q --no-cov` (224 s), CI
  keeps full coverage. LEARNINGS `{#pre-push-gate-timeout-358}`.

## Key decisions

- The run's broker `owner_id` IS the `team_run_id` — the owned-resource snapshot is
  exactly the broker's lease set for that owner (no second registry, R1).
- Deterministic intent identity (`sha256(team_run_id|terminal_reason)`) makes "B8 exactly
  once logically" a mechanical ledger dedup rather than prose (R3).
- Subprocess stop policy rides the lease's `agent_type`
  (`owned-subprocess:term-only|term-then-kill`) — recorded at spawn in the trusted store,
  never taken from prose at action time (R8).
- Adapter default is conservative retain: an unwired slot can never destroy anything; the
  run stays a truthful blocked terminal (KTD6).
- Value objects handed back to the broker are constructed from the broker's own defining
  module (dual-load dataclass equality; LEARNINGS `{#dual-load-token-equality-358}`).

## Checks run

Focused suites green per unit; full gate at `737ccaf8`: repo-wide pytest (in flight at
writeup time — see the tick's gate verdict), `ruff check` + `ruff format --check` (431
files), `mypy plugins/ scripts/ tests/` zero errors, bandit `-ll` clean on changed files,
`validate_plugins`, marketplace validator + `sync_marketplace --check`,
`check_release_surface_parity`, `release_surface_diff_guard` (all three plugins bumped),
`git diff --check`. One pre-existing drift guard (`test_no_pulse_owned_status_field`)
updated for the legitimate `teardown` fact kind.

## Ceremony round 1 (`wf_95b82683-d93`) — 14 findings, remediated in `148ecb50`

Two real P1 defects, one P2, seven testing gaps, four advisories:

- **P1 (devils F1)** — broker admission-record eviction + re-close mints a fresh
  `close_generation`; the teardown-intent re-append conflicted (the generation was replay
  identity even though `intent_id` deliberately excludes it), permanently poisoning an
  incomplete run. Fixed by excluding `close_generation` from intent replay identity; the
  driver fences on its pass-local generation. LEARNINGS `{#intent-replay-generation-358}`.
- **P1 (validate-concurrency)** — two concurrent `reclaim_all` passes both invoked the
  adapter for one action key: ledger dedup records once but does not serialize side
  effects, and attempt-append freshness cannot distinguish a live racer from a crashed
  predecessor (whose dangling attempt must stay re-actable). Fixed structurally with the
  per-run exclusive flock `_reclaim_guard` (completion short-circuit re-checked under the
  lock; a dead holder's flock releases with its process).
- **P2 (devils F2)** — one run's `TeardownError` aborted the whole `recover()` pass,
  head-of-line blocking every newer run. Fixed with per-run try/except that appends a
  `recovery-run-error:<type>` observation and continues.
- **Testing (TST-1..7)** — negative tests added: generation-loss completion refusal,
  alive-after-kill, eviction-gate lease-absent, every process-stop retain/absent reason,
  head-None adapter branches, driver/builder guards, and the conformance checker now
  audits the real enumerated consumer sources, not only its fixtures.
- **Advisory (SEC-1/SEC-2/ARCH-1/event-flow)** — the "no reopen" fence claim was
  overstated: the bounded map's eviction lapses admission open until re-close. Docs now
  state the retention-scoped guarantee (driver re-closes at pass start, snapshots after
  the close, rechecks the pass-local generation — eviction costs a retry, never a false
  receipt), proven by the unfenced-window capture test; the inherent os.kill PID-reuse
  window is documented.

Full suite after remediation: 4986 passed / 0 failed / 1 skipped; ruff, format, mypy,
bandit clean.

## Ceremony round 2 (`wf_fcdc177d-727`) — 9 findings, remediated in `0271ecdf`

Security and event-flow returned **clean**; all 22 round-1 remediation verdicts came back
fixed-adequately except CONC-1 (a sharp catch: my recovery isolation only caught
`TeardownError`, so a broker-raised `RegistryCorruptError` for one corrupt owner record
still wedged the pass — exactly the head-of-line bug the fix claimed to close, via a
different exception family). Round-2 fixes:

- **CONC-1 (P2)** — recover() isolation widened to every exception family with the
  `recovery-run-error:<type>` observation; the regression test patches the bound method so
  the real broker class (and the dual-load token module resolution) stays intact.
- **TST-FENCE-GAP-1 (P2)** — `acquire_successor` and `prepare_batch_call` closed-owner
  refusals: all seven fence sites now carry negative tests.
- **TST-BUDGET-GAP-2 (P2) + DA-R2-1 (P3)** — the recovery budget now bounds real adapter
  invocations only (`recovered-after-crash` reconciles are unbudgeted bookkeeping);
  multi-run exhaustion, honest skip observations, and the crash-reconcile exemption are
  pinned by `TestRecoveryBudget`.
- **ARCH-R2-1/ARCH-R2-2/CONC-2 (P3)** — `_reclaim_guard` provisions the store directory
  with a typed failure surface, and the per-run lock sidecar unlinks under the lock once
  the receipt is final (post-completion passes are read-only short-circuits).
- **DA-R2-2 (P3)** — the append-time validation boundary is documented (ledger-internal;
  the broker zero-open gate is the driver's) and the bypass-visibility test proves a
  driver-bypassing receipt stays visibly inconsistent (`open_count` derives live).

Full suite after remediation: 4997 passed / 0 failed / 1 skipped; ruff, format, mypy,
bandit clean.

## Ceremony round 3 (`wf_055dc7a5-ef5`) — 4 findings, remediated

**Devils-advocate returned clean (converged).** All round-2 remediation verdicts came
back fixed-adequately except CONC-1 — the concurrency validator empirically proved the
round-2 isolation was still not total: the except-handler's own bookkeeping (budget
recount + observation append) was unguarded, so a second ledger/broker failure while
recording run A's evidence escaped `recover()` and starved every later run
(CONC-1-R3-1, P2). Round-3 fixes:

- **CONC-1-R3-1 (P2)** — evidence recording is now best-effort by design:
  `_observe_recovery` degrades an observation-append failure to the run's in-memory
  pass entry (`evidence_error`); the recount failure charges zero budget (a liveness
  ceiling, not a safety bound — the reclaim call was already capped, and every action
  re-enters `reclaim_all`'s own guards); every skip branch is equally guarded. Pinned
  by `TestRecoveryEvidenceBestEffort` (secondary count failure, observation refusal).
  LEARNINGS `{#recovery-isolation-total-358}`.
- **ARCH-R3-1 / TST-R3-1 (P3, one root)** — the guard's OSError→TeardownError branch
  had zero real coverage (the test named for it asserted the unrelated unknown-run
  path). Added `test_guard_provisioning_failure_surfaces_typed_refusal` (regular file
  blocking the store dir → typed "cannot provision the reclaim guard") and renamed the
  fresh-repo test to what it actually proves.
- **DA-R2-1-R3-1 (P3)** — the budget exemption was a bare string an adapter could
  spoof. `recovered-after-crash` is now a driver-reserved reason code:
  `ActionOutcome.validated()` refuses it from the adapter surface (same loud-failure
  precedent as the bogus-disposition refusal), and the write site, budget filter, and
  refusal all share one constant.

Full suite after remediation: 5001 passed / 0 failed / 1 skipped; ruff, format, mypy,
bandit clean.

## Ceremony round 4 (`wf_bc90e4d4-b00`) — HALTED at the three-cycle tripwire

Round 4 (architecture, testing, concurrency at HEAD `7dd5789c`) judged the guard-test
and reserved-reason-code remediations **fixed-adequately**, but the concurrency
validator judged CONC-1-R3-1's remediation **inadequate** — the third consecutive
inadequate verdict on the recovery-isolation seam:

- **ARCH-R4-1 / CONC-R4-1 (P2, one root, both lenses reproduced it empirically)** —
  the round-3 restructure moved the baseline count inside the try. When the
  before-count fails transiently but the after-count succeeds, `taken` diffs the run's
  full historical result count against a placeholder `before = 0`: phantom actions are
  charged against the cross-run budget (re-creating head-of-line starvation), and the
  durable observation fact records `actions_taken` for a pass where `reclaim_all`
  never ran, with no `evidence_error` marker. Pre-restructure (`0271ecdf`) the
  before-count was outside the try and could not degrade to a false baseline.
  Converged suggested fix from both lenses: an unmeasured baseline is *uncountable* —
  charge zero and set `evidence_error`, exactly like the after-count-failure branch;
  never diff against a fabricated baseline.
- **TST-FRESH-1 (P3)** — the reclaim-succeeds + after-count-fails corner (zero charge,
  `evidence_error`, later run keeps the uncharged budget) has no direct test.
- **TST-FRESH-2 (P3)** — the skip-branch `evidence_error` glue (live-owner /
  budget-exhausted with a refused observation append) is unexercised.

**Tripwire.** The approved operating contract: "Three unsuccessful remediation cycles
halt and page the operator." Lineage on this seam: r1 fix `148ecb50` → judged
inadequate by r2 (exception family); r2 fix `0271ecdf` → judged inadequate by r3
(handler bookkeeping); r3 fix `7dd5789c` → judged inadequate by r4 (phantom-charge
regression). Autonomous remediation is halted; the operator is paged.

**Converged and stable:** devils-advocate (r3), security + event-flow (r2) clean; all
seven broker fence sites tested; intent replay, reclaim mutex, guard lifecycle,
reserved reason codes, and the fence-site tests all judged adequate. The only open
thread is `recover()`'s budget/evidence bookkeeping.

## Next step

Operator decision: authorize remediation cycle 4 with the lens-converged patch
(baseline-measured flag → uncountable charges zero + `evidence_error`; plus the two
regression tests) and a fresh affected-lens re-run, or redirect (manual take-over or a
structural redesign of `recover()`'s bookkeeping). Branch is unmerged; nothing ships
while halted.
