---
title: Doc-review — tier floors & backend enforceability plan
target: docs/plans/2026-07-06-tier-floors-enforceability-plan.md
reviewed_revision: working tree
blocked: false
date: 2026-07-06
linked_issue: infiquetra/infiquetra-claude-plugins#369
linked_plan: docs/plans/2026-07-06-tier-floors-enforceability-plan.md
---

# Doc-review — tier floors & backend enforceability

**Readiness verdict: READY to drive implementation. Not blocked.** All findings were safe,
evidence-backed, and fixed in place (per operator instruction to fix every finding, not just P0/P1).
No P0/P1 remain; nothing is left as an open finding.

## Applied fixes

| # | Priority | Finding | Fix |
|---|----------|---------|-----|
| 1 | P2 | U1 claimed `unenforceable_tier` should "serve both the Unit and Node houses," but `outcome_spec.Node` (`outcome_spec.py:187`) carries no `{model,effort}` tier — building that generality would be dead-wiring. | Rewrote U1 to take an execution-spec `Tier` only, with the Node-has-no-tier evidence cited. |
| 2 | P2 | Plan never stated #369's open/closed disposition given partial (mechanisms 1&2) delivery. | Added an **Issue disposition** subsection: file a mechanism-3 follow-up at merge, keep #369 open (or close pointing at it), use `re #369` in the PR body to avoid auto-close. |
| 3 | P3 | U3 test scenario implied `emit_team_structure` could be driven with an `inline` backend, but it is team-execution-only (no backend param). | Clarified that the "passes on enforcing backend" half is a helper-level assertion in U1, and the team_emitter test owns only the HALT branch. |
| 4 | P3 | `min_tier` validation behavior for an on-palette-but-unrunnable floor (e.g. `haiku/xhigh`) and clamp safety were unstated. | Added to KTD3: the floor validates as a normal tier (so `haiku/xhigh` halts), and the per-axis clamp cannot produce an unrunnable pair. |

## Verification performed

- All cited line anchors re-confirmed against current code: `SANDBOX_ENFORCEABLE_BY_BACKEND:115`,
  `unenforceable_sandbox_axis:588`, `segment_units:1525`, `strongest("model",…):1618`, team_emitter
  sandbox-halt `:217/:220`.
- No symbol collisions: `TIER_ENFORCEABLE_BY_BACKEND`, `unenforceable_tier`, `min_tier` are absent
  from `plugins/saga/scripts/` today.
- Enforceability basis confirmed: team-execution agent frontmatter models = `{opus, sonnet, haiku}`,
  no `fable`; `fable` ceiling is `xhigh` so `fable/xhigh` is a valid-but-unenforceable tier.

## Residual risk

Low. The plan builds on proven in-repo patterns (the sandbox matrix, optional-field round-trip, the
#370 palette ladder ops) and cites live anchors. The one judgment call — deferring mechanism 3 — is an
explicit operator decision (KTD5) with the dead-wiring rationale recorded.
