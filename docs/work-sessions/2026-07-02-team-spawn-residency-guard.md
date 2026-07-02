---
title: Work session — Team-spawn residency guard (#289)
date: 2026-07-02
issue: infiquetra/infiquetra-claude-plugins#289
plan: docs/plans/2026-07-02-team-spawn-residency-guard-plan.md
review: docs/reviews/2026-07-02-team-spawn-residency-guard-plan-readiness.md
branch: feat/289-team-spawn-residency-guard
destination: merge
orchestration: inline
status: PR-ready pending code-review gate
---

# Work session — Team-spawn residency guard (#289)

Executed the three-unit plan inline on the work branch, one commit per unit.

## What shipped

- **U1 — hook + tests.** New `plugins/saga/hooks/team_spawn_residency_hook.py`: warn-only
  `PreToolUse` shim. `load_trigger_set` parses `reviewer-registry.md` (backticked
  `<name>-reviewer` tokens on any table row) and `validator-registry.md`'s `## Testers` section
  only (section-scoped, not suffix-filtered — scanners/monitors/deploy-watcher live in sibling
  sections) into the 18-agent trigger set, fresh on every invocation (no materialized manifest).
  `_find_references_dir` resolves the registries' directory via the plan's four-step chain:
  dev-repo sibling → versioned-cache install (reading the active version from
  `installed_plugins.json`, authoritative over a max-semver glob fallback) → `CLAUDE_PROJECT_DIR`
  → bounded (≤10 level) cwd-ancestor scan. `decide()` is a pure predicate: warns iff a
  (prefix-stripped) `subagent_type` is in the (env-adjusted) trigger set AND `name` is
  missing/empty/non-string; `run_in_background` is never consulted (KTD1 — the field no longer
  exists on this harness's `Agent` tool). 40 tests (unit + tmp_path layout fixtures + real
  subprocess invocation of the plan's manual acceptance checks).
- **U2 — hooks.json registration.** Third `PreToolUse` entry, matcher `Agent|Task`, alongside
  the existing `Edit|Write|MultiEdit` and `Bash` entries. Registration guard test mirrors
  `test_spore_hooks_registration.py` and proves the sibling entries are untouched.
- **U3 — release triad.** saga `0.47.0` → `0.48.0` across `plugin.json`, `marketplace.json`,
  `CHANGELOG.md`.

## Deviation from the plan (caught by the full test gate, not the plan itself)

`tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match`
pins the saga plugin version as a literal assertion with a per-bump comment — a fourth
version-bearing surface the plan's U3 didn't enumerate (it named only the automated
`test_release_triad.py` guard). The full-suite pytest run in Phase 3 caught the resulting
single failure; fixed in the same phase, before any commit claimed the gate was green.

## Test evidence

Full suite: **1746 passed** (0 failed) after the fix above. `ruff check` + `ruff format --check`
clean on `plugins/saga/hooks/`. `mypy plugins/ scripts/ tests/ --ignore-missing-imports` clean
(115 source files). `test_release_triad.py -k saga`: 3 passed. Manual acceptance checks from the
plan's Verification section all match expected behavior (prefixed nameless → advisory JSON on
stdout, exit 0; named → silent, exit 0; malformed stdin → silent, exit 0; `hooks.json` still
valid JSON) — run with no env vars set, proving the bounded cwd-ancestor fallback (F2's fix)
resolves the registries from a bare process cwd.

## Files modified

Code: `plugins/saga/hooks/team_spawn_residency_hook.py` (new), `plugins/saga/hooks/hooks.json`.
Release: `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`.
Tests: `tests/test_team_spawn_residency_hook.py` (new), `tests/test_saga_plugin.py`.
Docs (prior commit, same branch): `docs/plans/2026-07-02-team-spawn-residency-guard-plan.md`,
`docs/reviews/2026-07-02-team-spawn-residency-guard-plan-readiness.md`,
`docs/engineering-journal/DECISIONS.md`.

## Next step

Run `/code-review` (operator-directed: opus 4.8) against `REVIEWED_SHA`, gate hard on P0/P1 or
staleness, then offer PR-open + reviewer request under explicit confirmation. Destination is
merge, also under confirmation.
