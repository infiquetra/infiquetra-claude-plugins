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

## Next step

Ceremony round 2 (`wf_fcdc177d-727`) at HEAD `148ecb50` — same approved vehicle plus
per-finding remediation verdicts; then `/code-review` + `/qa` gates and the ship ceremony.
