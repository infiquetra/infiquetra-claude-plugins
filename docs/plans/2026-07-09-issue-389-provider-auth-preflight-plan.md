---
title: Provider Auth Preflight From Engine Registry - Issue #389
type: feat
status: active
date: 2026-07-09
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/389
---

# Provider Auth Preflight From Engine Registry - Issue #389

## Summary

Move CLI-engine credential availability from hardcoded resolver maps into registry-authored row data.
Current `origin/main` already has row-driven HTTP bearer auth under `invocation.auth`; this plan extends
that contract to CLI rows, exposes a normalized `EngineEntry.auth`, and makes preflight redaction-safe
for file, env, and secret-ref credential probes.

## Problem Frame

Issue #389 was written before the HTTP bridge landed. The old issue text correctly identifies
`ENGINE_CLI` and `ENGINE_CONFIG_PATHS` in `plugins/saga/scripts/engine_resolver.py` as the remaining
hardcoded CLI availability model, but its claim that `EngineEntry` has no auth concept is now stale for
HTTP rows. `plugins/saga/scripts/engine_registry.py` validates `invocation.auth` for HTTP bearer rows,
and `plugins/saga/references/engine-registry.yaml` already declares `auth.mode: bearer` with
provider env-var names for Ollama Cloud and DeepSeek.

The gap is now narrower and cleaner: CLI rows still cannot declare their binary or credential story in
the registry, so adding a third CLI engine with custom auth would still require resolver code changes.

## Requirements

R1. CLI rows declare their executable and credential availability requirements in
`plugins/saga/references/engine-registry.yaml`, not in resolver module constants.

R2. `EngineEntry` exposes a normalized `auth` mapping for every row, derived from `invocation.auth`.

R3. Supported auth modes include file existence, env-var presence, and secret-ref resolvability; existing
HTTP bearer rows keep working without YAML churn beyond any wording cleanup.

R4. `preflight()` checks CLI presence separately from credential presence and returns only credential
kind/name/ref metadata plus boolean/reason strings, never secret values.

R5. A new CLI engine row can preflight with no resolver-code change when it supplies `invocation.cli`
and `invocation.auth`.

R6. Existing fallback/halt behavior is preserved: capability worker/generator routes may fallback when
their selected engine is unavailable, while named engines and halt-role panel/advisory routes halt
loudly.

R7. Tests cover each auth mode, missing credentials, third-engine no-code-change behavior, redaction,
and existing HTTP bearer behavior.

R8. Saga plugin release surfaces are updated in the same PR because resolver and registry behavior
change.

R9. Preflight memoization is row-aware whenever an `EngineEntry` is supplied, so variants sharing an
`engine_id` cannot reuse a credential result from a different registry row or auth context.

## Key Technical Decisions

**KTD1: Reuse `invocation.auth` as the authored registry location.** HTTP rows already use
`invocation.auth`; adding a top-level `auth` field would create two registry contracts. `EngineEntry`
will expose `auth` as a normalized dataclass field copied from `invocation["auth"]`, while YAML keeps
auth colocated with invocation data.

**KTD2: Replace `ENGINE_CONFIG_PATHS` and `ENGINE_CLI` with row data.** CLI rows gain
`invocation.cli` and `invocation.auth`. `_cli_preflight()` will use the entry when supplied, defaulting
only for legacy test callers that omit an entry.

**KTD3: Auth modes are probe contracts, not secret fetch contracts.** `files` checks any configured
path exists, `env` checks env-var presence, `bearer` keeps existing HTTP key-env semantics, and
`secret-ref` checks resolvability through an injected boolean resolver. No helper returns or stores a
secret value.

**KTD4: Secret-ref default is fail-loud unavailable, not a fake backend.** If no secret-ref resolver is
provided, preflight returns unavailable with a reason naming the ref, not the value. A future secret
backend can inject the resolver without changing registry schema.

**KTD5: Redaction is enforced at the resolver boundary.** Return payloads and reasons may contain
`key_env`, file path, or secret ref strings; they must never contain the env-var value or a resolved
secret value.

**KTD6: HTTP transport tests stay in place.** Existing HTTP auth behavior is already row-driven and
must remain green; this work adds CLI parity instead of refactoring HTTP dispatch.

**KTD7: `RunMemo` preflight cache keys include row identity when row auth participates.** The current
memo cache is keyed by `engine_id`, which is safe only for legacy callers that omit `entry`. Once auth
lives on rows, preflight cache lookup and storage must key by `entry.key` or an equivalent row/auth
fingerprint when `entry` is supplied.

## Implementation Units

### U1. Registry Auth Schema

**Summary:** Extend registry validation so every row can carry normalized auth metadata.

**Changes:** In `plugins/saga/scripts/engine_registry.py`, add an `AUTH_MODES` closed vocabulary and
`EngineEntry.auth: dict[str, Any]`. Parse `invocation.auth` for all transports. Validate:

