---
title: capability: mid-run operator adjustment envelope (quiesce, pause points, andon-cord, act-log-notify)
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
objective: Ship run-start intent envelope for lifecycle autonomy
tier: structural
wave: wave-1
---

# capability: mid-run operator adjustment envelope (quiesce, pause points, andon-cord, act-log-notify)

### Objective

Ship run-start intent envelope for lifecycle autonomy

## Summary

A run-start intent envelope (the operator's up-front directives) has no mid-run counterpart:
once a `/work` or `/outcome` run is dispatched, an operator or a worker has no durable,
polled surface to raise "pause," "stop," "re-tier," or "this mutation needs review" without
killing the run or hand-editing state. This capability ships **one** documented,
versioned control-file schema — the adjustment envelope — polled at existing segment
and frontier boundaries, that carries four related directives under one roof: an
operator-raised quiesce sentinel, plan-declared pause points, a worker-raised andon-cord
halt, and an act-log-inverse-notify posture for reversible mutations so pauses are
reserved for irreversibles.

## Problem Frame

The fleet has no mid-run operator control surface today. Evidence, grounded in this
repo's own journal and code:

- **Ad hoc tier reasoning every time.** The grounding brief's recurring-pain synthesis
  names this directly: "Ad hoc tier reasoning every time — 'xhigh-Opus on everything is
  wasteful'; manual per-unit tier tables; operator asking for mid-run model-change
  pauses (3 repos)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:126-128`,
  theme 12). The operator has asked for mid-run adjustment more than once, in more than
  one repo, and no primitive exists to answer it.
- **Gate-primitive unreliability** compounds the gap: "AskUserQuestion silently
  auto-proceeds on timeout treating silence as consent... fires before answers are
  captured, errors outright; agents fall back to plain-text questions (6 repos)"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:113-116`, theme 6). A durable
  polled file, not a synchronous prompt that can silently time out, is the shape this
  calls for.
- **Subagents idle without delivering; stale idle notifications** — the coordinator must
  detect and re-ping (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:121-122`,
  theme 6) — is the same "the run needs an operator-visible signal channel, not just an
  internal one" shape.
- The `/outcome` coordinator's tick loop already has exactly one boundary where an
  envelope could be polled without new machinery: it breaks the dispatch loop when
  `tick_dispatched` is false ("quiescent: nothing new to dispatch this tick" —
  `plugins/saga/scripts/outcome.py:696`). Today that boundary only asks "is there more
  work"; it has no notion of "has the operator or a worker asked me to stop or change
  course."
- The `/outcome` campaign's binding decision is **HALT-not-degrade**: "Derived-on-read
  status, never committed status fields; HALT-not-degrade; backend menu off-by-default
  with host-conditional degrade; cost ledger = leaf-produced fact"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`,
  `docs/engineering-journal/DECISIONS.md:739-744`, `{#outcome-backend-degrade-stance}`).
  Any new pause/halt mechanism must compose with this existing HALT precedence
  (presence × guarantee × side-effect) rather than inventing a second, conflicting halt
  semantics.
- `team-execution`'s iteration loop already has an unbounded-vs-bounded halt precedent
  worth reusing rather than re-deriving: "Maximum iterations: 3. After 3 cycles, proceed
  with the best available version regardless of scores"
  (`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:17`)
  and the affected-validator re-run loop at
  `plugins/team-execution/skills/team-execution/references/validator-execution-order.md:27`.
  Neither loop has a worker-raised stop-the-line signal today — only a scoring cap.
- No existing mutation in mission-control or saga is reversible-by-default today. Board
  moves, label changes, and issue edits currently have no undo path, which is why every
  prior "should this pause" question defaults to "pause," even for cheap, reversible
  actions — inflating operator interruption load for no safety benefit.

## Requirements

Requirements are grouped by the four writers that share the one envelope file, plus the
default posture for reversible mutations.

**Envelope primitive (all writers converge here)**

R1. One documented, versioned control-file schema
(`plugins/saga/references/adjustment-envelope.md` or equivalent) defines the directive
vocabulary: `quiesce`, `pause_after`, `andon_halt`, `re-tier`/`add-reviewer`/`cancel`/
`abort`. Corresponds to `T6-F4-6` (primary), tier `moonshot`.

