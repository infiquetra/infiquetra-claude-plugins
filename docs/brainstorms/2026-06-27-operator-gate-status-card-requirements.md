---
date: 2026-06-27
topic: operator-gate-status-card
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-5 (Operator Surface as an O(1) Projection — Glyph Card + Controlled Vocabulary)
---

# Operator Gate-Status Card — Requirements

## Summary

Render every saga gate-bearing surface (`/work`, `/code-review`, `/qa`, `/outcome`, `/resume`) through
one shared, fixed-position **glyph card** that is a derived-on-read projection of gate state — read by
location, constant in size, every cell traceable to its evidence, with a controlled vocabulary enforced
by there being a single render site.

## Problem Frame

The operator is the one resource in the engine that does not parallelize. Every other improvement in the
campaign — more engines, wider fan-out, deeper review panels — adds parallel machine work, and each one
quietly raises the cost of staying in control: more state to track, more prose to read, more places
status can be phrased differently. Operator attention is a fixed budget being spent against a growing
surface.

Today that surface is ad hoc. The gates exist — `/work` has implementation, doc-review, test, and
code-review gates plus HITL merge/deploy; `/qa` computes a health score and ship verdict; `/code-review`
runs lenses and validators — but each surface re-derives its status in **prose**, freshly, inconsistently
phrased, with no fixed shape. The same concept ("tests passed") reads differently across surfaces and
across runs. When the prose gets long or the operator distrusts it, they abandon it and tail raw logs —
which is the failure this is meant to prevent. There is no fixed card anywhere today (verified absent:
no glyph/card rendering in any of the five surface skills).

The cost is governability. A status surface that grows with the work, and that the operator can't trust
without re-reading, means the operator either over-reads (spending the one non-parallel budget) or
under-reads (losing control). A constant-size, position-stable, evidence-traceable card keeps the
attention cost flat as the machine work scales.

## Key Decisions

