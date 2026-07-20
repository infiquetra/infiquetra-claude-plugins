# Closing report — lease-safe-runtime-continuity

- **Date**: 2026-07-20
- **Status**: **COMPLETE — 11/11 leaves done**, outcome cockpit `complete: true`
  (harvest commit `bdfcabda` on this branch)
- **Acceptance**: **green, 14/14 scenarios, exit 0** at Claude `787654d0` (saga 0.106.1,
  fleet-core 0.16.0) x Codex `f3e1af75` (saga 0.78.0+codex.20260720120109, fleet-core
  0.10.0+codex.20260720120109); committed bundle
  `docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json` on `main`
  (PR #629, merge `00adb06f`)
- Supersedes the 2026-07-20 AFK halt report (`afk-halt-report.md`): decision 1 ("fix #628")
  was authorized by Jeff ("628 fix authorized") and executed to completion.

## Closure chain (from the halt to green)

1. **#628** (Claude v2 dispatch-vocabulary blindness → cross-runtime double dispatch,
   documented red 12/14 by the acceptance harness): fixed in **PR #630** (saga 0.106.0) —
   codex's `reduce_dispatch_ledger` ported verbatim, all Claude consumers derive through it;
   3-lens code review CLEAN (4 findings repaired at `93f3cead`, delta-adjudicated 4/4);
   pre-merge `u4-race` 5/5.
2. First full re-run at `22c9aa87` went **13/14**: the #628 settled-guard consulted the
   reduction for ANY settled state — broader than the codex reference — reordering refusal
   codes in the byte-frozen accept flow (`handoff-already-settled` where the contract says
   `handoff-receiver-conflict` for a replayed handoff). Filed **#631**, fixed in **PR #632**
   (saga 0.106.1, reduction consult restricted to the receipt-authoritative `dispatched`
   state); adversarially verified 6/6 upheld; pre-merge `u3-handoff` 4/4.
3. Full re-run at `787654d0`: **14/14 pass, exit 0**. README "Current verdict" flipped to
   pass with the two-defect discharge history (`589c2827`); PR #629 marked ready and merged;
   #605 closed with evidence.
4. Leaf harvested through the closure gate (evidence ledger
   `docs/evidence/leaf-lease-safe-runtime-continuity-cross-runtime-acceptance/`: code-review
   `clean` + qa `ship-with-deferred` at close SHA `b9f65e11`, deferred item discharged);
   #579 closed; Operations board reconciled (#579/#604/#605/#628/#631/codex#34 → Done).

## Open follow-ups (outside this outcome's scope)

- **infiquetra-claude-plugins#627** (OPEN): lease seam and guard-scope defects from the
  codex PA-2 review — supersede-on-acquire overclaim, missing `DispatcherError` arm,
  resolve-scope guard bypass, reducer-invisible halt records.
- **infiquetra-codex-plugins#43** parity backlog: COR3 advisory (prune lease-authority site
  unported — worktree-lease layer port unit), recorded as an issue comment by the PA-2
  review.
- **Unpushed local-main commits in the primary clone** (verified 2026-07-20, predate this
  ceremony, not part of this outcome): `dc1d8bef` "fix(runtime): isolate external CLI
  children from cmux" and `1a7b145a` "test(fleet-monitor): pin the cmux-bypass real proof".
  They need Jeff's decision (push, PR, or drop) — left untouched.

## LEARNINGS ledger state

Shipped with their changes (in `docs/engineering-journal/LEARNINGS.md` on `main`):
`{#v2-vocabulary-asymmetry-628}` (PR #630) and `{#settled-guard-precedence-631}` (PR #632).

Remaining candidates for `/retro` promotion (evidence pointers, not yet in LEARNINGS):

- **Harness coin-flip gap**: `_scenario_simultaneous` originally played no codex runner, so
  with a *correct* Claude runtime a codex-won race legitimately ended unsettled and the
  scenario was a coin flip — masked by the old always-dispatching Claude. Fixed on the
  acceptance branch (`fd320f20`) by completing the codex-native chain when census shows
  exactly one un-acked native intent. Rule: an acceptance scenario must model every actor
  needed to reach quiescence, or a runtime fix can flip it red for the wrong reason.
- **Typed-exception blind spot**: see the #605 code-review artifact
  (`docs/code-reviews/2026-07-20-issue-605-cross-runtime-acceptance-code-review.md`) finding
  table — broad exception arms hid a specific failure class until the review forced typed
  handling.
- **Evidence-theater remediation**: see the same review artifact and the QA artifact
  (`docs/evidence/adhoc-work-605-cross-runtime-acceptance/`) — evidence claims must bind to
  the SHA and artifact actually produced, not to narrative self-reports; the closure gate's
  stale-sha/supersession vocabulary is the enforcement seam.
