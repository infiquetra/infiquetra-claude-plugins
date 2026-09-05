# Issue 912 — repair round integration log

This log was written **after the fact**, during review-cycle-1 repair of DOC-13.
It reconstructs the four integration runs from the controller's preserved gate-log
results supplied in the repair dispatch, corroborated by
[repair-round-9.md](repair-round-9.md#gates). It was not collected live during the
runs. The repair worker has not rerun the full gate or claimed new reads of the
preserved log directories; the `result.txt` contents below reproduce the reads
reported by the controller.

The source dispatch is
`/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/9a7fbbe1-60b2-4ce4-baed-afe304e8671c/scratchpad/run912b/repair-cycle-1.md`,
under finding DOC-13. The previously recorded substance remains in
`repair-round-9.md`; this file supplies the location promised by the historical
repair plan. No plan was rewritten.

## Four integration gate results

The controller ran each gate in a clean detached worktree and verified all three
signals: wrapper exit status **0**, the green `result.txt` marker, and exactly
**25 step headers**. The recorded tests and coverage were:

| Integration commit | Lane | Wrapper exit | Step headers | Tests | Coverage |
|---|---|---|---|---|---|
| `8a250b1a` | A — handoff envelope core | 0 | 25 | 7297 passed, 7 skipped | 85% |
| `f8f661bf` | B — contract prose, guard, journal | 0 | 25 | 7300 passed, 7 skipped | 85% |
| `c21f7de8` | C — routing prose, guards, docs model | 0 | 25 | 7309 passed, 7 skipped | 85% |
| `5483b9e6` | Journal fold | 0 | 25 | 7309 passed, 7 skipped | 85% |

### `8a250b1a` — Lane A: recorded `result.txt` read

```text
GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered.
```

### `f8f661bf` — Lane B: recorded `result.txt` read

```text
GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered.
```

### `c21f7de8` — Lane C: recorded `result.txt` read

```text
GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered.
```

### `5483b9e6` — Journal fold: recorded `result.txt` read

```text
GATE GREEN — 25 steps ran, 0 blocking failures, 0 uncovered.
```

## Final candidate at review

The final candidate hash at the time of review was **`f28505a7`**, as supplied by
the controller. Evidence-ledger sequence 19 binds the seven-lens review to that
candidate and records `repairs_requested`. These historical green gates are not
an acceptance verdict and do not claim verification of the subsequent TEST-11 /
DOC-13 repair revision; the controller owns its next gate and review.
