---
title: "capability: stacked-PR auto-close cascade guard with automatic child rebase-and-reopen"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: moonshot
objective: Automate the ship ceremony end-to-end
wave: wave-3
---

# capability: stacked-PR auto-close cascade guard with automatic child rebase-and-reopen

### Objective

Automate the ship ceremony end-to-end

### Tier

moonshot

### Wave

wave-3

### Intent

When a base PR in a stacked-PR chain merges, GitHub auto-closes (or silently orphans) the
child PRs stacked on top of it, and their CI runs are left targeting a branch that no longer
exists in the merge path. This capability adds a stack-topology field to the saga `pr_refs`
schema and a base-merge cascade handler so that merging the base of a two-deep (or deeper)
stack automatically rebases each child onto the new base, reopens any child GitHub auto-closed,
and re-triggers CI for each — so a stacked-PR workflow through `/work` no longer requires a
human to manually walk the stack after every base merge.

### Problem / Motivation

Session-mining synthesis names stacked-PR handling as a named, dated gap in the ship ceremony,
not a hypothetical: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:147` lists
"stacked-PR auto-close + CI branch-trigger gap" among the concrete singleton findings from the
27-session mining pass, alongside the `gh pr merge --auto`/`--delete-branch` surprises. The same
gap is carried in the final theme roster's direct-to-candidate pool as "stacked-PR CI-trigger
support" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:185`), and theme 7's summary
line explicitly frames the ship-ceremony theme as covering "8-repo manual ritual; stacked-PR
gaps" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:169`).

