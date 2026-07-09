---
title: Issue #453 Engines Route Explain Plan
type: feat
status: active
date: 2026-07-09
origin: infiquetra/infiquetra-claude-plugins#453
---

# Issue #453 Engines Route Explain Plan

## Summary

Add an operator-facing Saga `/engines` command and registry CLI that can list engine rows, show local
pin/deprecate overlay state, write that repo-local overlay, and dry-run route explanations for a
capability without invoking an engine. The operator-facing route dry-run is `/engines route explain
<capability>`; the underlying CLI subcommand may be `route explain`. The work is a visibility and
local-policy layer over the existing registry ranking; it does not introduce a second ranking algorithm
or any gate authority.

## Problem Frame

The current registry already validates a closed capability vocabulary at
`plugins/saga/scripts/engine_registry.py:14`, ranks capability candidates by rating, `cost_speed_rank`,
and `registry_order` at `plugins/saga/scripts/engine_registry.py:502`, and exposes staleness detection at
`plugins/saga/scripts/engine_registry.py:543`. Operators still have no command surface to inspect that
state or ask why a capability resolves to one engine over another.

Current `main` has 21 Saga command docs under `plugins/saga/commands/` and no `engines.md`. Direct search
finds no `engine-overlay`, `engine_overlay`, `explain_capability`, or `route explain` implementation.
This is greenfield CLI/command work over existing registry primitives.

## Requirements

R1. `/engines` lists every registry row with `engine_id/variant`, declared capability ratings,
`cost_speed_rank`, `latency_class`, and stale/current state derived from `Registry.stale()`.

R2. `/engines` shows repo-local overlay state for each row: pinned for one or more capabilities,
deprecated, or neither.

R3. `/engines pin <capability> <engine_id>/<variant>` writes `.saga/engine-overlay.json` only after
validating that the variant exists and declares the requested capability.

R4. Pinning a variant that does not declare the requested capability fails with a typed error and leaves
the overlay file unchanged.

R5. `/engines deprecate <engine_id>/<variant>` writes an overlay entry excluding that variant from
overlay-aware candidate lists.

R6. If all candidates for a capability are deprecated, overlay-aware resolution and route explanation halt
with a typed error naming the capability and the exhausted candidate set.

R7. `/engines route explain <capability>` prints the ordered candidate list, selected winner, runner-up
when one exists, and the reason each candidate sorts where it does: rating first, then `cost_speed_rank`,
then `registry_order`, or an explicit pin override.

R8. `/engines route explain` is read-only and idempotent: it never invokes engines, never writes the
overlay, and produces byte-identical output for unchanged registry/overlay state.

R9. Existing resolver behavior remains unchanged unless a caller supplies a repo root or overlay. Existing
`Registry.by_capability(capability)` callers keep today's result.

R10. Saga release surfaces and tests land in the same PR: plugin manifest, marketplace entry, CHANGELOG,
and version assertions.

## Key Technical Decisions

KTD1. Keep core ranking single-source. Add an explanation helper that reuses the same candidate ordering
as `Registry.by_capability()`; `route explain` renders that helper instead of reimplementing sort logic.

KTD2. Make overlay explicit, not ambient. Store repo-local pin/deprecate state in
`.saga/engine-overlay.json`, parse it through a small helper module, and pass the parsed overlay into
registry/resolver helpers. Do not make `Registry.by_capability()` read the current working directory.

KTD3. Preserve no-overlay compatibility. Existing calls to `Registry.by_capability(capability)` and
`engine_resolver.resolve(..., registry=...)` keep byte-identical behavior. Overlay support is opt-in via
an explicit overlay object or `repo_root` parameter.

KTD4. Pins outrank ranking only after validation. A pin for `capability -> engine/variant` wins only when
the row exists, is not deprecated, and declares the capability. Invalid pins fail loud; they do not silently
fall back to the ranked ladder.

KTD5. Deprecation filters candidates before ranking. A deprecated row is excluded from overlay-aware
candidate lists. If that leaves no candidates, the caller gets `RegistryError` rather than a hidden fallback.

KTD6. CLI output is deterministic text/JSON over registry data. Tests should call the CLI entrypoint or
formatter directly and assert output order/content without live engine calls or external network.

