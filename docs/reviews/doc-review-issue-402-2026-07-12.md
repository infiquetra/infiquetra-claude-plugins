# Doc Review — issue #402 spend-observability plan (2026-07-12)

One-line verdict: **READY** — six findings, all safely fixed in place from repo evidence; three
P3 residual notes remain open. No P0/P1 outstanding; `/work` is unblocked.

## Review-result contract

- **Target:** `docs/plans/2026-07-12-spend-observability-plan.md`
- **Reviewed revision:** working tree (pre-commit; plan not yet committed)
- **Blocked:** no
- **Linked:** issue #402; plan saga `issue-402` (destination `pr`, orchestration `inline`,
  recommended `team-execution`); outcome `evidence-integrity` sub-402
- **Method:** readiness-skeptic pass, no formal SDLC rubric (plan-phase document, not
  idea/issue/spec-phase). Factual claims verified against live repo reads —
  `execution_spec.py` (`Unit`/`Verify` dataclasses, `unit_spend`/`adjacent_tier`/`is_escalation`/
  `SPEND_BASELINE`), `outcome_spec.py` (`Node` dataclass field inventory — confirmed absent tier
  field, confirmed presence of `gated`/`risky`/`destructive`/`guarantee_tags`), `outcome_costs.py`
  (`rollup`/`record_cost`, the "no data yet" honesty rule), `evidence_ledger.py` (full read: `write`/
  `freeze_criteria`/`latest`/`verify_chain`/`close_verify`), `tier_defaults.py`/`spend_authority.py`/
  `effort_ledger.py` (full reads), `retro/SKILL.md` (full read, Phase 1/5 structure), `sandbox-
  spawn-sites.md` (full read, table format + fallback ladder), the two real committed
  `docs/outcomes/*/outcome-spec.json` examples (both roll up empty — verified directly), the
  `_example-ship-auth` directory (confirmed no `outcome-spec.json`, so `spend_retro.py`'s glob
  cannot accidentally aggregate it), `resume/SKILL.md`'s committed-docs/GitHub-wins-over-cache
  precedence, `mission-control`'s `_append_tier_band` vs the issue's own distinct "Recommended
  executor profile" section, and current `tests/` file listing (confirmed no
  `test_spend_estimate.py`/`test_spend_receipt.py`/`test_spend_retro.py`/
  `test_tier_efficacy_retro.py`/`test_shadow_audit.py` exist yet, and the real drift-guard test
  names — `tests/test_release_triad.py`, `tests/test_release_surface_parity.py`, not the issue's
  own guessed `-k plugin_metadata_drift`).

## Findings

