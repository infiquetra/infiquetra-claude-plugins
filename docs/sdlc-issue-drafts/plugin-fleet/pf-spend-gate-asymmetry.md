---
title: "enhancement: spend-delta machinery — silent-cheap/ask-expensive classifier, worth-it receipts, relative lever, and spend authority"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Make tier+effort a first-class priced resolvable lever"
---

# enhancement: spend-delta machinery — silent-cheap/ask-expensive classifier, worth-it receipts, relative lever, and spend authority

### Intent
Give `/plan` and `/work` a single shared primitive for reasoning about tier-spend deltas, then use it
to close four related gaps in how `{model, effort}` tier changes are proposed, justified, approved, and
recorded:

1. A `spend_delta(old_tier, new_tier) -> {cheapen | escalate | lateral}` classifier, built directly on
   the ordered `MODELS`/`EFFORTS` tuples `segment_units()` already trusts
   (`plugins/saga/scripts/execution_spec.py:49-53`, `:1474-1475`), so every lever in the codebase
   answers "is this more or less expensive?" identically instead of hand-rolling its own notion of
   "more expensive."
2. A `validate()` hard-block requiring any above-`sonnet/medium`-baseline tier row (`opus`, `fable`,
   `xhigh` in either axis) to carry a one-line "worth it because…" justification plus a named
   adjacent-cheaper fallback rung, so premium spend is always self-justifying and always one
   documented downgrade away.
3. A relative three-way override lever (`cheaper` / `as-proposed` / `dearer`) computed by walking one
   notch along the same ordered ladder, instead of forcing the operator to re-pick an absolute tier out
   of the full `MODELS × EFFORTS` closed enum.
4. An optional per-repo `.saga/spend-authority.json` delegation-of-authority matrix that lets the
   classifier's silent/ask split be configured rather than hardcoded, with a documented default when
   the file is absent.

