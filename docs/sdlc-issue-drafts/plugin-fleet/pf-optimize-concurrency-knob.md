---
title: "enhancement: re-add a rescoped, defaulted-off max_concurrent to /optimize that engages the original removal decision"
repo: infiquetra-claude-plugins
type: enhancement
tier: quick-win
objective: "Govern fleet concurrency and reclaim leaked resources"
wave: wave-1
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: medium, backend: inline, external_llm: none}
---

# enhancement: re-add a rescoped, defaulted-off max_concurrent to /optimize that engages the original removal decision

### Intent
`/optimize` deliberately shed `ce-optimize`'s `max_concurrent` fan-out as one item in a bundle
(git-worktree-per-experiment isolation + parallel fan-out + auto-commit/auto-merge of experiment
branches) — all of which "re-enter only" via the heavyweight Phase-4 operator-choice escalation,
today recorded narratively rather than as machinery (`plugins/saga/skills/optimize/SKILL.md:17-19`).
This issue re-adds *only* a concurrency ceiling to the default `/optimize` path — no worktree
isolation, no auto-merge — sourced from the shared `ConcurrencyPolicy` primitive
(`{#pf-concurrency-policy-spec}`), and turns the narrated Phase-4 escalation into a real,
defaulted-off `max_concurrent` field on the experiment-log schema. The shared concurrency
registry also gains an explicit `serial-by-design` marker so `/optimize`'s concurrency=1 default
reads as a declared invariant, not an unguarded gap. Field absent (today's behavior) must remain
byte-identical to current serial execution.

## Problem / Motivation

- **The shed was a bundle; concurrency governance is separable from isolation/merge, and that
  separability is the explicit revisit condition.** `plugins/saga/skills/optimize/SKILL.md:17-19`:
  "The default path SHEDS `ce-optimize`'s git-worktree-per-experiment isolation, its parallel /
  `max_concurrent` fan-out, and its auto-commit / auto-merge of experiment branches. Those
  re-enter only [with the heavy path]." Isolation and auto-merge were shed for safety/simplicity
  reasons — one-variable measurement contamination and unreviewed branch merges — that do not
  apply to a bare rate-limit ceiling. Today there is no way to re-add the ceiling without dragging
  back the whole apparatus.
- **The escalation path is narrated prose today, not a typed field — exactly the
  aspiration-not-machinery failure the fleet's grounding brief calls out.**
  `plugins/saga/skills/optimize/SKILL.md:19-20`: "Those re-enter only by an explicit
  operator-choice escalation (Phase 4), recorded narratively. The loop runs serial ... by
  default." There is no schema field an operator can set; the escalation exists only as
  documentation.
- **The fleet's only orchestration-level cap has no home for a declared, intentional
  serial-by-design exception.** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 notes
  the sole existing cap (`VERIFY_N_CAP`, `plugins/saga/scripts/execution_spec.py:114`) and that
  "team-execution reviewer fan-out, `/outcome` leaf dispatch, and engine bridges are unbounded."
  `/optimize`'s deliberate concurrency=1 currently looks identical to an unbounded site that
  "forgot to cap" rather than a declared invariant — the shared cap registry (built by
  `{#pf-concurrency-policy-spec}`, facets `T13-F1-2`/`T13-F4-7`) has no vocabulary yet for a
  serial-by-design exception.
- **Binding constraint this issue must not violate:** `{#tier-vocab-ordering}` — tier tuples are
  ordered escalation ladders. The `max_concurrent` field's default-null/serial behavior and its
  Phase-4-gated escalation must be expressed as an ordered ladder (serial default → explicit
  operator escalation), not a flat on/off toggle.

## Definition of Done

Merged PR(s) delivering:

1. `plugins/saga/skills/optimize/SKILL.md` documents a rescoped concurrency ceiling on the
   default path — explicitly *not* worktree isolation or auto-merge — wired to the shared
   `ConcurrencyPolicy` primitive, with the original bundle-shed rationale (isolation/merge
   remain shed) cited inline.
2. The `/optimize` experiment-log schema gains an optional `max_concurrent` field, default
   `null` (meaning serial, i.e. today's behavior), settable only via explicit Phase-4 operator
   escalation.
3. The shared concurrency-registry vocabulary (in `plugins/saga/scripts/execution_spec.py` or
   its `ConcurrencyPolicy` module) gains a `serial-by-design` marker, applied to `/optimize`'s
   default context, so the cap resolver returns `1` for `/optimize` and the registry lists it as
   a named exception rather than an unbounded gap.
4. `docs/engineering-journal/DECISIONS.md` records why `/optimize` stays serial by default and
   the concrete revisit-when condition (Phase-4 escalation demonstrably needed), matching the
   fleet's already-adopted decision-entry format.
5. A schema/behavior test proving: field absent → serial (byte-identical to current behavior);
   field set → the resolved cap comes from `ConcurrencyPolicy`, not a bespoke `/optimize`-local
   literal; and the registry resolver returns `1` for the `/optimize` context when
   `max_concurrent` is unset.

Verify: `doc-review` on the `SKILL.md` diff confirming isolation/auto-merge remain shed; a schema
test asserting default-serial and explicit-set-only activation; a registry test asserting the
`serial-by-design` resolver value for `/optimize`.

### Acceptance criteria
- [ ] **AC1 (T13-F1-5, primary).** The default `/optimize` path documents and wires a concurrency
  ceiling sourced from `ConcurrencyPolicy`, while worktree isolation and auto-commit/auto-merge
  remain explicitly shed. Check: a diff of `plugins/saga/skills/optimize/SKILL.md` shows the new
  ceiling language plus retained "isolation/auto-merge re-enter only via Phase 4" language; doc
  review confirms no regression to the shed apparatus.
- [ ] **AC2 (T13-F2-6).** The `/optimize` experiment-log schema has an optional `max_concurrent`
  field defaulting to `null` (serial). Check: `uv run pytest tests/test_optimize_schema.py -k
  max_concurrent_default_serial` → passes, asserting `null` resolves to serial (width 1)
  execution.
- [ ] **AC3 (T13-F2-6).** The field only activates on an explicit operator set (Phase 4), never
  implicitly. Check: `uv run pytest tests/test_optimize_schema.py -k
  max_concurrent_explicit_set_only` → an unset field never produces parallel fan-out; an
  explicitly-set field does.
- [ ] **AC4 (T13-F1-5).** With the field absent, `/optimize`'s emitted/executed behavior is
  byte-identical to pre-change serial behavior. Check: `uv run pytest
  tests/test_optimize_schema.py -k field_absent_byte_identical` → a golden-output comparison of
  the experiment loop with and without this change, field unset, passes.
- [ ] **AC5 (T13-F4-5).** The shared concurrency registry carries a `serial-by-design` marker for
  `/optimize`, and the resolver returns `1` for the `/optimize` context. Check: `uv run pytest
  tests/test_concurrency_policy.py -k optimize_serial_by_design` → passes.
- [ ] **AC6 (T13-F4-5).** `docs/engineering-journal/DECISIONS.md` contains an entry naming why
  `/optimize` stays serial and its revisit-when condition (Phase-4 escalation demonstrably
  needed). Check: `grep -n "optimize.*serial-by-design\|serial-by-design.*optimize"
  docs/engineering-journal/DECISIONS.md` → matches a dated entry.
- [ ] **AC7.** The escalation path is spec-driven (a settable field), not merely narrated in prose.
  Check: `grep -n "max_concurrent" plugins/saga/skills/optimize/SKILL.md` → references the typed
  schema field, not only narrative "Phase 4" prose.

### Out-of-scope / non-goals
**In scope:** a `max_concurrent` field on the `/optimize` experiment-log schema (default null =
serial), wiring that field's resolution through the shared `ConcurrencyPolicy` primitive, a
`serial-by-design` registry marker for `/optimize`, the `SKILL.md` doc update, and the
`DECISIONS.md` entry.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Re-introducing `ce-optimize`'s git-worktree-per-experiment isolation or auto-commit/auto-merge
  of experiment branches — these stay shed; only the bare concurrency ceiling re-enters.
- Building the `ConcurrencyPolicy` primitive itself (resolution ladder, wave chunking, tier
  weighting, per-lane overrides) — that is `{#pf-concurrency-policy-spec}`'s scope. This issue is
  a consumer of that primitive, not its builder, and is blocked on it landing first.
- Any change to `/optimize`'s hard degenerate gates, stopping rules, or LLM-judge phase — the
  concurrency ceiling only bounds experiment fan-out width, not the measurement or judging logic.
- Any Phase-4 UX/CLI surface for setting `max_concurrent` beyond the schema field itself — how an
  operator invokes the escalation is `/plan`'s concern, not specified here.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T13-F1-5` | `plugins/saga/skills/optimize/SKILL.md:17-18`: "The default path SHEDS `ce-optimize`'s git-worktree-per-experiment isolation, its parallel / `max_concurrent` fan-out, and its auto-commit / auto-merge ... Those re-enter only [with the heavy path]." The shed is a bundle; concurrency governance is separable — that is the revisit engagement. | primary |
| `T13-F2-6` | `plugins/saga/skills/optimize/SKILL.md:17-20`: "Those re-enter only by an explicit operator-choice escalation (Phase 4), recorded narratively. The loop runs serial ... by default." Reconciles narrated escalation into a typed, defaulted-off schema field. | facet |
| `T13-F4-5` | `plugins/saga/skills/optimize/SKILL.md:18-20` (same shed passage). Records the serial default as a declared `serial-by-design` registry exception rather than re-adding a fan-out knob outright. | facet |

**Binding decisions this issue builds on / must not contradict:**
- `{#tier-vocab-ordering}` — tier tuples are ordered escalation ladders; the serial-default →
  Phase-4-escalation path must read as an ordered ladder, not a flat toggle.
- Depends on `{#pf-concurrency-policy-spec}` (the `ConcurrencyPolicy` primitive, `T13-F1-2` et
  al.) landing first — this issue consumes that primitive's resolution ladder rather than
  building a bespoke `/optimize`-local cap.
- `/optimize`'s own binding shed decision (`plugins/saga/skills/optimize/SKILL.md:17-19`) — this
  issue explicitly does not reverse the isolation/auto-merge shed; only the bare concurrency
  ceiling re-enters.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** a bounded schema-field addition plus a doc/registry update over an existing,
  well-documented shed decision and an existing (dependency-provided) validation pattern — not
  novel design or adversarial judgment. Sonnet/medium matches the fleet's mechanical,
  deterministic work-shape heuristic; no external-LLM chaperone dispatch is warranted.

## Release-Surface Checklist

This issue changes `/optimize`'s documented behavior (a new schema field, a doc update to
`SKILL.md`) and adds a shared-registry marker, so the following must update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the `/optimize`
      schema/behavior change.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description kept in sync with the
      `plugin.json` bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the `max_concurrent` field, its
      default-serial/explicit-escalation behavior, and the `serial-by-design` registry marker.
- [ ] Drift-guard/version-metadata tests (repo's existing marketplace/plugin-metadata drift
      tests) updated or confirmed still green against the version bump.

## Files Expected to Change

- `plugins/saga/skills/optimize/SKILL.md` — documents the rescoped concurrency ceiling, retains
  the isolation/auto-merge shed language, cites the `ConcurrencyPolicy` wiring.
- `plugins/saga/scripts/execution_spec.py` (or the `ConcurrencyPolicy`/registry module it lands
  in) — adds the `serial-by-design` marker and resolver entry for `/optimize`.
- `/optimize`'s experiment-log schema module (location depends on where the schema currently
  lives, e.g. under `plugins/saga/skills/optimize/` or `plugins/saga/scripts/`) — adds the
  optional `max_concurrent` field, default `null`.