- **KD1 — All five gate-bearing surfaces in v1, one shared renderer.** The constant-size-attention value
  only holds if the operator isn't re-deriving status on whichever surfaces the card skips. So the card
  spans `/work`, `/code-review`, `/qa`, `/outcome`, and `/resume`, all rendered through a single shared
  emitter. (Operator's scope call.)
- **KD2 — Enforcement by construction, not a lint.** Because the shared renderer is the *only* site that
  emits operator-facing gate status, the controlled vocabulary cannot drift — there is no second surface
  to fall out of sync. v1 builds no separate vocabulary lint, and the CLAUDE.md house-style cleanup
  (the lint path) is explicitly out of scope. (Operator's enforcement call.)
- **KD3 — Drill-down is core, not deferred.** Each cell resolves to the concrete state behind it. A card
  the operator can't verify gets abandoned for raw logs, so traceability *is* the value, not a later
  polish. (Operator's call; matches the ideation second-opinion REWORK on S-5.)
- **KD4 — Reuse, don't rebuild.** The card is a *renderer over derived-on-read state*, not a new source
  of truth. `/outcome` renders the projection that already exists (`outcome_projection.py`); the only new
  projection work is for the surfaces that lack one.
- **KD5 — Derived-on-read, no operator-writable status.** Every cell is computed from durable engine
  state. There is no field an operator can set, so the card can never show a number that lies; where a
  cell's state can't be determined it shows *unknown*, never a confident *done*. (Inherits the
  `outcome_projection.py` invariant.)

## Actors

- **A1 — Operator.** The sole reader. Needs constant-size, position-stable, drill-down-traceable status
  to stay in control across parallel machine work without tailing raw logs.
- **A2 — Gate-bearing surfaces** (`/work`, `/code-review`, `/qa`, `/outcome`, `/resume`). Each declares
  its own ordered gate/state list and supplies derived-on-read gate state; none hand-writes its own
  status prose.
- **A3 — The shared card renderer.** The single render site. Projects each surface's gate state into the
  fixed glyph grammar, applies the display-label map, and attaches a drill-down reference per cell.

## Requirements

### Card grammar & projection

R1. The card is a fixed-position glyph card with a stable, documented glyph vocabulary (done /
in-progress / blocked-on-gate / not-reached). Status is read by **location**, not by parsing prose — the
same gate is always in the same place.

R2. Every cell is a **derived-on-read** projection of durable engine state, with **no operator-writable
status field**. A fresh process regenerates an identical card from the same state. (Mirrors the
`outcome_projection.py` R17 invariant.)

R3. The card is **constant-size and position-stable**: a gate not yet reached still occupies its row, so
the operator's reading surface never grows with the amount of parallel machine work. (The O(1)
governability property.)

R4. A **single shared renderer is the only emitter** of operator-facing gate status. Every surface
renders through it; no surface emits its own hand-written status prose.

### Surface coverage

R5. The card renders at the gate boundaries of all five surfaces: `/work`, `/code-review`, `/qa`,
`/outcome`, `/resume`. Each surface declares its ordered gate/state list; the renderer (R4) is shared.

R6. `/outcome`'s card **reuses** the existing `outcome_projection.py` derived-on-read projection (states,
ready frontier, blocked set, progress, attention) rendered in the shared glyph grammar. It does not
introduce a second outcome projection.

R7. For the surfaces without an existing projection (`/work`, `/code-review`, `/qa`, `/resume`), v1
defines a derived-on-read gate-state projection per surface, each obeying R2. Where a gate's state is not
yet captured in a derivable form, the capture is added so the cell projects real state — never a
hand-set value.

### Controlled vocabulary (enforced by construction)

R8. A **single canonical gate taxonomy** spans all surfaces: each gate concept has exactly one
operator-facing label and one glyph, used identically wherever it appears. The same concept never renders
under two names across surfaces.

R9. Operator-facing labels are **decoupled from internal/wire identifiers** via a render-edge display-label
map (extending the `saga.py:79` pattern): the stored enum/marker stays frozen, only the label the
operator reads is mapped.

R10. The vocabulary is **enforced by construction** — because the shared renderer (R4) is the only site
that emits operator-facing gate status, there is no second surface to drift. No separate vocabulary lint
is built in v1.

R11. Agent-facing markers (wire enums, internal phase ids, machine status) stay **distinct** from the
operator-facing vocabulary: the card renders operator words while the durable/stored values stay
machine-stable.

### Drill-down traceability

R12. Every cell carries a **resolvable reference** to the concrete state it projects — the saga tick,
gate verdict, or durable artifact (doc-review readiness, code-review report, qa health-score) behind the
glyph. The card is the top layer of a projection, never the only layer.

R13. A glyph **never asserts a status the operator cannot trace to its evidence**. A cell whose state is
unknown or unverifiable renders as such (e.g. *not-reached* / *unknown*), not as a confident *done*.

## Key Flows

F1. **Render at a gate boundary.** **Trigger:** a surface reaches a gate. The surface supplies its
derived-on-read gate-state projection; the shared renderer maps it to the glyph grammar, applies the
display-label map, attaches a drill-down reference per cell, and emits the fixed positional card.
**Covers R1, R2, R4, R5.**

F2. **Drill down from a glyph.** **Trigger:** the operator wants to verify a cell. The cell's reference
resolves to the underlying saga tick / gate verdict / durable artifact. **Covers R12, R13.**

F3. **Cross-surface consistency.** **Trigger:** the same gate concept appears on two surfaces. It renders
with the same label, glyph, and positional grammar regardless of which surface emits it, because both go
through the one renderer and the one taxonomy. **Covers R8, R9, R10.**

## Acceptance Examples

AE1. **Constant size (R1, R3).** A gate not yet reached still occupies its row as *not-reached*; the
card's height is identical at phase 1 and phase 5 of `/work`.

AE2. **Regenerable, no writable status (R2).** Regenerating the card from the same saga envelope on a
fresh process yields an identical card; there is no input an operator can set to change a cell without
changing the underlying state.

AE3. **`/outcome` reuse (R6).** On `/outcome`, the card's done/total/frontier/blocked values match
`outcome_projection.py`'s `project()` output exactly — same source, rendered in glyph grammar.

AE4. **Projected, not hand-advanced (R7).** On `/work`, the "Tests" cell reads *in-progress* while tests
run and *done* only when the test gate's durable verdict says pass; it is never hand-advanced.

AE5. **One label per concept (R8).** The test-gate concept renders with the same label and glyph on
`/work` and `/qa` — it does not appear as "Tests" on one surface and "checks" on the other.

AE6. **Drill-down resolves (R12).** Selecting the "Reviewer panel" cell on `/work` resolves to the
code-review report and per-reviewer scores behind it.

AE7. **No untraceable confidence (R13).** A reviewer panel still mid-run renders *in-progress* with the
pending count traceable (e.g. 3/5, 2 pending); a cell whose state cannot be determined renders *unknown*,
not *done*.

AE8. **Rename the label, freeze the value (R9).** Changing a gate's operator-facing label changes only
the display-label map; the stored saga envelope value/enum is byte-for-byte unchanged (the
`cc-workflows-ultracode` precedent).

## Scope Boundaries

**In scope (v1):** the shared glyph-card renderer; per-surface derived-on-read gate-state projections for
all five surfaces; reuse of `outcome_projection.py` for `/outcome`; the canonical gate taxonomy +
display-label-map extension; per-cell drill-down references.

**Deferred for later:**
- The CLAUDE.md house-style cleanup and a standalone vocabulary lint (the ideation R8 fold) — excluded by
  the single-render-site enforcement choice (KD2), revivable if vocabulary ever leaks beyond the card.
- A unified card + mission-control issue-progress-comment emitter (one spec, two emitters): the card is
  *designed* as a derived-on-read projection so the issue-progress comment could later render from the
  same source, but that second emitter is not built in v1.
- Transcript-mining for additional surfaces.

**Outside this thing's identity:**
- Any operator-writable status — the card projects engine state or shows *unknown*; it never carries a
  number an operator set (KD5).
- Redesigning the gates themselves — the card projects the *existing* gates; it does not change gate
  logic, thresholds, or verdicts.
- The mission-control GitHub write — the projection emits an artifact; pushing anything stays a separate
  operator-initiated consumer (the `outcome_projection.py` boundary).

## Dependencies / Assumptions

- **Depends on** the saga work-state envelope (`saga.py`) carrying gate state for `/work`, `/code-review`,
  `/qa`, and `/resume`, and on `outcome_projection.py` for `/outcome`.
- **Reuses** the display-label-map pattern (`saga.py:79`, LEARNINGS `#display-label-map-decouples-enum-from-prose`)
  and the derived-on-read / no-operator-writable-status invariant (`outcome_projection.py`, DECISIONS
  `#outcome-report-projection-stance`).
- **Assumption to verify at `/plan` (unverified-depth).** The gate *structure* of each surface is verified
  from its SKILL.md, but whether each gate's *state* is already captured in a derivable form is not. The
  assumption is that the saga envelope plus each surface's durable artifact already carry enough state to
  project most cells; any gate found to be prose-only needs a structured capture added (R7). This is the
  main sizing unknown.

## Success Criteria

- The operator reads gate status by position, in constant size, across all five surfaces; no surface
  emits hand-written status prose.
- Every glyph is traceable to its evidence in one step.
- The card regenerates identically from the same state — no writable status, no drift.
- The same gate concept renders identically wherever it appears.
- `/doc-review` can act on this doc without follow-up clarifications.

## Outstanding Questions

All deferred to planning — none blocks `/plan`.

- **Drill-down render mechanism (Deferred to planning).** How a cell exposes its reference in a terminal
  surface (inline ref, indexed footer, resolvable id).
- **Per-surface state-derivability audit (Deferred to planning).** Which gates across `/work`,
  `/code-review`, `/qa`, `/resume` are already derivable vs prose-only, and the capture to add for any
  that are not (sizes R7).
- **Renderer home and invocation (Deferred to planning).** Whether the shared renderer lives as a script
  (à la `outcome_projection.py`) or a shared skill reference, and how each surface invokes it.
- **Canonical taxonomy label set (Deferred to planning).** The exact operator-facing label + glyph per
  gate concept per surface; the requirement pins "one label+glyph per concept," planning ratifies the
  enumerated list.

## Sources / Research

- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — survivor **S-5** (Operator Surface as an O(1)
  Projection — Glyph Card + Controlled Vocabulary), folding seeds A10 + B5 + A6/R8; second-opinion REWORK
  (drill-down-traceable, "the card is the top layer not the only layer") from agy-Flash.
- `plugins/saga/scripts/outcome_projection.py` — the derived-on-read, no-operator-writable-status
  projection precedent (R17/R25) the card reuses and mirrors.
- `plugins/saga/scripts/saga.py:79` + LEARNINGS `#display-label-map-decouples-enum-from-prose` — the
  controlled-vocabulary-at-the-render-edge mechanism (display-label map over a frozen wire enum).
- DECISIONS `#outcome-report-projection-stance` (projection conventions) and
  `#saga-tiering-execution-campaign-shipped` (one spec → two emitters, R9).
- Surface gate structures: `plugins/saga/skills/{work,code-review,qa,resume,outcome}/SKILL.md`.
