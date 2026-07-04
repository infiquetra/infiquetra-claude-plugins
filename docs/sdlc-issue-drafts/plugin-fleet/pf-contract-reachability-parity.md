---
title: "enhancement: declared-but-unwired seam audit + producer/consumer contract-pairing and parity guards"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
wave: wave-2
---

# enhancement: declared-but-unwired seam audit + producer/consumer contract-pairing and parity guards

## Summary

The fleet declares a model/effort vocabulary and at least one producer/consumer contract
(`ENGINE_INTENTS`) that are not verified end-to-end: parts of the vocabulary are unreachable
outside a single skill, and nothing checks that a value produced on one side of a contract is
ever consumed on the other. This issue builds one contract-symbol registry and three guards on
top of it: a reachability audit script (with an advisory CI job) that reports declared-but-unwired
symbols, a paired-test meta-test that fails when a registered contract lacks a producer- or
consumer-side test, and a static parity guard that fails when a contract key is alive on only one
end. All three guards are read-only / advisory-first — they report and fail tests, they do not
change runtime behavior of any plugin.

## Problem Frame

The fleet's only operator-facing model/effort lever is saga `/plan`'s unit-tier table
(`plugins/saga/skills/plan/SKILL.md:296-310`), which is driven by the vocabulary
`MODELS = ("fable", "opus", "sonnet", "haiku")` / `EFFORTS = ("low", "medium", "high", "xhigh")`
declared in `plugins/saga/scripts/execution_spec.py:52-53`. Verified today:
`fable` and `xhigh` are referenced nowhere else in the fleet outside saga's own plan vocabulary
and tier table (`plugins/saga/skills/plan/SKILL.md:304`, `execution_spec.py:52-53`) — grounded in
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:14-21` ("fable/xhigh unreachable outside
saga plan vocabulary"). Every agent frontmatter across the fleet hardcodes a `model:` field
(35 `model:` occurrences across 34 agent files, verified via
`grep -n 'model:' plugins/*/agents/*.md | wc -l` and `ls plugins/*/agents/*.md | wc -l`), and zero
of them carry an `effort:` field (`grep -rl 'effort:' plugins/*/agents/*.md` returns no matches) —
so there is no dispatch-time override lever anywhere in agent frontmatter, matching the brief's
"zero `effort:` fields ... no dispatch-time override lever anywhere except saga's readonly-verifier
per-call pattern" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:18-20`).

Separately, `ENGINE_INTENTS = ("offload", "second-opinion")` (`execution_spec.py:68`) is a
producer/consumer pair: it is authored and validated in `/plan`
(`execution_spec.py:557-560`, `plan/SKILL.md:303-304`) and is meant to be rendered downstream in
team-execution's Step A7 worker table (`plugins/team-execution/skills/team-execution/SKILL.md:229`
onward, referencing `references/external-engine-workers.md`) — per the grounding brief's corrections
intake, item (c): "`ENGINE_INTENTS` producer/consumer pair — authored in `/plan`
(`plan/SKILL.md:303-304`), rendered in team-execution Step A7 worker table
(`team-execution/SKILL.md:229-233` → `references/external-engine-workers.md`)"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:23-26`). Today nothing statically verifies
that every value a producer can emit for a contract key has a live consumer reference, and nothing
fails a build if one side of a producer/consumer pair drifts (a value added on the producer side,
or removed on the consumer side, silently orphans). There is also no registry that names which
symbols are contracts at all, so there is no place to plug a "does this contract have tests on both
ends" check. Confirmed absent today: no `scripts/audit_wiring.py`, no `tests/test_contract_pairing.py`,
no `tests/test_producer_consumer_parity.py` exist anywhere in the repository (`find . -iname
'*audit_wiring*'` and `find . -iname '*contract_pairing*' -o -iname '*producer_consumer_parity*'`
both return no results).

## Requirements

**Contract-symbol registry (shared foundation)**

R1. A single registry (new module, e.g. `plugins/saga/scripts/contract_registry.py` or an
equivalent data file) enumerates the fleet's known producer/consumer contract symbols, starting
with the two verified cases: the `MODELS`/`EFFORTS` tier vocabulary (producer: `execution_spec.py`
constants + `plan/SKILL.md` tier table; consumer: agent frontmatter `model:`/`effort:` fields
fleet-wide) and `ENGINE_INTENTS` (producer: `execution_spec.py:68`, `plan/SKILL.md:303-304`;
consumer: `team-execution/SKILL.md` Step A7 worker table / `references/external-engine-workers.md`).
Each registry entry names the symbol, its producer location(s), and its consumer location(s).

R2. The registry is the single source both the reachability audit and the two paired-test
meta-tests read from — no duplicated symbol lists between the three guards.

**Reachability audit (declared-but-unwired seam)**

R3. `scripts/audit_wiring.py` (or `plugins/saga/scripts/audit_wiring.py`) walks the registry and
reports, for each registered vocabulary value, every location it is referenced; a value with zero
non-declaration references outside its own producer definition is reported as unreachable.

R4. Running the audit against the current fleet state reports the two known gaps: `fable` and
`xhigh` unreachable outside saga's own plan vocabulary/tier table, and (if still true at
implementation time) the `ENGINE_INTENTS` producer/consumer wiring gap between `execution_spec.py`
and the team-execution worker-table renderer.

R5. The audit runs as an advisory (non-blocking) CI job — it reports findings without failing the
build, consistent with this being a fleet-integrity signal rather than a merge gate.

**Producer/consumer paired-test requirement**

R6. `tests/test_contract_pairing.py` is a meta-test that, for every symbol in the contract
registry, asserts a producer-side test reference and a consumer-side test reference both exist
(as recorded in the registry or discovered via a declared test-reference convention). A registered
contract missing either side fails this meta-test, naming the missing side.

R7. Deleting or omitting a seeded consumer-side test reference for a registered contract causes
`test_contract_pairing.py` to fail, naming the contract and the missing side.

**Producer/consumer parity guard**

R8. `tests/test_producer_consumer_parity.py` statically extracts the current `ENGINE_INTENTS`
values from `execution_spec.py` and cross-references them against the team-execution renderer
(`team-execution/SKILL.md` Step A7 / `references/external-engine-workers.md`), using a
`(producer, consumer)` pairs registry (may be the same registry as R1, or a dedicated pairs table).

R9. A synthetic contract key present on the producer side with no corresponding consumer reference
causes `test_producer_consumer_parity.py` to fail, naming the orphaned key.

## Definition of Done

- A shared contract-symbol registry (R1, R2) plus `scripts/audit_wiring.py` (R3-R5),
  `tests/test_contract_pairing.py` (R6-R7), and `tests/test_producer_consumer_parity.py` (R8-R9)
  are merged, with no duplicated hardcoded symbol lists across the three.
- The reachability audit reports the known `fable`/`xhigh` and `ENGINE_INTENTS` wiring gaps as an
  advisory (non-blocking) CI job.
- Both meta-tests pass on clean fleet state and fail — naming the missing side or orphaned key —
  against seeded fixtures (deleted consumer-side test reference; synthetic producer-only key).

### Acceptance criteria
- [ ] AC1 (R4). Running the reachability audit against current fleet state reports `fable` and
  `xhigh` as unreachable outside `plugins/saga/skills/plan/SKILL.md` and
  `plugins/saga/scripts/execution_spec.py`. Check: `python3 plugins/saga/scripts/audit_wiring.py`
  (or equivalent entry point) exits and its output names both `fable` and `xhigh` as unreachable.
- [ ] AC2 (R6, R7). A registered contract lacking either a producer-side or a consumer-side test
  reference fails the pairing meta-test. Check:
  `uv run pytest tests/test_contract_pairing.py -k missing_consumer_side -v` fails and its output
  names the contract and the missing side, against a fixture with a seeded consumer-side test
  reference deleted.
- [ ] AC3 (R8, R9). A synthetic contract key with no consumer reference fails the parity guard,
  naming the orphaned key. Check:
  `uv run pytest tests/test_producer_consumer_parity.py -k synthetic_orphan_key -v` fails and its
  output names the synthetic key.
- [ ] AC4 (R1, R2). The audit script and both meta-tests read symbol/pair definitions from one shared
  contract-symbol registry module — no duplicated hardcoded symbol lists across the three files.
  Check: `grep -rn "MODELS = \|EFFORTS = \|ENGINE_INTENTS = " scripts/audit_wiring.py
  tests/test_contract_pairing.py tests/test_producer_consumer_parity.py` returns no matches (the
  three files import from the registry rather than re-declaring the vocabulary).
- [ ] AC5 (R5). The audit runs as an advisory CI job that reports findings without failing the build.
  Check: the CI workflow step invoking the audit script is configured non-blocking (e.g.
  `continue-on-error: true` or equivalent), verifiable by inspecting the workflow file diff.
- [ ] AC6. A clean fleet state (no seeded orphan/missing-test fixtures) passes both meta-tests.
  Check: `uv run pytest tests/test_contract_pairing.py tests/test_producer_consumer_parity.py -v`
  exits 0 against the current, un-seeded repository state.

### Out-of-scope / non-goals
- This issue does not add `effort:` fields to any agent frontmatter, does not wire `fable`/`xhigh`
  into new call sites, and does not change team-execution's rendering logic — it only detects and
  reports the existing gap. Closing the reachability gap itself (making `fable`/`xhigh` reachable,
  or removing them from the vocabulary) is separate follow-on work, not this issue.
- The contract-symbol registry starts with the two verified cases (`MODELS`/`EFFORTS` tier
  vocabulary, `ENGINE_INTENTS`). Registering every other declared-but-possibly-unwired symbol
  fleet-wide is out of scope for v1; the registry is designed to be extended later without
  rework, but this issue does not perform that full-fleet enumeration.
- No runtime behavior of any plugin changes. All three guards are read-only analysis plus tests;
  none of them modify `execution_spec.py`, `plan/SKILL.md`, or the team-execution renderer.
- The advisory CI job is non-blocking by design (AC5) — this issue does not promote the audit to
  a blocking gate. Promoting it to blocking, if ever warranted, is a separate decision.

## Grounding References

- `T11-F1-4` (primary) — "Declared-but-unwired seam (reachability) review lens + audit script".
  Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (id `T11-F1-4`);
  `dod_sketch`: "Merged scripts/audit_wiring.py + contract-symbol registry + review-lens doc +
  advisory CI job; verified by reporting the known fable/xhigh + ENGINE_INTENTS gaps and a
  meta-test on a synthetic producer-only symbol." Grounded further in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:14-21`.
- `T11-F1-5` (facet) — "Producer-AND-consumer paired-test requirement for every contract symbol".
  Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (id `T11-F1-5`);
  `dod_sketch`: "Merged contracts registry + tests/test_contract_pairing.py meta-test that fails
  when a registered contract lacks either a producer-side or consumer-side test reference;
  verified by deleting a seeded consumer-side test."
- `T11-F6-7` (facet) — "Producer/consumer parity guard: no contract key alive on only one end".
  Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (id `T11-F6-7`);
  `dod_sketch`: "Merged tests/test_producer_consumer_parity.py statically extracting
  ENGINE_INTENTS keys and cross-referencing the team-execution renderer, plus a (producer,consumer)
  pairs registry; verified a synthetic key with no consumer reference fails naming the orphan."
- Consolidation rationale (from `issue-map-final.json`): "One contract-symbol registry serves all
  three: reachability audit (fable/xhigh, ENGINE_INTENTS gaps), paired-test requirement, and
  no-key-alive-on-one-end parity."
- Binding decisions this builds on (from `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`):
  `{#tier-vocab-ordering}` — tier tuples are ordered escalation ladders, not just closed sets, so
  the registry must preserve `MODELS`/`EFFORTS` ordering semantics, not just membership;
  `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an active concern, reinforcing that this
  work is a shared cross-plugin registry rather than a per-plugin bespoke check;
  `{#external-engines-never-gatekeepers}` (#283) and `{#external-engine-chaperone-dispatch}` (#318)
  — relevant context for why `ENGINE_INTENTS` (`offload`/`second-opinion`) is a real contract worth
  guarding: it governs chaperone-dispatch tier selection, not executor identity.

## Recommended Executor Profile

- Model: sonnet. Effort: medium. Backend: inline. External LLM: none.
- Justification: this is mechanical, deterministic work — writing a registry data structure, a
  static-analysis script that greps/parses known file locations, and two meta-tests with fixed
  fixture-based assertions. No architectural judgment or adversarial review is required beyond
  what is already specified in the acceptance criteria above; per the `executor_profile` in
  `issue-map-final.json` for this slug, sonnet/medium/inline/none is the assigned tier and no
  escalation above sonnet is warranted.

## Release-Surface Checklist

This issue adds a script and tests to `plugins/saga/scripts/` and `tests/` but does not change any
plugin's user-facing behavior, prompts, or schemas. Confirm at PR time whether any of the
following apply and update accordingly; expected outcome for this issue is "no change needed" for
each, but this must be verified, not assumed:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump only if the new script/registry is
      exposed as a new skill-facing command; if it stays an internal `scripts/` utility plus tests,
      no bump is required. Verify at PR time.
- [ ] `.claude-plugin/marketplace.json` — no change expected (no new plugin, no version bump
      unless the plugin.json bump above applies).
- [ ] `plugins/saga/CHANGELOG.md` — add an entry describing the new audit script and meta-tests if
      `plugin.json` is bumped; otherwise still note the addition under an "Unreleased" or
      "Internal" section per repo convention.
- [ ] Drift-guard tests — no existing plugin-metadata drift-guard test should need updating unless
      `plugin.json`/`marketplace.json` change; confirm by running the full metadata drift-guard
      suite (see Verification) and checking it stays green.

## Files Expected to Change

- `plugins/saga/scripts/contract_registry.py` (new) — shared contract-symbol registry.
- `plugins/saga/scripts/audit_wiring.py` (new) — reachability audit script.
- `tests/test_contract_pairing.py` (new) — producer/consumer paired-test meta-test.
- `tests/test_producer_consumer_parity.py` (new) — parity guard meta-test.
- `.github/workflows/*.yml` (or repo's CI config) — add advisory (non-blocking) audit job.
- `plugins/saga/CHANGELOG.md` — entry for the new audit/guard additions.

## Tests to Add or Update

- `tests/test_contract_pairing.py` — new: passes on clean registry state; fails, naming the
  missing side, when a seeded consumer-side test reference is deleted (AC2).
- `tests/test_producer_consumer_parity.py` — new: passes on clean `ENGINE_INTENTS` state; fails,
  naming the orphaned key, when a synthetic producer-only key is injected (AC3).
- Existing full suite must stay green: `uv run pytest`.

### Verification
```bash
# Reachability audit reports the known fable/xhigh + ENGINE_INTENTS gaps
python3 plugins/saga/scripts/audit_wiring.py

# Paired-test meta-test: fails naming the missing side when consumer test is removed
uv run pytest tests/test_contract_pairing.py -k missing_consumer_side -v

# Parity guard: fails naming the orphaned key for a synthetic producer-only symbol
uv run pytest tests/test_producer_consumer_parity.py -k synthetic_orphan_key -v

# Clean-state pass (no seeded fixtures)
uv run pytest tests/test_contract_pairing.py tests/test_producer_consumer_parity.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green except the deliberately-seeded failure-mode checks above, which fail with the
named missing side / orphaned key as specified in AC2 and AC3.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: ideation-synthesis
- Source title: Grounding Brief — Plugin-Fleet Ideation (Gate B)

### Intent

The fleet declares a model/effort vocabulary and at least one producer/consumer contract (`ENGINE_INTENTS`) that are not verified end-to-end: parts of the vocabulary are unreachable outside a single skill, and nothing checks that a value produced on one side of a contract is ever consumed on the other. This issue builds one contract-symbol registry and three guards on top of it: a reachability audit script (with an advisory CI job) that reports declared-but-unwired symbols, a paired-test meta-test that fails when a registered contract lacks a producer- or consumer-side test, and a static parity guard that fails when a contract key is alive on only one end. All three guards are read-only / advisory-first — they report and fail tests, they do not change runtime behavior of any plugin.

### Context library links

_none_

### Files expected to change

- `references/external-engine-workers.md`
- `scripts/audit_wiring.py`
- `tests/test_contract_pairing.py`
- `tests/test_producer_consumer_parity.py`
- `plugins/saga/scripts/contract_registry.py`
- `plan/SKILL.md`
- `team-execution/SKILL.md`
- `plugins/saga/scripts/audit_wiring.py`

### Tests to add or update

- `tests/test_contract_pairing.py`
- `tests/test_producer_consumer_parity.py`

### Objective

"Gate fleet integrity (agent files, prompts, release surfaces)"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/426
- Number: 426
- Created at: 2026-07-04T08:09:36.407475+00:00