## High-Level Technical Design

Add one small overlay helper and one CLI facade:

```text
plugins/saga/scripts/engine_overlay.py
plugins/saga/scripts/engine_registry_cli.py
plugins/saga/commands/engines.md
```

Registry lookup flow becomes:

```text
Registry.by_capability(capability)                         # unchanged no-overlay path
Registry.explain_capability(capability, overlay=None)      # shared ordered candidate model
engine_resolver.resolve(..., repo_root=...)                # optional overlay-aware path
engine_registry_cli.py route explain <capability>          # read-only rendered explanation
engine_registry_cli.py engines [pin|deprecate|clear]       # list or overlay mutation
```

Overlay file shape:

```json
{
  "version": 1,
  "pins": {
    "code-generation": "codex/gpt-5.5-xhigh"
  },
  "deprecated": [
    "agy/gemini-3.1-pro-high"
  ]
}
```

`engine_overlay.py` owns schema validation and atomic writes. `.gitignore` should ignore
`.saga/engine-overlay.json`, matching the existing local preference file pattern.

## Implementation Units

### U1. Add Repo-Local Overlay Helper

**Goal:** Provide validated load/save primitives for `.saga/engine-overlay.json`.

**Requirements:** R2, R3, R4, R5, R10.

**Files:** `plugins/saga/scripts/engine_overlay.py`, `.gitignore`, `tests/test_engine_overlay.py`.

**Approach:** Define `EngineOverlay` with `pins: dict[str, str]` and `deprecated: frozenset[str]`.
Implement `load_overlay(repo_root)`, `save_overlay(repo_root, overlay)`, and mutation helpers for pin,
deprecate, and clear. Validate version, object shape, capability names, and engine/variant key syntax.
Use atomic replace like `engine_offer.save_preference()`.

**Test scenarios:**

- Happy path: absent overlay loads empty.
- Happy path: save/load roundtrip preserves pins and deprecated keys.
- Error path: malformed JSON, wrong version, invalid capability, or malformed engine key fails loudly.
- Mutation path: failed validation leaves the prior overlay file unchanged.
- Hygiene: `.gitignore` contains `.saga/engine-overlay.json`.

**Verification:** `uv run pytest tests/test_engine_overlay.py -v`.

### U2. Add Overlay-Aware Registry Explanation

**Goal:** Let code ask "what would this route to, and why" without duplicating ranking logic.

**Requirements:** R3, R4, R5, R6, R7, R8, R9.

**Files:** `plugins/saga/scripts/engine_registry.py`, `tests/test_saga_engine_registry.py`.

**Approach:** Add immutable result objects such as `CapabilityCandidate` and `CapabilityExplanation`.
Add `Registry.ranked_candidates(capability, overlay=None)` and
`Registry.explain_capability(capability, overlay=None)`. Make `Registry.by_capability()` delegate to the
same ranked candidate helper with `overlay=None` by default. Explain rows should include key, rating,
`cost_speed_rank`, `registry_order`, and decision reason. Validate pins against row support and
deprecated state before honoring them.

**Test scenarios:**

- Regression: all existing no-overlay `by_capability()` winners remain unchanged.
- Pin: valid pin wins even when it would not rank first.
- Pin error: pin to an undeclared capability raises `RegistryError`.
- Deprecate: deprecated top candidate is skipped and next ranked candidate wins.
- Exhaustion: deprecating all candidates for a capability raises a typed `RegistryError`.
- Explain: rating tie identifies `cost_speed_rank`; cost tie identifies `registry_order`.

**Verification:** `uv run pytest tests/test_saga_engine_registry.py -k "pin or deprecate or explain" -v`.

### U3. Add CLI And `/engines` Command Surface

**Goal:** Expose listing, pin, deprecate, clear, and route-explain operations to operators.

**Requirements:** R1, R2, R3, R4, R5, R6, R7, R8.

**Files:** `plugins/saga/scripts/engine_registry_cli.py`, `plugins/saga/commands/engines.md`,
`tests/test_engine_registry_cli.py`.

