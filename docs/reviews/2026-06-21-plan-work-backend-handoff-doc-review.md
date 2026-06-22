---
date: 2026-06-21
target: docs/brainstorms/2026-06-21-plan-work-backend-handoff-requirements.md
revision: working tree
classification: requirements (brainstorm)
reviewer: /doc-review
blocked_for_work: yes (3 P1 findings) — but the target feeds /plan, not /work; the P1s are required planning inputs, not a /plan blocker
source_chain: docs/ideation/2026-06-21-plan-work-backend-handoff-ideation.md → docs/brainstorms/2026-06-21-plan-work-backend-handoff-requirements.md
---

# Doc Review: Plan→Work Execution-Backend Handoff Requirements

## Readiness summary

The requirements doc is well-grounded and mostly implementation-ready — the decisions are explicit, the requirements are testable, and the core direction (finish the unwired emitter; run-or-halt; provenance guard) is sound and verified against the code. It is **not yet safe to hand to `/plan` untouched**: three P1 findings are load-bearing mechanism gaps where the doc currently asserts behavior the code does not yet support, and one was a factually false scope claim (now fixed). None block `/plan` from *starting* — they are exactly what `/plan` must resolve — but each must be answered *in* planning, not deferred past it.

## Applied fixes

| fix | basis |
|---|---|
| Corrected the Scope Boundaries claim that team-execution's emitter "already feeds it; that path works" → it is **also** currently unwired (zero skill callers, verified). Added the wiring decision to Outstanding Questions. | `grep team_emitter/emit_team_structure/## Team Structure` across `plugins/saga/skills/` returns zero hits. |
| Restructured Outstanding Questions into "Resolve during planning" (the 3 P1s + team-emitter scope) vs "Deferred to planning," pointing at this review. | The findings below. |

## Findings

| pri | id | finding | status |
|---|---|---|---|
| P1 | F1 | Workflow-launch + off-host-detection mechanism unspecified/unverified | open → planning |
| P1 | F2 | KD3 (spec canonical/regenerable) contradicts R2 (only script path stored); no spec is persisted | open → planning |
| P1 | F3 | `ExecutionSpec` has no refute-N/judge primitive — the guarantee the operator lost may be inexpressible | open → planning |
| P2 | F4 | No requirement enforces KD1's "approved" step (surface emitted script/tiers before save) | open → planning |
| P2 | F5 | Round-N / re-plan behavior is an assumption, not a governed requirement | open → planning |
| P2 | F6 | R10's invariant needs field semantics pinned (`saga.py` permits `mode != operator_choice`) | open → planning |
| P3 | F7 | R4/R5 (tier capture / default derivation) lack acceptance examples | open → planning |
| P3 | F8 | prose-unit → agent-prompt derivation is flagged trivial; it is a real, lossy transform | noted |

### P1 detail

**F1 — Workflow launch + off-host detection.** R6 ("run the script") vs R7 ("halt") branches on whether `/work` can invoke the Workflow tool in its session. `/work` has no workflow-launch logic today (verified), and the doc asserts "available without ultracode mode (operator-confirmed)" without pinning the actual trigger — does a saga-recorded backend choice authorize a launch with no current-turn operator signal, and what observable signal means "genuinely absent"? If the harness needs a current-turn opt-in, R6's auto-run cannot fire and every ultracode plan hits the R7 halt (safe, but it defeats the auto-run intent). Resolve: name the launch trigger and the absence signal; if a current-turn signal is required, R6 becomes "surface a one-keystroke launch," still never a silent substitute.

**F2 — Spec persistence vs KD3.** KD3 says the spec is canonical and the `.workflow.js` is regenerable; R2 stores only the *script* path in `orchestration_ref`; and no skill persists a spec JSON (verified). As written the spec is ephemeral, so KD3's "re-emit from the spec for freshness" is impossible. Resolve: either persist the spec and point/extend `orchestration_ref` at it, or drop KD3 and declare the emitted script canonical (and then F5/round-N drift needs a different answer).

**F3 — refute-N expressibility.** Dropped refute-N verification was the operator's headline injury and a primary reason ultracode is chosen, but `ExecutionSpec` has no refute/judge/verify primitive (verified: only `fanout`/`targets`/`pilot`/`returns`/`depends_on`). A judge-panel would have to be hand-encoded as a fan-out of verifier units. Resolve: confirm refute-N round-trips through `ExecutionSpec → emit_workflow_script` into a real judge-panel before relying on the fix to preserve the guarantee — otherwise choosing ultracode still would not guarantee adversarial verification, and the fix misses its headline value.

### P2 detail

**F4 — "Approved artifact" is unenforced.** KD1's value is that `/work` runs an *approved* artifact, but no requirement makes `/plan` surface the emitted script (or its per-unit tiers/prompts) for operator confirmation before saving. Add a requirement, or "approved" is aspirational and the auto-derived tiers/prompts (R5, F8) ship unreviewed.

**F5 — Round-N / re-plan.** When a plan changes on `/work` re-entry and a stale `orchestration_ref`/script exists, the doc only gestures at "a re-plan re-emits" (KD3) with no governing requirement. Pin it (re-emit on re-plan / staleness detection), interacting with F2's persistence answer.

**F6 — R10 field semantics.** `saga.py:172` comments that `operator_choice` *can* legitimately differ from `mode` "when the operator overrides the recommendation," and the issue-38 drift was `mode=ultracode`/`choice=inline` (high vs low). R10 ("`mode != operator_choice` ⇒ needs downgrade") is plausibly the right invariant, but only once the doc pins which field is authoritative for "what actually ran" vs "what the operator picked," and which divergence directions are legitimate. Define before asserting, or R10 risks rejecting valid overrides or missing the real inversion.

### P3 detail

**F7** — Add acceptance examples for R4/R5; default-tier derivation is testable ("a judgment unit with no tier → opus/high; a mechanical unit → sonnet or haiku").

**F8** — The deferred "prose-unit → agent-prompt derivation" is framed as a trivial transform; it is the substantive, lossy part of building a good spec from prose units. Plan for it as real work.

## Residual risk from limited evidence

F1 turns partly on runtime harness opt-in behavior (whether a saga-recorded backend choice lets `/work` call the Workflow tool without a current-turn keyword), which cannot be fully verified from the repo. Treat the resolution as "verify against actual harness behavior during `/plan`," not as a settled assumption.

## Links

- Requirements (target): `docs/brainstorms/2026-06-21-plan-work-backend-handoff-requirements.md`
- Ideation (provenance): `docs/ideation/2026-06-21-plan-work-backend-handoff-ideation.md`
- Forensic basis: campps `.claude/saga/sagas/issue-38/`