| # | Pri | Finding | Status |
|---|---|---|---|
| F1 | P1 | KTD1's node-tier fallback lookup resolved via the leaf's own saga `orchestration_ref` — but that state lives under the git-ignored `.claude/saga/` cache, which `resume/SKILL.md` itself names "the anchor, not the authority." `spend_retro.py` (U3) must aggregate long after the fact, possibly from a different machine/fresh clone, so this source would silently fail most of the time. | **fixed** in place: KTD1/R3/DECISIONS.md rewritten to a 2-step lookup sourced only from durable state (the node's committed `github.issue` → its stamped tier band via `gh issue view`, else `SPEND_BASELINE`) |
| F2 | P1 | R1/U1 as originally drafted implied the outcome-node estimate renders inside `/plan`'s own tier table, but the issue's own DoD anchors the estimate column specifically to `/plan/SKILL.md` §5.2a — a single-session `ExecutionSpec.Unit` surface. As drafted, U1's Files list never touched `plan/SKILL.md` at all, so the literal AC ("renders an estimate column alongside `/plan`'s tier table") would not be satisfied by the units as written. | **fixed** in place: R1 reworded to separate the two surfaces; U1 Files/Approach now include a `plan/SKILL.md` edit (Phase 5.2a Step 1 gains the Estimate column) |
| F3 | P1 | R3's tier-value-scoring payoff-at-stake signal was specified as a node's `gated`/`risky`/`destructive`/`guarantee_tags` fields — but those exist only on `outcome_spec.Node`, not on `execution_spec.Unit`, the object R1 anchors the scorer to. As drafted, the scorer's primary (`/plan`-rendered) surface had no signal to read. | **fixed** in place: R3 and U1's Approach now define the scorer over an abstract `{irreversible, gated, destructive}` triple; the `Unit`-level caller derives it from `sandbox`/`verify`/`pilot` fields (which do exist there), the `Node`-level caller reads its own fields directly |
| F4 | P2 | The post-run reconcile's "actual" side (`outcome_costs.py` tokens/wall_seconds) and the ordinal estimate are fundamentally different measurement systems; an unstated reconcile design risked an implementer inventing an unvalidated token-per-ordinal-unit exchange rate (exactly the false-precision R10 forbids). | **fixed** in place: KTD3 pins the reconcile to commensurable fields only (`operator_touches`/`retries`), with tokens/wall_seconds rendered as labeled non-commensurable context |
| F5 | P2 | `shadow_audit.py`'s sufficiency classifier was described only as "structural-equivalence," leaving the implementer to invent a similarity algorithm — itself a false-precision risk (an unvalidated fuzzy-diff threshold). | **fixed** in place: `classify()` pinned to whitespace-normalized exact-match only; anything else defers to the invoking flow's own judgment-based verdict, never a fabricated similarity score |
| F6 | P2 | The attended-mode gate named two possible unlock signals (`--yes`, `.saga/shadow-audit.json`) without stating precedence or whether either alone suffices. | **fixed** in place: either signal alone unblocks `sample`; `--yes` is the narrower one-shot override, the config file the standing default — both stated explicitly, with a matching test scenario added |
| D1 | P3 | The exact `tier_value_score()` formula (how payoff-at-stake and remaining-budget combine numerically into a ladder-rung recommendation) is left to the implementer, bounded only by the two test-matrix endpoints. | **open** (accepted): plans capture decisions, not implementation code (`plan-sections.md`); the boundary behavior is pinned, the formula is an implementation-time choice `/work` documents in the commit |
| D2 | P3 | `tier_efficacy.py`'s `min_samples=3` default is a reasonable but not data-derived choice. | **open** (accepted): low-stakes, adjustable; no repo evidence exists yet to derive a better default (the same "zero real telemetry" gap KTD3/KTD4 already document) |
| D3 | P3 | `spend_retro.py`'s exact journal-table column layout is not pinned to the byte. | **open** (accepted): `formatting-style.md`'s table-for-comparative-data rule already governs the render shape; the implementer has latitude within that contract |

## Applied fixes

Six in-place edits to the plan (Requirements R1/R3, Key Technical Decisions KTD1, Implementation
Units U1/U5, and two Scope Boundaries additions), plus two matching corrections to the
`DECISIONS.md` `{#spend-observability-ktds-402}` entry so the journal and the plan tell the same
story. Two cosmetic line-wrap artifacts from the edit process were also cleaned up (a broken
inline-code span and an awkward mid-sentence hard wrap) — no content change, `formatting-style.md`
rule 5 compliance.

## Residual risk from limited evidence

- Zero real `outcome_costs.py` telemetry exists in this repo today (both committed example
  outcome specs roll up empty) — every "actual"-side test scenario in U1/U2/U3 necessarily runs
  against synthetic fixtures, not a real production run. This is disclosed in the plan itself
  (KTD3/KTD4) rather than hidden, and is the correct honest posture per the repo's own "no data
  yet" rule — but it means the reconcile/receipt/retro surfaces will not see their first real
  numbers until some future outcome actually records cost telemetry.
- The `/retro` tier-efficacy pass's real-world `RunRecord` assembly (joining `spend_retro.py`
  output with `evidence_ledger.py`'s per-check verdict history) is described in the plan's
  Approach but not exercised by an integration-level test scenario — the unit tests exercise
  `propose_downgrades()` directly over hand-built `RunRecord`s. This is an acceptable scope
  boundary (the join logic is a thin `/retro` Phase-1.10 prose step, not a unit this plan
  numbers), but `/work` should keep the two shapes in sync if either changes independently.
