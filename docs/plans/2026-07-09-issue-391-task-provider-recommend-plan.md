---
title: Task Provider Recommendation Primitive - Issue #391
type: feat
status: active
date: 2026-07-09
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/391
---

# Task Provider Recommendation Primitive - Issue #391

## Summary

Add an advisory `recommend()` primitive for task-to-provider routing. It returns a ranked ladder of viable engine variants, including each candidate's prompting protocol, cost metadata, and egress suitability, without dispatching any engine or replacing `engine_resolver.resolve()`.

---

## Problem Frame

Issue #391 asks for the upstream choice that `engine_resolver.resolve()` deliberately does not answer. `resolve()` requires exactly one `capability` or explicit `engine`, then returns one `Resolution` for advisory or dispatch use (`plugins/saga/scripts/engine_resolver.py:320` and `plugins/saga/scripts/engine_resolver.py:424`). The registry already has capability ratings, cost metadata, and deterministic candidate ranking (`plugins/saga/scripts/engine_registry.py:574` and `plugins/saga/scripts/engine_registry.py:681`), but there is no public helper that returns a ranked, policy-aware ladder for "what should this task use?"

Current registry data is close but not complete for the issue's sensitivity requirement. Rows expose `substrate`, `cost_speed_rank`, `cost_per_token`, `cost_class`, `latency_class`, and prompting protocols (`plugins/saga/scripts/engine_registry.py:322`), while seed rows show all current chat/completion engines using networked providers even when invoked through in-repo CLIs (`plugins/saga/references/engine-registry.yaml:31`, `plugins/saga/references/engine-registry.yaml:105`, `plugins/saga/references/engine-registry.yaml:190`, and `plugins/saga/references/engine-registry.yaml:262`). Sensitive/no-egress routing therefore needs an explicit row field; deriving it from `substrate` would be wrong for agy.

---

## Requirements

R1. `recommend()` returns an ordered list of candidates, not a singleton, whenever more than one row satisfies task constraints.

R2. `policy="free-first"` ranks free viable rows ahead of metered viable rows while still respecting capability fit and context constraints.

R3. `policy="cheapest-viable"` ranks by cheapest sufficient candidate after filtering for capability fit, sensitivity, token/context fit, and explicit constraints; it must not select a globally cheap row that is a poor fit. Default sufficient fit is `MODERATE` or stronger, matching the current resolver's WEAK-as-no-fit posture.

R4. Every candidate carries the engine id, variant, capability rating, prompting protocol, cost metadata, context window, latency class, egress policy, and a human-readable reason.

R5. Sensitive tasks only return `egress_policy="local-only"` candidates. If none exist, `recommend()` returns an explicit empty/halt result and never falls back to networked providers.

R6. `recommend()` is advisory and read-only. It must not call preflight, invoke a provider, write manifests, satisfy gates, or alter `engine_dispatch.py`.

R7. Existing `engine_resolver.resolve()` behavior remains unchanged; explicit engine resolution, capability dispatch, fallback/halt role posture, overlays, payload assembly, and protocol preservation keep their current tests.

R8. The Saga plugin release surfaces and drift guards reflect the new helper and registry schema field.

---

## Key Technical Decisions

**KTD1: Add `engine_recommend.py` rather than overloading `engine_resolver.resolve()`.** `resolve()` is the single-selector dispatch/advisory contract. `recommend()` answers a prior question and should stay side-effect-free, so a new module keeps dispatch semantics stable.

**KTD2: Use `egress_policy` as an explicit registry row field.** `substrate` describes how the row is installed or reached, not whether task content leaves the machine. Agy is `in-repo` but still sends content to Gemini, so sensitivity filtering needs `local-only|networked` as a closed vocabulary.

**KTD3: Build recommendations from registry candidates, not a second capability scorer.** The helper should reuse `Registry.ranked_candidates()` so overlays, deprecations, capability ratings, and existing tie-break behavior remain single-source.

**KTD4: Separate policy ordering from viability filtering.** Capability support, minimum rating, context window, and egress constraints filter the candidate set first. `free-first` and `cheapest-viable` only order viable rows.

**KTD5: Empty sensitive results are terminal recommendations, not fallbacks.** If no local-only candidate exists, the helper returns an explicit halt/empty result that callers can surface. Falling back to networked rows would violate the issue's core safety constraint.

**KTD6: Recommendation rows copy protocol and cost metadata from `EngineEntry`.** Do not call `_resolution_from_entry()` or `preflight()` during recommendation; those belong to resolver/dispatch paths and would blur the read-only guarantee.

