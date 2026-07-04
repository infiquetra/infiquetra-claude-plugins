---
title: "enhancement: write-ownership lane manifest + marketplace-CI lint across saga / mission-control / deploy"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
---

# enhancement: write-ownership lane manifest + marketplace-CI lint across saga / mission-control / deploy

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

## Summary

Today, nothing in the marketplace CI job stops a script in one plugin's write lane from
reaching across into another plugin's owned mutation surface — e.g. a `deploy` script
calling `gh issue`, or a `saga` script writing board fields that are `mission-control`'s to
own. The ship-ceremony ownership boundary between `saga`, `mission-control`, and `deploy` is
currently prose-only (scattered across skill docs and CLAUDE.md conventions), not a
machine-checked contract. This issue ships a durable, machine-readable ownership-lanes
manifest plus a lint script wired into the existing marketplace CI job that fails the build
on a cross-lane mutation and passes on the current (clean) tree.

## Problem Frame

The three-plugin ship/board/deploy seam has a real, recorded ownership-ambiguity history:

- `docs/plans/2026-07-03-plugin-fleet-ideation-2026-07-03/survivors/T7.json`, entry
  `T7-F1-7` ("Ship-ceremony ownership contract: a documented handoff protocol across saga /
  mission-control / deploy") was killed as a duplicate specifically because it proposed only
  "a prose contract + drift test," while `T7-F4-5` (absorbed by this issue) was kept as "the
  stronger enforcement version (machine-checkable lane manifest + marketplace-CI grep lint)
  rather than a prose contract + drift test." The prose-only shape was explicitly rejected —
  this issue must ship the machine-checked lane manifest, not documentation alone.
- `T7-F3-7` ("The ceremony is owned by no one — name the seam contract") was independently
  killed as a duplicate of `T7-F5-8`'s typed-handoff-with-ack mechanism, noting "the
  machine-checked contract is T7-F4-5" — i.e. this issue is the one place in the surviving
  roster that actually owns turning the seam-ownership question into an enforced check,
  rather than a richer handoff protocol (that richer protocol is out of scope here; see
  Scope & non-goals).
- The repo's own release-surface discipline is already prose-enforced and known to drift:
  `CLAUDE.md` step 6 under Development Workflow requires that "For every plugin behavior,
  schema, command, prompt, or user-facing guidance change, update the plugin release
  surfaces in the same PR" — `plugin.json`, `marketplace.json`, `CHANGELOG.md`, and any
  drift-guard tests — but nothing today lints that a change actually stayed inside its
  plugin's own release-surface files, or flags when a script from one plugin's directory
  invokes a command whose write authority belongs to a different plugin (e.g. a
  `plugins/deploy/` script shelling out to `gh issue create`, which is `mission-control`'s
  domain).
- The existing marketplace CI job already runs plugin-manifest and marketplace-registry
  validation (`.github/workflows/ci.yml:72-76`: "Validate plugin manifests" →
  `scripts/validate_plugins.py`, then "Validate marketplace registry" →
  `marketplace/validator/validate.py`), giving this lint a natural, already-wired-in home
  rather than a new CI job to stand up.

## Requirements

R1. A durable, version-controlled ownership-lanes manifest exists (proposed:
`marketplace/ownership_lanes.json` or `scripts/ownership_lanes.json`) enumerating, per
plugin directory (`saga`, `mission-control`, `deploy`, and any other plugin under
`plugins/`), the write-mutation surfaces it owns — at minimum: which `gh` subcommands
(`gh issue`, `gh pr`, `gh api projects/...`) and which board/status-write calls each
plugin's scripts are permitted to invoke directly.

R2. A lint script (proposed: `scripts/check_ownership_lanes.py`) statically scans each
plugin's `scripts/` (and other executable-bearing) directories for invocations of
`gh`/board-mutation calls that are not in that plugin's declared lane per the manifest, and
exits non-zero naming the offending file, line, and the out-of-lane call when it finds one.

R3. The lint is wired into the existing marketplace CI job in `.github/workflows/ci.yml`
(alongside the current "Validate plugin manifests" / "Validate marketplace registry" steps)
so a cross-lane mutation fails CI on any PR, not just on manual review.

R4. The lint passes clean against the current tree (no false positives against today's
`saga`, `mission-control`, and `deploy` scripts).

R5. The lint fails against a seeded, throwaway cross-lane mutation (a `deploy`-lane script
calling `gh issue`) used as the test fixture, and the failure message names the violating
file and the lane it crossed into.

R6. The manifest and lint are documented (README or an inline module docstring) with the
ownership boundary rationale, so a future plugin author can extend the manifest without
reverse-engineering the lint's regex/AST logic.

### Acceptance criteria
- [ ] **AC1 (T7-F4-5 primary).** `marketplace/ownership_lanes.json` (or equivalent path) exists,
  is valid JSON, and enumerates write-mutation lanes for at least `saga`, `mission-control`,
  and `deploy`. Check: `python3 -c "import json; json.load(open('marketplace/ownership_lanes.json'))"`
  exits `0`.
- [ ] **AC2.** `scripts/check_ownership_lanes.py` exists and, run against the current tree,
  exits `0` with no violations reported. Check:
  `uv run python scripts/check_ownership_lanes.py` → exit `0`.
- [ ] **AC3 (ac_sketch, seeded-violation gate).** A test fixture that plants a cross-lane
  mutation — a `deploy`-lane script calling `gh issue` — causes the lint to fail with a
  message naming the file and the crossed lane. Check:
  `uv run pytest tests/test_check_ownership_lanes.py -k seeded_violation` → passes (asserts
  non-zero exit + expected message substring from a fixture invocation, not a live edit to
  `plugins/deploy/`).
- [ ] **AC4.** The lint is invoked as a step in `.github/workflows/ci.yml`'s marketplace job,
  alongside `scripts/validate_plugins.py` and `marketplace/validator/validate.py`. Check:
  `grep -n "check_ownership_lanes.py" .github/workflows/ci.yml` returns a match, positioned
  after the existing "Validate plugin manifests" / "Validate marketplace registry" steps.
- [ ] **AC5.** Running the lint against the real, unmodified `saga`, `mission-control`, and
  `deploy` plugin directories today produces zero violations (proves R4 / no false
  positives). Check: `uv run python scripts/check_ownership_lanes.py --verbose` output
  contains no `VIOLATION` lines.
- [ ] **AC6.** Full repo quality gate stays green. Check:
  `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
- **In scope:** the ownership-lanes manifest, the lint script, its CI wiring, and tests
  proving both the clean-pass and seeded-fail cases for the three named plugins (`saga`,
  `mission-control`, `deploy`).
- **Out of scope — richer cross-plugin handoff protocol.** The positive-ack typed-handoff
  baton across saga → deploy → mission-control (absorbed separately under `T7-F5-8`) is not
  this issue's job; this issue only gates *unauthorized* mutation, it does not build the
  authorized-handoff mechanism.
- **Out of scope — prose ownership contract as a standalone deliverable.** `T7-F1-7`'s
  documented-handoff-protocol framing was explicitly killed in favor of this issue's
  machine-checked shape; do not substitute a Markdown ownership doc for the manifest +
  lint pair as the primary deliverable (a short doc explaining the manifest is fine per R6,
  but it is not the gate).
- **Out of scope — extending lane coverage beyond the three named plugins.** Other plugins
  under `plugins/` (`home-lab-ops`, `redis-channel`, `unifi`, `agy`, `team-execution`) may be
  added to the manifest opportunistically but are not required for this issue's acceptance;
  the manifest schema must not preclude adding them later.
- **Out of scope — runtime/dynamic enforcement.** This is a static, CI-time lint over
  checked-in scripts, not a runtime guard intercepting live `gh` calls during an agent
  session.
- **Minimal blast radius:** no existing plugin behavior changes; the only new coupling is
  the new CI step and the new manifest/lint files.

## Grounding References

- Absorbed idea: `T7-F4-5` — "Write-ownership lane manifest + marketplace-CI lint that
  enforces it" (primary; source:
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`). `dod_sketch`: "Merged
  ownership-lanes manifest + check_ownership_lanes.py wired into the marketplace CI job;
  lint fails on a seeded cross-lane mutation (deploy script calling `gh issue`) and passes on
  the current tree."
