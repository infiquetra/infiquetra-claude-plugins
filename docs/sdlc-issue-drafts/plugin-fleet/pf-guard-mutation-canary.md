---
title: "capability: mutation canary proving drift guards have teeth"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: moonshot
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
wave: wave-2
---

# capability: mutation canary proving drift guards have teeth

### Objective
Gate fleet integrity (agent files, prompts, release surfaces)

## Summary

This repository has accumulated a growing family of drift-guard tests — `test_agent_registration_drift.py`,
`test_manifest_consumer_matrix.py`, `test_release_triad.py`, `test_team_execution_pointers.py`,
`test_saga_docs_coverage.py`, `scripts/validate_plugins.py`, `marketplace/validator/validate.py` — each
asserting a specific fleet-integrity invariant (agent discoverability, provenance-manifest sync,
release-surface version lockstep, plugin/marketplace schema). None of them are ever tested against
their own failure mode: nobody proves that a guard that has silently regressed to a no-op (a stale glob,
a loosened regex, a swallowed exception) will actually go red when the invariant it claims to protect is
violated. This issue ships a mutation canary — a small harness that deliberately breaks one guarded
invariant in a throwaway checkout, runs the target guard, and asserts the guard reports failure — plus
a scheduled workflow that runs the canary against every registered guard and a canary log recording the
result.

## Problem Frame

- The fleet's drift-guard family exists specifically because ungrounded/circular claims about plugin
  state have been a recurring failure mode (`CLAUDE.md` Validation Discipline section; repo `CLAUDE.md`
  step 6 requiring plugin release surfaces to move in lockstep). Guards were added reactively, one per
  incident: `tests/test_agent_registration_drift.py` (`#325 R4`, docstring: "Cannot assert the running
  session's agent roster from CI (unobservable), so this guards every repo-side precondition of
  discoverability instead"), `tests/test_release_triad.py` (`U15`/`R17`, asserting `plugins/<name>/.claude-plugin/plugin.json`
  version, `.claude-plugin/marketplace.json` entry version, and `plugins/<name>/CHANGELOG.md` first
  `## <version>` heading stay byte-identical), `tests/test_manifest_consumer_matrix.py` (`R17`, provenance-manifest
  producer/consumer matrix in `saga-spec.md` §13.3 vs. schema fields in `provenance_manifest.py`), and
  `tests/test_team_execution_pointers.py::test_byte_drift_raises_hash_mismatch` (KTD1 temp-index holding-ref
  hash check).
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 finding: "mission-control/saga contract copies
  drifting from source of truth" is a recurring cross-repo pain (2+ repos), and §7 records that "Release-surface
  drift persists despite CLAUDE.md step 6 — room for automation" — i.e. the prose instruction alone does not
  reliably hold, which is exactly why the guard tests above were built, and exactly why nobody has verified
  those guards themselves stay effective as the surfaces they check evolve.
- None of the existing guard tests carry a companion "does this guard actually fire" check. A guard can
  regress to a false-positive-free no-op silently: a regex loosened during an unrelated refactor, a path
  glob that stops matching after a directory rename, an `except Exception: pass` swallowing the real
  assertion. CI only proves "the guard did not fire on today's tree" — it can never distinguish "the tree
  is clean" from "the guard is dead."
