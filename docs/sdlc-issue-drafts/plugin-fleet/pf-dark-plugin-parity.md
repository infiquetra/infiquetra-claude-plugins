---
title: "exploration: the dark half of the fleet — in-or-out verdict and primitive-parity pass for deploy, home-lab-ops, unifi, redis-channel"
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Expand saga+deploy capability breadth (misc/quick-wins)"
wave: wave-3
slug: pf-dark-plugin-parity
---

# exploration: the dark half of the fleet — in-or-out verdict and primitive-parity pass for deploy, home-lab-ops, unifi, redis-channel

### Objective

Expand saga+deploy capability breadth (misc/quick-wins).

### Intent

Produce a decision/recommendation document — not a PR against plugin behavior — that gives each of
the fleet's four "dark" plugins (`deploy`, `home-lab-ops`, `unifi`, `redis-channel`: the four of
eight fleet plugins never audited against saga/team-execution's cross-cutting primitives) an
explicit, per-primitive in-or-out verdict, so the fleet's coverage story stops being an accident of
which plugins ideation happened to focus on. This is a decision deliverable: `dod_sketch` is a
recommendation document with a per-plugin, per-primitive verdict table and a follow-up issue list
for every "in" cell — not a code change to any of the four plugins themselves.

## Problem / Motivation

The fleet is 8 independently versioned, independently installed marketplace plugins: saga 0.51.0,
team-execution 2.9.0, mission-control 2.4.0, agy 0.1.0, deploy 0.1.2, home-lab-ops 1.2.0,
redis-channel 0.5.0, unifi 1.1.0 (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`).
Nearly every recent capability-breadth theme in this ideation batch — model/effort tier levers,
cost/evidence ledgers, sandbox guards — was scoped and grounded against saga and team-execution
only. The other four plugins (`deploy`, `home-lab-ops`, `unifi`, `redis-channel`) were never put
through the same lens, and nothing today records whether that is a deliberate scope decision or
just an oversight.

Concretely, three primitives are candidates for fleet-wide adoption and none has been evaluated
against the four dark plugins:

1. **Tier lever.** The fleet's one operator-facing model/effort lever lives entirely in saga
   `/plan`'s unit tier table (`plugins/saga/skills/plan/SKILL.md:295-306`), with vocabulary
   `MODELS=("fable","opus","sonnet","haiku")` / `EFFORTS=(...,"xhigh")`
   (`plugins/saga/scripts/execution_spec.py:52-53`). Every agent frontmatter across all 8 plugins
   hardcodes `model:` with zero `effort:` fields (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:14-21`),
   including the four dark plugins' own agents (`plugins/deploy/agents/release-orchestrator.md`,
   `plugins/home-lab-ops/agents/homelab-sre.md`, `plugins/unifi/agents/unifi-network-ops.md`,
   `plugins/redis-channel/agents/redis-channel-coach.md`). No one has recorded whether these four
   agents should ever gain a tier lever, or why not.
2. **Ledgers.** `/outcome`'s cost ledger is a leaf-produced fact, derived-on-read, never a
   committed status field (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`). None of
   `deploy`, `home-lab-ops`, `unifi`, or `redis-channel` participate in `/outcome` or any ledger
   today — whether that is correct (they are operational/CLI tools, not lifecycle leaves) or a gap
   has never been stated explicitly.
3. **Guards.** The readonly-verifier sandbox contract (`subagent_type: saga:readonly-verifier` +
   `isolation: "worktree"` for every verify/review-class spawn) has a full spawn-site inventory for
   saga, with team-execution and `/agy:delegate` explicitly recorded as out-of-scope-with-rationale
   (`plugins/saga/references/sandbox-spawn-sites.md`, "Out-of-scope (with rationale)" table). None
   of the four dark plugins appear in that inventory at all — not as in-scope, not as
   out-of-scope-with-rationale. `plugins/home-lab-ops/agents/homelab-sre.md` and
   `plugins/deploy/agents/release-orchestrator.md` both describe agents that could plausibly spawn
   verify-class sub-work (pre-flight checks, deployment verification); this repo's own CLAUDE.md
   already states the binding rule ("Any verify/review-class Agent-tool spawn made outside a saga
   skill must pass `subagent_type: saga:readonly-verifier` + `isolation: \"worktree\"`") but no
   audit has confirmed the four dark plugins comply, are exempt, or don't spawn verify-class agents
   at all.

