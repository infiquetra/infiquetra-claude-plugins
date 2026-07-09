---
title: "Capability: typed second-opinion reconciliation (#393)"
type: feat
status: active
date: 2026-07-09
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json
deepened: 2026-07-09
---

# Capability: typed second-opinion reconciliation (#393)

## Summary

Build a typed, Claude-adjudicated reconciliation path for external-engine evidence, backed by the existing append-only run-fact ledger. The work adds a third `divergence` intent, recovers rejected offloads as review signal, bounds advisory-jury panels, and lets `/retro` propose—never apply—recipe changes from recorded outcomes.

## Problem Frame

The chaperone contract currently permits claimed-only `claim_provenance` and has no intent-specific reconciliation protocol. `engine_dispatch` already preserves Claude as verifier-of-record and `run_ledger` already provides the local hash-chained store; #393 must close the reconciliation gaps without changing either authority boundary.

## Requirements

R1. Every chaperone-dispatched external-engine result produces a typed reconciliation result whose items name the source finding, status (`reconciled`, `dropped`, or `overridden`), Claude adjudicator identity, and rationale.

R2. A net-new engine finding omitted from the accepted result is represented as an explicit `dropped` item; verification cannot pass with an unaccounted-for net-new finding.

R3. Every valid `engine_intent` resolves to exactly one data-defined reconciliation recipe. Runtime dispatch and external-worker documentation consume the same registry contract.

R4. `divergence` becomes a valid third intent and treats Claude/engine agreement as an outcome requiring explicit review, while preserving the existing default `offload` behavior.

R5. A chaperone-rejected offload has a distinct manifest disposition with a non-empty note, and that note enters the Claude reviewer/validator evidence trail as advisory signal.

R6. Advisory-jury panel requests have a named hard cap, reject over-cap input, and record output only after Claude foreman reconciliation. No panel output can satisfy a gate.

R7. Reconcile and apply events append `reconciliation` facts to the existing hash-chained `run_fact.v1` ledger; `/retro` derives approval-gated recipe-update proposals from those facts and never mutates the registry itself.

R8. Both affected plugin release surfaces, documentation, journal decision, metadata parity checks, and focused tests ship in the same implementation change.

---

## High-Level Technical Design

One reconciliation controller owns intent-to-recipe lookup, item accounting, ledger fact construction, and the read-only proposal view. Existing `engine_dispatch` remains the authority boundary: it creates advisory evidence, builds manifests, and refuses non-Claude-verified or panel evidence as gates.

```text
external-engine output + Claude adjudication
                  |
                  v
  reconcile.py: typed result + recipe lookup + accounting
                  |
          +-------+--------+
          |                |
          v                v
  provenance manifest   run_ledger reconciliation fact
          |                |
          v                v
 reviewer evidence     /retro read-only proposal view
```

`run_ledger.py` currently accepts only `spend`, `cache`, `engine`, and `delegation` facts, so the controller extends that closed vocabulary with a `reconciliation` kind rather than creating a parallel file. The fact records the typed result or a stable pointer to its serialized canonical form, the recipe, event action (`reconcile` or `apply`), and the producer identifiers needed for append-only auditability.

---

## Key Technical Decisions

**KTD1 — Reconciliation is a Saga-local typed controller and an extension of `run_fact.v1`, not a new persistence subsystem:** `plugins/saga/scripts/run_ledger.py` already provides the append-only, hash-chained, leaf-produced store; a `reconciliation` fact kind preserves one audit trail and avoids the stale draft's parallel-ledger design.

**KTD2 — Canonical intent vocabulary remains fleet-core-owned:** add `divergence` to `plugins/fleet-core/scripts/fleet_commons/tier_palette.py`, then consume it in Saga validation and the generated plan-tier contract, because `execution_spec.py` imports rather than owns `ENGINE_INTENTS`.

**KTD3 — The recipe registry is closed and exhaustive:** use one data-defined recipe per canonical intent, validate registry parity against `ENGINE_INTENTS`, and reject unknown or duplicate mappings rather than defaulting to offload behavior.

**KTD4 — Dropped and overridden findings are explicit evidence, not prose omissions:** reconcile raw external findings against Claude's adjudicated set; a net-new finding must be reconciled, dropped with rationale, or overridden with rationale before verification proceeds.

