---
title: "capability: adaptive admission governor — AIMD wave-width control, shed-to-requeue-ledger preemption, and 429-pressure offload routing"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: moonshot
objective: Govern fleet concurrency and reclaim leaked resources
wave: wave-1
---

# capability: adaptive admission governor — AIMD wave-width control, shed-to-requeue-ledger preemption, and 429-pressure offload routing

### Objective

Govern fleet concurrency and reclaim leaked resources — replace the fleet's ad hoc, per-surface
responses to rate-limit pressure (static caps, silent exits, or nothing at all) with one governor
that watches 429/latency signal, adjusts effective wave width AIMD-style within the existing static
policy ceiling, sheds preemptible work into a durable, drainable requeue ledger instead of dropping
it, and — where provider routing exists — diverts offload-eligible units to the external ($0/cheap)
lane under pressure instead of queueing them behind the same constrained lane.

### Problem / Motivation

The fleet has a real, named concurrency cap today, but no control loop that adapts it, and the
recorded failure pattern is fan-outs dying under rate-limit pressure with no mechanism to shed or
reroute the load:

- **`VERIFY_N_CAP` is a static ceiling with no feedback loop.** `plugins/saga/scripts/execution_spec.py:114`
  sets `VERIFY_N_CAP = 7`, enforced at `execution_spec.py:355-363` ("bounded (KTD3): `1 <= n <=
  VERIFY_N_CAP`, with a soft warn band above `VERIFY_N_WARN`"). This is a hand-set upper bound, not
  a governor — it never tightens under observed 429 pressure and never recovers itself; the operator
  sets the number once, at plan time, for the whole run.
- **The recorded failure mode is exactly "no concurrency knob."** The grounding brief's session-mining
  synthesis, recurring pattern 4, records: *"Rate-limit fan-out kills — '6/7 agents failed on
  rate-limiting'; 'the emitter has no concurrency knob... KTD6 aspiration, not machinery'"* (3 repos)
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, §7, pattern 4). `/optimize` independently
  documents the same gap from the other direction: its SKILL explicitly SHEDS `ce-optimize`'s
  `max_concurrent` fan-out and runs serial by default (`plugins/saga/skills/optimize/SKILL.md:18-20`)
  — there is no adaptive concurrency primitive anywhere in the fleet for `/optimize` to have adopted
  even if it wanted to.
- **When a wave hits pressure today, work is dropped or killed, not shed to something recoverable.**
  `docs/engineering-journal/LEARNINGS.md:954-960` records a live fan-out where transient 429s "ate
  retry budget," and the fix applied was a one-off, hand-tuned batch size (5-at-a-time) baked into a
  single prompt run — not a durable mechanism. There is no requeue ledger anywhere in the fleet
  scripts (`plugins/saga/scripts/`, `plugins/team-execution/`) that a shed unit could land in; a
  preempted or rate-limited unit today either retries in place, dies, or requires an operator to
  re-trigger it by hand.
- **The fleet already has an external-lane primitive this governor can route to, but nothing wires
  429 pressure to it.** `plugins/saga/scripts/engine_dispatch.py` defines `dispatch()` (`:103`) and
  `AdvisoryEvidence` (`:28`) for routing units to external engines (Codex/Gemini via agy), governed
  by the binding decision that external engines are advisory/generator-only, never gatekeepers
  (`docs/engineering-journal/DECISIONS.md:1985` `{#external-engines-never-gatekeepers}`) and that
  team-execution's external-engine slot is chaperone dispatch, not a second executor kind
  (`docs/engineering-journal/DECISIONS.md:2021` `{#external-engine-chaperone-dispatch}`). Today
  nothing consults 429 pressure to decide whether a unit should divert there — the dispatch path
  exists, but the trigger this issue adds (rate-limit-pressure-driven offload) does not.
- **`/outcome`'s derived-on-read-status and HALT-not-degrade decisions constrain how a governor may
  represent shed/queued work.** The `/outcome` campaign decisions (grounding brief §2: "Derived-on-read
  status, never committed status fields; HALT-not-degrade; backend menu off-by-default host-conditional
  degrade; cost ledger = leaf-produced fact") mean the requeue ledger this issue adds must be a
  leaf-produced fact and a derived-read surface, not a new committed status field, or it directly
  violates a binding decision.

Four related-but-disconnected gaps — a static cap with no feedback, an admitted "aspiration, not
machinery" concurrency knob, no durable shed target, and an offload lane no pressure signal drives —
collapse into one governor rather than four more bespoke, uncoordinated fixes.

## Definition of Done

A merged admission governor that:

- Reads 429/latency signal from the wave-dispatch surfaces it fronts (initially: the emitted
  `parallel([...])` wave path in `execution_spec.py` and the `/outcome` leaf-dispatch path in
  `outcome.py`) and adjusts an *effective* wave width AIMD-style — halving (or otherwise multiplicatively
  decreasing) on sustained 429 pressure, additively recovering toward the ceiling on quiet periods —
  while treating the existing static value (`VERIFY_N_CAP` for verify-panel waves; each unit's own
  declared concurrency bound elsewhere) as a hard ceiling the governor can only sit at or below, never
  exceed.
- Persists governor state (current effective width, backoff/recovery counters) in saga session state,
  so a resumed run picks up the governor's last-known width rather than resetting to the ceiling.
- On shedding a unit (either because the governor tightened width below the number of ready units, or
  because a unit is explicitly tagged preemptible/shed-priority), writes it as a fact to a durable
  requeue ledger — never silently drops it — and drains the ledger back into the ready frontier on
  the next admission tick, consistent with `/outcome`'s derived-on-read status model (the ledger is a
  leaf-produced fact stream, not a new committed status field).
- Where a unit is tagged offload-eligible (per the existing chaperone-dispatch external-engine
  machinery), sustained 429 pressure on the Claude-side lane diverts that unit to the external lane via
  `engine_dispatch.dispatch()` instead of holding it in the requeue ledger — gated behind a feature
  flag, off by default, and never applied to a unit that is not already offload-eligible (this issue
  adds no new offload-eligibility criteria and does not touch gated/verifier-of-record work).
- Ships a deterministic simulation test that drives a synthetic 429 burst through the governor and
  asserts: width descends under pressure, recovers additively once pressure clears, no unit is lost
  (every shed unit is later observed either completed or still resident in the requeue ledger), and
  the governor never requests width above the static ceiling.

### Acceptance criteria
- [ ] **AIMD width control under a simulated 429 burst.** A test drives a burst of synthetic 429
      responses through the governor and asserts effective width decreases multiplicatively during
      the burst, then increases additively once the burst clears, converging back toward (but never
      exceeding) the static ceiling.
      Check: `uv run pytest tests/test_admission_governor.py -k aimd_burst_then_recovery` → passes.
- [ ] **Ceiling is a hard bound, never exceeded.** A test asserts that regardless of recovery-phase
      length, the governor's requested width never exceeds the unit's/wave's static concurrency bound
      (`VERIFY_N_CAP` for verify-panel waves).
      Check: `uv run pytest tests/test_admission_governor.py -k width_never_exceeds_ceiling` → passes.
- [ ] **No work is silently lost on shed — every shed unit lands in the requeue ledger and drains.**
      A test sheds N units under simulated pressure, asserts each appears as a fact in the requeue
      ledger, then asserts the next admission tick re-picks each one from the ledger into the ready
      frontier with no unit missing and no duplicate.
      Check: `uv run pytest tests/test_admission_governor.py -k requeue_ledger_no_loss` → passes.
- [ ] **Shed decisions are logged as facts, never silently dropped units.** A test asserts each shed
      decision produces a durable, inspectable record (unit id, reason, timestamp) rather than a bare
      state mutation, and that the record survives a simulated process restart (persisted, not
      in-memory only).
      Check: `uv run pytest tests/test_admission_governor.py -k shed_decision_is_a_fact` → passes.
- [ ] **Requeue ledger respects `/outcome`'s derived-on-read-status decision.** A test asserts the
      requeue ledger introduces no new *committed* status field on the leaf/outcome record — status
      remains derived from the ledger's fact stream on read, matching the existing `/outcome`
      derived-on-read-status-never-committed decision.
      Check: `uv run pytest tests/test_admission_governor.py -k ledger_no_committed_status_field` →
      passes.
- [ ] **Offload diversion only fires for already offload-eligible units, and only behind a feature
      flag.** A test asserts a non-offload-eligible unit under 429 pressure is shed to the requeue
      ledger (never diverted externally), an offload-eligible unit under pressure diverts to
      `engine_dispatch.dispatch()` only when the feature flag is on, and stays in the requeue ledger
      when the flag is off.
      Check: `uv run pytest tests/test_admission_governor.py -k offload_diversion_gated` → passes.
- [ ] **Offload diversion honors the never-gatekeepers decision.** A test asserts a diverted unit's
      result surfaces as `AdvisoryEvidence` (no verdict field) and that `engine_dispatch.satisfy_gate`
      still requires a distinct Claude verification step before any gated outcome depends on it —
      the governor's diversion path does not create a new path for an external engine to hold a gated
      verdict.
      Check: `uv run pytest tests/test_admission_governor.py -k offload_never_gatekeeper` → passes.
- [ ] **Governor state persists and resumes.** A test starts a run, lets the governor tighten width
      under pressure, simulates a saga resume, and asserts the resumed run starts from the persisted
      effective width rather than resetting to the static ceiling.
      Check: `uv run pytest tests/test_admission_governor.py -k state_persists_across_resume` →
      passes.
- [ ] **Non-429 failures still HALT — the governor does not convert a genuine failure into a shed.**
      A test asserts a non-429 error inside a governed wave still propagates and HALTs exactly as it
      does today; only 429/rate-limit-classified pressure triggers width adjustment or shedding.
      Check: `uv run pytest tests/test_admission_governor.py -k non_429_still_halts` → passes.
- [ ] **Full suite, lint, types, security stay green.**
      Check: `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` →
      all pass.

### Out-of-scope / non-goals
In scope: one admission-governor module fronting (a) the emitted `parallel([...])` wave path in
`execution_spec.py` and (b) `/outcome` leaf dispatch in `outcome.py`; AIMD width adjustment bounded
by each surface's existing static ceiling; a durable requeue ledger for shed units; feature-flagged
offload diversion for already offload-eligible units via the existing `engine_dispatch.dispatch()`
path.

Out of scope (do not do in this issue):

- Raising or redesigning `VERIFY_N_CAP` or any other static ceiling — this issue only adds a governor
  that operates *within* the existing ceiling; changing the ceiling's value is a separate decision.
- Introducing new offload-eligibility criteria, or expanding which units may be routed externally —
  the governor only diverts units already marked offload-eligible under the existing chaperone-dispatch
  machinery; it does not decide eligibility.
- Changing team-execution's existing proceed-best-available iteration cap or validator-panel logic
  (`plugins/team-execution/skills/team-execution/references/validator-execution-order.md`) — this is a
  concurrency/admission concern, not a consensus/verification-iteration one.
- Building the shared 429 retry/backoff primitive itself (`retry_with_backoff`, `bridge_call()`) —
  that is a separate, narrower consolidation issue (`pf-429-retry-primitive`); this governor consumes
  429/latency signal, it does not implement the low-level retry wrapper. If both land, the governor
  should call the shared primitive rather than reimplementing backoff, but this issue does not block
  on that one landing first — a minimal local 429 classifier is acceptable for v1 if the primitive
  is not yet available.
- Fronting the `unifi` or `mission-control` HTTP clients, or any inline (non-wave, non-`/outcome`)
  agent invocation path — this issue governs the two named fan-out surfaces only.
- Any change to `/outcome`'s HALT-not-degrade posture for genuine (non-429) failures.
- A UI/dashboard for governor state — state is inspectable via the persisted session state and
  requeue-ledger facts, not a new visualization surface.

## Grounding References

- `G-hybrids-8` (primary) — "Ambient AIMD admission control with a requeue ledger — cap, backoff, and
  shed as one governor" (parents: `H-F2-7`, `T13-F5-3`, `H-F6-6`, `T13-F4-5`); basis: direct synthesis
  of the fleet's static-cap-with-no-feedback gap and the recorded shed-not-implemented pain; dod_sketch:
  "A governor that reads 429/latency signals, adjusts effective wave width AIMD-style within the
  policy block's bounds, sheds preemptible work to a durable requeue ledger, and (when provider
  routing exists) diverts offload-eligible units to the external lane."
- `T13-F1-6` (facet) — "Per-session AIMD concurrency governor that dials wave width to the observed
  429 rate"; basis: external (AIMD as a well-established congestion-control pattern applied to agent
  fan-out); dod_sketch: "Merged AIMD governor persisting state in saga session state, bounded by
  `ConcurrencyPolicy.max`; verified by a deterministic 429-burst-then-quiet trace test showing width
  descends to 1 then recovers toward the cap." (This issue's AIMD-state-persistence and burst-then-quiet
  acceptance criteria are drawn directly from this facet; `ConcurrencyPolicy.max` in the source idea
  maps to the existing static ceilings named above — `VERIFY_N_CAP` at `execution_spec.py:114` — since
  no `ConcurrencyPolicy` class exists in the fleet today.)
