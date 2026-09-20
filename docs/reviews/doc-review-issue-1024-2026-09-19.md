# Document review: issue 1024 roster helper plan

**Target:** `docs/plans/2026-09-19-issue-1024-roster-helper-plan.md`
**Reviewed revision:** working tree, on branch `issue/1024` at base commit `0fa2ea32`
**Linked issue:** `infiquetra/infiquetra-claude-plugins` issue 1024, child of issue 1018
**Blocked:** no
**Rounds:** two, plus a re-read; no finding was weakened to close a round

## Readiness summary

The plan can drive implementation. Eight findings were raised in the first round and one more in
the second; all nine were repaired in place from evidence already in the card, the sibling code on
this branch, or the herdr command surface read live from the binary. Nothing remains at P0 or P1.

The two checks the repository runs against a plan document both pass at the reviewed revision: the
plan-artifact conformance pass (`plugins/saga/scripts/plan_artifact_conformance.py`) exits 0 with no
finding against this document, and the gate-absence lint
(`plugins/saga/scripts/lint_gate_absence_contract.py`) exits 0 with zero violations.

## Findings

| Key | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The card's three acceptance criteria were never mapped to the units that satisfy them, so a reader could not tell which unit proves what | fixed in place: a mapping table plus a runnable verification block |
| D2 | P1 | `--record <path>` (the card's flag) and `run_record.py`'s store-root-plus-issue interface were left unreconciled, so the implementer would have had to invent the resolution | fixed in place as KTD10 |
| D3 | P1 | `up` was not idempotent; re-running it after an interruption would have created a second set of panes and orphaned the first | fixed in place as R12, with a test scenario |
| D4 | P1 | The launcher's staged-input stop (`prompt_delivered: false`) was unhandled, leaving a session created but unbriefed with no stated response | fixed in place as R13, with a test scenario |
| D5 | P1 | Two Lens Reviewer seats would have resolved to the same pane name, and the launcher splits a pane rather than failing on a duplicate tab label — a silent wrong result | fixed in place: a per-seat naming rule and a pre-launch collision refusal |
| D6 | P2 | The launch receipt location was shown only in an example; a receipt written inside a worktree disappears when issue 1025's driver removes that worktree, after which `down` cannot prove ownership and the panes leak | fixed in place as KTD9 |
| D7 | P2 | Nothing prevented the helper from closing the coordinator's own pane if a record named it | fixed in place as R14, with a test scenario |
| D8 | P3 | The plan did not name its descent — the card, the parent, the objective-plan section, and the review recommendation | fixed in place: a "Source and descent" section |
| D9 | P3 | The concurrency ceiling said "refuse" without saying why a partial roster is not an option | fixed in place: R11 now states the reason |

## Lenses applied

The three always-apply issue-phase rubrics were run against the plan
(`lifecycle_review.py rubrics list-cores --phase issue`): acceptance-criteria clarity, which produced
D1; devil's advocate, which produced D3, D4, D5, and D7; and spec fidelity, which produced D8. The
readiness-skeptic pass produced D2, D6, and D9. Deployment-readiness scrutiny applies here in a
narrow form — the plan performs a destructive operation on the operator's live terminal server — and
that is the lens that drove D5, D6, and D7 to their priorities.

No external-engine panel was dispatched; this is not a cross-family artifact and no operator asked
for one.

## Residual risk from limited evidence

Two things in the plan are read from a live system rather than from a committed contract, and could
move under it. The herdr command surface (subcommands, flags, and the JSON shape of
`herdr agent list`) was read from `herdr 0.9.0` on this machine on 2026-09-19; a herdr upgrade could
change it, and the plan's own defence is that the tests inject a fake runner and assert on the
argument vectors the helper builds. The staffing registry's role rows and the roles library's index
are both files on this branch; the plan's KTD2 drift test is what turns a change in either into a
test failure rather than a briefingless session.
