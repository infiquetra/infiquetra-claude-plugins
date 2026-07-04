---
title: "capability: outcome draft — refine raw text into a clarity-checked node skeleton, with a $0 deterministic parser for structured notes"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Ship run-start intent envelope for lifecycle autonomy"
wave: wave-1
---

# capability: outcome draft — refine raw text into a clarity-checked node skeleton, with a $0 deterministic parser for structured notes

## Objective

Ship run-start intent envelope for lifecycle autonomy (`Objective: Ship run-start intent
envelope for lifecycle autonomy`, wave-1).

## Problem / motivation

`/outcome start <id> <objective>` already exists and creates the branch-local spec
(`docs/outcomes/<id>/outcome-spec.json` + store) — see the verb table at
`plugins/saga/skills/outcome/SKILL.md:48`. But that verb assumes the operator hands it an
`<objective>` that is already a well-formed, gate-passable string plus (implicitly) a node
skeleton; nothing in the `/outcome` surface today turns raw, unstructured operator input —
a brain-dumped paragraph, or a scratch markdown file of checklist items — into that
structured form first.

- **Ungrounded activity-phrased objectives pass through unrefined.** `OutcomeSpec.validate`
  (`plugins/saga/scripts/outcome_spec.py:425`, `:431`) and `Node.validate`
  (`outcome_spec.py:456`) fail loud on structural defects (missing fields, bad references,
  schema violations), but neither checks whether the objective string is *outcome-shaped* —
  activity-phrased ("work on the auth flow") rather than a measurable direction+threshold
  claim. `start` will happily accept and persist an unrefined objective; there is no rubric
  gate between raw operator text and the committed spec.
- **No deterministic path exists for already-structured notes.** An operator who already has
  a markdown checklist or heading tree (e.g. scratch notes from a planning session) has no
  faster path than hand-authoring node dicts or going through the full LLM `draft` refiner —
  there is no zero-cost, deterministic `parse_structured_input()` that recognizes a
  checklist/heading shape and emits a node skeleton directly, nor a `start --from-notes`
  entry point that would consume it.
- **`outcome_decompose.py`'s existing safety net is drafting, not intake.** The
  decomposition module's module docstring (`plugins/saga/scripts/outcome_decompose.py`,
  header block) states the runner **drafts** a subplot DAG and the **operator reviews**
  before anything dispatches — "mandatory safety net against a mis-drafted graph (R20)".
  That R20 review gate exists for *in-flight* graph edits (draft/prune/lazy-grow/elaborate-
  in-place/promote, R21); it is not wired to a run-start intake path that turns raw
  unstructured operator text into the initial skeleton in the first place. This issue wires
  a new `draft` verb's output through that same clarity/validation posture at run start,
  it does not modify R20/R21's in-flight edit semantics.
- **Binding decision this issue must engage.** The `/outcome` campaign binding-decision row
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:47`, "`/outcome` campaign
  (U1–U11)") establishes: "Derived-on-read status, never committed status fields;
  HALT-not-degrade; backend menu off-by-default with host-conditional degrade; cost ledger =
  leaf-produced fact." A structured-intake path must not commit a partial or ambiguous spec
  under HALT-not-degrade — an ambiguous parse must halt loud with no partial file written,
  never silently emit a best-guess skeleton.
- **Operator ask is explicit and pre-existing.** `docs/plans/2026-07-03-plugin-fleet-
  grounding-brief.md:90-97` (§5, "Pre-existing seeds — this repo's QUEUED.md") lists this
  class of intake-refinement idea among the direct operator-ask seeds carried into ideation,
  and the seed itself (`S-24`, "`/outcome` structures small unstructured input") states the
  ask directly: "operator statement — `/outcome ... structure small unstructured input`."

Net effect: today an operator with raw notes (prose or a checklist) has no supported path
from that text into a valid `/outcome` skeleton — they either hand-author node dicts, feed
an already-refined objective to `start`, or go around the tool entirely. There is also no
zero-token path for the common case where the input is already checklist/heading-shaped.

## Definition of Done

A merged PR that:

1. Adds a `draft` verb to the `/outcome` CLI/skill surface (alongside `start`, `graph`,
   `advance`; verb table at `plugins/saga/skills/outcome/SKILL.md:48-50`) that takes a raw
   unstructured string and:
   - Runs it through an `outcome_clarity` rubric (Claude as verifier-of-record, per
     `{#external-engines-never-gatekeepers}` — external engines are never gatekeepers of a
     gated decision; this rubric check is a Claude-run gate, not delegated) that assesses
     whether the input yields a measurable direction+threshold objective.
   - Feeds a passing rubric result into the existing `R20` review-gate posture
     (`plugins/saga/scripts/outcome_decompose.py`, module docstring) before any skeleton is
     committed — the drafted skeleton is presented for operator review, mirroring the
     existing draft/review safety net rather than inventing a new one.
   - On a failing/ambiguous rubric result, halts with no partial spec file written
     (HALT-not-degrade, per the `/outcome` campaign binding decision).
