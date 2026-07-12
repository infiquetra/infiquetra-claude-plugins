# Work Session — Issue #565: backend offer flow + verify panel tiers (2026-07-12)

One-line summary: executed the full plan via the approved dynamic workflow (`wf_5687b3c2-1cc`,
10 agents, 0 errors, 6 refute-3 verifiers all upholding), fixed all 4-lens findings plus both
sub-threshold observations in one review round, and reached PR-ready on PR #566 with the
falsification loop RESOLVED on its first round.

## What was built (by U-ID)

- **U1** — `lifecycle_state.py` recommender contract: subtractive `release_surface_file_count`
  (KTD1), frozen `WORKFLOW_SHAPES` vocabulary with fail-loud validation (KTD2),
  `workflow_availability {available, source}` provenance (KTD3), full three-entry `backends`
  enumeration with `omit_ultracode` deleted (KTD4), plus the `outcome_dispatcher.py`
  frontier-downgrade `backends` re-stamp the doc-review P1 demanded (R1-R4).
- **U2** — six prose sites rewritten in lockstep: `plan/SKILL.md` Phase 5.2 (ToolSearch probe
  mandate, five-shape framing), `operator-choice.md` §3.2/§4 (always-name-and-mark), the loop
  SKILL, `work/SKILL.md`, `execution-strategy.md` (new JSON shape), `drive-and-resume.md`.
- **U3** — `execution_spec.py` `Verify.tier` optional panel tier with its own
  `worth_it_because`/`cheaper_fallback` receipts, effective-tier emission at the single
  verifier-opts site, panel-tier-aware `unit_spend`, byte-identical emission when absent (R5/R6).
- **U4** — release surfaces: saga 0.79.0 → 0.80.0, marketplace, CHANGELOG, drift pin (R7).

## Checks run

- Full suite at final SHA `383b1cb`: **3331 passed / 0 failed / 1 skipped**. ruff check + format
  clean; mypy CI scope exit 0; bandit delta zero vs base (security lens, reproduced).
- Workflow refute-3 panels on U1/U3: 0 refuted across 6 verifiers; completeness manifests 4/4.
- 4-lens review + falsification: envelope at
  `docs/code-reviews/2026-07-12-work-565-backend-offer-fix-code-review.md` — 4 P3 + 2
  sub-threshold, all fixed; falsifier RESOLVED first round (12 probes, 0 refutations, ~1.4M-combo
  brute force on the dead-code claim).

## Commits (branch `work/565-backend-offer-fix`, PR #566)

- `0c24aac` docs(plan): plan, spec, workflow, doc-review, KTD record
- `efc8510` fix(saga): the full offer-contract + panel-tier change (15 files, +902/−90)
- `383b1cb` fix(saga): review round — negative-count guard, CLI shape choices, suppressor
  honesty, quote/anchor drift

## Process notes

- The testing lens's mutation J was the round's sharpest instrument: it proved the
  `and not elevated_risk` term dead under current branch precedence — the shipped behavior was
  right, but the test comment claimed a mechanism that never executes. Resolution kept the term
  as a reordering guard and made every comment state the true mechanism (team precedence).
- Issue #565's original AC test paths named nonexistent files (`tests/test_lifecycle_state.py`);
  the real homes are `tests/test_saga_plugin.py` / `tests/test_saga_execution_spec.py` — issue
  body corrected as part of U4's hygiene.
- This PR's own workflow run was offered through the pre-fix offer flow and its refute-3 panels
  rode unit tiers under the R4 rule this change relaxes — the first spec authored after merge can
  price a premium panel over a cheap unit.

## Next step

Flip PR #566 ready + request review (`open_pr` / `request_review` transitions), then the round-N
loop: merge under explicit operator confirmation, board moves, issue close — the QUEUED
`{#plan-backend-recommendation-broken}` entry retires with the merge.