**KTD5 — Rejected offloads and panel output stay advisory:** add a distinct disposition and reviewer-evidence route, but retain `engine_dispatch.satisfy_gate()` as the structural enforcement point that requires Claude verification and rejects panel/advisory evidence as gate authority.

**KTD6 — Advisory-jury fan-out gets a typed request/result path and `PANEL_N_CAP`, not an implicit reuse of `Verify`:** existing `Verify` only bounds verifier panels and the resolver returns one `Resolution`; a separate bounded request preserves that single-resolution contract and makes Claude foreman reconciliation mandatory before persistence.

**KTD7 — `/retro` emits proposal records only:** the retro reader derives a registry-update proposal from reconciliation facts, labels it approval-gated, and makes no direct registry write, matching `/retro`'s terminal advisory boundary.

---

## Implementation Units

### U1. Typed reconciliation registry and ledger writer

Create the domain controller that makes reconciliation and audit records explicit.

**Goal:** Add `plugins/saga/scripts/reconcile.py` with typed reconciliation item/result and recipe structures, exhaustive intent-to-recipe lookup, raw-versus-adjudicated finding accounting, and append-only reconciliation fact writes.

**Requirements:** R1, R2, R3, R7.

**Dependencies:** None.

**Files:** `plugins/saga/scripts/reconcile.py` (new); `plugins/saga/scripts/run_ledger.py`; `plugins/saga/references/run-fact-ledger.md`; `tests/test_reconcile.py` (new); `tests/test_run_ledger.py`.

**Approach:** Make recipes data rather than branch-local prose. The controller accepts typed raw findings and Claude adjudications, rejects malformed/duplicate finding identifiers, requires a rationale for `dropped` and `overridden`, and fails verification readiness when a net-new engine finding is absent from the result. Extend `FACT_KINDS` with `reconciliation`; append one fact per reconcile/apply action through `run_ledger.append_fact`, retaining the hash-chain and torn-tail behavior rather than handling files directly.

**Patterns to follow:** `plugins/saga/scripts/run_ledger.py:40-197` for closed fact vocabulary and append/read/verify behavior; `plugins/saga/scripts/engine_dispatch.py:663-722` for telemetry-only fact recording; `tests/test_run_ledger.py:91-158` for chain-integrity coverage.

**Test scenarios:** A normal offload with all findings accounted for yields typed reconciled items and one valid ledger fact; a net-new finding omitted from Claude's accepted output fails readiness until an explicit `dropped` or `overridden` item supplies rationale; empty findings yield an empty typed result without a crash; duplicate finding IDs and missing adjudicator/rationale reject before append; repeated reconcile/apply events append separate facts without mutating prior records; a corrupted or unknown reconciliation fact fails loudly under the existing ledger rules.

**Verification:** Registry parity and reconciliation tests prove each fact is valid `run_fact.v1`, chain verification still passes after normal writes, and an unaccounted net-new finding cannot be declared verified.

### U2. Canonical divergence intent and plan-time tier contract

Add `divergence` to the shared intent vocabulary and make its cost posture explicit.

**Goal:** Admit `divergence` through fleet-core, Saga execution-spec parsing, and the plan skill's generated tier table, with the `opus / high` chaperone default used for adversarial review.

**Requirements:** R3, R4.

**Dependencies:** U1.

**Files:** `plugins/fleet-core/scripts/fleet_commons/tier_palette.py`; `plugins/saga/scripts/execution_spec.py`; `plugins/saga/skills/plan/SKILL.md`; `tests/test_saga_execution_spec.py`; any existing tier-registry synchronization test that pins the generated table.

**Approach:** Add the intent once to `ENGINE_INTENTS`, retain the existing selector XOR and omitted-intent default, and have U1's exhaustive registry test make a missing recipe a failure. Add the generated tier-table row through its source/generation convention rather than editing a rendered copy if the repository exposes one.

**Patterns to follow:** `plugins/fleet-core/scripts/fleet_commons/tier_palette.py:98-101`; `plugins/saga/scripts/execution_spec.py:88-92`; `tests/test_saga_execution_spec.py:91-151`; `plugins/saga/skills/plan/SKILL.md:301-307`.

**Test scenarios:** An engine-selected and a capability-selected `divergence` unit parse, validate, round-trip, and resolve its high-tier default; an unknown intent still fails; omitted intent still defaults to `offload`; every canonical intent maps to exactly one U1 recipe; a plain Claude unit still serializes without `engine_intent`.