2. Adds a deterministic, zero-token `parse_structured_input()` function that recognizes a
   markdown checklist or heading-tree shape in the raw input and emits node dicts directly
   (no LLM call), and wires it behind a new `start --from-notes <path>` entry point on the
   existing `start` verb (`outcome/SKILL.md:48`).
   - When the input is not checklist/heading-shaped (e.g. free prose), `parse_structured_
     input()` raises a HALT sentinel — it does not fall through to a best-effort partial
     parse, and no partial spec is written.
3. Both paths validate the resulting skeleton via the existing `OutcomeSpec.validate()` /
   `Node.validate()` machinery (`outcome_spec.py:425`, `:431`, `:456`) before persisting —
   neither path invents a new validation mechanism.
4. Is verified by tests asserting the acceptance criteria below.
5. Does not change `start`'s existing behavior when invoked without `--from-notes`, and does
   not change R20/R21's in-flight graph-edit semantics in `outcome_decompose.py`.

### Acceptance criteria
- [ ] **AC1 (T8-F1-5, primary).** An activity-phrased raw string (e.g. "work on the auth
      flow") run through `draft` yields a measurable direction+threshold objective (not the
      unrefined activity phrase) and a node skeleton that passes `OutcomeSpec.validate()`.
      Test: `draft` on a fixture activity-phrased string produces an objective string
      containing an explicit direction and threshold, and the resulting spec's `validate()`
      raises no error.
- [ ] **AC2 (T8-F1-5).** `draft`'s clarity rubric is Claude-run (verifier-of-record), not
      delegated to an external engine, per `{#external-engines-never-gatekeepers}`. Test:
      the `draft` implementation's rubric-check call path contains no external-engine
      dispatch (codex/agy) in its gating branch — inline code inspection assertion in the
      test suite (e.g. `grep`-style static check or call-graph assertion) confirms no
      external-engine import/call sits on the gate path.
- [ ] **AC3 (T8-F1-5).** A `draft` input whose rubric result is ambiguous/failing halts with
      no partial spec file written. Test: a fixture prose input engineered to fail the
      clarity rubric raises the halt path, and no `outcome-spec.json` (or equivalent partial
      artifact) exists on disk afterward.
- [ ] **AC4 (T8-F6-4, primary).** A markdown checklist fixture run through
      `parse_structured_input()` yields exactly N node dicts matching the checklist's item
      count, with no LLM call made. Test: a fixture checklist with a known item count N
      parses to N nodes, and the test asserts zero calls to any LLM-invocation seam (mocked
      and asserted not-called).
- [ ] **AC5 (T8-F6-4).** A prose (non-checklist, non-heading) fixture run through
      `parse_structured_input()` raises the HALT sentinel, and no partial spec is written.
      Test: a free-prose fixture raises the documented HALT exception type, and no
      `outcome-spec.json` (or equivalent) exists on disk afterward.
- [ ] **AC6 (T8-F6-4).** `start --from-notes <path>` wires `parse_structured_input()`'s
      output into the existing `start` verb's spec-creation path
      (`outcome/SKILL.md:48`) and the resulting spec passes `OutcomeSpec.validate()`/
      `Node.validate()` unchanged from the manual-authoring path. Test: `start --from-notes`
      against a checklist fixture produces a spec file identical in validated shape to one
      hand-authored with equivalent nodes.
