---
title: "enhancement: CI-level delegation integrity — marketplace proof gate on bridge version bumps + fleet delegation monitor"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
objective: Gate fleet integrity (agent files, prompts, release surfaces)
wave: wave-2
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan, ci
risk: medium
handoff_maturity: requirements-ready
---

# enhancement: CI-level delegation integrity — marketplace proof gate on bridge version bumps + fleet delegation monitor

## Summary

Two CI-enforced guards for the "did the delegated bridge actually run and persist?" problem that today
is caught only by manual transcript audits:

1. A **marketplace proof gate**: any PR that bumps the version of a bridge-carrying plugin's
   `marketplace.json` entry (currently `agy`; extensible to any future bridge plugin) must ship a
   valid delegation-proof artifact, or CI fails.
2. A **fleet delegation monitor**: a scheduled/PR-triggered job that sweeps recorded bridge transcripts
   across the fleet and fails on any silent no-op, unrecorded fallback, untokened orphan write, or
   broken proof chain — replacing the current "an operator happened to notice" detection with a
   standing check.

## Problem / Motivation

The fleet has a documented, repeated failure mode: a delegated bridge run silently does nothing (or
falls back to Claude cloning the work) while the run still reports green.

- `docs/engineering-journal/LEARNINGS.md:293` (`#agy-delegate-silent-claude-fallback`, 2026-06-29):
  a full transcript audit found that runs believed to be genuine `agy` delegation (#278, #279) made
  **zero `agy` calls** — the spawned teammate inherited Claude's full toolset and just did the work
  itself, emitting Claude's own `★ Insight` output style. The only reliable discriminator turned out to
  be grepping the transcript for an actual `agy --model` Bash call; the *name* of the spawn path is not
  a trustworthy signal.
- The same document records a second bridge failure class in the surrounding entries (`agy Flash as a
  delegated coder, n=2`, immediately below `:293` in `LEARNINGS.md`): the code was cheap to fix, but the
  *silent no-op* itself was the expensive failure, because nothing detected it automatically.
- The grounding brief for this ideation pass names this as its own theme, not a rehash of existing
  release-surface discipline: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:101-104` — "Silent
  no-ops in delegation & dead wiring (5+ learnings: agy silent Claude-fallback, dead-wiring
  producer+consumer, test-shape-masks-dead-wiring, fake-adapter mismatch) — bridge/delegation idea
  needs 'did it actually run/persist' verification," logged as new theme candidate 15 (delegation
  integrity), and repeated in the final theme roster at line 180 ("Delegation integrity — silent-no-op
  detection across all bridges").
- Today's only enforcement in this space is **file-existence** parity, not **behavioral** proof: the
  existing `{#marketplace-ci-guard}` seed (`docs/engineering-journal/QUEUED.md:176-191`) and the
  `{#marketplace-drift}` learning (`docs/engineering-journal/LEARNINGS.md:1516-1522`, the
  `blueprint-reviewer` plugin merged to `main` but never registered in `marketplace.json`) only check
  that a plugin directory and its marketplace entry exist and stay in sync. Neither checks that a
  bridge plugin's delegated work actually happened. This issue is the behavioral layer on top of that
  structural layer, for bridge-carrying plugins specifically.
- `agy` is the fleet's one shipped bridge plugin today (`plugins/agy/.claude-plugin/plugin.json`,
  version `0.1.0`, described as "Antigravity-backed coder and reviewer bridge agents"; registered at
  `.claude-plugin/marketplace.json:179-191`). CLAUDE.md step 6 ("For every plugin behavior, schema,
  command, prompt, or user-facing guidance change, update the plugin release surfaces in the same PR")
  already requires release-surface hygiene on every plugin PR but has no automated check that a bridge
  plugin's version bump is backed by proof the bridge itself was exercised and produced real,
  attributable output — this issue closes that specific gap.

## Definition of Done

- A merged PR to `infiquetra-claude-plugins` adds:
  1. A CI job (in `.github/workflows/ci.yml` or a new `.github/workflows/delegation-integrity.yml`)
     that runs a new script — e.g. `scripts/check_delegation_proof.py` — which fails the build when a
     bridge-carrying plugin's `marketplace.json` version field changes in the diff without an
     accompanying, schema-valid delegation-proof artifact (e.g. a transcript excerpt or proof-bundle
     file referenced from the PR/commit, per whatever proof format the script defines and documents).
  2. A second CI job (or a mode of the same script) that performs a fleet-wide sweep of recorded bridge
     transcripts/proof artifacts and fails when it finds: a silent no-op (bridge invoked but produced no
     attributable external-tool call), an unrecorded fallback (Claude did the work but the run was
     logged/labeled as bridge-delegated), an untokened orphan write (a write attributed to no traceable
     actor), or a broken proof chain (a proof artifact that does not verify against its claimed run).
- Both jobs are wired into the existing CI pipeline so they run on every PR touching a bridge plugin's
  `marketplace.json` entry or its recorded proof artifacts.
- `docs/engineering-journal/DECISIONS.md` gains an entry recording the chosen proof-artifact schema and
  why (what counts as sufficient proof, and what was rejected — e.g. trusting the spawn-path name alone,
  which `LEARNINGS.md:293` already disproved as a discriminator).
- Release-surface checklist items below are completed in the same PR wherever the change touches
  `agy`'s plugin behavior (e.g. if the proof-artifact requirement changes what `agy:delegate` must emit).

### Acceptance criteria
- [ ] **Version-bump gate fires red without proof, green with it (absorbed T15-F4-6).**
   A fixture PR that bumps `agy`'s `marketplace.json` version with no delegation-proof artifact attached
   causes the new CI job to fail (`check_delegation_proof.py` exits non-zero); an otherwise-identical
   fixture PR that includes a valid proof artifact causes the same job to pass.
   ```
   # Fixture 1: version bump, no proof -> CI red
   pytest tests/test_check_delegation_proof.py::test_version_bump_without_proof_fails

   # Fixture 2: version bump, with valid proof -> CI green
   pytest tests/test_check_delegation_proof.py::test_version_bump_with_proof_passes
   ```

- [ ] **Fleet sweep fires red on a seeded silent no-op (absorbed T15-F6-8).**
   A seeded fixture transcript representing a silent no-op (bridge invoked, zero external-tool calls,
   Claude did the work) causes the fleet delegation-monitor job to fail; a seeded fixture transcript
   representing a genuine bridge run (matching the discriminator in `LEARNINGS.md:293` — an actual
   `agy --model ...` Bash invocation) causes it to pass.
   ```
   pytest tests/test_delegation_fleet_monitor.py::test_silent_no_op_transcript_fails
   pytest tests/test_delegation_fleet_monitor.py::test_genuine_bridge_transcript_passes
   ```

- [ ] **The two checks are distinct and both documented as such.**
   The version-bump gate (per-PR, triggers on a marketplace version diff) and the fleet sweep
   (continuous/broad, triggers on any recorded bridge transcript) are implemented as separably testable
   units — not collapsed into one undifferentiated check — matching the grounding brief's explicit
   distinction between "F4-6 (version-bump gate)" and "F6-8 (per-run all-bridge sweep)."
   ```
   # Both scripts/functions are independently invocable and independently testable
   python3 scripts/check_delegation_proof.py --mode version-gate --dry-run
   python3 scripts/check_delegation_proof.py --mode fleet-sweep --dry-run
   ```

- [ ] **CI workflow wiring is verifiable end to end.**
   Running the new/updated GitHub Actions workflow locally (via `act` or by inspecting the workflow
   YAML) shows both jobs triggered on the correct paths (`**/marketplace.json` for the version gate;
   a bridge-transcript/proof-artifact path for the fleet sweep).
   ```
   grep -n "delegation" .github/workflows/*.yml
   ```

- [ ] **Release-surface drift guard passes.** Any plugin behavior change made to satisfy this issue (e.g.
   to `agy`'s proof-emission behavior) is reflected in `plugins/agy/.claude-plugin/plugin.json` version,
   `.claude-plugin/marketplace.json`, and `plugins/agy/CHANGELOG.md` in the same PR, and the existing
   marketplace-consistency drift-guard test still passes.
   ```
   uv run pytest tests/ -k marketplace
   ```

- [ ] Full repo gate passes: `uv run pytest && uv run ruff check .`
### Out-of-scope / non-goals
**In scope:**
- A CI-enforced proof-of-execution gate scoped to bridge-carrying plugins (today: `agy` only), keyed off
  `marketplace.json` version-diff detection.
- A fleet-wide delegation-integrity sweep script/job that classifies recorded bridge transcripts against
  the failure taxonomy above.
- Documentation of the proof-artifact schema in `DECISIONS.md` and in the relevant plugin's README/skill
  reference.

**Non-goals (this issue does not):**
- Build a new bridge plugin, or change `agy`'s coding/review behavior beyond what's needed to emit a
  verifiable proof artifact.
- Retroactively re-audit historical sessions/transcripts predating this gate (the fleet sweep operates on
  recorded artifacts going forward; a backfill, if wanted, is a separate issue).
- Replace or duplicate the existing structural marketplace-drift guard (`{#marketplace-ci-guard}`,
  `docs/engineering-journal/QUEUED.md:176-191`) — that guard checks directory/entry parity; this issue
  is additive, behavioral proof-of-execution on top of it, and should reuse rather than fork its
  plugin-directory/marketplace-entry diffing logic where practical.
- Extend the gate to non-bridge plugins or to model/effort tier-vocabulary concerns
  (`plan/SKILL.md:296-352`) — those are separate, already-tracked threads per the grounding brief's
  theme roster.
- Stand up a general-purpose "zero operators watching" alerting/notification system beyond CI red/green;
  the moonshot-tier framing of the fleet-sweep facet (T15-F6-8, `tier_guess: moonshot`) is descoped here
  to a CI-only check, not a live monitoring service.

## Grounding References

- **Absorbed idea `T15-F4-6`** (primary; role: primary) — "Marketplace-CI delegation-proof gate for any
  bridge-carrying version bump," `tier_guess: structural`, `verdict: survive`.
  DoD sketch (from survivor record, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):
  "Merged PR adds a CI job + `check_delegation_proof.py` failing when a bridge-declaring plugin's
  `marketplace.json` version changes without a valid proof artifact; verified by CI red on a fixture PR
  bumping `agy` with no proof, green with it. Extends CLAUDE.md step-6 release-surface discipline."
- **Absorbed idea `T15-F6-8`** (facet; role: facet) — "Zero operators watching: a fleet-wide continuous
  delegation-integrity monitor in CI," `tier_guess: moonshot`, `verdict: survive`.
  DoD sketch (from survivor record): "Merged PR adds a `.github/workflows` delegation-integrity job +
  fleet-audit script aggregating all bridge proofs/transcripts in a run and failing on any un-launched
  delegation, unrecorded fallback, untokened orphan write, or broken chain; verified by CI red on a
  seeded silent-no-op transcript. Distinct from F4-6 (per-run all-bridge sweep vs version-bump gate)."
  This facet is descoped in this issue's DoD from a moonshot-scale continuous monitor to a CI-triggered
  sweep job (see Non-goals) — the behavioral check it specifies is preserved, the "always watching"
  infrastructure ambition is not.
- **Grounding brief theme roster**, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:101-104` and
  `:180-181` — names this theme "Delegation integrity — silent-no-op detection across all bridges" and
  explicitly separates it from pre-existing release-surface drift concerns.
- **Prior learnings this builds on**:
  `docs/engineering-journal/LEARNINGS.md:293` (`#agy-delegate-silent-claude-fallback`) — establishes the
  transcript-grep discriminator this gate must operationalize; the surrounding `agy Flash as a delegated
  coder, n=2` entry establishes that the no-op itself, not the resulting code quality, is the expensive
  failure this issue targets.
  `docs/engineering-journal/LEARNINGS.md:1516-1522` (`#marketplace-drift`) — the pre-existing structural
  (file-existence) drift class this issue's behavioral gate sits on top of, not a replacement for.
- **Binding decisions engaged:**
  `{#external-engines-never-gatekeepers}` (#283) — Claude remains verifier-of-record; this gate does not
  make `agy` (or any bridge) a gating decision-maker, it only verifies that a *claimed* delegation was
  real.
  `{#external-engine-chaperone-dispatch}` (#318) — consistent with treating `agy` as chaperone-dispatched
  worker, not a second git-participant residency; this issue adds verification, not new dispatch
  authority.
  CLAUDE.md step 6 (this repo, release-surface discipline) — this issue is an automated enforcement
  extension of that existing manual step, per the `T15-F4-6` DoD sketch's own framing ("Extends
  CLAUDE.md step-6 release-surface discipline").

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** Per the absorbed entry's own `executor_profile`. This is a mechanical CI/script
  build (a Python check script + GitHub Actions wiring + fixture tests) against an already-well-specified
  proof taxonomy documented above — no architectural ambiguity or adversarial judgment call that would
  justify escalating above sonnet/medium, and no external-LLM bridge participation is appropriate for
  work that is itself building a guard *against* unverified bridge delegation.

## Release-Surface Checklist

Complete in the same PR if this issue's implementation touches `agy`'s behavior (e.g. requiring `agy` to
emit a structured proof artifact on every delegated run):

- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump reflecting the behavior change.
- [ ] `.claude-plugin/marketplace.json` — corresponding `agy` entry version updated to match.
- [ ] `plugins/agy/CHANGELOG.md` — entry describing the new proof-emission requirement.
- [ ] Marketplace/version drift-guard tests (existing `{#marketplace-ci-guard}` class of test) still pass
      and, if extended, cover the new proof-artifact field.
- [ ] `docs/engineering-journal/DECISIONS.md` — new entry for the proof-artifact schema choice, rejected
      alternatives (e.g. trusting spawn-path name), and a "revisit when" condition (e.g. "revisit when a
      second bridge-carrying plugin ships and needs the same gate").
- [ ] `docs/engineering-journal/LEARNINGS.md` — if the implementation surfaces a new non-obvious
      mechanism (e.g. a transcript-format edge case the sweep script had to handle), capture it per this
      repo's auto-maintain convention.

If this issue's implementation does *not* touch `agy`'s runtime behavior (i.e. it only adds CI
scripts/workflows that inspect existing artifacts without changing what `agy` emits), the plugin.json/
marketplace.json/CHANGELOG bump items above do not apply — but the DECISIONS.md and LEARNINGS.md items
still do.

### Verification
```
# Run the new delegation-proof and fleet-monitor test suites
uv run pytest tests/test_check_delegation_proof.py tests/test_delegation_fleet_monitor.py -v

# Confirm the workflow file wires both jobs
grep -n "delegation" .github/workflows/*.yml

# Confirm marketplace/plugin.json/CHANGELOG stay in sync if agy's behavior changed
uv run pytest tests/ -k marketplace
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

## Files Expected to Change

- `scripts/check_delegation_proof.py` (new)
- `.github/workflows/ci.yml` or `.github/workflows/delegation-integrity.yml` (new job(s))
- `tests/test_check_delegation_proof.py` (new)
- `tests/test_delegation_fleet_monitor.py` (new)
- `docs/engineering-journal/DECISIONS.md` (new entry)
- Conditionally, if `agy`'s runtime behavior changes: `plugins/agy/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/agy/CHANGELOG.md`, `plugins/agy/agents/*.md`

### Handoff maturity

requirements-ready — grounded in two absorbed survivor-map ideas plus direct file:line citations from
this repo's engineering journal and grounding brief; ready for `/plan`.

### Intent

Two CI-enforced guards for the "did the delegated bridge actually run and persist?" problem that today is caught only by manual transcript audits:

### Context library links

_none_

### Files expected to change

- `plugins/agy/.claude-plugin/plugin.json`
- `.github/workflows/ci.yml`
- `.github/workflows/delegation-integrity.yml`
- `scripts/check_delegation_proof.py`
- `docs/engineering-journal/DECISIONS.md`
- `.claude-plugin/marketplace.json`
- `plugins/agy/CHANGELOG.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`

### Tests to add or update

- `tests/test_check_delegation_proof.py`
- `tests/test_delegation_fleet_monitor.py`

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/457
- Number: 457
- Created at: 2026-07-04T08:25:10.725723+00:00

