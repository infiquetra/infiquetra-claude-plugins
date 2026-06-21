---
date: 2026-06-20
topic: saga-tiering-and-execution-campaign
maturity: requirements-ready
source: docs/ideation/2026-06-20-net-new-skills-agents-ideation.md (survivors #1-#8) + docs/ideation/2026-06-20-execution-backend-representation-ideation.md (survivors S1-S7)
---

# Saga Tiering & Execution-Mechanism Campaign

## Summary

Make saga put the right work on the right execution mechanism — decided where the work is defined,
enforced in code or a hook, not in the expensive main context or in human memory. This unifies two
2026-06-20 ideation runs (net-new offload/tiering/hooks + dynamic-workflow representation/authoring)
into one campaign, planned and built **epic-by-epic**, with tiering as the shared spine.

## Problem Frame

Two independent ideation efforts converged on the same root waste. The first found that the
highest-value offloads are deterministic and cheap — yet the repo runs every subagent on the Opus main
model (35 agent files were `model: inherit`; ~10 still are), has **zero hooks**, and re-pays expensive
tokens for binary answers a hook could settle for free. The second found that saga *undersells and
structurally avoids* its cheapest powerful backend: the `/plan` offer pitches dynamic (ultracode)
workflows as fan-out only, and the recommender hard-forces team-execution on any consensus signal — so
a workflow judge-panel is never recommended even though the Workflow tool documents judge panels as
first-class.

The seam between them is **tiering**: doc1's "pin the model where agents are dispatched" and doc2's
"assign a per-unit `{model, effort}` where plan work is defined" are the same decision on two dispatch
surfaces. Left unbuilt, every downstream choice — which backend, which model, which verification —
keeps defaulting to the most expensive option by omission. The cost is paid every session, silently.

## Key Decisions

These framing choices were settled in the brainstorm and constrain the requirements below.

**KD1 — Tiering is the spine, built first.** It is the one genuine cross-doc overlap (doc1 #4 ↔ doc2
S5), and landing it unblocks correct-tier defaults for the authoring and executor epics. One rule, two
dispatch surfaces.

**KD2 — Representation precedes authoring.** Do not build a workflow-authoring bridge before the
recommender can route to it (S2) and the offer surfaces it (S1); otherwise the bridge is dead wiring.

**KD3 — Decouple, do not rename.** The enum string is a stored contract carried in persisted sagas.
Show "dynamic workflows" through a display-label map and freeze the wire value — the contract already
declares prose labels ≠ the stored contract.

**KD4 — One spec, two emitters.** team-execution and dynamic-workflows are not two authoring problems;
they are one authored execution-spec with two emitters. The governance difference (a standing, recorded,
deploy-blocking verdict vs throwaway confidence) is *which emitter runs*, not the authoring.

**KD5 — "Lean into workflows" is enable + measure + keep-safe, not a blunt default-flip.** It is
realized as making the recommender *able* to pick a workflow for consensus (R7), measuring the real
override-rate before re-weighting any default (R12), and keeping a workflow choice safe to resume
off-host (R11). A raw default-flip collides with the governance boundary and the capability gate.

**KD6 — This is a campaign frame, planned epic-by-epic.** `/plan` consumes one epic at a time. Epic 3
(hooks) is independent of the saga-execution epics and can start in parallel from day one.

## Requirements

Grouped by epic in build order. R-IDs are continuous across groups.

**Epic 0 — Tiering spine** *(the cross-doc seam; lands first)*

R1. A single tier-assignment rule governs every model/effort choice in saga: judgment clauses → Opus;
mechanical/deterministic clauses (census, link checks, file-existence, enumeration) → Sonnet or Haiku;
read-only sampling/survey → Sonnet.

R2. The rule is enforced at **both** dispatch surfaces: (a) saga plugin agent frontmatter pins `model:`
and the dispatching skills pass a per-call model for the still-unpinned survivor agents and their
dispatch sites; (b) a `/plan`-authored workflow spec carries an explicit per-unit `{model, effort}`
annotation.

R3. A workflow spec enforces the pilot↔fan-out same-tier invariant: a pilot agent and the fan-out it
gates run at the same tier, asserted at authoring time — a mis-tiered pilot is an invalid oracle.

R4. The tier rule is recorded once as prose where it is auto-loaded every session (the global
`~/.claude/CLAUDE.md`), not in `DECISIONS.md` (which is not auto-loaded and would go unread).

**Epic 1 — Execution-backend representation** *(cheap, high-certainty; precedes Epic 2)*

R5. The `/plan` execution-backend offer names dynamic workflows' **both** purposes — breadth/scale
fan-out AND adversarial confidence (judge-panel / refute-N / perspective-diverse verification) — not
fan-out alone.

R6. The offer frames the team-execution↔workflow choice on the **governance** axis ("does the verdict
need to stick — block a merge/deploy and persist as evidence — or is it throwaway?"), not on "review
depth," which both backends have.

R7. The recommender distinguishes **gated consensus** (must block a merge/deploy and persist → team-execution)
from **advisory consensus** (N independent votes acted on in-session → eligible for a dynamic-workflow
judge-panel), and stops hard-forcing team-execution on every consensus signal.

R8. The operator-facing label for the dynamic-workflows backend is "dynamic workflows" via a display-label
map consumed by every offer surface; the stored enum value is unchanged (frozen wire contract).

**Epic 2 — Dynamic-workflow authoring** *(the big build; depends on Epics 0-1)*

R9. `/plan` can author one structured execution-spec (units, per-unit tiers, return contracts, dependency
barriers, escalations) and emit from it **either** a runnable Claude Code workflow script **or** the
team-execution markdown protocol; saga records a pointer to the artifact and never vendors backend
machinery.

R10. Every fan-out unit in an authored workflow declares an **enumerated** target list with post-run
reconciliation (each named target produced an output or surfaced an error) — never a silent filter.

R11. An authored workflow is capability-portable: every plan carries a runnable inline/serial baseline,
the dynamic-workflow layer applies on a capable host, and on off-host resume the choice is re-checked, a
one-line downgrade is surfaced, and only the orchestration tier recompiles down (unit specs and tiers
preserved).

R12. Backend choice-vs-recommendation is recorded, and a `/retro` or `/optimize` pass surfaces the
override-rate (plus over/under-tier and budget-exhaustion signals) so any future default re-weighting is
evidence-driven, not asserted.

**Epic 3 — Hook harness** *(independent; the repo's first hooks; can run in parallel)*

R13. A deterministic hook validates `.claude-plugin/marketplace.json` / `plugin.json` on edit (JSON parse
plus a bracket-count assertion) and blocks on failure with the offending line, making the recurring
double-`]` corruption unrepresentable.

R14. A hook nudges (does not write) when a `feat`/`fix` commit touches code but stages no
`docs/engineering-journal/` entry, per the same-commit journal mandate, and ships so it can fire
cross-repo.

R15. A hook runs the repo's pre-push gate from a single-source gate manifest and reports by exception
before push.

**Epic 4 — Cheap executor + release guards** *(lowest-priority tail)*

R16. Exactly one cheap-tier executor agent (haiku, Bash-only), dispatched by saga commands and inert
until called, handles mechanical op-discriminated work (the mechanical-handoff substrate).

R17. A guard keeps the plugin release triad in sync (`plugin.json` version ↔ `.claude-plugin/marketplace.json`
↔ `CHANGELOG.md`) on a version-bearing change.

R18. A SHA-stamp stager and a stale-main-after-squash guard, both scoped to this marketplace repo, close
the remaining this-repo-local release rituals.

## Key Flows

F1. **The execution-backend offer-and-author path (Epics 1-2 happy path).**
**Trigger:** `/plan` reaches the execution-backend offer for a settled plan.
1. The recommender reads the work shape and classifies any consensus need as gated or advisory (R7).
2. The offer surfaces the backends with both workflow purposes named and the governance fork framed
   (R5, R6), pre-selecting the cheapest-correct, and shows "dynamic workflows" as the label (R8).
3. On a dynamic-workflows pick, `/plan` authors the tiered execution-spec and emits a runnable workflow
   script with enumerated fan-out targets (R9, R10, R2, R3); saga records the pointer.
4. The choice and the recommendation are recorded for later override-rate analysis (R12).

F2. **Off-host resume degradation (R11).**
**Trigger:** a saga carrying a dynamic-workflows pointer is resumed on a host without the Workflow tool.
1. Capability is re-checked at resume (not only at the original offer).
2. A one-line downgrade is surfaced; the orchestration tier recompiles down to team-execution or inline.
3. Unit specs and per-unit tiers are preserved; the downgrade is recorded.

## Acceptance Examples

AE1. **Covers R7.** When work wants consensus but does NOT need to block a merge/deploy or persist a
verdict → the recommender offers a dynamic-workflow judge-panel (advisory), not team-execution.

AE2. **Covers R7.** When work wants consensus AND must block a deploy or be recorded as evidence → the
recommender routes to team-execution (gated).

AE3. **Covers R11.** When a dynamic-workflows saga is resumed on a host lacking the Workflow tool → a
one-line downgrade is surfaced and the orchestration recompiles to team-execution/inline with unit tiers
preserved; it never errors out or silently runs nothing.

AE4. **Covers R10.** When an authored fan-out unit's named target produces no output → reconciliation
surfaces it as an error, not a silent skip (the failure mode the context-fleet-audit run actually hit).

AE5. **Covers R13.** When an edit leaves `marketplace.json` unparseable or with unbalanced brackets → the
hook blocks the edit and names the offending line.

## Scope Boundaries

In scope: all 15 ideation survivors, organized as the five epics above, plus the tiering-seam resolution
that unifies them.

Out of scope:
- HOW-level design — the hook JSON, the workflow-generator internals, the recommender's gated/advisory
  signal-acquisition mechanism, return schemas, and file layouts — all belong to `/plan`.
- The revivable cuts (doc2 R1-R7; doc1's R-items) unless explicitly revived.
- Work already shipped: the 17→7 portfolio cut and the marketplace-lister relocate.
- Cross-host **routing** (doc2 R6 — shipping a workflow to a capable host); only the degradation path
  (R11) is in scope.
- Redesigning the enum into a continuous spectrum or a two-axis vocabulary (doc2 R2/R3 cuts).

## Dependencies / Assumptions

- **Sequencing dependencies:** Epic 0 (tiering) precedes Epic 2 (R9 authoring) and Epic 4 (R16 executor)
  — both need the tier rule to exist. Epic 1 (representation) precedes Epic 2 (don't author what nothing
  routes to). Epic 3 (hooks) is independent and parallelizable.
- **Capability gate:** dynamic workflows run on Claude Code only; this constrains R5 (omit the option
  off-host) and is the reason R11 (degradation) exists.
- **Verified facts:** the repo has zero hooks today, so Epic 3 is greenfield; ~25 of 35 agent files are
  already model-pinned, so Epic 0's enforcement is a small tail (the unpinned survivor agents + the
  per-call arg + the rule), not a from-scratch build; the `cc-workflows-ultracode` enum string is carried
  in persisted sagas, which is why R8 freezes it; `langfuse` ships user-enabled hooks cross-repo, the
  existence proof for R14's distribution.
- **Assumption:** the Workflow tool's per-agent `model`/`effort` overrides and `budget` API are stable —
  R3, R9, and R12 depend on them.

## Success Criteria

- **Epic 0:** no saga-dispatched subagent runs on a richer tier than its work warrants, and the tier rule
  is visible to every session (loaded, not buried).
- **Epic 1:** an operator reading the offer can tell that consensus-via-workflows is available without
  opening the contract doc; a drift-guard test fails if a future rebuild drops a stated workflow purpose.
- **Epic 2:** a dynamic-workflows pick yields a runnable, correctly-tiered workflow artifact with no
  silent-skip path; an off-host resume degrades with a recorded note rather than erroring.
- **Epic 3:** the double-`]` corruption cannot reach a commit; a code-only `feat`/`fix` with no journal
  entry is nudged.
- **Epic 4:** mechanical handoff work runs on haiku rather than Opus; the plugin release triad cannot
  drift silently.

## Outstanding Questions

None block writing or planning the campaign frame. Deferred to `/plan` (per-epic):

- R7 — does the recommender learn the gated-vs-advisory distinction from a new `/plan` interrogation
  question, or infer it from work-shape signals? (The crux of S2's feasibility.)
- R8 — should the "dynamic workflows" display label encode "Claude-Code-only" so the capability gate is
  legible from the label itself?
- R9 — does the authored execution-spec live inside the plan doc or as a sibling artifact the saga points
  at?
- R15 — what is the single-source format for the pre-push gate manifest?
- Sequencing — Epic 0 and Epic 3 are both cheap and independent; either can be the literal first move.

## Sources / Research

- Ideation: `docs/ideation/2026-06-20-net-new-skills-agents-ideation.md` (#1-#8) and
  `docs/ideation/2026-06-20-execution-backend-representation-ideation.md` (S1-S7).
- Grounding (`file:line`): `plugins/saga/skills/plan/SKILL.md:253` (the offer under-sell);
  `plugins/saga/references/operator-choice.md:101-104` (dual purpose), `:105-110` (governance boundary),
  `§1` (labels ≠ contract), `§6` (every writer records the mode); `plugins/saga/scripts/lifecycle_state.py:158`
  (the `or needs_consensus` hard-force); `plugins/saga/scripts/saga.py:71` (the stored enum);
  `plugins/team-execution/skills/team-execution/SKILL.md:234` (the markdown `## Team Structure` artifact).
- The plan→script reference pattern: `infiquetra-context-library/scripts/context-fleet-audit.workflow.js`
  authored from `infiquetra-context-library/docs/plans/2026-06-20-context-fleet-audit-plan.md` (EC
  contracts → agent preamble; phases → `phase()`; units → `agent()`; the Opus/Sonnet/Haiku tiering rule;
  the pilot↔fan-out invariant; the silent-skip lesson behind R10).
- Journal: `DECISIONS.md` `#operator-choice-framework` and `LEARNINGS.md` 2026-06-13 (the team↔workflow
  line is governance, not review depth); the `workflow_structuredoutput_budget` learning (cap output,
  mandatory emit, skim, batch — binds R9's generated cheap-tier agents).
