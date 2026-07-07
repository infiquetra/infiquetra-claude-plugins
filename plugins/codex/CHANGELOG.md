# Changelog

## [Unreleased]

## [0.1.0] - 2026-07-06

### Added

- Register the `codex` plugin with `/codex:delegate`, `codex-coder`, and `codex-reviewer`.
- Add the `codex.delegation.v1` envelope schema (roles `coder`/`reviewer`, modes
  `read-only`/`task`, review lenses, evidence levels, status vocabulary) mirroring
  `agy.delegation.v1` minus members that do not apply to codex's v1 scope (KTD1).
- Add `Envelope` dataclass with fail-loud validation (`EnvelopeError`) at
  `plugins/codex/scripts/codex_delegate.py`.
- Vendor `plugins/fleet-core/scripts/fleet_commons_shim.py` byte-identically into
  `plugins/codex/scripts/fleet_commons_shim.py`, per the established fleet-commons +
  vendored-shim distribution mechanism (`{#fleet-commons-mechanism-463}`); the vendored copy is
  covered by the existing vendored-copy drift guard
  (`tests/test_fleet_commons_resolution.py`).
- Add the `bridge_receipt.v1` emitter seam (`_supervised_receipt`, parity with
  `plugins/agy/scripts/agy_delegate.py:1390-1412`): a completed run that actually launched
  `codex` maps a schema-valid CLI `bridge_receipt.v1`; launch-failure paths emit no receipt.
  This moves `codex-bridge` from `PENDING_EMITTERS` to `IN_REPO_EMITTERS` in
  `tests/test_bridge_receipt_drift.py` (KTD6).
- Add `tests/test_codex_delegate_contract.py` (envelope round-trip valid/invalid) and
  `tests/test_codex_plugin.py` (plugin.json required fields).

### Notes

- The supervised `codex exec` runner, evidence-bundle writer, diff-scan machinery, and registry
  rewire are out of scope for this unit and land in U2–U4 of
  `docs/plans/2026-07-06-codex-first-party-bridge-plugin-plan.md`.
