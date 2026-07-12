# Doc Review — issue #565 backend-offer fix plan (2026-07-12)

One-line verdict: **READY** — one P1 and one P2 completeness gap found and fixed in place (with
the execution spec updated in lockstep and re-emitted); no unresolved P0/P1 findings remain.

## Review-result contract

- **Target**: `docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md`
- **Reviewed revision**: working tree (plan not yet committed; commits land on the work branch)
- **Blocked**: no
- **Linked**: issue infiquetra/infiquetra-claude-plugins#565; spec
  `docs/plans/2026-07-12-issue-565-backend-offer-fix-spec.json` (re-validated
  `--require-receipts`, re-emitted `.workflow.js` after fixes); saga `issue-565`; origin
  `docs/engineering-journal/QUEUED.md` `{#plan-backend-recommendation-broken}`
- **Rubrics**: issue-phase cores (acceptance_criteria_clarity, devils_advocate_issue,
  spec_fidelity) + extras by applicability (context_completeness, prerequisite_mapping) — no
  unresolved rubric findings; the plan traces to the issue, the issue to the QUEUED entry and
  the operator directive
- **Engine offer**: `engine_offer.py offer --stage doc-review` → stored preference, no prompt,
  no external pass

## Findings

| # | Pri | Finding | Status |
|---|---|---|---|
| F1 | P1 | `outcome_dispatcher.py:411-425` is a direct Python consumer the plan scoped out without stating the compat contract; its frontier-budget downgrade rewrites `recommended`/`alternatives`, which would leave the new authoritative `backends` enumeration contradicting the downgraded recommendation | **fixed**: KTD4 gains the explicit compat contract (additive kwargs; retained key semantics; downgrade re-stamps `backends`); U1 files + test scenarios extended (`outcome_dispatcher.py`, `tests/test_outcome_dispatcher.py`); Scope Boundaries corrected; spec U1 prompt/files lockstepped |
| F2 | P2 | U2's lockstep list missed two offer-rendering prose sites that perpetuate defect 4's alternatives-only framing: `plugins/saga/skills/work/SKILL.md:50,229-232` and `plugins/saga/skills/loop/references/drive-and-resume.md:52-56` | **fixed**: both added to U2 files with the render-from-`backends` instruction; spec U2 prompt/files lockstepped |
| F3 | P3 | KTD2's `review` shape vs the existing `adversarial_confidence` trigger was ambiguous (an implementer could merge or precedence-order them) | **fixed**: KTD2 states the split — `review` = multi-lens sweep request; `adversarial_confidence` = explicit refute-N/judge-panel; co-firing allowed, no precedence |

## Readiness summary

The plan carries verified `file:line` evidence for every load-bearing claim (all cites re-read
this session), stable R/KTD/U IDs, per-unit test scenarios in the real test homes
(`tests/test_saga_plugin.py`, `tests/test_saga_execution_spec.py`,
`tests/test_outcome_dispatcher.py` — the issue's original `tests/test_lifecycle_state.py` /
`tests/test_execution_spec.py` paths do not exist; U4 corrects the issue body), and a
dependency-serialized spec priced at 263 that validates under `--require-receipts`.

## Residual risk

- The `backends`/`alternatives` dual representation is deliberate back-compat; if a future
  consumer reads only `alternatives` for an *offer* (not an escalation list), defect 4 can
  reappear — U2's prose is the guard, and the KTD4 rejected-alternatives note records why
  `omit_ultracode` got no deprecation shim.
- Line anchors (`~:286`, `~:153`, etc.) will drift once U1 lands before U2 runs; the spec
  prompts use approximate anchors plus content descriptions, so the U2 agent must match on
  content, not line numbers.
