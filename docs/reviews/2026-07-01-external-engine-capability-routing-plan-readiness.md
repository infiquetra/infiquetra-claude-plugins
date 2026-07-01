---
date: 2026-07-01
target: docs/plans/2026-07-01-external-engine-capability-routing-plan.md
reviewed_revision: working tree (plan uncommitted)
review_type: plan readiness (saga /doc-review)
verdict: READY
blocked: false
linked_issue: infiquetra/infiquetra-claude-plugins#283
linked_saga: issue-283
---

# Readiness Review — External-Engine Capability Routing (plan)

## Verdict

**READY for `/work`, not blocked.** No `P0` remains and no `P1` remains after fixes. The plan can safely
drive implementation: every requirement R1–R26 maps to a unit (R12 explicitly deferred to U12), the
resolver contract is now deterministic, and Claude-verifier-of-record is enforced structurally rather
than merely asserted. One `P2` (the capability tie-break, KTD9) is resolved with a deterministic
default but flagged for explicit operator confirmation — it does not block execution.

## Method

Readiness-skeptic pass (no formal SDLC rubric applies to a plan doc). Adversarial depth came from two
independent passes under **Claude-side verification** — every finding was checked against the plan or
repo source before adoption, nothing on an engine's say-so:

- **Claude self-review** (adversarial framing against a self-authored plan) — surfaced the two `P1`s.
- **Codex / gpt-5.5** (read-only, repo access) — dispatched via `codex:codex-rescue`, dogfooding the
  R16 external-reviewer pattern this plan proposes. Its repo access caught a citation error the
  self-review missed, and it surfaced four additional real gaps.

The cross-family lens earned its keep: Codex confirmed the tie-break gap the self-review had already
flagged (independent corroboration), caught a wrong file:line the self-review propagated from its own
grounding agent, and one Codex `P1` was **refuted** against the plan text (the reason Claude-side
verification is mandatory).

## Applied fixes

All evidence-backed; the plan was edited in place.

| # | Pri | Finding | Source | Fix |
|---|---|---|---|---|
| 1 | P1 | Operator surface for R18/R19/R20 under-specified — an implementer could invent a `/engine` command | Claude | Added an explicit "Operator surface" note (declarative `engine`/`capability` unit fields + doc-review panel opt-in) + a matching Scope Boundary |
| 2 | P1 | Codex read-only containment (KTD6/R23) hinged on a mode the `codex:codex-rescue` forwarder does not enter for a code-gen task (it defaults to `--write`) — silently running the rejected uncontained posture | Claude | Pinned the explicit read-only framing + a `git status --porcelain` before/after guard treating any Codex tree-write as a contract breach |
| 3 | P1 | `recommend_execution_backend(advisory_consensus=…)` — no such parameter; would `TypeError` | Codex | Corrected to `needs_consensus=True, consensus_is_gated=False`; noted `advisory_consensus` is computed internally (`lifecycle_state.py:99-113`) |
| 4 | P1 | Resolver request had no `role_kind` discriminator, yet fallback (R8, worker/generator) vs halt (R17, reviewer/panel) depends on it | Codex | Added `role_kind` to the request schema; specified role-gated fallback-vs-halt in U2 |
| 5 | P2 | `Unit.engine` ambiguous — held an engine but the surface claimed "engine or capability" | Codex | Split into mutually-exclusive `engine:` / `capability:` fields; `from_dict` rejects both-set; added a test |
| 6 | P2 | R13 (verifier-of-record) asserted as policy but not structurally enforced in the dispatch/emit path | Codex | Added an `advisory-evidence` result type that cannot satisfy a gated return without a Claude verification stamp (U4) |
| 7 | P2 | U4 dispatch tests omitted the wrapper failure statuses (timeout, no-output, error, malformed, agy clone failure) that the wrappers actually return | Codex | Added a failure-mode test per wrapper status → halt + provenance, no gated verdict (`agy_delegate.py:441-498, :745-788`) |
| 8 | P2 | Citation error: `saga-spec.md:176-180` for `orchestration_downgrade` — those lines are `status`/`maturity` | Codex | Corrected to `saga-spec.md:121-125` (field at :125), verified directly |
| 9 | P2 | agy `--model` verbatim canonical string not captured in the registry schema (only Codex shown) | Claude | Added the `invocation.model` verbatim-string rule for agy entries (`agy_delegate.py:1519-1542`) |
| 10 | P2 | Preflight conflated presence with auth; `--version` ≠ authed, rate-limits undetectable cheaply | Claude + Codex | Clarified preflight is best-effort presence+config; relocated rate-limit/auth test expectations to U4 dispatch-time halt |
| 11 | P2 | Delegation Map framed as capability routing, but the seed profile could resolve `code-generation` to Gemini Flash | Claude | Reframed as explicit-engine (R19) requests |

## Remaining findings

| Priority | Finding | Status |
|---|---|---|
| P2 | **Capability tie-break (KTD9).** When ≥2 variants rate a capability equally, the resolver needs a deterministic order. | **Resolved & operator-confirmed 2026-07-01 → cost·speed** (cheapest-fastest; registry order as final backstop). Consequence folded in: the registry schema gains an integer `cost_speed_rank` field (U1 validated, U7 seeded) so the ordering is well-defined. |
| P3 | U8 does not name the saga version to bump (currently ~0.43.0). | Open — a work-time detail. |

## Refuted (not adopted)

- **Codex P1.2** — "R10/R12 traceability claims full coverage while deferring team-execution." Refuted:
  the plan already marks R12 **Deferred (U12 follow-up)** in both the traceability table and Scope
  Boundaries, and scopes R10 to inline + cc-workflows — which is exactly Codex's recommended fix.

## Residual risk

- **The `cost_speed_rank` seed values (KTD9) are operator-assigned ordinals, not measured.** They make
  the tie-break deterministic; like the rest of the seed data they drift and are re-validated by use
  (R21), not by a measurement loop.
- **The `advisory-evidence` enforcement (fix #6) is a design requirement, not yet code.** Its real proof
  is U4's "cannot satisfy a gated return without a Claude stamp" test landing green.
- **Codex read-only containment (fix #2) depends on the `git status` guard actually running each round.**
  The guard is specified in the plan; discipline at `/work` time is what makes it real.

## Next step

`/work #283` — execute inline to a merge-bound PR (destination `merge`, backend `inline` on saga
`issue-283`). No override needed and no open operator decisions: KTD9 is confirmed (cost·speed). The
only remaining item is a `P3` (name the saga version to bump), which is a work-time detail.