This is a real, recurring failure shape distinct from (but adjacent to) the single-PR ship
ritual: recurring pattern 1 in the same synthesis — "Manual ship ceremony — commit→PR→merge→
checkout-main→pull→cleanup done by raw git/gh in session after session" (8 repos,
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:169`) — is the single-PR case the sibling
issue `pf-ship-ceremony-primitive` (`plugins/saga/scripts/ship_ceremony.py`) and
`pf-ship-hazard-preflight-and-undo` already own. Neither of those issues rebuilds stack topology
or automatically walks a stack after a base merge; the dedup map explicitly folded the original
stacked-PR seed (`S-14`, "Stacked-PR support in ship ceremony") into this issue's primary idea
(`T7-F2-7`) rather than duplicating stack-specific machinery across two issues.

Today `/work`'s PR-continuation loop tracks exactly one `pr_refs` entry per saga
(`plugins/saga/skills/work/references/pr-continuation-loop.md:84`: "`pr_refs` — set when the PR
is opened (SKILL Phase 5.4)"), with no concept of a parent/child stack relationship or of what
should happen to a dependent PR when its base merges
(`plugins/saga/skills/work/references/pr-continuation-loop.md:10-80` describes the transition
table for a single PR only). There is no stack-topology field, no cascade handler, and no
automatic recovery path today — a base merge over a stack currently requires a human to notice
the child was auto-closed, manually re-point its base, reopen it, and re-trigger CI by hand.

### Non-goals boundary (explicit dependency)

This capability is deliberately scoped as **the recovery machinery only**, sitting behind the
hazard preflight that decides whether a merge is safe to proceed at all. Per the consolidation
rationale for this issue in the issue map: "the recovery machinery (stack topology in `pr_refs`
+ cascade handler) is a self-contained moonshot behind the hazard preflight." The sibling issue
`pf-ship-hazard-preflight-and-undo` already commits to stacked-PR hazard *detection* (its
acceptance criterion "Stacked-PR hazard detection (T7-F4-4)" and its explicit non-goal: "The
stacked-PR cascade guard's automatic rebase-and-reopen machinery... is `pf-stacked-pr-cascade-
guard`... separate wave-3 moonshot explicitly described as sitting 'behind hazard preflight'
before this issue ships"). This issue is the moonshot machinery that hazard preflight defers to;
it does not re-implement hazard detection, and it must not fire on a stack the hazard preflight
has flagged as unsafe to merge in the first place.

## Definition of Done

1. `pr_refs` gains a stack-topology field (parent PR reference, ordered child list, and each
   child's current base) written when a stacked PR is opened through `/work`, so the saga
   record — not GitHub state alone — is the source of truth for "what stack is this PR part
   of and what merged under it."
2. A base-merge cascade handler in the ship-ceremony path (invoked once the hazard preflight in
   `pf-ship-hazard-preflight-and-undo` has cleared a merge as safe) that, on detecting a merged
   base with recorded children in `pr_refs`: rebases each child onto the new base branch (the
   base PR's target), reopens any child GitHub auto-closed as a side effect of the base merge,
   and re-triggers each child's CI run against its rebased head.
3. A fixture-driven test simulates a base merge over a two-deep stack (base → child A → child
   B) and asserts each child ends rebased onto the correct new base, reopened if auto-closed,
   and with a fresh CI run triggered — with no manual intervention.

### Acceptance criteria
- [ ] **Stack-topology field recorded at stack creation (T7-F2-7).** Opening a second PR in a
  saga whose `pr_refs` already has an open PR records a parent/child stack relationship (parent
  PR number, child PR number, child's current base branch) in `pr_refs`, rather than overwriting
  the existing single-PR record. Check: `uv run pytest tests/test_pr_refs_stack.py -k
  records_stack_topology_on_second_pr` → passes.
- [ ] **Base merge over a two-deep stack rebases, reopens, and CI-retriggers each child
  (T7-F2-7).** Given a fixture stack of base → child A → child B recorded in `pr_refs`, merging
  the base triggers the cascade handler, which rebases child A onto the base's merge target,
  reopens child A if GitHub auto-closed it, and re-triggers child A's CI; the same handler then
  cascades to child B once child A's rebase completes, rebasing it onto child A's new head.
  Check: `uv run pytest tests/test_cascade_handler.py -k two_deep_stack_rebase_reopen_retrigger`
  → passes.
- [ ] **Cascade handler only fires after hazard preflight clears the merge (T7-F2-7 /
  dependency on pf-ship-hazard-preflight-and-undo).** The cascade handler is invoked from the
  ship-ceremony merge step only after `ceremony_hazards.detect()` (from
  `pf-ship-hazard-preflight-and-undo`) has returned no blocking stacked-PR hazard for the base
  being merged; a fixture where the hazard detector flags the base merge as unsafe asserts the
  cascade handler is never invoked. Check: `uv run pytest tests/test_cascade_handler.py -k
  cascade_not_invoked_when_hazard_blocks` → passes.
- [ ] **Auto-close recovery is idempotent on re-run.** Re-invoking `/work` (or the cascade
  handler directly) on a saga whose stack was already fully cascaded is a no-op — it does not
  re-rebase, re-reopen, or re-trigger CI a second time. Check: `uv run pytest
  tests/test_cascade_handler.py -k cascade_idempotent_on_rerun` → passes.
- [ ] **Full repo gate passes.** Check:
  ```
  uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
  ```

### Out-of-scope / non-goals
- **In scope:** the `pr_refs` stack-topology schema addition; the base-merge cascade handler
  (rebase, reopen, CI-retrigger for each child in a stack); fixture tests covering a two-deep
  stack.
- **Out of scope — stacked-PR hazard detection.** Deciding whether a stacked-PR base merge is
  safe to proceed at all (order-of-merge hazards, auto-merge + delete-branch combinations
  against an open child) is `pf-ship-hazard-preflight-and-undo`'s acceptance criterion
  "Stacked-PR hazard detection (T7-F4-4)." This issue consumes that clearance signal; it does
  not re-implement hazard detection.
- **Out of scope — the single-PR ship ceremony primitive.** The base state machine, transition
  table, and resumability this cascade handler hooks into is
  `pf-ship-ceremony-primitive`'s `plugins/saga/scripts/ship_ceremony.py`. This issue extends
  that primitive's merge step; it does not redesign its transitions.
- **Out of scope — deeper-than-two-level stacks beyond the fixture depth, and rebase-conflict
  resolution.** If a rebase produces a merge conflict when cascading a child, this issue's
  handler surfaces a named, typed failure and halts the cascade (halt-not-degrade) rather than
  attempting automatic conflict resolution; automatic conflict resolution is explicitly out of
  scope.
- **Out of scope — ceremony-terminal teardown/reconciliation** (worktree cleanup, lease release
  after a successful ship) — owned by `pf-ship-teardown-reconciliation`.
- **Out of scope — board↔saga status reconciliation for ceremony** — already shipped
  separately per `6b33eba feat(saga): board↔saga reconciliation on resume (#295) (#330)`; this
  issue does not touch board-status write paths.

## Grounding References

- **Primary — `T7-F2-7`** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`,
  theme T7 "Lifecycle auto-progression & the ship ceremony," frame F2
  "ceremony-edge-cases"), "Stacked-PR auto-close cascade guard with automatic child
  rebase-and-reopen." `dod_sketch`: "Merged stack-topology field in `pr_refs` + base-merge
  cascade handler that rebases and reopens children; test simulates a base merge over a
  two-deep stack asserting each child is rebased, reopened, and CI-retriggered." This entry
  carries no `basis` field of its own (a thin seed on the dedup-merge side); its full intent is
  reconstructed here from the grounding-brief citations below and from the parallel `S-14` seed
  it absorbed.
- **Dedup-merged — `S-14`** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`,
  theme T7, seed axis), "Stacked-PR support in ship ceremony." Basis: "brief §8
  direct-to-candidate 'stacked-PR'; §5 pattern 1 + §7 stacked-PR gaps." `dod_sketch`: "Merged
  `/work` ship-ceremony handling for stacked PRs (base tracking, `--auto`/`--delete-branch`
  interplay). Verify: a two-PR stack merges in order with correct base rebasing (scripted
  repro)." The issue-map's consolidation rationale explicitly folds this seed into `T7-F2-7`:
  "Dedup-map already folded seed S-14 (stacked-PR support) into T7-F2-7; the recovery machinery
  (stack topology in `pr_refs` + cascade handler) is a self-contained moonshot behind the hazard
  preflight."
