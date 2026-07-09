# Changelog

## [Unreleased]

## [0.1.1] - 2026-07-09

### Added - output-attested bridge receipts (#388)

- `plugins/codex/scripts/codex_delegate.py`: bridge receipts now include `receipt_emitter`,
  `run_id`, parsed or byte-derived `external_tokens`, and `output_attestation.v1` over
  `last-message.txt` so Saga can reject zero-token or unattested Codex output as
  `proof-integrity`.

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
- Add the supervised synchronous `codex exec` runner: verified 0.142.5 invocation shape
  (`exec --json -o … -s … -c model_reasoning_effort=…`, `-m` only when a model is set), prompt
  fed via stdin write-then-close, timeout and no-output watchdogs, cumulative output byte cap
  (`MAX_OUTPUT_BYTES`), whole-tree kill (process group, SIGTERM→SIGKILL escalation) with the
  kill outcome captured — an unreaped tree surfaces as terminal `shutdown_incomplete`, never as
  a clean timeout.
- Add SIGTERM/SIGINT die-clean handling across the whole bundle span (launch window AND clone
  setup / token parse / diff scan / bundle writes): kill the codex tree, write a terminal
  `result.json`, tear down the clone, exit nonzero.
- Add the evidence bundle at `.claude/codex/runs/<run-id>/` (envelope, prompt, JSONL
  transcript, last message, command argv, token accounting, `result.json` — all JSON written
  atomically via tmp+rename); every attempted run ends with an on-disk terminal status, even on
  unexpected post-launch exceptions.
- Add enforced mode surfaces: reviewer runs `-s read-only` with a snapshot-relative diff-scan
  (only NEW dirt flags `out_of_scope_mutation`; reversions of pre-existing dirt are surfaced as
  `reverted_paths`/`reversion_suspected` audit signals; the scan excludes only
  `.claude/codex/runs`, keeping the rest of `.claude` visible); coder runs confined to a
  disposable remote-stripped clone with patch capture, never the live tree.
- Add `tests/test_codex_delegate_contract.py`, `tests/test_codex_delegate_modes.py`,
  `tests/test_codex_delegate_lifecycle.py` (real-subprocess kill/terminality proofs, live smoke
  gated on `codex login status`), and `tests/test_codex_plugin.py`.

### Notes

- Invoking `codex_delegate.py` without `--validate-only`/`--dry-run` launches a live,
  supervised `codex exec` subprocess by default.
- The saga registry/dispatch rewire off `codex:codex-rescue` ships alongside this release in
  saga `0.73.1` (see `plugins/saga/CHANGELOG.md`).
