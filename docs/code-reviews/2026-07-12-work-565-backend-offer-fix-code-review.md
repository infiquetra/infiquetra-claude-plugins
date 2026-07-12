# Code Review — Issue #565 (backend offer flow + verify panel tiers)

One-line verdict: **PASS** — 4 actionable findings (4 P3) plus 2 sub-threshold observations from
a 4-lens adversarial review, all fixed in-branch; the falsification loop attacked the fix round
with 12 independent probes and returned **RESOLVED** with zero refutations, including a ~1.4M-
combination brute force converting the dead-code claim from empirical to logically certain.

## Review-result contract

- **Target**: branch `work/565-backend-offer-fix`, diff `0c24aac..383b1cb`
- **Reviewed SHA**: 4-lens pass at `efc8510`; falsification `RESOLVED` at `383b1cb` (the fix
  commit). Artifact commits after `383b1cb` are docs-only and non-staling for the code verdict.
- **Mode**: programmatic / report-only — `/work` owns persistence (this artifact)
- **Lenses**: correctness, security, testing, maintainability — each `saga:readonly-verifier`,
  worktree isolation, opus tier, `examined_sha` reported (all four: `efc8510`)
- **Linked**: issue #565; PR #566; plan
  `docs/plans/2026-07-12-issue-565-backend-offer-fix-plan.md`; saga `issue-565`

## Findings

| # | Sev | Conf | Lens | Finding | Status |
|---|---|---|---|---|---|
| 1 | P3 | 90 | testing | `and not elevated_risk` in the ultracode expression is dead code — mutation J (term removed) survived all 69 tests; the "suppressor" test comment claimed a mechanism that never executes (team-branch precedence does the routing) | **fixed** `383b1cb`: term KEPT as a reordering guard; code comment + test docstring/comment now state the real mechanism and the term's unreachability honestly |
| 2 | P3 | 80 | maintainability | three doc sites quoted an availability-note substring the code never emits ("unverified — probe" vs the code's "unverified; probe") — the repo's named prose-vs-code truthfulness class | **fixed** `383b1cb`: all three sites quote the code's real substring; falsifier confirmed zero residual drift repo-wide |
| 3 | P3 | 55 | correctness (reproduced) | dispatcher fork fast-path returns a reduced dict with no `backends`/`workflow_availability` — latent KeyError for an unconditional consumer (pre-existing shape, `fork` is outside the 3-backend vocabulary, no production consumer affected) | **fixed** `383b1cb` (documentation): comment declares the intentionally reduced shape and the consumer contract |
| 4 | P3 | 50 | maintainability | CHANGELOG cited pre-edit line numbers that no longer locate the rewritten prose | **fixed** `383b1cb`: numeric cites replaced with section anchors (falsifier verified every anchor resolves) |
| 5 | sub | 40/70 | correctness+testing | negative `release_surface_file_count` inflates the functional count and could silently over-escalate; branch untested | **fixed** `383b1cb`: fail-loud `ValueError` in `should_offer_team_execution` + tests through both API paths and CLI |
| 6 | sub | ~40 | correctness | CLI `--workflow-shape` raw-traceback rejection vs sibling flag's clean argparse `choices=` | **fixed** `383b1cb`: `choices=WORKFLOW_SHAPES` added (per-entry with `action="append"`, falsifier-verified); CLI test updated to `SystemExit` |

Security lens: **PASS, zero findings** — JS-injection into the emitted workflow refuted (enum
validation halts before emit; receipts text never reaches the emitter; `_js_string` is
`json.dumps` in a non-HTML ESM context); provenance is display-only; bandit delta zero vs base.

## Falsification round (`383b1cb`, RESOLVED)

12 probes, zero refutations. Highlights: the elevated-risk impossibility claim brute-forced over
~1.4M input combinations (0 counterexamples) and then proven structurally (every `elevated_risk`
component is itself a team trigger behind the same `has_code_surface` gate); the negative-count
guard fires through all three paths with no production caller able to pass a computed negative;
`choices` and the API validation share one tuple so they cannot disagree. One residual
observation, kept as-is by design: the CLI surfaces the negative-count `ValueError` as a raw
traceback (exit 1) — the module's pre-existing baseline for API errors; the finding was
silent-over-escalation, which is closed.

## Non-vacuousness evidence (testing lens)

10 mutations: 9 killed by named tests (subtraction revert, ValueError drop, enumeration omission,
effective-tier ignore, spend-at-unit-tier, dispatcher re-stamp removal, palette-check drop,
receipts-threading drop, provenance-note strip); 1 survived (the elevated-risk term — finding 1,
resolved as documented-guard). Plan scenario → test mapping complete for U1 and U3 with no
uncovered scenario.
