# Changelog

All notable changes to the fleet-core plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.15.0] - 2026-07-18

### Added

- Monotonic `close_owner_admission` / `inspect_owner_admission` on the lease broker (#358 R2):
  one committed close under the authority lock refuses every subsequent acquire, reserve,
  claim, and retry for that exact owner (`OwnerAdmissionClosedError`) while existing leases
  stay inspectable and releasable. Repeating close is idempotent; there is no reopen
  operation. The `close_generation` is issued from the registry's one fencing sequence so a
  teardown driver can re-verify the still-closed generation before emitting a zero-open
  completion receipt — the fence that prevents a spawn racing `teardown-complete`.
- Registry schema gains the bounded `closed_owner_admissions` map (pre-#358 authorities
  migrate to an empty map). Overflow evicts the lowest-generation record, which lapses that
  owner's admission back open until re-closed — the fence is scoped to record retention, a
  liveness ceiling, not unbounded history. The teardown driver re-closes at pass start,
  snapshots after the close, and refuses its receipt unless the pass-local generation is
  still the closed one, so eviction can cost a retry but never a false completion.

## [0.14.0] - 2026-07-17

### Added
- Added the pure shared liveness engine with bounded phi scoring, five-interval cold start,
  attribution-safe signal fusion, closed decisions, and Team-only terminal authority after three
  receipt-proven response windows.
- Kept lease renewal/expiry out of liveness evidence and made skew, boot drift, malformed numbers,
  unresolved sends, and exhausted delivery fail closed without granting destructive authority.

## [0.13.0] - 2026-07-17

### Added
- Added broker-owned prepare, commit, abort, conservative retained-authority inspection, canonical
  close receipts, and exact-receipt successor CAS for accepted external-runtime writes. Automatic
  restart-safe producer replay remains lifecycle work for #358.
- Added closed orphan-evidence schemas, bounded write-once quarantine, immutable refusal events and
  close-seal mirrors, plus deterministic read-only candidate projection.
- Kept authority and audit state owner-only, added Darwin process identity, and made generic release
  fail closed while settlement authority is retained. These are cooperative local-plugin safeguards,
  not a hostile same-user security boundary.
- Advanced the lease protocol to version 2 for the incompatible prepare/commit/abort settlement
  contract. Exact archived heads remain authoritative even after they leave bounded inspection.

## [0.12.0] - 2026-07-16

### Added
- Added the process-locked `lease_broker.py` fleet authority with separate agent and outcome-
  worktree pools, all-or-nothing batch reservation, trusted child binding, cooperative renewal,
  two-signal foreground release, owner/session teardown, fencing-token supersession, and safe
  dead-owner sweep. Registry writes are closed-schema, permission-checked, atomic, and rooted in a
  runtime-neutral state directory.
- Added closed concurrency admission records and shared defaults of three normal agents, four
  read-only agents, and seven aggregate agents. The broker records the resolved policy digest and
  refuses mixed live policy snapshots instead of re-resolving consumer policy.
- Published lease broker protocol version 1 so armed consumers reject a missing or skewed
  fleet-core installation before dispatch.
- Hardened the authority boundary after whole-diff review: renew and single-lease release require
  the exact fencing token, delegated parent validation and child grant share one transaction,
  abandoned pre-spawn admission pins expire and remain inspectable, owner teardown trusts only
  broker-recorded terminal evidence, and closed resource heads move to permission-checked cold
  archives when the hot registry reaches its bound without losing closed/superseded classification.
- Made the restricted-host boot identity fallback stable across processes and calls, so a denied
  kernel boot-time query falls back to Darwin's persistent boot record instead of making a newly
  acquired lease expire before its first renewal.

## [0.11.0] - 2026-07-14

### Added
- `intent_envelope.py` (#373): three OPTIONAL, additive schema-v1 fields on the canonical
  `IntentEnvelope` — `backends_permitted` (a type-strict unique backend list; the consuming
  dispatch seam owns the vocabulary), `degrade_policy` (closed vocabulary `halt` /
  `operator_away_one_rung`; absent means "not captured" → HALT by default when a backend
  posture is engaged), and `spend_envelope` (`SpendEnvelope`: `tier_ceiling` validated
  against the fleet `tier_palette.MODELS` ladder and/or `cost_ceiling_tokens`, a finite
  positive token budget; an empty object is an authoring error). Absent fields emit no keys,
  so every pre-#373 v1 envelope round-trips byte-identical — no forced migration; the
  closed-schema rule is unchanged (unknown keys still fail).
- `authorize_spend(spend, *, actual_tokens, requested_tier)` (#373): the pure, HALT-only
  pre-dispatch spend decision (`SpendAuthorization`) — a tier stronger than the ceiling or
  actuals at/past the cost ceiling deny for explicit step-up; an un-rankable tier denies
  (fail closed); wrong-typed actuals raise loudly. `None` actuals ("no data yet") and an
  undeclared tier do not engage their gate — leaf-produced actuals are self-attested, and the
  module threat model now says exactly that, plus the narrowing guarantee: the #373 fields
  only ever narrow dispatch relative to the uncaptured default, never grant a write path.

## [0.10.0] - 2026-07-14

### Added
- Issue-fence extraction is CRLF-safe: `` ```intent-envelope `` blocks on GitHub-web-authored
  bodies (CRLF line endings) extract identically to LF — adoption on the consumer side and the
  BLOCKING validity gate on the capture side both see the envelope (#380).
- `scripts/fleet_commons/intent_envelope.py` (#380): the canonical fleet `IntentEnvelope` —
  one committed run-start posture schema (`run_mode` + a `ceremony_gates` block of
  `reviews_required` / `merge` / `deploy_nonprod`, each `gate`|`auto` defaulting to `gate`),
  the single composed run-start posture interview (`INTERVIEW`, a typed challenge-response
  manifest with closed options), the mode-keyed machinery (`recommend_tier(work_shape,
  run_mode)` — unattended is exactly one ladder rung cheaper; `spend_posture(run_mode)` —
  cache-tight/silent vs interactive/ask-on-spend-increase; `resolve_spend_action` raising
  `PostureError` on an attended spend increase without an approval token;
  `self_select_posture` for unattended defaults from the same matrix), and the issue-carried
  envelope block (`render_issue_block` / `envelope_from_issue_body` /
  `outcome_start_decision`). The schema is closed per `schema_version` — unknown keys and
  off-vocabulary values fail loudly; provenance fields are documented self-attested and the
  envelope authorizes nothing by itself (the token-checked write class is #449's mechanism).
  Consumers: saga (`OutcomeSpec.intent` / `ExecutionSpec.intent` / `/outcome start`),
  team-execution (Step B1 `posture_check.py`), mission-control (issue-capture block).

## [0.9.0] - 2026-07-13

### Added
- `scripts/fleet_commons/delegation_state.py` grows the durable delegation-integrity attempt
  counter (#520 F1): `record_integrity_divergence` / `integrity_attempts` /
  `clear_integrity_attempts` over `.claude/delegation/integrity.json`, keyed session + engine with
  the same 4h TTL and fail-open-read posture as `active.json`. This is where the dispatch layer's
  re-queue-once-then-HALT count (KTD7, #384) now lives, so it survives one-process-per-attempt
  consumers.

### Fixed
- `delegation_state.arm()` / `disarm()` read-modify-write is now serialized under an exclusive
  `fcntl.flock` on a sibling `<name>.lock` file (#520 F4): two sessions arming concurrently could
  previously lose an entry last-writer-wins — a silent, fail-open loss of tripwire protection.
  Reads stay lock-free and fail-open.

## [0.8.5] - 2026-07-12

### Added
- Add `scripts/fleet_commons/audit_store.py`, the durable delegation audit store
  (`~/.claude/delegation-audit` by default): mirrors receipts, agy result snapshots, and provenance
  manifests keyed by run id/execution id, plus a write-once pre-fix draft snapshot primitive for the
  chaperone-dispatch path (#396). Deliberately machine-local and uncommitted, unlike
  `evidence_ledger.py`'s committed-per-saga store — different durability requirement, different home.
- Extend `scripts/fleet_commons/delegation_audit.py` with `reconcile_store(...)`, reconciling the
  durable audit store against claimed dispositions and flagging exactly the delegations whose
  disposition claims real execution but carry no schema-valid receipt as no-ops.

## [0.8.4] - 2026-07-09

### Added
- Add `divergence` to the canonical external-engine intent vocabulary with the high-tier
  Claude-chaperone posture used when agreement and disagreement both require explicit review.

## [0.8.3] - 2026-07-09

### Added
- Add `scripts/fleet_commons/output_attestation.py`, the shared `output_attestation.v1` helper
  for byte count, SHA-256, and empty-output proof over bridge-produced artifacts.
- Extend `bridge_receipt.emit_receipt(...)` with optional `receipt_emitter`, `run_id`,
  `external_tokens`, and `output_attestation` fields while keeping `bridge_receipt.v1` base
  validation backward-compatible for historical receipts.

## [0.8.2] - 2026-07-09

### Added
- Add the `offload-test-gated` tier-policy row so Saga can resolve cheap, ratify-only
  chaperone defaults for test-gated external-engine offloads from the shared fleet table.

## [0.8.1] - 2026-07-08

### Fixed
- Clamp positive `Retry-After` hints in `fleet_commons/retry_backoff.py` to `max_delay`, and treat
  zero or negative hints as absent so retry loops use computed jittered backoff instead of sleeping
  forever or retrying immediately.

## [0.8.0] - 2026-07-07

### Added — `delegation_audit.py` engine-parametrized classifier + corroborator, `delegation_state.py` arm/disarm liveness channel (#384, U1/U2)

- `scripts/fleet_commons/delegation_audit.py` — one auditor, two engine configs (agy, codex):
  `classify(transcript_path, engine=None) -> AuditClassification` (`real` / `fallback_suspected`
  vocabulary, generalizing the scan at `agy_delegate.py:995-1021`), `corroborate(engine, since_ts)
  -> BundleCorroboration` (launch flag + receipt presence under the engine's bundle root), and
  `reconcile(classification, corroboration, self_report) -> verdict` (`real` /
  `fallback_suspected` / `delegation_integrity`). Streams transcripts line-by-line under an 8 MiB
  cap (matching codex's `MAX_LAST_MESSAGE_BYTES` precedent). agy's original `classify_transcript`
  stays untouched as a parity tripwire (R7).
- `scripts/fleet_commons/delegation_state.py` — `arm(engine, session_id)` / `disarm(...)` /
  `active(session_id)` over `.claude/delegation/active.json`, atomic tmp+rename writes (codex
  `_write_json` precedent), TTL-reaped stale entries (default 4h), plus an `arm`/`disarm`/`status`
  CLI. Reads never raise — corrupt or missing state is always treated as unarmed (fail-open).
- Both modules live under `scripts/fleet_commons/` per the vendored-shim placement rule
  (`{#fleet-commons-mechanism-463}`); saga's hooks and dispatch layer load them the same way
  `engine_dispatch.py` already loads `bridge_receipt`.

## [0.7.0] - 2026-07-06

### Added — bridge_receipt.v1 schema module (#387, #383)

- `scripts/fleet_commons/bridge_receipt.py` — the `bridge_receipt.v1` proof-of-execution schema:
  `emit_receipt(...)` builder and `validate_receipt(dict) -> list[str]` (empty list = valid). Common
  core (`schema`, `engine_id`, `variant`, `transport`, `wall_time_s`, `bytes_produced`) plus
  transport-discriminated `runner` evidence — `{pid, argv, exit_code}` for `transport: cli`,
  `{url, status_code, model}` for `transport: http`. The emit helper stamps `schema`/version itself
  so a caller cannot mislabel a receipt.
- Canonical home for the schema per the fleet-commons + vendored-shim distribution mechanism
  (`{#fleet-commons-mechanism-463}`) — `plugins/agy/scripts/fleet_commons_shim.py` carries a
  byte-identical vendored copy, covered by the existing vendored-copy drift guard.

## [0.6.0] - 2026-07-06

### Added — ordinal cost-weight table beside the tier palette (#366)

- `scripts/fleet_commons/cost_weights.json` + `cost_weights.py` — a 16-cell ordinal weight grid and
  `to_spend(model, effort)`, co-located with `models.json` (the ordering it prices). Validated against
  the live `tier_palette` MODELS/EFFORTS ordering at import: completeness, per-axis strict monotonicity,
  and off-palette rejection all raise `CostWeightsError`, so a drifted table fails loud rather than
  silently mis-pricing a run (closes the `{#tier-vocab-ordering}` two-contracts gap for the cost axis).
- Weights are ordinal/relative, not dollar prices — hand-authored non-linear so premium tiers
  (opus/fable, xhigh) cost disproportionately more. Consumed by saga's `#366` `cost_budget` HALT and
  `spend_envelope`; additive-only, no change to existing fleet_commons modules.

## [0.5.0] - 2026-07-06

### Added — single-source tier palette: models.json registry + ladder ops (#370)

- `scripts/fleet_commons/models.json` — canonical model/effort registry with explicit per-model
  `rank`, per-effort `rung`, and per-model `effort_ceiling`. `tier_palette.py` now derives the
  ordered `MODELS`/`EFFORTS` tuples from these indices at import instead of hand-ordering them;
  import-time validation rejects duplicate/gapped rank and a missing/unknown `effort_ceiling`.
- `tier_palette.py` — `escalate` / `downgrade` / `clamp` / `stronger` / `strongest` ladder ops that
  reason in *strength* (so the opposite-direction MODELS strongest-first / EFFORTS weakest-first
  tuples can't be confused), plus `effort_ceiling` / `supports_effort` / `clamp_effort_to_model`
  (the AC5 surfaced-note clamp).
- `references/tier-palette.md` — onboarding runbook for adding a model/effort, encoding the
  `{#tier-vocab-ordering}` "grep `.index(` before extending a closed vocabulary" rule.

## [0.4.0] - 2026-07-05

### Added
- `scripts/fleet_commons/effort_rider.py` (#363): `inject_effort(prompt, effort, spawn_kind)` —
  the one swappable seam honoring a resolved `effort` value on every dispatch path. On the
  `workflow`/`external-engine` spawn kinds (which already accept effort as a real per-call knob)
  it is a guarded no-op pass-through; on the `agent` spawn kind — the native Agent-tool teammate
  path with no real per-call effort knob — it prepends a labeled `EFFORT_RIDER[effort]` proxy
  directive to the prompt. Also ships `reconcile_effort(resolved_effort, spawn_kind, ...)`,
  emitting a named `tiering-drift[<spawn_kind>]` line when a post-run actual (manifest-recorded
  effort, or rider text on the `agent` path) disagrees with the resolved value.
- References: `plugins/fleet-core/references/` gained the effort-convention documentation
  consumed by team-execution's `SKILL.md` (R8) — the single fleet-wide place `effort:`
  frontmatter's meaning and cascade precedence are documented once, not re-declared per plugin.

## [0.3.0] - 2026-07-05

### Added
- `scripts/fleet_commons/tier_resolver.py` — dispatch-time tier resolver (#362):
  `resolve(work_shape, role_kind, envelope_ceiling, operator_override) -> {model, effort,
  because, cheaper_fallback, needs_confirm}`, reading defaults from `tier_policy.json` and the
  ladder ops from `tier_palette` (never re-declaring `MODELS`/`EFFORTS`). Consumed cross-plugin
  via `fleet_commons_shim.load("tier_resolver")`; `fable`/`xhigh` reachable behind a
  `needs_confirm` gate.
- `scripts/fleet_commons/tier_policy.json` — machine-readable work-shape → tier registry
  (6 keys incl. the `mechanical`/`purely-mechanical` split).
- `scripts/fleet_commons/render_tier_table.py` — renders the `/plan` Step-1 tier table from the
  registry, drift-guarded against `plan/SKILL.md`.

## [0.2.0] - 2026-07-05

### Added
- `fleet_commons/retry_backoff.py` shared primitive (#348): `retry_with_backoff` (jittered
  exponential backoff, attempt cap, non-429 pass-through, injectable RNG/clock/sleep + a
  `retry_after` seam), a `CircuitBreaker` (CLOSED→OPEN→HALF_OPEN→CLOSED over an injected clock),
  and `bridge_call`. Stdlib-only; import-ready for engine-bridge (agy/codex) adoption. Consumers
  vendor the byte-identical `fleet_commons_shim.py` and call
  `fleet_commons_shim.load("retry_backoff")`.

## [0.1.0] - 2026-07-04

### Added
- Initial release: fleet-commons distribution mechanism (issue #463, DECISIONS
  `{#fleet-commons-mechanism-463}`).
- `scripts/fleet_commons/tier_palette.py` — canonical tier palette (`MODELS`, `EFFORTS`,
  `CHEAP_MODELS`, `ENGINE_INTENTS`, `model_rank()`, `effort_rank()`), moved verbatim from
  saga's `execution_spec.py` as the first-mover primitive.
- `scripts/fleet_commons_shim.py` — canonical resolution shim (five-rung ladder with rung
  provenance, `FLEET_COMMONS_DEBUG=1` stderr diagnostics, fail-loud); consumers vendor
  byte-identical copies guarded by a repo drift test.
