---
title: "capability: end-to-end lifecycle regression harness on a fixture repo"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
objective: Gate fleet integrity (agent files, prompts, release surfaces)
tier: structural
wave: wave-2
---

# capability: end-to-end lifecycle regression harness on a fixture repo

## Summary

None of the fleet's existing checks exercise the lifecycle skills (`saga:spec`, `saga:plan`,
`saga:work`, `saga:code-review`, `saga:doc-review`, `saga:qa`, `saga:outcome`, …) end-to-end as a
running system. Coverage today is unit-level and structural: agent-registration drift, tool-scope
audits, contract-pairing meta-tests, release-surface parity. All of that verifies the fleet's
*parts*; nothing runs the skills themselves against a real (if toy) repo and asserts that a
lifecycle scenario actually produces the artifacts it claims to — a spec JSON, an appended saga
entry, a gate record, a reclaimed worktree. This capability adds a small fixture repo plus a
scheduled, cheap-tier CI job that drives 3-5 canonical lifecycle scenarios headlessly and asserts
on artifact shape, closing that negative-space gap.

## Problem Frame

The fleet has accumulated per-component tests but never a whole-lifecycle regression suite. Direct
evidence:

- `tests/test_agent_registration_drift.py`, `tests/test_agent_tiering.py`,
  `tests/test_completeness_gate.py` (`tests/test_completeness_gate.py:24-57`), and
  `tests/test_manifest_consumer_matrix.py` all validate one seam each (agent registration, tier
  policy, completeness-gate classification, contract pairing) — none of them invoke a saga skill
  and observe what it actually produces on disk.
- `scripts/validate_plugins.py:21` (`validate_plugin_file`) and `marketplace/validator/validate.py`
  validate plugin *manifests* — structure, not runtime behavior. The engineering journal records
  this validator itself missed a whole scanning-scope bug for months
  (`docs/engineering-journal/LEARNINGS.md` — `validate_plugins.py` only glob-scanned top-level
  `plugins/*.md`, non-recursive, `{#validate-plugins-only-scans-top-level-md}`), which is exactly
  the class of "looks validated, isn't" failure a real fixture-repo run would have caught by
  actually exercising the scan against a nested fixture.
- The recurring-pain themes captured for this ideation round name the gap directly:
  "Local-vs-CI verification parity gaps — CI red on checks local runs passed" and "Subagents idle
  without delivering; stale idle notifications — coordinator must detect and re-ping" (grounding
  brief, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, section 7, patterns 9-10) are
  both failure modes that only show up when a lifecycle scenario is actually *run*, not when its
  static shape is linted.
- Worktree hygiene is a live, unverified concern: the grounding brief records "15 stale abandoned
  saga worktrees in `.worktrees/` inflating the repo 10x+" (section 4) — direct evidence that
  nothing today asserts a lifecycle run reclaims the worktree it opened.
- The closest adjacent machinery — `plugins/saga/references/sandbox-spawn-sites.md` (worktree +
  `saga:readonly-verifier` isolation contract) and `plugins/saga/scripts/execution_spec.py`
  (`Unit.returns` structured-output contract, `:180`) — defines what a correct run should produce,
  but nothing runs a scenario through it and diffs the result against that shape.
- CI today (`.github/workflows/ci.yml`) runs pytest, plugin-manifest validation, marketplace
  validation, ruff, and mypy — all fast, all static. There is no CI job of any kind that drives a
  saga skill against a live (fixture) repo and inspects what it left behind.

## Requirements

