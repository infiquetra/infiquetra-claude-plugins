# Code review — #628 v2 dispatch-vocabulary awareness (Claude runtime)

- **Date**: 2026-07-20
- **Mode**: programmatic (PA-unit precedent; caller-owned persistence, zero writes by the review itself)
- **Branch**: `work/628-v2-vocabulary` (worktree `.claude/worktrees/work-628`), diff base `794b4da6` (= `origin/main`)
- **REVIEWED_SHA**: `4b088552` (review execution) → **`93f3cead`** (all findings repaired; final)
- **Vehicle**: 3 adversarial lenses + 1 delta adjudicator, all `saga:readonly-verifier` +
  disposable worktree isolation, ≤3 concurrent
- **Verdict**: **CLEAN** — 4 confirmed findings (1 P1, 1 P2, 2 P3), all repaired at `93f3cead`
  and delta-adjudicated resolved; zero open findings, no P0

## Scope

The #628 production fix: port the codex runtime's version-aware dispatch reducer
(`outcome_store.reduce_dispatch_ledger`, byte-identical to infiquetra-codex-plugins at
`f3e1af75`) and derive all Claude-side consumers from it — `_dispatch_records`, the
`_reconcile_once` settled/in-flight sets (+ a visible in-flight halt receipt),
`_settled_lookup(repo_root, outcome_id)` for the `accept_handoff` already-settled guard,
`replay_pending`, and `derive_states`. Release surfaces: saga 0.106.0 (plugin.json,
marketplace.json, CHANGELOG, drift-guard pin). Companion harness commit `fd320f20` on
`work/605-cross-runtime-acceptance` (the codex-won simultaneous race now completes the
codex-native chain via the launched runner before judging R5 at quiescence) was reviewed in
the same pass.

## Lens roster and posture

| Lens | Tier | Result |
| --- | --- | --- |
| correctness/parity | opus / high | AST-body diff of the reducer vs codex (byte-identical); every consumer traced; harness census arithmetic traced; 1 finding |
| robustness/security | opus / high | Hostile-ledger probes executed empirically (forged acks/intents, type degenerates, ordering hazards); NEW-vs-pre-existing risk split; 1 finding |
| test adequacy | sonnet / medium | Mutation-tested every new test against its production change (all load-bearing); fixture fidelity verified against the real codex writer; 2 findings |

All three lenses independently upheld the load-bearing #628 invariants: the reducer port is
byte-identical to the codex reference; a receipt-authoritative launched ack settles exactly
like a legacy commit (mutation-killable); a live native intent halts loudly instead of
re-driving (mutation-killable); the settled guard consults the shared reduction
(mutation-killable); the forged-record surface is pre-existing shared-clone trust, not
widened by this diff.

## Confirmed findings and repairs (all fixed at `93f3cead`)

| # | Sev | Finding | Repair |
| --- | --- | --- | --- |
| 1 | P1 | No unit coverage for the literal defect shape — ONE subplot carrying records from BOTH vocabularies (the reducer's legacy-commit ordering guard was not mutation-killable) | `test_reduce_same_subplot_cross_vocabulary_collision`: native-then-legacy and legacy-then-native orders both converge on the native settlement; the mid-sequence settled bit is pinned |
| 2 | P2 | The CLI seam `attach --advance` → `_settled_lookup(root, args.outcome_id)` had no regression protection (reverting to the one-arg form passed every test) | `test_cli_attach_advance_wires_outcome_id_into_settled_lookup` records the constructed guard's arguments through `main()` |
| 3 | P3 | Handed-off settlements made the cockpit and `attend` contradict: `status` said `dispatched`, `attend` said "not dispatched yet" | `derive_states` surfaces `handed-off` (before the settled map); `attend` raises a distinct "settled without a native leaf saga" error; `test_handed_off_leaf_status_and_attend_tell_one_story` |
| 4 | P3 | `outcome_decompose._IN_FLIGHT` did not honor the new in-flight vocabulary — prune/elaborate could discard a natively-in-flight leaf (R33) | `_IN_FLIGHT` gains `intent-created` and `handed-off`; `test_elaborate_a_natively_in_flight_node_is_rejected` |

Noted, not raised (pre-existing, unchanged blast radius): the shared-clone ledger is
trust-on-write — a forged v2 ack settles exactly as a forged legacy commit always did; a
forged bare v2 intent wedges the frontier loudly (the deliberate trade replacing the silent
double dispatch), with reclaim living in the issuing runtime (codex ack / operator handoff),
matching the codex posture. The Claude port of `_dispatch_records` deliberately keeps ALL
settled entries (legacy is Claude's native vocabulary — its own dispatches must read
`dispatched`), diverging from codex's v2-launched-only form; the handed-off surfacing repair
closes the one user-visible inconsistency this created.

## Delta adjudication at `93f3cead`

One fresh adversarial `saga:readonly-verifier` (opus, disposable worktree) mutation-verified
repairs 1 and 2 (each new test fails when its production change is reverted), verified the
handed-off precedence and the R33 guard on both `prune` and `elaborate` paths, confirmed no
other `derive_states` consumer misbehaves on the new state strings, and confirmed the diff
`4b088552..93f3cead` contains nothing beyond the four repairs plus the version drift-guard
pin, and independently ran the five outcome suites clean (227 passed). **4/4 resolved,
zero new findings, diff fully accounted.**

## Gates at `93f3cead`

- Full battery: **5236 collected — 5235 passed, 1 skipped** (pre-push gate, both pushes)
- Focused outcome suites: 314 passed; `ruff check` + `ruff format --check` clean repo-wide;
  `mypy` (CI scope) clean
- Live pre-merge harness `--units u4-race` at claude `93f3cead` / codex `f3e1af75`:
  **5/5 pass, exit 0** (including three consecutive codex-won simultaneous interleaves at
  `4b088552` exercising the new in-flight refusal + runner-completion path)

## Issue acceptance criteria

| AC | Status |
| --- | --- |
| Launched ack settles like a legacy commit | Met — reducer + `test_native_launched_ack_settles_leaf_no_redispatch` |
| Live intent reads IN-FLIGHT with explicit refusal | Met — visible halt receipt + `test_live_native_intent_reads_in_flight_not_redriven` |
| `accept_handoff` refuses natively-settled (`handoff-already-settled`) | Met — `_settled_lookup` reduction consult + direct, wiring, and refusal tests |
| Reducer parity with the codex arms | Met — AST-body identical to `f3e1af75` |
| Regression tests: codex-first, simultaneous, handoff refusal | Met — unit level (collision test both orders) + live harness (5/5 u4-race incl. codex-won simultaneous) |
