# Doc review — issue #526 operator-confirm gate plan

**Verdict: READY.** All findings fixed in place (operator instructed "fix all issues found, not
just P0/P1"); nothing remains open and `/work` is unblocked.

- **Target:** `docs/plans/2026-07-11-issue-526-ship-ceremony-operator-gate-plan.md`
- **Reviewed revision:** working tree (plan uncommitted; rides the work branch), 2026-07-11
- **Blocked:** no — zero unresolved P0/P1
- **Linked issue:** infiquetra/infiquetra-claude-plugins#526
- **Linked spec:** `docs/plans/2026-07-11-issue-526-ship-ceremony-operator-gate-spec.json`
  (re-validated `--require-receipts` and workflow re-emitted after the sync fix)
- **External second opinion:** offered per `engine_offer.py` (`prompt_required`), operator chose
  `none`; preference persisted to `.saga/engine-prefs.json`
- **Rubric engine:** not applicable — plan-phase document; readiness-skeptic pass ran (the
  idea/issue rubric phases cover blueprints/ADRs and issues, not plans)

## Findings

| Key | Priority | Status | Finding |
|---|---|---|---|
| D1 | P1 | fixed | U1 scenario 6's existing-test census was wrong: it listed `test_parity_git_surface_vs_work:284`, which calls no `run()` at all (a phantom edit target), and missed the two other tests that do cross gated steps — `test_already_complete_ceremony_is_a_noop:268` (loops all 7 transitions) and `test_merge_before_open_pr_is_a_named_failure:502` (must pass `operator_confirmed="merge"` or the new refusal fires before the `pr_refs` guard the test exercises). Implementing from the document literally would have produced red CI plus a confusing no-op edit. |
| D2 | P3 | fixed | The flag-on-completed-ceremony edge was unstated: `run(operator_confirmed=...)` after all transitions have run must still return `already shipped` (the `upcoming is None` early return at `ship_ceremony.py:404-405` precedes the gate). Added as scenario 7 and folded into KTD3's ordering language. |
| D3 | P3 | fixed | The ExecutionSpec's U1 prompt said "the six test scenarios" — stale the moment scenario 7 landed. Reworded count-free and pointed at the plan's census; spec re-validated, `.workflow.js` re-emitted so the canonical artifact and emitted script cannot drift. |

## Applied fixes

1. Rewrote U1 scenario 6 from the verified census of all 14 `SC.run(` call sites in
   `tests/test_ship_ceremony.py`: four tests cross gated steps (`:238`, `:268`, `:255` — its 4th
   call executes `merge` — and `:502`); every other call site stops at reversible steps.
2. Added U1 scenario 7 (flag on a completed ceremony → `already shipped`, unchanged) and the
   matching KTD3 clause placing the gate after the `upcoming is None` early return.
3. Synced the spec's U1 prompt to the census wording; `execution_spec.py validate
   --require-receipts` OK; workflow re-emitted.

## Evidence base

Full read of `plugins/saga/scripts/ship_ceremony.py` (590 lines) and the gate-relevant regions of
`tests/test_ship_ceremony.py` (33 tests; `SC.run(` census via grep), plus live verification of
every `path:line` citation in the plan (tier table `:95-103`, `run()` `:393-424`, CLI boundary
`:583-585`, `start()` `:427-482`, drift-guard pin `tests/test_saga_plugin.py:48`, guidance
surfaces `plugins/saga/skills/work/SKILL.md:528-541` and
`plugins/saga/skills/work/references/pr-continuation-loop.md:99-104`, version `0.75.23` across
`plugin.json` / `marketplace.json:86` / `CHANGELOG.md:3`). Confirmed no code caller of
`ship_ceremony.py run` exists outside tests (saga.py mentions are comments only).

## Residual risk

None from limited evidence — every claim in the plan was checked against the live tree this
session. The one behavioral assumption left to implementation is argparse's exact error text for
an off-palette `--operator-confirmed` value (`choices=TRANSITIONS`), which scenario coverage does
not pin; it is cosmetic.
