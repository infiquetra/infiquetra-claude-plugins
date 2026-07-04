---
title: "capability: cache-aware fan-out dispatch economics"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Govern fleet concurrency and reclaim leaked resources"
wave: wave-1
---

# capability: Cache-aware fan-out dispatch — stagger-warm release, within-run wave queue, fork_is_cheap propagation, and the 1-hour-TTL escalation gate

### Intent
Every current fan-out dispatch path (saga verify-panel, `/outcome` ready-frontier, the
workflow emitter batch, and the ideate/recon spawn sites) fires its members without asking
whether a warm prompt cache is available or being wasted. Give the fleet one shared,
cache-aware dispatch discipline instead of four independent blind ones: (1) stagger-warm
release so a batch's shared prefix is paid for once, not N times; (2) a reactive within-run
wave queue that dispatches the next ready unit the instant a resident frees a slot, instead
of a coordinator idle-polling; (3) the existing `fork_is_cheap` cost lever extracted out of
`outcome_dispatcher.py` and consulted by every spawn site, including the readonly-verifier
recon fan-out that today pays a cold cache miss unconditionally; and (4) engaging the
`{#worker-cache-scheduling}` decision's own named revisit-when for `/outcome`'s idle-poll
gaps, via a TTL-tight wave queue with an attended 1-hour-cache-TTL escalation as an explicit
spend decision, never a silent one.

## Problem Frame

**Stagger-warm waste.** A prompt-cache entry becomes readable only after the first response
begins streaming; N parallel requests sharing a prefix all pay the full uncached price if
fired simultaneously (Anthropic prompt-caching guidance, cited directly in the absorbed idea
`T4-F1-7`). This repo has at least three fan-out sites that share a prefix across their
batch members and fire them all at once today:
- Saga verify-panel dispatch, capped at `VERIFY_N_CAP = 7`
  (`plugins/saga/scripts/execution_spec.py:114`).
- `/outcome`'s ready-frontier release (`plugins/saga/scripts/outcome_spec.py:622`,
  `ready_frontier`).
- The workflow emitter's batch loop (same execution-spec.py fan-out machinery that backs
  `VERIFY_N_CAP`).

The fleet's own concurrency cap of 3 (`{#worker-cache-scheduling}` binding decision,
`docs/engineering-journal/DECISIONS.md:1950`) already bounds any given batch to a small
number in flight — small enough that firing member 1, letting it start streaming, and only
then releasing members 2..N is a strict win with no throughput cost.

