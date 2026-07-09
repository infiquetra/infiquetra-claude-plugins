---
title: Issue #451 Engine Offer Helper Plan
type: feat
status: active
date: 2026-07-09
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json
---

# Issue #451 Engine Offer Helper Plan

## Summary

Add one shared Saga `engine_offer` helper for lifecycle-stage engine offers. The helper resolves stage and unit shape into an advisory intent and tier, reads and writes per-repo stage preferences, and keeps mechanical offload defaults conservative and opt-out-able.

The implementation stays advisory-only: it can recommend `offload`, `second-opinion`, or `none`, but it never dispatches an engine, never gates completion, and never overrides the stage command's operator-choice flow.

## Problem Frame

Issue #451 asks for a single decision primitive behind five Saga surfaces: `ideate`, `brainstorm`, `work`, `doc-review`, and `code-review`. The issue traces to `T1-F2-1`, `T1-F2-2`, and `T1-F2-8` in `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`, where the survivor set explicitly calls for a tested helper, remembered per-stage choices, and opt-out offload for mechanical units.

Current Saga has the tier vocabulary and external-engine safety constraints, but no offer primitive. The `/plan` skill already renders the binding work-shape and external-engine tier table at `plugins/saga/skills/plan/SKILL.md:295`. `execution_spec.py` re-exports the canonical model/effort vocabulary and treats ordering as load-bearing at `plugins/saga/scripts/execution_spec.py:52`. External-engine resolution already distinguishes advisory and dispatch role kinds at `plugins/saga/scripts/engine_resolver.py:19`, while chaperone economics already keeps offload review policy in a pure helper at `plugins/saga/scripts/chaperone_economics.py:1`.

I searched for `engine_offer`, `engine-prefs`, and `mechanical-fingerprint` across `plugins/saga`, `tests`, and the cited plan docs and found no existing implementation. The five target stage skills have their own interaction and operator-choice rules, but no shared offer call site.

## Requirements

R1. The helper resolves each supported stage and unit shape to a closed advisory offer: `none`, `offload`, or `second-opinion`, with model/effort tiers drawn from the existing Saga vocabulary.

R2. Judgment-shaped review stages resolve to `second-opinion` with `opus/high` by default when an offer is appropriate; mechanical scaffold-shaped work resolves to `offload` with `sonnet/medium` by default.

R3. The helper never dispatches engines, never writes gate evidence, and never decides readiness. It only returns an offer object for the calling stage to present or reuse.

R4. `.saga/engine-prefs.json` is read before prompting. A stored preference for a repo/stage pair is reused silently in unattended mode.

R5. In attended mode with no stored preference, the helper returns a prompt-ready offer with explicit choices. The stage owns the actual operator prompt, then calls the helper to persist the selected preference.

R6. A stored `none` preference round-trips and suppresses future offers for that repo/stage pair without falling back to another intent.

R7. Mechanical-fingerprint defaults are conservative. Explicit unit shape beats text heuristics; text heuristics can default to offload only for scaffold/deterministic transform signals and must not classify judgment work as offload.

R8. Drift guards prove each of the five target stage SKILL.md files references the shared helper and does not document a hand-rolled offer equivalent.

