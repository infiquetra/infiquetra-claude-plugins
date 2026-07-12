# Work Session — Issue #402: spend observability on the ledger (2026-07-12)

One-line summary: built five reader/leaf-appender modules over `outcome_costs.py`'s cost ledger
(estimate-reconcile, itemized receipts, spend retro, a `/retro` tier-efficacy pass, and
shadow-audit evidence), bumped saga to 0.82.0, and reached PR-ready with a clean full-suite gate.

## What was built (by U-ID)

- **U1** — `spend_estimate.py`: a pre-run ordinal estimate joined onto `/plan`'s Phase 5.2a tier
  table (a small edit to `plan/SKILL.md` itself — the issue's literal DoD anchor), a
  payoff-at-stake x remaining-budget tier-value score (`tier_value_score`/`ladder_dearness`, an
  abstract `{irreversible, gated, destructive}` signal triple so both the `ExecutionSpec.Unit`
  caller and the `outcome_spec.Node` caller can supply it from their own fields), a read-time
  `resolve_node_tier` fallback lookup for `Node` (which carries no tier field — issue tier band
  via `gh issue view`, else `SPEND_BASELINE`), and a post-run `reconcile()` reader over
  `outcome_costs.py`'s rollup that deltas only `operator_touches`/`retries` (both estimated at 0),
  rendering `tokens`/`wall_seconds` as labeled non-commensurable context.
- **U2** — `spend_receipt.py`: itemized per-unit/per-tier receipt; `counterfactual_total` sums
  each unit's fallback tier (`Unit.cheaper_fallback` -> `adjacent_tier` -> `resolve_node_tier`, in
  that priority order); a unit already at the cheapest tier reports "already cheapest" rather than
  raising.
- **U3** — `spend_retro.py`: globs every committed `docs/outcomes/*/outcome-spec.json`, aggregates
  tier-mix / premium-spend-share (via U1's node resolver) / terminal-state counts, and appends a
  dated section to `docs/engineering-journal/LEARNINGS.md`. Both real committed examples in this
  repo roll up empty today — verified directly and pinned as a regression-guard test.
- **U4** — `/retro` tier-efficacy pass: a new Phase-1.10 evidence sub-section + Phase-5(e)
  propose-diff-and-wait step in `retro/SKILL.md`, plus `tier_efficacy.py`'s
  `propose_downgrades()` (never calls `write_tier_default`). Requires `min_samples` runs, ALL
  zero marginal findings, and a single consistent tier per work-shape before proposing a
  one-rung-cheaper diff.
- **U5** — `shadow_audit.py`: 1-in-N deterministic sampling (seeded), gated per attended (`--yes`
  or `.saga/shadow-audit.json`) / unattended (`--max-samples` mandatory) modes, a strict
  whitespace-normalized `classify()` for simple diffable outputs (or an accepted external
  verdict), verdict recording through `evidence_ledger.py` (#398) under a namespaced
  `shadow-audit:<stage>:<unit-id>` `check_id`, and a per-stage sufficiency-rate `report`. The
  module never spawns an Agent itself; the replay dispatch site is documented as a new row in
  `sandbox-spawn-sites.md`.
- **U6** — saga 0.81.0 -> 0.82.0 (`plugin.json`), `marketplace.json` regenerated via
  `scripts/sync_marketplace.py` (never hand-edited), `CHANGELOG.md` entry, and the version-pinned
  assertion in `tests/test_saga_plugin.py` updated to match.

## Checks run

- New tests: `tests/test_spend_estimate.py` (9), `tests/test_spend_receipt.py` (7),
  `tests/test_spend_retro.py` (7), `tests/test_tier_efficacy_retro.py` (7),
  `tests/test_shadow_audit.py` (7) — 37/37 passed.
- Release-surface drift guards: `tests/test_release_triad.py`, `tests/test_release_surface_parity.py`,
  `tests/test_saga_plugin.py` — 86/86 passed.
- Full repo gate: `ruff check .` clean, `ruff format --check .` clean (322 files), `mypy plugins/
  scripts/ tests/ --ignore-missing-imports` clean (195 files), `bandit -r
  plugins/saga/scripts/{spend_estimate,spend_receipt,spend_retro,tier_efficacy,shadow_audit}.py`
  zero issues at any severity (one `# nosec B311` on a deliberately-seeded, non-cryptographic
  `random.Random` sampling call).
- Full suite: 3387 passed / 0 failed / 1 skipped (pre-existing skip), confirmed twice
  (pre- and post-release-surface-bump).
- Each new script's `--help` exits 0 (the issue's own verification block).

## Commits (branch `work/402-spend-observability`)

- `856a423` docs(plan): issue #402 spend-observability plan, doc-review, KTD record
- `f261227` feat(saga): spend observability on the ledger (#402)
- `b36b028` chore(saga): release surfaces for spend observability (#402)

## Process notes

- Doc-review (self-run, since this leaf executes inline with no separate reviewer session) found
  and fixed three P1s before implementation started: a fallback-tier lookup step that would have
  read the git-ignored saga cache (not durable enough for `spend_retro.py`'s cross-run,
  possibly-cross-machine aggregation); a missing `/plan` SKILL.md wiring (the estimate column
  would never actually have rendered where the issue's own DoD anchors it); and a tier-value
  scoring signal (`gated`/`risky`/`destructive`) that only exists on `outcome_spec.Node`, not on
  the `ExecutionSpec.Unit` the scorer's primary surface is anchored to. All three are documented
  as KTDs in the plan and in `DECISIONS.md` rather than silently patched.
- Confirmed by direct read that `execution_spec.Unit` already carries the `cheaper_fallback`/
  `worth_it_because` fields the issue's non-goals section anticipated stubbing (shipped by
  `#367`/`#565`) — no stub was needed there, only at the `outcome_spec.Node` granularity.
- The two real committed `docs/outcomes/*/outcome-spec.json` examples both roll up empty
  (`cost_rollup: {}`) — confirmed directly rather than assumed, and pinned as an explicit
  regression-guard test in `test_spend_retro.py` so a future change cannot silently start crashing
  on that real, currently-untelemetered state.
- Execution ran **inline** (not team-execution, despite `recommend_execution_backend()` naming
  team-execution per the ~12-functional-file size signal) — matching sibling leaf #398's
  precedent and this leaf's own execution instructions; recorded as an explicit
  recommended-vs-chosen override on the saga tick, not a silent divergence.

## Next step

Run `/code-review` programmatically for the pre-PR gate, then open the draft PR.