- `H-F6-6` (facet) — "Shed, don't cap: a 429-driven preemption supervisor with a requeue ledger instead
  of static concurrency knobs"; basis: direct; outcome_shape: "Merged: shed-priority tagging convention
  + a requeue-ledger schema and supervisor loop in the workflow emitter path, with team-execution
  reviewer fan-out as first adopter." (This issue's shed-priority-tagging and requeue-ledger-schema
  acceptance criteria are drawn from this facet; team-execution reviewer fan-out as "first adopter" is
  noted but not built here — this issue fronts the emitted wave and `/outcome` paths first, per the
  scope above.)
- `X-codex-3` (facet) — "Rate-Limit Air Traffic Control"; basis: external (codex/GPT proposal) —
  "concurrency must be governed at the fleet level because rate limits fail at the fleet level";
  outcome_shape in the source idea proposed a standalone `fleet_dispatch_broker.py` + `dispatch-policy.yaml`
  + adapters for team-execution/`/outcome`/external-engine bridges. This issue narrows that fleet-wide
  broker proposal to one governor module fronting the two surfaces named in Definition of done, per the
  registry-home precedent set by `{#external-engines-never-gatekeepers}` (new standalone plugins are
  rejected in favor of extending the existing seam-owning location); a fleet-wide broker spanning
  team-execution as well remains a possible future follow-up, not this issue's scope.
