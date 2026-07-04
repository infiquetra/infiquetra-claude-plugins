---
title: "capability: TTL-lease broker for fleet concurrency slots, worktree/teardown reclamation, and orphan write-fencing"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Govern fleet concurrency and reclaim leaked resources"
wave: wave-1
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: xhigh, backend: team-execution, external_llm: none}
---

# capability: TTL-lease broker for fleet concurrency slots, worktree/teardown reclamation, and orphan write-fencing

### Intent
Ship one file-backed TTL-lease broker (`plugins/saga/scripts/lease_broker.py`, proposed path) that
every fleet spawn site acquires before dispatching work. A lease simultaneously *is* a concurrency
slot, names the worktree/branch it holds, and carries a monotonic fencing token for the write path.
Expiry is the single event that frees the slot, arms the worktree reaper, and invalidates the token
so a stale retry cannot clobber a live retry's evidence. Three fleet diseases the grounding brief
documents separately — unbounded cross-workflow fan-out, 15 stale abandoned worktrees, and an orphan
process overwriting a passing retry's evidence with its own stale result — collapse into one
invariant: **no resource (agent slot, worktree, write) exists outside a live lease.**

## Problem / Motivation

- **Per-workflow caps compose additively, not as a fleet ceiling.** `plugins/saga/scripts/execution_spec.py:114`
  defines `VERIFY_N_CAP = 7`, the fleet's only orchestration-level cap — and it bounds exactly one
  spawn site (the verify panel via `VerifyPanelSpec.validate()`, `execution_spec.py:352-368`). Nothing
  stops a saga emit and a concurrent team-execution reviewer fan-out from each independently obeying
  their own local cap while jointly exceeding the operator's stated invariant, "maximum 3 concurrent
  agents at any moment, across all phases" (survivor `T13-F1-4`, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json`).
  The grounding brief's session-mining synthesis independently surfaces the same failure as its
  fourth-ranked cross-repo pattern: "Rate-limit fan-out kills — '6/7 agents failed on rate-limiting';
  'the emitter has no concurrency knob... KTD6 was aspiration, not machinery'" across three repos
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §7 item 4).
- **Worktree lifecycle is already lease-shaped but scoped to one outcome, not the fleet.**
  `plugins/saga/scripts/outcome_worktrees.py:53` defines `WORKTREE_CAP = 4` and enforces "bounded
  proliferation (R15)" with a reaper (`reap_worktree`, `outcome_worktrees.py:254`) and an explicit
  "worktree-removed negative terminal (R32)" — but every invariant in that module is scoped to one
  running `/outcome`'s registry, not to the fleet-wide set of `.worktrees/` entries a saga emit, a
  team-execution run, and a manual clone can each create independently. The grounding brief records
  direct evidence this scope gap is live today: "15 stale abandoned saga worktrees in `.worktrees/`
  inflating the repo 10×+" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4, echoed at §8).
- **Orphan writes clobber live evidence with no fencing today.** The grounding brief's research
  synthesis names, as a standalone singleton finding, "probe script overwriting a FAIL evidence
  artifact with a later PASS" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §7) — an orphan
  process that outlived its intended scope still had write access to a path a fresher retry was also
  writing, corrupting the audit chain-of-custody. Nothing in the fleet today rejects a write from a
  process whose lease has expired; only vigilance (an operator noticing the mismatched result) would
  catch it.
- **The three failures are one mechanism, already consolidated at ideation time.** Absorbed idea
  `H-F4-3` names this directly: "Do not extend `VERIFY_N_CAP` into a global constant — constants
  govern one spawn site each and teach nothing... leases carry TTLs and name the resources held (agent
  slot, worktree path); expiry drives two second-order wins for free: rate-limit governance and
  stale-resource reclamation" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json`). The
  primary hybrid idea `G-hybrids-2` extends this with the write-fencing facet: "expiry simultaneously
  frees the slot, arms the reaper for the worktree, invalidates the token so the orphan cannot clobber
  the retry's evidence" (`docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json`).
- **Teardown has no owning step today.** `plugins/team-execution` has no equivalent of a "Step B8"
  that stops idle teammates and reclaims worktrees when a team run completes (absorbed seed `S-32`,
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`); the same stale-worktree evidence
  above is this seed's direct proof.
- **Background/worktree write-routing already fails ungracefully.** Absorbed seed `S-12` names the
  reproducible failure mode directly: an `Edit` after worktree removal fails instead of erroring
  cleanly, forcing a manual read-first dance (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`;
  grounding brief §5 pattern 8, three repos). A lease-aware write path turns this into the fencing
  check this issue ships rather than an ad hoc retry dance per call site.

