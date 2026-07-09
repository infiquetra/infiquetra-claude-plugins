---
title: Issue #382 Consensus Advisory Seat Plan
type: feat
status: active
date: 2026-07-09
origin: docs/sdlc-issue-drafts/plugin-fleet/pf-consensus-external-advisory-seat.md
---

# Issue #382 Consensus Advisory Seat Plan

## Summary

Add a typed, non-scoring external-engine advisory seat to Team Execution's consensus panel, plus a generated Claude-vs-external convergence report. The seat is present in reviewer guidance and helper code, but cannot affect the `>= 9.0` acceptance threshold, the `< 7.0` blocking rule, or Saga gate satisfaction.

## Problem Frame

Issue #382 is requirements-ready and explicitly combines two deliverables: the external advisory reviewer seat and the convergence diff that makes the seat useful (`docs/sdlc-issue-drafts/plugin-fleet/pf-consensus-external-advisory-seat.md:27`). The non-goal is equally explicit: the external seat must never count toward the consensus gate or become a second executor, resident teammate, wave participant, or direct git actor (`docs/sdlc-issue-drafts/plugin-fleet/pf-consensus-external-advisory-seat.md:125`).

Current Team Execution docs have only Claude reviewer rows in the base and optional registries (`plugins/team-execution/skills/team-execution/references/reviewer-registry.md:14`, `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:26`, `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:40`). The consensus protocol collects reviewer scores and gates directly on `ALL >= 9.0`, with the existing exclusion machinery only documented for precondition-bearing dimensions such as `architecture-reviewer` coverage (`plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26`, `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:66`, `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:82`).

