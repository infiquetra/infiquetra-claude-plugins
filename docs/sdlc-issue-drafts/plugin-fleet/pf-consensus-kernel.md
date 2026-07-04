---
title: "capability: portable consensus kernel — consensus_spec.py extraction, invocation contract, verdict envelope, authority bit, worthiness pre-gate, append-only score log"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Establish single-source-of-truth for shared primitives
wave: wave-2
slug: pf-consensus-kernel
---

# capability: portable consensus kernel

### Objective

Establish single-source-of-truth for shared primitives.

## Summary

`team-execution`'s review-revise consensus cycle (Step B3 of
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`) is the fleet's
proven defect-catcher — the grounding brief records consensus review "catching defects two green
suites missed" as an operator-praised, two-independent-repo finding (grounding brief §3, finding 2)
— but it is trapped as prose inside one plugin. No other lifecycle stage can invoke the primitive:
`saga`'s `/work` reaches for a structurally different gate (`/code-review`'s P0/P1 findings, no
numeric threshold), `/outcome` leaves run their own verify path, and every consumer that wants
consensus-grade review re-derives its own shape instead of calling the one that already works.

This capability extracts the consensus contract into a portable kernel: a data module holding the
numeric contract, a documented invocation contract any lifecycle stage can call, a JSON verdict
envelope any plugin can emit or read, a typed authority bit that makes the gated/advisory governance
split a durable property of the verdict rather than a transient dispatch decision, a pre-spawn
worthiness gate so trivial diffs stop paying full-panel cost, and an append-only score ledger so
per-iteration reviewer trajectories survive past the end of the run.

## Problem Frame

**The contract is prose, not data, so it drifts.** The numeric contract — pass threshold `>= 9.0`,
revision band `7.0–8.9`, blocking floor `< 5.0`/`< 7.0` for security dimensions, and a 3-iteration
cap — is hardcoded directly in
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:17,40,49,70-78,239-240`.
`docs/engineering-journal/DECISIONS.md:88` (the Layer B rationale entry) already records that the
existing drift-guard test, `tests/test_team_execution_consensus.py`, "pins contract *text*, not
whether behavior holds." There is no single numeric/structural source of truth a second plugin could
import instead of re-copying constants by hand.

**The primitive has no invocation seam outside team-execution.** `saga`'s `/work` cannot call the
proven panel — it re-derives a different, non-numeric gate in
`plugins/saga/skills/code-review/SKILL.md`, and `/outcome` leaves independently reinvent their own
verify step. Nothing declares the inputs (participants, threshold-profile, governance-mode) and
outputs (verdict + persisted evidence) of the B3 cycle as a contract another stage can invoke without
re-deriving the cycle end to end.

**The verdict dies as free text, so nothing downstream can honor it.** Today the consensus verdict is
only ever rendered as an ephemeral per-cycle table
(`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:142-157`) and a final
prose note (`:166-172`) inside a session transcript / completion report. There is no schema, so
`/code-review`, an `/outcome` leaf, or `/qa` cannot read a produced verdict and must re-spend tokens
re-running the panel. `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`
already establishes exactly this typed-JSON-pointer pattern in the same plugin (per `CLAUDE.md`'s
note that team-execution is "hybrid" because of it) — the consensus verdict has no equivalent.