**Approach:** Implement an argparse CLI with two top-level command families:
`engines list|pin|deprecate|clear` and `route explain`; expose the dry-run through
`/engines route explain <capability>` in the command doc. Default registry path is
`plugins/saga/references/engine-registry.yaml`; default release dates path is
`plugins/saga/references/model-releases.yaml`; default repo root is `.`. Provide deterministic text output
and a `--json` option for tests or future consumers. The command doc should point `/engines` at the CLI
and state that no engine dispatch happens.

**Test scenarios:**

- Listing includes every fixture row plus rating, cost rank, latency, stale/current, and overlay state.
- Pin command writes the overlay and subsequent list/explain output shows pinned state.
- Deprecate command writes the overlay and route explain skips the row.
- Route explain is read-only: repeated `/engines route explain` runs are byte-identical and overlay
  mtime/content is unchanged.
- Unknown capability returns nonzero with the same `RegistryError` wording.

**Verification:** `uv run pytest tests/test_engine_registry_cli.py -v`.

### U4. Thread Optional Overlay Through Resolver

**Goal:** Allow future lifecycle surfaces to honor the same repo-local overlay without changing today's
resolver default.

**Requirements:** R5, R6, R9.

**Files:** `plugins/saga/scripts/engine_resolver.py`, `tests/test_saga_engine_resolver.py`.

**Approach:** Add optional `repo_root` and/or `overlay` parameters to `resolve()` and pass the overlay into
the capability decision path only when supplied. Keep the memo key overlay-safe by including an overlay
fingerprint in capability-decision cache keys or bypassing cached decisions when overlay is supplied.
Explicit engine requests remain explicit and are not reranked by overlay.

**Test scenarios:**

- No-overlay resolver result remains unchanged.
- Overlay pin changes a capability resolution only when `repo_root` or `overlay` is supplied.
- Deprecated winner falls back to the next candidate.
- All candidates deprecated returns the same fallback/halt behavior as today's no-fit path for the role
kind.
- Memoized capability decisions do not leak across different overlays.

**Verification:** `uv run pytest tests/test_saga_engine_resolver.py -k overlay -v`.

### U5. Release Surfaces And Work Evidence

**Goal:** Ship the new operator-visible command as a complete Saga plugin release.

**Requirements:** R10.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`,
`docs/work-sessions/2026-07-09-issue-453-engines-route-explain.md`.

**Approach:** Bump Saga from `0.75.10` to `0.75.11`, update marketplace parity and CHANGELOG, add the
work-session artifact, and run release-surface guards.

**Test scenarios:**

- Saga plugin metadata and marketplace entry agree on `0.75.11`.
- CHANGELOG contains an entry for #453.
- The new `engines.md` command is packaged by `tests/test_saga_plugin.py`.

**Verification:** `uv run pytest tests/test_saga_plugin.py -v`; `uv run python scripts/sync_marketplace.py --check`; `uv run python scripts/check_release_surface_parity.py`.

## Scope Boundaries

- Do not change the shipped registry seed ranking or capability ratings in this issue.
- Do not dispatch any external engine from `/engines` or `route explain`.
- Do not make overlay state global or committed; it is repo-local and gitignored.
- Do not add automated stale-row remediation or benchmark refresh.
- Do not change Team Execution or execution-spec external-engine dispatch beyond optional resolver overlay
  support.

## Testing And Gates

Run focused gates first:

- `uv run pytest tests/test_engine_overlay.py tests/test_engine_registry_cli.py -v`
- `uv run pytest tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py -k "overlay or explain or deprecate or pin" -v`
- `uv run pytest tests/test_saga_plugin.py -v`
- `uv run ruff check plugins/saga/scripts/engine_overlay.py plugins/saga/scripts/engine_registry_cli.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py tests/test_engine_overlay.py tests/test_engine_registry_cli.py tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py`

Then run PR gates:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `git diff --check`
- Broad pytest. If Redis live-service tests are unavailable locally, use the established local exclusion
  and rely on CI for the full matrix.

## Recommended Execution

Backend: `inline`

Model: `sonnet`

Effort: `low`

Reason: this is bounded Python CLI and data-structure work over an already-tested registry module. The
main risk is preserving no-overlay behavior while making overlay behavior explicit, which is best handled
with tight regression tests.
