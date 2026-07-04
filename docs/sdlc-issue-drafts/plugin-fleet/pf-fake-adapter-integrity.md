---
title: "enhancement: fake-adapter integrity — shape lint, golden fixtures, fakes registry, real-adapter lane, boundary-crossing convention"
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

# enhancement: fake-adapter integrity — shape lint, golden fixtures, fakes registry, real-adapter lane, boundary-crossing convention

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

## Problem / motivation

This repo has shipped, and then had to fix under adversarial review, more than one test suite that
was 100% green while the thing it claimed to prove was false — because the suite never crossed the
boundary (a real adapter, a persisted field) it was supposed to validate:

- **`docs/engineering-journal/LEARNINGS.md:92` / `:98`** (`{#test-shape-masks-dead-wiring-291}`) — the
  saga Layer-2 end-to-end test for `artifact_pointers` was green, but the consumer leg derefed the
  producer's in-memory `pointer_json` rather than the value read back from the persisted tick. "A
  round-trip test only proves the round-trip if the consumer reads from the boundary it claims to
  validate." Fixed in commit `79a49ea` (#291).
- **`docs/engineering-journal/LEARNINGS.md:417`–`430`** (`{#fake-adapter-hides-real-path-mismatch}`) —
  U7's `WorktreeOps` fake (`FakeWT`) keyed liveness on exact in-memory path strings, and the
  real-adapter unit tests fed `git worktree list --porcelain` output that was hand-crafted to already
  match the queried string. Every test passed; only the adversarial `verify-outcome-u7` workflow,
  driving the **real** `git_worktree_ops` adapter against a **real** git repo, found the P0: real
  `git worktree` output is realpath-canonicalized, and a symlinked or relative `--repo-root` diverges
  from the fake's naive string comparison, silently marking live worktrees as absent. Fixed via
  canonicalization + a real-git regression test (`plugins/saga/scripts/outcome_worktrees.py`,
  DECISIONS `docs/engineering-journal/DECISIONS.md:782` `{#outcome-decompose-worktree-stance}`).
- **`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:12`–`15`** names this as a repo-wide
  recurring-pain theme (theme candidate 15, "delegation integrity" / test-shape-honesty): "Silent
  no-ops in delegation & dead wiring (5+ learnings) ... any bridge/delegation idea needs 'did it
  actually run/persist' verification."

Both incidents were caught only by manual adversarial review, after the code had already merged. There
is no mechanical, always-on gate in CI that would catch a repeat of either failure mode — a fake-only
test suite, or a fake whose behavior has silently drifted away from the real adapter it stands in for.

## Definition of Done

Merged artifacts, all wired into CI (or documented as advisory where the absorbed facet specifies
advisory-only), with the verification below actually run and green:

1. `scripts/lint_test_shape.py` — an AST-based lint that flags a test module which imports/patches
   only fakes and never imports or exercises the real production module it claims to cover. Wired as
   a CI lint-job step.
