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
- **U4** (`51596bf3`) — `/outcome` CLI verbs `discover` / `handoff` / `attach`
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

`uv run pytest tests/test_outcome_cross_runtime_contract.py` (94 passed at U5, 102 after the
ceremony remediations; 142 across the focused pair with `test_outcome_command`), plus focused
regression on `test_outcome_command` (40, incl. the rewritten R10 rejection oracle), `test_outcome_store`, `test_outcome_dispatcher`,
`test_saga_plugin` (45, version guards at 0.103.0). `ruff check` + `ruff format --check`,
`mypy` clean on the changed modules; bandit carries only the house-baseline B404
subprocess-import Low.

Gate-fix commit `05370bf5` before the full gate: the sub-358 release guard in
`test_liveness_consumer_conformance.py` pinned current versions (broke on 0.103.0) — rewritten
as changelog-history assertions plus a semver floor with live plugin/marketplace coherence;
two `cast()`s for mypy on importlib-loaded module returns. Full repository gate green at
`05370bf5` (pytest 5102/0/1, ruff check+format, mypy, bandit at the 4-finding pre-existing
baseline, release parity, marketplace sync, diff guard, whitespace).

## Six-lens cc-workflow ceremony (anchor `214431cf…`, approved 2026-07-18)

Reviewers devils-advocate / security / architecture / testing at opus+high; validators
concurrency / event-flow at sonnet+medium; every lens `saga:readonly-verifier` + worktree
isolation; bounded pool 3. Converged in three rounds, two remediation cycles (tripwire is
three).

- **Round 1** `wf_93a4736f-ba0` at `05370bf5` — 6/6 lenses. P0=0 P1=0 **P2=2 P3=5**; security
  (90), concurrency (88), event-flow (88) clean; devils-advocate 90, architecture 91,
  testing 82. Findings: settled-attempt binding inert under empty `--dispatch-id`
  (devils-advocate), attach `--advance`/`--attend` non-exclusive (architecture), five halt
  codes without negative oracles (testing: schema-malformed-json, handoff-source-not-closed,
  git-failed, git-output-cap, discovery-node-cap).
- **Remediation 1** `33d93550` — advance-one offers now require a non-empty dispatch id at the
  `offer_handoff` module boundary (reusing the closed `schema-field-type` code); attach modes
  argparse-mutually-exclusive; five new halt oracles → 39/39 halt-code coverage; contract doc
  updated. Focused pair (contract + `test_outcome_command`) 141 passed; full gate green at
  `33d93550` (pytest 5109/0/1, all steps).
- **Round 2** `wf_3ca79e79-90f` at `33d93550` — affected lenses (devils-advocate 95,
  architecture 95, testing 88) fresh. All seven r1 fixes adjudicated **fixed-adequately** at
  the byte level; testing recounted halt coverage 39/39 by AST-parsing every raise site. One
  new **P3**: the dispatch-id guard's negative scope (attend may omit) had no oracle.
- **Remediation 2** `4ace6d80` — `test_attend_offer_permits_empty_dispatch_id` drives the full
  attend offer success path with an empty dispatch id (focused pair 142 passed).
- **Round 3** `wf_82f87b45-b16` at `4ace6d80` — testing lens fresh: **clean** (92), fix
  fixed-adequately with a mutation argument (an over-broadened guard would halt before
  identity resolution and turn the oracle red); no new raise sites, 39/39 preserved.

## Next step

Full repository gate re-verified at `4ace6d80`, then programmatic `/code-review` (capture
`REVIEWED_SHA`), `/qa`, PR, merge under Jeff's standing outcome approval, leaf harvest with
`leaf_saga_id` backfill, board reconcile.
