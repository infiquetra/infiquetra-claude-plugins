# Run coordination record — issue 907, Agent Launcher session contract

The durable record of operator rulings, cycle accounting, and preserved evidence for this run.
Written by the run coordinator; superseded only by a later dated entry in this file.

## Ruling 1 — hard cap of three valid Saga Code Review cycles

**At most three valid installed Saga Code Review cycles** may run against this integrated target.
Cycle 4 is not started and is not permitted.

The earlier review — a custom brief with an ordinary subagent fan-out producing a Markdown report,
which invoked none of the Saga mechanisms — was ruled an **invalid lifecycle phase** and **does not
count as a cycle**.

| Cycle | State | Evidence |
|---|---|---|
| — | Invalid manual review, not a cycle | `docs/reviews/2026-08-30-cp907-integrated-code-review.md`, SHA-256 `36af250989b55ae6e4f2b59d504f6204a8dcd8537cb0a9af272a2200bb88b85c`. Retained as unvalidated prior art. |
| 1 | **Spent** | Valid installed controller at frozen revision `43498f142f09fbb5c566bf32221394678359db46`. Outcome `repairs_requested`. `cycle_history` holds exactly one entry. |
| 2 | Available | |
| 3 | Available — final | |

**After valid cycle 3** the installed Saga controller serializes the final `review_result.v1` and the
run takes its terminal disposition. No further Code Review is run and no further review work is
generated.

### The cap is machine-enforced, not merely conventional

| Location | Enforcement |
|---|---|
| `plugins/saga/scripts/review_consensus.py:100` | `MAX_REVIEW_CYCLES = 3` |
| `:1469` | a lens approval with `cycle > MAX_REVIEW_CYCLES` is rejected |
| `:1551` | no further cycle is planned once `cycle_count >= MAX_REVIEW_CYCLES` |
| `:1143`–`:1153` | with failing lenses at the cap the terminal outcome is `cycle_cap_best_available`, bound to `best_available_revision` |

## Ruling 2 — separate concurrency cap

**At most three lens workers concurrently.** This is a distinct constraint from the cycle cap and
remains in force independently of it.

## Ruling 3 — residual policy: blockers are repaired, everything else is a transparent residual

Cycle 1 returned **62 findings — 10 blocking, 28 P2, 24 P3** — with all seven lenses below the 9.0
acceptance threshold (security 8.20, api-contract 7.50, architecture-maintainability 7.286,
reliability 7.25, correctness 6.60, testing 6.20, documentation-clarity 5.833).

Two remaining cycles cannot absorb 62 findings and will not attempt to. Repair effort targets
**validated acceptance blockers only**.

Advisory, polish, pre-existing, and human-routed findings are carried as **transparent residuals**
unless an authoritative repair cycle proves a given finding blocks the typed acceptance rule. They
are not deleted, not hidden, and not silently downgraded: every one stays recorded in the typed
result and the evidence artifact, and may become a follow-up issue.

Repair plan under the cap:

1. **Now** — the ten blocking findings, in scope with the current worker and unchanged.
2. **Cycle 2** — re-score, then one repair round against whatever still blocks acceptance.
3. **Cycle 3** — final. If lenses still fail, serialize `cycle_cap_best_available` and surface the
   final scores and residuals rather than grinding further.

## Ruling 4 — no-saga custody, corrected

Code Review §5.1 states that a scan finding no work-thread saga means **no saga write**; §5.4 gates
the tick on a saga existing; §5.3 gives the `adhoc-work-<slug>` branch-id custody form. The cycle-1
review minted `.claude/saga/sagas/issue-907/` and wrote the ledger under an issue-scoped id the
no-saga branch does not authorise.

Corrected using only the installed mechanism, at commit `edcc5626`: the synthetic saga was unminted
and quarantined intact, `saga.py scan` returns zero candidates, and custody was re-persisted under
`adhoc-work-cp907-launcher-session-contract`. The artifact and criteria content-address to identical
hashes under the new custody id, proving nothing was fabricated. No lens re-ran and no score changed.

## Preserved evidence inventory — nothing here is deleted or rewritten

| Artifact | SHA-256 |
|---|---|
| `docs/code-reviews/…-review-result.v1.json` (pre-correction) | `1a015fa6bb0311093e64bec4448d1f9ca2ff2ee8814167d836a90a69c3700861` |
| `docs/code-reviews/…-review-cycle-state.v1.json` (pre-correction) | `7818d5f1a9be62771edd821eaded676611e9ba7343a06dc99c194d310c3e877c` |
| `docs/evidence/issue-907/criteria-code-review-43498f14….json` | `8d432d07319d4f746fdaf664de29ad0aad6b8aa12b11af6a1261b56b81b00b90` |
| `docs/evidence/issue-907/artifacts/70f17ef1….md` | `70f17ef16c6586cb9de3790daba7017cb2c17fb0835b6864809e8c63dec40770` |
| `docs/evidence/issue-907/ledger.jsonl` | `ef68e63050b922e70282a94cb5b99df52de23f0bf76f6100d1d172837496ee1d` |
| `docs/evidence/issue-907/ledger.head` | `531fb77db4f97423bb79b039a4e13eccb1aca1b86ab24fc56ac7af634a8304c3` |
| `docs/evidence/adhoc-work-…/criteria-code-review-43498f14….json` | `8d432d07319d4f746fdaf664de29ad0aad6b8aa12b11af6a1261b56b81b00b90` |
| `docs/evidence/adhoc-work-…/artifacts/70f17ef1….md` | `70f17ef16c6586cb9de3790daba7017cb2c17fb0835b6864809e8c63dec40770` |
| `docs/evidence/adhoc-work-…/ledger.jsonl` | `4b5d414b668dd8102ca9fc0cd8045d651144f3fc447ced9817a311711cffde13` |
| `docs/evidence/adhoc-work-…/ledger.head` | `c3443a45b6948fa7058d47fed6da2c94c11504e58907d990d5daf36c8ac7a405` |
| Quarantined synthetic saga `state.json` | `9b376b8821dbbd846f6b78a569a966d9298d397b056c373f5493d1e40768c95f` |
| Quarantined synthetic tick `20260830-213033.md` | `eb5b6960ade938a65bb45959445273e31a1c89545eecb3963b74da70fe72a632` |
| Parked repair patch (round B, superseded finding set) | `579323465aaa7e6961b4e1c5ce98b3d553005ade085e023b46240b6b5d36177e` |

Both evidence-ledger chains verify independently: `entry_count 2, verified_artifacts 1,
verified_criteria 1`.

## Ruling 5 — out-of-scope findings are filed, not absorbed

Two findings against Orchestrate's launch loop and sweep were ruled outside this run's scope and
filed as issue 944 rather than widening a fixed-membership run. The early plan-validation gap the
runtime checkpoint surfaced is already owned by issue 879 under the sibling parent, and was likewise
not absorbed here.
