# Code review — #605 cross-runtime Outcome acceptance harness

- **Date**: 2026-07-20
- **Mode**: programmatic (`saga:code-review` gate; caller-owned persistence, zero writes by the review itself)
- **Branch**: `work/605-cross-runtime-acceptance` (worktree `.claude/worktrees/work-605-acceptance`)
- **Diff base**: `794b4da6` (= `origin/main` = merge base; 7 all-new files, +4115/-0 at review time)
- **REVIEWED_SHA**: `d59f0dc2` (review execution) → **`8b13b2a5`** (all findings repaired; final)
- **Vehicle**: cc-workflow `wf_2736f0d0-4fa` — 4 lenses + 8 per-finding validators, all
  `saga:readonly-verifier` + disposable worktree isolation, bounded pool 3
- **Verdict**: **CLEAN** — 8 confirmed findings (4 P2, 4 P3), all repaired at `8b13b2a5` and
  delta-adjudicated resolved; zero open findings, no P0/P1 at any point

## Scope and known-intended state

The branch is the #605 acceptance deliverable: the revision-pinned dual-runtime subprocess
harness (`tools/run_cross_runtime_outcome_acceptance.py`), its hermetic suite
(`tests/test_cross_runtime_acceptance.py`), and the validation evidence set under
`docs/validation/lease-safe-runtime-continuity/` plus the work-session record. Two states were
declared known-intended and are NOT findings:

- The committed evidence bundle records `overall_verdict: fail` (12/14): `race-codex-first`
  and `race-simultaneous` document production defect
  [#628](https://github.com/infiquetra/infiquetra-claude-plugins/issues/628) (Claude advance
  dedup + handoff settled-guard blind to codex-native `outcome.dispatch.v2` records), filed
  upstream per the plan's failure rule and KTD7. The bundle stays red until that fix ships and
  the Claude pin advances.
- KTD4: the branch is harness-only (`tools/`, `tests/`, `docs/`) — zero production plugin or
  release-surface changes, intentionally.

## Lens roster and posture

| Lens | Tier | Result |
| --- | --- | --- |
| correctness | opus / high | Full 2504-line read; negative-matrix codes traced into pinned `outcome_compat.py`; oracles traced for false-pass; 1 finding |
| security | opus / high | Privacy pipeline executed; bundle grepped for secret shapes and paths; child-env curation verified; 3 findings |
| testing | sonnet / medium | Suite re-run under fresh TMPDIR; remediation-commit claims verified via `git log -S`; 2 findings |
| maintainability | sonnet / medium | Full read of both files + all six docs; gates re-run; #628 corroborated live via `gh`; 2 findings |

`missingLenses: []` — every lens returned. Stage A: 8 raw findings, 0 suppressed by the
confidence gate, 0 fingerprint duplicates. Stage B: 8/8 independently validated (each by a
fresh per-finding validator); 0 dropped, 0 over budget.

Notably, all four lenses independently reconfirmed the headline claims: the two red scenarios
attribute to #628 (not to harness bugs), the 49-test suite passes, gates are clean, and the
committed bundle is schema-valid and privacy-clean.

## Confirmed findings and repairs (all fixed at `8b13b2a5`)

| # | Sev | Finding | Repair |
| --- | --- | --- | --- |
| 1 | P2 | `_ABS_PATH_RE` required two path segments, so single-segment absolute paths (`/etc`, `/tmp`, `/root`) escaped both `scrub_check` and `_bounded` | Quantifier loosened `+` → `*` (any absolute path now flags; URLs still self-protect via the `//` scheme guard); 3 new tests incl. URL-stays-clean; committed bundle re-scrubbed clean under the tightened regex |
| 2 | P2 | Simultaneous-race control dir was shared across retry attempts — stale `go`/`ready-*` files from attempt N pre-satisfied attempt N+1's barrier, so retries ran unsynchronized and could only serialize | Control dir namespaced per rig (`race-control-{outcome_id}`; the retry loop's `-r{n}` outcome-id suffix makes it unique per attempt) |
| 3 | P2 | `_child_env_names` (the `env-name-unlisted` halt gate) had zero hermetic coverage | New `TestChildEnvNames` with duck-typed `_StubEnvRuntime`: allowlist-order projection, unlisted-name halt (asserting the leaked name is reported), and a no-dead-entries pin |
| 4 | P2 | Non-`HarnessError` escapes (child `TimeoutExpired`, malformed-output parse errors) bypassed the halt model — the finally-block still persisted a bundle with `halt: null` over a partial scenario set | `main()` now catches untyped escapes as halt code `unhandled-exception` (bounded detail, traceback to stderr, exit 2); new `TestUnhandledEscapeHalt` drives `main()` end-to-end through a raised `TimeoutExpired` and asserts the persisted halt |
| 5 | P3 | `PYTHONPATH` and `XDG_STATE_HOME` were dead `ENV_NAME_ALLOWLIST` entries no child-env builder ever emits | Both removed; `test_allowlist_carries_no_dead_entries` pins the allowlist to exactly the emittable set |
| 6 | P3 | `require_clean_pinned` git probes inherited the operator's full `os.environ` (only children in the file not env-curated) | Both probes now pass `env=dict(_HARNESS_GIT_ENV)` (`GIT_CONFIG_NOSYSTEM=1`, no HOME); `TestPinProbeEnv` asserts the curated env reaches the probe |
| 7 | P3 | Embedded stale-issuer `_tree()` spy had drifted from host `_tree_state` (missing symlink guard) | Symlink guard added to the snippet, restoring behavioral parity between the two effect spies |
| 8 | P3 | Post-barrier `proc.communicate(timeout=…)` had no kill on timeout — a hung barrier-released advance orphaned both OS children past harness exit | `TimeoutExpired` now kills and drains every child in `procs`, then raises a `race-simultaneous` `HarnessError` |

