---
title: "capability: execution-substrate decoupling — mechanism-neutral review/ceremony substrate rendered onto agent-team and workflow backends, inherent-property backend chooser, rigor-preserving degrade ladder"
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
slug: pf-execution-substrate-decoupling
---

# capability: execution-substrate decoupling

### Objective

Establish single-source-of-truth for shared primitives.

## Summary

The fleet has two execution mechanisms — agent teams (Agent tool + addressable teammates) and
dynamic workflows (Workflow tool + compiled orchestration script) — but only one of them carries
the review substrate. team-execution owns 25 agent definitions (reviewers, scanners, testers,
monitors in `plugins/team-execution/agents/`), the consensus choreography, and the ship ceremony,
for the historical reason that agent teams existed before the Workflow tool. The consequence is a
category error at every backend decision: executors are chosen for *provisioned* properties
("team-execution has reviewers") instead of *inherent* ones (compiled vs interpreted coordination),
and saga's own `DEGRADE_LADDER = ("cc-workflows-ultracode", "team-execution", "inline")`
(`plugins/saga/scripts/outcome_dispatcher.py:55`) is quietly incoherent — degrading a rung changes
not just coordination but the review rigor the run receives.

This capability extracts the substrate into mechanism-neutral form: a machine-readable substrate
manifest declaring every reviewer/scanner/tester/monitor as portable content; a workflow renderer
that compiles a plan plus that manifest into a standard Workflow script (panel fan-out, bounded
review-fix rounds, ceremony steps, budget ceiling); a backend chooser rubric defined **only** on
inherent mechanism properties; and a rigor-preserving degrade ladder whose receipts record any
substrate delta. The harness already permits all of this: workflow `agent()` calls resolve
`agentType` from the same registry as the Agent tool — saga's execution-spec emitter already
renders a review-class agent onto the workflow mechanism today
(`plugins/saga/scripts/execution_spec.py:88-93,904`, `READONLY_VERIFIER_AGENT_TYPE =
"saga:readonly-verifier"`). What is missing is not capability but a harness of standard practices —
the substrate contract and the renderer.

## Problem Frame

**The review substrate is coupled to one mechanism by history, not necessity.** The 25 agent
definitions under `plugins/team-execution/agents/` are prompt content — mechanism-portable by
construction, since the Workflow tool resolves `agentType` from the same agent registry the Agent
tool uses. Yet the rosters and triggers that govern them live in team-execution-internal prose
(`plugins/team-execution/skills/team-execution/references/reviewer-registry.md`,
`validator-registry.md`), consumable only by the agent-team choreography. A workflow-backend run
gets none of it unless someone hand-authors reviewer prompts into a bespoke script.

**Backend choice is argued from the wrong properties.** With the substrate trapped in one backend,
every executor decision collapses to "needs reviewers → team-execution," which is not a mechanism
property at all. The actual inherent differences are: workflows give deterministic compiled control
flow, per-call model/effort/schema dispatch, native resume/cache (journal replay), and a hard token
budget primitive, but are non-interactive mid-run and their agents are one-shot and unaddressable;
agent teams give model-driven adaptive coordination, persistent addressable teammates
(SendMessage), context-inheriting forks, and operator gates anywhere, but have no native
durability (saga built spores and board↔saga reconciliation, #295, to approximate what workflows
get free), no budget primitive, and no per-call effort (verified 2026-07-04: zero effort threading
anywhere in `plugins/team-execution/` — the gap `pf-effort-first-class` exists to close).

**The degrade ladder changes rigor silently.** `outcome_dispatcher.py:47-55,294-295` implements a
one-rung degrade across `("cc-workflows-ultracode", "team-execution", "inline")` — but because the
substrate is unequal across rungs, a degrade is not the same work on a cheaper coordinator; it is
different review coverage with no receipt saying so. A ladder is only coherent if the substrate is
constant (or its delta explicit) across rungs.

