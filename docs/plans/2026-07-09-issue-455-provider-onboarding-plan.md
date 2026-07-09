---
title: Provider Onboarding, Registry Conformance, and Shadow-Mode Standing - Issue #455
type: feat
status: active
date: 2026-07-09
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/455
deepened: 2026-07-09
---

# Provider Onboarding, Registry Conformance, and Shadow-Mode Standing - Issue #455

## Summary

Add a safe provider-onboarding path that scaffolds an OpenAI-compatible HTTP registry row, proves every checked-in row reaches the existing dispatch substrate, and keeps new providers off advisory and panel roles until run-ledger evidence makes them eligible for explicit promotion.

---

## Problem Frame

The registry loader validates row shape and cross-references, but adding a provider still means hand-authoring every field (`plugins/saga/scripts/engine_registry.py:331` and `plugins/saga/scripts/engine_registry.py:500`). The existing CI step validates schema and model-release currency (`.github/workflows/ci.yml:78`), while the bridge receipt drift test accounts for emitter implementations (`tests/test_bridge_receipt_drift.py:170`); neither proves that every row can be converted into the invocation shape consumed by dispatch.

Issue #455 predates the generic HTTP bridge. Current architecture explicitly makes an OpenAI-compatible HTTP provider a registry row rather than a provider-specific code path (`plugins/saga/references/dispatch-adapter-contract.md:10` and `plugins/saga/scripts/engine_bridge_http.py:4`). Creating a generated provider bridge stub now would contradict that contract and produce dead code, so the scaffolder must wire rows to `engine-bridge-http` and `http-bridge` instead.

There is also no structural trust distinction between a new row and an incumbent. `EngineEntry` carries routing, cost, egress, invocation, and evidence metadata but no standing (`plugins/saga/scripts/engine_registry.py:331`), and `resolve_role()` expands every configured role member as an advisory reviewer (`plugins/saga/scripts/engine_resolver.py:368`). New rows therefore need a fail-closed probation tier enforced before advisory resolution, plus an evidence-only promotion assessment over the existing hash-chained run-fact ledger (`plugins/saga/references/run-fact-ledger.md:15`).

---

## Requirements

### Provider scaffolding

R1. `tools/add-engine.sh` accepts a compact, structured provider specification and can add one OpenAI-compatible HTTP row to a selected registry without hand-editing the registry. The generated row uses the existing generic HTTP bridge and defaults to `trust_tier: probation`, `write_capable: false`, `egress_policy: networked`, and advisory-only evidence semantics.

R2. Missing required metadata, an empty capability map or source list, an unsupported transport, a duplicate engine key, a stale concurrent registry edit, or a candidate that fails schema/conformance validation aborts before the destination registry changes. Re-running the same add must fail clearly and leave the file byte-identical.

R3. `docs/adding-a-provider.md` documents the exact provider-spec fields, dry-run/apply behavior, generic-bridge boundary, conformance checks, probation behavior, and explicit promotion workflow.

### Registry conformance

R4. A reusable offline conformance checker proves every live row is reachable by exact key, appears in the candidate set for each capability it advertises, materializes a dispatch invocation through the real invocation builder, and names a registered receipt emitter. It must not read credentials, call provider preflight, or perform network I/O.

R5. A deliberately dead-wired fixture can remain schema-valid but fails conformance with the row key and broken dispatch seam in the error.

R6. `tests/test_engine_registry_conformance.py` covers the checker, and a distinct `Engine Registry Conformance` CI step blocks pull requests independently of the existing schema/currency lint.

### Shadow-mode standing

R7. `EngineEntry` requires `trust_tier` from the closed vocabulary `probation|advisory`. Every checked-in incumbent row is explicitly `advisory`; scaffolded rows are explicitly `probation`; registry and `/engines` output expose the value.

R8. Probationary rows remain eligible for `worker` and `generator` offload. Capability-based advisory resolution excludes probationary candidates, explicit probationary advisory-reviewer resolution halts with a trust-tier reason, and a composing role cannot include a probationary member. Resolver memoization must include role kind so an offload selection cannot leak into a later advisory lookup.