**Verification:** Focused execution-spec and tier-sync tests demonstrate no fallback or drift between the canonical vocabulary, registry, and user-visible tier table.

### U3. Rejected-offload disposition and manifest evidence wiring

Preserve a chaperone rejection as typed advisory review signal rather than a dead end.

**Goal:** Add a distinct rejected-offload manifest disposition with mandatory note, route it through reconciliation and reviewer/validator evidence, and update the chaperone contract documentation.

**Requirements:** R1, R2, R5.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_dispatch.py`; `plugins/saga/scripts/provenance_manifest.py`; `plugins/team-execution/skills/team-execution/references/worker-manifest.md`; `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`; `tests/test_saga_engine_dispatch.py`; `tests/test_provenance_manifest.py`; `tests/test_reconcile.py`.

**Approach:** Extend the existing manifest-builder precedence rather than create a second manifest path. A rejected offload must carry a non-empty normalized note, create a reconciliation item that reviewers can inspect, and remain advisory; no change may relax the existing `verified_by_claude`, observer-corroboration, or panel restrictions in `satisfy_gate()`.

**Patterns to follow:** `plugins/saga/scripts/provenance_manifest.py:54-76,396-475` for disposition serialization; `plugins/saga/scripts/engine_dispatch.py:769-1015` for manifest construction, adjudication, and gate refusal; `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:207-233` for chaperone manifest ownership.

**Test scenarios:** A rejected offload emits the new disposition and its exact non-empty note; a missing/blank note rejects the manifest; the note appears in the reconciliation/reviewer evidence contract; fallback, substituted-engine, integrity, and normal requested dispositions retain their precedence; rejected advisory evidence and panel evidence cannot satisfy a gate even when marked verified.

**Verification:** Manifest round-trip and dispatch tests prove the rejection is durable and visible without changing gate authority.

### U4. Bounded advisory-jury panel and foreman reconciliation

Add an explicit bounded panel path whose output is persisted only after Claude adjudication.

**Goal:** Define `PANEL_N_CAP`, validate typed external-engine panel requests, resolve and dispatch their members through a new bounded path, and require the Claude foreman to reconcile the combined output before ledger append.

**Requirements:** R1, R2, R6, R7.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/execution_spec.py`; `plugins/saga/scripts/engine_resolver.py`; `plugins/saga/scripts/engine_dispatch.py`; `plugins/saga/scripts/reconcile.py`; `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`; `tests/test_saga_execution_spec.py`; `tests/test_saga_engine_resolver.py`; `tests/test_saga_engine_dispatch.py`; `tests/test_reconcile.py`.

**Approach:** Model panel multiplicity separately from the existing `Verify` object and preserve `engine_resolver`'s existing one-`Resolution` API for ordinary callers. Validation hard-fails zero, malformed, unavailable, and over-cap requests; the dispatch path gathers advisory member evidence, requires a Claude foreman reconciliation result, then records only that typed result. It never writes raw panel output directly to the ledger or changes `NON_GATING_ROLE_KINDS`.

**Patterns to follow:** `plugins/saga/scripts/execution_spec.py:152-159,524-578` for hard-cap validation; `plugins/saga/scripts/engine_resolver.py:563-647` for panel halt-not-fallback behavior; `plugins/saga/scripts/engine_dispatch.py:28-35,934-1015` for advisory-only authority.

**Test scenarios:** A panel at the cap resolves and records only after foreman reconciliation; an over-cap request, zero count, malformed selector, and unavailable member hard-fail without partial append; empty member output is explicitly reconciled rather than silently ignored; duplicate member evidence is accounted once; a successful panel still cannot satisfy a gate; a failed foreman adjudication writes no apply fact.

**Verification:** Focused spec, resolver, dispatch, and reconciliation tests prove the cap is a blocking boundary and the ledger contains no unadjudicated panel output.

### U5. Read-only retro proposal view

Turn recorded reconciliation outcomes into approval-gated learning without self-modifying the registry.

**Goal:** Add a derive-on-read reconciliation-ledger reader and document `/retro`'s proposal output for intent-to-recipe updates.

**Requirements:** R3, R7.

**Dependencies:** U1, U3, U4.

