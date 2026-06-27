---
date: 2026-06-27
kind: doc-review
target: docs/brainstorms/2026-06-27-operator-gate-status-card-requirements.md
reviewed_revision: working tree (fixes applied on top of commit e786042)
blocked: false
---

# Readiness Review — Operator Gate-Status Card

## Readiness summary

**READY to drive planning.** No `P0` or `P1` findings remain open. This was a heavier revision than a
clean pass: the operator's "all five surfaces" scope (KD1) exposed genuine structural heterogeneity the
first draft glossed — `/outcome` is a dynamic DAG and `/resume` is a forensic reconstruction surface,
neither a linear gate sequence — and "enforced by construction" silently assumed an unscoped migration.
Eight `P1`s and five `P2`s surfaced; all were resolved by evidence-backed in-place fixes. The load-bearing
addition is a **per-surface status-row contract** (a table naming each surface's archetype, rows, durable
source, and capture gaps) that promotes the previously-deferred derivability audit to a requirements-level
contract. The residual deferred items are genuine `/plan` mechanism (renderer home, drill-down render UX,
exact glyph characters, per-row derivation code-confirmation), not unverified assumptions.

This review ran codex (`gpt-5.5`, xhigh, read-only with repo access) and agy (`Gemini 3.1 Pro (High)`,
hermetic) as **gated generators under Claude-side verification** — each finding was checked against the
doc or cited source before adoption. The engines converged on the three structural problems
(unscoped migration, `/resume` mismatch, `/outcome` DAG mismatch), each surfaced distinct net-new findings
(codex: the AE4 test-verdict shape and the AE6 invented field; agy: the R12⇄R13 contradiction and the AE2
brittleness), and neither parroted. Claude's own pass added the missing-failure-glyph finding that neither
engine caught. Both of codex's codebase claims were verified true before adoption (`saga.py:160-215`
stores `checks_run`/`phase_status` not a test verdict; `code-review` SKILL §5.2 columns are
`Reviewer/Confidence/Route`, not "scores").

## Applied fixes (15)

All edits are evidence-backed (verified source or internal consistency).

- **Two card archetypes (new KD6).** One glyph grammar, two shapes: a *gate-sequence* card (one row per
  declared gate) for `/work`/`/code-review`/`/qa`, and a *summary-projection* card (fixed summary rows
  over dynamic state) for `/outcome`'s DAG and `/resume`'s threads. Resolves the DAG-to-gate impedance
  mismatch and the `/resume` mismatch in one reframe. (KD6, R3, R5, R6)
- **Per-surface status-row contract (new table).** Names each surface's archetype, ordered rows, durable
  source (real saga fields from `saga.py:160-215`), and capture gaps. Promotes the deferred audit into a
  requirements-level contract; `/plan` confirms derivation as its first step. (R7, Dependencies)
- **Failure/halt glyph added.** R1's state set now covers `done · in-progress · blocked · failed
  (negative terminal) · halted · not-reached/unknown` — the card can render a failure, which
  `outcome.py:352 derive_states` deliberately surfaces. (R1, AE9)
- **Migration made explicit (new R14).** Retiring/routing the existing per-surface prose renders
  (`/work` §5.4, `/code-review` §5.2, `/qa` §5) is in scope and likely the bulk of v1; "enforced by
  construction" is false until then. (R14, R4, R10, KD2, Scope, AE10)
- **Taxonomy reworked.** R8 is now a shared-core vocabulary plus per-surface subsets, not a single flat
  taxonomy asserted identically across incompatible surfaces. (R8)
- **Reference types enumerated.** R12 covers saga ticks, durable artifacts, and external reads
  (GitHub/CI/HITL); R13 exempts unknown/not-reached cells from the reference requirement, resolving the
  R12⇄R13 contradiction. (R12, R13, AE7)
- **AE4 corrected.** The Tests cell derives from `checks_run`/`qa`/`phase_status`, not an assumed clean
  verdict (flagged as the main capture gap in the contract). (AE4, R7)
- **AE6 corrected.** Tests the reference's *presence* (not the deferred selection interaction) and names
  the real code-review fields `Reviewer/Confidence/Route`, not the invented "per-reviewer scores." (AE6)
- **AE2 de-brittled.** "Identical glyphs and status values," not "byte-identical." (AE2)
- Minor: Summary/Actors generalized "gate" → "status row/boundary"; Success Criteria, Sources, and
  Outstanding Questions updated to match (the audit item is now a scoped first-`/plan` confirmation, not
  an open question).

## Findings by priority

| Pri | Finding | Source | Status |
|-----|---------|--------|--------|
| P1 | "Only emitter / enforced by construction" omits the unscoped migration of existing prose renders | codex + agy + claude | Fixed |
| P1 | `/resume` forced into a gate-sequence model; it is a reconstruction/routing surface | codex + agy | Fixed |
| P1 | R6 hides a DAG-to-gate impedance mismatch — `/outcome` is node states/frontier, not a gate sequence | codex + claude | Fixed |
| P1 | No failure/halt glyph — card can't render the negative terminals `outcome.py` surfaces | claude | Fixed |
| P1 | R8 single canonical taxonomy not ratifiable across incompatible surface state models | codex | Fixed |
| P1 | AE4 assumes a durable `/work` test verdict; saga stores `checks_run`+`phase_status` | codex | Fixed |
| P1 | R12/R13 define no references for external (CI/HITL) or no-saga state | codex + agy | Fixed |
| P1 | Per-surface derivability audit fully deferred → understates cost / un-plannable | codex + agy | Fixed |
| P2 | KD1 all-five scope vs KD2 low-ceremony tension (renderer/taxonomy/capture deferred) | codex + agy + claude | Fixed |
| P2 | AE6 invents "per-reviewer scores" — real fields are `Reviewer/Confidence/Route` | codex | Fixed |
| P2 | AE6 over-specifies "selecting" a cell while drill-down mechanism is deferred | agy | Fixed |
| P2 | R12 ("every cell") contradicts R13 (unknown/not-reached cells lack state to reference) | agy | Fixed |
| P2 | R3 constant-size assumed a static linear sequence on every surface | agy + codex | Fixed |
| P3 | AE2 "byte-identical" brittle against any time-derived field | agy | Fixed |

## Residual risk from limited evidence

Low-to-moderate. The per-surface contract names each row's durable source from **verified** state
(`saga.py:160-215`, `outcome_projection.py`, the surface SKILLs), but whether each source is parseable
per-row without new capture is confirmed at `/plan` by reading code. The contract's right-hand column
names the three known capture gaps honestly (`/work` test verdict, `/resume` spine, `/code-review`
parseability), so the sizing risk is located and scoped, not hidden — but the v1 effort genuinely hinges
on how many rows need new capture vs. already derive.

## Scope observation (operator's call, not a blocker)

Both engines questioned the all-five-surfaces v1 scope (KD1) against the low-ceremony framing (KD2). The
operator chose all five deliberately; the doc resolves the tension by the two-archetype split and by
promoting the taxonomy + state-capture into the contract rather than cutting scope. A clean alternative
remains available if desired: ship the three gate-sequence surfaces (`/work`, `/code-review`, `/qa`)
first and add `/outcome` + `/resume` as a fast-follow. Not required for readiness — the doc is coherent
and plannable as-is.
