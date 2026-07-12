# Changelog

## [Unreleased]

## [0.2.2] - 2026-07-12

### Added - durable delegation-audit-store mirror (#396)

- `plugins/agy/scripts/agy_delegate.py`: new `--audit-store` CLI option (default
  `~/.claude/delegation-audit`). Every bundle — validation-only and supervised alike — mirrors its
  `result.json` payload (and the embedded `bridge_receipt.v1`, when the run launched) to this
  durable, machine-local store outside the repo tree, resolvable by `run_id` alone independent of
  whether the originating `.claude/agy/runs/<run_id>` bundle directory (or its enclosing disposable
  worktree) still exists. `create_validation_bundle` / `create_supervised_bundle` gained an
  `audit_store_root: Path | None = None` parameter (skip when omitted — every existing direct caller
  is unaffected; the CLI resolves the real-world default).
- Every existing subprocess-driven CLI test now passes an isolated `--audit-store <tmp_path>` so no
  test writes into a real developer's home directory.
- Consumes the new `plugins/fleet-core/scripts/fleet_commons/audit_store.py` (fleet-core 0.8.5) via
  `fleet_commons_shim.load("audit_store")`.

## [0.2.1] - 2026-07-09

### Added - output-attested bridge receipts (#388)

- `plugins/agy/scripts/agy_delegate.py`: bridge receipts now include `receipt_emitter`,
  `run_id`, `external_tokens`, and `output_attestation.v1` over the emitted summary so Saga can
  reject zero-token or unattested delegated output as `proof-integrity`.

## [0.2.0] - 2026-07-07

### Changed — BREAKING: `provenance_required` now coerces unproven passing runs to fail loud (#390 U1)

- `plugins/agy/scripts/agy_delegate.py`: a passing status (`success`/`patch_ready`/`applied`) whose
  supervision verdict (`_real_agy_verdict`) is `unproven`, combined with `provenance_required=True`
  (the envelope default), now coerces the run status to `fallback_suspected` and exits non-zero via
  the existing exit mapping. **Behavior change**: callers that previously relied on exit 0 for an
  unproven run under `provenance_required=True` (the default) will now see exit 1 —
  `provenance_required` was parsed and threaded since its introduction but consulted nowhere; this
  closes that dead wire. `provenance_required=False` preserves the old behavior unchanged, and a
  status already `fallback_suspected` via the stdout marker is not double-coerced. Transcript
  auditing stays the Stop-hook's responsibility (#384) — the wrapper's only signal is
  `_real_agy_verdict`.
- Bundle-wide status consistency: `run-lease.json` now reports the same (post-coercion) status as
  `result.json` instead of the raw pre-coercion supervisor status, and the status→exit-code
  mapping has a single source (`_PASSING_STATUSES` / `_exit_code_for_status`) shared by `main()`
  and the contract tests (#390 code-review round).

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