- [ ] **AC7 (S-24, dedup-merged).** A short (1–2 item) unstructured prompt produces a valid
      1–2 node outcome envelope without manual scaffolding, via either the `draft` or
      `--from-notes` path (operator's choice is not gated by this issue). Test: a one-line
      raw string and a one-item checklist each independently produce a 1-node valid envelope
      end to end.
- [ ] **AC8.** Neither new path changes `start`'s existing (non-`--from-notes`,
      non-`draft`) behavior, nor R20/R21's in-flight graph-edit semantics in
      `outcome_decompose.py`. Test: the existing `outcome_decompose.py` / `start`-without-
      flags test suite passes unchanged.

### Out-of-scope / non-goals
- **In scope:** the `draft` verb (LLM clarity-rubric path), `parse_structured_input()` (the
  deterministic zero-token path) and its `start --from-notes` wiring, and validation against
  the existing `OutcomeSpec.validate()`/`Node.validate()` machinery.
- **Out of scope / non-goals:**
  - Any change to R20/R21's in-flight graph-edit legality rules
    (`outcome_decompose.py` — draft/prune/lazy-grow/elaborate-in-place/promote) — this issue
    is a run-start intake path, not an in-flight editing change.
  - Any change to `start`'s existing spec-creation behavior when invoked without
    `--from-notes` — the flag is additive.
  - Backend/degrade posture or spend-ceiling capture at dispatch time (a separate, already-
    drafted `/outcome` issue, `pf-outcome-backend-spend-envelope`) — this issue is about
    intake/authoring, not dispatch-seam gating.
  - Handling arbitrarily large or multi-file unstructured input — the deterministic parser
    targets "small unstructured input" per the S-24 seed's own framing; large/ambiguous
    corpora remain out of scope for v1 and would need a fast-follow.
  - Building a new clarity rubric authoring UI — the rubric is a fixed check wired into
    `draft`, not an operator-configurable scoring surface.

## Grounding References

- **T8-F1-5** (primary) — "`outcome draft`: refine a raw brain-dump into a clarity-checked
  objective + node skeleton" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json`).
  DoD sketch: "Merged PR adding a `draft` verb wiring the outcome_clarity rubric (Claude as
  verifier-of-record) feeding the R20 gate; verified by a test where an activity-phrased raw
  string yields a measurable direction+threshold objective and a skeleton that `validate()`s."
- **T8-F6-4** (facet) — "$0 zero-LLM parser: markdown checklist/headings -> node draft, HALT
  on ambiguity" (same survivors file). DoD sketch: "Merged PR adding a deterministic
  `parse_structured_input()` (checklist/heading tree->node_dicts, else raise HALT) +
  `start --from-notes`; verified by tests where a checklist fixture yields N nodes and a
  prose fixture raises the HALT sentinel with no partial spec written. Distinct: zero-budget
  deterministic path vs F1-5's LLM refiner."
- **S-24** (dedup-merged seed) — "/outcome structures small unstructured input"
  (same survivors file). Basis: "operator statement '/outcome ... structure small
  unstructured input'." DoD sketch: "Merged /outcome path that turns a short unstructured
  prompt into a minimal structured DAG/envelope. Verify: a one-line ask produces a valid
  1-2 node outcome envelope without manual scaffolding."
- **Consolidation rationale** (from the issue map): same target — unstructured input becomes
  a valid DAG — via two complementary mechanisms: the LLM clarity-rubric refiner and the
  zero-token checklist/heading parser with HALT-on-ambiguity; S-24 is the dedup-map-folded
  seed for the same target.
