# External-Engine Workers — Chaperone Dispatch Protocol

This document is the wrapper contract R12 names as missing: how a team-execution worker can be
an external engine (agy, codex) instead of a Claude agent, without team-execution growing a
second executor kind. It closes #283's deferred U12 leg and activates the dispositions
`worker-manifest.md` reserves (`fell-back-to-claude` / `substituted-engine` /
`rejected-offload`).

> **Dispatch-adapter contract, generic HTTP bridge, and `bridge_receipt.v1`:** how a
> `transport: http` registry row dispatches through the shared generic HTTP bridge with zero
> per-provider branching, and the receipt-gated proof-of-execution contract every bridge (CLI or
> HTTP) now emits, live in
> [`plugins/saga/references/dispatch-adapter-contract.md`](../../../../saga/references/dispatch-adapter-contract.md)
> (#387, #383). No team-execution code changes with a new registry row — resolution here stays
> fully declarative by `<engine-key>` / `cap:<capability>`; new rows join automatically.

**Shape (KTD1):** one resident **chaperone** — an ordinary Claude team-execution worker,
`worker-<engine>` or `worker-<capability>` per the Workers-table naming rule
(`SKILL.md`'s `### Workers`, KTD3) — owns an engine's units end-to-end: resolve → dispatch →
verify → apply → test → manifest. There is no separate "external worker" executor; the engine
never joins wave scheduling, the residency protocol, or git directly. It is evidence the
chaperone consumes (R23) — never write-capable in this contract.

## Never a gatekeeper (R13/R15, restated)

Nothing in this document lets an external engine satisfy a gate. The canonical call is
`engine_dispatch.satisfy_gate(evidence, reconciliation=result, ...)`: before the existing authority
checks, the ready typed result must bind exactly to the dispatch execution id, canonical intent and
recipe, evidence digest, and ordered source-finding IDs. The guard then still requires
`evidence.verified_by_claude is True`, observer corroboration, and any supplied manifest's matching
execution and adjudicated claims; it refuses panel/advisory-reviewer roles, rejected offloads,
substitutions, proof-integrity failures, and liveness contradictions. An external-engine worker's diff
still goes through the same reviewer consensus and validator gates as any other worker's diff
(`SKILL.md` Step B2/B3); this contract only changes *who wrote the diff*, not what clears it for merge.

## Advisory-reviewer seat (non-scoring)

The consensus panel may also request an external-engine second opinion with
`role_kind="advisory-reviewer"`. This uses the same chaperone posture — Claude resolves, dispatches,
reads, verifies, and reports the external synthesis — but the result is reviewer evidence only. It is
not a worker package, not a resident teammate, not a wave-scheduled executor, and never touches git.

`role_kind="advisory-reviewer"` is a halt-not-fallback role in `engine_resolver.py`: if the selected
engine is unavailable or fails preflight, the advisory seat is recorded as absent/halted rather than
substituted with Claude. That absence is a no-op for the Team Execution gate; the Claude reviewer
panel continues with its existing score math.

Advisory-reviewer evidence is report-only. `engine_dispatch.satisfy_gate()` refuses
`role_kind="advisory-reviewer"` evidence even when Claude has verified it and the observer
corroborated the run. The only consumer is the Claude-vs-external convergence report described in
`consensus-protocol.md`.

## Intent and typed reconciliation

Every chaperone unit carries exactly one fleet-core-owned `engine_intent`: `offload`,
`second-opinion`, or `divergence` (omission defaults to `offload`). Saga's closed recipe registry maps
each intent exactly once: offload accounts for accepted, dropped, and overridden engine findings;
second-opinion makes Claude independently adjudicate every review finding; divergence treats both
agreement and disagreement as findings requiring explicit Claude review. Unknown intents and registry
drift fail closed rather than falling back to offload.

The engine runner returns findings as an ordered array of `{"content": <string>}` records. Dispatch
replaces the prose with immutable `SourceFinding` metadata: an ordinal-bearing per-content ID and
SHA-256 digest. Non-empty `second-opinion` and `divergence` output requires this typed envelope;
`offload` alone may omit it and receive one explicit opaque-artifact source for the whole output.
Typed multi-finding offloads retain every separate source. Reconciliation must cover the exact ordered
ID tuple with one ordered item per source; no intent may collapse typed multi-finding output into an
opaque singleton.

All three paths produce a ready typed `ReconciliationResult` before gate evaluation. Reconcile and
apply events are append-only `run_fact.v1` reconciliation facts; rejected offloads project their
mandatory note as a typed `dropped` item for reviewer and validator evidence. `/retro` may derive an
`approval_required` recipe-update proposal from those facts, but neither it nor a chaperone edits the
registry. Typed results, rejection notes, panel output, and proposals are advisory evidence only:
Claude remains verifier-of-record and `satisfy_gate()` remains the sole authority boundary.

## Advisory-jury panel (Claude foreman)

The rare hardest-call jury starts from an explicit
`AdvisoryPanelRequest(role=<registered-role>)`. It is not a unit's `verify` object: `Verify` bounds
Claude verifier calls over one unit result, while the advisory jury expands a named external-engine
composing role.
`PANEL_N_CAP = 7` is the independent hard bound for this external member multiplicity. The constant
and the normalized-role/advisory-verdict/Claude-foreman checks live in the lower-level Saga
`engine_registry` policy shared by spec validation and runtime resolution, not in either caller.

The chaperone validates the role name, advisory verdict, Claude verifier, and resolved member count
before any member preflight. Zero-member, malformed, unknown, or over-cap roles halt with no member
preflight, dispatch, or ledger append. It then calls `engine_resolver.resolve_role()` once, checks
the complete returned list with `panel_halt()`, and only starts member dispatch when every member is
available. It must not call `resolve({role_kind: "panel"})`; that API remains the resolver's existing
single-resolution role policy, not a fan-out request.

Member output stays in-memory advisory evidence. Duplicate non-empty output becomes one source
finding while retaining all producing member identities; an empty response becomes an explicit,
member-specific source finding. Claude's foreman must return a ready typed `ReconciliationResult`
that matches both the exact ordered source finding IDs and the canonical SHA-256 digest of the ordered
gathered-evidence metadata. Only after that validation may
`dispatch_advisory_panel()` append the typed `reconcile` and `apply` facts. Raw member output is never
written to the run-fact ledger, and a failed foreman result writes neither fact. Dispatch rejects a
member above 64 KiB or cumulative UTF-8 panel output above 256 KiB before the foreman runs; the ledger
stores only the bounded structural item-id/status projection and its hashes, never raw output or
rationale prose.

Successful reconciliation grants no authority. Every member evidence record is stamped
`role_kind="panel"`, which remains in `NON_GATING_ROLE_KINDS`; `satisfy_gate()` therefore refuses it
regardless of Claude verification or observer corroboration. The panel does not join wave scheduling,
reviewer score math, or any merge/deploy gate.

## 1. Context package (coordinator → chaperone)

At residency spawn (Step B1's wave scheduling), the coordinator hands the chaperone a context
package carrying:

A package may contain one unit or a homogeneous same-engine batch. Batching amortizes the
chaperone's context load only: it never merges unit manifests or turns batch success into per-unit
`verified_by_claude=True`; it never lets the engine touch the working tree. Mixed selectors, mixed
intents, incompatible sandbox/write handling, or incompatible test-oracle handling stay as separate
one-unit packages.

| Field | Source | Purpose |
|---|---|---|
| `unit_ids` | the plan's Implementation Units assigned to this segment | scope — same as any resident worker (SKILL.md Step B1) |
| `unit_contexts[]` | one record per unit id | per-unit scope that stays distinct inside a batch: `unit_id`, `selector`, `intent`, `verifiability`, `write_set`, `test_oracle`, and `manifest_identity` |
| `plan_pointer` | plan doc path | authoritative spec, read once, not re-transcribed |
| `selector` | the unit's `engine` or `capability` field (`execution_spec.py` `Unit.engine`/`Unit.capability`, mutually exclusive — `_validate_external_engine_selector`, `execution_spec.py:241-265`) | what `engine_resolver.resolve()` is called with |
| `intent` | the unit's `engine_intent` (`offload` / `second-opinion` / `divergence`, defaults `offload`) | selects the exhaustive typed reconciliation recipe and is carried for provenance/audit; the operational effect (chaperone tier) was already locked at plan time via the tier-table recommendation (`plugins/saga/skills/plan/SKILL.md`) |
| `verifiability` | the unit's `verifiability` (`test-gated` / `unverifiable`; absent means `unverifiable`) | selects ratify-only vs full-review chaperoning; batch members must match |
| `test_oracle` | the unit's declared tests, output contract, or plan verification note | what a `test-gated` unit asks the chaperone to ratify before accepting the external evidence |
| `plan_time_resolution_preview` | the tier-table recommendation row the operator approved (U2): `{"engine_id": "<key>", "variant": "<key>"}` for a capability-routed unit; absent/null for an explicit-engine unit (R26 makes substitution unreachable there — see §4) | the baseline §4 compares the run-time resolution against |
| `write_set` | the unit's declared `files` (Create/Modify) | scopes what the **chaperone's own apply step** may touch — not the engine's; the wrapper envelope's own `write_set` stays `[]` at v1 (R23) regardless of this value |
| `chaperone` | `chaperone_economics.ChaperoneDecision.to_provenance()` when batching/sampling applies | advisory provenance: batch id, review mode, sampled units, full-review units, tier escalation recommendation, and cache hit/miss |

No other context crosses the boundary. The chaperone does not forward its own system prompt,
prior conversation, or other units' state to the engine — only what §2 assembles.

Sampling is advisory cost control, not acceptance. A sampled defect escalates every unsampled unit in
the same batch to `full-review`; no unit may inherit a sampled sibling's passing result.

## 2. Resolve

The chaperone calls the resolver in `dispatch` mode with `role_kind="worker"`:

```python
resolution = engine_resolver.resolve(
    {"role_kind": "worker", "engine": selector} | {"role_kind": "worker", "capability": selector},
    mode="dispatch",
    registry=registry,
)
```

(`role_kind` rides in the request dict; `engine`/`capability` are mutually exclusive keys —
`engine_resolver.py:79`, `MODES = ("advisory", "dispatch")` at `:17`, `ROLE_KINDS` at `:18`.)
`role_kind="worker"` puts the chaperone in `FALLBACK_ROLE_KINDS` (`engine_resolver.py:19`), which
governs how the resolver responds when nothing usable is available:

- **Capability selector, no engine fits** (unsupported capability or a fitness rejection) →
  the resolver itself returns a Claude-fallback `Resolution` (`engine_id="claude"`, `halt=None`,
  `fallback="<reason>"` — `engine_resolver.py:272-288`). The chaperone does the unit itself;
  no dispatch happens. Disposition = `fell-back-to-claude` (§5).
- **Capability selector, entry found but the engine's CLI/config preflight fails** → same
  Claude-fallback path (`_resolve_entry`'s `explicit_engine or role_kind in HALT_ROLE_KINDS`
  check is false for a capability-routed worker, so it falls back rather than halting).
- **Context-window overflow for the resolved variant** → the resolver halts regardless of
  selector kind or role (`_context_window_halt`, R25) — this is not R26; see §4's halt path.
- **Explicit-engine selector, that engine unavailable** → **halt**, never fallback (R26 —
  `explicit_engine=True` forces the halt branch in `_resolve_entry` for every role kind). This is
  the only halt condition specific to naming an engine by key.

## 3. Dispatch — protocol forwarded verbatim (R11)

When `resolution.halt` is `None` and the engine is not `"claude"`, the chaperone builds the
wrapper invocation from the resolution's own payload — never re-authored or paraphrased:

```python
invocation = (
    engine_dispatch.build_codex_invocation(resolution, sandbox=unit_sandbox)
    if resolution.engine_id == "codex"
    else engine_dispatch.build_agy_envelope(
        resolution, model=model, sandbox=unit_sandbox, write_set=unit_files
    )
)
evidence = engine_dispatch.dispatch(
    resolution, runner=runner, model=model, sandbox=unit_sandbox, write_set=unit_files,
    execution_id=f"{worker_id}-{unit_id}", intent=unit_intent,
    expected_identity=(
        f"{plan_time_resolution_preview['engine_id']}/{plan_time_resolution_preview['variant']}"
        if plan_time_resolution_preview is not None
        else None
    ),
)
```

`expected_identity` (`engine_dispatch.py:165`) is the §1 plan-time preview, forwarded verbatim
so `dispatch()` stamps it onto the evidence's provenance. This is what lets the shared manifest
builder derive the substitution disposition itself in §5 — the chaperone never computes or
constructs that disposition by hand.

`unit_sandbox` is the unit's declared `sandbox` envelope (or `None`) and `unit_files` its declared
`files` list. Both builders assert byte-identical payload preservation (`_assert_payload_preserved`)
— `resolution.payload` is the resolved prompting protocol plus context, assembled once by the
resolver (`_assemble_payload`, `engine_resolver.py`) and never touched again. The `runner` that
actually invokes the engine is the existing containment wrapper, not a new one this contract adds:

- **agy** → `/agy:delegate` (or the `agy:agy-coder` / `agy:agy-reviewer` Bash-only bridge agents),
  which calls `agy_delegate.py`. Never invoke raw `agy`. **Default / read-only units keep the
  evidence-only ceiling** — `mode: "no-write"`, `write_set: []`, `apply_policy: "preserve-patch"`.
  A **`sandboxed-mutate`** unit (read-write × owned-worktree) lifts that ceiling by WIRING agy's
  existing clone + gated patch import (#287 U5): `mode: "patch-only"`, `write_set` = the unit's
  declared files, `apply_policy: "preserve-patch"` (`build_agy_envelope`). No new isolation is
  built — the remotes-stripped disposable clone agy already sets up is the workspace, and the
  `git diff <BASE_SHA>` harvest imports only the declared write_set (R23 gate stays upstream).
- **codex** → `codex:delegate`, `sandbox: "read-only"` (`build_codex_invocation`). codex has
  **no write adapter**: a `sandboxed-mutate` unit routed to codex HALTS with a visible
  `DispatchError` rather than silently running read-only and dropping the write (#287 KTD4/R6).

The leaf's declared sandbox is recorded on the provenance manifest as **pre-hoc attribution**
(`build_dispatch_manifest(..., sandbox=<profile>)`, #287 R7) — an optional, absent-tolerant
`attribution.sandbox` string that does not bump `saga.manifest.v1`.

`dispatch()` short-circuits to a halted `AdvisoryEvidence` without invoking the runner at all when
`resolution.halt is not None` (`engine_dispatch.py:79-90`) — the halt path in §4 never reaches the
wrapper.

## 4. Substitution detection (KTD4)

Compare the resolution the chaperone actually got against the plan-time preview from §1, **only
for capability-routed units** (an explicit-engine unit that resolves to anything other than the
named engine is a contradiction the resolver cannot produce — it halts instead, R26):

```python
substituted = (
    plan_time_resolution_preview is not None
    and resolution.halt is None
    and resolution.engine_id != "claude"
    and (resolution.engine_id, resolution.variant)
        != (plan_time_resolution_preview["engine_id"], plan_time_resolution_preview["variant"])
)
```

A `True` result changes the disposition written in §5 from `ran-as-requested` to
`substituted-engine` — the run-time capability router resolved a different engine/variant than
the one the operator approved in the tier table. This is the only reachable substitution path: the
shared builder derives it itself from `expected_identity` (§3/§5), it is never hand-constructed
here.

## 5. Verify → reconcile → gate → apply → test → manifest

1. **Verify.** The chaperone reads `evidence.evidence` (the engine's returned patch/output) and
   reviews it itself — never self-attested. Only after review does the chaperone set
   `evidence.verified_by_claude = True`; this is the bit `satisfy_gate()` requires (§ "Never a
   gatekeeper"). If review rejects an otherwise dispatched offload, the chaperone calls
   `engine_dispatch.reject_offload(evidence, rejection_note)` with its normalized, non-empty
   reason. It does not apply the rejected patch.
2. **Build and record the normal reconciliation.** This step is mandatory for accepted `offload`,
   `second-opinion`, and `divergence` units. `dispatch()` in §3 receives the unit's stable
   `execution_id` and canonical `intent`; the returned immutable evidence carries its full-artifact
   SHA-256 digest plus ordered typed source findings and IDs. For non-empty `second-opinion` and
   `divergence`, the runner must have supplied the ordered findings envelope. Only an unstructured
   `offload` may carry the synthesized opaque singleton. Claude builds one typed
   `ReconciliationItem` per source in source order (including explicit dropped/overridden outcomes),
   then builds a ready result with those exact bindings. Typed multi-finding evidence therefore needs
   exact multi-item coverage. The caller records one transition per helper call, in order, and passes
   that same result object to the gate:
   ```python
   result = reconcile.build_result(
       reconciliation_id=reconciliation_id,
       execution_id=evidence.execution_id,
       intent=evidence.intent,
       adjudicator_id="claude/<variant>",
       evidence_digest=evidence.evidence_digest,
       source_finding_ids=evidence.source_finding_ids,
       items=typed_items,
   )
   reconcile.append_reconciliation_fact(
       ledger, result, action="reconcile", subplot_id=subplot_id, at=reconciled_at,
   )
   engine_dispatch.satisfy_gate(
       evidence, manifest, reconciliation=result, ledger=ledger, store=store,
   )
   ```
   `manifest` is passed whenever it exists, and the `ledger`/`store` liveness pair is passed
   together.
3. **Apply.** Only after the gate accepts the bound result does the chaperone apply the reviewed patch
   — the engine never touches the working
   tree (KTD6/R23). The chaperone **owns the commit**, but the commit itself happens only after
   Test (step 4) and the empty-delivery check (step 4a) pass — apply and commit are distinct
   steps of the same chaperone-owned sequence. This is the same file-edit scope every
   team-execution worker already has (`worker-manifest.md` "grants no privilege... workers keep
   today's file-edit scope"). After the reviewed patch is applied, record the matching transition:
   ```python
   reconcile.append_reconciliation_fact(
       ledger, result, action="apply", subplot_id=subplot_id, at=applied_at,
   )
   ```
   Each append is independently lock-atomic, and `apply` requires exactly one matching prior
   `reconcile`. The fact records the chaperone-controlled apply event; it never claims that the
   external engine wrote the worktree.
4. **Test.** The chaperone runs its unit's tests, same as any resident worker at segment exit.
4a. **Empty-delivery check (R7, KTD6).** Between Test and the chaperone-owned commit, the
   chaperone runs `check_empty_delivery.check_empty_delivery()` (or its CLI,
   `plugins/saga/scripts/check_empty_delivery.py --claims-delivery`) against the working tree. A
   unit whose evidence claims delivery but changed zero paths gets a HALT verdict — the chaperone
   surfaces that HALT to the coordinator exactly like any other blocked worker and never reaches
   the commit step below. A proceed verdict authorizes continuing to Apply's commit; the helper
   itself never commits and mints no new auto-commit machinery (none exists in this repo — `/optimize`
   deliberately shed its own). This is a distinct axis from `manifest_store.py`'s `missing-output`
   trip (`manifest_store.py:249-363`), which checks the returned-value axis, not file delivery.
5. **Manifest and rejected-offload evidence.** One path, for every disposition —
   `ran-as-requested`, `fell-back-to-claude`, `substituted-engine`, and `rejected-offload` alike.
   The chaperone never branches into a second manifest constructor and never constructs
   `provenance_manifest.Manifest` directly; it always calls the existing builder, forwarding the
   same `expected_identity` it passed to `dispatch()` in §3:
   ```python
   engine_dispatch.record_dispatch_manifest(
       store, evidence,
       execution_id=f"{worker_id}-{unit_id}", saga_ref=saga_ref, created_at=created_at,
       effort=resolution.effort, protocol="\n".join(resolution.protocol),
   )
   ```
   `build_dispatch_manifest` derives the disposition from the
   evidence alone: `evidence.halt is not None` → `FELL_BACK_TO_CLAUDE` (carrying the
   halt/downgrade note as `disposition_note`); otherwise, when the evidence's provenance carries
   an `expected_identity` that differs from `f"{evidence.engine_id}/{evidence.variant}"` →
   `SUBSTITUTED_ENGINE` (`_substitution_note`, `engine_dispatch.py:456-470`, naming both the
   previewed and the resolved engine/variant); receipt/proof integrity dispositions retain their
   existing precedence; then a `rejected_offload_note` stamped by `reject_offload()` →
   `REJECTED_OFFLOAD`; otherwise `RAN_AS_REQUESTED`. Attribution is always
   `kind=EXTERNAL_ENGINE`, `identity=f"{evidence.engine_id}/{evidence.variant}"` — the same
   identity format the builder always emits. There is no second, hand-built manifest path;
   `record_dispatch_manifest` is the only manifest-construction call this contract documents.

   For `REJECTED_OFFLOAD`, the chaperone calls
   `engine_dispatch.rejected_offload_reconciliation(..., intent=evidence.intent,
   evidence=evidence)`, then passes
   `reconcile.reviewer_validator_evidence(result)` to both the reviewer and validator evidence
   inputs. Passing the evidence retains the unit's canonical intent, immutable digest, and source
   IDs; the result contains one typed `dropped` item per source whose rationale is the manifest's
   concise normalized rejection summary. The summary is evidence-bound, single-line, and capped at
   1024 UTF-8 bytes; it is never a copy of unbounded engine output. Final manifest JSON is written
   atomically and forced to mode `0600`. This recovers the failed quality check as review signal
   without giving it authority or writing raw engine output to the ledger: `satisfy_gate()` refuses
   `REJECTED_OFFLOAD` even when Claude verification and observer corroboration are both present, and
   panel/advisory-reviewer restrictions remain unchanged.

   The fail-loud discriminator this feeds (#392): a substituted run is not a passing external
   result. `satisfy_gate()` (`engine_dispatch.py:664`) refuses a manifest whose disposition is
   `SUBSTITUTED_ENGINE` outright — the chaperone must surface that refusal as a HALT to the
   coordinator, never paper over it or let the run count toward the unit's gate as if it were
   `RAN_AS_REQUESTED`.

   A halted unit (§2's R26/R25 halt paths) never reaches this step — nothing ran, so there is
   nothing to manifest. The chaperone surfaces `resolution.halt` to the coordinator and stops on
   its assigned units, exactly like any other blocked worker.

Tier and `claim_provenance` guidance for the resulting manifest are unchanged from
`worker-manifest.md`'s existing "Tier" and "Claim provenance" sections — this contract only adds
the `kind=external-engine` attribution leg those sections already reserved space for.

## 5a. Runtime tripwire contract (#384) — the chaperone's obligations, not new team-execution code

The mechanics in §§1-5 above are now backed by always-on runtime enforcement living in
`saga`/`fleet-core` (`{#external-engine-chaperone-dispatch}` (#318)). This is documentation of
that existing contract, not a change to team-execution's own code — no chaperone behavior in this
plugin changes; the enforcement already runs underneath every dispatch a chaperone makes through
`engine_dispatch.dispatch()`.

1. **Arm before you dispatch.** Before invoking an external engine, the chaperone (via
   `engine_dispatch.dispatch(..., gated=True, session_id=..., workspace_root=...)`) arms the
   delegation-liveness marker through the `delegation_state` CLI/API
   (`plugins/fleet-core/scripts/fleet_commons/delegation_state.py`) for the duration of the
   engine run, and disarms it in a `finally` once the run completes — win, lose, or raise. A
   chaperone that calls `dispatch()` with `gated=True` gets this for free; there is no separate
   arm/disarm call for the chaperone to make itself.
2. **Two-signal acceptance, not one.** While armed, a `Write`/`Edit`/`MultiEdit`/`NotebookEdit`
   tool call with no evidenced genuine engine invocation is blocked at the tool-call boundary
   (PreToolUse tripwire, exit 2) and, at turn end, the transcript is classified against the
   engine's bundle evidence (Stop/SubagentStop audit). A dispatched unit is accepted only when
   **both** signals agree: Claude's own self-report AND independent observer corroboration
   (schema-valid receipt + bundle launch flag `true`). Neither signal adjudicates alone — the
   `verified_by_claude` bit that satisfied gates before #384 is no longer sufficient by itself
   for a gated dispatch.
3. **Disagreement re-queues once, then HALTs.** When the two signals diverge, the chaperone does
   not get to choose which one to believe. `dispatch()` returns a re-queue disposition on the
   first divergence for a given session; the chaperone may re-dispatch that unit at most once.
   A second consecutive divergence raises a hard `DispatchError` and the chaperone HALTs on that
   unit exactly as it does for any other blocked-worker halt path (§2's halt paths) — it does not
   retry further, silently fall back, or manifest the unit as accepted.
4. **`DELEGATION_INTEGRITY` names the failure.** Whenever a HALT originates from this two-signal
   disagreement rather than an ordinary substitution/fallback, the halt reason surfaced to the
   coordinator names it explicitly as `DELEGATION_INTEGRITY` (the same disposition name
   `provenance_manifest.Disposition.DELEGATION_INTEGRITY` records on the manifest). A chaperone
   relaying a halt upward must not paraphrase this away — the coordinator and any operator
   reading the halt need to see the literal `DELEGATION_INTEGRITY` string to distinguish "the two
   signals disagreed" from an ordinary engine failure or substitution.

No behavior in team-execution's own dispatch, consensus, or validator-cap code changes as a
result of this section — it is documentation of mechanics saga/fleet-core already enforce
underneath every chaperone dispatch call.

## 5b. Output-attestation and bridge-run liveness contract (#388)

The chaperone continues to call `engine_dispatch.record_dispatch_manifest(...)`; it must not build
`provenance_manifest.Manifest` directly. The builder now records `bridge_run_key` when a bridge
receipt provides it and may classify a successful-looking run as `proof-integrity` when the
registered bridge signature is missing output attestation, nonzero external-token proof, or the
producer/consumer liveness join fails.

A wired chaperone path requires both halves to name the same bridge run key: the producer side
launches and receipts the run, and the consumer side manifests that same run. A launched-but-
unconsumed run and a consumed-but-unlaunched result are both proof-integrity failures. As with
`substituted-engine`, the chaperone must surface this as HALT evidence to the coordinator; it must
not count the run as `ran-as-requested` or paper over the failure with a Claude-only answer.