- Duplicate context (not absorbed, informative only): `T7-F1-7` (killed, "kept_duplicate_of":
  `T7-F4-5`) and `T7-F3-7` (killed, "kept_duplicate_of": `T7-F5-8`, noting "the machine-checked
  contract is T7-F4-5") — both confirm the prose-contract framing was rejected in favor of
  this issue's enforcement shape.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, section 2 (binding-decision
  register) — no binding decision directly contradicts this issue; it is a net-new CI gate,
  not a revisit of `/outcome`'s derived-status or external-engine gatekeeper decisions.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, sections 5-6 (pre-existing
  `QUEUED.md` seeds and recurring-pain themes) — release-surface drift and cross-plugin
  ownership ambiguity are recurring pain points this repo's own CLAUDE.md already tries to
  cover by policy (step 6, Development Workflow); this issue converts that policy into a
  checked gate for the write-mutation subset of that surface.
- CI anchor: `.github/workflows/ci.yml:72-76` — existing "Validate plugin manifests" /
  "Validate marketplace registry" steps in the marketplace job; this issue's new lint step
  is added alongside them, not as a new job.
- Repo convention anchor: `CLAUDE.md`, "Development Workflow" step 6 — the release-surface
  parity requirement this lint operationalizes for the ownership-boundary subset.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** mechanical, deterministic scope — a manifest schema, a static-scan
  lint script, one new CI step, and fixture-driven tests. No architectural judgment call or
  adversarial review is required beyond what a sonnet-tier implementer + the repo's existing
  code-review gate already covers; no justification for opus is needed.

