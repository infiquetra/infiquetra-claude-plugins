# Code review: issue #618 — settlement-gate operator waiver

**Verdict: clean** — zero P0/P1/P2; 7 P3 findings (6 repaired in-round, 1 deferred with
rationale) plus 2 non-blocking advisories.

- **Branch**: `work/618-settlement-gate-operator-waiver` · diff base `53cd65f5` (= origin/main)
- **REVIEWED_SHA**: `8af39df2e837427823c9da87c07818a4484d2f64` (U1 `60828eab`, U2 `ebb18782`,
  U3 `8af39df2`)
- **Post-repair head**: `4746a06b` — delta since REVIEWED_SHA is tests + one comment line only
  (no production code); delta adjudicated **clean**, lens verdicts carry over.
- **Pre-merge delta**: `0f7138a6` (docs-only tail) + `4f830e1c` (ruff-format collapse of the
  version-pin assertion in `tests/test_saga_plugin.py` — caught by CI Lint on PR #640; the
  finding-7 comment repair shortened the line below the wrap threshold). No production code;
  adjudicated **clean**, verdict carries to the merge head.
- **Mode**: programmatic (called by `/work` Phase 5.1); persistence owned by `/work` via the
  evidence ledger. Saga `issue-618` `review_paths` appended.
- **Plan judged against**: `docs/plans/2026-07-22-issue-618-settlement-gate-operator-waiver-plan.md`
  (R1–R8; R9 live acceptance deliberately deferred behind an operator go — not faulted).

## Method

Three adversarial lenses, each a read-only verifier in an isolated worktree (opus tier, at the
3-concurrent cap), prompted to refute rather than confirm:

1. **Semantic correctness** — refute the `_report_and_roster` refactor's byte-identity, the KTD3
   subset rule, grant-time concurrency, roster ⇔ halt equivalence, and the gate partition.
2. **Fail-closed compatibility** — refute old-reader isolation, waiver schema closure, R5
   byte-identity, injection bounds, and the FACT_KINDS write-side widening.
3. **Plan fidelity & test adequacy** — built-vs-planned audit and reachable-untested-path attack.

## Results

**Zero refutations across all lenses.** Highlights, all independently probed:

- Refactor byte-identity: differential fuzz re-implementing the pre-refactor break-based halt —
  200,000 random ledgers, 0 divergences.
- Subset rule: 433,452 benign-delivery transitions never grew the roster (waiver keeps
  covering); 181,567 retry-spawn transitions always broke coverage (new attempt re-halts).
- Roster-empty ⇔ halt-false: 200,000 fuzzed ledgers, 0 violations (late-delivery demotion
  handled via `latest_states`).
- Old-reader isolation verified consumer-by-consumer (`rollup`/`_numeric_fields`, settlement
  snapshot readers, pulse, provider control chart, reconcile); `outcome_compat.py` does not
  import `run_ledger` at all, and the diff does not touch it.
- Schema closure: 7 corruption probes (digest mismatch, stale digest, duplicate pairs,
  non-canonical order, extra field, `delivered` state, out-of-range states) all rejected;
  the only passing payload is a fully self-consistent forge, which still requires rewriting
  the tamper-evident chain — the documented ledger trust boundary, not new exposure.
- Cross-runtime claim CONFIRMED by direct inspection of the frozen codex copy
  (`infiquetra-codex-plugins/plugins/saga/scripts/run_ledger.py`): its `FACT_KINDS` check is
  write-side only (`build_fact`); its read path only hash-chains — an appended
  `dispatch-waiver` fact is kind-ignored, so codex coordinators keep halting (fail-closed),
  never error.
- Plan fidelity: every U1/U2 named test scenario maps to a real assertion; release surfaces,
  drift pins, parity, CHANGELOG accuracy, and the DECISIONS entry all check out; no scope
  creep (the `test_pulse_telemetry.py` FACT_KINDS pin update is a required companion).

## Findings

| # | Priority | Status | Finding |
| --- | --- | --- | --- |
| 1 | P3 | repaired (`4746a06b`) | Outcome-verb healthy-cohort refusal untested (plan U2 scenario 7 element). |
| 2 | P3 | repaired (`4746a06b`) | Broken-chain guard on waiver read/grant untested. |
| 3 | P3 | repaired (`4746a06b`) | Canonicalizer value-drift and missing-field branches untested. |
| 4 | P3 | repaired (`4746a06b`) | `_waiver_roster` malformed stored-roster branch untested. |
| 5 | P3 | deferred | `--at` wall-clock default success path unasserted — non-deterministic timestamp makes a direct assertion brittle; the default expression now executes on the healthy-cohort refusal path. |
| 6 | P3 | repaired (`4746a06b`) | `settlement-waived` receipt `reason`/`at` subfields unasserted. |
| 7 | P3 | repaired (`4746a06b`) | Stale `#637` annotation on the bumped version pin in `test_saga_plugin.py`. |

Advisories (no change required): (a) a malformed `dispatch-waiver` fact injected by a
direct-`append_fact` writer halts every coverage evaluation loudly — fail-closed availability,
reachable only with ledger write access, consistent with the existing threat model; (b) the
waived-receipt key digest changes only when the covering-waiver set changes (re-waive), stable
for a lone waiver across ticks.

## Gates at `4746a06b`

Affected suites 250 passed post-repair (full battery 5346 passed / 1 skipped at `8af39df2`;
delta is tests-only); `ruff check` + `ruff format --check` clean; `mypy plugins/ scripts/
tests/` clean; bandit zero findings on touched scripts vs the origin/main baseline;
`check_release_surface_parity.py` clean.
