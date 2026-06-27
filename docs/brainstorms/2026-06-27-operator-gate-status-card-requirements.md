---
date: 2026-06-27
topic: operator-gate-status-card
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-5 (Operator Surface as an O(1) Projection — Glyph Card + Controlled Vocabulary)
---

# Operator Gate-Status Card — Requirements

## Summary

Render every saga status-bearing surface (`/work`, `/code-review`, `/qa`, `/outcome`, `/resume`)
through one shared, fixed-position **glyph card** that projects each surface's status rows — an ordered
gate sequence for the gate-bearing surfaces, a fixed summary for the dynamic ones — derived-on-read from
durable engine state, constant in size, every cell traceable to its evidence, with a controlled
vocabulary enforced by there being a single render site.

## Problem Frame

The operator is the one resource in the engine that does not parallelize. Every other improvement in the
campaign — more engines, wider fan-out, deeper review panels — adds parallel machine work, and each one
quietly raises the cost of staying in control: more state to track, more prose to read, more places
status can be phrased differently. Operator attention is a fixed budget being spent against a growing
surface.

Today that surface is ad hoc. The gates exist — `/work` has implementation, doc-review, test, and
code-review gates plus HITL merge/deploy; `/qa` computes a health score and ship verdict; `/code-review`
runs lenses and validators — but each surface re-derives its status in **prose**, freshly, inconsistently
phrased, with no fixed shape, at its own emission points (`/work` SKILL §5.4, `/code-review` §5.2, `/qa`
§5). The same concept ("tests passed") reads differently across surfaces and across runs. When the prose
gets long or the operator distrusts it, they abandon it and tail raw logs — which is the failure this is
meant to prevent. There is no fixed card anywhere today (verified absent: no glyph/card rendering in any
of the five surface skills).

The cost is governability. A status surface that grows with the work, and that the operator can't trust
without re-reading, means the operator either over-reads (spending the one non-parallel budget) or
under-reads (losing control). A constant-size, position-stable, evidence-traceable card keeps the
attention cost flat as the machine work scales.

## Key Decisions

- **KD1 — All five status-bearing surfaces in v1, one shared renderer.** The constant-size-attention
  value only holds if the operator isn't re-deriving status on whichever surfaces the card skips. So the
  card spans `/work`, `/code-review`, `/qa`, `/outcome`, and `/resume`, all rendered through a single
  shared emitter. (Operator's scope call. The two structurally-different surfaces — `/outcome` and
  `/resume` — are handled by KD6, not forced into a gate sequence.)
