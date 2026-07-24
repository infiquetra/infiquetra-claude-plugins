# Doc Review — Issue #626 plan (outcome settlement-halt for externally-executed leaves)

**Verdict: READY to drive `/work`.** No `P0`/`P1`. Every load-bearing `file:line` anchor was verified
accurate to the line at the reviewed revision; one imprecise code-notation was safe-fixed in place. One
`P2` (release-surface bump decision) and one `P3` (close-ceremony pointer) remain — neither blocks
`/work`; the `P2` should be resolved consciously before the release-surface unit runs.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-07-24-issue-626-outcome-settlement-halt-externally-executed-leaves-plan.md` |
| Reviewed revision | working tree at main `03c2640c` (plan doc untracked) |
| Classification | plan (readiness-skeptic pass; no formal idea/issue rubric engine) |
| Blocked | No |
| Findings | 1×`P2`, 1×`P3` remaining; 1 safe fix applied |
| Review artifact | `docs/reviews/doc-review-issue-626-2026-07-24.md` |
| Linked plan | `docs/plans/2026-07-24-issue-626-outcome-settlement-halt-externally-executed-leaves-plan.md` |
| Linked issue | `infiquetra/infiquetra-claude-plugins#626` (leaf `sub-626`, outcome `governed-execution-integrity`, Objective #639) |
| Saga | `issue-626` (plan phase complete) |

## Applied fixes

**Fix-1 — `is_success` notation precision (Problem Frame, stage-1 harvest bullet).** The plan described
harvest materializing `CompletionEvent(state="done", is_success=True)`, writing a **derived property**
as if it were a constructor kwarg. Corrected in place to state that `is_success` is not a field — it
returns `state in SUCCESS_STATES`, and `SUCCESS_STATES = frozenset({"done"})` — with anchors
`outcome_store.py:276-277` and `outcome_spec.py:78`. The plan's *conclusion* (a harvested completion is
`is_success` True) was already substantively correct; this only removes a mechanism-misread that could
have led an implementer to try to set the field.

## Anchor verification (readiness surface #1)

Every anchor in the plan was checked against live code at `03c2640c`. All are accurate to the cited
line or range:

| Plan anchor | Reality at `03c2640c` | Verdict |
|---|---|---|
| `dispatch_settlement.py:27` `WAIVER_KIND="dispatch-waiver"` | `:27` exact | ✓ |
| `dispatch_settlement.py:55` `DEFAULT_THRESHOLD_PERCENT = 0` | `:55` exact | ✓ |
| `:293,1470,1678` threshold defaults | all three exact | ✓ |
| `:1060-1069` open-state / `current_complete` | `current_complete` at `:1069` | ✓ |
| `:1075-1088` halt gate (`* 100 >`, `progress_halt`) | breach expr `:1085`, `progress_halt` `:1088` | ✓ |
| `:1083` DELIVERED exit from casualty set | `latest_states[unit_id][1] != DELIVERED` at `:1083` | ✓ |
| `:1545-1643` `settle_attempt` | def at `:1545` | ✓ |
| `:1572-1594` same-classification no-op | `return dict(prior)` at `:1594` | ✓ |
| `:1591` contradictory-under-same-class raises | raise at `:1591` | ✓ |
| `:1595-1626` casualty→DELIVERED late-delivery path | branch `:1595`, append `:1615-1626` | ✓ |
| `outcome.py:1023-1059` `if autonomous:` → `reconcile_board` | `#620` comment `:1032`, call `:1059` | ✓ |
| `outcome.py:1206-1215` `active_waiver_covers` | call at `:1211` inside `#618` block `:1205-1215` | ✓ |
| `outcome.py:2100-2209` `production_harvester` | def `:2100`, `return harvester` ≈`:2209` | ✓ |
| `outcome.py:2148-2206` reconcile loop over `outcome_dispatch_bindings` | bindings `:2150`, loop `:2156-2205` | ✓ |
| `outcome.py:2182` `settle_attempt`; `:2192` `SILENT_NOOP` | `:2182` / DELIVERED `:2190` / SILENT_NOOP `:2192` | ✓ |
| `outcome_orchestrator.py:186-274` harvest writes completion | def `:186`, `CompletionEvent(state="done")` `:264`, `write_completion_event` `:272` | ✓ (see Fix-1) |