R9. A read-only promotion assessment filters run-ledger `engine` facts by exact engine and variant and reports eligibility only after the five most recent matching runs all have `status=ok`, `proof_integrity_status=ok`, and non-empty `bridge_run_key`. Missing, corrupt, mixed-variant, unproven, or failed evidence is not eligible; promotion remains an explicit reviewed registry edit rather than an automatic telemetry write.

### Release integrity

R10. Saga release metadata, changelog, command/docs surfaces, tests, work-session evidence, and the engineering journal describe the shipped behavior consistently.

---

## Key Technical Decisions

**KTD1: Scaffold only the provider class the generic bridge actually supports.** Version 1 accepts OpenAI-compatible HTTP providers and derives their invocation/receipt wiring from the existing bridge. CLI providers require a real wrapper and are rejected instead of receiving an inert generated stub.

**KTD2: Use a compact JSON provider spec and a thin shell wrapper.** Python owns parsing, validation, rendering, conformance, and atomic writes; `tools/add-engine.sh` only locates the repository and forwards arguments. This keeps the tool script testable without reimplementing schema logic in shell.

**KTD3: Preserve the authored YAML with parser-anchored insertion.** Build and validate the candidate registry in memory, use PyYAML node marks to locate the top-level `roles` boundary, insert only the serialized row, re-parse the rendered result, recheck the source hash, and atomically replace the destination. Full-file `safe_dump()` is rejected because it would erase comments and create unrelated churn.

**KTD4: Conformance calls the real dispatch invocation builder but never provider preflight.** Schema validation and receipt-emitter accounting already exist. The missing proof is registry-to-resolver-to-invocation lockstep, which can be tested with synthetic task context and no credentials or network.

**KTD5: Trust standing is required authored data.** Missing or unknown `trust_tier` fails registry loading. Incumbents receive explicit `advisory` standing in the same change; the scaffolder is the only path that supplies the safe `probation` default.

**KTD6: Advisory eligibility is role-aware at selection time and rechecked at explicit resolution.** Capability routes skip probationary candidates for `advisory-reviewer` and `panel`, exact-key advisory requests halt, and role validation rejects probationary members. Including `role_kind` in the capability memo key prevents cross-role cache reuse.

**KTD7: Promotion is evidence-gated and read-only.** Five consecutive proof-integrity-valid successful facts for the exact variant are the v1 threshold. The assessment reports evidence and reasons; changing `trust_tier` remains a normal reviewed PR so machine-local telemetry cannot silently rewrite committed policy.

**KTD8: Existing incumbents keep standing without fabricating promotion history.** Their explicit `advisory` values preserve current behavior as a migration decision. The telemetry threshold applies only to future probationary rows seeking promotion.

---

## High-Level Technical Design

The onboarding path validates before it writes, while the runtime and promotion paths remain independent consumers of the same authored standing.

```text
provider spec -> row builder -> Registry.from_dict -> conformance checker
                                          |                 |
                                          +---- pass --------+
                                                   |
                                  parser-anchored atomic registry insert

registry trust_tier -> capability/role selection -> resolver -> dispatch

run-fact ledger -> exact-variant promotion assessment -> operator-reviewed PR
```

No onboarding or promotion command invokes an external engine. Dispatch remains the only provider-call surface, and external output remains advisory under `{#external-engines-never-gatekeepers}`.

### Provider Spec Contract

The scaffolder command is `tools/add-engine.sh --spec <provider.json> [--registry <path>] [--apply]`. It defaults to dry-run, uses the checked-in registry when `--registry` is omitted, and only writes when `--apply` is present.

The v1 provider spec has this exact shape:

```json
{
  "transport": "http",
  "engine_id": "fixture-http",
  "variant": "fixture-chat",
  "base_url": "https://api.example.com/v1",
  "model": "fixture-chat",
  "auth_key_env": "FIXTURE_API_KEY",
  "context_window": 32768,
  "cost_speed_rank": 99,
  "cost_class": "metered",
  "cost_per_token": {
    "input_usd": 0.000001,
    "output_usd": 0.000002
  },
  "budget_ceiling_usd": 5.0,
  "latency_class": "standard",
  "model_identity": "fixture-chat",
  "last_validated": "2026-07-09",
  "capability_profile": {
    "code-generation": {
      "rating": "MODERATE",
      "note": "fixture provider onboarding proof"
    }
  },
  "prompting_protocol": [
    "Return advisory evidence only."
  ],
  "sources": [
    {
      "claim": "OpenAI-compatible endpoint and model id",
      "url": "https://api.example.com/docs",
      "date": "2026-07-09",
      "tag": "OFFICIAL",
      "corroboration": "STRONG"
    }
  ]
}
```