- **KD2 — Enforcement by construction, not a lint.** Because the shared renderer is the only site that
  emits operator-facing status, the controlled vocabulary cannot drift — there is no second surface to
  fall out of sync. This holds *only once the existing per-surface prose renders are retired or routed
  through the renderer* (R14). v1 builds no separate vocabulary lint, and the CLAUDE.md house-style
  cleanup (the lint path) is explicitly out of scope. (Operator's enforcement call.)
- **KD3 — Drill-down is core, not deferred.** Each cell resolves to the concrete state behind it. A card
  the operator can't verify gets abandoned for raw logs, so traceability is the value, not a later
  polish. (Operator's call; matches the ideation second-opinion REWORK on S-5.)
- **KD4 — Reuse, don't rebuild.** The card is a renderer over derived-on-read state, not a new source of
  truth. `/outcome` renders the projection that already exists (`outcome_projection.py`); the only new
  projection work is for the surfaces that lack one.
- **KD5 — Derived-on-read, no operator-writable status.** Every cell is computed from durable engine
  state. There is no field an operator can set, so the card can never show a number that lies; where a
  cell's state can't be determined it shows *unknown*, never a confident *done*. (Inherits the
  `outcome_projection.py` invariant.)
- **KD6 — Two card archetypes, one grammar.** The surfaces are not uniform, so the card has two shapes
  under one glyph grammar: a **gate-sequence** card (one row per declared gate, in order) for the
  gate-bearing surfaces (`/work`, `/code-review`, `/qa`), and a **summary-projection** card (a fixed set
  of summary rows over dynamic state) for the surfaces whose item set is dynamic (`/outcome`'s DAG nodes,
  `/resume`'s reconstructed threads). Both are constant-size; they differ in what a row *is*. The
  per-surface contract below pins each surface's archetype and rows.

## Actors

- **A1 — Operator.** The sole reader. Needs constant-size, position-stable, drill-down-traceable status
  to stay in control across parallel machine work without tailing raw logs.
- **A2 — Status-bearing surfaces** (`/work`, `/code-review`, `/qa`, `/outcome`, `/resume`). Each declares
  its archetype and its ordered status-row set and supplies derived-on-read state; none hand-writes its
  own status prose (R14 retires the existing prose renders).
- **A3 — The shared card renderer.** The single render site. Projects each surface's state into the fixed
  glyph grammar, applies the display-label map, and attaches a drill-down reference per cell.

## Requirements

### Card grammar & projection

R1. The card is a fixed-position glyph card with a stable, documented glyph vocabulary covering every
state the projected sources can hold: **done · in-progress · blocked · failed (negative terminal:
failed/rejected/stalled) · halted (backend-down receipt) · not-reached/unknown**. Status is read by
location, not by parsing prose — the same row is always in the same place. (The exact glyph characters
are ratified with the label set; the *set of states* is pinned here because the card must be able to
render a failure, which `outcome.py` `derive_states` surfaces deliberately — "negative terminal —
surfaced, not masked", `outcome.py:352`.)

R2. Every cell is a **derived-on-read** projection of durable engine state, with **no operator-writable
status field**. A fresh process regenerates an identical card from the same state. (Mirrors the
`outcome_projection.py` R17 invariant.)

R3. The card is **constant-size and position-stable**. For a gate-sequence surface (KD6), the surface
declares a static superset of its gates and a gate not yet reached still occupies its row as
*not-reached*. For a summary-projection surface (KD6), the row set is the fixed summary fields, not one
row per dynamic item — so a 3-node and a 30-node `/outcome` DAG render the same-height card. Either way
the operator's reading surface never grows with the amount of parallel machine work. (The O(1)
governability property.)

R4. A single shared renderer is the **only emitter** of operator-facing status. Every surface renders
through it; no surface emits its own hand-written status prose. (Made true by R14, which retires the
existing prose renders — until then this is aspirational.)

### Surface coverage

R5. The card renders at the status boundaries of all five surfaces: `/work`, `/code-review`, `/qa`,
`/outcome`, `/resume`. Each surface declares its archetype (KD6) and its ordered status-row set per the
per-surface contract below; the renderer (R4) is shared.

R6. `/outcome`'s card is a **summary-projection** that reuses the existing `outcome_projection.py`
derived-on-read projection (progress, ready frontier, blocked set, attention, and the negative-terminal
nodes it surfaces) rendered in the shared glyph grammar. It does not introduce a second outcome
projection and does not render one row per node.

R7. For the surfaces without an existing projection (`/work`, `/code-review`, `/qa`, `/resume`), v1
defines a derived-on-read state projection per surface, each obeying R2, with its rows and durable
sources pinned by the **per-surface status-row contract** below. Where a row's state is not yet captured
in a derivable form (notably `/work`'s test verdict — `saga.py` stores `checks_run` + a coarse
`phase_status`, not a per-gate pass/fail), the capture is added so the cell projects real state — never a
hand-set value. Confirming each row's derivation against code is the first `/plan` step (the contract
scopes it; `/plan` sizes it).

### Per-surface status-row contract

The card's rows, archetype, and durable source per surface. Verified against each surface's SKILL and the
saga state (`saga.py:160-215`); cells marked *(confirm at /plan)* name where the derivation must be
checked or a capture added.

| Surface | Archetype | Status rows (in order) | Durable source | Capture gap → `/plan` |
|---|---|---|---|---|
| `/work` | gate-sequence | Implementation · Doc-review · Tests · Reviewer panel · Scanners · CI · Merge (HITL) · Deploy (HITL) | saga envelope `phase`/`round`/`progress_pct`/`last_commit_sha` (impl); `review_paths` → code-review artifact (reviewer panel, scanners); `checks_run`+`phase_status`+`qa_paths` (tests); `pr_refs`+`head_sha`+`destination` → GitHub (CI, merge, deploy) | Tests has no clean per-gate verdict — derive from `checks_run`/`qa` or add a structured test-gate capture |
| `/code-review` | gate-sequence | Scope · Intent/built-vs-planned · Lenses · Review fan-out · Merge · Validators · Verdict | the code-review artifact `docs/code-reviews/…` (columns `Reviewer/Confidence/Route`, blocked status) + saga `review_paths` | confirm the artifact is parseable per-row *(confirm at /plan)* |
| `/qa` | gate-sequence | Risk class · Checks · Findings · Health score · Ship verdict | the qa artifact (`qa_paths`): deterministic health score + PASS/FAIL verdict | — (qa already computes a deterministic score + verdict) |
| `/outcome` | summary-projection | Progress (done/total) · Ready frontier · Blocked · Attention · Negative terminals | `outcome_projection.py` `project()` (derived-on-read) | none — reuse as-is (R6) |
| `/resume` | summary-projection (reconstruction) | Open leaves · Ready frontier · Last gate verdicts · Route | the reconstructed thread spine (`/resume` Phase 2-3) over the append-only saga log | define the spine projection — mirrors the S-3 "spore" spine *(confirm at /plan)* |

### Controlled vocabulary (enforced by construction)

R8. Shared status concepts use **one operator-facing label and one glyph** wherever they appear (a test
gate reads identically on `/work` and `/qa`). Surfaces also have **surface-specific rows** that are not
shared (e.g. `/outcome`'s frontier, `/resume`'s route); those are named once in the per-surface contract.
The vocabulary is therefore a shared core plus per-surface subsets, not a single flat taxonomy asserted
identically across incompatible surfaces.

R9. Operator-facing labels are **decoupled from internal/wire identifiers** via a render-edge display-label
map (extending the `saga.py:78` pattern): the stored enum/marker stays frozen, only the label the
operator reads is mapped.

R10. The vocabulary is **enforced by construction** — because the shared renderer (R4) is the only site
that emits operator-facing status, there is no second surface to drift. This depends on R14 (retiring the
existing prose renders). No separate vocabulary lint is built in v1.

R11. Agent-facing markers (wire enums, internal phase ids, machine status) stay **distinct** from the
operator-facing vocabulary: the card renders operator words while the durable/stored values stay
machine-stable.

### Drill-down traceability

R12. Every **determinable** cell carries a **resolvable reference** to the concrete state it projects.
Reference types are enumerated: a saga tick/field, a durable artifact (doc-review readiness, code-review
report, qa health-score), or an **external read** (a GitHub PR / CI check / HITL target) for state that
lives outside saga (CI, merge, deploy). The card is the top layer of a projection, never the only layer.

R13. A glyph **never asserts a status the operator cannot trace to its evidence**. A cell whose state is
unknown or not-reached renders as such — and is **exempt from R12's reference requirement** precisely
because it has no concrete state yet to reference. A failure or halt is a *determinable* state and must
carry its reference (the failing artifact / HALT receipt).

### Migration (makes R4/R10 true)

R14. v1 **retires or routes through the shared renderer** every existing per-surface prose status
emission, so the renderer is genuinely the only emitter. The known emission points to convert:
`/work` SKILL §5.4 (continuation/status), `/code-review` SKILL §5.2 (present findings), `/qa` SKILL §5
(report). This migration is in scope and is likely the bulk of the v1 effort — "enforced by
construction" is false while a second prose render still exists.

## Key Flows

F1. **Render at a status boundary.** **Trigger:** a surface reaches a status boundary. The surface
supplies its derived-on-read state per its archetype (KD6); the shared renderer maps it to the glyph
grammar, applies the display-label map, attaches a drill-down reference per determinable cell, and emits
the fixed positional card. **Covers R1, R2, R4, R5.**

F2. **Drill down from a glyph.** **Trigger:** the operator wants to verify a cell. The cell's reference
resolves to the underlying saga tick / durable artifact / external read. **Covers R12, R13.**

F3. **Cross-surface consistency.** **Trigger:** a shared concept appears on two surfaces. It renders with
the same label, glyph, and positional grammar regardless of which surface emits it, because both go
through the one renderer and the shared vocabulary core. **Covers R8, R9, R10.**

## Acceptance Examples

AE1. **Constant size (R1, R3).** On `/work` (gate-sequence), a gate not yet reached still occupies its
row as *not-reached*; the card's height is identical at phase 1 and phase 5. On `/outcome`
(summary-projection), a 3-node and a 30-node DAG render the same-height card.

AE2. **Deterministic regeneration, no writable status (R2).** Regenerating the card from the same engine
state on a fresh process yields **identical glyphs and status values**; there is no input an operator can
set to change a cell without changing the underlying state.

AE3. **`/outcome` reuse (R6).** On `/outcome`, the card's progress/frontier/blocked/attention values
match `outcome_projection.py`'s `project()` output exactly — same source, rendered in glyph grammar, as a
fixed summary, not one row per node.

AE4. **Projected, not hand-advanced (R7).** On `/work`, the "Tests" cell derives from the durable check
evidence (`checks_run` / `qa` artifact / `phase_status`): it reads *in-progress* while checks run and
*done* only when that evidence shows pass; it is never hand-advanced. (If a structured test-gate verdict
is added per R7, the cell derives from it.)

AE5. **One label per shared concept (R8).** The test-gate concept renders with the same label and glyph
on `/work` and `/qa` — it does not appear as "Tests" on one surface and "checks" on the other.

AE6. **Drill-down reference present (R12).** The `/work` "Reviewer panel" cell carries a resolvable
reference to the code-review artifact behind it (its `Reviewer/Confidence/Route` rows) — the requirement
is that the reference is present and resolvable, independent of the deferred terminal-interaction
mechanism.

AE7. **No untraceable confidence (R13).** A reviewer panel still mid-run renders *in-progress* with the
pending count traceable; a cell whose state cannot be determined renders *unknown* (and carries no
reference), not *done*.

AE8. **Rename the label, freeze the value (R9).** Changing a row's operator-facing label changes only the
display-label map; the stored saga envelope value/enum is byte-for-byte unchanged (the
`cc-workflows-ultracode` precedent).

AE9. **Failure is representable (R1).** A failed `/work` test gate, a `/qa` FAIL verdict, and an
`/outcome` `failed`/`rejected`/`stalled`/`halted` node each render with the failure/halt glyph and carry
a reference to the failing evidence — never *blocked* or *not-reached*.

AE10. **Single emitter after migration (R4, R14).** After v1, no surface emits hand-written status prose
outside the renderer; the converted emission points (`/work` §5.4, `/code-review` §5.2, `/qa` §5) render
through the card.

## Scope Boundaries

**In scope (v1):** the shared glyph-card renderer (both archetypes); per-surface derived-on-read state
projections for all five surfaces per the contract; reuse of `outcome_projection.py` for `/outcome`; the
shared-core + per-surface-subset vocabulary and display-label-map extension; per-cell drill-down
references (saga / artifact / external); **retiring or routing the existing per-surface prose status
renders** (R14).

**Deferred for later:**
- The CLAUDE.md house-style cleanup and a standalone vocabulary lint (the ideation R8 fold) — excluded by
  the single-render-site enforcement choice (KD2), revivable if vocabulary ever leaks beyond the card.
- A unified card + mission-control issue-progress-comment emitter (one spec, two emitters): the card is
  designed as a derived-on-read projection so the issue-progress comment could later render from the same
  source, but that second emitter is not built in v1.
- Transcript-mining for additional surfaces.

**Outside this thing's identity:**
- Any operator-writable status — the card projects engine state or shows *unknown*; it never carries a
  number an operator set (KD5).
- Redesigning the gates themselves — the card projects the *existing* gates/states; it does not change
  gate logic, thresholds, or verdicts.
- The mission-control GitHub write — the projection emits an artifact; pushing anything stays a separate
  operator-initiated consumer (the `outcome_projection.py` boundary).

## Dependencies / Assumptions

- **Depends on** the saga work-state envelope (`saga.py:160-215` — `phase`, `phase_status`, `checks_run`,
  `review_paths`, `qa_paths`, `pr_refs`, `destination`, `head_sha`) and the per-surface durable artifacts
  (doc-review readiness, code-review report, qa health-score) for the four projected surfaces, and on
  `outcome_projection.py` for `/outcome`.
- **Reuses** the display-label-map pattern (`saga.py:78`, LEARNINGS `#display-label-map-decouples-enum-from-prose`)
  and the derived-on-read / no-operator-writable-status invariant (`outcome_projection.py`, DECISIONS
  `#outcome-report-projection-stance`).
- **Main sizing unknown (scoped, not open).** The per-surface contract names each row's durable source
  from verified state, but whether each source is parseable per-row without a new capture is confirmed at
  `/plan` by reading code. The known capture gaps are the contract's right-hand column (`/work` test
  verdict, `/resume` spine projection, `/code-review` artifact parseability). The effort hinges on how
  many of these need new capture vs. already derive — this is the first `/plan` step.

## Success Criteria

- The operator reads status by position, in constant size, across all five surfaces; after migration
  (R14) no surface emits hand-written status prose.
- Every determinable glyph is traceable to its evidence in one step, including external (CI/HITL) state;
  failure and halt are representable, never masked as blocked/not-reached.
- The card regenerates deterministically from the same state — no writable status, no drift.
- A shared concept renders identically wherever it appears.
- `/doc-review` can act on this doc without follow-up clarifications.

## Outstanding Questions

All deferred to planning — none blocks `/plan`.

- **Per-surface derivation confirmation (Deferred to planning).** Confirm each contract row's durable
  source is parseable per-row, and add the flagged captures (`/work` test verdict, `/resume` spine,
  `/code-review` parseability). The contract scopes this; `/plan` sizes it as its first step.
- **Drill-down render mechanism (Deferred to planning).** How a cell exposes its reference in a terminal
  surface (inline ref, indexed footer, resolvable id).
- **Renderer home and invocation (Deferred to planning).** Whether the shared renderer lives as a script
  (à la `outcome_projection.py`) or a shared skill reference, and how each surface invokes it.
- **Label + glyph set ratification (Deferred to planning).** The exact operator-facing label and glyph
  character per state and per shared concept; the requirements pin the *state set* (R1) and "one
  label+glyph per shared concept" (R8), planning ratifies the exact characters.

## Sources / Research

- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` — survivor **S-5** (Operator Surface as an O(1)
  Projection — Glyph Card + Controlled Vocabulary), folding seeds A10 + B5 + A6/R8; second-opinion REWORK
  (drill-down-traceable, "the card is the top layer not the only layer") from agy-Flash.
- `plugins/saga/scripts/outcome_projection.py` — the derived-on-read, no-operator-writable-status
  projection precedent (R17/R25) the card reuses and mirrors; `plugins/saga/scripts/outcome.py:333-352` —
  `derive_states` surfaces negative-terminal nodes ("surfaced, not masked"), the basis for R1's failure
  state.
- `plugins/saga/scripts/saga.py:160-215` — the work-state envelope fields the four projected surfaces
  derive from; `saga.py:78` + LEARNINGS `#display-label-map-decouples-enum-from-prose` — the
  controlled-vocabulary-at-the-render-edge mechanism (display-label map over a frozen wire enum).
- DECISIONS `#outcome-report-projection-stance` (projection conventions) and
  `#saga-tiering-execution-campaign-shipped` (one spec → two emitters, R9).
- Surface gate structures: `plugins/saga/skills/{work,code-review,qa,resume,outcome}/SKILL.md` (work §5.4,
  code-review §5.2, qa §5 — the existing prose emission points R14 retires).