- `G-negative-space-4` (facet) — "Route around the rate limit: 429 pressure sheds offloadable work to
  the $0/external provider lane instead of queueing it"; basis: reasoned (T13 x T2 rerouting
  intersection); dod_sketch: "Merged reroute branch on the shared 429 primitive consulting
  `engine_resolver` for offload-tagged units + dispatch-ledger reroute stamps; verified by a 429-storm
  test where offload units reroute, gated units HALT-queue, and every reroute is ledgered." (This
  issue's offload-diversion acceptance criteria — gated-units-never-diverted, offload-only,
  feature-flagged, ledgered — are drawn directly from this facet.)
- Binding decisions this issue must not violate:
  - `{#external-engines-never-gatekeepers}` (#283) (`docs/engineering-journal/DECISIONS.md:1985`) —
    a diverted unit's result is `AdvisoryEvidence` only; `engine_dispatch.satisfy_gate` still requires
    a distinct Claude verification step. This governor adds no new path for an external engine to hold
    a gated verdict.
  - `{#external-engine-chaperone-dispatch}` (#318) (`docs/engineering-journal/DECISIONS.md:2021`) —
    offload diversion routes through the existing chaperone-dispatch shape; this issue does not add a
    second executor kind or a new residency/git-participant role for external engines.
  - `/outcome` campaign (grounding brief §2) — derived-on-read status, never committed status fields;
    HALT-not-degrade for genuine failures. The requeue ledger is a leaf-produced fact stream, and
    non-429 failures continue to HALT exactly as today.
  - `{#worker-cache-scheduling}` — not directly engaged by this issue (no change to segment/tier
    residency), but the governor's session-state persistence should not introduce a second,
    conflicting notion of "where wave state lives" — it persists in saga session state, the same home
    this decision already establishes for saga-side derivation.

### Recommended executor profile

- **Model:** opus
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM:** second-opinion
- **Justification:** this is control-loop design (AIMD tuning, shed/preemption ordering, offload
  diversion gating) whose failure modes — oscillation, starvation, ledger loss, ceiling violation,
  gated-verdict leakage through the offload path — span every spawn site the governor fronts.
  Getting the width-adjustment and shed-ordering logic wrong fails silently (a starved queue or a
  slow oscillation) rather than loudly, which is exactly the class of judgment call that warrants
  opus over sonnet. An advisory second-opinion review specifically targets the control-loop's
  stability properties (does it oscillate under adversarial 429 patterns, can a unit starve
  indefinitely in the requeue ledger) before this ships, given the four absorbed ideas propose
  meaningfully different mechanisms (AIMD tuning, shed-priority tagging, a fleet-wide broker, and
  offload rerouting) that this issue must reconcile into one coherent module rather than four
  half-integrated ones.

### Release-surface checklist

This issue changes runtime behavior of the `saga` plugin (`/outcome` leaf dispatch, emitted-wave
admission control) and adds a new consumer of the existing `engine_dispatch` module. Update in the
same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new admission-governor behavior
      affecting `/outcome` dispatch and emitted-wave execution).
- [ ] `.claude-plugin/marketplace.json` — reflect the saga version bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the AIMD admission governor, requeue ledger, and
      feature-flagged offload diversion.
- [ ] Any existing plugin-metadata/version drift-guard tests (marketplace/plugin.json parity test)
      re-run green after the bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — new entry recording the governor's design (AIMD
      bounded by existing static ceilings; shed-to-ledger never drop; offload diversion gated and
      chaperone-shaped) as the settled pattern, with a revisit-when condition (e.g., a fleet-wide
      broker spanning team-execution as well becomes warranted, per `X-codex-3`'s broader proposal).

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/admission_governor.py` — new AIMD width controller + requeue ledger + offload
  diversion gate (proposed path).
- `plugins/saga/scripts/execution_spec.py` — the emitted `parallel([...])` wave path consults the
  governor for effective width instead of always dispatching at the static `VERIFY_N_CAP`
  (`:114`, `:355-363`).
- `plugins/saga/scripts/outcome.py` — leaf dispatch (`:542`, `advance()`) consults the governor before
  admitting a leaf; a rate-limited dispatch sheds to the requeue ledger instead of failing terminally.
- `plugins/saga/scripts/engine_dispatch.py` — offload diversion calls the existing `dispatch()` (`:103`)
  and `AdvisoryEvidence` (`:28`) path; no changes to `satisfy_gate` (`:281`) semantics.
- `docs/engineering-journal/DECISIONS.md` — new entry per Release-surface checklist.
- `plugins/saga/CHANGELOG.md` — entry per Release-surface checklist.
- `tests/test_admission_governor.py` — new.
- `tests/test_execution_spec.py` — add governed-width wave-dispatch cases.
- `tests/test_outcome.py` — add rate-limited-leaf-sheds-to-ledger case.

### Verification

```bash
uv run pytest tests/test_admission_governor.py tests/test_execution_spec.py tests/test_outcome.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports \
  && uv run bandit -r plugins/
```

Expected: all green.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Context library links

_none_

### Tests to add or update

- `tests/test_admission_governor.py`
- `tests/test_execution_spec.py`
- `tests/test_outcome.py`

### Intent

The fleet has a real, named concurrency cap today, but no control loop that adapts it, and the recorded failure pattern is fan-outs dying under rate-limit pressure with no mechanism to shed or reroute the load:

### Inputs inventory

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/scripts/engine_dispatch.py`
- `plugins/team-execution/skills/team-execution/references/validator-execution-order.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
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

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/349
- Number: 349
- Created at: 2026-07-04T07:46:12.296106+00:00

