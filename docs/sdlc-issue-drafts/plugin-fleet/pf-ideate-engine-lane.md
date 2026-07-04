---
title: "enhancement: blind external-engine divergent-generator lane in /ideate"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
type: enhancement
---

# enhancement: blind external-engine divergent-generator lane in /ideate

### Objective
Stand up the external-engine offload lane

### Summary
`/ideate`'s Phase 2 (Divergent ideation) dispatches only Claude frame agents today
(`plugins/saga/skills/ideate/SKILL.md:406-437`). This issue adds one additional lane in that same
phase — an external-engine frame agent (codex/agy, per the existing chaperone-dispatch model) that
generates its own candidate batch under the identical frame-agent prompt contract used by the Claude
frame agents. Its candidates merge into the same master pool (`SKILL.md:497-508`) tagged
`engine-generated`, are blind to the rest of the pool during generation exactly as every other frame
agent already is, and then pass through Phase 3 convergence (`references/convergence-and-partnership.md`)
under the identical basis and categorical-kill criteria as Claude-authored candidates — no separate
gate, no exemption, no privileged survival path.

### Problem Frame
`/ideate` is the one lifecycle stage in the fleet's ideation/divergent-generation surface that has no
external-engine lane at all today: `grep -n "codex\|agy\|external.engine" plugins/saga/skills/ideate/SKILL.md`
(run 2026-07-03) returns no hits in Phase 2. Every frame agent dispatched in Phase 2 is a Claude
sub-agent (`plugins/saga/skills/ideate/SKILL.md:410`, "Dispatch the N frame agents chosen in Phase 0.4
in parallel, on the inherited model (no tier-down)"), so the divergent phase's idea diversity is
bounded by one model family, even though the fleet's binding external-engine model already treats
external engines as legitimate non-gated generators/advisory-reviewers elsewhere in the lifecycle
(DECISIONS `{#external-engines-never-gatekeepers}` #283, `{#external-engine-chaperone-dispatch}` #318;
grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1, "Corrections intake §9(c)":
`ENGINE_INTENTS` is authored in `/plan` (`plugins/saga/skills/plan/SKILL.md:303-304`) and consumed in
team-execution's Step A7 worker table (`plugins/team-execution/skills/team-execution/SKILL.md:229-233`,
→ `references/external-engine-workers.md`) — but `/ideate`, `/brainstorm`, and `/work` are named in that
same brief entry as surfaces with no `ENGINE_INTENTS` wiring yet).

