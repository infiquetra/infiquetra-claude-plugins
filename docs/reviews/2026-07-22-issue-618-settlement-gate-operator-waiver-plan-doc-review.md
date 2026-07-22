# Doc Review: Issue 618 settlement-gate operator waiver plan

**Verdict: READY** — the plan can safely drive implementation; no blocking findings.

- **Target**: `docs/plans/2026-07-22-issue-618-settlement-gate-operator-waiver-plan.md`
- **Reviewed revision**: working tree (plan uncommitted; repo main at `a6f3bcff`, code anchors
  verified against saga 0.108.0 sources)
- **Classification**: plan (readiness-skeptic pass; no idea/issue rubric phase applies)
- **Blocked**: no
- **Applied fixes**: 2 — D1 and D2 resolved in the plan on operator instruction (2026-07-22,
  "lets complete the remaining findings"); see finding statuses below
- **External engine**: stored preference for doc-review is no offer (`engine_offer.py` intent
  `none`); verdict is Claude-owned
- **Linked**: issue infiquetra/infiquetra-claude-plugins#618 · saga `issue-618` (plan phase) ·
  outcome `governed-execution-integrity` leaf `leaf-governed-execution-integrity-sub-618`

## Evidence verified

Every load-bearing citation was re-checked against the working tree:

| Claim | Verified at |
| --- | --- |
| Settlement gate blocks all new units on any halt-required report; receipt key `settlement-gate:{sid}:{digest16}` | `plugins/saga/scripts/outcome.py:1191-1224` |
| `progress_halt = not current_complete or unresolved_threshold_breach` | `plugins/saga/scripts/dispatch_settlement.py:1059` |
| `FACT_KINDS` closed set, no waiver kind; enforced write-side only in `build_fact` | `plugins/saga/scripts/run_ledger.py:44-55`, `:115-118` |
| Read path hash-chains without kind validation | `run_ledger.py:238-259` (`read_snapshot`, `append_fact_atomic`) |
| Settlement readers validate only `kind == "dispatch-settlement"` records — a `dispatch-waiver` fact is invisible to old readers (KTD2/R5 hinge) | `dispatch_settlement.py:951-958` (`_verified_snapshot`) |
| `approve_frontier` provenance precedent (answerer/transport provenance-not-authorization, machine-local `_write_once`) | `plugins/saga/scripts/outcome_decompose.py:367-397` |
| Gate reads the same ledger the verb would write (`RunLedger.resolve(root)`) | `outcome.py:2598` |
| `approve` subparser and wiring the `waive` verb mirrors | `outcome.py:2470`, `:2628-2645` |
| Helpers exist: `_identifier` (:140), `_bounded_text` (:153), `evidence_digest` (:1490), CLI subparser region (:1673+); no existing `waive` symbol anywhere in `outcome.py`/`dispatch_settlement.py` | `dispatch_settlement.py` |
| `blocking_roster` implementable from `CasualtyReport.entries` — `CasualtyEntry` carries `unit_id`/`attempt`/`classification` incl. synthetic `"open"`/`"unspawned"` | `dispatch_settlement.py:87-94`, `:986-1004` |
| Current saga version `0.108.0`; parity script present | `plugins/saga/.claude-plugin/plugin.json:3`, `scripts/check_release_surface_parity.py` |

Adversarial pass on KTD3's subset rule against the live derivation: delivery drops a pair from the
roster (still covered), a new casualty or new attempt cohort adds a pair (re-halts), an unresolved
breach-feeding casualty always contributes a pair, so roster-empty ⇔ halt-false holds — the plan
already pins that equivalence with a U1 property test.

## Findings

| Key | Priority | Status | Finding |
| --- | --- | --- | --- |
| D1 | P3 | fixed | Multi-waiver receipt composition was underspecified. Resolved: one receipt per newly dispatched sid, mirroring the halt receipt's per-sid shape, naming every covered dispatch id, keyed `settlement-waiver:<sid>:<digest16>` with the digest over the sorted covering-waiver roster digests; re-waive mints a fresh receipt. Encoded in R6, the U2 approach, and a new U2 test scenario. |
| D2 | P3 | fixed | The site-agnostic `waive` CLI flag naming was unstated. Resolved: `dispatch_settlement.py` CLI uses the fact's field names (`--dispatch-id`, `--at`, `--waived-by`, `--reason` required; `--transport` optional); the operator-facing `outcome.py waive` keeps `--answerer` for `approve` parity and maps it to `waived_by`. Encoded in the U1 and U2 approaches. |

## Residual risk

The live-cohort acceptance (R9) mutates the real outcome ledger and is correctly deferred behind an
explicit operator go at `/work` end; it was reviewed as specification only, not exercised here. The
codex-runtime "old readers never error" claim was verified against this repo's reader code and the
memory-recorded fact that `infiquetra-codex-plugins` carries byte-identical copies — the codex-side
files themselves were confirmed present in a prior session, not re-diffed in this review.
