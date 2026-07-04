---
title: "capability: one shared 429 retry/backoff primitive across emitted waves, engine bridges, and /outcome dispatch"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Govern fleet concurrency and reclaim leaked resources
wave: wave-1
---

# capability: one shared 429 retry/backoff primitive across emitted waves, engine bridges, and /outcome dispatch

### Objective

Replace four independent, partial responses to fleet rate-limiting with one shared, hardened
retry/backoff primitive that every call site that can hit a 429 — emitted parallel waves, the
engine bridges, and `/outcome` leaf dispatch — imports and reuses, so a rate-limited call re-queues
or trips a breaker instead of killing an agent or requiring an operator to hand-resume.

### Problem / Motivation

The fleet's dominant recorded rate-limit failure is not "no handling exists" — it is that handling
exists in three or four disconnected places, none of which cover the paths that actually die today:

- **HTTP-level 429 handling is duplicated and narrow.** It exists only inside the two REST HTTP
  clients (`plugins/unifi/skills/unifi-network/scripts/unifi_network_client.py:151-158` and
  `plugins/unifi/skills/unifi-protect/scripts/unifi_protect_client.py:158-166`, each independently
  parsing `Retry-After` and calling `sys.exit(1)` — no retry, just a typed error) and inside the
  `gh`-CLI status-code classifier in
  `plugins/mission-control/scripts/sdlc_manager.py:525-591` (`ApiRateLimitedError`, again just
  classification, not retry). None of the three share an implementation, and none of them retry —
  they all surface and exit.
- **The emitted parallel-wave path has no 429 handling at all.** `plugins/saga/scripts/execution_spec.py`
  emits `parallel([...])` waves of `agent()` thunks (see `:943-1080`, `_JS_GATE_HELPER` at `:132`) with
  no wrapper distinguishing a transient 429 from a real agent failure. This is the documented failure
  shape: `docs/engineering-journal/LEARNINGS.md:954` records that transient 429s were visible in a
  live fan-out run and "ate retry budget" even though they were not the root cause of that particular
  failure — the fleet has no mechanism today that would make a 429 anything other than a wasted retry
  or a dead agent.
- **`/outcome` leaf dispatch has no rate-limit-aware retry, only rate-limit-aware *reads*.**
  `plugins/saga/scripts/outcome_github.py:10` establishes the existing safe-degrade posture for
  reads ("Every read degrades safely: if `gh` is unavailable / rate-limited / the ref is unknown, the
  state is degraded") — but `advance()`/dispatch in `plugins/saga/scripts/outcome.py:542` has no
  equivalent for a leaf whose *dispatch* hits a 429: today that leaf fails terminally and needs an
  operator to re-trigger it manually.
- **The engine bridges are the newest and least protected surface.** `plugins/agy/scripts/agy_delegate.py`
  (the current external-engine bridge script) has no 429/backoff/circuit-breaker handling at all;
  the grounding brief calls the bridges out as unbounded call surfaces with "HTTP-level 429 handling
  exists only in the unifi/mission-control clients" (grounding brief consolidated finding, section on
  engine bridges).

Four call sites, four different (or absent) responses to the same failure mode, none of them
retrying. This issue consolidates them into one shared primitive rather than adding a fifth
bespoke handler when the next bridge or client is added.

## Definition of Done

A single retry/backoff module — `retry_with_backoff(fn, *, on_status=429)` (jittered exponential
backoff, attempt cap, non-429 passthrough) plus a `bridge_call()` wrapper that adds circuit-breaker
state (OPEN on a run of 429s, cooldown, HALF-OPEN probe, CLOSE on success) — lives in one shared
scripts location importable by all four call sites:

- The `unifi-network` and `unifi-protect` HTTP clients call the shared primitive instead of their
  own inline 429 handling, and continue to pass their existing tests.
- The emitted `.workflow.js` `parallel([...])` wave (via `execution_spec.py`) wraps each `agent()`
  thunk in the shared retry primitive so a 429'd agent re-queues (bounded) instead of counting as a
  wave failure; a genuine non-429 error still propagates and HALTs the wave (no silent degrade).
- `/outcome` `advance()`/dispatch classifies a 429'd leaf dispatch as `retriable-pending` — a
  derived-on-read status, never a committed field, consistent with the existing `/outcome`
  derived-status decision — so the next `advance` tick re-picks it from the ready frontier without
  operator action.
- The `agy` engine-bridge script (and any future provider bridge) routes outbound calls through
  `bridge_call()`, giving it backoff-with-jitter plus a circuit breaker for a run of 429s.

A 429 anywhere in the fleet becomes an invisible retry or a re-queued/re-picked unit of work, never
a silent success and never (by default) a hard kill requiring manual intervention.