R9. Saga release surfaces stay synchronized in the same PR: `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, and the Saga plugin version test.

## Key Technical Decisions

KTD1. Use one pure policy module plus a small CLI facade: `plugins/saga/scripts/engine_offer.py` owns offer calculation and preference persistence, and exposes a CLI that markdown-driven stage skills can invoke. This avoids five copy-pasted prose policies while keeping stage skills in control of user interaction.

KTD2. Stage skills prompt; the helper does not. The helper returns prompt choices and persistence commands, but `ideate`, `brainstorm`, `work`, `doc-review`, and `code-review` keep their existing blocking-question or channel-inline conventions.

KTD3. Preference state is repo-local and stage-scoped. Store `.saga/engine-prefs.json` as a small schema-versioned JSON object keyed by stage name, with atomic writes and clear failure on malformed JSON. Silent discard would make operator choices untrustworthy.

KTD4. Mechanical classification is intentionally narrow. Caller-provided `unit_shape` is authoritative; keyword fallback only recognizes scaffold/deterministic transform language. Unknown or judgment language returns no offload default.

KTD5. Use existing tier names literally. The helper returns `{"model": "opus", "effort": "high"}` or `{"model": "sonnet", "effort": "medium"}`, not compound strings such as `opus-high`, so it stays aligned with `execution_spec.py` and release-surface tests.

## Implementation Units

### U1. Add the Engine Offer Policy Helper

Create the shared helper that resolves stage, unit shape, preference, and attended/unattended mode into a structured offer.

**Goal:** Provide the single implementation point for R1, R2, R3, and R7.

**Requirements:** R1, R2, R3, R7.

**Files:** `plugins/saga/scripts/engine_offer.py`, `tests/test_engine_offer.py`.

**Approach:** Define closed vocabularies for stages, intents, unit shapes, models, efforts, and offer sources. Add dataclasses or typed dictionaries for `EngineOfferRequest`, `EngineOffer`, and preference values. Implement a pure `resolve_offer()` that accepts stage, repo root, attended flag, explicit unit shape, optional text fingerprint, and optional loaded preference. Invalid stage or vocabulary values raise `EngineOfferError`.

**Test scenarios:** Happy path: `code-review` with judgment shape returns `second-opinion` plus `opus/high`. Happy path: `work` with mechanical shape returns `offload` plus `sonnet/medium`. Edge case: unknown shape returns `none` or no default offer, not offload. Error path: unsupported stage raises a clear error. Integration scenario: helper uses existing model/effort strings that `execution_spec.py` accepts.

**Verification:** Focused tests prove intent/tier resolution and no dispatch/gate side effects.

### U2. Implement Repo-Local Preference Persistence

Add `.saga/engine-prefs.json` load/save support and make stored preferences control offer behavior.

**Goal:** Preserve ask-once repo/stage choices without making the store a committed artifact.

**Requirements:** R4, R5, R6.

**Files:** `plugins/saga/scripts/engine_offer.py`, `tests/test_engine_offer.py`.

**Approach:** Add `load_preferences(repo_root)`, `save_preference(repo_root, stage, preference)`, and atomic write behavior through a temp file plus replace. Use schema version `1` and a structure like `{"version": 1, "stages": {"work": {"intent": "offload", "model": "sonnet", "effort": "medium"}}}`. Keep tests in temporary directories so no real `.saga` state is written.

**Test scenarios:** Happy path: first attended choice writes a preference, second unattended call reuses it silently. Edge case: missing `.saga` directory is created as needed. Error path: malformed JSON raises `EngineOfferError` with the file path. Round-trip: stored `none` suppresses future offers. Called twice: saving the same stage preference twice is idempotent and leaves valid JSON.

**Verification:** Preference tests exercise temporary repo roots and assert no global state leaks between tests.

### U3. Add Mechanical-Fingerprint Classification

Implement the conservative scaffold/deterministic transform classifier used when callers cannot pass an explicit unit shape.

**Goal:** Default mechanical units to offload without accidentally offloading judgment work.

**Requirements:** R2, R7.

**Files:** `plugins/saga/scripts/engine_offer.py`, `tests/test_engine_offer.py`.

**Approach:** Add `classify_unit_shape()` that first honors explicit `unit_shape`, then checks caller-supplied labels and short text for a narrow allowlist such as `scaffold`, `template`, `generated`, `deterministic transform`, and `bulk rename`. Reject or return unknown for design/review/adversarial/architecture signals even if mechanical words also appear.

**Test scenarios:** Happy path: scaffold-shaped unit defaults to offload. Edge case: empty text returns unknown and no offload default. Error path: conflicting text with architecture/review language does not default to offload. Duplicate/called-twice: repeated classification returns stable output.

**Verification:** Unit tests pin the classifier's conservative behavior.

### U4. Wire the Five Stage Skill Call Sites

Document one shared call site in each target Saga skill and add drift guards.

**Goal:** Make the lifecycle surfaces consume the helper instead of forking offer policy.

**Requirements:** R5, R8.

**Files:** `plugins/saga/skills/ideate/SKILL.md`, `plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/skills/work/SKILL.md`, `plugins/saga/skills/doc-review/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md`, `tests/test_engine_offer.py`.

**Approach:** Add a compact "Engine Offer" block to each skill near its existing interaction/operator-choice section. The block should say to invoke `python3 plugins/saga/scripts/engine_offer.py offer ...`, respect `prompt_required`, and persist the operator's selected preference through the helper. It must also state that the offer is advisory and never a gate. The drift guard should load all five files and assert the shared helper command/reference appears exactly where expected.

**Test scenarios:** Happy path: drift guard finds the helper reference in all five skills. Edge case: removing one stage reference fails with the missing stage name. Error path: a local hand-rolled phrase such as `engine-prefs.json` without `engine_offer.py` should fail the guard. Integration: skill text preserves existing channel-inline/AskUserQuestion constraints.

**Verification:** `uv run pytest tests/test_engine_offer.py -k drift_guard` fails on missing call sites and passes after all five are wired.

### U5. Update Release Surfaces and Journal

Ship the helper as a Saga plugin behavior change with synchronized metadata.

**Goal:** Keep installed-plugin metadata, changelog, tests, and journal aligned with the implementation.

**Requirements:** R9.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`.