`transport` must be exactly `http`; `base_url` must be an absolute HTTPS URL with a host and no embedded credentials, query, or fragment; and `auth_key_env` is an environment-variable name, never a credential value. Free rows omit `budget_ceiling_usd` and carry zero input/output prices; metered rows require a non-negative ceiling.

The scaffolder derives `substrate: external`, `egress_policy: networked`, `trust_tier: probation`, `write_capable: false`, `transport: http`, `invocation.via: engine-bridge-http`, `invocation.effort: default`, bearer auth, and `receipt_emitter: http-bridge`. `default_for_engine` is `true` for the first row of an engine id and `false` for later variants, leaving the existing default unchanged.

Promotion assessment is a separate read-only command: `python3 plugins/saga/scripts/engine_promotion.py <engine>/<variant> [--registry <path>] [--ledger <path>] [--json]`. It exits nonzero for invalid input or corrupt evidence, but an evidence-valid ineligible result is a successful assessment with `eligible: false`.

### Prerequisites and Sequencing

All hard prerequisites are merged on current `main`: the generic HTTP bridge and receipt contract via PR #516 (issues #383/#387), the run-fact ledger via PR #489 (issue #401), the first-party Codex emitter via PR #518 (issue #476), provider-auth preflight via PR #537 (issue #389), registry schema/currency via PR #543 (issue #452), and proof-integrity telemetry via PR #547 (issue #388).

No external credential, provider account, live endpoint, infrastructure, or cross-repository change is required. Outcome leaves #393 and #394 have no authored dependency on #455 and may remain dispatched independently; this plan does not make their progress a prerequisite.

---

## Implementation Units

### U1. Trust-Tier Schema and Resolver Enforcement

Make probation a first-class, fail-closed routing constraint without changing offload eligibility.

**Goal:** Add required trust metadata, migrate incumbent rows, expose standing to operators, and enforce role-aware selection in registry and resolver paths.

**Requirements:** R7, R8, R10; T2-F5-4.

**Dependencies:** None.

**Files:** `plugins/saga/scripts/engine_registry.py`, `plugins/saga/scripts/engine_resolver.py`, `plugins/saga/scripts/engine_registry_cli.py`, `plugins/saga/references/engine-registry.yaml`, `tests/test_saga_engine_registry.py`, `tests/test_saga_engine_resolver.py`, `tests/test_engine_registry_cli.py`, `tests/test_engine_registry_lint.py`, `tests/test_saga_engine_dispatch.py`, `tests/test_engine_recommend.py`.

**Approach:** Add `TRUST_TIERS`, parse a required field into `EngineEntry`, and require role members to reference advisory rows. Make capability decisions role-aware, include `role_kind` in `RunMemo` capability keys, skip probationary candidates for advisory roles, and retain exact-key halts as defense in depth. Keep `worker` and `generator` behavior unchanged.

**Patterns to follow:** Closed vocabularies and row parsers in `plugins/saga/scripts/engine_registry.py:14`; fallback/halt role sets in `plugins/saga/scripts/engine_resolver.py:22`; explicit role expansion in `plugins/saga/scripts/engine_resolver.py:368`.

**Test scenarios:** Happy path: an advisory row resolves for worker and advisory-reviewer roles. Probation path: the same probationary row resolves for worker/generator but exact advisory resolution halts. Candidate path: a stronger probation row is skipped for advisory capability selection in favor of an advisory row, while worker selection may use it. Memo path: resolving worker then advisory with one `RunMemo` produces role-correct choices. Role path: a composing role naming a probation row fails with the role and member key. Error path: missing or unknown trust tier names the row. Migration path: every checked-in row is advisory and existing route winners remain unchanged.

**Verification:** Focused registry, resolver, and CLI tests prove both allowed offload and denied advisory paths, then existing resolver suites prove fallback, panel, overlay, and preflight behavior did not regress.

### U2. Offline Registry Conformance Gate

Prove schema-valid rows can actually reach the dispatch invocation seam before a pull request can merge.

