# Doc review — issue #346 plan (ceremony hazards, merge-watcher, ship --undo)

**Verdict: READY — not blocked.** 0 P0/P1 remaining. Four safe fixes applied in place; one
report-only P3 stands as a documented assumption with its revisit condition already recorded.

- **Target:** `docs/plans/2026-07-11-issue-346-ceremony-hazards-watcher-undo-plan.md`
- **Reviewed revision:** working tree, 2026-07-11 (plan not yet committed; authored this session)
- **Blocked:** no
- **Linked issue:** infiquetra/infiquetra-claude-plugins#346 · **Spec:**
  `docs/plans/2026-07-11-issue-346-ceremony-hazards-watcher-undo-spec.json` (validated, spend 110,
  tiers operator-confirmed)
- **Mode:** plan classification (path + `origin:`/`Implementation Units`/KTD/U-ID markers);
  readiness-skeptic pass — the idea/issue rubric phases do not apply to plans. Engine offer probed:
  stored preference `intent=none` for doc-review, no external panel dispatched.

## Applied fixes

| # | Pri | Anchor | Finding | Fix |
|---|---|---|---|---|
| D1 | P2 | R4 / U2 / U4 | Flip-detection placement was ambiguous: R4 promised mid-poll catches "at merge time" while U4 wires only `validate` — an agent following literally might grow a poll loop inside `run()`, breaking its stateless single-shot contract | R4 now pins the division: `validate` is the point-in-time hard gate in `run()`; `watch` is the CLI/library poll utility exercised by the AC fixture and offered in U5 guidance |
| D2 | P2 | U3 Behavior | Strict newest→oldest undo sequencing conflicts with the merge revert needing `main` checked out after a checkout-undo moved HEAD | U3 now states newest→oldest governs mutation order, not HEAD; ref-sensitive steps manage their own checkout explicitly |
| D3 | P3 | U4 Goal | `--operator-confirmed undo` could trip the #526 forward mismatch rule (`confirmed != upcoming` refuses) if the undo branch forked after the gate logic | U4 now requires the `--undo` fork before the forward gate/mismatch checks |
| D4 | P3 | KTD1 | Cited `tier-session-override.json` as hosted in `.claude/saga/` — the file is absent; it is an on-demand mechanism (`tier_session.py:29`). Same phrasing mirrored in the DECISIONS entry | Both the plan KTD1 and DECISIONS `{#ceremony-sidecars-forward-only-undo-346}` now cite it as the on-demand #365 mechanism; `effort-ledger.json` verified on disk |

## Remaining findings

| # | Pri | Anchor | Finding | Status |
|---|---|---|---|---|
| D5 | P3 | KTD4 / U3 | Merge-undo pushes a revert commit directly to `main`, which assumes no branch protection — true today (verified: PR #561 merged with `reviewDecision: ""`, sole-maintainer repo) but silently breaks if protection lands | report-only — the DECISIONS entry's "revisit when" already names branch protection as the trigger to switch to a revert PR |

## Verification notes (readiness-skeptic evidence)

- Code citations checked against the live tree: `_do_merge` at `ship_ceremony.py:345-349`,
  `_do_branch_delete` at `:364-373`; grounding-brief refs `:119`/`:147` present.
- `gh pr view --json headRefOid,statusCheckRollup` field names verified against PR #561 (7 check
  contexts returned) — the U2 recorded-set baseline works in this repo, which has no
  branch-protection "required checks" set.
- R5 baseline re-verified: zero `--auto`/`--delete-branch` matches across `plugins/saga/` (all
  hits are the unrelated `--autonomous`), so the keep-clean framing is correct.
- AC `-k` patterns each map to a named test scenario in U1–U4 (substring-match checked).
- Requirement mapping: ACs 1–7 → R1–R7; AC 8 → Verification section; release checklist → R9.
  No unmapped acceptance criterion found.

Review complete