The two-stage chain the plan hinges on is confirmed structurally: inner `harvester`
(`outcome.py:2140`) calls `outcome_orchestrator.harvest` (stage 1, `:2141`), then reconciles **every**
dispatched subplot (`:2148-2206`) with `completion = events[-1]`, `is_success = completion.is_success`
(`:2181`), and `classification = DELIVERED if is_success else SILENT_NOOP` (`:2182-2192`). The loop is
keyed on *dispatched-and-has-completion*, with no `site`/`backend` filter — so an externally-executed
leaf auto-settles exactly as the plan claims. `outcome_dispatch_bindings` is keyed by `subplot_id`
(one binding per sid), which is the precise basis of the plan's `#628` note.

## Readiness summary

The plan is coherent, honestly framed, and safe to execute. Its central move — that #626's residual is
**zero required production code** because direction (a) is already wired, backend-agnostic, and
idempotent — is verified true at the code level. The intellectual-honesty posture (KTD3: characterization
tests that pass, no manufactured red state, load-bearingness proved by an operator-gated stash/neuter
probe during R-live) is exactly right for a verify-and-close and is well-defended against the obvious
`/code-review` objection ("these tests never fail"). Requirements R1–R6 + R-live each map to a concrete
U1/U2 test, a U3 doc, or the operator-gated live leg. Scope boundaries correctly exclude #620/#618
(shipped), #628 (noted, not fixed), #642, #635, and codex#45 (downstream, noted as unblocked-by-close).

The only decision the plan leaves under-adjudicated is the release-surface bump (D1), and one optional
completeness pointer (D2) would de-risk the close.

## Remaining findings

| Key | Priority | Status | Finding |
|---|---|---|---|
| D1 | P2 | open | U4/R6/KTD2 assert a saga patch bump `0.114.0 → 0.115.0` is required, but the justification ("tests + CHANGELOG are part of the plugin's shipped surface") is questionable: tests live at repo-root `tests/`, not under `plugins/saga/`, and #626 ships zero plugin-directory code. The #605 precedent (harness/tests-only → intentional **zero** release-surface change) is a direct in-campaign counterexample. Drift pins key on `plugin.json`, which a test-only PR does not change, so no gate forces a bump. Resolve the bump/no-bump decision consciously against the #605 precedent before the release-surface unit runs — a needless bump re-invites the same-version sibling-collision the plan itself warns about; skipping one that is actually wanted would leave the CHANGELOG silent about the hardening. |
| D2 | P3 | open | The plan states "closing #626 unblocks codex#45 — the campaign critical path" but gives no pointer to the close/harvest mechanics. This campaign's own recurring gotcha (an empty spec `leaf_saga_id` makes the closure gate **silently skip** the harvest — the #617 lesson) and the harvest-under-`leaf-governed-execution-integrity-sub-626` mapping are the exact steps that make the "unblock codex#45" outcome real. A one-line pointer in U3 or Acceptance would de-risk the close. Arguably `/work` + `/outcome` territory, hence P3. |

## Residual risk from limited evidence

**R-live enforcement seam (mitigated by precedent, not a plan defect).** The plan states in four places
that R-live gates the close ("before the issue closes"), but R-live is *post-merge* and operator-gated,
so the surface that actually withholds the #626 close until R-live passes is implicit
(`/work` merges under confirmation; `/outcome advance` harvests/closes). The #615 R9 / #620 R10 pattern
makes this operationally clear — merge → run the live leg → then close/harvest — so it is called out as
residual risk rather than a finding.

**Not independently re-verified (out of #626 scope):** #620's five-rung resolver internals and its R10
PASS, and the live outcome-DAG state (6/9, `sub-626` dispatched-and-idle) are taken as the plan's
premises from sibling-leaf evidence; a doc-review does not re-derive them.
