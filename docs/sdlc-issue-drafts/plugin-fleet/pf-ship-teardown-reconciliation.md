---
title: capability: ship ends in teardown — opened-resource manifest, closing-count reconciliation, immutable ship receipt, idle worktree reclamation
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Automate the ship ceremony end-to-end"
wave: wave-1
slug: pf-ship-teardown-reconciliation
---

# capability: ship ends in teardown — opened-resource manifest, closing-count reconciliation, immutable ship receipt, idle worktree reclamation

### Objective
Automate the ship ceremony end-to-end

### Tier
structural

### Wave
wave-1

### Intent

Make teardown the guarded ship verb's *terminal gate*, not an optional afterthought: register every
resource the ceremony opens (branch, worktree, background session, scratch space, draft PR) in an
opened-resource manifest at open time, block `ship` from declaring the run done while that manifest's
closing count is non-zero, mint an immutable ship receipt only once the count reaches zero, and add a
`reclaim` subcommand — reusing the existing `outcome_worktrees` teardown machinery
(`plugins/saga/scripts/outcome_worktrees.py`) — that removes merged-branch worktrees while leaving
unmerged ones untouched.

### Problem / Motivation

The grounding brief's hygiene find is direct, present-tense evidence, not a hypothetical: **15 stale
abandoned saga worktrees** sit in `.worktrees/` today, inflating the repo 10x+, and the brief explicitly
calls this "the same disease as team-execution's missing Step B8"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`). `team-execution`'s own run lifecycle
confirms the shape of that disease: its documented steps run `Step B0: Parse Approved Team Plan`
(`plugins/team-execution/skills/team-execution/SKILL.md:277`) through `Step B7: Completion`
(`plugins/team-execution/skills/team-execution/SKILL.md:403`), and Step B7 reports worker changes,
reviewer scores, and gate results — it never tears down or reclaims anything the run opened. There is
no terminal reclamation step anywhere in that lifecycle today.

Reused machinery already exists for the reclaim half of this problem: `outcome_worktrees.py` implements
`reap_worktree()` (`plugins/saga/scripts/outcome_worktrees.py:254`) — an idempotent remove-and-deregister
that keeps a registry entry when removal fails so a later pass retries it, precisely to avoid a silent
leak (`plugins/saga/scripts/outcome_worktrees.py:257-270`). What does not exist is (a) a manifest that
registers *every* opened-resource kind at open time (not just worktrees — also branches, background
sessions, scratch space, and draft PRs), (b) a gate that gives `ship`'s "done" declaration teeth by
refusing to fire while that manifest's closing count is non-zero, and (c) a durable, immutable receipt
that proves the ceremony (including its cleanup) actually ran, rather than trusting a green-looking exit.

Four absorbed ideation facets converge on this same "ship ends in teardown" gap and are folded into one
issue per the plugin-portfolio-groom binding decision (`{#plugin-portfolio-groom-17-to-7}` — new-primitive
ideas carry a consolidation burden of proof, cited in
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`):

- **G-hybrids-3** (primary) — the framing correction: `/ship` is redefined as the guarded verb whose
  *final* gate is verified reclamation (worktree removed, branch pruned, scratch cleared, lease
  released); a dry-run artifact shows `HALT` when any opened resource survives; the receipt is minted
  only on clean teardown. This makes teardown the exit condition of the verb, not a separate cleanup
  script bolted on after.
- **T7-F5-2** (facet) — the reconciliation mechanism: an opened-resource manifest registration hook
  (branch, worktree, background session, scratch, draft PR) fires in the `/work`/`/outcome` cleanup
  path, and `ship` blocks its "done" declaration while the manifest's closing count is non-zero — a
  seeded test with two orphan worktrees and one outstanding background session must surface as
  unreconciled and block.
- **T7-F4-7** (facet) — the proof mechanism: an immutable `ship_receipt.py` writer/reader, invoked by
  the ship ceremony's reclamation-verify step, that records what was opened and what was closed; a
  synthetic case where a worktree survives the receipt's own cleanup claim must be flagged rather than
  silently trusted.
- **T7-F2-2** (facet) — the reclaim mechanism: an idle-triggered `reclaim` subcommand reusing
  `outcome_worktrees`' existing teardown, gated by a reversibility certificate, that removes
  merged-branch worktrees while leaving unmerged worktrees untouched — the quick-win half of the same
  disease the 15 stale worktrees demonstrate live.

All four are `tier_tag: structural` (T7-F2-2 alone is tagged `quick-win` but folds in as a facet of the
same terminal-gate mechanism) with `verdict: survive` in the ideation survivor set
(`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`, entries for `G-hybrids-3`, `T7-F5-2`,
`T7-F4-7`, `T7-F2-2`) and share theme `T7` ("Lifecycle auto-progression & ship ceremony").

### Requirements

R1. An opened-resource manifest primitive registers every resource the ship/`/work`/`/outcome` cleanup
    path opens — branch, worktree, background session, scratch directory, draft PR — at the moment
    each is opened (register-on-open), mirroring the register-on-spawn pattern already used by
    `outcome_worktrees.register()` (`plugins/saga/scripts/outcome_worktrees.py:141`).

R2. The manifest exposes a derived, on-read "closing count" — the count of registered-but-not-yet-closed
    entries — computed the same way `outcome_worktrees.harvest_worktrees()` derives live state from the
    registry cross-checked against git (`plugins/saga/scripts/outcome_worktrees.py:297`), not a cached
    field that can drift from reality.

R3. The ship ceremony's terminal "declare done" transition is gated on the manifest's closing count:
    it refuses to declare the ceremony complete while the count is non-zero, surfacing which entries
    remain open (worktree path, branch name, session id, etc.) rather than a bare boolean.

R4. A `ship_receipt.py` writer/reader mints an immutable receipt only once the closing count reaches
    zero. The receipt records what was opened (per the manifest) and what was closed, and is written
    once and never mutated after — a later discrepancy is a *new* receipt or a flagged anomaly, not an
    edit to the original.

R5. The reclamation-verify step that gates the receipt re-checks reality before trusting the manifest's
    own closed-count: a synthetic case where a worktree still exists on disk despite the manifest
    claiming it closed is flagged as a discrepancy, not silently trusted (mirrors
    `outcome_worktrees.reap_worktree()`'s "keep the entry if removal fails" discipline,
    `plugins/saga/scripts/outcome_worktrees.py:266-268`).

R6. A `reclaim` subcommand reuses `outcome_worktrees`' existing teardown (`reap_worktree` /
    `harvest_worktrees`) to remove merged-branch worktrees while leaving unmerged-branch worktrees
    untouched, gated by a reversibility certificate (consistent with the fleet's existing
    reversibility-verdict convention used elsewhere in the outcome lifecycle).

R7. `reclaim` is invocable both on demand (operator-triggered) and idle-triggered (no fresh manifest
    activity past a bound), so the 15-stale-worktree failure mode the grounding brief documents cannot
    silently recur once this capability ships.

## Definition of Done

Teardown is the ship ceremony's terminal gate, not an optional afterthought: an opened-resource
manifest registers every resource the ceremony opens (branch, worktree, background session, scratch
space, draft PR) at open time; `ship`'s "declare done" transition refuses to fire while the manifest's
derived closing count is non-zero; an immutable `ship_receipt.py` writer/reader mints a receipt only
once that count reaches zero, and a reclamation-verify step re-checks reality rather than trusting the
manifest's own claim; and a `reclaim` subcommand reuses `outcome_worktrees` teardown to remove
merged-branch worktrees while leaving unmerged ones untouched.

### Acceptance criteria
- [ ] AC1 (T7-F5-2). Seeding two orphan worktrees and one outstanding background background session
      against the manifest, then invoking ship's terminal "declare done" transition, blocks with a
      non-zero closing count naming the three unreconciled entries.
      Check: `uv run pytest tests/test_ship_teardown_reconciliation.py -k blocks_on_nonzero_closing_count` → passes.
- [ ] AC2 (G-hybrids-3). A dry-run of the ship ceremony against a seeded scenario where one worktree
      survives cleanup emits `HALT` rather than a clean completion, and no receipt is minted.
      Check: `uv run pytest tests/test_ship_teardown_reconciliation.py -k dry_run_halt_on_surviving_worktree` → passes.
- [ ] AC3 (T7-F4-7). Running a full ceremony to completion emits an immutable receipt recording every
      opened resource and its closed state; attempting to mutate a written receipt in place raises
      rather than silently overwriting.
      Check: `uv run pytest tests/test_ship_teardown_reconciliation.py -k immutable_receipt_recorded` → passes.
- [ ] AC4 (T7-F4-7). A synthetic case where a worktree survives despite the manifest's own
      closed-count claiming it torn down is flagged by the reclamation-verify step rather than trusted.
      Check: `uv run pytest tests/test_ship_teardown_reconciliation.py -k flags_surviving_worktree_despite_claim` → passes.
- [ ] AC5 (T7-F2-2). `reclaim` run against a fixture with one merged-branch worktree and one
      unmerged-branch worktree removes the merged one and leaves the unmerged one untouched.
      Check: `uv run pytest tests/test_ship_teardown_reconciliation.py -k reclaim_merged_only` → passes.
- [ ] AC6. Teardown is exercised as the ceremony's terminal transition on every completion path
      (success, and a seeded partial-failure path that still reaches an explicit terminal state) — not
      an optional post-step that can be skipped by configuration.
      Check: `uv run pytest tests/test_ship_teardown_reconciliation.py -k terminal_transition_not_skippable` → passes.
- [ ] AC7. Full suite, format, lint, and types stay green.
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope**: the opened-resource manifest (register-on-open for branch, worktree, background session,
scratch, draft PR); the closing-count reconciliation gate on ship's terminal "declare done" transition;
`ship_receipt.py` (immutable writer/reader) and its invocation from the reclamation-verify step; the
`reclaim` subcommand reusing `outcome_worktrees` teardown, gated by a reversibility certificate.

**Out of scope / non-goals**:
- Building `ship_ceremony.py`'s own state machine, transition table, or its `/work`-start front-loaded
  draft-PR mode — that is `pf-ship-ceremony-primitive`'s deliverable; this issue supplies the *terminal
  gate* that primitive's "declare done" transition calls into, not the ceremony itself.
- `team-execution`'s generic non-skippable Step B8 teardown contract, its own reclamation ledger, TTL
  worktree reaper, and idle-TTL resident-teammate eviction — that is `pf-teardown-reclamation-contract`'s
  deliverable (theme T6), a parallel fix for the same underlying disease scoped to `team-execution`'s
  run lifecycle rather than the ship verb. This issue's manifest and `reclaim` subcommand are scoped to
  the saga `/work`/`/outcome`/ship surface and reuse `outcome_worktrees.py`, not `team-execution`'s
  separate ledger primitive.
- `{#worker-cache-scheduling}`'s named-teammate warm-pool residency model
  (`docs/engineering-journal/DECISIONS.md:1950`) — untouched; this issue's manifest tracks background
  sessions as an opened-resource entry, it does not reopen residency/idle-eviction policy.
- Deploy/canary mutation — owned by the `deploy` plugin, not touched here.
- Backfilling the manifest/receipt onto repos other than `infiquetra-claude-plugins` — the 15-worktree
  finding is motivating evidence from this repo; this issue ships the primitive here first.

## Grounding References

- `G-hybrids-3` — primary — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json` (`dod_sketch`:
  guarded ship ceremony whose terminal state is verified reclamation — worktree removed, branch pruned,
  scratch cleared, lease released — receipt minted only on clean teardown; dry-run shows `HALT` when a
  worktree survives).
- `T7-F5-2` — facet — same file — closing-count reconciliation axis: opened-manifest registration hook
  (branch, worktree, background session, scratch, draft PR) in the work/outcome cleanup path plus a
  saga-spec field and teardown-reconcile reference; test seeds two orphan worktrees and one background
  session, asserts ship blocks on non-zero closing count.
- `T7-F4-7` — facet — same file — proof axis: `ship_receipt.py` writer/reader invoked by the ship
  ceremony's reclamation-verify step; test runs ship and asserts the receipt records deleted
  branch/worktree, flags a synthetic case where a worktree survives the receipt's cleanup claim.
- `T7-F2-2` — facet — same file — reclaim axis: idle-triggered `reclaim` subcommand reusing
  `outcome_worktrees` teardown gated by a reversibility certificate; test creates a merged-branch
  worktree, runs reclaim, asserts merged worktrees reclaimed while unmerged worktrees are untouched.
- Direct present-tense evidence of the disease: **15 stale abandoned saga worktrees** in `.worktrees/`
  inflating the repo 10x+, named "the same disease as team-execution's missing Step B8"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:86-88`).
- Reused reclaim machinery this issue builds on: `outcome_worktrees.reap_worktree()`
  (`plugins/saga/scripts/outcome_worktrees.py:254`, idempotent remove-and-deregister that keeps the
  registry entry on removal failure to avoid a silent leak) and `harvest_worktrees()`
  (`plugins/saga/scripts/outcome_worktrees.py:297`, the derived-on-read reconcile pass this issue's
  closing-count logic mirrors).
- Confirming shape of the disease in the adjacent surface: `team-execution`'s run lifecycle stops at
  `Step B7: Completion` (`plugins/team-execution/skills/team-execution/SKILL.md:403`) with no terminal
  reclamation step — the parallel gap `pf-teardown-reclamation-contract` addresses on that surface.
- Binding decision constraining consolidation: `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an
  active concern, new-primitive ideas carry a consolidation burden of proof
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`) — satisfied here by folding four absorbed
  facets (G-hybrids-3, T7-F5-2, T7-F4-7, T7-F2-2) into one primitive rather than four.