**Approach:** Bump Saga from `0.75.7` to `0.75.8`, add a changelog entry for issue #451, update the Saga metadata version assertion, and keep the decision entry tied to `engine_offer`'s advisory-only boundary and preference persistence. Run both release-surface checks before PR.

**Test scenarios:** Happy path: plugin.json, marketplace, and top changelog version match. Error path: diff-aware guard fails if `engine_offer.py` changes without the Saga plugin.json and changelog bump. Integration: full CI Release Surface Parity passes on the PR.

**Verification:** `uv run python scripts/check_release_surface_parity.py`, `uv run python scripts/sync_marketplace.py --check`, and `python3 tools/release_surface_diff_guard.py --base-ref origin/main` all pass.

## Scope Boundaries

This issue does not implement new external-engine dispatch. It only decides whether a stage should offer an existing intent/tier path.

This issue does not change Saga gate semantics, Team Execution reviewer math, or outcome completion rules. External engines remain advisory or chaperoned and never become gatekeepers.

This issue does not add new stage surfaces beyond `ideate`, `brainstorm`, `work`, `doc-review`, and `code-review`.

This issue does not redesign the generated `/plan` tier table. It consumes the existing vocabulary and should not hand-edit generated tier-table content.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Helper silently becomes a dispatch/gate surface | Keep dispatch out of `engine_offer.py`; tests assert returned object has no runner or gate fields. |
| Mechanical fingerprint over-classifies judgment work | Make explicit shape authoritative, keep keyword fallback narrow, and test conflicting language. |
| Preference corruption hides operator choice | Fail loudly on malformed JSON instead of overwriting it. |
| Skill docs drift from helper behavior | Add drift guard tests over all five SKILL.md call sites. |
| Release surface repeats #540 failure pattern | Include Saga version, marketplace, changelog, and version assertion in U5, and run both release guards locally. |

## Verification Plan

- `uv run pytest tests/test_engine_offer.py -q`
- `uv run pytest tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -q`
- `uv run ruff check plugins/saga/scripts/engine_offer.py tests/test_engine_offer.py`
- `uv run ruff format --check plugins/saga/scripts/engine_offer.py tests/test_engine_offer.py`
- `uv run mypy plugins/saga/scripts/engine_offer.py tests/test_engine_offer.py --ignore-missing-imports`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`

## Route

Destination: `merge`, per outcome authorization.

Execution backend: `inline`, recommended because the plan is one Saga plugin helper with local tests and no cross-repo deployment or consensus fan-out.

Next command: `/doc-review docs/plans/2026-07-09-issue-451-engine-offer-helper-plan.md`