The chaperone contract already says an external engine is advisory evidence consumed by one resident Claude chaperone, not a second executor or git participant (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md:16`). Saga already knows `role_kind="advisory-reviewer"` at the resolver layer, and marks advisory-reviewer/panel roles as halt-not-fallback roles (`plugins/saga/scripts/engine_resolver.py:19`). What is missing is the Team Execution panel shape and the dispatch/gate provenance that proves reviewer-role evidence remains non-gating.

## Requirements

R1. Team Execution documents a distinct external advisory seat outside the base/optional Claude reviewer tables, so the standard reviewer roster remains unchanged.

R2. Advisory reviewer results are excluded from the consensus denominator, the `ALL >= 9.0` decision, the `< 7.0` blocking-stop rule, and reviewer re-run selection under every score combination.

R3. Advisory absence, preflight halt, or external-engine failure is reported as an advisory-seat status and leaves the Claude-only consensus decision unchanged.

R4. A convergence report is generated when an advisory result exists, with explicit converged, Claude-only, external-only, and conflicting findings.

R5. The convergence report uses stable finding keys or fingerprints, not fuzzy prose matching, so the Claude lead remains verifier-of-record for any semantic reconciliation.

R6. Saga dispatch evidence can carry reviewer role provenance, and `satisfy_gate()` refuses `role_kind="advisory-reviewer"` evidence even if it is Claude-verified and observer-corroborated.

R7. External advisory dispatch reuses the existing chaperone contract and resolver role vocabulary; it does not introduce a new executor kind, residency path, direct git access, or fallback-to-Claude substitution for reviewer roles.

R8. Release surfaces stay synchronized in the same PR: Team Execution plugin version, marketplace entry, changelog, drift-guard tests, and engineering journal decision.

## Key Technical Decisions

KTD1. Add a small Team Execution consensus helper, not only prose drift guards: existing tests assert documentation text, but #382 needs executable evidence that advisory scores cannot move gate math. A helper under `plugins/team-execution/skills/team-execution/scripts/` keeps the model local to Team Execution without pretending there is a runtime consensus service.

KTD2. Model seat authority explicitly: reviewer results carry `seat="gated"` or `seat="advisory"` instead of relying on reviewer names or score conventions. Gate calculations consume only gated reviewer results; advisory results are available for reporting only.

KTD3. Make convergence matching key-based: findings compare by a caller-provided `key` or deterministic fingerprint fields, producing `converged`, `claude_only`, `external_only`, and `conflicting` buckets. The first version avoids semantic/fuzzy matching because a false convergence report would be worse than a conservative diff.

KTD4. Stamp dispatch role provenance on advisory evidence and refuse advisory-reviewer gate satisfaction: `AdvisoryEvidence.role_kind` should default to `worker` for backward compatibility, while `satisfy_gate()` gets an early role check for `advisory-reviewer`.

KTD5. Document advisory-reviewer dispatch as a chaperoned reviewer-role path, not a worker path: the resolver already treats `advisory-reviewer` as halt-not-fallback, so Team Execution should describe absence as advisory unavailability rather than Claude substitution.

KTD6. Bump Team Execution to `2.14.0`: this adds new user-visible panel behavior and helper code, so a minor version is clearer than another patch-only docs entry.

## Implementation Units

### U1. Add Consensus Advisory Helper

Create the executable model for gated reviewer math and advisory convergence reporting.

**Goal:** Add a small stdlib-only helper that accepts reviewer results, computes consensus from gated seats only, reports advisory absence as no-op, and builds key-based convergence reports.

**Requirements:** R2, R3, R4, R5.

**Dependencies:** None.

**Files:** `plugins/team-execution/skills/team-execution/scripts/consensus_advisory.py`; `tests/test_team_execution_consensus_advisory.py`; `tests/test_team_execution_consensus.py`.

**Approach:** Define dataclasses for reviewer results and findings, with a closed seat vocabulary. `calculate_consensus()` should return gated reviewers considered, excluded advisory reviewers, accepted boolean, blocking reviewer/dimension details, and rerun reviewer names. `build_convergence_report()` should compare Claude-panel and external findings by explicit key and report conflicts when matching keys differ in summary/severity/recommendation.

**Patterns to follow:** Team Execution keeps support scripts under `plugins/team-execution/skills/team-execution/scripts/`; existing consensus tests live in `tests/test_team_execution_consensus.py` and currently act as text drift guards.

**Test scenarios:** Happy path: three gated Claude reviewers pass at `>= 9.0`, external advisory reports `4.0`, consensus still accepts. Edge: no advisory result returns accepted Claude-only consensus with an advisory status of absent. Error path: invalid seat vocabulary raises a clear `ValueError`. Integration: convergence report fixture yields one converged, one Claude-only, one external-only, and one conflicting finding.

**Verification:** Focused tests prove advisory exclusion and convergence buckets without invoking external engines.

### U2. Add Advisory-Reviewer Gate Refusal

Make Saga dispatch provenance prove that reviewer-role external evidence can never satisfy a gate.

**Goal:** Add role-kind provenance to `AdvisoryEvidence` and make `satisfy_gate()` reject `advisory-reviewer` evidence before checking verification/corroboration.

**Requirements:** R6, R7.

**Dependencies:** None.

**Files:** `plugins/saga/scripts/engine_dispatch.py`; `tests/test_saga_engine_dispatch.py`.

**Approach:** Add `role_kind: str = "worker"` to the dataclass for backward compatibility. The current `Resolution` dataclass does not carry role kind, so this unit does not invent dispatch threading; reviewer-role callers construct advisory evidence with `role_kind="advisory-reviewer"` and the gate boundary enforces the refusal. Test with verified, observer-corroborated advisory-reviewer evidence to prove role refusal wins even when the normal worker evidence would pass.

**Patterns to follow:** `engine_dispatch.AdvisoryEvidence` already added additive fields such as `runner_receipt`; `satisfy_gate()` centralizes never-gatekeeper checks and already refuses unverified, uncorroborated, substituted, or unadjudicated evidence.

**Test scenarios:** Happy path: existing verified worker evidence with `observer_corroborated=True` still passes. Error path: `role_kind="advisory-reviewer"` verified/corroborated evidence raises `DispatchError`. Backward compatibility: constructing `AdvisoryEvidence` without `role_kind` preserves the worker default.

**Verification:** `uv run pytest tests/test_saga_engine_dispatch.py -k "satisfy_gate or advisory_reviewer" -q`.

### U3. Update Team Execution Protocol Docs

Bind the helper behavior into the operator-facing Team Execution protocol.

**Goal:** Update consensus protocol, reviewer registry, and external-engine worker guidance so the external advisory seat is visible, non-scoring, chaperoned, and convergence-diffed.

**Requirements:** R1, R2, R3, R4, R7.

**Dependencies:** U1, U2.

**Files:** `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`; `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`; `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`; `tests/test_team_execution_consensus.py`; `tests/test_team_execution_plugin.py`.

**Approach:** Add an "External Advisory Seat" section to the registry outside base/optional tables. Extend B3 score collection to display gated reviewer scores first and advisory output afterward. Extend the non-applicable/excluded-dimension section with an always-excluded advisory-seat case. Add a convergence-report shape to the consensus artifact. Cross-reference `role_kind="advisory-reviewer"` in external-engine worker docs and state that resolver halt/unavailability is advisory absence, not panel failure.

**Patterns to follow:** Existing docs already distinguish precondition exclusions from failures and use drift-guard tests to pin text that agents rely on.

**Test scenarios:** Documentation drift guards assert the advisory section is outside base/optional reviewer tables, the consensus protocol names always-excluded advisory seats, and convergence buckets are documented. Plugin contract tests assert external-engine docs mention `role_kind="advisory-reviewer"` and halt/no-op absence.

**Verification:** `uv run pytest tests/test_team_execution_consensus.py tests/test_team_execution_plugin.py -q`.

### U4. Update Release Surfaces And Journal

Keep installed-plugin metadata and durable decisions aligned with the behavior change.

**Goal:** Bump Team Execution to `2.14.0`, sync marketplace metadata, update changelog, and record the durable KTDs.

**Requirements:** R8.

**Dependencies:** U1, U2, U3.

**Files:** `plugins/team-execution/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`; `plugins/team-execution/CHANGELOG.md`; `docs/engineering-journal/DECISIONS.md`; `tests/test_team_execution_plugin.py`.

**Approach:** Update plugin description to mention the non-scoring external advisory seat and convergence diff. Run `uv run python scripts/sync_marketplace.py` after plugin metadata changes, then run parity checks.

**Patterns to follow:** `AGENTS.md` requires release surfaces in the same PR for plugin behavior, schema, command, prompt, or user-facing guidance changes.

**Test scenarios:** Metadata test expects `2.14.0` and matching marketplace entry. Release parity check passes against plugin JSON, marketplace JSON, and top changelog heading.

**Verification:** `uv run python scripts/sync_marketplace.py --check`; `uv run python scripts/check_release_surface_parity.py`; `python3 tools/release_surface_diff_guard.py --base-ref origin/main`.

## Scope Boundaries

This plan does not add external-engine execution, residency, direct git access, or a new worker kind. It does not change the base or optional Claude reviewer roster, reviewer prompts, the three-cycle cap, escalation rules, or any deployment behavior.

Deferred follow-up work: a standing divergence-rate dashboard, fuzzy semantic convergence matching, and an operator-facing `/outcome --loop` command that emits the objective loop without consulting the repo narrative.

## Risks & Dependencies

Risk: a prose-only implementation would satisfy docs while leaving the gate invariant untested. Mitigation: U1 creates executable helper tests and U2 adds a Saga gate-boundary test.

Risk: convergence matching may look more precise than it is. Mitigation: first version is key/fingerprint based and reports unmatched findings plainly instead of semantic merging.

Risk: role provenance could be mistaken for a gate signal. Mitigation: the only new gate-facing behavior is a refusal path in `satisfy_gate()`, and release docs state advisory-reviewer evidence is report-only.

## Sources / Research

- `docs/sdlc-issue-drafts/plugin-fleet/pf-consensus-external-advisory-seat.md:27` defines the seat and convergence-diff intent.
- `docs/sdlc-issue-drafts/plugin-fleet/pf-consensus-external-advisory-seat.md:125` pins the non-goals.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:26` shows the current B3 review cycle and score collection.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:66` defines `>= 9.0` and `< 7.0` gate semantics.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:82` defines the existing exclusion precedent.
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:14` and `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:26` show the current reviewer tables.
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:16` states the one-resident-chaperone boundary.
- `plugins/saga/scripts/engine_resolver.py:19` shows `advisory-reviewer` is an existing resolver role kind.
- `plugins/saga/scripts/engine_dispatch.py:41` defines advisory evidence; `plugins/saga/scripts/engine_dispatch.py:638` is the gate consumer to extend.