**Idle-poll ritual, twice named as a sanctioned revisit condition.** The
`{#worker-cache-scheduling}` decision (`docs/engineering-journal/DECISIONS.md:1950`) settled
cache economics as "derive (segment+agent+tier) saga-side, reside team-side," and explicitly
reserved two revisit triggers: "named-teammate residency proves insufficient, **or idle-poll
justifies a formal wave queue**." That trigger has now fired twice, independently:
- Inside a single team-execution run — reproduced live in the fleet-ideation session itself
  (grounding brief section 7, pattern 9: "Subagents idle without delivering... also
  reproduced live in this very session"; recurring across 2 repos).
- Across `/outcome`'s cross-leaf ready-frontier advances, which can leave a resident leaf's
  cache dead well past the 5-minute ephemeral cache TTL before its next same-segment work
  arrives (absorbed idea `T4-F1-8`, citing `outcome_spec.py:622` `ready_frontier`).

**Fork cost lever is outcome-local only.** `fork_is_cheap()`
(`plugins/saga/scripts/outcome_dispatcher.py:310-318`) is today the only place in the fleet
that asks "is a warm fork cheaper than a fresh worker" — and it only gets asked inside
`/outcome` dispatch. The readonly-verifier verify-class spawns
(`plugins/saga/references/sandbox-spawn-sites.md`) and the ideate/recon fan-out that burned
350-450k tokens in under 20 minutes of pure recon (grounding brief section 7, singleton
finding) never consult it — every one of those spawns pays a cold cache miss regardless of
whether a warm, matching parent context was sitting right there.

**Rate-limit and no-concurrency-knob pain corroborate the theme.** The grounding brief's
recurring-pain synthesis independently surfaces "the emitter has no concurrency knob... KTD6
was aspiration, not machinery" and "6 of 7 agents failed on rate-limiting" across 3 repos
(grounding brief section 7, pattern 4) — the same unmanaged-fan-out shape this issue targets,
observed from the failure side rather than the cache-economics side.

## Binding decisions this builds on / must not violate

- `{#worker-cache-scheduling}` (`docs/engineering-journal/DECISIONS.md:1950`) — this issue
  is the decision's own sanctioned revisit-when firing, not a contradiction of it. The
  segment-boundary-derivation and team-side-residency architecture stays as-is; only the
  wave-queue and idle-poll handling are new.
- `{#readonly-verifier-fallback-ladder-325}` / verify-agent-git-checkout-clobber — verify-class
  spawns must keep readonly + worktree isolation. The fork-cost lever propagated into those
  spawn sites may only choose fork-vs-fresh; it must never relax sandbox posture.
- Saga's coordinator-level `ready_frontier` stays source-of-truth for leaf ordering — the
  within-run wave queue subordinates to it rather than introducing a competing scheduler.
- Halt-not-degrade (`/outcome` campaign decisions) — an unavoidable cache-gap in `/outcome`
  dispatch surfaces as an attended spend-yes gate, never a silent degrade.

## Definition of Done

A single merged PR (or small stack) that:
1. Adds a stagger-warm dispatch helper and wires it at the three shared-prefix fan-out sites:
   saga verify-panel dispatch (`execution_spec.py` VERIFY path), `/outcome` ready-frontier
   release (`outcome_spec.py` / `outcome/SKILL.md`), and the workflow emitter batch loop.
2. Adds a within-run reactive wave-queue scheduler to team-execution that dispatches the next
   ready segment the instant a resident worker frees a slot under the existing concurrency-3
   cap, subordinate to saga's `ready_frontier`.
3. Extracts `fork_is_cheap` (`outcome_dispatcher.py:310-318`) into a shared
   `plugins/saga/scripts/cache_lever.py` module and wires it into the readonly-verifier
   spawn-site guidance (`sandbox-spawn-sites.md`) and the recon fan-out dispatch path, without
   altering readonly/worktree sandbox posture at any of those sites.
4. Adds a TTL-tight wave-queue batching layer to `/outcome` dispatch that groups ready leaves
   within the 5-minute ephemeral cache window where possible, and on an unavoidable gap,
   surfaces a 1-hour `ttl:"1h"` cache-TTL escalation as an attended spend-yes gate (not a
   silent choice).
5. Adds a `docs/engineering-journal/DECISIONS.md` entry recording that this work engages the
   `{#worker-cache-scheduling}` revisit-when, with rationale and a fresh revisit-when of its
   own.
6. All Acceptance Criteria below pass under `uv run pytest`, and full CI parity
   (`ruff`, `mypy`, `bandit` per repo CLAUDE.md) stays green.

### Acceptance criteria
- [ ] AC1 (stagger-warm, `T4-F1-7`). Given a batch of 3+ dispatch targets sharing a common
  prefix at any of the three wired sites (verify-panel, `/outcome` frontier release,
  workflow emitter), batch members 2..N are released only after member 1 has begun
  streaming; a test asserts release-order and a run's cost ledger shows the shared prefix
  charged once, not N times. Check: `uv run pytest tests/test_execution_spec.py -k
  stagger_warm` (or equivalent per wired site) passes.
- [ ] AC2 (reactive wave queue, `T4-F2-5`). Given a team-execution run with more ready segments
  than free concurrency slots, a resident worker completing dispatches the next ready segment
  immediately, without any coordinator poll loop, and the concurrency-3 cap is never exceeded.
  Check: `uv run pytest tests/test_team_execution_wave_queue.py -k free_slot_dispatch` and
  `-k cap_enforced` both pass.
- [ ] AC3 (fork-cost propagation, `T4-F6-5`). Given a readonly-verifier or recon spawn candidate
  whose model+system+tools match a warm parent but whose candidacy is past the cache TTL,
  `cache_lever.fork_is_cheap` (or its call site) does not recommend it as a fork; a passing
  candidate within TTL and full signal match is recommended as a fork. Check: `uv run pytest
  tests/test_cache_lever.py -k ttl_expired_not_forked` and `-k all_signals_match_forked` both
  pass, and a separate assertion confirms the readonly+worktree sandbox posture at the
  verify-class spawn site is unchanged by the lever's answer.
- [ ] AC4 (idle-poll wave queue + escalation gate, `T4-F1-8`). Given an `/outcome` run with an
  induced greater-than-5-minute gap in the ready frontier, the wave queue either batches the
  affected leaves within the ephemeral cache window, or halts and surfaces the 1-hour-TTL
  escalation as an attended yes/no spend decision (never silently absorbing the doubled write
  cost). Check: `uv run pytest tests/test_outcome_wave_queue.py -k induced_frontier_gap`
  passes and asserts one of the two named outcomes.
- [ ] AC5 (decision journal). `docs/engineering-journal/DECISIONS.md` contains a new entry
  recording that this work engages the `{#worker-cache-scheduling}` revisit-when, with its
  own revisit-when condition. Check: `grep -n "revisit-when" docs/engineering-journal/DECISIONS.md`
  shows the new entry.

### Out-of-scope / non-goals
- In scope: the four mechanisms above, at the four cited spawn/dispatch sites only.
- Out of scope: changing the segment-boundary derivation or team-side residency architecture
  settled by `{#worker-cache-scheduling}` — this issue only adds wave-queue/stagger-warm
  machinery on top of it.
- Out of scope: relaxing readonly/worktree sandbox posture for any verify-class or recon
  spawn — the fork-cost lever chooses fork-vs-fresh only, never sandbox posture.
- Out of scope: introducing a new scheduler that competes with saga's coordinator-level
  `ready_frontier` — the within-run wave queue is explicitly subordinate to it.
- Out of scope: raising the global concurrency-3 cap, or building a standing/scheduled
  cache-hit-rate measurement harness (no such ask was made for this theme).
- Out of scope: any new plugin — all four mechanisms land inside existing saga/team-execution
  surface area (`{#plugin-portfolio-groom-17-to-7}` applies; no new plugin directory).

## Grounding References

- `T4-F1-7` (primary) — stagger-warm parallel dispatch. Basis: Anthropic prompt-caching
  guidance (cache entry readable only after first stream begins) + fan-out sites verified in
  grounding brief section 1 (`VERIFY_N_CAP=7`, unbounded team-execution/outcome/emitter
  fan-out) + intake concurrency-cap-3.
- `T4-F2-5` (facet) — within-run wave queue. Basis: `docs/engineering-journal/DECISIONS.md:1970-1971`
  revisit-when ("or a single team-execution run shows enough internal idle-poll to justify a
  formal within-run wave queue"); grounding brief section 7 pattern 9 (idle subagents,
  reproduced live in the ideation session); plan R10 (segment frontier subordinate to
  `outcome_spec.py:622` `ready_frontier`).
- `T4-F6-5` (facet) — fork_is_cheap propagation. Basis: `outcome_dispatcher.py:310-318`
  (`fork_is_cheap` is outcome-local only); grounding brief section 7 ("350-450k tokens in
  <20min pure recon fan-out"); binding decision `{#readonly-verifier-fallback-ladder-325}`
  (verify spawns keep readonly+worktree isolation — the lever chooses fork-vs-fresh only).
- `T4-F1-8` (facet) — 1-hour-TTL wave queue for `/outcome` idle-poll gaps. Basis:
  `{#worker-cache-scheduling}` revisit-when (grounding brief section 2, verbatim: "named-teammate
  residency proves insufficient, or idle-poll justifies a formal wave queue"); 1-hour TTL
  cache economics (`ttl:"1h"`, 2x write vs 1.25x, needs >=3 reads to pay off) from Anthropic
  prompt-caching guidance; `/outcome` ready-frontier idle-poll path
  (`outcome_spec.py:622` `ready_frontier`).

## Recommended Executor Profile

- Model: sonnet
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution
- External LLM posture: none
- Justification: mechanical, well-scoped propagation of an existing pattern (stagger-warm,
  fork-cost lever) into four named sites, plus one bounded new scheduler subordinate to an
  existing frontier primitive. No architectural judgment call above what the binding
  decisions already settled — sonnet at high effort is sufficient; no case for opus.

## Release-Surface Checklist

This issue changes saga and team-execution plugin behavior (new dispatch module, new
scheduler, new decision-journal entry), so the following must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new
      `cache_lever.py` module and stagger-warm/wave-queue behavior changes.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
      within-run wave-queue scheduler.
- [ ] `.claude-plugin/marketplace.json` — synced version/metadata for both plugins.
- [ ] `plugins/saga/CHANGELOG.md` and `plugins/team-execution/CHANGELOG.md` — entries
      describing the new dispatch economics.
- [ ] Any version/metadata drift-guard tests updated to reflect the new versions.
- [ ] `plugins/saga/references/sandbox-spawn-sites.md` updated to reference the shared
      `cache_lever.py` fork-vs-fresh check at verify-class spawn sites.

## Files Expected to Change

- `plugins/saga/scripts/execution_spec.py` — stagger-warm dispatch helper wiring at the
  VERIFY path.
- `plugins/saga/scripts/outcome_spec.py` — stagger-warm wiring at `ready_frontier` release;
  TTL-tight wave-queue batching + 1-hour-TTL escalation gate.
- `plugins/saga/scripts/outcome_dispatcher.py` — `fork_is_cheap` extraction point (moves to
  `cache_lever.py`, re-exported or re-imported here).
- `plugins/saga/scripts/cache_lever.py` — new shared fork-cost-lever module.
- `plugins/saga/references/sandbox-spawn-sites.md` — guidance update referencing
  `cache_lever.py` at verify-class spawn sites.
- `plugins/saga/skills/outcome/SKILL.md` — wave-queue batching + escalation-gate behavior
  documentation.
- `plugins/team-execution/skills/team-execution/` (dispatch/scheduling reference or script) —
  within-run reactive wave-queue scheduler.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates.
- `docs/engineering-journal/DECISIONS.md` — new revisit-when-engagement entry.
- `tests/test_execution_spec.py`, `tests/test_outcome_wave_queue.py`,
  `tests/test_team_execution_wave_queue.py`, `tests/test_cache_lever.py` — new/updated tests.

## Tests to Add or Update

- `tests/test_execution_spec.py -k stagger_warm` — batch member 2..N release gated on member
  1 streaming; ledger shows shared prefix charged once.
- `tests/test_outcome_wave_queue.py -k induced_frontier_gap` — induced greater-than-5-minute
  frontier gap either batches within window or halts for the spend decision.
- `tests/test_team_execution_wave_queue.py -k free_slot_dispatch` and `-k cap_enforced` —
  resident-completes-dispatches-next-ready-segment without a poll; concurrency-3 cap held.
- `tests/test_cache_lever.py -k ttl_expired_not_forked` and `-k all_signals_match_forked` —
  the four boolean signals (model/system/tools match, within TTL) gate the fork
  recommendation correctly; readonly+worktree invariant unchanged.

### Verification
```bash
uv run pytest tests/test_execution_spec.py tests/test_outcome_wave_queue.py \
  tests/test_team_execution_wave_queue.py tests/test_cache_lever.py -v
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```
Expected: all green; stagger-warm/wave-queue/fork-lever tests pass; no readonly/worktree
sandbox regression at verify-class spawn sites.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json` (ids `T4-F1-7`,
  `T4-F2-5`, `T4-F6-5`, `T4-F1-8`)
- Source type: ideation survivor consolidation
- Source title: Cache-aware fan-out dispatch economics

### Context library links

_none_

### Files expected to change

- `plugins/saga/references/sandbox-spawn-sites.md`
- `outcome/SKILL.md`
- `plugins/saga/scripts/cache_lever.py`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`

### Tests to add or update

- `tests/test_cache_lever.py`
- `tests/test_execution_spec.py`
- `tests/test_outcome_wave_queue.py`
- `tests/test_team_execution_wave_queue.py`

### Objective

"Govern fleet concurrency and reclaim leaked resources"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/352
- Number: 352
- Created at: 2026-07-04T07:46:54.316856+00:00

