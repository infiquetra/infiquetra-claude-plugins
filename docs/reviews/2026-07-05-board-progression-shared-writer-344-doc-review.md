# Doc-review — board_progression shared writer (#344)

- **Target:** `docs/plans/2026-07-05-board-progression-shared-writer-344-plan.md`
- **Reviewed revision:** working tree (plan authored this session, pre-`/work`)
- **Blocked:** No — no P0/P1 remain after safe fixes; `/work` may proceed.
- **Linked:** issue #344; saga `issue-344`; execution-order row 6.

## Verdict

Ready to drive implementation. Two P1 gaps were found and **fixed in place** (both evidence-backed
from exact call sites); three P3 clarity items remain, none blocking.

## Applied fixes (safe, in-place)

| # | Was | Fix | Evidence |
|---|---|---|---|
| F1 (P1) | Plan defined only a Python library `authorize_and_write`; never said how a markdown skill invokes it, nor where the concrete `board_writer` comes from for a CLI. U4/U5 unbuildable. | Added **KTD6** + revised U1/U4: `board_progression` moves in `_default_board_writer` (the `OpKind`→mission-control mapping) and exposes a `write …` CLI printing record JSON; `/work` branches on `written` vs `gated`. | `outcome.py:452` (`_default_board_writer`), `:1322` (already CLI-constructed); `work/SKILL.md` drives all board moves via `python3 …/*.py`. |
| F2 (P1) | U1 proposed *moving* `_safe_ledger_name` into `board_progression`; that would strand `outcome_reconcile`. Plan called `outcome_reconcile` a mere "ledger-dir reader." | Corrected grounding + KTD1 + U2: `outcome_reconcile:256` consumes 5 helpers; `_safe_ledger_name` must be **re-exported**; added `tests/test_outcome_reconcile.py` passes-unchanged scenario. | `outcome_reconcile.py:271/272/285/298/337` (`sync._default_schema_path/_resolve_status_map/_parse_issue_ref/_candidate_ops/_safe_ledger_name`). |

## Remaining findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P3 | U3 assumes `saga_obj` exposes `lifecycle_phase`; it's a durable field (`loop/SKILL.md:121`) but the implementer should `getattr(..., default)` — SAFE-DEGRADATION rule already bounds a miss to NOT_REACHED. | Open (low risk) |
| 2 | P3 | U3 names arc stages (Idea·Plan·Work·Review·Merge·Deploy) but not the exact `lifecycle_phase`→stage mapping; implementer defines it. Pure function + purity test + safe-degradation bound the risk. | Open (low risk) |
| 3 | P3 | Issue AE6 (end-to-end lifecycle closure) has no single automated test — verified by composition (U1 CLI gated/written + U3 purity + U4/U5 wiring) since the suite forbids live `gh`. | Open (by design) |

## Residual risk

Low. The two structural hazards (skill→CLI invocation seam; helper-surface stranding) are fixed and
now carry explicit test scenarios (`test_board_progression.py` CLI cases; `test_outcome_reconcile.py`
unchanged). The P3s are implementation-clarity items the SAFE-DEGRADATION rule already de-risks.
