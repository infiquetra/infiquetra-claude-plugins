# Changelog

## [Unreleased]

## [0.1.2] - 2026-07-06

### Added

- `plugins/agy/scripts/fleet_commons_shim.py` vendors the canonical
  `bridge_receipt.py` module (`plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py`)
  byte-identical, per the established fleet-commons + vendored-shim distribution mechanism
  (`{#fleet-commons-mechanism-463}`) — `agy_delegate.py`'s `SupervisedRunResult` now maps a
  schema-valid CLI `bridge_receipt.v1` for a completed run; launch-failure paths (agy missing,
  `OSError`) emit no receipt, since there is nothing to prove. The vendored copy is covered by the
  existing vendored-copy drift guard (`tests/test_fleet_commons_resolution.py`).

## [0.1.1] - 2026-07-05

### Added

- `agy-coder` agent: add validated `effort: medium` frontmatter field, consuming the fleet
  effort convention (#363) — proves the first-class effort vocabulary applies fleet-wide, not
  saga-only.

## [0.1.0] - 2026-06-30

### Added

- Register the `agy` plugin with `/agy:delegate`, `agy-coder`, and `agy-reviewer`.
- Add the shared `agy.delegation.v1` wrapper with validation-only, supervised foreground `agy`
  launch, run leases, evidence bundles, clone-backed diff derivation, write-set enforcement, and
  guarded `patch-only` / `auto-if-clean` apply policies at
  `plugins/agy/scripts/agy_delegate.py`.
- Add static prompt-contract tests, wrapper policy tests, harness transcript auditing, and live
  Claude Code harness proof for reviewer and coder flows.