2. A documented golden-fixture convention (e.g. `docs/testing/golden-fixtures.md` or equivalent
   reference doc) plus `scripts/check_fake_fixtures.py`, which pins each fake's fixture data to a
   golden artifact derived from the real producer and flags drift (deleted or mutated golden). One
   real seeded pairing (fake + its golden) ships as the worked example. Advisory in CI (per absorbed
   facet `T11-F1-6`'s `tier_guess: structural` but advisory rollout).
3. `tests/fakes_registry.py` — a registry binding each registered fake to its real class/protocol,
   with an import-time signature-parity test that fails if the real adapter's public contract
   (method names/signatures) drifts out from under its fake.
4. `tests/real_adapter/` lane — a new test lane that exercises at least one real adapter seam against
   its real substrate (not a fake), converting the worktree-liveness-oracle seam
   (`plugins/saga/scripts/outcome_worktrees.py`, the U7 seam from `{#fake-adapter-hides-real-path-mismatch}`)
   as the first migrated case, run under a real, non-canonical (symlinked or relative) repo root.
5. `assert_reads_from_boundary` — a shared pytest helper added to `tests/conftest.py`, plus a
   documented boundary-crossing test convention, applied to convert one existing round-trip test so
   it re-reads its asserted value from the persistence boundary (disk/tick) instead of an in-memory
   shared variable.

### Acceptance criteria
One per absorbed facet, minimum:

- [ ] **(T11-F2-8, shape lint)** A fixture test module that imports/patches only a fake and never
      touches the real production module fails `scripts/lint_test_shape.py` / the lint CI step; a
      fixture test module that does import/exercise the real module passes.
      Check: `uv run python scripts/lint_test_shape.py tests/fixtures/lint_shape/fake_only_module.py`
      exits non-zero; `uv run python scripts/lint_test_shape.py tests/fixtures/lint_shape/real_import_module.py`
      exits `0`.
- [ ] **(T11-F1-6, golden fixtures)** Deleting or mutating a fake's golden fixture is flagged by
      `scripts/check_fake_fixtures.py`.
      Check: `uv run pytest tests/test_check_fake_fixtures.py -k golden_drift` passes (asserts a
      mutated/deleted golden trips the check).
- [ ] **(T11-F6-8, fakes registry + real-contract shadow)** Renaming a public method on a real
      adapter class registered in `tests/fakes_registry.py` fails that fake's signature-parity test.
      Check: `uv run pytest tests/test_fakes_registry.py -k signature_parity` passes against the
      current registry; a scratch rename (in a throwaway copy / mutation test) demonstrably fails it.
- [ ] **(T11-F4-8, real-adapter lane)** The converted worktree-liveness-oracle seam in
      `tests/real_adapter/` passes against the real `git worktree` CLI and fails on a
      mis-canonicalized (non-realpath) path.
      Check: `uv run pytest tests/real_adapter/test_worktree_liveness.py -v` passes; a deliberately
      broken (non-canonicalized) comparison in a throwaway patch fails the same test.
- [ ] **(T11-F4-7, boundary-crossing convention)** The converted round-trip test using
      `assert_reads_from_boundary` fails when the persistence write is stubbed out.
      Check: `uv run pytest tests/test_saga_saga.py -k boundary_crossing_roundtrip` passes; stubbing
      the write call (throwaway patch) makes it fail, proving the assertion reads from the boundary
      rather than an in-memory value.
- [ ] Full suite, format, lint, types stay green.
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — all pass.

- [ ] Full repo gate passes: `uv run pytest && uv run ruff check .`
### Out-of-scope / non-goals
In scope: the five mechanisms above (shape lint, golden-fixture convention + checker, fakes registry
with parity test, one converted real-adapter lane seam, one converted boundary-crossing test) and
their CI wiring.

Non-goals (minimal blast radius):

- Backfilling golden fixtures or registry entries for every existing fake in the repo — v1 ships one
  worked example per mechanism; broad backfill is a separate follow-on.
- Converting every fake-backed test suite to a real-adapter lane — only the worktree-liveness-oracle
  seam is migrated in this issue.
- Converting every round-trip test to use `assert_reads_from_boundary` — only one test is converted
  as the worked example and convention proof.
- Changing the production behavior of `outcome_worktrees.py`, saga persistence, or any other
  production module — this issue only adds test-integrity tooling and converts test shape; no
  production logic changes.
- Making the golden-fixture check or real-adapter lane a hard CI-blocking gate beyond what each
  absorbed facet's `tier_guess` specifies — where a facet is advisory, ship it advisory (see DoD #2).

## Grounding References

- **T11-F2-8** (primary) — "Fake-adapter detector: lint away test suites that never touch real code."
  Basis: `docs/engineering-journal/LEARNINGS.md:92`–`99` (`{#test-shape-masks-dead-wiring-291}`).
- **T11-F1-6** (facet) — "Fake-adapter suites must pin a golden fixture derived from the real
  producer." Basis: same recurring-pain theme, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:12`–`15`.
- **T11-F6-8** (facet) — "Fake-adapter registry with mandatory real-contract shadow." Basis:
  `docs/engineering-journal/LEARNINGS.md:417`–`430` (`{#fake-adapter-hides-real-path-mismatch}`).
- **T11-F4-8** (facet) — "Real-adapter contract lane: a registry of fake-only seams gets one
  real-substrate test each." Basis: same as above, `{#fake-adapter-hides-real-path-mismatch}`; the
  worktree-liveness-oracle is the seam named directly in that learning entry.
- **T11-F4-7** (facet) — "Boundary-crossing test convention + shared helper so round-trip tests
  actually cross persistence." Basis: `docs/engineering-journal/LEARNINGS.md:92`–`99`
  (`{#test-shape-masks-dead-wiring-291}`); the `assert_reads_from_boundary` helper name and pattern
  come directly from that learning's generalizable rule.
- Binding decisions this builds on: `docs/engineering-journal/DECISIONS.md:782`
  (`{#outcome-decompose-worktree-stance}`, U7 worktree lifecycle — the seam being migrated into the
  real-adapter lane); `docs/engineering-journal/DECISIONS.md:203` (`{#artifact-pointer-ktds-291}`,
  the Layer-1/2 artifact-pointer design whose consumer-boundary bug motivates the boundary-crossing
  convention).
- Repo-wide framing: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:12`–`15` (recurring-pain
  theme 1, "Silent no-ops in delegation & dead wiring").

## Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** mechanical, well-specified tooling work (AST lint, fixture diffing, a registry
  + parity test, one migrated test each for two conventions) with no architectural ambiguity — sonnet
  at high effort is appropriate; no case for opus (no adversarial judgment call or novel design), and
  no external-LLM involvement is needed since nothing here crosses a trust boundary.

## Release-surface checklist

This issue is test/tooling-only and does not change any plugin's runtime behavior, schema, command,
prompt, or user-facing guidance — no plugin.json/marketplace.json/CHANGELOG bump is required. If
implementation later surfaces a new user-facing skill or command (e.g. `lint_test_shape.py` exposed
as a `/qa`-invoked check), then before merge:

- [ ] N/A at authoring time — re-check at PR time whether `plugins/saga/.claude-plugin/plugin.json`
      needs a version bump (only if a skill/command surface is added).
- [ ] N/A — re-check `.claude-plugin/marketplace.json` for the same reason.
- [ ] N/A — re-check `plugins/saga/CHANGELOG.md` for the same reason.
- [ ] No drift-guard test changes anticipated; re-check `tests/test_agent_registration_drift.py` /
      `tests/test_marketplace_hook.py` if any new agent or skill surface is added.

### Tests to add or update
- `tests/test_lint_test_shape.py` (or a fixtures-driven test under `tests/fixtures/lint_shape/`)
- `tests/test_check_fake_fixtures.py`
- `tests/test_fakes_registry.py`
- `tests/real_adapter/test_worktree_liveness.py`
- `tests/test_saga_saga.py` — one converted boundary-crossing test using `assert_reads_from_boundary`

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `scripts/lint_test_shape.py` (new)
- `scripts/check_fake_fixtures.py` (new)
- `docs/testing/golden-fixtures.md` (new convention doc)
- `tests/fakes_registry.py` (new)
- `tests/real_adapter/__init__.py`, `tests/real_adapter/test_worktree_liveness.py` (new)
- `tests/conftest.py` (add `assert_reads_from_boundary` helper)
- `docs/testing/boundary-crossing-convention.md` (new convention doc)
- `plugins/saga/scripts/outcome_worktrees.py` (referenced, not modified, by the real-adapter lane
  unless the migration surfaces a bug)
- `tests/test_saga_saga.py` (one test converted)
- `.github/workflows/*.yml` or equivalent CI config (wire the new lint step)

### Verification
```bash
# Shape lint
uv run python scripts/lint_test_shape.py tests/fixtures/lint_shape/fake_only_module.py   # non-zero
uv run python scripts/lint_test_shape.py tests/fixtures/lint_shape/real_import_module.py # exit 0

# Golden fixtures
uv run pytest tests/test_check_fake_fixtures.py -k golden_drift -v

# Fakes registry parity
uv run pytest tests/test_fakes_registry.py -k signature_parity -v

# Real-adapter lane
uv run pytest tests/real_adapter/test_worktree_liveness.py -v

# Boundary-crossing convention
uv run pytest tests/test_saga_saga.py -k boundary_crossing_roundtrip -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; each mechanism's negative case (mutated golden, renamed real method, broken
canonicalization, stubbed persistence write) demonstrably fails the corresponding check.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/c23d3bf9-9081-4727-8e0d-140ebc73f63f/scratchpad/ideation/issue-map/issue-map-final.json`
- Source type: issue-map (saga:ideate convergent output)
- Source title: pf-fake-adapter-integrity

### Intent

This repo has shipped, and then had to fix under adversarial review, more than one test suite that was 100% green while the thing it claimed to prove was false — because the suite never crossed the boundary (a real adapter, a persisted field) it was supposed to validate:

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/458
- Number: 458
- Created at: 2026-07-04T08:25:27.815326+00:00