**Goal:** Add a reusable conformance module, a red/green fixture suite, and a named CI gate.

**Requirements:** R4, R5, R6; T2-F4-3.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/engine_registry_conformance.py`, `tests/test_engine_registry_conformance.py`, `.github/workflows/ci.yml`.

**Approach:** For each row, verify exact-key identity, candidate membership for every advertised capability, role/trust consistency, successful synthetic invocation materialization through `engine_dispatch` without preflight, and membership of `receipt_emitter` in `bridge_signatures.load_registry()`. Return all row-scoped errors in one report and provide a CLI exit code for CI. Keep bridge source-emission proof in `tests/test_bridge_receipt_drift.py` rather than duplicating its AST contract.

**Patterns to follow:** Error-collecting lint CLI in `plugins/saga/scripts/check_engine_registry.py`; hermetic bridge accounting in `tests/test_bridge_receipt_drift.py`; transport-keyed invocation construction in `plugins/saga/scripts/engine_dispatch.py:1070`.

**Test scenarios:** Live path: the shipped registry passes with no provider credentials. Dead-wired path: a schema-valid HTTP row with an unsupported `via` value fails and names the row/seam. Capability path: a fixture whose advertised capability is absent from candidate reachability fails. Multi-error path: independent broken rows are both reported. Side-effect path: patched preflight/network functions raise if the checker calls them. CI path: the CLI returns zero on the real registry and nonzero on a broken fixture.

**Verification:** The named test file and standalone CI command both exercise the same conformance function; no duplicate implementation lives in workflow YAML.

### U3. Provider Scaffolder and Atomic Apply

Generate a conformant probationary HTTP row and apply it without rewriting the surrounding authored registry.

**Goal:** Add the provider-spec parser, safe defaults, dry-run/apply modes, concurrency guard, and shell entrypoint.

**Requirements:** R1, R2; T2-F1-5.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_onboarding.py`, `tools/add-engine.sh`, `tests/test_engine_onboarding.py`.

**Approach:** Accept a JSON spec containing provider identity, endpoint/model/auth env-name metadata, context/cost/latency data, at least one capability rating, prompting guidance, and at least one source. Derive generic bridge fields and probation standing, validate a candidate registry in memory, run conformance, render only the new row, verify the source hash is unchanged, and atomically replace on explicit `--apply`; default to a dry-run fragment plus validation summary.

**Patterns to follow:** Strict field errors in `EngineEntry.from_dict()`; temp-file-plus-replace state writes in `plugins/saga/scripts/engine_overlay.py`; repository-root shell forwarding rather than shell-owned generation.

**Test scenarios:** Happy path: a fixture provider spec dry-runs a probation row that passes schema and conformance. Apply path: the row is inserted before `roles`, existing comments/content remain byte-identical outside the insertion, and `Registry.load()` succeeds. Missing input paths: absent capability, source, auth env name, model, or cost field names the field and writes nothing. Unsupported transport path: CLI input is rejected with the generic-HTTP scope boundary. Duplicate/called-twice path: the second apply fails and the file hash is unchanged. Concurrency path: an intervening registry edit causes an abort rather than overwrite. Conformance path: a deliberately dead-wired derived row cannot be applied.

**Verification:** Tests invoke the shell wrapper and Python module against temporary registries; no test mutates the checked-in registry or contacts a provider.

### U4. Telemetry-Fed Promotion Assessment

Turn successful shadow-mode evidence into an auditable eligibility result without allowing telemetry to rewrite policy.

**Goal:** Add a typed, exact-variant promotion assessment over run-fact ledger records and an operator-readable CLI result.

