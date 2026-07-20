# Work session — #605 cross-runtime acceptance harness (U1-U5)

**Status**: U1-U5 ALL COMPLETE. Final bundle at
`docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json`:
**overall fail — 12/14 pass**, both failures are the claude v2-blindness production defect,
filed upstream as **#628** (Operations board, risk high, requirements-ready). Full battery
green (5259 passed, ruff+format+mypy clean, release-surface parity). Next: ceremony, then the
merge question escalates via the AFK halt protocol (a red acceptance cannot close #605). Branch
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

## U3 — DONE (`u3-handoff` unit; both directions + 14-case negative matrix)

Committed in the harness: positive handoff each direction (issuer mints on clone A, the OTHER
runtime accepts, successor lease + offer/intent/commit records asserted, advance must move
ready-leaf), then 14 adversarial acceptances each direction, every one refused with the exact
expected receipt code and byte-identical effect-spy state (`_tree_state` maps over clone A/B
`saga-outcomes` stores + broker root). Smoke: all 6 scenarios (u2+u3) PASS rc 0 against the
real pins.

Case → code: copied-reference-clone-b/missing-record→`handoff-missing`;
byte-tamper→`handoff-seal-invalid`; wrong-repository/-operation/-subplot/-revision→their codes;
replay-second-receiver→`handoff-receiver-conflict`; wrong-fence (tamper-and-reseal token) +
wrong-authority (foreign broker root)→`handoff-superseded`; ttl 301→`handoff-ttl-too-long`;
broad scope `advance-all`→`schema-field-type` (offer-side, driven with broker=None);
expired/future-skew (tamper-and-reseal timestamps)→`handoff-expired`/`handoff-clock-skew`.
`wrong-fence` is the ONE post-intent refusal: the write-once accept-intent is the designed
crash-resume artifact — the spy asserts it is the only store delta.

U3 mechanics learned (do not rediscover):

- **Broker roots must be mode 0o700** — a default-umask mkdir is refused with
  `UnsafeAuthorityError` at first acquire (`_private_dir` helper).
- **`_store_dirs` was vacuous**: the real store namespace is `.git/saga-outcomes`
  (`outcome_store.STORE_NAMESPACE`), not any of the guessed names — fixed + pinned by test;
  the U2 clone-B state-free check is only now actually load-bearing.
- Clone A/B carry the canonical (unreachable) GitHub remote — pull revision bumps by path:
  `git fetch <origin_path> <branch>:refs/remotes/origin/<branch>` + `merge --ff-only` so all
  committed-spec candidate refs agree.
- `load_spec` returns an `OutcomeSpec` object — bump via `spec.bump_revision(reason=…)` +
  `save_spec`, then `commit <id> --push` from the creator clone.
- **Native-flavor asymmetry is correct (R6)**: after an accepted advance, claude reports
  ready-leaf `dispatched` (inline path) while codex reports `intent-created` (native
  outcome.dispatch.v2) — the positive assertion accepts exactly these two states.
- Smoke invocations must use ABSOLUTE `--claude-repo`/`--codex-repo` paths (the shell cwd
  resets between commands; a relative pin path halts `pin-not-a-repo`).
- CLI refusals: `CompatibilityHaltError` → receipt JSON on stdout + exit 3; broker errors →
  `{"ok": false}` on stderr + exit 1.

## U4 — DONE (`u4-race` unit; 3 pass / 2 FAIL — the failures are production truth)

Five scenarios on fresh single-leaf topologies (`race-leaf`, pr:12 OPEN, frontier approved via
`approve` on clone A — approval lives in the SHARED STORE, run it on clone A, no push):

- **race-claude-first PASS**: claude settles the legacy chain (intent+commit); codex observes
  shared settlement, dispatches nothing, invents no native ack (R6 claude-half).
- **race-codex-first FAIL (R6/R5 defect)**: the codex-native chain WORKS end to end — v2
  intent, harness-as-launched-runner writes the write-once effect + protected launch receipt
  (`saga.outcome-dispatch-launch.v1` under the hermetic home's user-state root with
  `.repo-identity.json`, all vocabulary from installed `workflow_compat.emit`) and
  `reconcile-dispatch --ack-kind launched` lands (`receipt_authority owner-user-state-v1`).
  Then claude's advance RE-DISPATCHES the natively-settled leaf → `settled_chains: 2`.
- **race-simultaneous FAIL (same root cause)**: barrier-released two-OS-process race with
  wall-clock overlap receipts; codex entered first (v2 intent), claude dispatched anyway →
  one settled legacy chain + a DANGLING un-acked codex intent.
- **race-crash-before/after-effect PASS**: injected write-once dispatcher; crash windows leave
  intent-only ledgers; recovery (0.5 s `lease_ttl`, sleep past expiry) settles exactly one
  commit; effect file written exactly once (writer identity asserted).

**U4 finding (upstream defect, claude repo)**: claude at 794b4da6 has ZERO
`outcome.dispatch.v2` vocabulary in `outcome.py`/`outcome_store.py`/`outcome_compat.py` — its
advance dedup (`_dispatch_records` = legacy commits only), in-flight derivation, AND the
handoff `_settled_lookup` (#351 run-ledger only) are all blind to codex-native intents/acks.
Codex-side is v2-aware AND legacy-aware (asymmetry: claude→codex safe, codex→claude double
dispatch). Route per plan: "Failures retain artifacts and file/reopen the owning defect
without production edits" + KTD7. The mirror of #627's codex-side findings.

U4 mechanics learned: codex CLI verb `reconcile-dispatch <id> <sid> --ack-kind launched
--dispatch-ack-ref '<user-state-path>#sha256=<hex>' --leaf-saga-id <leaf>`; receipt must sit
under `emit(USER_STATE_ROOT)<repo-name>/dispatch-receipts/` with owner-only modes and a
`.repo-identity.json` binding `repo_root_sha256`; `advance` returns `skipped_busy` when the
coordinator lease is held; claude inline leaf saga id convention `leaf-<oid>-<sid>`.

## Next: U5 — teardown, fleet doctor, final bundle

Note: with U4 red at the current pins, the FINAL live bundle stays `overall: fail` until the
claude defect ships and the pin advances. U5 + ceremony still complete the harness; the merge
decision (a red acceptance cannot close #605) escalates via the AFK halt protocol.

- U4 (R5/R6) original sketch: two OS processes + deterministic file-based barrier released just before broker
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
