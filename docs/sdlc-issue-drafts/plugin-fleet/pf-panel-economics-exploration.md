---
title: "exploration: panel economics — measured reviewer independence, consensus elasticity, acceptance-sampling review"
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Build the fleet telemetry and ledger substrate"
wave: wave-2
---

# exploration: panel economics — measured reviewer independence, consensus elasticity, acceptance-sampling review

### Objective

Build the fleet telemetry and ledger substrate.

### Intent

Produce one recommendation document that answers, with evidence rather than intuition, when the
team-execution consensus panel's cost can safely shrink without weakening the gate. The document
must (1) define the exact ledger facts the fleet's telemetry substrate must emit to make reviewer
independence and agreement measurable, (2) name the miscalibration risk each proposed cost-shrink
mechanism introduces and how that mechanism would detect it, and (3) end in an explicit
build-or-park recommendation, in priority order, for each of three absorbed mechanisms:
measured-independence panel-selection guards, consensus elasticity (agreement-driven panel
shrink with spot-check snap-back), and acceptance-sampling review (risk-stratified hunk sampling
on large diffs). This is an exploration: it produces a recommendation document with kill criteria,
not shipped code.

## Problem / Motivation

The team-execution consensus panel currently spends a fixed, convention-set cost on every review
regardless of measured signal. Three independent gaps back this:

1. **No independence measurement.** `reviewer-registry.md` lists candidate lenses with no
   independence or correlation metadata, so a panel of three correlated lenses (for example,
   security-reviewer, privacy-reviewer, data-handling-reviewer) scores as if it were three
   independent votes when it may be one opinion counted three times. The one number the fleet has
   for what independent review is worth — "Claude+Codex independent syntheses converging 15/17,
   hand-reconciled" (theme-5 prior art, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
   section 7) — was measured once, by hand, and never captured as a repeatable signal.
2. **No agreement ledger.** `consensus-protocol.md:142-157` renders reviewer scores only as an
   ephemeral per-cycle table, and `:161-172` keeps only a final prose summary of the outcome after
   iteration; no per-reviewer, per-iteration agreement record survives the run. Panel size is set
   by convention, not by measured agreement, so the operator-praised defect catches recorded in
   the grounding brief's section 3 finding 2 (consensus catching defects two repos' green suites
   missed) may be concentrated in a minority of lens/file-type combinations while the rest of the
   panel is over-provisioned ceremony that nobody has verified is earning its cost.
3. **No cost-scaling by diff size.** `consensus-protocol.md:28,190-198` passes reviewers the full
   diff (or an artifact-pointer to it) with no size-scaling; review cost grows with lot size on
   every diff regardless of risk concentration, while the grounding brief's cache-economics
   singleton ("350-450k tokens in <20 min for read-only recon fan-outs," section 7) shows how fast
   this class of fan-out spend compounds.

Without this exploration, the fleet has three separately-argued cost-shrink ideas
(`T5-F3-6`, `T5-F5-7`, `H-F6-10`) with no common measurement substrate to decide which, if any, are
safe to build, and no way to distinguish "this mechanism would save real cost" from "this mechanism
would quietly erode the gate."

## Definition of Done

A merged recommendation document (a durable markdown artifact, for example under `docs/plans/` or
`docs/engineering-journal/narratives/`) that:

1. **Defines the exact ledger facts** the fleet's run-fact/telemetry substrate must emit for each
   of the three absorbed mechanisms to be evaluable — at minimum: per-reviewer per-iteration score
   and verdict, a findings-overlap or lens-correlation signal between panel members, and a
   per-hunk risk classification (security/auth/public-API vs. other) — and states, for each fact,
   whether the current substrate already emits it or would need new instrumentation.
2. **States the miscalibration risk each shrink mechanism introduces**, and names that mechanism's
   own detection signal for the risk it introduces (independence-weighting risks scoring
   correlated lenses as independent; consensus elasticity risks a shrunk panel missing a defect a
   full panel would have caught; acceptance sampling risks an out-of-sample hunk containing the one
   real defect).
3. **Ends in an explicit build-or-park recommendation per mechanism**, in priority order, each
   with a stated kill criterion (a condition under which the mechanism should not be built even if
   feasible) and — for any mechanism recommended to build — a pointer to what a follow-up
   implementation issue would need to cover.

This issue does not implement any of the three mechanisms; it produces the evidence and
recommendation substrate a follow-up implementation issue would consume.

### Acceptance criteria
- [ ] **AC1 (ledger facts named and matched to substrate, facet: `H-F6-10`).** The document names
      the exact fields an agreement-ledger written by team-execution's consensus step would need
      (per-reviewer, per-iteration score/verdict, and a findings-overlap measure) and states
      whether `consensus-protocol.md`'s current per-cycle score table already carries this data or
      whether new instrumentation is required. Check: the document contains a section titled (or
      clearly headed) "Agreement ledger fields" listing each field and its current-substrate
      status.
