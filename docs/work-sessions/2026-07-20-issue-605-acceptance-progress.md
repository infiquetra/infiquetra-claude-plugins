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

## Anchored ceremony — round 1 complete, all 17 findings remediated

The anchored 7-lens ceremony (cc-workflow run `wf_d80aedc3-39c`, anchor `4b21df73…` verified
byte-exact) ran against HEAD `eae03b4`. All 7 lenses reported (`missing: []`). Panel verdict:
**the core acceptance claims and the #628 attribution SURVIVED adversarial refutation** — three
lenses independently re-executed the harness against the real pins and reproduced the 12/14
split scenario-for-scenario, and the event-flow validator confirmed the double-dispatch ledger
records by direct inspection. 17 findings (2 P1, 6 P2, 9 P3), all on evidence integrity and
oracle strength, all fixed in the remediation commit:

- **P1 broker_root_digest constant** → now run-derived: each installed runtime resolves the
  broker root from the hermetic child env (`resolve_state_root`), divergence halts
  (`broker-root-divergence`), digest is over the workbench-relative path.
- **P1 retention promise false on scenario failures** → `_should_keep()` retains the workdir
  for any failing scenario, not just hard halts; help text fixed; hermetic test added.
- **P2 environment_names_set sampled harness env** → computed from the real child env dicts;
  PWD added to (and TMPDIR dropped from) the allowlist; out-of-list child names halt
  (`env-name-unlisted`).
- **P2 facts empty on failing race scenarios** → `HarnessError.facts` carries partial
  structured evidence through the fail path; both red scenarios now record chain summaries +
  overlap receipts in the bundle.
- **P2 README R7 mis-citation** → attributed to the contract suites, not the hermetic suite.
- **P2 verdict oracles untested** → hermetic tests for `_chain_summary` (double-settlement,
  dangling native), `_expect_refusal` (rc/code/last-line/mechanism-text), `_expect_unchanged`
  (mutation + addition), `_should_keep`.
- **P2 clone-B denial accepted any nonzero** → typed refusal pinned: rc 3 + `handoff-missing`.
- **P2 wrong-issuer negative absent** → new offer-side `stale-issuer` case (a successful offer
  relinquishes the issuer's authority; re-offer from the closed lease refuses
  `handoff-issuer-not-current` with in-process zero-effect proof). Matrix is now 15 cases.
- **P3s** → legacy-import oracle pins the retirement-receipt text (refusal is
  unconditional-by-design; fixture reframed); `handoff-superseded` aliasing broken by pinning
  receipt mechanism text (wrong-authority → head-absent, wrong-fence → head-moved);
  `scrub_check`/`_bounded` generalize to any absolute path root (`_ABS_PATH_RE`), not a 7-root
  denylist; positive-handoff leaf state pinned per receiver; doctor sensitivity requires the
  `unledgered-spawn` class; crash recovery polls past lease expiry instead of one fixed sleep;
  serialized (non-overlapping) race runs get a distinct `race-serialized` code and up to two
  fresh-rig retries instead of reading a scheduling hiccup as a defect.

Regenerated bundle (sha `1cf824e6…`): still **12/14, overall fail** — both reds remain #628
production truth, now with auditable in-bundle facts. Full battery 5273 passed; schema valid;
44 hermetic harness tests.

## Re-adjudication round 2 — all 17 round-1 findings RESOLVED; 2 new P3s fixed (cycle 2)

Round-2 panel (workflow `wf_44b776e2-ed6`, 6 originating lenses, fresh saga:readonly-verifier +
worktree spawns at round-1 tiers): **every round-1 finding confirmed genuinely resolved and
non-vacuous**; the #628 attribution and the 12/14 bundle were re-upheld. Two NEW P3s from the
remediation itself, both fixed in the cycle-2 commit:

- **review-security P3**: the generalized `_ABS_PATH_RE` lookbehind excluded ':', so
  colon-immediately-prefixed paths (`tmpdir:/var/folders/…`) slipped both scrub_check and
  _bounded — a false negative the old denylist caught. Fix: drop ':' from the lookbehind; URLs
  stay safe because a scheme's "//" fails the first-segment class (proven by test). Leak +
  redaction tests added; committed bundle re-verified clean under the tightened guard.
