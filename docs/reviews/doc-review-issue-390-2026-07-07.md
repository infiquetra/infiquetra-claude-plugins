# Doc review — no-silent-Claude-fallback plan (#390)

**Target:** `docs/plans/2026-07-07-no-silent-claude-fallback-plan.md`
**Reviewed revision:** working tree on `main@5d45bed` (plan not yet committed)
**Blocked:** no — all findings fixed in place; plan is ready to drive implementation
**Owning saga:** `issue-390` · destination merge · backend `cc-workflows-ultracode`
(`docs/plans/2026-07-07-no-silent-claude-fallback-spec.json`)
**Mode:** fix-all-severities (P0–P3), per operator instruction

## Verdict

Ready. One P1 (ungrounded classifier leg in U1) and three lower-severity accuracy issues were
found; all four were evidence-backed safe fixes and were applied to the plan, with the P1's
mirror applied to the spec's U1 prompt followed by re-validate → re-emit → re-patch (12 verifier
guardrail inserts, JS syntax-checked). No unresolved findings remain.

## Findings and dispositions

| # | Priority | Finding | Status |
|---|---|---|---|
| F1 | P1 | Plan U1 (and spec U1 prompt) keyed the coercion off "transcript classification is `fallback_suspected`" — but `classify_transcript` has NO run-path call site in the wrapper (`agy_delegate.py:995` is fixture-parity only; #384 moved transcript auditing to the fleet-core Stop-hook). A literal implementer would hunt for a nonexistent call site or re-introduce in-run transcript auditing #384 deliberately kept out. | FIXED — U1 re-keyed to `_real_agy_verdict` (`:1627-1635`) at the `_result_payload` assembly point (`:1416-1454`, call sites `:415/:474/:612`); explicit prohibition added; bogus test scenario replaced with a no-double-coercion (marker-path `:1374`) scenario. Spec U1 prompt mirrored; spec re-validated + re-emitted + guardrail re-patched. |
| F2 | P2 | Risks section cited `engine_dispatch.py:97` as the saga envelope author setting `provenance_required: True` — stale issue-body line; actual site is `:146`. | FIXED — citation corrected in Risks and Sources. |
| F3 | P3 | Problem Frame named "the supervised provenance classifier (`:1620-1635`)" — the function is `_real_agy_verdict` at `:1627-1635`; `:1620` region is the supervision-report builder. | FIXED — named and re-cited precisely; Sources updated (added `:1374`, `:1416-1454`). |
| F4 | P3 | R5's verification grep (`pm.Disposition.SUBSTITUTED_ENGINE`) cannot match the bare enum definition the requirement said it would find. | FIXED — R5 reworded to what the grep actually proves. |

## Readiness-skeptic checks that passed

Every remaining `path:line` citation in the plan was re-verified against the tree this session:
`AdvisoryEvidence`/builder/gate (`engine_dispatch.py:41-55,146,197-207,443-506,585-625`),
`Disposition` enum (`provenance_manifest.py:54-71`), `record-completeness` missing-output axis
(`manifest_store.py:249-363`), reader report surface (`manifest_reader.py:211` `format_report`),
run-fact-ledger writer ownership (`run_ledger.py` docstring → #386/#393), emitter verdict/panel
regions (`execution_spec.py:1326-1439`), hand-build doc site (`external-engine-workers.md:174`),
ladder region (`sandbox-spawn-sites.md:50-80`). All named test homes exist
(`test_agy_delegate_contract.py`, `test_saga_engine_dispatch.py`, `test_manifest_reader.py`,
`test_manifest_consumer_matrix.py`, `test_saga_execution_spec.py`, plugin drift guards ×3). The
plan's deliberate deviations from the stale 2026-07-03 issue body (no `DELEGATION_NOOP` — zero
repo-wide hits; no auto-commit flow — `/optimize` shed its own; corrected test homes) were
confirmed as accurate corrections, not drift. Binding constraints honored: #283 (every change
fails loud, none grants engine authority), #318, ladder attribution-only, #388 seam (resolver and
registry untouched — R2's `expected_identity` threads through `dispatch()` evidence only).

## Adversarial pass

U3 and U5 both edit `external-engine-workers.md` — serialized chain plus U5's "additive, do not
undo U3" instruction covers the collision. U2/U4 both touch `test_saga_engine_dispatch.py` —
serialized. The workflow's 12 verifier prompts all carry the Wave-A materialization mandate
(branch `fix/390-no-silent-claude-fallback`, quoted examined-sha), so panels cannot vacuously
judge `main`. Residual risk from limited evidence: the emitted verdict schema was not exercised
against a live panel this session — mitigated by the #384 precedent running the identical
prompt-patch mechanics to a merged PR.

## Links

Plan: `docs/plans/2026-07-07-no-silent-claude-fallback-plan.md` ·
Spec: `docs/plans/2026-07-07-no-silent-claude-fallback-spec.json` ·
Workflow: `docs/plans/2026-07-07-no-silent-claude-fallback.workflow.js` ·
Issue: infiquetra/infiquetra-claude-plugins#390 (+#392 facet) ·
Decisions: `docs/engineering-journal/DECISIONS.md` `{#no-silent-claude-fallback-390}`
