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
- `f29ccd4` docs(work-session): issue #402 spend-observability session record
- `88a0006` fix(saga): code-review fixes for issue #402 spend observability
- `86c385a` docs(evidence): record code-review verdict for issue #402 in the evidence ledger

## Code review (programmatic `/code-review`, 4 lenses: correctness, security, testing, maintainability)

- **P1 (correctness, fixed):** `tier_efficacy.propose_downgrades()` was missing the "above
  baseline tier" gate its own docstring and `retro/SKILL.md` claimed — a work-shape already at or
  below `SPEND_BASELINE` could get a downgrade proposal despite having no over-spend to correct.
  Fixed by adding the same `is_escalation(SPEND_BASELINE, tier)` predicate `spend_retro.py`
  already uses; regression-tested.
- **P2s (fixed):** uncaught `TypeError` on malformed JSON in `shadow_audit.py sample` /
  `tier_efficacy._record_from_dict` (security); `spend_receipt.py`'s docstring/plan overclaiming
  unimplemented `OutcomeSpec` node-level support (correctness); the `min_samples` exact-boundary
  case exercised but unasserted (testing); `CHANGELOG.md` release-surface drift from the
  `spend_receipt.py` fix plus a stale test count (maintainability).
- **P3s fixed:** all-cheapest/zero-eligible-pool untested at `sample()`/`sample_gated()` level; a
  bare `SPEND_BASELINE` docstring reference implying a nonexistent local alias; `--root` CLI
  argument help-text inconsistency (verified the differing *defaults* were correct, only help text
  was missing).
- **P3s residual (not fixed, low priority):** CLI malformed-input error-path coverage gap remains
  for `spend_estimate.py`/`spend_receipt.py`/`spend_retro.py`'s own error classes (a pattern shared
  with the rest of this repo's script CLIs, not introduced by this PR); `spend_estimate.py`'s
  `_cost_weights()` lazy-wrapper deviates from the sibling module-level-constant-binding
  convention; the attribute-docstring style (bare string literal after a dataclass field) is new
  to this PR and applied inconsistently.
- Full envelope persisted to the evidence ledger: `docs/evidence/issue-402/ledger.jsonl`
  (`check_id=code-review`, `reviewed_sha=88a0006`, `verdict=PASS`).
- Post-fix full suite: 3392 passed / 1 skipped (was 3387 pre-review); ruff/mypy/bandit all clean.

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

Draft PR #570 is open at `commit`-tier ceremony with all 6 CI checks green. Operator: review and,
when ready, request review / flip ready-for-review (not performed by this automation — reserved
for explicit human confirmation).
