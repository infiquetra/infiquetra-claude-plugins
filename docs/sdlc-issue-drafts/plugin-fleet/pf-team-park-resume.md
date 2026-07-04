---
title: "capability: park & resume a running team across sessions"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-3
objective: Expand saga+deploy capability breadth (misc/quick-wins)
---

# capability: park & resume a running team across sessions

## Objective

Expand saga+deploy capability breadth (misc/quick-wins).

### Intent
Give a running team-execution run enough persisted state that it can be deliberately parked —
session killed, machine rebooted, days pass — and later resumed in a fresh session at the same
point, instead of the operator either leaving the session open indefinitely or re-spawning the
whole Phase B orchestration from scratch.

Today team-execution's Phase B state is session-resident, not durably parkable:

- Segment/worker state lives in named, `run_in_background` resident teammates spawned per segment
  (`plugins/team-execution/skills/team-execution/SKILL.md:308`, "Persistent Resident Workers
  (R3): Spawn exactly one named, persistent teammate per resident worker (segment)... rather than
  spawning anonymous workers per unit."). A killed session has no defined way to reconstitute those
  named teammates or know which segment each was mid-unit on.
- The within-run segment frontier (`plugins/team-execution/skills/team-execution/SKILL.md:307`,
  "This within-run segment frontier is strictly subordinate to saga's coordinator-level
  `ready_frontier`") and reviewer-consensus progress
  (`plugins/team-execution/skills/team-execution/SKILL.md:340`, Step B2) are tracked in-session;
  neither has a documented on-disk schema for suspend/restore.
- Worker provenance manifests are written at segment/unit exit
  (`plugins/team-execution/skills/team-execution/SKILL.md:319`, "Each worker writes a provenance
  manifest at segment/unit exit") and validator evidence is written per validator run
  (`plugins/team-execution/skills/team-execution/references/validator-execution-order.md:27`), but
  neither is currently read back to reconstruct an interrupted run's status — they are
  write-only artifacts today.
- team-execution has no `park` or `resume` verb anywhere in its skill surface (verified absent:
  `grep -rn "park\|pause\|resume" plugins/team-execution/skills/team-execution/SKILL.md` and
  `plugins/team-execution/skills/team-execution/references/*.md` returns no hits). The only
  existing park/resume-shaped precedent in the fleet is one level up, at the coordinator layer:
  saga's `/outcome resume <id>` reconstructs live DAG status from spec + store even after the
  local cache is wiped (`plugins/saga/skills/outcome/SKILL.md:52`, "`resume <id>` | reconstruct
  live status from spec + store (works even if the cache was wiped)"), and `/outcome reconcile`
  detects board↔saga drift on wake against the board-sync ledger
  (`plugins/saga/skills/outcome/SKILL.md:57`, `{#295}`, landed in commit 6b33eba "feat(saga):
  board↔saga reconciliation on resume (#295) (#330)"). That pattern exists for the
  coordinator-level DAG; it has no counterpart inside a single team-execution run's own Phase B
  state.
- Session mining recorded parked/interrupted resident-worker sessions and background-session
  write-routing failures as a recurring cross-repo pain
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, recurring-pain theme: "Subagents idle
  without delivering; stale idle notifications — coordinator must detect and re-ping" and
  "Background-session/worktree write-routing failures — Edit fails after worktree removal;
  Read-first dance"), i.e. the fleet already has adjacent evidence that session-resident state
  is fragile across interruption, without a dedicated park/resume mechanism to address it.

This capability adds explicit `park` and `resume` verbs to team-execution plus a durable
park-state schema, so a deliberately-parked run can be picked back up in a new session at the
same segment/unit boundary, with per-member status and reviewer-consensus progress intact, and
without leaving stale leases or orphaned worktrees behind.

## Problem Frame

- **No durable suspend point exists inside Phase B.** Resident-worker identity, segment
  position, and consensus progress are session-resident constructs
  (`plugins/team-execution/skills/team-execution/SKILL.md:307-311`, R3/R4/R8/R10/R11); none of
  them are currently serialized to a form a fresh session can rehydrate from.
- **The write-only manifest/evidence surface is the natural substrate, but isn't read back
  today.** Worker provenance manifests (`SKILL.md:319`) and validator evidence records
  (`references/validator-execution-order.md:27`) already capture per-segment/per-validator state
  at exit time; a park/resume mechanism can reuse this substrate as its serialization surface
  rather than inventing a second one, but currently nothing reads them back into a
  reconstituted run.
- **Precedent exists one layer up, not at this layer.** The coordinator-level `/outcome resume`
  and board↔saga reconciliation-on-wake pattern (`plugins/saga/skills/outcome/SKILL.md:52`,
  `:57`; commit 6b33eba, #295/#330) is the fleet's only shipped park/resume-shaped mechanism.
  This capability is the equivalent mechanism scoped one level down, inside a single
  team-execution run, and should reuse the same reconciliation shape (detect drift between the
  parked state and current board/saga state on resume) rather than inventing a divergent
  protocol.
- **Leases and worktrees must not leak across a park.** team-execution already relies on
  cross-worktree evidence records (`plugins/team-execution/skills/team-execution/references/
  worker-manifest.md:4`, "typed, cross-worktree evidence record for a delegated output") and
  same-cwd resident teammates plus linked-worktree children
  (`plugins/team-execution/skills/team-execution/references/artifact-pointers.md:94`). The
  grounding brief separately records **15 stale abandoned saga worktrees** found in `.worktrees/`
  as a live hygiene defect inflating repo size 10x+
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, §4: "Hygiene find: 15 stale abandoned
  saga worktrees in `.worktrees/` inflating repo 10×+ → direct evidence theme 6 (teardown/
  reclamation), same disease as team-execution's missing Step B8."). A park/resume mechanism
  that doesn't explicitly release or re-acquire worktree leases would add a second, more direct
  path to that same disease.
- **Binding decisions engaged:** `{#worker-cache-scheduling}` ("Cache economics theme settled
  architecture: derive (segment+agent+tier) saga-side, reside team-side; segment boundary =
  plugin directory") constrains where park-state may live (team-side, segment-boundary-scoped);
  this capability must serialize state consistent with that boundary, not invent a new
  segmentation scheme. `{#readonly-verifier-fallback-ladder-325}` +
  `{#verify-agent-git-checkout-clobber}` constrain any verify-class spawn used to validate a
  resumed run's state (readonly profile + worktree isolation) if this capability's resume path
  spawns a verification check.

### Out-of-scope / non-goals
- **In scope:** a `park` verb (or equivalent doc-driven step) that serializes roster, segment
  position, per-member/reviewer-consensus status, provenance-manifest and validator-evidence
  pointers, and worktree/lease handles to a durable on-disk park-state schema; a `resume` verb
  that rehydrates a parked run into a fresh session at the same segment/unit boundary; explicit
  lease release-or-clean-reacquire semantics on park and resume; a reconciliation step on resume
  that reuses the existing board-saga reconciliation pattern (`{#295}`/commit 6b33eba) rather
  than inventing a new drift-detection shape; tests proving park→kill-session→resume continuity,
  reconciliation reuse, and no orphaned worktrees.
- **Non-goal:** building a new coordinator-level DAG-resume mechanism — that already exists as
  `/outcome resume`/`reconcile` (`plugins/saga/skills/outcome/SKILL.md:52,57`) and is out of
  scope to re-implement; this capability is the leaf-run-internal counterpart only.
- **Non-goal:** changing the segment-boundary cache-economics architecture itself
  (`{#worker-cache-scheduling}`) — this capability serializes state consistent with that existing
  boundary, it does not redesign it.
- **Non-goal:** general worktree hygiene/reclamation cleanup for pre-existing stale worktrees
  (the 15 found in the grounding brief) — that is tracked separately as a teardown/reclamation
  concern; this issue only ensures parked-team worktrees specifically don't join that pile.
- **Non-goal:** automatic/implicit parking (e.g. on idle timeout or crash) — v1 covers only
  deliberate, operator-invoked park; automatic park-on-crash detection is a future extension.

## Definition of Done

Merged PR that:

- Adds `park` and `resume` verbs (documented in
  `plugins/team-execution/skills/team-execution/SKILL.md` and/or a new
  `plugins/team-execution/skills/team-execution/references/park-resume.md`) plus a park-state
  schema (roster, segment position, per-member status, reviewer-consensus progress, provenance-
  manifest/validator-evidence pointers, worktree/lease handles) serialized under a
  `.claude/`-ignored, team-side location consistent with `{#worker-cache-scheduling}`'s
  segment-boundary-scoped residency.
- Implements the resume path so a parked run continues from its recorded segment/unit boundary
  in a brand-new session, without re-spawning already-completed segments.
- Implements the resume-time reconciliation step reusing the existing board-saga reconciliation
  pattern (`plugins/saga/skills/outcome/SKILL.md:57`, `{#295}`).
- Implements explicit lease handling: park releases or durably records worktree/session leases;
  resume either reuses the still-valid lease or cleanly re-acquires one — no orphaned worktrees
  result from a parked-then-resumed or parked-then-abandoned run.
- Ships a test suite exercising: park mid-segment → kill session → resume in a fresh session →
  team continues from the recorded boundary; resume-time reconciliation firing against a
  deliberately drifted board/saga state; and a worktree-orphan check after a park/resume cycle.

### Acceptance criteria
- [ ] Parking a team mid-segment, killing the session, and resuming in a fresh session continues
      execution from the recorded segment/unit boundary — not from segment zero. Check:
      `uv run pytest tests/test_team_execution_park_resume.py -k park_mid_segment_resumes_at_boundary` → passes.
- [ ] Per-member (resident worker) status and reviewer-consensus progress recorded at park time
      are intact and readable immediately after resume. Check:
      `uv run pytest tests/test_team_execution_park_resume.py -k resume_preserves_member_and_consensus_status` → passes.
- [ ] The resume path invokes the existing board-saga reconciliation pattern (`{#295}`) rather
      than a divergent drift-detection mechanism, and surfaces a drift finding when board/saga
      state has moved since park. Check:
      `uv run pytest tests/test_team_execution_park_resume.py -k resume_reuses_board_saga_reconciliation` → passes.
- [ ] Worktree/session leases held by a parked team are either still valid on resume or are
      cleanly re-acquired; no orphaned worktree remains after a park→resume cycle or a
      park→abandon (never resumed) cycle. Check:
      `uv run pytest tests/test_team_execution_park_resume.py -k park_resume_no_orphaned_worktrees` → passes.
- [ ] Park-state schema is versioned/validated on read; a resume attempt against a malformed or
      schema-mismatched park-state file fails loud rather than silently degrading (halt-not-
      degrade). Check:
      `uv run pytest tests/test_team_execution_park_resume.py -k resume_rejects_malformed_park_state` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification
```bash
# Unit + integration tests for park/resume
uv run pytest tests/test_team_execution_park_resume.py -v

# Full repo gate (CI parity)
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the park→kill→resume test demonstrates continuation from the recorded
boundary with member/consensus status intact; the reconciliation test demonstrates reuse (not
reinvention) of the `{#295}` board-saga pattern; the worktree-orphan test shows zero leaked
worktrees after both a resumed and an abandoned park.

### Files expected to change
Indicative only — exact set is `/plan`'s to determine.

- `plugins/team-execution/skills/team-execution/SKILL.md` — `park`/`resume` verb documentation.
- `plugins/team-execution/skills/team-execution/references/park-resume.md` (new) — park-state
  schema, lease-handling contract, resume reconciliation contract.
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md` — read-back
  contract for provenance manifests during resume, if extended.
- `plugins/team-execution/skills/team-execution/references/validator-execution-order.md` —
  read-back contract for validator evidence during resume, if extended.
- `tests/test_team_execution_park_resume.py` (new) — park/resume continuity, reconciliation
  reuse, and orphan-worktree tests.
- `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates for the new verbs and schema.

## Out-of-scope / non-goals

- Re-implementing coordinator-level DAG resume (`/outcome resume`/`reconcile` already exists).
- Redesigning the segment-boundary cache-economics architecture (`{#worker-cache-scheduling}`).
- General cleanup of pre-existing stale worktrees found in the grounding brief's hygiene sweep.
- Automatic/implicit park on idle-timeout or crash detection — v1 is deliberate, operator-invoked
  park only.

## Release-surface checklist

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` version bumped for new `park`/`resume`
      verbs and park-state schema.
- [ ] `.claude-plugin/marketplace.json` entry for `team-execution` updated to match.
- [ ] `plugins/team-execution/CHANGELOG.md` entry added describing the new capability.
- [ ] Any version/metadata drift-guard tests updated to reflect the new verb/schema surface.

## Recommended executor profile

- **Model:** sonnet
- **Effort:** xhigh — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM posture:** none
- **Justification:** This is structural, cross-cutting state-machine work — serializing and
  faithfully rehydrating in-flight segment/consensus/lease state across a session boundary, with
  a hard correctness bar (no silent state loss, no orphaned worktrees, halt-not-degrade on
  malformed state) and a reuse constraint against an existing coordinator-level pattern
  (`{#295}`). That correctness surface and cross-file reconciliation reasoning warrant `xhigh`
  effort even though the executing model is sonnet, matching the fleet's existing tier heuristic
  for structural-but-non-adversarial work (`plugins/saga/skills/plan/SKILL.md:296-300`). No
  external LLM is needed; this is Claude-authored, Claude-verified mechanism work per
  `{#external-engines-never-gatekeepers}`.

## Handoff maturity

requirements-ready

## Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Grounding References

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json` (idea `T6-F1-6`) and
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`.
- Source type: ideation (issue-map)
- Source title: Park & resume a running team across sessions

### Context library links

_none_

### Tests to add or update

- `tests/test_team_execution_park_resume.py`

### Objective

Expand saga+deploy capability breadth (misc/quick-wins)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/437
- Number: 437
- Created at: 2026-07-04T08:13:59.922303+00:00