**Files:** `plugins/saga/scripts/reconcile.py`; `plugins/saga/skills/retro/SKILL.md`; `tests/test_saga_retro.py` (new); `tests/test_reconcile.py`.

**Approach:** Read only valid `reconciliation` facts, aggregate enough evidence to describe a proposed recipe change, and emit a structured proposal marked `approval_required`. Keep the ledger and registry untouched during the read; malformed/torn facts follow the run-ledger reader's existing integrity behavior, and no-data returns an explicit no-proposal result.

**Patterns to follow:** `plugins/saga/scripts/run_ledger.py:141-197` for read/chain verification; `plugins/saga/skills/retro/SKILL.md:27-31,376-383` for the terminal advisory and no-saga-write boundaries.

**Test scenarios:** Populated reconciliation facts produce a proposal containing evidence references and an approval gate; an empty ledger produces no proposal; a proposal cannot mutate the recipe registry; invalid chain data fails visibly rather than generating a recommendation; repeated facts are deduplicated by stable reconciliation identity before aggregation.

**Verification:** New focused retro tests prove output is derive-on-read, approval-gated, and non-mutating.

### U6. Documentation, decision record, release surfaces, and integration closure

Make the installed plugins and durable records tell the same story as the implementation.

**Goal:** Update the external-worker and manifest references, run-fact schema guidance, engineering decision record, both plugin versions/changelogs, marketplace entry, and release-surface checks.

**Requirements:** R3, R4, R5, R6, R7, R8.

**Dependencies:** U1, U2, U3, U4, U5.

**Files:** `docs/engineering-journal/DECISIONS.md`; `plugins/saga/references/run-fact-ledger.md`; `plugins/saga/.claude-plugin/plugin.json`; `plugins/team-execution/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`; `plugins/saga/CHANGELOG.md`; `plugins/team-execution/CHANGELOG.md`; `tests/test_saga_plugin.py`; release-surface drift guard inputs as required by current checks.

**Approach:** Record the intent-to-recipe registry decision with its fourth-intent revisit condition and correct the issue's obsolete parallel-ledger assumption. Regenerate marketplace metadata through the repository tool, keep version literals synchronized, and avoid changing unrelated fleet-core release policy unless a current guard proves that cross-plugin release metadata is required.

**Patterns to follow:** `docs/engineering-journal/DECISIONS.md:3115-3156` for the binding gatekeeper/chaperone decisions; `docs/plans/2026-07-05-run-fact-ledger-401-plan.md` for run-fact release closure; `.github/workflows/ci.yml:146-194` for repository quality gates.

**Test scenarios:** Release metadata and marketplace entries agree for both plugins; changelog headings and version literals pass their drift guards; documentation names all three intents and the panel cap; the journal decision states that external engines remain advisory; the full focused reconciliation suite remains green after release-surface changes.

**Verification:** Metadata parity, marketplace sync check, release-surface diff guard, focused tests, and `git diff --check` all pass.

---

## System-Wide Impact

The change crosses `saga`, `fleet-core`, and `team-execution` inside this repository. It expands a shared input vocabulary and records new durable local facts, but it must preserve two invariants: external engines never gain gate authority, and the ledger remains append-only/hash-chained with derive-on-read consumers.

## Risks and Dependencies

| Risk or dependency | Mitigation |
| --- | --- |
| Existing #393 draft assumes no ledger exists. | Reuse `run_ledger` and add a closed `reconciliation` kind; do not create a second store. |
| `ENGINE_INTENTS` has more than one consumer. | Change its fleet-core source once and add parity tests through execution spec and recipes. |
| New disposition changes manifest precedence. | Extend the existing builder and cover fallback, substitution, integrity, proof, and requested paths. |
| Panel fan-out can amplify cost/rate-limit failures. | Use a named hard cap, fail before dispatch, and persist only foreman-adjudicated results. |
| Reconciliation may accidentally become a gate bypass. | Keep `satisfy_gate()` unchanged in authority semantics; security review and dedicated negative tests are required. |
| `/retro` could silently rewrite policy. | Emit approval-gated proposals only; test that registry data is unchanged after reads. |

## Alternatives Considered

**A separate reconciliation ledger:** Rejected because `run_ledger` already supplies the desired append-only, hash-chained local substrate and a second file would fragment audit history.

**Treat `divergence` as a special-case `second-opinion`:** Rejected because agreement-is-signal is a distinct semantic protocol that needs its own recipe and visible operator tier posture.

