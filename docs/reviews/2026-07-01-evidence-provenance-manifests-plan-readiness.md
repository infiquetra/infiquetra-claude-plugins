# Doc-review: evidence/provenance manifests plan (#285) — readiness

**Verdict: READY — no P0/P1 remain; `/work` is not blocked.** Both operator-raised concerns were
investigated with evidence; both produced safe in-place fixes to the plan.

- **Target:** `docs/plans/2026-07-01-evidence-provenance-manifests-plan.md`
- **Reviewed revision:** working tree (plan uncommitted at review time), 2026-07-01
- **Classification:** plan (`docs/plans/`, `origin:`, U-IDs, KTDs) → readiness-skeptic pass; the
  idea/issue rubric phases do not apply to plan artifacts
- **Linked issue:** infiquetra/infiquetra-claude-plugins#285 · **Saga:** issue-285 ·
  **Spec:** `docs/plans/2026-07-01-evidence-provenance-manifests-spec.json`
- **Blocked:** no

## Operator concerns investigated

**Concern 1 — "the plan looks like it defined a team execution with agent teams."** Refuted for the
backend, confirmed as a documentation gap. The emitted
`docs/plans/2026-07-01-evidence-provenance-manifests.workflow.js` is a pure Claude Code Workflow
harness (header: "emitted Claude Code workflow harness"; `agent()` control flow; zero reviewer /
consensus / Team Structure machinery), and the saga tick records
`orchestration_mode: cc-workflows-ultracode` with the operator's explicit choice. The confusion was
legitimate: the plan never stated its own backend, and U5 wires *team-execution as a manifest
producer surface*, which read as "this build uses agent teams."

**Concern 2 — "consider Fable 5 and Sonnet 5."** Grounded via the claude-api skill (cached
2026-06-24): Claude Fable 5 `claude-fable-5`, $10/$50 per MTok, capability tier above Opus 4.8,
`xhigh` effort recommended for the hardest agentic work; Claude Sonnet 5 `claude-sonnet-5`, $3/$15
(intro $2/$10 through 2026-08-31), near-Opus on coding/agentic. Harness facts: the session's Agent
tool lists `fable` as a valid subagent model, and the `sonnet` alias resolves to `claude-sonnet-5`
(session config). Blocker found: saga's spec validator (`plugins/saga/scripts/execution_spec.py:49-50`)
accepts only `opus|sonnet|haiku` × `low|medium|high` — fable/xhigh tiers cannot validate today.

## Applied fixes (all in the plan document)

1. Added **"Execution backend (operator-confirmed)"** section: backend = dynamic workflows, the
   team-execution wording disambiguation, the verify-panel statement, and the four-step `/work`
   entry procedure (U0 → retier spec → re-validate/re-emit → launch, with an opus/high fallback).
2. Added **KTD10** (Claude 5 tier decision with pricing facts and the U0 gate) and **U0** (extend
   `MODELS` with `"fable"`, `EFFORTS` with `"xhigh"`, plus tier round-trip tests in
   `tests/test_workflow_emitter.py` / `tests/test_team_emitter.py`).
3. Retiered **U1 and U3 to fable/xhigh** in the per-unit tier table (was opus/high); noted the
   sonnet-alias → Sonnet 5 upgrade for the mechanical units; made the verify-panel line declarative
   (backend now confirmed).
4. Retitled **U5** "…(product surface, not this build's execution backend)".
5. Renamed the U4 contract-less-leaf test to
   `test_completeness_contract_bearing_exempts_contract_less_leaf` so both AE3 halves match the
   issue's `-k completeness_contract_bearing` acceptance selector.

## Remaining findings

| # | Priority | Status | Finding |
|---|---|---|---|
| F1 | P2 | fixed | Plan stated no execution backend; U5 invited the team-execution misread (operator concern 1). |
| F2 | P2 | mitigated (deliberate) | Model tiers predated Claude 5. Plan now retiers U1/U3, but the on-disk spec JSON and `.workflow.js` intentionally keep opus/high — fable tiers cannot pass `validate` until U0 lands, so the checked-in artifacts are the valid-today fallback. `/work` regenerates both after U0 (documented in the plan). |
| F3 | P3 | fixed | One U4 test name missed the issue's `-k completeness_contract_bearing` selector. |
| F4 | P3 | open (residual risk) | `fable` as a *workflow-subagent* model is evidenced by the Agent tool enum but not yet exercised through the Workflow dispatch path end-to-end. Fallback documented: revert U1/U3 to opus/high, re-validate, re-emit, record the downgrade in the saga tick. |

## Residual risk from limited evidence

- F4 above — resolves at the first fable-tier dispatch in `/work`; failure mode is a one-line spec
  revert, not a redesign.
- Fable 5 requests may return `stop_reason: "refusal"` on classifier-flagged content (claude-api
  skill). This plan's material (provenance schemas, gate wiring) is far from the flagged domains;
  noted only because U1/U3 move onto that model class.
