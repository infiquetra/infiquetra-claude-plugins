# Code review — work/526-ship-ceremony-operator-gate

**Verdict: CLEAN — not blocked.** 0 unresolved P0/P1. All actionable findings fixed on-branch in
`aacc1c9` and re-verified adversarially; the review is fresh at that SHA (the only later commits are
this artifact and session docs — no code moved).

- **Target:** branch diff `e102a77..aacc1c9` (merge base = origin/main `e102a77`, verified fresh)
- **Reviewed SHA:** `aacc1c9` (initial 4-lens pass at `d1a667a`; staleness re-review of
  `d1a667a..aacc1c9` passed — every fix claim falsification-tested)
- **Mode:** programmatic (called by `/work` as the pre-PR gate); envelope persisted here by `/work`
- **Linked issue:** infiquetra/infiquetra-claude-plugins#526 · **PR:** #561 (draft)
- **Plan:** `docs/plans/2026-07-11-issue-526-ship-ceremony-operator-gate-plan.md`
- **Work-session:** `docs/work-sessions/2026-07-11-issue-526-ship-ceremony-operator-gate.md`

## Scope check: CLEAN

Intent (issue #526 / plan): make `ship_ceremony.py run` refuse `always_operator`-tier transitions
without `--operator-confirmed <transition>`; move guidance + release surfaces in the same PR.
Delivered: exactly that — 9 plan-named files plus plan/review/work-session docs. No drift.

## Plan-completion audit (built-vs-planned)

| Item | State | Evidence |
|---|---|---|
| U1 gate + flag + 7 test scenarios | DONE | `ship_ceremony.py:425-441` gate; all 7 scenarios mapped to named tests (testing lens `scenario_map`); 43 tests pass |
| U2 guidance names the flag | DONE | `SKILL.md` Phase-5 item 4; `pr-continuation-loop.md` merge section (rewritten for the four-invocation sequence in `aacc1c9`) |
| U3 release surfaces 0.76.0 + journal | DONE | plugin.json / marketplace.json / CHANGELOG / drift-guard pin all 0.76.0; LEARNINGS addendum |
| R1-R7 | DONE | correctness + security lens clean-areas; R1's "runner never invoked" now directly proven (finding #1 fix) |

## Findings (stable numbering; lenses: correctness, security, testing, maintainability)

| # | Sev | Conf | File | Finding | Status |
|---|---|---|---|---|---|
| 1 | P2 | 90 | `tests/test_ship_ceremony.py:314` | Refusal tests proved ledger-unchanged but not runner-never-invoked; merge test's `_prs` proxy assertion was inert (mutation-probe proven) | **fixed** `aacc1c9` — origin-main-sha equality + branch-still-exists assertions; re-reviewer falsified both (guard bypass → assertions fail) |
| 2 | P2 | 75 | `plugins/saga/skills/work/SKILL.md:538` | Merge-guidance lines ballooned to 135/171 chars and misread as one `run` covering four transitions | **fixed** `aacc1c9` — rewrapped ≤106, four separate invocations named |
| 3 | P2 | 75 | `.../references/pr-continuation-loop.md:100` | Same blowout/ambiguity in the reference doc | **fixed** `aacc1c9` |
| 4 | P3 | 100 | `plugins/saga/scripts/outcome_github.py:338` | Outcome DAG auto-merge queue is a separate `gh pr merge` authority that never routes through the ceremony gate | **report-only** — pre-existing (blame `602e2c5`, 2026-06-26), deliberate CI+consensus authorization model; out of #526 scope by plan |
| 5 | P3 | 80 | `tests/test_ship_ceremony.py:338` | Gated-vs-gated confirmation mismatch untested | **fixed** `aacc1c9` — `test_operator_confirmed_mismatch_between_two_gated_steps_refuses` |
| 6 | P3 | 75 | `plugins/saga/scripts/ship_ceremony.py:590` | argparse off-palette rejection shape (exit 2) unpinned | **fixed** `aacc1c9` — `test_cli_main_rejects_off_palette_operator_confirmed_value` |
| 7 | P3 | 75 | `tests/test_ship_ceremony.py:241` | Tier-ternary duplicated 4× | **fixed** `aacc1c9` — `_confirm_for` helper, 0 inline ternaries remain |

Suppressed: 1 (re-reviewer's P3 at confidence 40 — "each explicitly confirmed" phrasing quibble in
SKILL.md; below the 75 anchor, and the phrase correctly refers to the `/work` offer pattern, not the
CLI flag).

## Validation method

Stage-A survivors were validated by direct probe (grep/awk/blame/fake-handler read) rather than a
per-finding validator fan-out — every finding was one-command checkable and 7/7 validated, so agent
validators would have re-derived known results (context-economy call by `/work`, the persisting
caller). The staleness re-review of the fix commit ran as an adversarial agent pass with
falsification probes.

## Coverage / residual risk

- `tests/test_ship_ceremony.py`: 43 passed; `ship_ceremony.py` at 99% line coverage (2 missed lines
  pre-existing, unrelated). Full suite 3104 passed / 1 skipped. ruff check + format, mypy (CI
  scope), bandit (changed file 0→0) all clean.
- Residual: finding #4 stands as documented design; if a single repo-wide merge chokepoint is ever
  wanted, that is a new issue, not #526.
- Panel context: the build itself carried a refute-3 verifier panel on U1 (unanimous uphold on the
  implementation; one fabricated side-claim killed — see work-session).

Review complete