**Reuse the existing `Verify` panel as the advisory jury:** Rejected because it bounds verifier votes, not external-engine member fan-out, and cannot express foreman reconciliation or preserve resolver's one-resolution contract.

---

## Scope Boundaries

**In scope:** Typed reconciliation; a closed intent-to-recipe registry; the `divergence` intent; rejected-offload evidence; cap-bounded advisory panels; `run_fact.v1` reconciliation facts; read-only retro proposals; affected documentation, release metadata, and tests.

**Out of scope:** Any external engine satisfying a gate; a second executor kind; direct external-engine working-tree writes or residency; a scheduled monitoring service or dashboard; cross-repository changes; migration of existing `outcome_costs` or other historical ledger records.

**Deferred to Follow-Up Work:** A fourth intent or changed recipe prompted by an explicitly approved retro proposal; fleet-wide ledger adoption outside Saga; a separately scoped monitoring/measurement service.

---

## Team Structure

This is a deep, gated consensus job: it spans 20 planned files across six dependency-ordered units, changes a gate-adjacent evidence boundary, and must leave durable review evidence. Execution backend: `team-execution`; destination: `plan-only` until doc review accepts the plan.

### Workers

| Agent | Units | Tier | Mode | Depends-on | Engine | Intent |
| --- | --- | --- | --- | --- | --- | --- |
| `worker-reconcile-core` | U1 | sonnet/high | bypassPermissions | — | — | — |
| `worker-intent-contract` | U2 | sonnet/high | bypassPermissions | `worker-reconcile-core` | — | — |
| `worker-manifest-signal` | U3 | sonnet/high | bypassPermissions | `worker-reconcile-core`, `worker-intent-contract` | — | — |
| `worker-panel-foreman` | U4 | opus/high | bypassPermissions | `worker-reconcile-core`, `worker-intent-contract` | — | — |
| `worker-retro-reader` | U5 | sonnet/high | bypassPermissions | `worker-reconcile-core`, `worker-manifest-signal`, `worker-panel-foreman` | — | — |
| `worker-release-closure` | U6 | sonnet/medium | bypassPermissions | `worker-reconcile-core`, `worker-intent-contract`, `worker-manifest-signal`, `worker-panel-foreman`, `worker-retro-reader` | — | — |

`Engine` and `Intent` are `—` because this capability implements the containment protocol and must not use the protocol under construction as its own execution authority.

### Reviewers

| Agent | Focus | Required |
| --- | --- | --- |
| `devils-advocate-reviewer` | Search for silent-omission, incorrect precedence, and cap-bypass paths. | yes |
| `security-reviewer` | Confirm untrusted engine output remains opaque advisory data and cannot become gate authority. | yes |
| `architecture-reviewer` | Check registry/ledger/module boundaries, shared-vocabulary ownership, and dependency order. | yes |
| `testing-reviewer` | Challenge failure-path and integration coverage for reconciliation, manifests, caps, and retro reads. | yes |
| `clarity-reviewer` | Verify the two plugin contracts, plan tier table, journal, and release guidance remain aligned. | yes |

### Validators

| Agent | Group | Required | Selection Reason | Blocking |
| --- | --- | --- | --- | --- |
| `security-scanner` | Scanner | yes | Python parsing and a gate-adjacent evidence boundary change. | hard-fail blocks completion |
| `scenario-tester` | Tester | yes | Six issue flows need end-to-end evidence across controller, manifest, panel, and retro seams. | hard-fail blocks completion |
| `github-actions-monitor` | Monitor | yes | Implementation is expected to open a PR and must prove repository CI completion. | blocked signal blocks completion |

`runtime-monitor`, `deploy-watcher`, and contract/IaC/dependency scanners are not selected: this plan has no runtime deploy, API contract, infrastructure, dependency, or package-manifest change. Validator state belongs in `.claude/team-execution/validators/`, which is ignored by `.gitignore:55`.

### Execution Gates

- Reviewer consensus threshold: at least `9.0/10` from every reviewer, with no dimension below `7.0`.
- Reviewer non-consensus blocks validators unless the operator explicitly overrides.
- `security-scanner` and `scenario-tester` run only after reviewer consensus; a hard-fail blocks completion.
- `github-actions-monitor` captures CI evidence after the PR/CI phase; a required missing evidence record is a `missing-output` completion block.
- Maximum three remediation loops; then escalate with evidence and remaining risk.
- No merge, deploy, push, or PR action is authorized by this plan-phase artifact.

