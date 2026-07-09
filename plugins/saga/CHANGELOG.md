# Changelog

## [0.75.10] - 2026-07-09

### Added - engine-registry schema currency (#452)

- `plugins/saga/references/engine-registry.yaml`: adds capability vocabulary for
  bulk classification, structured extraction, and embeddings, materialized GPT-5.5
  family capability defaults, per-row cost/latency metadata, and an embeddings-only
  Ollama Cloud row.
- `plugins/saga/references/model-releases.yaml` and
  `plugins/saga/scripts/check_engine_registry.py`: add authored model-release
  currency data plus a named CI lint gate for stale registry rows.
- `plugins/saga/references/surface_intent_defaults.yaml` and
  `plugins/saga/scripts/engine_offer.py`: move lifecycle engine-offer intent
  defaults into data while preserving repo-local preference overrides.

## [0.75.9] - 2026-07-09

### Added - engine output trust-boundary contract (#385)

- `plugins/saga/references/engine-output-trust-boundary.md`: documents external-engine advisory
  output as untrusted input, forbidden executable/gate sinks, and opaque-data handling.
- `tests/test_engine_output_trust_boundary.py`: adds contract anchors, seeded unsafe interpolation
  guards, and an adversarial `AdvisoryEvidence.evidence` fixture proving malicious advisory text stays
  inert through `satisfy_gate`.

## [0.75.8] - 2026-07-09

### Added - shared lifecycle-stage engine offer helper (#451)

- `plugins/saga/scripts/engine_offer.py`: adds an advisory-only offer helper with
  stage/shape intent-tier resolution, repo-local `.saga/engine-prefs.json`
  preferences, conservative mechanical offload defaults, and a CLI facade for
  markdown-driven skills.
- `ideate`, `brainstorm`, `work`, `doc-review`, and `code-review` now document a
  shared helper call site with drift-guard coverage.

## [0.75.7] - 2026-07-09

### Fixed - advisory consensus evidence remains outside Saga completion gates (#382)

- `plugins/saga/scripts/engine_dispatch.py`: classify consensus advisory reviewers as
  non-gating evidence so panel/advisory receipts cannot satisfy completion gates even when
  verified or corroborated.

## [0.75.6] - 2026-07-09

### Added — cheap external-engine chaperoning economics (#381)

- `plugins/saga/scripts/chaperone_economics.py`: adds pure policy helpers for homogeneous same-engine batching, explicit `test-gated` / `unverifiable` review modes, evidence-size tier escalation, deterministic acceptance sampling, and sampled-defect full-review escalation.
- `plugins/saga/scripts/execution_spec.py`: adds optional external-engine `Unit.verifiability`, emits it only when authored, and threads it into emitted external-engine call metadata while preserving old specs byte-for-byte.
- `plugins/saga/scripts/engine_dispatch.py` and `engine_resolver.py`: add optional advisory chaperone provenance and run-scoped payload caching keyed by `unit_id`, protocol hash, and context hash; no manifest schema or gate semantics change.
- `/plan` tier table now has a registry-rendered `offload` + `verifiability=test-gated` ratify-only row and keeps absent/unverifiable offload on full-review posture.

## [0.75.5] - 2026-07-09

### Added — registry-authored provider credential preflight (#389)

- `plugins/saga/scripts/engine_registry.py`: `EngineEntry` now exposes normalized
  `invocation.auth` metadata for `files`, `env`, `bearer`, and `secret-ref` credential probes;
  HTTP bridge rows remain bearer-only until the bridge can consume another credential mode.
- `plugins/saga/scripts/engine_resolver.py`: CLI preflight now reads executable and credential
  requirements from registry rows, keeps legacy no-entry callers working, and caches row-backed
  preflight by row identity instead of only `engine_id`.
- `plugins/saga/references/engine-registry.yaml`: codex and agy CLI rows now declare `invocation.cli`
  plus file-backed auth probes, matching the existing HTTP bearer-row contract.

## [0.75.4] - 2026-07-08

### Fixed — refute-N verifier panels fail loudly instead of passing under-strength (#519)

- `plugins/saga/scripts/execution_spec.py`: verifier `agent()` calls now carry a structured
  verdict schema requiring `refuted`, `upheld`, `verifier_identity`, `fallback_depth`, and
  `examined_sha`, so prose verdicts no longer collapse panels to `0/N` reporting.
- Emitted workflows append the unit result directly to verifier prompts and instruct isolated
  verifiers to materialize the primary checkout SHA before judging, making branch/output
  visibility an explicit verifier contract rather than an improvisation.
- Below-quorum panels now throw `verifier-under-strength` after logging missing-verifier detail;
  refuted quorum panels still throw `verifier-disagreement`.

## [0.75.3] - 2026-07-08

### Fixed — execution_spec emits StructuredOutput schemas for returned unit values (#503)

- `plugins/saga/scripts/execution_spec.py`: unit `agent()` calls now carry a schema derived
  from declared `returns`, so singleton units, parallel thunks, iterate-to-consensus loops,
  external-engine dispatches, and unattended climb retries request structured output at
  generation time instead of relying only on prose parsing in `__gate`.
- Cheap-tier unit schemas preserve the existing pull-cord escape hatch with a `oneOf`
  alternative, keeping budget-depth escalation behavior compatible with the structured return
  contract.

## [0.75.2] - 2026-07-08

### Fixed — cross-repo Objective ingestion stamps child repos and collision-safe subplot IDs (#512/#513)

- `discover_subissues.py` now fetches `repository.nameWithOwner` for sub-issues and tracked issues,
  preserving typed repo/number relationships for cross-repo Objectives.
- `outcome_edges.py` centralizes subplot ID derivation: existing `sub-<number>` IDs are preserved
  for unique numbers, while same-number collisions become repo-qualified and edge inference resolves
  typed cross-repo dependencies without guessing ambiguous legacy refs.
- `outcome.py` stamps each ingested node with the child issue's own repository and uses the shared
  subplot ID mapping, so board-sync, reconcile, and harvest target the correct GitHub issue.

## [0.75.1] - 2026-07-08

### Fixed — board-sync progress comments are crash-replay idempotent (#502)

- `plugins/saga/scripts/board_progression.py`: `issue-progress-comment` payloads now carry a
  hidden marker derived from the same idempotency key as the board-sync ledger. The production board
  writer checks existing issue comments for that marker before posting, so a crash after the GitHub
  comment POST but before the local ledger write replays as a remote-marker skip and then restores
  the missing local ledger key instead of double-posting.

## [0.75.0] - 2026-07-07

### Added — fail-loud provenance wiring: SUBSTITUTED_ENGINE derivation, gate refusal, empty-delivery HALT, verify-spawn attribution (#390 U2/U4/U5/U6)

- `plugins/saga/scripts/engine_dispatch.py`: `dispatch()` gains an optional `expected_identity`,
  stamped into evidence provenance; `build_dispatch_manifest` auto-derives
  `Disposition.SUBSTITUTED_ENGINE` when the evidence's expected engine identity differs from the
  resolved `engine_id`/`variant`, with a disposition note naming both identities (branch
  precedence: `DELEGATION_INTEGRITY` > halt (`FELL_BACK_TO_CLAUDE`) > `SUBSTITUTED_ENGINE` >
  receipt check). Every non-`RAN_AS_REQUESTED` manifest now carries a non-empty
  `disposition_note` (fixed fallback string for degenerate empty reasons). `satisfy_gate` refuses
  any manifest whose disposition is `SUBSTITUTED_ENGINE` — substituted evidence can never satisfy
  a gate as-approved. `expected_identity=None` callers keep prior behavior byte-for-byte.
- `plugins/saga/scripts/manifest_reader.py`: the roll-up report gains a reasons section listing
  execution id, disposition, and `disposition_note` for every manifest whose disposition is not
  `RAN_AS_REQUESTED`, so a forced fallback is traceable to prose, not just an enum.
- `plugins/saga/scripts/check_empty_delivery.py` (new): pure verdict function plus a thin CLI
  (reads `git status --porcelain -z`) that HALTs a delegated unit claiming delivery with zero
  changed paths, and returns a proceed verdict authorizing the existing chaperone-owned commit
  step for a delivering unit. Kept distinct from `manifest_store.py`'s returned-value
  `missing-output` axis.
- `plugins/saga/scripts/execution_spec.py`: verifier verdict schema and prompt gain
  `verifier_identity` (emitter-stamped) and `fallback_depth` (default 0); panel aggregation
  renders an explicit "fallback tier N" marker in the gate summary when any reporter's depth
  exceeds 0, and no marker for an all-first-choice `saga:readonly-verifier` panel.
  `plugins/saga/references/sandbox-spawn-sites.md` documents the rung-recording requirement for
  inline prose-ladder spawns (rungs 2/3). The fallback ladder's own order and contract are
  unchanged.

## [0.74.1] - 2026-07-07

### Fixed — code-review: gate Phase 5.4 saga append in programmatic mode (#468, Defect 2)

- `plugins/saga/skills/code-review/SKILL.md`: update Phase 5.4 to skip the saga tick append entirely
  in programmatic / report-only mode where the caller owns persistence, while keeping the
  interactive mode behavior and the no-saga scan-first guard unchanged.

## [0.74.0] - 2026-07-07

### Added — runtime delegation tripwires: armed PreToolUse block, Stop-hook audit, two-signal acceptance (#384, U3-U5)

- `hooks/delegation_tripwire_hook.py` (new `PreToolUse` hook, matcher
  `Write|Edit|MultiEdit|NotebookEdit`): while a session is armed and no genuine engine invocation
  is yet evidenced (a run directory under `.claude/agy/runs/` or `.claude/codex/runs/` containing
  a `prompt.txt` newer than the armed-at timestamp), Claude's own file-tool calls are blocked
  (exit 2). Unarmed sessions and every error path (malformed stdin, unreadable marker) fail open
  (exit 0) — zero behavior change when nothing is armed.
- `hooks/delegation_stop_audit_hook.py` (new `Stop` + `SubagentStop` hook): on an armed turn,
  classifies the transcript and corroborates the engine's bundle via fleet-core's
  `delegation_audit` module; hard-blocks the stop (exit 2, stderr reason) on
  `fallback_suspected`, honoring the `stop_hook_active` loop guard (one forced continuation
  max, banner + durable audit record under `.claude/delegation/audits/`). Transcript-verdict vs.
  engine self-report divergence is surfaced as `DELEGATION_INTEGRITY` rather than silently
  resolved either way.
- `engine_dispatch.py` arms around each adapter run and reconciles the engine's self-report
  against observer corroboration (receipt validity + bundle launch flag); divergence is a new
  `Disposition.DELEGATION_INTEGRITY` member on `provenance_manifest.py`, returned as a typed
  re-queue disposition — one re-dispatch attempt, then HALT (never silent accept).
  `satisfy_gate()` now additionally requires observer corroboration, not just Claude's own
  `verified_by_claude` bit.