## Release-Surface Checklist

This issue adds a new CI-enforced script but does not change any single plugin's runtime
behavior, schema, command, or prompt — it constrains what plugin scripts are *allowed* to
call. Per `CLAUDE.md` Development Workflow step 6, treat the following as required only if
the manifest is later scoped as living inside a specific plugin's directory (e.g.
`plugins/saga/`) rather than at repo root under `marketplace/` or `scripts/`:

- [ ] If the manifest/lint lands under a specific plugin's directory rather than repo-root
  `marketplace/`/`scripts/`, update that plugin's `plugin.json` version and
  `CHANGELOG.md`.
- [ ] If any plugin's `SKILL.md` or agent doc changes to describe the new ownership
  boundary, update that plugin's `.claude-plugin/plugin.json` and `CHANGELOG.md` in the same
  PR.
- [ ] `.claude-plugin/marketplace.json` — update only if this issue's artifacts are
  registered as a new plugin entry (not expected; default plan is repo-root tooling under
  `scripts/`/`marketplace/`, which does not require a marketplace entry).
- [ ] Add or confirm a drift-guard test asserting the new CI step stays wired (AC4) so a
  future workflow edit can't silently drop the lint.
- [ ] If no plugin's behavior, schema, command, or prompt actually changes (expected outcome
  for this issue), explicitly note in the PR description that the release-surface checklist
  is not applicable, per the same CLAUDE.md step.

## Definition of Done

- `marketplace/ownership_lanes.json` (or equivalent versioned path) merged, declaring
  write-mutation lanes for `saga`, `mission-control`, and `deploy`.
- `scripts/check_ownership_lanes.py` merged, wired as a new step in the marketplace job of
  `.github/workflows/ci.yml`.
- `tests/test_check_ownership_lanes.py` merged, covering both the clean-pass case (AC2/AC5)
  and the seeded cross-lane-violation case (AC3) via a throwaway fixture, not a live edit to
  `plugins/deploy/`.
- Full suite green per AC6.

### Files expected to change

Indicative only; `/plan` determines the exact set.

- `marketplace/ownership_lanes.json` — new ownership-lanes manifest.
- `scripts/check_ownership_lanes.py` — new lint script.
- `.github/workflows/ci.yml` — new CI step in the marketplace job.
- `tests/test_check_ownership_lanes.py` — new tests (clean-pass + seeded-violation fixture).

### Tests to add or update

- Clean-pass: lint against the real `saga`, `mission-control`, `deploy` plugin directories
  reports zero violations.
- Seeded-violation: a fixture directory/file simulating a `deploy`-lane script calling
  `gh issue` causes the lint to exit non-zero and name the file + crossed lane.
- Manifest schema: malformed or missing manifest causes the lint to fail loud with a clear
  error, not a silent pass.

### Verification

```bash
# Lint runs clean against the real tree
uv run python scripts/check_ownership_lanes.py

# Seeded-violation fixture trips the lint
uv run pytest tests/test_check_ownership_lanes.py -k seeded_violation

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: lint exits `0` against the real tree; the seeded-violation test passes (proving the
lint fails loud on a planted cross-lane mutation); full suite/lint/type-check all green.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json` (id `T7-F4-5`)
- Source type: ideation survivor (absorbed into issue map)
- Source title: Write-ownership lane manifest + marketplace-CI lint that enforces it

### Intent

Today, nothing in the marketplace CI job stops a script in one plugin's write lane from reaching across into another plugin's owned mutation surface — e.g. a `deploy` script calling `gh issue`, or a `saga` script writing board fields that are `mission-control`'s to own. The ship-ceremony ownership boundary between `saga`, `mission-control`, and `deploy` is currently prose-only (scattered across skill docs and CLAUDE.md conventions), not a machine-checked contract. This issue ships a durable, machine-readable ownership-lanes manifest plus a lint script wired into the existing marketplace CI job that fails the build on a cross-lane mutation and passes on the current (clean) tree.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/431
- Number: 431
- Created at: 2026-07-04T08:11:41.326579+00:00

