# Changelog

All notable changes to the fleet-core plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