R2. A parser polls the envelope at existing segment/frontier boundaries — the `/outcome`
coordinator tick boundary (`plugins/saga/scripts/outcome.py:696`) and the `/work`
segment boundary — rather than introducing a new poll loop.

R3. An unknown or malformed directive in the envelope fails closed: the run halts and
surfaces the unrecognized directive rather than silently proceeding. (No silent
proceed, per `T6-F4-6`'s `dod_sketch`.)

**Operator-raised quiesce (writer 1)**

R4. An operator can raise a quiesce sentinel (e.g. a `.saga/pause` file or an envelope
`quiesce` directive) mid-run. The run drains any in-flight leaf, dispatches no new work,
and surfaces a resumable point — without requiring a process restart. Corresponds to
`T6-F3-3`, tier `structural`.

**Plan-declared pause points (writer 2, absorbing seed S-31)**

R5. A plan can declare `pause_after: <segment>` in its schema. When declared, the run
halts deterministically at exactly that boundary and resumes only on an explicit
continue signal. Corresponds to `T6-F2-4`, tier `quick-win`.

R6. Absent an explicit `pause_after` declaration, only irreversible actions pause by
default (the intake-tension-3 posture); reversible actions proceed under R9's
act-log-notify instead. This is the load-bearing default that keeps R5 additive rather
than making every plan pause-heavy by default.

R7. The pause-point mechanism generalizes seed `S-31` ("built-in pause points to adjust
context/model inline, /outcome, /plan" —
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`, id `S-31`): a
declared pause point additionally accepts a context/model change before the run
continues, and the run must honor that change on resume (verified via transcript, not
just accepted-and-ignored).

**Worker-raised andon-cord (writer 3)**

R8. Any worker or reviewer inside a `team-execution` team can raise an andon-cord halt
signal that reaches the coordinator through the same envelope file (not a separate
channel). Corresponds to `T6-F5-8`, tier `structural`.

R9. A raised andon blocks the next wave/tick from dispatching and writes an
operator-surface record — extending the existing HALT-not-degrade posture
(`docs/engineering-journal/DECISIONS.md:744`) rather than adding a second halt
vocabulary. This must not weaken or bypass the existing per-loop iteration caps at
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:17` and
`plugins/team-execution/skills/team-execution/references/validator-execution-order.md:27`
— an andon halt and an iteration-cap "proceed with best available" are distinct,
coexisting outcomes.

**Reversible-mutation default (defines the "when NOT to pause" posture — H-F2-1)**

R10. Reversible mutations (mission-control board/label/issue moves; saga
branch/PR steps) do not pause by default. Instead they write an inverse operation to an
undo ledger and notify the operator, proceeding without blocking. Corresponds to
`H-F2-1`, tier `structural`.

R11. Each registered reversible operation has a proven round-trip inverse (an `/undo`
replay path), shrinking the set of operations that require a gated pause to
no-inverse operations only. This is what makes R6's "only irreversibles pause by
default" claim true rather than aspirational — without a working inverse, an operation
is definitionally not reversible and must fall back to pausing.

## Key Flows

F1. **Operator quiesce mid-run.** Trigger: operator writes the quiesce sentinel while a
run is executing. At the next poll boundary (R2) the run drains the in-flight leaf,
dispatches nothing new, and surfaces a resume point. Covers R1–R4.

F2. **Plan-declared pause with context/model change.** Trigger: the executing plan
reaches a segment with `pause_after` declared. The run halts exactly there, accepts an
operator-supplied context/model change, and resumes honoring the change. Covers
R1, R5–R7.

F3. **Worker-raised andon-cord.** Trigger: a worker or reviewer inside a team-execution
wave raises an andon signal via the envelope. The next wave is not dispatched; an
operator-surface HALT record is written. Iteration caps elsewhere in the loop are
unaffected. Covers R1, R2, R8, R9.

F4. **Reversible mutation, no pause.** Trigger: a leaf performs a registered reversible
mutation (e.g. a board status move). The action proceeds; its inverse is written to the
undo ledger; the operator is notified post-hoc rather than blocked pre-hoc. Covers
R10, R11.

F5. **Unknown directive, fail closed.** Trigger: the envelope contains a directive the
parser does not recognize. The run halts and names the unrecognized directive rather
than silently continuing. Covers R1, R3.

## Scope Boundaries

- **One schema, four writers — not four separate control files.** The envelope is the
  single polled surface; quiesce, pause-points, and andon-cord all write into it. A
  design that gives each writer its own file is out of scope for v1.
- **Reuses existing poll boundaries.** This capability does not add a new standing poll
  loop; it hooks the existing `/outcome` tick-quiescence check
  (`plugins/saga/scripts/outcome.py:696`) and the `/work` segment boundary. A
  general-purpose event bus is out of scope.
- **Does not change team-execution's existing iteration caps.** The 3-cycle
  best-available-proceed behavior at `consensus-protocol.md:17` and the affected-validator
  re-run loop at `validator-execution-order.md:27` stay as-is; the andon-cord is an
  additional, orthogonal halt path, not a replacement for those caps.
- **Undo ledger covers only the operations named in R10** (mission-control board/label/
  issue moves; saga branch/PR steps) for v1. Backfilling inverse operations onto every
  mutation in the fleet is out of scope; operations without a registered inverse keep
  the existing gated-pause behavior (R11).
- **Does not touch the `/outcome` HALT-not-degrade backend-selection semantics**
  (`{#outcome-backend-degrade-stance}`); the andon-cord and quiesce sentinel compose with
  that existing precedence rather than replacing it.
- **No new operator-facing UI.** The envelope is a file the operator or a hook writes;
  a dashboard or chat-based control surface is out of scope for this issue.

## Dependencies / Assumptions

- Builds directly on the `/outcome` campaign's binding HALT-not-degrade decision
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`;
  `docs/engineering-journal/DECISIONS.md:739-744`, `{#outcome-backend-degrade-stance}`) —
  the andon-cord and quiesce mechanisms must compose with, not contradict, that existing
  precedence.
- Assumes the `/outcome` tick-quiescence boundary (`plugins/saga/scripts/outcome.py:696`)
  and the `/work` segment boundary are suitable, already-existing hook points for polling
  the envelope; verified present in code at grounding time.
- Assumes `team-execution`'s existing iteration-cap loops
  (`consensus-protocol.md:17`, `validator-execution-order.md:27`) remain unmodified and
  compose with the new andon-cord path rather than needing rework.
- Consolidates five ideation survivors under one primitive per the issue map's
  consolidation rationale: "The run-start intent envelope's mid-run counterpart: five
  mechanisms that are all 'a durable surface the run polls for operator directives' —
  the control file (F4-6) is the primitive; plan-declared pause points (F2-4, absorbing
  seed S-31 per dedup-map), operator-raised quiesce sentinel (F3-3), and worker-raised
  andon-cord (F5-8) are the three writers; H-F2-1's act-log-inverse-notify posture
  defines the default for reversible mutations so pauses are reserved for
  irreversibles." (`issue-map-final.json`, slug `pf-midrun-adjustment-envelope`).

## Grounding References

| Absorbed id | Role | Title | Basis |
|---|---|---|---|
| `T6-F4-6` | primary | Adjustment-envelope control file | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` — dod_sketch: merged PR adding `references/adjustment-envelope.md` + poll-boundary parser for re-tier/drain/cancel/add-reviewer/abort, failing closed on unknown directive |
| `T6-F2-4` | facet | Plan-declared pause points | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` — dod_sketch: `pause_after` plan-sections schema + deterministic halt-check matching team-execution/`/work` boundary |
| `T6-F3-3` | facet | Quiesce primitive (operator-raised sentinel) | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` — dod_sketch: `.saga/pause` sentinel + boundary-poll drain semantics wired into `/work` and `/outcome` |
| `T6-F5-8` | facet | Andon-cord halt | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` — dod_sketch: bottom-up andon/HALT worker-signal lane in team-execution + Step B1 rule blocking the next wave |
| `S-31` | dedup-merged into T6-F2-4 | Built-in pause points to adjust context/model inline, `/outcome`, `/plan` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` — direct operator statement; dod_sketch: explicit pause affordances honoring a model/context change on resume |
| `H-F2-1` | facet | Undo-ledger: act-log-inverse-notify | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` — dod_sketch: `undo_ledger.py` + inverse-op writes in mission-control board/label/issue and saga branch/PR steps + `/undo` replay command |

Binding decisions this issue must engage: `{#outcome-backend-degrade-stance}` /
HALT-not-degrade (`docs/engineering-journal/DECISIONS.md:739-744`); the `/outcome`
campaign's derived-on-read-status stance (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`).

## Recommended Executor Profile

- **Model:** Sonnet
- **Effort:** xhigh — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** Sonnet at xhigh effort is appropriate rather than Opus because the
  work is well-grounded, schema-and-wiring shaped (one new control-file schema plus
  polling hooks at boundaries that already exist) rather than open-ended judgment work;
  team-execution is warranted over inline because the four writers (quiesce, pause-points,
  andon-cord, undo-ledger) touch three separate subsystems (`/outcome`, `/work`,
  `team-execution`, mission-control) and benefit from reviewer consensus on the shared
  schema before any writer is wired in.

### Out-of-scope / non-goals
See Scope Boundaries above. In short: one envelope schema and parser, reusing existing
poll boundaries, three writers into it, and an undo-ledger default for reversible
mutations — no new poll loop, no change to team-execution's existing iteration caps, no
new operator UI, no full-fleet inverse-operation backfill.

## Definition of Done

- Merged PR adding a documented, versioned adjustment-envelope schema (e.g.
  `plugins/saga/references/adjustment-envelope.md`) plus a parser polled at the existing
  `/outcome` tick boundary (`plugins/saga/scripts/outcome.py:696`) and `/work` segment
  boundary, supporting `quiesce`, `pause_after`, `andon_halt`, and re-tier/add-reviewer/
  cancel/abort directives.
- Reversible mutations (mission-control board/label/issue; saga branch/PR steps) proceed
  under an act-log-inverse-notify path (`undo_ledger.py` + `/undo` replay command) instead
  of pausing, with a proven round-trip inverse per registered operation.
- An unknown directive in the envelope fails closed (halts, names the directive) rather
  than silently proceeding.
- Full suite, lint, format, and type checks stay green.

### Acceptance criteria
- [ ] A quiesce sentinel written mid-run causes the run to drain the in-flight leaf,
  dispatch nothing new, and surface a resume point — without a process restart. Check:
  `uv run pytest tests/test_adjustment_envelope.py -k quiesce_drain` → passes.
- [ ] A plan with a declared `pause_after: <segment>` halts exactly at that boundary and
  resumes only on an explicit continue signal; a plan without a declaration pauses only
  on irreversible actions. Check:
  `uv run pytest tests/test_adjustment_envelope.py -k pause_after_boundary` → passes.
- [ ] A declared pause point accepts an operator-supplied context/model change and the
  resumed run honors it (verified via transcript/log assertion, not silently ignored).
  Check: `uv run pytest tests/test_adjustment_envelope.py -k pause_context_model_change`
  → passes.
- [ ] A worker- or reviewer-raised andon-cord halt reaches the coordinator through the
  envelope and blocks the next wave from dispatching, without weakening the existing
  `consensus-protocol.md:17` 3-cycle cap or the `validator-execution-order.md:27`
  re-run loop. Check: `uv run pytest tests/test_adjustment_envelope.py -k andon_blocks_next_wave`
  → passes.
- [ ] A registered reversible mutation (mission-control board/label/issue move; saga
  branch/PR step) proceeds without pausing, writes an inverse to the undo ledger, and
  notifies the operator; `/undo` replays the inverse correctly. Check:
  `uv run pytest tests/test_undo_ledger.py -k round_trip_inverse` → passes.
- [ ] An unregistered/no-inverse mutation still falls back to the existing gated-pause
  behavior rather than proceeding unpaused. Check:
  `uv run pytest tests/test_undo_ledger.py -k no_inverse_falls_back_to_pause` → passes.
- [ ] An unknown or malformed envelope directive halts the run and names the
  unrecognized directive (no silent proceed). Check:
  `uv run pytest tests/test_adjustment_envelope.py -k unknown_directive_fails_closed`
  → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

## Out-of-scope / non-goals

- A separate control file per writer (quiesce / pause-points / andon-cord each get their
  own file) instead of one shared envelope schema.
- A new standing poll loop; this issue only hooks existing boundaries
  (`plugins/saga/scripts/outcome.py:696`, `/work` segment boundary).
- Changing team-execution's existing iteration caps
  (`consensus-protocol.md:17`, `validator-execution-order.md:27`).
- Backfilling inverse operations onto every mutation in the fleet — only the operations
  named in R10 get a registered inverse in v1.
- Changing `/outcome`'s HALT-not-degrade backend-selection semantics
  (`{#outcome-backend-degrade-stance}`).
- A new operator-facing dashboard or chat control surface.

### Files expected to change
Indicative only; exact set is `/plan`'s to determine.

- `plugins/saga/references/adjustment-envelope.md` — new schema doc (versioned control-file
  format).
- `plugins/saga/scripts/outcome.py` — poll the envelope at the existing tick-quiescence
  boundary (`:696`).
- `plugins/saga/skills/work/SKILL.md` and its segment-boundary logic — poll the envelope
  at `/work` segment boundaries; wire `pause_after`.
- `plugins/saga/scripts/undo_ledger.py` — new module: inverse-op registry + `/undo`
  replay command.
- `plugins/team-execution/skills/team-execution/references/` — new andon-cord signal lane
  (Step B1 rule) wired alongside `consensus-protocol.md` and
  `validator-execution-order.md`.
- `tests/test_adjustment_envelope.py` — new test file: quiesce drain, pause_after
  boundary, andon blocks next wave, unknown-directive fail-closed.
- `tests/test_undo_ledger.py` — new test file: round-trip inverse per registered
  operation, no-inverse falls back to pause.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`
  — version bump if the plugin behavior/schema surface changes.
- `.claude-plugin/marketplace.json` — metadata sync for affected plugins.
- `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md` — entries for the new
  envelope schema, andon-cord lane, and undo ledger.

## Release-surface checklist

Because this issue changes plugin behavior and adds a new schema/command surface,
update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump (andon-cord lane).
- [ ] `.claude-plugin/marketplace.json` — metadata sync for `saga` and `team-execution`.
- [ ] `plugins/saga/CHANGELOG.md` — entry for adjustment-envelope schema, quiesce, pause
  points, undo ledger, `/undo` command.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry for the andon-cord signal lane.
- [ ] Version/metadata drift-guard tests updated to reflect the new commands/schema
  (per CLAUDE.md step 6 — installed-plugin metadata must tell the same story as the diff).

### Verification
```bash
# New envelope + writer tests
uv run pytest tests/test_adjustment_envelope.py -v
uv run pytest tests/test_undo_ledger.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```

Expected: all green; quiesce/pause/andon scenario tests pass; undo-ledger round-trip
tests pass for every registered reversible operation; unknown-directive test asserts a
fail-closed halt.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`,
  slug `pf-midrun-adjustment-envelope`
- Source type: ideation issue-map (Gate B consolidation)
- Source title: Mid-run operator control surface — adjustment envelope

### Intent

A run-start intent envelope (the operator's up-front directives) has no mid-run counterpart: once a `/work` or `/outcome` run is dispatched, an operator or a worker has no durable, polled surface to raise "pause," "stop," "re-tier," or "this mutation needs review" without killing the run or hand-editing state. This capability ships **one** documented, versioned control-file schema — the adjustment envelope — polled at existing segment and frontier boundaries, that carries four related directives under one roof: an operator-raised quiesce sentinel, plan-declared pause points, a worker-raised andon-cord halt, and an act-log-inverse-notify posture for reversible mutations so pauses are reserved for irreversibles.

### Context library links

_none_

### Tests to add or update

- `tests/test_adjustment_envelope.py`
- `tests/test_undo_ledger.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/372
- Number: 372
- Created at: 2026-07-04T07:52:49.759952+00:00