## Definition of Done

Merged PR(s) delivering:

1. A `lease_broker.py` module (proposed `plugins/saga/scripts/lease_broker.py`) implementing
   `acquire(kind, owner, ttl_s, resource_ref=None) -> Lease`, `renew(lease_id)`, `release(lease_id)`,
   and `sweep()`, backed by an `flock`-guarded on-disk registry (mirrors the
   read-modify-write-under-lease pattern already used by `outcome_worktrees.py`'s own registry,
   `plugins/saga/scripts/outcome_worktrees.py:22-24`).
2. Every lease carries: a fleet-wide concurrency slot, an optional named resource
   (`worktree_path` / `branch`), a monotonic fencing token, and a TTL; expiry is derived on read
   (no committed "expired" status field written elsewhere — honors the `/outcome` campaign's
   derived-on-read binding decision, `plugins/saga/skills/outcome/SKILL.md:35`).
3. Adoption at every fan-out spawn site enumerated in
   `plugins/saga/references/sandbox-spawn-sites.md` (the saga emitter's verify-panel/verify-loop
   sites in `execution_spec.py`, team-execution's reviewer fan-out, `/outcome` leaf dispatch) plus
   the engine bridges named in the grounding brief §1 — each acquires a lease before spawning and
   releases (or lets it expire) on completion.
4. `VERIFY_N_CAP` (`execution_spec.py:114`) becomes a broker policy value (default 3, matching the
   operator's stated fleet-wide invariant) rather than a per-spawn-site literal; the existing
   `VerifyPanelSpec.validate()` soft-warn/hard-cap behavior (`execution_spec.py:352-368`) is preserved,
   now sourced from the broker.
5. A reclamation sweep (`lease_broker.py --sweep` or equivalent CLI entry point) that finds expired
   worktree-holding leases and invokes the existing `reap_worktree` path
   (`plugins/saga/scripts/outcome_worktrees.py:254`) rather than reimplementing worktree teardown —
   the broker generalizes the *cap and reaper trigger* fleet-wide; it reuses the existing per-outcome
   removal mechanics.
6. A teardown adoption point in team-execution (the absorbed `S-32` "Step B8" gap) that releases a
   team's leases and invokes the sweep when a team run reaches a terminal state.
7. A write-fencing check consulted by the worktree write path: a write whose caller presents an
   expired or superseded fencing token is rejected with a typed, loud error (never silently applied),
   turning both the orphan-clobber failure (grounding brief §7 singleton) and the
   Edit-after-worktree-removal failure (absorbed `S-12`) into the same clean, typed rejection.
8. Release-surface updates (see checklist below) reflecting the new broker as a fleet-behavior
   change.

Verify: a fleet-cap contention test (concurrent acquirers against a capped broker cannot sum past the
cap); an expired-lease write-fencing test (a write presenting a stale token is rejected, not silently
applied); a reclaim-sweep test that reproduces the 15-stale-worktree condition against a fixture and
confirms zero orphaned worktrees survive a sweep; a derived-on-read registry test (no lease "status"
field is ever committed independently of TTL arithmetic).

### Acceptance criteria
- [ ] **AC1 (concurrency cap, `T13-F1-4` / `H-F4-3`).** Two independently-driven concurrent acquirers
  (simulating a saga emit and a team-execution reviewer fan-out) against a 3-slot broker cannot both
  succeed past the cap; the (N+1)th acquirer blocks or fails until a slot is released or expires.
  Check: `uv run pytest tests/test_lease_broker.py -k fleet_cap_contention` → passes (asserts at most 3
  concurrently-held leases across two independent caller identities).
- [ ] **AC2 (session-scoped ceiling, `T13-F5-7`).** Within one session, two same-session fan-outs (an
  `/outcome` leaf dispatch and an ad hoc team-execute) share the same session-scoped ceiling rather
  than each getting an independent full cap.
  Check: `uv run pytest tests/test_lease_broker.py -k session_scoped_ceiling` → passes.
- [ ] **AC3 (write-fencing, `G-hybrids-2`).** A write presenting an expired or already-superseded fencing
  token is rejected with a typed error before it touches the target path; a write presenting the
  current live token for its resource succeeds.
  Check: `uv run pytest tests/test_lease_broker.py -k write_fencing_rejects_stale_token` → passes.
- [ ] **AC4 (orphan-clobber reproduction, `G-hybrids-2`).** Reproducing the grounding-brief singleton
  scenario — an orphan process holding an expired lease attempts to overwrite a fresher retry's
  evidence artifact — is rejected by the fencing check rather than silently applied.
  Check: `uv run pytest tests/test_lease_broker.py -k orphan_clobber_reproduction` → passes.
- [ ] **AC5 (worktree reclamation, `H-F4-3` / `S-32`).** A fixture reproducing 15 stale worktree-holding
  leases whose TTL has expired all get swept: the sweep releases the slot, invokes
  `reap_worktree` (`outcome_worktrees.py:254`) for each, and zero stale entries remain.
  Check: `uv run pytest tests/test_lease_broker.py -k reclaim_sweep_stale_worktrees` → passes.
- [ ] **AC6 (team teardown, `S-32`).** Completing a team-execution run releases all leases the team held
  and triggers a sweep; no orphaned teammates or worktrees survive the run's terminal transition.
  Check: `uv run pytest tests/test_team_execution_teardown.py -k lease_release_on_team_terminal` →
  passes.
- [ ] **AC7 (write-routing robustness, `S-12`).** An `Edit` attempted after the target worktree has been
  removed out-of-band fails with an explicit, typed error identifying the missing worktree, never a
  silent write to the wrong path and never a bare stack trace requiring a manual read-first dance.
  Check: `uv run pytest tests/test_lease_broker.py -k edit_after_worktree_removal_fails_loud` → passes.
- [ ] **AC8 (derived-on-read registry, `/outcome` campaign binding decision).** The lease registry never
  writes an independent "expired" status field; expiry is always computed from `acquired_at + ttl_s`
  versus current time at read time.
  Check: `uv run pytest tests/test_lease_broker.py -k no_committed_expiry_field` → passes (asserts the
  registry schema carries no status/expired key, only timestamps + ttl).
- [ ] **AC9 (spawn-site coverage, `T13-F1-4`).** Every spawn site enumerated in
  `plugins/saga/references/sandbox-spawn-sites.md` acquires a lease before dispatching; a fixture that
  adds an unguarded `parallel([...])`/spawn call outside the broker fails a conformance test.
  Check: `uv run pytest tests/test_lease_broker_conformance.py -k all_spawn_sites_acquire_lease` →
  passes; injecting an unguarded spawn site turns it red.
- [ ] **AC10 (`VERIFY_N_CAP` sourced from broker policy).** `execution_spec.py`'s verify-panel cap is
  derived from the broker's fleet policy value rather than the standalone `VERIFY_N_CAP` literal, and
  the existing soft-warn-then-hard-cap behavior (`execution_spec.py:352-368`) is unchanged in
  observable behavior.
  Check: `uv run pytest tests/test_execution_spec.py -k verify_panel_cap` → passes unchanged, now
  reading the derived value; `grep -n "^VERIFY_N_CAP = 7" plugins/saga/scripts/execution_spec.py`
  returns no match (replaced by a broker-policy reference).

### Out-of-scope / non-goals
- **Rate-limit HTTP-level retry/backoff is out of scope.** This issue governs admission (whether a
  slot exists to spawn into), not 429 handling once a call is in flight; grounding brief §1 notes
  429-level handling exists only in unifi/mission-control HTTP clients today and is a distinct,
  separately-scoped capability.
- **Does not redesign team-execution's reviewer/validator dispatch mechanics.** The teardown adoption
  point (AC6) releases leases and triggers a sweep at a team's terminal transition; it does not touch
  consensus protocol, validator ordering, or reviewer selection.
- **Does not backfill worktree isolation onto backends that lack it today.** `SANDBOX_ENFORCEABLE_BY_BACKEND`
  (`execution_spec.py:105-109`) already documents that `team-execution` enforces neither restrictive
  sandbox axis; this issue's write-fencing check applies wherever a worktree-scoped write path exists
  today and does not add worktree isolation to backends where none exists.
- **Does not relax the existing sandbox-spawn-site mandate for verify/review-class agents.** The
  `saga:readonly-verifier` + `isolation: "worktree"` requirement (and its documented fallback ladder)
  stays exactly as-is; the broker's spawn-site conformance test (AC9) is a sibling guard alongside it,
  not a replacement.
- **Does not re-implement worktree removal mechanics.** The reclamation sweep (DoD item 5) calls the
  existing `reap_worktree` (`outcome_worktrees.py:254`); it does not fork or duplicate that logic.
- **Does not extend the broker to non-fleet resources** (e.g. database connections, external API
  quota) in v1 — scope is agent concurrency slots, worktrees/branches, and the write-fencing token
  tied to those two resource kinds only.

## Grounding References

| Absorbed idea | Role | Basis |
|---|---|---|
| `G-hybrids-2` | primary | `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json` — merges `H-F4-3` (concurrency+teardown are both leases), `T6-F3-1` (ephemeral resources as leases with a reaper), `T15-F5-6` (fencing tokens reject stale writes), and `T13-F1-4` (fleet-wide lease file) into one primitive; grounding brief §4 ("15 stale abandoned saga worktrees") and §7 (rate-limit pattern + orphan-clobber singleton) cited directly in its own basis. |
| `H-F4-3` | dedup-merged | Grounding brief §1 (`VERIFY_N_CAP = 7`, `execution_spec.py:114`, "the only orchestration-level cap"; team-execution reviewer fan-out, `/outcome` leaf dispatch, and engine bridges are unbounded); §4 (15 stale worktrees); §7 pattern 4 (rate-limit fan-out kills, 3 repos). |
| `S-12` | dedup-merged | Grounding brief §5 pattern 8: "Background-session/worktree write-routing failures — Edit fails after worktree removal; Read-first dance" (3 repos). |
| `S-32` | dedup-merged | Operator statement "shut down agent teams when no longer needed"; grounding brief §4 stale-worktree teardown evidence and §8 theme 6 teardown gap. |
| `T13-F1-4` | facet | Operator invariant "maximum 3 concurrent agents at any moment, across all phases" (survivor basis, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json`); names `plugins/saga/references/sandbox-spawn-sites.md` as the spawn-site enumeration this issue's conformance test (AC9) walks. |
| `T13-F5-7` | facet | Session-scoped ceiling as a cheaper, single-host alternative to a full fleet coordinator (cgroup-inheritance framing); folded into AC2 as the session-scope layer sitting between per-workflow and fleet-wide caps. |

**Binding decisions this issue builds on / must not contradict:**

- `/outcome` campaign (U1–U11) — derived-on-read status, never committed status fields (R17,
  `plugins/saga/skills/outcome/SKILL.md:35`); the lease registry follows the same discipline (AC8).
- `{#readonly-verifier-fallback-ladder-325}` + `{#verify-agent-git-checkout-clobber}` — verify-class
  spawns keep their existing readonly-profile + worktree-isolation + fallback-ladder requirement; the
  broker's conformance test is additive, not a replacement (see Non-Goals).
- CLAUDE.md sandbox-spawn-sites discipline
  (`plugins/saga/references/sandbox-spawn-sites.md`) — this issue's spawn-site conformance test
  mirrors that file's enumerate-and-assert pattern for concurrency instead of sandboxing.
- `{#plugin-portfolio-groom-17-to-7}` — this issue adds a module to the existing `saga` plugin; it
  does not introduce a new plugin.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** xhigh — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** none
- **Justification:** the mechanical shape (a file-backed lease registry with `flock`, TTL arithmetic,
  and a sweep) is well within sonnet's competence and mirrors an existing house pattern
  (`outcome_worktrees.py`'s own read-modify-write-under-lease registry), so opus is not warranted.
  `xhigh` effort over the default reflects genuine cross-cutting risk: the broker sits underneath
  every fan-out spawn site in the fleet (`sandbox-spawn-sites.md`'s full inventory), its correctness
  is concurrency-and-race-sensitive (TTL expiry racing a renew, a fencing-token check racing a write),
  and a defect here reproduces exactly the failure modes it is meant to close (silent over-spawn,
  orphan clobber) rather than failing loudly. `team-execution` as backend is recommended over inline
  because the blast radius (every spawn site in the fleet) benefits from reviewer-consensus gating
  before merge, matching this repo's own guidance that consequential, cross-cutting architectural
  changes warrant more than a single-pass review.

## Release-Surface Checklist

This issue changes saga's fan-out behavior fleet-wide (new required acquire/release calls at every
spawn site, a new CLI sweep entry point, a policy-sourced `VERIFY_N_CAP`), so update in the same PR:

- `plugins/saga/.claude-plugin/plugin.json` — version bump + description note for the new lease-broker
  module and its adoption across the fan-out surface.
- `.claude-plugin/marketplace.json` — mirrored version/description update for the `saga` plugin entry.
- `plugins/saga/CHANGELOG.md` — entry documenting the broker, `VERIFY_N_CAP`'s move to broker policy,
  the new sweep/teardown behavior, and the write-fencing check.
- `plugins/saga/references/sandbox-spawn-sites.md` — cross-reference the new spawn-site
  lease-conformance test alongside the existing sandbox-conformance discipline it documents.
- Drift-guard tests: `tests/test_lease_broker_conformance.py` (spawn-site coverage, AC9) and any
  existing plugin-metadata/version-drift guard tests updated to reflect the new module and version.

## Files Expected to Change

- `plugins/saga/scripts/lease_broker.py` — new module: `acquire`/`renew`/`release`/`sweep`, `flock`-guarded
  on-disk registry, fencing-token issuance and validation.
- `plugins/saga/scripts/execution_spec.py` — `VERIFY_N_CAP` (`:114`) sourced from broker policy;
  verify-panel/verify-loop spawn sites (`_emit_verify_panel`, `_emit_verify_loop_singleton`) acquire a
  lease before emitting.
- `plugins/saga/scripts/outcome_worktrees.py` — sweep integration point calling the existing
  `reap_worktree` (`:254`); no change to per-outcome cap/registry semantics themselves.
- `plugins/team-execution/skills/team-execution/references/` — new teardown reference documenting the
  lease-release-on-terminal step (the absorbed `S-32` "Step B8" gap) plus reviewer fan-out adoption.
- `plugins/saga/references/sandbox-spawn-sites.md` — cross-reference note for the new conformance
  test.
- `tests/test_lease_broker.py` — new acquire/release/TTL/sweep/fencing/derived-on-read tests.
- `tests/test_lease_broker_conformance.py` — new spawn-site coverage/drift-guard test.
- `tests/test_team_execution_teardown.py` — new lease-release-on-team-terminal test.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_lease_broker.py::test_fleet_cap_contention` — two independent callers against a 3-slot
  broker cannot sum past 3 concurrently-held leases.
- `tests/test_lease_broker.py::test_session_scoped_ceiling` — two same-session fan-outs share one
  ceiling.
- `tests/test_lease_broker.py::test_write_fencing_rejects_stale_token` — expired/superseded token
  rejected; live token succeeds.
- `tests/test_lease_broker.py::test_orphan_clobber_reproduction` — reproduces the grounding-brief
  singleton (stale process overwriting fresher evidence) and asserts it is rejected.
- `tests/test_lease_broker.py::test_reclaim_sweep_stale_worktrees` — 15-stale-worktree fixture swept to
  zero.
- `tests/test_lease_broker.py::test_edit_after_worktree_removal_fails_loud` — typed error, not a silent
  write or bare traceback.
- `tests/test_lease_broker.py::test_no_committed_expiry_field` — registry schema carries no
  status/expired field.
- `tests/test_lease_broker_conformance.py::test_all_spawn_sites_acquire_lease` — every enumerated
  spawn site covered; an injected unguarded spawn fails it.
- `tests/test_team_execution_teardown.py::test_lease_release_on_team_terminal` — team completion
  releases leases and triggers a sweep.
- `tests/test_execution_spec.py::test_verify_panel_cap` — existing soft-warn/hard-cap behavior
  unchanged, now sourced from broker policy.

### Verification
```bash
# New lease-broker suite: contention, session ceiling, fencing, reclamation, derived-on-read
uv run pytest tests/test_lease_broker.py -v

# Spawn-site conformance/drift guard
uv run pytest tests/test_lease_broker_conformance.py -v

# Team-execution teardown adoption
uv run pytest tests/test_team_execution_teardown.py -v

# Existing verify-panel cap regression stays green against the now-derived VERIFY_N_CAP
uv run pytest tests/test_execution_spec.py -k verify_panel_cap

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; deliberately reproducing the 15-stale-worktree fixture or an unguarded spawn site
turns the corresponding new test red before the fix and green after.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json` (`G-hybrids-2`),
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json` (`H-F4-3`, `T13-F1-4`, `T13-F5-7`),
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (`S-12`, `S-32`)
- Source type: ideation survivors + issue-map consolidation
- Source title: TTL-lease broker — concurrency slots, worktree/teardown reclamation, and orphan
  write-fencing as one cross-workflow primitive

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/lease_broker.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/saga/references/sandbox-spawn-sites.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

### Tests to add or update

- `tests/test_execution_spec.py`
- `tests/test_lease_broker.py`
- `tests/test_lease_broker_conformance.py`
- `tests/test_team_execution_teardown.py`

### Objective

"Govern fleet concurrency and reclaim leaked resources"

### Inputs inventory

- `plugins/saga/scripts/lease_broker.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/saga/references/sandbox-spawn-sites.md`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/356
- Number: 356
- Created at: 2026-07-04T07:48:13.516785+00:00

