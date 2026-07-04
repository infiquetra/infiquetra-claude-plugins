---
title: "capability: data-driven provider credential resolution (env/secret-ref) with redaction-safe preflight"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# capability: data-driven provider credential resolution (env/secret-ref) with redaction-safe preflight

## Problem / Motivation

Saga's external-engine layer resolves and dispatches to `codex` and `agy` today, but the
availability check that decides whether an engine can be used at all is hardcoded, not
data-driven, and lives outside the registry that is supposed to be the single source of
truth for engine facts:

- `plugins/saga/scripts/engine_resolver.py:16-30` hardcodes two module-level dicts —
  `ENGINE_CLI = {"agy": "agy", "codex": "codex"}` and `ENGINE_CONFIG_PATHS` (a per-engine
  tuple of hardcoded config-file paths: `~/.config/agy/config.json`, `~/.gemini/settings.json`
  for agy; `~/.codex/auth.json`, `~/.codex/config.toml` for codex). Adding, removing, or
  reconfiguring an engine's credential story requires editing Python in the resolver module,
  not the registry.
- `plugins/saga/scripts/engine_resolver.py:52-76` (`preflight()`) reads those two dicts to
  decide `available: bool` — CLI-on-PATH check via `shutil.which`, then a config-file-exists
  check via `_default_config_exists`. It never inspects environment variables directly (no
  `os.environ` credential lookup), and it has no concept of a `secret-ref` resolution kind
  (e.g. a vault path or 1Password reference) — only "is there a file at this fixed path."
- `plugins/saga/scripts/engine_registry.py:164-180` (`EngineEntry`) — the dataclass that
  models each registry row — has no `auth` field at all. The registry
  (`plugins/saga/references/engine-registry.yaml`, 4 rows across 2 engines: `codex` at
  lines 22 and 52, `agy` at lines 78 and 108) cannot express per-row credential kind
  (`env` vs `secret-ref`), which env var name, or which secret path to check.