- Binding decision on halt-not-degrade: the `/outcome` campaign's settled convention — "HALT-not-degrade"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-49`, `/outcome` campaign register) —
  directly constrains R3/AC2: the ceremony must halt loudly on a non-zero closing count, never proceed
  with a degraded/partial teardown.

### Recommended Executor Profile

- **Model**: sonnet
- **Effort**: high
- **Backend**: inline
- **External LLM**: none
- **Justification**: A well-bounded mechanical capability — a registration hook, a derived-on-read
  reconciliation count, an immutable receipt writer/reader, and a reclaim subcommand reusing existing
  `outcome_worktrees` machinery — with no ambiguous design judgment beyond what `/plan` resolves.
  Sonnet at high effort matches the fleet's tiering guidance for structural-but-mechanical work; no
  external-engine involvement is applicable (purely internal saga-script surface, no
  generator/advisory-reviewer role).

### Release-Surface Checklist

This issue changes plugin behavior (new manifest primitive, new receipt format, new `reclaim`
subcommand, and a new terminal gate on ship's "declare done" transition) and therefore requires, in the
same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new opened-resource
      manifest, `ship_receipt.py`, and `reclaim` subcommand capability.
- [ ] `.claude-plugin/marketplace.json` — matching version bump for the `saga` entry.
- [ ] `plugins/saga/CHANGELOG.md` — new dated entry describing the opened-resource manifest, the
      closing-count reconciliation gate, the immutable ship receipt, and the `reclaim` subcommand,
      following the existing entry format.
- [ ] Any version/metadata drift-guard tests under `tests/` — confirm they pass against the bumped
      version and the updated skill/reference file set.
- [ ] Any saga-spec schema file this issue's manifest field lands on — updated alongside its own
      version/schema drift-guard test, if one exists.

### Tests to Add or Update

- `tests/test_ship_teardown_reconciliation.py` (new) — opened-resource manifest registration,
  closing-count reconciliation blocking behavior, immutable receipt writer/reader, reclamation-verify
  discrepancy flagging, and `reclaim` merged-vs-unmerged worktree behavior.
- Existing `outcome_worktrees` tests (`tests/test_outcome_worktrees.py`, if present) — confirm the
  `reclaim` subcommand's reuse of `reap_worktree`/`harvest_worktrees` does not regress existing
  reap/harvest behavior.

### Verification

```bash
# New primitive's own test suite
uv run pytest tests/test_ship_teardown_reconciliation.py -v

# Full-repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

# Confirm the 15 currently-stale worktrees this issue's evidence cites are reclaimable via the new
# subcommand once implemented (manual spot-check, not part of the automated suite)
git worktree list
```

Expected: all green; `reclaim` run against the repo's current stale worktrees removes the merged ones
and leaves any unmerged ones untouched.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json (ids G-hybrids-3, T7-F5-2, T7-F4-7, T7-F2-2)
- Source type: ideation survivor set (issue-map-final.json entry `pf-ship-teardown-reconciliation`)
- Source title: Ship ends in teardown: opened-resource manifest, closing-count reconciliation, immutable ship receipt, idle worktree reclamation

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/outcome_worktrees.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `tests/test_ship_teardown_reconciliation.py`
- `tests/test_outcome_worktrees.py`

### Tests to add or update

- `tests/test_outcome_worktrees.py`
- `tests/test_ship_teardown_reconciliation.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/347
- Number: 347
- Created at: 2026-07-04T07:45:30.862319+00:00