- Absorbed idea `T11-F5-8` (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`) names this
  directly: "Chaos Monkey for drift guards: nightly mutation canary proving the guards have teeth,"
  `dod_sketch`: "Merged `tools/wiring_canary.py` that mutates one guarded invariant in a throwaway checkout,
  runs the target guard, and asserts red + scheduled workflow + canary log; verified each guard reports
  RED-as-expected and a weakened guard is flagged toothless."
- This is deliberately a meta-guard over guards other issues ship (e.g. `pf-lever-site-census`'s
  control-surface inventory), so it is only sensible to build after those land and is isolated in its own
  throwaway-checkout machinery (`consolidation_rationale` in
  `/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/c23d3bf9-9081-4727-8e0d-140ebc73f63f/scratchpad/ideation/issue-map/issue-map-final.json`
  entry `pf-guard-mutation-canary`).

## Requirements

R1. A registry file (e.g. `tools/canary_registry.json` or a `CANARY_TARGETS` constant in the canary
    script) names every guard this canary exercises, each entry carrying: the guard's pytest node id or
    script invocation, the guarded invariant in one sentence, and the specific file/line mutation that
    should trip it. Registry seeds with at minimum the four guards named in Problem Frame:
    `tests/test_agent_registration_drift.py`, `tests/test_release_triad.py`,
    `tests/test_manifest_consumer_matrix.py`, `tests/test_team_execution_pointers.py::test_byte_drift_raises_hash_mismatch`.

R2. `tools/wiring_canary.py` creates a throwaway checkout (temp directory copy of the repo tree, never
    the live working tree) for each registry entry, applies that entry's mutation to the copy only,
    invokes the target guard against the mutated copy, and asserts the guard's exit code / pytest result
    is a failure (red). No mutation ever touches the real working tree or is committed.

R3. If a guard runs green against a deliberately-broken invariant, the canary reports that guard as
    **toothless** — a distinct, named outcome from "guard passed" or "guard errored" — and the canary's
    own process exit code is non-zero when any guard is toothless.

R4. The canary supports running a single registered guard by name (for local debugging) and running the
    full registry (for the scheduled job), via a CLI flag (e.g. `--target <guard-id>` / default: all).

R5. A scheduled GitHub Actions workflow (new file, e.g. `.github/workflows/mutation-canary.yml`, since
    `.github/workflows/ci.yml` currently has no `schedule:` trigger) runs the canary against the full
    registry on a recurring cadence and fails the workflow run when any guard is toothless.

R6. Each canary run appends a structured record (guard id, mutation applied, result: `caught` |
    `toothless` | `error`, timestamp) to a canary log (e.g. `docs/engineering-journal/canary-log.jsonl` or
    a workflow-run artifact) so toothless-guard history is inspectable without re-running the canary.

R7. The canary itself is covered by unit tests (`tests/test_wiring_canary.py`) that exercise both branches
    without needing the real target guards: a fixture guard that is known-effective (canary reports
    `caught`) and a fixture guard that is deliberately toothless (canary reports `toothless`), proving the
    canary's own pass/fail logic is correct independent of which real guards are registered.

## Key Flows

F1. **Guard has teeth (expected case).** Canary copies the repo to a throwaway checkout, mutates the
    registered invariant (e.g. renames an agent's on-disk file without updating its frontmatter `name:`
    for the `test_agent_registration_drift.py` entry), runs the target guard against the checkout, guard
    fails as expected → canary records `caught`, exits 0 for that entry.
    **Covers R1, R2, R6.**

F2. **Guard has gone toothless.** Same mutation applied, but the target guard's assertion has regressed
    (simulated in canary's own test suite via a fixture guard — R7 — since deliberately weakening a real
    guard in this repo is out of scope) and passes anyway → canary records `toothless`, non-zero overall
    exit.
    **Covers R3, R6, R7.**

F3. **Scheduled run surfaces regressions without a human triggering it.** The scheduled workflow (R5)
    runs unattended, and any toothless guard fails the workflow run and is visible in canary log history
    (R6) — closing exactly the gap named in the grounding brief's "Release-surface drift persists despite
    CLAUDE.md step 6" finding.
    **Covers R5, R6.**

## Definition of Done

`tools/wiring_canary.py` and its seed registry (`tools/canary_registry.json`) exist and register at least
the four guards named in Problem Frame; each reports `caught` when run against a throwaway checkout with
that guard's deliberate mutation applied, and no mutation ever touches the real working tree (R1, R2). The
canary's own `caught`/`toothless` logic is proven independent of the real guards via fixture-guard tests in
`tests/test_wiring_canary.py` (R3, R7), a scheduled `.github/workflows/mutation-canary.yml` runs the full
registry and fails on any toothless guard (R5), and each run appends a structured record to the canary log
(R6). All Acceptance Criteria and Verification checks below pass green.

### Acceptance criteria
- [ ] AC1. **Covers R1.** `tools/canary_registry.json` (or equivalent) lists at least the four guards named in Problem Frame, each with a guard reference, invariant description, and mutation description. Check: `python3 -c "import json; d=json.load(open('tools/canary_registry.json')); assert len(d) >= 4"` exits 0.
- [ ] AC2. **Covers R2, F1.** Running the canary against the `test_agent_registration_drift.py` registry entry against a throwaway checkout with a deliberately mismatched `name:` frontmatter field reports that guard as `caught` (red-as-expected). Check: `python3 tools/wiring_canary.py --target agent-registration-drift` exits 0 and prints `caught`.
- [ ] AC3. **Covers R2, F1.** Running the canary against the `test_release_triad.py` registry entry against a throwaway checkout with a deliberately bumped `plugin.json` version (and unbumped `marketplace.json`) reports that guard as `caught`. Check: `python3 tools/wiring_canary.py --target release-triad` exits 0 and prints `caught`.
- [ ] AC4. **Covers R3, R7, F2.** The canary's own fixture-guard tests prove the toothless-detection path fires: a fixture guard that always passes, when run against a mutated fixture checkout, is reported `toothless` and causes non-zero exit. Check: `uv run pytest tests/test_wiring_canary.py -k toothless` passes.
- [ ] AC5. **Covers R2.** No mutation applied by the canary is ever visible in `git status` of the real working tree after a canary run (all mutation happens in a `tempfile`-created throwaway checkout, cleaned up after). Check: `python3 tools/wiring_canary.py --target agent-registration-drift && git status --porcelain` produces empty output.
- [ ] AC6. **Covers R4.** `python3 tools/wiring_canary.py --help` documents both `--target <id>` (single guard) and the default full-registry mode. Check: `python3 tools/wiring_canary.py --help` output contains `--target`.
- [ ] AC7. **Covers R5.** `.github/workflows/mutation-canary.yml` exists, has a `schedule:` trigger, and invokes `tools/wiring_canary.py` with no `--target` (full registry). Check: `grep -q "schedule:" .github/workflows/mutation-canary.yml && grep -q "wiring_canary.py" .github/workflows/mutation-canary.yml`.
- [ ] AC8. **Covers R6.** After a canary run, the canary log contains one structured record per registry entry with `guard`, `result`, and `timestamp` fields. Check: `python3 tools/wiring_canary.py && python3 -c " import json, pathlib lines = pathlib.Path('docs/engineering-journal/canary-log.jsonl').read_text().splitlines() rec = json.loads(lines[-1]) assert {'guard', 'result', 'timestamp'} <= rec.keys()"`.
- [ ] AC9. **Covers R7.** `tests/test_wiring_canary.py` exists and covers both the `caught` and `toothless` outcomes using fixture guards, independent of the real registered guards. Check: `uv run pytest tests/test_wiring_canary.py -v` passes with at least one test per outcome.
### Out-of-scope / non-goals
- **In scope:** the canary harness itself, a seed registry of the four already-shipped drift guards named
  above, the scheduled workflow, the canary log, and the canary's own test coverage.
- **Not in scope:** deliberately weakening any real, currently-effective guard in this repository to prove
  the "toothless" branch fires against production code — that would leave the repo's actual guards
  regressed. Toothless-detection is proven exclusively via fixture guards owned by
  `tests/test_wiring_canary.py` (R7), never by mutating a real guard's assertion logic.
- **Not in scope:** building new drift guards. This issue only exercises guards that already exist;
  registering a new guard (e.g. any produced by `pf-lever-site-census`) is a follow-on registry-entry
  addition, not new canary machinery.
- **Not in scope:** a general chaos-engineering framework for runtime/production systems — this is
  narrowly a CI-time / throwaway-checkout mutation harness for static repo-content guards.
- **Not in scope:** auto-remediation of a toothless guard. The canary reports and fails loud; fixing a
  regressed guard is separate follow-up work triaged from the canary log.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** mechanical harness construction (throwaway-checkout copy, subprocess invocation of
  existing pytest/script targets, structured logging) against a well-scoped, already-enumerated set of
  four target guards. No architectural ambiguity or adversarial judgment call above what sonnet/medium
  routinely handles; escalation to opus is not warranted per the model/effort tiering guidance (judgment /
  design / adversarial review → opus; mechanical or deterministic work → sonnet or haiku).

## Release-Surface Checklist

This issue does not change any shipped plugin's runtime behavior, schema, command, or user-facing
skill/agent guidance — it adds a new `tools/` script, a new CI workflow, and new tests, none of which are
plugin-owned surfaces. Per repo `CLAUDE.md` step 6, the release-surface lockstep requirement (plugin.json /
marketplace.json / CHANGELOG.md / drift-guard test updates) applies only when a **plugin's** behavior,
schema, command, or prompt/guidance changes.

- [ ] Confirm no `plugins/<name>/.claude-plugin/plugin.json` version bump is needed (no plugin behavior
      changed). Check: `git diff --stat -- 'plugins/*/.claude-plugin/plugin.json'` is empty.
- [ ] Confirm no `.claude-plugin/marketplace.json` entry changed. Check:
      `git diff --stat -- .claude-plugin/marketplace.json` is empty.
- [ ] Confirm no `plugins/<name>/CHANGELOG.md` entry is required. Check:
      `git diff --stat -- 'plugins/*/CHANGELOG.md'` is empty.
- [ ] If, during implementation, the canary needs to live inside a plugin (e.g. `saga`) rather than
      repo-root `tools/`, re-open this checklist and complete the full plugin release-surface lockstep
      (plugin.json version bump, marketplace.json entry, CHANGELOG.md entry, drift-guard test update).

## Grounding References

- **Absorbed:** `T11-F5-8` (role: primary) — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`.
  `dod_sketch`: "Merged `tools/wiring_canary.py` that mutates one guarded invariant in a throwaway checkout,
  runs the target guard, and asserts red + scheduled workflow + canary log; verified each guard reports
  RED-as-expected and a weakened guard is flagged toothless." `ac_sketch`: "each registered guard reports
  RED-as-expected", "a weakened guard is flagged toothless."
- **Consolidation rationale:**
  `/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/c23d3bf9-9081-4727-8e0d-140ebc73f63f/scratchpad/ideation/issue-map/issue-map-final.json`,
  entry `pf-guard-mutation-canary`: "Meta-guard over every guard other issues ship; only sensible after land,
  isolated in its own throwaway-checkout machinery."
- **Grounding brief:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3 ("mission-control/saga
  contract copies drifting from source of truth", 2+ repos) and §7 ("Release-surface drift persists despite
  CLAUDE.md step 6 — room for automation").
- **Existing guards this canary registers against:** `tests/test_agent_registration_drift.py` (`#325 R4`),
  `tests/test_release_triad.py` (`U15`/`R17`), `tests/test_manifest_consumer_matrix.py` (`R17`),
  `tests/test_team_execution_pointers.py::test_byte_drift_raises_hash_mismatch` (KTD1).
- **Binding decisions this builds on:** `{#readonly-verifier-fallback-ladder-325}` (drift-guard precedent
  pattern this canary extends); `{#plugin-portfolio-groom-17-to-7}` (new-tool sprawl concern — this issue
  is a `tools/` script, not a new plugin, deliberately avoiding that burden).
- **Sibling issue this depends on landing first (per consolidation rationale):** `pf-lever-site-census`
  (control-surface inventory) — not a hard blocker for this issue's initial seed registry, but its output
  is the expected source of future registry entries.

## Files Expected to Change

- `tools/wiring_canary.py` — new mutation-canary harness.
- `tools/canary_registry.json` — new registry of guarded invariants and their mutations.
- `.github/workflows/mutation-canary.yml` — new scheduled workflow.
- `tests/test_wiring_canary.py` — new tests covering the canary's own caught/toothless logic via fixture guards.
- `docs/engineering-journal/canary-log.jsonl` — new append-only canary run log (or equivalent artifact path
  chosen during planning).
- `docs/engineering-journal/LEARNINGS.md` — dated entry once merged, per this repo's always-on journal rule.

## Tests to Add or Update

- `tests/test_wiring_canary.py::test_caught_outcome` — fixture guard that correctly fails on a planted
  mutation is reported `caught`.
- `tests/test_wiring_canary.py::test_toothless_outcome` — fixture guard that incorrectly passes on a
  planted mutation is reported `toothless` and drives non-zero canary exit.
- `tests/test_wiring_canary.py::test_no_mutation_leaks_to_working_tree` — asserts the canary's throwaway
  checkout never touches the real working tree (`git status --porcelain` empty after a run).
- `tests/test_wiring_canary.py::test_registry_loads_seed_entries` — asserts the seed registry contains the
  four named guards.

### Verification
```bash
# Canary's own unit tests (fixture-guard based, independent of real registered guards)
uv run pytest tests/test_wiring_canary.py -v

# Full registry run against real guards (each entry uses a throwaway checkout; real working tree untouched)
python3 tools/wiring_canary.py
git status --porcelain   # expect empty output

# Scheduled workflow shape check
grep -q "schedule:" .github/workflows/mutation-canary.yml
grep -q "wiring_canary.py" .github/workflows/mutation-canary.yml

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; `tools/wiring_canary.py` exits 0 with every registered guard reporting `caught`;
`git status --porcelain` empty after the run.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Intent

This repository has accumulated a growing family of drift-guard tests — `test_agent_registration_drift.py`, `test_manifest_consumer_matrix.py`, `test_release_triad.py`, `test_team_execution_pointers.py`, `test_saga_docs_coverage.py`, `scripts/validate_plugins.py`, `marketplace/validator/validate.py` — each asserting a specific fleet-integrity invariant (agent discoverability, provenance-manifest sync, release-surface version lockstep, plugin/marketplace schema). None of them are ever tested against their own failure mode: nobody proves that a guard that has silently regressed to a no-op (a stale glob, a loosened regex, a swallowed exception) will actually go red when the invariant it claims to protect is violated. This issue ships a mutation canary — a small harness that deliberately breaks one guarded invariant in a throwaway checkout, runs the target guard, and asserts the guard reports failure — plus a scheduled workflow that runs the canary against every registered guard and a canary log recording the result.

### Context library links

_none_

### Files expected to change

- `scripts/validate_plugins.py`
- `marketplace/validator/validate.py`
- `tests/test_agent_registration_drift.py`
- `tests/test_release_triad.py`
- `.claude-plugin/marketplace.json`
- `tests/test_manifest_consumer_matrix.py`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`

### Tests to add or update

- `tests/test_agent_registration_drift.py`
- `tests/test_manifest_consumer_matrix.py`
- `tests/test_release_triad.py`
- `tests/test_team_execution_pointers.py`
- `tests/test_wiring_canary.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/427
- Number: 427
- Created at: 2026-07-04T08:10:33.560016+00:00

