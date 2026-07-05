# Code-review (programmatic gate) — /outcome start --from-objective (#375)

- **Scope:** `feat/pf-outcome-from-objective-375` vs `origin/main` (U1–U5).
- **Mode:** programmatic inline gate (no agent spawn), backend inline.
- **Verdict:** PASS — no P0/P1. Not blocked; PR-ready.

## Lenses applied

| Lens | Finding |
|---|---|
| GraphQL correctness | PASS — added `stateReason` + `trackedIssues(first:50){nodes{number}}`, both stable `Issue` fields; no speculative dependency field (would 400 the query). Runner seam defaults to `subprocess.run`; live path unchanged. |
| Edge cycle-safety | PASS — `edges_from_relationships` builds incrementally with a reachability guard, so it drops any edge (any cycle length) that would close a cycle and produces an always-acyclic map; `OutcomeSpec.validate()` (Kahn) passes. Dangling/self edges dropped + reported. |
| Provenance stamp | PASS — `github={repo, issue:"<owner>/<repo>#<N>", sub_issue:N}` uses the sub-issue's own number; proven consumable by `outcome_board_sync._parse_issue_ref` (test) — resolves `(repo, number)` for the reconcile/board-sync consumers. |
| Structural-state discipline (KD) | PASS — closed sub-issue seeds authored `Node.state` (done/rejected via `stateReason`), a structural spec field, never a committed status column or completion event. |
| Regression (R7) | PASS — `_starter_nodes` untouched; no-flag `start` unchanged; 2020 tests green. |
| Security | PASS — `gh api graphql` args `-f/-F` separated (no injection); ref parsed by a strict regex; no `shell=True`. |

## Findings

| Priority | Finding | Status |
|---|---|---|
| P3 | Relationship source narrowed from the approved plan's `trackedIssues` + `timelineItems` to `trackedIssues` only. `timelineItems` cross-ref extraction needs inline-fragment GraphQL that adds risk for marginal edge yield; KTD1 frames edges as best-effort/degrade-to-no-edges, so this reduces auto-edge *yield*, never correctness. | Open — documented deviation; a clean follow-up if richer edge inference is wanted. |
| P3 | Edge-inference *precision* is heuristic (a tracker depends on what it tracks); fixture tests validate the pure mapper, not GraphQL→`blocked_by` fidelity. | Open (by design, KTD1). |

## Gates

Full CI-parity gate green pre-PR: `pytest` 2020 passed (8 new), full-repo `ruff format --check .` +
`ruff check .` clean, full-scope `mypy plugins/ scripts/ tests/` clean, release-surface parity +
diff-guard green.
