# Decisions — Infiquetra Claude Plugins

## 2026-07-06

### External-engine HTTP bridge + bridge_receipt.v1 keystone pair: transport-keyed adapter, fleet-commons receipt schema, receipt-gated disposition, required emitter wiring {#http-bridge-receipt-pair-387-383}

**Context.** `docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md` (#387, #383).
Scope-note corrections on both issues named them a keystone pair: a bridge that ships unproven, or
a receipt contract with no consuming emitter, would each ship incomplete — one PR lands both.

- **KTD1 — the adapter table extends `engine_dispatch.py`, keyed on a new top-level registry field
  `transport` (closed vocab `cli | http`, default `cli`).** `_build_invocation` gains a
  transport-keyed branch: `http` builds a generic invocation from row data with zero
  per-provider branching in the bridge; `cli` keeps the existing codex/agy builders unchanged.
  *Rejected:* a new `plugins/team-execution/scripts/engine_dispatch.py` (a draft suggestion) — would
  fork the dispatch substrate; the scope note is explicit that dispatch already lives in saga and
  should be extended, not forked. *Revisit when:* team-execution needs its own dispatch surface for
  a reason unrelated to external engines (none identified).
- **KTD3 — `ollama-cloud` and `deepseek` are new seed registry rows; routing-stability is enforced
  by a literal-baking regression test, not a promise.** Neither row may rate any capability above
  the current `by_capability` winner (verified against `engine-registry.yaml` at authoring time);
  new rows either omit capabilities or rate low enough, or use a losing `cost_speed_rank`, to never
  hijack today's winner. Base URLs and model ids are authored against provider docs, not recalled
  from memory, and proven live only by an availability-gated smoke test (skip-not-fail when no key
  or endpoint unreachable). *Rejected:* trusting rating authorship alone without a regression test —
  a plausible-looking rating is exactly the failure mode a "should be fine" review misses.
  *Revisit when:* `/retro` re-validates ratings against fresh seed data (same posture as the
  2026-06-27 seed data) and the literals need a deliberate, reviewed update.
- **KTD6 — `bridge_receipt.py` is canonical in fleet-commons, vendored into agy via the established
  shim mechanism.** A saga-local module imported directly by agy would break at install time
  (`{#marketplace-install-layout-no-import-path}`); fleet-commons + vendored shim
  (`{#fleet-commons-mechanism-463}`) is the established mechanism, and agy did not carry a shim
  before this pair — U2 adds one, byte-identical, covered by the existing vendored-copy drift
  guard. *Rejected:* a per-plugin vendored copy of the receipt module's schema logic itself (as
  opposed to the file) — the whole reason the shim mechanism exists is so schema logic never has to
  be independently re-implemented per plugin. *Revisit when:* a third consumer needs the receipt
  schema and the shim-per-plugin pattern starts feeling like duplication rather than isolation.
- **KTD8 — receipt-less success maps to a new `Disposition.UNPROVEN`, never a silent
  `RAN_AS_REQUESTED`.** `AdvisoryEvidence` gains an additive `runner_receipt: dict | None = None`
  field; `build_dispatch_manifest` assigns `RAN_AS_REQUESTED` only when a schema-valid receipt is
  present, else `UNPROVEN` with a note naming what is missing. `FELL_BACK_TO_CLAUDE` is unaffected
  (a halt carries no receipt because there is nothing to prove). Existing tests asserting
  `RAN_AS_REQUESTED` without a receipt were updated to supply one — a deliberate assertion flip,
  called out in the PR rather than treated as collateral damage. *Rejected:* leaving receipt-less
  success as `RAN_AS_REQUESTED` and treating the receipt as advisory metadata — that would make the
  whole receipt contract provably unenforced from day one. *Revisit when:* a v2 receipt schema
  needs a third disposition state (none anticipated).
- **KTD9 — `receipt_emitter` is a required registry key, validated at load, with an explicit
  pending-emitter ledger rather than a silent skip.** Every row must declare `receipt_emitter`; a
  missing one raises `RegistryError` at load, enforced in CI. The bridge-enumeration drift guard
  (`tests/test_bridge_receipt_drift.py`) proves every declared emitter actually emits through the
  shared path — a test-double bridge that skips the emit call reds it (forcing-function verified,
  journal `{#verify-the-guard-reds}`) — and a `PENDING_EMITTERS = {"codex-bridge": "#476"}` entry
  covers the not-yet-landed codex bridge (`plugins/codex/`, #476) so its absence doesn't red the
  suite, while the guard reds if that issue closes and the entry is still marked pending. *Rejected:*
  a silent skip for any registry row lacking an emitter — that is exactly the "harvest never fires"
  missing-producer failure mode already logged once in this repo (LEARNINGS, re #495/#491/#343).
  *Revisit when:* `plugins/codex/` (#476) ships its bridge — the `PENDING_EMITTERS` entry must be
  removed in that same PR, not left stale.

**Release surfaces** (R12, same PR): `plugins/saga` 0.72.0→0.73.0, `plugins/agy` 0.1.1→0.1.2,
`plugins/fleet-core` 0.6.0→0.7.0 (new schema module), `plugins/team-execution` 2.12.0→2.12.1
(documentation-only pointer update to the new
`plugins/saga/references/dispatch-adapter-contract.md` from
`external-engine-workers.md` — no team-execution code change, since `ENGINE_INTENTS`
resolution is declarative and new rows join it automatically). `.claude-plugin/marketplace.json`
mirrored for all four; `check_release_surface_parity.py` green.

### Runtime ladder climbing: one rung, effort-first, throw-with-proposal is the attended ask gate {#runtime-ladder-climbing-364}

**Context.** `docs/plans/2026-07-06-runtime-ladder-climbing-plan.md` (#364). The tier ladder had
plan-time merge (#369) and a manual mid-run lever (#365) but no *runtime* reaction to a failure
signal — a refuted unit threw and a human guessed the next tier from the transcript.

- **KTD1 — pair-level climb is effort-first, then model, one rung per event.** Effort is the
  cheapest increment; model dominates spend, so it climbs last. Runnability is validated via
  `supports_effort`, never assumed. *Rejected:* model-first (spends the dominant axis first).
- **KTD2 — `escalate_tier` returns `None` at the top; callers convert to HALT.** The palette's
  `escalate` no-ops at the top (vocabulary contract, `fleet_commons` untouched); runtime
  halt-not-loop semantics belong to the consumer.
- **KTD3 — attendance is emit-time (`emit --unattended`), never spec state.** A run property, not
  a plan property; precedent `outcome.py --autonomous`. Existing specs round-trip byte-identical.
- **KTD4 — the attended ask gate is throw-with-proposal + the existing #365 lever.** An emitted
  workflow cannot question the operator mid-run; the refute throw carries the
  `escalation-proposal` and the `/work` loop confirms via `/tier` patch + re-emit. No new ask
  machinery enters the emitted script. *Rejected:* an in-script ask primitive (doesn't exist) or
  auto-climb-then-report (violates the attended asymmetric-approval rule).
- **KTD5 — silent climbs are strictly bounded: one climb per unit per run, ceiling-aware, then
  HALT.** Chained silent climbs are the loop/overspend failure the issue forbids. The `let`-vs-
  `const` declaration tracks *actual* reassignment (`_emits_climb_retry`), keeping all
  non-climbing emission byte-stable.
- **KTD6 — the cost delta is ordinal** (`<old> → <new> (+1 <axis> rung)`); no price-per-tier data
  exists in the repo — the priced classifier is #367's (same deferral as `commands/tier.md`).
- **KTD7 — `pull_cord` always batches to ONE coordinator entry** (attended and unattended); the
  R6 silent-climb permission is exercised on the refute path where the retry is cleanly boundable.
  v1 composition exclusions at `validate`: `iterate_to_consensus`, fan-out, no-panel (doc-review
  P1s — unbounded-spend / dead-wiring vectors). **Revisit when.** #366/#367 land spend telemetry +
  the priced classifier (chained climbs across runs), or a real unattended run shows cords are
  frequent enough to earn silent climbing.

### Persisted tier preferences: repo overlay > issue band > registry, and the band stamps at compile {#tier-defaults-368}

**Context.** `docs/plans/2026-07-06-persisted-tier-preferences-plan.md` (#368). Tier judgment was
evaporating at the end of every run — run N re-derived the same table cold as run 1. Two persistence
mechanisms (repo overlay, issue-carried band), one precedence rule.

- **KTD1 — `.saga/tier-defaults.json` is a committed per-repo file** (`.saga/` is not git-ignored —
  verified), schema `{"<work-shape>": {"model", "effort"}}`, owned by saga's new `tier_defaults.py`.
  Write-back dirties a *tracked* file by design: the repo accretes tier judgment, committed like any
  change. *Rejected:* the git-ignored `.claude/saga/` cache — that's machine-local session state
  (#365's ceiling lives there); a repo preference must travel with the repo.
- **KTD2 — the overlay is saga-side; `fleet_commons` is untouched** (additive-only 0.x contract not
  even exercised). The shared resolver keeps a single registry contract; per-repo layering is a saga
  concern.
- **KTD3 — write-back is read-merge-write, confirmed-override-only.** `write_tier_default` sets one
  key, never clobbers others; every persisted entry originates from an explicit operator confirmation
  in `/plan` (non-goal: silent auto-promotion). Loading re-validates existing entries, so a bad file
  can't be extended — it fails loud first.
- **KTD4 — asymmetric strictness on the two inputs.** The overlay (repo-authored config) and a
  *present* issue band both fail loud on malformation (`TierDefaultsError`, halt-not-degrade); an
  *absent* band is `None` and normal. The split: absence is the common legitimate case, malformation
  is a claim that something stamped wrongly and must surface.
- **KTD5 — one precedence function is the tested contract:** `resolve_tier_for_plan` = repo overlay >
  issue band > shared registry. The repo override is closest to execution, so it wins the coarser
  issue-time band; the band seeds only where no override exists.
- **KTD6 — mission-control stamps the band as an auto-populated body section, not a template/contract
  field.** `derive_tier_band(issue_type)` (defect/capability→`opus/high`,
  enhancement/context-update→`sonnet/medium`, exploration→`sonnet/low`, objective→none) + an
  idempotent `_append_tier_band` on the `_source_to_issue_body` *wrapper* — so every compiled body
  carries it and a future call site can't miss the stamp (the #369 post-merge-halt lesson). The card
  validator needs no change (it checks required H3 sections only), the sha256/parity-pinned generated
  contract is untouched, and the cross-repo canonical templates are untouched — the exact rabbit hole
  the doc-review flagged, avoided by riding the Lifecycle Origin auto-populate discipline. A
  cross-plugin roundtrip test (stamp with `sdlc_manager`, parse with `tier_defaults.parse_tier_band`)
  pins the format contract. **Revisit when.** The band needs to become author-visible in the canonical
  templates (then it enters the generated contract properly), or an org-level tier store supersedes
  per-repo v1.

### Tier floors & backend enforceability ship in two parts; the agent-frontmatter floor is deferred {#tier-floors-enforceability-369}

**Context.** `docs/plans/2026-07-06-tier-floors-enforceability-plan.md` (#369). The issue bundled three
mechanisms to stop a unit/teammate silently running below its intended tier. Grounding against the
post-#370 code showed two are clean and live; the third has no live producer today.

- **KTD1 — `TIER_ENFORCEABLE_BY_BACKEND` + `unenforceable_tier()` live in `execution_spec.py`, beside
  `SANDBOX_ENFORCEABLE_BY_BACKEND`.** Both are backend-keyed (a backend is an execution/outcome-spec
  concept, not a vocabulary one), and the sandbox matrix is deliberately kept out of the palette so the
  module needn't import `outcome_spec`. The vocabulary palette stays vocabulary-only. *Rejected:* putting
  the matrix in `tier_palette.py` beside `MODELS`/`EFFORTS` — mixes backend routing into the vocab.
- **KTD2 — v1 enforces the MODEL axis only.** `team-execution` maps to `{opus, sonnet, haiku}` (its
  agent-frontmatter set; no `fable`), so `fable/xhigh` HALTs there and passes on `inline`/`cc-workflows`.
  The EFFORT axis (`xhigh`) enforceability is entangled with per-teammate effort (the QUEUED
  `{#team-execution-per-teammate-effort}` lever), so it rides with the deferred mechanism 3 rather than
  half-shipping. Unknown backend → `frozenset()` (never permissive), mirroring the sandbox matrix.
- **KTD3 — `Unit.min_tier: Tier | None` reuses the `Tier` type + the `sandbox`/`verify` optional-field
  round-trip pattern** (parse only when present, emit only when non-None → byte-identical when absent).
  The floor validates as a normal (non-engine) tier, so an off-palette or unrunnable floor fails loud.
- **KTD4 — the floor clamp reuses the palette's `strongest()`/`stronger()` ladder ops (#370),** never
  re-derived index arithmetic — the `{#tier-vocab-ordering}` invariant. A segment collapses to one
  resident spawn, so any member unit's floor raises the whole merged segment tier.
- **KTD5 — mechanism 3 (agent-owned `tier-floor:` frontmatter) is deferred** to a follow-up issue that
  lands it with the per-teammate tier-override lever, so the field ships with a real producer *and*
  consumer. *Rationale:* the floor-bearing entities (named team-execution agents) are not the entities
  `team_emitter` tiers (synthetic `worker-<dir>` segments), and the override that would ever assign a
  sub-floor tier is itself unbuilt — shipping the field now would be a field consumed only by its test
  (the recurring dead-wiring failure). Operator-confirmed 2026-07-06. **Revisit when.** The
  `{#team-execution-per-teammate-effort}` override lever is built.

### `/tier` mid-run lever enforces at emit, and the live ceiling is the final word {#tier-mid-run-lever-365}

**Context.** `docs/plans/2026-07-06-tier-mid-run-lever-plan.md` (#365). A run-scoped `/tier` ceiling +
mid-run spec patch, so an operator can steer tier without aborting and re-planning.

- **KTD1 — session override is a git-ignored, machine-local single file** (`.claude/saga/tier-session-override.json`),
  schema `{ceiling, unit_overrides}`, owned by `tier_session.py`, off-palette fails loud. Per-session
  isolation is out of scope for v1 (single-operator).
- **KTD2 — enforcement is at EMIT, not in the resolver.** Both emitters clamp the final unit/segment
  tier to the ceiling before rendering; `inline` honors it advisorily. The shared-`fleet_commons`
  `tier_resolver.envelope_ceiling` is deliberately **not** touched — it is additive-only 0.x, has no
  live caller, and is #366's; extending it would be redundant with the emit clamp and a contract risk.
- **KTD3 — the ceiling runs BEFORE the #369 enforceability halt.** A ceiling that caps `fable -> sonnet`
  makes a segment spawnable by team-execution, so the halt judges the clamped tier. The clamp is
  downward-only (`tier_palette.clamp`, `{#tier-vocab-ordering}`), and the live ceiling is the **final
  word** — it can clamp below a `min_tier` floor (the operator's live override wins over the
  plan-authored floor; the downgrade is logged). *Rejected:* floor-wins — a live, deliberate operator
  cap should not be silently overridden by a plan-time default.
- **KTD4 — mid-run patch is a pure `patch_spec_tiers()` (not-yet-run units only) + a CLI re-emit.** The
  `/tier` command derives already-run ids from live run-state and is conservative when unavailable;
  patch -> validate (hard gate) -> emit rides the existing CLI seam.
- **KTD5 — R6 escalation gate is the minimal ask-rule, not a spend-delta classifier.** An up-ladder
  move (`is_escalation`) asks; cheapen/lateral is silent. The cost-weighted classifier is #367's.
- **KTD6 — R7 built in full (operator decision 2026-07-06):** `team_emitter` honors the override at
  emit; the segment-boundary isolation is the not-yet-run filter. Unlike #369 mechanism 3, R7 has a
  real segment-shed boundary and an emit-time consumer, so it was not deferred.

## 2026-07-05

### Effort becomes a first-class, validated, pluggably-honored field fleet-wide {#effort-first-class-363}

**Context.** `docs/plans/2026-07-05-effort-first-class-plan.md` (#363, companion to #362's
dispatch-time tier resolver). `model:` was already a real per-agent frontmatter field fleet-wide;
`effort` existed only as emitted A7 `Tier`-cell metadata and a real parameter on two of three
dispatch paths, never honored on the native Agent-tool teammate spawn team-execution uses. Closes
the standing `{#team-execution-per-teammate-effort}` queue item (`QUEUED.md`).

- **KTD1 — Honoring mechanism = first-class value + pluggable `inject_effort()` seam (Option C).**
  Honor the real knob where the path has it (Workflow `agent({effort})`, external-engine offload —
  already live); use a labeled `EFFORT_RIDER` proxy only on the native Agent-tool path; both behind
  one seam so a future native subagent-effort knob is a one-function swap. *Rejected:* (A)
  `EFFORT_RIDER` on every path — downgrades the two paths that already honor real effort to a prose
  proxy and hides the real-vs-faked split; (B) route team-execution onto the Workflow engine —
  dissolves its persistent named-teammate model (its reason to exist) and blurs the
  team(gated)/workflow(advisory) governance seam. Operator-confirmed.
- **KTD2 — `EFFORT_RIDER` is a `dict[str, str]` (`{effort → directive}`)**, structurally a
  prompt-preamble rider like `BUDGET_RIDER` (`execution_spec.py:132`) but keyed by effort rather
  than a single cheap-tier string. Injected via the same `parts.append(...)` +
  `"\n\n".join(parts)` pattern the two `BUDGET_RIDER` sites use.
- **KTD3 — Vocabulary source is `tier_palette.EFFORTS`/`MODELS`** (`fleet-core`, canonical since
  #463). Never re-declare the tuples; never cite the stale `execution_spec.py:52-53` (they
  re-export via the shim). Resolves a stale-citation concern flagged during #363 review.
- **KTD4 — The cascade wraps #362's `tier_resolver.resolve()`** — #363 is its first real consumer.
  `resolve()` has no "team-default" parameter, so the cascade is not one call: `resolve()` supplies
  the base layer (agent-frontmatter default via work-shape registry), with the team default and the
  plan-authored per-unit tier applied above it, most-specific wins. The provenance line records
  which of the three layers supplied the winning value.
- **KTD5 — Chaperone exclusion preserves the intent-driven default; it does not override.** The
  offload (`sonnet/medium`) and second-opinion (`opus/high`) rows are intent-driven
  recommendations, so the cascade skips chaperone workers entirely rather than resolving then
  restoring — keeping the two intents pulling in opposite directions as designed.
- **KTD6 — The R2 lint is a new glob+membership shape**, distinct from the existing hardcoded
  `PINNED_AGENTS` value-pinning test. It reuses `_parse_frontmatter`, globs
  `plugins/*/agents/*.md`, asserts membership in `EFFORTS`/`MODELS`, and honors a
  `tiering_exempt` escape hatch.
- **KTD7 — Reconcile is honest per path.** "Actual effort" means the effort passed to
  `agent()`/the engine on real-knob paths, but only "the rider text reached the prompt" on the
  Agent-tool path — the seam cannot observe harness reasoning spend there. The drift line names
  the path and the compared quantity so it never overclaims.
- **Revisit when.** Claude Code ships a real native subagent-effort knob (KTD1/KTD2's one-function
  swap point), or #370 lands ladder operations the cascade could adopt.

---

### One saga-local, hash-chained, leaf-produced run-fact ledger substrate; derive-on-read views {#run-fact-ledger-401}

**Context.** Phase 0 item 10, final (#401, objective #338). A single `run_fact.v1` ledger that spend /
cache / engine-usage / delegation telemetry all write into, landed empty of most consumers so the ≥8
wave-1 writers inherit one format instead of N. `plugins/saga/scripts/run_ledger.py`.

- **KTD1 — saga-local, not fleet-commons.** Every consumer (`engine_dispatch`,
  `lifecycle_state.recommend_execution_backend`, `outcome`) is in saga; no cross-plugin consumer exists
  (the #348 fleet-commons trigger). Precedents: `manifest_store.py`, `outcome_costs.py`. Fleet-wide
  adoption + a fleet-commons move are documented follow-ups, not this issue.
- **KTD2 — a distinct hash-chained `run-facts.jsonl`, separate from the replay ledger.**
  `outcome_store`'s `ledger.jsonl` (`append_ledger`) is append-only but **un-chained** and serves
  crash-replay; the run-fact ledger reuses its durable-append discipline (`resolve_common_dir`,
  `O_APPEND`, `_heal_torn_tail`) and adds a `prev_hash`→`this_hash` chain. Not an overload.
- **KTD3 — derive-on-read, no committed summary.** `rollup`/`reuse_ratio`/`last_n_prior` computed from
  the stream each read (mirrors `outcome_costs.rollup`). Binding: `#outcome-economics-stance`.
- **KTD4 — leaf-produced facts; the coordinator only aggregates** (each fact carries its `subplot_id`).
- **KTD5 — the `engine` fact is telemetry, never a gate.** The `engine_dispatch.dispatch(ledger=…)`
  wiring writes facts without touching `satisfy_gate`/dispatch behavior; omitting the ledger is a no-op.
  Binding: `#external-engines-never-gatekeepers`.
- **KTD6 — `run_fact.v1` + `kind` discriminator, forward-tolerant readers** (unknown kinds/fields and a
  torn trailing line never crash a reader).
- **KTD7 — no `outcome_costs.py` migration (non-goal).** Coexists; porting it + adopting the wave-1
  writers are follow-up.

**Tamper-evidence, not tamper-resistance.** `verify_chain` catches in-place mutation / reorder /
middle-deletion (a fact can't be silently altered or buried) but not a full-access rewrite or trailing
truncation — acceptable because the store is machine-local and never committed. Documented in
`references/run-fact-ledger.md` so no consumer over-claims.

**Revisit when:** a non-saga plugin needs to write facts (fleet-commons move), or the wave-1 writers /
`outcome_costs` migration land.

### Remote gate approval defers sender-auth to the transport; saga carries the code, redis-channel stays router-agnostic {#remote-gate-approval-379}

**Context.** Phase 0 item 8 (#379): give the durable `/outcome` R20 frontier-approval gate a second,
unattended delivery surface — the fleet's own redis-channel / Discord channel — so a gate that fires
while the terminal is unattended can be answered remotely. This is a remote-**approval** security
feature; the trust boundary (a channel prompt-injection must not forge an approval) is the crux.
Operator chose **option A** (2026-07-05): defer access to the transport, record provenance.

- **KTD1 — v1 wires only the `/outcome` R20 gate; per-skill `AskUserQuestion` gates are contract-only.**
  The R20 gate is the only operator gate with a durable structured record (`approvals/r{rev}.json`);
  per-skill gates have no durable record and wiring one would be a *new* gate mechanism
  `{#operator-choice-framework}` forbids. A durable per-skill gate record is deferred follow-up.
- **KTD2 — defer sender-auth to the transport; never reimplement an allowlist (option A).** Verified
  against real code: Discord `gate()` (`server.ts:236-294`) drops non-`allowFrom` senders before the
  session ever sees them (`:813` returns on `drop`; the `:836` comment states the exact "already
  gate()-approved … so we trust the reply" model); redis-channel `_dispatch` (`redis_consumer.py:159-194`)
  delivers unconditionally and defers to its router. So AC4's "access-policy-approved sender" is
  enforced *upstream of the session* on both transports. `parse_gate_answer` records the already
  authorized `answerer`/`transport` as provenance and correlates only a pending gate id — it never
  re-authorizes a sender. **Rejected:** an in-plugin allowlist (violates router-agnosticism); coupling
  the gate to Discord `access.json` (couples to one transport).
- **KTD3 — provenance extends the write-once `approvals/rN.json` dict, not a new schema.** `answerer`/
  `transport` are added conditionally; `frontier_approved` is existence-only, so a terminal approval
  stays byte-identical and the extra keys are backward-compatible. **Rejected:** a net-new dataclass
  (over-engineering).
- **KTD4/KTD6 — render via the existing `reply()` inline-choice shape + a gate-id correlation; answer
  recognition is contract + a pure parse helper, not a background daemon.** No new Redis stream or
  protocol verb. The gate id is `<outcome_id>@r<spec_revision>` (mirrors the approval key + pins the
  revision, so a stale reply can't match the current frontier). `parse_gate_answer` is fail-closed:
  ambiguous/unattributable/no-pending-match → `None`, never a default *approve*. The mirror to the
  existing permission-reply pattern is **trust-model only** — that reply is router-intercepted
  (`server.ts:837`); the gate answer is session-recognized as an ordinary `<channel>` inbound.
- **KTD5 — the gate logic lives in `saga`; `redis-channel` stays router-agnostic.** New saga module
  `outcome_gate_transport.py` (stdlib-only, imports neither `outcome_spec` nor redis-channel) holds
  compose/parse; the only redis-channel change is a docs-only `PROTOCOL.md` note documenting the
  transport-agnostic convention (a router MUST NOT special-case gate notices).

**Delivery is session-driven for both transports** (doc-review P1 correction): the session holding the
gate composes with `compose_gate_notice` and calls the connected transport's `reply()`. The Python
`emit_gate_notice`/`publish_outbound` seam is redis-channel-only (Discord has no Python-callable
producer; a bare `outcome advance` CLI has no Redis client/`chat_id`/`session_name`), retained for a
future Python driver, not the v1 hot path.

**Revisit when:** a transport supports button/`react()` answers (the Discord button handler
`server.ts:744-800` is the future seam), or a durable per-skill `AskUserQuestion` gate record is built.

### One shared 429 retry/backoff primitive in fleet-commons; emitted-wave JS mirror + derived-on-read `/outcome` re-pick {#shared-retry-backoff-primitive-348}

**Decision.** Consolidate the fleet's four disconnected 429 responses onto one hardened
`retry_backoff` primitive in **fleet-commons** (`plugins/fleet-core/scripts/fleet_commons/`,
stdlib-only), adopted by the two unifi clients, mirrored as an emitted-JS `__retry` helper in every
`.workflow.js` parallel wave, and consumed by `/outcome` dispatch as a derived-on-read
`retriable-pending` classification (#348).

**KTD1 — primitive lives in fleet-commons; consumers vendor the shim.** Per the #463 commons
decision, `retry_backoff.py` goes under `plugins/fleet-core/scripts/fleet_commons/` (not saga), so
consumers couple to the stable commons, not saga's churn. Each consumer vendors the byte-identical
`fleet_commons_shim.py` and calls `fleet_commons_shim.load("retry_backoff")`; the shim copies are
drift-guarded by `tests/test_fleet_commons_resolution.py`.

**KTD2 — `agy_delegate` is scoped OUT.** `agy_delegate.py` has no HTTP 429 surface (its rate-limit
manifests as a subprocess timeout, not a 429 status); wiring auto-relaunch retry there would invent
speculative subprocess-relaunch semantics and risk double-spending tokens on a genuinely
non-transient failure. Safer, not merely easier: the primitive (incl. the fault-injection-tested
`CircuitBreaker`) is **import-ready** for agy/codex adoption when an engine bridge exposes a real
rate-limit signal. Consequence: no agy release bump, no `test_agy_delegate.py` change.

**KTD3 — emitted-wave retry is a dual-impl JS mirror, not a shared import.** A `.workflow.js` runs
as JS and cannot import the Python primitive, so `execution_spec.py` emits a `_JS_RETRY_HELPER`
(`__retry`/`__is429`/`__retryBackoffMs`, `function`-only so it perturbs no emitted-shape golden,
deterministic backoff with no `Math.random`) and wraps each `parallel([...])` wave thunk (all three
`_emit_thunk` forms) and refute-N panel verifier `agent()` call. Retry is scoped to **waves** (the
concurrency-driven rate-limit hotspot); singleton `await agent()` calls stay unwrapped, which also
preserves the singleton emission goldens. Rejected: wrapping every `agent()` call (scope creep + a
larger golden blast radius for no wave-level benefit).

**KTD4 — `retriable-pending` is a derived-on-read RESULT label, never a committed `NODE_STATE`.**
`NODE_STATES` deliberately excludes `retriable-pending`; adding it would be a committed status-field
change the derived-on-read model forbids. Instead a 429'd dispatch (`BackendRateLimitError`) writes
**no commit** — the leaf's derived state stays `ready`, so the ready frontier re-picks it on the next
`advance()` call with no operator action and no git/ledger mutation. A per-call `retriable_seen` set
de-hammers a `loop=True` run. This is distinct from a HALT (backend down → operator attention): a 429
is transient and self-clearing. Every non-429 failure keeps HALTing exactly as before.

**Rejected alternatives.** (a) saga-hosted commons — couples consumers to saga's churn (#463 already
rejected this). (b) A committed `retriable-pending` node state — violates derived-on-read and would
need a persisted status write on a transient condition. (c) Executing the emitted JS in tests to
prove retry — there is no JS runtime in the suite, so retry semantics are asserted structurally on
the emitted string, consistent with every other emitter test.

**Revisit when** an engine bridge (agy/codex) exposes a real rate-limit signal — wire the
import-ready primitive + `CircuitBreaker` into the bridge and add the `rate_limited` dispatch-result
producer (the `make_dispatcher` translation is already in place, awaiting that producer).

### `/outcome start --from-objective` seeds the DAG from GitHub sub-issues; edge inference is best-effort over stable fields {#outcome-from-objective-ingestion-375}

**Decision.** Wire `discover_subissues.py`'s GraphQL reader into `/outcome start --from-objective
<owner>/<repo>#<N>`, producing one node per sub-issue with kind-from-label, an authored terminal
`state` for closed sub-issues, a `github` provenance stamp, and inferred `depends_on` edges. Ingestion
writes **structural spec state only** (nodes, `depends_on`, `github`, authored `state`) — never a
committed status field or a completion event (KTD2). `Node.state` is authored structural spec state
(validated against `NODE_STATES`), distinct from the mutable board status column the derived-on-read
model replaces, so CLOSED+COMPLETED→`done` / CLOSED+NOT_PLANNED→`rejected` is permitted.

**KTD1 — edge inference uses only stable GraphQL fields and degrades to no-edges.** The relationship
source is `trackedIssues` (a tracker depends on what it tracks); we do not reference a speculative
`blockedBy`/dependency field because an unknown field **400s the entire query** (all-or-nothing), which
would break ingestion rather than degrade it. The relationship fetch is isolated so any error yields an
empty `blocked_by`; `edges_from_relationships()` is a pure function fixture-tested independent of the
live schema; node ingestion never fails on missing relationship data. Edge inference is therefore
best-effort — the fixture tests validate the *mapper*, not GraphQL→`blocked_by` fidelity, which is
heuristic. (Implementation narrowed the approved plan's `trackedIssues`+`timelineItems` to
`trackedIssues` only — the timeline cross-ref path needs inline-fragment GraphQL for marginal yield; a
clean follow-up.)

**KTD3 — the produced spec always passes `validate()`.** `edges_from_relationships` keeps only edges
whose both endpoints are ingested, and builds incrementally with a reachability guard that drops (and
reports) any edge that would close a cycle of any length — so the `OutcomeSpec.validate()` declared-target
+ Kahn-acyclicity checks never fail on ingested output. Dangling and self edges are dropped and reported
too, never silently discarded.

**Revisit when.** Richer edge inference is wanted (add the `timelineItems`/issue-dependency source), or
GitHub exposes a stable issue-dependency GraphQL field to replace the `trackedIssues` heuristic.

### `board_progression.py` extracts the certificate-gated board writer as a shared mechanism; the allowlist stays in the certificate {#board-progression-shared-writer-344}

**Decision.** Extract `/outcome`'s per-op board-write mechanism (authorize → idempotency ledger →
bounded-retry write → fail-loud record) from `outcome_board_sync.reconcile_board` into a plugin-agnostic
`board_progression.py` with a `write` CLI, and wire `/work` (post-merge) + `/loop` (render) onto it.
Caller-specific *policy* (leaf-state derivation, schema resolution, drift-hold) stays with each caller;
only the *mechanism* is shared (KTD1). `reconcile_board` delegates with zero behavior diff — proven by
60 unchanged tests — injecting `outcome_store._write_once` as the ledger writer to preserve exact
atomicity and the existing monkeypatch seam, and re-exporting `_safe_ledger_name`/`_default_board_writer`
so `outcome_reconcile` and `outcome.py`'s call sites are untouched.

**Rationale.** Widening *who* writes the board (from `/outcome` to `/work`/`/loop`) must not widen *what*
may be written autonomously. Because `board_progression` routes every op through
`reversibility_certificate.authorize_write` and re-derives no verdict, the autonomously-writable set is
structurally fixed by the certificate registry: merge/deploy op-kinds are absent (default-GATE) and
`PARENT_ISSUE_CLOSE` is `ALWAYS_OPERATOR` (KTD2). A new consumer cannot escalate autonomy without
bypassing the certificate, which the single-writer design and R3 tests forbid — which is also why inline
was the cheapest-correct backend despite the issue's team-execution recommendation.

**KTD6 — the writer ships a CLI.** `/work`/`/loop` are markdown skills that invoke `python3 …/*.py`, not
Python importers, so a library function alone is unbuildable by its consumers; the extraction moves
`default_board_writer` (the `OpKind`→mission-control mapping) into the module and exposes
`write --op … --repo … --number …`, printing a record JSON the skill branches on (`written` fired,
`gated` → fall back to the operator-prompted `mission-control` path).

**KTD3 — `/loop` renders, `/work` writes.** `/loop`'s first principle is route-and-sequence, not
execute-phase-work. So `/loop`'s consumer role is the read-only `project_arc` render (a pure derived-on-read
projection over durable saga fields, never a writable board column — KD4); the autonomous allowlisted write
fires from `/work`'s post-merge path, which owns the merge. Rejected: wiring `/loop` to write the board —
violates its router principle and duplicates `/work`'s authority.

**Revisit when.** A consumer needs an op the certificate does not yet allow (that is a certificate change,
reviewed on its own), or rollback execution is wanted (v1 records the write; it does not undo — the
certificate declares inverses as data only).

### `ship_ceremony.py` resolves by explicit `--saga-id` (and skips terminal sagas by-branch) so task ceremonies finish on `main` (pending commit) {#ship-ceremony-saga-id-resolution}

**Decision.** `resolve_saga` gains a `saga_id` parameter with top precedence (`saga_id` >
`issue_ref` > by-branch), surfaced as `ship_ceremony run --saga-id <id>`. The by-branch fallback
additionally excludes `done`/`abandoned` sagas.

**Rationale.** A task-kind ceremony has no `issue_ref`, so it resolved by current branch — but after
`checkout_main` the saga being shipped still records its *feature* branch, so a by-branch match on
`main` can never find it and instead collides with every saga left on `main` (18 at the time, 14 of
them terminal). An explicit stable key is the only thing that survives the branch change; it mirrors
the existing `--issue-ref` path. Excluding terminal sagas is a correctness fix in its own right (a
`done` saga is never a live ceremony target) and shrinks by-branch pollution, though it alone was
insufficient — 4 non-terminal sagas remained on `main`.

**Rejected alternatives.** (1) Exclude-terminal only — insufficient: the ceremony's saga isn't on
`main` at all (feature branch), and 4 active sagas still collided. (2) Resolve by the ceremony's
recorded branch instead of the current branch — fragile and implicit; an explicit key is clearer and
matches `--issue-ref`. (3) File as a tracked issue — skipped as disproportionate overhead (operator's
call), same as the two changes it follows.

**Revisit when:** a single branch legitimately hosts multiple live sagas that must each be shippable
without an explicit key (would need a richer disambiguator than status + branch).

**Refs.** Fixes LEARNINGS `{#ship-ceremony-task-saga-resolve-on-main}`; follows
`{#ship-ceremony-autoclose-fixes-line}`; ships in saga 0.56.0.

### `ship_ceremony.py` injects `Fixes #N` so merges auto-close the tracked issue (pending commit) {#ship-ceremony-autoclose-fixes-line}

**Decision.** `_do_open_pr`'s fresh-create path adds a `Fixes #<N>` line (parsed from the saga's
`issue_ref`, `owner/repo#N`) to the PR body, alongside the existing `Plan:` link — so merging
auto-closes the tracked issue. Bundled with the #480 follow-up: `head_sha`/`last_commit_sha` now
refresh on every save like `branch` (no default-branch guard needed — SHAs have no downgrade
concern).

**Rationale.** #477's fix shipped but its issue was left open because the manual `gh issue close`
step was forgotten, and the plan-of-attack `[x]` tick gave a false "done" signal. A `Fixes #N` line
makes closure a property of the merge rather than a separate step to remember — the structural fix
for that whole miss class. Guarded on `issue_num.isdigit()` so task-kind sagas (no `issue_ref`) and
malformed refs add no line.

**Rejected alternatives.** (1) A post-merge `gh issue close` inside the ceremony's `merge`
transition — rejected: more API surface and it races the merge; `Fixes #N` is declarative and
GitHub-native. (2) File the two changes as tracked issues under #340 — skipped as disproportionate
overhead for a solo repo (operator's explicit call); both are small, understood, and
campaign-adjacent.

**Revisit when:** a ceremony PR must reference an issue in a different repo than the PR (the bare
`Fixes #N` form assumes same-repo), or a PR should link multiple issues.

**Refs.** Follows [#ship-ceremony-open-pr-push-478] and the #477 close-miss; ships in saga 0.55.0.

### `ship_ceremony.py` pushes at `open_pr`, not `merge`, to close the front-loaded stale-HEAD gap (pending commit) {#ship-ceremony-open-pr-push-478}

**Decision.** Fix issue #478 (`_do_open_pr`'s front-loaded/existing-PR branch flips the draft PR
ready without pushing the commits accumulated since `start()`) by pushing the branch in that
branch — before `gh pr ready` — via a new shared `_push_branch` helper also called from
`_do_commit`. The `merge` transition is deliberately left unchanged.

**Rejected alternatives.** (1) Pushing at `merge` too, as issue #478's body hinted ("ideally
merge/request_review") — rejected: `/work`'s round-N PR continuation loop already re-pushes
post-`open_pr` commits (`work/references/pr-continuation-loop.md:33,35`), so the only unpushed
window is `start()`→`open_pr`; and a merge-time push would reset required CI checks to pending,
after which `_do_merge`'s `gh pr merge --squash` (no `--auto`) fails — or on a non-gated repo
merges unvalidated code, the exact bug class. (2) A merge-time read-only "refuse if local ahead
of remote" guard — rejected as redundant with `/work`'s staleness gate
(`pr-continuation-loop.md:36`) and as a new failure mode that could block legitimate autonomous
completion. (3) Inlining a second `git push` rather than extracting `_push_branch` — rejected to
avoid argv drift between the two push sites (and to keep `_do_commit`'s argv identical so the
existing `fail_prefix` test still matches).

**Rationale.** Remote-vs-local integrity *at merge* is `/work`'s responsibility (round-N re-push
+ staleness gate); the ceremony's only gap is the front-loaded accumulation window, which the
`open_pr` push closes exactly. Pushing before flipping ready means CI validates the real HEAD.

**Revisit when:** `/work` stops owning the round-N re-push, or `ship_ceremony.py` gains a
post-`open_pr` transition that itself accumulates commits — either would reopen the question of a
merge-time integrity check.

**Refs.** Plan `docs/plans/2026-07-05-ship-ceremony-open-pr-push-478-plan.md`; follows
[#ship-ceremony-request-review-noop-477] (the previous ship_ceremony defect fix).

### `saga.py` refreshes `branch` from live git on every save, not just the first (pending commit) {#saga-branch-refresh-on-every-save-480}

**Decision.** Fix issue #480 (`save()` locks `branch` at its first-ever value, so a saga minted
on `main` by `/plan` before its work branch exists carries `branch="main"` forever) with a
**protected live-git refresh**: `branch` refreshes from live git on every save
(`if live_branch and not downgrades_work_branch:`), but a save made back on the default branch
(`main`/`master`) never overwrites an already-stored real work branch. Scope the behavior change
to `branch` alone; leave the sibling `head_sha`/`last_commit_sha` fields on first-save-only capture.

**Rejected alternatives.** (1) *Pure* live-git-wins (drop the first-save-only guard outright,
`if git["branch"]:`) — this was the plan's first draft and is **wrong**: `ship_ceremony.run`
records progress via `saga.py save` after every transition, so the save after `checkout_main`
resets `branch` to `main` right before `branch_delete`. `/work`'s test gate caught it with two
`test_ship_ceremony.py` failures (green on `origin/main`, red under the draft fix). The downgrade
guard is what makes auto-refresh ceremony-safe. (2) An explicit `--branch` CLI override instead of
auto-refresh — rejected: `/work` already re-saves on the work branch (`work/SKILL.md:151`), so the
refresh makes that instruction true with zero caller changes, whereas a flag requires every caller
to remember it. (3) Fix `head_sha`/`last_commit_sha` in the same change — deferred per the issue's
explicit branch-only scope (audit found refresh safe: `head_sha` → `status_card.py:307`
display-only CI ref; `last_commit_sha` → no behavior-gating consumer).

**Rationale.** The ceremony **does** re-save the saga (to record `ceremony_transition`), and
`_do_branch_delete` reads the *stored* `branch` after `checkout_main` has already run — so the
field must survive a save made on `main`. The protected refresh does exactly that: it tracks the
work branch when `/work` saves on it, and refuses to downgrade that to `main` when the ceremony's
own progress-save lands back on the default branch. `main`/`master` is not arbitrary —
`_do_checkout_main` hard-codes `git checkout main`, so the guard mirrors the ceremony's constant.
The guard that tripped on #477 and #478 stays intact; the fix removes the bad input, not the guard.

**Revisit when:** a caller legitimately needs to record a branch different from the current
checkout (would motivate a `--branch` override), the default branch is renamed away from
`main`/`master` (widen `_DEFAULT_BRANCHES` or detect it dynamically), or the
`head_sha`/`last_commit_sha` follow-up lands.

**Refs.** Plan `docs/plans/2026-07-05-saga-branch-refresh-480-plan.md`; downstream of
[#ship-ceremony-open-pr-push-478] and [#ship-ceremony-request-review-noop-477] (this is the third
ship-ceremony-adjacent defect surfaced by the fleet-execution campaign).

## 2026-07-04

### `ship_ceremony.py` `request_review` becomes a no-op, not a resolved-login reviewer request (pending commit) {#ship-ceremony-request-review-noop-477}

**Decision.** Fix issue #477 (`_do_request_review` always fails: `gh pr edit --add-reviewer @me` is
not a valid login for the `requestReviewsByLogin` mutation) by making the transition's body a no-op,
rather than resolving the real authenticated login via `gh api user -q .login` and requesting that.

**Rejected alternatives.** Resolving the real login and passing it to `--add-reviewer` — rejected
because this repository has exactly one human maintainer, who is also the sole author of every
ceremony PR; requesting review from yourself has no one to add value regardless of whether the
call would technically succeed. (GitHub's reviewer-request path is widely understood to also
reject self-review requests, which would make that path trade one known-fail call for a
plausibly-still-fail call — offered as context, not verified, and not needed to justify this
decision on its own.) A configurable-reviewer flag was also rejected as unwarranted surface for a
single-maintainer repo with no near-term second reviewer.

**Revisit when:** a second human maintainer joins this repository — at that point
`request_review` should resolve and request that person's real login instead of staying a no-op.

> **ADR-style records of plugin-pattern / convention / tooling choices.** When you commit a chosen path over alternatives — pick A over B, flip a flag, change a threshold, choose a category, adopt a tool — capture rationale + tradeoff + revisit-when condition + commit hash.
>
> The point is to make **revisit conditions explicit** so a future Claude (or human) reading "why did we pick X?" gets the answer cold, including when it would be right to reconsider.
>
> **Append new entries to the top.** Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short title (commit hash)  {#slug}
>
> **Decision.** What we picked.
> **Rejected alternatives.** What we considered and didn't pick.
> **Rationale.** Why this won.
> **Revisit when.** Condition that would change the calculus.
> **Refs.** Related LEARNINGS / QUEUED / narratives.
> ```
>
> When new evidence invalidates a decision, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**.

---

## 2026-07-05

### Release-surface single source: canonical CHANGELOG grammar + license/category stay marketplace-owned (#429, planning)  {#release-surface-single-source-429}

**Decision.** Canonical `CHANGELOG.md` grammar (KTD1): file title exactly `# Changelog`, version
headings `## [X.Y.Z] - YYYY-MM-DD` (bracketed version, hyphen-minus date separator), optional
`## [Unreleased]`. Separately (KTD2), `sync_marketplace.py`'s generator treats `license` and
`category` as marketplace-owned pass-through fields — preserved from the existing entry on
regeneration, never sourced from `plugin.json` — because no plugin's `plugin.json` carries either
field today and adding them is an out-of-scope schema change per the issue itself.

**Rejected alternatives.** For CHANGELOG grammar: `deploy`'s/`saga`'s unbracketed
`## X.Y.Z - date`; `team-execution`'s plugin-name-suffixed title; `mission-control`'s em-dash date
separator — all three shapes are already live in the fleet and are exactly what the lint now
rejects. For license/category: adding both fields to every `plugin.json` was considered and
rejected as an unnecessary schema change the issue explicitly scopes out; a repo-wide default with
no override was also rejected since `--category` differs meaningfully across the 9 plugins already
(e.g. `infrastructure` vs no category on `mission-control`).

**Rationale.** The chosen CHANGELOG grammar is the plurality shape already in the fleet (5 of 9
plugins match it exactly, minimizing edit surface); its bracketed-version, hyphenated-date shape is
also literally what Keep a Changelog recommends, so no plugin adopting Keep-a-Changelog conventions
in its header prose needs to change anything but non-conforming heading lines. Treating
license/category as marketplace-owned resolves a genuine contradiction in the issue's own DoD
(which says the generator derives them "from `plugin.json`") without a schema change, and keeps the
generator's `--check` mode meaningful (it only flags drift on fields that actually have a single
source of truth).

**Revisit when.** A 9th-plus new plugin's provenance needs a materially different CHANGELOG shape
(e.g. auto-generated release notes from conventional commits); or the fleet decides `license`/
`category` do need a real source of truth (auditable per-plugin, not marketplace-only) — at that
point a small explicit source file (not a `plugin.json` schema change) is the likely next step.

**Refs.** Plan `docs/plans/2026-07-05-release-surface-single-source-plan.md`. LEARNINGS
`{#marketplace-drift}` (`docs/engineering-journal/LEARNINGS.md:1516-1533`) is the drift bug this
issue converts from a guard-class fix into a generator.

---

## 2026-07-04

### ship_ceremony.py: reversibility tiers stay local, ceremony state rides the work-thread saga, git-surface entry is an alias never a hook (#345, planning)  {#ship-ceremony-primitive-345}

**Decision.** `ship_ceremony.py`'s transition table (commit → open_pr → request_review →
merge → checkout_main → pull → branch_delete) gets its own local `Tier` registry
(`reversible` / `additive` / `always_operator`) rather than reusing
`reversibility_certificate.py`; its resumable state is written as new `ceremony_state` fields
on the issue's existing work-thread saga tick (via new `saga.py save --ceremony-transition` /
`--ceremony-tier` flags) rather than a dedicated side-channel store; its terminal-only entry
point (R4b) is a local (`--local`, repo-scoped) git alias (`git ship`) installed/uninstalled
by the primitive itself, never a real git hook (`pre-push`/`post-commit`).

**Rejected alternatives.** (1) Reusing `reversibility_certificate.py` for ceremony
transitions — rejected because that module's own docstring scopes its `OpKind` allowlist to
mission-control board/issue verbs and explicitly excludes "merge, deploy, and repo-level
mutations" (its R20); forcing git/gh ops through it would fight its closed-allowlist design.
(2) A dedicated `.claude/saga/ship-ceremony/<branch>/` ledger mirroring `outcome_store.py` —
rejected because every ceremony run already has a governing issue saga keyed by `branch`,
and a second store means `/work` reconciling two state sources on resume. (3) A real git
hook as the git-surface entry point — rejected because a hook auto-fires on a git event with
no confirmation step, directly conflicting with the requirement that merge/PR-open/review-request
stay explicitly operator-confirmed.

**Rationale.** Each choice keeps the primitive's state and authority inside mechanisms that
already exist and are already trusted (the work-thread saga, `/work`'s confirmation
boundary) instead of adding a parallel one. The git-alias choice is genuinely novel ground —
no git-alias-installer precedent existed in this repo before this issue.

**Revisit when.** If a future primitive needs reversibility tiering for git/repo-level ops
beyond ceremony (not just mission-control writes), consider promoting the local `Tier`
vocabulary into a shared registry rather than each primitive re-declaring its own — evaluate
once a second consumer appears (do not speculatively generalize now, per KTD1-adjacent
scope discipline).

**Refs.** Plan: `docs/plans/2026-07-04-ship-ceremony-primitive-plan.md`. Prior art excluding
repo-level ops: `plugins/saga/scripts/reversibility_certificate.py`. Program sequencing:
`docs/plans/2026-07-04-plugin-fleet-execution-order.md` (Phase 0 item 4).

### Fleet-commons distribution mechanism: fleet-core plugin + vendored resolution shim (#463)  {#fleet-commons-mechanism-463}

**Decision.** Cross-plugin shared primitives live in a new scripts-only library plugin,
`plugins/fleet-core/` (0.1.0), under `scripts/fleet_commons/` — one stdlib-only module per
primitive, loaded by path, never an installed Python package. A consumer plugin vendors one
byte-identical file, `scripts/fleet_commons_shim.py` (canonical copy in fleet-core; drift guarded
by `tests/test_fleet_commons_resolution.py::test_vendored_shim_is_byte_identical_to_canonical`),
which resolves the fleet-core root by a five-rung ladder with rung provenance in the return value:
(1) `FLEET_COMMONS_ROOT` env override, (2) repo-checkout walk-up from `__file__`,
(3) `~/.claude/plugins/installed_plugins.json` lookup by `fleet-core@` key prefix
(marketplace-agnostic), (4) cache-sibling highest-semver scan, (5) fail loud with an actionable
message. `FLEET_COMMONS_DEBUG=1` prints `fleet-commons: rung=<n> (<name>) root=<path>` to stderr.
First-mover primitive: the tier palette (`MODELS`/`EFFORTS`/`CHEAP_MODELS`/`ENGINE_INTENTS` +
rank helpers), consumed by saga (`execution_spec.py` re-export seam — its four intra-saga
importers untouched) and mission-control (`executor_profile_lint.py`, which enforces the
until-now-unenforced above-sonnet-requires-justification rule). Compatibility contract:
additive-only change to commons primitives within fleet-core 0.x.

**Rejected alternatives.** (a) *Hosting the commons inside saga* — avoids a ninth plugin but
couples every consumer to the fleet's fastest-churning surface: 14 cached saga versions on this
machine, and saga is the one plugin observed version-skewed right now (installed 0.49.0, repo
0.52.0, verified 2026-07-04 against `installed_plugins.json`). (b) *A published Python package* —
the marketplace install runs no pip/venv step (verified live: a plugin install is a bare
per-plugin per-version file copy under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`),
so the dependency would be user-managed and adds a publish/index surface the fleet has no tooling
for. (c) *The marketplace git clone as commons root* — `~/.claude/plugins/marketplaces/<mp>/` is a
full repo clone tracking marketplace HEAD, not the versions the user actually has installed, so
consumers would resolve code ahead of (or behind) everything else they run.

**Rationale.** The install layout (verified live 2026-07-04, all three surfaces inspected) leaves
no resolvable cross-plugin import path at install time — imports only work inside the monorepo
because pytest puts repo paths on `sys.path`, which is exactly the trap the install-time test
(`tests/test_fleet_commons_install_time.py`) closes by asserting rung-3 provenance, not import
success. `installed_plugins.json` (schema `version: 2` observed; values are *lists* of install
records with `installPath`) is the authoritative installed location and immune to cache-version
skew, hence rung 3 over rung 4. Vendoring the shim is safe where `validate_card_body` was not
(incident #222): that was an unguarded, growing hand-copy of active business logic; the shim is
minimal, rarely-changing bootstrap code with a byte-identity CI guard — the accepted residual
risk. Anti-sprawl (`{#plugin-portfolio-groom-17-to-7}` burden of proof): fleet-core is
consolidation, not sprawl — every future primitive that lands there is a hand-copy that never
gets made; the alternative is ~2 dozen independently drifting copies.

**Census (AC5, adapted).** The issue's "at least 28 pool ideas" was not reproducible from any
artifact (keyword censuses yielded 10–21 over `pool-final.json`, 19 over survivors; no artifact
enumerates 28 ids — operator-acknowledged adaptation, 2026-07-04). Recorded deterministic query:
case-insensitive regex
`cross-plugin|shared primitive|fleet-commons|fleet commons|hand-cop|shared (module|library|constant|vocabulary)|canonical (module|tier|palette|home)|import.{0,40}(another|other|sibling) plugin`
over `title`+`idea` of every record in
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/*.json` (`seeds.json` excluded) → 22 ids,
unioned with the 7 issue-named ids (6 not keyword-caught) → **28 ids**, enumerated in QUEUED
[`{#fleet-commons-dependents}`](QUEUED.md#fleet-commons-dependents). Delta from the issue's
figure: the count happens to coincide at 28; the enumerated list — not the number — is now the
canonical census.

**Revisit when.** A commons primitive needs its first breaking change (the additive-only 0.x
contract can't absorb it); or `installed_plugins.json` departs from schema `version: 2` (rung 3
already degrades to rung 4 on parse failure, but a durable schema change deserves a shim rev); or
a primitive needs non-stdlib dependencies (the no-pip constraint binds the whole design).

**Refs.** Plan `docs/plans/2026-07-04-fleet-commons-mechanism-plan.md` (KTD1–KTD6, grounding
table); issue #463; LEARNINGS [[#marketplace-install-layout-no-import-path]]; incident #222
(contract-mirror drift); `{#tier-vocab-ordering}`; `{#plugin-portfolio-groom-17-to-7}`.

### Gate-divergence entries stored as base64-wrapped JSON blobs, pipe-joined (#399)  {#pf-gate-divergence-json-encoding-399}

**Status.** Planned in `docs/plans/2026-07-04-gate-divergence-telemetry-plan.md` (Phase 0 item
2 of the `improve-claude-plugins` execution program).

**Decision.** The new `Saga.gate_divergence` field encodes each entry as base64
(`base64(json.dumps({"gate_id", "offered", "answer", "divergence", "latency_seconds"}))`)
joined pipe-separated across entries via the existing `_split_list` helper
(`saga.py:1177-1184`) — no change to `_split_list` itself.

**Rejected alternatives.** (1) `gate_verdicts`'s `gate:state:ref` colon convention
(`saga.py:1145-1168`): safe only because `state` is a closed 6-value enum
(`saga.py:1140-1143`); `gate_divergence`'s `answer` field is arbitrary free text, so a
positional-colon split would silently corrupt entries containing colons. (2) Raw (un-encoded)
JSON blobs pipe-joined, matching `--artifact-pointers`'s help-text convention
(`saga.py:1295-1298`): rejected after verifying during doc-review that nothing in the codebase
actually `json.loads`s an `artifact_pointers` entry, and that `_split_list` is a raw
`value.split("|")` with no escaping — a JSON blob whose `answer` field contains a literal `|`
would silently corrupt the split and misalign every subsequent entry. Treating that help text as
a working precedent without verifying a real consumer would have reproduced the "stale claim
asserted as fact" failure mode #461's KTD1 already flags for this program.

**Rationale.** Base64's alphabet (`A-Za-z0-9+/=`) contains no `|` by construction, so the
existing raw pipe-split is safe regardless of entry content — zero changes to `_split_list`,
zero new parsing primitives at the CLI layer.

**Revisit when.** If a future gate-record primitive (`pf-durable-gate-records`) replaces this
ad hoc field with a structured store, this encoding choice becomes moot and should be retired in
favor of that primitive's native schema.

**Refs.** Issue #399; `docs/plans/2026-07-04-gate-divergence-telemetry-plan.md` KTD1.

### Gate-divergence latency captured by the instrumented skill, no separate write-helper process (#399)  {#pf-gate-divergence-latency-399}

**Status.** Planned alongside the above.

**Decision.** Latency between a gate's offer and the operator's answer is captured by the
instrumented `SKILL.md`'s own inline `date +%s` calls bracketing the `AskUserQuestion` call,
passed into the same `saga.py save --gate-divergence` call already made in that skill's flow.
No new write-helper script or process boundary is introduced.

**Rejected alternatives.** A separate Python write-helper module invoked as its own process:
rejected because gate sites are prose instructions in skill files executed by the assistant
in-session, not a long-running process that could hold a timer across the offer/answer gap —
there is nothing for a helper module to wrap that the skill instructions don't already do via
inline shell timestamps.

**Rationale.** Zero new moving parts; rides the existing save-call plumbing exactly as
`orchestration_operator_choice` already does.

**Revisit when.** If `pf-durable-gate-records` introduces a real gate-firing event with its own
process boundary, latency capture should move there instead of living in skill prose.

**Refs.** Issue #399; `docs/plans/2026-07-04-gate-divergence-telemetry-plan.md` KTD2.

### Baseline-metrics citations re-verified at write-time, not copied from the issue (#461)  {#pf-baseline-citation-reverify-461}

**Status.** Shipped as `docs/plans/2026-07-04-plugin-fleet-baseline-metrics.md` (Phase 0 item 1 of the
`improve-claude-plugins` execution program, `docs/plans/2026-07-04-plugin-fleet-execution-order.md`).

**Decision.** When drafting the baseline metrics doc, re-derived every `grounding-brief.md:N`
citation directly from the file as it exists today, rather than trusting the line numbers issue
#461 quoted (e.g. the issue cited `:112` for the ship-ceremony metric; the file today has it at
`:119` — every one of the issue's 8 citations had drifted 3–10 lines from edits made to the brief
after the issue was drafted).

**Rejected alternatives.** Copying the issue's cited line numbers verbatim (faster, but would have
shipped a "before" baseline with stale citations — failing AC2/AC9 on first re-derivation, and
reproducing the exact "stale claim asserted as fact" failure mode the same grounding brief warns
about, §6 item 2).

**Rationale.** A citation into a *living* document (not a frozen commit or a quoted excerpt) is only
as good as its last re-verification. This baseline doc's entire purpose is to be re-derivable cold —
shipping unverified citations into it would undermine the artifact on day one.

**Revisit when.** Any future issue-derived plan cites line numbers into a document that is still being
actively edited; re-verify those citations at write-time rather than trusting the issue body, or cite
a commit SHA + line instead of a bare path + line if the source needs to be pinned exactly.

**Refs.** `docs/plans/2026-07-04-plugin-fleet-baseline-metrics-plan.md`,
`docs/reviews/2026-07-04-plugin-fleet-baseline-metrics-plan-review.md`.

---

## 2026-07-03

### Board-saga reconcile: reconstruct intent from the success-only ledger, trigger at the /outcome boundary (#295)  {#board-saga-reconcile-ktds-295}

**Status.** Shipped in saga 0.51.0 (`outcome_reconcile.py`; `advance --autonomous` detect-before-write +
the `outcome reconcile` verb). The doc-review revision of KTD7 (board Status read via `gh issue view
--json projectItems` in `outcome_github.board_status`, no mission-control verb) is what shipped.

**Decision.** Build #295's reconcile-on-wake as pure detection over #279's shipped board-sync
ledger: the baseline is ledger records + append-only `reconcile-override` records + expected values
*recomputed* from `derive_states`/`_candidate_ops`/the schema status map (no intent ledger, no #279
record-schema change). Detection auto-runs at the top of `advance --autonomous` (drift-holding only
the affected issue's ops) plus an explicit `outcome.py reconcile` verb. External closes are
contract-aware with `stateReason`: contract-satisfied + `completed` stays the harvester's sanctioned
silent path; `not_planned` or contract-unsatisfied closes are drift; unreadable `stateReason`
degrades to today's contract-only behavior. v1 field class = exactly what the writer writes (Status,
open/closed); resolution is HITL behind a `decide(drift, policy=None)` seam.

**Rejected alternatives.** (a) Two-phase intent/commit board-sync ledger — duplicates what
deterministic key/value recomputation gives free, and touches the scope-locked shipped writer.
(b) Trigger via `/resume` or a SessionStart hook (the issue's Q1 lean) — `/resume` is contractually
read-only on the world, and hooks are deadline-bounded/offline; board fetches don't belong there.
(c) Treating all external closes as drift (issue R1.6 literal) — fights the shipped harvester,
which already adopts a contract-satisfying close as GitHub-canonical completion, and would prompt
on every legitimately completed non-code leaf. (d) Label/comment-deletion drift — the writer never
emits label ops; every finding would be a false positive.

**Rationale.** Idempotency keys and target values are pure functions of observable state
(`reversibility_certificate.idempotency_key`, `outcome_board_sync._candidate_ops`), so the
landed-but-unrecorded crash case reconciles by recomputation — persistence would add a second
source of truth to keep honest. The `/outcome` boundary is where the ledger lives and where the
writer is about to act on a possibly-moved board, making detect-before-write the natural gate.

**Revisit when.** The writer starts emitting label ops (field class grows); a precedence policy
lands behind the R8 seam (HITL default changes); the harvester adopts `issue_close_info` (the
never-written-leaf `not_planned` blind spot closes); or `advance` gains a live read-before-write
guard (the accepted mid-run window shrinks).

**Refs.** Plan `docs/plans/2026-07-03-board-saga-reconciliation-plan.md`; issue #295 + brainstorm
`docs/brainstorms/2026-06-28-board-saga-reconciliation-requirements.md`; #279 shipped writer
`{#outcome-board-status-schema-resolve-326}` and `plugins/saga/scripts/outcome_board_sync.py`.

### Layer B dimension exclusion is honesty-gated, not counter-pressured — accepted for v1 (#293)  {#layer-b-exclusion-honesty-gap-293}

**Decision.** Ship `architecture-reviewer.md`'s non-applicable-dimension exclusion (#293 U4)
without a counter-pressure mechanism against over-exclusion. A reviewer that excludes a
dimension in bad faith (claiming "no architecture docs" to drop what would otherwise be a
low-scoring dimension) faces no penalty: exclusion is explicitly exempted from the re-review
path and does not lower the overall. An adversarial review pass (and its Stage-B validator)
confirmed this is *more* gameable than the fabricated-N/A-8.0-default it replaces — the old
default was a headwind dragging the overall toward 8.0; exclusion removes that headwind
entirely, so a would-be-blocking (<7.0) score can be made to vanish from the denominator rather
than fail the gate.

**Rejected alternatives.** (a) A runtime penalty or escalation for exclusion — no scoring
engine exists to enforce it; Layer B is prompt-only by design (KTD7), so any counter-pressure
would itself be prompt-enforced and equally honesty-dependent, adding complexity without
closing the gap. (b) Blocking #293 on this finding — the gaming surface is bounded to one
dimension (Architecture Documentation Coverage) on one reviewer, is strictly narrower than the
uphold-bias defect #293 exists to fix, and a runtime enforcement mechanism is a larger design
change than this issue's scope.

**Rationale.** Layer B's only enforcement lever available in v1 is the drift-guard test suite
(`tests/test_team_execution_consensus.py`), which pins the contract *text*, not whether a given
review applies it honestly — the same limitation the rest of the prompt-contract system
(reviewer scoring generally) already lives with. Accepting this now, with the gap explicitly
recorded, is preferable to silently shipping it undocumented.

**Revisit when.** A reviewer is observed (or suspected) excluding a dimension to reach ACCEPT
in a real review cycle, or Layer B gains a scoring engine / cross-reviewer audit step that could
carry a counter-pressure check.

**Refs.** infiquetra/infiquetra-claude-plugins#293;
`docs/code-reviews/2026-07-03-fix-293-verify-panel-robustness-code-review.md` (finding #3).

### Verify-panel missing-member KTDs: null-or-malformed detection, no v1 timeout, ⌈n/2⌉ floor, skeptical asymmetry (#293)  {#verify-panel-missing-member-ktds-293}

**Decision.** For #293 (plan `docs/plans/2026-07-03-verify-panel-robustness-plan.md`): (1) a
"missing" verifier is a `null` verdict **or** a non-null verdict lacking a usable `.refuted`
array (`v == null || !Array.isArray(v.refuted)`) — both are the harness/verifier failing to
deliver a trustworthy signal, and neither should be silently counted as a reporting non-refuter.
**Corrected during `/code-review`** (see `#verify-panel-malformed-verdict-superseded` in
ARCHIVE.md): the original decision treated malformed-non-null verdicts as already handled by
`completeness_gate.py`'s malformed-output failure class — that premise was false
(`completeness_gate.classify()` never inspects verifier panel verdicts, only the unit's own
result), so the malformed case is folded into "missing" instead of left unguarded. (2) No
verifier-level timeout in v1 — workflow scripts have no timer primitive
(`Date.now()`/`new Date()` throw for resume-safety) and `agent()` exposes no timeout opt, so a
hung verifier remains a harness/operator liveness concern. (3) Quorum floor = `⌈n/2⌉` of the
declared n, baked at emit time; recomputed threshold = `max(1, ⌈reported/2⌉)` (majority) /
`max(1, reported)` (unanimous), so all-missing is deterministically not-refuted. (4) Skeptical
asymmetry: a refutation over reporters always acts, even under-strength; the quorum floor only
annotates the accept path. (5) The recompute is emitted from one shared helper across all three
reconciliation sites (the `_verifier_agent_opts` precedent).

**Rejected alternatives.** `Promise.race` sleep timeout (no timer in the script sandbox); a
fixed floor of 2 (doesn't scale with n); suppressing under-strength refutations (reintroduces
the uphold bias being fixed); leaving malformed-verdict handling deferred to a follow-up issue
once the original rationale was shown false (the fix was small and mechanically localized to
the already-consolidated shared helper, so shipping it in the same PR was cheaper than tracking
a known, adversarially-confirmed gap across two PRs).

**Rationale.** See KTD1–KTD5 in the plan — each names the tradeoff; the load-bearing one is that
the defect under repair is *masked refutation*, so every ambiguity resolves toward skepticism.

**Revisit when.** The harness grows a per-agent timeout or scripts get a timer primitive (the Q1
residue becomes implementable), or real panel telemetry shows `⌈n/2⌉` mis-sized.

**Refs.** infiquetra/infiquetra-claude-plugins#293; `docs/reviews/2026-06-28-verify-panel-robustness-readiness.md`;
`docs/code-reviews/2026-07-03-fix-293-verify-panel-robustness-code-review.md` (finding #1, the
malformed-verdict correction).

### readonly-verifier fallback: Explore-first ladder, not general-purpose-only (#325)  {#readonly-verifier-fallback-ladder-325}

**Decision.** When `saga:readonly-verifier` is unresolvable in a session, degrade through a
two-step ladder documented in `sandbox-spawn-sites.md`: (1) `subagent_type: Explore` +
`isolation: "worktree"` — `Explore` structurally lacks `Edit`/`Write`/`NotebookEdit` while
retaining `Bash`, preserving the `mutation_policy: read-only` axis by tool omission; (2)
`general-purpose` + worktree + an explicit read-only prompt instruction, only if `Explore` is
also absent. `CLAUDE.md`'s ad-hoc spawn rule carries a one-line pointer into the ladder rather
than restating it.

**Rejected alternatives.** (a) `general-purpose`-only, as #325 originally proposed — simpler, but
loses the structural mutation-by-tool-omission guarantee when a stronger rung (`Explore`) is
already available in virtually every session. (b) Hard-fail with no fallback — rejects the
issue's graceful-degrade premise and reproduces the exact ungoverned-spawn outcome (#291) the
mandate exists to prevent. (c) A runtime roster-registration drift guard in CI — the running
session's agent roster is unobservable from CI, so this failure class cannot be tested directly;
the guard instead pins static discoverability preconditions (frontmatter validity, name/reference
consistency, fallback-doc presence).

**Rationale.** Tool omission is enforcement; a prose instruction to a tool-capable agent is a
request. `Explore` is already a saga-plugin dependency (used for fan-out grounding elsewhere), so
promoting it to the fallback ladder's first rung introduces no new dependency, and it strictly
dominates the issue's original proposal on the one property (`mutation_policy: read-only`) the
mandate exists to guarantee.

**Revisit when.** The harness exposes the running session's agent roster to hooks or CI (then a
true runtime registration guard becomes possible, superseding the static-precondition guard); or
`Explore` stops being a load-bearing saga-plugin dependency (then re-justify it as the fallback's
first rung independently).

**Refs.** LEARNINGS `{#stale-agent-roster-325}`; `plugins/saga/references/sandbox-spawn-sites.md`
"Fallback when `saga:readonly-verifier` is unavailable"; `tests/test_agent_registration_drift.py`;
issue #325; plan `docs/plans/2026-07-03-readonly-verifier-registration-fallback-plan.md`.

## 2026-07-02

### /outcome board status: schema-resolve from phase_board_map, not a literal swap (#326, plan)  {#outcome-board-status-schema-resolve-326}

**Status.** Planned (`docs/plans/2026-07-02-outcome-board-status-schema-resolve-plan.md`); ships with the #326 fix.

**Decision.** Replace the hardcoded `"In Progress"` in `outcome_board_sync._candidate_ops` with a
status resolved from mission-control's `sdlc-schema.json` `saga_lifecycle.phase_board_map`, mapping
leaf-state `ready` through the `review` phase row and `dispatched` through the `work` phase row for
the target project. Thread one `project` value from the `advance` call site to both the board writer
and the resolver; schema-resolution failure is per-op fail-loud + retryable (no ledger key), never
tick-fatal.

**Rejected alternatives.** (a) Literal `"Active"` swap — re-breaks on the next ladder/board change,
still wrong for campps, and couples the fix to the open Operations-ladder decision. (b) Resolving
the map in `outcome.py` and injecting it — strands the mapping logic away from its consumer and
bypasses the module's own testable seam.

**Rationale.** Operations/asgard run `intent_flow` (no `In Progress`); campps runs
`campps_initiative`. Only schema resolution is correct for all boards simultaneously and stays
correct under ladder changes. Known consequence: campps `ready` moves from `"In Progress"` to
`"Committed"` — the schema-correct value, asserted by test and called out in the CHANGELOG.

**Revisit when.** `phase_board_map` rows stop being single-element lists, a board gains a workflow
with no `review`/`work` row, or `/outcome` grows an operator-facing `--project` flag (then the
threading default should be revisited).

**Refs.** Issue #326; upstream `infiquetra-context-library/docs/plans/2026-07-02-operations-board-followups-plan.md`
(Workstream A/U1); verification corrections recorded in the plan's Problem Frame (nested
`saga_lifecycle.phase_board_map`; pre-existing `tests/test_outcome_board_sync.py` asserting the
buggy literal at `:102`).

### Typed artifact pointers: temp-index tree snapshot, 4 KB threshold, live-on-both-axes saga field (#291, plan)  {#artifact-pointer-ktds-291}

**Status.** Shipped in team-execution 2.8.0 / saga 0.49.0.

**Decision.** The typed-pointer plan (`docs/plans/2026-07-02-typed-artifact-pointer-passing-plan.md`)
commits: (KTD1) the issue-Q1 dirty-tree locator is a **temp-index tree snapshot**
(`GIT_INDEX_FILE=<tmp> git add -A && git write-tree`) pinned by a holding ref
`refs/team-execution/snapshots/<run-id>/<epoch>` — covers staged/unstaged/untracked, survives
`git gc`, resolves from linked worktrees, mutates neither the real index nor the worktree;
(KTD4) pointerize at **> 4 KB, or > 1 KB with ≥ 2 recipients; ≤ 1 KB always inline**; (KTD5) the
saga envelope gains one `artifact_pointers` list field shipped with producer + consumer + real-CLI
end-to-end test in one unit (dead-wiring rule, LEARNINGS
`{#dead-wiring-needs-producer-and-consumer}`); (KTD7) degradation is **capability-keyed** — git-object
pointers do not resolve in external-engine disposable clones
(`external-engine-workers.md:99-105`), so those paths keep inlined content.
**Rejected alternatives.** `git stash create` (skips untracked; dangling-object GC-bait); a
checkpoint commit (mutates history); routing diffs through the Layer-2 store (loses git's free
content addressing and worktree sharing); a new pointer envelope parallel to saga's path fields
(violates the no-back-edge rule, DECISIONS.md `{#saga-docs-source-model}` lineage).
**Premise drift honored.** The issue's "reviewers re-spawned fresh each cycle" premise was reversed
by the residency protocol (`consensus-protocol.md:53,169-170` — persistent teammates, delta-only
re-engagement); the plan sizes the win as N ≥ 3 initial full-diff copies + inlined deltas, not
per-cycle full re-sends.
**Revisit when.** External-engine envelopes need pointerizing (requires a clone-visible locator,
e.g. git bundle); or per-lens scoping gains a no-silent-drop guarantee; or live runs show the
4 KB threshold mis-set.
**Consensus-gate remediation (cycle 1).** A five-reviewer panel (all opus) surfaced two guarantee
gaps, now closed: (a) `git gc` **does** pack custom-namespace refs into `packed-refs` and delete the
loose file (verified empirically, git 2.54) — the KTD1 "survives `git gc`" claim held for the tree
*object* (pinned by the ref) but the gc *reclamation* went blind once the loose ref was packed,
leaking L1 refs and defeating R9. Fixed: snapshot refs are created with `--create-reflog`, enumerated
via `for-each-ref`, and dated by the reflog ENTRY timestamp — which survives both ref-packing and
`git gc`'s internal `reflog expire`, whereas the reflog file mtime does not (a cycle-2 correction:
the first fix dated by the file mtime, which `reflog expire` resets to now). (b) The KTD5
`artifact_pointers` field was producer-only — no skill read it back, and the e2e test's consumer leg
reused the in-memory store output, masking the gap. Fixed: `/resume` now derefs a restored tick's
pointers, and the e2e test crosses the persistence boundary (`saga.py restore` → `deref`). Also
hardened: L1 deref no longer parses the free-form `deref` string (a tampered `--output=` was an
arbitrary-file-write — security P1); argv is rebuilt from a validated `base` field; `symbol`-kind
deref rejects cleanly; sparse-checkout snapshots fail loud (KTD7). **KTD6 (script placement):**
`artifact_pointer.py` lives under `team-execution/skills/team-execution/scripts/` — team-execution is
now a **hybrid** plugin (its first executable script beside its skills/agents), no longer purely
skills-based.
**Revisit when (added).** The `base` tree OID needs authentication — it is format-validated
(`_is_git_oid`) but not cryptographically bound to the snapshot, so a tampered persisted pointer could
substitute another valid tree, yielding a misleading (but strictly git-object-store-confined, never
filesystem-escaping) diff on `/resume`; or the advisory KTD4 threshold / KTD7 fallback warrant runtime
enforcement (a capability preflight) over orchestrator judgment; or reflog-entry gc dating needs
revisiting under an aggressive reflog-expiry config (`git reflog expire --expire=now` or
`gc.reflogExpireUnreachable < 7d` — these refs point at trees, so the *unreachable* expiry applies and
the 30d default exceeds the 7d TTL), which would prune a snapshot's creation entry and leak the ref
(bounded, non-default-config).
**Refs.** #291; `docs/plans/2026-07-02-typed-artifact-pointer-passing-plan.md`.

### Team-spawn residency guard: name-only predicate, registry-parse trigger set (#289, plan)  {#team-spawn-residency-guard-ktds-289}

**Decision.** The warn-only spawn-shape hook (plan
`docs/plans/2026-07-02-team-spawn-residency-guard-plan.md`) commits six KTDs: (1) persistence
predicate is **non-empty `name` only** with matcher `Agent|Task` — the go/no-go probe found the
current `Agent` tool schema has **no `run_in_background` parameter** (live transcript + session
schema), so requiring it per S-1 U3's prose would false-warn on every correctly-named spawn;
(2) normalize `subagent_type` by stripping the `<plugin>:` prefix (live spawns use
`team-execution:security-reviewer`, registries hold bare names); (3) locate registries via a four-step pure-pathlib chain — plugin-root sibling (dev repo);
versioned-cache lookup reading `installed_plugins.json` for team-execution's **active**
`installPath` (installed layout is `cache/<marketplace>/<plugin>/<version>/`, so the naive
sibling path is wrong there; max-semver glob only as last resort when the registry file is
absent/unreadable); `CLAUDE_PROJECT_DIR`; then bounded cwd-ancestor scan — no subprocess (R11),
silent degrade when absent (D5); (4) parse the two registries per invocation, **no cache/materialized
file** — a data file would be the drift-prone second source R4 forbids, and two ≤5K reads are
negligible; (5) operator override via `TEAM_SPAWN_GUARD_INCLUDE`/`EXCLUDE` env vars, not a config
file; (6) no debounce in v1 — stateless per D4.

**Rejected alternatives.** Requiring `run_in_background` (field no longer exists); suffix-matching
`-reviewer`/`-tester` instead of registry parsing (violates R4, triggers on non-team agents);
materialized trigger-set data file (dead-wiring/drift); `git rev-parse` for repo root (subprocess
on the spawn hot path).

**Rationale.** The probe-before-plan gate in #289 paid off: the harness drifted from the S-1
protocol prose (`consensus-protocol.md:26` still names `run_in_background`), and only a live-source
check caught it. D6's sequencing gate is cleared — S-1 (#275) is closed and the residency prose is
live at `consensus-protocol.md:26,51-53`.

**Revisit when.** The `Agent` tool schema reintroduces or renames persistence fields; U3 worker
roles gain a parseable registry section (extend the parse, drop the INCLUDE workaround); telemetry
shows advisory fatigue (add debounce) or routinely-ignored warnings with real cost (revisit
blocking).

**Refs.** Plan `docs/plans/2026-07-02-team-spawn-residency-guard-plan.md`; requirements
`docs/brainstorms/2026-06-28-team-spawn-residency-guard-requirements.md`; S-1 record
[#worker-cache-scheduling](#worker-cache-scheduling) (KTD3/KTD4 context).

### Pre-push gate enforces CI's mypy step, not just documents it (#314)  {#local-gate-enforces-ci-mypy-314}

**Decision.** Add a `mypy` step to `tools/gate-manifest.json`
(`uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports`) so the *enforced*
pre-push gate runs it, and require it in the drift-guard test
(`test_manifest_contains_required_gate_steps`). This closes the loop on
`{#ci-mypy-scope-wider-than-local}`, which had aligned only the *documented* command in CLAUDE.md —
the gate the hook actually runs still never invoked mypy.
**Rejected alternatives.** (a) Rely on the documented command alone — rejected: documentation is not
enforcement; a dev who skips the manual command still pushes type errors (the #314 comment cites PR
#315's post-push Type Check failure, fixed in `1fdda3b`). (b) Hardcode the step in
`pre_push_gate_hook.py` — rejected: breaks the single-source manifest contract (R15/KTD10).
**Rationale.** The gate-manifest is the single source the hook executes; adding one step makes
local↔CI "green" mean the same thing with zero hook change.
**Revisit when.** CI changes its static-check set (a new linter, bandit becomes required, or mypy's
path scope shifts) — mirror it in the manifest and the drift-guard's `required` set in the same PR.
**Refs.** LEARNINGS `{#ci-mypy-scope-wider-than-local}`, `{#issue-premises-drift-314}`;
`.github/workflows/ci.yml:123`; `tools/gate-manifest.json`.

### Capability-scoped sandbox — implementation decisions (#287)  {#capability-sandbox-implementation}

**Status.** Adopted, ships in saga 0.47.0 / team-execution 2.7.0. Builds on
`{#capability-sandbox-plan-stance}`.

**Decision.**
- KTD1 — field name `sandbox`, an envelope of two axes (`Unit.capability` was taken by engine
  routing); profile-string shorthand expands at parse; `to_dict` emits expanded axes; absent = no
  key (existing specs byte-identical).
- KTD2 — native harness isolation (`agentType` + `isolation: 'worktree'`), not a per-leaf saga
  wrapper; `outcome_worktrees.py` granularity untouched.
- KTD3 — team-execution is authoring-time-unenforceable: `team_emitter.emit` raises `SpecError` for
  a restrictive-sandbox unit (residents run bypassPermissions with no per-leaf tool restriction).
- KTD4 — external face is a dispatch-builder change: agy `sandboxed-mutate` ⇒ patch-only +
  write_set; codex `sandboxed-mutate` ⇒ halt. No new isolation built.
- KTD5 — no hook interception (PreToolUse can't see the caller's profile).
- KTD6 — verify-class default has no opt-out (an opt-out would be an escalation channel
  contradicting R8).
- KTD7 — `.git`-shared worktree residuals accepted under the accidental-clobber threat model;
  documented in `sandbox-spawn-sites.md`, not defended.

**Rejected alternatives.** A shared `Sandbox` class imported across `execution_spec`/`outcome_spec`
— would cross the deliberate independent-houses boundary and leak the wrong error type past
`Node.validate`; mirrored instead, guarded by a cross-module drift test.

**Revisit when.** A team-execution per-leaf tool-restriction consumer exists (flips KTD3), or a
codex write adapter ships (flips KTD4).

**Refs.** `{#capability-sandbox-plan-stance}`; LEARNINGS `{#dynamic-module-reload-breaks-exception-identity}`.

---

### Capability-scoped sandbox stance (planned): `sandbox` envelope, native isolation, wire-don't-build external face (#287)  {#capability-sandbox-plan-stance}

**Decision.** Plan #287 as a two-axis `sandbox` envelope on `Unit`/`Node` (`mutation_policy` × `workspace_isolation`, profile shorthands `read-only-verify`/`sandboxed-mutate`), enforced by native harness primitives (`agentType` + `isolation: 'worktree'`) on inline/cc-workflows, authoring-time `SpecError` halt for team-execution, and the external write-ceiling lift as a **dispatch-builder wiring** of `agy_delegate.py`'s proven clone mechanism (`mode: "patch-only"` + unit `write_set`) — codex `sandboxed-mutate` halts.

**Rejected alternatives.** Naming the field `capability` (collides with #283's engine-routing `Unit.capability`); a saga-side per-leaf worktree wrapper (duplicates harness-native isolation and violates `outcome_worktrees.py`'s deliberate per-sub-outcome granularity); building a generalized owned-worktree harvest for external engines (duplicates the n=3-dogfooded clone + patch-import path); `PreToolUse` command interception (hook cannot see the caller's profile); the issue's full original scope (its "S-4/R11 unbuilt" premise was falsified by PRs #316/#317/#319).

**Rationale.** A trust-but-verify re-grounding on 2026-07-02 found the issue's center of gravity had moved: the external `sandboxed-mutate` face largely exists (remotes-stripped clone, `git diff <BASE_SHA>` harvest, out-of-scope-mutation detection — LEARNINGS `{#agy-pro-high-coder-dogfood-281}`), while the `read-only-verify` face (the clobber closer) is entirely unbuilt. Tool omission alone cannot stop the clobber (Bash `git checkout` needs no Edit/Write), so the isolation axis is the load-bearing layer.

**Revisit when.** A team-execution per-leaf tool-restriction consumer ships (flips that matrix row from halt to enforce); codex grows a write-capable sandbox flag (lifts its halt); an internal Claude leaf genuinely needs `sandboxed-mutate` (defines the internal owned-worktree harvest v1 deliberately omitted).

**Refs.** Plan `docs/plans/2026-07-02-capability-scoped-sandbox-plan.md` (Drift audit + KTD1-KTD7); requirements `docs/brainstorms/2026-06-28-capability-scoped-sandbox-requirements.md`; LEARNINGS `{#verify-agent-git-checkout-clobber}`, `{#agy-delegated-coder-contain-agency}`; DECISIONS `{#agy-delegated-build-no-jail}`, `{#antigravity-teammate-plugin-plan-stance}`.

---

## 2026-07-01

### Manifest carrier = git-common-dir `saga-manifests/` tree + typed `manifest_ref` pointer (#285 KTD1)  {#manifest-carrier-git-common-dir}

**Decision.** One JSON file per delegated invocation at
`<git-common-dir>/saga-manifests/<saga-id>/<execution-id>.json`, resolved through the same
`resolve_common_dir()` `outcome_store.py` already uses, plus a typed `manifest_ref` pointer key in
`CompletionEvent.payload` for outcome leaves.

**Rejected alternatives.** (1) `CompletionEvent.payload`-only — rejected: covers outcome leaves only;
fails R19 breadth because delegations that never emit a `CompletionEvent` (agy runs during plain
`/work`, team-execution outside an outcome) would have no manifest at all. (2) Saga tick pointer —
rejected: ticks are per-checkout, git-ignored, and worktree-local, so a bg-worktree manifest would be
invisible to `/code-review` running in main.

**Rationale.** `resolve_common_dir()` is the only candidate location that is both cross-worktree-stable
and already load-bearing for a sibling cross-worktree store (`outcome_store.py:93`), so reuse avoids a
second resolution mechanism.

**Revisit when.** A carrier needs to survive outside a single git checkout entirely (e.g. cross-repo
delegation) — the git-common-dir home stops being sufficient.

**Refs.** Plan `docs/plans/2026-07-01-evidence-provenance-manifests-plan.md`; issue #285; commit f2f7160 (U1-U2).

### Full-loop v1: producers + both already-shipped gates + advisory consumers, one PR (#285 KTD2)  {#manifest-full-loop-one-pr}

**Decision.** Ship the manifest schema, carrier, producers (external-engine + cc-workflows +
team-execution), both gate wirings, and the three advisory consumers (`/code-review`, `/qa`, `/retro`)
in one PR rather than sequencing gates after a contract-first landing.

**Rejected alternatives.** The requirements doc's contract-first sequencing (D7), which assumed the two
consuming gates did not yet exist.

**Rationale.** Drift-driven (V2 in the issue verification report): `completeness_gate.py` (#277) and
`engine_dispatch.py`'s `satisfy_gate()` (#283) already compute-and-discard exactly the data R11/R13
need persisted — gate wiring is persistence of already-computed data, not new verification logic, so
the sequencing risk the contract-first plan was hedging against doesn't exist.

**Revisit when.** A future manifest-consuming gate needs verification logic that doesn't already exist
elsewhere in the codebase — then contract-first sequencing becomes the safer default again.

**Refs.** Issue #285 drift report V2; plan `docs/plans/2026-07-01-evidence-provenance-manifests-plan.md`.

### Saga-local schema version key; external attestation vocabularies are prior art only (#285 KTD3)  {#manifest-schema-saga-local}

**Decision.** The envelope carries a saga-local `schema: "saga.manifest.v1"` version key rather than
adopting an external attestation vocabulary (in-toto, SLSA, PROV) wholesale.

**Rejected alternatives.** in-toto / SLSA / PROV adoption — rejected: those solve cross-organization
supply-chain attestation with signing and verifier ecosystems saga doesn't have; adopting one wholesale
is ceremony disproportionate to a one-operator plugin system.

**Rationale.** Field *naming* may still borrow from those vocabularies where it clarifies intent, but
that's a non-authoritative styling choice (D2), not a schema dependency.

**Revisit when.** saga manifests need to be verified or consumed outside this repo's own tooling (a
real cross-organization boundary appears) — then a real attestation format becomes worth the ceremony.

**Refs.** Plan `docs/plans/2026-07-01-evidence-provenance-manifests-plan.md` KTD3.

### Producer-claimed vocabulary stays three-valued: `verified | inferred | not-checked` (#285 KTD4)  {#manifest-producer-claimed-three-valued}

**Decision.** Keep the producer-claimed status vocabulary three-valued. At a gate, every gate-relevant
claim requires Claude adjudication before a verdict persists regardless of the producer's tag — the tag
never changes what the gate accepts, only where the verifier spends budget first (`not-checked`/
`inferred` before claimed-`verified`, per R15's budget-concentration logic).

**Rejected alternatives.** Collapsing to a two-valued `verified | unverified` — rejected: erases the
`inferred`-vs-`not-checked` distinction the verifier uses to rank attention, and buys nothing since the
producer-claimed layer is non-authoritative either way (D2).

**Rationale.** Closes R5's open question about gate-effect: the taxonomy exists to help the verifier
triage, not to grant any producer claim authority.

**Revisit when.** A producer tag needs to carry gate-relevant authority of its own (would contradict D2
directly) — not expected under the current "external engines never gatekeepers" decision.

**Refs.** Plan KTD4; `#external-engines-never-gatekeepers`; commit landing U1.

### Adjudicated-status taxonomy as a pure predicate, `is_parroting` unit-testable without I/O (#285 KTD5)  {#manifest-parroting-pure-predicate}

**Decision.** Adjudicated statuses are `verified | inferred | not-checked | refuted`; `mismatch_reason`
is `not-adjudicated | scope-excluded | source-stale | unsupported | refuted`. Parroting is counted iff
claimed-`verified` AND adjudicated is in `{refuted, unsupported}` (R7), implemented as a pure
`is_parroting(claim)` predicate in the schema module.

**Rejected alternatives.** Computing the parroting check inline at each call site (reader, gate) —
rejected: duplicates taxonomy logic and makes it untestable without constructing full manifest I/O
fixtures at each site.

**Rationale.** Matches the house pattern already established by `completeness_gate.py` ("pure Python,
no I/O at import") — a pure predicate is trivially unit-testable and has exactly one place to fix if
the taxonomy changes.

**Revisit when.** The taxonomy grows a case that depends on runtime state (e.g. a live source-freshness
check) — then `is_parroting` needs an injectable clock/fetcher seam instead of staying pure.

**Refs.** `tests/test_provenance_manifest.py`; plan KTD5.

### Rename `completeness_gate.check_manifest` → `check_required_keys` (#285 KTD6)  {#completeness-gate-check-manifest-rename}

**Decision.** Rename the existing `completeness_gate.py:172` function `check_manifest` (meaning
"required-keys check") to `check_required_keys` before landing the new provenance `Manifest` envelope,
since the two now collide in name but mean different things.

**Rejected alternatives.** Leaving the name as-is and relying on module-qualified imports to
disambiguate — rejected: cheap now (zero external callers per a repo-wide grep across `tests/`,
`plugins/`, `status_card.py`; module was two days old), confusing forever later once the new manifest
concept ships and both names are load-bearing.

**Rationale.** `classify()`'s behavior is unchanged by the rename; `tests/test_completeness_gate.py`
updated in the same unit (U4) that ships the rename, so there's no drift window.

**Revisit when.** N/A — mechanical rename, no future condition changes the calculus.

**Refs.** Issue #285 drift report V6; plan KTD6; commit landing U4.

### cc-workflows manifests are driver-materialized, not leaf-emitted (#285 KTD7)  {#manifest-cc-workflows-driver-materialized}

**Decision.** Workflow scripts cannot touch the filesystem (V13 in the drift report), so a cc-workflows
leaf cannot emit its own manifest file. The driving session persists one manifest per unit post-run via
`manifest_store.py record-completeness --spec <spec.json> --results <results.json>`, deriving the
declared contract from `completeness_gate.Contract.from_unit` and the produced side from returned
results; attribution (R2) uses the spec's per-unit label/model/effort.

**Rejected alternatives.** Requiring the cc-workflows leaf itself to write a manifest — rejected: not
possible given the workflow runtime's filesystem sandboxing; the issue's phrasing ("the producing agent
emits a manifest") needed this qualification for the cc-workflows leg specifically.

**Rationale.** The producer *declares* (in the spec and its return value); the driver *materializes*
(writes the file) — a clean split that matches how cc-workflows already separates producer intent from
driver-owned side effects.

**Revisit when.** The cc-workflows runtime gains a sandboxed filesystem write capability for leaves —
then leaf-emitted manifests become possible and the driver-materialization step could be dropped.

**Refs.** Issue #285 drift report V13; plan KTD7; commit landing U4.

### `/retro` surfacing via a new `manifest_reader.py`, sibling to `override_rate_reader.py` (#285 KTD8)  {#manifest-reader-sibling-override-rate}

**Decision.** Add `plugins/saga/scripts/manifest_reader.py` as an advisory reader (parroting count,
disposition rate, adjudicated-verified ratio) invoked by `/retro` alongside the existing
`override_rate_reader.py`, rather than folding manifest reporting into the override-rate reader itself.

**Rejected alternatives.** Extending `override_rate_reader.py` to also read manifests — rejected: the
two readers consume different carriers (override-rate reads saga tick history; manifests read the
git-common-dir store) and different questions; merging them would couple unrelated read paths.

**Rationale.** Mirrors an already-proven pattern in the same skill (`/retro` already invokes one
sibling reader), keeping each reader single-purpose and independently testable.

**Revisit when.** Two readers start needing to cross-reference each other's data for a single report —
then a shared aggregation layer above both becomes worth building.

**Refs.** Plan KTD8; `plugins/saga/skills/retro/SKILL.md`; commit landing U6.

### One schema, tier-sized payload — lightweight vs full manifest (#285 KTD9)  {#manifest-tier-sized-payload}

**Decision.** One schema serves both payload sizes (R9): a *lightweight* manifest is the envelope with
both subrecords absent (attribution + disposition + an existence bit); a *full* manifest adds the
`output_completeness` and `claim_provenance` subrecords. No second schema, no second store path —
`validate()` enforces that gate-feeding or contract-bearing outputs carry the relevant subrecord.

**Rejected alternatives.** A separate lightweight schema/store path — rejected: doubles the surface
area for no benefit, since the only difference is subrecord presence, which `validate()` can already
express as a constraint.

**Rationale.** Keeps the schema module single-sourced (one `Manifest` dataclass, one round-trip test
suite) while still letting low-stakes delegations skip the cost of computing subrecords they don't need.

**Revisit when.** A third payload tier is needed (e.g. partial subrecords) — then the binary
lightweight/full split stops being sufficient and `validate()`'s constraint logic needs to grow a real
tier enum.

**Refs.** Plan KTD9; `tests/test_provenance_manifest.py::test_advisory_never_blocks_no_verdict_field`
(covers the lightweight-valid-with-zero-subrecords case); commit landing U1.

### Tier the schema and gate-semantics units on Claude Fable 5 xhigh (#285 KTD10)  {#manifest-fable-xhigh-tiering}

**Decision.** U1 (the schema contract everything downstream consumes) and U3 (gate semantics) run on
Claude Fable 5 at `xhigh` effort — the highest generally-available capability tier, above Opus 4.8 —
bounded to 8 calls total (2 units + 2×3 same-tier verifiers). Mechanical units stay on the `sonnet`
alias, which the harness now resolves to Claude Sonnet 5.

**Rejected alternatives.** Running every unit at a uniform tier (e.g. all-opus or all-sonnet) —
rejected: the schema and gate-semantics units are the load-bearing, hardest-to-unwind design surface
(everything downstream consumes them), justifying the cost premium ($10/$50 per MTok vs Opus 4.8's
$5/$25) on a bounded call count, while mechanical units don't need it.

**Rationale.** `execution_spec.py:49-50` only accepted `opus|sonnet|haiku` × `low|medium|high` before
U0 extended `MODELS`/`EFFORTS` to include `fable`/`xhigh` — gated as U0 so later units could declare the
tier without a spec-validator change mid-campaign. Fallback if the Workflow runtime rejects fable
dispatch is opus/high.

**Revisit when.** Fable-tier costs or availability change materially, or a cheaper tier proves adequate
for schema/gate-semantics work on a future campaign.

**Refs.** claude-api skill (cached 2026-06-24); plan KTD10; commit 766145a (U0).

## 2026-06-30

### PreCompact spore = a two-hook structured re-grounding at the compaction boundary (#281)  {#precompact-spore-two-hook}

**Decision.** Guard the mid-run auto-compaction boundary with a two-hook "spore": a `PreCompact` hook
freezes the active saga box + the OutcomeOrchestrator DAG frontier to a session-keyed cache at
`<git-common-dir>/saga-spores/<session_id>.json`, and a **separate** `SessionStart(source=compact)`
hook reads it, unlinks before emitting (at-most-once), and re-injects it as a self-describing
`additionalContext` block. The DAG is frozen via `outcome.status()` (the single derived-on-read
source); outcome discovery is leaf-id-authoritative with a bounded best-effort store scan and a hard
"≥2 non-complete stores + no leaf-id → omit the DAG" anti-guess; serialization is a deterministic ≤9k
budget with the ready frontier never dropped + a counted-drop pointer; both hooks degrade silently AND
on a 1.5s SIGALRM wall-clock deadline.

**Rejected alternatives.** (1) A single SessionStart hook that branches — rejected: `PreCompact` cannot
inject (only `decision: block`), so the write-then-reinject split is *mandatory*, not a preference.
(2) Folding the compact path into `stale_main_session_hook.py` (KTD1) — rejected: a separate
`compact`-matched hook keeps the proven `startup|resume` path at zero regression risk. (3) Adding a
`Saga.outcome_id` field (KTD4) — rejected: the leaf saga id already encodes the outcome, so no schema
change is needed; ambiguity is closed by the anti-guess instead. (4) Writing a saga tick at PreCompact
(KTD8) — rejected: ticks land under the worktree-relative `.claude/saga` and would re-introduce the
vanish-under-removed-worktree hazard the git-common-dir cache exists to fix.

**Rationale.** The spore AUGMENTS the post-compaction window with authoritative structured facts beside
the lossy prose summary; it is the anchor, never the authority (committed docs + GitHub win on durable
conflict, R11). The git-common-dir home (mirroring `outcome_store`) is the only worktree-stable
location. Never blocking/stalling compaction is non-negotiable — the user is waiting on it — hence the
silent + bounded-deadline degrade (R12).

**Revisit when.** A clean session→saga binding source appears (`session_id` reaching `saga.py save`),
letting the same-cwd multi-session R9 limitation be closed with a real map; OR if the harness
`additionalContext` cap/spill semantics change (the ≤9k budget assumes >10k spills to a file, not
truncation).

**Refs.** Plan `docs/plans/2026-06-30-precompact-spore-rehydration-plan.md`; LEARNINGS
`#precompact-spore-grounding-corrections` + `#agy-pro-high-coder-dogfood-281`; commits 6e19dae (U1) →
a809194 (U5).

### Use mode-specific `agy` argv for the first-party wrapper  {#agy-wrapper-mode-specific-argv}

**Decision.** The `plugins/agy/scripts/agy_delegate.py` wrapper invokes `agy` in foreground print
mode with mode-specific execution flags: `no-write` adds `--sandbox`; patch-producing modes add
`--dangerously-skip-permissions`, `--add-dir <disposable-clone>`, and an absolute repository
boundary in the prompt packet before any patch is imported into the live tree.

**Rejected alternatives.** Rejected always using `--sandbox` because live proof showed write tasks
completed while modifying Antigravity's default scratch directory instead of the wrapper clone.
Rejected omitting noninteractive permission approval for write modes because live proof showed the
write path could sit silent until the no-output watchdog killed it. Rejected trusting `agy` stdout
claims because the plugin's contract is git-derived evidence and managed patch import.

**Rationale.** The wrapper's safety boundary is the disposable clone plus changed-path,
verification, and `git apply` gate. `no-write` benefits from sandboxed print mode because no patch
should be produced. Write modes need permission to modify the clone so the wrapper can derive a real
diff, but the live tree remains protected by the explicit write-set and apply policy.

**Revisit when.** Revisit if `agy` gains a noninteractive flag that writes inside a named workspace
without broad tool approval, if `--sandbox` gains a way to bind the repository root as the writable
scratch, or if live evidence shows write-mode `--dangerously-skip-permissions` can mutate outside the
disposable clone despite prompt and remote-removal controls.

**Refs.** LEARNINGS [#agy-print-mode-repo-boundary](LEARNINGS.md#agy-print-mode-repo-boundary);
harness proof `plugins/agy/docs/harness-proof.md`.

### Plan the Antigravity teammate plugin as an evidence-first `agy` plugin with clone-backed patch import  {#antigravity-teammate-plugin-plan-stance}

**Decision.** Build the new Antigravity teammate integration as a first-party `agy` Claude Code
plugin (`plugins/agy`) with `agy-coder`, `agy-reviewer`, and `/agy:delegate` all routed through one
Python wrapper and one versioned delegation envelope. The implementation plan chooses Bash-only
bridge agents, full local evidence bundles under ignored `.claude/agy/runs/<run-id>/`, fresh `agy`
invocations by default, and disposable local clone plus patch-import semantics for all write modes.
Marketplace registration is deliberately the final implementation unit, after direct wrapper tests
and live Claude Code harness proof.

**Rejected alternatives.** Rejected reusing the current upstream plugin as the product surface,
because the failures are command-shape, liveness, and false-provenance failures. Rejected a normal
raw `/agy:run` command for v1 because it invites bypassing the envelope. Rejected live-tree
delegation as the reusable teammate substrate because it makes apply safety post-hoc instead of
structural. Rejected early marketplace registration because this repo treats metadata as a shipping
surface.

**Rationale.** The requirements review left no P0/P1 product blockers, but it explicitly pushed the
plugin namespace, agent tool constraints, live harness proof, and evidence schema into planning.
Local evidence shows that a "delegated" run can be a Claude-clone fallback with zero `agy` calls,
and that background paths can hang with zero output. The wrapper therefore needs to make real-`agy`
proof, liveness, changed paths, and apply decisions machine-checkable before chat prose can claim
success.

**Revisit when.** Revisit the clone boundary if implementation proves local clones cannot preserve
the context `agy` needs, if OS-level sandboxing becomes available and cheap enough for v1, or if the
live harness proves Bash-only agents still cannot force the wrapper path. Revisit marketplace-last
sequencing only if release tooling gains a dormant/unadvertised plugin state with explicit tests.

**Refs.** Plan: `docs/plans/2026-06-30-antigravity-teammate-plugin-plan.md`; requirements:
`docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md`; readiness review:
`docs/reviews/2026-06-30-antigravity-teammate-plugin-requirements-readiness.md`; LEARNINGS
[#agy-delegate-silent-claude-fallback](LEARNINGS.md#agy-delegate-silent-claude-fallback) and
[#agy-delegate-plain-is-the-path](LEARNINGS.md#agy-delegate-plain-is-the-path); blueprint:
`docs/external-agent-delegation/blueprint.md`.

---

## 2026-06-29

### Pull the clone-jail from the #277 delegated-build protocol — contain by post-hoc verification, not isolation  {#agy-delegated-build-no-jail}

**Decision.** Build #277 by handing each unit to plain `/agy:delegate --model flash <task>` against the REAL working tree (the unit's write-set doubling as a tight in-prompt allow-set), then treating agy as a junior engineer: Claude reviews, FIXES, and is sole committer. Containment is **post-hoc verification** — `git status` changed-paths ⊆ allow-set, the FULL gate (`pytest` + `ruff format --check` + `ruff check` + `mypy`), mutation-proofing any tests agy wrote, and reading the diff — NOT workspace isolation. A failed draft is recovered by Claude fixing it (default) or one Pro retry; scrap threshold: never polish a fundamentally wrong draft.

**Rejected alternatives.** Rejected the originally-planned **clone-jail harness** (disposable clone, `remote remove origin`, `git` PATH-shim, `agy --sandbox` probe, sibling-repo/`~/.claude` FS audit, remote-drift check): too many moving parts, and every part requires the hand-authored `agy`/git shell scripting the operator has banned in this harness. Rejected building the units myself (loses the delegation-dogfood signal that is half the point of #277-as-n=2).

**Rationale.** n=2/U1 proved plain delegate + post-hoc verify contains cleanly with zero isolation: agy wrote only its two allow-set files (`git status` confirmed), 8/8 tests + `--self-test` rc=0, no fork, no jail. The harness already provides the load-bearing guarantees — sole-committer ⇒ a broken *uncommitted* tree never reaches `origin`; full gate ⇒ correctness; `git status` ⇒ containment. Isolation is the right tool for *independent agents with their own workspace* (the distributed-delegation topology), not an in-session junior-draft loop.

**Revisit when.** agy actually wanders outside its allow-set on a write job (then add a throwaway `git worktree`, or the clone-jail as an optimization), OR per-unit review-and-fix churn exceeds the cost of writing the unit directly (then stop delegating that unit class).

**Outcome (2026-06-29, full run — VALIDATED).** Shipped #277 via PR #303 (`b09ad50`, saga 0.40.0 / team-execution 2.4.0). The no-jail posture held across all three delegated units (U1/U2/U3): `git status` showed only allow-set paths every time, no wander, no rogue commit/push (the plain-delegate path never gives agy a jailed git to abuse, and sole-committer makes a broken uncommitted tree unable to reach `origin`). Review-fix churn was **cosmetic** — U1 clean; U2 a stray comment + an unapplied `ruff format`; U3 a clean draft with one accepted DRY residual — well under the "cheaper to write it myself" threshold. The one place the threshold *tripped* was a NEW failure mode, **F6 silent no-op**: U4 (prose) finished writing nothing, so it was hand-written. Net: the revisit conditions did not fire for code; they fired once for a prose unit. Regime question got a first positive data point (U3, a non-mechanical typed-halt + bounded loop, implemented correctly in-bounds).

**Refs.** Plan: `docs/plans/2026-06-28-silent-omission-completeness-gate-plan.md` (KTD6/KTD7 + Delegated Build Protocol); LEARNINGS [#agy-delegate-plain-is-the-path](LEARNINGS.md#agy-delegate-plain-is-the-path) + n=1 [#agy-delegated-coder-contain-agency](LEARNINGS.md#agy-delegated-coder-contain-agency); blueprint `docs/external-agent-delegation/blueprint.md` (clone-jail retained there as a deferred optimization).

---

## 2026-06-28

### Create-prepared GraphQL resolver stance (planned) {#create-prepared-graphql-resolver-stance}

**Decision.** Fix issue #280 by replacing mission-control's dual `issue(number:)` plus `pullRequest(number:)` GraphQL resolvers with `issueOrPullRequest(number:)` union queries, while keeping `_gh` and `_graphql` strict. The post-create part of `issue create-prepared` should become a resumable sidecar state transition: record the created issue URL/number before board-add and Status, then finalize only after both steps complete.

**Rejected alternatives.** Rejected blanket "return non-null data despite errors" handling because `_graphql` is shared by mutations and would hide failed board-add or Status writes. Rejected `_gh`-wide GraphQL partial-success handling because it would widen the success criteria for every CLI caller. Rejected auto-deleting a created issue on post-create failure because that is destructive and loses the issue URL operators need for recovery.

**Rationale.** The live probe in the requirements source showed the union query exits 0 for an issue while the current dual-branch query exits 1 with usable issue data plus a speculative PR `NOT_FOUND`. Keeping strict error handling preserves the safety boundary around mutation call sites, and the resumable sidecar guard addresses the real operational failure mode: a created issue abandoned before board membership and Status assignment.

**Revisit when.** Add a strictly scoped read-resolver partial-tolerance path only if a future GitHub GraphQL read genuinely cannot be expressed without nullable speculative branches. Revisit the sidecar state names if a broader prepared-draft state machine lands.

**Refs.** Plan: `docs/plans/2026-06-28-create-prepared-partial-graphql-error-plan.md`; requirements: `docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md`; readiness review: `docs/reviews/2026-06-27-create-prepared-partial-graphql-error-readiness.md`; issue: `https://github.com/infiquetra/infiquetra-claude-plugins/issues/280`.

---

## 2026-06-26

### OutcomeOrchestrator ships (U11): the feature-flip is a version-triad bump + advertise-the-complete-surface + a compose-it-all integration gate, NOT a retroactive drift sync; saga 0.38.0  {#outcome-release-flip-stance}

**Decision.** U11 is the **feature-flip**: it converts the saga CHANGELOG `[Unreleased]` block (the U1–U10 bullets) into a real `## 0.38.0` release, bumps `plugins/saga/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` to **0.38.0** (the release triad: plugin.json == marketplace.json == the CHANGELOG's first version heading), advertises the complete `/outcome` surface (the saga descriptions gain the OutcomeOrchestrator one-liner; the `outcome-orchestration` keyword replaces the redundant `sdlc`; the README + `docs/commands.md` move to **20 files / 19 routable**; the Command Matrix visual gains the `/outcome` coordinator card + bumps its subtitle to 19, regenerated so the golden test passes), and adds the **all-34 integration gate** `tests/test_outcome_integration.py`.
- **Per-unit KTD14 already kept each release surface in sync as it landed**, so U11 does NOT retroactively sync earlier drift — it does the one saga-feature-level flip (marketplace advertises `/outcome`; the integration suite proves the units compose). "Co-equal at release ≠ co-equal as work order" — the U1→U11 spine was the work order; the release bar is all 34 composing.
- **The integration gate proves COMPOSITION, not per-requirement pins.** The per-unit `test_outcome_*` suites pin each R1–R34 in isolation (1239 tests). `test_outcome_integration` drives the whole vertical slice through the **production** `advance` wiring (the same dispatcher + harvester + merge + worktree + liveness + cost + approval-gate processors the CLI uses) on a real DAG with a stateful fake `gh` and a real git repo — start → approve → dispatch → GitHub-canonical harvest (a non-code leaf on a closed issue, a code leaf on a merged PR) → auto-merge → cost rollup → report → projection → `complete`. A second test affirms the thesis in the positive (a parallel fan-out `beat_one_thread`). This catches a wiring/compose regression a unit test cannot.
- **The version bump is a MINOR (0.37 → 0.38).** A whole new `/outcome` capability is additive and backward-compatible (no existing command changed), so semver minor is correct for a pre-1.0 plugin; a major would falsely signal a breaking change.
- **bandit is informational, not blocking** — CI runs `bandit -ll ... || true`; the new `outcome_*` scripts are clean at `-ll` (the `# nosec B603/B404` annotations on the fixed-argv `gh`/`git` subprocess calls hold). The plugin-description `maxLength` is **200** (the validator), so the `/outcome` advertisement is a tight one-liner, not the verbose form.

**Ship-gate fold (the `verify-outcome-u11` adversarial pass returned `ship_ready: False` and was right).** The gate caught a **P0**: R26/R27 spec persistence was a NO-OP — `save_spec` wrote the working tree but nothing committed/pushed the spec to a branch, so the "all 34 ship" + cross-machine cold-reentry (F5) claim was false. Rather than downgrade the claim, the persistence was **implemented**: `commit_spec` commits + pushes the canonical spec to the outcome's own branch (refuses on `main`/`master`, R26 "not main"), exposed via `/outcome commit [--push]` + `/outcome advance --persist`, with a real-git test that reads the committed blob back (`git show outcome/<slug>:…outcome-spec.json`) to prove a different-machine pull reconstructs it. Three more folded: (P1) the integration gate did NOT exercise the dispatch seam — `merge_processor`-then-`harvester` completed both leaves on tick 0 before dispatch ran, so it passed with a raising dispatcher; hardened so a leaf's issue/PR resolves only after a settled dispatch record, and the test now asserts `dispatched == {design, build}`. (P2) the auto-merge queue ignored the DAG frontier — `process_merge_queue` now gates merge eligibility on `all(dep in success)`, so a clean PR with an incomplete (especially non-code) upstream is never squashed out of order. (P2) two stale `18/17` command counts in `docs/README.md` + `docs/boundaries.md` moved to 20/19. The gate's value: it blocked a release that asserted a requirement (R26/R27) that was genuinely unimplemented — exactly what a ship gate is for.

**Rejected alternatives.**
- *Retroactively re-sync every earlier-unit surface in U11.* Rejected — KTD14 kept them in sync per-unit; U11 is only the feature-level flip + the integration gate, not a drift sweep.
- *A major version bump (1.0.0).* Rejected — the change is additive/backward-compatible; minor is the honest signal.
- *Skip the integration gate (rely on the per-unit suites).* Rejected — unit suites pass while a compose/wiring bug hides between units (the integration test caught exactly that class during authoring: a fake-`gh` argv mismatch that would have masked a real harvest path). The all-34 ship-claim needs a composition proof.
- *The verbose `/outcome` description.* Rejected — it overran the 200-char `maxLength`; a tight one-liner advertises it within the schema.

**Rationale.** The whole 11-unit build paid down risk by landing each unit independently releasable (per-unit release-surface sync) so the feature could ship in one flip rather than a big-bang merge. Generalizable rule: **build a large feature as independently-releasable units kept release-surface-synced as they land, then ship it with a single version-flip + a composition integration gate — never a big-bang integration at the end.**

**Revisit when.** A `/qa` pass advances the outcome-orchestration saga past `lifecycle_phase=work` (deferred to the `/qa` rebuild). If `/outcome` grows operator-facing help that drifts from `docs/commands.md`, regenerate from the model. If a networked cross-host completion stream (Redis) is ever needed (the deferred scope boundary), it slots in behind the GitHub-canonical barrier.

**Refs.** `plugins/saga/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (0.38.0), `plugins/saga/CHANGELOG.md` (the `## 0.38.0` flip), `plugins/saga/README.md` + `docs/commands.md` (20/19), `scripts/render_docs_visuals.py` + `docs/assets/command-matrix.svg` (the `/outcome` card), `tests/test_outcome_integration.py`, `tests/test_release_triad.py` / `tests/test_saga_plugin.py` (the version + surface guards). Closes U11 of the [outcome-orchestration build plan](#outcome-orchestration-plan); ships the whole OutcomeOrchestrator (R1–R34) built across [#outcome-spec-validator-stance](#outcome-spec-validator-stance) … [#outcome-economics-stance](#outcome-economics-stance).

### Outcome economics (U10): cost is a leaf-produced ledger fact materialized into spec.cost_rollup (producer→spec→U8, no U8↔U10 cycle), "did the DAG beat one thread" = critical-path vs serial, missing telemetry is no-data-yet, pruned cost is sunk (U10 PR pending — SHA-fill on merge)  {#outcome-economics-stance}

**Decision.** U10 records the realized R24 telemetry and exposes the per-outcome rollup (the falsifiable cost-vs-operator-time proof) + the optimize/retro consumers. Conventions:
- **Cost is a LEAF-produced ledger fact, not a coordinator-computed one.** The coordinator never runs a leaf (R3), so it cannot know a leaf's tokens/wall — the leaf reports them via `record_cost` into the shared store as it finishes. The coordinator only *aggregates* (`rollup`) + *materializes*. This keeps R3 intact and makes cost telemetry a genuine producer/consumer pair (every field has both).
- **The producer→consumer edge is U10 → `spec.cost_rollup` → U8 (the report), NEVER U8 → U10.** The U8 stance forbids the report depending on U10 (it would cycle — `/optimize` and `/retro` consume the report). So U10's `cost_processor` (in `advance`) materializes the rollup into the canonical `spec.cost_rollup` field (R26), which the U8 report already renders — the report gains realized cost with **zero U8 code change** and no import edge to U10. Materialize is guarded on change (no per-tick spec churn).
- **"Did the DAG beat one long thread?" = critical-path vs serial.** `wall_seconds_parallel` is the DAG's critical path (the parallel lower bound, derived from `depends_on` + per-leaf wall); `wall_seconds_serial` is the sum (one inline thread). `beat_one_thread = parallel < serial`. A pure chain reports `False` honestly (no parallelism, no win) — the metric is falsifiable, not a foregone slogan.
- **Honesty (the U8 stance, kept).** No telemetry → an **empty** rollup → the report renders "no data yet" (never a fabricated zero). A leaf with no record is **counted as missing** (`leaves_with_cost`/`leaves_total`), never summed as 0. Cost against a **pruned** subplot (no longer in the spec) is reconciled into a **`sunk`** bucket — the pruned-node cost reconcile U7 deferred (R33), accounted not dropped.
- **`/optimize` + `/retro` are READ-ONLY consumers.** They cite the rollup (+ the existing `override_rate_reader` for the R12 operator-override signal) as a portfolio-shaped baseline/evidence; they never write cost telemetry (the leaves do). `/optimize` adds an Outcome-economics baseline section; `/retro` adds a §1.7 evidence pass with the same zero-data contract as its §1.6 R12 pass.

**Rejected alternatives.**
- *The report calls `outcome_costs.rollup` directly.* Rejected — that is the forbidden U8→U10 edge (a cycle); materialize into `spec.cost_rollup` instead so the data flows U10→spec→U8.
- *The coordinator computes cost.* Rejected — it never runs the leaf (R3); the leaf is the only party that knows its realized cost.
- *Wall-clock parallel = wall-clock of the longest single leaf.* Rejected — the critical path (longest dependency *chain* of walls) is the right parallel lower bound; a single long leaf understates a deep chain.
- *Sum missing leaves as 0 / fabricate a 0 rollup.* Rejected per the U8 honesty stance — "no data yet" + an explicit missing-count.

**Rationale.** The acyclicity discipline from U8 pays off: by making cost a *data* field on the canonical spec (not a code call), the producer (U10) and consumer (U8 report, /optimize, /retro) stay decoupled — the dependency edge is one-way through the artifact. Generalizable rule: **when a later layer must feed an earlier layer's render, push the value into the shared canonical artifact the earlier layer already reads — never add a back-edge import.**

**Revisit when.** U11 (the feature-flip) advertises `/outcome` + the realized-cost rollup in the released docs. If per-leaf cost needs sub-records (incremental token accrual mid-run rather than a final snapshot), extend `record_cost` to accumulate rather than latest-wins. If the critical-path proxy proves too theoretical, capture the DAG's actual wall-clock (first-dispatch → last-completion) as a measured `wall_seconds_parallel`.

**Refs.** `plugins/saga/scripts/outcome_costs.py`, the `cost_processor` + `production_cost_processor` wiring in `outcome.py`, `plugins/saga/skills/optimize/SKILL.md` + `skills/retro/SKILL.md` (§1.7), `tests/test_outcome_economics.py`; reuses `scripts/override_rate_reader.py` (R12 override signal). Implements U10 of the [outcome-orchestration build plan](#outcome-orchestration-plan); fills the U8 [report stance](#outcome-report-projection-stance) "no data yet" cost slot + the U7 [decompose stance](#outcome-decompose-worktree-stance) pruned-node cost reconcile; consumes the U9 [degrade stance](#outcome-backend-degrade-stance) executor-used telemetry.

### Outcome backend menu + degrade + liveness (U9): the menu is host-conditional + off-by-default, the degrade decision lives in the reconcile loop (not the dispatcher), HALT/degrade is presence×guarantee×side-effect, liveness is timestamp-derived (U9 PR pending — SHA-fill on merge)  {#outcome-backend-degrade-stance}

**Decision.** U9 completes the executor menu (R6), adds the presence-conditional degrade policy (R23), and enforces leaf liveness (R31). The load-bearing conventions:
- **The menu is host-conditional and OFF by default.** `resolve_available()` returns only the always-available floor (`inline` / `team-execution` / `manual`) unless the host explicitly advertises `--host-capable` / `--workflow-available`. The coordinator is a Python script that cannot probe the Claude Code host, so it never *claims* a backend it cannot verify — an unverifiable choice HALTs or degrades, never silently substitutes (R5). (This also preserves U4: a `fork` leaf with the conservative default still HALTs when attended.)
- **The degrade DECISION lives in `_reconcile_once` (the loop), not the dispatcher.** `degrade_decision` is a pure policy function; the loop invokes it (it has the node + the store), records the HALT/`DegradeReceipt` in the ledger, and dispatches on the *resolved* backend. The injected dispatcher is a pure minter given the full menu (it never HALTs in production — the loop owns the decision); a restricted/unit dispatcher can still raise `BackendHaltError` and the loop records it. This put the side-effecting record where the store is, without changing the str-returning `Dispatcher` contract that U4–U8 depend on.
- **HALT vs degrade is `presence × guarantee × side-effect`, in that precedence.** Attending → HALT (the operator decides, never auto-degrade under their nose); else guarantee-bearing → HALT (never run a guaranteed leaf on a lesser backend); else side-effected (a `destructive` leaf) → HALT (never duplicate a deploy/migration/write); else (autonomous + away + clean) → degrade one rung. Presence is a per-*advance* signal (`--autonomous`), not per-leaf — the coordinator can't know which leaf the operator is watching, so an interactive advance is "attending" and an unattended loop is "away."
- **`destructive` IS the side-effect proxy.** R23's "already executed partially (deploy/migration/write/repo-mutation)" maps to the existing `destructive` flag — a clean, derivable signal, no new field.
- **Liveness is timestamp-derived from the ledger (R31).** The dispatch `commit` record carries an `at`; a running leaf may `record_heartbeat`; `harvest_liveness` stalls a dispatched leaf that breaches `heartbeat_seconds` (since last activity) or `timeout_seconds` (since dispatch). The `stalled` terminal is idempotent (pages once) and cascades (R22) — the same sticky-terminal + cascade shape as U6 `rejected` / the U7 worktree-removed. A leaf with neither budget is never killed (opt-in timeouts).

**Rejected alternatives.**
- *Put the degrade decision in the dispatcher (the seam).* Rejected — the dispatcher has no store to record the `DegradeReceipt`, and threading a store/sink in at make-time (before the store exists) is fragile; the loop is the natural owner.
- *Default the full menu ON.* Rejected — the coordinator can't verify host capability; claiming `cc-workflows-ultracode`/`fork` it can't run would dispatch into a dead backend. Off-by-default + explicit enable is honest (and preserves the U4 HALT contract).
- *Degrade `fork`/`subagent`/`goal` to inline.* Rejected — they're not on R23's capability ladder; an unavailable off-ladder backend HALTs (no defined rung, no silent substitution).
- *A new `had_side_effect` field.* Rejected — `destructive` already captures it.
- *Liveness without timestamps (a tick counter).* Rejected — wall-clock budgets need real timestamps; the dispatch `at` + heartbeat `at` are injected so the check stays unit-testable.

**Rationale.** The recurring "the system that owns the resource is the guard / degrade-safe" lesson (U6 GitHub, U7 git) here becomes "the coordinator that owns the dispatch decision is the guard" — the loop, not the seam, owns HALT/degrade because only it has the store + node + presence. Generalizable rule: **put a side-effecting policy decision where the durable state and the full context live (the reconcile loop), keep the mechanism (the dispatcher) a pure minter, and make "is it safe to substitute" a presence×guarantee×side-effect gate that fails toward HALT.**

**Revisit when.** U10 consumes the `R24` telemetry this unit *captures* (executor used + the degrade/halt receipts) into the realized-cost rollup + the optimize/retro consumers. If a real host-capability probe becomes available, wire it into `resolve_available` instead of the manual flags. A degraded leaf could become a U8 consolidator signal (an "informational" tier) if operators want it ranked, not just in the Degradations section.

**Refs.** `plugins/saga/scripts/outcome_dispatcher.py` (`resolve_available` / `degrade_decision` / `recommend_outcome_backend` / `fork_is_cheap`), `plugins/saga/scripts/outcome_liveness.py`, the `_reconcile_once` degrade wiring + `liveness_processor` in `outcome.py`, `references/operator-choice.md` §8, `tests/test_outcome_backends.py`, `tests/test_outcome_liveness.py`. Implements U9 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U4 [dispatcher seam stance](#outcome-dispatcher-seam-stance) (HALT-no-fallback) + reuses the U6/U7 sticky-terminal + cascade shape. NOTE: the plan listed `lifecycle_state.py` for U9; the frontier-budget logic is an outcome concern, so it lives in `outcome_dispatcher.recommend_outcome_backend` (which reuses the saga-generic `lifecycle_state.recommend_execution_backend`) — keeping `lifecycle_state` saga-generic, and liveness is its own `outcome_liveness.py` rather than polluting `lifecycle_state`.

### Outcome reporting + consolidator + projection (U8): everything is derived-on-read, the report can't drift (no wall-clock), the consolidator is type-tier-then-leverage, U8 never depends on U10 (U8 PR pending — SHA-fill on merge)  {#outcome-report-projection-stance}

**Decision.** U8 adds three operator surfaces — the attention consolidator (R18), the report (R19), the mission-control projection (R25) — in two modules (`outcome_report` + `outcome_projection`). Conventions:
- **Everything is derived-on-read (R17), with NO operator-writable status field.** Every number/state in the report + projection is *computed* from the committed spec + the store (`derive_states`, `blocked_subtree`, `ready_frontier`), never read from a stored scalar an operator could set to lie. A test pins `projection["states"] == derive_states(...)` and the absence of a `status` key.
- **The report is deterministic so it cannot drift.** No wall-clock in the body → re-rendering on unchanged state is **byte-identical**. Combined with **overwrite-from-state** (never hand-edited), the artifact physically cannot diverge from the truth (R19/F6). The cost rollup renders **"no data yet"** when absent rather than a fabricated zero.
- **U8 depends only on U5/U6, never U10 — the acyclicity rule.** The realized cost (R24) is a *render slot* in U8 that shows "no data yet" until U10 populates it; making U8 read U10 would create a U8↔U10 cycle (U10's optimize/retro consume the report). So cost is rendered-when-present, and the dependency edge points U10→U8, not back.
- **The consolidator is type-tier-then-leverage (AE5), one kind per node.** Sort key = (tier, -leverage, sid): tier orders gate(1) → ambiguity(2) → failure(3); leverage = `len(blocked_subtree({sid}))` (downstream work gated). Classification precedence is failure (terminal-negative) → ambiguity (HALT receipt) → gate (gated/risky/destructive + dispatched), so a node is exactly one kind and a terminal node is never miscounted as a still-live gate.
- **The projection is a SECONDARY view; it never auto-closes the parent.** `parent_close = "operator-keystroke-only"` is encoded in the projection so a downstream mission-control consumer cannot mistake "complete" for "close the parent" — closing a parent stays the operator's deliberate keystroke (R25). U8 produces the projection *artifact*; the actual GitHub write is a separate operator-initiated consumer (no auto-push, no dead-wiring).

**Rejected alternatives.**
- *A timestamp / "generated at" line in the report body.* Rejected — it breaks determinism (every regen differs), defeating the "cannot drift" guarantee; provenance belongs in git history, not the artifact body.
- *Read realized cost from U10 in the report.* Rejected — a U8↔U10 cycle; render "no data yet" and let the edge point U10→U8.
- *Per-leaf pages for the operator.* Rejected per R18 — N pages is exactly the cognitive-overload failure mode; one ranked prompt, type-tier then leverage.
- *Auto-close the parent issue when the projection reads complete.* Rejected per R25 — closing a parent is a deliberate operator keystroke; the projection only reports.

**Rationale.** "Derived-on-read, no stored status" + "deterministic overwrite" together make a cockpit that *cannot lie*: there is no field to set wrong and no stale copy to diverge. Generalizable rule: **a status surface that is recomputed from canonical state every read and written deterministically has no failure mode where it disagrees with reality — prefer it over any cached/settable status, and keep the consuming layer (U10) depending on the producer (U8), never the reverse.**

**Revisit when.** U10 populates the realized-cost rollup → the report's "no data yet" slot fills in (no U8 change needed). U9's degrade receipts may add a fourth consolidator signal (a degraded leaf the operator should know about). When mission-control grows a real projection consumer, wire the operator-initiated push there (U8 already emits the artifact).

**Refs.** `plugins/saga/scripts/outcome_report.py`, `plugins/saga/scripts/outcome_projection.py`, `tests/test_outcome_report.py`, `tests/test_outcome_projection.py`, `docs/outcomes/_example-ship-auth/`; wiring in `outcome.py` (`report` / `project` verbs + consolidated `attend`). Implements U8 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U5 [completion barrier stance](#outcome-completion-barrier-stance) + the U6 [auto-merge queue stance](#outcome-merge-queue-stance) (evidence + merge state) + the U7 [decompose/worktree stance](#outcome-decompose-worktree-stance) (the `blocked_subtree` leverage signal).

### Outcome decomposition + worktree lifecycle (U7): worktrees are per-sub-outcome (not per-leaf), git is the liveness oracle, edits are atomic + state-aware, approval is per-revision (U7 PR pending — SHA-fill on merge)  {#outcome-decompose-worktree-stance}

**Decision.** U7 splits into two modules — `outcome_decompose` (graph editing) + `outcome_worktrees` (the durable worktree lifecycle) — that later units (U8 reporting, U9 degrade, U10 economics) build on. The load-bearing conventions:
- **Worktrees are per-SUB-OUTCOME, not per-leaf.** Only an `is_outcome` node (`child_spec_ref` set — an autonomous child outcome that runs concurrently with siblings) gets its own durable, named, owner-tagged worktree, **reused across all of that child's leaves**; a plain code leaf runs in the ambient outcome worktree and is unmanaged. This is the only reading of R15 ("one worktree per sub-outcome, not per subtask") that fits the per-node terminal model — the worktree-removed terminal (R32) is per-node, and a sub-outcome node IS the worktree-bearing unit.
- **git is the liveness oracle (the U6 lesson, generalized).** Whether a worktree still exists is read from `git worktree list` (the injected `WorktreeOps`), never from our own registry — so a worktree removed **out-of-band** is detected (it frees a cap slot + reaches the `rejected` terminal that cascades, R22/R32). The registry (`<store>/worktrees.json`) holds only what git can't carry (owner tag, shared-install ref, branch); it is written read-modify-write **under the coordinator lease** (single-writer, R13). A transient git failure degrades to **present** (never falsely terminate a live sub-outcome, R34) — the same degrade-safe stance as U6's `branch_exists`.
- **The cap defers, it never overshoots.** Past N live worktrees, provisioning returns `capped` (a page-and-wait), never an (N+1)th — an N-sub-outcome outcome cannot exhaust a solo machine. Heavy installs are **shared** across siblings via one `shared_install_ref` (the module records + propagates the *policy*; the physical symlink is the adapter's job — an honest "no fake install" boundary).
- **Every graph edit is atomic AND state-aware.** Atomic = the U1 `redirect_dependency` shape generalized to all six ops (snapshot → validate → bump revision + trail; a rejected edit leaves `nodes`/`depends_on`/`spec_revision`/`decision_trail` untouched, R26). State-aware = a **dispatched** node may not be pruned or elaborated (it would silently discard in-flight work) — a terminal transition first (R33). Live state is read derived-on-read (R17), never a stored scalar.
- **Approval is per-`spec_revision`.** The R20 dispatch gate ties directly to R33's versioning: approval is recorded against the current revision, and any structural edit (which bumps the revision) **re-closes** the gate — so a mis-drafted edit can never auto-dispatch before re-review. The gate sits **upstream of the backend HALT** (an unapproved leaf is gated, never reaches the dispatcher).
- **Orphan reconciliation runs AFTER the canonical prune commits.** A prune mutates+validates+bumps the spec first; only then (best-effort, through injected adapters) closes the sub-issue + reaps the worktree — so a rejected prune never closes a live issue. The sub-issue *producer* is U8 (projection); U7 wires the consumer (`issue_close`) but passes `None` in the CLI until U8 generates refs (a real consumer awaiting its producer, not dead-wiring).

**Rejected alternatives.**
- *One worktree per leaf.* Rejected per R15 (proliferation) — and it has no per-leaf terminal to attach the removed-state to; the sub-outcome is the right granularity.
- *A separate cross-tree worktree registry as the liveness source.* Rejected — the registry can drift from reality; git owns worktree existence, so read it from git and keep the registry to metadata only.
- *Treat an indeterminate `git worktree list` as "removed".* Rejected — a git flake would falsely fire the removed terminal + cascade; degrade to present, only a definite absence terminates (R34).
- *A non-atomic graph edit (mutate then validate-and-maybe-rollback-partially).* Rejected — a half-applied edit + a bumped revision is the U2 lie-on-the-trail bug; snapshot-validate-then-bump is the only safe shape.
- *Approval keyed to the outcome (once), not the revision.* Rejected — it would let a post-approval graph edit auto-dispatch un-reviewed edges; per-revision re-closes the gate exactly when the structure changes.

**Rationale.** Two invariants recur from earlier units and pay off again here: **the system that owns the resource is the guard** (U6: GitHub via `--match-head-commit`; U7: git via `worktree list`) and **a "current" precondition must be enforced atomically, degrade-safe** (U6: defer on outage; U7: present on a git flake, atomic snapshot-validate on every edit). Generalizable rule: **model an external resource's existence by reading the system that owns it, not a local mirror; and make every "is this still safe to mutate" check atomic + fail toward "don't touch it."**

**Revisit when.** U8 generates the projected sub-issues → wire the real `issue_close` into the prune CLI (the producer the consumer is waiting on). U9 adds the degrade decision (a capped/HALTed sub-outcome may degrade rather than wait). U10 reconciles the pruned node's **cost** (the third orphan facet, deferred here). If the per-outcome cap proves too coarse for a deep tree, lift it to a tree-shared registry under the git-common-dir.

**Refs.** `plugins/saga/scripts/outcome_decompose.py`, `plugins/saga/scripts/outcome_worktrees.py`, `tests/test_outcome_graph_edit.py`, `tests/test_outcome_worktrees.py`; wiring in `plugins/saga/scripts/outcome.py` (`worktree_processor` / `gate_factory` / `approve`-`prune`-`promote` verbs); work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U7 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U6 [auto-merge queue stance](#outcome-merge-queue-stance) (the git-is-the-guard + degrade-safe lessons) + the U1 [spec validator stance](#outcome-spec-validator-stance) (atomic structural mutation).

### Outcome auto-merge queue (U6): GitHub is the atomic merge guard (not a local SHA compare), churn cap not spin, conflict is retryable, gh-outage defers never fails (U6 PR pending — SHA-fill on merge)  {#outcome-merge-queue-stance}

**Decision.** `outcome_merge` is the serialized auto-merge queue + GitHub negative-state handler (R12/R32). Conventions later units (U7 worktree terminal, U9 degrade) build on:
- **GitHub itself is the atomic stale-tree guard — not a local SHA compare.** `gh pr merge --squash --match-head-commit <head>` is rejected by GitHub if the PR is not mergeable (base moved/`behind`, conflict/`dirty`, head moved, checks unmet), so a stale tree can never be squashed (R12/R30). The loop reads GitHub's `mergeStateStatus` to *classify* (behind→rebase, dirty→conflict, blocked→wait) and treats a rejected squash as a reloop. (A local "read the base SHA twice and compare" is a TOCTOU, not a CAS — the SHA was never bound to the merge; the verify panel proved a base change after the read still squashed. The CAS must be performed by the server that owns the ref.)
- **A gh outage DEFERS, never fails the leaf (R34).** `unknown` merge-state or an unreadable base → `not-ready` (defer); `squash_merge` returns `merged`/`error` (a non-zero exit is NOT assumed to be a conflict — conflicts come from `merge_state="dirty"`). The earlier "non-zero exit → conflict → permanent `failed` terminal" turned a transient outage into a wrong, sticky action.
- **A conflict is RETRYABLE; only `rejected`/`stalled` permanently skip.** The merge-queue skip-set is success ∪ truly-terminal-negative — a `failed` (conflict) leaf re-enters the queue once /work fixes it (a `successful_only=False` skip-set was a conflict-recovery deadlock). Negative terminals are sticky completion events at a fresh attempt (the U5 attempt-fix pattern) and `blocked_subtree` cascades only their downstream (R22).
- **Single-writer cross-process via the coordinator lease.** `process_merge_queue` is serialized within a process (sequential) AND the caller (`advance`) holds the coordinator lease (R13), so two coordinators can't both squash on stale bases — the in-process loop alone is not enough.
- **`branch_exists` rejects only on a DEFINITE 404.** A transient gh error degrades to *present* (a flake must never falsely reject a live subplot); the deleted-branch terminal fires only when GitHub says `404`/not-found.
- **GitHub ops are an injected `MergeOps` adapter**, so the queue's logic is fully unit-testable with no real `gh` — but tests MUST use values the real adapter can actually emit (a `squash="error"` fake masked the R34 violation; the regression now drives the REAL `github_merge_ops` with a failing runner).

**Rejected alternatives.**
- *Local read-the-base-SHA-twice "guard".* Rejected: it is a TOCTOU, not a CAS (the SHA is never bound to the merge); GitHub's `--match-head-commit` is the real atomic guard.
- *Non-zero `gh pr merge` exit → conflict → `failed` terminal.* Rejected: it fails a leaf on a transient outage (R34) and conflates transient with conflict; classify conflicts via `merge_state`, defer on uncertainty.
- *Skip `failed` leaves permanently (`successful_only=False`).* Rejected: conflict-recovery deadlock — a fixed leaf must re-enter the queue.
- *Treat an indeterminate `branch_exists` as "gone".* Rejected — a gh flake would falsely reject a live subplot; only a definite 404 rejects.

**Rationale.** The first cut tried to be the guard locally (read the base SHA, then squash) — the adversarial-verify panel proved that is a TOCTOU, not a CAS: the SHA is never bound to the merge, so a base change after the read still squashes. The correct shape is the same "encode the invariant as a guard the adversarial interleaving must pass" as the U2 atomic-redirect and U4 HALT-no-fallback, but the guard must be performed by **the party that owns the resource** — GitHub, via `--match-head-commit`. Generalizable rule: **a "still-current" precondition for a mutation must be enforced atomically by the system that owns the resource (a server-side CAS), not by a local read-then-act — and "degrade safe" means a transient failure DEFERS, never fabricates a terminal (a test that can't emit the real failure value gives false safety confidence).**

**Revisit when.** U7 adds the worktree-removed terminal (another R32 negative → same sticky-event + cascade path); U9 adds the degrade decision (a non-clean leaf may degrade rather than wait). If `gh pr merge --match-head-commit` proves insufficient under heavy base churn, add a server-side merge-queue (GitHub's native one) rather than re-introducing a local SHA compare.

**Refs.** `plugins/saga/scripts/outcome_merge.py`, `plugins/saga/scripts/outcome_github.py` (write side), `tests/test_outcome_merge_queue.py`; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U6 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U5 [completion barrier stance](#outcome-completion-barrier-stance) (its negative-terminal half) + the U2 [store durability stance](#outcome-store-durability-stance).

### Outcome completion barrier (U5): GitHub-canonical completion materialized into the cache, parent-owned predicate over evidence, unknown is the safe degraded value (U5 PR pending — SHA-fill on merge)  {#outcome-completion-barrier-stance}

**Decision.** Completion is decided by a **parent-owned barrier predicate** (`outcome_orchestrator.barrier_satisfied`, R9) over evidence the parent can re-verify on GitHub — never a child's self-report. Conventions later units (U6 auto-merge/negative-states, U8 report) must follow:
- **GitHub is canonical for completion; the cache is a materialization.** The barrier reads canonical truth from GitHub via `outcome_github` (a code leaf's **PR merged**, a non-code leaf's **tracking issue closed**); `harvest` writes that truth into the store as a success completion event so the existing `completed_subplots` frontier read unlocks the next Kahn layer (R10). A wiped cache is **re-harvested from GitHub** — this is the concrete realization of R27's "cache-loss loses no canonical state" that the U2 cache-loss test had to stand in for.
- **`unknown` is the safe degraded value (R34).** Every GitHub read degrades to `unknown` on a `gh` failure, and `merged` requires a real `mergedAt` (a closed-unmerged PR reads `closed`, R32, not `merged`). Only positive terminals unlock; a GitHub outage can DELAY an unlock, never fabricate one.
- **The barrier returns a verdict object** (contract + canonical state + evidence + reason), so a HALT is explainable and re-verifiable, and the cockpit (U8) can show *why* a leaf is not done.
- **Harvest is success-only in U5.** Negative-terminal harvest (closed-unmerged PR → `rejected` cascade) is U6; U5 unlocks on success. `blocked_subtree` (R22) pauses only a block's downstream subtree.
- **The reconcile loop's harvest half is an injected hook.** `advance(harvester=...)` runs the harvest before the frontier read each tick; the engine stays decoupled from `outcome_orchestrator` (which reads GitHub), mirroring the injected-dispatcher pattern.

**Rejected alternatives.**
- *Trust the leaf's own completion tick as "done".* Rejected per R9 — "done" is the parent's predicate over evidence; a child self-reporting done (without a merged PR / closed issue) must not unlock dependents.
- *Make the cache the source of completion truth.* Rejected: a cache wipe would then lose completion (the exact gap the U2/U3 verifiers flagged). GitHub-canonical + harvest-materialize keeps cache-loss lossless.
- *Coerce a GitHub read failure to "open" or "not done" silently.* Rejected in favor of an explicit `unknown` so the degraded state is visible and never mistaken for a real negative terminal.

**Rationale.** Encoding completion as a parent predicate over GitHub-canonical evidence makes the two honesty gaps from earlier units real: U2's "cache holds no canonical state" and U3's "resume reconstructs from GitHub" both now have a concrete read+harvest path. Generalizable rule: **when a cache claims to be non-authoritative, there must be an actual re-derive-from-canonical path that a test exercises — not just an assertion that the cache holds nothing.**

**Revisit when.** U6 adds the merge *action* + negative-state handling (the harvest gains negative terminals → `rejected`/`stalled` and the R22 cascade fires on them); U8 consumes `barrier_report` for the cockpit. If GitHub read latency dominates the tick, add a short-TTL state cache keyed on PR/issue number (invalidated by an event), but never a committed completion field.

**Refs.** `plugins/saga/scripts/outcome_orchestrator.py`, `plugins/saga/scripts/outcome_github.py`, `tests/test_outcome_completion.py`; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U5 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U2 [store durability stance](#outcome-store-durability-stance) (closes its cache-loss honesty gap) + the U4 [dispatcher seam stance](#outcome-dispatcher-seam-stance).

### Outcome dispatcher seam (U4): HALT is the absence of a fallback path, team-execution as first backend, recompile_for_tier's third leg, R8 destructive cleanup carries its own guard (U4 PR pending — SHA-fill on merge)  {#outcome-dispatcher-seam-stance}

**Decision.** U4 added the single backend dispatcher seam (`outcome_dispatcher.py`) + reshaped team-execution (R8). Conventions every later backend/degrade unit (U6 auto-merge, U9 full menu + degrade) must follow:
- **"Never silently substitute" is encoded as a missing capability, not a runtime check.** `dispatch` has NO code branch that falls back to a lesser backend — an unavailable backend *always* returns a HALT receipt (`HaltReceipt` / `BackendHaltError`). So R5/R23's "emit a visible HALT-not-degrade receipt rather than silently substituting" is structural and provable (parametrized over every NODE_BACKEND), the same "encode the invariant as the absence of a code path" rule from the U3 R3 invariant.
- **team-execution is the first real backend; the rest of the menu HALTs until U9.** `DEFAULT_AVAILABLE = (inline, team-execution)`. Choosing fork/subagent/cc-workflows-ultracode/goal/manual today HALTs visibly — the full menu (R6) and the operator-presence degrade-vs-halt *decision* (R23) land in U9. U4 owns only the seam + the HALT receipt.
- **The dispatcher seam wires `team_emitter` through `recompile_for_tier`'s third leg.** `execution_spec.recompile_for_tier(spec, "team-execution")` now emits the `## Team Structure` markdown (lazy import-by-path to avoid the `execution_spec ↔ team_emitter` cycle), rather than reinventing emission in the dispatcher.
- **A destructive deletion ships its own guard (KTD13) + its own release-triad bump (KTD14) in the same PR.** The tmux/`team-setup` deletion replaced the asset-pinning test with one that fails if any deleted asset returns OR any tmux ref reappears outside CHANGELOG; team-execution bumped to 2.2.0 (plugin.json + marketplace + CHANGELOG) so the interim merge stays releasable.

**Rejected alternatives.**
- *Let the seam degrade an unavailable backend to inline.* Rejected: that is the silent-substitution R5/R23 forbids — a leaf could run on an inferior tier (or duplicate a side effect) without the operator knowing. HALT + page instead.
- *Leave `recompile_for_tier`'s team-execution leg falling through to the inline baseline.* Rejected: it was a documented gap (`outcome_spec.py:88` flagged it as "waiting for R5"); wiring `team_emitter` is the intended correction, and it is safe because no test pinned `team-execution` → baseline.
- *Defer the team-execution release-triad bump / the deleted-asset guard to U11.* Rejected per KTD14/KTD13 — that would red the drift guard at this interim merge or ship a gutted plugin early.

**Rationale.** The merged-engine change (`recompile_for_tier`) was de-risked by first proving no released test pins `team-execution` → baseline (only inline / cc-workflows / unknown-tier are pinned), so the change is additive to released behavior. Generalizable rule: **before changing a by-mode dispatcher in merged engine code, grep for which modes its tests actually pin — an unpinned mode is safe to wire; a pinned one needs the test updated in the same change.**

**Revisit when.** U9 adds the full backend menu (fork/subagent/goal/manual become available, shrinking the HALT set) + the R7 recommender + the R23 operator-presence degrade decision (the dispatcher gains a degrade-one-rung path *guarded* by operator-away + no-side-effect-yet, distinct from HALT). U6's auto-merge consumes the dispatch return channel.

**Refs.** `plugins/saga/scripts/outcome_dispatcher.py`, `plugins/saga/scripts/execution_spec.py` (recompile_for_tier), `plugins/team-execution/**` (R8 reshape), `tests/test_outcome_dispatcher.py`, `tests/test_team_execution_plugin.py`; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U4 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U3 [reconcile engine stance](#outcome-reconcile-engine-stance).

### Outcome reconcile engine (U3): node state is derived-on-read not committed, dispatch-not-execute via injected dispatcher, command surface lands now but releases at U11 (U3 PR pending — SHA-fill on merge)  {#outcome-reconcile-engine-stance}

**Decision.** `outcome.py` is the OutcomeOrchestrator coordinator runtime over the spec (U1) + store (U2). Three conventions every later coordinator unit (U4 backends, U5 barrier, U6 auto-merge, U7 decompose, U8 report, U9 degrade) must follow:
- **Node operational state is DERIVED on read, never committed per tick.** The committed branch spec carries *structure* (nodes/edges/decision-trail/cost); a node's live state (`ready`/`dispatched`/`done`/`blocked`/`pending`) is recomputed every call from completion events (store) + dispatch records (ledger) via `derive_states`. There is no stored status field (R17). This keeps branch history free of per-tick state churn and makes the loop level-triggered + crash-tolerant (R29) — a crash mid-tick just re-derives.
- **The coordinator dispatches, it never executes (R2/R3).** `advance` only calls an **injected `dispatcher`** (record-only by default; real backends are dispatcher implementations in U4/U9) and harvests completion events. It never runs a leaf's work in-process, so a coordinator failure can never collapse the DAG into one inline context.
- **Dispatch idempotency = per-subplot lock (concurrent-tick guard) + durable ledger dispatch-record (skip marker).** A second concurrent `advance` no-ops on the held coordinator lease, released in a `finally` so a raising dispatcher can't brick the loop.

**Rejected alternatives.**
- *Persist node.state into the committed spec each tick.* Rejected: pollutes branch history with bot state-churn commits (the R21-vs-R26 cadence tension) and creates a stored status field that can drift (violates R17). Derive-on-read is canonical.
- *Let the coordinator run the leaf inline when a backend is cheap.* Rejected: that is exactly the R3 context-collapse failure — the coordinator must always route, never execute, regardless of backend.
- *Defer the command/skill markdown + model/manual integration to U11.* Rejected: the plan lists them as U3 files, and landing `commands/outcome.md` without the model entry breaks the `wrappers == commands | aliases` guard — it is all-or-nothing. So the full surface lands in U3 (dogfoodable now); only the marketplace **version flip + advertisement** defer to U11. The generated command-matrix visual stays at the released 18 because the renderer uses a hardcoded command list (adding `/outcome` to the model changes no SVG) — a deliberate "in source, not yet released" state.

**Rationale.** The derive-on-read model falls directly out of R17 (no operator-writable status) + R29 (level-triggered, holds no authoritative in-memory DAG). The injected-dispatcher seam makes the R3 invariant *structural and testable* — the engine has no code path that runs a leaf body, so a record-only dispatcher proves "dispatched, not executed" by construction. Generalizable rule: **when an invariant says "X never happens," encode it as a missing capability (no code path), not a runtime check — then a test that would trip the path proves it.**

**Revisit when.** U9 wires the recommender + real backends (the dispatcher gains tier selection + degrade-only-leaves, completing R3/R6/R7); U8 adds the full report + attention consolidator (completing R17/R18); U11 flips the version + advertises `/outcome` (and adds it to the command-matrix renderer + regenerates the visual). If derive-on-read ever proves too slow at scale (large DAGs re-deriving each tick), add a derived-state cache invalidated by spec_revision + completion-event count — but never a committed status field.

**Refs.** `plugins/saga/scripts/outcome.py`, `plugins/saga/commands/outcome.md`, `plugins/saga/skills/outcome/SKILL.md`, `tests/test_outcome_command.py`; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U3 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U1 [validator stance](#outcome-spec-validator-stance) + U2 [store durability stance](#outcome-store-durability-stance).

### Outcome store (U2): write-once-vs-atomic split, self-healing ledger, sticky success, best-effort lease with defense-in-depth (U2 PR pending — SHA-fill on merge)  {#outcome-store-durability-stance}

**Decision.** `outcome_store.py` is the git-common-dir **cache** (R27) beside the canonical spec + GitHub — never committed, deleting it loses nothing. KTD15's durability primitives lock these conventions every later unit (U5 barrier, U6 auto-merge/negative-states, U7 graph editing) must honor:
- **Two distinct write primitives.** Mutable files use temp + `os.replace` (`_atomic_write`); write-once files (completion events, lease creation) use temp + `os.link` (`_write_once`, refuses to clobber). Both build the temp via `_unique_tmp` = pid + thread id + monotonic nonce (pid alone collides across same-process threads).
- **The ledger self-heals on append, not just tolerates on read.** `append_ledger` truncates an unterminated trailing fragment *before* writing (and loops on short writes); `read_ledger` tolerates a torn/non-object **trailing** line but raises on any non-trailing corruption. Tolerance is a precise allowance, never a blanket "skip bad lines".
- **Completion success is sticky.** `completed_subplots` counts a leaf as done if **any** attempt reached a SUCCESS state — a later `failed` attempt never un-completes a merged leaf. Post-merge negatives (a merged PR later closed → `rejected`) are a distinct GitHub transition (U6), not completion-attempt recency.
- **Idempotency converges under races.** The write-once link-loser compares keys and returns `"skipped"` for a duplicate, raising only on a genuine divergent-completion conflict.
- **Leases are best-effort by design, safe by defense-in-depth.** Free-slot create + held-fresh reject are race-safe; the stale **reclaim** is a documented TOCTOU. A brief double-coordinator window cannot cause a duplicate *effect* because the per-subplot dispatch lock + completion idempotency are the real anti-duplication guarantees and the cache is non-authoritative.
- **Offline degraded mode = supersede-drop + exponential backoff + page-on-exhaustion.** GitHub wins for completion (a server-superseded queued write is dropped, not replayed); failures schedule `next_retry_at = now + base·2^(n-1)`, consumed by `drain_offline`.

**Rejected alternatives.**
- *A shared append log for completions.* Rejected: per-leaf write-once files mean two leaves finishing at once never contend (R10) and each completion is immutable + auditable.
- *Latest-attempt-wins for completion state.* Rejected under adversarial review: it let a later `failed` attempt erase a recorded success and re-lock the frontier.
- *A fencing token on the lease now.* Deferred to U6: the consumer (the coordinator runtime that would present the token) doesn't exist yet, so adding the field now is dead-wiring (a recurring campaign anti-pattern).
- *Read-only torn-tail tolerance (no self-heal).* Rejected: the very crash the ledger exists to survive — a torn append followed by recovery appends — silently lost the first record and bricked `read_ledger` on the second.

**Rationale.** Surfaced by a 3-lens adversarial-verify workflow (concurrency/atomicity, durability/replay, requirements-honesty), each lens running the store standalone with real threads, clock injection, and crash sequences. It found two genuine P1s (the idempotency-race raise and the non-self-healing ledger) that the 34-test green suite missed because no test appended *after* a torn line or raced an identical key. Generalizable rule: **a "tolerate on read" durability guarantee is incomplete without a matching "repair on write" — and concurrency invariants need a test that actually races, not just a serial happy path.**

**Revisit when.** U6 builds the coordinator runtime → add the lease fencing token (consumer now exists) for strict single-writer exclusivity; if cross-host realtime coordination ever enters core scope, the best-effort reclaim and the cache-only model both need revisiting (networked completion stream). If a single outcome's ledger ever grows large enough that `_heal_torn_tail`'s full-read-on-torn-tail matters, switch to a bounded tail read.

**Refs.** `plugins/saga/scripts/outcome_store.py`, `tests/test_outcome_store.py`, `tests/test_outcome_replay.py`; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U2 of the [outcome-orchestration build plan](#outcome-orchestration-plan); builds on the U1 [validator stance](#outcome-spec-validator-stance).

---

## 2026-06-25

### Outcome-spec validator (U1): hard invariants vs advisory smells, atomic structural mutation, Kahn is a deliberate reimplementation (U1 PR pending — SHA-fill on merge)  {#outcome-spec-validator-stance}

**Decision.** `outcome_spec.OutcomeSpec.validate` enforces only **hard, dispatch-blocking** invariants (closed vocab, unique ids, self-dep, missing dep, cycle, local `child_spec_ref` constraints incl. sibling-collision). Three conventions every later unit (esp. U7 graph editing) must follow:
- **Disconnection is advisory, not a hard failure.** Independent workstreams under one objective are first-class, so a multi-component graph is *legal*; `structural_warnings(spec)` returns a non-fatal advisory for >1 weakly-connected component (consistent for a lone isolate **and** a multi-node island). The state-aware half of R33 (legal-edits-after-dispatch + dynamic orphan reconciliation) is deferred to U7 — `validate` is intentionally dispatch-state-blind in U1.
- **Structural mutations are atomic.** `redirect_dependency` applies to a snapshot and `validate`s **before** bumping `spec_revision`/appending `decision_trail`; a rejected mutation rolls back and advances neither. The canonical artifact must never carry a bumped revision with a trail entry that lies about a rejected change.
- **`from_dict` fails loud, never coerces.** A string `depends_on`/`guarantee_tags` is rejected (not character-iterated into corrupted edges); `bool`/float liveness budgets and non-positive `spec_revision` are rejected.

**Rejected alternatives.**
- *Hard-fail a degree-0 "orphan" node when the graph has any edge* (the first U1 cut). Rejected under adversarial review: it was both **too strict** (rejected a legitimate pipeline + one independent task) and **too loose** (silently passed a disconnected multi-node island — the exact forgot-to-wire error it claimed to catch). The advisory replaces it.
- *Reuse `execution_spec.dependency_layers`* (R1 "reuse saga machinery" literal reading). Rejected: `execution_spec` adds an implicit `pilot` barrier edge the outcome layer has no concept of, so the two **deliberately diverge**. `outcome_spec.dependency_layers` is a parallel Kahn reimplementation keyed on `Node`; the docstring says so and the two must not be assumed to agree (no forced parity test that would only hold on pilot-free fixtures).

**Rationale.** Surfaced by a 3-lens adversarial-verify workflow (validator-bypass / round-trip / requirements-honesty), each lens required to PROVE claims by running the module standalone. 13 findings, all real except one correctly-refuted (`sort_keys=False` determinism held across 5 `PYTHONHASHSEED=random` subprocesses). The non-atomic-mutation defect (P1) is the load-bearing generalizable rule: **a mutate-then-validate sequence that also bumps a version/audit counter must be transactional, or a rejected mutation corrupts the canonical artifact.**

**Revisit when.** U7 adds add/prune/promote — they bump through `bump_revision` and must adopt the same snapshot-validate-then-commit shape; if a future unit needs to *block* on disconnection (e.g. a "strict" outcome mode), promote `structural_warnings` to an opt-in hard gate rather than reinstating the degree-0 heuristic.

**Refs.** `plugins/saga/scripts/outcome_spec.py`, `tests/test_outcome_spec.py`, `plugins/saga/references/outcome-spec.md`; work log `docs/work-sessions/2026-06-25-outcome-orchestration.md`. Implements U1 of the [outcome-orchestration build plan](#outcome-orchestration-plan).

---

### Outcome-orchestration build plan — multi-engine trust-but-verify synthesis, store/ledger facet split, degrade-layer wiring (plan PR pending — SHA-fill on merge)  {#outcome-orchestration-plan}

**Decision.** The `OutcomeOrchestrator` implementation plan (`docs/plans/2026-06-25-operator-outcome-orchestration-plan.md`, 11 units U1–U11, R1–R34 coverage matrix) locks these load-bearing HOW choices:
- **Store split by facet.** Outcome structure = canonical JSON `outcome-spec.json` on the outcome's own branch; completion = GitHub; the `git rev-parse --git-common-dir` store is a pure cache (verified to resolve identically across worktrees and survive `git worktree remove`). Completion events = per-leaf immutable `O_EXCL` JSON files (multi-writer-safe), never a shared append log.
- **Transition ledger is cache-resident, NOT committed.** Same-machine crash recovery replays the fine-grained ledger; a fresh-machine reconstruct recovers to GitHub+spec granularity via idempotent reconcile — coarser but correct, the boundary stated honestly (R34/F5).
- **Guarantee/degrade logic lives in the degrade path, NOT `recompile_for_tier`.** `child_spec_ref` is a typed new node field, never an overload of saga's `orchestration_ref` (a single-saga backend pointer).
- **Release-triad sync is a first-class unit (U11).** Auto-merge = serialized coordinator queue, rebase-then-reverify, capped at 3.

**Rejected alternatives.**
- *Commit the transition ledger per-transition* (one input plan's choice). Rejected: stronger cross-machine replay but pollutes branch history with bot commits mid-run (the R21-grows-lazily vs R26-committed cadence tension).
- *Inject halt-not-degrade into `recompile_for_tier`* (one input plan's choice). Rejected: **verified** that `recompile_for_tier` (`execution_spec.py:708`) is a by-mode dispatcher, not the downgrade-enforcer — the policy lives in `recheck_orchestration_capability` (`lifecycle_state.py:223`). Wiring guarantee logic there attaches it to the wrong layer.
- *Overload `orchestration_ref` with `child_spec:<path>`* (one input plan's choice). Rejected: type-unsafe, conflates the backend pointer with a parent→child link.
- *Stage out nested recursion / economics / team-execution cleanup* (one input plan's choice). Rejected: violates the operator's all-co-equal/no-phasing release decision (R4); the spine is internal work order only.

**Rationale.** The plan was synthesized from three independently-generated plans (Claude, Codex gpt-5.5 xhigh, Antigravity Gemini 3.1 Pro High) under a trust-but-verify discipline — no code claim adopted without checking the file. The two engines that actually verified (Claude, Codex) independently caught the same two requirements-doc errors (`recompile_for_tier` is a dispatcher not a downgrade-enforcer; tmux count is 60 not 59); Antigravity parroted both, which is why its plan's degrade wiring was wrong. Codex supplied the strongest backbone (node schema, store layout, release-gate unit); the honest cache-ledger boundary and the corrections came from Claude; the rebase-attempt cap and Mermaid cockpit from Antigravity.

**Revisit when.** Cross-host realtime completion is actually needed (then add the networked completion stream that is currently out-of-core-scope), or a fresh-machine mid-transition crash recovery proves too coarse in practice (then reconsider committing a compacted ledger snapshot per spec-revision rather than per-transition).

**Refs.**
- Plan: `docs/plans/2026-06-25-operator-outcome-orchestration-plan.md`; requirements: `docs/brainstorms/2026-06-25-operator-outcome-orchestration-requirements.md`.
- Builds on DECISIONS [parallel-layer emitter + /work halt-not-degrade + provenance guard](#parallel-refuteN-emitter-plan-work-wiring) (KTD6/KTD7) and [saga tiering + execution-mechanism campaign](#saga-tiering-execution-campaign-shipped) (one spec → two emitters, `orchestration_ref` pointer model).

---

## 2026-06-21

### Parallel-layer emitter, refute-N judge-panels, /plan author-validate-approve-persist-emit, /work halt-not-degrade, and provenance guard at save() (#250, 88b61be)  {#parallel-refuteN-emitter-plan-work-wiring}

**Decision.** Seven key design calls that together close the R9 keystone:

- **KTD1 — direct spec authoring.** `/plan` authors the spec directly (no code generation, no LLM-to-spec translation). The hand-authored campaign harness dogfooded the spec shape before the emitter automated it; authoring by hand validated that thin prompts + structured fields are the right abstraction.
- **KTD2 — thin prompts.** Each unit prompt is a one-line thin pointer to the plan doc, not a prose transcription. The emitter appends fan-out reconciliation, budget riders, and return contracts automatically; depth comes from the agent reading the plan.
- **KTD3 — refute-N defaults n=3/majority/cap 7.** Default `verify` panel: `n=3`, `pass_rule="majority"` — a finding survives unless ≥2 of 3 verifiers refute it. Hard cap at `VERIFY_N_CAP=7` (guards the rate-limit overcorrection that occurred at 22-23 verifiers); soft warn band above 5.
- **KTD4 — topological-layer parallelism.** `dependency_layers(spec)` (Kahn) computes independent layers; a layer of >1 unit emits one `parallel([...])` wave. Pilot implicit barriers are included in the layer computation so the gate survives complex topologies. Cycles fail emit.
- **KTD5 — `verify` as an optional Unit field.** Present → emits a refute-N judge-panel in the generated script; absent → round-trips unchanged (existing specs and `team_emitter.py` never gain a spurious key). Verifiers run at the same `{model, effort}` tier as the parent unit (R4).
- **KTD6 (was KD3) — `/work` halts off-host, not recompile-down.** A `cc-workflows-ultracode` choice is guarantee-bearing (parallel fan-out + refute-N). When the Workflow tool is absent or the spec/ref is missing, `/work` halts with a recovery line — it never silently substitutes hand-rolled serial subagents (the campps issue-38 failure). This is explicitly NOT the off-host recompile-down path (`recheck_orchestration_capability`), which is reserved for `/loop`/`/resume` in operator-absent polling contexts.
- **KTD7 — guard at the `save()` chokepoint.** `saga.py save` rejects a tick that newly asserts `orchestration_mode != orchestration_operator_choice` without an `orchestration_downgrade` note justifying THAT divergence — `/work` cannot cover a secret backend substitution by rewriting `operator_choice`. The guard is precise: a no-op when no `operator_choice` is asserted, and it lets an *unchanged* byte-identical carry-forward of a prior already-vetted divergence through (a stale note from a *different* divergence cannot launder a fresh one). The only legitimate paths: operator picks a backend, `/work` records it via `--orchestration-mode` (choice derives equal, no divergence); or a genuine degrade carries its `orchestration_downgrade` note WITH the divergence.

**Dogfooding fix (operator_choice auto-derive).** The `_build_save_saga` auto-derive of `operator_choice` from `--orchestration-mode` must not fire on a tick that carries NO orchestration args at all (a plain progress tick). An auto-derived `operator_choice` on a no-orchestration-args tick was triggering a false-divergence rejection of normal progress ticks by the provenance guard. Fix: the auto-derive only applies when `--orchestration-mode` is explicitly set; an absent flag leaves both `operator_choice` and `recommended` as empty strings and the guard does not fire.

**`orchestration_ref` lifecycle for `cc-workflows-ultracode`.** At `/plan` time the ref is set to the **spec JSON path** (the canonical artifact — the `.workflow.js` is regenerable and is NOT the durable ref). After `/work` launches the Workflow and receives a workflow id, it overwrites the ref with that id via a second tick. The spec JSON is always the authoring artifact; the workflow id is the transient execution handle.

**Rejected alternatives.** (a) Use the `.workflow.js` as the `orchestration_ref` — rejected: the script is derived; a re-plan that edits the spec would leave the ref pointing at a stale script; the spec JSON is the single source of truth. (b) Allow `/work` to fall back to inline when the Workflow tool is absent — rejected: this loses exactly the parallel fan-out and refute-N guarantees the operator chose ultracode for; the campps issue-38 post-mortem is the evidence. (c) Verify panel verifiers at a cheaper tier than the unit — rejected (R4): a mis-tiered verifier validates a different cost surface; same-tier keeps the oracle honest. (d) Check for divergence on every tick (not just orchestration ticks) — rejected: over-fires on normal progress ticks; the guard must be scoped to ticks that carry an explicit `orchestration_mode`. (e) Place the guard in the `Saga` dataclass constructor or in `render_envelope`/`parse_envelope` (KTD7) — rejected: that would reject an unsaved render→parse round-trip with `operator_choice != mode` (e.g. `tests/test_saga_saga.py:1259`); the guard must be `save()`-scoped so pure (de)serialization stays valid.

**Rationale.** Thin prompts + spec-as-contract give the emitter clean separation from the plan body; the emitter handles all the boilerplate (budget riders, reconciliation, return contracts). The verify cap at 7 and the halt-not-degrade rule are both grounded in observed failure modes (rate-limit overcorrection; campps #38 silent substitution). The dogfooding fix is a one-condition guard that narrows the auto-derive to exactly the ticks where it is meaningful.

**Revisit when.** Real override-rate data (R12) shows the halt-not-degrade rule is too conservative (operators frequently switch backends mid-session because the Workflow tool is unavailable — then reconsider a softer fallback path); the verify panel's same-tier rule proves too expensive on large opus/high specs (then consider a tiered verifier vocab); the `VERIFY_N_CAP` value needs recalibrating based on observed rate-limit behavior.

**Refs.** `plugins/saga/scripts/execution_spec.py` (`dependency_layers`, `Verify`, `_emit_verify_panel`, `emit_workflow_script`); `plugins/saga/scripts/saga.py` (save provenance guard); `plugins/saga/skills/plan/SKILL.md` §5.2a; `plugins/saga/skills/work/SKILL.md` §1.5; `plugins/saga/references/execution-spec.md`; `plugins/saga/references/operator-choice.md` §6; saga 0.37.0.

### Stale-main SessionStart hook generalized to run in ANY git repo, self-contained in the plugin (PR pending — SHA-fill on merge)  {#stale-main-hook-generalized}

**Decision.** The saga `SessionStart` hook (`plugins/saga/hooks/stale_main_session_hook.py`) now runs in **ANY git repo with an `origin` remote** — there is no repo-presence gate. It is **self-contained in the plugin**: it no longer invokes `tools/stale_main_guard.py` (which remains the repo-local manual tool / R18 artifact). It detects the default branch generically (`git symbolic-ref --short refs/remotes/origin/HEAD` → strip `origin/`, fall back to probing `origin/main` then `origin/master`), never hardcoding `main`. The operator chose **auto-fast-forward when safe**: if the local default branch is behind `origin/<default>` AND the current branch IS the default branch AND the tree is clean → `git merge --ff-only origin/<default>`; otherwise (feature branch, dirty, or a linked worktree) → WARN only. Preconditions (not-a-repo, no `origin`, undeterminable default) → exit 0 silent. Always non-blocking; emits the standard SessionStart `additionalContext` shape only when there is a message. Supersedes [#stale-main-sessionstart-hook](#stale-main-sessionstart-hook).

**Rejected alternatives.** (a) Warn-only everywhere (no auto-FF) — rejected: the operator wants the stale local default branch fixed automatically in the common safe case, not just flagged. (b) Opt-in-per-repo (keep some presence/marker gate so the behaviour only activates where explicitly enabled) — rejected: defeats the point of a user-scope distributed hook; the safety is intrinsic (auto-FF only when cleanly ON the default branch, which git guarantees is the holding checkout — never a linked worktree).

**Rationale.** Saga installs at user scope, so the old repo-presence gate made the hook inert in every repo except this one. Auto-FF is worktree-safe by construction: being ON the default branch means you hold its checkout (git forbids the same branch in two worktrees), so the auto-FF never mutates another worktree's branch. Generic default-branch detection avoids hardcoding `main` and handles `master`-default repos. The small git-logic overlap with `tools/stale_main_guard.py` is accepted for now (the plugin hook must be self-contained; the repo tool stays as the manual R18 path).

**Revisit when.** Auto-fast-forwarding in arbitrary repos proves surprising to users (then reconsider warn-only-default or an opt-out), or the duplicated git logic across the plugin hook and `tools/stale_main_guard.py` drifts (then consider consolidating to one source).

**Refs.** `plugins/saga/hooks/stale_main_session_hook.py`, `plugins/saga/hooks/hooks.json`, `tests/test_stale_main_session_hook.py`; `tools/stale_main_guard.py` (left intact, R18); saga 0.36.0. Supersedes [#stale-main-sessionstart-hook](#stale-main-sessionstart-hook).

### Stale-main guard ships as a repo-guarded SessionStart hook in the distributed saga plugin (PR pending — SHA-fill on merge)  {#stale-main-sessionstart-hook}

> **Superseded 2026-06-21 by [#stale-main-hook-generalized](#stale-main-hook-generalized)** — the hook is now self-contained and runs in any git repo (no repo-presence gate, no dependency on `tools/stale_main_guard.py`).

**Decision.** Install the existing `tools/stale_main_guard.py` (R18) as a `SessionStart` hook (matcher `startup|resume`) wired through the **saga plugin's** `hooks/hooks.json` via a thin wrapper `plugins/saga/hooks/stale_main_session_hook.py`. Because saga is distributed to other repos, the wrapper carries a **repo-presence guard**: it resolves the CWD repo root (`git rev-parse --show-toplevel`) and only runs the guard if `<root>/tools/stale_main_guard.py` exists — otherwise it exits 0 silently (no `git fetch`, no subprocess). It invokes the repo's OWN guard copy (not `${CLAUDE_PLUGIN_ROOT}`'s) and surfaces output as SessionStart `additionalContext` (`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`), always exit 0.

**Rejected alternatives.** (a) A project-level `.claude/settings.json` SessionStart hook — rejected: `.claude/` is gitignored here, so the hook config can't be committed/shared. The committable home is the saga plugin's `hooks.json`. (b) Hardcoding a repo-name check inside the wrapper — rejected: brittle and fork-hostile; presence of the guard tool at the repo root IS the signal, so any fork that ships the tool gets the behaviour for free and every other repo stays inert.

**Rationale.** The guard already exists and is non-blocking; the only missing piece was an install point that (1) is committable and (2) cannot fire in the many other repos where saga is installed. The presence-of-tool guard satisfies both without coupling the distributed plugin to this repo's identity.

**Revisit when.** Saga grows a repo-agnostic SessionStart behaviour that should run everywhere (then the presence guard becomes the wrong default and the wrapper needs an explicit opt-in/opt-out), or Claude Code changes the SessionStart stdin/`additionalContext` contract.

**Refs.** `plugins/saga/hooks/stale_main_session_hook.py`, `plugins/saga/hooks/hooks.json`, `tools/stale_main_guard.py`, `tests/test_stale_main_session_hook.py`; saga 0.35.0.

### Saga tiering + execution-mechanism campaign — shipped, all 5 epics merged (#241–#245)  {#saga-tiering-execution-campaign-shipped}

**Decision.** The campaign planned in [#saga-tiering-execution-campaign-plan](#saga-tiering-execution-campaign-plan) **shipped in full** — all 5 epics merged to `main` as their own squashed PRs, in the planned barrier order, with the per-unit `{model, effort}` tier intact: **epic0** (U2, U3) `#241` `27ec81c`; **epic1** (U4, U5, U6) `#242` `1575907`; **epic3** (U7, U8, U9) `#243` `c9757e3`; **epic4** (U14, U15, U16) `#244` `9bdf363`; **epic2** (U10–U13) `#245` `9e9f29c`. The locked KTDs held: **KTD2** per-unit tiering (4 callable agents pinned — `homelab-sre`→opus, `sdlc-operator`/`unifi-network-ops`/`release-orchestrator`→sonnet, `mechanical-executor`→haiku); **KTD5/R8** display-label map renders "dynamic workflows" while the enum `cc-workflows-ultracode` stays byte-for-byte frozen (`saga.py:79`); **KTD7** `redis-channel-coach` documented `tiering_exempt` (MCP-`instructions=` pointer, not Agent-dispatched); **R7** gated-vs-advisory recommender split (`lifecycle_state.py`, `consensus_is_gated` default `True`); **R9** one execution-spec → two emitters (`team_emitter.py` + the workflow-script emitter), saga stores only the `orchestration_ref` pointer. The full gate is green on the post-merge tree (926 tests, both validators, ruff format+check, mypy 67 files, issue-contract parity). **R4** (global `~/.claude/CLAUDE.md` tier rule) is applied-inline per KTD8 — **operator confirms out of band**, tracked in the U17 reconciliation report, not built by any unit.

**Rejected alternatives.** Force-merging a non-green epic to "finish the run" (rejected — the autonomous oracle is the gate; KTD3 forbids weakening it); auto-resolving a cross-epic `saga.py` rebase conflict (none occurred, but KTD9 forbids it regardless — load-bearing-code conflicts HALT for review); folding R4 into the workflow (KTD8 — a global out-of-repo file must never be edited in an unattended fan-out).

**Rationale.** Hand-authoring the one ultracode harness dogfooded R9 and validated the execution-spec by walking it before Epic 2 automated it; epic-grouped PRs (~5 CI runs) kept isolation without per-unit churn; the merge gate stayed honest because the gate-fix loop was capped and barred from weakening tests/assertions. The campaign also retro-hardened the merge gate: `main` was branch-protected (the 5 checks + strict) *before* the run, so GitHub enforced the gate rather than leaning on poll discipline alone.

**Revisit when.** Real override-rate data (R12, surfaced by `override_rate_reader.py`) justifies re-weighting a recommender default; a future rebuild needs the `cc-workflows-ultracode` enum actually renamed (then do the migration the display-label map deferred); the Workflow tool's `model`/`effort`/`budget` API changes under the harness.

**Refs.** Reconciliation report `docs/analysis/2026-06-21-saga-tiering-execution-campaign-report.md` (every R-ID → landed unit); plan + sibling `.workflow.js`; [#saga-tiering-execution-campaign-plan](#saga-tiering-execution-campaign-plan); LEARNINGS [#display-label-map-decouples-enum-from-prose](#display-label-map-decouples-enum-from-prose), [#gated-vs-advisory-consensus-is-a-governance-split](#gated-vs-advisory-consensus-is-a-governance-split), [#validate-plugins-only-scans-top-level-md](#validate-plugins-only-scans-top-level-md).

### Plan the saga tiering + execution-mechanism campaign as one workflow-built, per-unit-tiered build (plan PR pending — SHA-fill on merge)  {#saga-tiering-execution-campaign-plan}

**Decision.** Plan the **whole** campaign (5 epics, 17 units U1-U17, requirements R1-R18) in one Deep plan and execute it through **one hand-authored ultracode workflow** (`docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`) with a per-unit `{model, effort}` tier on every step (**5 Opus / 11 Sonnet / 1 Haiku**, operator-approved). Topology: `Preflight → parallel(Epic0, Epic1, Epic3) → barrier(E0+E1 merged) → parallel(Epic2, Epic4) → Final`, each epic an isolated worktree+branch landing as one PR, **full hands-off auto-merge** when the 5 required CI checks are green. Four operator/derived locks: **R7** gated-vs-advisory consensus via an explicit `/plan` interrogation question with a work-shape default (advisory → the existing `adversarial_confidence` ultracode branch); **R8** decouple-not-rename (display-label map → "dynamic workflows", enum `cc-workflows-ultracode` frozen); **R9** one spec, two emitters, saga points; **Epic 0** pins **4** callable agents (`redis-channel-coach` exempt — an MCP-instructions pointer, not Agent-dispatched).

**Rejected alternatives.** (a) Plan epic-by-epic as separate docs (the brainstorm's KD6) — the operator chose to plan the whole thing; each epic still lands as its own PR, so independent execution is preserved. (b) Per-unit PRs — rejected for CI volume (~16 CI runs); epic-grouped PRs (~5 runs) with serial intra-epic units keep isolation without the churn. (c) Rename the enum to `dynamic-workflows` — rejected: the enum is a stored contract carried in persisted sagas; a display-label map is cheaper and reversible. (d) Infer R7 purely from work-shape, or always-ask with no default — rejected for explicit-question-**with**-default: the governance call ("does the verdict need to stick?") is the operator's, but the default removes friction. (e) Edit `~/.claude/CLAUDE.md` (R4) from inside the autonomous workflow — rejected: a global file outside the repo must not be in an unattended fan-out; applied inline with confirmation (KTD8).

**Rationale.** Tiering is the genuine cross-doc seam, so it is the spine and lands first. Building the campaign **via** the workflow dogfoods R9 and validates the execution-spec by walking it manually before Epic 2 automates it. The autonomous oracle is sound — the test suite + the two plugin validators + the drift-guards gate every PR, and a red gate blocks the auto-merge — so full hands-off is safe behind green CI. R7 is a *surgical* split, not new plumbing: `adversarial_confidence` already exists as an ultracode trigger one branch from the `or needs_consensus` hard-force (`lifecycle_state.py:163` vs `:158`).

**Revisit when.** Real override-rate data (R12) justifies re-weighting a recommender default; a second workflow-built campaign shows epic-PR auto-merge is too coarse (drop to per-unit checkpoints); the Workflow tool's `model`/`effort`/`budget` API changes; or a future rebuild needs the enum renamed after all (then do the migration the display-label map deferred).

**Refs.** Plan `docs/plans/2026-06-21-saga-tiering-and-execution-campaign-plan.md` + sibling `.workflow.js`; requirements `docs/brainstorms/2026-06-20-saga-tiering-and-execution-campaign-requirements.md`; reference harness `infiquetra-context-library/scripts/context-fleet-audit.workflow.js`; [#operator-choice-docs-and-confidence](#operator-choice-docs-and-confidence); Track-1 builds queued under [#plugin-portfolio-groom-17-to-7](#plugin-portfolio-groom-17-to-7). Campaign-level LEARNINGS land at build time (U17).

## 2026-06-20

### Plugin portfolio groomed 17 → 7; marketplace version majors on plugin removal (04fa93e)  {#plugin-portfolio-groom-17-to-7}

**Decision.** Cut the marketplace from 17 plugins to **7 keepers** (`saga`, `team-execution`, `mission-control`, `redis-channel`, `home-lab-ops`, `unifi`, `deploy`). Removed 9 zero-fire plugins (`slack`, `pagerduty`, `splunk`, `identity-toolkit`, `sdk-lifecycle`, `python-toolkit`, `test-suite`, `docs-generator`, `todoist-manager`) and relocated `marketplace-lister` → `infiquetra-hermes-plugins` (removed here; **registration there is a separate follow-up**). Bumped the registry version **2.4.0 → 3.0.0 (major)** and aligned the stale nested `metadata.version` (2.1.0 → 3.0.0). Removed each plugin's `marketplace.json` entry + 7 client test files; repointed every doc that named a cut plugin (README table/examples, CLAUDE.md/AGENTS.md examples, MARKETPLACE_GUIDE, the `/ideate` worked example) to survivors; pruned the orphaned pagerduty/splunk/slack conftest fixtures.

**Rejected alternatives.** (a) Keep the thicker dev plugins (`python-toolkit`/`test-suite`/`docs-generator`) — rejected: zero fires; current LLMs subsume the knowledge-only ones; rebuild later if a real need appears (git history is the archive). (b) Minor bump (2.5.0) to match the rename campaign's precedent — rejected: removing 10 of 17 plugins breaks installs of those plugins, which is exactly what a major signals; a minor would bury the largest-ever portfolio change. (c) Hand-edit `marketplace.json` entry-by-entry — rejected for the double-`]` footgun; regenerated programmatically (load → filter to keep-set → dump → trailing newline) instead.

**Rationale.** The 17-plugin registry was mostly zero-fire service wrappers and knowledge-only plugins. Both validators are **structural, not enumerative** (`validate.py` requires each entry's `source` path to exist and validates whatever dirs are present; `validate_plugins.py` globs `plugins/*.md` = no-op), so a consistent dir+entry removal stays green with **no drift-guard rewrite** — the per-plugin metadata tests are match-tests for kept plugins only. Convention set: **marketplace registry version majors on plugin removal, minors on additions/metadata.**

**Revisit when.** A cut plugin is needed again (revive from git history + re-register), `marketplace-lister` lands in `infiquetra-hermes-plugins` (closes the relocate follow-up), or a "generate `marketplace.json` + README from `plugin.json`" survivor ships (fold the programmatic-regen into it).

**Refs.** Ideation: `docs/ideation/2026-06-19-plugin-ecosystem-grooming-ideation.md` + `2026-06-19-plugin-grooming-next-steps.md`. Track 1 survivor builds (tiering pins, hook harness, mechanical-handoff substrate) remain queued. Shipped via PR #232 (squash 04fa93e).

## 2026-06-17

### Mission-control issue-contract consumer sync (planned; issue #222)  {#mission-control-issue-contract-consumer-sync}

**Decision.** Plan issue #222 as a consumer-sync fix, not as a wholesale validator rewrite. `infiquetra-sdlc`
`issue_fields` remains the contract source; `mission-control` vendors generated data and keeps local
control flow hand-maintained. `validate_card_body(body)` stays body-only for compatibility, and a
context-aware prepared-readiness path should enforce issue-type/risk conditional fields when those
values are known. Prepared actionable issue bodies should be compiled from contract data rather than
from separate freehand Asgard/Olympus strings. Saga remains template-free and delegates issue body
ownership to `mission-control`.

**Rejected alternatives.** *Generate or vendor the home-lab validator algorithm into mission-control* —
rejected because the established boundary is generated data plus hand-maintained consumer algorithms.
*Replace `validate_card_body(body)` with a signature that requires type/risk* — rejected because
existing body-only callers such as `flow validate-card` should keep working. *Copy SDLC issue templates
into Saga* — rejected because the handoff boundary already says `mission-control` owns issue artifacts.

**Rationale.** Current `main` already enforces the always-required body surface through the generated shim,
so redoing that work would churn the wrong layer. The live gaps are prepared body compilation, risk-aware
readiness, stale template docs, and vendored schema/data parity.

**Revisit when.** The validator algorithm is relocated into `infiquetra-sdlc`; GitHub issue forms become
the only authoring path again; or Asgard starts accepting actionable Hermes task cards through a distinct
non-Olympus runtime gate.

**Refs.** Issue #222; plan
[`docs/plans/2026-06-17-mission-control-issue-contract-sync-plan.md`](../plans/2026-06-17-mission-control-issue-contract-sync-plan.md).

## 2026-06-13

### Correct the operator-choice ultracode framing; add `adversarial_confidence` + `has_code_surface` to the backend recommender (PR #215, squash `331505a`)  {#operator-choice-docs-and-confidence}

**Decision.** (1) Document `cc-workflows-ultracode` as deterministic fan-out **and** independent/adversarial
verification; the line to `team-execution` is **governance** (consensus + named scanner gates + guarded
deploy), framed as *artifact kind* — a throwaway signal vs a standing blocking verdict (operator-choice §3.2).
(2) Add `adversarial_confidence` as a second ultracode trigger beside `broad_independent_fanout` (default
False). (3) Add `has_code_surface` (default True): pure docs/spec/research neutralizes the output-blind
code-shaped proxies (`file_count`, `phase_count`, `has_infra`, `has_security`, `deployment_sensitive`);
`cross_repo` + `needs_consensus` survive as output-agnostic governance signals; the ultracode risk-suppressor
is itself gated by it. (4) Keep the lean precedence `team-execution > cc-workflows-ultracode > inline`
unchanged.

**Rejected alternatives.** *Plain reaffirm* — the §3.2 sentence is provably false against the Workflow tool
spec + official docs, and the `inline` reachability gap is real. *A new decision mechanism (rebuild the
ladder)* — it maps onto the existing `if/elif` and would churn the locked assertions for no behavioral gain.
*An `output_kind` enum (code|docs|research) as a primary chooser* — the code/docs correlation breaks (trivial
code, contested specs, broad code migrations); keying on the label misroutes those. *Keep a docs size-backstop
to team-execution* (Agent 1's caution) — the real governance docs go off-chain (`/strategy`, `/spec` don't
call the recommender); a governance doc that reaches it carries `needs_consensus` or breadth; forcing consensus
ceremony on uncontested docs is the misfire being fixed. *Names `no_deploy_surface` / `is_docs`* —
double-negative / too narrow; `has_code_surface` (positive, default True) names the real discriminator and
makes the safe default the conservative one.

**Rationale.** The routing was ~80% right (the code's risk gate already encoded governance); this makes the
prose true and reaches the two shapes the helper couldn't — adversarial confidence, and docs de-escalation.
Minimal blast radius: two default-safe kwargs + one predicate clause; every locked assertion is unchanged.

**Revisit when.** `has_code_surface` gets mis-set often in practice (it is a looser caller judgment than the
others — revisit toward deriving it, or folding `cross_repo` into the neutralizer); OR `parse_issue.py` gains a
real file-touch signal for infra/security (then neutralizing those two for docs is redundant); OR
`adversarial_confidence` over-routes to ultracode in practice (PR #216 gated it to an **explicit**
many-attempts request, but it still lacks a true magnitude gate — add one if it fires too readily).

**Refs.** LEARNINGS [#operator-choice-ultracode-framing-and-docs-proxies](LEARNINGS.md#operator-choice-ultracode-framing-and-docs-proxies);
refines [#operator-choice-framework](#operator-choice-framework).

## 2026-06-09

### Saga documentation source model and generated SVG visual kit (commit `2f9f2f2`)  {#saga-docs-source-model}

**Decision.** Maintain Saga's comprehensive user documentation from a curated docs model at
`plugins/saga/docs/model/saga-docs-model.yaml`, with generated SVG assets under
`plugins/saga/docs/assets/` rendered by `plugins/saga/scripts/render_docs_visuals.py`. The README is
the atlas/index; detailed manual pages live under `plugins/saga/docs/`.

**Rejected alternatives.**
- *Hand-maintained Mermaid or PNG diagrams as the primary visual source.* Rejected: the user explicitly
  wanted presentation-worthy visuals, and hand-maintained images drift from command/state reality.
- *Graphviz/D2/Python Diagrams as a new dependency.* Rejected: Saga's first four visuals are simple
  enough for deterministic direct SVG, and a new renderer dependency would make docs maintenance heavier.
- *Fully generated manual prose.* Rejected: command selection needs curated operator judgment; the model
  guards coverage while the manual carries human-readable decisions.

**Rationale.** Saga's facts were already present but scattered across wrappers, SKILL files,
dispatch-table references, saga state docs, and sibling Codex-port docs. A curated model gives reviewers
one coverage surface for commands, routes, readiness, scenarios, owners, and visuals; deterministic SVG
keeps the visual layer reviewable in git and reusable in README/manual/presentation contexts.

**Revisit when.** The visual set grows beyond simple fixed-layout diagrams, a docs site becomes a real
product surface, or the source model starts duplicating source-of-truth behavior instead of documenting
selection and coverage.

**Refs.** `docs/plans/2026-06-09-saga-comprehensive-documentation-plan.md`;
`plugins/saga/docs/model/saga-docs-model.yaml`; `plugins/saga/scripts/render_docs_visuals.py`;
LEARNINGS {#visual-docs-need-rendered-sanity-check}.

### Track renamed Hermes plugin repo in Mission Control (commit `75aae9e`)  {#mission-control-hermes-plugin-repo-rename}

**Decision.** Update the vendored Mission Control repository mapping to use
`infiquetra-hermes-plugins`, and update current journal references that point readers at the
Hermes-facing plugin repository.

**Rejected alternatives.**
- *Rely on GitHub redirects.* Rejected: project mapping data is not a clone URL and must match the
  canonical repository name used for board routing.
- *Leave journal references under the old name.* Rejected: the affected entries are current
  guidance for where to inspect Hermes plugin examples, not only historical evidence.

**Rationale.** This repo remains an active Mission Control source and reference lineage for the
Codex/Antigravity ports. Keeping the repo mapping and current guidance aligned avoids drift across
the plugin-family variants during the cutover.

**Revisit when.** Mission Control discovers repositories live instead of using vendored canonical
sets, or this repo no longer carries Mission Control as an active source plugin.

**Refs.** `plugins/mission-control/config/project-mappings.json`;
`plugins/mission-control/tests/test_project_mappings_resolution.py`.

## 2026-06-07

### Saga document formatting contract — one shared reference, table-rendered schema (squash `abcc06b`, PR #205, #201)  {#saga-doc-formatting-contract}

**Decision.** All nine saga doc-writing skills (ideate, plan, brainstorm, spec, strategy, retro, doc-review, code-review, founder-review) link one shared reference, `saga/references/formatting-style.md`, which mandates: ≤3-sentence blank-line-separated paragraphs; a one-line summary opening each ranked item/section; comparative or ranked data as a table; the compact engineer-facing schema fields (basis/confidence/complexity/axis/status, findings severity/file/line) rendered as a table while narrative fields stay prose; no-hard-wrap soft-wrap for generated output; and dropping a field a heading already carries. A pytest (`tests/test_saga_doc_formatting.py`) enforces the no-stacked-bold-label rule and the link-presence rule across the templates.
**Rejected alternatives.** Per-template duplication (drifts — `plan` fixed the CommonMark collapse once at `plan-sections.md` and `ideate` regressed into the stack anyway); a two-file `.fields.yaml` sidecar or a full doc serializer (both serve a field-level parser that does not exist, and a serializer cannot author narrative prose); fenced-block-for-all-fields (loses the at-a-glance scannability of the compact fields).
**Rationale.** A single referenced contract means one edit improves every skill and the next new one; the table render kills the CommonMark collapse, scans at a glance, and — since the schema consumer is an LLM reader plus a human, not a regex — is *more* legible, not a parse risk; the pytest makes the format unable to silently regress.
**Revisit when.** A real field-level parser is introduced for ideation/review schemas (a structured sidecar like the rejected R1 may then earn its place), or the pytest's stacked-bold-label heuristic proves too narrow or too noisy in practice.
**Refs.** `docs/plans/2026-06-07-saga-doc-readability-plan.md`; `docs/ideation/2026-06-07-saga-doc-readability-ideation.md`; `docs/reviews/2026-06-07-saga-doc-readability-plan-doc-review.md`; LEARNINGS {#saga-doc-schema-no-field-parser}.

---

## 2026-06-05

### Whole-family plugin rename — Scheme Y: functional names + a shared `saga` category, drop the `infiquetra-` prefix, fold `blueprint-reviewer` into `saga` (squash `b6a03e0`, PR #199)  {#plugin-family-rename-scheme-y}

**Decision.** Rename the lifecycle/SDLC/deploy plugin family to short **functional names** and consolidate it under a shared marketplace **category `saga`** — "Scheme Y" of the rename options. The renames: `infiquetra-lifecycle` -> **`saga`**, `sdlc-manager` -> **`mission-control`**, `infiquetra-deploy` -> **`deploy`**. Drop the `infiquetra-` prefix (it was carried by only 2 of 18 plugins — this family — so prefix-consistency was never real). **Fold `blueprint-reviewer` into `saga`** rather than keeping it standalone: its idea/spec/issue rubric libraries move to `plugins/saga/references/rubrics/{idea,spec,issue}/{core,extras}/` and its reviewer script to `plugins/saga/scripts/lifecycle_review.py`. Rebrand the SDLC command/skill surface off the `sdlc-` prefix (`/issue`, `/board`, `/metrics`, `/triage`, `/flow`, `/labels`, `/milestones`, plus `/rollout` for deploy) and **drop the `/sdlc-create` compatibility alias**. Net marketplace: **17 plugins**, metadata **2.1.0**. This repo is **Phase 1** of a coordinated multi-repo migration.

**Kept on purpose (NOT renamed).** The SDLC-domain tokens are **externally anchored to the `infiquetra-sdlc` repo** (its issue taxonomy / schema / vocabulary), so renaming them here would desync from the source of truth. Retained as-is: the `sdlc_manager.py` module filename, `config/sdlc-schema.json`, `agents/sdlc-operator.md`, `docs/sdlc-issue-drafts/`, and the `INFIQUETRA_SDLC_PATH` env var. The directory prefix + the user-facing command/skill brand changed; the SDLC vocabulary inside `mission-control` did not. Also kept separate on purpose: `team-execution` and `deploy` are **NOT vendored into `saga`** — they stay standalone plugins that `saga` routes to, preserving their own boundaries (validator/nonprod automation for team-execution; tag-promotion/deploy mutation for deploy).

**Rejected alternatives.**
- *Prefix-consistency (rename everything TO `infiquetra-*`).* REJECTED — only 2 of 18 plugins carried the prefix, so "consistency" meant adding noise to 16 plugins to match 2; dropping it from the 2 is the cheaper, cleaner direction.
- *A `saga-*` sub-brand (`saga-lifecycle`, `saga-sdlc`, `saga-deploy`).* REJECTED — re-introduces a prefix we just removed and buries the functional name; the shared **category** `saga` groups the family in the marketplace without prefixing every name.
- *Consolidate the whole family into one `saga` plugin.* REJECTED — collapses three distinct boundaries (lifecycle engine, SDLC issue/board ownership, deploy mutation) into one plugin, losing the ownership seams the engine-merge campaign deliberately preserved; `mission-control` and `deploy` stay separate.
- *Descope to a `saga`-only rename (the DA's recommendation — leave `sdlc-manager` + `infiquetra-deploy` alone).* REJECTED — **Jeff overrode** the devil's-advocate descope: the family reads as one unit, so a half-rename (rename lifecycle, leave the prefix on deploy + the `sdlc-` brand on the SDLC commands) would leave the inconsistency the rename exists to fix. Whole-family in Phase 1.

**Rationale.** The lifecycle plugin's 13-command engine-merge campaign made `infiquetra-lifecycle` the spine of a tightly-coupled trio (lifecycle routes to SDLC handoff and to deploy). Short functional names (`saga` / `mission-control` / `deploy`) + a shared `saga` category make the family legible at a glance; the `infiquetra-` prefix added length without grouping value (2 of 18). Folding `blueprint-reviewer` in removes a fourth plugin whose rubric-based review is squarely lifecycle review work — it belongs under `saga`, not beside it. The SDLC tokens stay because they answer to an external contract (`infiquetra-sdlc`), and team-execution/deploy stay standalone because their boundaries are real, not cosmetic.

**Revisit when.** A fourth repo consumes these plugins and the short names collide with another `saga`/`deploy` in its namespace (revisit prefixing); OR `infiquetra-sdlc` itself renames its SDLC vocabulary (re-sync the kept-on-purpose tokens then); OR the `mission-control`/`deploy` boundaries stop earning their separateness (revisit the consolidation rejection). The follow-on migration phases (home-lab, the antigravity fork, dotfiles, infiquetra-sdlc) each have their own revisit triggers tracked with that phase.

**Refs.** Ship record: ARCHIVE [#plugin-family-rename-shipped](ARCHIVE.md#plugin-family-rename-shipped). The campaign whose engine now lives under `plugins/saga/` — [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign), ARCHIVE [#lifecycle-engine-merge-campaign-complete](ARCHIVE.md#lifecycle-engine-merge-campaign-complete). Squash `b6a03e0`, PR #199.

---

## 2026-06-04

### Rebuild `/optimize` as the lifecycle's metric-driven optimization engine — CE `ce-optimize` SINGLE-SOURCE port + infiquetra-native agent-usability metric class (NOT a merge), off-chain, saga UNTOUCHED (PR #197, squash d00a506)  {#optimize-engine-rebuild}

**Decision.** Rebuild `/optimize` from a 20-line stub into a **metric-driven optimization engine** — the **thirteenth and FINAL command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`, `/spec`). It runs a **bounded-experiment loop** toward a measurable target: pick a metric, baseline it, hypothesize, run a bounded experiment, measure the delta, keep or discard, repeat until the target is hit or the budget is spent. The five settled interview answers:

- **(Q1) Saga UNTOUCHED.** `/optimize` writes no saga, advances no `lifecycle_phase`, and makes **no `saga.py` edit at all** — mirrors `/strategy` / `/spec`. It is **off-chain** (advisory, never blocks `/loop`). It records the run **narratively**.
- **(Q2) ZERO new Python.** No new script ships; the engine is SKILL-resident. (Contrast `/qa`, which shipped one ported scorer — `/optimize` needs none.)
- **(Q3) Eight metric classes** — the **maximal v1 taxonomy**: performance, cost, reliability, **agent-usability**, security, quality, developer-experience, maintainability.
- **(Q4) Handoff DEFERRED.** No `docs/optimize/` is added to `handoff_envelope.py`'s `SOURCE_DIRS`, and **no `handoff_envelope.py` edit** ships. An optimization run's durable output is narrative, not a `/handoff`-discoverable artifact yet; wire it only when a run routinely needs to become an SDLC issue.
- **(Q5) Operator-choice OFFERS.** `/optimize` **does** cite operator-choice — independent experiments fan out cleanly across backends (default **serial inline**). The choice is recorded **narratively** (saga-untouched), not via an `orchestration_mode` saga field.

The five decisions a–e:

- **(a) One engine, no profile-coach sibling.** `/optimize` is a single metric-loop engine. There is **no** developer-psychographic question-coach sibling (gstack `plan-tune`'s shape) — that supplies nothing portable.
- **(b) Serial default + shed CE's worktree/parallel machinery.** Experiments run serial inline by default; CE `ce-optimize`'s in-engine worktree spawn / parallel-runner plumbing is **shed** (parallelism is offered via operator-choice, not baked into the engine).
- **(c) OFFERS operator-choice, recorded narratively** (see Q5).
- **(d) `/qa` boundary = gate vs loop.** `/qa` **gates a shipped change** (ship-or-not); `/optimize` **loops toward a measurable target** by bounded experiment. "Good / secure enough to ship?" → `/qa`; "drive this metric toward a target?" → `/optimize`.
- **(e) `/pulse` boundary = bounded vs continuous, and not a gate.** `/optimize` is a **bounded** experiment loop with a target and a budget; a future `/pulse` would be **continuous live telemetry**, not a one-shot loop and not a gate. The optimize-side boundary is settled; `/pulse` stays a separate queued item.

**Honest attribution (load-bearing).** `/optimize` is a **CE `ce-optimize` SINGLE-SOURCE PORT**. The **agent-usability** metric class is an **infiquetra-native** angle (Jeff's) — **NOT a gstack contribution**: a **full-file grep of gstack `plan-tune` for the agent-usability terms returned ZERO**. gstack `plan-tune` is a developer-psychographic question-coach that supplies **nothing portable** and is **not ported**. This is **NOT a merge** of any kind; gstack is credited with **no insight**.

**Rejected alternatives.**
- *Frame as a balanced CE+gstack merge.* REJECTED — gstack `plan-tune` supplies nothing portable; a grep for the agent-usability terms returned zero. Single-source CE port is the honest provenance.
- *Port ce-plan / a benchmark harness.* REJECTED — `ce-optimize` is the metric-loop engine to port; ce-plan is `/plan`'s engine.
- *Add a gstack profile-coach sibling command.* REJECTED — one engine; the question-coach shape is not what `/optimize` is for.
- *Bake in-engine worktree parallelism (CE's runner).* REJECTED — shed it; parallel fan-out is offered via operator-choice (default serial inline), not hardwired.
- *Add `docs/optimize/` to handoff `SOURCE_DIRS`.* REJECTED — deferred; an optimization run's output is narrative, not yet a `/handoff` source. No `handoff_envelope.py` edit.
- *Make the saga read-only (read the work-thread for evidence).* REJECTED — there is no real downstream consumer for an `/optimize` saga write or read; saga UNTOUCHED is the cleaner off-chain stance (the recurring dead-wiring guard).

**Rationale.** Metric improvement work kept lacking a repeatable engine — "make it faster / cheaper / more reliable" routed nowhere with discipline. `/optimize` is that engine: a bounded-experiment loop with an explicit target, a baseline, and a budget, across 8 metric classes. Off-chain + saga-untouched keeps it from blocking the loop or dead-wiring a saga write; narrative recording avoids a saga field with no consumer. The agent-usability class is the infiquetra-native angle that makes the engine fit a 1-human + agents shop — earned honestly, not borrowed.

**Revisit when.** The 8-class taxonomy proves unwieldy in practice (it is the **maximal v1 set** — trim if classes go unused); OR an optimization run routinely needs to become an SDLC issue (revisit Q4 handoff-deferred); OR the prose-only experiment log demonstrably drifts/corrupts across context compaction (revisit ZERO-new-Python — see QUEUED [#optimize-log-helper](QUEUED.md)); OR a `/pulse` continuous-telemetry command is built (settle the shared boundary from the pulse side).

**Refs.** ARCHIVE [#optimize-engine-rebuild-shipped](ARCHIVE.md#optimize-engine-rebuild-shipped) + the campaign-complete capstone; LEARNINGS [#shipped-on-origin-not-in-stale-local-tree](LEARNINGS.md#shipped-on-origin-not-in-stale-local-tree), [#campaign-brief-merge-is-a-provenance-hypothesis](LEARNINGS.md#campaign-brief-merge-is-a-provenance-hypothesis) (its third firing); the off-chain / saga-untouched twins — [#strategy-engine-rebuild](#strategy-engine-rebuild), [#spec-interrogation-engine-rebuild](#spec-interrogation-engine-rebuild); the gate sibling — [#investigate-systematic-debugging-engine-rebuild](#investigate-systematic-debugging-engine-rebuild) (the `/qa`-boundary pattern); operator-choice — [#operator-choice-framework](#operator-choice-framework). Campaign — [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign) (now COMPLETE). Consumed QUEUED [#optimize-engine-merge](QUEUED.md); added QUEUED [#optimize-log-helper](QUEUED.md).

### Add `/spec` as the lifecycle's spec-interrogation engine — gstack `spec` SINGLE-SOURCE WHAT-interrogation port (the WHAT-rigor sibling of `/plan`'s HOW-rigor), off-chain, saga UNTOUCHED (PR #195)  {#spec-interrogation-engine-rebuild}

**Decision.** Add `/spec` — the **twelfth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`) and the campaign's **spec-interrogation engine**: the pass that owns relentless **WHAT-rigor** — the sibling of `/plan`'s HOW-rigor. A **gstack `spec` SINGLE-SOURCE port** of the WHAT-interrogation half: the principal-engineer-who-refuses-ambiguous-work persona, the HARD GATE (no spec after message 1 — always start the interview), Phase-1 five-Why, Phase-2 scope / MVP / out-of-scope / failure-mode lock, Phase-3 read-code-first grounding, quantify-everything, and a draft-review pass. The four settled Qs + decisions a–d:

- **(Q1) Saga UNTOUCHED.** `/spec` writes no saga, advances no `lifecycle_phase`, and makes **no `saga.py` edit at all** — mirrors `/strategy`. It is **off-chain** (advisory, never blocks `/loop`). Its only durable output is a sharp WHAT artifact under `docs/specs/`.
- **(Q2) Handoff = add `docs/specs/` to the handoff source set.** `handoff_envelope.py` now treats `docs/specs/` as an auto-discoverable handoff SOURCE: `Path("docs/specs")` added to `SOURCE_DIRS` (the **functional** edit — a fresh spec becomes discoverable). `infer_maturity()` maps `docs/specs/` → `requirements-ready` — this **equals the existing default**; it is set for consistency with the other source dirs, **NOT a behavior change and NOT dead-wiring**: a spec is a sharp WHAT, **not** plan-ready. `infer_lifecycle_phase()` leaves `docs/specs/` returning `"unknown"` (off-chain — no lifecycle phase); **no `spec` member is added to `LIFECYCLE_PHASES`**.
- **(Q3) Read-code-first = HARD with a non-code escape.** Phase-3 grounding requires citing `path:line` before asking design questions; a non-code ask (pure product/process) takes the documented escape rather than fabricating a citation.
- **(Q4) Exec gate = OPTIONAL `/doc-review` pass.** A spec may be routed through `/doc-review` for readiness; the `docs/specs/ → requirements` path tie-breaker steers that pass to the **requirements** lens, not the blueprint `/spec-review` route.
- **(c) Operator-choice NEVER OFFERS.** `/spec` does not cite operator-choice: a single durable spec artifact has no parallelism to escalate; size/risk lives in its scope sections, and the downstream executor (`/plan` / `/work`) owns backend selection. (Mirrors `/strategy`'s never-offers row; also consistent with saga-untouched.)
- **(d) Brainstorm-seam resolved in favor of a standalone `/spec`** (option b of `#brainstorm-spec-interrogation-seam`): `/spec` owns WHAT-rigor; `/brainstorm` stays the divergent explorer and now offers **Sharpen with `/spec`** in its Phase-4 menu (divergent `/brainstorm` → convergent `/spec`).

**Honest attribution (load-bearing).** Single source = gstack `spec`, WHAT-interrogation half only. There is **NO CE spec engine** (ce-plan is `/plan`'s planning engine — not ported, not fabricated as a "ce-spec"). There is **NO /ideate+/brainstorm graft** — the assumption-challenge + failure-mode register is **native to gstack's persona**; the failure-mode bank already lives in `/plan/references/interrogation.md` (itself a gstack port). No superpowers borrow. `/spec` and `/plan` split one gstack source along the **WHAT vs HOW** altitude axis; the `/spec` SKILL does **not** duplicate `/plan`'s interrogation register. Sheds the entire gstack preamble (telemetry/gbrain/plan-mode/vendoring/routing-injection/writing-style/Boil-the-Lake/feature prompts), the dedupe machinery, the codex quality gate, the two-layer redaction, `--execute` worktree spawn, gh issue authoring/filing, and the `~/.gstack` store.

**Rejected alternatives.**
- *Map `docs/specs/` to `plan-ready` maturity.* REJECTED — a spec is a sharp WHAT, not an implementation plan; `requirements-ready` is correct (and `/plan` consumes it).
- *Graft ce-plan into `/spec`.* REJECTED — ce-plan is the planning engine `/plan` already ported; there is no CE spec engine to port.
- *Graft the /ideate+/brainstorm assumption-challenge register.* REJECTED — that rigor is native to gstack's persona and already present in `/plan/references/interrogation.md`; grafting it would duplicate, not add.
- *Offer operator-choice.* REJECTED — no parallelism to escalate; the downstream executor owns backend selection.
- *Fold the WHAT-interrogation into `/brainstorm`* (option a of the seam). REJECTED — keep `/brainstorm` divergent; relentless WHAT-rigor lands in exactly one place, the standalone `/spec`.

**Rationale.** Vague asks keep reaching `/handoff` and `/plan` and producing under-specified issues agents bounce back. `/plan` deliberately took only gstack `spec`'s HOW-interrogation and left the WHAT-rigor upstream with a one-way bounce to `/brainstorm`; that WHAT-rigor had no settled owner. `/spec` is that owner — the convergent WHAT-sharpening pass that turns a vague ask into a precise, agent-runnable `docs/specs/` artifact, then routes the work OUT (`/handoff` as a `requirements-ready` source, `/plan` for the HOW, or an optional `/doc-review`). Off-chain + saga-untouched keeps it from blocking the loop or dead-wiring a saga write; sdlc-manager keeps sole ownership of issue bodies.

**Revisit when.** A spec routinely needs a backend choice before handoff (revisit (c) operator-choice never-offers); OR `/brainstorm` and `/spec` start competing for the same interrogation in practice (revisit the (d) standalone-vs-fold split); OR a `docs/specs/` artifact needs to participate in the saga chain (revisit Q1 saga-untouched + the `LIFECYCLE_PHASES` decision).

**Refs.** ARCHIVE [#spec-interrogation-engine-shipped](ARCHIVE.md#spec-interrogation-engine-shipped), [#brainstorm-spec-interrogation-seam-resolved](ARCHIVE.md#brainstorm-spec-interrogation-seam-resolved); LEARNINGS [#campaign-brief-merge-is-a-provenance-hypothesis](LEARNINGS.md#campaign-brief-merge-is-a-provenance-hypothesis); the seam it closed — [#plan-engine-rebuild](#plan-engine-rebuild) (where `/plan` took HOW and left WHAT upstream); the off-chain / saga-untouched twin — [#strategy-engine-rebuild](#strategy-engine-rebuild). Campaign — [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Consumed QUEUED [#spec-interrogation-engine](QUEUED.md) + [#brainstorm-spec-interrogation-seam](QUEUED.md).

### Add `/investigate` as the lifecycle's systematic-debugging engine — CE `ce-debug` spine + gstack `investigate` grafts + superpowers borrow, diagnosis-primary, saga READ-ONLY, full `/qa` cross-engine rewire (PR #193)  {#investigate-systematic-debugging-engine-rebuild}

**Decision.** Add `/investigate` — the **eleventh command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`) and the campaign's **net-new systematic-debugging engine**: the diagnostic brain that answers "what is actually broken, and why?" — the causal-chain work `/qa` (the gate) deliberately does not own. A **CE `ce-debug` SPINE** + **gstack `investigate` grafts** + a **superpowers systematic-debugging borrow**:

- **(Q1) Saga READ-ONLY.** `/investigate` reads saga context for evidence (the work-thread's prior ticks, `pr_refs`, plan path) but **writes no saga** and advances no `lifecycle_phase`. It is **off-chain** — advisory, never blocks `/loop`. Like `/retro` (saga read-only) and `/founder-review` / `/strategy` (off-chain, no saga), a diagnostic pass is not a saga-track artifact. Confirmed there is no real downstream CONSUMER for an `/investigate` saga write before adding one (the recurring dead-wiring guard — see `/work`, `/founder-review`, and `/retro`'s dropped `→retro` advance).
- **(Q2) Verification OWN-MINIMAL — NOT a call into `/qa`.** This **overrode the pre-decision** in the QUEUED brief, which read "`/investigate`'s verification phase CALLS `/qa` rather than reimplementing test discipline." `/investigate` carries its **own minimal verification** (confirm the causal chain reproduces, the falsifiable prediction holds, the fix/diagnosis is sound) and routes the heavier acceptance gate OUT. There is **no `/investigate` → `/qa` verify loop`** — `/qa` routes deep failures INTO `/investigate` (the one-directional wiring), and a back-call would create a cycle (`/qa` → `/investigate` → `/qa` → …).
- **(Q3) `/qa` FULL all-refs rewire.** Building `/investigate` closes `/qa`'s deferred "when `/investigate` is built" route at **every site**, not one: the rewire touched **5 `/qa` SKILL mentions** (principle-1 fixer list, the post-merge FAIL branch, the deferral block, the hard-boundary line) + **2 other-file notes** (`operator-choice.md`, office-hours `frame-diagnostic.md`). `/qa`'s post-merge FAIL branch is now a **two-target branch**: deep/uncertain root cause → `/investigate`; clear/trackable defect → `/handoff`. Pre-merge still → `/work`. Routing still **reads** `loop/references/dispatch-table.md`.
- **(Q4) Learning-capture BOTH-SPLIT.** Non-obvious root causes → journal LEARNINGS; a confirmed trackable bug → an sdlc-manager defect issue (via `/handoff` — describe the defect with the DEBUG REPORT **linked as evidence**, never passed to `handoff_envelope`'s path-classifier) — both, with a split by what the finding is. `/investigate` does not create issues itself (sdlc-manager owns that).

**Key design points.**
- **CE `ce-debug` is the SPINE** (252L, all engine, the cleaner port base): causal-chain gate, **falsifiable predictions for uncertain links** (predict something in a *different* code path that must also be true; a wrong prediction but a "working" fix = symptom not cause — the same mechanic `/qa` grafts), assumption audit, Phase-0 triage with issue-tracker fetch + trivial fast-path, smart-escalation, parallel read-only sub-agent dispatch.
- **gstack `investigate` GRAFTS:** the pattern-signature table (race / null / state / integration / config / cache), the two distinct numeric stop gates (hypothesis-exhaustion + 3-failed-fix), the DEBUG REPORT Status enum. Dropped: gstack scope-lock/freeze (CE's minimal-diff + workspace-check covers it), the GSTACK REVIEW REPORT gate, the ~755L preamble, gstack-learnings bins, and all gstack runtime bins.
- **Diagnosis-primary, never a fixer.** Output is a DEBUG REPORT (file:line, causal chain, regression-test path, Status enum) — agent-consumable **evidence**; the fix reaches `/work` via a `/handoff` issue (not by `/work` reading `docs/investigations/`). Routes the work OUT by what it finds: a **real fix** → `/work` (via a `/handoff` issue); an **applied inline fix** → `/work` or `/code-review` to ship; a **trackable defect** → `/handoff`; a **design-level root cause** → `/brainstorm`. It does not commit, push, open/merge a PR, or deploy.
- **ZERO new Python, ZERO `saga.py` / `handoff_envelope.py` / `saga-spec.md` edits.** `/investigate` is a markdown engine (SKILL + references + command) reusing existing helpers. Operator-choice offered (saga read-only) for large/parallel fixes + parallel hypothesis-probes; default single-hypothesis/single-file inline.

**Rejected alternatives.**
- *Fold debugging into `/qa`.* REJECTED — `/qa` is gate-only by its own settled boundary (0.13.0); a diagnostic fix-loop brain is a distinct job. ADOPT standalone was the brief's verdict.
- *`/investigate`'s verification CALLS `/qa` (the brief's pre-decision).* REJECTED/OVERRIDDEN — own-minimal verification instead; a back-call into `/qa` creates a routing cycle (`/qa` already routes INTO `/investigate`).
- *Write a saga / advance `lifecycle_phase`.* REJECTED — off-chain, saga read-only; no real downstream consumer, the recurring dead-wiring trap.
- *Close `/qa`'s deferral at only the one obvious site.* REJECTED — a deferred cross-engine route leaves notes at multiple sites; closing one and missing four leaves stale "future" framing live (LEARNINGS [#deferred-cross-engine-wiring-must-close-on-build](LEARNINGS.md#deferred-cross-engine-wiring-must-close-on-build)).
- *Keep gstack scope-lock/freeze + the runtime bins.* REJECTED — CE's minimal-diff/workspace-check covers scope; the bins are dead weight (campaign shed pattern).

**Rationale.** Debugging today is unstructured ad-hoc whack-a-mole; `/qa` surfaces failures (with a falsifiable prediction for uncertain causes) but is gate-only and cannot do root-cause work. `/investigate` owns the causal-chain brain `/qa` routes to, with CE's prediction discipline as the spine and gstack's pattern table / stop rule / report enum grafted on. Diagnosis-primary keeps it from colliding with `/work` (which fixes) — it produces the agent-consumable DEBUG REPORT and routes the fix out. Saga read-only + off-chain keeps it from blocking the loop and avoids a dead-wired saga write. Own-minimal verification (not a `/qa` back-call) avoids a routing cycle.

**Revisit when.** A real prod incident-response surface appears (revisit whether `/investigate` should read live telemetry/logs beyond the repo); the pattern-signature table needs tuning to infiquetra's serverless/Lambda/DynamoDB stack (queued tuning); or own-minimal verification proves too thin and a structured `/qa` handoff (artifact, not a call) becomes worth the seam.

**Refs.** Plugin `0.16.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). The `/qa` gate-only boundary this engine complements (and the falsifiable-prediction graft `/qa` carried for it) — DECISIONS [#qa-engine-rebuild](#qa-engine-rebuild). Off-chain / saga-read-only siblings — DECISIONS [#retro-engine-rebuild](#retro-engine-rebuild), [#founder-review-engine-rebuild](#founder-review-engine-rebuild), [#strategy-engine-rebuild](#strategy-engine-rebuild). The deferred-wiring lesson + the routed-output dead-wiring axis — LEARNINGS [#deferred-cross-engine-wiring-must-close-on-build](LEARNINGS.md#deferred-cross-engine-wiring-must-close-on-build). Consumed from QUEUED [#investigate-systematic-debugging-engine](QUEUED.md#investigate-systematic-debugging-engine). Ship record: ARCHIVE [#investigate-systematic-debugging-engine-shipped](ARCHIVE.md#investigate-systematic-debugging-engine-shipped). Shipped via PR #193, squash 5079d8f.

---

## 2026-06-03

### Rebuild `/retro` as the meta-improvement engine — a real 3-source merge (gstack `retro`+`learn` + CE `ce-compound`) behind a tiered self-edit gate, saga READ-ONLY (PR #191, squash f6faae2)  {#retro-engine-rebuild}

**Decision.** Rebuild `/retro` — the **tenth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`) — from a 19-line stub into the lifecycle's **meta-improvement engine**: the engine that captures lifecycle learnings, curates durable journal knowledge, and proposes improvements to the workflow itself (up to and including the lifecycle plugin's own SKILLs). A **real 3-source merge**: gstack `retro` (forensics + the stale-base/wrong-"today" BLOCK guard) + gstack `learn` (the knowledge-curation loop) + CE `ce-compound` (the "leave the system smarter" framing). The four interview answers settled with Jeff:

- **(Q1) FULL engine in v1 — all 6 net-new passes + lean metrics, nothing deferred.** All six net-new passes neither source has — (1) structured interview of Jeff, (2) session-transcript review as evidence, (3) "do we need a NEW skill/plugin?", (4) refine `infiquetra-lifecycle` ITSELF, (5) refine claude/agent/antigravity directive files, (6) memory updates/pruning across the journal + auto-memory — ship in v1, with a **lean** metrics snapshot (not gstack's full quantitative forensics). The QUEUED brief's "MVP = interview + curation + pruning; defer metrics + self-refinement to v2" split was rejected: Jeff wants the whole meta-improvement engine now.
- **(Q2) Single `/retro` command + an optional pass argument.** One command runs all passes; a focused sub-pass can be invoked directly via an optional arg (e.g. a curate-only or prune-only run). Not separate `/retro interview` / `/retro curate` / `/retro prune` commands — one engine, selectable passes.
- **(Q3) Tiered self-edit gate.** Pure-append, additive-only journal writes **auto-apply**; **everything else** — every delete / modify / move of existing durable state — is **propose-diff-and-wait**. This is the safety contract for a self-modifying engine (LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate)).
- **(Q4) Full self-modification blast radius — including the lifecycle SKILLs.** The gate's reach is the **complete** self-modification surface: the journal, `.claude` memory, the claude/agent/antigravity directive files, AND `infiquetra-lifecycle`'s own SKILLs. The engine can propose edits to itself. Reach is **full**; safety comes from the hard gate (Q3), not from narrowing what the engine may touch.

**Key design points.**
- **Saga READ-ONLY — the planned `->retro` advance is dead wiring, dropped, so NO `saga-spec.md §11` row.** `/retro` reads saga context for evidence but writes **no** saga and advances **no** `lifecycle_phase`. The pre-rebuild plan's `work`/`qa`→`retro` saga advance was **dead wiring** — `/retro` is a terminal, off-chain reflection pass whose durable sink is the journal, not a saga track; a retro tick would just record "a retro happened" with no consumer. So `/retro` is saga read-only: `saga.py` is untouched AND `saga-spec.md` gets **no §11 change** (the campaign's first command consumer that deliberately writes nothing to the saga).
- **In-repo vs global/cross-project directive disambiguation, with a cross-project warning.** The directive-refinement pass (Q4 reach) distinguishes a **repo-local** directive (this repo's `CLAUDE.md`, this repo's journal) from a **global / cross-project** one (`~/.claude/CLAUDE.md`, auto-memory, the antigravity directive class). A repo-local edit follows the normal tiered gate; a global / cross-project edit carries an **extra cross-project-impact warning** before the propose-diff, because the blast radius spans every repo (LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate)).
- **3-source merge frame: gstack `retro` + `learn` + CE `ce-compound`.** gstack `retro` contributes the lean metrics snapshot + the stale-base/wrong-"today" BLOCK guard; gstack `learn` contributes the typed/confidence/source curation loop (staleness + contradiction + dedup) as the memory-pruning mechanism; CE `ce-compound` contributes only the compounding frame (leave the system smarter, output agent-consumable findings → journal entries + concrete edit proposals, not a 4500-word essay).
- **ZERO new Python — reuse only.** `/retro` is a markdown engine (SKILL + references + command) that reuses existing helpers (read-only `gh` evidence, the journal sink, existing saga readers); it adds **no** `.py`. `saga.py` is untouched.
- **Stale-base guard scoped to the windowed mode.** gstack's stale-base/wrong-"today" BLOCK guard (which maps onto Jeff's validation-discipline rule) is kept but **scoped to the windowed/metrics mode** — the mode that reads a time-window of git history — not applied to every pass (a pure interview pass has no base to be stale against).

**Folded-in deferred sub-items (from the consumed QUEUED brief — nothing silently dropped).**
- **Antigravity directive class — a global/cross-project surface.** The directive-refinement pass's reach explicitly includes the **antigravity directive files** as one more **global / cross-project** directive surface (alongside `~/.claude/CLAUDE.md` and auto-memory) — so it gets the same cross-project-impact warning. Folded here from the QUEUED brief's directive-files pass so it is not lost when the brief entry is removed.
- **Output-routing of surfaced follow-ups — OPEN.** When a pass decides "new skill/plugin needed" or "refine command X," whether the output is a QUEUED entry, a `/handoff`, or a ready-to-run ultracode/team-execution plan is **left open** for the build to settle per-case (a retro proposing a large multi-file self-edit offers to hand EXECUTION to team-execution or an ultracode workflow; it proposes + names the tool, never auto-launches a destructive self-edit). Recorded here so the open routing question survives the QUEUED removal.

**Rejected alternatives.**
- *The dead-wiring saga advance (`work`/`qa`→`retro` `lifecycle_phase` transition).* REJECTED — `/retro` is a terminal off-chain reflection pass; a saga advance to a `retro` phase has no downstream consumer and would record "a retro happened" with nothing reading it. `/retro` is saga read-only; no `saga.py` edit, no `saga-spec.md §11` row.
- *MVP-then-v2 split (defer metrics + self-refinement).* REJECTED — Jeff wants the full meta-improvement engine in v1: all 6 net-new passes + lean metrics, nothing deferred (Q1).
- *Narrow the self-modification reach (exclude the lifecycle SKILLs / directive files) instead of gating it.* REJECTED — full reach + a hard tiered gate beats narrow reach; the engine must be able to improve itself, and safety comes from propose-diff-and-wait + the cross-project warning, not from forbidding the edit (Q3/Q4, LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate)).
- *Flat-absence contract floors (treat an absent pass / absent finding as a hard failure).* REJECTED — a pass with no evidence (e.g. no transcripts to review, no directive drift) is a graceful no-op, not a contract violation; floors assert mechanism presence, not that every optional pass fired.
- *Auto-apply directive / memory / lifecycle-SKILL edits like journal appends.* REJECTED — only pure-additive journal appends auto-apply; every delete/modify/move of existing durable state is propose-diff-and-wait, and a global/cross-project edit needs the extra warning.
- *Sub-mode commands (`/retro interview`, `/retro curate`, …).* REJECTED — one `/retro` command with an optional pass arg (Q2); separate commands fragment the engine.

**Rationale.** `/retro` is the meta-improvement engine — the pass that makes the whole lifecycle (and Claude itself) smarter after each loop — and it had only a 19-line stub. The three sources each contribute a distinct mechanic (gstack `retro` forensics + guard, gstack `learn` curation, CE `ce-compound` framing), merged into one engine we own. The danger is that a meta-engine that can edit its own plugin, memory, and directive files is a foot-gun; the answer is full reach behind a **tiered self-edit gate** (auto-apply pure-additive journal appends; propose-diff-and-wait everything else; extra cross-project warning for global edits). Saga read-only because retro is a terminal off-chain reflection pass, not a saga-track step — so zero `saga.py` edits and no §11 change. No new Python.

**Revisit when.** A retro's auto-applied journal append turns out to need human review too (tighten the auto-apply tier); the windowed-metrics mode's stale-base guard fires falsely on a legitimately old base; the output-routing open question (QUEUED vs `/handoff` vs ready-to-run plan) needs a settled default rather than per-case judgment; or a real `/investigate` / `/pulse` lands and overlaps the metrics/curation passes.

**Refs.** Plugin `0.15.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). The self-modifying-engine safety lesson (tiered gate + cross-project warning) — LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate). Saga read-only / off-chain siblings (write no saga) — DECISIONS [#founder-review-engine-rebuild](#founder-review-engine-rebuild), [#strategy-engine-rebuild](#strategy-engine-rebuild). Consumed the QUEUED brief `#retro-meta-improvement-engine` (removed; its deferred sub-items folded in above). Ship record: ARCHIVE [#retro-engine-rebuild-shipped](ARCHIVE.md#retro-engine-rebuild-shipped). Commit: f6faae2 (PR #191, squash f6faae2).

### Rebuild `/strategy` as the interview-driven STRATEGY.md engine — a faithful single-source CE `ce-strategy` PORT (PR #189, squash a9d4c90)  {#strategy-engine-rebuild}

**Decision.** Rebuild `/strategy` — the **ninth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`) — from a 21-line stub into the lifecycle's **interview-driven STRATEGY.md engine**. A **faithful single-source PORT of CE `ce-strategy`**, NOT a merge: it is the campaign's second single-source port (after `/founder-review`'s gstack port), but here the single source is **CE**. The four interview answers settled with Jeff:

- **(Q1) CE-only source — gstack has no strategy engine.** Jeff's pre-audit intent named "gstack cso (Chief Strategy Officer)", but that file is the Chief **SECURITY** Officer — a 14-phase security audit, the **wrong officer**. The `cso` ≈ "Chief Strategy Officer" name-match was a mixup, not a verified mapping (LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic)). gstack has **nothing** strategy-specific to steal; CE `ce-strategy` is the sole engine source. This makes `/strategy` a single-source PORT, not a two-engine merge.
- **(Q2) Keep all 8 sections + the Rumelt kernel.** Port the whole engine: the Rumelt-grounded kernel (diagnosis / guiding-policy / coherent-action), the Phase-1 8-section interview, and the locked template — no trimming. CE's structure is the proven engine; reducing it would re-stub the command.
- **(Q3) Agent-as-customer is persona-only — tracks stay pure investment areas.** Personas may name **AI-agent actors when the product is agent-consumed**; **tracks remain pure investment areas / domains of work, NOT actors.** The QUEUED brief's pre-written adaptation ("personas/tracks must name AI-agent actors") was **half a category error** — tracks are domains of work, not actors — caught by reading the real CE `interview.md` section semantics + a Jeff challenge (LEARNINGS [#spec-adaptation-is-a-hypothesis](LEARNINGS.md#spec-adaptation-is-a-hypothesis)). Only the persona-as-agent-customer half is sound.
- **(Q4) Keep the mandatory 2-round pushback per section.** CE's relentless 2-round-pushback-per-section discipline is kept verbatim, not softened — it is the mechanism that turns shapeless prose into a real strategy.

**Key design points.**
- **Artifact home = the repository-root `STRATEGY.md`.** The durable direction lives at the repo root (a single locked-template doc: 3-5 metrics, 2-4 tracks), rerunnable update-in-place via Phase-0 file-state routing (new doc vs targeted-section update vs pick-a-section).
- **ZERO `saga.py` edits — off-chain / pre-saga.** `/strategy` runs **upstream of the work loop** and writes **no saga**, the same off-chain position as `/founder-review` (DECISIONS [#founder-review-engine-rebuild](#founder-review-engine-rebuild)): the saga's `review_paths`/`lifecycle_phase` are the wrong home for a durable direction doc, and the guard would skip ~always. Cross-session persistence = the committed `STRATEGY.md` + the journal ADR.
- **No new Python.** `/strategy` is a markdown engine (SKILL + references + command); `saga.py` is untouched. No team-execution / workflows offer (a single durable doc, no parallelism).
- **Strategy records, founder-review challenges.** The two are complementary on a STRATEGY.md: `/strategy` is the *direction-recording* engine; `/founder-review` is the *ambition lens* that challenges it (and `/doc-review` the readiness lens). Not a collision.

**Rejected alternatives.**
- *Merge a gstack strategy engine in (the pre-audit "gstack cso" mapping).* REJECTED — `cso/` is the Chief SECURITY Officer; there is no gstack strategy engine to merge. A plausible name match is not a verified mapping.
- *Trim CE's 8 sections / drop the Rumelt kernel.* REJECTED — reducing the structure re-stubs the command; the whole engine is the value.
- *Name AI-agent actors in tracks too (the QUEUED brief's blanket adaptation).* REJECTED — tracks are investment areas / domains of work, not actors; only persona-as-agent-customer is a sound adaptation, and only for agent-consumed products. The blanket note was half a category error.
- *Soften the mandatory 2-round pushback to a lighter touch.* REJECTED — the relentless pushback is the mechanism that produces a real strategy; softening it reverts toward facilitation.
- *Write a saga / advance `lifecycle_phase`.* REJECTED — `/strategy` is off-chain/pre-saga; a durable direction doc is not a saga-track artifact. Zero `saga.py` edits.

**Rationale.** `/strategy` owns the durable repository direction — "where are we pointed, and why?" — and it had only a stub. CE `ce-strategy` is the sole real engine source (gstack's `cso` is the wrong officer), so this is a faithful single-source port: keep the Rumelt kernel, the 8-section interview, the 2-round pushback, and the locked template; record direction off-chain in `STRATEGY.md` (no saga, like `/founder-review`); name AI-agent actors only in personas for agent-consumed products, never in tracks (which are domains of work). No new Python — `/strategy` is a markdown engine.

**Revisit when.** A repo's `STRATEGY.md` needs metrics wired to live telemetry (revisit the qualitative-only stance — overlaps the queued `/pulse` / `/optimize` metric loops); a real gstack (or other) strategy engine appears worth merging; or strategy starts needing to write durable cross-session state beyond the committed doc (revisit the no-saga position).

**Refs.** Plugin `0.14.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Off-chain/pre-saga sibling (no saga write, records-vs-challenges) — [#founder-review-engine-rebuild](#founder-review-engine-rebuild). Source-mapping correction (gstack `cso` = SECURITY, not Strategy; name-match ≠ verified mapping) — LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic). The spec-adaptation-is-a-hypothesis lesson (the brief's blanket tracks-as-actors note was half a category error) — LEARNINGS [#spec-adaptation-is-a-hypothesis](LEARNINGS.md#spec-adaptation-is-a-hypothesis), which pairs with [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways). Ship record: ARCHIVE [#strategy-engine-rebuild-shipped](ARCHIVE.md#strategy-engine-rebuild-shipped). Shipped via PR #189 (squash a9d4c90).

### Rebuild `/qa` as the gate-only acceptance-evidence engine — a real gstack `/qa`+`/qa-only` merge + ce-debug graft, severity-banded verdict + ported deterministic health score, saga qa-track consumer (PR #187, squash fb2c1b3)  {#qa-engine-rebuild}

**Decision.** Rebuild `/qa` — the **eighth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`) — from a 19-line stub into the lifecycle's **gate-only acceptance-evidence engine**: the gate downstream of `/work` + `/code-review` that answers "does the shipped thing actually work?". A **real two-engine merge** against the **cloned** gstack source (`/qa` 354L `.tmpl` + `/qa-only` 114L + `/investigate` 259L) plus a CE `ce-debug` graft — **not** a phantom (gstack was first absent from the local install cache, then cloned from GitHub; see LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways)). `/qa` adopts gstack's own report-only **`/qa-only` model**: it classifies the change into risk classes, runs acceptance checks (browser folded under behavior as one MCP class), gathers evidence, assigns severity, derives a ship verdict, writes a durable artifact, advances the saga qa-track on pass, and routes — and **never fixes, commits, pushes, opens/merges a PR, deploys, files SDLC issues, or sets readiness labels**. The four interview answers settled with Jeff:

- **(Q1) Gate + route, NEVER fix.** The `/qa-only` model. Campaign-consistent (every shipped review/verify command is gate-only), faithful to gstack's own report/fix split, and zero git-mutation surface. `/work` (round-N) and the future `/investigate` own all fixing. gstack's fix half — Phase 8, the WTF-likelihood guard, atomic fix commits, regression-test generation-as-action — is **dropped**; regression tests are **recommended** in the report, not generated.
- **(Q2) Severity-banded verdict + a PORTED deterministic health score, reported ALONGSIDE each other [RE-OPENED, final].** This question moved twice. Jeff **initially said keep gstack's score**; an interim review then wrongly claimed gstack had "no formula" (LLM-eyeballed) and on that basis the score was briefly slated to be **dropped → zero new Python**. That "no formula" claim was a one-hop-short source read and is corrected — the formula **is real**: `scripts/resolvers/utility.ts:286-321` is a deterministic weighted **Health Score Rubric** (per-finding deductions Critical -25 / High -15 / Medium -8 / Low -3, explicit category weights, `score = Σ (category_score × weight)`), exported as `generateQAMethodology` and injected as the `{{QA_METHODOLOGY}}` macro `qa/SKILL.md.tmpl:122` (the interim "no formula" reading stopped at `gen-skill-docs.ts`; corrected in LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways)). Once the real formula was located, **Jeff chose to PORT it, not drop it** — a deterministic scorer (`scripts/qa_health_score.py`) that ports gstack's deduction values **verbatim** (critical -25 / high -15 / medium -8 / low -3), swaps gstack's web-only category weights (Console/Links/Visual/Functional/UX/Performance/Content/Accessibility — which don't map onto serverless / SDK / Ansible / plugin work) for **documented infiquetra 9-way ship-risk-class weights** (behavior 20, security 20, data 15, api 15, deployment 10, infra 10, config 5, docs 3, trivial 2 — ranked by ship blast radius), **re-normalizes the weights over only the in-scope classes** (a class absent from findings is N/A and excluded; present-but-clean scores 100), and emits a **delta against a baseline-from-prior-report** score. The 0-100 number is reported **ALONGSIDE** the severity-banded verdict — pass/fail per risk class + critical/high/medium/low findings + a ship verdict (`ship` / `ship-with-deferred` / `no-ship`) from the tier threshold. **Honest caveat (in the scorer's own docstring):** the scorer's inputs are LLM-assigned severities, so the score is **one signal, not the gate decision** — the severity-banded verdict remains the gate. Severity uses gstack's vocab with a documented ↔ P0-P3 cross-walk to `/code-review`. **This adds one new script: `qa_health_score.py` (the scorer) + its oracle test.**
- **(Q3) Saga qa-track consumer (advance), zero `saga.py` edits.** `restore` the work-thread → run the gates → write `qa_paths` + on PASS advance `lifecycle_phase` from `work` to `qa` (the advance `/work` 0.10.0 explicitly deferred to this rebuild); on FAIL keep `lifecycle_phase=work` and record evidence. Every flag already exists — `qa` @ `LIFECYCLE_PHASES` (`saga.py:56`), `--lifecycle-phase qa` (`:1057`), `--qa-paths` (`:1075`), `qa_paths` field (`:155`) — and there is no phase-transition validation in `_merge`, so the advance is unblocked with **zero `saga.py` edits**. No fix sub-saga. Adds the missing `/qa` (and the also-missing `/code-review`) row to `saga-spec.md §11`.
- **(Q4) Ship a durable risk-class reference.** A 9-way risk router (PRIMARY) + per-class acceptance/evidence checklists; gstack's 7 web categories + per-page browser checklist fold under behavior/browser as **one MCP-driven class** (chrome-devtools/playwright, graceful no-op off-UI); the file-pattern → risk-class map (diff-aware); severity defs + the P0-P3 cross-walk; the ship-verdict derivation + tier → blocking-threshold table.

**Key design points.**
- **ce-debug graft = the falsifiable-prediction mechanic specifically [DA-M3].** The single distinct ce-debug import (the rest of "evidence discipline" already lives in `/code-review` principle 2): for each failure whose **cause is uncertain**, state a falsifiable prediction — "if this is the real cause, X in a different path must also fail." A wrong prediction means symptom, not cause; a right one gives the routed fixer a head start. Obvious-cause findings skip it.
- **Merge-state failure routing [DA-H3, the big correctness catch].** PASS → `/handoff` or `/retro`. FAIL routes by **merge state**: pre-merge (PR open) → `/work` (re-enter the round-N loop, wired via `/work` Phase 0.4 `pr_refs`); post-merge (merged to `main`) → `/handoff` to open a **new defect thread** (NOT `/work` round-N — a merged saga's PR would cycle the merged PR straight back to `/qa`). `/investigate` is **future-prose only** — it is not on the dispatch-table's routable list, so `/qa` never emits it as a runnable route. Routing **reads** `loop/references/dispatch-table.md` (never restated).
- **Diff-aware mode reuses `/code-review`'s stale-base mechanic [DA-H4].** Pre-merge: `git fetch origin <base> --quiet; DIFF_BASE=$(git merge-base origin/<base> HEAD); git diff --name-only "$DIFF_BASE"` (two-dot merge-base, not three-dot, which is empty post-merge on `main`). Post-merge: read the merge commit's changeset via `gh pr view <N> --json files`.
- **Browser is one MCP-driven risk class, not seven web categories.** gstack's `$B`/`browse` daemon, bun build, and CDP coupling are dropped; the browser check uses the installed MCP and is a graceful no-op for serverless / SDK / Ansible / plugin repos.
- **Pin `--phase` on the PASS tick [DA-M4].** The qa-advance tick reuses the restored integer `phase` so `--phase-status complete` does not advertise a phantom counter advance.
- **`docs/qa/` collision with `/optimize` resolved in-PR [DA-M2].** The shipped `/optimize` stub also wrote `docs/qa/`; resolved here with a one-line change of `/optimize` to `docs/optimize/` (not deferred). `handoff_envelope.py` does not classify `docs/qa/`, so no handoff/sdlc classifier collision.
- **One new script (the ported scorer), no `agents/` dir.** The Q2 final lands one new Python file — `scripts/qa_health_score.py` (the deterministic health scorer) + its oracle test; otherwise `/qa` is a markdown engine (SKILL + 2 refs + command + the scorer + tests). Parallel/large risk-class verification offers an operator-choice backend and uses **generic `Explore`/`Task` agents** (the `/code-review:164` convention — no plugin `agents/` dir).

**Rejected alternatives.**
- *Gate + opt-in fix, or fix-by-default.* REJECTED — `/qa` owning any fix path adds a git-mutation surface and competes with `/work`/`/investigate`; gstack itself ships the report-only `/qa-only` as a separate command. Gate-only is campaign-consistent.
- *Drop gstack's 0-100 health score entirely.* REJECTED (the interim "no formula → drop" position was itself superseded). The score's deduction formula **is real** (`scripts/resolvers/utility.ts:286-321`, the `{{QA_METHODOLOGY}}` macro); the honest move once it was located was to PORT it — a deterministic, reproducible scorer — and report it **alongside** the banded verdict, with the explicit caveat that its inputs are LLM-assigned severities (so it is one signal, not the gate). Dropping a real, deterministic formula would have thrown away reproducible signal. See LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways).
- *Invent the scorer's weights from scratch.* REJECTED — fabricating deduction values would be net-new false precision (and a tautological test). Instead we **port gstack's deduction values verbatim** (critical -25 / high -15 / medium -8 / low -3) and only **document the infiquetra class weights** (the one deliberate adaptation, because gstack's weights are web-only categories that don't map onto infiquetra work), re-normalized over the in-scope classes — porting a proven formula, not inventing one.
- *Fix sub-saga for failures.* REJECTED — `/qa` is gate-only; a fix sub-saga is a fix loop by another name. Failures route to the merge-state-correct fixer.
- *Read-only saga consumer (no phase advance).* REJECTED — `/work` deferred the `work`→`qa` advance specifically to this rebuild; declining it would leave the deferred advance permanently unlanded.
- *Edit `saga.py` to add a qa-specific path.* REJECTED — every flag already exists and the advance is unblocked; `/qa` is a pure consumer (zero `saga.py` edits).
- *Custom `/qa` subagent / an `agents/` dir.* REJECTED — contradicts the shipped `/code-review:164` no-`agents/`-dir convention; parallel verification uses generic agents.
- *Browser-coupled (port gstack's `browse`/CDP daemon).* REJECTED — most infiquetra repos are non-UI; browser is one risk-driven MCP class behind the router, a graceful no-op off-UI.

**Rationale.** `/qa` is the acceptance-evidence GATE — "is the shipped thing actually shippable?". Keeping it gate-only matches gstack's own `/qa-only` split and every shipped lifecycle review/verify command, and keeps all fixing in `/work` + the future `/investigate`. On the score: its formula (`scripts/resolvers/utility.ts:286-321`) is real and deterministic, so the honest move once it was located was to **PORT it** (deduction values verbatim, documented infiquetra class weights, re-normalized) and report the 0-100 number **alongside** the severity-banded verdict — with the explicit caveat that its inputs are LLM-assigned severities, so the score is one signal and the banded verdict stays the gate. That keeps reproducible signal instead of discarding a proven formula; it lands one new script (`qa_health_score.py` + its oracle test). The saga qa-track consumer lands the advance `/work` deferred without touching `saga.py`, and the merge-state failure routing is grounded in the actual `/work` Phase 0.4 re-entry + the dispatch-table's routable list rather than an aspirational `/investigate` route.

**Revisit when.** `/investigate` ships (then deep post-merge failures route there for root-cause work instead of `/handoff`); a real UI product makes the browser class high-frequency enough to warrant more than one MCP-driven check; or a health signal becomes available whose **inputs** are deterministically measured (not LLM-assigned counts) and genuinely additive over the banded verdict (revisit the dropped score — gstack's formula is real, but only re-adopt a number when its inputs are measured, not eyeballed).

**Refs.** Plugin `0.13.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Consumes the saga foundation as the qa-track consumer (zero edits) — [#saga-schema-foundation](#saga-schema-foundation), spec `plugins/saga/references/saga-spec.md` §11. Lands the advance deferred by — [#work-engine-rebuild](#work-engine-rebuild) (`work/SKILL.md:354`). Gate-only + no-`agents/`-dir conventions from — [#code-review-engine-rebuild](#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`; the `git merge-base` diff mechanic). No-false-precision posture from — [#founder-review-engine-rebuild](#founder-review-engine-rebuild). The future debugging engine `/qa` routes to — QUEUED [#investigate-systematic-debugging-engine](QUEUED.md#investigate-systematic-debugging-engine). Source-fidelity lesson (clone the repo; read the engine, not the scaffold) — LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways), the counterpart to LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Ship record: ARCHIVE [#qa-engine-rebuild-shipped](ARCHIVE.md#qa-engine-rebuild-shipped). Shipped via PR #187 (squash fb2c1b3).

### Rebuild `/resume` as the lifecycle's heavy forensic reconstruction engine — a real CE `ce-sessions` PORT (PR #185, squash 73975ec)  {#resume-engine-rebuild}

**Decision.** Rebuild `/resume` — the **seventh command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`) — from a 23-line "read committed docs first" doc into the lifecycle's **heavy forensic reconstruction engine**, the **unblocked heavy partner** the `/loop` rebuild (0.11.0) explicitly deferred to it. The lightweight/heavy split is now both halves shipped: `/loop` owns the **lightweight** scan → restore → route + inline cold-reconstruction; `/resume` owns the **heavy** forensic dig. Unlike `/loop` (the campaign's native rebuild against a phantom brief source), `/resume` is a **real CE `ce-sessions` PORT** — its named upstream was verified to exist and be portable, the **opposite** of the `/loop` phantom. Two tiers: **Tier 1** (saga-anchored deep reconstruction — the common path) = a NEW saga **all-ticks reader** walking the full append-only tick-chain trajectory + PR archaeology + conflict reconciliation; **Tier 2** (FALLBACK ONLY, no saga AND no resolvable issue) = a slim Claude-only port of CE `ce-sessions` (discover → file-mediated skeleton extract to scratch → generic-agent synthesis). The four interview answers settled with Jeff:

- **(Q1) Port CE `ce-sessions` now, staged behind Tier 1.** Yes, port the CE forensic session-log reconstruction — but as **Tier 2 fallback only**, behind the saga-anchored Tier 1. The brief source was verified TRUE + portable (the positive counterpart to the `/loop` phantom — see LEARNINGS [#resume-port-source-verified-true](LEARNINGS.md#resume-port-source-verified-true)).
- **(Q2) Drop the `[gstack-context]` WIP-commit trailer.** `/resume` does NOT adopt gstack's `[gstack-context]` save-trailer. The saga's append-only tick log already IS the durable trajectory; a parallel commit trailer would duplicate the saga it would have to reconcile against.
- **(Q3) Route to any phase via the REFERENCED shared dispatch-table — no ping-pong.** `/resume` routes to any lifecycle phase via the **shared** `loop/references/dispatch-table.md` (referenced, never duplicated — single source of truth). It does NOT route back through `/loop` (no `/loop` ↔ `/resume` ping-pong) and does not maintain its own copy of the table.
- **(Q4) Write one git-ignored re-entry tick reusing the restored `saga_id`.** On a successful Tier-1 reconstruction `/resume` writes **exactly one** git-ignored re-entry saga tick, **reusing the restored `saga_id`** — never minting a new saga. `/resume` is a reader/restorer, not a saga primary writer.

**Key design points.**
- **A real port — the opposite of `/loop`.** The `/loop` rebuild's lesson was "verify a brief's source claims before building" (LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact)). Applying that same verification to `/resume` confirmed CE `ce-sessions` exists and is portable — verification cuts both ways. `/resume` is a genuine CE port (file-mediated extraction discipline + generic-agent synthesis), not a native author-from-scratch.
- **Two-tier, Tier-2 context-safe by construction.** Tier 1 is the common path (a saga exists or an issue resolves to one); Tier 2 fires ONLY when there is **no saga AND no resolvable issue** — same-machine work that never wrote a saga (NOT a fresh clone — corrected from the DA's H3). Tier 2 never reads multi-MB session JSONL into context: it discovers candidates, extracts a file-mediated skeleton to scratch, and hands the skeleton to a generic agent for synthesis. Context-safety is structural, not a budget guess.
- **Generic-agent synthesis — no `agents/` dir [C1].** Tier-2 synthesis uses **generic** agents, honoring the convention the shipped `/code-review` encodes (no plugin `agents/` dir → generic agents, `skills/code-review/SKILL.md:164`). Adding an `agents/` dir would have been a structural first against a settled sibling convention.
- **The all-ticks `read_ticks` lives in `saga.py`, NOT `load_saga_context.py` [brief deviation].** The brief implied extending `load_saga_context.py`. But that wrapper is **issue-locked** — its `--issue` argument is required — so it is structurally the wrong layer for a cold, no-issue trajectory read. The all-ticks capability belongs in the saga engine itself (`saga.py read_ticks`); `load_saga_context.py` stays the shared issue-keyed substrate `/loop` and `/resume` both use. See LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer).
- **Tier 1 is not a `/loop` echo [DA-H1].** `/loop`'s lightweight restore reads only the **latest** tick; `/resume`'s Tier-1 all-ticks reader walks the **full** append-only log (the trajectory `/loop` cannot see). `load_saga_context.py` is the **shared substrate** both consume — `/resume`'s value-add over `/loop` is the all-ticks trajectory + PR archaeology + conflict reconciliation, not a re-implementation of `/loop`'s restore.
- **Reuse-`saga_id` never-mint discipline [C2].** `/resume` reuses the restored `saga_id` for its one re-entry tick. `saga.py save` mints unconditionally, so never-mint is SKILL-prose discipline (reuse the resolved id) + verified by test, the same shape `/code-review`'s append-only/never-mint used.
- **Boundary.** `/resume` reconstructs + restores + routes; it does NOT mint a new saga, does NOT own a phase's execution loop, and does NOT duplicate the dispatch table.

**Rejected alternatives.**
- *Saga-anchored-only (drop the CE port).* REJECTED — leaves the lifecycle with **no** cold-recovery path when no saga and no issue exist (the verified hole — LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer)). Tier 2 fills exactly that gap.
- *Adopt the `[gstack-context]` commit trailer.* REJECTED — duplicates the saga's append-only log; a parallel durable trajectory to reconcile against is churn, not value.
- *Section-11-literal routing (a `/resume` copy of the routing table).* REJECTED — the dispatch table is `loop/references/dispatch-table.md`; reference it, do not fork it (single source of truth, no drift).
- *Pure read-only (no re-entry tick).* REJECTED — a resumed thread that records nothing leaves the next resumer blind; one git-ignored re-entry tick (reusing the saga_id) marks the resume without minting.
- *Extend `load_saga_context.py` for the all-ticks read.* REJECTED — the wrapper's `--issue` is required, so it is issue-locked and cannot serve a cold no-issue read; the capability belongs in `saga.py`.
- *Re-port gstack context-save/restore.* REJECTED — that engine is the already-shipped saga; there is nothing left to port.
- *Custom `/resume` subagent (an `agents/` dir).* REJECTED — contradicts the shipped `/code-review:164` no-`agents/`-dir convention; use generic agents.
- *Port CE's keyword/branch relevance ranking now.* REJECTED for v1 — recency-MVP ranking is enough until a no-saga forensic returns >5 candidates; deferred to QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking).

**Rationale.** `/resume` is the lifecycle's cold-recovery engine — "I lost context, rebuild the work-thread and continue." The `/loop` rebuild deliberately deferred the heavy half here, and the saga foundation gave it a durable trajectory to reconstruct from. Tier 1 (saga all-ticks) is the common, high-value path; the CE `ce-sessions` Tier-2 port is the last-resort fallback for same-machine work that never wrote a saga — the only path that previously had **no** recovery (the issue-locked `load_saga_context.py` could not serve it). Keeping the all-ticks read in `saga.py` (not the issue-locked wrapper), using generic agents (the `/code-review` convention), referencing the shared dispatch table (no fork, no ping-pong), and reusing the restored `saga_id` for one re-entry tick all keep `/resume` aligned with the conventions the campaign already settled.

**Revisit when.** Codex/Cursor forensics become a real recovery source (revisit the Claude-only Tier-2 port); a no-saga forensic routinely returns >5 candidate sessions and recency-only mis-ranks (revisit the deferred keyword/branch relevance ranking — QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking)); or a fresh-clone (cross-machine) recovery path becomes a real need (Tier 2 is scoped to same-machine today).

**Refs.** Plugin `0.12.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Consumes the saga foundation (adds the all-ticks `read_ticks` reader) — [#saga-schema-foundation](#saga-schema-foundation), spec `plugins/saga/references/saga-spec.md`. Heavy partner of the lightweight half — [#loop-engine-rebuild](#loop-engine-rebuild) (Q4, the lightweight/heavy split it deferred). Verification-cuts-both-ways counterpart to the phantom-source lesson — LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact), [#resume-port-source-verified-true](LEARNINGS.md#resume-port-source-verified-true). No-`agents/`-dir convention catch — DECISIONS [#code-review-engine-rebuild](#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`). Wrapper-wrong-layer learning — LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer). Ship record: ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). Deferred relevance ranking: QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking). Shipped via PR #185 (squash 73975ec).

### Rebuild `/loop` as the campaign's one NATIVE router engine — no upstream to port or merge (PR #183, squash 1fca13a)  {#loop-engine-rebuild}

**Decision.** Rebuild `/loop` — the **sixth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) — from a router stub into a **self-contained native router engine**. This is the campaign's **ONE native rebuild**: unlike every prior rebuild, there is **no upstream engine to port or merge**. CE ships no router; the gstack "dispatch table SKILL" the QUEUED brief named is **phantom** (verified — gstack's root SKILL is browser-testing, there is no router dir; see LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact)); and gstack's context-save/restore is the shipped **saga** plus the queued `/resume`'s engine, **not** `/loop`'s. So `/loop` is authored fresh against the lifecycle's own primitives (saga + operator-choice). Three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive** (inline phase walk with a per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan → restore → route a durable work-thread, with inline cold-reconstruction). The four interview answers settled with Jeff:

- **(Q1) Offload model: inline phase walk + per-decision operator-choice offer; offload pointer scoped to `/loop`-OWNED work only; `/loop` does NOT instruct a routed command's backend.** In Drive mode `/loop` walks the lifecycle phases inline and offers the three execution backends (`inline`/`team-execution`/`cc-workflows-ultracode`) **per decision point** for work it owns. The offload pointer is recorded **only for `/loop`-owned offloads**. When `/loop` *routes* to another command (e.g. `/work`), it does **not** instruct that command's backend — `/work` writes but never reads `orchestration_mode` (verified — SKILL:174,190), so any instruction would have no receiver. Each command owns its own backend decision.
- **(Q2) Routing tick: existing fields + offload pointer only; no schema change.** A routing event ticks the saga carrying the **existing** fields (kind/id/phase/round/status) plus the offload pointer **only for `/loop`-owned offloads**. No new saga schema field — the offload pointer rides existing envelope structure. Avoids foundation churn against the shipped saga spec.
- **(Q3) Durable substrate: volatile `.claude/infiquetra-lifecycle/` + committed artifacts.** `/loop`'s re-entry reads from the volatile session dir `.claude/infiquetra-lifecycle/` for in-flight state plus the committed artifacts (plans, reviews, work-sessions) as the durable substrate. Same split the rest of the lifecycle uses; `/loop` adds no new persistence location.
- **(Q4) Resume split: `/loop` owns lightweight, `/resume` (queued) owns heavy.** `/loop` owns a **lightweight** scan→restore→route plus **inline cold-reconstruction** via `load_saga_context.py` when re-entering without a live session. The **heavy forensic** reconstruction (commit-trailer archaeology, CE forensic reconstruction) belongs to the then-queued `/resume` rebuild — **since SHIPPED 0.12.0**, ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). The `/resume` route from `/loop` is **opt-in advisory**, not a hard handoff.

**Key design points.**
- **No upstream port/merge — authored native.** This is the load-bearing distinction from every prior rebuild. The QUEUED brief (produced by a budget-exhausted brief workflow — see LEARNINGS [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget)) asserted a "gstack dispatch table SKILL" source that does not exist. Verifying that before building (rather than trusting the brief) is what kept the rebuild from chasing a phantom merge — see LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). `/loop` is built directly on the saga (storage) + operator-choice (decision) contracts.
- **Additive saga picker-field extension — closes Defect 1 of `#code-review-saga-scan-touchups`.** `saga.py` `scan()` / `_saga_summary` gained the `issue_ref` / `plan_path` / `branch` match keys (plus `destination` + the `orchestration_mode`/`orchestration_ref` pair the `/loop` picker needs) so a resuming `/loop` (and a standalone `/code-review`) can match the right thread **without** `restore`-ing every candidate. This is the additive, no-schema-churn fix for **Defect 1** of the cross-skill defect the `/work` rebuild surfaced (scan-dict omitted the match keys) — shipped here with the `/loop` rebuild, asserted by `test_scan_exposes_picker_fields`. **Defect 2 (the `/code-review` Phase-5.4 programmatic-mode append contradiction) is a `/code-review` SKILL change, out of scope for this rebuild — which touched no other skill — and REMAINS queued.**
- **Boundary.** `/loop` classifies + routes + (in Drive) walks phases for work it owns; it does NOT override a routed command's own loop (`/work` keeps owning its execution + PR loop), does NOT do heavy forensic reconstruction (`/resume`), and does NOT instruct a destination command's backend.

**Rejected alternatives.**
- *Full hand-to-Workflow (offload the whole loop to a Claude Code Workflow).* REJECTED — overrides `/work`'s own execution loop; each command owns its backend, `/loop` only offers it per decision for work it owns.
- *Router-only (drop the Drive inline-walk value-add).* REJECTED — Route alone makes `/loop` a thin dispatcher with no value over invoking the command directly; the Drive inline phase walk + per-decision backend offer is the value-add.
- *Fold `/resume` into `/loop`.* REJECTED — scope-creeps the queued `/resume` P1 (heavy forensic reconstruction); `/loop` owns only lightweight scan→restore→route + inline cold-reconstruction.
- *Committed offload pointer (a new committed index file).* REJECTED — duplicates the saga index; the routing tick carries the pointer on existing envelope structure.
- *Extend the saga schema for the offload pointer.* REJECTED — foundation churn against the shipped saga spec for a `/loop`-only field; ride existing fields.
- *Instruct the destination command's backend.* REJECTED — no receiver (`/work` never reads `orchestration_mode`, SKILL:174,190); the instruction would silently no-op.
- *Port a gstack "dispatch table".* REJECTED — it does not exist (phantom brief source; root gstack SKILL is browser-testing, no router dir).
- *Re-port gstack context-save/restore.* REJECTED — that engine is the already-shipped saga + the queued `/resume`'s scope, not `/loop`'s.

**Rationale.** `/loop` is the lifecycle's front door — the command that decides where work goes — and it had only a stub. There was no engine to inherit (CE has no router; the named gstack source is phantom), so it had to be authored native against the lifecycle's own saga + operator-choice contracts. Keeping the Route/Drive/Resume split — and scoping the offload pointer + backend offer to `/loop`-owned work only — keeps `/loop` from overriding the per-command backend ownership the campaign already settled (`/work` reads no `orchestration_mode`). Shipping the additive saga picker-field extension here closes **Defect 1** of the cross-skill scan defect the `/work` rebuild surfaced without a schema change; Defect 2 (a `/code-review` SKILL change) remains queued.

**Revisit when.** The `/resume` rebuild lands the heavy forensic reconstruction (revisit the lightweight/heavy split + the advisory `/resume` route); a routed command starts reading `orchestration_mode` (revisit the "do not instruct destination backend" decision); the offload pointer needs to survive across sessions in a queryable way (revisit the no-new-persistence + ride-existing-fields decision); or a real upstream router engine appears worth porting.

**Refs.** Plugin `0.11.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Built native on the saga foundation — [#saga-schema-foundation](#saga-schema-foundation) — and the operator-choice contract — [#operator-choice-framework](#operator-choice-framework). Backend-ownership partner (writes but never reads `orchestration_mode`) — [#work-engine-rebuild](#work-engine-rebuild). Closes Defect 1 of the scan touch-up — ARCHIVE [#code-review-saga-scan-touchups-shipped](ARCHIVE.md#code-review-saga-scan-touchups-shipped); Defect 2 remains QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups). Heavy-resume partner (since SHIPPED 0.12.0): DECISIONS [#resume-engine-rebuild](#resume-engine-rebuild), ARCHIVE [#resume-engine-rebuild-shipped](ARCHIVE.md#resume-engine-rebuild-shipped). Phantom-source learning: LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Ship record: ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped). Shipped via PR #183 (squash 1fca13a).

### Rebuild `/work` by merging CE `ce-work` execution engine + gstack `ship`/`land-and-deploy` into a saga-primary-writer execution-loop engine (PR #181, squash d398055)  {#work-engine-rebuild}

**Decision.** Rebuild `/work` — the **fifth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`) and the **execution-loop track** — from a 39-line facilitator stub into a **self-contained infiquetra execution engine that merges CE's `ce-work` execution engine (Jeff-preferred spine) with gstack `ship`/`land-and-deploy`'s autonomy + readiness/staleness gates**. This is a genuine **two-source merge** (like `/code-review`), not a single-source port (like `/founder-review`). It is the **most architecturally entangled** rebuild of the campaign because it lands two deferred foundations at once: the saga becomes first-class (`/work` is its **primary writer**) and the deferred `recommend_execution_backend()` CLI helper finally gets a real caller. Five numbered phases: enter + scan saga + triage + detect round-N → setup + task-list + backend → execute phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready + continuation routing. The four interview answers settled with Jeff:

- **(Q1) Boundary: PR-ready execution + own the round-N PR continuation loop; merge is a confirmed git op `/work` owns; only deploy is delegated.** `/work` executes the build loop to PR-ready, then **owns the PR→review→merge→qa continuation loop** (Jeff's elaboration: "would want to trigger request for review/approval, pickup and /qa after approval and merge, or handle PR requested changes"). `/work` performs the merge itself when destination ⊇ merge, but **only as an explicitly operator-confirmed `gh pr merge`, never silent** — there is no separate "git/human" skill, merge is a git op `/work` owns under confirmation. Only **deploy mutation** is delegated to `infiquetra-deploy`. gstack's canary-verify + offer-revert are **relocated** to `infiquetra-deploy` (a deliberate brief deviation — read to relocate knowingly, not dropped silently; the capability is queued there). Honors saga-spec §1.1/§10 (deploy is deploy's hard boundary).
- **(Q2) Backend offer: recommend + confirm (land `recommend_execution_backend()`).** The deferred CLI helper gets its first real caller: auto-compute the recommendation from size/risk (reusing `should_offer_team_execution`'s six signals), pre-select it, always surface alternatives so escalation is one keystroke, operator confirms. Exactly operator-choice §2. A library-only helper would be uncallable from markdown — the CLI subcommand resolves the deferral.
- **(Q3) Saga role: first-class round-N state spine (primary writer).** `/work` is saga's **primary writer** (saga-spec §11): `restore`-on-resume (rehydrate round/phase/checks_run/next_step), mint/advance `lifecycle_phase` plan→work, a tick per phase boundary, `issue_ref` adoption, `status=done` at completion. It **mints the *findable* saga a standalone `/code-review` appends to** — it sets `issue_ref`/`plan_path`/branch (the match keys), and for its own pre-PR gate calls `/code-review` programmatically and reads the returned envelope **directly** (programmatic mode hands persistence to the caller). The old `load_saga_context.py`/`find_inflight_work.py` become thin read helpers/fallbacks. Resume is deterministic.
- **(Q4) Review gate: hard + override-with-rationale + computed staleness.** Block PR-ready on unresolved P0/P1 (read `/code-review`'s programmatic envelope **directly**) **OR** a stale review (commits since a `/work`-captured reviewed SHA — `git rev-parse HEAD` at review time, `git rev-list <sha>..HEAD --count`). Allow explicit operator override with a **recorded** rationale (never silent). Matches the current stub + `/loop` intent.

**Key design points.**
- **Saga primary-writer; forward-coupling via findable identity, gate via direct envelope.** `/code-review` (shipped 0.8.0) is append-only/never-mint and, when run **standalone**, matches the work-thread saga on `issue_ref`/`plan_path`/`branch`. `/work`'s job is to mint a **findable** saga: it sets `--issue-ref` (the saga-spec §11 issue_ref-adoption write), `--plan-path` when a plan exists, and saves **on the work branch** — the three match keys. For its **own** in-loop pre-PR gate `/work` does **not** depend on code-review finding or writing the saga: it calls `/code-review` programmatically and reads the **returned envelope directly** (programmatic mode = caller owns persistence — code-review writes nothing in that mode). This was a correction folded after the build's adversarial review caught the original "name the identity into the programmatic call so code-review appends" design as **one-sided**: shipped `/code-review` has no arg to receive a caller-named identity and writes no artifact in programmatic mode, so the gate could not read a saga `review_paths` that was never written. Reading the envelope directly + a self-captured reviewed SHA removes that dependency entirely; the standalone-code-review coupling is preserved by the match keys.
- **Round-N saga ownership.** `/work` owns mint + phase tick + round bump (`--rounds-seen`, never `next_round` — it is derived, saga-spec §6.1) + `issue_ref` adoption; a **standalone** `/code-review` appends `review_paths` + preserves `lifecycle_phase`. The two halves of the round-N saga ownership the journal said to settle, now settled. (Residual: `saga.py scan()` does not surface `issue_ref`/`plan_path`/`branch`, so even standalone code-review must `restore` each candidate to match — a cross-skill defect queued for the `/code-review` touch-up, QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups).)
- **`recommend_execution_backend()` lands in `lifecycle_state.py` + a CLI subcommand.** A pure function next to `should_offer_team_execution` (reused, all 6 kwargs passed, plus a `needs_consensus` branch) with an `ultracode` branch and `inline` default. **`alternatives` is computed independently of the precedence winner** so operator-choice §3.3 "offer BOTH on overlap" survives as a one-keystroke escalation. `main()` refactored from the bare positional into `normalize` + `recommend-backend` subcommands (verified no script/test/CI/hook invoked the positional CLI, so the refactor breaks nothing). A deliberate `or needs_consensus` divergence from §3.1's "PLUS" is documented in the docstring.
- **`issue_progress.py` CLI extension.** The *function* `render_issue_comment()` already accepted `work_session_path`/`commit_sha`/`checks_run`/`blockers`/`pr_url`/`review_status`/`doc_review_*`/`deploy_status`/`workflow_url`/`evidence_link`, but the CLI exposed only 8 of those fields — so `/work`'s Phase-4 comment was uninvokable from markdown (dead wiring). This rebuild extends `parse_args`/`main` to forward the full field set (pipe-separated for the list fields). Same "consumer rebuild extends the CLI" pattern as the helper.
- **Computed staleness from a self-captured SHA (the saga has no `reviewed_sha` field).** `/work` captures `REVIEWED_SHA=$(git rev-parse HEAD)` at the moment it runs `/code-review`, then `git rev-list <REVIEWED_SHA>..HEAD --count > 0` ⇒ stale. No parse of a code-review artifact (programmatic mode writes none) and no stored field. Pinned in `test-and-gates.md`. (Corrected from the original artifact-parse design after the adversarial review flagged that programmatic mode writes no artifact to parse.)
- **qa/resume routing is advisory; the qa-phase-advance is honestly deferred.** `/qa` is still a 19-line stub with zero saga awareness (verified). So on merge `/work` sets `phase_status=complete` + `next_step="run /qa"` and routes to `/qa` **advisorily**, but **leaves `lifecycle_phase=work`** — it does NOT claim "/qa owns/advances the qa slot" as if wired. The saga legitimately sits at `work` post-merge until the `/qa` rebuild lands the `qa` advance (`/handoff` deriving `resume-ready` for that state is correct). Likewise `/resume` routing is advisory — `/work`'s own Phase-0 re-entry is the load-bearing "come back later" mechanism, independent of the `/resume` stub.
- **Boundary.** `/work` builds, gates, records, coordinates the PR loop (merge only under explicit confirmation); it does NOT silently mutate GitHub, own deploy/canary (`infiquetra-deploy`), file SDLC issues (`sdlc-manager`), or advance `lifecycle_phase` past `work`.
- **Three new references + own `docs/work-sessions/` artifact dir.** `references/{execution-strategy,test-and-gates,pr-continuation-loop}.md` — the PR-loop transition table got its own ref so the new surface doesn't crowd the SKILL. Work-session artifacts → the canonical `docs/work-sessions/` (no new dir; `handoff_envelope.py` already classifies it).

**Rejected alternatives.**
- *Own canary-verify + offer-revert inside `/work`.* REJECTED — deploy/canary is `infiquetra-deploy`'s hard boundary (saga-spec §1.1/§10); gstack's canary/revert is read-then-relocated to `infiquetra-deploy` (queued there), recorded as a deliberate brief deviation, not dropped silently.
- *Advisory review gate (CE-style, no teeth).* REJECTED — no teeth lets P0/P1 or stale reviews through to PR; the hard gate + honest recorded override matches the stub + `/loop` intent and Jeff's no-lies rule.
- *Load-context-only saga (not a primary writer).* REJECTED — the round-N spine + the standalone-code-review coupling demand `/work` be the first-class minter/writer (setting the findable `issue_ref`/`plan_path`/branch identity), not a read helper.
- *Library-only `recommend_execution_backend()` helper.* REJECTED — uncallable from markdown skills + would drift against the operator-choice doc (the exact reason the 0.5.0 foundation deferred it); ship it with a runnable CLI subcommand, resolved here.
- *Port all of gstack `ship`/`land-and-deploy`.* REJECTED — drags in gbrain, telemetry, VERSION/CHANGELOG/TODOS/Greptile steps, the section-file split, `~/.gstack` persistence, and template machinery irrelevant to infiquetra; extract the autonomy/readiness/staleness/merge-base mechanics, shed the rest.

**Rationale.** `/work` is the loop's execution hub — every real build runs through it — and it had no engine. CE `ce-work` is the proven execution engine (complexity triage, U-ID task-lists, parallel safety, test discipline); gstack `ship` carries the autonomy + readiness/staleness gates CE lacks. Merging both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained and adapted to a 1-human + agents shop. Making `/work` the saga primary-writer is what turns the saga from an unconsumed primitive (and `/code-review`'s append-only write from a no-op) into a real deterministic round-N spine, and landing `recommend_execution_backend()` here gives the deferred operator-choice helper its first real caller. The PR-ready boundary + round-N continuation loop is what makes "PR-ready" not a dead-end while keeping deploy/canary on the right side of the boundary.

**Revisit when.** The `/qa` rebuild lands the `qa` `lifecycle_phase` advance (revisit the post-merge "sits at work" deferral + the advisory routing); the `/resume` rebuild changes who owns cross-session re-entry; `infiquetra-deploy` ships the relocated canary-verify/offer-revert capability (revisit the deploy handoff shape); code-review emits a greppable `reviewed-sha:` token (revisit the staleness parse regex); or the merge-under-confirmation flow proves awkward on real PRs.

**Refs.** Plugin `0.10.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Lands the deferred operator-choice helper — [#operator-choice-framework](#operator-choice-framework). Saga primary-writer against the spec — [#saga-schema-foundation](#saga-schema-foundation). Forward-coupling partner (append-only/never-mint) — [#code-review-engine-rebuild](#code-review-engine-rebuild). Ship record: ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped). Relocated canary capability: QUEUED [#infiquetra-deploy-canary-verify-revert](QUEUED.md#infiquetra-deploy-canary-verify-revert). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. Shipped via PR #181 (squash d398055).

### Port `/founder-review` (alias `/ceo-review`) from gstack `plan-ceo-review` as the scope/ambition review lens (PR #179, squash e4eedf2)  {#founder-review-engine-rebuild}

**Decision.** Rebuild `/founder-review` (alias `/ceo-review`) — the **fourth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`) — from a 20-line stub into a **self-contained infiquetra scope/ambition/direction review engine ported from gstack `plan-ceo-review`** (the 4 scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted pre-review system audit). Unlike `/code-review`'s genuine two-source merge, this is a **PORT, not a merge**: the brief scopes THIS command as **gstack-sole-engine + a single CE posture steal** (the sharpened no-false-precision fragment of `ce-product-pulse`), not a reduced merge. (The brief's "ceo-review" label is loose — the real gstack path is `plan-ceo-review`, verified.) Position in the lifecycle: `/founder-review` is the third member of the review trio — `/doc-review` = plan-readiness, `/code-review` = code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?** — firing **upstream of execution** on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc scope question. Its output is a **scope decision** (challenge direction; `/strategy` records it). The four interview answers settled with Jeff:

- **(Q1) product-pulse: steal the posture only (sharpened); QUEUE a standalone `/pulse`.** Lift only the *transplantable* fragment of CE `ce-product-pulse`'s posture — **no false precision** (when founder-review cites a number — effort, file count, scope size — present it and let the operator judge) + **no hardcoded "too big/too small" thresholds**. Do NOT lift the full telemetry "present the numbers, reader judges" posture wholesale — founder-review is qualitative, not a numbers report. A standalone `/pulse` live-telemetry component is QUEUED (worth-it-when a live product has real telemetry; Infiquetra is pre-revenue greenfield with no data yet).
- **(Q2) Scope modes: keep all 4 (the engine's spine).** SCOPE EXPANSION (cathedral) / SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon) — each distinct, all relevant pre-traction. The operator selects one via `AskUserQuestion` and it is **committed for the whole review — no silent drift**. Context-defaults retained (greenfield→Expansion, enhancement→Selective, bugfix/refactor→Hold, >15 files→suggest Reduction). Trimming re-opens the thin-reskin gap.
- **(Q3) System audit: keep, adapted to infiquetra.** Re-source the pre-review audit to infiquetra inputs — plan artifact + journal + `docs/office-hours/` design notes + `STRATEGY.md` + git context + retrospective + landscape WebSearch (skip gracefully if unavailable); DROP the `~/.gstack`/gbrain/remote-slug/`ceo-plans` machinery. The audit makes the critique grounded (founder-review's analog of code-review's built-vs-planned audit).
- **(Q4) Opt-in flow: per-expansion, capped (+ channel digest).** Keep individual `AskUserQuestion` opt-in per expansion (the "100% in control" guarantee), options A) add / B) defer-to-journal / C) skip, **capped** (gstack's "top 5-6 if >8"). In a redis-channel session `AskUserQuestion` is unavailable → inline + trim aggressively (collapse 0C-bis to a single confirm; present expansions as a digest) so the channel UX stays usable. References `skills/brainstorm/SKILL.md`'s channel-inline convention.

**Key design points.**
- **Scope-layer engine + deep rigor routed in a REAL closed loop.** The engine owns the scope/ambition layer and applies the 9 Prime Directives + 18 CEO patterns as internalized scope-level lenses producing **named scope findings** — it does NOT reproduce gstack's 11 deep-rigor review sections (Architecture, Error-&-Rescue-Map, Security, Data-flow, Code-quality, Test, Performance, Observability, Deployment, Long-Term-Trajectory, Design-&-UX) because infiquetra splits the review lenses (doc/code/founder). Deep rigor is **routed** in a real closed loop: `/doc-review:86` routes *inbound* (suggest founder-review when scope/ambition is prominent); founder-review closes it *outbound* by **writing/updating the (re-)expanded plan artifact and handing it back with the concrete path** (`/doc-review docs/plans/<file>` for readiness; `/code-review` once built). Without the concrete handback, expanding scope then "recommending /doc-review" drops the rigor.
- **founder-review ↔ doc-review boundary stated in the SKILL.** Both can target a `STRATEGY.md`/scope doc; they are complementary lenses — founder-review = *challenge the direction* (ambitious? coherent? worth doing?), doc-review = *check readiness* (can this drive implementation?). The SKILL states this; doc-review already cross-suggests founder-review (`:86`). No doc-review edit (verify-only).
- **Target-conditional Step-0 ceremonies.** gstack's 0C-bis (implementation alternatives) + 0E (HOUR-by-HOUR temporal interrogation) are plan-specific and incoherent on a strategy/scope-question, so they are **conditional on target type** (plan → run both; strategy/brainstorm/scope-question → skip/recast). 0A/0B/0C/0F generalize and always run.
- **No saga write.** founder-review runs upstream/pre-saga and its output is a scope decision, not a readiness/code-review artifact — `saga.py`'s `review_paths` is the wrong home and the "if saga exists" guard would skip ~always. Cross-session persistence = the `docs/founder-reviews/` artifact + the journal ADR. founder-review is NOT a saga review-track consumer.
- **`docs/founder-reviews/` scope-decision dir.** Its own dir (the office-hours/code-review precedent), but the rationale is a scope decision captured for `/plan`/`/strategy` + a journal ADR — deliberately separate from the readiness-review (`docs/reviews/`) and code-review (`docs/code-reviews/`) tracks, and intentionally NOT a `/handoff` artifact source.
- **Office-hours mid-session escape.** Ported as a prose offer in 0A (vague/unframed session → offer `/office-hours`, re-read `docs/office-hours/` notes on return). The gstack `{{INVOKE_SKILL:office-hours}}` inline hack is shed; the detection+offer behavior is kept.

**Rejected alternatives.**
- *Port all 11 deep-rigor sections.* REJECTED — duplicates `/doc-review` + `/code-review`; infiquetra splits the review lenses, so founder-review owns the scope layer and routes deep rigor (closed loop) rather than reproducing the section machinery.
- *Hand-wave the routing ("recommend /doc-review" with no artifact).* REJECTED — the rigor evaporates; gstack bundled all 11 sections precisely to re-rigor expanded scope in-session, so the routing must be a real artifact handback (expanded-plan path → `/doc-review`).
- *Write a saga (append `review_paths`).* REJECTED — dead wiring (the guard skips ~always upstream of the work thread) + wrong field; founder-review is not a saga review-track consumer.
- *Trim the 4 scope modes to 2-3.* REJECTED — re-opens the thin-reskin gap; the 4 modes are the engine's spine, each distinct and pre-traction-relevant.
- *Build `/pulse` now (or fold the analytics artifact in).* REJECTED — premature; Infiquetra is pre-revenue greenfield with no telemetry. Steal the posture, QUEUE the component.
- *Run 0C-bis/0E unconditionally.* REJECTED — they are plan-specific and break on a strategy/scope target; made target-conditional instead.

**Rationale.** gstack `plan-ceo-review` IS the engine for this lens — the 4 committed scope modes + internalized CEO cognition + grounded pre-review audit are the whole point, and there is no CE counterpart engine (CE `product-pulse` is a different artifact — a live-telemetry report). So this is a faithful port + a single posture steal, not a merge. Splitting the review lenses (doc/code/founder) is what lets founder-review own the scope layer and route deep rigor in a closed loop rather than re-implementing 11 sections that already live in its sibling engines. The no-saga-write, scope-decision-dir, and target-conditional ceremonies keep the engine coherent for its actual upstream-of-execution position.

**Revisit when.** A real mid-work-thread founder-review need emerges (revisit no-saga-write); Infiquetra reaches a live product with real telemetry (build the queued `/pulse` and revisit whether founder-review should consume it); the closed-loop handback to `/doc-review`/`/code-review` proves awkward on real expansions; or `/strategy` and founder-review's boundary blurs in practice.

**Refs.** Plugin `0.9.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Sibling review-lens rebuild: [#code-review-engine-rebuild](#code-review-engine-rebuild). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Ship record: ARCHIVE [#founder-review-engine-rebuild-shipped](ARCHIVE.md#founder-review-engine-rebuild-shipped). Queued `/pulse` component: QUEUED [#pulse-live-telemetry-component](QUEUED.md#pulse-live-telemetry-component). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. Shipped via PR #179 (squash e4eedf2).

### Rebuild `/code-review` by merging CE `ce-code-review` spine + gstack `/review` scope/plan audit (PR #177, squash 0a9d8cd)  {#code-review-engine-rebuild}

**Decision.** Rebuild `/code-review` — the third command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`) — from a 20-line stub into a **self-contained infiquetra pre-PR review engine that merges CE's `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories**. Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) → review fan-out → merge + validate → report + route + saga. Position in the lifecycle: `/code-review` is a **within-work gate at the work→PR boundary** (after `/work` produces code, before PR/merge) — it is a code-quality review LENS, a sibling of `/doc-review` and `/founder-review`, but NOT the saga `LIFECYCLE_PHASES` `review` slot (that slot is `/doc-review`'s plan→work gate). The four interview answers settled with Jeff:

- **(Q1) Lens model: CE judgment-based lenses, lean infiquetra set — NOT gstack fixed specialists.** The orchestrator reads the diff and spawns only lenses with real work (CE model, matching `/doc-review`'s triggered-lenses pattern). Always-on (4): correctness, security, testing, maintainability/conventions. Conditional-by-judgment: a **distinct deploy/migration-verification lens** (NOT folded away — its own DynamoDB/IaC/Ansible checklist), plus reliability, performance, api-contract, adversarial/red-team, agent-native, previous-comments. Rails/Swift/Stimulus reviewers dropped. gstack's high-signal checklist categories (enum-completeness-reads-OUTSIDE-the-diff, LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the correctness/security lens checklists.
- **(Q2) Fix behavior: gate-only; adopt the full schema as routing metadata.** Adopt CE's full findings schema NOW (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` / `pre_existing` / `evidence`) so findings are agent-consumable — but `/code-review` itself reports + classifies + routes; it never mutates code, commits, pushes, opens PRs, or files SDLC issues. Fixer dispatch (review-fixer agent / `/work` / team-execution) is OFFERED via operator-choice; the safe-autofix *apply* mode is a later add. The programmatic mode (for `/work`'s future call) is **zero-write to reviewed code** — built from CE's `report-only` BEHAVIOR + `headless` ENVELOPE, deliberately NOT CE's mutating `headless` behavior.
- **(Q3) Validator pass: keep, right-sized by MODE (not severity).** Run CE's independent per-finding validator (a fresh agent re-checks each survivor: real in code? introduced by THIS diff? handled elsewhere? → `{validated, reason}`). Right-sizing is **mode-based** (CE's actual mechanism): programmatic/headless → validate all Stage-A survivors (capped 15, ordered P0→P3, failure → drop); interactive → the operator is the per-finding validator (skip the pre-dispatch pass). The cost control is the upstream suppress-<75 confidence gate + the 15-cap, NOT a severity carve-out.
- **(Q4) Fan-out + saga: all three backends + journal audit + saga review-track (append-only, never mint).** Offer `inline` / `team-execution` / `cc-workflows-ultracode` for the lens fan-out + validator pass, cited at the plugin-root path (`../../references/operator-choice.md`). The plan-completion audit reads the `docs/plans/` artifact + the journal (built-vs-planned, faithful to both engines). `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread saga (found via `saga.py scan`): append the artifact path to `review_paths` + record the backend in `orchestration_mode`, preserving `lifecycle_phase` (code-review does NOT advance the phase). If no saga exists → skip the saga write, never mint, never invent `--kind/--id`.

**Key design points.**
- **Gate-only boundary.** code-review reviews + classifies + routes; it does NOT implement fixes, commit/push/PR, or file SDLC issues — the same lifecycle boundary `/plan` enforces. The programmatic mode carries an explicit "ZERO file writes to reviewed code" rule.
- **Saga append-only, never mint.** `saga.py save` mints unconditionally, so the never-mint guard lives in SKILL prose (scan-first; append to the found saga's exact `--kind` + `--id`; preserve `lifecycle_phase`; skip if absent) + a negative smoke test. No `saga.py` changes (fields/flags already exist).
- **Own-dir `docs/code-reviews/`.** Durable artifacts get their own dir (NOT `docs/reviews/`) to avoid the `handoff_envelope.py` / `sdlc_manager.py` "any file in `docs/reviews/` → plan-ready" classifier misclassification — the office-hours-dir precedent.
- **Scope-drift is informational.** gstack scope-drift produces findings but does not itself block; infiquetra keeps it informational — the normal P0/P1 findings gate is what blocks the PR.
- **Lens-as-judgment lean set with a distinct deploy/migration lens.** The lens set is judgment-selected and lean, but the deploy/migration-verification lens and the reliability lens are kept distinct (sub-domains enumerated in `lens-catalog.md`) so no lens ships as a one-liner.

**Rejected alternatives.**
- *gstack fixed-specialist list with scope gates.* REJECTED — re-opens "spawn reviewers that find nothing on this diff"; CE's judgment-based selection matches `/doc-review` and the agent-team philosophy.
- *Safe-autofix-now (apply fixes in this rebuild).* REJECTED — blurs the gate/work boundary; the apply mode is a future add, fixer dispatch is offered not auto-run.
- *Drop the validator (trust first-pass confidence).* REJECTED — re-opens false positives; a review that cries wolf is worse than none (Jeff's no-lies rule).
- *Severity-carved validator (trust anchor for P2/P3).* REJECTED — a no-op after the suppress-<75 gate already removed low-confidence findings, AND falsely attributed to CE (which has no severity-based validator exemption); mode-based right-sizing is CE's actual mechanism.
- *Saga mint-on-absent.* REJECTED — would create phantom sagas with invented `--kind/--id`; append-only never-mint with a negative smoke test instead.
- *`docs/reviews/`-shared artifact dir.* REJECTED — collides with the `handoff_envelope.py` / `sdlc_manager.py` plan-ready classifier predicate; own `docs/code-reviews/` dir instead.
- *Folded operational lens (deploy-verify folded into a generic lens).* REJECTED — loses deploy-verify specificity; the deploy/migration-verification lens stays distinct.

**Rationale.** CE's `ce-code-review` is the strongest findings/validator engine of either source (rich agent-consumable schema, independent per-finding re-verification, judgment-based lens selection); gstack `/review` contributes the scope-drift + plan-completion audit + high-signal checklist army CE lacks. Merging the two — CE's spine + gstack's audit/checklist — gives an infiquetra-owned review engine that is agent-consumable, grounded in the plan + journal, and honest (verify-don't-guess), without inheriting either source's runtime boilerplate or auto-apply behavior. Gate-only keeps it inside the lifecycle's review-not-execute boundary; the saga append-only wiring makes it the first review-track consumer without re-minting the work thread `/work` owns.

**Revisit when.** A real PR run shows the gate-only stance is too passive and the safe-autofix *apply* mode earns its weight (add the apply mode behind operator-choice); the mode-based validator cap (15) proves too tight or too loose on real diffs; the `/work` rebuild lands and wants code-review to mint/advance the saga rather than append-only (revisit the never-mint guard); or the distinct deploy/migration lens proves redundant with a rebuilt `/qa`.

**Refs.** Plugin `0.8.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Builds on the `/plan` rebuild [#plan-engine-rebuild](#plan-engine-rebuild), the operator-choice contract [#operator-choice-framework](#operator-choice-framework), and the saga foundation [#saga-schema-foundation](#saga-schema-foundation). Ship record: ARCHIVE [#code-review-engine-rebuild-shipped](ARCHIVE.md#code-review-engine-rebuild-shipped). `/work` forward-coupling (now closed — `/work` is saga's primary writer): DECISIONS [#work-engine-rebuild](#work-engine-rebuild), ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped). Shipped via PR #177 (squash 0a9d8cd).

## 2026-06-02

### Rebuild `/plan` by merging CE `ce-plan` artifact engine + gstack `spec` HOW-interrogation (PR #175, squash a13ba68)  {#plan-engine-rebuild}

**Decision.** Rebuild `/plan` — the second command rebuild of the engine-merge campaign — from a 27-line stub into a **self-contained infiquetra plan engine that merges CE's `ce-plan` structured-artifact engine (Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end**. Six numbered phases: enter + warranted-gate → ground (HOW) → interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route + operator-choice. Position in the lifecycle: `/plan` answers **"How should it be built?"** (the WHAT is assumed settled upstream). The four interview answers settled:

- **(Q1) Adopt CE's full artifact skeleton + right-size it.** Take CE's R-ID/KTD/U-ID + per-unit test-scenario shape wholesale (the canonical plan shape, three-audience: human + agent + `/work` consumer), but right-size the engine to infiquetra rather than porting CE's heaviest machinery verbatim — concretely, a CONDENSED deepening pass rather than CE's full 248-line deepening.
- **(Q2) HOW-only interrogation; assume the WHAT upstream.** `/plan` interrogates *how to build it*, grounding in code (cite `path:line`) before asking. It does NOT re-litigate requirements/scope — that's `/ideate` → `/brainstorm` → `/office-hours` territory. Open WHAT-ambiguity triggers a **one-way bounce**: recommend the operator run `/brainstorm` first (with an explicit guard: do NOT claim `/brainstorm` "accepts" a handoff).
- **(Q3) One plan saga via the CLI; epic split → sdlc-manager.** `/plan` emits a single durable **plan saga** via `scripts/saga.py save --lifecycle-phase plan` (runnable, with a hard "never `git add` the tick" boundary). It does NOT mint per-U-ID sagas; multi-unit/epic splits hand to `sdlc-manager`.
- **(Q4) All three backends via the operator-choice doc.** Offer `inline` | `team-execution` | `cc-workflows-ultracode`, cited by path (`references/operator-choice.md`), offered not defaulted — implements the shipped operator-choice contract.

**Key design points.**
- **Review-phase rationale (the gauntlet is NOT dropped).** The full review gauntlet — `/doc-review` + `/code-review` + `/founder-review` — IS the `review` phase, a separate lifecycle stage. `/plan` keeps a CONDENSED deepening self-review and **routes to `/doc-review` (the recommended next exit) before `/work`**. Folding the gauntlet into `/plan` would break the phase model.
- **Doc-frontmatter vs saga-tick split.** The durable plan doc carries human-facing frontmatter (`title`/`type`/`status`/`date`/`origin`) plus the artifact markers (`Implementation Units` / `Key Technical Decisions` / `U1`) so `/doc-review` recognizes it; the machine work-state (lifecycle phase, destination, ADR/KTD refs, orchestration mode) lives in the saga tick. Two surfaces, deliberately not conflated.
- **One-way `/plan`→`/brainstorm` route.** The bounce is a recommendation only, in one direction; `/plan` never claims a handoff contract on the brainstorm side.

**Rejected alternatives.**
- *Lighter agent-consumable variant (thin reskin of the stub).* REJECTED — the stub is exactly the thin-reskin disease the campaign exists to cure; the artifact skeleton is what makes a plan traceable + agent-consumable.
- *Full gstack interrogation in `/plan`.* REJECTED — gstack `spec`'s five-Why + scope/MVP/failure-mode lock is WHAT-rigor that duplicates `/brainstorm`; `/plan` takes only the HOW-interrogation + code-grounding front end. (Seam between the two left as a queued decision-point — see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).)
- *Per-U-ID sagas.* REJECTED — over-reach; one plan saga is the durable record, the U-IDs are slices inside it, and epic splitting belongs to `sdlc-manager`.
- *Defer the saga (plan writes a doc only).* REJECTED — contradicts the saga foundation's §11 consumer contract; `/plan` is a saga consumer and emits one plan saga.
- *Run the full review gauntlet inside `/plan`.* REJECTED — breaks the phase model; the gauntlet is the `review` phase, `/plan` only does a condensed self-review + routes to `/doc-review`.
- *CE's full 248-line deepening pass.* REJECTED — over-heavy for infiquetra; ship a condensed confidence pass instead.

**Rationale.** CE's `ce-plan` is the strongest artifact engine of either source (stable IDs, traceability, per-unit test scenarios, three-audience, already agent-consumable); gstack `spec` contributes the code-grounded interrogation discipline CE lacks at the front. Merging the two — taking CE's skeleton wholesale and grafting gstack's HOW-interrogation — gives an infiquetra-owned plan engine that is traceable, agent-runnable, and grounded, without inheriting either source's runtime boilerplate or duplicating the WHAT-rigor that lives upstream. Right-sizing (condensed deepening, one saga, HOW-only) keeps it proportional to a 1-human + agents shop.

**Revisit when.** A real multi-PR epic shows the one-plan-saga + sdlc-manager epic-split seam is awkward (revisit per-slice saga emission); the `/brainstorm` ↔ `spec` interrogation seam gets resolved and changes where HOW vs WHAT interrogation lives (see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam)); or the condensed deepening pass proves too thin and CE's fuller confidence pass earns its weight.

**Refs.** Plugin `0.7.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#plan-engine-rebuild-shipped](ARCHIVE.md#plan-engine-rebuild-shipped). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Saga foundation: [#saga-schema-foundation](#saga-schema-foundation). Interrogation seam: QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).

### Rebuild `/office-hours` as a faithful two-mode gstack port adapted to infiquetra (PR `#173`, squash `aec888c`)  {#office-hours-engine-rebuild}

**Decision.** Rebuild `/office-hours` — the first command rebuild of the engine-merge campaign — as a **faithful two-mode gstack diagnostic port**, adapted to infiquetra and merged with the CE boundary contract (front-door framing + the `/ideate`↔`/brainstorm` handshake). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE. It is the Think-phase **frame-finding front door** — `/ideate` routes unframed asks here; `/brainstorm` bounces open thought-partner work back. The four interview answers settled:

- **(Q1) KEEP both modes** — Startup mode + Builder mode, not collapsed to one diagnostic. **Jeff override:** Infiquetra is a real startup heading toward paying customers, currently pre-revenue greenfield, so the startup forcing-questions earn their place.
- **(Q2) Route always / frame-note optional** — every session closes by naming a next command; writing a frame note is optional.
- **(Q3) Re-target pushback** — hard on vagueness and ungrounded assumptions, **not** on the operator's judgment; push-twice with escape hatches.
- **(Q4) Frame-finding only + plural exits** — stop the moment you can name the problem and a route; clean exits to `/brainstorm`, `/plan`, `/strategy`. HARD GATE (absolute): never implement, plan, or file an SDLC issue.

**Key adaptations.**
- **Stage-aware startup mode** with a **PRE-TRACTION hypothesis-forming register** — a pre-revenue greenfield operator gets hypothesis-forming questions, not an evidence-audit of customers/traction that don't exist yet.
- **Builder-mode DEPTH FLOOR** — Builder mode is infiquetra's high-frequency mode (infra/workflow/internal-tooling), so it carries real discovery/shaping rigor, not a one-liner.
- **Mid-session mode-switch** — startup↔builder can flip within a session.
- **Frame note in its OWN `docs/office-hours/` dir** (frontmatter `kind: frame-note`), NOT `docs/ideation/` — avoids colliding with the `/ideate` resume-scan (`skills/ideate/SKILL.md:56`).

**Rejected alternatives.**
- *Collapse to one "is the frame settled?" diagnostic.* REJECTED — a review recommended it, **OVERRIDDEN** because Infiquetra is a real startup heading to paying customers; the startup forcing-questions matter.
- *Frame note under `docs/ideation/`.* REJECTED — resume collision with the `/ideate` resume scan (`skills/ideate/SKILL.md:56`); the frame note gets its own `docs/office-hours/` home.
- *Thin builder mode (one-liner).* REJECTED — Builder mode is the high-frequency path and must carry depth.
- *Literal evidence-audit startup questions for a pre-traction operator.* REJECTED — wrong register for pre-revenue greenfield; ported stage-aware to hypothesis-forming instead.

**Rationale.** Faithful gstack port keeps the engine that makes the front door repeatable, shedding gstack's runtime boilerplate per the campaign's port model. The two-mode split survives because infiquetra is genuinely both a startup and a builder shop; the stage-aware + depth-floor adaptations make each mode fit the actual operator rather than a generic YC founder or a throwaway builder check.

**Revisit when.** Infiquetra reaches PMF (revisit the pre-traction register — startup questions can shift back toward evidence-audit); `/investigate` + `/spec` ship (add them as routes).

**Refs.** Plugin `0.6.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#office-hours-engine-rebuild-shipped](ARCHIVE.md#office-hours-engine-rebuild-shipped). Frame-note home: `docs/office-hours/`.

### Operator-choice framework ships doc-only; CLI helper deferred to `/work` (PR `#171`)  {#operator-choice-framework}

> **Update (2026-06-13).** The §3.2 "deterministic fan-out, not review depth" framing introduced here was
> corrected, and `adversarial_confidence` + `has_code_surface` were added to the recommender — see
> [#operator-choice-docs-and-confidence](#operator-choice-docs-and-confidence). The doc-only-then-helper
> sequencing, the three-backend enum, and the always-confirm/capability-gate properties below all stand.

**Decision.** Ship the operator-choice framework as a **DOC-ONLY foundation**: `references/operator-choice.md` — the decision contract for the three execution backends `inline` | `team-execution` | `cc-workflows-ultracode` (these enum strings are the contract; prose labels like "CC workflows"/"ultracode" are not) — plus short prose **offer hooks** in `/loop` and `/work`. Lifecycle owns the **choice**, not execution. No code/helper ships this PR. The four interview answers settled:

- **(a) Who decides** — auto-recommend + **always confirm**. Inline-by-default; escalation is cheap. The agent proposes a backend; the operator confirms.
- **(b) Triggers** — `team-execution` when any `should_offer_team_execution` constant trips (`file_count>=8`, `phase_count>=4`, `has_security`, `has_infra`, `cross_repo`, `deployment_sensitive`) **or** the work needs reviewer consensus; `cc-workflows-ultracode` for broad-independent-parallel-fan-out / exhaustive-sweep work (Claude-Code-only). On **OVERLAP, offer BOTH** — no hard precedence rule.
- **(c) Capability gate** — document all three backends always; **hide** the ultracode option only when the Workflow tool is observably absent; **always graceful-fallback** at execution time.
- **(d) Scope** — `/loop` and `/work` only this PR. The other command rebuilds wire their own offers as they land.

**Rejected alternatives.**
- *Add a library-only `recommend_execution_backend()` helper now.* REJECTED — skills are markdown the agent reads, so a Python helper with no caller would be uncallable and would drift against the doc. This is the verified state of the existing `should_offer_team_execution` (defined in `lifecycle_state.py` but never called outside its own test). The CLI-backed helper is **DEFERRED to the `/work` rebuild**, where it gets a real caller.
- *Silent auto-pick.* REJECTED — violates always-confirm; the operator must see and accept the escalation.
- *Show-but-disable the ultracode option when unavailable.* REJECTED — hide it instead (cleaner; capability is observable).
- *Wire all lifecycle commands now.* REJECTED — scope is `/loop` + `/work`; the rest cite the doc as they rebuild.
- *A hard "risk dominates fan-out" precedence rule on overlap.* REJECTED — cosmetic given always-confirm; offering BOTH lets the operator decide.
- *Copy the brainstorm channel-inline wording verbatim.* REJECTED — reference `skills/brainstorm/SKILL.md`'s canonical channel-inline convention (redis-channel sessions cannot call AskUserQuestion) instead of duplicating it.

**Rationale.** Matches the queue's "no scripts" sizing — one shared reference doc + 2-3 line offer hooks. The doc is the consumed source of truth (the decision contract, complementing `saga-spec.md`'s storage contract). An honest unconsumed-style foundation in the same spirit as the saga ship: settle the contract before consumers calcify it.

**Revisit when.** The `/work` rebuild — wire the CLI-backed execution-backend helper against this doc (or decide the prose offer suffices and no helper is needed).

**Refs.** Plugin `0.5.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Decision contract: `plugins/saga/references/operator-choice.md`; complements storage contract `references/saga-spec.md`. Ship record: ARCHIVE [#operator-choice-framework-shipped](ARCHIVE.md#operator-choice-framework-shipped). Channel-inline convention: `plugins/saga/skills/brainstorm/SKILL.md`. Shipped via PR `#171` (squash `e935bd4`).

### Saga schema: derived `kind-id` identity + append-only envelope log + three-axis state (PR `#170`)  {#saga-schema-foundation}

**Decision.** Define `saga` — the durable, resumable work-state envelope — as the first foundation of the engine-merge campaign, with this schema:

- **Identity: derived `kind-id`** (`issue-<N>` / `task-<slug>`), minted at birth and **sticky**. `round` and `phase` are *fields*, not identity. A task-saga that later gets an issue keeps its id and gains an `issue_ref` (the index cross-references `issue_ref → saga_id` so it stays findable by issue#). Human-legible dirs (`sagas/issue-42/`), deterministic, backward-compatible with the old `{kind}-{id}`.
- **Storage: append-only timestamped envelope log (canonical) + derived `state.json` index (rebuildable).** Each tick is an immutable file `sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`; ordering is **always by filename string, never mtime** (same-second collision → `-1` suffix). The index is `{last_updated, active_saga_id, sagas:{...}, current_work:{…legacy fields…, saga_id}}`, written atomically (temp+rename); a corrupt index is never fatal because `scan` rebuilds from the log.
- **File format: gstack envelope** — YAML frontmatter (machine fields incl. `extra:` for unknown-key round-trip) + `## Summary` / `## Decisions` (KTDs) / `## Remaining` / `## Notes / Tried` body. Cold-resume reads from frontmatter; matches the shipped CE-artifact house style.
- **Three stored state axes, one derived:** `lifecycle_phase` (CE flow: `ideation|brainstorm|plan|review|work|qa|retro`), `phase_status` (`pending|in_progress|complete`; authoritative, drives `next_phase` = phase+1 if complete else phase), `status` (thread disposition: `active|blocked|paused|handed-off|done|abandoned`; MUST NOT take `pending`/`in_progress`). **`maturity` is derived at `/handoff` time** from `lifecycle_phase` (the existing `infer_maturity` mapping), not stored.
- **List merge: full-snapshot semantics** — a tick's lists replace; absent carries forward; empty clears. Not union.
- **Full unify now:** one `saga.py` engine (`save`/`restore`/`scan`/`context`) with the 3 legacy scripts refactored into thin wrappers.
- **Spec home: plugin-level** `plugins/saga/references/saga-spec.md` (a new convention — no plugin-level `references/` existed before); each consuming SKILL links to it.

**Rejected alternatives.**
- *Minted opaque saga-id (UUID/counter).* Rejected: not human-legible, not deterministic, requires a lookup to resume issue-born work. Derived `kind-id` is self-describing and backward-compatible.
- *Engine-only, migrate the storage format later (PR1 engine+wrappers / PR2 format).* Considered as a de-risk fallback; rejected for this ship in favor of one PR — the user chose "full unify now," and characterize-first tests make the format migration safe in a single change.
- *mtime ordering.* Rejected: mtime is not stable across rsync/backup/snapshot-restore; filename-as-order is deterministic and copy-safe. (Note: the win is for rsync/backup, NOT git worktrees — those don't carry git-ignored state at all.)
- *Union list merge.* Rejected: union-only lists accumulate stale `open_questions`/files and mislead cold resume; gstack ticks are full snapshots, so resume payloads must be able to shrink.
- *Stored `maturity` axis.* Rejected: redundant with `lifecycle_phase`; deriving it at `/handoff` removes a constant axis and the `status`↔`phase_status` ambiguity.
- *Round/phase in the identity.* Rejected: would re-mint a saga id every round, breaking sticky resume; round and phase are mutable fields of a single sticky-id thread.

**Rationale.** Saga is **gstack-dominant** (CE has no saga primitive — single-session assumption — so only its artifact-discipline framing is borrowed): gstack supplies the envelope mechanics (frontmatter+body, filename-as-order, branch-agnostic restore); the payload richness (issue+PR rounds, journal/ADR linkage) is lifecycle's own scripts; CE's contribution is the implied flow recorded in `lifecycle_phase`. Settling the contract semantics (axes, snapshot lists, `current_work`) in the spec **before** consumers calcify them is the whole point of building this foundation first. This ships an **unconsumed primitive** — after this PR no command calls `restore`/`scan`; the 3 legacy CLIs keep working as wrappers and the engine is validated by its own unit tests + manual smoke. Consumer wiring (`/work`, `/resume`, `/loop`, `/plan`) is each consumer's own queued item.

**Revisit when.** A consumer rebuild surfaces a missing/awkward field or enum (extend via `schema_version` + the `extra:` preserve-unknown seam, not a breaking change); append-only growth needs a GC policy (the spec leaves a `max_ticks` seam); or a second identity collision pattern emerges that the derived-id guards don't cover.

**Refs.** Plugin `0.4.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Spec: `plugins/saga/references/saga-spec.md`. Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. ARCHIVE [saga foundation shipped](ARCHIVE.md#saga-foundation-shipped) — consumers remain queued in [QUEUED.md](QUEUED.md).

### Rebuild lifecycle commands by merging gstack + CE engines into self-contained infiquetra engines (commit pending)  {#lifecycle-engine-merge-campaign}

**Decision.** Rebuild each diverged `infiquetra-lifecycle` command — and adopt two missing ones (`/investigate`, `/spec`) — by **merging the best of compound-engineering (CE) and gstack into a new, self-contained infiquetra engine**, worked **1-by-1 via an interview-driven merge**. Port model = the shipped `/ideate` rebuild: extract the engine, adapt to infiquetra (1-human + multi-agent team; `sdlc-manager` owns SDLC issues/boards/readiness; `infiquetra-deploy` owns deploy; the engineering journal; context-libraries), and shed gstack's ~780-line runtime boilerplate **with Jeff's per-item sign-off**. Neither source has priority — Jeff leans CE. Build two foundations first: a first-class `saga` durable/resumable work-state envelope (P0) and a shared inline / team-execution / Claude-Code-workflows operator-choice framework (P1), because the command rebuilds read them. Full per-command queue: [QUEUED.md](QUEUED.md) engine-merge initiative.

**Rejected alternatives.**
- *Adopt one upstream wholesale (just gstack, or just CE).* Rejected — Jeff: "otherwise I would just use one or the other and forget about all this." The value is a merged engine infiquetra owns and evolves, taking bits of both.
- *Vendor gstack / runtime-depend on CE.* Rejected — same standalone-boundary rationale as the `/ideate` ADR ([#ce-ideation-engine-restore](#ce-ideation-engine-restore)); gstack also carries ~780 lines of runtime plumbing (telemetry, gbrain, `~/.gstack`, model overlays) irrelevant to infiquetra.
- *Leave the thin stubs.* Rejected — they bias toward facilitation; the engine is what makes a command repeatable. See LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic).
- *Auto-shed gstack boilerplate without review.* Rejected — Jeff wants input on what's shed; each rebuild surfaces shed candidates for sign-off.

**Rationale.** CE and gstack each have engine mechanics worth keeping (CE: structured artifacts, causal-chain debugging, persona/findings/validator review; gstack: scope-mode reviews, risk-gated QA, multi-specialist fan-out, save/restore checkpoints). Merging the best of both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained, evolvable, and adapted to a 1-human + agents shop where artifacts must be agent-consumable. Worked 1-by-1 so each merge is a deliberate, interview-settled design, not a bulk port that would re-introduce the stub-disease at engine level.

**Revisit when.** A command's interview shows the merged engine is more than infiquetra needs (ship a lighter version), or CE/gstack ship a materially better engine worth re-syncing, or the parallel-fork maintenance cost exceeds the value of self-containment.

**Refs.** QUEUED engine-merge initiative; LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic), [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget), [#stub-port-drops-engine](LEARNINGS.md#stub-port-drops-engine); DECISIONS [#ce-ideation-engine-restore](#ce-ideation-engine-restore), [#sdlc-handoff-ownership-boundary](#sdlc-handoff-ownership-boundary).

## 2026-06-01

### Restore the CE ideation engine into `/ideate` + `/brainstorm`, self-contained (commit `30c9099`)  {#ce-ideation-engine-restore}

**Decision.** Rebuild `infiquetra-lifecycle`'s `/ideate` and `/brainstorm` from thin facilitative
stubs into full divergent→convergent engines ported from compound-engineering (CE) and adapted to the
infiquetra world — self-contained, no runtime dependency on CE. `/ideate` generates many candidates
across parallel frame agents, critiques all, and presents only survivors; cut ideas stay revivable.
Two deliberate improvements over CE: (1) a two-way partnership — operator seeds feed *into* the frame
agents and face the same critique; (2) a revival state machine that re-enters the filter with new
evidence (and adjudicates novelty) so revival cannot soft-promote a categorically-cut idea. Added
infiquetra grounding CE never had: context-library reader (`*-context-library` via `gh`), named-repo
reader, grounding-fit gate, read-only `gh` issue-theme clustering. Dropped CE's Proof/HITL,
HTML/output-mode, elsewhere/non-software modes, Slack, and web-research-cache.

**Rejected alternatives.**
- *Delegate to CE at runtime (load `ce-ideate` when present).* Rejected: couples lifecycle to CE
  being installed at a compatible version and drags in CE's ecosystem (Proof, modes, conventions);
  contradicts the plugin's standalone Boundaries.
- *Keep the thin facilitative stubs.* Rejected: "produce a small option set; lead the user through
  choices" biases toward facilitation, which is why ideation felt like the operator supplied all the
  ideas. See LEARNINGS `{#stub-port-drops-engine}`.
- *Issue themes via `sdlc-manager`.* Rejected: `sdlc-manager` has no theme-clustering and issue
  *reads* are not its boundary (it owns mutation). `/ideate` reads issues read-only via `gh` and
  clusters them itself.

**Rationale.** The operator wanted CE's generative engine + survivors back, plus a genuine
partnership where their ideas also enter the pool and rejected ideas are revivable. Self-contained
keeps the plugin's ownership boundaries clean. Forked from CE 3.9.2; authored and adversarially
verified via an ultracode workflow (13 agents; 5 major findings remediated, 0 blocking).

**Revisit when.** CE ships a materially better ideation engine worth re-syncing, or the parallel-fork
maintenance cost exceeds the value of staying self-contained.

**Refs.** Plugin `0.3.0`, marketplace metadata `2.4.0`. LEARNINGS `{#stub-port-drops-engine}`. Plan
`.claude/plans/can-you-review-the-inherited-lantern.md`.

## 2026-05-31

### Rename `infiquetra-loop` → `infiquetra-lifecycle` (commit `0ed70f2`)  {#rename-loop-to-lifecycle}

**Decision.** Rename the plugin to `infiquetra-lifecycle`. "Loop" named only the `/loop` router
command, not the idea-to-ship lifecycle the plugin actually spans (Think → Plan & execute → Hand
off → Review → Improve & route). Renamed the ignored runtime-state dir to
`.claude/infiquetra-lifecycle/` and the handoff-envelope field `loop_owner` → `lifecycle_owner`,
with `sdlc-manager` updated in lockstep (its 4 hardcoded state-path references). Kept the `/loop`
command name unchanged — it's one verb in the lifecycle, not the whole thing. Surfaced the
five-phase command grouping in the plugin description, both READMEs, and the changelog so users see
the categorization.

**Rejected alternatives.**
- *`infiquetra-flow`.* Rejected: still reads too close to "loop" and is vaguer about scope.
- *`infiquetra-sdlc`.* Rejected: collides conceptually with the existing `sdlc-manager` plugin,
  blurring the boundary (lifecycle workflow vs GitHub issue/board ownership).
- *`infiquetra-cadence` / `-forge` / `-workbench`.* Rejected: evocative but less self-describing
  than "lifecycle".
- *Rewrite the old name in dated historical docs (brainstorms, ideation, plans, reviews,
  work-sessions, `ARCHIVE.md`).* Rejected per the journal rule "never silently overwrite history" —
  those artifacts record what the plugin was called at the time.

**Rationale.** The name should describe what the plugin does to a first-time user. "Lifecycle"
matches the description and command taxonomy; "loop" undersold it.

**Revisit when.** The plugin's scope narrows back to pure routing/iteration, or a clearer
single-word name for "full engineering lifecycle" emerges.

**Refs.** Plugin `0.2.0`, `sdlc-manager` `1.6.1`, marketplace metadata `2.3.0`.

### SDLC handoff issue artifacts belong to `sdlc-manager` (commit `2fc317e`)  {#sdlc-handoff-ownership-boundary}

**Decision.** Put handoff issue drafting, source artifact resolution, handoff maturity metadata,
prepared-draft sidecars, mutation plans, labels, board placement, and create-after-confirmation in
`sdlc-manager`. Keep `infiquetra-loop` responsible for lifecycle context and future `/handoff`
routing only.

**Rejected alternatives.**
- *Generate handoff issue bodies inside `infiquetra-loop`.* Rejected: it would duplicate SDLC
  issue semantics and make two plugins responsible for labels, project fields, and readiness.
- *Add a separate handoff artifact format.* Rejected: prepared issue drafts already provide the
  markdown plus JSON sidecar boundary needed for review before mutation.
- *Require recipient teams to have `infiquetra-loop` installed.* Rejected: handoff issues must be
  self-contained for agent teams or humans working only from GitHub.

**Rationale.** This keeps the lifecycle plugin thin at the exit point while centralizing SDLC
mutation rules in the plugin that already owns issue readiness. The prepared draft remains useful
without mutation, and `issue create-prepared` remains the single place where side effects are
rendered and confirmed.

**Revisit when.** Multiple non-SDLC destinations need the same handoff source resolver, or
`infiquetra-loop` grows durable lifecycle state that cannot be represented cleanly in the
prepared issue sidecar.

**Refs.** Plan [Add SDLC handoff flow](../plans/2026-05-30-002-feat-sdlc-handoff-flow-plan.md);
requirements [Infiquetra Loop SDLC Handoff](../brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md).

### Prepared issue workflow uses draft/sidecar boundary plus confirmed mutation (commit `74cd372`)  {#prepared-issue-workflow-boundary}

**Decision.** Add `sdlc-manager issue prepare` and `issue create-prepared` as separate steps.
`issue prepare` writes a markdown draft and JSON sidecar; `issue create-prepared` re-runs
readiness, renders a mutation plan, asks for confirmation, repairs repo prerequisites, handles
mapping PRs, creates the issue, and records the result back onto the draft.

**Rejected alternatives.**
- *Direct source-text to `gh issue create`.* Rejected: bypasses review and makes readiness failures
  visible only after the external issue exists.
- *Put LLM interpretation inside `sdlc_manager.py`.* Rejected: the CLI should stay deterministic;
  skills and agents own rough-source interpretation.
- *Create new issue types for Asgard/Olympus.* Rejected: the six SDLC issue types remain
  canonical; team differences belong in readiness profiles and board/status routing.

**Rationale.** The split gives operators a durable review point before GitHub mutation while still
letting the final create flow perform repo repair and board placement as one visible plan.
Sidecars keep deterministic metadata and lifecycle state out of prose-only markdown, and
re-validation prevents stale edited drafts from bypassing team readiness.

**Revisit when.** Multiple non-agent callers need deterministic text-to-body generation inside the
CLI, or when prepared drafts become common enough to justify a richer review UI or batch create
surface.

**Refs.** LEARNINGS [prepared issue artifact boundary](LEARNINGS.md#prepared-issue-artifact-boundary).

## 2026-05-29

### Split Infiquetra lifecycle orchestration from deployment mutation (commit pending)  {#infiquetra-loop-deploy-boundary}

**Decision.** Add `infiquetra-loop` as the daily lifecycle orchestration plugin and
`infiquetra-deploy` as a separate deployment plugin. `infiquetra-loop` owns office-hours,
strategy, ideation, brainstorm, planning, work execution, code review, optimization, QA, SDLC
issue progress, engineering-journal prompts, retro, and resume. `infiquetra-deploy` owns
tag-promotion deployment, status, release notes, rollback, and hotfix helpers. `team-execution`
remains independent and is offered only when risk, size, or parallelism justify the cost.

**Rejected alternatives.**
- *One merged super-plugin.* Rejected: deployment mutation has a higher blast radius than
  lifecycle coaching and should keep a hard operational boundary.
- *Copy Superpowers, Compound Engineering, gstack, and VECU workflows wholesale.* Rejected:
  the useful pieces need to be adapted to Infiquetra docs, SDLC, and context-library references;
  generic cleanup, GitHub helper, and plugin-management utilities are intentionally out of scope.
- *Version raw loop state as repo artifacts.* Rejected: durable plans and work-session summaries
  belong in repo docs, but raw checkpoint state, API caches, validator JSON, and resume scratch
  are local session data and already covered by the `.claude/` ignore convention.

**Rationale.** The split lets the daily loop replace recurring Superpowers and Compound
Engineering lifecycle use while still enforcing a clear deployment safety boundary. Durable docs
give session-to-session continuity without committing stale runtime state. Keeping `team-execution`
separate preserves its validator and nonprod automation contract without forcing every loop to pay
that token or coordination cost.

**Revisit when.** Deployment policy moves out of tag-promotion, loop usage shows deployment
handoff friction dominates safety value, or `team-execution` becomes cheap enough to run by
default on normal work.

**Refs.** `plugins/infiquetra-loop/`, `plugins/deploy/`,
[team-execution v2 decision](#team-execution-v2-validators).

---

## 2026-05-27

### `team-execution` v2 uses context-selected validators and guarded nonprod automation (commit pending)  {#team-execution-v2-validators}

**Decision.** Evolve `team-execution` from reviewer-only orchestration into a reviewer plus
validator workflow. Validators are a maximum available roster, selected by repository context,
changed files, workflows, contracts, docs, tests, and optional `.team-execution.json`. Automation
is allowed only for `github.com/infiquetra/*`, only after gates pass, and only for nonprod or
publish-nonprod workflows.

**Rejected alternatives.**
- *Spawn every validator on every plan.* Rejected: creates noise, cost, and false blockers for
  validators unrelated to the change.
- *Let validators run before reviewer consensus.* Rejected: reviewer non-consensus means the
  implementation is still unstable; validator findings would be stale or duplicated.
- *Allow generic deployment automation once checks pass.* Rejected: production, staging, branch
  deletion, force-push, and credential changes carry a higher operational risk than this plugin
  should automate.

**Rationale.** Context selection keeps validator evidence proportional to risk while still making
the approved roster available. Gating validators after reviewer consensus creates a stable artifact
to scan and test. Nonprod-only automation gives useful end-to-end validation without turning a
planning plugin into a production deployment system.

**Revisit when.** We have repeated evidence that a validator category is always selected together
with another category and should be merged, or when production deployment safety is owned by a
separate audited release plugin.

**Refs.** LEARNINGS [team setup asset drift](LEARNINGS.md#team-setup-asset-drift).

---

## 2026-05-25

### `redis-channel` plugin: Hermes-agnostic Claude Code channel over Redis Streams (commit pending)  {#redis-bridge-decoupled}

**Decision.** Build the `redis-channel` plugin as a generic Claude Code channel that speaks a documented Redis-streams protocol — no Hermes-specific knowledge in the plugin. The Hermes-side counterpart (`hermes-claude-code-router`) lives in its own public GitHub repo so the protocol is reusable by any future consumer.

**Rejected alternatives.**
- *Embed Hermes/Discord logic directly into the plugin.* Rejected: would reimplement Discord voice-receive that already works (battle-tested) in `hermes-agent`. Verification confirmed the voice-receive code is **not** in `home-lab/asgard_voice_arbiter` (where the initial design assumed it lived) — the arbiter is routing-only; the sink/decode lives in closed-source `hermes-agent.gateway.platforms.discord`. Rebuilding would have been 3–5 days of unknown work.
- *Add the router as a 4th plugin inside `infiquetra/infiquetra-hermes-plugins`.* Considered seriously after `infiquetra-hermes-plugins` was identified as the canonical external-plugin pattern. Rejected per user preference for independent versioning. The router's expected LoC (~1k+) justifies its own home.
- *Use HTTP transport between plugin and router.* Rejected: Redis already runs on Mac mini for `voice_coordinator`; Streams give durable + ordered + consumer-group resume; no port-binding on either side; matches existing Hermes infra patterns.

**Rationale.** Decoupling means: (a) any future consumer (web UI, mobile app, CLI test harness) can drive a Claude Code session by speaking the protocol; (b) the plugin is testable without Hermes infrastructure; (c) protocol changes are version-gated, not implicit. The protocol spec (PROTOCOL.md) and pydantic models (`server/protocol.py`) are copied verbatim into both repos; synchronized PRs enforce drift detection at review time.

**Revisit when.** A second router consumer materializes and surfaces protocol shortcomings, OR the multi-session registry proves unused after 1 month of production data (then collapse to 1:1 lock and merge the router back into a more direct architecture).

**Refs.** [voice-only-permission-approval](#voice-only-permission-approval), [askuserquestion-interception](#askuserquestion-interception), [redis-bridge-verification](LEARNINGS.md#redis-bridge-verification), plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

### Permission approval is voice-only in v1 with destructive echo-confirm (commit pending)  {#voice-only-permission-approval}

**Decision.** Tool-permission relay over the channel accepts only voice approval ("yes <id>" / "no <id>"). Discord button approval (ephemeral DM Allow/Deny) is deferred to v2. Destructive operations (Write/Edit/NotebookEdit + Bash regex matches in `is_destructive`) trigger an echo-confirm safety net: "Approving destructive Bash. Say 'cancel' within 3 seconds."

**Rejected alternatives.**
- *Voice + Discord buttons in parallel (first-wins).* Rejected for v1: adds discord.py interaction handling, ephemeral message lifecycle, race-cancel logic — and the parallel-path UX optimizes for a scenario that doesn't actually exist (you're either hands-free in voice OR at Discord text; rarely both). v2 candidate if usage shows demand.
- *Tool-class allowlist (voice can approve read-only, never destructive).* Rejected by user: they want full hands-free. Mitigated by destructive echo-confirm + audit logging from day 1; revisit if false-positive rate is non-trivial.
- *Always require terminal approval.* Rejected: defeats the hands-free use case.

**Rationale.** Whisper false-positive rate (~1.4% on clean audio, higher in noise) is a real risk for destructive commands. 5-char random IDs (~11.8M space, generated by Claude Code core) make accidental triggering unlikely; 30s window bounds exposure; echo-confirm provides a "did you really mean it" beat. Audit logging from day 1 produces the data needed to tighten or relax this later.

**Revisit when.** Audit logs show ≥1 false-positive destructive approval in a month, OR usage data shows users prefer Discord-button approval to voice approval (would justify the parallel-path build cost). See [Discord button approval](QUEUED.md#discord-button-approval).

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `is_destructive` classifier at `plugins/redis-channel/server/protocol.py`.

### `AskUserQuestion` interception over agent-file coaching (commit pending)  {#askuserquestion-interception}

**Decision.** When Claude calls `AskUserQuestion` from a `redis-channel` channel session, the CC plugin's MCP server intercepts the tool call and converts the structured question to an inline-choice reply ("Which? A) ..., B) ..., C) ..."). The user's free-text response is parsed against the options and returned as the tool result. Agent-file coaching (in `agents/redis-channel-coach.md`) is provided as a friction-reducing hint but is **not** the enforcement layer.

**Rejected alternatives.**
- *Coach Claude via `agents/redis-channel-coach.md` to avoid AskUserQuestion when source is a channel.* Rejected as primary mechanism: Claude's training pulls it toward AskUserQuestion for clarification; coaching is probabilistic, not deterministic. Verified the channel protocol has no native facility by reading the official Discord channel plugin source + `https://code.claude.com/docs/en/channels-reference`.
- *Wait for the Claude Code channels protocol to add structured-question support.* Rejected: not on the published roadmap; would block v1.
- *Fail the AskUserQuestion call with an error so Claude retries with inline text.* Rejected: poor UX (user sees a tool error, not a question).

**Rationale.** Interception is deterministic. The MCP server sees every tool call before it reaches the user; converting it to a `reply` + parsing the next inbound is a finite-state interaction the server fully controls. Removes a category of "Claude ignored the coach" failures.

**Revisit when.** Claude Code adds a native `notifications/claude/channel/question_request` / `question_verdict` pair to the channel protocol — then replace interception with passthrough. Tracked in `plugins/redis-channel/PROTOCOL.md` "Reserved future expansion."

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `plugins/redis-channel/PROTOCOL.md` AskUserQuestion section.

---

## 2026-05-08

### Adopt uv as canonical dependency sync (commit pending)  {#uv-canonical-sync}

**Decision.** Use uv as the canonical repository dependency sync tool. Track `uv.lock`, install CI dependencies with `uv sync --locked --extra dev`, and run local and CI checks through `uv run`.

**Rejected alternatives.**
- *Keep using pip in CI.* Rejected: it contradicts the desired repository standard and leaves installs unreproducible.
- *Use `uv pip install` without a lockfile.* Rejected: it is still an ad hoc install path and does not satisfy the existing revisit condition for tracking `uv.lock`.
- *Move all dev dependencies to `[dependency-groups]` now.* Rejected: the existing `dev` extra maps directly from the prior `pip install -e ".[dev]"` workflow, so moving dependency ownership would add churn without improving the conversion.

**Rationale.** The repository already has `pyproject.toml` metadata and had a documented revisit condition to track `uv.lock` once uv became canonical. A checked lockfile plus `uv sync --locked --extra dev` makes CI and local development use the same dependency graph.

**Revisit when.** uv stops being the repository development standard, or the project intentionally changes from extras-based dev dependencies to uv dependency groups.

**Refs.** Supersedes the `uv.lock` portion of [gitignore `.claude/` + no `uv.lock`](#gitignore-claude-and-no-uv-lock); archived pre-correction version in [ARCHIVE](ARCHIVE.md#superseded-no-uv-lock-decision).

---

## 2026-05-01

### Gitignore `.claude/`; `uv.lock` decision superseded (commit `4da5705`)  {#gitignore-claude-and-no-uv-lock}

**Decision.** Add `.claude/` to `.gitignore`. The prior decision not to track `uv.lock` is superseded by [Adopt uv as canonical dependency sync](#uv-canonical-sync).

**Rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.

**Rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). The earlier `uv.lock` rationale was correct when the repo used ad hoc pip/uv installs, but no longer applies now that uv is the canonical lock-and-install path.

**Revisit when.** Claude Code introduces a *shared* settings file under `.claude/` that's intended to be checked in. At that point, narrow the gitignore from `.claude/` to specifically `.claude/settings.local.json` and `.claude/context/`.

**Refs.**
- DECISIONS [uv canonical sync](#uv-canonical-sync) — supersedes the lockfile portion of this decision.
- LEARNINGS [marketplace registry drift](LEARNINGS.md#marketplace-drift) — same PR (#112).
- ARCHIVE [PR #112](ARCHIVE.md#pr-112-marketplace-fix) — shipped record.
- ARCHIVE [superseded no-uv-lock decision](ARCHIVE.md#superseded-no-uv-lock-decision) — pre-correction record.

---

## Worker×Model cache scheduling — derive saga-side, reside team-side  {#worker-cache-scheduling}

**Date.** 2026-06-27. **Plan.** `docs/plans/2026-06-27-worker-model-cache-scheduling-plan.md` (from
`docs/brainstorms/2026-06-27-worker-model-cache-scheduling-requirements.md`, ideation S-1 build-first).

Port VECU's worker residency split along infiquetra's existing seam: **saga derives** (segment +
agent-id + tier), **team-execution resides** (named teammate + `SendMessage` reuse).

- **KTD1 — derivation saga-side, residency runtime team-side.** `Unit.depends_on`/`tier` already live
  in saga's `ExecutionSpec` (`execution_spec.py:176,:182`); `team_emitter.py:107` discards them.
  Derivation goes where the data is; team-execution consumes the emitted ids. *Rejected:* VECU's
  team-execution-side `worker_derivation.py` — right for VECU's primitive saga, wrong here.
- **KTD2 — segment boundary = plugin directory.** Single monorepo; VECU's repo-change proxy never fires.
- **KTD3 — stable agent id = segment/unit id**, replacing positional `worker-{i}` (residency needs a
  durable `SendMessage` handle).
- **KTD4 — behavioral residency is markdown protocol; the testable surface is the saga-side plumbing.**
  Reuse/wave/review-loop live in skills prose validated by `/doc-review` + operator runs + headroom
  telemetry; un-flatten + segmentation carry pytest. Consistent with the solo-operator measurement loop.
- **KTD5 — R15a context-GC excluded** — no harness lever (Messages-API-only).

**Revisit when.** Named-teammate residency proves insufficient (revisit warm-pool / crew-pairing); or a
single team-execution run shows enough internal idle-poll to justify a formal within-run wave queue.

**Refs.** Brainstorm requirements (origin); QUEUED [#ideate-brainstorm-do-less-bias](QUEUED.md#ideate-brainstorm-do-less-bias)
(skill-bias catch from the same session); ideation S-1.

**Doc-review addendum (2026-06-27).** A codex + agy adversarial pass + readiness review found 1 P0 + 4
P1, all fixed in the plan: `Unit` carried no file-path data for segmentation (added `Unit.files`); emit
cardinality was undefined (now **one row per segment**, KTD3); segment-level dependency derivation was
missing (KTD4 — collapse the unit dep graph to segments); and segmentation must not mutate the shared
`ExecutionSpec` (KTD5 — side mapping / copy). The "additive emitter" claim was corrected to
schema-breaking. Review record: `docs/reviews/2026-06-27-worker-model-cache-scheduling-review.md`.

---

## External engines are never gatekeepers {#external-engines-never-gatekeepers}

**Date.** 2026-07-01. **Plan.** `docs/plans/2026-07-01-external-engine-capability-routing-plan.md`
(from `docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md`, VECU seed S-4,
#283). Saga gains a capability-aware registry + resolver + dispatch adapter for external LLM engines
(Codex, Gemini via agy). This decision fixes the trust boundary the whole capability rides on.

- **KTD — the binding rule.** Claude is verifier-of-record for every gated decision. An external
  engine may occupy generator, advisory-reviewer, or non-gated-worker roles only; it never holds a
  gated verdict that blocks a merge/deploy or persists as a gate. Enforced **structurally, not
  asserted**: external output is an `AdvisoryEvidence` value with no verdict field, and
  `engine_dispatch.satisfy_gate` raises unless a distinct Claude verification step has stamped it.
- **Why this is a NEW decision, not a restatement.** The parroting note (`DECISIONS.md:276-290`) is
  *evidence* (Antigravity parroted while Claude/Codex independently verified), not a standing rule;
  the gated-vs-advisory consensus split (`operator-choice.md:82-95`) is the *mechanism* this rides on.
  Neither previously bound external engines as non-gatekeepers — #283 establishes that rule.
- **KTD — registry home = saga.** The registry (YAML data, R4) + resolver live in saga because every
  seam they hook (the per-unit engine/capability field, `recommend_execution_backend`,
  `saga.orchestration_downgrade`, the reviewer role) is already there. *Rejected:* a new
  `external-engines` plugin (fragments the seams, adds an 8th marketplace plugin); folding into `agy`
  (conflates one engine's containment wrapper with the router; agy is in-repo, codex external).
- **KTD — `engine` is a parallel Unit field, not an extended tier.** `MODELS = (opus,sonnet,haiku)`
  is load-bearing for Claude-agent dispatch; the resolver reads `Unit.engine`/`Unit.capability`
  before `tier.model`. *Rejected:* widening the closed `MODELS` enum.
- **KTD — capability tie-break = cost·speed (operator-confirmed).** When variants rate a capability
  equally, the cheaper·faster variant wins (`cost_speed_rank`, registry order as final backstop).
  *Rejected:* corroboration-strength (operator chose cost·speed); prompt-on-every-tie (breaks
  autonomous dispatch, R20).
- **Revisit when.** The ideation-R14 read-only-sandbox profile ships (external workers may then mutate
  files, R23 second half); team-execution gains an external-engine worker context-package slot (then
  R10/R12 team-execution dispatch, deferred here as U12); or the seed capability data drifts
  materially (re-validated by use via `/retro`, R21, not a measurement loop). Readiness record:
  `docs/reviews/2026-07-01-external-engine-capability-routing-plan-readiness.md`.

---

## External-engine workers in team-execution: chaperone dispatch, not a second executor kind {#external-engine-chaperone-dispatch}

**Date.** 2026-07-02. **Plan.** `docs/plans/2026-07-02-team-execution-external-engine-workers-plan.md`
(#318, U12 follow-up from #283's ship-with-deferred). Fulfills the "team-execution gains an
external-engine worker context-package slot" revisit trigger recorded in
[External engines are never gatekeepers](#external-engines-never-gatekeepers).

- **KTD1 — chaperone worker, not coordinator dispatch.** One resident Claude worker
  (`worker-<engine>` / `worker-<capability>`) owns an engine's units end-to-end: resolve → wrapper
  dispatch → verify → apply as sole-committer → test → manifest. There is no second executor kind
  in wave scheduling — the engine is evidence the chaperone consumes (R23), never a participant in
  residency, review, or git. *Rejected:* the coordinator dispatching inline (context bloat per
  dispatch; a second driver-materialized manifest-writer mode; two executor kinds in wave
  scheduling for what should be one).
- **KTD2 — delegation intent drives chaperone tier, operator confirms.** `offload` defaults the
  chaperone to `sonnet/medium` (a heavier chaperone erases the token savings that motivated the
  delegation); `second-opinion` defaults it to `opus/high` (adversarial verification IS the
  product; extra spend assumed). The two intents pull tier in opposite directions, so this is a
  per-unit operator-confirmed recommendation in the `/plan` tier table, not a fixed policy.
  *Rejected:* one fixed chaperone tier (wrong for one intent by construction).
- **KTD5 — advisory validators are opt-in and structurally incapable of gating.** The
  `external-second-opinion` validator is selected only via `.team-execution.json`'s
  `external_second_opinion` key, never auto-selected by Phase A; its Gate Status can never resolve
  to `hard-fail`/`blocked` for completion purposes (R13/R15), and Required-Evidence Absence does
  not apply to it (it cannot be missing what it was never required to provide).
- **Naming carve-out (KTD3).** An explicit-engine unit renders `worker-<engine-key>` (the bare
  engine id, e.g. `worker-agy` — not `worker-agy/gemini-3.5-flash-high`); a capability-routed unit
  renders `worker-<capability-key>` with Engine cell `cap:<key>` — the plan previews only what is
  knowable at plan time, since the concrete engine for a capability route is resolved at run time.
- **Revisit when.** The ideation-R14 sandbox profile ships and file-mutating external workers
  become possible (issue #287) — this plan's evidence-only chaperone scope would need revisiting;
  or `/retro` surfaces that the sonnet/medium offload default is still eating more than it saves.
  Readiness record: `docs/reviews/2026-07-02-team-execution-external-engine-workers-plan-readiness.md`.

---

## Dispatch-time tier resolver: one seam mapping (role-class, work-shape, overrides) to {model, effort} {#dispatch-time-tier-resolver}

**Date.** 2026-07-05. **Plan.** `docs/plans/2026-07-05-dispatch-tier-resolver-plan.md` (#362, half of
the effort/tier vocabulary work alongside #363 and #370).

- **KTD1 — resolver + registry live in `fleet_commons`, not `saga/scripts`.** The vocabulary this
  work builds on (`tier_palette.py`) already lives in `fleet-core`, and the resolver is consumed
  cross-plugin (saga, team-execution, the workflow emitter) — `executor_profile_lint.py:89` already
  proves the `fleet_commons_shim.load(...)` consumption pattern works. This overrides an earlier
  Gate E draft that proposed `plugins/saga/scripts/tier_resolver.py`.
- **KTD2 — build on `tier_palette.py`, do not create a competing vocabulary.** `cheaper_fallback`'s
  ladder math uses the already-shipped `model_rank`/`effort_rank` (#463); #362 does not block on
  #370's `escalate`/`downgrade`/`clamp` named operations. When #370 lands them, the resolver migrates
  its inline rank math onto them as a later, mechanical swap.
- **KTD3 — `cheaper_fallback` = weaken model first, then effort.** "Cheaper" means stepping down one
  `MODELS` rung (strongest-first) before lowering effort, matching operator intuition ("drop to the
  next cheaper model before turning down reasoning depth"). At the ladder floor (weakest model,
  lowest effort) the fallback equals the resolved tier — a no-op floor, never an error.
- **KTD4 — the expensive-tier gate is pure/testable, `/plan` doc/CLI-driven, runtime-injected.**
  `fable`/`xhigh` tiers are gated behind an operator-confirm flag per the operator-choice framework;
  the gate function itself stays pure and unit-testable, with the confirm prompt injected by the
  caller (`/plan`), not baked into the resolver.
- **KTD5 — `role-tier:` is backward-compatible.** All 25 team-execution agent frontmatters gain a
  `role-tier:` value; the pre-existing bare `model:` literal is kept as a last-resort fallback, never
  removed.
- **KTD6 — dispatch-time resolution is this issue's scope; effort-as-first-class-citizen in the
  plan/worker table schema is #363's.** #362 emits into a table shape that #363 parses; schema
  alignment between the two is called out as a live comment on #363, not solved here.
- **KTD7 — `role-tier` is a small agent-facing vocabulary mapping cleanly onto work-shape registry
  keys, and the team-execution migration is tier-preserving by construction.** Verified against the
  current fleet: all 10 `*-reviewer` agents were `opus`, all 8 `*-tester` agents were `sonnet`, and
  all 7 `*-scanner`/`*-monitor`/`deploy-watcher` agents were `haiku`. Three `role-tier` values
  preserve each group's existing tier — `adversarial-review` → opus/high (reviewers),
  `contract-test` → sonnet/medium (testers), `mechanical-scan` → haiku/low
  (scanners/monitors/deploy-watcher) — resolving through the registry's `judgment`, `mechanical`,
  and `purely-mechanical` work-shape rows respectively (the sonnet-vs-haiku split already named at
  `plugins/saga/skills/plan/SKILL.md:301`). The migration changes no agent's effective model; a
  tier-preservation test asserts each of the 25 agents still resolves to its pre-migration model.
  Intentional re-tiering is explicitly out of scope for #362.
- **Revisit when.** #370 lands `escalate`/`downgrade`/`clamp` as named ladder operations (KTD2's
  planned migration point), or #363 lands the effort-first-class plan/worker table schema and needs
  the emission shape reconciled with what #362 renders (KTD6).

---

### Run-scoped spend budgets — price the tier lever with a guarded ordinal weight table (commit pending)  {#run-scoped-spend-budgets-366}

Issue #366 gives the fleet's one model/effort lever a notion of *magnitude*: a shared ordinal
cost-weight table, a run-scoped `spend_envelope`, an emit-time `cost_budget` HALT, and an effort-escrow
ledger. Operator chose the **full DoD** (escrow ledger in the same PR, not deferred). Outcome leaf
`sub-366` of `tier-effort-first-class`; the spend-*delta* classifier is the separate #367.

- **KTD1 — `cost_weights.json` + its `cost_weights.py` loader live in `fleet_commons/`, beside
  `models.json`, not in `saga/references/`.** The weight table must not drift from the `tier_palette`
  ordering it prices; co-locating it with the ordering source and validating monotonicity at load
  closes the `{#tier-vocab-ordering}` two-contracts gap. `execution_spec.py` loads it via
  `fleet_commons_shim.load("cost_weights")`, symmetric with `tier_palette`. This overrides the issue's
  *indicative* `plugins/saga/references/cost_weights.json` (the issue delegates the path to `/plan`).
- **KTD2 — weights are hand-authored ordinal values (non-linear allowed), not `rank + rung`
  arithmetic.** A hand-authored table lets `xhigh`/`opus`/`fable` be disproportionately expensive (a
  real cost signal) while a load-time monotonicity guard keeps it honest. Weights stay ordinal/relative
  — no dollar prices, stable across provider price changes.
- **KTD3 — the `cost_budget` HALT mirrors `VERIFY_N_CAP` exactly** (`execution_spec.py:489-500`): same
  fail-loud `SpecError`, both sides named, optional soft warn band. This is the correctness-critical
  facet — a false-negative silently lets an over-budget run proceed, violating the `/outcome` campaign's
  binding HALT-not-degrade rule — so its unit carries the adversarial verify gate at merge.
- **KTD4 — `spend_envelope`/`cost_budget` live on `ExecutionSpec` (per-run), not `OutcomeSpec`.**
  `OutcomeSpec` keeps its derived `cost_rollup` (R24 leaf-produced fact); a run-scoped budget on the
  coordinator would fight the grounding-brief `/outcome` law ("cost ledger = leaf-produced fact"). This
  resolves the DoD's "run/outcome spec" ambiguity toward the per-run spec.
- **KTD5 — `SpendEnvelope` is a pure accumulator primitive** (crossing iff `cumulative + delta >
  envelope` while `cumulative <= envelope`), tested in isolation. Its consumers are a new
  `execution_spec.py spend` CLI verb (real read) and `/work`'s #364 between-rounds escalation (doc). No
  autonomous runtime gate is built (#366: "not a new autonomous gate; the envelope is a CLI-set field").
- **KTD6 — the effort-escrow ledger is a self-contained module** (`allocate`/`record_actual`/`refund`/
  `request_escalation`, allocations in `to_spend()` units) with `effort-policy.yaml` real config it
  loads via PyYAML. `/work` records actuals (producer); the refund/escalation compute and `/plan`
  reading the policy are consumers. The escalation-request surfaces pre-execution, mirroring #364's
  between-rounds gate.
- **KTD7 — new test files are `test_cost_weights.py`, `test_spend_envelope.py`, `test_effort_ledger.py`;
  `cost_budget` over/under-budget tests land in the EXISTING `tests/test_saga_execution_spec.py`.** The
  issue names `tests/test_execution_spec.py`, which does not exist (same reconciliation #364 made). The
  AC `-k` selectors become test-function-name fragments so every AC check resolves.
- **KTD8 — the `cost_budget` sum accounts for call MULTIPLICITY, not one weight per unit (surfaced by
  doc-review).** A fan-out unit runs its op `len(targets)` times and a verify panel adds `n` verifier
  calls at the unit's tier (× iterations when it iterates to consensus), so `unit_spend = to_spend(tier)
  × max(len(targets),1) + verify.n × to_spend(tier) × iterations`. A `pilot` is a separate declared unit
  counted on its own row and is deliberately not re-added (double-count guard). A one-weight-per-unit sum
  would undercount exactly the expensive fan-out/panel plans and false-negative the HALT — the
  HALT-not-degrade violation U2 exists to prevent, which is why U2 carries the adversarial gate.
- **Revisit when.** A second emitter (`team-execution`'s markdown path) needs budget parity and must
  consume the shared `cost_weights.json`; or #367's spend-delta classifier lands and the ordinal weight
  unit needs reconciling with its `spend_delta`/`adjacent_tier` ordering math.

---

### Spend-delta machinery — one three-way direction primitive built on the existing ordering (commit pending)  {#spend-delta-machinery-367}

Issue #367 gives `/plan` and `/work` one shared primitive for tier-spend *direction*: a
`spend_delta(old, new) -> {cheapen | escalate | lateral}` classifier, a `worth_it_because` +
`cheaper_fallback` validate hard-block, a relative `adjacent_tier` lever, and a
`.saga/spend-authority.json` silent/ask matrix. The **final leaf** `sub-367` of `tier-effort-first-class`
— merging it completes the outcome (9/9). Backend inline; saga-only.

- **KTD1 — `spend_delta` is per-axis ordering (three-way), not `to_spend` magnitude.** The `lateral`
  bucket is for sideways axis trades (stronger model + weaker effort). `to_spend` (#366) is a total order
  and injective over the 16 distinct cost cells, so a magnitude classifier could never yield `lateral`.
  `to_spend` answers "how much?"; `spend_delta` answers "which way?" — different primitives.
- **KTD2 — `spend_delta` generalizes `is_escalation`; the latter becomes `spend_delta(...)=="escalate"`.**
  One primitive, no parallel two-way/three-way vocabulary. A grid guard test proves equivalence so #365's
  `/tier` gate is behavior-preserved.
- **KTD3 — `spend_delta` + `adjacent_tier` live in `execution_spec.py`, not fleet_commons.** They are
  `Tier`-typed (the dataclass lives in saga) and sit beside `is_escalation`. `adjacent_tier("cheaper")`
  reuses `tier_resolver.cheaper_fallback` (#362, via the shim) so the down-rung logic is not duplicated;
  `dearer` uses `tier_palette.escalate`. This keeps #367 saga-only — no fleet-core bump (reuse, not
  modify).
- **KTD4 — `adjacent_tier` raises at ladder boundaries.** `cheaper_fallback`'s floor no-op (returns the
  same tier) is converted to a raise; `dearer` raises at the ceiling. The issue's explicit "boundary
  calls raise rather than silently clamping/wrapping."
- **KTD5 — one shared `sonnet/high` baseline for both the worth-it hard-block and the spend-authority
  default.** Both trigger on `is_escalation(SPEND_BASELINE, tier)` with `SPEND_BASELINE = sonnet/high`, so
  the two levers cannot disagree about what "premium" means.
- **KTD6 — `.saga/spend-authority.json` is a `silent_ceiling` tier, not a 16-cell map.** Modeled on a
  signature-authority limit ("authorized silently up to tier X"); the resolver compares via
  `is_escalation` (re-expressed on dict tiers, pinned to `is_escalation` by an exhaustive grid test).
  Absent → `sonnet/high`; malformed → loud `SpendAuthorityError` (the #368 `tier_defaults.py` precedent).
- **KTD7 — test placement:** `spend_delta`/`adjacent_tier` → new `tests/test_spend_delta.py`; the
  worth-it hard-block → existing `tests/test_saga_execution_spec.py`; spend-authority →
  `tests/test_spend_authority.py`. The issue's `tests/test_execution_spec.py` does not exist.
- **KTD8 — the worth-it hard-block is `require_receipts`-gated, not unconditional (implementation-forced).**
  The AC says "fails `validate()`", but the non-goal ("no retroactive backfill — new specs going forward")
  forbids an unconditional check: `validate()` runs on every emit and every existing spec (75 emitter
  tests break). Resolution: a `validate(require_receipts=True)` gate `/plan` sets at authoring; `emit()`
  and existing specs use the default `validate()` unchanged. Interaction: `/tier`-patching (#365) up to a
  premium tier is subject to the same authoring gate — a deliberate extension.
- **KTD9 — `SPEND_BASELINE = sonnet/high`, not sonnet/medium.** The issue's premium set "(opus, fable,
  xhigh in either axis)" — which omits `high` — is authoritative over the "sonnet/medium baseline"
  phrasing; `is_escalation(sonnet/high, tier)` yields exactly that set and avoids retroactively flagging
  common `sonnet/high` units.
- **Revisit when.** The `ask` path needs an actual operator-prompt surface (single vs batched), or a
  cross-repo authority registry is wanted beyond the single per-repo `.saga/spend-authority.json`.

---

## 2026-07-06

### /outcome completion harvest — supply the missing PR-ref producer, don't touch the consumers  {#outcome-completion-harvest-writeback-495}

Issue #495 (the first `/outcome` dogfood defect, found running `tier-effort-first-class` / objective
#343): code-leaf completion harvest silently never fired. The `code:pr-merged` barrier and the auto-merge
queue both *consume* `node.github["pr"]`, but the record-only dispatch → native `/work` → squash-merge
flow never *produced* it. Backend inline; saga-only.

- **KTD1 — Supply the one missing producer (`link-pr`); do not change the consumers.** Both the harvester
  barrier (`outcome_orchestrator.py:100-112`) and `outcome_merge._is_mergeable_kind` (`:170`, which
  requires `bool(node.github.get("pr"))` before it will queue a merge) consume the ref, so one producer
  unblocks both. **Rejected: a merge-time writeback** — vacuous, since the merge queue already requires
  the ref to act. **Rejected: a closing-PR timeline resolver** — `issue_close_info`/`_closed_by` surface
  only the closing *actor*, a robust closing-PR query is edge-case-heavy, and it would not even have
  fired for the tier-effort leaves (their sub-issues were closed manually, not by a keyword-closing PR).
- **KTD2 — Normalize refs at READ time, in `outcome_github`, via a components `_parse_ref`.** Read-time
  normalization repairs already-committed specs (tier-effort's `owner/repo#N` issue refs) with no
  migration. `_parse_ref → (owner, repo, number)` is consumed by both the `view` calls (which build a
  gh-consumable URL via `_gh_ref`) and `_closed_by`'s REST events path (which needs the components) — so
  normalizing a view-ref to a URL never starves `_closed_by` (the doc-review coupling guard).
- **KTD3 — `owner/repo#N` → full URL, not `N --repo owner/repo`.** A URL is one cwd-independent positional
  token, uniform across pr/issue; the caller's kind picks `/pull/` vs `/issues/`. Full URLs and bare
  numbers pass through unchanged.
- **KTD4 — `link-pr` writes local + optional `--push`; no auto-commit by default.** Consistent with
  `prune`/`promote` (`save_spec` local) and the R26/R27 explicit-bank cadence. It attaches a *pointer* —
  the barrier re-verifies `merged`, so a wrong/unmerged link never falsely completes a node.
- **KTD5 — R17 is untouched (rejected the "self-describing artifact" broadening).** The fix operates on
  GitHub refs + completion events, never persists derived `node.state`/`complete` into the committed spec
  JSON. The operator confirmed the outcome is already durably reconstructable (committed gh-consumable PR
  refs + reconstruct-on-advance); `node.state: pending` in the JSON is authoring-time by design.
- **KTD6 — "Automatic" = the attended verb, not zero-touch (operator-confirmed scope).** In an attended
  outcome an explicit `link-pr` verb IS the automation (vs hand-editing committed JSON + re-commit). A
  zero-touch autonomous producer is **deferred**, on evidence: no code leaf has ever reached the auto-merge
  queue (all outcomes ran attended/inline), and its auto-mechanisms are fragile or couple the leaf to the
  coordinator.
- **KTD7 — test placement:** ref normalization + the `code:pr-merged` guard → `tests/test_outcome_completion.py`;
  the `link-pr` verb → `tests/test_outcome_command.py`; the end-to-end harvest loop → `tests/test_outcome_integration.py`.
- **Revisit when.** The autonomous auto-merge path is actually exercised (then build the zero-touch
  producer — a coordinator-side read of the dispatched leaf saga's PR ref), or ingestion is changed to
  store full-URL refs at the source.

---

### /outcome attend — resolve the leaf's real issue-backed saga id at the handoff seam  {#outcome-attend-issue-backed-handoff-491}

Issue #491 (last execution-discovered defect of the `tier-effort-first-class` dogfood, objective #343):
`/outcome attend` printed the dispatcher's raw `leaf_saga_id` (`leaf-<outcome>-<subplot>`), a dead
`/resume` pointer — an issue-backed leaf's real native saga is `issue-<N>`. Backend inline; saga-only.

- **KTD1 — Resolve `issue-<N>` from the node, prefer bare `sub_issue`.** A node's `github` carries both
  `sub_issue` (bare int) and `issue` (`owner/repo#N`); prefer the digit `sub_issue`, else parse `issue`
  via `outcome_github._parse_ref` (landed in #495 — the two dogfood defects share one primitive).
- **KTD2 — Inline `f"issue-{N}"`, don't import `saga`.** Mirrors `saga.derive_saga_id` (`saga.py:333`);
  `outcome.py` deliberately imports only its `outcome_*` siblings, so a one-line format doesn't justify
  pulling in the heavy `saga` module. Cited in a comment so drift is catchable.
- **KTD3 — `attend` loads the spec.** It read only the dispatch ledger before; it now `load_spec` +
  `node_by_id` to reach `node.github`, with a node-miss / no-issue fallback to the raw id (never raises).
- **KTD4 — Scope is `attend` only.** `outcome_report.py` was verified to never emit the leaf handoff
  (`AttentionItem` carries only `subplot_id`; it never calls `attend`); the issue title's "attend/report"
  over-scoped. Corrected here so a reader doesn't think the report was missed.
- **Revisit when.** A non-issue-backed (task/ad-hoc) leaf needs a resolvable native id beyond the raw
  `leaf_saga_id` fallback — then extend the resolver for the `task-<slug>` case.

---

### Decompose a stale multi-issue objective into an `/outcome` DAG: re-triage first, seed flat, edge only what is genuinely hard, correct on the issue  {#outcome-dag-decompose-stale-objective-336}

Standing up objective #336 ("external-engine offload lane", 20 children) as the `external-engine-offload` `/outcome` DAG so the operator works it hands-on. The children's drafts were authored at Gate E (2026-07-03/04) and had drifted against substrate that shipped since (#401 ledger, #343 tier/effort, the 2026-07-05 first-party-codex decision).

- **KTD1 — Seed via `outcome start --from-objective`, accept a flat DAG.** Edge inference reads each sub-issue's GitHub `blocked_by` list (`outcome_edges.edges_from_relationships`); the 21 siblings had none, so the seed is a flat 21-node frontier. That is *honest*, not a gap: the lane's substrate (registry/resolver/dispatch/gates/manifests from #283/#285/#318, ledger from #401) already shipped, so the children are independent extensions. Do NOT invent dependency edges to express priority.
- **KTD2 — Value-ordering is operator frontier choice + `approve`-gating, never fake edges.** HTTP-cloud-first is a *priority*, not a hard dependency; overloading `depends_on` with priority lies about the graph and blocks legitimate parallelism. The operator sequences the ready frontier; `advance` only dispatches an `approve`d frontier (R20).
- **KTD3 — Encode only genuinely-hard edges.** Exactly one added by hand: `sub-384 -> {sub-383, sub-476}` — the tripwires audit cannot audit a receipt schema (#383) or a codex bridge (#476) that does not exist. It flipped `sub-384` `ready -> blocked`, confirming the reconcile loop honors it. Hand-edit the spec JSON `depends_on`, then `load_spec` (which `validate()`s declared-target + Kahn acyclicity) before commit.
- **KTD4 — Re-triage before decompose; fold what is already shipped.** A read-only triage of all 21 children against current HEAD found 5 stale "verified absent" draft claims and one fold: #392 -> #390 (3 of its 4 facets already shipped via #318/#319; the surviving invocation-proof discriminator is #390's fail-loud concern). Pruned `sub-392` (R33), closed #392 not-planned, grew #390.
- **KTD5 — Persist corrections onto the artifact the planner reads (the issue), not a side doc.** `/plan` Phase 0.1 reads the issue thread, so 7 scope-note comments (#387/#386/#390/#393/#381/#383/#384) make each stale draft self-correct at plan time — the operator need not remember. Same R17/derived-truth principle one level down: durable state belongs where it is consumed.
- **Durability.** Spec lives on branch `outcome/external-engine-offload` (R26, never main), committed via `outcome commit` (path-limited to the spec file, refuses on main) + pushed; a new machine reconstructs by pulling the branch and re-harvesting from GitHub (R27).
- **Revisit when.** A future `--from-objective` seed where GitHub `blocked_by` IS populated on the children — then edges auto-infer and KTD3's manual step is redundant; consider setting `blocked_by` on GitHub as the durable, re-derivable home for a hard edge instead of a spec-local edit.

---