R1. A fixture repo lives at `tests/lifecycle-fixture/` — a minimal but real git repository (its own
`.git`, a handful of files, no dependency on the parent repo's history) that lifecycle scenarios
run against, so runs never touch the real `infiquetra-claude-plugins` working tree.

R2. The harness defines 3-5 canonical lifecycle scenarios, each driving one saga skill (or a short
chain) headlessly against the fixture repo end to end — e.g. `saga:spec` → `saga:plan` → `saga:work`
happy path, a `saga:code-review` pass against a seeded diff, and a `saga:outcome` start/advance/resume
round-trip. Each scenario is independently runnable and independently attributable to a failure.

R3. Every scenario asserts artifact shape after the run, not just process exit code: the spec JSON
produced validates against its schema, the saga log gained an appended entry, any required gate
record (e.g. a code-review verdict, a completeness-gate class) is present in the expected location,
and any worktree the scenario opened is reclaimed (absent from `.worktrees/` / `git worktree list`
at teardown).

R4. A scenario failure names the specific artifact-shape violation it hit (e.g. "spec JSON missing
required key `units`", "saga log has no entry after `/work`", "worktree `<path>` still present after
scenario teardown") rather than surfacing only a generic non-zero exit or stack trace.

R5. The harness runs as a scheduled, cheap-tier CI job (cron-triggered, not on every PR) separate
from the existing PR-blocking `ci.yml` jobs (Tests, Validate Plugins, Lint, Type) — it is a
detection instrument for lifecycle-shape regressions, not a merge gate, matching the fleet's
existing pattern of advisory/scheduled checks alongside blocking ones.

R6. The fixture repo and its scenario definitions are documented (a short README under
`tests/lifecycle-fixture/`) so an operator can add a sixth scenario without re-deriving the harness's
conventions from source.

### Out-of-scope / non-goals
- This harness runs saga skills against a fixture repo; it does not replace or duplicate the
  existing structural/unit tests (agent registration, tool-scope, contract pairing, completeness
  gate) — those stay as-is and continue to run on every PR.
- Team-execution's teammate/consensus machinery is out of scope for the first 3-5 scenarios;
  the initial scenario set targets the saga skill chain (`spec`/`plan`/`work`/`code-review`/
  `outcome`). A follow-up can extend the harness to team-execution once the fixture/scenario
  pattern is proven.
- No changes to the existing blocking `ci.yml` jobs — this is an additive, separately-scheduled
  job. It does not gate merges.
- Not a performance or load benchmark — scenarios assert artifact shape, not timing.
- Does not attempt to cover every lifecycle skill in v1; 3-5 canonical scenarios is the deliberate
  initial scope, chosen to prove the harness pattern rather than achieve full coverage in one PR.

## Dependencies / Assumptions

- Assumes saga skills can be driven headlessly (non-interactively) against a target repo path —
  this is already true of every skill invoked via the CLI/agent-driven pattern used elsewhere in
  the fleet (`plugins/saga/scripts/execution_spec.py` — spec authored once, emitted to a runnable
  path).
- Assumes the completeness-gate and worktree-isolation contracts this harness checks against
  (`tests/test_completeness_gate.py`, `plugins/saga/references/sandbox-spawn-sites.md`) remain the
  source of truth for "what a correct run produces" — the harness consumes those contracts, it does
  not redefine them.
- This capability does not change plugin behavior, commands, prompts, or schemas — it is
  additive test/CI infrastructure only. No release-surface files (`plugin.json`,
  `marketplace.json`, `CHANGELOG.md`) require updates for this issue; the release-surface
  checklist below is included per repo convention and should be confirmed empty during review.

### Files expected to change
Indicative only; `/plan` determines the exact set.

- `tests/lifecycle-fixture/` — new fixture repo directory (seed files, its own `.git` history,
  scenario fixtures).
- `tests/lifecycle-fixture/README.md` — scenario/convention documentation (R6).
- `tests/lifecycle-fixture/scenarios/` — one file per canonical scenario (3-5 files).
- `tests/test_lifecycle_regression_harness.py` — the runner + artifact-shape assertion library
  invoked by the scheduled job (repo-root collected, consistent with existing `tests/test_*.py`
  layout).
- `.github/workflows/lifecycle-regression.yml` — new scheduled (cron) workflow, separate from
  `.github/workflows/ci.yml`.

### Tests to add or update
- One test per scenario asserting the full artifact-shape contract (spec JSON validates, saga
  entry appended, gate record present, worktree reclaimed) — passes on a healthy scenario run.
- One negative test per scenario category proving the harness actually detects a violation (e.g.
  seed a run that leaves a worktree behind; assert the harness names it, does not silently pass).
- A meta-test asserting the scheduled workflow file references every scenario file under
  `tests/lifecycle-fixture/scenarios/` (coverage-by-construction, matching the fleet's existing
  pattern in `tests/test_agent_registration_drift.py`).

## Definition of Done

- Fixture repo (`tests/lifecycle-fixture/`, its own `.git`) exists with 3-5 canonical lifecycle
  scenarios under `tests/lifecycle-fixture/scenarios/`, each independently runnable.
- A healthy scenario run asserts all four artifact-shape checks (spec JSON validity, saga-log
  append, gate-record presence, worktree reclamation), and a seeded failure names the specific
  violated artifact shape rather than surfacing a generic exit code.
- The harness runs as a separate, scheduled (cron) CI job — additive, not merged into the
  PR-blocking `ci.yml` and not gating merges.
- `tests/lifecycle-fixture/README.md` documents scenario conventions, and the full suite
  (pytest, ruff format/check, mypy) stays green.

### Acceptance criteria
- [ ] Fixture repo exists at `tests/lifecycle-fixture/` with its own `.git`, isolated from the
  parent repo's working tree. Check: `git -C tests/lifecycle-fixture rev-parse --is-inside-work-tree` → prints `true`, and its `remote -v` differs from the parent repo's.
- [ ] At least 3 and at most 5 canonical lifecycle scenarios exist under
  `tests/lifecycle-fixture/scenarios/`, each independently runnable. Check:
  `uv run pytest tests/test_lifecycle_regression_harness.py --collect-only -q | grep -c scenario` →
  reports a count between 3 and 5.
- [ ] A healthy scenario run asserts spec JSON validity, saga-log append, gate-record presence, and
  worktree reclamation — all four, not a subset. Check:
  `uv run pytest tests/test_lifecycle_regression_harness.py -k healthy_scenario -v` → passes, and
  test output/log names all four assertions as checked.
- [ ] A scenario failure surfaces the specific violated artifact shape, not a generic exit code.
  Check: `uv run pytest tests/test_lifecycle_regression_harness.py -k seeded_failure -v` → passes,
  and asserts the failure message contains one of the named violation strings (e.g.
  `"worktree still present"`, `"saga log missing entry"`).
- [ ] The harness runs as a scheduled CI job separate from the PR-blocking `ci.yml` jobs. Check:
  `.github/workflows/lifecycle-regression.yml` exists, contains an `on: schedule:` trigger, and is
  not a job inside `.github/workflows/ci.yml`.
- [ ] `tests/lifecycle-fixture/README.md` documents how to add a new scenario. Check: file exists
  and contains a section describing scenario file conventions.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# Run the lifecycle regression harness locally (out-of-band, mirrors the scheduled job)
uv run pytest tests/test_lifecycle_regression_harness.py -v

# Confirm scenario count and fixture isolation
uv run pytest tests/test_lifecycle_regression_harness.py --collect-only -q
git -C tests/lifecycle-fixture rev-parse --is-inside-work-tree

# Full repo gate (CI parity, matching CI's mypy scope)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; harness scenario tests pass on a healthy fixture-repo run and demonstrably
fail with a named artifact-shape violation on a seeded-bad run.

## Release-surface checklist

This capability does not change any plugin's behavior, schema, command, or prompt surface, so no
release-surface files are expected to change. Confirm during review:

- [ ] `plugins/*/.claude-plugin/plugin.json` — unchanged (no plugin behavior changed).
- [ ] `.claude-plugin/marketplace.json` — unchanged.
- [ ] `plugins/*/CHANGELOG.md` — unchanged.
- [ ] No version/metadata drift-guard test needs updating, since no plugin surface moved.

## Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is mechanical test/fixture-infrastructure work — scaffolding a fixture
  repo, wiring scenario runners, writing artifact-shape assertions against already-defined
  contracts (completeness-gate classes, worktree-isolation rules, saga-log format). It requires no
  novel architectural judgment or adversarial review posture, so sonnet at high effort (enough to
  carefully wire 3-5 scenarios and their negative-test counterparts without missing an assertion)
  is sufficient; no case for opus or an external-LLM chaperone is present here.

## Grounding References

- **Absorbed idea:** `G-negative-space-7` (survivor set `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`)
  — "Execute the skills: an end-to-end lifecycle regression harness on a fixture repo," frame
  `gap-negative-space`, axis `test-shape-honesty`, tier `structural`, verdict `survive`. `dod_sketch`:
  "`tests/lifecycle-fixture/` toy repo + scheduled cheap-tier CI job running 3-5 canonical lifecycle
  scenarios headlessly with artifact-shape assertions." This is the sole absorbed idea for this
  issue (`consolidation_rationale` in `issue-map-final.json`: "Nothing else exercises the skills
  themselves end-to-end; a fixture repo with canonical scenarios is its own self-contained
  deliverable.").
- **Binding decisions this issue must honor:**
  - `{#readonly-verifier-fallback-ladder-325}` + `{#verify-agent-git-checkout-clobber}` — any
    verify-class spawn inside a scenario (e.g. one that exercises `saga:code-review`) must use the
    readonly profile + worktree isolation, per `plugins/saga/references/sandbox-spawn-sites.md`.
  - `{#operator-choice-framework}` — the harness is doc/CLI-driven scaffolding, not a
    fan-out-reframing of operator choice.
  - `{#plugin-portfolio-groom-17-to-7}` — this issue adds no new plugin; it is test infrastructure
    inside the existing repo layout.
- **Recurring-pain grounding:** grounding brief section 7 patterns 9 ("subagents idle without
  delivering") and 10 ("local-vs-CI verification parity gaps"), and section 4's "15 stale abandoned
  saga worktrees" finding — all are failure modes only a real lifecycle run (not a static lint) can
  catch, which is this issue's reason to exist.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (id `G-negative-space-7`)
  plus `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json` (slug
  `pf-lifecycle-regression-harness`)
- Source type: ideation-survivor
- Source title: End-to-end lifecycle regression harness on a fixture repo

**Absorbed ideas:** G-negative-space-7

### Intent

None of the fleet's existing checks exercise the lifecycle skills (`saga:spec`, `saga:plan`, `saga:work`, `saga:code-review`, `saga:doc-review`, `saga:qa`, `saga:outcome`, …) end-to-end as a running system. Coverage today is unit-level and structural: agent-registration drift, tool-scope audits, contract-pairing meta-tests, release-surface parity. All of that verifies the fleet's *parts*; nothing runs the skills themselves against a real (if toy) repo and asserts that a lifecycle scenario actually produces the artifacts it claims to — a spec JSON, an appended saga entry, a gate record, a reclaimed worktree. This capability adds a small fixture repo plus a scheduled, cheap-tier CI job that drives 3-5 canonical lifecycle scenarios headlessly and asserts on artifact shape, closing that negative-space gap.

### Context library links

_none_

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/428
- Number: 428
- Created at: 2026-07-04T08:10:51.659523+00:00

