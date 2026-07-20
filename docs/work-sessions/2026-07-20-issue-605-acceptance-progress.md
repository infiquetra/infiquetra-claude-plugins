# Work session — #605 cross-runtime acceptance harness (U1-U5)

**Status**: U1 + U2 COMPLETE and committed; U3/U4/U5 next. Branch
`work/605-cross-runtime-acceptance` (worktree `.claude/worktrees/work-605-acceptance`), base
`origin/main` = `794b4da6`. Plan authority:
`docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md` on the outcome branch
(anchor `4b21df73…` over `## Workflow Structure` → `## Completion gate`).

## Pins (both re-verified via fresh fetch, U1 gate satisfied)

- Claude `794b4da6` — saga `0.105.0`, fleet-core `0.16.0`. Clean pinned checkout for harness
  input: detached worktree `.claude/worktrees/xr-pin-claude` (primary checkout is dirty with
  sdlc-issue-draft files; R1 refuses it, correctly).
- Codex `f3e1af75` — saga `0.78.0+codex.20260720120109`, fleet-core
  `0.10.0+codex.20260720120109`. Primary checkout `../infiquetra-codex-plugins` is clean AT the
  pin (fast-forwarded 2026-07-20).

## Done

- **U1** (`eea7b286` + style fix): RuntimePin/require_clean_pinned, contract_digests
  (RUNTIME_LABEL-normalized byte-identity), install_isolated (staged package + hermetic HOME +
  readback identity), closed `cross-runtime-acceptance.v1` schema, scrub_check/assert_privacy,
  atomic_write_json. 21 hermetic tests.
- **U2** (`6b8c4c9d`): Topology (bare origin → creator clone → clone A/B), fake `gh` shim
  (PATH-injected, fixtures keyed `pr:<n>`/`issue:<n>`, serves `--json` field subsets),
  `u2-discovery` unit — **both directions PASS against the real pinned runtimes**
  (envelope parity mod producer, byte-identical canonical projections across runtimes AND
  clones, completed=[done-leaf] frontier=[ready-leaf] unknown=[untracked-leaf], clone B
  state-free + `attach --advance` refused rc!=0 with zero writes).

## Hard-won mechanics (do not rediscover)

- Isolated installs need `FLEET_COMMONS_ROOT=<install_root>/plugins/fleet-core` in the child
  env — outcome.py imports fleet_commons_shim at module load; without the override the CLI dies
  at import (`install-readback` halt). Allowlisted in ENV_NAME_ALLOWLIST.
- `outcome commit --push` runs a bare `git push` — the seed branch must be pushed with `-u`
  first or it reports `pushed: false` silently and discovery halts `discovery-spec-absent`.
- Node kinds are closed: `("code", "non-code")`. Completion: code+PR merged→complete (fixture
  `{"state": "MERGED", "mergedAt": ...}`), code+PR open→open, non-code without issue→unknown
  (excluded from frontier).
- Discovery validates remote shape: clone A/B get
  `git remote set-url origin git@github.com:infiquetra/xr-fixture-target.git` AFTER cloning
  from the local bare path (identity `github.com/infiquetra/xr-fixture-target`).
- Origin bare repo needs `symbolic-ref HEAD refs/heads/outcome/<id>` so clones check out the
  spec branch at HEAD (candidate refs must agree byte-wise).
- Halt details flow through `_bounded()` which path-redacts (`<home>`, `<path>`) — REQUIRED,
  assert_privacy refuses the bundle otherwise.
- `start()` signature identical in both runtimes:
  `start(repo_root, outcome_id, objective, nodes)` — driven via `InstalledRuntime.python()`
  against the INSTALLED package. All other verbs via `InstalledRuntime.outcome()` (real CLI).
- Smoke invocation (also the final run shape):

```bash
uv run python tools/run_cross_runtime_outcome_acceptance.py \
  --claude-repo .claude/worktrees/xr-pin-claude --claude-sha 794b4da6971a5df3ba57ab7d15cb3deca2ec0ce3 \
  --claude-saga-version 0.105.0 --claude-fleet-core-version 0.16.0 \
  --codex-repo ../infiquetra-codex-plugins --codex-sha f3e1af75d06ac4c64a499f05e99c54903d978f35 \
  --codex-saga-version 0.78.0+codex.20260720120109 --codex-fleet-core-version 0.10.0+codex.20260720120109 \
  --units all --output docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json
```

## Next: U3 — protected handoff + negative matrix (R4)

**Positive path PROBED WORKING end to end (2026-07-20, scratch xr-probe)**: Claude issued on a
consumer clone (no prior store state needed — handoff works from the committed spec), codex
accepted the same reference over the shared broker root and ran the attached advance
(`successor_lease_id` minted, tick result `states: {a: intent-created}`).

- Issuer CLI: `handoff <id> <sid> --operation advance-one --dispatch-id
  outcome:<id>:frontier:<sid> --session-id S --policy-sha256 <64hex> --session-limit N
  --aggregate-limit N --broker-root B` → prints `outcome.handoff-reference.v1`
  (fields: digest, handoff_id, operation, protocol{...capabilities}, schema, subplot_id).
  `advance-one` REQUIRES `--dispatch-id` (halt `schema-field-type` without it).
- Receiver CLI: `attach <id> --advance --handoff-id <handoff_id> --subplot <sid>
  <same admission flags> --broker-root B` → JSON `{handoff_id, subplot_id,
  successor_lease_id, advance: {...advance tick result...}}`, rc 0. The target leaf must be in
  the candidate frontier (gh fixture must serve its PR as OPEN — a missing fixture reads
  unknown and the leaf is excluded). TTL cap 300 s, skew cap 30 s
  (`HANDOFF_MAX_TTL_SECONDS`, `HANDOFF_MAX_CLOCK_SKEW_SECONDS` in outcome_compat).
- Negatives (each must reject BEFORE any mutable effect — capture pre/post store hashes):
  copied reference on clone B; wrong repository/revision/operation/subplot/receiver/issuer/
  fence; broad scope; replay (second accept); byte tamper; missing protected record; expiry
  >300 s; future skew >30 s. Effect spies: hash the handoffs dir + broker registry + ledger
  before/after each refusal.
- U4 (R5/R6): two OS processes + deterministic file-based barrier released just before broker
  admission; write-once fake backend (the dispatcher seam is ACTIVE codex-side since PA-2 —
  `DispatcherError` mid-tick records a reducer-visible halt, see PA-2 review artifact);
  orderings Claude-first/Codex-first/simultaneous/loser-retry/winner-crash-before-after/
  lease-expiry/already-settled; assert exactly one backend effect + codex-native
  `outcome.dispatch.v2` intent + `ack_kind=launched` chain when codex launches (R6).
- U5 (R9/R10): teardown twice (idempotent), fleet doctor
  (`plugins/saga/scripts/fleet_doctor.py --repo-root <cloneA> --lease-store … --audit-store …
  --format json`, strict read-only) must report zero open positions; final bundle + README +
  outcome report update; then full battery + programmatic code review + saga:qa.

## Ceremony + gates after U5

Anchored cc-workflow ceremony (4 opus reviewer lenses + 3 sonnet validators, bounded pool 3,
all saga:readonly-verifier + worktree isolation, halt-if-Workflow-unavailable, three-cycle
tripwire) per the plan's `## Workflow Structure`; then programmatic code-review (CLEAN gate),
then `saga:qa` (no waiver), then PR (session URL footer, Closes #605) and merge under the
standing 2026-07-18 pre-approval. Merge closes #605; #579 close + board reconcile + harvest
follow (tasks #50/#51).