**Requirements:** R9; T2-F5-4.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/engine_promotion.py`, `tests/test_engine_promotion.py`, `plugins/saga/references/run-fact-ledger.md`.

**Approach:** Read and chain-verify the ledger, filter `kind=engine` records by exact engine/variant, inspect the five most recent matches, and require every record to be successful, proof-integrity valid, and keyed to an actual bridge run. Return counts, inspected run keys, eligibility, and precise reasons. Refuse promotion assessment for an already-advisory or unknown row and never edit registry YAML.

**Patterns to follow:** Defined-empty derive-on-read views in `plugins/saga/scripts/run_ledger.py:221`; exact engine/variant facts written by `plugins/saga/scripts/engine_dispatch.py:663`; chain verification before evidence use.

**Test scenarios:** Eligible path: five exact-variant proven successes report eligible. Insufficient path: zero through four matches report the deficit. Failure paths: one failed, unproven, missing-key, or proof-integrity-failed record in the window reports ineligible. Variant isolation: facts from sibling variants do not count. Ordering path: only the five most recent exact matches decide. Integrity path: a broken ledger chain fails closed. Standing path: an incumbent advisory row reports promotion not applicable.

**Verification:** Promotion tests use temporary ledgers and registry fixtures; the CLI output is deterministic JSON/text and makes no registry write.

### U5. Operator Documentation, Release Surfaces, and Durable Evidence

Keep the installed plugin, operator workflow, and durable decision trail synchronized with the new behavior.

**Goal:** Document onboarding and promotion, update dispatch guidance, bump Saga release surfaces, and capture work/review evidence.

**Requirements:** R3, R10.

**Dependencies:** U1, U2, U3, U4.

**Files:** `docs/adding-a-provider.md`, `plugins/saga/references/dispatch-adapter-contract.md`, `plugins/saga/references/engine-dispatch.md`, `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `tests/test_saga_plugin.py`, `docs/engineering-journal/DECISIONS.md`, `docs/work-sessions/2026-07-09-issue-455-provider-onboarding.md`.

**Approach:** Give operators a complete sample spec and dry-run/apply/promotion sequence, state that CLI providers need a separate real bridge implementation, and explain that advisory promotion is a reviewed authored-data change. Bump the Saga patch version across the release triad and update the plugin contract assertion. Record focused/full checks, Team Execution evidence, code review, PR, and merge receipts in the work session.

**Patterns to follow:** Release-triad handling in `plugins/saga/CHANGELOG.md` and `tests/test_saga_plugin.py`; generic bridge documentation in `plugins/saga/references/dispatch-adapter-contract.md`; prior outcome work-session artifacts under `docs/work-sessions/`.

**Test scenarios:** Documentation contract: example spec keys match the parser and generated row defaults. Release parity: plugin, marketplace, changelog, and test assertion agree. Drift path: release-surface and marketplace generators report no mismatch. Hygiene path: no `.claude/saga`, `.codex`, Team Execution state, provider credentials, or temporary fixture registries are staged.

**Verification:** Release-surface checks, documentation assertions in focused tests, diff hygiene, and the committed work-session/code-review artifacts establish parity.

---

## Team Structure

The leaf runs under Team Execution because it crosses registry, resolver, tooling, CI, docs, and release contracts. The installed protocol probe reports serial mode, so every selected role is run sequentially by the main thread and recorded with `vehicle=team-execution-serial`.

### Runtime

- Mode: serial; no callable delegated-agent surface is available in this session.
- State root: `~/.codex/team-execution/state/infiquetra-claude-plugins/issue-455/` because repo-local `.codex/team-execution/` is not ignored.
- Main-thread final verification: required.
- Sensitive-data boundary: provider specs contain env-var names only; no credential values enter reviewer or validator evidence.

### Workers

| Workstream | Units | Runtime | Ownership |
| --- | --- | --- | --- |
| Registry and resolver | U1 | serial main thread | Schema, eligibility, cache isolation, incumbent migration |
| Onboarding and conformance | U2, U3 | serial main thread | Offline dispatch proof, CI gate, safe scaffolding and apply |
| Promotion and documentation | U4, U5 | serial main thread | Ledger assessment, operator docs, release and durable evidence |

### Reviewers

| Role | Required | Selection reason |
| --- | --- | --- |
| `devils-advocate-reviewer` | yes | Base reviewer; challenge stale issue assumptions, failure modes, and scope |
| `security-reviewer` | yes | Base reviewer; validate untrusted provider specs, env-name handling, and write boundaries |
| `architecture-reviewer` | yes | Base reviewer; preserve generic bridge and registry/resolver ownership boundaries |
| `testing-reviewer` | yes | New conformance and promotion gates need red-condition and side-effect proof |
| `clarity-reviewer` | yes | The provider guide must be executable without hidden context |

### Validators

