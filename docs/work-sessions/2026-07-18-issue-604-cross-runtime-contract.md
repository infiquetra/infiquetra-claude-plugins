# Work session — issue #604 Claude-side cross-runtime Outcome contract (2026-07-18)

- **Saga:** `issue-604` (lifecycle work) · branch `work/604-cross-runtime-outcome-contract`
  from `origin/main` `30bde209` · worktree `.claude/worktrees/issue-604-cross-runtime`
- **Plan:** `docs/plans/2026-07-15-claude-cross-runtime-outcome-contract-plan.md` (refreshed
  2026-07-18, delta review READY 0 findings, codex second opinion clean; ceremony anchor
  `214431cf…` approved by Jeff in-session)
- **Outcome leaf:** `claude-cross-runtime` of `lease-safe-runtime-continuity`, dispatched
  attempt 1 (store ledger intent+commit, backend manual, leaf saga id
  `leaf-lease-safe-runtime-continuity-claude-cross-runtime`)

## Built (by unit)

- **U1** (`0d028a3c`) — `plugins/saga/scripts/outcome_compat.py`: canonical repository
  identity, committed-spec discovery via git blobs (ref-ambiguity fatal), the four closed
  `outcome.*.v1` schemas, narrow protocol negotiation, bounded fixed-argv git adapter,
  redacted halt receipts. 52 oracles on real temp git repos.
- **U2** (`b1ce30e4`) — `build_canonical_status`: committed spec + GitHub only, zero cache
  materialization, unknown-reduces-never-fabricates, byte-identical across clones.
- **U3** (`2b733d9f`) — protected same-clone handoff: offer written inside the #356 broker's
  settlement-close protected write (#355 linearization); write-once accept-intent binds one
  receiver; successor via close-receipt CAS; accept-commit; crash-gap idempotent resume; 17
  oracles against the REAL fleet broker.
- **U4** (`<u4-commit>`) — `/outcome` CLI verbs `discover` / `handoff` / `attach`
  (read-only default; `--advance` = ONE one-subplot tick behind the validated handoff with
  revision+frontier re-checks; `--attend` = native resume after validation); halts exit 3.
  Race + replay oracles: one successor, zero double dispatch.
- **U5** (this commit) — legacy `outcome-bundle/1` retired (export = discover alias with
  stderr warning; import refuses with migration receipt, zero writes); golden fixtures at
  `tests/fixtures/outcome-cross-runtime/v1/`; `references/outcome-cross-runtime.md`; outcome
  SKILL.md verb surface; saga 0.102.0 → 0.103.0 across plugin.json / marketplace / changelog /
  version guards; LEARNINGS `{#module-identity-cross-plugin-604}`.

## Key decisions in execution

- The offer record IS the settlement-close protected write's payload — offering and
  relinquishing are one linearized, receipt-bearing broker transition (KTD4 consumption, no
  sibling authority). The close-receipt sha becomes the successor CAS the receiver must match.
- Broker-owned classes (exceptions, `FencingToken`) resolve from the broker INSTANCE's own
  module (`_broker_module`), never a parallel shim load — the sub-358 dual-load precedent,
  now recorded as `{#module-identity-cross-plugin-604}`.
- The broker's settlement producer vocabulary is closed (`{"agy", "saga", "team-execution"}`);
  this surface produces as `saga`.
- `attached_advance` re-checks committed revision AND ready frontier AFTER authority
  acquisition — a moved spec or frontier HALTs loudly (`handoff-frontier-changed`) instead of
  silently broadening or shrinking the one-subplot authorization.

## Checks run

`uv run pytest tests/test_outcome_cross_runtime_contract.py` (94 passed), plus focused
regression on `test_outcome_command` (40, incl. the rewritten R10 rejection oracle),
`test_outcome_store`, `test_outcome_dispatcher`, `test_saga_plugin` (45, version guards at
0.103.0). `ruff check` + `ruff format --check`, `mypy` clean on the changed modules; bandit
carries only the house-baseline B404 subprocess-import Low. Full-suite gate: run at the U5
boundary (see next step).

## Next step

Full repository gate (pytest / ruff / mypy / bandit / release parity / marketplace sync / diff
guard), then the six-lens cc-workflow ceremony under approved anchor `214431cf…`.