- This is exactly the "hardcoded 2-engine availability model" the fleet ideation dedup pass
  flagged: five separate auth/preflight idea variants converged on one root cause
  (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`, id `T2-F1-2`,
  axis `auth-config-secrets`, tier `structural`, verdict `survive`). Onboarding a third
  engine, or moving an existing one from a config-file credential to an env-var or
  secret-manager credential, currently means editing the two hardcoded dicts in
  `engine_resolver.py` rather than adding a row/field in the registry — the opposite of the
  registry-driven model the rest of `engine_registry.py`/`engine-registry.yaml` already
  establishes for capability ratings, cost/speed rank, and prompting protocol.
- The existing test suite (`tests/test_saga_engine_resolver.py:312-345`, three tests:
  `test_preflight_available_when_cli_and_config_present`,
  `test_preflight_reports_not_configured_when_config_absent`,
  `test_preflight_reports_not_installed_when_cli_absent`) locks in the current
  CLI-then-config-file-exists contract and will need to grow parallel coverage for the new
  `env`/`secret-ref` auth kinds without regressing the CLI-presence check.
- Binding constraints this work must respect (both already governing this code path):
  `{#external-engines-never-gatekeepers}` (#283) — external engines stay generator /
  advisory-reviewer / non-gated worker only, this issue does not touch gate authority; and
  the `/outcome` campaign's HALT-not-degrade convention — an engine whose credential cannot
  be resolved must halt loudly for roles that require it, never silently fall back to a
  degraded mode that hides the missing credential.

## Definition of Done

A merged PR that:

1. Adds a per-row `auth` block to the `EngineEntry` schema (`engine_registry.py`) supporting
   at minimum two `kind`s — `env` (an environment-variable name to check) and `secret-ref`
   (a resolvable secret-manager/vault reference) — validated the same way every other
   `EngineEntry` field is validated (`RegistryError` on malformed rows, via the existing
   `_require_*` helper family in `engine_registry.py`).
2. Rewires `preflight()` in `engine_resolver.py` to resolve credentials off each engine's
   `auth` block instead of the hardcoded `ENGINE_CLI` / `ENGINE_CONFIG_PATHS` dicts. CLI-path
   presence (`shutil.which`) stays a separate, still-mandatory check; credential presence is
   the new registry-driven check layered alongside it.
3. Never lets a resolved or attempted secret value reach a log line, error message, manifest,
   or `Resolution`/preflight return payload — only the credential's *name/kind* and a
   boolean/reason string.
4. Preserves halt-not-degrade for roles in `HALT_ROLE_KINDS` (`engine_resolver.py:19`,
   `advisory-reviewer`/`panel`): a missing credential for those roles is a hard halt, not a
   silent Claude-fallback. `FALLBACK_ROLE_KINDS` (`worker`/`generator`) keep their existing
   fallback-to-Claude behavior for CLI/config preflight failure — this issue extends what
   preflight checks, not who is allowed to swallow a failure.
5. Is verified by: a test per new `auth.kind` covering the present and absent case, a
   regression test that unmodified rows (bare CLI/config-file rows if any remain) still
   resolve exactly as before, and a redaction test that asserts a known dummy secret value
   never appears in any string returned by `preflight()`/`resolve()` or written to a
   provenance/manifest artifact during a simulated missing-credential run.

### Acceptance criteria
- [ ] `EngineEntry` (`engine_registry.py:164-180`) carries an `auth` field whose schema
      supports `kind: env` (env-var name) and `kind: secret-ref` (secret-manager reference)
      per row, validated at load time with `RegistryError` on a malformed/unknown `kind`.
      Check: `uv run pytest tests/test_saga_engine_registry.py -k auth_kind` → passes.
- [ ] `preflight()` (`engine_resolver.py:52-76`) resolves availability from the row's `auth`
      block (env-var lookup or secret-ref resolution) instead of the module-level
      `ENGINE_CLI`/`ENGINE_CONFIG_PATHS` dicts; the two dicts are removed or reduced to a
      CLI-binary-name lookup only (CLI-on-PATH stays a separate check).
      Check: `uv run pytest tests/test_saga_engine_resolver.py -k preflight_auth_env` → passes.
- [ ] Per-row auth declaration fully replaces the hardcoded 2-engine availability model — a
      third registry row with a new `engine_id` and its own `auth` block resolves correctly
      with zero changes to `engine_resolver.py`.
      Check: `uv run pytest tests/test_saga_engine_resolver.py -k third_engine_no_code_change` → passes.
- [ ] A missing credential for a `worker`/`generator` role (`FALLBACK_ROLE_KINDS`) still
      resolves the existing documented fallback-to-Claude path; a missing credential for an
      `advisory-reviewer`/`panel` role (`HALT_ROLE_KINDS`) halts loudly and never silently
      degrades.
      Check: `uv run pytest tests/test_saga_engine_resolver.py -k halt_role_missing_credential` → passes.
- [ ] No secret value (env-var value or resolved secret-ref value) ever appears in a
      `preflight()`/`resolve()` return payload, a log line, or a written provenance/manifest
      artifact — only the credential's name/kind and a boolean/reason string appear.
      Check: `uv run pytest tests/test_saga_engine_resolver.py -k redaction_no_secret_leak` → passes.
- [ ] Existing preflight contract (CLI-not-installed / config-not-found reasons) keeps
      passing unchanged for any row that has not been migrated to the new `auth` block.
      Check: `uv run pytest tests/test_saga_engine_resolver.py -k test_preflight_available_when_cli_and_config_present or test_preflight_reports_not_configured_when_config_absent or test_preflight_reports_not_installed_when_cli_absent` → passes.
- [ ] `plugins/saga/references/engine-registry.yaml`'s four existing rows (`codex` ×2,
      `agy` ×2) are migrated to declare an explicit `auth` block matching their real
      credential story (codex: `~/.codex/auth.json`/`config.toml`; agy: `~/.config/agy/config.json`
      or `~/.gemini/settings.json`) so the registry stays the single source of truth.
      Check: `python3 -c "import sys; sys.path.insert(0,'plugins/saga/scripts'); import engine_registry; r=engine_registry.Registry.from_dict(__import__('yaml').safe_load(open('plugins/saga/references/engine-registry.yaml'))); assert all(e.auth for e in r.engines)"` → exits 0.

### Out-of-scope / non-goals
**In scope:** the `EngineEntry`/`Registry` schema in `engine_registry.py`, the `preflight()`
function and its two hardcoded dicts in `engine_resolver.py`, the four rows in
`engine-registry.yaml`, and their direct test coverage in `tests/test_saga_engine_resolver.py`
/ `tests/test_saga_engine_registry.py`.

**Non-goals (explicitly deferred):**
- No new secret-manager integration/vendor is being adopted — `secret-ref` resolution can
  shell out to whatever mechanism the repo already trusts (e.g. `ansible-vault`,
  1Password CLI, or a simple file-based lookup); wiring an actual new secret backend is a
  separate capability if one is needed.
- No change to `engine_dispatch.py`'s dispatch/manifest/provenance contract beyond ensuring
  it never receives or echoes a raw secret value — the chaperone-dispatch protocol
  (`{#external-engine-chaperone-dispatch}`, #318) and gate authority
  (`{#external-engines-never-gatekeepers}`, #283) are unchanged.
- No change to `HALT_ROLE_KINDS`/`FALLBACK_ROLE_KINDS` membership itself — only what
  `preflight()` checks before those existing role-kind branches run.
- No UI/CLI surface for interactively entering or rotating credentials — this issue is the
  resolution model, not a credential-management tool.
- No change to the `codex`/`agy` invocation builders (`engine_dispatch.build_codex_invocation`,
  `build_agy_envelope`) — only the gate in front of them.

## Grounding References

- **Absorbed idea:** `T2-F1-2` ("Provider credential-resolution model (env/secret-ref) with
  secret redaction") — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`,
  theme T2 / frame F1, axis `auth-config-secrets`, `tier_guess: structural`,
  `verdict: survive`. Its `dod_sketch` (compressed in the survivors file, decompressed by
  reasoning about the axis/theme naming and the code the theme references): a merged PR
  adding an `EngineEntry.auth` block plus a `resolve_credentials` path, rewiring preflight
  off the hardcoded path map, verified by a test asserting a missing env-style credential
  yields `available: False` with a reason, plus a redaction grep/assertion that the
  credential *value* never appears in preflight/provenance output.
- **Consolidation rationale** (`issue-map-final.json`, `pf-provider-auth-preflight` entry):
  dedup already funneled five separate auth/preflight idea variants into this single
  `T2-F1-2` survivor; it is one clean PR (per-row auth block, env-var-first resolver,
  redaction guard, halt-not-degrade preflight) and merging it into any larger bridge issue
  would make that PR omnibus — this issue stays a standalone, minimal-blast-radius capability.
- **Code grounding** (verified directly against the current tree, not from memory):
  `plugins/saga/scripts/engine_resolver.py:16-30` (`ENGINE_CLI`, `ENGINE_CONFIG_PATHS`),
  `:52-76` (`preflight()`), `:19` (`HALT_ROLE_KINDS`), `:18` (`FALLBACK_ROLE_KINDS`);
  `plugins/saga/scripts/engine_registry.py:164-180` (`EngineEntry` dataclass, no `auth`
  field today); `plugins/saga/references/engine-registry.yaml:22,52,78,108` (the four
  registry rows to migrate); `tests/test_saga_engine_resolver.py:312-345` (existing
  preflight test contract to preserve).
- **Binding decisions this work must not violate**
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, section 2):
  `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; this
  issue never lets an engine self-attest availability into a gate decision.
  `{#external-engine-chaperone-dispatch}` (#318) — unaffected; this issue sits upstream of
  dispatch, in resolution only. `/outcome` campaign's HALT-not-degrade convention — mirrored
  here as "missing credential halts loudly for advisory/panel roles, never silently
  degrades."
- **Grounding brief context** (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`,
  section 1, "Model/effort reality" and section 8, theme roster item 2 "Provider/model
  routing beyond CLI engines — one router plugin, registry-driven") frames this capability
  as the registry-driven groundwork the wave-1 "external-engine offload lane" Objective
  depends on: routing/model decisions downstream assume the registry, not hardcoded Python,
  is authoritative for what an engine needs to be usable.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none — this is core saga-scripts schema/logic work with a
  well-scoped, mechanically testable surface (one dataclass, one function, four YAML rows,
  a handful of unit tests). It does not need opus-tier judgment or an external-engine
  second opinion; sonnet/medium matches the fleet's own tiering guidance for
  well-scoped structural changes with clear test oracles
  (`plugins/saga/skills/plan/SKILL.md:296-352` unit-tier table).
- No justification for going above sonnet is present: no ambiguous design tradeoffs, no
  cross-repo blast radius, no adversarial-review need beyond the existing `/code-review` gate.

## Release-Surface Checklist

This issue changes saga's engine-registry schema and resolver behavior — a
plugin-behavior change — so the following must ship in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (patch/minor per semver
      impact of the schema addition) and, if the description references engine resolution
      behavior, updated wording.
- [ ] `.claude-plugin/marketplace.json` — matching version bump for the `saga` entry.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the new `auth` block on `EngineEntry`,
      the preflight rewire, and the migration of the four existing registry rows.
- [ ] Any version/metadata drift-guard test in `tests/` (e.g. a test asserting
      `plugin.json` version matches `marketplace.json`) stays green after the bump —
      run it explicitly, don't assume.
- [ ] `plugins/saga/references/engine-registry.yaml`'s inline header comment (currently
      documenting "SEED DATA (2026-06-27)... re-validated by use through `/retro`") updated
      if the `auth` block changes how staleness/re-validation is framed for credential rows.

## Tier / Type / Objective / Wave

- **Tier:** structural
- **Type:** capability
- **Objective:** Stand up the external-engine offload lane
- **Wave:** wave-1

### Verification
```bash
uv run pytest tests/test_saga_engine_resolver.py tests/test_saga_engine_registry.py -v
uv run ruff check plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_registry.py
```

Expected: all green; the redaction test explicitly asserts a dummy secret value string
never appears anywhere in captured stdout/stderr or in any object returned by
`preflight()`/`resolve()`.

### Suggested next action

Use `/plan` on this issue to produce an implementation plan (schema shape for `auth`,
exact `secret-ref` resolution mechanism, migration order for the four registry rows).

### Intent

Saga's external-engine layer resolves and dispatches to `codex` and `agy` today, but the availability check that decides whether an engine can be used at all is hardcoded, not data-driven, and lives outside the registry that is supposed to be the single source of truth for engine facts:

### Context library links

_none_

### Files expected to change

- `plugins/saga/references/engine-registry.yaml`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`
- `tests/test_saga_engine_resolver.py`
- `tests/test_saga_engine_registry.py`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`

### Tests to add or update

- `tests/test_saga_engine_registry.py`
- `tests/test_saga_engine_resolver.py`

### Objective

"Stand up the external-engine offload lane"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/389
- Number: 389
- Created at: 2026-07-04T07:58:03.606234+00:00