- [ ] **AC2 (independence/correlation signal defined, facet: `T5-F3-6`).** The document defines
      what "measured reviewer independence" means operationally for the fleet's panel (a
      findings-overlap or correlation metric between two or more lens outputs on the same diff)
      and states what `reviewer-registry.md` would need to carry to make a panel-selection
      independence guard evaluable. Check: the document contains a worked example distinguishing a
      correlated three-lens panel from a diverse panel using the defined metric.
- [ ] **AC3 (risk-stratified sampling model defined, facet: `T5-F5-7`).** The document defines the
      risk-stratification rule for acceptance-sampling review (which hunk categories are always
      in-sample, which are AQL-sampled by diff magnitude) and states the acceptance-number
      escalation-to-full-review rule. Check: the document states explicitly that security/auth/
      public-API hunks are always in-sample under the proposed model, and gives the escalation
      condition in one sentence.
- [ ] **AC4 (miscalibration risk stated per mechanism).** For each of the three mechanisms, the
      document states in prose the specific way that mechanism could quietly weaken the gate if
      built carelessly, and names the signal that would detect that specific degradation (not a
      generic "test coverage" statement — a named, mechanism-specific detection signal).
- [ ] **AC5 (build/park recommendation, ordered, with kill criteria).** The document ends with an
      explicit, ordered (not merely listed) build-or-park recommendation for all three mechanisms,
      each carrying a stated kill criterion. Check: a reader can identify, without inference, which
      mechanism (if any) is recommended to build first and under what condition each should be
      parked instead.
- [ ] **AC6 (never-gatekeepers boundary respected).** The document does not recommend any mechanism
      that would let an external engine's score count toward the panel's pass/fail gate — all three
      mechanisms are scoped to Claude-internal panel composition, sizing, and sampling, consistent
      with `{#external-engines-never-gatekeepers}` (#283). Check: the document contains an explicit
      statement that none of the three recommendations touches the gated/advisory boundary.
- [ ] **AC7 (grounded, not extrapolated).** Every claim about current fleet behavior in the document
      cites a specific file:line (e.g. `consensus-protocol.md:142-157`, `reviewer-registry.md`) or
      a named grounding-brief section, rather than an unverified "likely" or "probably" claim about
      how the consensus protocol currently behaves.

### Out-of-scope / non-goals
**In scope:** reading the current consensus protocol, reviewer registry, and grounding-brief
evidence; producing one merged recommendation document covering all three absorbed facets
(independence measurement, consensus elasticity, acceptance sampling); defining the ledger
substrate each needs; issuing an explicit ordered build-or-park recommendation with kill criteria.

**Non-goals (explicitly out of scope for this issue):**
- Implementing any agreement ledger, panel-selection guard, elasticity policy, or hunk sampler —
  those are follow-up implementation issues if this exploration recommends building them.
- Changing `consensus-protocol.md`, `reviewer-registry.md`, or `execution_spec.py` — this issue is
  read-only research and recommendation, no plugin behavior changes.
- Resolving the `T5-F5-2` authority-gradient or `H-F5-4` Byzantine-quorum ideas — those were killed
  as duplicates of stronger candidates in the same theme and are not part of this issue's scope.
- Standing up a scheduled or repeating measurement loop — any recommended ledger is a one-time
  substrate-definition exercise for this issue; a standing measurement ceremony is explicitly the
  kind of shape the grounding brief's section 4 records as already rejected elsewhere in the fleet
  for a solo tool, and this document must not casually reintroduce it.

## Grounding References

- **Absorbed ideas** (`docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`,
  slug `pf-panel-economics-exploration`):
  - `H-F6-10` (primary) — "Consensus elasticity: shrink panels where measured reviewer agreement is
    high, backed by sampled spot-checks" (theme T5, frame F6, axis `zero-consensus`, basis_type
    `direct`, verdict `survive`) — basis: grounding brief section 7 singleton on the
    Claude+Codex 15/17 hand-reconciled convergence, and section 3 item 2 (consensus catching
    defects two repos' green suites missed) as the counter-pressure the spot-check snap-back
    answers — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`.
  - `T5-F3-6` (facet) — "Correlated lenses fake agreement — measure panel independence, don't
    assume it" (theme T5, frame F3, axis `membership-diversity`, basis_type `reasoned`, verdict
    `survive`) — basis: the 15/17 convergence number is meaningful only because the two syntheses
    were independent, and `reviewer-registry.md` lists lenses with no independence metadata today
    — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`.
  - `T5-F5-7` (facet) — "Acceptance-sampling review: inspect a risk-stratified sample of hunks, not
    every line" (theme T5, frame F5, axis `cost-scaling`, basis_type `external`, verdict `survive`)
    — basis: MIL-STD-105E / ISO 2859-1 acceptance sampling (sample size and acceptance number as
    functions of lot size and Acceptable Quality Level), applied against
    `consensus-protocol.md:28,190-198`'s no-size-scaling full-diff review and the grounding brief's
    large-diff review-cost spend driver — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`.
- **Binding decisions this issue builds on and must not violate**
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 2):
  - `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; any
    independence, elasticity, or sampling mechanism this document recommends must remain
    Claude-internal panel tuning, never a lever that lets an external engine's score gate a merge.
  - `{#tier-vocab-ordering}` — if the recommendation touches panel-size or iteration-cap ordering,
    it must be expressed as ordered/bounded policy, consistent with how `T5-F3-8`'s "reconcile the
    two panel-cap constants" framing treats bounded-panel cost as governance, not ad hoc numbers.
- **Consumer-side evidence** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 6/7):
  recurring-pain item "Stale memory/doc claims asserted as fact, caught only by operator recall"
  and the session-mining "350-450k tokens in <20 min for read-only recon fan-outs" singleton both
  motivate why this exploration insists on measured, ledger-backed signals rather than
  convention-set panel sizing.