Left unresolved, each of these primitives will keep expanding one plugin at a time (saga, then
team-execution, maybe mission-control) while the fleet's anti-sprawl posture
(`{#plugin-portfolio-groom-17-to-7}`, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`)
has no record of whether the remaining four plugins were ever considered — an operator or an
auditor cannot tell "deliberately excluded" from "nobody looked."

## Definition of Done

A decision/recommendation document exists — not a code change to any of the four plugins — giving
each of the fleet's four "dark" plugins (`deploy`, `home-lab-ops`, `unifi`, `redis-channel`) an
explicit, per-primitive (tier lever, ledger, guard) in-or-out verdict, with a stated rationale for
every "out" cell and a follow-up issue stub for every "in" cell (`dod_sketch`: "Decision/
recommendation doc with per-plugin in-or-out verdicts per fleet primitive and a follow-up issue
list for the ins.").

### Verification

```bash
# Decision doc exists and names all four dark plugins
grep -n "dark-plugin-parity" docs/engineering-journal/DECISIONS.md

# Verdict table covers all 4 plugins x 3 primitives (12 cells), none blank/TBD
python3 - <<'EOF'
import re
text = open("docs/engineering-journal/DECISIONS.md").read()
section = text.split("dark-plugin-parity", 1)[1]
plugins = ["deploy", "home-lab-ops", "unifi", "redis-channel"]
primitives = ["tier lever", "ledger", "guard"]
missing = [(p, prim) for p in plugins for prim in primitives
           if not re.search(rf"{p}.*{prim}|{prim}.*{p}", section, re.I | re.S)]
assert not missing, f"missing verdict cells: {missing}"
print("all 12 verdict cells present")
EOF

# Follow-up issue list present in QUEUED.md for every "in" verdict
grep -n "dark-plugin-parity" docs/engineering-journal/QUEUED.md
```

Expected: all commands succeed; the Python check prints "all 12 verdict cells present" with no
assertion error.

### Acceptance criteria
- [ ] **AC1 (every dark plugin has an explicit verdict per primitive).** `DECISIONS.md` entry
  contains a verdict table (or equivalent explicit prose per cell) covering all 4 dark plugins
  (`deploy`, `home-lab-ops`, `unifi`, `redis-channel`) × all 3 fleet primitives (tier lever, ledger,
  guard) = 12 cells, each stating "in" or "out." Check: the verification-block Python script above
  exits 0 with no missing cells.
- [ ] **AC2 (opt-outs carry a stated rationale).** Every cell marked "out" includes a one-sentence
  rationale distinguishing it from a blank/deferred/TBD entry (e.g. "redis-channel has no
  verify/review-class spawn sites — it bridges message transport only, confirmed by grep across
  `plugins/redis-channel/skills/` finding zero `Task`/`agent()` calls"). Check: `grep -B2 "out" docs/engineering-journal/DECISIONS.md`
  (within the dark-plugin-parity section) shows no cell followed only by "out" with no trailing
  rationale sentence — manual review confirms each "out" cell has a distinguishing clause.
- [ ] **AC3 (guard verdict is grounded in an actual spawn-site check, not assumed).** For the guard
  primitive specifically, each of the 4 plugins' verdict cites whether it was found to spawn any
  verify/review-class sub-agent (via `Task`/`agent()` calls in its `skills/` or `agents/`
  directory), and if it does, whether `subagent_type: saga:readonly-verifier` +
  `isolation: "worktree"` is already applied. Check: entry text for each plugin's guard cell
  contains either "no verify/review-class spawn sites found (`grep` of `plugins/<name>/skills/`
  and `plugins/<name>/agents/`)" or a citation to the specific spawn site and its current sandbox
  status.
- [ ] **AC4 (every "in" verdict has a follow-up issue).** For every cell marked "in," a follow-up
  issue exists or is stubbed in `docs/engineering-journal/QUEUED.md` naming the specific plugin,
  the primitive, and the concrete next step (not "consider adopting X someday"). Check:
  `grep -A2 "dark-plugin-parity" docs/engineering-journal/QUEUED.md` shows one queued item per "in"
  cell from AC1's table.
- [ ] **AC5 (grounded, not extrapolated).** Every claim about current dark-plugin behavior cites a
  specific file (and line where applicable) verified during this exploration — no
  "likely"/"probably"/"should be" language about whether a plugin spawns sub-agents or participates
  in a primitive today. Check: manual review of the `DECISIONS.md` entry finds a citation attached
  to every factual claim about current state.
- [ ] **AC6 (engages the anti-sprawl and never-gatekeepers binding decisions where relevant).** If
  any "in" verdict proposes new shared infrastructure (e.g. a fleet-wide guard registry), the entry
  explicitly engages `{#plugin-portfolio-groom-17-to-7}` rather than silently proposing a ninth
  plugin or an uncoordinated new surface. Check: entry text contains the anchor
  `{#plugin-portfolio-groom-17-to-7}` if and only if a new shared-infrastructure "in" verdict is
  recommended.

### Out-of-scope / non-goals
- Implementing any of the "in" verdicts — this issue produces the decision doc and follow-up issue
  list; the follow-up issues (AC4) carry the actual implementation.
- Auditing saga, team-execution, mission-control, or agy — those four plugins already have primitive
  coverage recorded (tier table, sandbox spawn-site inventory, `/outcome` ledger); this issue is
  scoped to the four plugins that don't.
- Adding new fleet primitives beyond the three named (tier lever, ledger, guard) — if the audit
  surfaces a fourth candidate primitive, name it in the decision doc as a follow-up seed, don't
  scope-creep this issue to cover it.
- Changing `plugins/saga/references/sandbox-spawn-sites.md` itself — this issue may recommend
  entries be added to it as a follow-up (AC4), but does not edit it directly.

## Grounding References

- **Absorbed idea** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`, id
  `G-negative-space-11`, role: primary, theme `NEW:dark-plugin-parity`, frame
  `gap-negative-space`, axis "fleet coverage honesty") — "The dark half of the fleet: an explicit
  in-or-out verdict and primitive-parity pass for deploy, home-lab-ops, unifi, and redis-channel."
  `basis_type: direct`, `verdict: survive`, `tier_tag: incremental` (escalated to `structural` in
  the issue-map consolidation given the cross-fleet blast radius of the primitives under review).
- **Consolidation rationale** (`docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`,
  slug `pf-dark-plugin-parity`): "Decision deliverable, not a PR: which fleet primitives (tier
  lever, ledgers, guards) the four dark plugins adopt or explicitly opt out of."
- **Fleet map** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`): 8 plugins,
  independently versioned and installed — the structural fact that makes "dark" plugins a real
  coverage gap rather than a naming nuance.
- **Tier-lever reality** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:14-21`,
  `plugins/saga/skills/plan/SKILL.md:295-306`, `plugins/saga/scripts/execution_spec.py:52-53`): the
  fleet's only operator-facing model/effort lever, confirmed absent from every agent frontmatter
  across all 8 plugins.
- **Guard spawn-site inventory** (`plugins/saga/references/sandbox-spawn-sites.md`): the existing
  readonly-verifier classification for saga, team-execution, and `/agy:delegate` spawn sites — the
  precedent this exploration extends to the four dark plugins, and the CLAUDE.md-binding rule this
  repo already states for any verify/review-class spawn outside a saga skill.
- **`/outcome` ledger discipline** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:48`):
  derived-on-read cost ledger, leaf-produced fact, never committed status — the shape any ledger
  verdict for a dark plugin must match if it lands "in."
