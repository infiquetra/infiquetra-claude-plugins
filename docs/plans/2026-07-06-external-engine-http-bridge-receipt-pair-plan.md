---
title: External-engine HTTP bridge + bridge_receipt.v1 keystone pair (#387 + #383)
type: feat
status: active
date: 2026-07-06
origin: "GitHub handoff issues infiquetra/infiquetra-claude-plugins#387 and #383 (requirements-ready), corrected by the 2026-07-06 scope-note comments on each issue (objective #336 outcome re-triage)"
---

# External-engine HTTP bridge + bridge_receipt.v1 keystone pair (#387 + #383)

One PR lands the Wave A keystone of outcome `external-engine-offload`: a generic
OpenAI-compatible HTTP bridge (cloud-first — Ollama Cloud and DeepSeek as the first registry
rows, provider selectable at use-time) that is receipt-proven from its first dispatch, because
the same PR ships `bridge_receipt.v1` — the proof-of-execution contract every bridge emits,
enforced at registry load and by a drift test.

## Why one plan for two issues

The scope notes on both issues (2026-07-06) name them a keystone pair: the bridge must emit
`bridge_receipt.v1` from day one, and the receipt contract is only provable against a bridge
that emits it. Building them separately would ship either an unproven bridge or an unconsumed
contract. One branch, one PR, closes both; `link-pr` attaches the PR to both `sub-387` and
`sub-383`.

## Corrections carried in from the scope notes (authoritative over the draft bodies)

1. **Cloud-first, selectable at use-time.** Priority providers are HTTP cloud endpoints with
   API keys — Ollama Cloud and DeepSeek first. Local Ollama (`localhost:11434`, keyless) is
   deferred follow-up. Draft AC3's "keyless localhost" check is superseded (restated as AC3'
   below).
2. **Not greenfield.** `plugins/saga/scripts/engine_dispatch.py` (codex/agy invocation
   builders, `engine_dispatch.py:386-397` if-ladder), `plugins/saga/scripts/engine_registry.py`
   (schema loader), `plugins/saga/scripts/engine_resolver.py` (resolve/preflight), and
   `plugins/saga/references/engine-registry.yaml` (codex/agy rows) all ship today. This work
   extends that substrate with a `transport=http` lane; the draft's "verified absent" claims
   are stale.
3. **No codex-plugin retirement here.** The first-party `plugins/codex/` bridge is #476's job.
   #383's codex-side receipt emission lands there, not in this PR (see U7 for how the drift
   guard stays honest meanwhile).
