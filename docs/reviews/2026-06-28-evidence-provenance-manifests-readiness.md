---
date: 2026-06-28
target: docs/brainstorms/2026-06-28-evidence-provenance-manifests-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review)
verdict: READY
blocked: false
---

# Readiness Review — Evidence / Provenance Manifests

## Verdict

**READY for `/plan`** after a heavy fix pass. As first written the doc was *not* plan-ready — all three
engines independently raised `P0`s, and codex (repo access) put it plainly: it "treats unbuilt S-4/S-7
proposals as existing consumers while deferring the schema and sequencing decisions that would make
those consumers real." Sixteen evidence-backed fixes were applied in place. No `P0` or `P1` remains:
the framing now states honestly that R11 *defines a contract* two scheduled gate consumers will read
while its advisory consumers are live today, the manifest is restructured as one envelope with two
subrecords, and the parroting signal is scoped to an actual contradiction. Remaining open items are
genuine `/plan` design choices (schema, carrier, build-sequencing), recorded as Outstanding Questions —
not readiness gaps.

## Method

Reviewed as a requirements artifact (readiness-skeptic pass; no formal SDLC rubric applies to a
brainstorm doc). Adversarial depth came from a **three-engine panel as gated generators under
Claude-side verification** — every finding was verified against the doc or repo source before adoption;
nothing was adopted on an engine's say-so:

- **Codex / gpt-5.5** at `xhigh`, read-only, with repo access (verified the file:line claims directly).
- **agy Gemini 3.1 Pro (High)**, hermetic (doc inlined).
- **agy Gemini 3.5 Flash (High)**, hermetic (doc inlined).

The cross-family panel earned its keep on every axis. **Four-way convergence** (all three engines plus
the Claude-side pass) on the parroting over-classification. **Three-way convergence** on "two records
sharing a name" → the envelope/two-subrecords reframe. Codex's repo access alone caught two citation
errors and the S-7 opportunistic-boundary over-reach the hermetic engines could not see. And one Flash
`P2` was **refuted** by repo evidence — the reason Claude-side verification is mandatory.

## Applied fixes

