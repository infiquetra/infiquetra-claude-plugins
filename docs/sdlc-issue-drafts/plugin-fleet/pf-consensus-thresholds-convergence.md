---
title: "enhancement: consensus threshold and convergence policy (risk-tiered profiles, HALT on non-convergence, Byzantine-tolerant quorum)"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
---

# enhancement: consensus threshold and convergence policy

### Objective

Establish single-source-of-truth for shared primitives

### Intent

`team-execution`'s consensus panel today hard-codes its acceptance bar (`>= 9.0/10` per
reviewer, `>= 7.0` for architecture's precondition-gated dimension), a fixed 3-cycle
iteration cap that silently proceeds on both gated and advisory failure to converge, and
a panel-size bound (`VERIFY_N_CAP = 7`, `VERIFY_N_WARN = 5`) that is duplicated instead of
shared with `saga`'s own refute-N panel emitter. None of this is configurable per risk
tier, none of it distinguishes "gated" from "advisory" verdicts on cap-out, and a single
miscalibrated reviewer can currently flip a verdict the rest of the panel agrees on. This
issue establishes one policy schema — authored by `/plan` or a `.consensus.json` sidecar,
defaulting to today's exact numbers — that both plugins' kernels evaluate, replacing five
independently-drifting mechanisms with one.

### Problem / motivation

- **Fixed acceptance bar, no risk tiering.** `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:13`
  hard-codes "Each reviewer must achieve an overall score of `>= 9.0/10` to signal
  acceptance," and `:240` hard-codes the architecture precondition-gated dimension's floor
  at `>= 7.0`. There is no mechanism for a plan to raise or lower this bar per risk tier —
  every unit gets the same acceptance threshold regardless of whether it is a one-line
  config change or a security-sensitive migration.