- `docs/engineering-journal/DECISIONS.md` — new entry recording the serial-by-design rationale
  and revisit-when condition.
- `tests/test_optimize_schema.py` (new or extended) — default-serial, explicit-set-only, and
  byte-identical-when-absent tests.
- `tests/test_concurrency_policy.py` (extended) — `serial-by-design` resolver test for
  `/optimize`.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_optimize_schema.py::test_max_concurrent_default_serial` — field absent/null
  resolves to serial (width 1).
- `tests/test_optimize_schema.py::test_max_concurrent_explicit_set_only` — the field never
  activates fan-out implicitly; only an explicit operator-set value does.
- `tests/test_optimize_schema.py::test_field_absent_byte_identical` — golden-output comparison
  proving today's serial behavior is unchanged when the field is absent.
- `tests/test_concurrency_policy.py::test_optimize_serial_by_design` — the registry resolver
  returns `1` for the `/optimize` context and lists it as a named `serial-by-design` exception.

### Verification
```bash
# New /optimize schema tests: default-serial, explicit-set-only, byte-identical-when-absent
uv run pytest tests/test_optimize_schema.py -v

# Registry serial-by-design marker/resolver test
uv run pytest tests/test_concurrency_policy.py -k optimize_serial_by_design

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; unsetting `max_concurrent` reproduces byte-identical serial output; setting
it routes through `ConcurrencyPolicy` rather than a bespoke local cap; the registry resolver
reports `1` with a `serial-by-design` label for `/optimize`.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan. Note: this issue is blocked on
`{#pf-concurrency-policy-spec}` (the `ConcurrencyPolicy` primitive) landing first, since this
issue consumes that primitive rather than building its own cap mechanism.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json` (ids `T13-F1-5`,
  `T13-F2-6`, `T13-F4-5`)
- Source type: ideation survivors + issue-map consolidation
- Source title: Re-add a rescoped, defaulted-off max_concurrent to /optimize that engages the
  original removal decision

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/skills/optimize/SKILL.md`
- `plugins/saga/scripts/execution_spec.py`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `tests/test_optimize_schema.py`

### Tests to add or update

- `tests/test_concurrency_policy.py`
- `tests/test_optimize_schema.py`

### Objective

"Govern fleet concurrency and reclaim leaked resources"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/354
- Number: 354
- Created at: 2026-07-04T07:47:39.595180+00:00