All evidence-backed; the doc was edited in place.

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | Parroting scoped to claimed-`verified` + adjudicated-`refuted`/`unsupported` only; added a `mismatch_reason` taxonomy (`not-adjudicated`/`scope-excluded`/`source-stale`/`unsupported`) (R7, D2, AE1-2) | Pro P0 + Flash P0 + Codex P1 (4-way) | benign-divergence logic; `built-vs-planned.md:58-59` |
| 2 | "One manifest, two readers" → one **envelope** with `output_completeness` + `claim_provenance` subrecords; each consumer reads one (D4, R1-4, R13-14) | Codex P1 + Pro P1 + Flash P1 (3-way) | S-7 already names its half a "manifest diff" (#277:148); field-sets verified disjoint |
| 3 | Reframed S-7/S-4 gates as **scheduled, not existing**; R11 defines the contract, advisory consumers are live today (D3, D7, A3/A4, Dependencies) | Codex P0 ×2 | #277/#283 are OPEN proposals (verified via `gh`) |
| 4 | R10 scoped to **contract-bearing** delegated leaves (not every leaf) | Codex P1 | S-7 check is "opportunistic … v1 does not require a contract on every leaf" (#277:104-105, verified) |
| 5 | R12 clarified: R11 adds **no gate of its own**; inline/exploratory never blocked | Flash P1 + Pro P0 + Claude C4 | S-7 is delegated-only by design (#277:60,219,235, verified) |
| 6 | Added R17 — a **producer/consumer matrix** per field (producer, reader, live-vs-scheduled); no-reader fields stay out of schema | Codex P1 | `saga-spec.md:274-278` unknown-key preservation = silent-persist mechanism |
| 7 | Inline Claude does not self-attest, but the **adjudication record is attested** (`adjudicator/source/scope/revision/decision`) (D5, R6, AE5) | Codex P2 + Pro P2 + Flash P2 + Claude C5 (4-way) | makes R15's trust-skip safe without who-verifies-the-verifier regress |
| 8 | `not-checkable` (no source ref) is a distinct protocol state, excluded from parroting (R4) | Pro P1 | conflation with `not-checked` would mis-tally protocol errors as parroting |
| 9 | Payload sized to tier — full adjudicated manifest only at gated/contract-bearing outputs; lightweight metadata for advisory (R9) | Codex P2 + Claude C2 | prices the "every delegated output" overhead honestly |
| 10 | Adjudication granularity decided: per-claim for gate-relevant/consumed claims (removed the R15-vs-Outstanding contradiction) | Codex P1 | R15 per-claim vs Outstanding per-output were inconsistent |
| 11 | Each producer-claimed status must carry a defined gate-effect; `verified\|unverified` collapse flagged to `/plan` (R5) | Codex P1 + Flash P2 | `inferred` vs `not-checked` under-defined for gating |
| 12 | Carrier must be cross-session readable (git-common-dir cache); typed key + reader contract required before selecting `CompletionEvent.payload` (R19) | Codex P1; Flash P2 (premise refuted) | `outcome_store.py:93-148` (cross-worktree), `:252-296` (open dict) |
| 13 | Citation corrected: `orchestration_downgrade` produced in `lifecycle_state.py:238-304`, guarded/persisted in `saga.py:630-687`, consumed in `override_rate_reader.py` | Codex P2 | verified all three directly |
| 14 | Citation reframed: `saga-spec.md:274-278` is forward-compat unknown-key preservation, not a "trap" | Codex P2 | verified §3.5 text |
| 15 | Noted S-4 team-execution external-wrapper context contract as an upstream prerequisite (R14, Scope, Deps) | Codex P1 | S-4 doc `:323-327` marks it a prerequisite |
| 16 | Problem Frame separates "existing prose habit" from "existing durable machinery" | Codex P3 | the four skills are prose; `orchestration_downgrade`/`validator-evidence-state` are machinery |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P0 | Unbuilt S-4/S-7 treated as existing consumers | Codex | Fixed (D3/D7, A3/A4, Deps) |
| P0 | Parroting over-classified (claimed≠adjudicated ≠ parroting) | Pro + Flash + Codex(P1) | Fixed (R7 taxonomy) |
| P1 | "Two records sharing a name" | Codex + Pro + Flash | Fixed (D4 envelope/subrecords) |
| P1 | R10 over-reaches S-7's opportunistic boundary | Codex | Fixed (R10 contract-bearing) |
| P1 | Dead-wiring: fields' consumers are future docs | Codex | Fixed (R17 matrix) |
| P1 | Adjudication granularity contradiction | Codex | Fixed (per-claim decided) |
| P1 | `inferred` vs `not-checked` under-defined | Codex + Flash | Fixed (R5 gate-effect + /plan flag) |
| P1 | Carrier not a consumer surface / cross-session | Codex | Fixed (R19) |
| P1 | `not-checkable` conflated with `not-checked` | Pro | Fixed (R4) |
| P1 | S-4 team-execution wrapper not a real consumer yet | Codex | Fixed (R14/Deps prerequisite) |
| P1 | R10 vs R12 contradiction / inline auto-fail | Flash + Pro | Fixed (R12, delegated-only) |
| P2 | Inline-Claude adjudication unattested | Codex + Pro + Flash | Fixed (D5 attested adjudication) |
| P2 | "Every delegated output" unpriced overhead | Codex + Claude | Fixed (R9 tiered payload) |
| P2 | Citation: `saga.py` mislabeled as downgrade writer | Codex | Fixed (D1/Sources) |
| P2 | Citation: `saga-spec.md:277` mislabeled a "trap" | Codex | Fixed (D1/Sources) |
| P3 | Problem statement conflates habit with machinery | Codex | Fixed (Problem Frame) |
| — | Carrier registry needs new store (contradicts D1) | Flash | **Refuted** — git-common-dir cache is the existing cross-session carrier (`outcome_store.py:93-148`) |
| — | Split into two separate manifests | Flash | **Refined**, not adopted — one envelope/two subrecords preserves single production point + lifecycle |

## Residual risk

- **The two gate consumers (S-7 #277, S-4 #283) are unbuilt**, so R11's *gating* value is unproven
  until they land. Mitigated three ways: the advisory consumers are live today; the contract is defined
  so the gates inherit it rather than reinventing it; build-order is an explicit `/plan` decision (D7).
- **Per-claim adjudication cost at scale is untested.** The doc argues the mandatory half is already
  paid (gates already verify in prose) and sizes advisory payload down, but only operator use will
  confirm the overhead is acceptable.
- **The producer/consumer matrix is required (R17) but its concrete per-field code owners are `/plan`
  work** — the dead-wiring guard is now a hard requirement, not yet a proven wiring.

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`), same pipeline as S-1 (#275), S-7 (#277), S-5 (#278), S-2 (#279), S-3 (#281),
S-4 (#283). Recipient action: `/plan` (requirements-ready; the Outstanding Questions are the planning
agenda, with build-sequencing of the three issues the first item).