**KTD7: Cheapest means deterministic unit-price score, then existing registry tie-breaks.** `cheapest-viable` uses `cost_per_token.input_usd + cost_per_token.output_usd` as the primary price score after viability filtering, with `cost_speed_rank` and `registry_order` as deterministic tie-breaks. If implementation adds output-token estimates later, that is a follow-up ranking refinement, not v1 scope.

---

## Implementation Units

### U1. Registry Egress Policy Field

Add a strict egress policy field to registry rows so sensitivity routing is data-backed instead of inferred.

**Goal:** Extend `EngineEntry` and registry validation with `egress_policy: local-only|networked`, then author the field on every checked-in engine row.

**Requirements:** R4, R5, R8.

**Files:** `plugins/saga/scripts/engine_registry.py`, `plugins/saga/references/engine-registry.yaml`, `tests/test_saga_engine_registry.py`, `tests/test_engine_registry_lint.py`.

**Approach:** Add `EGRESS_POLICIES = ("local-only", "networked")`, parse the required field in `EngineEntry.from_dict()`, expose it on the dataclass, and reject unknown or missing values. Mark all current networked chat/completion rows `networked`; use fixture-only local rows in tests unless a real local/no-egress row already exists by implementation time.

**Test scenarios:** Happy path: a fixture row with `egress_policy: local-only` loads and exposes the field. Error path: missing or unknown egress policy raises `RegistryError` naming the row. Shipped-registry path: every current registry row declares an egress policy. Regression path: existing capability ranking tests still pass.

**Verification:** `tests/test_saga_engine_registry.py`, `tests/test_engine_registry_lint.py`.

### U2. Advisory Recommendation Module

Implement the read-only recommendation API over the registry's ranked candidates.

**Goal:** Add `plugins/saga/scripts/engine_recommend.py` with typed task-shape input, recommendation rows, result status, and deterministic policy ordering.

**Requirements:** R1, R2, R3, R4, R5, R6, R7.

**Files:** `plugins/saga/scripts/engine_recommend.py`, `tests/test_engine_recommend.py`.

**Approach:** Define a small public surface such as `recommend(task, *, registry, overlay=None) -> RecommendationResult`. The task shape should include `capability`, optional `policy` defaulting to `cheapest-viable`, optional `sensitive`, optional `token_estimate`, optional `min_rating` defaulting to `MODERATE`, and optional `limit`. Use `registry.ranked_candidates()` as the base set, filter weak/under-floor rows, context-window failures, and sensitive networked rows, then sort according to the selected policy. For `cheapest-viable`, sort by unit-price score, then `cost_speed_rank`, then `registry_order`; for `free-first`, sort viable free rows before viable metered rows and preserve registry candidate order within each cost class. Include a `next_rung(index=1)` or equivalent accessor so callers can explicitly walk the ladder without reimplementing list indexing.

**Test scenarios:** Happy path: with three viable rows, result contains at least two ordered candidates and `next_rung()` returns the second. Free-first path: free viable rows rank ahead of metered rows when both satisfy the task. Cheapest-viable path: lower unit-price score ranks first only after the default `MODERATE` capability floor is satisfied, and a WEAK free row is excluded. Protocol path: every candidate carries non-empty prompting protocol copied from its row. Error path: unknown policy or non-integer token estimate raises `RegistryError`.

**Verification:** `tests/test_engine_recommend.py`.

### U3. Sensitivity and Empty-Result Semantics

Prove sensitive routing never leaks into networked providers and produces an explicit halt when no local-only candidate exists.

**Goal:** Encode the egress failure mode as a first-class recommendation result rather than an exception that encourages fallback.

**Requirements:** R5, R6.

**Files:** `plugins/saga/scripts/engine_recommend.py`, `tests/test_engine_recommend.py`.

**Approach:** For `sensitive=True`, filter to `egress_policy="local-only"` before policy ordering. If the filtered set is empty, return a result with `status="halted"` or `status="empty"` plus a reason such as `no local-only candidate supports capability ...`. Do not include networked candidates in an advisory "alternatives" field for sensitive tasks.

**Test scenarios:** Sensitive happy path: a fixture local-only row is selected and all returned candidates are local-only. Sensitive no-candidate path: result is halted/empty, candidates are empty, and the reason names no local-only candidate without suggesting a networked fallback. Side-effect path: monkeypatch resolver preflight/dispatch-adjacent functions so the test fails if recommendation calls them.

**Verification:** `tests/test_engine_recommend.py`.

### U4. Documentation, Release Surfaces, and Saga Trace

Keep the installed plugin metadata and durable decision trail synchronized with the new helper.

**Goal:** Update release surfaces and journal decisions so future work knows `recommend()` is separate from dispatch and sensitivity is explicit data.

