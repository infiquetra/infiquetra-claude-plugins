---
title: "enhancement: non-scoring external-engine advisory seat in the team-execution consensus panel"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Stand up the external-engine offload lane"
---

# enhancement: non-scoring external-engine advisory seat in the team-execution consensus panel

### Objective
Stand up the external-engine offload lane

### Tier
structural

### Wave
wave-1

### Intent
Add a non-scoring **advisory reviewer seat** to the team-execution consensus panel
(`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`) that an
external engine (agy/codex) can occupy, dispatched through the existing chaperone-dispatch
contract, and automatically generate a **Claude-vs-external convergence diff** attached to the
verdict. The external seat's synthesis is read and reported, but by construction can never move
the panel's `>= 9.0` acceptance gate or the `< 7.0` blocking-stop rule — it is advisory only, the
same posture the fleet already committed to for every other external-engine touchpoint.

This closes two related but previously separate ideas surfaced independently during the
2026-07-03 plugin-fleet ideation pass (theme T5, "consensus-protocol portability," frame F2 and
F4, axis "membership-diversity"):

- Add the external-advisory reviewer slot itself (a roster/dispatch concern).
- Automate the convergence diff between the Claude panel and the external synthesis (a
  reporting/reconciliation concern people were previously doing by hand).

They are one deliverable because the diff has nothing to reconcile without the seat existing,
and the seat is pointless without an automated readout of where it agreed/disagreed with Claude —
building either alone leaves the other as unfinished, manual follow-up work.

### Problem Frame

**Today, the consensus panel has no seat for an external engine at all.**
`plugins/team-execution/skills/team-execution/references/reviewer-registry.md:9-18` defines only
Claude-agent reviewers (base: `devils-advocate-reviewer`, `security-reviewer`,
`architecture-reviewer`; optional: `infra-reviewer`, `api-reviewer`, `testing-reviewer`,
`code-quality-reviewer`, `privacy-reviewer`, `clarity-reviewer`, `ai-usefulness-reviewer`) — every
row is a Claude subagent, and `consensus-protocol.md:26-58` (Step B3a-B3d) spawns and scores only
that roster. There is no row, no dispatch path, and no scoring exclusion for an external
participant.