- **review-architecture P3**: `_resolved_broker_digest`'s halt branches had no hermetic test.
  Fix: `TestBrokerRootDigest` with a duck-typed stub runtime — agreement digest, runtime
  divergence halt, agreed-but-wrong-root halt, probe-failure halt. Suite 44 → 49.

## Ceremony CONVERGED — round 3, HEAD e7ec568e

Cycle-3 re-adjudication (2 fresh opus/high saga:readonly-verifier + worktree spawns): both
cycle-2 P3s RESOLVED, zero new findings. Security lens probed the regex both directions
(quote/bracket/equals/JSON-embedded prefixes all flag; every documented legit fact shape —
URLs, git remotes, refs, version strings, dispatch ids, `#sha256=` refs — stays clean) and
re-verified the committed bundle clean. Architecture lens verified the stub runtime is
faithful to `InstalledRuntime.python`'s contract (tests non-vacuous), every halt branch
pinned, KTD4 intact. Full ceremony record:
`docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance-ceremony.md`.
Next: programmatic saga:code-review (CLEAN gate) + saga:qa, then the PR + AFK halt report
(red acceptance blocks the #605 close; #628 fix is a new production unit outside recorded
authority).

## Programmatic saga:code-review gate — 8 findings, all repaired at 8b13b2a5

The gate ran as cc-workflow `wf_2736f0d0-4fa` at REVIEWED_SHA d59f0dc2: 4 lenses
(correctness + security at opus/high, testing + maintainability at sonnet/medium, all
saga:readonly-verifier + worktree isolation, pool 3), then one independent validator per
finding. 8 raw findings, 0 suppressed, 8/8 validated — 4 P2, 4 P3, no P0/P1. All four lenses
independently re-upheld the #628 attribution, the 12/14 bundle, and the gate results.

All 8 repaired in commit `8b13b2a5` (harness + tests only): single-segment absolute paths now
flag in the privacy guard; the simultaneous-race control dir is namespaced per retry rig;
untyped escapes (child timeout, malformed output) persist an honest `unhandled-exception`
halt instead of `halt:null`; hung race children are killed on communicate timeout; pin probes
run under the curated git env; the embedded stale-issuer tree spy regained the symlink guard;
two dead allowlist entries dropped; hermetic suite 49 → 57 (env-name-unlisted halt,
unhandled-escape halt, pin-probe env, single-segment privacy breadth). Full battery 5286
passed / 1 skipped; ruff + format + mypy clean; committed bundle re-verified scrub-clean under
the tightened regex (no regeneration needed — repairs touch retry/halt/hygiene paths the
recorded run never entered). Durable artifact:
`docs/code-reviews/2026-07-20-issue-605-cross-runtime-acceptance-code-review.md`.

## race-simultaneous codex-won interleave — harness completion gap repaired (post-#628-fix)

The #628 runtime fix (branch `work/628-v2-vocabulary`, `4b088552`) made the codex-won
simultaneous interleave reachable for the first time: a v2-aware Claude now refuses the
in-flight native intent instead of double-dispatching. That exposed a harness gap, masked
until now by the old always-dispatching Claude: `_scenario_simultaneous` played no launched
runner, so a codex-won race could never settle (`settled_chains: 0`, one legitimately
in-flight intent) and the scenario was a coin flip on the barrier winner. Repair: when the
post-retry census shows exactly one un-acked native intent and nothing settled, the scenario
now completes the codex-native chain the same way `race-codex-first` does (launch prep →
write-once effect → receipt-validated `launched` ack) and then re-asserts at quiescence that
BOTH runtimes still refuse and exactly one settled chain exists. Verified: 3 consecutive
`--units u4-race` runs at claude `4b088552` / codex `f3e1af75` — 5/5 pass each, all three
exercising the codex-won branch (`v2_intents=1, legacy_commits=0`). Hermetic suite 57 passed;
ruff clean.