- `hooks/hooks.json`: registers both new hooks (`PreToolUse` matcher-scoped;
  `Stop`/`SubagentStop` both marker-gated, each fed the correct turn's transcript path).

## [0.73.1] - 2026-07-06

### Retired — `codex:codex-rescue` (openai-codex marketplace plugin) (#476, R6)

- Every in-repo dispatch reference to the retired `codex:codex-rescue` agent (engine
  registry rows, `engine_dispatch.py`'s `build_codex_invocation`, engine-dispatch and
  external-engine-workers reference docs, tests) now points at the first-party
  `codex:delegate` (`plugins/codex/`). A grep sweep for `codex:codex-rescue` / `codex-rescue`
  confirms zero live references remain outside historical CHANGELOG and
  `docs/engineering-journal` entries, which are records and intentionally untouched. See
  `plugins/codex/README.md`'s operator runbook for uninstalling the `openai-codex`
  marketplace plugin and the `codex:` namespace-collision note (both plugins claim the
  `codex:` agent prefix; the marketplace copy must be uninstalled before this plugin's
  agents resolve cleanly).

## [0.73.0] - 2026-07-06

### Added — generic HTTP bridge + bridge_receipt.v1 keystone pair (#387, #383)

- `engine_dispatch.py`'s `_build_invocation` gains a `transport`-keyed branch: `transport: http`
  registry rows dispatch through one generic OpenAI-compatible bridge
  (`engine_bridge_http.py`, stdlib `urllib.request` behind a `Runner`-shaped seam) with zero
  per-provider branching inside the bridge — provider differences live entirely in registry row
  data (base URL, auth mode/env var, model id). `transport: cli` keeps the existing codex/agy
  builders unchanged (default `cli`, byte-identical for every existing row).
- `engine_registry.py` / `engine-registry.yaml`: new `transport` field (closed vocab `cli | http`)
  plus http-conditional required invocation fields (`base_url`, `model`, `auth.mode`,
  `auth.key_env` when bearer, explicit `effort`); `receipt_emitter` is now a required key on every
  row, validated at load (`RegistryError` on a row missing it — a row without receipt wiring
  cannot be dispatched to). Two new seed rows: `ollama-cloud` (Ollama Cloud, bearer auth from
  `OLLAMA_API_KEY`, first $0-marginal offload row) and `deepseek` (bearer auth from
  `DEEPSEEK_API_KEY`). Neither row outranks an existing `by_capability` winner (routing-stability
  regression test bakes current winners as literals).
- `engine_resolver.py`: transport-aware `preflight()` (HTTP checks the auth env var is present and
  the row is well-formed — no live network; reachability is proven only by the availability-gated
  smoke test) and an explicit `RunMemo` object threaded as an optional `memo` keyword through
  `resolve` / `resolve_role`, memoizing one resolve/preflight per engine per run
  (`(capability, token_estimate)` for resolution, `engine_id` for preflight) — 10 resolves of one
  engine in a single run now invoke the availability probe once. Memo is opt-in; the no-memo path
  stays today's byte-for-byte behavior.
- `bridge_receipt.v1` (new `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py`,
  vendored to `plugins/agy/scripts/fleet_commons_shim.py`): the proof-of-execution contract every
  bridge emits — a common core (`schema`, `engine_id`, `variant`, `transport`, `wall_time_s`,
  `bytes_produced`) plus transport-discriminated runner evidence (`{pid, argv, exit_code}` for
  `cli`, `{url, status_code, model}` for `http`). `AdvisoryEvidence` gains an additive
  `runner_receipt: dict | None = None` field; `build_dispatch_manifest` assigns
  `Disposition.RAN_AS_REQUESTED` only when a schema-valid receipt is present, else the new
  `Disposition.UNPROVEN` (receipt-less success is never mislabeled as proven; `FELL_BACK_TO_CLAUDE`
  is unaffected). A structural guard rejects any runner result carrying a gate/verdict-shaped key
  (`verdict`, `gate_status`, `adjudicated`) as a `DispatchError` — external engines can never become
  gatekeepers (`{#external-engines-never-gatekeepers}` #283), enforced by construction, not policy.
- New `tests/test_bridge_receipt_drift.py`: a forcing-function drift guard enumerating every
  registry `receipt_emitter` value and proving each in-repo emitter dispatches through the shared
  receipt-emitting path (`PENDING_EMITTERS = {"codex-bridge": "#476"}` covers the not-yet-landed
  codex bridge; the guard reds if a pending entry's issue closes while the entry is still pending).
- Secret lifecycle: a bearer token resolved from `auth.key_env` exists only in the HTTP request
  headers at call time — never in the invocation dict (which flows into run-ledger telemetry), a
  receipt, `AdvisoryEvidence`, or a log line. Receipts may carry the env var *name*, never its
  value.
- New `plugins/saga/references/dispatch-adapter-contract.md`: the dispatch-adapter contract
  reference for anyone adding a `transport: http` registry row or a new bridge.
- Existing callers stay byte-identical: no signature breaks, `transport` defaults to `cli` for
  every pre-existing row, memo is opt-in, and `preflight()`'s new `entry` parameter is optional.

## [0.72.0] - 2026-07-06

### Fixed — /outcome attend emits the leaf's real issue-backed saga id (#491)

- `/outcome attend <id> <subplot>` printed the dispatcher's raw `leaf_saga_id`
  (`leaf-<outcome>-<subplot>`), but an issue-backed leaf's actual native saga is `issue-<N>` (what
  `/plan` and `/work` mint via `saga.derive_saga_id`) — so the `/resume` handoff pointed at a saga id
  that does not exist. `attend` now resolves the real id: `_leaf_handoff_id` reads the node's
  `github.sub_issue` (bare number) or parses `owner/repo#N` from `github.issue` (reusing
  `outcome_github._parse_ref`, #495) and emits `/resume issue-<N>`; a non-issue-backed (task/ad-hoc) leaf
  keeps the raw id.
- Scope is `attend` only: `outcome_report.py` never emitted the leaf handoff (`AttentionItem` carries
  only `subplot_id`), so it is unchanged.

### Notes

- Saga-only; last execution-discovered defect from the `tier-effort-first-class` `/outcome` dogfood.

## [0.71.0] - 2026-07-06

### Fixed — /outcome code-leaf completion harvest silently never fired (#495)

- **The producer gap (gap 1).** The `code:pr-merged` barrier (`outcome_orchestrator.py`) and the
  auto-merge queue (`outcome_merge._is_mergeable_kind`) both *consume* `node.github["pr"]`, but the
  record-only dispatch → native `/work` → squash-merge flow never *produced* it, so `advance` read
  "no PR ref yet" forever and left every code leaf pending (the only recovery was a hand-edit of the
  committed spec). New verb **`/outcome link-pr <id> <subplot> <pr-url>`** is the attended producer:
  it writes `node.github["pr"]` (validated as a PR URL, code-node-only, idempotent; `--push` banks it
  to the outcome branch). It attaches a pointer only — the barrier still re-verifies `merged`, so a
  wrong/unmerged link never falsely completes a node.
- **The ref-format gap (gap 2).** `outcome_github._parse_ref`/`_gh_ref` normalize a stored ref
  (`owner/repo#N` | full URL | bare `N`) to a gh-consumable token; `pr_state`, `issue_state`,
  `board_status`, and `issue_close_info` now resolve `owner/repo#N` (previously `gh` rejected it as an
  invalid issue format / misread it as a branch). `_closed_by` consumes `_parse_ref` too, so
  normalizing a view-ref to a URL never starves its REST events path.
- The `code:pr-merged` contract is unchanged and now regression-guarded: a closed tracking issue never
  satisfies a code leaf; only a merged `github.pr` does.

### Notes

- Saga-only; **R17 preserved** — the fix touches GitHub refs + completion events, never persists derived
  `node.state`/`complete` into the committed spec JSON.
- Deferred (not built): a zero-touch autonomous PR producer (the autonomous auto-merge path is not yet
  exercised, and its auto-mechanisms are fragile/coupling); a merge-time writeback was rejected as
  vacuous (the merge queue already requires `github.pr` to act).

## [0.70.0] - 2026-07-06

### Added — spend-delta machinery: the silent-cheap/ask-expensive levers (#367)

- `spend_delta(old, new) -> {cheapen | escalate | lateral}` in `execution_spec.py`: the three-way
  direction classifier, built on per-axis ordering (a shared `_axis_deltas` helper via the palette
  `stronger` op, never raw `.index()`). `is_escalation` now shares that helper but keeps its exact
  two-way semantics — `lateral` (a sideways axis trade) is deliberately distinct from `escalate`.
  Built on ordering, not `to_spend` magnitude: the cost table is injective, so a magnitude reading
  could never produce `lateral`.
- `adjacent_tier(tier, "cheaper"|"dearer")`: the relative one-notch lever. `cheaper` reuses
  `tier_resolver.cheaper_fallback` (#362); `dearer` is the symmetric one-rung-up. Boundary calls
  **raise** rather than clamp or wrap.
- `Unit.worth_it_because` + `Unit.cheaper_fallback` (both optional, byte-identical round-trip absent) +
  a **premium-tier worth-it hard-block**: `validate(require_receipts=True)` fails a premium tier
  (opus/fable model or xhigh effort, above the `sonnet/high` baseline) that lacks a justification or a
  strictly-cheaper named fallback. Gated on `require_receipts` — enforced at `/plan` authoring, never on
  the unconditional `validate()` that emit and existing specs run (no retroactive break).
  `execution_spec.py validate --require-receipts` is the authoring gate. Engine-owned units are exempt.
- `spend_authority.py` + `.saga/spend-authority.json`: a per-repo `silent_ceiling` matrix resolving each
  unit `silent`/`ask` (premium → `ask`). Absent file → safe default `sonnet/high`; malformed → loud
  `SpendAuthorityError`. Same `is_escalation` predicate as the worth-it block (pinned by an exhaustive
  grid guard test), so the two levers agree on what "premium" means.
- `/plan` §5.2a Step 1c documents the relative override, worth-it receipts, and spend-authority stamp.

### Notes

- Saga-only (no fleet-core change): `spend_delta`/`adjacent_tier` are `Tier`-typed and live in
  `execution_spec.py`; `tier_resolver.cheaper_fallback` is reused, not modified.
- Completes the `tier-effort-first-class` outcome (9/9): #366's `cost_budget`/`spend_envelope` answered
  "how much?"; #367's `spend_delta` answers "which way?".

## [0.69.0] - 2026-07-06

### Added — run-scoped spend budgets: price the tier lever (#366)

- `cost_weights.json` + `cost_weights.py` (in `fleet_commons`, beside `models.json`): an ordinal
  16-cell weight table and `to_spend(model, effort)`. Validated at import against the live
  `tier_palette` ordering — completeness, per-axis strict monotonicity, and off-palette rejection all
  raise `CostWeightsError` (a drifted table fails loud, closing the `{#tier-vocab-ordering}` gap).
  Weights are ordinal/relative, not dollar prices.
- `ExecutionSpec.cost_budget` + the emit-time cost HALT: `validate()`/`emit` raise a `SpecError` naming
  total vs ceiling when the multiplicity-aware summed spend exceeds the budget (mirrors `VERIFY_N_CAP`,
  with a soft warn band). The sum counts call multiplicity — fan-out target count and verify-panel `n`
  × iterations — so it cannot false-negative on the expensive fan-out/panel plans (HALT-not-degrade).
  `spec_spend()` and the module-level `unit_spend()` expose the arithmetic.
- `ExecutionSpec.spend_envelope` + the `SpendEnvelope` accumulator: collapses "ask before every
  expensive choice" into "ask once, at the crossing" (`consider(delta)` prompts only on the crossing
  choice). A CLI-set field + primitive, not an autonomous gate.
- `execution_spec.py spend <spec.json>` CLI verb: reports per-unit spend, total, `cost_budget` headroom,
  and `spend_envelope` — the surface `/plan` invokes to price a plan before locking it.
- `effort_ledger.py` + `effort-policy.yaml`: an effort-escrow ledger recording per-unit actual-vs-planned
  spend, refunding an under-spending unit's unused allocation to a run pool, and surfacing an
  escalation-request **before** a unit executes when it would exceed its allocation. CLI verbs
  `allocate` / `record` / `escalate` / `report`; an absent policy file resolves to the safe default.
- `/plan` §5.2a Step 1b (price the plan, set the guards) and `/work` execution-strategy effort-escrow
  accounting document the producer/consumer wiring.

### Notes

- All new `ExecutionSpec` fields round-trip byte-identical when absent — existing specs and
  `team_emitter` are untouched.
- The cost-weighted spend-*delta* classifier (silent-cheap/ask-expensive, relative lever, spend
  authority) is the separate #367.

## [0.68.0] - 2026-07-06

### Added — runtime ladder climbing: gated one-rung escalation on failure signals (#364)

- `escalate_tier(tier, ceiling=None)` — the pair-level one-rung climb: effort-first, then model
  (`supports_effort` invariant, never unrunnable), built on the named `tier_palette` ops. Returns
  `None` at the top of the ladder or when blocked by a ceiling — every caller renders that as an
  explicit HALT, never a silent same-tier re-run.
- `Unit.escalate_on_signal` (requires a verify panel): attended emission renders a refute as a
  throw-with-`escalation-proposal` ask gate (confirmed via the #365 `/tier` patch + re-emit);
  `emit --unattended` renders ONE in-script climb retry at the climbed tier with a fresh panel,
  then HALT — one climb per unit per run, session-ceiling-aware. Attendance is a run property and
  never enters the spec JSON (absent field round-trips byte-identical). v1 validate exclusions:
  `iterate_to_consensus`, fan-out, and no-panel (all unbounded-spend or dead-wiring vectors).
- `pull_cord` — the worker-initiated out-of-depth disposition on the cheap-tier return contract:
  the gate accepts `{"pull_cord": "<reason>"}` distinct from success/crash, the unit is never
  marked complete, and all cords batch into ONE end-of-run coordinator escalation entry carrying
  one-rung proposals.
- `/work` between-rounds recovery step (`references/pr-continuation-loop.md`): on a failure row,
  propose exactly one rung with the ordinal cost delta (`<old> -> <new> (+1 <axis> rung)`),
  end-clamped at the ladder top / session ceiling, gated on operator confirmation. The priced
  spend-delta classifier stays #367's.

## [0.67.0] - 2026-07-06

### Added — persisted tier preferences: repo overlay + issue band + one precedence rule (#368)

- New `scripts/tier_defaults.py`: committed per-repo `.saga/tier-defaults.json` overlay
  (`{"<work-shape>": {"model", "effort"}}`) pinning repo-tuned tier defaults over the shared
  `tier_policy.json` registry. `load_tier_defaults` (missing → `{}`, malformed → loud
  `TierDefaultsError`), `resolve_tier_with_overlay` (repo overlay > registry),
  `write_tier_default` (read-merge-write confirmed overrides, never clobbers other keys).
- `resolve_tier_for_plan(work_shape, issue_band)` — the one tested precedence contract:
  **repo overlay > issue-carried band > shared registry** (the repo override is closest to
  execution, so it wins the coarser issue-time band).
- `parse_tier_band(body)` — reads the `### Recommended Tier Band` section mission-control
  stamps at issue creation. Absent → `None` (normal); present-but-invalid (unparseable,
  off-palette, or unrunnable tier) → loud `TierDefaultsError` (halt-not-degrade).
- `/plan` SKILL Step 1 documents the resolve → confirm → write-back loop; every persisted
  override originates from an explicit operator confirmation (never silent auto-promotion),
  and the dirtied tracked overlay is committed with the run's changes.

## [0.66.0] - 2026-07-06

### Added — `/tier` mid-run lever: session ceiling + mid-run spec patch (#365)

- New `/tier` command (`commands/tier.md`) + `tier_session.py` module: a session-local, git-ignored
  override (`.claude/saga/tier-session-override.json`) recording a run-scoped tier **ceiling** and
  per-unit **overrides**. Off-palette values fail loud on read and write.
- `clamp_tier_to_ceiling()` — a pure, 2-axis, downward-only ceiling clamp (via `tier_palette.clamp`).
- Both emitters (`emit_workflow_script`, `team_emitter.emit_team_structure`) accept a `session_ceiling`
  and clamp each unit/segment tier down before rendering — the single enforcement point, applied
  **before** the #369 enforceability halt (so a ceiling can make an otherwise-unspawnable `fable` unit
  runnable on team-execution). Downgrades are logged; the `inline` backend honors the ceiling
  advisorily. The ceiling is the final word — it can clamp below a `min_tier` floor (the live override
  wins).
- `patch_spec_tiers()` (not-yet-run units only) + `is_escalation()` + an `execution_spec.py patch`
  subcommand: apply the session override's per-unit tiers, re-validate (hard gate), re-emit; an
  up-ladder escalation is surfaced for operator confirmation. The `emit` CLI now honors the ceiling.

## [0.65.0] - 2026-07-06

### Added — tier floors & backend enforceability (#369)

- `TIER_ENFORCEABLE_BY_BACKEND` matrix + `unenforceable_tier()` helper (`execution_spec.py`), the
  tier-axis sibling of `SANDBOX_ENFORCEABLE_BY_BACKEND`: each backend maps to the models it can spawn
  (`inline` / `cc-workflows-ultracode` reach the whole palette; `team-execution` = `{opus, sonnet,
  haiku}`, no `fable`). A backend absent from the matrix enforces nothing — unknown is never permissive.
- `team_emitter.emit_team_structure()` now HALTs (`SpecError`) when a unit's model is unreachable by
  `team-execution` (e.g. `fable`/`xhigh`) instead of rendering a cosmetic Tier cell the runtime will
  not obey — the tier-axis sibling of the existing unenforceable-sandbox halt.
- Optional `Unit.min_tier` floor: `segment_units()` clamps a merged segment tier UP to the strongest
  member floor via the palette ladder ops (never bare index math). An absent `min_tier` emits no key
  and round-trips byte-identical; an off-palette or unrunnable floor fails validation loudly.

### Deferred

- Agent-owned `tier-floor:` frontmatter (issue #369 mechanism 3) is deferred to a follow-up that
  lands it together with the per-teammate tier-override lever (`{#team-execution-per-teammate-effort}`)
  so the field ships with a real producer and consumer.

## [0.64.0] - 2026-07-06

### Changed — execution_spec consumes the single-source tier palette (#370)

- `segment_units()` now merges member tiers via `tier_palette.strongest()` instead of inlining
  `min(MODELS.index)` / `max(EFFORTS.index)` — the named ladder op reasons in strength, closing the
  `{#tier-vocab-ordering}` two-contracts footgun.
- `Tier.validate()` now HALTs (raises `SpecError`) when a Claude teammate's effort exceeds the
  model's `effort_ceiling` (e.g. `haiku`/`xhigh`) rather than silently running an un-runnable tier;
  engine-owned chaperone-dispatch units (`{#external-engine-chaperone-dispatch}`, #318) are excluded
  from the per-teammate ceiling check.

## [0.63.0] - 2026-07-05

### Changed — `team_emitter.py` validates and cascade-resolves per-teammate effort (#363)

`emit_team_structure()` now validates the A7 `Tier` cell's effort half against the canonical
`EFFORTS` vocabulary (`fleet_commons.tier_palette`, R4) — an off-palette value raises at compose
time instead of rendering an un-runnable team-structure table. A new `resolve_teammate_effort()`
resolves each non-chaperone teammate's effort through the three-layer cascade (plan-unit →
team-default → agent-frontmatter base, R5, KTD4), wrapping `tier_resolver.resolve()` and recording
which layer won as a provenance line. Chaperone workers (`offload`/`second-opinion` engine or
capability segments) are excluded from the cascade entirely — their effort is intent-driven and
must not be overridden (R6, KTD5). Closes the standing `{#team-execution-per-teammate-effort}`
queue item via the `inject_effort()` seam (see team-execution 2.11.0), not the rejected
route-onto-Workflow re-architecture.

## [0.62.0] - 2026-07-05

### Changed — `/plan`'s Step-1 tier table now renders from the shared work-shape→tier registry (#362)

Part of the dispatch-time tier resolver work (`fleet_commons/tier_resolver.py`, `tier_policy.json`)
that maps `(role_kind, work_shape, envelope_ceiling, operator_override)` to `{model, effort, because,
cheaper_fallback}`. `plugins/saga/skills/plan/SKILL.md`'s heuristic tier table is now a
registry-sourced block instead of prose, drift-guarded against `tier_policy.json` so the two can never
silently diverge. `plugins/saga/references/sandbox-spawn-sites.md` gained the tier-resolver dispatch
site alongside the existing readonly-verifier spawn-site inventory.

## [0.61.0] - 2026-07-05

### Added — one append-only, hash-chained, leaf-produced run-fact ledger substrate (#401)

The final Phase 0 item (objective #338). A single `run_fact.v1` ledger that spend / cache /
engine-usage / delegation telemetry all append into — landed empty of most consumers so the ≥8 wave-1
writers inherit one canonical format instead of N.

- **`run_ledger.py`** (new, saga-local, stdlib-only) — `run_fact.v1` schema (`kind` ∈
  spend|cache|engine|delegation, leaf-produced with `subplot_id`), a **hash-chained** `append_fact`
  (`prev_hash`→`this_hash`, reusing `outcome_store`'s `resolve_common_dir` + `O_APPEND` + torn-tail
  discipline in a **distinct** `run-facts.jsonl`, separate from the replay ledger), `read_facts`, and
  `verify_chain` (fails on in-place mutation, reorder, or middle-deletion — tamper-*evidence*).
- **Derive-on-read views** — `rollup`, `reuse_ratio` (defined-empty on no data), `last_n_prior`; no
  committed summary field.
- **Two consumers wired** — `engine_dispatch.dispatch(ledger=…, subplot_id=…, at=…)` records an
  `engine` fact on any advisory call and a `delegation` fact for an `agy.delegation.v1` call (telemetry
  only, never gates, no-op without a ledger); `lifecycle_state.recommend_execution_backend(ledger=…)`
  surfaces a `last_n_prior` prior additively (byte-identical to today with no ledger/data).
- **Docs** — `references/run-fact-ledger.md` (schema, chain custody + the tamper-evidence-not-resistance
  threat-model bound, derive-on-read views, adoption note) + DECISIONS `{#run-fact-ledger-401}`.

## [0.60.0] - 2026-07-05

### Added — remote gate approval over the fleet's own channel (#379)

Give the durable `/outcome` R20 frontier-approval gate a second, unattended delivery surface: the
fleet's own redis-channel / Discord bridge. When a gate holds while the terminal is unattended, its
prompt travels over the channel and the operator's reply becomes the durable approval — recording
**who** answered and over **which transport** as provenance (option A, 2026-07-05).

- **Provenance on the durable record** — `outcome_decompose.approve_frontier(...)` gains keyword-only
  `answerer` / `transport`, written into `approvals/r{rev}.json` only when supplied (a terminal
  approval stays byte-identical; `frontier_approved` is existence-only, so the extra keys are
  backward-compatible). `outcome approve` gains `--answerer` / `--transport`.
- **New `outcome_gate_transport.py`** (stdlib-only, decoupled from redis-channel) — transport-agnostic
  `compose_gate_notice` (renders the gate id `<outcome_id>@r<rev>` + pending subplots + lettered
  choices), `parse_gate_answer` (accepts a reply **only** when it quotes a gate id in the caller's
  `pending_gate_ids`, reads `answerer` / `transport` from router-set inbound fields not the body, and
  never defaults to *approve*), and a redis-only `emit_gate_notice` programmatic seam.
- **Access deferred to the transport (option A / KTD2)** — sender authorization is enforced upstream
  of the session by the transport's own access policy (Discord `gate()` pre-filters to `allowFrom`;
  redis-channel defers to its router); the gate records provenance and correlates a pending gate, it
  never re-authorizes a sender. A channel message cannot forge or escalate an approval.
- **Documented contract** — `references/operator-choice.md` §5.1 (channel-transport gate delivery) and
  `redis-channel/PROTOCOL.md` (transport-agnostic gate notice/answer convention; redis-channel stays
  router-agnostic — docs-only there). Notice delivery is session-driven for both transports.

## [0.59.0] - 2026-07-05

- Feat: fleet-wide 429 handling adopts the shared fleet-commons `retry_backoff` primitive (#348).
  The emitted `.workflow.js` wraps every `parallel([...])` wave thunk and refute-N panel verifier
  `agent()` call in a `__retry` helper (bounded exponential backoff, `Retry-After` honored) so a
  rate-limited agent re-queues instead of counting as a wave failure; a non-429 error still throws
  and HALTs the wave (singleton `await agent()` calls are unwrapped by design). `/outcome` dispatch
  now classifies a 429 (`BackendRateLimitError`) as `retriable-pending` — a derived-on-read RESULT
  label (`AdvanceResult.retriable`), never a committed `NODE_STATE`: the 429'd leaf stays `ready`
  and the ready frontier re-picks it on the next `advance()` tick with no operator action and no
  git/ledger state change (a per-call `retriable_seen` guard de-hammers a loop=True run).

## [0.58.0] - 2026-07-05

- Feat: `/outcome start --from-objective <owner>/<repo>#<N>` seeds the DAG from a GitHub Objective's
  sub-issues (#375). Wires the previously-unwired `discover_subissues.py` GraphQL reader (extended with
  `stateReason` + `trackedIssues`) through a new library `fetch_objective`, builds one node per
  sub-issue with `kind` from labels, an authored terminal `state` for closed sub-issues (COMPLETED→done,
  NOT_PLANNED→rejected — structural spec state, never a committed status field), and a `github`
  provenance stamp the reconcile/board-sync consumers read.
- Feat: new `outcome_edges.py` — a pure, cycle-safe `edges_from_relationships()` that infers
  `depends_on` edges among the ingested sub-issues, dropping and reporting dangling/cyclic edges so the
  produced spec always passes `OutcomeSpec.validate()`. Edge inference is best-effort (uses only stable
  GraphQL fields) and degrades to no-edges; the no-flag `start` default is unchanged.

## [0.57.0] - 2026-07-05

- Feat: extracted `/outcome`'s certificate-gated autonomous board writer into a new plugin-agnostic
  `board_progression.py` (#344). The per-op mechanism (authorize via `reversibility_certificate` →
  idempotency-keyed ledger → bounded-retry write → fail-loud record) plus the production
  `default_board_writer` (the `OpKind` → mission-control verb mapping, moved from `outcome.py`) now
  live there behind a `write` CLI so the markdown skills can invoke it. `outcome_board_sync.reconcile_board`
  delegates to it with zero behavior diff (`outcome_store._write_once` injected to preserve exact
  atomicity + test-patchability); `_safe_ledger_name`/`_default_board_writer` are re-exported so
  `outcome_reconcile` and `outcome.py`'s call sites are untouched.
- Feat: `/work`'s post-merge phase now fires the allowlisted Status → Done and sub-issue-close moves
  autonomously through `board_progression.py` (no operator prompt); merge/deploy and any
  non-allowlisted op still return `GATE` and fall back to the operator-prompted `mission-control`
  path — the autonomously-writable set cannot widen because the allowlist lives in the certificate.
- Feat: `status_card.py` gains `project_arc`, a pure derived-on-read idea→deploy lifecycle arc
  (gate-sequence over durable saga fields only), rendered by `/loop` at Route/Drive/Resume. `/loop`
  renders and sequences but never writes the board itself (router first-principle preserved).

## [0.56.0] - 2026-07-05

- Fix: `ship_ceremony.py` could not resolve a task-kind saga (no `issue_ref`) once `checkout_main`
  moved off the work branch — by-branch resolution on `main` matched every other saga left there
  and raised `AmbiguousSagaError`, forcing manual `pull`/`branch_delete` cleanup. `run` now accepts
  `--saga-id` (resolved directly, ahead of `issue_ref`, surviving any branch change), and the
  by-branch fallback ignores terminal (`done`/`abandoned`) sagas so stale sagas left on a branch no
  longer force a false ambiguous match.

## [0.55.0] - 2026-07-05

- Feat: `ship_ceremony.py`'s `open_pr` transition now injects a `Fixes #N` line (parsed from the
  saga's `issue_ref`) into the PR body it creates, so merging auto-closes the tracked issue instead
  of leaving the manual close step to be forgotten. Only added when the saga names a numeric issue;
  the `Plan:` link is preserved alongside it.
- Fix: `saga.py`'s `save()` now also refreshes `head_sha`/`last_commit_sha` from live git on every
  save (the #480 follow-up), so they track the current commit instead of freezing at the mint-time
  HEAD (`status_card` renders `head_sha` as its CI reference). SHAs need no default-branch guard.

## [0.54.4] - 2026-07-05

- Fix: `saga.py`'s `save()` only auto-derived the `branch` field from live git state on a saga's
  first-ever save (`if not merged.branch`), so a saga minted by `/plan` on `main` — before its
  work branch existed — carried `branch="main"` for its entire life, even after `/work` re-saved
  it on the work branch. `branch` now refreshes from live git on every save whenever git reports a
  definite (non-empty) branch, so `ship_ceremony.py`'s `branch_delete` guard and `/code-review`'s
  branch-match see the real branch. The non-empty guard is retained so a detached-HEAD / no-git
  read never clobbers a stored value; `head_sha`/`last_commit_sha` keep first-save-only capture
  pending a follow-up (#480).

## [0.54.3] - 2026-07-05

- Fix: `ship_ceremony.py`'s `open_pr` transition, on the front-loaded/existing-PR path, flipped
  the draft PR ready (`gh pr ready`) without pushing the commits accumulated since `start()` opened
  it — so CI could validate a stale HEAD while real work sat unpushed. It now pushes the branch
  first, via a shared `_push_branch` helper also used by the `commit` transition (#478).

## [0.54.2] - 2026-07-04

- Fix: `ship_ceremony.py`'s `request_review` transition always failed (`gh pr edit --add-reviewer
  @me` is not a valid login for the `requestReviewsByLogin` mutation). It is now a deliberate
  no-op — this repository has exactly one human maintainer, who is also the sole author of every
  ceremony PR, so there is no one else to request review from (#477).

## [0.54.1] - 2026-07-05

- Reformat CHANGELOG version headings to the fleet's canonical grammar (bracketed version,
  hyphen-minus date) as part of the release-surface single-source generator work (#429).

## [0.54.0] - 2026-07-05

### Feat: ship_ceremony.py — resumable ship-ceremony transition primitive (#345)
- New `scripts/ship_ceremony.py`: an explicit, ordered transition table
  (`commit -> open_pr -> request_review -> merge -> checkout_main -> pull -> branch_delete`),
  resumable across process restarts by re-reading the governing issue's saga tick each
  invocation. Each transition records a local `CeremonyTier` reversibility tag
  (`reversible` / `additive` / `always_operator`) — a small local registry, not a reuse of
  `reversibility_certificate.py` (that module's own scope excludes repo-level git/merge ops).
- `saga.py save` gains `--ceremony-transition` / `--ceremony-tier` (new `CEREMONY_TIERS`
  constant); ceremony state rides the existing work-thread saga tick, no second store.
- Two entry points share the implementation: `/work`'s PR-ready flow (section 5.4 no longer
  hand-drives raw `gh pr create` / `gh pr merge` / cleanup commands) and a new local
  (repo-scoped) `git ship` alias, installed/uninstalled by the primitive itself — never a
  real git hook, so merge/PR-open/review-request stay explicitly operator-confirmed.
- A front-loaded `ship_ceremony.py start` mode, offered right after `/work`'s Phase 1.4 saga
  mint, pushes the branch and opens a draft PR carrying the plan link immediately; the later
  `open_pr` transition detects it and flips it ready instead of opening a second PR.
- Decision record: `docs/engineering-journal/DECISIONS.md#ship-ceremony-primitive-345`.

## [0.53.0] - 2026-07-04

### Refactor: tier palette re-exported from fleet-core through the vendored fleet-commons shim (#463)
- `execution_spec.py` now loads `MODELS` / `EFFORTS` / `_CHEAP_MODELS` / `ENGINE_INTENTS` through
  the vendored `scripts/fleet_commons_shim.py` (byte-identical to fleet-core's canonical copy,
  drift-guarded in CI) and re-exports them under their existing names — intra-saga importers and
  the existing suite are untouched. `PASS_RULES` stays saga-local (refute-N vocabulary, not tier
  vocabulary). Vocabulary content and ordering are unchanged; the ordering contract is documented
  at the canonical home (`fleet-core` 0.1.0, DECISIONS `{#fleet-commons-mechanism-463}`).

## [0.52.0] - 2026-07-04

### Feat: gate-divergence telemetry — rubber-stamp rate for operator gates (#399)
- New `gate_divergence` full-snapshot list field on the `Saga` envelope, sibling to
  `gate_verdicts` — each entry records a gate id, the offered default/recommendation, the
  operator's actual answer, a divergence bit, and (when available) the offer-to-answer latency.
  Entries are base64-wrapped JSON blobs, pipe-joined (KTD1): `gate_verdicts`' colon convention is
  safe only because its `state` is a closed 6-value enum, but `gate_divergence`'s `answer` field
  is arbitrary `AskUserQuestion` free text, so a raw pipe-joined blob could be corrupted by a
  literal `|` in an answer — base64 makes the encoding safe against that regardless of content.
- New `plugins/saga/scripts/gate_divergence_reader.py` (modeled on `override_rate_reader.py`'s
  R12 house pattern) reports a per-gate-id rubber-stamp rate, interaction count, and mean
  latency, with the same zero-data "no data yet" contract; read-only.
- `/retro` Phase 1.6a runs the new reader read-only alongside the existing R12 override-rate
  reader and includes its output in the evidence block.
- Instrumentation notes added at the 5 `AskUserQuestion` gate sites currently offering a
  recommendation or pre-selected default (`brainstorm`, `founder-review` — 2 distinct gates,
  `investigate`, `loop`, `outcome`); see
  `plugins/saga/references/gate-divergence-instrumentation.md` for the convention and `gate_id`
  naming.
- This is a measurement facet only: it does not change what any gate does, does not add new
  gates, and does not itself widen any autonomous-progression allowlist.

## [0.51.0] - 2026-07-03

### Feat: board↔saga reconciliation on resume — detect drift over the /outcome board-sync ledger (#295)
- `/outcome` gains **reconcile-on-wake**, the companion to #279's autonomous board-sync writer.
  #279 drives and records autonomous board writes but never re-reads the live board, so an
  outside writer (operator, CI, a review agent) who changes a saga-owned board field while saga
  is at rest was never noticed — and a recorded idempotency key made the next tick *skip* the op,
  so the drift persisted silently forever. Reconcile closes that loop.
- New `outcome reconcile <id> [--resolve <drift-id> --action accept-board|re-assert|hold]` verb,
  and `advance --autonomous` now **detects drift before any board write**: a detected drift
  drift-holds only the affected issue's ops (`{status: drift-hold}`) while other leaves proceed
  (KTD3, not gate-all), and drift/recovered records ride `AdvanceResult.drift`.
- Detection is pure classification over three per-issue views: **asserted** (latest of ledger
  write record + reconcile-override, KTD5), **expected** (recomputed from `derive_states` →
  `_candidate_ops` → the schema status map, so a landed-but-unrecorded write is reconciled by
  recomputation with zero change to #279's writer, KTD1), and **live** (`outcome_github.board_status`
  + `issue_close_info`). Scope is ledger-bearing issues only (KTD6) — an untouched issue is never
  probed, so no false positives.
- External closes are **contract-aware + stateReason** (KTD4): a `completed` close that satisfies
  a non-code leaf's completion contract stays the harvester's sanctioned silent path; a
  `not_planned` close, or a close on a code leaf (contract = PR-merged), is drift. An unreadable
  stateReason degrades to today's contract-only behavior.
- Resolution is **HITL behind a replaceable policy seam** (`decide(drift, policy=None)`, R8);
  accept-board / re-assert / hold are recorded as append-only `reconcile-override` records.
  re-assert `authorize_write`s FIRST, then re-drives through the injected `board_writer` — never a
  direct gh call (R9). No new autonomous writer, no new persistence, no mission-control change.
- New reads `outcome_github.board_status` (via `gh issue view --json projectItems`) and
  `issue_close_info` (state/stateReason + best-effort close author from the REST events endpoint);
  both mirror `issue_state`'s never-raise degrade-safe contract. `issue_state` is untouched.
- `plugins/saga/references/outcome-spec.md` documents the reconcile-on-wake contract, the
  saga-owned field class, and the drift-hold semantics.

## [0.50.0] - 2026-07-03

### Fix: verify-panel reconciliation recomputes over reporting verifiers, not declared n (#293)
- A runtime-missing verifier (a `null` verdict slot from a skipped or terminally-errored
  `agent()` call) was previously counted as "did not refute" while the pass-rule threshold
  stayed fixed at the declared panel size (`⌈n/2⌉` majority / `n` unanimous) — masking genuine
  majority refutations, the unsafe direction, across all three emission sites
  (`_emit_thunk`, `_emit_verify_loop_singleton`, `_emit_verify_panel`).
- The three sites are consolidated into one shared `_emit_panel_reconciliation` helper
  (mirroring the `_verifier_agent_opts` single-source precedent), which now records which
  verifiers reported vs. went missing (by index), recomputes the threshold over the reporters
  (`majority`: `max(1, ⌈k/2⌉)`; `unanimous`: `max(1, k)`), and logs an UNDER-STRENGTH marker
  when the reporting count falls under a baked `⌈n/2⌉` quorum floor of the declared `n`. A
  refutation over reporters still throws/retries regardless of under-strength — the floor only
  annotates the accept path, so a small quorum disagreeing is never silently suppressed.
- **No behavior change when every verifier reports**: the recomputed expressions are
  arithmetically identical to today's fixed threshold in the all-report case (`k = n`).
- `plugins/saga/references/execution-spec.md` documents the throw consumer (not `log()`-only),
  the recompute table, the quorum floor, the static-vs-runtime two-kinds boundary, and the
  known no-verifier-timeout residue (workflow scripts have no timer primitive).

## [0.49.2] - 2026-07-03

### Fix: documented fallback + registration drift guard for `saga:readonly-verifier` (#325)
- `saga:readonly-verifier` is mandated by `CLAUDE.md` and `sandbox-spawn-sites.md` for every
  ad-hoc verify/review-class spawn, but a session whose plugin roster predates the agent's merge
  (#287/#320) cannot resolve it — the spawn hard-fails with no documented degrade path. Root cause
  confirmed at plan time: a live spawn in a fresh session resolved and ran successfully, so this is
  environmental staleness, not a registration defect.
- `sandbox-spawn-sites.md` gains a two-step fallback ladder: `Explore` + `isolation: "worktree"`
  first (structurally omits `Edit`/`Write` while keeping `Bash`, preserving the read-only axis by
  tool omission), then `general-purpose` + worktree + an explicit read-only prompt instruction only
  if `Explore` is also absent. `CLAUDE.md`'s ad-hoc spawn rule now points to it.
- New `tests/test_agent_registration_drift.py` pins the repo-side preconditions of
  discoverability: agent frontmatter `name:` matches its file stem, `execution_spec.py`'s
  `READONLY_VERIFIER_AGENT_TYPE` matches the on-disk agent, every spawn-context
  (`subagent_type`/`agentType`) `saga:<name>` reference resolves to a real agent file, and the
  fallback section is documented. Scoped to spawn-context lines specifically — a bare
  `saga:<name>` grep would false-positive on skill mentions like `/saga:work`, which share the
  same namespace.

## [0.49.1] - 2026-07-03

### Fix: `/outcome` autonomous board-sync schema-resolves status instead of a hardcoded literal (#326)
- `outcome_board_sync._candidate_ops` mapped every `ready`/`dispatched` leaf state to a hardcoded
  `"In Progress"` — a campps-workflow value with no meaning on the operations/asgard `intent_flow`
  board (`Idea → Shaping → Ready → Active → Verify → Done`), where the autonomous write failed
  loud and repeated. Now resolves `ready`/`dispatched` from mission-control's `sdlc-schema.json`
  `saga_lifecycle.phase_board_map` for the target project — correct for every board, and
  decoupled from any future ladder change.
- `reconcile_board` and `outcome.advance` gain a `project` parameter (default `"operations"`),
  threaded to both the board writer and the status resolver so they can never disagree about
  which board they're targeting. Resolution is lazy (attempted only when a leaf is actually
  `ready`/`dispatched`) and, on failure (missing schema, unknown project), fails loud and
  retryably per-op — no ledger key written, so the next tick re-attempts — while the coalesced
  progress comment for the same leaf still posts.
- **Behavior change:** on `campps`, a `ready` leaf now resolves to `"Committed"` instead of
  `"In Progress"` — the schema-correct value for that board's `campps_initiative` workflow.
  `dispatched` on campps is unchanged (`"In Progress"`).
- `done` (`SUB_ISSUE_CLOSE`) and the deferred no-op terminals (`blocked`/`failed`/`rejected`/
  `stalled`) are unchanged.

## [0.49.0] - 2026-07-02

### Artifact-pointers saga envelope field (#291)
- New `artifact_pointers` field on the `Saga` dataclass and `FRONTMATTER_FIELDS`, beside the
  existing `review_paths` block (`saga.py:192-195/253-254/274-275`), plus an `--artifact-pointers`
  flag on the `save` subparser wired into `_build_save_saga` (beside `--review-paths`,
  `saga.py:1218-1219/1280`). Absent field round-trips byte-identical on existing sagas.
- Lets a saga record typed artifact pointers (git-object diff pointers, content-addressed store
  pointers, or symbol pointers — see team-execution 2.8.0) so spawned team-execution agents can
  dereference stored artifacts the saga points at instead of receiving them inlined (KD5).
- `/resume` now **consumes** the field: a restored tick's `artifact_pointers` are dereferenced via
  `artifact_pointer.py deref` to recover the exact artifact bytes (fail-closed on
  `POINTER_HASH_MISMATCH` / `POINTER_STALE`), closing the producer+consumer dead-wiring loop
  (LEARNINGS `{#dead-wiring-needs-producer-and-consumer}`). The field was producer-only before this.

## [0.48.0] - 2026-07-02

### Team-spawn residency guard (#289)
- New warn-only `PreToolUse` hook, `team_spawn_residency_hook.py`: when a team-execution
  reviewer or tester is spawned (`Agent` in this harness, `Task` on stock Claude Code) without
  the named-persistent-teammate shape S-1 (#275) mandates, emits a one-line
  `additionalContext` advisory pointing at spawning with `name` for `SendMessage`
  re-addressability. Never blocks, denies, or mutates the spawn.
- Trigger set (18 agents: 10 reviewers, 8 testers) is parsed fresh from
  `reviewer-registry.md` / `validator-registry.md`'s `## Testers` section on every
  invocation — no materialized manifest to drift. Scanners, monitors, and `deploy-watcher`
  are excluded.
- Registry directory resolved via a four-step chain (dev-repo sibling → versioned-cache
  install, reading the active version from `installed_plugins.json` with a max-semver glob
  as last resort → `CLAUDE_PROJECT_DIR` → bounded cwd-ancestor scan) so it resolves correctly
  under both the dev-repo layout and a marketplace-installed versioned cache.
- Registered as a third `PreToolUse` entry (matcher `Agent|Task`) alongside the existing
  `Edit|Write|MultiEdit` and `Bash` entries.

## [0.47.0] - 2026-07-02

### Capability-scoped agent sandbox (#287)
- `execution_spec.py` / `outcome_spec.py`: new optional two-axis `sandbox` envelope on `Unit`/`Node`
  — `mutation_policy` (read-only | read-write) × `workspace_isolation` (ambient |
  disposable-worktree | owned-worktree), with named profile shorthand (`read-only-verify`,
  `sandboxed-mutate`) that expands at parse. Absent ⇒ ambient × read-write (existing specs
  round-trip byte-identical).
- New `plugins/saga/agents/readonly-verifier.md` (read-only toolset: Bash/Read/Grep/Glob, no
  Edit/Write). All three verifier-emitting sites now emit `agentType: "saga:readonly-verifier"` +
  `isolation: "worktree"` unconditionally (KTD6), collapsed into one `_verifier_agent_opts` helper.
- Per-backend enforceability matrix (`SANDBOX_ENFORCEABLE_BY_BACKEND` +
  `unenforceable_sandbox_axis`): a restrictive sandbox a backend cannot enforce HALTS (never
  downgrades). `team_emitter.emit` raises `SpecError` at authoring time (KTD3);
  `outcome_dispatcher.dispatch` probes the matrix into an axis-naming `HaltReceipt`; unlisted
  backends (fork/subagent/goal/manual) default to halt (R4).
- External write-ceiling lift (`engine_dispatch.py`): a `sandboxed-mutate` agy unit ⇒
  `mode: "patch-only"` + `write_set` from the unit's files; a `sandboxed-mutate` codex unit HALTS
  (no write adapter). Default/read-only is byte-identical. The declared sandbox is recorded as
  optional `attribution.sandbox` on the provenance manifest (no `saga.manifest.v1` bump).
- New `plugins/saga/references/sandbox-spawn-sites.md` inventory + ad-hoc spawn rule + `CLAUDE.md`
  pointer; four verify/review skills (code-review/qa/investigate/resume) name the read-only
  verifier + worktree isolation.
- New tests: `tests/test_sandbox_clobber_contained.py` (a real disposable worktree contains a
  `git checkout` clobber; the primary tree's uncommitted work survives), plus
  `tests/test_sandbox_spawn_sites.py` and sandbox coverage across the spec/emitter/dispatch suites.

## [0.46.0] - 2026-07-02

### External-engine workers — plan-time tier recommendation + resolution preview (#318)
- `execution_spec.py`: new optional `Unit.engine_intent` (`offload` / `second-opinion`, valid only
  alongside `engine`/`capability`, defaults to `offload`) carries the KTD2 delegation intent that
  drives a team-execution chaperone worker's tier recommendation.
- `segment_units()`: an engine/capability unit now gets its own resident boundary
  (`worker-<engine>` / `worker-<capability>`, keyed on the bare engine id, not the full
  engine/variant selector) instead of grouping purely by file path — it never merges with a plain
  Claude segment or a different engine/capability, regardless of adjacent file paths.
- `team_emitter.py`: the `### Workers` table gains Engine/Intent columns rendering the new
  segmentation (`cap:<key>` for a capability route, `—`/`—` for Claude segments); new column-shape
  test oracles (none existed before this change).
- `/plan` SKILL.md's tier-derivation table gains the KTD2 intent→tier recommendation rows and the
  plan-time capability-resolution preview ("resolves today to `<engine>/<variant>`") that a
  team-execution chaperone's `substituted-engine` disposition compares the run-time resolution
  against.

## [0.45.0] - 2026-07-01

### Evidence / provenance manifests — verified-vs-adjudicated record per delegated output (#285)
- `provenance_manifest.py`: frozen-dataclass envelope (`schema: "saga.manifest.v1"`) with
  `output_completeness` (declared vs produced) and `claim_provenance` (producer-claimed vs
  Claude-adjudicated) subrecords, pure `is_parroting`/`mismatch_reason_for`/`validate` predicates,
  no verdict field, no I/O at import (R1-R9, R12, R18, R20).
- `manifest_store.py`: git-common-dir carrier at `<git-common-dir>/saga-manifests/<saga-id>/
  <execution-id>.json` (reusing `resolve_common_dir`), a typed `manifest_ref` payload-key helper for
  outcome leaves, and CLI `write`/`read`/`list`/`record-completeness` entry points (R19, R3, R10, R13).
- `outcome_orchestrator.py`: `harvest` attaches the advisory `manifest_ref` pointer to a leaf's
  CompletionEvent payload when its dispatch recorded a provenance manifest (saga id = outcome id,
  execution id = subplot id; canonical store layout only — advisory, R8).
- `engine_dispatch.adjudicate_manifest` keys adjudications by `(claim text, source_ref)` so two
  claims sharing text but grounded in different sources adjudicate independently.
- `manifest_store._safe_name` delegates to `outcome_store._safe_name` — one implementation of the
  traversal guard, translated into `ManifestStoreError`.
- `engine_dispatch.py`: new `build_dispatch_manifest`/`record_dispatch_manifest` let the driving
  session persist an envelope-backed manifest for a dispatch through `manifest_store` (`dispatch()`
  itself does not auto-emit); `satisfy_gate()` now enforces R11 — a gated verdict cannot persist
  unless gate-relevant claims are Claude-adjudicated.
- `completeness_gate.py`: renamed `check_manifest` → `check_required_keys` (no external callers) to
  free "manifest" for the new envelope; `classify()` behavior unchanged.
- `manifest_reader.py`: advisory reader (parroting count, disposition rate, adjudicated-verified
  ratio) wired into `/code-review`, `/qa`, and `/retro` as a non-blocking signal (R7, R8, R15, R16,
  R18).
- `saga-spec.md` gains the manifest contract section (envelope/subrecord field reference + R17
  producer/reader matrix); a guard test enforces no manifest field ships without a live-or-scheduled
  reader.
- Enabled `fable`/`xhigh` execution-spec tiers (#285 U0) so judgment-heavy units (schema, gate
  semantics) can run on Claude Fable 5 xhigh.

## [0.44.0] - 2026-07-01

### External-engine capability routing — right engine, effort, protocol per task (#283)
- New saga-owned registry + resolver + dispatch adapter mapping a logical capability or an explicit
  engine to `{engine, effort, protocol}` and dispatching external LLM engines (Codex via
  `codex:codex-rescue`, Gemini via `agy:delegate`) as gated generators / advisory reviewers /
  non-gated workers, with Claude as verifier-of-record on every gated decision (R13).
- `engine-registry.yaml` (editable data, R4): per-variant capability profiles, prompting protocols,
  invocation recipes, a `cost_speed_rank` tie-break key, context-window limits, and per-row source
  attribution. Seeded 2026-06-27 for codex/gpt-5.5-{high,xhigh} and agy Gemini 3.5 Flash / 3.1 Pro.
- `engine_resolver.py`: capability-XOR-engine resolution (advisory/dispatch modes), role_kind-gated
  fallback (worker/generator) vs halt (reviewer/panel), byte-verbatim payload assembly (R9/R11),
  context-window fitness halt (R25), preflight availability, and `resolve_role` panel expansion (R16).
- `engine_dispatch.py`: an `AdvisoryEvidence` result type whose `satisfy_gate` structurally requires
  Claude verification before any gated return; failure statuses -> halt + provenance note (R24).
- execution_spec Units gain optional mutually-exclusive `engine`/`capability` selectors (backward
  compatible); the emitter routes engine-bearing units through an external-engine dispatch marker.
- `/doc-review` gains an opt-in cross-family external-reviewer panel. Records the binding
  "external engines are never gatekeepers" decision (DECISIONS.md).

## [0.43.0] - 2026-06-30

### PreCompact spore — re-ground the continuing session on structured facts (#281)
- New two-hook "spore" that guards the mid-run auto-compaction boundary: a `PreCompact` hook freezes the
  active saga box + the OutcomeOrchestrator DAG frontier (derived-on-read via `outcome.status`) to a
  session-keyed, worktree-stable cache `<git-common-dir>/saga-spores/<session_id>.json`; a separate
  `SessionStart(source=compact)` hook reads it, unlinks before emitting (at-most-once), and re-injects it
  as a self-describing `additionalContext` block so the continuing session re-grounds on structured
  facts, not the lossy prose summary.
- New `saga_spore.py` core (pure, offline-testable): active-saga resolution, leaf-id + bounded-scan
  outcome discovery (never guesses on ambiguity), DAG freeze, deterministic ≤9k serialization with the
  ready frontier **never dropped** plus a counted-drop pointer, and the dump/load seam with a
  `saga_id` + repo-root mismatch guard.
- Both hooks degrade silently **and** on a hard 1.5s wall-clock deadline (SIGALRM) — compaction is never
  blocked or stalled. The existing `/resume` path, tick chain, and `state.json` model are untouched
  (additive cache; the spore is the anchor, never the authority).
- Hooks registered in `hooks.json`: `PreCompact` (matcher `auto|manual`) + a sibling `SessionStart`
  (matcher `compact`, separate from the existing `startup|resume` entry).

## [0.42.0] - 2026-06-29

### Reversibility/idempotency certificate + autonomous `/outcome` board-sync (#279)
- New `reversibility_certificate.py` — one pure-data authority that declares each board op's
  reversibility facts and answers a single `authorize_write` verdict (AUTHORIZED / GATE, **default
  GATE**) over a closed, enumerated `OpKind` allowlist with declared inverses. Merge, deploy, and
  parent-issue-close (`ALWAYS_OPERATOR`) are never authorized.
- Subsumption: `degrade_decision`'s `had_side_effect → HALT` and `outcome_projection`'s parent-close
  are now derived from the certificate — behavior byte-identical (proven by a 672-combination
  equivalence sweep), with the certificate as the single source of both reversibility facts.
- New `outcome_board_sync.py` — the first autonomous consumer. `outcome advance --autonomous`
  reconciles each leaf's derived state to reversibility-authorized board writes (set-field "In
  Progress", sub-issue close, label add/remove, one coalesced progress comment), idempotent on a
  **separate** write-once board-sync ledger, with bounded retry + fail-loud surfacing. The default
  `advance` performs no board writes; GATE'd ops surface to the operator, never silently skip.
- Pairs with mission-control 2.4.0 (the new issue-write verbs the consumer drives).

## [0.41.0] - 2026-06-29

### Operator gate-status card (#278)
- New `status_card.py` — one shared, derived-on-read glyph-card renderer that is the single emitter of
  operator-facing status across all five saga surfaces. Constant-size, position-stable; every
  determinable cell is traceable to evidence via an indexed footer, and no operator-writable status
  field exists. Two archetypes (one renderer): gate-sequence and summary-projection (U1).
- A frozen six-value wire-state enum (`done` / `in-progress` / `blocked` / `failed` / `halted` /
  `not-reached`) with an additive operator-label + glyph display map and a raw-string fallback; an
  undeterminable cell renders *unknown* with no ref — never a guessed glyph (U1).
- `gate_verdicts` capture in the saga work-state envelope: a full-snapshot `list[str]` of
  `"gate:state:ref"` entries plus a repeatable `--gate-verdict` CLI flag and a `parse_gate_verdict`
  helper (splits on the first two colons so colon-bearing refs survive; validates the six gate
  states) (U2).
- Per-surface projections: `project_work` / `project_code_review` / `project_qa` (gate-sequence) and
  `project_outcome` / `project_resume` (summary-projection). `/work`'s Tests cell derives from
  `gate_verdicts`; `/outcome` re-renders `outcome_projection.project()` exactly (no second
  projection); `/qa` renders a failing verdict unmistakably (U3/U4).
- Routed all five surfaces' status-summary emissions through the card while keeping per-finding
  evidence as drill-down detail; `/work` now writes `gate_verdicts` on its test gate (U5).

## [0.40.0] - 2026-06-29

### Silent-omission completeness gate (#277)
- New `completeness_gate.py` oracle — the single source of omission semantics: a `FailureClass`
  enum (`missing-output` / `malformed-output` / `verifier-disagreement`, extensible), pure check
  predicates (presence, truncation, fan-out count, manifest-key), `classify()`, and a `--self-test`
  CLI that plants the four canonical omission fixtures (U1).
- `emit_workflow_script` now injects a single `__gate(result, opts)` helper (porting the oracle
  semantics to JS) and a guard call after every unit-result `agent()` site — the singleton and each
  `parallel` var — so an omission HALTS the workflow instead of passing `null`/partial downstream;
  the verify-panel verifier agents are excluded (U2).
- A refuted verify panel now HALTS with a typed `verifier-disagreement` throw instead of
  `log()`-and-proceed (R4), plus an opt-in bounded iterate-to-consensus override on `Verify`
  (`iterate_to_consensus` + `max_iterations`, `< 1` rejected at validate) (U3).

## [0.39.0] - 2026-06-28

### Worker×model cache scheduling (#275)
- Add a `files` field to `Unit` and a pure `segment_units()` that derives resident-worker
  segments — contiguous plugin-directory grouping, upgrade-only segment tier, and collapsed
  segment-level dependencies — without mutating the shared `ExecutionSpec`.
- `team_emitter` now emits one worker row per resident-worker segment
  (`Agent | Units | Tier | Mode | Depends-on`) instead of one row per unit.

## [0.38.0] - 2026-06-26

### OutcomeOrchestrator (outcome-orchestration feature — built across U1–U11, co-equal at release; the U11 feature-flip ships it)

- **U11** — **Feature flip + integration gate.** Advertise the complete `/outcome` surface and ship all
  34 requirements: saga metadata (`plugin.json` description + `marketplace.json`) advertises the outcome
  coordinator; the README + `docs/commands.md` + `docs/README.md` + `docs/boundaries.md` command counts
  move to **20 files / 19 routable** (the `/outcome` 19th routable); the Command Matrix visual gains the
  `/outcome` coordinator card; `tests/test_outcome_integration.py` drives a full outcome end-to-end
  through the **production** `advance` wiring (start → approve → **dispatch** → GitHub-canonical harvest →
  auto-merge → liveness → cost rollup → report → projection) on a DAG, proving the U1–U10 units compose
  (the dispatch seam is load-bearing — completion only flows after a leaf is dispatched). team-execution
  metadata already carries no tmux/setup (U4's R8 reshape). Released at saga 0.38.0 (the version-triad:
  `plugin.json` == `marketplace.json` == this heading).
- **U11 (R26/R27 persistence — closed the ship-gate P0).** `outcome.commit_spec` **commits + pushes the
  canonical spec to the outcome's own branch** (`outcome/<slug>`, **refuses on `main`/`master`** — R26
  "not main mid-run"), so a **different machine reconstructs the whole outcome by pulling the repo** then
  re-harvesting completion from GitHub, with no dependence on the local cache (R27/F5). Exposed as
  `/outcome commit [--push]` and `/outcome advance --persist` (commit each tick on an unattended run); the
  *cadence* is operator/`/loop`-driven, the *mechanism* now ships. `save_spec` no longer falsely claims to
  persist (it writes the working tree; `commit_spec` does the git write).
- **U11 (auto-merge dependency gate).** `process_merge_queue` now merges a code leaf only once **all of
  its `depends_on` are success-complete** — GitHub's mergeability does not model the outcome DAG, so a
  coincidentally-clean PR for a leaf with an incomplete (especially non-code) upstream is no longer
  squashed out of dependency order (R12 + the DAG).

- **U1** — Add the canonical outcome spec + DAG validator (`scripts/outcome_spec.py`,
  `references/outcome-spec.md`, `tests/test_outcome_spec.py`): a JSON outcome document
  (superset-in-pattern of `ExecutionSpec`) modelling a concurrent DAG of subplots with a per-node
  operational state machine in data (KTD2 — `state`/liveness/negative-state hooks/`child_spec_ref`),
  the Kahn `dependency_layers` + `ready_frontier` frontier engine, and a `validate` that rejects
  duplicate id / self-dep / cycle / missing dep / invalid `child_spec_ref` (incl. collision with a
  sibling `subplot_id`) **before any dispatch** (R20, R31 validation). Disconnection is a non-fatal
  advisory (`structural_warnings`), not a hard failure — independent workstreams under one objective
  are legal; the "forgot to wire it in" smell (R33) is surfaced consistently for a lone isolate and a
  multi-node island. Fail-loud `from_dict` coercion (a string `depends_on` is rejected, not
  char-iterated; `bool`/float liveness budgets and non-positive `spec_revision` are rejected);
  `redirect_dependency` is atomic (a rejected redirect never advances the revision or decision-trail,
  R26 fidelity). Pure functions, deterministic JSON round-trip, no I/O at import. (U1 covers the
  structure facet of R26 and the spec-container slice of R1/R2/R21/R33; the cross-facet machinery —
  GitHub completion, sub-issue projection, the coordinator runtime, decompose/promote — lands in
  later units.) Survived a 3-lens adversarial-verify pass (validator-bypass / round-trip / requirements
  honesty); the P1 redirect-atomicity + P2 string-edge/orphan-rule defects it surfaced are folded in.
- **U2** — Add the outcome **store** (`scripts/outcome_store.py`, `tests/test_outcome_store.py`,
  `tests/test_outcome_replay.py`): the git-common-dir cache + coordination substrate beside the
  canonical spec + GitHub (KTD15). Resolves its root from `git rev-parse --git-common-dir` so the cache
  is shared across every worktree but never committed and **deleting it loses no canonical state**
  (R27). Primitives: immutable write-once **completion events** (one file per leaf per attempt via
  `os.link`; idempotency-key dedup with a genuine new-attempt retry proceeding, R9/R10/R28); atomic
  `os.replace` writes + malformed-file **quarantine** (no torn read, R30); an append-only **replay
  ledger** (`O_APPEND`) tolerating a torn trailing line, with `replay_pending` pairing intents to
  commits so a crash after a side effect but before its commit re-drives idempotently (R30); lease-based
  **coordinator + per-subplot dispatch locks** (a second `advance` no-ops on a held lease, reclaims a
  stale one; no duplicate dispatch, R13); and an **offline queue** with the R34 policy made concrete
  (GitHub wins for completion → a server-superseded queued write is dropped; retry exhaustion pages the
  operator). Dependency-injected `runner`/`now` → unit-testable offline with no real git repo or wall
  clock; no I/O at import. (U2 ships the cache/durability facets of R9/R10/R13/R14/R27/R28/R30/R34; the
  parent-owned barrier predicate lands in U5, real GitHub/export wiring in U5/U6/U7.)
- **U3** — Add the thin `/outcome` command + skill + the reconcile engine (`commands/outcome.md`,
  `skills/outcome/SKILL.md`, `scripts/outcome.py`, `tests/test_outcome_command.py`): the
  **OutcomeOrchestrator** coordinator over a DAG of leaf sagas. A **level-triggered reconcile loop**
  (R29) — each `advance` tick reconstructs live state from the durable store, dispatches the ready
  frontier to executors via an injected dispatcher, and pages only on exceptions; it holds no
  authoritative in-memory DAG (crash-tolerant, host-agnostic). Enforces two invariants structurally:
  the **coordinator routes, never executes** (R2/R3 — `advance` only dispatches + harvests, never runs
  a leaf's work in-process; the record-only default dispatcher proves it, real backends arrive U4/U9),
  and **status is derived on read** (R17 — node live-state is computed each call from spec + completion
  events + dispatch records, never a stored field). Idempotent (the per-subplot dispatch lock + ledger
  record dedup repeated ticks); a second concurrent `advance` no-ops on the held coordinator lease
  (R13). Thin coordinator verbs only (KTD11/R16): `start` / `graph` / `advance` / `attend` / `resume` /
  `status` / `export` / `import` — `attend` prints the native `/resume <leaf-saga-id>` handoff; leaf
  work stays the native verbs (no `/outcome work`). Ships the R14 export/import portable bundle. Wired
  into the saga docs model + manual card (`/outcome` is in the source but the marketplace version flip +
  advertisement stay deferred to U11). (U3 ships R16/R29 + the dispatch-seam facet of R1/R3; the degrade
  path, real backends, decompose/report/close verbs land in later units.)
- **U4** — Add the backend **dispatcher seam** + make team-execution the first real backend
  (`scripts/outcome_dispatcher.py`, `tests/test_outcome_dispatcher.py`; promotes the by-mode fork in
  `scripts/execution_spec.py`). The single seam every subplot routes through (R5): it dispatches a leaf
  to its backend — minting a leaf saga id + a `/resume` **return channel** (the R9 re-entry token out) —
  or, when the chosen backend cannot run, emits a **visible HALT-not-degrade receipt** (`BackendHaltError`
  + `HaltReceipt`) rather than silently substituting a lesser backend (R5/R23). **team-execution is the
  first runnable backend** (R6); the rest of the menu (fork / subagent / cc-workflows-ultracode / `/goal`
  / manual) HALTs until U9, never a silent inline fallback. Wires the existing `team_emitter` as the
  **third leg of `recompile_for_tier`** (`team-execution` mode now recompiles to the `## Team Structure`
  markdown protocol, not the inline baseline — R5). The **production `/outcome advance` CLI now routes
  through the real seam** (`make_dispatcher`); the U3 record-only dispatcher is the test/skeleton fallback
  only. A HALT is handled **per leaf** in the reconcile loop: the leaf's dispatch lock is released (so a
  re-tick re-surfaces it rather than a leaked lease masking it for the TTL), the receipt is recorded in
  the ledger and returned in `AdvanceResult.halted`, and reconcile **continues** to other runnable leaves
  — one unavailable backend never starves the frontier and a HALT is never silently substituted. (U4
  ships R5/R6-first-backend + the R23 HALT receipt; the operator-presence degrade-vs-halt *decision* and
  the full backend menu land in U9.) The destructive **R8 reshape of team-execution** ships in that
  plugin's own 2.2.0 bump (see `plugins/team-execution/CHANGELOG.md`): tmux + `/team-setup` removed,
  validator-state check re-homed.
- **U5** — Add the **completion barrier** + GitHub-canonical completion read + harvest + cascade
  (`scripts/outcome_orchestrator.py`, `scripts/outcome_github.py`, `tests/test_outcome_completion.py`).
  "Done" is a **parent-owned barrier predicate over the returned evidence** (R9), never a child's
  self-report, HALTing on an unmet contract. Per-subplot completion **contract** (R11): a **code** leaf
  is done only when its **PR reads merged**; a **non-code** leaf when its **tracking sub-issue reads
  closed** (the cache-less-reconstructable canonical marker) or, untracked, a `canonical`-flagged
  completion event (cache-resident only — a wipe loses it; tracked work uses the issue path); a
  **child-outcome** node (`child_spec_ref`, KTD10) only when the child's terminal state reads
  successful — the production harvester **recurses** into the child outcome (cycle-guarded) to read it.
  `outcome_github` is the read-only PR/issue-state primitive (merged/closed/open) — **degrades to
  `unknown` on any `gh` failure, never a false completion** (R34); the merge/close *actions* are U6.
  `harvest` runs the barrier each tick and **materializes** GitHub-canonical completions as success
  events in the store (at a fresh attempt slot, so a prior negative terminal never collides), unlocking
  the next Kahn layer (R10) and surviving a cache wipe (re-derived from GitHub, R27). `blocked_subtree`
  is the R22 cascade — only a block's downstream subtree pauses, independent siblings keep running.
  **Wired into the production `/outcome advance` CLI** via an injected `harvester` (`AdvanceResult.harvested`),
  so a merged PR / closed issue unlocks dependents in the live loop. (U5 ships the **barrier-predicate
  half of R9** — the re-entry-token-out is U4's dispatch — plus R10/R11/R22 + the R27/R28 completion-read
  leg the U2/U3 honesty passes deferred here; the auto-merge action + negative-state cascade land in U6.)
- **U6** — Add the **auto-merge queue** + GitHub negative terminal states (`scripts/outcome_merge.py`,
  `scripts/outcome_github.py` write side, `tests/test_outcome_merge_queue.py`). A non-gated, clean code
  subplot **auto-merges** (server-side squash) to unlock dependents (R12). Merges are **serialized**, and
  **GitHub is the authoritative atomic guard** (not a local SHA compare): `gh pr merge --squash
  --match-head-commit <head>` is rejected by GitHub if the PR is not mergeable — base moved (`behind`),
  conflict (`dirty`), head moved, or required checks unmet — so a **stale tree can never be squashed**
  (R12/R30). The loop classifies via GitHub's `mergeStateStatus`: `behind` → **rebase (update-branch)
  then re-verify**; `dirty` → **conflict** (fail the leaf back to `work` + page, never a silent skip);
  `blocked` → wait for gates (the CI-green/review evidence is GitHub's own readiness); a rejected squash
  → **reloop**, base churn **capped at 3** → halt + page (no spin). **R34 safe-degrade:** an `unknown`
  merge-state or unreadable base (gh outage) **defers** (`not-ready`) — a gh outage never fails a leaf or
  merges wrongly. **Negative GitHub terminals** (R32): a PR **closed-unmerged** or a **definite-404
  deleted branch** records a sticky `rejected` terminal that **cascades** like a block (R22); an
  out-of-band merge is never double-merged; a `conflict` records a **retryable** `failed` terminal
  (re-enters the queue once /work fixes it — only `rejected`/`stalled` permanently skip). **Wired into
  the production `/outcome advance`** (`merge_processor`, `AdvanceResult.merges`) under the held
  coordinator lease, so it is single-writer **cross-process** too (R13). GitHub ops are an injected
  `MergeOps` adapter → fully unit-testable offline. (U6 ships R12 + R32-PR/branch + R22 negative cascade +
  R30 merge atomicity; the worktree-removed terminal is U7, the degrade decision U9.)
- **U7** — Add **decomposition + in-flight graph editing + the durable per-sub-outcome worktree
  lifecycle** (`scripts/outcome_decompose.py`, `scripts/outcome_worktrees.py`,
  `tests/test_outcome_graph_edit.py`, `tests/test_outcome_worktrees.py`). **Graph editing** (R21/R33): the
  four growth mechanisms — `add_node`/`prune`, `lazy_grow`, `elaborate` (splice a node into sub-nodes,
  inheriting its upstream + rewiring its dependents onto the sinks), `promote` (set `child_spec_ref`,
  rejecting a point-back at this/any **ancestor** outcome — the cross-spec cycle guard U1 deferred) — each
  **atomic** (snapshot → validate → bump revision + decision-trail; a rejected edit leaves the spec
  untouched, R26) and **state-aware**: a **dispatched** node may not be pruned or elaborated (would
  silently discard in-flight work) — a terminal transition must come first (R33). **Orphan
  reconciliation** (R33): a prune drops every edge to the node, **closes its generated sub-issue**
  (injected adapter; U8 produces the ref), and **reaps its worktree** — no zombies. **Draft-then-review
  approval gate** (R20): approval is recorded **per `spec_revision`**, so any structural edit (which bumps
  the revision) **re-closes** the gate — no layer dispatches before the operator approves the current
  frontier's edges. **Worktree lifecycle** (R15): one durable, named, owner-tagged worktree **per
  sub-outcome** (`child_spec_ref` node), **reused across its leaves** (not one-per-leaf); a hard **cap**
  defers past N (never an (N+1)th worktree); heavy installs **shared** across siblings via one
  `shared_install_ref`; reaped on terminal. **git is the liveness oracle** (the U6 lesson): a worktree
  removed **out-of-band** is detected from `git worktree list` and reaches the **defined `rejected`
  terminal** (R32 — the one U6 deferred) that **cascades** like a block (R22); a transient git failure
  degrades to **present** (never falsely terminates a live sub-outcome, R34). Paths are **canonicalized to
  git's absolute realpath form** on both sides (and `--repo-root` is resolved), so a relative or symlinked
  root can never read a live worktree as absent (which would silently break both the cap and R34). **Wired into the production
  `/outcome advance`**: a `worktree_processor` (reap + worktree-removed terminal + provision, under the
  held coordinator lease) and a `gate_factory` (the approval gate), plus new `/outcome approve` / `prune` /
  `promote` verbs (`AdvanceResult.worktrees` / `.gated`). Both `WorktreeOps` (git) and `issue_close` are
  injected → fully unit-testable offline. (U7 ships R13-namespacing + R14-graph-portability + R15 + R20 +
  R21 + R32-worktree + R33.)
- **U8** — Add the **derived-on-read report + attention consolidator + mission-control projection**
  (`scripts/outcome_report.py`, `scripts/outcome_projection.py`, `docs/outcomes/_example-ship-auth/`,
  `tests/test_outcome_report.py`, `tests/test_outcome_projection.py`). **Attention consolidator**
  (R18/AE5/F3): when several leaves need the operator at once, `consolidate()` bubbles them into **one**
  ranked prompt — **type-tier first** (a *gate* = ready-to-ship → an *ambiguity* = needs-a-decision → a
  *failure* = needs-a-fix), then **unblock-leverage** within a tier (the item gating the most downstream
  work first, `len(blocked_subtree)`); each node classified into **one** kind (terminal-negative →
  failure, HALT receipt → ambiguity, gated/risky/destructive + dispatched → gate); a healthy steady state
  consolidates to an empty surface. **Report** (R19/F6): `/outcome report` regenerates
  `docs/outcomes/<id>/report.md` from state — the Mermaid topology, the consolidated prompt, a per-subplot
  state + evidence + cost table, the cost rollup (**rendered when present, "no data yet" when absent** —
  so U8 depends only on U5/U6, **never on U10**, avoiding a U8↔U10 cycle), and the decision trail (the
  "why" for cold re-entry, F5). **Deterministic** (no wall-clock in the body) + **overwritten from
  state**, so it physically cannot drift. **Projection** (R25): `/outcome project` emits the
  mission-control **secondary** portfolio view, **generated** from the spec + store (no operator-writable
  status, R17) and **never auto-closes the parent** (`parent_close = operator-keystroke-only`). New
  `/outcome report` / `project` verbs + a consolidated `/outcome attend` (no subplot → the ranked prompt).
  (U8 ships R17 + R18 + R19 + R25 + AE5 + F3/F5/F6.)
- **U9** — Add the **full backend menu + the presence-conditional degrade policy + leaf liveness**
  (`scripts/outcome_dispatcher.py` extended, `scripts/outcome_liveness.py`, `references/operator-choice.md`
  §8, `tests/test_outcome_backends.py`, `tests/test_outcome_liveness.py`). **Full menu** (R6):
  `resolve_available()` exposes the host-conditional set — the always-available floor (`inline` /
  `team-execution` / `manual`) plus the host-dependent `fork` / `subagent` / `goal` / `cc-workflows-ultracode`
  (off by default; enabled via `--host-capable` / `--workflow-available`). **Presence-conditional degrade**
  (R23/AE1): `degrade_decision` — an unavailable backend **HALTs** when the operator is attending / the
  leaf is guarantee-bearing (`guarantee_tags` or `degrade_policy="halt"`) / it already side-effected (a
  `destructive` leaf), else **degrades one rung** down the `cc-workflows-ultracode → team-execution →
  inline` ladder (recording a visible `DegradeReceipt` surfaced in the report's **Degradations** section)
  when the leaf is autonomous and the operator is away; a backend off the ladder HALTs (no silent
  substitution, R5). **Liveness** (R31): `outcome_liveness.harvest_liveness` reclaims a dispatched leaf
  that breaches its `heartbeat_seconds` / `timeout_seconds` budget as the **`stalled`** terminal (pages
  once, cascades R22); `record_heartbeat` pushes back the deadline. **Frontier-budget + fork-cost levers**
  (R7): `recommend_outcome_backend` downgrades a per-leaf `cc-workflows-ultracode` recommendation to
  `team-execution` on a wide frontier, and `fork_is_cheap` claims the fork lever only when model + system
  + tools match the parent within the cache TTL. **Wired into the production `/outcome advance`**: a
  `liveness_processor` (under the held lease) + `available` / `attending` (`--autonomous`) driving the
  degrade decision in `_reconcile_once`; `AdvanceResult.liveness` / `.degraded`. (U9 ships R3 + R5 + R6 +
  R7 + R23 + R24-telemetry-capture + R31.)
- **U10** — Add **realized economics + the optimize/retro consumers** (`scripts/outcome_costs.py`,
  `skills/optimize/SKILL.md` §Outcome-economics, `skills/retro/SKILL.md` §1.7,
  `tests/test_outcome_economics.py`). **Producer** `record_cost` (a leaf saga reports its realized
  executor / tokens / wall-clock / operator-touches / retries / evidence into the shared store — the
  coordinator never runs the leaf, R3). **Consumer** `rollup` aggregates per outcome (R24): summed
  tokens/operator_touches/retries, `by_executor`, and the load-bearing **DAG-vs-one-thread** answer —
  `wall_seconds_parallel` (the critical path) vs `wall_seconds_serial` (the one-long-thread sum) +
  `beat_one_thread` — the falsifiable cost-vs-operator-time proof. Honest: an empty rollup is **"no data
  yet"** (never a fabricated zero), missing leaves are **counted** (`leaves_with_cost` / `leaves_total`)
  not summed as 0, and cost against a **pruned** subplot is reconciled into **`sunk`** (the pruned-node
  cost reconcile U7 deferred, R33). **Wired** as a `cost_processor` in `advance` that **materializes the
  rollup into `spec.cost_rollup`** (the producer → spec → U8-report edge — no U8→U10 dependency, the
  acyclicity rule). `/optimize` cites the rollup as a portfolio baseline + the override-rate reader;
  `/retro` adds a §1.7 read-only outcome-economics evidence pass. (U10 ships R7 + R24, and fills the U8
  report's "no data yet" cost slot + the U7 pruned-node cost reconcile.)

## [0.37.0] - 2026-06-21

- Document the parallel-layer + refute-N emitter constructs in `references/execution-spec.md`:
  topological-layer parallelism (KTD4) — independent units in the same dependency layer emit as a
  single `parallel([...])` wave; `Unit.verify` (KTD5) — optional refute-N judge-panel with `n` and
  `pass_rule` fields, default `n=3/majority`, hard cap `VERIFY_N_CAP=7`; `pass_rule` vocabulary
  (`majority`/`unanimous`); `/plan` author-validate-approve-persist-emit five-step flow for
  `cc-workflows-ultracode`; spec naming convention.
- Document the `/work` halt-not-degrade guarantee and `orchestration_ref` lifecycle in
  `references/operator-choice.md` §6: a `cc-workflows-ultracode` choice is guarantee-bearing (parallel
  fan-out + refute-N); `/work` halts when the Workflow tool is absent or the spec/ref is missing rather
  than silently substituting inline subagents; `orchestration_ref` points at the **spec JSON** at
  `/plan` time (canonical artifact — the `.workflow.js` is regenerable), then is overwritten with the
  workflow id after `/work` launches; the `saga.py` provenance guard backstops substitution attempts.
- Add `DECISIONS.md` entry `#parallel-refuteN-emitter-plan-work-wiring` covering KTD1-KTD7 rationale
  and the dogfooding fix (auto-derive must not fire on no-orchestration-args ticks).
- Bump saga to **0.37.0** (feature: parallel + refute-N emitter, /plan + /work wiring, provenance guard).

## [0.36.0] - 2026-06-21

- Generalize the stale-main `SessionStart` hook to run in ANY git repo. The hook
  (`plugins/saga/hooks/stale_main_session_hook.py`) is now fully SELF-CONTAINED — it no longer
  depends on the repo-local `tools/stale_main_guard.py` (which remains the repo's manual tool /
  R18 artifact), so the distributed plugin's hook is active everywhere saga is installed (user
  scope), not just this repo.
- Preconditions, each → exit 0 SILENT: CWD is inside a git repo (`git rev-parse --show-toplevel`);
  an `origin` remote exists (`git remote get-url origin`); the default branch is determinable.
- Default-branch detection is GENERIC (never hardcodes `main`): `git symbolic-ref --short
  refs/remotes/origin/HEAD` stripped of the `origin/` prefix, falling back to probing
  `origin/main` then `origin/master` via `git show-ref --verify`.
- Auto-fast-forward when safe (the chosen policy): if the local default branch is behind
  `origin/<default>` AND the current branch IS the default branch AND the tree is clean, the hook
  runs `git merge --ff-only origin/<default>` and confirms. Otherwise (feature branch, dirty tree,
  or a linked worktree) it WARNs only and mutates nothing. `git fetch origin` degrades quietly
  when offline. Always non-blocking (exit 0); emits the standard SessionStart `additionalContext`
  shape only when there is a message.
- Tests (`tests/test_stale_main_session_hook.py`) rebuilt around REAL temp git repos (bare origin
  + clone + advanced origin) — no mocks of git: not-a-repo (silent), no-origin (silent), up-to-date
  (silent), behind-on-default-clean (auto-FF actually moves the branch), behind-on-feature-branch
  (warn only, branch not moved), and a `master`-default repo (detected + handled).

## [0.35.0] - 2026-06-21

- Install the stale-main guard as a `SessionStart` hook (`startup|resume`). New wrapper
  `plugins/saga/hooks/stale_main_session_hook.py` reads the SessionStart payload from stdin,
  resolves the CWD repo root via `git rev-parse --show-toplevel`, and runs the repo's OWN
  `tools/stale_main_guard.py` — surfacing its output as SessionStart `additionalContext`
  (`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`).
- Repo-presence guard keeps the distributed plugin INERT elsewhere: if the CWD is not a git repo,
  or `tools/stale_main_guard.py` is absent at the repo root, the hook exits 0 silently (no
  `git fetch`, no subprocess). Always non-blocking (exit 0); degrades quietly on any error/timeout.
- Wire the new `SessionStart` event into `plugins/saga/hooks/hooks.json` (the plugin's 4th hook).
- Tests (`tests/test_stale_main_session_hook.py`): a fake repo-local guard exercises the wrapper
  end-to-end without any real `git fetch` — repo-without-guard (inert), not-a-git-repo (silent),
  guard-stale (warning reaches `additionalContext`), guard-silent (no output).

## [0.34.0] - 2026-06-21

- Wire the R12 producer path so override-rate telemetry is no longer inert. `saga.py save` gains
  `--orchestration-recommended` and `--orchestration-operator-choice` (both `choices=ORCHESTRATION_MODES`,
  default empty); `_build_save_saga` now sets `orchestration_recommended` from the flag and
  `orchestration_operator_choice` from its flag, defaulting to `--orchestration-mode` (the operator's
  chosen backend IS their choice). Backward-compatible: absent flags → `""`; older sagas still load.
- `/plan` (Phase 5.3) and `/work` (Phase 1.4) now instruct recording `--orchestration-recommended`
  alongside `--orchestration-mode` on each orchestration decision, so `override_rate_reader` sees real
  recommended-vs-chosen data instead of "no data yet".
- Tests: end-to-end producer→consumer test drives the real `saga.py save` twice (an override + a match)
  then asserts `override_rate_reader` reports non-zero data; a MultiEdit invalid-JSON case for the
  marketplace validation hook.

## [0.33.0] - 2026-06-21

- Add R12 override-rate reader (`scripts/override_rate_reader.py`): scans saga envelopes and
  surfaces override-rate, over/under-tier direction, and budget-exhaustion (capability
  degradation) signals. Zero-data reports "no data yet" (no divide-by-zero). Read-only; CLI
  supports `--json` for machine output.
- Wire the reader into `/retro` Phase 1.6: a dedicated evidence-gathering step runs the reader
  and includes its output verbatim; reference added to the SKILL.md reference-files section.
- Signal accrues post-merge as `/plan` records recommended vs operator-chosen backends (U3);
  this surface enables evidence-driven default re-weighting (R12's intent).

## [0.32.0] - 2026-06-21

- Capability-portable degradation (R11 / U12): every authored plan now carries a runnable
  inline/serial **baseline** alongside the dynamic-workflow script, so a plan executes on ANY
  host. Add `execution_spec.emit_inline_baseline()` (the always-runnable floor — no Workflow
  tool, no `agent()` harness; preserves every unit and its per-unit `{model, effort}` tier and
  enumerates fan-out targets) and `execution_spec.recompile_for_tier()` (re-emit the same spec
  for a possibly-downgraded orchestration tier). New `execution_spec.py baseline` CLI subcommand.
- Add `lifecycle_state.recheck_orchestration_capability()`: on an off-host resume it re-checks the
  Workflow tool and recompiles **only** the orchestration tier DOWN
  (`cc-workflows-ultracode → team-execution → inline`), preserving unit specs + per-unit tiers and
  surfacing a one-line downgrade note. AE3: it never errors and never silently runs nothing — an
  unknown or unavailable tier floors to the always-runnable inline baseline. New
  `lifecycle_state.py recheck-capability` CLI subcommand.
- Record the downgrade durably: add the `orchestration_downgrade` saga field (one-line note;
  empty on a host that ran the authored tier; backward-compatible default for older sagas).
- Document the degradation flow in `references/execution-spec.md` and the new field in
  `references/saga-spec.md`.

## [0.31.0] - 2026-06-21

- Add `scripts/execution_spec.py` (R9 keystone): the structured execution-spec schema and the
  Claude Code workflow-script emitter. `/plan` authors **one** spec (units with a per-unit
  `{model, effort}` tier, return contracts, dependency barriers, escalations, and enumerated
  fan-out targets) and emits a runnable `.workflow.js` from it; saga records only an
  `orchestration_ref`, never vendoring backend machinery.
- Enforce two authoring-time invariants at EMIT time so a mis-built spec fails loudly: a fan-out
  unit with no enumerated targets fails emit (R10, never a silent filter), and a pilot at a
  different tier than its fan-out fails emit (R3, a mis-tiered pilot is an invalid oracle).
- Bake the `workflow_structuredoutput_budget` lesson (cap output, mandatory final emit, skim, batch)
  into generated cheap-tier (haiku) agents, and bake enumerated-target post-run reconciliation into
  fan-out agents.
- Add `references/execution-spec.md` documenting the spec shape, the R3/R10 invariants, and the CLI
  (`validate` / `emit`).

## [0.30.0] - 2026-06-21

- Add `plugins/saga/agents/mechanical-executor.md`: cheap-tier (haiku, Bash-only)
  op-discriminated executor agent for deterministic mechanical ops dispatched by saga
  commands.  Approved ops: `census` (file enumeration), `file-exist` (path presence),
  `json-validate` (JSON parse check), `grep-count` (pattern match count), `link-check`
  (HTTP 2xx probe).  Unknown ops are rejected with a clear error message — never guessed.
  The agent is inert until called; it has no auto-trigger.  Addresses R16 / Epic 4 (U14).
- Update `plugins/saga/skills/work/references/execution-strategy.md`: add a `mechanical-executor`
  dispatch paragraph to the subagent dispatch section, naming the approved ops, the haiku/Bash-only
  scope, the op-discriminated rejection contract, and an example dispatch payload.  Wires the
  agent into the saga `/work` dispatch path without duplicating agent prose.

## [0.29.0] - 2026-06-21

- Add `tools/gate-manifest.json`: single-source declarative listing of the pre-push gate steps
  (`ruff format --check`, `ruff check`, `validate_plugins`, `validate marketplace`, `pytest`),
  each with an `id`, `label`, `command`, and `failure_hint`.  This file is the sole authoritative
  gate definition — the hook reads it at runtime and never diverges.  Addresses R15 / KTD10
  (Epic 3 hook harness, U9).
- Add `plugins/saga/hooks/pre_push_gate_hook.py`: a `PreToolUse` / Bash hook that fires when the
  Bash tool runs a `git push` command.  Reads `tools/gate-manifest.json` relative to the repo root,
  runs every step in order, and reports by exception — silent on pass, prints each failed step's
  label, output, and failure hint to stderr then exits 2 (blocking) on any failure.  Cross-repo-safe:
  degrades silently when the manifest is absent.  Co-located with U7/U8 in `hooks/hooks.json`.
- Update `plugins/saga/hooks/hooks.json`: add a `PreToolUse` / `Bash` matcher entry wiring
  `pre_push_gate_hook.py` into the hook harness alongside the existing JSON validator (U7) and
  journal nudge (U8).
- Add `tests/test_pre_push_gate.py`: 20 tests covering manifest structure (5 required step IDs,
  uniqueness, all fields present), push detection, exit-code contract (silent on pass, exit 2 on
  failure, exit 0 on non-push/non-Bash/malformed/missing-manifest), failure reporting (all failing
  steps listed, output echoed, hints included), and the single-source invariant (hook executes
  manifest-defined steps, not a hard-coded list).

## [0.28.0] - 2026-06-21

- Add `plugins/saga/hooks/journal_nudge_hook.py`: a non-blocking `PostToolUse` hook (exit 0 always)
  that fires on a `feat`/`fix` Bash commit touching code files with no `docs/engineering-journal/`
  entry staged, and prints a one-line nudge to stderr.  Does not write the entry and does not block.
  Ships cross-repo-safe: degrades silently when the journal dir is absent or git is unavailable.
  Co-located with U7 in `hooks/hooks.json` under a new `PostToolUse` / `Bash` matcher.
  Addresses R14 (Epic 3 hook harness, U8).

## [0.27.0] - 2026-06-21

- Add `plugins/saga/hooks/hooks.json` and `hooks/validate_json_hook.py`: the repo's first hook.
  A `PreToolUse` hook that JSON-parses `marketplace.json` and `plugin.json` on every
  `Edit`/`Write`/`MultiEdit`, asserts balanced brackets, and exits 2 (blocking) with the
  offending file path and line on failure.  Unrelated files pass through silently (exit 0).
  Addresses R13 (Epic 3 hook harness).

## [0.26.0] - 2026-06-21

- Split the recommender's `needs_consensus` signal on the **governance** axis (R7 keystone). A consensus
  signal is no longer an unconditional hard-force to `team-execution`: `recommend_execution_backend`
  gains `consensus_is_gated` (default True). **Gated** consensus (the verdict must block a merge/deploy and
  persist as evidence) → `team-execution`; **advisory** consensus (throwaway in-session votes) is OR'd into
  the existing `adversarial_confidence` ultracode trigger → `cc-workflows-ultracode`. A
  contested-but-not-gated job now reaches the advisory judge-panel and never regresses to `inline`.
- Add `--advisory-consensus` to the `recommend-backend` CLI so the markdown caller can reach the advisory
  branch; gated stays the default when the flag is omitted.
- Add the KTD4 gated-vs-advisory interrogation question + work-shape default to `skills/plan/SKILL.md` §5.2
  (default *gated* when deploy/security/persist signals are present, *advisory* otherwise; the operator
  confirms).
- Update `references/operator-choice.md` §3.1 to record the gated/advisory governance split and that only
  gated consensus reaches `team-execution`.
- Cover AE1 (advisory → ultracode), AE2 (gated → team), the overlap case, the docs-gating case, and the
  CLI round-trip in `tests/test_saga_plugin.py`.

## [0.25.0] - 2026-06-21

- Rewrite the `/plan` (`skills/plan/SKILL.md`) and `/code-review` execution-backend offers to name
  **both** dynamic-workflow purposes from `operator-choice.md` §3.2 — **breadth / scale** fan-out **and**
  **adversarial confidence** (judge-panel / refute-N / perspective-diverse) — instead of underselling
  `cc-workflows-ultracode` as fan-out only (R5).
- Reframe the team↔workflow fork on the **governance** axis ("does the verdict need to stick?" — gated
  consensus that blocks a merge/deploy and persists vs. advisory throwaway votes), not on "review depth"
  (which both backends have) (R6).
- Add `tests/test_operator_choice_drift.py` — a drift guard asserting every offer surface stays a
  SUPERSET of the §3.2 purpose list (anchored on stable content markers, not line numbers), so a future
  rebuild cannot silently drop a purpose or reintroduce the "review depth" framing.

## [0.24.0] - 2026-06-21

- Add `orchestration_recommended` and `orchestration_operator_choice` fields to the saga envelope
  (R12 — choice-vs-recommendation recording). Enables override-rate computation in `/retro`+`/optimize`.
  Both fields default to `""` so pre-0.24.0 sagas parse without error (backward-compatible additive
  evolution per §9 of the saga spec).
- Add `ORCHESTRATION_MODE_LABELS` display-label map to `saga.py` (`cc-workflows-ultracode` →
  "dynamic workflows", `team-execution` → "team execution", `inline` → "inline") and a
  `display_orchestration_mode()` helper that falls back to the raw enum string on a miss — never errors
  (R8 / KTD5).
- Route all offer-surface prose in `/plan`, `/work`, `/code-review`, `/loop`, `/founder-review`,
  `/optimize`, and `/retro` skills through the display labels so operators see "dynamic workflows"
  in descriptions while the stored enum string `cc-workflows-ultracode` remains the frozen wire
  contract (carried in persisted sagas and `--orchestration-mode` CLI choices, byte-for-byte unchanged).

## [0.23.0] - 2026-06-20

- Add the `/promote` skill — the workspace tier of the engineering journal. It promotes the *select few*
  cross-repo "transcendent" learnings into `infiquetra-context-library`'s `LEARNINGS.md` as distilled,
  pull-only org standards: a manual, gated, agent-judged pass with two feeders (the `/retro`-declared
  `**Transcendent.**` marker and a recurrence net over legacy `**Generalizable rule.**` lines). It mirrors
  `/ideate`'s cross-repo grounding, clusters the same lesson across repos by judgment (no vectors), and
  upserts ONE entry per lesson behind a propose-diff-and-wait gate. READ-ONLY on the SDLC; writes only to
  context-library; never writes back to source repos.
- Add `scripts/promote_scan.py` — the deterministic backbone: enumerate `*/docs/engineering-journal/
  LEARNINGS.md`, parse the marker + legacy-rule variants, compute the drift-stable `<repo>:<hash>` source
  key, read context-library's `promote-keys` ledger to drop already-promoted candidates, exclude
  context-library and self-feed entries (two layers), group exact-recurrence clusters, and render the
  idempotent gated upsert (create / update / noop). The marker form, key recipe, parser, entry template,
  and ledger are frozen in `skills/promote/references/promotion-contract.md` (the single source of truth).
- Teach `/retro`'s Phase-4 curation to propose the `**Transcendent.**` marker on the select cross-repo
  learnings (the single-repo, propose-diff-and-wait declare feeder).

## [0.22.1] - 2026-06-13

- Tighten the `adversarial_confidence` guidance: `/work` sets `--adversarial-confidence` only on an explicit
  operator request for many-independent-attempt verification (refute-N / judge-panel / perspective-diverse),
  never inferred from generic "make me more confident" phrasing — closes the oversell risk the adversarial
  review flagged. The trigger stays categorical; a true magnitude gate remains a documented revisit-when.
- Journal bookkeeping: record the 0.22.0 squash SHA (`331505a`).

## [0.22.0] - 2026-06-13

- Correct the execution-backend recommender (`recommend_execution_backend`) and the operator-choice contract
  so `cc-workflows-ultracode` (ultracode) is no longer framed as "fan-out, not review depth": ultracode
  delivers deterministic fan-out **and** independent/adversarial verification. The line to `team-execution`
  is GOVERNANCE (reviewer consensus + named scanner gates + guarded deploy), not review depth.
- Add `adversarial_confidence` as a second `cc-workflows-ultracode` trigger beside `broad_independent_fanout`
  (CLI `--adversarial-confidence`): prove-by-refutation / judge-panel work with no deploy/security signal now
  reaches ultracode instead of silently falling to `inline`.
- Add `has_code_surface` (default True; CLI `--no-code-surface`) so pure docs/spec/research output neutralizes
  the output-blind team-execution proxies — `file_count`, `phase_count`, and the `parse_issue.py` keyword
  flags `has_infra` / `has_security` / `deployment_sensitive` that fire on a doc merely *mentioning* infra or
  auth. `cross_repo` (ownership boundary) and `needs_consensus` (contested) survive as the output-agnostic
  governance signals; the ultracode risk-suppressor is itself gated by `has_code_surface` so broad infra/
  security DOCS still fan out.
- Reword operator-choice §3.1 (`PLUS` -> `OR`, matching the code's sufficient-on-its-own consensus) and §3.2
  (the corrected ultracode framing + the throwaway-signal-vs-standing-verdict mechanical boundary).

## [0.21.0] - 2026-06-09

- Add a comprehensive Saga documentation system: README atlas, manual pages under
  `plugins/saga/docs/`, curated source model, and generated SVG visual kit.
- Document every Saga command as a comparable decision card, including the 18 command-file /
  17 routable-command distinction and the `/ceo-review` -> `/founder-review` alias.
- Add dedicated lifecycle, state/readiness, scenario, boundary, and visual-maintenance pages.
- Add `plugins/saga/scripts/render_docs_visuals.py` to generate presentation-ready SVG assets from
  `plugins/saga/docs/model/saga-docs-model.yaml`.
- Add `tests/test_saga_docs_coverage.py` to guard command coverage, alias handling, derived
  readiness maturity, scenario coverage, manual links, source references, and visual inventory.

## [0.20.0] - 2026-06-07

- Add a shared formatting contract, `saga/references/formatting-style.md`, linked by all nine
  doc-writing skills (ideate, plan, brainstorm, spec, strategy, retro, doc-review, code-review,
  founder-review). It mandates scannable output: ≤3-sentence blank-line-separated paragraphs, a
  one-line summary opening each ranked item/section, comparative data as tables, the compact
  engineer-facing schema fields rendered as a table (narrative fields stay prose), no-hard-wrap
  soft-wrap for generated output, and dropping fields a heading already carries. (#201)
- Fix the triggering case: `ideate`'s `ideation-artifact.md` SURVIVOR SCHEMA no longer stacks
  bold-label lines (the CommonMark collapse that read as "all jumbled together") — it now leads with
  a one-line summary and renders the schema as a table.
- Enforce it: `tests/test_saga_doc_formatting.py` fails CI on a stacked-bold-label collapse and on
  any doc-writing skill that does not link the contract.

## [0.19.0] - 2026-06-05

- Rename the engine plugin to `saga` (Scheme Y plugin-family rename) and fold `blueprint-reviewer`
  into it. Metadata/marketplace change; no command behavior change. (#199)

## [0.18.0] - 2026-06-04

- Rebuild `/optimize` from a 20-line stub into a **metric-driven optimization engine** — the
  **thirteenth and final command rebuild** of the engine-merge campaign (after `/office-hours`,
  `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`,
  `/retro`, `/investigate`, `/spec`). It runs a **bounded-experiment loop** toward a measurable
  target: pick a metric, baseline it, hypothesize, run a bounded experiment, measure the delta,
  keep or discard, repeat until the target is hit or the budget is spent.
- **Honest attribution — single source, no merge.** `/optimize` is a **CE `ce-optimize`
  single-source PORT**. The **agent-usability** metric class is an **infiquetra-native** angle
  (Jeff's), **NOT a gstack port** — a full-file grep of gstack `plan-tune` for the agent-usability
  terms returned **zero**; `plan-tune` is a developer-psychographic question-coach that supplies
  nothing portable and is not ported. This is **NOT a merge** of any kind, and gstack is credited
  with **no insight**.
- **Off-chain, saga UNTOUCHED.** `/optimize` writes no saga, advances no `lifecycle_phase`, and
  makes **no `saga.py` edit** (mirrors `/strategy` / `/spec`). **No new Python** — no
  `handoff_envelope.py` edit either; the `docs/optimize/` handoff source dir is deliberately
  **deferred**.
- **Eight metric classes (the maximal v1 taxonomy):** performance, cost, reliability,
  **agent-usability**, security, quality, developer-experience, maintainability.
- **OFFERS operator-choice** for independent experiment fan-out (default serial inline); the choice
  is recorded **narratively** (saga-untouched) — not via an `orchestration_mode` saga field.
- **Campaign-closer.** With `/optimize` shipped, **all 13 command rebuilds of the engine-merge
  campaign are complete.** (Scope: this closes the *command-rebuild* campaign; `/pulse` live
  telemetry and other enhancements remain separate, queued items.)
- **Periphery** — version bumps (plugin `0.18.0`, marketplace entry `0.18.0`; keywords stay at 10);
  dispatch-table `/optimize` row flipped stub → shipped (metric-loop engine, advisory + off-chain),
  routing-rubric row updated, plus a `/qa`-vs-`/optimize` boundary note (gate-to-ship vs
  loop-toward-target); `operator-choice.md` `/optimize` row "at its rebuild" → "now, offers";
  README `/optimize` command-summary line tightened to the bounded-experiment loop + 8 metric
  classes. Dispatch-table command count stays **17** (`/optimize` was already counted).
- Documented in the engineering journal (PR #197): DECISIONS `#optimize-engine-rebuild`, ARCHIVE
  `#optimize-engine-rebuild-shipped` + the campaign-complete capstone (closes
  `#lifecycle-engine-merge-campaign`), LEARNINGS `#shipped-on-origin-not-in-stale-local-tree` +
  the third firing of `#campaign-brief-merge-is-a-provenance-hypothesis`; consumed
  `#optimize-engine-merge` from QUEUED, added `#optimize-log-helper`.

## [0.17.0] - 2026-06-04

- Add `/spec` — the lifecycle's net-new **spec-interrogation engine** and the **twelfth command
  rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`, `/investigate`). It
  owns the relentless **WHAT-rigor** — the sibling of `/plan`'s HOW-rigor. A **gstack `spec`
  single-source port** of the WHAT-interrogation half: the principal-engineer-who-refuses-ambiguous-work
  persona, the HARD GATE (no spec after message 1 — always start the interview), Phase-1 five-Why,
  Phase-2 scope / MVP / out-of-scope / failure-mode lock, Phase-3 **read-code-first grounding** (cite
  `path:line` before asking, with a non-code escape), quantify-everything, and a draft-review pass.
- **Honest attribution — single source, no merge.** There is **NO CE spec engine** (ce-plan is
  `/plan`'s planning engine, not ported here), **NO /ideate+/brainstorm graft** (the
  assumption-challenge + failure-mode register is native to gstack's persona — the failure-mode bank
  already lives in `/plan/references/interrogation.md`, itself a gstack port), and no superpowers
  borrow. `/spec` and `/plan` split one source along the **WHAT vs HOW** altitude axis. The `/spec`
  SKILL does not duplicate `/plan`'s interrogation register. Sheds the entire gstack preamble,
  dedupe machinery, codex quality gate, two-layer redaction, `--execute` worktree spawn, gh issue
  authoring/filing, and the `~/.gstack` store.
- **Off-chain, saga UNTOUCHED.** `/spec` writes no saga, advances no `lifecycle_phase`, and makes no
  `saga.py` edit at all (mirrors `/strategy`). Its only durable output is a sharp WHAT artifact under
  `docs/specs/`. **No new Python.**
- **Q2 handoff wiring — the functional edit.** `handoff_envelope.py` now treats `docs/specs/` as an
  auto-discoverable handoff SOURCE: added `Path("docs/specs")` to `SOURCE_DIRS`, and
  `infer_maturity()` maps `docs/specs/` → `requirements-ready` (equals the existing default — a spec
  is a sharp WHAT, **not** plan-ready — set for consistency with the other source dirs, not a
  behavior change). `infer_lifecycle_phase()` leaves `docs/specs/` returning `"unknown"` (off-chain,
  no lifecycle phase). `references/saga-spec.md` §3.3 and `skills/handoff/SKILL.md` document the
  `docs/specs/ → requirements-ready` doc-path mapping; no `spec` phase is added to `LIFECYCLE_PHASES`.
- **Q4 + operator-choice honesty.** An offered `/doc-review` pass on a spec hits the **requirements**
  lens (`docs/specs/ → requirements` path tie-breaker added), not the blueprint route.
  Operator-choice **never offers** for `/spec` — a single durable spec artifact, no parallelism to
  escalate; size/risk lives in its scope sections and the downstream executor (`/plan` / `/work`)
  owns backend selection.
- **Brainstorm-seam resolution (decision d).** The `#brainstorm-spec-interrogation-seam` is resolved
  in favor of a **standalone `/spec`** that owns WHAT-rigor; `/brainstorm` stays the divergent
  explorer. `/brainstorm`'s Phase-4 handoff menu now offers **Sharpen with `/spec`** (divergent
  `/brainstorm` → convergent `/spec`).
- **Periphery** — version bumps (plugin `0.17.0`, marketplace entry `0.17.0`; keywords stay at 10);
  dispatch-table now **total over 17 routable commands** with `/spec` added (off-chain advisory route,
  routing OUT to `/handoff` / `/plan` / optional `/doc-review`); README `/spec` command-summary line.
  Two deferral closures: `operator-choice.md` `/spec` row "at its rebuild" → "never offers";
  office-hours `frame-diagnostic.md` `/spec` moved from "campaign-queued" to an active routing-rubric
  row.
- Documented in the engineering journal (PR #195): DECISIONS
  `#spec-interrogation-engine-rebuild`, ARCHIVE `#spec-interrogation-engine-shipped` +
  `#brainstorm-spec-interrogation-seam-resolved`, LEARNINGS
  `#campaign-brief-merge-is-a-provenance-hypothesis`; consumed both `#spec-interrogation-engine` and
  `#brainstorm-spec-interrogation-seam` from QUEUED.

## [0.16.0] - 2026-06-04

- Add `/investigate` — the lifecycle's net-new **systematic-debugging engine** and the **eleventh
  command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`, `/retro`). It answers "what is
  actually broken, and why?" — the diagnostic brain `/qa` (the gate) deliberately does not own. A
  **CE `ce-debug` spine** (causal-chain gate, falsifiable predictions for uncertain links, assumption
  audit, Phase-0 triage with trivial fast-path, smart-escalation, parallel read-only sub-agent
  dispatch) + **gstack `investigate` grafts** (the pattern-signature table — race/null/state/integration/config/cache
  — the two distinct numeric stop gates (hypothesis-exhaustion + 3-failed-fix), and the DEBUG REPORT
  Status enum) + a **superpowers
  systematic-debugging borrow**. Drops gstack scope-lock/freeze and all gstack runtime bins.
- **Diagnosis-primary, never a fixer.** `/investigate` produces a DEBUG REPORT (file:line, causal
  chain, regression-test path, Status enum) and **routes** the work out: a real fix → `/work` (via a
  `/handoff` issue); an applied inline fix → `/work` or `/code-review` to ship; a trackable defect →
  `/handoff`; a design-level root cause → `/brainstorm`. It does not commit, push, open/merge a PR, or
  deploy.
- **Saga READ-ONLY — zero saga edits.** `/investigate` reads saga context for evidence but writes no
  saga; **off-chain** (advisory, never blocks `/loop`). `saga.py`, `handoff_envelope.py`, and
  `references/saga-spec.md` are untouched. **No new Python** — `/investigate` is a markdown engine
  (SKILL + references + command). Verification is **own-minimal** (carries its own light verification),
  NOT a call back into `/qa`, overriding the pre-decision "verification CALLS /qa".
- **Full `/qa` cross-engine rewire — closes the deferred route at every site.** `/qa` deferred deep
  post-merge root-cause failures to "when `/investigate` is built." Building it closes that deferral
  **everywhere** (5 `/qa` SKILL mentions + 2 other-file notes): `/qa`'s post-merge FAIL branch is now
  **two-target** — deep-root-cause failures route to `/investigate` (now on the dispatch-table's
  routable list), clear/trackable defects still route to `/handoff`; pre-merge still routes to `/work`.
  Routing still **reads** `loop/references/dispatch-table.md`. No `/investigate`→`/qa` verify loop.
- **Periphery** — version bumps (plugin `0.16.0`, marketplace entry `0.16.0`; keywords stay at 10);
  dispatch-table now **total over 16 routable commands** with `/investigate` added (off-chain failure
  route); README `/investigate` command-summary entry; `operator-choice.md` + office-hours
  `frame-diagnostic.md` `/investigate` notes moved from "at its rebuild" / "campaign-queued" to active.
- Documented in the engineering journal (PR #193, squash 5079d8f):
  DECISIONS `#investigate-systematic-debugging-engine-rebuild`, ARCHIVE
  `#investigate-systematic-debugging-engine-shipped`, LEARNINGS
  `#deferred-cross-engine-wiring-must-close-on-build`; consumed from QUEUED.

## [0.15.0] - 2026-06-03

- Rebuild `/retro` from a 19-line stub into the lifecycle's **meta-improvement engine** — the **tenth
  command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`,
  `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`). A **real 3-source merge**, not a
  port: gstack's `retro` + `learn` passes merged with CE's `ce-compound` framing into one engine that
  captures lifecycle learnings, distills durable knowledge, and proposes improvements to the workflow
  itself.
- **Six net-new passes on top of the merged retro+learn+compound base** plus a lean metrics surface —
  the FULL engine shipped in v1, nothing deferred. `/retro` runs as a single command with an optional
  pass argument so a focused sub-pass can be invoked directly.
- **Tiered self-edit gate — the safety contract for a self-modifying engine.** Pure-additive,
  append-only journal writes auto-apply; every delete / modify / move of existing durable state
  (memory, directives, the lifecycle plugin's own SKILLs) is **propose-diff-and-wait**, and any
  global / cross-project edit carries an extra cross-project-impact warning. The blast radius is the
  full self-modification surface **including the lifecycle SKILLs**, gated rather than narrowed.
- **In-repo vs global/cross-project directive disambiguation.** `/retro` distinguishes a repo-local
  directive from a global / cross-project one and warns before touching cross-project surfaces.
- **Saga READ-ONLY — zero saga edits, no §11 change.** The planned `->retro` saga advance was dead
  wiring; it is dropped. `/retro` reads saga context but writes none, so `saga.py` and `saga-spec.md`
  are untouched. **No new Python** — `/retro` is a markdown engine (SKILL + references + command) that
  reuses existing helpers; the windowed mode keeps a stale-base guard scoped to that mode.
- Version bumps: plugin `0.15.0`, marketplace entry `0.15.0`. keywords stay at 10 (unchanged).

## [0.14.0] - 2026-06-03

- Rebuild `/strategy` from a 21-line stub into the lifecycle's **interview-driven STRATEGY.md
  engine** — the **ninth command rebuild** of the engine-merge campaign (after `/office-hours`,
  `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`). A **faithful
  single-source PORT of CE `ce-strategy`**, NOT a merge: gstack has **no** strategy engine — `cso/`
  is the Chief **SECURITY** Officer (a 14-phase security audit), so the pre-audit "gstack cso ≈ Chief
  Strategy Officer" mapping was a name-match mixup. CE `ce-strategy` is the sole engine source.
- **The whole engine, ported.** Rumelt-grounded kernel (diagnosis / guiding-policy / coherent-action)
  + Phase-0 file-state routing (new STRATEGY.md vs targeted-section update vs pick-a-section) +
  Phase-1 **8-section interview with a mandatory 2-round pushback per section** + a **locked
  root-`STRATEGY.md` template** (3-5 metrics, 2-4 tracks) + rerunnable update-in-place. All 8
  sections and the Rumelt kernel are kept (no trimming).
- **Agent-as-customer is persona-only.** Personas may name AI-agent actors **when the product is
  agent-consumed**; **tracks stay pure investment areas / domains of work, NOT actors**. The QUEUED
  brief's blanket "personas/tracks must name AI-agent actors" was half a category error — tracks are
  domains of work, not actors — caught by reading the real CE `interview.md` section semantics.
- **Zero saga edits, off-chain / pre-saga.** `/strategy` owns the durable `STRATEGY.md` direction
  and writes no saga (like `/founder-review`, it runs upstream of the work loop); `/founder-review`
  challenges the direction, `/strategy` records it. **No new Python** — `/strategy` is a markdown
  engine (SKILL + references + command). `saga.py` is untouched.
- Version bumps: plugin `0.14.0`, marketplace entry `0.14.0`. keywords stay at 10 (`strategy` was
  already a keyword; unchanged).

## [0.13.0] - 2026-06-03

- Rebuild `/qa` from a 19-line stub into the lifecycle's **gate-only acceptance-evidence engine** — the
  **eighth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`,
  `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`). A **real two-engine merge** against
  the cloned gstack source (`/qa` + `/qa-only` + `/investigate`) plus a CE `ce-debug` graft, **not** a
  phantom port: `/qa` adopts gstack's own report-only `/qa-only` model — it tests, gathers evidence,
  assigns severity, derives a verdict, and routes, but **never fixes, commits, pushes, opens/merges a
  PR, or deploys**.
- **Severity-banded verdict + a ported deterministic health score, reported alongside each other.** Each
  finding carries critical / high / medium / low (with a documented ↔ P0-P3 cross-walk to `/code-review`);
  pass/fail is stated per risk class and the overall ship verdict (`ship` / `ship-with-deferred` /
  `no-ship`) is derived from the tier's blocking threshold — and that verdict is the gate decision. A new
  deterministic scorer `scripts/qa_health_score.py` **ports gstack's Health Score Rubric**
  (`scripts/resolvers/utility.ts:286-321`, injected as the `{{QA_METHODOLOGY}}` macro): gstack's deduction
  values verbatim (critical -25 / high -15 / medium -8 / low -3) with documented infiquetra 9-way
  ship-risk-class weights, re-normalized over the in-scope classes, plus a baseline-from-prior-report
  delta. The 0-100 number is reported **alongside** the banded verdict, with the explicit caveat that its
  inputs are LLM-assigned severities — so it is one signal, not the gate decision.
- **Saga qa-track consumer — lands the deferred work→qa advance.** `/qa` `restore`s the work-thread
  saga, writes `qa_paths`, and **on PASS advances `lifecycle_phase` from `work` to `qa`** — the advance
  `/work` (0.10.0) explicitly deferred to this rebuild. On FAIL it keeps `lifecycle_phase=work` and
  records evidence. Every flag already exists (`--lifecycle-phase qa`, `--qa-paths`, the `qa` phase) —
  **zero `saga.py` edits**.
- **Durable risk reference + falsifiable-prediction graft.** Ships a `references/risk-taxonomy.md`
  (9-way risk router + per-class checklists + diff-aware file→class map + severity defs + the P0-P3
  cross-walk; gstack's 7 web categories fold under behavior/browser as **one MCP-driven class**, a
  graceful no-op off-UI) and `references/qa-report.md` (the report shape + ship-verdict derivation +
  tier→blocking-threshold table). Grafts CE `ce-debug`'s **falsifiable-prediction** discipline: for
  each uncertain-cause failure, state a prediction another path must also fail if the cause is real,
  giving the routed fixer a head start.
- **Merge-state failure routing.** PASS routes to `/handoff` or `/retro`; FAIL routes by merge state —
  pre-merge to `/work` (re-enter the round-N loop), post-merge to `/handoff` (open a new defect
  thread). `/investigate` is future-prose only (not on the dispatch-table's routable list). Routing
  **reads** `loop/references/dispatch-table.md`, never restating it.
- **One new script.** The Q2 final ports gstack's formula into `scripts/qa_health_score.py` (the scorer)
  with an oracle test; otherwise `/qa` is a markdown engine (SKILL + 2 refs + command + the scorer +
  tests), and `saga.py` is untouched. Also resolves the present-tense `docs/qa/` collision with the
  `/optimize` stub (one-line `/optimize` → `docs/optimize/`).
- Version bumps: plugin `0.13.0`, marketplace entry `0.13.0`. keywords stay at 10.

## [0.12.0] - 2026-06-03

- Rebuild `/resume` from a 23-line "read committed docs first" doc into the lifecycle's **heavy
  forensic reconstruction engine** — the **seventh command rebuild** of the engine-merge campaign
  (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`) and the
  **unblocked heavy partner** the `/loop` rebuild (0.11.0) explicitly deferred to it. `/loop` owns the
  **lightweight** scan → restore → route + inline cold-reconstruction; `/resume` owns the **heavy**
  forensic half. Unlike `/loop` (the campaign's native rebuild against a phantom brief source),
  `/resume` is a **real CE `ce-sessions` PORT** — verified TRUE and portable against the actual
  upstream, the positive counterpart to the `/loop` phantom-source lesson.
- **Two-tier design.** **Tier 1** (the common path) = saga-anchored deep reconstruction: a NEW saga
  **all-ticks reader** (`saga.py` `read_ticks`) that walks the full append-only tick-chain trajectory —
  the trajectory `/loop`'s latest-tick-only `restore` cannot see — plus PR archaeology and conflict
  reconciliation. **Tier 2** (FALLBACK ONLY, when there is **no saga AND no resolvable issue**) = a slim
  Claude-only port of CE `ce-sessions`: discover → file-mediated skeleton extract to scratch → **generic
  agent synthesis**, never reading multi-MB session JSONL into context (context-safety by construction).
- **The all-ticks reader lives in `saga.py`, NOT `load_saga_context.py`.** A brief deviation: the
  `load_saga_context.py` wrapper is **issue-locked** (its `--issue` arg is required), so it is the wrong
  layer for a cold-no-issue trajectory read. The all-ticks capability belongs in the saga engine itself
  (`read_ticks`); `load_saga_context.py` stays the shared issue-keyed substrate `/loop` and `/resume`
  both use.
- **Generic-agent synthesis — no `agents/` dir.** Tier-2 synthesis uses generic agents, honoring the
  shipped `/code-review` convention (no plugin `agents/` dir → generic agents, SKILL:164) rather than
  adding a structural first.
- **Drop the `[gstack-context]` commit trailer.** `/resume` does NOT adopt gstack's WIP-commit trailer —
  the saga's append-only tick log already IS the durable trajectory; a parallel trailer would duplicate
  it. Corrected Tier-2 trigger: same-machine work that never wrote a saga (NOT fresh-clone).
- **Routing + the one re-entry tick.** Routes to any phase via the **shared**
  `loop/references/dispatch-table.md` (referenced, never duplicated — no `/loop` ↔ `/resume` ping-pong).
  Writes exactly **one** git-ignored re-entry saga tick, **reusing the restored `saga_id`** (never-mint
  discipline — `/resume` is a reader/restorer, not a saga primary writer).
- **Recency-MVP ranking** for Tier-2 candidate sessions; keyword/branch relevance ranking deferred
  (QUEUED `#resume-session-relevance-ranking`).
- Version bumps: plugin `0.12.0`, marketplace entry `0.12.0`. keywords stay at 10.

## [0.11.0] - 2026-06-03

- Rebuild `/loop` from a router stub into a native router engine — the **sixth command rebuild** of the
  engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) and the
  campaign's **one native rebuild**: there is no upstream engine to port or merge. CE ships no router; the
  gstack "dispatch table" the QUEUED brief named is **phantom** (gstack's root SKILL is browser-testing, no
  router dir), and gstack's context-save/restore is the shipped saga + the queued `/resume`'s engine, not
  `/loop`'s. Three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive**
  (inline phase walk with a per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan →
  restore → route a durable work-thread).
- **Saga resume wiring.** `/loop` `scan`s for the matching work-thread saga, `tick`s a routing event, and
  `restore`s state on re-entry — plus inline cold-reconstruction via `load_saga_context.py` when re-entering
  without a live session. The routing tick carries the existing saga fields plus an offload pointer only for
  `/loop`-owned offloads (no schema change).
- **Operator-choice offer for `/loop`-owned work.** `/loop` offers the three execution backends
  (`inline` / `team-execution` / `cc-workflows-ultracode`) per decision point in Drive mode for work it owns.
  The offload pointer is scoped to `/loop`-owned work only — `/loop` does **not** instruct a routed command's
  backend (`/work` writes but never reads `orchestration_mode`).
- **Additive saga picker-field extension.** `saga.py` `scan()` / `_saga_summary` gained the issue_ref /
  plan_path / branch picker fields so a resuming `/loop` (and `/code-review`) can match the right thread —
  closing the `#code-review-saga-scan-touchups` queued item.

## [0.10.0] - 2026-06-03

- Rebuild `/work` from a 39-line facilitator stub into a real execution-loop engine — the **fifth command
  rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`)
  and the most architecturally entangled, because it lands two deferred foundations at once. A genuine
  **merge**: CE `ce-work`'s execution engine (Phase-0 complexity triage, task-list from plan U-IDs, the
  Execution-Strategy table + Parallel Safety Check, test discovery + scenario-completeness + system-wide
  check, incremental-commit heuristic, "already shipped → verify don't reimplement") + gstack `ship` /
  `land-and-deploy`'s autonomy contract, Review-Readiness + staleness gate, and merge-base-before-tests.
  Five numbered phases: enter + scan saga + triage + detect round-N → setup + task-list + backend → execute
  phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready +
  continuation routing.
- **Saga becomes first-class — `/work` is its primary writer (saga-spec §11).** `/work` `scan`s/`restore`s on
  re-entry (rehydrate round/phase/checks_run/next_step), mints/advances the work-thread saga to
  `lifecycle_phase=work` with `--plan-path` set + saved on-branch, and writes a tick per phase boundary
  (round bump via `--rounds-seen`, never `next_round`). Crucially it **mints + names the exact saga that
  `/code-review` (shipped 0.8.0, append-only/never-mint) appends `review_paths` to** — and passes the saga
  identity (`kind`+`id`) into the programmatic `/code-review` call so code-review hits that thread instead of
  scan-guessing. This closes the forward-coupling for both issue AND ad-hoc task work.
- **The deferred `recommend_execution_backend()` helper lands here** — its first real caller (a library-only
  helper would be uncallable from markdown). A pure function in `scripts/lifecycle_state.py` next to
  `should_offer_team_execution` (reused), plus a `recommend-backend` CLI subcommand returning
  `{recommended, rationale, alternatives, omit_ultracode}`. `alternatives` is computed independently of the
  precedence winner so an overlap case (consensus AND broad fan-out) still offers `cc-workflows-ultracode` as
  a one-keystroke escalation. `main()` refactored into `normalize` + `recommend-backend` subcommands.
  Closes the operator-choice 0.5.0 deferral.
- **`issue_progress.py`'s CLI extended** to forward the full field set the function already accepts
  (`--work-session-path --commit-sha --checks-run` [pipe-separated] `--blockers --pr-url --review-status
  --doc-review-artifact --doc-review-blocked --doc-review-findings` [pipe-separated] `--doc-review-override
  --deploy-status --workflow-url --evidence-link`) — the Phase-4 progress comment was previously
  uninvokable from markdown (only 8 of the function's fields had argparse flags).
- **PR-ready boundary + round-N PR continuation loop (`/work` owns it, NOT `/resume`).** `/work` executes to
  PR-ready, then on re-entry reads PR state with a total `gh pr view --json
  state,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,isDraft,mergedAt` and walks a total
  transition table (draft → mark-ready; review-required → pause; changes-requested/conflicting/failing-checks
  → round N+1; approved+clean+fresh → offer merge). **Merge is a confirmed git op `/work` owns**
  (`gh pr merge` only under explicit operator confirmation, never silent); only deploy mutation is delegated
  to `deploy`.
- **Hard review gate + honest override + computed staleness.** PR-ready blocks on unresolved P0/P1 (read from
  `/code-review`'s programmatic envelope + the saga `review_paths`) OR a stale review (parse the reviewed SHA
  from the newest review artifact → `git rev-list <reviewed_sha>..HEAD --count > 0`). Override only with a
  recorded rationale, never silent. `requires_hard_test_gate` blocks risky change-kinds at the test gate.
- **Boundary.** `/work` builds, gates, records, and coordinates the PR loop (merge under confirmation); it does
  NOT silently mutate GitHub, own deploy/canary (gstack's canary-verify + offer-revert are **relocated** to
  `deploy`, queued there), file SDLC issues (`mission-control`), or advance `lifecycle_phase` past
  `work` (the `qa` advance is honestly deferred to the `/qa` rebuild — the saga sits at `work` post-merge;
  `/qa`/`/resume` routing is advisory).
- Three new references: `skills/work/references/{execution-strategy,test-and-gates,pr-continuation-loop}.md`
  (CE execution strategy + the `recommend_execution_backend()` integration; test discovery + hard-gate +
  computed-staleness + the gstack autonomy contract; the total PR-state transition table). Thin
  `commands/work.md` launcher (saga-primary-writer + PR-ready boundary + hard review gate +
  merge-under-confirmation; no deploy/canary ownership). Surgical flip of `references/operator-choice.md`'s
  deferred-helper notes now that the helper has shipped. Self-contained: merges the CE + gstack engines, no
  vendoring, no runtime dep.

## [0.9.0] - 2026-06-03

- Rebuild `/founder-review` (alias `/ceo-review`) from a 20-line stub into a real scope/ambition/direction
  review engine — the fourth command rebuild of the engine-merge campaign (after `/office-hours`, `/plan`,
  and `/code-review`). A **port, not a merge**: gstack `plan-ceo-review` is the sole engine source (4
  user-selected scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted
  pre-review system audit), with only CE `product-pulse`'s sharpened no-false-precision posture stolen.
  Fires upstream of execution on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc
  scope question — the third member of the review trio (`/doc-review` = plan-readiness, `/code-review` =
  code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?**).
- **Four scope modes, committed for the whole review (no silent drift)** — SCOPE EXPANSION (cathedral) /
  SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon), selected
  via `AskUserQuestion` with context-defaults (greenfield→Expansion, enhancement→Selective, bugfix/refactor
  →Hold, >15 files→suggest Reduction). Each is distinct; all relevant pre-traction.
- **Review-only boundary** — `/founder-review` challenges scope/ambition/direction + captures a scope
  decision; it never makes code changes, never commits/pushes/opens PRs, never files SDLC issues, and never
  *records* the direction (`/strategy` records; founder-review challenges). On a `STRATEGY.md`, founder-review
  is the *ambition lens* and `/doc-review` the *readiness lens* — complementary, not a collision.
- **CLOSED-LOOP routing (not a hand-wave)** — accepted scope routes to `/plan` to re-plan; the (re-)expanded
  plan artifact is written/updated and handed **back** to `/doc-review` (readiness) + `/code-review` (code)
  **with the concrete path**, so expanding scope re-rigors that scope rather than dropping it. Phase 3
  applies the directives + patterns as scope-level lenses producing **named scope findings**, not vibes.
- **Target-conditional Step-0 ceremonies** — gstack's 0C-bis (implementation alternatives) + 0E (temporal
  interrogation) are plan-specific, so they run on a plan target and are skipped/recast on a
  strategy/brainstorm/scope-question target (0A/0B/0C/0F always run). An **office-hours escape** in 0A
  offers `/office-hours` when the session is vague/unframed, resuming after.
- **NO saga write** — founder-review runs upstream/pre-saga and its output is a scope decision, not a
  readiness/code-review artifact; `saga.py`'s `review_paths` is the wrong home and the guard would skip
  ~always. Cross-session persistence = the `docs/founder-reviews/` scope-decision artifact + the journal ADR.
- Durable artifacts land in their own `docs/founder-reviews/` scope-decision dir (intentionally NOT a
  `/handoff` source and NOT `docs/reviews/`), carrying the Mode + Vision + a Scope-Decisions table
  (ACCEPTED/DEFERRED/SKIPPED) + the founder verdict (ship / sharpen / scrap-and-rethink) + the next-command
  handback. **Operator-choice** offer — all three backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) on a scope-expansion/scrap verdict.
- Two new references: `skills/founder-review/references/{ceo-cognition,review-modes}.md` (the 18 patterns + 9
  directives + sharpened posture; the 4 modes + ceremonies + adapted audit + target-conditional gating).
  Thin `commands/founder-review.md` + `commands/ceo-review.md` (alias) launchers (review-only, no saga
  mention). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE.

## [0.8.0] - 2026-06-03

- Rebuild `/code-review` from a 20-line stub into a real pre-PR code-quality review engine — the third
  command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`). Merges CE's
  `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack
  `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories into a
  self-contained infiquetra engine. Fires at the work→PR boundary (after `/work` produces code, before
  PR/merge) — it is a within-work gate, NOT the saga `review` lifecycle slot (`/doc-review` owns that).
  Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) →
  review fan-out → merge + validate → report + route + saga.
- **Gate-only boundary** — `/code-review` reports + classifies + routes; it never mutates code, commits,
  pushes, opens PRs, or files SDLC issues (`/work` / `deploy` / `mission-control` own those).
  Adopts CE's full findings schema (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` /
  `pre_existing` / `evidence`) as agent-consumable routing metadata; fixer dispatch is offered, never
  auto-run. The programmatic mode (for `/work`'s future call) is zero-write to reviewed code.
- **Judgment-based lenses** — read the diff, spawn only lenses with real work, announce the team with a
  one-line justification each. Four always-on lenses (correctness, security, testing,
  maintainability/conventions) plus conditional-by-judgment lenses including a distinct
  deploy/migration-verification lens (DynamoDB/IaC/Ansible checklist) and a reliability lens. gstack's
  Rails/Swift/Stimulus specialists dropped; its high-signal checklist categories (enum-completeness,
  LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the lens checklists.
- **Built-vs-planned audit** — scope-drift detection (informational: CLEAN / DRIFT / REQUIREMENTS-MISSING)
  plus the 5-state plan-completion audit (DONE / PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE) with the
  three verification modes (DIFF / CROSS-REPO / EXTERNAL-STATE) and the honesty rule, reading the
  `docs/plans/` artifact + the journal. The audit always emits findings; the normal P0/P1 findings gate
  is what blocks the PR.
- **Independent validator pass, right-sized by MODE** — programmatic/headless runs a fresh per-finding
  validator over all Stage-A survivors (capped 15, ordered P0→P3, validator-reject/failure → drop);
  interactive mode lets the operator be the per-finding validator. The cost control is the upstream
  suppress-<75 confidence gate + the 15-cap, not a severity carve-out.
- `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread
  saga (found via `saga.py scan`): appends the artifact path to `review_paths` + records the backend in
  `orchestration_mode`, preserving `lifecycle_phase` (it does NOT advance the phase). If no saga exists it
  skips the saga write — never mints, never invents `--kind/--id`. Never `git add` the tick.
- Durable artifacts land in their own `docs/code-reviews/` dir (NOT `docs/reviews/` — avoids the
  handoff/mission-control plan-ready classifier collision), carrying the reviewed SHA + a review-result
  contract. **Operator-choice** offer — all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) for the fan-out + validator
  pass.
- Four new references: `skills/code-review/references/{lens-catalog,findings-schema,validator,built-vs-planned}.md`.
  Thin `commands/code-review.md` launcher reflecting the engine (gate-only + saga append + the hard
  boundary). Self-contained: ports both source engines, no gstack vendoring, no runtime dep on CE.

## [0.7.0] - 2026-06-02

- Rebuild `/plan` from a 27-line stub into a real implementation-plan engine — the second command
  rebuild of the engine-merge campaign. Merges CE's `ce-plan` structured-artifact engine (the
  Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end into a
  self-contained infiquetra engine. Six numbered phases: enter + warranted-gate → ground (HOW) →
  interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route +
  operator-choice.
- Artifact contract (CE wholesale): stable **R-IDs** (requirements), **KTDs** (Key Technical
  Decisions), independently-landable **U-IDs** with per-unit enumerated **test scenarios** + explicit
  test-file paths; requirements traceability; "decisions not code"; three-audience design (human +
  agent + `/work` consumer). The plan doc carries `origin:` + `Implementation Units` +
  `Key Technical Decisions` + `U1` markers so `/doc-review` recognizes it.
- **Warranted-gate** + scope classes up front — a `/plan` invocation that doesn't warrant a durable
  plan is named and routed, not force-fit into the artifact.
- **HOW-only interrogation** — `/plan` assumes the WHAT (requirements/scope) settled upstream
  (`/ideate` → `/brainstorm` → `/office-hours`); open WHAT-ambiguity bounces back with a recommendation
  to run `/brainstorm` first (it does NOT claim `/brainstorm` "accepts" a handoff). The interrogation
  register grounds in code (cite `path:line`) before asking.
- **Condensed deepening pass** — a conditional confidence self-review (not CE's full 248-line
  deepening), kept proportional. The full review gauntlet is NOT dropped — it's the `review` phase
  (`/doc-review` + `/code-review` + `/founder-review`); `/plan` keeps the condensed self-review and
  routes to `/doc-review` (the recommended next step) before `/work`.
- One **plan saga** via the saga CLI (`scripts/saga.py save`, `--lifecycle-phase plan`) — runnable,
  with an explicit "never `git add` the tick" boundary; epic/multi-unit splits hand to `mission-control`.
- **Operator-choice** offer: all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`), offered not defaulted.
- Hard boundary: `/plan` does NOT implement, does NOT file SDLC issues (`mission-control` owns that), and
  does NOT run the full review gauntlet (`/doc-review` owns that). Position: `/plan` answers
  "How should it be built?".

## [0.6.0] - 2026-06-02

- Rebuild `/office-hours` from a 23-line facilitative stub into a real two-mode thought-partner
  diagnostic ported from gstack and adapted to infiquetra — the Think-phase frame-finding front
  door that `/ideate` routes unframed asks to and `/brainstorm` bounces open thought-partner work
  back to. Keeps that handshake.
- Two modes: **Startup mode** — gstack's six market/customer forcing questions, made
  **stage-aware** (a pre-traction / pre-revenue greenfield operator gets a hypothesis-forming
  register, not an evidence-audit of customers that don't exist yet); **Builder mode** —
  discovery/shaping for infra, workflow, and internal-tooling asks, infiquetra's high-frequency
  mode, carrying real depth (not a one-liner). Modes can switch mid-session.
- Anti-sycophancy + pushback re-targeted: hard on vagueness and ungrounded assumptions, not on
  the operator's judgment; push-twice with escape hatches. **HARD GATE** (absolute): never
  implement, plan, or file an SDLC issue — frame-finding only. Stops the moment it can name the
  problem and a route, with plural clean exits (`/brainstorm`, `/plan`, `/strategy`).
- Route always (close by naming a next command); an optional **frame note** lands in its own
  `docs/office-hours/<date>-<topic>-frame.md` (frontmatter `kind: frame-note`) — kept out of
  `docs/ideation/` to avoid colliding with the `/ideate` resume scan.
- Self-contained: ports the gstack engine, sheds its runtime boilerplate (brain-context preflight,
  gbrain sync, learnings-search, telemetry, `~/.gstack` path conventions). No gstack vendoring, no
  runtime dependency on compound-engineering.

## [0.5.0] - 2026-06-02

- Add the operator-choice framework: a new contract document, `references/operator-choice.md`, that
  codifies the 3-way execution-backend choice — `inline` / `team-execution` / `cc-workflows-ultracode`
  (the canonical `ORCHESTRATION_MODES` enum strings). Lifecycle owns the *choice* of backend; it does
  not own execution.
- Add short prose offer hooks to `/loop` and `/work` that surface the operator-choice when work
  warrants a non-inline backend, pointing at the decision contract.
- Fix the `saga-spec.md` `orchestration_mode` cross-ref: it pointed at §7 (the save/restore/scan
  operation contract) instead of the decision contract; it now references
  `references/operator-choice.md`.
- Doc-only foundation. No code or helper is added in this release — the CLI-backed
  orchestration-choice helper is deferred to the `/work` rebuild.

## [0.4.0] - 2026-06-02

- Add a unified saga engine (`scripts/saga.py`): one source of truth for durable, resumable
  work-state with a stable derived identity (`issue-<N>` / `task-<slug>`, sticky for the life of
  the work), save/restore/scan, and gh-context aggregation. Sagas are written as an append-only,
  timestamped envelope log under `.claude/saga/sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`
  (gstack-style YAML frontmatter + `Summary`/`Decisions`/`Remaining`/`Notes` body), plus a derived,
  rebuildable `state.json` index. Envelopes are immutable; each save appends a new tick.
- The three legacy scripts — `scaffold_checkpoint.py`, `find_inflight_work.py`, and
  `load_saga_context.py` — are now thin wrappers that delegate to `saga.py`. Every CLI flag and JSON
  output key is preserved, so existing callers keep working.
- Behavior changes from this unification:
  - Storage moved from per-phase `checkpoints/` files to per-saga `sagas/<saga_id>/` envelope
    directories.
  - Ordering is now by envelope filename (the timestamped name **is** the canonical order), never by
    filesystem `mtime`. This makes ordering deterministic and robust under rsync/backup/snapshot
    restore.
  - Saves are append-only (a new immutable tick per save) instead of overwriting a single checkpoint.
  - Three stored state axes — `lifecycle_phase` (CE flow position), `phase_status` (phase
    completion, drives the next phase), and `status` (thread disposition) — replace the prior
    ad-hoc fields; `maturity` is derived at `/handoff` time, not stored. Frontmatter lists use
    full-snapshot replace semantics (a tick's lists replace; absent carries forward; empty clears).
- Add a plugin-level contract document, `references/saga-spec.md`, that the lifecycle consumers
  (`/plan`, `/work`, `/resume`, `/loop`) implement against.
- **Upgrade warning:** complete any in-flight `/loop` work before upgrading. Legacy
  `.claude/saga/checkpoints/` state is read as a low-priority `scan` fallback for one
  version only and then dropped — finish or re-save active loops so they migrate into the new
  `sagas/` layout.

## [0.3.0] - 2026-06-01

- Rebuild `/ideate` from a thin facilitative stub into a full divergent→convergent engine ported from
  compound-engineering and adapted to the infiquetra world: parallel frame agents generate many
  grounded candidates, the orchestrator critiques all and presents only the survivors, and cut ideas
  stay first-class and revivable. Adds a two-way thought-partnership — the operator's seed ideas feed
  *into* the frame agents (build on / challenge / combine) and face the identical critique — and a
  revival state machine that re-enters the filter with new evidence, preserving explicit rejection as
  the quality mechanism.
- Add infiquetra-specific grounding to `/ideate`: a grounding-fit gate (proceed / decline /
  recommend `/office-hours` / ask) weighing idea breadth against available grounding; a
  context-library reader (`*-context-library` repos via `gh`, local-clone preferred); a named-repo
  reader for multi-repo asks; read-only `gh` issue-theme clustering on backlog intent; and smart-auto
  web research for the cross-domain-analogy frame. Adaptive frame count (1–6) scales to scope.
- Rebuild `/brainstorm` into a thinking-partner engine that deep-dives one chosen idea (a `/ideate`
  survivor or a named topic) into a right-sized requirements document: scope assessment, a product
  pressure-test, one-question-at-a-time dialogue, 2–3 approaches with a non-obvious angle, and a
  `requirements-ready` artifact under `docs/brainstorms/` for `/plan`.
- Add reference files: `skills/ideate/references/convergence-and-partnership.md`,
  `skills/ideate/references/ideation-artifact.md`, and
  `skills/brainstorm/references/requirements-sections.md`. Self-contained — no runtime dependency on
  compound-engineering.
- Add `/handoff` to route durable lifecycle artifacts to `mission-control` prepared issue drafts, with a
  thin handoff-envelope helper that records source, maturity, target hints, blockers, open questions,
  and the `/issue --prepare` routing command without owning SDLC issue bodies. Teach
  `/plan <issue>` and `/work <issue>` to consume handoff maturity and source context from prepared
  SDLC issues.

## [0.2.0] - 2026-05-31

- Rename the plugin from `infiquetra-loop` to `saga`; "loop" named only the `/loop`
  router command, not the whole idea-to-ship lifecycle the plugin covers. The `/loop` command name
  is unchanged.
- Rename the ignored runtime-state directory from `.claude/infiquetra-loop/` to
  `.claude/saga/`; `mission-control` updated in lockstep.
- Rename the handoff-envelope `loop_owner` field to `lifecycle_owner`.
- Document the command set by lifecycle phase: Think, Plan & execute, Hand off, Review, and
  Improve & route.

## [0.1.0] - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