- **Recurring-pain grounding** —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:147` (session-mining singleton finding
  naming the exact gap: "`gh pr merge --auto`/`--delete-branch` behavior surprises; stacked-PR
  auto-close + CI branch-trigger gap"), and
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:169` (final theme roster, theme 7:
  "Lifecycle auto-progression & the ship ceremony (8-repo manual ritual; stacked-PR gaps)"), and
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:185` (direct-to-candidate pool carrying
  "stacked-PR CI-trigger support" forward pre-grounded).
- **Existing `pr_refs` transition-table surface this extends without redesigning** —
  `plugins/saga/skills/work/references/pr-continuation-loop.md:84` ("`pr_refs` — set when the
  PR is opened (SKILL Phase 5.4)") and `plugins/saga/skills/work/references/pr-continuation-loop.md:10-80`
  (the current single-PR transition table this issue's stack-topology field is layered onto).
- **Depends on** `pf-ship-hazard-preflight-and-undo` (absorbing `T7-F4-4`/`T7-F2-6`/`T7-F1-2`) —
  its stacked-PR hazard detector (`ceremony_hazards.py`) must clear a base merge before this
  issue's cascade handler is permitted to fire; this issue's own non-goal explicitly excludes
  reimplementing that detector. That issue's non-goals section names this issue by slug and
  describes it as "separate wave-3 moonshot explicitly described sitting 'behind hazard
  preflight' before this issue ships" — i.e., the dependency runs in the opposite direction
  from the sibling issue's phrasing: hazard preflight ships and gates first; this cascade guard
  consumes its clearance.
- **Depends on** `pf-ship-ceremony-primitive` (absorbing `T7-F4-1`/`H-F3-6`/`H-F2-3`,
  `plugins/saga/scripts/ship_ceremony.py`) — the base state machine and merge step this issue's
  cascade handler hooks into.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** xhigh
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is moonshot-tier because the acceptance criteria require reasoning
  through a genuinely open edge-case space — nested rebase cascades, idempotent re-entry after a
  partial cascade, and correct sequencing behind a hazard gate owned by a sibling issue — with no
  existing stack-topology schema or cascade handler to extend. xhigh effort reflects the
  combinatorial edge cases in "rebase each child, in order, onto a moving base, without
  double-firing on re-run" needing to be fixture-verified correctly, not any need for consensus
  review or an external engine; the work is deterministic Python/git-graph logic well within
  sonnet's competence at higher effort.

### Release-surface checklist

This issue adds a new `pr_refs` schema field and a new cascade-handler module to the `saga`
plugin. Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new stack-topology field,
  cascade-handler surface).
- [ ] `.claude-plugin/marketplace.json` — reflect the version bump for `saga`.
- [ ] `plugins/saga/CHANGELOG.md` — release entry describing the stack-topology field and
  cascade-handler behavior.
- [ ] Plugin-metadata/version drift-guard tests — re-run and confirm marketplace/plugin.json
  version parity checks pass with the bump in place.
- [ ] `docs/engineering-journal/LEARNINGS.md` — dated entry on the stack-topology + cascade
  mechanism (non-obvious fix/feature per repo CLAUDE.md convention), including evidence
  (PR/commit, file:line) and a generalizable rule.
- [ ] `plugins/saga/skills/work/references/pr-continuation-loop.md` — document the new
  `pr_refs` stack-topology field and the cascade-handler transition alongside the existing
  single-PR transition table.

### Files expected to change

- `plugins/saga/scripts/ship_ceremony.py` — call-site for the cascade handler after a hazard-cleared base merge.
- `plugins/saga/scripts/stacked_pr_cascade.py` — new module: stack-topology helpers + cascade handler (proposed path).
- `plugins/saga/references/saga-spec.md` — `pr_refs` schema documentation update (stack-topology field).
- `plugins/saga/skills/work/references/pr-continuation-loop.md` — document stack-aware transitions.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — version sync.
- `plugins/saga/CHANGELOG.md` — release entry.
- `tests/test_pr_refs_stack.py` — stack-topology recording fixtures.
- `tests/test_cascade_handler.py` — two-deep-stack rebase/reopen/retrigger, hazard-gating, and idempotent-rerun fixtures.
- `docs/engineering-journal/LEARNINGS.md` — dated entry.

### Tests to add or update

- `tests/test_pr_refs_stack.py::records_stack_topology_on_second_pr`
- `tests/test_cascade_handler.py::two_deep_stack_rebase_reopen_retrigger`
- `tests/test_cascade_handler.py::cascade_not_invoked_when_hazard_blocks`
- `tests/test_cascade_handler.py::cascade_idempotent_on_rerun`

### Verification

```bash
# New stack-topology and cascade-handler unit tests
uv run pytest tests/test_pr_refs_stack.py tests/test_cascade_handler.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the two-deep-stack fixture shows each child rebased onto its correct new
base, reopened if GitHub auto-closed it, and with a fresh CI run triggered; the hazard-gating
fixture shows the cascade handler never invoked when the hazard detector blocks the base merge;
the idempotent-rerun fixture shows no duplicate rebase/reopen/CI-trigger on a second invocation
over an already-cascaded stack.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan once `pf-ship-hazard-preflight-and-undo`
and `pf-ship-ceremony-primitive` have landed (or are landing in the same wave-3 cycle), since
this issue's cascade handler depends on both.

### Source context

- Source: `/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/c23d3bf9-9081-4727-8e0d-140ebc73f63f/scratchpad/ideation/issue-map/issue-map-final.json` (`pf-stacked-pr-cascade-guard`)
- Absorbed ids: `T7-F2-7` (primary, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`), `S-14` (dedup-merged, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`)
- Source type: issue-map
- Source title: Stacked-PR auto-close cascade guard with automatic child rebase-and-reopen

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/434
- Number: 434
- Created at: 2026-07-04T08:12:32.813077+00:00