- **3-cycle cap silently proceeds on both gated and advisory failure.**
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:17` reads
  "Maximum iterations: **3**. After 3 cycles, proceed with the best available version
  regardless of scores" — with no fork on whether the unit is gated (should HALT and
  escalate) or advisory (proceeding is the intended behavior). The "After 3 Cycles" section
  (same file, "3-cycle cap reached" language) only ever documents "flag user" and proceed —
  never a hard stop. This directly contradicts the repo's binding HALT-not-degrade
  posture from the `/outcome` campaign (U1–U11): "Derived-on-read status, never committed
  status fields; HALT-not-degrade" (grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  section 2, binding-decision register).
- **Panel-size bound duplicated, not shared.** `plugins/saga/scripts/execution_spec.py:111-117`
  defines `VERIFY_N_CAP = 7` / `VERIFY_N_WARN = 5` for saga's refute-N judge panel emitter
  with an explicit rationale comment ("bound directly guards rate-limit overcorrection —
  R3: 22/23-judges panel tripped concurrency cap"). `team-execution`'s own reviewer panel
  (`consensus-protocol.md`, `validator-execution-order.md`) carries no cross-reference to
  this bound and defines its own reviewer-count expectations independently — two plugins,
  one unwritten policy, no reconciliation point.
- **No quorum fault-tolerance.** Today's consensus rule is effectively "every reviewer
  must individually clear the bar" — one miscalibrated or outlier reviewer score can block
  or force a cycle that the rest of the panel already agrees resolves. There is no
  Byzantine-tolerant quorum-with-adjudication path (T5-F5-5, survivors `T5.json`) for a
  panel where `f=0` failures should still let the honest majority's verdict stand.

### Absorbed ideas (grounding)

| ID | Role | Basis | Summary |
|---|---|---|---|
| `T5-F1-5` | primary | reasoned | Risk-tiered threshold profiles set by `/plan`, defaulting to today's `9.0/7.0/5.0`. `dod_sketch`: "Merged: `threshold_profile` field on plan->team-execution handoff + profiles table (default==9.0/7.0/5.0) derived [from] `parse_issue` risk signals; test asserts 'strict' propagates raised accept bar, default equals current numbers." |
| `T5-F1-4` | facet | direct | Fix the 3-cycle terminal action: a gated consensus that fails to converge must HALT, not silently ship. `dod_sketch`: "Merged: `consensus-protocol.md` 'After 3 Cycles' forks on mode (gated->HALT+escalate, advisory->proceed+record); `README.md` / `validator-execution-order.md` reconciled; test asserts gated cycle-3 non-convergence returns HALT/escalate, not COMPLETE." |
| `T5-F2-7` | facet | (thin seed — see below) | "Remove arbitrary 3-cycle cap: stop on convergence, not [a fixed count]." Reconstructed intent: the kernel should support an early-stop-on-convergence path so a panel that agrees before cycle 3 does not burn the remaining cycles, complementing F1-4's HALT-on-non-convergence fix for the opposite failure mode. |
| `T5-F3-8` | facet | (thin seed — see below) | "Two panel-blowup bounded-panel [bounds]: participant-cap [and] iteration-cap cross-referenced [between] `execution_spec.py` [and] `consensus-protocol.md`." Reconstructed intent: `saga`'s `VERIFY_N_CAP`/`VERIFY_N_WARN` (`plugins/saga/scripts/execution_spec.py:111-117`) and `team-execution`'s reviewer-panel bounds must be reconciled to one documented, cross-referenced policy rather than two independently-maintained numbers. |
| `T5-F4-2` | facet | (thin seed — see below) | "Plan-authored `.consensus.json`: [file] byte-identical [to default] `9.0/7.0/5.0/3` [when absent]." Reconstructed intent: the threshold/convergence policy must be expressible as a plan-authored `.consensus.json` sidecar (in addition to the `/plan`-handoff `threshold_profile` field from F1-5), and when no sidecar is present the kernel's effective defaults must be byte-identical to today's hard-coded `9.0/7.0/5.0` bar and 3-cycle cap. |
| `T5-F5-5` | facet | (thin seed — see below) | "Byzantine-tolerant quorum-with-adjudication, Claude-adjudicated, panel-size, `f=0` [fault tolerance]." Reconstructed intent: quorum evaluation tolerant of one outlier reviewer score, with Claude (never an external engine — per `{#external-engines-never-gatekeepers}` (#283), binding-decision register section 2) as adjudicator of record when reviewers disagree at the margin. |

For `T5-F2-7`, `T5-F3-8`, `T5-F4-2`, `T5-F5-5`: these survivor records carry `basis_type`
fields but their raw `idea`/`basis`/`outcome_shape` text was elided under lossy compression
in the source ideation artifact (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`);
intent above is reconstructed from each entry's `title`, `axis`, and `dod_sketch` fields
(fully preserved, uncompressed) plus the consolidated `dod_sketch`/`ac_sketch` on the merged
issue-map entry (`issue-map-final.json`, slug `pf-consensus-thresholds-convergence`). The
implementing plan must re-derive exact mechanism from these sketches — do not invent
additional scope beyond what the `ac_sketch` below makes testable.

### Binding decisions this must not violate

- `{#external-engines-never-gatekeepers}` (#283): Claude is verifier-of-record for every
  gated decision; the adjudication path in `T5-F5-5` must route through Claude, never an
  external engine.
- `/outcome` campaign (U1–U11), HALT-not-degrade: a gated unit that fails to converge must
  halt with a durable record, never silently proceed with a degraded/unresolved verdict.
  This is the decision `T5-F1-4` directly enforces.

## Definition of Done

A single threshold/convergence policy schema exists, with defaults reproducing today's
exact numbers (`9.0` reviewer accept bar, `7.0` precondition-gated-dimension floor, `5`
panel-size warn threshold, `7` panel-size hard cap, `3`-cycle iteration cap), expressible
either as a `threshold_profile` field on the `/plan` → `team-execution` handoff or as a
plan-authored `.consensus.json` sidecar. The `team-execution` consensus kernel evaluates
this policy to: (a) stop early once convergence is reached rather than always running to
the cap, (b) fork the cycle-cap terminal action on gate mode — HALT + escalate for gated
units, proceed + durable record for advisory units, (c) tolerate one outlier reviewer score
without flipping a verdict the remaining quorum agrees on, and (d) reconcile the two
plugins' panel-size bounds (`saga`'s `VERIFY_N_CAP`/`VERIFY_N_WARN` and `team-execution`'s
reviewer-panel expectations) to one documented, cross-referenced policy. Merged into
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`,
`validator-execution-order.md`, and `plugins/saga/scripts/execution_spec.py` (or a shared
module both import from), with tests proving default-equals-current-behavior and every new
branch (early-stop, HALT-fork, quorum-tolerance).

### Acceptance criteria
- [ ] **Defaults reproduce current behavior exactly (regression parity).** With no
  `threshold_profile` set and no `.consensus.json` present, the kernel's effective policy
  is `accept_threshold=9.0`, `gated_dimension_floor=7.0`, `panel_warn=5`, `panel_cap=7`,
  `max_iterations=3` — bit-for-bit the values at `consensus-protocol.md:13,17,240` and
  `execution_spec.py:111-117` today. Check: a new unit test asserts the parsed default
  policy object equals these five literals.
- [ ] **A gated unit that never converges HALTs with a durable record instead of
  silently shipping.** A gated consensus panel that reaches the 3-cycle cap without
  reaching its threshold returns a HALT/escalate outcome (never `COMPLETE` or an implicit
  proceed). Check: a test drives a gated unit through 3 non-converging cycles and asserts
  the terminal action is `HALT` with an escalation record, not completion.
  (Covers `T5-F1-4`.)
- [ ] **An advisory unit that never converges still proceeds with a durable record** (the
  cap's existing behavior is preserved for advisory-mode units — only gated mode's
  terminal action changes). Check: the same 3-cycle non-convergence drive on an
  advisory-mode unit asserts proceed-with-best-available, with the unresolved-issues
  record still written.
- [ ] **A panel that converges before cycle 3 stops early rather than always running to
  the cap.** Check: a test drives a panel to consensus on cycle 1 or 2 and asserts no
  further review cycle is spawned and the completion path is reached immediately.
  (Covers `T5-F2-7`.)
- [ ] **One outlier reviewer score cannot flip a verdict the remaining quorum agrees on.**
  Check: a test constructs a panel where all-but-one reviewer scores clear the accept
  threshold and the outlier scores well below it; asserts the quorum-tolerant policy
  still returns ACCEPT (not blocked by the single outlier), while a genuinely-split panel
  (two or more below threshold) still fails to converge normally. (Covers `T5-F5-5`.)
- [ ] **A risk-tiered `threshold_profile` propagates and raises the accept bar for
  `strict`.** Check: a test sets `threshold_profile: strict` on a plan → team-execution
  handoff and asserts the evaluated accept threshold for that unit is higher than the
  `9.0` default; a handoff with no `threshold_profile` set still resolves to the default
  numbers. (Covers `T5-F1-5`.)
- [ ] **A plan-authored `.consensus.json` sidecar, when absent, resolves to the exact
  default policy; when present, its values override the defaults.** Check: a test with no
  `.consensus.json` on disk asserts the resolved policy is byte-identical to the default
  literals; a second test with a `.consensus.json` present asserts its values are used
  instead. (Covers `T5-F4-2`.)
- [ ] **The two plugins' panel-size bounds are reconciled to one documented, cross-
  referenced policy.** `plugins/saga/scripts/execution_spec.py`'s `VERIFY_N_CAP`/
  `VERIFY_N_WARN` and `team-execution`'s reviewer-panel size expectations either share one
  constant/schema source or explicitly cross-reference each other in both files' comments
  and in `validator-execution-order.md`. Check: a drift-guard test (or grep-based check)
  fails if the two panel-size bounds diverge without an explicit documented reconciliation
  note. (Covers `T5-F3-8`.)

### Out-of-scope / non-goals
**In scope:**
- The threshold/convergence policy schema (accept threshold, gated-dimension floor,
  panel warn/cap, max iterations, gate mode fork), its defaults, and its two authoring
  paths (`threshold_profile` handoff field, `.consensus.json` sidecar).
- The kernel-side evaluation changes in `team-execution`'s consensus loop: early-stop on
  convergence, HALT-fork on gated cycle-cap, quorum-tolerant verdict aggregation.
- Reconciling (not necessarily merging into one file) `saga`'s and `team-execution`'s
  panel-size bounds documentation.

**Non-goals / explicitly out of scope:**
- Changing the reviewer rubric dimensions themselves (what architecture-reviewer,
  security-reviewer, etc. score) — this issue only touches the acceptance-threshold and
  convergence-policy layer, not scoring content.
- Adding new reviewer roles or changing panel composition beyond the existing
  `VERIFY_N_CAP`/`VERIFY_N_WARN` bound.
- Any change to `saga`'s inline-backend or non-`team-execution` verify-panel emitters
  beyond exposing/cross-referencing the shared bound.
- External-engine participation in adjudication — adjudication stays Claude-only per
  `{#external-engines-never-gatekeepers}` (#283).

## Executor Profile

- **Model:** Sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM posture:** none
- **Justification:** This is a structural, multi-file protocol change (schema design,
  two kernels' evaluation logic, cross-plugin bound reconciliation) but it is well-bounded
  by explicit `ac_sketch` facets and existing hard-coded values to preserve as defaults —
  it does not require judgment calls above Sonnet's ceiling. High effort is warranted for
  the regression-parity and cross-file reconciliation work; no external-LLM involvement
  since Claude remains verifier-of-record for all gated logic touched here.

### Release-surface checklist (this issue changes plugin behavior)

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump, changelog entry
  reference for the new consensus policy schema and HALT-fork behavior.
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump if `execution_spec.py`'s
  panel-bound constants move to a shared location or gain new cross-reference comments.
- [ ] `.claude-plugin/marketplace.json` — updated entries for both `team-execution` and
  `saga` if their plugin.json versions bump.
- [ ] `plugins/team-execution/CHANGELOG.md` and `plugins/saga/CHANGELOG.md` — entries
  describing the new threshold/convergence policy, its defaults, and the HALT-on-gated-
  non-convergence behavior change.
- [ ] Any version/metadata drift-guard tests in `tests/` — extended or added to assert
  plugin.json/marketplace.json/CHANGELOG stay in sync with this change, per CLAUDE.md
  step 6.

### Files expected to change

Indicative only — exact set for `/plan` to determine.

- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`
- `plugins/team-execution/skills/team-execution/references/validator-execution-order.md`
- `plugins/saga/scripts/execution_spec.py`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/team-execution/CHANGELOG.md`
- `plugins/saga/CHANGELOG.md`
- `tests/test_execution_spec.py` (or a new `tests/test_consensus_policy.py`)

### Tests to add or update

- [ ] Default-policy regression-parity test (5-literal equality check).
  Check: `uv run pytest tests/test_consensus_policy.py -k defaults_match_current` → passes.
- [ ] Gated cycle-3 non-convergence HALTs. Check:
  `uv run pytest tests/test_consensus_policy.py -k gated_halt_on_noncoverge` → passes.
- [ ] Advisory cycle-3 non-convergence still proceeds. Check:
  `uv run pytest tests/test_consensus_policy.py -k advisory_proceed_on_noncoverge` → passes.
- [ ] Early-stop-on-convergence before cycle 3. Check:
  `uv run pytest tests/test_consensus_policy.py -k early_stop_on_convergence` → passes.
- [ ] Outlier-tolerant quorum aggregation. Check:
  `uv run pytest tests/test_consensus_policy.py -k outlier_tolerant_quorum` → passes.
- [ ] Risk-tiered `threshold_profile` propagation. Check:
  `uv run pytest tests/test_consensus_policy.py -k strict_profile_raises_bar` → passes.
- [ ] `.consensus.json` sidecar override / absence-default parity. Check:
  `uv run pytest tests/test_consensus_policy.py -k consensus_json_sidecar` → passes.
- [ ] Panel-size bound reconciliation drift guard. Check:
  `uv run pytest tests/test_consensus_policy.py -k panel_bound_reconciled` → passes.
- [ ] Full suite, format, lint, types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification

```bash
# New consensus-policy unit tests
uv run pytest tests/test_consensus_policy.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; default-policy test proves byte-identical parity with today's
hard-coded `9.0/7.0/5.0/3` values; HALT-fork, early-stop, and outlier-tolerant-quorum
tests each exercise a distinct new branch not present before this change.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Grounding References

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json` (ids `T5-F1-5`
  [primary], `T5-F4-2`, `T5-F1-4`, `T5-F2-7`, `T5-F3-8`, `T5-F5-5`)
- Source type: ideation issue-map
- Source title: `pf-consensus-thresholds-convergence` (issue-map-final.json, slug entry;
  the consolidated issue-map artifact lives in the ideation session's scratchpad, not the
  committed repo tree — the per-facet detail it references is fully recoverable from the
  committed `survivors/T5.json`)
- Grounding: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` sections 2 (binding-decision register) and 8 (final theme roster)

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/412
- Number: 412
- Created at: 2026-07-04T08:05:12.196339+00:00

