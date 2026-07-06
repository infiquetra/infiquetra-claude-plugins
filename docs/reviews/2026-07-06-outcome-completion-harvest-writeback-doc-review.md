# Doc Review — /outcome completion harvest PR-ref writeback (#495)

**Target:** `docs/plans/2026-07-06-outcome-completion-harvest-writeback-plan.md`
**Reviewed revision:** working tree (2026-07-06)
**Linked issue:** infiquetra/infiquetra-claude-plugins#495
**Plan saga:** `issue-495` (git-ignored)
**Blocked:** No — no P0/P1 remain after safe fixes; one P2 scope question is flagged for operator confirmation.

## Readiness summary

Ready to drive implementation once the operator confirms the one scope question below. The plan is
well-grounded (every load-bearing claim cites a `path:line` verified against current code), and the
adversarial pass caught a real design defect in the plan's own U3 that would have wasted an
implementation unit. All fixes applied are evidence-backed against the code.

## Applied fixes

| # | Fix | Evidence |
|---|---|---|
| 1 | **Rewrote the vacuous U3.** The original "merge-time PR writeback" was a no-op: the auto-merge queue is a *consumer* of `github.pr`, not a producer. Replaced with an end-to-end harvest integration unit; reframed R1/KTD1 around the single missing producer that feeds both consumers. | `outcome_merge.py:170` `_is_mergeable_kind` requires `bool(node.github.get("pr"))`; `:113` reads the ref to merge. |
| 2 | **U1 now parses to components (`_parse_ref`)**, not a pre-baked URL, so normalization does not starve `_closed_by`'s events-API path (which needs `owner/repo#N`). Added a coupling-guard test. | `outcome_github.py:148` `_closed_by` regex matches only `owner/repo#N`; would return "" on a URL. |
| 3 | Decided U1's test file (`tests/test_outcome_completion.py`); removed the "or a new file" hedge. | No `tests/test_outcome_github.py` exists; `pr_state`/`issue_state` tests already live in `test_outcome_completion.py`. |
| 4 | Added a note to U2 that `link-pr` attaches a pointer only — the barrier re-verifies `merged`, so a wrong/unmerged link never falsely completes a node. | `outcome_orchestrator.py:104-112`. |

## Remaining findings

| Priority | Finding | Status |
|---|---|---|
| P2 | **Scope of "automatic."** The plan delivers *correct* (the `link-pr` verb removes the JSON hand-edit) but **defers** a zero-touch autonomous PR producer. Evidence supports deferral: no code leaf has ever reached the auto-merge queue (all outcomes ran attended/inline), and every auto-mechanism is either fragile (closing-PR timeline resolution, which would not even have fired for the tier-effort leaves since their sub-issues were closed manually) or couples the leaf executor to the coordinator. But the operator's directive said "correct **and** automatic," so this deviation is surfaced, not silently taken. | **Open — operator confirmation requested** |

## Verified, no finding

- Version bump `0.70.0 → 0.71.0`: current saga `plugin.json` is `0.70.0`; pin at `tests/test_saga_plugin.py:49`. Minor is correct for a new CLI verb.
- The `code:pr-merged` barrier predicate is correct as-is (the bug is the absent producer, not the consumer) — U4 pins it as a pure regression test.
- R17 non-goal is respected: the fix touches GitHub refs + completion events, never persists derived state into the spec JSON.

## Residual risk

Low. The two implementation risks (U1 ref-format edge cases; U3's harness reuse) are bounded and
test-covered. The single judgment call is the P2 scope question — resolved in the plan as "defer," pending
operator sign-off.