**Robustness evidence favors compiled coordination where it applies.** The 2026-07-03/04
plugin-fleet ideation program ran its multi-hundred-agent phases as workflows with zero agent
errors and free crash recovery via journal replay, while the session's coordination failures
(unauthorized relaunch with a dropped concurrency safeguard, an idle-without-delivering teammate)
were all model-driven-coordination failures — a compiled script cannot forget its safeguards
mid-run. Where coordination is decidable at plan time, the workflow mechanism is strictly more
durable, more budget-governable, and more precisely dispatched; the review substrate should not be
the reason it loses the backend decision.

## Requirements

R1. **Substrate manifest.** A machine-readable manifest (data module or structured file, sited per
R6) declares every reviewer/scanner/tester/monitor currently registered in
`reviewer-registry.md`/`validator-registry.md`: agent-type id, role, always-on vs
trigger-conditional (with trigger terms), required output contract, and gating authority — with no
agent-team choreography embedded in the entry. The two existing prose registries render from or
drift-guard against it.

R2. **Workflow renderer.** A generator script compiles (plan, substrate manifest, intent posture) →
a standard Workflow script: reviewer panel fan-out via `agent()` with `agentType` from the
manifest (per-call model/effort set from the plan's tier table), bounded review-fix rounds
(`while !approved && round <= cap`), worktree isolation for mutating stages, a hard budget ceiling,
and ceremony steps (branch/commit/PR/evidence-attach) as terminal stages. Precedent:
`execution_spec.py`'s emitter (`:88-93,904`) already does exactly this for saga verify panels.

R3. **Gates at boundaries, by design.** Operator gates (plan approval, pre-merge) land at workflow
boundaries: the renderer splits the compiled run into phases that return to the main loop at each
gate. The renderer must refuse (fail loud, not degrade) any plan whose gates are data-dependent
mid-unit — that plan is agent-team-shaped by the chooser rubric, not a rendering target.

R4. **Inherent-property backend chooser.** A documented rubric — consumed by saga `/plan`'s backend
recommendation and `/outcome`'s dispatcher — that decides agent-team vs workflow **only** on
inherent properties: coordination decidability at plan time, negotiation density (expected review
rounds / plan-rewrite likelihood), mid-run interactivity needs, durability/resume requirements,
budget-governance requirements, dispatch-precision requirements. A lint on the rubric doc asserts
no provisioned property (reviewer availability, ceremony presence) appears as a criterion.

R5. **Rigor-preserving degrade ladder.** `degrade_decision`'s receipts
(`outcome_dispatcher.py:267-295`) are extended to record the substrate delta of any rung change;
a degrade that would shed guarantee-bearing substrate (a gating reviewer, a required scanner)
HALTs instead of degrading — same posture as the existing guarantee-bearing HALT rule.

R6. **Siting follows the fleet-commons decision.** The manifest and renderer land where
`pf-fleet-commons-decision` concludes shared primitives live; until that exploration closes, the
default siting is beside the existing precedents (`consensus_spec.py` pattern, saga-hosted) with
team-execution consuming — no new plugin.

R7. **Evidence parity.** Both backends emit the same review-evidence envelope for equivalent runs
(depends on `pf-consensus-kernel`'s verdict envelope; this issue consumes that schema, never forks
it). A fixture plan run through both backends triggers the same manifest roster and produces
evidence of identical shape.

R8. **Honest effort asymmetry.** The renderer sets per-call effort on workflow `agent()` calls; the
agent-team path documents that effort is static (agent-definition frontmatter) until
`pf-effort-first-class` lands. The chooser rubric records this asymmetry as an input, and re-visits
when that issue ships.

## Key Flows

F1. **Plan → workflow backend, full substrate.** `/plan` classifies a decidable implement-and-merge
plan via the chooser (R4); the renderer (R2) compiles plan + manifest into a phased workflow
(implement → panel fan-out → bounded fix rounds → ceremony), gates at phase boundaries (R3);
the run emits the standard evidence envelope (R7). **Covers R1, R2, R3, R7.**

F2. **Same plan → agent-team backend, same substrate.** team-execution executes the identical plan
sourcing its roster/triggers from the same manifest (R1); evidence envelope is shape-identical
(R7); the run record notes static-effort posture (R8). **Covers R1, R7, R8.**

F3. **Degrade with receipt.** A leaf targeted at `cc-workflows-ultracode` on a host without it
degrades one rung to team-execution; the receipt records "substrate delta: none" (same manifest) —
whereas a hypothetical degrade to `inline` that sheds a gating reviewer HALTs with a
`BackendHaltError`-style receipt naming the shed guarantee. **Covers R5.**

F4. **Negotiation-dense plan routes to teams, with reasons.** A plan whose scope is expected to be
rewritten by implementation discoveries (chooser signals: exploratory refactor, unresolved design
questions, operator wants live steering) is routed to the agent-team backend; the chooser records
the inherent-property reasons on the decision record — never "because reviewers." **Covers R4.**

### Acceptance criteria
- [ ] AC1. Manifest covers the full roster with no choreography leakage. Check: `uv run pytest tests/test_substrate_manifest.py -k roster_parity` → passes, asserting every agent definition under `plugins/team-execution/agents/` has a manifest entry and no entry contains agent-team-specific choreography fields.
- [ ] AC2. The renderer compiles a fixture plan into a valid phased workflow script. Check: `uv run pytest tests/test_workflow_renderer.py -k renders_fixture_plan` → passes, asserting the emitted script contains manifest-sourced `agentType` references, per-call model/effort from the plan tier table, a bounded review-round loop, a budget guard, and gate-boundary phase splits.
- [ ] AC3. Data-dependent mid-unit gates fail loud at render time. Check: `uv run pytest tests/test_workflow_renderer.py -k midunit_gate_refused` → passes, asserting the renderer raises (with the chooser's agent-team recommendation in the error) rather than emitting a script that would skip the gate.
- [ ] AC4. Backend parity on a fixture plan. Check: `uv run pytest tests/test_backend_substrate_parity.py -k same_roster_same_evidence` → passes, asserting both backends trigger the identical manifest roster and emit shape-identical evidence envelopes for the same fixture plan.
- [ ] AC5. Degrade receipts carry substrate deltas; guarantee-shedding degrades HALT. Check: `uv run pytest tests/test_degrade_substrate_receipt.py` → passes for both the delta-recorded degrade and the HALT-on-shed-guarantee case.
- [ ] AC6. The chooser rubric contains no provisioned-property criteria. Check: `uv run pytest tests/test_backend_chooser_lint.py -k inherent_only` → passes, failing red if the rubric doc names reviewer availability, ceremony presence, or any other portable-content property as a decision criterion.
- [ ] AC7. Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.
## Definition of Done

The review/ceremony substrate is declared once in a machine-readable manifest that both backends
consume; a versioned renderer compiles plan + manifest into standard phased workflows with the
panel, bounded fix rounds, budget guard, and ceremony included; backend choice is made by a
documented inherent-property rubric that structurally cannot cite portable content; the degrade
ladder records substrate deltas and HALTs rather than silently shedding guarantees; and a fixture
plan run through both backends produces the same roster coverage and evidence shape. AC1–AC7 pass.

### Out-of-scope / non-goals
- **Not a backend-flip campaign.** Re-annotating the 38 existing plugin-fleet drafts whose executor
  profile names team-execution is follow-on work after the chooser lands; this issue ships the
  rubric, not the re-triage.
- **Not mid-workflow interactivity.** Workflow non-interactivity is inherent; this issue designs
  around it (gates at phase boundaries, fail-loud on mid-unit gates), it does not attempt to build
  operator input into a running workflow.
- **Not a replacement for team-execution.** Both backends remain first-class; negotiation-dense
  work keeps a real home. The deliverable is symmetry of substrate, not deprecation of a mechanism.
- **Not a consensus redesign.** The numeric consensus contract and verdict envelope are
  `pf-consensus-kernel`'s deliverables; this issue consumes them.
- **Not effort plumbing.** Per-teammate effort on agent teams is `pf-effort-first-class`; this
  issue only documents and rubric-encodes the asymmetry until then.
- **No new plugin** unless `pf-fleet-commons-decision` concludes otherwise; siting defers to that
  exploration (R6).

## Dependencies / Assumptions

- Depends on `pf-consensus-kernel` (verdict envelope + invocation contract — evidence-shape source
  for R7) and coordinates with `pf-reviewer-lens-registry` (its shared lens registry and this
  manifest must be one registry effort, not two — resolve at `/plan` time).
- Depends on `pf-fleet-commons-decision` for final siting (R6); does not block on it for the
  default siting.
- Interacts with `pf-outcome-backend-spend-envelope` (run-start posture capture): the chooser's
  decision becomes part of the captured envelope rather than a per-leaf re-derivation.
- Assumes the harness continues to resolve workflow `agentType` from the same registry as the
  Agent tool (verified precedent: `plugins/saga/scripts/execution_spec.py:88-93,904` emits
  `agentType: "saga:readonly-verifier"` into workflow `agent()` calls today).
- Assumes `plugins/saga/scripts/outcome_dispatcher.py:47-55` remains the backend-menu/degrade seam
  this issue extends (`ALWAYS_AVAILABLE`, `HOST_DEPENDENT`, `DEGRADE_LADDER`).
- Kinship, not absorption: seed `S-29` ("same consensus protocol from team-execution usable in
  dynamic workflows", absorbed by `pf-consensus-kernel`) is the consensus-scoped seed of this
  generalization; the partition contract keeps each idea id placed exactly once, so this issue
  cites it here without re-absorbing it.

### Files expected to change

Indicative only; exact set is `/plan`'s to determine.

- New: substrate manifest module + schema doc (siting per R6; default beside the
  `consensus_spec.py` precedent).
- New: workflow renderer script + rendered-script golden fixtures.
- New: backend-chooser rubric reference doc (consumed by saga `/plan` and `/outcome`).
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`,
  `validator-registry.md` — render from / drift-guard against the manifest.
- `plugins/saga/scripts/outcome_dispatcher.py` — substrate-delta receipts, HALT-on-shed-guarantee.
- `plugins/saga/skills/plan/SKILL.md` — backend recommendation consumes the chooser rubric.
- `tests/test_substrate_manifest.py`, `tests/test_workflow_renderer.py`,
  `tests/test_backend_substrate_parity.py`, `tests/test_degrade_substrate_receipt.py`,
  `tests/test_backend_chooser_lint.py` — new tests (repo-root collected).

### Tests to add or update

- Roster parity: every `plugins/team-execution/agents/*.md` has a manifest entry; no choreography
  leakage into entries.
- Renderer golden test: fixture plan → phased script with manifest `agentType`s, bounded rounds,
  budget guard, gate-boundary splits; mid-unit-gate plan → loud refusal.
- Backend parity: same fixture plan through both backends → same triggered roster, shape-identical
  evidence envelopes.
- Degrade receipts: substrate delta recorded; guarantee-shedding degrade HALTs.
- Chooser lint: rubric doc red on any provisioned-property criterion.

## Release-surface checklist

This capability changes plugin behavior and schema in both `team-execution` (registries render
from the manifest) and `saga` (dispatcher receipts, `/plan` chooser). Update in the same PR:

- `plugins/team-execution/.claude-plugin/plugin.json` — version bump.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version/metadata sync for both entries.
- `plugins/team-execution/CHANGELOG.md` and `plugins/saga/CHANGELOG.md` — entries describing the
  substrate manifest, workflow renderer, backend chooser, and rigor-preserving degrade receipts.
- Version/metadata drift-guard tests in `tests/` — run and confirm green before PR-ready.

### Verification

```bash
# New substrate tests
uv run pytest tests/test_substrate_manifest.py tests/test_workflow_renderer.py \
  tests/test_backend_substrate_parity.py tests/test_degrade_substrate_receipt.py \
  tests/test_backend_chooser_lint.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green.

## Grounding References

- **OP-gateE-1** (primary) — basis (direct, operator): Gate E review dialogue, 2026-07-04 —
  operator direction that reviewers/scanners/ceremony are provisioned content, not mechanism
  properties; that a substrate plugin should render them onto either mechanism; and that backend
  choice must rest on inherent differences only. Recorded as a Gate E amendment in
  `docs/plans/2026-07-04-plugin-fleet-issue-plan.md` (amendment log). Generalizes seed `S-29`
  (absorbed by `pf-consensus-kernel`).
- Harness/in-repo precedent — basis (direct): `plugins/saga/scripts/execution_spec.py:88-93,904`
  emits `agentType: "saga:readonly-verifier"` (with per-call model/effort) into workflow `agent()`
  calls: a review-class agent already runs on the workflow mechanism today.
- Backend menu seam — basis (direct): `plugins/saga/scripts/outcome_dispatcher.py:47-55,294-295`
  (`ALWAYS_AVAILABLE`, `HOST_DEPENDENT`, `DEGRADE_LADDER`, one-rung degrade) — substitutability is
  already asserted at the dispatch seam; substrate constancy is not.
- Substrate inventory — basis (direct): 25 agent definitions under `plugins/team-execution/agents/`
  plus `reviewer-registry.md`/`validator-registry.md` as the currently mechanism-coupled rosters.
- Effort asymmetry — basis (direct): zero effort threading in `plugins/team-execution/` (grep
  verified 2026-07-04); Workflow `agent()` accepts per-call `effort`; agent-definition frontmatter
  is the only agent-team effort locus until `pf-effort-first-class`.
- Robustness evidence — basis (reasoned, from this program's runs): ideation/repair phases ran as
  workflows (121 agents, 0 errors, journal-replay recovery) while the session's failures were
  model-driven coordination (dropped safeguard on relaunch; idle teammate) — compiled coordination
  cannot drop its own safeguards mid-run.

## Recommended executor profile

- **Model:** Opus
- **Effort:** high — *target posture: on the team-execution backend, per-teammate effort is not a
  live dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until
  then.*
- **Backend:** team-execution
- **External LLM posture:** none
- **Justification:** By this issue's own chooser rubric, the work is negotiation-dense — the
  manifest schema, renderer phase-split semantics, and chooser criteria will be renegotiated by
  what extraction discovers, and the design touches a governance seam (degrade HALT semantics)
  where persistent reviewer dialogue earns its cost. Opus (not Sonnet): contract design and rubric
  authoring are judgment work, not mechanical extraction. The follow-on backend-flip re-triage of
  existing drafts is mechanical and belongs at cheap tier once the rubric exists.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan pf-execution-substrate-decoupling` to create an implementation plan (first resolving the
registry-unification question with `pf-reviewer-lens-registry`).

### Source context

- Source: Gate E review dialogue (operator direction, 2026-07-04), recorded as an amendment in
  `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Source type: operator (Gate E amendment; id `OP-gateE-1` registered in
  `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map-final.json`)
- Source title: Execution-substrate decoupling — one review/ceremony contract, two coordination
  mechanisms, inherent-property backend choice

### Intent

The fleet has two execution mechanisms — agent teams (Agent tool + addressable teammates) and dynamic workflows (Workflow tool + compiled orchestration script) — but only one of them carries the review substrate. team-execution owns 25 agent definitions (reviewers, scanners, testers, monitors in `plugins/team-execution/agents/`), the consensus choreography, and the ship ceremony, for the historical reason that agent teams existed before the Workflow tool. The consequence is a category error at every backend decision: executors are chosen for *provisioned* properties ("team-execution has reviewers") instead of *inherent* ones (compiled vs interpreted coordination), and saga's own `DEGRADE_LADDER = ("cc-workflows-ultracode", "team-execution", "inline")` (`plugins/saga/scripts/outcome_dispatcher.py:55`) is quietly incoherent — degrading a rung changes not just coordination but the review rigor the run receives.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/415
- Number: 415
- Created at: 2026-07-04T08:06:00.286118+00:00