- `mode: files` with non-empty `paths: list[str]`
- `mode: env` with non-empty `key_env`
- `mode: bearer` with non-empty `key_env`
- `mode: secret-ref` with non-empty `ref`

CLI rows may omit auth only in legacy fixture tests that explicitly exercise backward compatibility;
checked-in registry rows must all declare auth.

**Tests:** Add `tests/test_saga_engine_registry.py` cases for valid auth modes, malformed modes, missing
mode-specific fields, and shipped registry entries exposing `entry.auth`.

### U2. Registry-Driven Preflight

**Summary:** Make resolver preflight read executable and auth requirements from `EngineEntry`.

**Changes:** In `plugins/saga/scripts/engine_resolver.py`, remove `ENGINE_CONFIG_PATHS` and reduce CLI
binary resolution to `entry.invocation["cli"]` or the engine id for legacy callers. Change
`preflight()` to pass `entry.auth` into credential probing for both CLI and HTTP rows. Add injectable
helpers for env lookup, file existence, and secret-ref resolvability so tests never touch real secrets.
Update `RunMemo` so preflight cache keys are row-aware when `entry` is present; legacy engine-id cache
behavior is only valid when no entry is supplied.

**Tests:** Extend `tests/test_saga_engine_resolver.py` for:

- CLI row with `mode: files` present and absent
- CLI row with `mode: env` present and absent
- CLI row with `mode: secret-ref` resolver present, absent, and missing resolver
- third CLI engine row using `invocation.cli` and auth without resolver code changes
- two rows for the same `engine_id` with different auth contexts do not share a stale memoized
  preflight result
- current HTTP bearer env behavior remains unchanged

### U3. Redaction And Halt/Fallback Behavior

**Summary:** Prove missing credentials are visible without leaking secret values.

**Changes:** Ensure preflight reason strings include only credential identifiers (`key_env`, `paths`,
`ref`) and never env-var values or resolver-returned values. Keep the existing resolve paths for
fallback-role and halt-role decisions; the only new input is a registry-driven preflight result.

**Tests:** Add redaction tests that set a dummy env-var value and a fake secret value, run preflight and
resolve paths, and assert the dummy secret strings do not appear in returned dicts, `Resolution`
strings, or dispatch/provenance helper output reached by this change. Add regression tests for
worker/generator fallback and advisory-reviewer/panel halt on missing credentials.

### U4. Registry Migration

**Summary:** Move the checked-in CLI rows onto explicit registry auth.

**Changes:** Update `plugins/saga/references/engine-registry.yaml`:

- codex rows: `invocation.cli: codex`, `auth.mode: files`, paths `~/.codex/auth.json` and
  `~/.codex/config.toml`
- agy rows: `invocation.cli: agy`, `auth.mode: files`, paths `~/.config/agy/config.json` and
  `~/.gemini/settings.json`

Keep existing HTTP rows' `auth.mode: bearer` unchanged. Update the registry header comment only if
needed to explain credential staleness/revalidation.

**Tests:** Add a shipped-registry assertion that every row has `entry.auth`, every CLI row has
`invocation.cli`, and capability routing winners remain unchanged.

### U5. Release Surfaces And Plan Traceability

**Summary:** Keep installed plugin metadata and docs aligned with behavior.

**Changes:** Bump `plugins/saga/.claude-plugin/plugin.json`, regenerate or update the saga entry in
`.claude-plugin/marketplace.json`, and add `plugins/saga/CHANGELOG.md` notes for registry-authored CLI
preflight. Keep the issue-draft artifact unchanged unless implementation discovers a material scope
correction that future planners need.

**Tests:** Run release-surface parity checks and the saga metadata/marketplace test.

## Scope Boundaries

In scope:

- `plugins/saga/scripts/engine_registry.py`
- `plugins/saga/scripts/engine_resolver.py`
- `plugins/saga/references/engine-registry.yaml`
- focused tests in `tests/test_saga_engine_registry.py` and `tests/test_saga_engine_resolver.py`
- saga plugin release metadata and changelog

Out of scope:

- new secret-manager vendor integration
- interactive credential setup or rotation
- changes to `engine_dispatch.py` invocation builders except for tests that prove no leaked values cross
  the resolver boundary
- changes to `HALT_ROLE_KINDS` or `FALLBACK_ROLE_KINDS`
- any gate authority change; external engines remain advisory/non-gated per the existing decisions

Deferred follow-up work:

- a real secret-ref backend once a specific store is chosen
- a CLI command that explains auth status for operators across every registry row

## Verification

Focused checks:

```bash
uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py -v
uv run ruff check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py
uv run ruff format --check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py
uv run mypy plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py --ignore-missing-imports
uv run bandit -r plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py
```

Release-surface checks:

```bash
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
python3 tools/release_surface_diff_guard.py --base-ref origin/main
uv run pytest tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v
git diff --check
```

Baseline already run before writing this plan:

```text
uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py -q
39 passed
```

## Route

Next command: `/doc-review docs/plans/2026-07-09-issue-389-provider-auth-preflight-plan.md`.