One sub-threshold observation was noted by the correctness lens but not raised (confidence
< 75): `_cli_advance` parses the FIRST `{`-prefixed stdout line while every other parse takes
the LAST line — a convention inconsistency with no observed misbehavior at the pinned CLIs.
Recorded here for the next maintainer; no change made.

## Delta adjudication at `8b13b2a5`

One fresh adversarial `saga:readonly-verifier` (opus/high, disposable worktree) re-checked
every repair at `8b13b2a5` and attempted to refute each. **8/8 resolved, zero new findings,
diff fully accounted** (nothing in `d59f0dc2..8b13b2a5` beyond the eight repairs). Load-bearing
spot checks it re-executed independently: single-segment paths flag while URLs / git remotes /
relative paths / ratio text stay clean AND the committed bundle re-scrubs clean under the new
regex; the retry loop's `-r{n}` outcome-id suffix makes the control dir unique per attempt;
the stub runtime signatures match the real call sites (tests non-vacuous); `HarnessError` is
still matched before the broad `except Exception` and `KeyboardInterrupt`/`SystemExit` are not
swallowed; the allowlist equals exactly the 11 emittable names; `_HARNESS_GIT_ENV` resolves at
call time and real-git pinning tests still pass without `HOME`; the repaired embedded snippet
compiles; the timeout path kills and drains every child so `TimeoutExpired` never escapes.

## Gates at `8b13b2a5`

- Hermetic harness suite: **57 passed** (49 → 57; +8 tests from repairs 1, 3, 4, 6)
- Full repo battery: **5286 passed, 1 skipped** (repo-wide)
- `ruff check` + `ruff format --check`: clean (repo-wide)
- `mypy` (CI scope): clean
- Committed bundle: schema-valid, scrub-clean under the tightened privacy regex — the bundle
  did not need regeneration (the repairs touch retry/halt/hygiene paths the recorded run never
  entered; scenario verdicts and facts are unchanged)

## Built-vs-planned audit (plan R1–R11)

Plan: `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md` (outcome branch).

| Req | Status | Evidence |
| --- | --- | --- |
| R1 revision-pinned runtimes | Built | `require_clean_pinned` + install readback identity; bundle `runtimes.*`; hermetic `TestPinning` |
| R2 hermetic fixtures + broker agreement | Built | `build_topology` (bare origin / creator / clone A / clone B), fake `gh` shim, run-derived `broker_root_digest`, child-env attestation |
| R3 discovery both directions | Built, green | `discovery-*-created` pass; byte-identical projections; clone-B typed denial (`rc 3` / `handoff-missing`) |
| R4 handoff + negative matrix | Built, green | Positive handoff both directions; 15 adversarial cases per direction incl. offer-side stale-issuer, mechanism-text disambiguation of the coarse `handoff-superseded` code, byte-exact effect spies |
| R5 races, crash windows, one effect | Built; two scenarios red by production defect | `race-claude-first` + both crash scenarios green; `race-simultaneous` red documenting #628 (harness deliverable complete; runtime contract violated) |
| R6 codex-native ack chain | Built; red by production defect | Codex-native v2 intent + protected `launched` ack proven working; the Claude-half re-dispatch is #628 |
| R7 mutation-free refusal breadth | Built (consciously bounded) | Negatives matrix + clone-B + effect spies; envelope negatives pinned by both repos' contract suites (README "Consciously bounded coverage") |
| R8 legacy import retired | Built, green | Unconditional retirement receipt, zero-write spy, both runtimes |
| R9 teardown + fleet doctor | Built, green | Idempotent reclaim; doctor zero-open + planted `unledgered-spawn` sensitivity |
| R10 closed privacy-safe bundle | Built | Closed schema; scrub + `assert_privacy` fail-closed gate; names-only env attestation; single-segment path guard (this review's finding 1) |
| R11 downstream QA gate | Sequenced next | The `saga:qa` gate runs immediately after this review — not a gap in the branch |

The acceptance verdict itself is honestly red (12/14) per the plan's failure rule: "Failures
retain artifacts and file/reopen the owning defect without production edits" — the owning
defect is #628, filed with in-bundle chain summaries and overlap receipts as evidence.

## Scope check

CLEAN. Every changed file is a named plan deliverable (`tools/`, `tests/`,
`docs/validation/lease-safe-runtime-continuity/`, `docs/work-sessions/`,
`docs/code-reviews/`). No production plugin, manifest, marketplace, or CHANGELOG surface is
touched (KTD4 — release surfaces intentionally untouched pending #628 upstream discharge).

## Saga routing

No work-thread saga exists for this issue (`saga.py scan` → 0 candidates); execution is
Claude-direct under outcome `lease-safe-runtime-continuity`
(leaf `leaf-lease-safe-runtime-continuity-cross-runtime-acceptance`, ledger-side). Per the
scan-first / never-mint rule, no saga was minted and no `review_paths` tick was written; the
leaf harvest at outcome close carries this artifact path instead.