### Acceptance criteria
- [ ] **Shared primitive exists and is tested standalone.** `retry_with_backoff(fn, *, on_status=429)`
      ships in a shared scripts location with unit tests covering: backoff schedule shape, jitter
      bounds, max-attempts cap, and non-429 errors passing through unretried.
      Check: `uv run pytest tests/test_retry_backoff.py -v` → all pass.
- [ ] **`unifi-network` client adopts the shared primitive; existing tests still green.**
      Check: `uv run pytest tests/test_unifi_network_client.py -v` → passes with no test deleted or
      weakened to accommodate the refactor.
- [ ] **`unifi-protect` client adopts the shared primitive; existing tests still green.**
      Check: `uv run pytest tests/test_unifi_protect_client.py -v` → passes.
- [ ] **Emitted wave re-queues a rate-limited agent instead of failing it.** A test reproduces the
      "N of M agents failed on rate-limiting" scenario (a stub 429-then-success agent inside a
      `parallel([...])` wave) and asserts the wave completes rather than reporting the agent as
      failed; a second test asserts a non-429 error in the same wave still HALTs it (no degrade).
      Check: `uv run pytest tests/test_execution_spec.py -k retry_on_429` → passes (2+ cases:
      retry-then-success, non-429-halts).
- [ ] **Emitted JS actually contains the bounded retry wrapper (golden assertion).**
      Check: `uv run pytest tests/test_execution_spec.py -k emitted_js_contains_retry_wrapper` →
      passes.
- [ ] **`/outcome` marks a 429'd leaf dispatch `retriable-pending` and re-picks it on the next tick,
      with no committed status field added.** A test simulates a rate-limited leaf dispatch and
      asserts (a) the leaf reappears in the ready frontier on the next `advance` call without
      operator action, and (b) no new persisted/committed status field was introduced (status stays
      derived-on-read, per the existing `/outcome` decision).
      Check: `uv run pytest tests/test_outcome.py -k retriable_pending` → passes.
- [ ] **Engine bridge (`agy_delegate.py`) routes through `bridge_call()` with breaker + jittered
      backoff.** A fault-injection test sends a run of simulated 429s, asserts the breaker trips
      OPEN, further calls short-circuit during cooldown, and a later call succeeds once the breaker
      HALF-OPENs and probes successfully.
      Check: `uv run pytest tests/test_agy_delegate.py -k circuit_breaker` → passes.
- [ ] **Full suite, lint, types, security stay green.**
      Check: `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/` → all pass.

### Out-of-scope / non-goals
In scope: one shared retry/backoff primitive plus a `bridge_call()` wrapper; adoption by the two
existing unifi HTTP clients, the emitted `parallel([...])` wave path in `execution_spec.py`, the
`/outcome` `advance()`/dispatch path, and the `agy` engine-bridge script.

Out of scope (do not do in this issue):

- Adopting the shared primitive in `mission-control`'s `_classify_gh_error` / `sdlc_manager.py` gh-CLI
  path. That path classifies rate-limiting from `gh` CLI stderr/stdout text, not raw HTTP responses,
  and gh itself already has its own retry semantics; folding it into the same primitive is a separate,
  narrower follow-up, not a blocking dependency here.
- Building a new engine-bridge script for codex. Only the existing `agy_delegate.py` bridge is
  in scope; a future codex bridge inherits the primitive by importing it, not by being built here.
- Any change to `/outcome`'s HALT-not-degrade posture for genuine (non-429) failures — this issue only
  adds a transient-retryable classification for 429s specifically; every other failure class keeps
  HALTing exactly as it does today.
- Any change to team-execution's existing proceed-best-available cap or validator-panel logic.
- Backfilling retry/backoff onto call sites not named above (e.g., any inline/non-parallel agent
  invocation path) — this is a targeted consolidation of the four named surfaces, not a fleet-wide
  HTTP client rewrite.

## Grounding References

- `T13-F4-3` (primary) — extract the shared `retry_with_backoff(fn, *, on_status=429)` primitive;
  basis: grounding brief §1 ("HTTP-level 429 handling exists only in unifi/mission-control clients")
  and the recorded rate-limit fan-out failure pattern.
- `T13-F2-3` (facet) — auto-retry-on-429 wrapper in the emitted `parallel([...])` helper so a
  rate-limited agent re-queues instead of dying; basis: `docs/engineering-journal/LEARNINGS.md:954`
  (transient 429s observed eating retry budget in a live fan-out run) and the `/outcome`
  HALT-not-degrade decision, which this facet respects by classifying 429 as transient-retryable
  rather than a degrade path.
- `T13-F2-4` (facet) — `/outcome` marks a rate-limited leaf dispatch `retriable-pending` so the next
  `advance` tick re-picks it; basis: `plugins/saga/scripts/outcome_github.py:10`'s existing
  safe-degrade-on-read posture, extended from reads to dispatch, and the `/outcome`
  derived-on-read-status-never-committed decision (its revisit-when is not crossed because
  `retriable-pending` is derived, not stored).