- **Binding decisions engaged (must not be contradicted):**
  - `/outcome` campaign (U1–U11) register row
    (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:47`): derived-on-read status,
    HALT-not-degrade, backend menu off-by-default with host-conditional degrade, cost ledger
    = leaf-produced fact. This issue's HALT-on-ambiguity behavior (AC3, AC5) is the direct
    application of HALT-not-degrade to the intake seam.
  - `{#external-engines-never-gatekeepers}` (#283) — Claude is verifier-of-record for every
    gated decision; codex/agy are generator / advisory-reviewer / non-gated worker only. The
    `draft` verb's clarity rubric must be Claude-run, not delegated (AC2).
- **Existing mechanism this issue extends** (not replaces):
  `plugins/saga/skills/outcome/SKILL.md:48` (`start <id> <objective>` verb table entry),
  `plugins/saga/scripts/outcome_decompose.py` (module docstring: R20 review-before-dispatch
  safety net, R21 in-flight edit rules), `plugins/saga/scripts/outcome_spec.py:425`, `:431`,
  `:456` (`OutcomeSpec.validate()` / `Node.validate()`).

## Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** both paths extend existing, well-documented seams — the `start` verb
  table and the `OutcomeSpec`/`Node` validation machinery — rather than inventing new
  architecture. The deterministic parser is mechanical pattern-matching over markdown
  structure; the `draft` verb's rubric-gating logic follows the already-settled
  verifier-of-record posture (`{#external-engines-never-gatekeepers}`) rather than deciding
  it. No novel design judgment beyond wiring two intake paths into existing gates — does not
  warrant opus/high.

## Release Surface Checklist

This adds a new `draft` verb and a new `start --from-notes` flag to the `/outcome` surface
inside the `saga` plugin, so the same PR must also update:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — matching version/metadata for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new `draft` verb (LLM clarity-rubric
      refiner) and `parse_structured_input()` / `start --from-notes` (deterministic
      zero-token parser).
- [ ] `plugins/saga/skills/outcome/SKILL.md` — verb table addition for `draft` and the
      `--from-notes` flag on `start`.
- [ ] Any version/metadata drift-guard tests in `tests/` that assert plugin.json /
      marketplace.json / CHANGELOG stay in lockstep — confirm they pass with the bump.

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/outcome.py` — `draft` verb wiring and `start --from-notes` flag.
- `plugins/saga/scripts/outcome_spec.py` (or a new `outcome_intake.py`) —
  `parse_structured_input()` (deterministic parser) and the `outcome_clarity` rubric
  integration point.
- `plugins/saga/scripts/outcome_decompose.py` — feeding `draft`'s output into the existing
  R20 review-gate posture (no change to R20/R21 semantics themselves).
- `plugins/saga/skills/outcome/SKILL.md` — verb table + `references/outcome-spec.md`
  updates documenting `draft` and `--from-notes`.
- `tests/test_outcome_draft.py` (or equivalent) — clarity-rubric, deterministic-parser, and
  HALT-sentinel tests.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface bump per checklist above.

### Tests to add or update
- Test: activity-phrased raw string → `draft` → measurable direction+threshold objective +
  `validate()`-passing skeleton (AC1).
- Test: `draft`'s rubric-gate call path makes no external-engine call (AC2).
- Test: rubric-failing prose input → halt, no partial spec on disk (AC3).
- Test: checklist fixture with N items → `parse_structured_input()` → N node dicts, zero LLM
  calls (AC4).
- Test: free-prose fixture → `parse_structured_input()` → HALT sentinel, no partial spec on
  disk (AC5).
- Test: `start --from-notes` against a checklist fixture → spec shape identical to
  hand-authored equivalent, passes `validate()` (AC6).
- Test: one-line raw string and one-item checklist each → valid 1-node envelope end to end
  (AC7).
- Test: existing `start` (no flags) and existing `outcome_decompose.py` R20/R21 suites pass
  unchanged (AC8).

### Verification
```bash
uv run pytest tests/test_outcome_draft.py -v
uv run pytest tests/test_outcome_spec.py tests/test_outcome_decompose.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the new `draft`/`--from-notes` tests pass alongside the full existing
`/outcome` spec and decompose suites (no regression to `start`'s no-flag behavior or to
R20/R21 in-flight edit semantics).

## Handoff maturity

requirements-ready

## Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json` (ids `T8-F1-5`,
  `T8-F6-4`, `S-24`) and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`.
- Source type: ideation issue-map (`issue-map-final.json`, slug
  `pf-outcome-draft-unstructured`).
- Source title: outcome draft — refine raw text into a clarity-checked node skeleton, with a
  $0 deterministic parser for structured notes.

### Intent

`/outcome start <id> <objective>` already exists and creates the branch-local spec (`docs/outcomes/<id>/outcome-spec.json` + store) — see the verb table at `plugins/saga/skills/outcome/SKILL.md:48`. But that verb assumes the operator hands it an `<objective>` that is already a well-formed, gate-passable string plus (implicitly) a node skeleton; nothing in the `/outcome` surface today turns raw, unstructured operator input — a brain-dumped paragraph, or a scratch markdown file of checklist items — into that structured form first.

### Context library links

_none_

### Objective

"Ship run-start intent envelope for lifecycle autonomy"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/374
- Number: 374
- Created at: 2026-07-04T07:53:24.986112+00:00

