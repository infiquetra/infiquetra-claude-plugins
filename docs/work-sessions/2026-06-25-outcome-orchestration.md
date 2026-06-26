---
title: OutcomeOrchestrator build — work session log
plan: docs/plans/2026-06-25-operator-outcome-orchestration-plan.md
review: docs/reviews/2026-06-25-operator-outcome-orchestration-plan-review.md
saga: task-outcome-orchestration
started: 2026-06-25
---

# OutcomeOrchestrator build — work session

Autonomous `/work` of the 11-unit plan, one unit per PR along the build spine, build vehicle =
**inline + ultracode assist** (operator pick; recommender said team-execution). Each unit: build inline
→ adversarial-verify via a right-sized ultracode workflow → full local gate → PR → auto-merge on green
→ next unit off updated `main`. Release-surface notes accumulate under saga's CHANGELOG `[Unreleased]`;
the version-flip + `/outcome` marketplace advertisement land at the U11 feature-flip.

## U1 — Outcome spec + DAG validation

**Built:**
- `plugins/saga/scripts/outcome_spec.py` — the canonical outcome document (KTD1): `OutcomeSpec` +
  `Node` dataclasses (superset-in-pattern of `ExecutionSpec`), per-node operational state machine in
  data (KTD2), Kahn `dependency_layers` + `ready_frontier`, `bump_revision` / atomic
  `redirect_dependency` (structural mutation → spec_revision + decision_trail, R26),
  `structural_warnings` (advisory), a `validate` that fails **before any dispatch**, and a
  `validate`/`layers` CLI.
- `plugins/saga/references/outcome-spec.md` — schema + state machine + validation-invariant reference,
  incl. the disconnection-is-advisory semantics and the `from_dict` fail-loud coercion rules.
- `tests/test_outcome_spec.py` — 47 tests across happy / edge / error / integration categories.
- `plugins/saga/CHANGELOG.md` — U1 note under a new `## [Unreleased]` section.

**Key decisions:**
- **Disconnection is advisory, not a hard failure** (revised under adversarial review). The first cut
  hard-failed a degree-0 "orphan" node when the graph had any edge. The verify panel proved that rule
  was both *too strict* (it rejected a legitimate pipeline + one independent `update-the-changelog`
  subplot) and *too loose* (it silently passed a disconnected multi-node island — the exact
  forgot-to-wire-it error it claimed to catch). Independent workstreams under one objective are
  first-class here, so disconnection is no longer dispatch-blocking; `structural_warnings(spec)` returns
  a non-fatal advisory for >1 weakly-connected component, consistently for a lone isolate and an island.
  The state-aware half of R33 (legal-edits-after-dispatch + dynamic orphan reconciliation) is U7.
- **`child_spec_ref` is a typed node field** (KTD10), never an overload of saga's `orchestration_ref`.
  U1 enforces the local, dispatch-blocking constraints (no self-recursion to the parent outcome_id, not
  the node's own id, and — added under review — no collision with a declared sibling `subplot_id`); the
  deep cross-spec ancestor-cycle check needs ancestor context and lands in U7.
- **Fail-loud type coercion at `from_dict`**: a string `depends_on`/`guarantee_tags` is rejected (not
  character-iterated into corrupted edges), `bool`/float liveness budgets are rejected (no silent 1s
  budget / truncation), and `spec_revision`/`schema_version` must be ≥ 1.
- **`redirect_dependency` is atomic**: validate-on-a-snapshot before bumping, so a rejected redirect
  never leaves a bumped revision + a decision-trail entry that lies about a rejected change (R26).
- JSON canonical (not Markdown front-matter / not SQLite) per KTD1 — deterministic round-trip, repo's
  JSON-parser tests apply.

**Requirements (honest facet scope):** U1 fully owns **R20** (validate-before-dispatch) and **R31
(validation)**, plus the **structure facet of R26** (the canonical spec container + decision-trail;
GitHub-completion + sub-issue projection are R26's other facets, in U2/U6). It ships the **spec-container
slice** of R1 (the distinct outcome-DAG data model — note `dependency_layers` is a *parallel
reimplementation* of the Kahn engine, deliberately divergent from `execution_spec`'s pilot-aware one,
not a reuse), R2 (the `leaf_saga_id`/`child_spec_ref` data seam; the coordinator-never-executes
invariant is enforced in U3), R21 (revision versioning + edge redirect; draft/prune/lazy-grow/promote
are U7), and R33 (revision versioning + the disconnection advisory; legal-edits-after-dispatch +
reconciliation are U7).

**Checks run:** `ruff format --check` ✓, `ruff check` ✓, `mypy` ✓ (no issues), `uv run pytest
tests/test_outcome_spec.py` ✓ 47 passed (96% module coverage); full suite ✓ 1013 passed (the single
local `test_suite_does_not_create_claude_dir_under_repo_root` failure is the known gitignored-saga-state
false-positive — the only leaked dir is `task-outcome-orchestration`, `git check-ignore` confirms it's
ignored and `git ls-files .claude` is empty, so it's absent in CI's clean checkout).

**Adversarial verification:** ultracode workflow (3 parallel lenses, each required to PROVE claims by
running the module standalone): validator-bypass, serialization/round-trip, requirements-honesty. **13
findings, all real except one correctly-refuted (`sort_keys=False` determinism — held across 5
`PYTHONHASHSEED=random` subprocesses).** Folded in: **P1** — `redirect_dependency` was non-atomic
(a rejected redirect left a bumped revision + a false decision-trail entry, corrupting the canonical
artifact) → now snapshot-validate-then-bump. **P2** — a string `depends_on` was character-iterated into
corrupted edges that passed `validate` → now rejected. **P2/P3** — the degree-0 orphan rule was both
too strict and too loose → replaced with the `structural_warnings` advisory. **P3s** — sibling
`child_spec_ref` collision now fails; `bool`/float liveness + negative `spec_revision` now rejected;
open pass-through maps deep-copied (detached snapshot). The requirements-honesty lens (no code bug,
fair over-claiming) drove the docstring + facet-scope corrections above and the `dependency_layers`
"reimplementation not reuse" relabel.

**Files modified:** `plugins/saga/scripts/outcome_spec.py` | `plugins/saga/references/outcome-spec.md` |
`tests/test_outcome_spec.py` | `plugins/saga/CHANGELOG.md`

**Next step:** U2 — shared store + completion events + transition ledger.