### Reference Files

- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`
- `plugins/team-execution/skills/team-execution/references/review-criteria.md`
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`
- `plugins/team-execution/skills/team-execution/references/validator-registry.md`
- `plugins/team-execution/skills/team-execution/references/validator-criteria.md`
- `plugins/team-execution/skills/team-execution/references/validator-execution-order.md`
- `plugins/team-execution/skills/team-execution/references/validator-evidence-state.md`
- `plugins/team-execution/skills/team-execution/references/validator-spawn-quirks.md`
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md`
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- `plugins/team-execution/skills/team-execution/references/artifact-pointers.md`

---

## Verification

Plan-phase validation:

```bash
python3 - <<'PY'
from pathlib import Path
import re

path = Path("docs/plans/2026-07-09-issue-393-typed-second-opinion-reconciliation-plan.md")
text = path.read_text(encoding="utf-8")
required = (
    "title: \"Capability: typed second-opinion reconciliation (#393)\"",
    "type: feat",
    "status: active",
    "date: 2026-07-09",
    "origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json",
    "## Requirements",
    "## Key Technical Decisions",
    "## Implementation Units",
    "### U1.",
    "### U6.",
    "## Scope Boundaries",
    "## Team Structure",
)
missing = [marker for marker in required if marker not in text]
assert not missing, missing
assert text.startswith("---\\n")
assert len(re.findall(r"^### U[1-6]\\. ", text, flags=re.MULTILINE)) == 6
print("plan contract valid")
PY
uv run pytest tests/test_saga_doc_formatting.py tests/test_saga_plugin.py -v
git diff --check
```

Implementation-focused checks:

```bash
uv run pytest tests/test_reconcile.py tests/test_saga_execution_spec.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_provenance_manifest.py tests/test_run_ledger.py tests/test_saga_retro.py -v
uv run ruff format --check plugins/saga/scripts/reconcile.py plugins/saga/scripts/run_ledger.py plugins/saga/scripts/execution_spec.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/provenance_manifest.py tests/test_reconcile.py tests/test_saga_execution_spec.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_provenance_manifest.py tests/test_run_ledger.py tests/test_saga_retro.py
uv run ruff check plugins/saga/scripts/reconcile.py plugins/saga/scripts/run_ledger.py plugins/saga/scripts/execution_spec.py plugins/saga/scripts/engine_resolver.py plugins/saga/scripts/engine_dispatch.py plugins/saga/scripts/provenance_manifest.py tests/test_reconcile.py tests/test_saga_execution_spec.py tests/test_saga_engine_resolver.py tests/test_saga_engine_dispatch.py tests/test_provenance_manifest.py tests/test_run_ledger.py tests/test_saga_retro.py
uv run mypy plugins/saga/scripts/ plugins/fleet-core/scripts/fleet_commons/ tests/ --ignore-missing-imports
uv run bandit -r plugins/saga/scripts/ plugins/fleet-core/scripts/fleet_commons/ -ll
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
python3 tools/release_surface_diff_guard.py --base-ref origin/main
git diff --check
```

## Sources

- GitHub issue `infiquetra/infiquetra-claude-plugins#393`, including the 2026-07-06 scope note requiring `run_ledger.append_fact`.
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`.
- `plugins/saga/scripts/run_ledger.py:40-197` and `plugins/saga/scripts/engine_dispatch.py:663-722`.
- `plugins/fleet-core/scripts/fleet_commons/tier_palette.py:98-101` and `plugins/saga/scripts/execution_spec.py:88-92,152-159`.
- `plugins/saga/scripts/provenance_manifest.py:54-76,396-475` and `plugins/saga/scripts/engine_dispatch.py:769-1015`.
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md:63-88` and `plugins/team-execution/skills/team-execution/references/external-engine-workers.md:207-233`.
- `docs/engineering-journal/DECISIONS.md:3115-3156` and `docs/engineering-journal/LEARNINGS.md:2124-2132`.

## Handoff

Run `/doc-review docs/plans/2026-07-09-issue-393-typed-second-opinion-reconciliation-plan.md` next. `/work #393` remains blocked on that review and on a subsequent explicit execution authorization.