**The gated/advisory governance split is a dispatch decision today, not a property of the artifact.**
`plugins/saga/scripts/lifecycle_state.py:108,125,131,164-165` computes `gated_consensus` /
`advisory_consensus` at dispatch time (`consensus_is_gated`, default `True`) and consumes it once —
the distinction is then lost. `docs/engineering-journal/LEARNINGS.md`'s
`{#gated-vs-advisory-consensus-is-a-governance-split}` entry documents the split as **governance**
(does the verdict stick?), not "review depth" — and the binding decision
`{#external-engines-never-gatekeepers}` (`docs/engineering-journal/DECISIONS.md:1985`, #283) requires
that "Claude is verifier-of-record every gated decision; external engine may occupy generator,
advisory-reviewer, non-gated-worker roles only... Enforced structurally, not asserted." If a verdict
is ever ported to a new locus (a resumed saga, an `/outcome` leaf, a `/code-review` escalation),
nothing on the artifact itself records whether it was gating or advisory — the structural enforcement
that binding decision requires cannot survive a port unless the mode travels with the artifact.

**Consensus always spawns the full panel, with no floor.** Step B3a
(`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26`ff) spawns "all
reviewers IN PARALLEL" unconditionally; the only existing cost lever is the "Re-review Scoping"
section, which is post-hoc (it re-runs only reviewers that scored below threshold). There is no
pre-spawn floor — a 3-line README fix pays the same reviewer fan-out as a payments migration. The
grounding brief (§7, finding 6: "xhigh-Opus on everything wasteful") and its recorded
350–450k-token unscaled fan-out singleton establish this as a live cost pain, not a hypothetical.

**Per-iteration score history is thrown away.** Consensus emits only a transient per-cycle table
(`consensus-protocol.md:142-157`) and a final prose summary (`:166-172`); once the run ends, the
per-reviewer, per-iteration trajectory is gone. The grounding brief (§7) separately records a real
chain-of-custody integrity gap ("probe script overwriting FAIL evidence artifact later PASS"), and §3
finding 5 records that the fleet's promote/learning-mining loop "has never fired" for lack of
structured substrate to mine.

## Requirements

R1. A `plugins/saga/scripts/consensus_spec.py` module exports the numeric/structural contract as
data — `PASS_THRESHOLD` (9.0), `REVISION_BAND` (7.0–8.9), `BLOCKING_FLOOR` (5.0, or 7.0 for security
dimensions), `MAX_ITERATIONS` (3), and the static non-applicable-dimension exclusion enum — sitting
beside `execution_spec.py` (the existing precedent for saga-hosted, saga-owned contract modules).
`consensus-protocol.md` is updated to render these constants rather than hardcode them.

R2. A prose-parity drift-guard test parses `consensus-protocol.md` for its stated thresholds/cap and
asserts equality against `consensus_spec.py`'s exported constants; the test goes red if a threshold
is ever edited in only one of the two places.

R3. A documented "Consensus Invocation Contract" section is added to `consensus-protocol.md` (and
cross-referenced from `plugins/saga/references/operator-choice.md` and the `/work` skill),
enumerating the three declared inputs (participants, threshold-profile, governance-mode) and the two
declared outputs (verdict + persisted evidence), so a lifecycle stage can invoke the panel without
re-deriving the cycle.

R4. `/work` (saga) can invoke the proven panel via that portable contract instead of, or in addition
to, `/code-review`'s findings-based gate — routed through the existing
`recommend_execution_backend`/team-execution transport, with no new plugin created.

R5. A `references/consensus-verdict-schema.md` defines a JSON verdict envelope (run-id, per-lens
scores, overall, verdict, gated/advisory bit, iteration, unresolved-fixes, produced-by) plus a
serialize/deref helper (in `artifact_pointer.py` or a sibling script) that Step B3 emits it after
each cycle. `/code-review`, an `/outcome` leaf, and `/qa` can read a produced verdict artifact without
re-running the panel.

R6. Every consensus verdict artifact carries an explicit `authority: gating | advisory` field per
participant and a `governance_mode` field on the verdict as a whole (extending
`lifecycle_state.py`'s dispatch-time `consensus_is_gated` computation so the mode is stamped onto the
persisted record, not only consumed once at dispatch). A guard rejects treating an advisory-stamped
verdict as a merge gate.

R7. An invariant test proves that perturbing an advisory participant's score (e.g. 10 → 0) never
changes the overall gate verdict — advisory scores are surfaced and reconciled by Claude but never
summed into the gate, and every external-reviewer entry is structurally `authority=advisory` by
metadata drift test (operationalizing `{#external-engines-never-gatekeepers}`).

R8. A "Step B2.5 — Consensus worthiness" pre-gate runs before any reviewer is spawned and classifies
the diff into `{none | single-check | full-panel}` using cheap signals (diff size,
`parse_issue.py`-style risk signals, the active `threshold_profile`), defaulting to `full-panel`
whenever a gated risk signal is present so a security/deploy diff is never silently downgraded. The
existing post-hoc re-review-scoping cost lever (top-end, `VERIFY_N_CAP`-bounded) is unchanged; this
adds the missing bottom-end floor.

R9. When the worthiness pre-gate concludes `none`, that conclusion is recorded with a machine-readable
reason (not silently skipped) so downstream consumers can distinguish "no panel was warranted" from
"a panel failed to run."

R10. An append-only consensus ledger (JSONL: run-id, iteration, reviewer, score, verdict,
fix-request digest, authority, adjudication-cause) is written by `consensus_spec.py` alongside the
completion report, one entry per reviewer per iteration. No consumer or process ever mutates a
written entry in place — corrections land as new entries.

## Key Flows

F1. **Existing team-execution run, unchanged behavior.** A team-execution consensus cycle runs
exactly as it does today (score, revise, re-run) but now sources its thresholds/cap from
`consensus_spec.py` instead of hardcoded prose, and emits a verdict envelope (R5) plus ledger entries
(R10) as side effects. **Covers R1, R2, R5, R10.**

F2. **`/work` invokes the portable panel.** `saga`'s `/work` calls the panel through the Consensus
Invocation Contract (R3) instead of re-deriving its own gate; the panel runs the worthiness pre-gate
first (R8) and, if it clears, spawns reviewers exactly as team-execution's Step B3 does, emitting the
same verdict envelope shape. **Covers R3, R4, R8, R9.**

F3. **Advisory participant never gates.** A run includes an external-engine reviewer stamped
`authority=advisory`. Its score is displayed and reconciled by Claude but the invariant test proves
flipping its score end to end never flips the overall verdict; the verdict envelope's
`governance_mode` records the run as gated (Claude's own scores decided it) even though an advisory
voice participated. **Covers R6, R7.**

F4. **Trivial diff skips the panel.** A 3-line README fix hits the worthiness pre-gate, which
concludes `none` with a recorded reason ("diff size below floor, no risk signals present"); no
reviewers are spawned, and the recorded reason is itself a readable artifact, not a silent skip.
**Covers R8, R9.**

### Acceptance criteria
- [ ] AC1. team-execution's review loop produces byte-equivalent verdicts through the kernel. Check: `uv run pytest tests/test_consensus_spec_parity.py -k byte_equivalent_verdict` → passes, proving the kernel-routed run and the pre-kernel run produce identical scores/verdict for the same fixture diff.
- [ ] AC2. `/work` can invoke the proven panel via the portable contract. Check: `uv run pytest tests/test_consensus_invocation_contract.py -k work_invokes_panel` → passes, proving `/work`'s call path reaches Step B3 through the documented contract (not a re-derived gate).
- [ ] AC3. Every verdict artifact carries the gated/advisory bit, and advisory can never flip a gate. Check: `uv run pytest tests/test_consensus_authority_invariant.py -k advisory_score_perturbation` → passes, proving a 10→0 perturbation of an `authority=advisory` participant's score does not change the persisted verdict.
- [ ] AC4. The worthiness pre-gate can conclude "no panel" with a recorded reason. Check: `uv run pytest tests/test_consensus_worthiness_gate.py -k trivial_diff_records_reason` → passes, asserting the `none` classification always persists a machine-readable reason string, and a fixture diff carrying a gated risk signal is never classified below `full-panel`.
- [ ] AC5. Scores land in an append-only log; no in-place verdict mutation. Check: `uv run pytest tests/test_consensus_ledger.py -k append_only_no_mutation` → passes, asserting the ledger writer only appends JSONL entries and a second write for the same run/iteration/reviewer key does not overwrite the first.
- [ ] AC6. The prose-parity drift-guard test fails when a threshold is edited in only one place. Check: `uv run pytest tests/test_consensus_spec_prose_parity.py -k single_edit_detected` → fails (red) when one of `consensus-protocol.md`'s thresholds is edited without a matching edit to `consensus_spec.py`, and passes when both are kept in sync.
- [ ] AC7. The verdict envelope round-trips without losing the gated-bit or applicable-denominator. Check: `uv run pytest tests/test_consensus_verdict_schema.py -k round_trip` → passes.
- [ ] AC8. Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.
## Definition of Done

`consensus_spec.py` exists as the single-source-of-truth data module for the numeric/structural
consensus contract, `consensus-protocol.md` renders from it instead of hardcoding constants, and a
prose-parity drift guard keeps the two in sync. `/work` can invoke the proven panel through a
documented invocation contract, every verdict carries a typed gated/advisory authority bit that
advisory participants can never flip, a pre-spawn worthiness gate lets trivial diffs skip the panel
with a recorded reason, and per-iteration scores land in an append-only ledger. AC1–AC8 all pass.

### Out-of-scope / non-goals
- This capability extracts and hardens the *existing* B3 consensus contract; it does not redesign
  the scoring rubric, the reviewer roster, or the 9.0/7.0/5.0 thresholds themselves (those stay as
  currently defined, just sourced from data instead of prose).
- No new plugin is created. The kernel lands inside `saga` (`consensus_spec.py`, beside
  `execution_spec.py`) per the same reasoning `T5-F2-1`/`T5-F1-1` already establish, honoring the
  fleet's plugin-portfolio-groom pressure to avoid an 8th marketplace plugin.
- Team-execution's existing proceed-best-available 3-cycle cap is unchanged by this work; the
  worthiness pre-gate (R8) only adds a pre-spawn floor, not a post-cycle behavior change.
- External-engine worker slots (a "team-execution gains an external-engine worker slot" expansion)
  are out of scope here; this capability only makes the authority bit typed and structurally
  enforced for whatever advisory participants already exist today.
- Backfilling a machine-readable output contract onto every existing reviewer prompt is out of
  scope; the worthiness pre-gate and verdict schema work with the reviewer roster as it exists.
- Full learning-mining consumption of the append-only ledger (closing the "promote loop never
  fired" gap from grounding brief §3 finding 5) is out of scope — this capability only produces the
  substrate; mining it is a separate downstream capability.

## Dependencies / Assumptions

- Depends on `plugins/saga/scripts/execution_spec.py` existing as the precedent pattern for a
  saga-hosted contract module (verified: `plugins/saga/scripts/execution_spec.py`).
- Depends on `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` existing as
  the precedent pattern for a typed JSON pointer artifact (verified: file present; `CLAUDE.md` notes
  team-execution is "hybrid" because of it).
- Depends on `plugins/saga/scripts/lifecycle_state.py:108,125,131,164-165` continuing to compute
  `consensus_is_gated`/`gated_consensus`/`advisory_consensus` at dispatch — this capability extends
  that computation to persist onto the verdict record rather than replacing it.
- Assumes the binding decision `{#external-engines-never-gatekeepers}` (DECISIONS.md #283) and the
  `{#gated-vs-advisory-consensus-is-a-governance-split}` LEARNINGS entry remain current policy; this
  capability is the structural-enforcement mechanism those two entries call for, not a new policy.
- Assumes `docs/engineering-journal/DECISIONS.md:88`'s "pins contract text, not behavior" gap is the
  correct characterization of `tests/test_team_execution_consensus.py`'s current coverage — verified
  by reading that test's assertions against `consensus-protocol.md`'s prose thresholds.

### Files expected to change

Indicative only; exact set is `/plan`'s to determine.

- `plugins/saga/scripts/consensus_spec.py` — new module (thresholds, cap, exclusion enum).
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — renders
  constants from `consensus_spec.py`; adds "Consensus Invocation Contract" and "Step B2.5 —
  Consensus worthiness" sections.
- `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` (or a sibling script) —
  verdict-envelope serialize/deref helper.
- `plugins/team-execution/skills/team-execution/references/consensus-verdict-schema.md` — new schema
  doc.
- `plugins/saga/scripts/lifecycle_state.py` — extend verdict record with `governance_mode` /
  `authority` fields.
- `plugins/saga/references/operator-choice.md`, `plugins/saga/skills/work/SKILL.md` — cross-reference
  the invocation contract.
- `tests/test_consensus_spec_prose_parity.py`, `tests/test_consensus_spec_parity.py`,
  `tests/test_consensus_invocation_contract.py`, `tests/test_consensus_authority_invariant.py`,
  `tests/test_consensus_worthiness_gate.py`, `tests/test_consensus_ledger.py`,
  `tests/test_consensus_verdict_schema.py` — new tests (repo-root collected).

### Tests to add or update

- Prose-parity drift guard: `consensus-protocol.md` thresholds/cap vs. `consensus_spec.py` exports.
- Byte-equivalent verdict parity: kernel-routed run vs. current team-execution run, same fixture.
- `/work` invocation-contract test: proves the call reaches Step B3, not a re-derived gate.
- Authority invariant: advisory-score perturbation (10→0) never changes the gate; metadata drift test
  asserts every external reviewer entry is `authority=advisory`.
- Worthiness pre-gate: trivial diff → `none` with recorded reason; gated risk signal → never below
  `full-panel`.
- Append-only ledger: no in-place mutation on a repeated write for the same key.
- Verdict-envelope round trip: gated-bit and applicable-denominator survive serialization.

## Release-surface checklist

This capability changes plugin behavior (`consensus-protocol.md`), schema (verdict envelope), and
CLI surface (`consensus_spec.py`, worthiness pre-gate) in both `team-execution` and `saga`. Update in
the same PR:

- `plugins/team-execution/.claude-plugin/plugin.json` — version bump (behavior + schema change).
- `plugins/saga/.claude-plugin/plugin.json` — version bump (new `consensus_spec.py` module, verdict
  fields on `lifecycle_state.py`).
- `.claude-plugin/marketplace.json` — version/metadata sync for both `team-execution` and `saga`
  entries.
- `plugins/team-execution/CHANGELOG.md` and `plugins/saga/CHANGELOG.md` — entries describing the
  consensus kernel extraction, verdict envelope, authority bit, worthiness pre-gate, and ledger.
- Any version/metadata drift-guard tests in `tests/` that assert plugin.json ↔ marketplace.json ↔
  CHANGELOG parity — run and confirm green before calling the PR ready.

### Verification

```bash
# New kernel tests
uv run pytest tests/test_consensus_spec_prose_parity.py tests/test_consensus_spec_parity.py \
  tests/test_consensus_invocation_contract.py tests/test_consensus_authority_invariant.py \
  tests/test_consensus_worthiness_gate.py tests/test_consensus_ledger.py \
  tests/test_consensus_verdict_schema.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green.

## Grounding References

Every absorbed idea below carries its own basis; this issue is their union.

- **G-hybrids-10** (primary) — basis: grounding brief §7 (Claude+Codex 15/17 convergence,
  hand-reconciled, session-mining synthesis `wf_7e5d77a2-5c0`) and §3.2 (consensus catching defects
  green suites missed, 2 independent repos, operator-praised). Parents: `T5-F6-1`, `T5-F4-3`,
  `T5-F4-4`, `T5-F6-8`. Builds on `{#external-engines-never-gatekeepers}`.
- **S-29** (dedup-merged) — operator statement: "same consensus protocol from team-execution usable
  in dynamic workflows."
- **S-20** (dedup-merged) — operator statement: "reuse one worker to write code with others
  reviewing."
- **T5-F2-1** (facet) — basis: `consensus-protocol.md:17,74` hardcodes `9.0`/`7.0`/`5.0`/"Maximum
  iterations: 3"; `DECISIONS.md:88` records the existing test "pins contract text, not behavior."
- **T5-F1-1** (facet) — basis: `consensus-protocol.md:10-62` defines the B3 cycle team-execution
  internal; `plugins/saga/skills/code-review/SKILL.md` reimplements a distinct findings-based gate;
  grounding brief §3 finding 2.
- **T5-F6-2** (facet) — basis: `artifact_pointer.py` already establishes the typed JSON pointer
  pattern in team-execution; `consensus-protocol.md:161-172` shows the verdict dying as free text
  with no schema.
- **T5-F4-3** (facet) — basis: crosses `{#external-engines-never-gatekeepers}` (#283), operationalizes
  `{#gated-vs-advisory-consensus-is-a-governance-split}`; `lifecycle_state.py:164-165` computes the
  split at dispatch only; `LEARNINGS.md:523-533` documents it as governance, not depth.
- **T5-F5-2** (facet) — basis: binding decision `{#external-engines-never-gatekeepers}` (#283,
  grounding brief §2): "Claude verifier-of-record every gated decision; codex/agy =
  generator/advisory-reviewer/non-gated worker only. Structurally enforced."
- **T5-F1-8** (facet) — basis: `consensus-protocol.md:26` (B3a) spawns "all reviewers IN PARALLEL"
  unconditionally; grounding brief §7 finding 6 ("xhigh-Opus on everything wasteful") and the
  350–450k-token unscaled fan-out singleton.
- **T5-F5-8** (facet) — basis: `consensus-protocol.md:142-157` and `:166-172` show scores rendered
  only as ephemeral per-cycle/final-prose; grounding brief §7 (probe-script FAIL/PASS
  chain-of-custody gap) and §3 finding 5 (promote/learning loop "has never fired").

## Recommended executor profile

- **Model:** Sonnet
- **Effort:** xhigh — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM posture:** none
- **Justification:** This is a structural, multi-plugin (saga + team-execution) extraction touching
  a load-bearing governance invariant (`{#external-engines-never-gatekeepers}`) with byte-equivalence
  and invariant tests as hard acceptance gates — xhigh effort is warranted to hold the parity and
  invariant proofs together across both plugins without regressing existing team-execution behavior.
  Sonnet (not Opus) is appropriate: the work is mechanical extraction/refactor of an already-decided
  contract (not a new judgment call), matching the fleet's model-tiering guidance that mechanical or
  deterministic work runs on Sonnet rather than Opus.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan pf-consensus-kernel` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`,
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- Source type: ideation (saga:ideate, wave-2 issue-map)
- Source title: Portable consensus kernel — consensus_spec.py extraction, invocation contract,
  verdict envelope, authority bit, worthiness pre-gate, append-only score log

### Intent

`team-execution`'s review-revise consensus cycle (Step B3 of `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`) is the fleet's proven defect-catcher — the grounding brief records consensus review "catching defects two green suites missed" as an operator-praised, two-independent-repo finding (grounding brief §3, finding 2) — but it is trapped as prose inside one plugin. No other lifecycle stage can invoke the primitive: `saga`'s `/work` reaches for a structurally different gate (`/code-review`'s P0/P1 findings, no numeric threshold), `/outcome` leaves run their own verify path, and every consumer that wants consensus-grade review re-derives its own shape instead of calling the one that already works.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/411
- Number: 411
- Created at: 2026-07-04T08:04:48.462453+00:00