None of this machinery exists today. `plan/SKILL.md:299-304` documents a per-unit tier-table heuristic
with a rationale column, but the table has no fallback field, no justification field, and no relative
adjustment path — the operator picks or overrides an absolute tier from prose alone. The ordering
comment at `execution_spec.py:49-53` ("ORDERING IS LOAD-BEARING… MODELS is strongest-first and EFFORTS
is weakest-first") already treats `MODELS`/`EFFORTS` as an escalation ladder for `segment_units()`'s own
upgrade-only merge, but nothing else in the codebase reuses that ordering to classify a spend delta,
compute an adjacent rung, or gate on missing justification. `docs/engineering-journal/LEARNINGS.md:164-179`
(`{#tier-vocab-ordering}`) records the exact ordering contract this issue's classifier and relative-adjust
helper are built on top of, and warns that the two axes (membership vs. ordering) have separate contracts
that only one of them currently validates.

### Problem / motivation
- **No shared spend-direction primitive.** `execution_spec.py` already computes tier ordering internally
  (`min(MODELS.index(...))` / `max(EFFORTS.index(...))` at `execution_spec.py:1474-1475`) but only for
  `segment_units()`'s own merge. Any other lever that needs to know "is this tier more or less expensive
  than that one" has no function to call and would reimplement the index arithmetic — exactly the drift
  `{#tier-vocab-ordering}` (`docs/engineering-journal/LEARNINGS.md:164-179`) warns "a tuple used for
  membership *and* ordering has two contracts, and only one shows up in the validator" already produced
  once for `segment_units()` itself.
- **Premium tiers are silently un-self-justifying.** `plan/SKILL.md:299-304`'s tier table has a
  `Rationale` column and documents that `fable/xhigh` is "available as a per-unit override, never a
  default" (`plan/SKILL.md:304`), but nothing requires a plan author to say *why* an above-baseline row
  is worth it, and nothing names a cheaper fallback the operator could pick instead. A plan can ship an
  `opus/high` unit with zero justification and no documented downgrade path.
- **The override UX forces an absolute re-pick.** Today overriding a proposed tier means picking a new
  absolute `{model, effort}` pair out of the full closed enum in `plan/SKILL.md`'s tier table, even
  though the common operator move — mined from how tier changes are actually discussed — is "one notch
  cheaper" or "one notch more expensive," not "re-derive the whole tier from scratch."
- **The silent-cheap/ask-expensive rule lives only in intake prose, not in code.** The asymmetric
  approval intent (cheapening proceeds silently, spend-increasing always asks) is a design tension from
  this ideation round's intake brief, not a machine-checked property of any plan or spec today. There is
  no per-repo way to configure where the silent/ask line sits, and no defined default behavior when no
  such configuration exists.

### Key decisions carried from ideation
- **One classifier, reused everywhere (T12-F4-3, primary).** `spend_delta(old, new)` is the single
  primitive every lever calls to decide whether to ask; it is derived from the exact ordered tuples
  `execution_spec.py` already trusts, so the asymmetric approval rule is enforced identically wherever
  it is invoked, not re-implemented per caller.
- **Fallback and justification are mandatory, not advisory (T12-F1-3).** Every above-baseline row is
  required — via a `validate()` hard-block, the same style of loud-fail `execution_spec.py` already
  uses at spec construction — to carry both a `worth it because…` justification and a named
  adjacent-cheaper rung. Missing either field fails validation; this is not a lint warning.
- **The override lever is relative, not absolute (T12-F3-6).** `cheaper` / `as-proposed` / `dearer`
  walks one notch along the existing ordered ladder via the same `min`/`max`-index arithmetic
  `segment_units()` uses. The ladder has hard boundaries: the cheapest tier cannot cheapen further, the
  most expensive tier cannot escalate further.
- **Authority is configurable, absence has a safe default (T12-F5-3).** The delegation-of-authority
  matrix (`.saga/spend-authority.json`) is optional per-repo config, modeled on standard
  signature-authority / approval-limit tables (the corporate procurement pattern this idea is directly
  borrowed from). When absent, the resolver defaults to `ask` for anything above `sonnet` — the safe
  side of the asymmetry — rather than defaulting to silent or failing to resolve.

## Definition of Done
A merged change to `plugins/saga/scripts/execution_spec.py` (plus a `plan/SKILL.md` docs update) that
ships all four facets as one coherent mechanism, backed by tests:

- `spend_delta(old_tier, new_tier) -> Literal["cheapen", "escalate", "lateral"]` implemented on the
  existing `MODELS`/`EFFORTS` ordering (reusing, not duplicating, the `segment_units()` index
  arithmetic).
- `ExecutionSpec`/`Unit` `validate()` hard-blocks any unit whose tier is above the `sonnet/medium`
  baseline (on either axis) and is missing a `worth_it_because` justification string or a
  `cheaper_fallback` field naming an adjacent, strictly-cheaper tier.
- A relative-adjust helper `adjacent_tier(tier, direction: Literal["cheaper", "dearer"]) -> Tier` used
  by a `plan/SKILL.md` override-step edit offering the three-way relative choice in place of an
  absolute re-pick; boundary calls (cheapest→cheaper, dearest→dearer) raise rather than silently
  clamping or wrapping.
- A `.saga/spend-authority.json` schema plus a resolver in `execution_spec.py` that stamps each unit
  `silent` or `ask` from the matrix (with optional per-lifecycle-stage overrides), defaulting to `ask`
  for anything above `sonnet` when no matrix file is present.
- New/updated tests in `tests/test_execution_spec.py` (or a new `tests/test_spend_delta.py`) covering
  the classifier, the validate hard-block, the ladder-boundary relative lever, and the absent-matrix
  default.
- Release-surface updates: `plugins/saga/.claude-plugin/plugin.json` version bump,
  `.claude-plugin/marketplace.json` entry sync, `plugins/saga/CHANGELOG.md` entry, and any drift-guard
  metadata tests updated in the same PR (this repo's CLAUDE.md step 6 requires code/tests and installed
  metadata to tell the same story).

### Out-of-scope / non-goals
- No changes to the emitted `.workflow.js` runtime execution path beyond consuming the new `silent`/`ask`
  stamp and the `worth_it_because`/`cheaper_fallback` fields already present on the spec — this issue
  does not touch the completeness-gate or verify-panel machinery.
- No UI/approval-prompt implementation for the "ask" path (e.g. a batched-approval prompt surface) —
  this issue delivers the classification and the spec-level stamp; how an "ask" is actually surfaced to
  the operator (single prompt vs. batched escalation set) is a separate follow-on.
- No retroactive backfill of `worth_it_because`/`cheaper_fallback` onto any existing plan artifacts —
  the hard-block applies to newly authored/validated specs going forward.
- No change to `team-execution`'s markdown emitter/protocol — this issue is scoped to
  `execution_spec.py`'s spec construction and validation surface and the `plan/SKILL.md` authoring flow
  that feeds it; the team-execution markdown path is out of scope for this issue.
- No new external configuration surface beyond the single `.saga/spend-authority.json` file per repo;
  no global/cross-repo authority registry.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/execution_spec.py` — `spend_delta()` classifier, `adjacent_tier()` relative
  helper, `validate()` hard-block for above-baseline `worth_it_because`/`cheaper_fallback`, and the
  `.saga/spend-authority.json` resolver stamping `{silent | ask}` on each unit.
- `plugins/saga/skills/plan/SKILL.md` — tier-table schema update (fallback/justification columns) and
  override-step edit offering the three-way relative (`cheaper`/`as-proposed`/`dearer`) choice.
- `.saga/spend-authority.json` — new example/default schema file (or documented absence behavior).
- `tests/test_execution_spec.py` (or new `tests/test_spend_delta.py`) — classifier, validate hard-block,
  ladder-boundary, and absent-matrix-default tests.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface sync for the behavior change.

### Tests to add or update
- `spend_delta("sonnet/medium", "opus/high") == "escalate"` and
  `spend_delta("opus/high", "sonnet/low") == "cheapen"`; a same-cost transposition classifies
  `"lateral"`.
- `validate()` fails on an above-baseline unit (e.g. `opus/high`) missing `worth_it_because` or
  `cheaper_fallback`, and passes when both are present with a genuinely cheaper named fallback.
- `adjacent_tier()` boundary tests: the cheapest tier in the ladder cannot go cheaper; the most
  expensive tier cannot go dearer; both raise rather than clamp/wrap silently.
- Resolver test: a mixed-tier spec against a populated `.saga/spend-authority.json` produces the exact
  expected `{silent, ask}` partition; a spec with no matrix file present defaults every above-`sonnet`
  unit to `ask`.

### Acceptance criteria
- [ ] `spend_delta("sonnet/medium", "opus/high") == "escalate"` and
      `spend_delta("opus/high", "sonnet/low") == "cheapen"`, derived from the existing
      `MODELS`/`EFFORTS` ordering (no duplicated index logic). Check:
      `uv run pytest tests/test_execution_spec.py -k spend_delta` → passes.
- [ ] A spec unit above the `sonnet/medium` baseline (e.g. `opus/high`, `fable/xhigh`) missing either
      `worth_it_because` or `cheaper_fallback` fails `validate()`; the same unit with both fields
      present, naming a genuinely cheaper adjacent rung, passes. Check:
      `uv run pytest tests/test_execution_spec.py -k worth_it_fallback` → passes.
- [ ] `adjacent_tier()` computes the correct one-notch-cheaper/dearer tier for a mid-ladder tier, and
      raises (not clamps/wraps) when called at either ladder boundary. Check:
      `uv run pytest tests/test_execution_spec.py -k adjacent_tier_boundary` → passes.
- [ ] `plan/SKILL.md`'s override step offers the three-way relative choice
      (`cheaper`/`as-proposed`/`dearer`) in place of an absolute tier re-pick. Check: manual doc review
      confirms the override-step text names all three options and defers to `adjacent_tier()`.
- [ ] A per-repo `.saga/spend-authority.json` matrix, when present, resolves each unit in a mixed-tier
      spec to the exact expected `{silent, ask}` partition the matrix specifies. Check:
      `uv run pytest tests/test_execution_spec.py -k spend_authority_matrix` → passes.
- [ ] When `.saga/spend-authority.json` is absent, every unit above `sonnet` in a mixed-tier spec
      resolves to `ask` (the safe default), never `silent`. Check:
      `uv run pytest tests/test_execution_spec.py -k spend_authority_absent_default` → passes.
- [ ] Release-surface metadata (`plugins/saga/.claude-plugin/plugin.json` version,
      `.claude-plugin/marketplace.json` entry, `plugins/saga/CHANGELOG.md`) is updated in the same PR
      as the behavior change. Check: `git diff --stat` for the PR includes all three paths alongside
      `execution_spec.py`.
- [ ] Full suite, format, lint, and types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# New spend-delta / validate / relative-lever / authority-matrix tests
uv run pytest tests/test_execution_spec.py -k "spend_delta or worth_it_fallback or adjacent_tier_boundary or spend_authority" -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the classifier/validate/relative-lever/authority-matrix tests each demonstrate the
specific behavior named in their acceptance criterion.

## Grounding References
- `T12-F4-3` (primary, quick-win) — shared `spend_delta` classifier deriving silent-vs-ask ordering.
  Basis: `plugins/saga/scripts/execution_spec.py:49-53` (ORDERING IS LOAD-BEARING comment) and this
  ideation round's intake tension 1 (asymmetric approval: cheapening silent, escalation always asks).
- `T12-F1-3` (facet, structural) — mandatory `worth it, because…` + named cheaper fallback on every
  above-baseline tier row. Basis: intake brief §Resolved tensions 4 ("expensive tier never a silent
  default; carries a cheaper fallback"), `plugins/saga/skills/plan/SKILL.md:304` (fable documented as
  override-never-default with no fallback field today), and `{#tier-vocab-ordering}`
  (`docs/engineering-journal/LEARNINGS.md:164-179`, confirming the ordered-ladder mechanism the
  adjacent-cheaper rung is computed from).
- `T12-F3-6` (facet, quick-win) — relative "one notch cheaper/dearer" lever instead of an absolute
  re-pick. Basis: `plugins/saga/scripts/execution_spec.py:49-53` and `:1474-1475` (the exact
  `min(MODELS.index)`/`max(EFFORTS.index)` merge arithmetic the relative-adjust helper reuses) and
  `{#tier-vocab-ordering}` (`docs/engineering-journal/LEARNINGS.md:164-179`).
- `T12-F5-3` (facet, structural) — per-repo `.saga/spend-authority.json` delegation-of-authority matrix
  for silent/ask resolution, absent-matrix default. Basis: standard corporate delegation-of-authority /
  signature-authority matrices (COSO/SOX-style approval-limit tables), operationalizing this ideation
  round's intake asymmetric-approval rule (intake §26-36) as config rather than operator memory.
- Binding decision this issue builds on: `{#tier-vocab-ordering}`
  (`docs/engineering-journal/LEARNINGS.md:164-179`) — "tier vocabulary tuples are ordered escalation
  ladders, not just closed sets"; a tuple used for membership *and* ordering has two contracts, and the
  spend-delta/adjacent-tier machinery in this issue is the second contract's first real consumer beyond
  `segment_units()`.
- Tier heuristic table this issue's justification field extends:
  `plugins/saga/skills/plan/SKILL.md:297-306` (Step 1 — Derive per-unit tiers).

### Recommended executor profile
`sonnet / medium`. This is a mechanical, deterministic extension of an existing, well-understood
ordering primitive (`execution_spec.py`'s `MODELS`/`EFFORTS` tuples and `segment_units()` merge logic) —
adding a classifier function, a validate hard-block, a relative-adjust helper, and a JSON-schema-driven
resolver, all following patterns the module already establishes (`ExecutionSpec.validate` /
`OutcomeSpec.validate` loud-fail style). No architectural judgment or adversarial review is required;
`opus`/higher effort is not justified for this scope. Backend: inline. External-LLM posture: none.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json (ids T12-F4-3 primary,
  T12-F1-3, T12-F3-6, T12-F5-3 facets)
- Source type: ideation
- Source title: Spend-delta machinery: silent-cheap/ask-expensive classifier, worth-it receipts,
  relative lever, and spend authority

### Context library links

_none_

### Objective

"Make tier+effort a first-class priced resolvable lever"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/367
- Number: 367
- Created at: 2026-07-04T07:51:30.121060+00:00