4. **`ENGINE_INTENTS` consumer unchanged.** team-execution's worker table
   (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`)
   consumes engines by `<engine-key>` / `cap:<capability>`; new rows join that resolution
   automatically. No team-execution code changes.

## Requirements

- **R1.** Any registry row declaring `transport: http` dispatches through one generic
  OpenAI-compatible bridge with zero per-provider branching inside the bridge — provider
  differences live entirely in registry row data (base URL, auth, model id). *(#387 AC1)*
- **R2.** The dispatch-adapter contract is testable without live network: a shared
  `FakeHttpRunner`, a contract test that reds on a dead/no-op adapter (returns without invoking
  the runner) and greens on a conformant one. *(#387 AC2)*
- **R3 (AC3', supersedes draft AC3).** The Ollama Cloud row resolves and dispatches with
  bearer auth from `OLLAMA_API_KEY` — the first $0-marginal (subscription) offload row. An
  availability-gated smoke records `status: ok` when the key is present and the endpoint
  reachable; it skips (never fails) otherwise.
- **R4.** The DeepSeek row resolves and dispatches via API-key routing (`DEEPSEEK_API_KEY`,
  never hardcoded); its output is advisory-tagged and can never carry a gate verdict. *(#387
  AC4)*
- **R5.** Resolution and preflight are memoized per run: N resolves against one engine in a
  single run invoke the availability probe once (10 → 1 in the call-counting test). Memo keys:
  `engine_id` for preflight, `(capability, token_estimate)` for resolution; invalidated at run
  boundary; absent memo = today's behavior byte-for-byte. *(#387 AC5)*
- **R6.** No code path in the bridge or adapter table lets an engine result set or override a
  gate/verdict field — structurally rejected, not policy-rejected. *(#387 AC6; binding decision
  `{#external-engines-never-gatekeepers}` #283)*
- **R7.** `bridge_receipt.v1` is one versioned invocation-evidence contract all bridges emit:
  common fields plus a transport-discriminated evidence section (CLI: pid/argv/exit_code;
  HTTP: url/status_code/model). Schema + emit + validate live in one shared module. *(#383
  DoD 1)*
- **R8.** `Disposition.RAN_AS_REQUESTED` is unreachable without a schema-valid receipt on the
  evidence; receipt-less "ok" evidence resolves to an explicit new `Disposition.UNPROVEN`
  (never silently `RAN_AS_REQUESTED`, and not the lie of `FELL_BACK_TO_CLAUDE` — nothing fell
  back). Halted dispatches keep today's `FELL_BACK_TO_CLAUDE`. *(#383 DoD 2)*
- **R9.** `receipt_emitter` is a required registry-row key validated at load (`RegistryError`)
  and by CI; a row without receipt wiring cannot be dispatched to. *(#383 DoD 3)*
- **R10.** A bridge-enumeration drift test asserts every registered emitter that exists in this
  repo emits through the shared path — with committed forcing-function tests proving the guard
  reds on the drift it claims to catch (journal `{#verify-the-guard-reds}`). *(#383 DoD 4)*
- **R11.** Existing callers stay byte-identical: no signature breaks; new dataclass fields
  default-valued; `transport` defaults to `cli` for existing rows; memo is opt-in.
- **R12.** Release surfaces updated in the same PR: `plugins/saga`, `plugins/agy`,
  `plugins/fleet-core` plugin.json version bumps, `.claude-plugin/marketplace.json`, all three
  CHANGELOGs, drift-guard tests green, journal DECISIONS entry.

## Key Technical Decisions

**KTD1 — Adapter table extends `plugins/saga/scripts/engine_dispatch.py`, keyed on a new
top-level registry field `transport` (closed vocab `cli | http`, default `cli`).**
`_build_invocation` (`engine_dispatch.py:386-397`) becomes: `transport=http` → generic HTTP
invocation builder driven by row data; `transport=cli` → the existing codex/agy builders
unchanged. Rationale: the dispatch substrate already lives in saga (scope-note correction #3);
the issue's non-goals explicitly defer migrating codex/agy onto table rows, so the cli arm
keeps the current builders. Rejected: a new `plugins/team-execution/scripts/engine_dispatch.py`
(draft suggestion) — would fork the dispatch substrate the scope note says to extend.

**KTD2 — HTTP row schema rides inside `invocation` plus one new top-level field.** New
`EngineEntry.transport: str = "cli"` (validated closed-vocab). For `transport: http` rows,
`invocation` must additionally carry `base_url`, `model` (wire model id), `auth: {mode:
bearer|none, key_env: <ENV_NAME>}`, and an explicit `effort` (the `_effort` fallback
`variant.rsplit("-", 1)[-1]` at `engine_resolver.py:431-435` produces nonsense for HTTP
variants). `EngineEntry.from_dict` already deep-copies `invocation`, so extra keys flow through
today; the change is validation, not plumbing. Existing rows parse unchanged (R11).

**KTD3 — New engine ids `ollama-cloud` and `deepseek`; conservative seed ratings.** Distinct
engine_id per provider+locality because preflight and the memo are keyed by `engine_id`
(`engine_resolver.py:52-76`); a future local Ollama row becomes `ollama-local`, not a variant
of a mixed id. Routing-stability rule (exact, not "≤ MODERATE is safe"): `by_capability` is
rating-dominant (`engine_registry.py:336-353`), so a new row must never rate a capability
**at or above the current per-capability winner** — MODERATE would hijack `long-form-writing`
(current best across all rows: WEAK — verified in `engine-registry.yaml:41,126`). New rows
therefore either omit such capabilities or rate them WEAK, use `cost_speed_rank` 5–6 (ties
lose to rank 1–4), and U3's regression test bakes the current winners as literals so any
reroute reds. Ratings are re-validated by use through /retro, same as the 2026-06-27 seed
data. Base URLs and wire model ids
(`https://ollama.com/v1`-style, `https://api.deepseek.com`, `deepseek-chat`, one Ollama Cloud
model) are registry data to be verified against provider docs during U3 implementation — not
asserted from memory; the availability-gated smoke is the live proof.

**KTD4 — Transport-aware preflight, still no live network.** `preflight()` branches on the
row's transport: `cli` keeps `shutil.which` + config-file checks; `http` checks the auth env
var is present (when `auth.mode: bearer`) and the row is well-formed. Preserves the documented
"cheap availability without live API calls" contract (`engine_resolver.py:58`); reachability
is proven only by the availability-gated smoke test. Preflight therefore needs the registry
row (not just `engine_id`) — signature grows an optional `entry` parameter, defaulted so
existing callers/tests stay green.

**KTD5 — Run-scoped memo is an explicit object, not module state.** A small `RunMemo` class in
`engine_resolver.py` threaded as an optional keyword (`memo: RunMemo | None = None`) through
`resolve` / `resolve_role` / `_resolve_entry` / `preflight`. Keys per #387 AC5: preflight by
`engine_id`, resolution by `(capability, token_estimate)`. Run boundary = the caller drops the
object; no TTL, no global cache (module-global state would leak across runs and break test
isolation). `memo=None` is today's behavior exactly (R11).

**KTD6 — `bridge_receipt.py` lives in fleet-commons
(`plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py`).** It has three consumers in
two plugins today (saga's dispatch manifest gating, saga's HTTP bridge, agy's delegate) and a
fourth coming (#476 `plugins/codex/`). A saga-local module imported by agy is exactly the
cross-plugin import that breaks at install time (journal
`{#marketplace-install-layout-no-import-path}`); fleet-commons + the vendored shim
(`fleet_commons_shim.py`, DECISIONS `{#fleet-commons-mechanism-463}`) is the established
mechanism. agy does not vendor the shim yet — U2 adds the byte-identical copy, covered by the
existing vendored-copy drift guard. Rejected: per-plugin vendored copies of the receipt module
itself (schema logic would drift; the shim exists so logic doesn't have to be vendored).

**KTD7 — Receipt schema: common core + transport-discriminated runner evidence.**
`bridge_receipt.v1` = `{schema: "bridge_receipt.v1", engine_id, variant, transport,
wall_time_s, bytes_produced, runner: {...}}` where `runner` is `{pid, argv, exit_code}` for
`transport=cli` and `{url, status_code, model}` for `transport=http`. #383's minimum field
list (pid/argv/exit_code) was authored CLI-only before the cloud-first inversion; the pair
build forces the discriminator now rather than a v2 next month. `validate_receipt(dict)`
returns typed errors; the emit helper stamps schema/version so emitters cannot mislabel.

**KTD8 — Receipt gating maps receipt-less success to a new `Disposition.UNPROVEN`.**
`AdvisoryEvidence` gains `runner_receipt: dict | None = None` (frozen dataclass, additive);
`dispatch()` populates it from the runner result's `receipt` key; `build_dispatch_manifest`
(`engine_dispatch.py:233-272`) assigns `RAN_AS_REQUESTED` only when a schema-valid receipt is
present, else `UNPROVEN` with a disposition note naming what was missing. Blast radius
checked: outside the two owning modules the only `Disposition` consumer is
`manifest_store.py:277` (a default builder) — additive enum value is safe. Unit split: the
field + threading land in U5 (which needs them), the gating + enum + guard in U6. Rejected:
`FELL_BACK_TO_CLAUDE` for receipt-less success (#383 allows it) — it asserts a fallback that
never happened; derived truth must not lie.

**KTD9 — `receipt_emitter` is a required row key naming the emitting module.** Values are a
closed per-row string (`http-bridge`, `agy-delegate`, `codex-bridge`); load-time
`RegistryError` when absent (R9). The codex rows declare `receipt_emitter: codex-bridge`,
which #476 will make real. U7's drift test enumerates emitters: emitters present in-repo must
demonstrably emit (red when the emit call is removed); `codex-bridge` is an explicit
`PENDING_EMITTERS = {"codex-bridge": "#476"}` entry — the test reds if `plugins/codex/`
appears without emit wiring, and reds if a pending entry's issue is closed while still
pending. No silent skip.

**KTD10 — HTTP client is stdlib `urllib.request` behind a Runner-shaped seam.**
`engine_bridge_http.py` exposes `runner()` → a `Runner` (same `dict → dict` contract
`dispatch()` already takes, `engine_dispatch.py:22`) returning `{status, output, tokens,
latency_seconds, receipt}`. Unit tests inject `FakeHttpRunner`; no live network in the suite.
Rejected: `requests` (already a repo dep) — the bridge is a thin seam by design and stdlib
keeps saga scripts runnable wherever the other saga scripts run; nothing in the contract needs
requests' surface.

**KTD11 — One PR, both issues, receipt-contract-first unit order.** The PR message closes
#387 and #383; after merge both `sub-387` and `sub-383` get `link-pr`. Branch:
`feat/387-383-http-bridge-receipt-pair` (cut from `main` — leaf work never rides the outcome
branch). Units land receipt-schema → registry → resolver → bridge → gating → agy →
drift-guard → surfaces, so every intermediate commit keeps the suite green.

## Implementation Units

### U1. `bridge_receipt.v1` schema module in fleet-commons

**Goal:** `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py` — schema constants,
`emit_receipt(...)` builder, `validate_receipt(dict) -> list[str]` (empty = valid), per KTD7.

**Files:** `plugins/fleet-core/scripts/fleet_commons/bridge_receipt.py` (new);
`tests/test_bridge_receipt.py` (new).

**Test scenarios:** valid CLI receipt round-trips; valid HTTP receipt round-trips; missing
common field named in errors; wrong `runner` section for the declared transport rejected;
unknown schema version rejected; `emit_receipt` output always passes `validate_receipt`
(property-style over both transports).

**Depends on:** none.

### U2. agy delegate emits the shared receipt

**Goal:** vendor `fleet_commons_shim.py` into `plugins/agy/scripts/` (byte-identical); map
`SupervisedRunResult` (pid, argv, return_code, stdout_bytes, started/ended timestamps —
already captured at `plugins/agy/scripts/agy_delegate.py:660-790`) through `emit_receipt` into
the delegate's result envelope.

**Files:** `plugins/agy/scripts/fleet_commons_shim.py` (new, vendored);
`plugins/agy/scripts/agy_delegate.py`; `tests/test_agy_delegate_contract.py` (extend);
`tests/test_fleet_commons_resolution.py` (extend the hardcoded vendored-copy list at
`tests/test_fleet_commons_resolution.py:28-29` with the agy copy — the guard does not
auto-discover).

**Test scenarios:** a supervised run result maps to a schema-valid CLI receipt; launch-failure
paths (agy missing, OSError) emit no receipt (there is nothing to prove) and the envelope
still validates; the vendored shim byte-matches the canonical file via the extended drift
guard.

**Depends on:** U1.

### U3. Registry: `transport` field, HTTP row validation, `receipt_emitter` required, two new rows

**Goal:** `EngineEntry.transport` (closed vocab, default `cli`) + http-conditional required
invocation fields (`base_url`, `model`, `auth.mode`, `auth.key_env` when bearer, explicit
`effort`) + `receipt_emitter` required on every row (KTD2/KTD9); add `ollama-cloud` and
`deepseek` rows and `receipt_emitter` values on the four existing rows (KTD3). Verify base
URLs / wire model ids / context windows against provider docs while authoring the rows. New
rows must satisfy the FULL existing row schema — the loader already requires
`capability_profile` (≥1 entry), `prompting_protocol`, and per-row `sources`
(`engine_registry.py:106-161`); author honest seed values tagged as seed data, never
placeholders.

**Files:** `plugins/saga/scripts/engine_registry.py`;
`plugins/saga/references/engine-registry.yaml`; `tests/test_saga_engine_registry.py` (extend).

**Test scenarios:** existing-shape row (no `transport`) parses as `cli`; `transport: http` row
missing `base_url`/`model`/`auth`/`effort` each raise `RegistryError` naming the field; row
missing `receipt_emitter` raises `RegistryError` (#383 AC: `-k missing_receipt_emitter`);
unknown transport value rejected; live `engine-registry.yaml` loads clean; `by_capability`
winners for every capability are unchanged from before this PR (routing-stability regression,
KTD3).

**Depends on:** none (parallel with U1).

### U4. Transport-aware preflight + run-scoped memo

**Goal:** `preflight` branches on transport (KTD4); `RunMemo` threaded through
`resolve`/`resolve_role`/`_resolve_entry`/`preflight` with AC5's keys (KTD5).

**Files:** `plugins/saga/scripts/engine_resolver.py`; `tests/test_saga_engine_resolver.py`
(extend); memoization cases in `tests/test_saga_engine_dispatch.py` per the issue's named
check (`-k resolve_memoization`).

**Test scenarios:** http row + key env present → available (no network callable invoked —
assert via injected fakes); http row + missing env → unavailable with reason naming the env
var; cli rows byte-identical results vs today; 10-resolve loop with memo → 1 preflight call
(call-counting fake); distinct engines don't share memo entries; `(capability,
token_estimate)` hit returns the same Resolution without re-ranking; no memo argument → probe
count unchanged (10).

**Depends on:** U3.

### U5. Generic OpenAI-compatible HTTP bridge + adapter-table dispatch

**Goal:** `plugins/saga/scripts/engine_bridge_http.py` — builds the chat/completions request
purely from row-driven invocation data, stdlib urllib, returns Runner-contract result with a
schema-valid HTTP receipt (KTD10, R7); `_build_invocation` gains the transport-keyed branch
(KTD1) building a generic http invocation (byte-preserved payload, same `_assert_payload_preserved`
guarantee); adds `AdvisoryEvidence.runner_receipt: dict | None = None` (frozen dataclass,
additive — the field lands HERE, not U6, because this unit threads it) and `dispatch()`
populates it from `result["receipt"]`. Secret lifecycle constraint: the resolved API key
exists only in the request headers at call time — never in the invocation dict (which flows
into run-ledger telemetry), the receipt, the evidence, or any log line; receipts and errors
may carry the env var *name* at most.

**Files:** `plugins/saga/scripts/engine_bridge_http.py` (new);
`plugins/saga/scripts/engine_dispatch.py`; `tests/test_engine_bridge_http.py` (new, includes
`FakeHttpRunner` shared fixture); `tests/test_saga_engine_dispatch.py` (extend).

**Test scenarios:** the same test body parametrized over an Ollama-Cloud-shaped and a
DeepSeek-shaped row produces byte-identical `AdvisoryEvidence` through the adapter table vs a
fake HTTP runner (#387 AC1 `-k transport_http_bridge`); bearer header present iff `auth.mode:
bearer` and never logged/echoed into evidence; payload byte-preservation holds for http
invocations; HTTP error / timeout / malformed-body → failure statuses from the existing
`FAILURE_STATUSES` vocabulary with downgrade note, never a fabricated `ok`; dead adapter
(returns without invoking runner) reds the contract test, conformant adapter greens (#387 AC2,
new `tests/test_dispatch_adapter_contract.py` cases may live in `test_engine_bridge_http.py`
if one file keeps the fixture shared — implementer's call, keep the issue's named `-k` selectors
working); availability-gated smoke: with `OLLAMA_API_KEY` set and endpoint reachable records
`status: ok`, else `pytest.skip` (R3).

**Depends on:** U1, U3, U4.

### U6. Receipt-gated disposition + never-gatekeeper guard

**Goal:** `build_dispatch_manifest` requires a valid receipt (on the `runner_receipt` field
U5 added) for `RAN_AS_REQUESTED`, else `Disposition.UNPROVEN` (new enum value) with a naming
note (KTD8, R8); structural rejection when a runner result attempts gate/verdict keys
(`verdict`, `gate_status`, `adjudicated`) — `DispatchError`, satisfying R6/#387 AC6. AC4's
"role field is advisory" maps to the existing structure: dispatch output is advisory by
construction (`verified_by_claude=False`, no gate fields on `AdvisoryEvidence`), and this
unit's guard makes gate-field injection structurally impossible.

**Files:** `plugins/saga/scripts/engine_dispatch.py`;
`plugins/saga/scripts/provenance_manifest.py`; `tests/test_saga_engine_dispatch.py` (extend —
the issue's named `-k fabricated_evidence_no_receipt` and `-k never_gatekeeper_guard` cases).

**Test scenarios:** ok evidence + valid receipt → `RAN_AS_REQUESTED`; ok evidence + no/invalid
receipt → `UNPROVEN`, never `RAN_AS_REQUESTED`; halted evidence unchanged
(`FELL_BACK_TO_CLAUDE`); manifest round-trips the new disposition; runner result carrying a
gate field raises `DispatchError`; existing manifest tests updated to supply receipts where
they assert `RAN_AS_REQUESTED` (the assertion-flip is the point of the PR, not collateral).

**Depends on:** U1, U5 (receipt threading).

### U7. Bridge-enumeration drift guard (forcing-function verified)

**Goal:** `tests/test_bridge_receipt_drift.py` — enumerate registry `receipt_emitter` values;
every in-repo emitter provably emits through the shared path; `PENDING_EMITTERS` per KTD9.

**Files:** `tests/test_bridge_receipt_drift.py` (new).

**Test scenarios:** current registry (http-bridge, agy-delegate emitters) passes; a test-double
bridge lacking the emit call reds (#383 AC `-k all_bridges_emit`); forcing-function reds
committed as tests (journal `{#verify-the-guard-reds}`): the guard reds when the emit call is
stubbed out of one emitter, and the matcher is probed against a realistic evasion (aliased
import / renamed local); `codex-bridge` pending entry reds if `plugins/codex/` exists without
emit wiring. All red conditions are **hermetic** — filesystem and registry state only, no
network, no GitHub-issue-state checks inside tests (a pending entry going stale is caught by
the `plugins/codex/`-exists condition when #476 lands, not by polling the issue).

**Depends on:** U2, U5.

### U8. Release surfaces, contract doc, journal

**Goal:** version bumps + changelogs for **four** plugins — `plugins/saga`, `plugins/agy`,
`plugins/fleet-core`, and `plugins/team-execution` (its `external-engine-workers.md` reference
is user-facing guidance; the same-PR release-surface rule applies to it too);
`.claude-plugin/marketplace.json` parity for all four; dispatch-adapter contract reference
doc; consumer-side pointer update; DECISIONS entry (KTD1/KTD3/KTD6/KTD8/KTD9 with rejected
alternatives and revisit-whens); live receipt proof pasted into the PR description (one agy
run + one HTTP run — the codex live-proof half of #383 is deferred to #476 per scope note).

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/agy/.claude-plugin/plugin.json`,
`plugins/fleet-core/.claude-plugin/plugin.json`,
`plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `plugins/agy/CHANGELOG.md`, `plugins/fleet-core/CHANGELOG.md`,
`plugins/team-execution/CHANGELOG.md`,
`plugins/saga/references/dispatch-adapter-contract.md` (new),
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (pointer
to the new rows), `docs/engineering-journal/DECISIONS.md`.

**Test expectation:** none beyond existing drift/parity guards staying green — this unit is
release metadata and documentation; the marketplace-vs-plugin.json parity tests are the check.

**Depends on:** U1–U7.

## Verification (whole-PR gate)

```bash
uv run pytest tests/test_bridge_receipt.py tests/test_bridge_receipt_drift.py -v
uv run pytest tests/test_saga_engine_dispatch.py tests/test_saga_engine_registry.py tests/test_saga_engine_resolver.py -v
uv run pytest tests/test_engine_bridge_http.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Issue-named selectors that must exist and pass: `-k transport_http_bridge`,
`-k resolve_memoization`, `-k never_gatekeeper_guard`, `-k missing_receipt_emitter`,
`-k fabricated_evidence_no_receipt`, `-k all_bridges_emit`. (Draft AC selector
`-k ollama_keyless_resolve` is superseded by AC3' — the cloud-auth resolve + gated smoke.)

**Issue-AC test-file re-homing (so /qa checks the right paths):** the draft ACs name
greenfield files that this plan re-homes into the existing suite —
`tests/test_engine_dispatch.py` → `tests/test_saga_engine_dispatch.py` (+ new
`tests/test_engine_bridge_http.py` for bridge/adapter cases);
`tests/test_dispatch_adapter_contract.py` → contract cases inside
`tests/test_engine_bridge_http.py`; `tests/test_engine_registry.py` →
`tests/test_saga_engine_registry.py`; #383's `tests/test_saga_engine_dispatch.py` /
`tests/test_saga_engine_registry.py` names already match. Selectors are preserved verbatim;
only file homes changed (extension-not-greenfield per scope note #3).

## Scope Boundaries

**Out of scope (true non-goals):** task-based engine recommendation; any gate/verdict
authority change (`{#external-engines-never-gatekeepers}` #283 binding); team-execution
chaperone tiering (`{#external-engine-chaperone-dispatch}` #318 binding); migrating codex/agy
call sites onto table rows; providers beyond the two rows; standing cost telemetry beyond the
existing run-ledger seam (#401, already threaded through `dispatch()` as telemetry-only);
retrofitting historical manifests.

**Deferred follow-up (tracked elsewhere):** local Ollama row (`ollama-local`, keyless,
`localhost:11434`) — the draft's original first row, deferred by scope note #1; codex receipt
emission + live codex proof (#476); tripwires audit consuming receipts (#384, blocked on this
pair by outcome DAG edge).

## Risk Analysis

- **Registry schema break for out-of-repo registry copies.** `receipt_emitter` becomes
  required; any yaml not shipped in this PR fails load. Registry + loader ship together in the
  saga plugin, and no other in-repo yaml exists (checked: one file). Residual risk accepted;
  CHANGELOG documents the migration line for any private overlay.
- **Existing tests asserting `RAN_AS_REQUESTED` without receipts go red.** Intended — U6
  updates them to supply receipts; the diff must show each flip is deliberate (reviewer
  checklist item).
- **Provider endpoint drift (base URL / model id wrong at authoring time).** Mitigated by
  KTD3's verify-at-implementation step + the availability-gated smoke; a wrong URL can never
  fail CI (skip-not-fail) but shows up on the first live dispatch — acceptable for seed rows,
  same posture as the 2026-06-27 seed data.
- **Secret leakage into evidence/receipts/telemetry.** Bearer tokens must never appear in
  receipts, evidence, logs, or the invocation dict — the invocation flows into run-ledger
  facts (`engine_dispatch.py:190-230`), so the key must be resolved from `auth.key_env` only
  at request-build time inside the bridge, never earlier. U5 has an explicit never-logged
  test. Receipt carries the env var *name* at most, never the value.
