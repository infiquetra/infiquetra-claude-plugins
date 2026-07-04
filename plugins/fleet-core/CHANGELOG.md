# Changelog

All notable changes to the fleet-core plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
