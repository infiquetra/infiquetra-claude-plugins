# Readiness Review — Capability-Scoped Agent Sandbox Plan

**Verdict: READY — all findings resolved.** Five evidence-backed safe fixes landed in the review
pass; the three remaining findings were discharged in an operator-directed fix-all pass
(2026-07-02, same session) by amending the plan and posting the #293 ordering note.

## Review-result contract

- **Target:** `docs/plans/2026-07-02-capability-scoped-sandbox-plan.md`
- **Reviewed revision:** working tree (plan uncommitted, authored same session)
- **Blocked:** no
- **Linked issue:** infiquetra/infiquetra-claude-plugins#287
- **Origin requirements:** `docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md`
- **Review artifact:** `docs/reviews/2026-07-02-capability-scoped-sandbox-plan-readiness.md` (this file)
- **Mode:** inline single-reviewer (operator-directed, no agents); rubric engine skipped — it has
  no `plan` phase (`plugins/saga/references/rubrics/{idea,issue,spec}` only), so the
  readiness-skeptic pass is the review

## Applied safe fixes

All five are supported by repository evidence cited in the fix.

| # | Fix | Evidence |
|---|---|---|
| F1 | U2 named only two verifier-emitting sites; there are **three** — added the parallel-layer thunk's inlined iterate-to-consensus loop, plus a test scenario covering all three emission shapes | `execution_spec.py:735-760` builds its own `verifier_opts`, distinct from `_emit_verify_panel` (`:864`) and `_emit_verify_loop_singleton` (`:808`) |
| F2 | U3 claimed `validate` raises on unenforceable routing — `validate` is backend-agnostic; reworded enforcement to the consumers (`team_emitter.emit` raises, `emit_workflow_script` wires opts, dispatcher probes) | `ExecutionSpec` carries no backend; backend binding happens at emit/dispatch |
| F3 | U3 matrix was silent on `fork`/`subagent`/`goal`/`manual`; added the unlisted-backend default: unenforceable ⇒ halt, unknown never means permissive | `outcome_spec.py:82` `NODE_BACKENDS` (7 backends); plan R4 halt-not-downgrade already implied it |
| F4 | U4 test location was an open "or"; pinned to new `tests/test_sandbox_spawn_sites.py` | open-choice pressure; naming convention `tests/test_*` |
| F5 | U5 manifest attribution left schema-version impact unstated; defaulted to optional absent-tolerant field, **no** `SCHEMA_VERSION` bump | `provenance_manifest.py:359-360` strict-equality version check; U1 absent-key round-trip precedent |

## Readiness summary

The plan's distinguishing strength is its drift audit: every load-bearing issue premise was
re-verified against the 2026-07-02 tree, and the two falsified premises (S-4/R11 "unbuilt", the
`capability` field name) are corrected with citations. Requirements map cleanly: issue
R1–R19 → plan R1–R10 → U1–U7, with the issue's six acceptance `-k` selectors each landing in a
named unit (clobber_contained/capability_axes → U6, enforce_halt → U3/U5, sandboxed_harvest → U5
plus existing agy suites, spawn_site_inventory → U4). Scope decisions ("wire don't build",
codex-halts, team-execution authoring-time halt) are recorded as KTDs with revisit conditions in
`DECISIONS.md` `{#capability-sandbox-plan-stance}`.

## Remaining findings

None open. Resolution record from the fix-all pass:

| Priority | Finding | Resolution |
|---|---|---|
| P2 | Enforcement hinges on harness-registry literals (`saga:readonly-verifier`, `isolation: 'worktree'`) — a rename on either side would silently un-enforce with tests green. | **Resolved** — split into both halves: U2 gained a saga-side literal-consistency guard test (emitted `agentType` derived from / asserted against the agent definition's `name:` frontmatter), and the plan gained a Verification section carrying the harness-side live spawn smoke into `/qa` acceptance (agent resolves, toolset lacks Edit/Write, cwd is a worktree). |
| P2 | #293 (verify-panel robustness) edits the same emitter functions; semantic merge-conflict risk. | **Resolved** — ordering decided: #287 lands first, #293 plans against the post-#287 emitter. Recorded in the plan's Risk Analysis and posted on #293 (issuecomment-4867720587). |
| P3 | Ad-hoc Agent-tool spawns outside skills remain prose-guarded (issue D5 targeted posture). | **Resolved to instruction-guarded** — U4 now ships the ad-hoc spawn rule in `sandbox-spawn-sites.md` plus a repo `CLAUDE.md` pointer, so every context-reading agent sees the rule; structural enforcement for ad-hoc spawns stays out of v1 by design. |

## Residual risk from limited evidence

Native `isolation: 'worktree'` semantics (auto-provision, auto-clean-if-unchanged, `.git`
sharing) are taken from the harness tool contracts and were not exercised live during this
review; KTD7's residual-risk framing depends on them. The U6 mechanism test builds its own real
worktree, so the load-bearing containment claim is independently proven, but the
harness-managed lifecycle itself is verified only at `/qa`.