- `T13-F5-4` (facet) — circuit breaker + backoff-with-jitter at the unbounded engine bridges; basis:
  grounding brief's callout that engine bridges are unbounded call surfaces with no shared 429
  handling, plus the recorded rate-limit fan-out failure pattern.
- Binding decisions this issue must not violate: `/outcome` campaign decisions on
  derived-on-read status (never committed status fields) and HALT-not-degrade for genuine failures;
  `{#external-engine-chaperone-dispatch}` (#318) — this issue does not add a new executor kind or
  change bridge dispatch shape, it only hardens the transport-level retry behavior of the existing
  chaperone-dispatch call.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** mechanical extraction-and-adoption work (one new module, four call sites
  refactored to import it, tests per site) with a well-specified target shape from four already-written
  survivor ideas; no architectural judgment call above sonnet's ceiling is required. High effort
  because the change touches four independent modules and must keep each one's existing test suite
  green while adding fault-injection coverage — that breadth, not novelty, is what warrants high
  over medium.

### Release-surface checklist

This issue changes runtime behavior of the `saga` plugin (`/outcome` dispatch, emitted-wave retry)
and the `agy` plugin (bridge call retry/breaker), and touches (but does not change the public
interface of) the `unifi` and `mission-control` plugins. Update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (behavior change to `/outcome`
      dispatch and emitted-wave execution).
- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump (bridge call now retries/breaks on 429).
- [ ] `.claude-plugin/marketplace.json` — reflect both version bumps.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the retry/backoff primitive adoption in
      emitted-wave execution and `/outcome` dispatch.
- [ ] `plugins/agy/CHANGELOG.md` — entry describing `bridge_call()` circuit-breaker adoption.
- [ ] Any existing plugin-metadata/version drift-guard tests (e.g. a marketplace/plugin.json parity
      test) re-run green after the bumps.
- [ ] `docs/engineering-journal/DECISIONS.md` — new entry recording "one shared retry/backoff
      primitive, adopted fleet-wide rather than a fifth bespoke handler" as the settled pattern, with
      a revisit-when condition (e.g., a fifth call site needs 429 handling that doesn't fit the shared
      shape).

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/retry_backoff.py` — new shared `retry_with_backoff()` + `bridge_call()`
  module (proposed path; exact location TBD by `/plan`, but must be importable from `saga`, `agy`,
  and `unifi` scripts without a circular/plugin-boundary dependency).
- `plugins/saga/scripts/execution_spec.py` — wrap emitted `agent()` thunks inside `parallel([...])`
  waves (`:943-1080`, `_JS_GATE_HELPER` at `:132`) with the retry wrapper.
- `plugins/saga/scripts/outcome.py` — `advance()`/dispatch path (`:542`) classifies a 429'd leaf
  dispatch as `retriable-pending`.
- `plugins/saga/scripts/outcome_github.py` — extend the existing safe-degrade-on-read posture
  (`:10`) to cover dispatch, if the shared classification needs a read-side hook.
- `plugins/unifi/skills/unifi-network/scripts/unifi_network_client.py` (`:151-158`) — replace inline
  429 handling with a call to the shared primitive.
- `plugins/unifi/skills/unifi-protect/scripts/unifi_protect_client.py` (`:158-166`) — same.
- `plugins/agy/scripts/agy_delegate.py` — route outbound calls through `bridge_call()`.
- `tests/test_retry_backoff.py` — new.
- `tests/test_execution_spec.py` — add retry-on-429 / non-429-halt / golden-JS cases.
- `tests/test_outcome.py` — add `retriable-pending` dispatch case.
- `tests/test_agy_delegate.py` — add circuit-breaker fault-injection case.
- `tests/test_unifi_network_client.py`, `tests/test_unifi_protect_client.py` — verify unchanged
  behavior post-refactor.

### Verification

```bash
uv run pytest tests/test_retry_backoff.py tests/test_execution_spec.py tests/test_outcome.py \
  tests/test_agy_delegate.py tests/test_unifi_network_client.py tests/test_unifi_protect_client.py -v
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

- `tests/test_agy_delegate.py`
- `tests/test_execution_spec.py`
- `tests/test_outcome.py`
- `tests/test_retry_backoff.py`
- `tests/test_unifi_network_client.py`
- `tests/test_unifi_protect_client.py`

### Intent

The fleet's dominant recorded rate-limit failure is not "no handling exists" — it is that handling exists in three or four disconnected places, none of which cover the paths that actually die today:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/348
- Number: 348
- Created at: 2026-07-04T07:45:51.635934+00:00