**Meanwhile the fleet already has the wiring this seat would reuse, but nothing plugs it into the
panel.** `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
defines the chaperone-dispatch protocol (a resident Claude worker owns resolve → dispatch →
verify → apply → test → manifest for an external engine, §1-§5) and is explicit that "an external
engine never joins wave scheduling, the residency protocol, or git directly" and "there is no
separate 'external worker' executor" (`external-engine-workers.md:8-13`). That contract is scoped
to **worker** units (`role_kind="worker"`, `external-engine-workers.md:44-56`) — it says nothing
about a **reviewer** role, and the consensus panel is reviewer-only territory. The two documents
simply never intersect today.

**And "evaluate external output against Claude's own review" is currently a manual, undocumented
step.** The grounding brief's binding-decision register records the operator's stated posture
verbatim: external-LLM output gets "evaluated [and] incorporated based on analysis [against the]
main LLM" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:54-56`) — i.e. a human/Claude
hand-reconciliation already happens informally whenever an external synthesis is in the loop. The
grounding brief's session-mining synthesis independently surfaces "15/17, hand-reconciled" as
existing prior art for a convergence-style comparison
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:145-146`, theme roster item 5 "Consensus-
protocol portability (gated-vs-advisory split preserved; 15/17 convergence prior art)",
`:164-165`). This enhancement is the machinery that makes that existing informal practice
automatic and auditable instead of ad hoc.

**This must not become a second gate.** Two binding decisions constrain the whole design and are
non-negotiable:

- `{#external-engines-never-gatekeepers}` (#283): "Claude is verifier-of-record [for] every gated
  decision; codex/agy = generator / advisory-reviewer / non-gated worker only. Structurally
  enforced." (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:45`)
- `{#external-engine-chaperone-dispatch}` (#318): "External engines in teams = chaperone dispatch
  (offload→sonnet/medium, second-opinion→opus/high), never second executor kind / residency / git
  participant." (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:46`)

The fleet already enforces the never-gatekeeper posture at the worker layer:
`engine_dispatch.satisfy_gate()` (`plugins/saga/scripts/engine_dispatch.py:238-258`) hard-requires
`evidence.verified_by_claude is True` before advisory evidence counts toward any verdict
(`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:17-23`). The
consensus panel's scoring math (`consensus-protocol.md:39-49`, "Pass threshold... average of
applicable dimensions") has an existing structural precedent for *excluding* a participant from
the denominator without treating the exclusion as failure — the "Non-applicable dimensions"
mechanism (R7/R8/R9, `consensus-protocol.md:82-108`), currently scoped to
`architecture-reviewer`'s precondition-bearing dimension. This enhancement extends that same
exclusion mechanism to a new, permanent case: an external-engine seat whose dimension(s) are
*always* excluded from the `>= 9.0` and `< 7.0` math, not just when a repo-state precondition is
absent.

### Key Decisions

- **Advisory-only by construction, not by convention.** The external seat's score never enters
  the acceptance-threshold arithmetic — it is typed and excluded the same way an
  `architecture-reviewer` non-applicable dimension is excluded today (`consensus-protocol.md:82-
  108`), generalized from "excluded when precondition absent" to "excluded always, this
  participant is advisory."
- **Dispatch reuses the existing chaperone contract, not a new executor.** The external seat is
  populated via the same chaperone pattern `external-engine-workers.md` already documents for
  workers — resolve → dispatch → verify, with `evidence.verified_by_claude` set before any output
  is attached to the panel's report. No second executor kind, no residency, no git participation
  (per #318).
- **Convergence diff is generated automatically, not hand-reconciled.** The diff enumerates
  converged and diverged findings between the Claude panel's consensus and the external seat's
  synthesis, attached to the verdict artifact — replacing today's ad hoc "evaluated [and]
  incorporated based on analysis" practice with a checkable artifact.
- **Absence is not failure.** If the external engine is unavailable, fails preflight, or halts
  (the same fallback/halt ladder `external-engine-workers.md` §2 already defines for workers), the
  panel proceeds exactly as it does today with the Claude-only roster — the advisory seat is
  additive, never a dependency.

### Out-of-scope / non-goals
- Making the external seat's score count toward `>= 9.0` acceptance or `< 7.0` blocking-stop in
  any way, under any configuration — this is structurally excluded, not a toggle.
- Adding a second non-Claude executor kind, giving the external engine residency, wave-scheduling
  participation, or direct git/write access in the panel context — the chaperone owns dispatch and
  the working tree exactly as `external-engine-workers.md` already specifies for workers.
- Changing the base/optional Claude reviewer roster in `reviewer-registry.md` — this adds one new
  advisory row/category, it does not alter existing reviewer selection logic.
- A standing catch-rate or divergence-rate dashboard — the convergence diff is generated per-run
  and attached to that run's verdict; no scheduled measurement harness.
- Reworking the 3-cycle re-review cap (`consensus-protocol.md:17`) or the escalation rules
  (`consensus-protocol.md:230-240`) — those apply to the Claude panel only and are unchanged.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` — register the
  external-advisory seat (dispatch selector, never a base/optional Claude reviewer row).
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — extend the
  Non-applicable-dimensions exclusion mechanism (R7/R8/R9, `:82-108`) to the new always-excluded
  external-seat case; add the convergence-diff generation step to Step B3c/B3d's score-collection
  flow.
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` — extend or
  cross-reference the chaperone-dispatch contract for a `role_kind="reviewer"` seat (today scoped
  to `role_kind="worker"`, `:44-56`).
- `plugins/saga/scripts/engine_dispatch.py` — confirm/extend `satisfy_gate()` (`:238-258`) so an
  advisory-reviewer evidence record is structurally ineligible to satisfy any gate, mirroring the
  existing worker-evidence guard.
- `tests/test_engine_dispatch.py` (or equivalent) — new tests asserting the external seat cannot
  move the gate.
- `plugins/team-execution/CHANGELOG.md`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface updates (see checklist below).

### Tests to add or update
- The external-advisory seat's verdict/score is excluded from the panel's `>= 9.0` average and
  from the `< 7.0` blocking-stop check under every combination of Claude-panel scores (including
  when the external seat itself reports a failing or divergent score).
- A convergence-diff artifact is generated whenever the external seat participates, enumerating at
  least one converged and one diverged finding in a synthetic fixture.
- When the external engine is absent, fails preflight, or halts (reusing the existing fallback/
  halt paths in `external-engine-workers.md` §2), the panel reaches consensus exactly as it would
  with no advisory seat configured — no new failure mode is introduced by the seat's absence.
- `engine_dispatch.satisfy_gate()` (or its reviewer-role extension) rejects an unverified
  (`verified_by_claude is False`) advisory-reviewer evidence record from satisfying any gate, the
  same way it already rejects unverified worker evidence.

### Verification
```bash
uv run pytest tests/test_engine_dispatch.py -v
uv run pytest tests/ -k "consensus or reviewer_registry or convergence" -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```
Expected: all green; the gate-exclusion and convergence-diff tests above pass explicitly; no
regression in the existing Non-applicable-dimensions (architecture-reviewer) test coverage.

### Acceptance criteria
- [ ] External-seat verdict influence on the panel's acceptance threshold is zero by construction
  — a synthetic test where the external seat reports a failing/divergent score still reaches
  consensus purely on the Claude panel's own scores. Check:
  `uv run pytest tests/test_consensus_protocol.py -k external_seat_excluded_from_gate` → passes.
- [ ] A convergence-diff artifact is generated automatically whenever the external seat
  participates, naming both converged and diverged findings. Check:
  `uv run pytest tests/test_consensus_protocol.py -k convergence_diff_generated` → passes.
- [ ] An absent, failed, or halted external engine leaves the panel's consensus flow unchanged
  from today's Claude-only behavior — advisory absence is never a panel failure. Check:
  `uv run pytest tests/test_consensus_protocol.py -k external_seat_absence_is_noop` → passes.
- [ ] `engine_dispatch.satisfy_gate()` (or its extension) refuses to let an unverified
  advisory-reviewer evidence record satisfy any gate. Check:
  `uv run pytest tests/test_engine_dispatch.py -k advisory_reviewer_never_gates` → passes.
- [ ] `reviewer-registry.md` documents the external-advisory seat as a distinct, clearly-labeled
  non-scoring category, not a row in the base/optional Claude reviewer tables. Check: manual
  doc-review confirms the new section is structurally separated from the base/optional tables.
- [ ] Release-surface artifacts (plugin.json, marketplace.json, CHANGELOG) are updated in the same
  PR as the behavior change. Check: `git diff --stat` shows all three touched alongside the
  `references/` changes.
- [ ] Full suite, format, lint, types, and security scan stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

## Definition of Done
The team-execution consensus panel accepts an external-engine advisory participant, dispatched
through the existing chaperone-dispatch contract (per #318), whose synthesis is automatically
diffed against the Claude reviewer panel into a convergence report attached to the run's verdict —
and that participant's score can never, under any code path, move the `>= 9.0`/`< 7.0` threshold
math. Merged artifact: updated `reviewer-registry.md` + `consensus-protocol.md` +
`external-engine-workers.md` (or a new cross-reference doc), plus the `engine_dispatch.py` gate
guard and its tests, plus updated release-surface files. Verification: the acceptance criteria's
test suite passes in CI, and a dogfooded run of team-execution on this very PR (with the external
seat configured) produces a convergence-diff artifact as its own acceptance evidence.

## Grounding References
- Absorbed idea `T5-F4-4` (primary) — "External-engine advisory reviewer slot in the consensus
  panel (non-scoring)" — basis type `external`; dod_sketch: "Merged: an advisory-reviewer registry
  entry + dispatch wiring reusing external-engine-workers.md, external findings routed to
  consolidation but excluded from the score denominator; test asserts an external verdict never
  moves the 9.0 gate." (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`, entry
  `T5-F4-4`)
- Absorbed idea `T5-F2-5` (facet) — "Automate the hand-reconciliation: an advisory
  convergence-diff between Claude and an external synthesis" — basis type `external`; dod_sketch:
  "Merged: a convergence-diff section in consensus-protocol.md + external-engine-workers.md
  computing a Claude-vs-external divergence table (external non-gating); test asserts external
  scores never alter the gating pass/fail." (`docs/plans/plugin-fleet-ideation-2026-07-03/
  survivors/T5.json`, entry `T5-F2-5`)
- Binding decision `{#external-engines-never-gatekeepers}` (#283) — Claude is verifier-of-record
  for every gated decision; codex/agy are generator/advisory-reviewer/non-gated worker only,
  structurally enforced (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:45`).
- Binding decision `{#external-engine-chaperone-dispatch}` (#318) — external engines in teams use
  chaperone dispatch only, never a second executor kind, residency, or git participant
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:46`).
- Operator alignment note — external-LLM posture is "evaluated [and] incorporated based on
  analysis [against the] main LLM," i.e. advisory-only
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:54-56`).
- Theme roster item 5, "Consensus-protocol portability (gated-vs-advisory split preserved; 15/17
  convergence prior art)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:164-165`),
  session-mining evidence for existing hand-reconciliation practice
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:145-146`).
- Existing exclusion-mechanism precedent this extends: `consensus-protocol.md`'s Non-applicable
  dimensions (R7/R8/R9), lines 82-108.
- Existing chaperone-dispatch contract this reuses: `external-engine-workers.md`, full document
  (worker-scoped resolve→dispatch→verify→apply→test→manifest protocol), especially the
  never-a-gatekeeper section (`:15-23`) and the resolve fallback/halt ladder (`:44-71`).
- Existing gate guard this extends: `engine_dispatch.satisfy_gate()`
  (`plugins/saga/scripts/engine_dispatch.py:238-258`).

## Executor Profile
- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** second-opinion
- **Justification:** The deliverable itself is second-opinion wiring — dogfooding the
  reconciliation on its own pull request (configuring the external advisory seat to review this
  very change and produce a convergence-diff artifact) is the natural, self-demonstrating
  acceptance evidence. High effort reflects the structural care needed to keep the exclusion
  mechanism airtight (never-gatekeeper is a hard fleet invariant, not a preference); sonnet is
  sufficient because the work extends existing, well-documented patterns
  (`consensus-protocol.md`'s exclusion mechanism, `external-engine-workers.md`'s chaperone
  contract) rather than inventing new architecture.

### Release-surface checklist
This issue changes plugin-user-facing behavior (a new reviewer-panel seat type and a new
generated artifact), so the following must land in the same PR:
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
  behavior.
- [ ] `.claude-plugin/marketplace.json` — entry updated to match the bumped version/description if
  applicable.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry describing the external-advisory seat and
  convergence-diff feature.
- [ ] Any version/metadata drift-guard tests (e.g. plugin.json/CHANGELOG consistency checks) —
  updated or confirmed passing against the bumped version.

### Context library links
- source_context: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json (entries
  `T5-F4-4`, `T5-F2-5`)
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json
- Source type: ideation-survivor
- Source title: Non-scoring external-engine advisory seat in the consensus panel, with automated
  Claude-vs-external convergence diff

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/382
- Number: 382
- Created at: 2026-07-04T07:55:48.854425+00:00