- **Current-state citations for AC7:** `consensus-protocol.md:17` (max-3-iterations cap, no
  agreement measurement), `:28,190-198` (full-diff/artifact-pointer review, no size-scaling),
  `:142-157` (ephemeral per-cycle score table), `:161-172` (final prose summary only);
  `reviewer-registry.md` (fixed lens roster, no independence/correlation metadata);
  `plugins/saga/scripts/execution_spec.py:114` (`VERIFY_N_CAP = 7`, the fleet's one existing
  panel-size bound, proving panel size is already a tunable but not yet a measured one).
- **Objective + wave placement:** consolidated under Objective "Build the fleet telemetry and
  ledger substrate," wave-2, per `issue-map-final.json`.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** second-opinion (a cheap external second opinion on the statistical
  design of the acceptance-sampling AQL parameters and the independence/correlation metric is
  intake-sanctioned and improves the document's rigor without letting the external engine gate
  anything; Claude remains verifier-of-record for the final recommendation)
- **Justification:** this is a judgment-shaped statistical-design question (what to measure, how
  to define independence and acceptance numbers, how to weigh cost-shrink against gate-quality
  risk) rather than mechanical scaffolding, warranting sonnet/high over a lower-effort tier; it does
  not warrant opus, since the deliverable is a grounded recommendation document over existing,
  already-scoped mechanisms, not novel system architecture.

## Release-Surface Checklist

Not applicable — this issue produces a recommendation document only and makes no plugin behavior,
schema, command, or prompt change. No updates required to any
`plugins/<plugin>/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, plugin
`CHANGELOG.md`, or drift-guard tests. If the document recommends building one or more of the three
mechanisms, each resulting follow-up implementation issue carries its own release-surface
checklist (team-execution's `plugin.json`/`marketplace.json`/`CHANGELOG.md` at minimum, since all
three mechanisms live in `plugins/team-execution/`).

## Files Expected to Change

Indicative only; exact set for `/plan` to determine.

- `docs/plans/` or `docs/engineering-journal/narratives/` — new merged recommendation document
  (exact path TBD by `/plan`).
- `docs/engineering-journal/LEARNINGS.md` — dated entry capturing what the exploration found about
  measured panel economics, per this repo's auto-maintain convention.
- No changes to `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`,
  `reviewer-registry.md`, or `plugins/saga/scripts/execution_spec.py`.

### Verification
```bash
# Confirm no consensus/registry implementation files were touched by this exploration
git diff --name-only origin/main... -- \
  plugins/team-execution/skills/team-execution/references/consensus-protocol.md \
  plugins/team-execution/skills/team-execution/references/reviewer-registry.md \
  plugins/saga/scripts/execution_spec.py
# Expected: empty output

# Confirm the recommendation document exists and covers all three absorbed mechanisms
test -f <recommendation-doc-path> && grep -Ec "agreement.ledger|independence|acceptance.sampling" <recommendation-doc-path>
# Expected: file exists; match count >= 3 (one section per mechanism)

# Confirm the document ends in an explicit ordered build/park recommendation
grep -Ei "recommend(ation)?s?:? (build|park)" <recommendation-doc-path>
# Expected: at least one build/park line per mechanism (3 total)
```

Expected: all checks pass; the recommendation document is committed and readable, with its
build-or-park verdicts and kill criteria legible without access to this issue's originating
conversation.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to scope which of the three mechanisms (if any) get a follow-up implementation
plan, once the recommendation document's build/park verdicts are in.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`, slug
  `pf-panel-economics-exploration`, absorbing `H-F6-10` (primary), `T5-F3-6` (facet), `T5-F5-7`
  (facet)
- Source type: ideation survivor (issue-map)
- Source title: Exploration: panel economics — measured reviewer independence, consensus
  elasticity, acceptance-sampling review

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`
- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/LEARNINGS.md`
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`
- `plugins/saga/scripts/execution_spec.py`

### Tests to add or update

- Full repo gate: `uv run pytest` (no new test files named; see Acceptance criteria)
