# Code review — #390 no-silent-Claude-fallback (`fix/390-no-silent-claude-fallback`)

**Mode:** programmatic report-only, called by `/work` (envelope persisted here by the caller)
**Reviewed revision:** `c2c2706` (7 commits over `main@2d35f36`; 24 files, +1053/−46), delta round
re-reviewed inline through `09f19a3` (the prescribed remediations only, +102/−22)
**Verdict:** PASS — 0 P0, 0 P1; 2 P2 + 5 P3 found, all validated findings remediated in `09f19a3`
except one recorded advisory · **Blocked:** no
**Scope check:** CLEAN — intent (issue #390 + scope notes + plan) vs delivered matches; no creep;
`engine_resolver.py` / `engine-registry.yaml` untouched (the #388 seam held)
**Plan completion:** U1–U7 all DONE against
`docs/plans/2026-07-07-no-silent-claude-fallback-plan.md` (R1–R10 covered; R10's red-on-main
evidence returned by U1/U2 and upheld by their panels)

## Review mechanics

Whole-diff lens team (per `{#unit-panels-vs-whole-diff-lenses-476}`, run even though all four unit
panels reported zero refutations): correctness+reliability (opus), security (sonnet),
testing+conventions (sonnet) — all `saga:readonly-verifier` + worktree, branch materialized,
examined SHA `c2c2706` quoted by each. Stage-B validators: one per P2 survivor (3 agents);
advisory P3s inline-validated against evidence read directly (right-sizing note: the P3s could
not affect the verdict and each was a one-grep check — recorded here rather than spent on agents).
Workflow panel caveat: the run's 12 unit verifiers returned prose, so the emitted panel
aggregation counted 0 structured reporters and logged UNDER-STRENGTH on every panel — the
verification content was real (zero refutations, SHAs quoted) but the aggregation was vacuous;
treated as advisory evidence only, this review being the gate. Follow-up filed (see work-session).

## Findings

| # | Sev | File | Finding | Validation | Disposition |
|---|---|---|---|---|---|
| 1 | P2 | tests/test_agy_delegate_contract.py | Marker path (`_blocked_status_from_logs`) never exercised — no test parses a real `FALLBACK_SUSPECTED:` marker anywhere in the tree | validator: CONFIRMED | FIXED `09f19a3` — marker-parser test over real log content (stdout + stderr legs) |
| 2 | P2 | plugins/agy/scripts/agy_delegate.py | Exit-code contract had three independently maintained copies of the passing-status set (`_PASSING_STATUSES`, `main()` literal, test literal) and no observed mapping | validator: CONFIRMED (sharpened) | FIXED `09f19a3` — `_exit_code_for_status()` single source used by `main()` and asserted by the contract test |
| 3 | P2 | tests/test_saga_engine_dispatch.py | "No real dispatch→builder→gate chain test" | validator: REFUTED — the stamp test chains real dispatch→builder; only the gate hop was fixture-fed | DROPPED per conservative-bias rule; the cheap third-hop extension was added anyway in `09f19a3` (real-dispatch manifest now refused by `satisfy_gate` in-test) |
| 4 | P3 | plugins/agy/scripts/agy_delegate.py:604 | `run-lease.json` recorded the pre-coercion status beside a coerced `result.json` — one bundle, two verdicts | inline: CONFIRMED (write order `:604` < `:612`) | FIXED `09f19a3` — lease written after `result_payload`, status unified; CHANGELOG line added |
| 5 | P3 | plugins/saga/scripts/execution_spec.py | Python `render_fallback_tier_marker` (test-only) diverged from the emitted JS (production) on malformed depths; defensive branches untested | inline: CONFIRMED (helper called only from tests) | FIXED `09f19a3` — JS `depthOf()` mirrors the Python coercion table; 7 parametrized malformed-depth cases added |
| 6 | P3 | tests/test_saga_engine_dispatch.py:935 | "byte-identical" docstrings overstated field-level assertions | inline: CONFIRMED | FIXED `09f19a3` — docstrings honest; omitted-vs-explicit-None provenance equality pinned at dispatch level |
| 7 | P3 | plugins/saga/scripts/manifest_reader.py:276 | Engine-influenced `disposition_note` prose renders unescaped in the operator report (advisory display only, not a control) | inline: CONFIRMED as theoretical | ADVISORY, recorded — escape only if the report ever renders clickable markdown |
| 8 | P3 | external-engine-workers.md §5 | Step 2 said Apply "owns the commit" while new step 3a gates "the commit step below" — ordering prose contradiction | inline: CONFIRMED (self-found) | FIXED `09f19a3` — apply vs commit split explicitly; commit after Test + 3a |

Suppressed: 3 security-lens verified-fine confirmations (JS-string escaping via `json.dumps`
everywhere, envelope bool type-check strict, bandit clean on the new subprocess surface — kept as
coverage evidence, not findings).

## Coverage and residuals

Gates at both rounds: pytest 2584→2592 passed / 1 skipped, `ruff check` + `ruff format --check`
clean, mypy clean (162 files); `sync_marketplace.py --check` clean; R5 grep clean. Residual
risks: finding 7 (advisory prose rendering); the emitter still does not schema-enforce verifier
verdicts (follow-up issue, out of #390's scope — attribution only was in scope); satisfy_gate's
evidence-only call path (manifest=None) remains documented-not-detected, unchanged from #384.

Links: plan `docs/plans/2026-07-07-no-silent-claude-fallback-plan.md` · doc-review
`docs/reviews/doc-review-issue-390-2026-07-07.md` · work-session
`docs/work-sessions/2026-07-07-no-silent-claude-fallback.md` · issue
infiquetra/infiquetra-claude-plugins#390 (+#392 facet)