**Requirements:** R8.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`, `docs/work-sessions/2026-07-09-issue-391-task-provider-recommend.md`.

**Approach:** Bump the Saga plugin version and marketplace entry in the same implementation PR. Add a changelog entry describing `engine_recommend.py` and `egress_policy`. Keep the decision entry focused on the dispatch boundary and egress field. During `/work`, record the work-session evidence and link this plan plus issue #391.

**Test scenarios:** Release parity: marketplace and plugin version match. Documentation drift: Saga plugin contract test expects the bumped version. Diff hygiene: no generated cache or local saga state is staged.

**Verification:** `tests/test_saga_plugin.py`, `scripts/sync_marketplace.py --check`, `scripts/check_release_surface_parity.py`, `tools/release_surface_diff_guard.py --base-ref origin/main`, `git diff --check`.

---

## Scope Boundaries

In scope:

- `plugins/saga/scripts/engine_recommend.py` as an advisory Python helper.
- Minimal `egress_policy` registry schema and checked-in row updates.
- Recommendation tests covering ranking, protocol, egress, context, and side-effect boundaries.
- Saga plugin release metadata, changelog, and decision journal updates.

Out of scope:

- Wiring `recommend()` into `/plan`, `/work`, `/engines`, or team-execution command UX.
- Changing `engine_resolver.resolve()` selection semantics.
- Changing `engine_dispatch.py`, bridge invocation, manifests, or gate authority.
- Adding a real local model row unless one already exists and can be validated inside this issue.
- Building a full pricing service or telemetry-backed optimizer.

Deferred to follow-up work:

- Operator-facing command or skill integration that calls `recommend()` from lifecycle surfaces.
- Runtime telemetry feedback into recommendation ranking.
- Local/no-egress provider onboarding once a real local row is available and validated.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| `egress_policy` gets confused with `substrate` | Sensitive tasks may be routed to networked providers | Closed vocabulary, required field, and fixture proving agy-like `in-repo` rows can still be `networked` |
| Recommendation duplicates registry ranking logic | Future overlay or rating changes drift | Use `Registry.ranked_candidates()` as the only candidate source |
| Free-first picks bad free rows | Cheap-but-weak candidate outranks sufficient paid candidate | Default `min_rating` to `MODERATE` and filter viability before cost policy ordering |
| Cheapest-viable means different things to different implementers | Ranking drift or reviewer disagreement | Define v1 price score as `input_usd + output_usd`, with `cost_speed_rank` and `registry_order` tie-breaks |
| Helper accidentally starts acting like dispatch | Side effects or gate confusion | Do not call resolver preflight/dispatch; add a side-effect sentinel test |

---

## Sources and Grounding

- `plugins/saga/scripts/engine_resolver.py:320` - current single-selector resolve contract.
- `plugins/saga/scripts/engine_resolver.py:424` - current exact-one-of target parsing.
- `plugins/saga/scripts/engine_registry.py:322` - current `EngineEntry` row metadata.
- `plugins/saga/scripts/engine_registry.py:574` - current ranked candidate helper.
- `plugins/saga/scripts/engine_registry.py:681` - current rating/cost-speed/registry-order sort key.
- `plugins/saga/references/engine-registry.yaml:31` - Codex row, networked CLI provider.
- `plugins/saga/references/engine-registry.yaml:105` - Agy row, in-repo CLI but networked provider.
- `plugins/saga/references/engine-registry.yaml:190` - Ollama Cloud HTTP row, free but networked.
- `docs/engineering-journal/DECISIONS.md#engine-registry-schema-currency-452` - registry cost/ranking metadata is authored data.
- `docs/engineering-journal/DECISIONS.md#provider-auth-preflight-389` - `invocation.auth` precedent for row-authored provider boundary data.

---

## Verification Plan

Focused checks:

```bash
uv run pytest tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py -v
uv run ruff check plugins/saga/scripts/engine_recommend.py plugins/saga/scripts/engine_registry.py tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py
uv run ruff format --check plugins/saga/scripts/engine_recommend.py plugins/saga/scripts/engine_registry.py tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py
uv run mypy plugins/saga/scripts/engine_recommend.py plugins/saga/scripts/engine_registry.py tests/test_engine_recommend.py tests/test_saga_engine_registry.py tests/test_engine_registry_lint.py --ignore-missing-imports
```

Release and broad checks:

```bash
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
uv run pytest tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v
git diff --check
```

Full CI parity if focused checks pass:

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

---

## Routing

Destination: merge.

Recommended execution backend: inline. The change is single-repo, bounded to Saga registry/recommendation code plus tests and release surfaces. Team-execution is not warranted unless implementation discovers broader lifecycle wiring or security-sensitive dispatch changes.

Next command: `/doc-review docs/plans/2026-07-09-issue-391-task-provider-recommend-plan.md`.