| Role | Group | Required | Selection reason | Blocking rule |
| --- | --- | --- | --- | --- |
| `security-scanner` | scanner | yes | Python parsing/writes and a shell entrypoint process untrusted local specs | High-confidence secret, injection, or unsafe-write finding blocks completion |
| `scenario-tester` | tester | yes | Scaffolder dry-run/apply, conformance red path, and promotion thresholds are user-visible workflows | Focused or broad behavioral assertion failure blocks completion |
| `github-actions-monitor` | monitor | yes | Destination includes PR, CI, and merge | Required GitHub checks must be green before merge and completion |

### Gates

- Reviewer consensus threshold: every reviewer overall score is at least 9.0/10 with no applicable dimension below 7.0.
- Serial consensus is valid gate evidence but is explicitly not independent delegated review.
- Reviewer non-consensus blocks validators unless explicitly overridden.
- Required validator hard-fail, blocked, or missing evidence blocks completion.
- Maximum three reviewer or validator remediation loops before escalation.

---

## Scope Boundaries

In scope:

- OpenAI-compatible HTTP provider scaffolding onto the existing generic bridge.
- Required probation/advisory metadata and resolver enforcement.
- Offline registry-to-dispatch conformance and a named CI gate.
- Read-only promotion eligibility from the existing run-fact ledger.
- Operator docs, Saga release surfaces, tests, and durable lifecycle evidence.

One-PR rationale: the three issue facets intentionally share one `EngineEntry` contract. The scaffolder must emit the probation field that the resolver enforces and must pass the same conformance function CI runs; separating them would create an interval where the generator, runtime, and gate disagree about a valid provider.

Out of scope:

- Generating a provider-specific HTTP bridge or adding provider branches to `engine_bridge_http.py`.
- Scaffolding CLI providers without a real plugin-owned wrapper and receipt emitter.
- Live provider calls, credential creation, credential validation beyond existing preflight, or secret storage.
- Automatic promotion, automatic role membership, or telemetry-driven edits to committed registry policy.
- Changing external-engine gate authority, recommendation pricing, overlay semantics, or model-family inheritance.
- Backfilling fabricated telemetry for incumbent advisory rows.

Deferred to follow-up work:

- Scaffolding a CLI provider after a reusable wrapper contract exists.
- A richer promotion policy if five consecutive proven runs is too strict or too weak in observed use.
- Availability-gated live smoke tests for specific newly onboarded providers.

---

## Risks and Dependencies

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scaffolder recreates provider-specific dispatch logic | Generic bridge contract drifts and each provider becomes a code path | Limit v1 to OpenAI-compatible HTTP and derive fixed bridge fields |
| YAML apply destroys comments or concurrent edits | Large unrelated diff or lost operator changes | Parser-anchored row insertion, source-hash recheck, atomic replace, byte-preservation tests |
| Probationary selection leaks through resolver memoization | A worker selection could later occupy an advisory role | Include role kind in memo keys and test worker-then-advisory reuse |
| Conformance duplicates existing schema/emitter tests | Three guards drift while claiming the same property | Keep conformance narrowly on candidate/invocation reachability and call the actual builder |
| Promotion counts weak or unrelated telemetry | Unproven provider gains advisory standing | Exact variant, last-five window, successful status, proof integrity, and bridge run key are all mandatory |
| Promotion mutates authored policy from machine-local state | Local telemetry silently changes shared trust | Assessment is read-only; promotion remains a reviewed PR |
| Issue text assumes a bridge stub that current architecture forbids | Literal implementation would add dead code | Record the generic-bridge correction in plan, journal, docs, and doc-review evidence |
| Offline conformance is mistaken for live provider compatibility | A syntactically reachable row may still point at a changed third-party API | Name the offline boundary explicitly and keep availability-gated live smoke tests as provider-specific follow-up |

---

## Alternatives Considered

| Alternative | Decision | Reason |
| --- | --- | --- |
| Generate one bridge file per provider | Rejected | Contradicts the existing zero-provider-branch generic HTTP bridge and creates unconsumed code |
| Rewrite the entire YAML with `yaml.safe_dump()` | Rejected | Drops authored comments and formatting, producing unsafe review noise |
| Add a YAML round-trip dependency | Rejected for v1 | Dependency and lockfile churn are unnecessary when parser node marks can anchor one insertion |
| Let missing trust tier default to advisory | Rejected | A hand-authored new row could bypass probation by omission |
| Let missing trust tier default to probation | Rejected | It hides incomplete authored data and makes incumbent migration implicit |
| Auto-promote after threshold | Rejected | Machine-local telemetry must not rewrite committed role policy |
| Fold conformance into schema lint only | Rejected | The issue explicitly requires a separate dead-wiring signal, and schema-valid invocation drift is the target failure |