The risk this issue is specifically shaped to avoid: Phase 3 convergence's categorical-kill gate is the
mechanism that keeps `/ideate` honest (`references/convergence-and-partnership.md` — "An idea with no
articulated basis does NOT surface — cut it here," `direct:`/`external:`/`reasoned:` basis strength
ordering). An external-engine lane that entered the pool with its own review path, or that skipped the
basis requirement because it came from a different generator, would create exactly the privileged
"second executor kind" the chaperone-dispatch decision (#318) forbids, and would violate
never-gatekeepers (#283) by letting a non-Claude generator's output survive review on anything but
Claude's verification.

### Key Decisions
- **Additional lane, not a replacement frame.** The external-engine agent is dispatched alongside the
  existing N Claude frame agents chosen in Phase 0.4 (`SKILL.md:410`), not instead of one of them — Phase
  2's adaptive frame-count logic is unchanged; this adds one more parallel dispatch.
- **Identical frame-agent contract, engine-agnostic dispatch only.** The external-engine agent receives
  the same verbatim frame-agent prompt (frame, grounding summary, axis list, per-agent target, captured
  user seeds, tactical-scope flag — `SKILL.md:434-437`) as every Claude frame agent. Only the dispatch
  target differs (chaperone-dispatch `offload`/`sonnet-medium` per `{#external-engine-chaperone-dispatch}`
  #318) — no separate prompt variant, no relaxed target count.
- **Tagged, not privileged.** Every candidate the external-engine lane returns is tagged
  `engine-generated` at merge time (`SKILL.md:497`, "Merge and dedupe every frame agent's candidates into
  one master candidate list") purely for provenance/audit — the tag carries no effect on critique,
  ranking, or gate criteria in Phase 3.
- **Blind by construction, not by a new check.** The external-engine lane simply reuses Phase 2's existing
  isolation: frame agents are dispatched independently and never see each other's in-flight candidates
  (implicit in the parallel-dispatch structure at `SKILL.md:410` and the "merge after all frame agents
  return" boundary at `SKILL.md:495-497`). No new blinding mechanism is introduced; the requirement is
  that the existing isolation is preserved, not bypassed, for this new lane.
- **Convergence applies unmodified.** Phase 3's basis contract (`direct:`/`external:`/`reasoned:`,
  strength-ordered) and categorical-kill gate apply to `engine-generated` candidates exactly as written in
  `references/convergence-and-partnership.md` — this issue adds zero new gate logic, exemption paths, or
  basis-strength carve-outs for the tag.

### Actors
- A1. External-engine frame agent — new Phase 2 dispatch target (codex/agy via chaperone dispatch);
  generates a candidate batch under the identical frame-agent prompt.
- A2. Claude frame agents — the existing N dispatched agents (`SKILL.md:406-437`); unchanged.
- A3. Merge/dedupe step (`SKILL.md:497-508`) — combines all frame agents' output, including the new lane's,
  into one master pool with the `engine-generated` tag applied to the new lane's candidates.
- A4. Phase 3 convergence (`references/convergence-and-partnership.md`) — critiques the merged pool; must
  apply identically regardless of the `engine-generated` tag.
- A5. Operator — sees `engine-generated` provenance on relevant survivors in the final ideation artifact,
  with no separate section or privileged status.

### Requirements
R1. Phase 2 dispatches one additional external-engine frame agent (chaperone-dispatch `offload`/
`sonnet-medium` per DECISIONS #318) alongside the N Claude frame agents chosen in Phase 0.4, using the
identical verbatim frame-agent prompt contract (`SKILL.md:434-437`).

R2. The external-engine lane's candidates are invisible to every other Phase 2 frame agent during
generation (no shared in-flight state), consistent with the existing parallel-dispatch isolation already
governing all frame agents.

R3. At merge time (`SKILL.md:497`), every candidate produced by the external-engine lane is tagged
`engine-generated` in the master candidate list; every other candidate is untagged (or tagged with its
originating Claude frame) as today.

R4. Phase 3 convergence applies its existing basis contract and categorical-kill gate
(`references/convergence-and-partnership.md`) to `engine-generated` candidates with zero code-path
branching on the tag — no exemption, no relaxed basis-strength requirement, no separate survive/kill
threshold.

R5. If the external-engine dispatch fails or is unavailable (CLI missing, no credentials), `/ideate`
degrades to the existing Claude-only frame-agent set and proceeds — the external-engine lane is additive
and its absence must not block a run (consistent with `{#external-engines-never-gatekeepers}` #283:
external engines are never on a load-bearing gated path).

### Key Flows
F1. **Normal run with external-engine lane available.** Trigger: Phase 2 dispatch, external-engine CLI
reachable. The helper dispatches the external-engine frame agent alongside the N Claude frame agents, all
under the identical prompt contract, all blind to one another. After all return, candidates merge into one
pool; the external-engine lane's candidates carry `engine-generated`. Phase 3 critiques the whole pool
under one basis/kill standard. Covers R1, R2, R3, R4.

F2. **External-engine lane unavailable.** Trigger: Phase 2 dispatch, external-engine CLI/credentials
absent or the dispatch errors. `/ideate` proceeds with the existing Claude-only frame-agent set exactly as
it does today; no run is blocked and no error is surfaced as a hard failure. Covers R5.

### Acceptance Examples
AE1. **Covers R1.** A `/ideate` run with 4 adaptive Claude frames dispatches a 5th, external-engine frame
agent using the same substituted frame/grounding/axis/target/user-seed prompt template as the other four.

AE2. **Covers R2, R3.** After Phase 2 completes, the merged master candidate list contains candidates from
the external-engine lane tagged `engine-generated`, and no Claude frame agent's raw-candidate output
references or reacts to an external-engine candidate mid-generation.

AE3. **Covers R4.** An `engine-generated` candidate with a weak or absent basis is cut in Phase 3's
categorical-kill gate exactly as a Claude-authored candidate with the same weak basis would be — same
rejection reasoning, same survivor template fields, no separate "external engine" leniency path. A test
asserts the convergence code path applied to `engine-generated` candidates contains no tag-conditional
branch.

AE4. **Covers R5.** With the external-engine CLI unreachable, a `/ideate` run completes using only the
Claude frame-agent set, with no partial-failure state and no operator-facing error blocking the run.

### Out-of-scope / non-goals
- This issue adds exactly one new Phase 2 dispatch lane to `/ideate`. It does not add external-engine
  lanes to `/brainstorm`, `/work`, `/doc-review`, or `/code-review` — those are out of scope here (see the
  related `pf-engine-offer-helper` issue for the shared offer primitive across those other surfaces; this
  issue does not depend on or block that one).
- It does not change Phase 3 convergence's basis contract, kill criteria, or survivor template
  (`references/convergence-and-partnership.md`, `references/ideation-artifact.md`) — it verifies the
  existing mechanism is applied unmodified, it does not redesign it.
- It does not change Phase 0's adaptive frame-count logic (`SKILL.md:141-172`) beyond adding one
  additional, always-attempted external-engine dispatch alongside the existing N.
- It does not add a new dispatch mechanism for external engines — it reuses the existing chaperone-dispatch
  model (`{#external-engine-chaperone-dispatch}` #318, `offload`/`sonnet-medium`); no new executor kind,
  residency, or git-participant role is introduced.

### Dependencies / Assumptions
- Binding: DECISIONS `{#external-engines-never-gatekeepers}` (#283) — external engines are never
  verifier-of-record; this lane's output is subject to Claude-run Phase 3 convergence like every other
  candidate, and its unavailability must never block a run.
- Binding: DECISIONS `{#external-engine-chaperone-dispatch}` (#318) — external engines in the fleet are
  chaperone dispatch (`offload`→`sonnet/medium`) only, never a second executor kind or residency; this
  issue's dispatch target follows that model exactly.
- Reuses the existing Phase 2 dispatch structure and frame-agent prompt contract:
  `plugins/saga/skills/ideate/SKILL.md:406-437` (parallel dispatch, inherited model, verbatim prompt).
- Reuses the existing Phase 3 basis/kill gate: `plugins/saga/skills/ideate/references/convergence-and-partnership.md`
  (`direct:`/`external:`/`reasoned:` basis strength; "an idea with no articulated basis does NOT surface").
- Verified absent today: `grep -n "codex\|agy\|external.engine" plugins/saga/skills/ideate/SKILL.md`
  (run 2026-07-03) returns no hits — this is a net-new lane, not a refactor of an existing one.
- `ENGINE_INTENTS` producer/consumer pair exists today only for `/plan` (authoring,
  `plugins/saga/skills/plan/SKILL.md:303-304`) and team-execution (consuming, `plugins/team-execution/skills/team-execution/SKILL.md:229-233`,
  → `references/external-engine-workers.md`); grounding brief §1 names `/ideate` among the surfaces with no
  such wiring yet, which this issue closes for the divergent phase specifically.
- Grounding references (absorbed idea, from ideation Gate B): `T1-F1-2` — "Blind external-engine
  divergent-generator lane in /ideate" (theme T1, frame F1, axis `surface-points`, tier `structural`,
  verdict `survive`). This entry's `dod_sketch` is thin (no full brainstorm body); the requirements,
  flows, and acceptance examples above reconstruct its intent from that `dod_sketch` — "Merged PR:
  `/ideate` divergent phase gains an engine-generator lane; verified by a run yielding engine-authored
  candidates tagged `engine-generated` that pass convergence unprivileged (test asserts no gate/basis
  exemption)" — combined with the binding external-engine decisions and the existing Phase 2/Phase 3
  mechanics documented above.

## Definition of Done
- `/ideate`'s divergent phase produces `engine-generated` candidates in a normal run when the external
  engine is reachable, with zero change in Phase 3's per-candidate basis/kill behavior.
- A test explicitly proves the absence of any tag-conditional branch or exemption in the convergence gate
  applied to `engine-generated` candidates.
- Unavailability of the external-engine lane degrades to today's Claude-only behavior with no blocked run.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/skills/ideate/SKILL.md` — Phase 2 dispatch section (add the external-engine lane,
  documented degrade-on-unavailable behavior).
- `plugins/saga/skills/ideate/references/convergence-and-partnership.md` — note (not new logic) confirming
  the basis/kill gate applies unmodified to `engine-generated` candidates.
- `plugins/saga/skills/ideate/references/ideation-artifact.md` — survivor template: add `engine-generated`
  as a valid provenance tag value alongside existing frame-provenance tagging.
- `tests/test_ideate_engine_lane.py` — new tests (dispatch, blind isolation, tag application, no-exemption
  convergence, graceful degrade).
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — plugin metadata sync.
- `plugins/saga/CHANGELOG.md` — entry for the new lane.

### Tests to add or update
- Dispatch: Phase 2 dispatches the external-engine frame agent alongside the N Claude frame agents with
  the identical substituted prompt contract.
- Isolation: the external-engine lane's in-flight candidates are not visible to any Claude frame agent
  during generation (and vice versa).
- Tagging: merged pool applies `engine-generated` to the external-engine lane's candidates only.
- No-exemption: a test that inspects (or exercises) the Phase 3 convergence path and asserts no
  `engine-generated`-conditional branch exists in basis evaluation or the categorical-kill gate — an
  `engine-generated` candidate with a weak basis is cut identically to a Claude-authored one with the same
  weak basis.
- Graceful degrade: external-engine CLI unavailable → run proceeds Claude-only, no hard failure.

## Grounding References
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (id `T1-F1-2`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 (`ENGINE_INTENTS`
  producer/consumer pair, "corrections intake §9(c)"), §2 (binding-decision register — #283, #318)

### Acceptance criteria
- [ ] Phase 2 dispatches an external-engine frame agent using the identical frame-agent prompt contract as
  the Claude frame agents. Check: `uv run pytest tests/test_ideate_engine_lane.py -k dispatch_contract` →
  passes.
- [ ] The external-engine lane's candidates are not visible to other frame agents during generation. Check:
  `uv run pytest tests/test_ideate_engine_lane.py -k blind_isolation` → passes.
- [ ] Merged candidate pool tags every external-engine-lane candidate `engine-generated` and leaves other
  candidates untagged/frame-tagged as today. Check: `uv run pytest tests/test_ideate_engine_lane.py -k
  tag_application` → passes.
- [ ] An `engine-generated` candidate with a weak/absent basis is cut by Phase 3 convergence identically to
  a Claude-authored candidate with the same weak basis, with no tag-conditional exemption in the code path.
  Check: `uv run pytest tests/test_ideate_engine_lane.py -k no_gate_exemption` → passes.
- [ ] With the external-engine CLI unreachable, `/ideate` completes using only the Claude frame-agent set
  with no blocked run. Check: `uv run pytest tests/test_ideate_engine_lane.py -k graceful_degrade` →
  passes.
- [ ] Release-surface metadata (plugin version, marketplace entry, CHANGELOG) is updated in the same PR.
  Check: `git diff --name-only` includes `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Unit tests for the new lane
uv run pytest tests/test_ideate_engine_lane.py -v
# Confirm no tag-conditional branch exists in the convergence gate
uv run pytest tests/test_ideate_engine_lane.py -k no_gate_exemption -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the no-gate-exemption test explicitly proves `engine-generated` candidates receive
no special treatment in Phase 3 convergence.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none (this issue builds the offer/dispatch lane itself; it does not consume an
  external engine as part of its own execution)
- **Justification:** The dispatch target, chaperone-dispatch tier (`offload`/`sonnet-medium`), and
  never-gatekeepers constraint are already settled by binding decisions #283 and #318; the Phase 2/Phase 3
  mechanics this issue plugs into are documented and unchanged. This is an additive, well-bounded skill-file
  and reference-file change with a clear no-exemption test to write — sonnet/medium is sufficient; no case
  for opus or an external engine in the implementation of this issue.

### Release-surface checklist
This issue changes plugin behavior (new Phase 2 dispatch lane, new survivor provenance tag value), so the
following must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — plugin metadata sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new external-engine divergent-generator lane.
- [ ] Drift/no-exemption test (`tests/test_ideate_engine_lane.py -k no_gate_exemption`) so a future edit to
  Phase 3 convergence that special-cases `engine-generated` fails CI instead of silently drifting into a
  privileged path.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (id `T1-F1-2`)
- Source type: ideation-survivor
- Source title: Blind external-engine divergent-generator lane in /ideate

### Context library links

_none_

### Intent

`/ideate`'s Phase 2 (Divergent ideation) dispatches only Claude frame agents today (`plugins/saga/skills/ideate/SKILL.md:406-437`). This issue adds one additional lane in that same phase — an external-engine frame agent (codex/agy, per the existing chaperone-dispatch model) that generates its own candidate batch under the identical frame-agent prompt contract used by the Claude frame agents. Its candidates merge into the same master pool (`SKILL.md:497-508`) tagged `engine-generated`, are blind to the rest of the pool during generation exactly as every other frame agent already is, and then pass through Phase 3 convergence (`references/convergence-and-partnership.md`) under the identical basis and categorical-kill criteria as Claude-authored candidates — no separate gate, no exemption, no privileged survival path.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/454
- Number: 454
- Created at: 2026-07-04T08:22:52.721239+00:00

