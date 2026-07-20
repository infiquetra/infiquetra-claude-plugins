# Anchored review ceremony record — #605 cross-runtime acceptance harness

**Outcome**: lease-safe-runtime-continuity, leaf cross-runtime-acceptance.
**Branch**: `work/605-cross-runtime-acceptance` (base `origin/main` = `794b4da6`).
**Ceremony authority**: the plan's anchored `## Workflow Structure` section
(`docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md` on the outcome branch),
anchor `4b21df73f98030f97b5f770adddaf33e14048a07af8221005f6d5e3699e1cb0f` over 3754 bytes,
byte-verified before launch. Vehicle: Claude-direct cc-workflow inline ceremony under the
operator's recorded 2026-07-20 AFK delegation.

**Convergence**: round 3, HEAD `e7ec568e` — all findings resolved, zero open, no lens
downgraded, `missing: []` in every round.

## Rounds

| Round | Subject HEAD | Vehicle | Result |
| --- | --- | --- | --- |
| 1 — full 7-lens panel | `eae03b4` | workflow `wf_d80aedc3-39c` (7 lenses, pool 3) | Core acceptance claims + #628 attribution UPHELD by independent re-execution; 17 findings (2 P1, 6 P2, 9 P3) on evidence integrity / oracle strength |
| Remediation 1 | → `b6749142` | root integrator | All 17 fixed; bundle regenerated (sha `1cf824e6…`, still honestly 12/14 fail); hermetic suite 30 → 44; full battery 5273 passed |
| 2 — re-adjudication, 6 originating lenses | `b6749142` | workflow `wf_44b776e2-ed6` (pool 3, round-1 tiers) | All 17 round-1 findings confirmed RESOLVED and non-vacuous; 2 NEW P3s in the remediation itself |
| Remediation 2 | → `e7ec568e` | root integrator | Colon-prefixed path-guard regression fixed (`_ABS_PATH_RE` lookbehind); `TestBrokerRootDigest` halt-branch coverage added; suite 44 → 49 |
| 3 — re-adjudication, 2 originating lenses | `e7ec568e` | fresh `saga:readonly-verifier` + worktree spawns (opus/high) | Both P3s RESOLVED, zero new findings — **CONVERGED** |

Three-cycle tripwire: no finding exceeded one remediation cycle; the ceremony used two
remediation cycles total across disjoint finding sets.

## Lens roster (per the anchored section)

- `review-devils`, `review-security`, `review-architecture`, `review-testing` — opus/high
- `validate-concurrency`, `validate-event-flow`, `validate-scenarios` — sonnet/medium
- All spawns: `saga:readonly-verifier` agent type + disposable worktree isolation, bounded
  pool of 3, structured findings schema, temp-dir-only outputs.

## What the panel proved (beyond the findings)

- Three lenses independently re-executed the harness against the pinned runtimes
  (Claude `794b4da6` / saga 0.105.0, Codex `f3e1af75` / saga 0.78.0+codex.20260720120109)
  and reproduced the 12/14 split scenario-for-scenario, twice each with identical verdicts
  (no flakiness observed).
- `validate-event-flow` confirmed the #628 double-dispatch from the retained ledger directly:
  codex-native `outcome.dispatch.v2` intent → receipt-validated `ack_kind=launched`
  (`receipt_authority=owner-user-state-v1`) → Claude legacy intent+commit for the SAME
  `leaf_saga_id`, timestamped after the native ack. The claude-first ledger contains no v2
  vocabulary at all — the asymmetry is exactly as filed.
- `review-devils` confirmed the codex launched-ack chain is written by the real installed
  codex `reconcile-dispatch` CLI, not fabricated by the harness; the failure attribution
  could not be converted into a harness bug.
- `validate-scenarios` re-ran the FULL harness end-to-end: fresh bundle matched the committed
  one scenario-for-scenario with identical contract digests; schema valid; zero privacy leaks.

## Finding themes (round 1) and their remediations

All 17 findings — none overturned a scenario verdict — clustered on **evidence integrity**
(a constant presented as agreement evidence; the harness's own env attested as child env;
facts dropped exactly on the failing scenarios; a retention promise only true for hard halts)
and **oracle strength** (any-nonzero-exit refusal checks; a coarse refusal code aliasing two
mechanisms; a missing plan-enumerated negative case; untested verdict helpers). The full
inventory, fixes, and per-round verdicts live in
`docs/work-sessions/2026-07-20-issue-605-acceptance-progress.md`.

## Post-convergence state

- Evidence bundle `cross-runtime-acceptance.json`: **overall `fail`, 12/14 pass** — the two
  red scenarios (`race-codex-first`, `race-simultaneous`) document production defect
  **#628** (Claude advance dedup + handoff settled-guard blind to codex-native
  `outcome.dispatch.v2` records) and now carry their chain summaries and overlap receipts
  in-bundle. The bundle stays red until #628 ships and the Claude pin advances (README
  "Current verdict" section).
- Gates at `e7ec568e`: full battery 5273 passed / 1 skipped, hermetic harness suite 49
  passed, ruff check + format clean, mypy clean, bundle schema-valid, scrub clean.
- KTD4 verified every round: the branch touches only `tools/`, `tests/`, `docs/` — zero
  production plugin or release-surface files.