---

## Sources and Grounding

- `plugins/saga/scripts/engine_registry.py:331` - current row model lacks trust standing.
- `plugins/saga/scripts/engine_registry.py:500` - registry materialization and validation boundary.
- `plugins/saga/scripts/engine_registry.py:584` - candidate enumeration used for capability reachability.
- `plugins/saga/scripts/engine_resolver.py:320` - public resolve contract.
- `plugins/saga/scripts/engine_resolver.py:368` - composing roles expand members as advisory reviewers.
- `plugins/saga/scripts/engine_resolver.py:535` - role-sensitive halt/fallback and preflight boundary.
- `plugins/saga/references/dispatch-adapter-contract.md:10` - generic HTTP row, not provider-specific bridge, contract.
- `plugins/saga/scripts/engine_bridge_http.py:4` - zero provider branching in the live bridge.
- `plugins/saga/scripts/engine_dispatch.py:663` - exact engine/variant run-fact producer.
- `plugins/saga/references/run-fact-ledger.md:15` - hash-chained telemetry schema and derive-on-read posture.
- `tests/test_bridge_receipt_drift.py:170` - existing receipt-emitter accounting boundary.
- `.github/workflows/ci.yml:78` - existing schema/currency CI gate that conformance remains distinct from.
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` - source facets T2-F1-5, T2-F4-3, and T2-F5-4.
- `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map-final.json` - consolidation rationale for one provider-onboarding path.
- `docs/engineering-journal/DECISIONS.md#external-engines-never-gatekeepers` - external output remains advisory.
- `docs/engineering-journal/DECISIONS.md#provider-auth-preflight-389` - registry-auth and preflight remain the credential boundary.

---

## Verification Plan

Focused behavior and contract checks:

```bash
uv run pytest tests/test_engine_onboarding.py tests/test_engine_registry_conformance.py tests/test_engine_promotion.py tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py tests/test_engine_registry_cli.py tests/test_engine_registry_lint.py tests/test_saga_engine_dispatch.py tests/test_engine_recommend.py -v
uv run pytest tests/test_bridge_receipt_drift.py tests/test_saga_engine_dispatch.py tests/test_engine_registry_lint.py -v
uv run ruff format --check plugins/saga/scripts/engine_onboarding.py plugins/saga/scripts/engine_registry_conformance.py plugins/saga/scripts/engine_promotion.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py tests/test_engine_onboarding.py tests/test_engine_registry_conformance.py tests/test_engine_promotion.py
uv run ruff check plugins/saga/scripts/engine_onboarding.py plugins/saga/scripts/engine_registry_conformance.py plugins/saga/scripts/engine_promotion.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py tests/test_engine_onboarding.py tests/test_engine_registry_conformance.py tests/test_engine_promotion.py
uv run mypy plugins/saga/scripts/engine_onboarding.py plugins/saga/scripts/engine_registry_conformance.py plugins/saga/scripts/engine_promotion.py plugins/saga/scripts/engine_registry.py plugins/saga/scripts/engine_resolver.py tests/test_engine_onboarding.py tests/test_engine_registry_conformance.py tests/test_engine_promotion.py --ignore-missing-imports
```

Release and repository gates:

```bash
uv run python plugins/saga/scripts/check_engine_registry.py
uv run python plugins/saga/scripts/engine_registry_conformance.py
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
uv run pytest tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v
uv run bandit -r plugins/saga/scripts
git diff --check
```

Broad CI parity after focused gates pass:

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

---

## Routing

Destination: merge.

Recommended and selected execution backend: `team-execution`. The backend recommender selected review consensus and gates for five implementation units spanning 28 unique implementation/evidence paths near dispatch trust policy. The active host has no callable delegated-agent surface, so execution uses the skill's serial fallback and user-local evidence state; `inline` was the surfaced alternative.

Next command: `/doc-review docs/plans/2026-07-09-issue-455-provider-onboarding-plan.md`.