- **Binding decision engaged**: `{#plugin-portfolio-groom-17-to-7}` (plugin sprawl is an active
  concern; new-plugin or new-shared-infrastructure "in" verdicts carry a consolidation burden of
  proof) — `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`.

### Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** second-opinion (advisory only; Claude remains verifier-of-record per
  `{#external-engines-never-gatekeepers}` (#283) — an external engine may propose or critique a
  verdict but does not gate the decision).
- **Justification:** this is a survey-and-record exploration (grep the four plugins' `skills/` and
  `agents/` directories, cross-reference three already-defined primitives, write a verdict table)
  rather than a novel architectural design — sonnet at medium effort is proportionate. A
  second-opinion pass is worth the modest cost because a wrongly-recorded "out" verdict (e.g.
  missing an actual verify-class spawn site) would silently leave a plugin non-compliant with this
  repo's own CLAUDE.md sandboxing rule.

### Release-Surface Checklist

This issue does not change any plugin's behavior, schema, command, or user-facing guidance directly
— it produces a decision document. No `plugin.json`, `marketplace.json`, `CHANGELOG.md`, or
drift-guard test changes are required for this issue itself. Each follow-up issue spawned from an
"in" verdict (AC4) must carry its own release-surface checklist when it lands, per this repo's
`CLAUDE.md` step 6.

### Files Expected to Change

Indicative only — exact set is `/plan`'s to determine.

- `docs/engineering-journal/DECISIONS.md` — new dark-plugin-parity entry with the 12-cell verdict
  table.
- `docs/engineering-journal/QUEUED.md` — follow-up issue stubs for each "in" verdict.
- `plugins/saga/references/sandbox-spawn-sites.md` — potentially annotated (not rewritten) to note
  that the four dark plugins were audited and their guard verdicts, even if this remains a
  follow-up rather than landing in this PR.

### Tests to Add or Update

- No new automated tests are required for the decision doc itself; the verification block's
  Python check (grep-based cell-coverage assertion) is the acceptance mechanism for this issue.
- Each follow-up issue spawned from an "in" verdict (AC4) is responsible for its own test coverage
  when implemented.

### Context library links

- _none_

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan for the audit-and-decision work once this
issue is filed.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`, slug
  `pf-dark-plugin-parity`, absorbing `G-negative-space-11` (primary)
- Source type: ideation survivor (issue-map)
- Source title: The dark half of the fleet: in-or-out verdict and primitive-parity pass for
  deploy, home-lab-ops, unifi, redis-channel

**Absorbed ideas:** G-negative-space-11

### Files expected to change

- `plugins/deploy/agents/release-orchestrator.md`
- `plugins/home-lab-ops/agents/homelab-sre.md`
- `plugins/unifi/agents/unifi-network-ops.md`
- `plugins/redis-channel/agents/redis-channel-coach.md`
- `plugins/saga/references/sandbox-spawn-sites.md`
- `docs/engineering-journal/QUEUED.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`

### Tests to add or update

- Full repo gate: `uv run pytest` (no new test files named; see Acceptance criteria)
