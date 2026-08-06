# External-engine dispatch contract

How a resolved `{engine, effort, invocation, protocol, payload}` (from `engine_resolver.resolve`) reaches an
external engine and comes back as evidence Claude verifies. This reference governs the *policy*; the
mechanism lives in `plugins/saga/scripts/engine_dispatch.py`.

The rule that governs everything here: **Claude is verifier-of-record (R13). An external engine never
holds a gated verdict.** Dispatch produces *advisory evidence*, never a decision.

## The three dispatch paths

The adapter dispatches to the wrapper each engine already owns — it does not re-implement containment.

- **Codex** (`resolution.engine_id == "codex"`) → `codex:delegate`. The invocation carries
  `sandbox: read-only` (R23), the registry's explicit `model` and `effort`, and `task` set to
  `resolution.payload` **byte-for-byte** — the assembled
  protocol + context is forwarded verbatim, never paraphrased or shell-interpolated (R9/R11/AE5).
  Its canonical registry identity is `<model>-<effort>` (for example, `gpt-5.6-sol-high`), so the
  invocation payload and bridge receipt can be compared directly.
  `advisory-reviewer` and `panel` dispatches additionally carry `role: reviewer`; ordinary workers omit
  the field and retain their existing invocation bytes.
- **agy** (`resolution.engine_id == "agy"`) → `agy:delegate`. The invocation is an
  `agy.delegation.v1` envelope with `mode: no-write` (R23), `task` = `resolution.payload`, and `model`
  set to the registry entry's **verbatim canonical string** (e.g. `Gemini 3.1 Pro (High)`), forwarded
  byte-for-byte because agy's `--model` is passed through unmodified. Worker/generator envelopes retain
  `role: coder`; `advisory-reviewer` and `panel` use `role: reviewer` under the same no-write ceiling.
- **Generic HTTP** (`transport == "http"`) → `engine-bridge-http`. The invocation carries the
  registry row's base URL, model, and bearer environment-variable name into the one generic
  OpenAI-compatible Chat Completions bridge. Provider-specific HTTP branches are forbidden; use the
  [provider onboarding guide](https://github.com/infiquetra/infiquetra-claude-plugins/blob/main/docs/adding-a-provider.md)
  to add a probationary row.

All paths are **evidence-only by default** (R23): the engine returns proposed output; it does not
mutate the working tree. File-mutating external work is deferred until the ideation-R14 sandbox
profile exists — until then an external worker asked to change files returns the proposed change as
evidence, not an edit (AE7).

## Direct delegation versus registry dispatch

The direct `/codex:delegate` command accepts an envelope with omitted `model` and `effort`; the
Codex CLI then uses the user's local `~/.codex/config.toml` default. Saga registry dispatch is a
different contract: the resolved Codex row must carry non-empty `invocation.model` and
`invocation.effort`, and dispatch halts before execution if either is missing. This prevents a
capability route from silently changing model identity between the plan, CLI invocation, receipt,
and Saga evidence.

## Trust standing and promotion

Every row has an authored `trust_tier` of `probation` or `advisory`. A probationary row can serve
`worker` and `generator` offload, but advisory capability selection skips it, explicit
`advisory-reviewer` resolution halts, and composing roles reject it. This check is role-aware and is
independent of transport.

`engine_promotion.py <engine>/<variant>` verifies the run-fact ledger and assesses the five most
recent exact-variant engine facts. Eligibility requires five successful, proof-integrity-valid,
distinct bridge runs. The command is read-only; changing standing remains an operator-reviewed
registry pull request, and advisory standing still does not grant gate authority.

## The advisory-evidence result type (R13 enforcement)

`dispatch()` returns an `AdvisoryEvidence` — a value that carries `evidence`, `provenance`, immutable
dispatch `execution_id`, canonical `intent`, and resolver-validated `role_kind`, a SHA-256 digest of the
full evidence artifact, an ordered tuple of typed `SourceFinding` metadata, its ordered IDs, a
`verified_by_claude` flag (default `False`), and an optional `halt`. It carries **no gated-verdict field**.

A runner's optional `findings` field is an ordered array of `{"content": <string>}` objects.
Dispatch retains each bounded content string in-memory with immutable
`external-finding:<ordinal>:<sha256(content)>` metadata; it never persists that prose to a manifest
or run fact. For `second-opinion` and `divergence`, non-empty `output` must equal
`reconcile.render_source_findings(findings)` exactly. That canonical ordered envelope prevents the
runner from hiding output outside the findings Claude must adjudicate. Only `offload` may omit the
envelope; a non-empty unstructured offload then becomes one explicit
`opaque-artifact:0:<sha256(evidence)>` source. Typed offloads remain separate ordered sources. The
runner envelope is capped at 256 findings and 256 KiB cumulative UTF-8 content before construction.

The canonical guard call is:

```python
satisfy_gate(
    evidence,
    adjudicated.manifest,
    reconciliation=result,
    ledger=ledger,
    store=store,
    audit_store_root=audit_store_root,
    manifest_close_receipt=adjudicated.close_receipt,
)
```

This call happens only after the receipt-chained claim and adjudication transitions have produced
`adjudicated.close_receipt`, and before any patch is applied. Since the fleet broker's retirement
(#677/U3) the chain is self-authenticating: dispatch mints a `saga.close-receipt.v1` receipt onto
`provenance["dispatch_close"]`, each manifest transition re-validates its predecessor by digest
re-derivation and mints its own, and the gate re-validates the final receipt and its output/write
intent bindings. `manifest` is optional only when no
manifest exists; a caller that has one must pass it. `ledger` and
`store` are an optional pair for bridge-liveness checking: pass both or neither. The same exact
in-memory `result` that Claude built and that the worker recorded is passed as `reconciliation`.

Before any older authority check, `satisfy_gate` requires that result to be ready and unused, and
binds it exactly to the dispatch: the evidence has a non-empty `execution_id`; result and evidence
match on `execution_id`, canonical `intent`, canonical recipe, evidence digest, and the ordered source
finding IDs; every source is accounted for by a typed item in that same order; and non-empty evidence
has at least one typed item. Multi-finding evidence cannot pass through a singleton reconciliation.
A supplied manifest must name that same execution. Replaying an already-satisfied evidence/result
pair is refused.

Those binding checks do not replace the standing refusals. The function still rejects panel and
advisory-reviewer roles, rejected-offload evidence, missing Claude verification, missing observer
corroboration, substituted/rejected/proof-integrity manifests, proof-integrity failures, bridge-
liveness contradictions, and producer-claimed-only manifest claims. External evidence therefore
cannot satisfy a gated return until a distinct Claude adjudication produces a bound typed result and
all existing authority checks pass. This is R13 made structural rather than merely asserted.

## Failure modes → halt + provenance

The runner (the thing that actually invokes the wrapper) reports a `status`. Every non-`ok` status —
`timeout`, `no-output`, `error`, `malformed`, `clone-failed` (the statuses the wrappers actually
return, cf. `plugins/agy/scripts/agy_delegate.py`) — produces an `AdvisoryEvidence` with `halt` set and
a one-line downgrade/provenance note (R24), and **never** a gated verdict. A `resolution` that already
carries a `halt` (an unavailable named engine, an unavailable panel member, or a context-window
overflow from the resolver) short-circuits: `dispatch()` returns that halt without invoking the runner.

## Offload economics preview vs dispatch stop

`plugins/saga/scripts/engine_offer.py` may include `cost_delta_preview` on an advisory `offload` offer when
the caller provides complete economics estimates. That preview is operator-facing context only: it must not
be treated as authorization to spend or as a completion gate.

`dispatch()` remains the hard enforcement point. Metered offload routes require enough economics metadata to
prove both positive token savings and provider-budget headroom before runner invocation. If the break-even
or budget-ceiling checks fail, dispatch returns halted `AdvisoryEvidence` before `_build_invocation()` and
before the runner can spend provider budget. `none` and `second-opinion` offers never attach offload savings
claims.

## Provenance and downgrade notes (R24)

Any fallback or substitution emits a visible one-line note (`downgrade_note(engine, reason)`), shaped
like the existing `orchestration_downgrade` record (`plugins/saga/references/saga-spec.md:121-125`), so
a later `/retro` or `/optimize` pass — and the operator — can see the run went degraded and why.
Degradation is durable, never silent.

## Override semantics (R20)

- **Inline / interactive dispatch** — the operator can override the resolver's selection *before*
  dispatch.
- **Autonomous cc-workflows dispatch** — the adapter acts on the standing registry configuration (which
  is itself the operator's authored choice) and surfaces its selection *post-hoc* in the result rather
  than blocking to wait for an override.

## Backends

Inline and cc-workflows dispatch use the same adapter. Team Execution routes an external-engine unit
through a resident Claude chaperone using the context-package contract in
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`. The engine still
never joins residency or owns a gate; the chaperone dispatches, reconciles, calls the structural gate,
applies as sole committer, tests, and writes the manifest.

## Proof-integrity attestation (#388)

Every registered receipt emitter (`codex-bridge`, `agy-delegate`, `http-bridge`) must satisfy
`plugins/saga/references/bridge-signatures.json` before a successful dispatch can become
`ran-as-requested`. A schema-valid `bridge_receipt.v1` is necessary but no longer sufficient:
the receipt must carry `receipt_emitter`, `run_id`, nonzero `external_tokens`, and an
`output_attestation.v1` record. Dispatch checks its SHA-256 and byte count against the raw runner
output; review intents first require that raw output to equal the canonical findings envelope, so the
receipt and Claude's reconciliation bind the same complete artifact.

Missing signature fields, empty required output, hash mismatch, zero external tokens, and
bridge-run liveness contradictions are classified as `proof-integrity` instead of
`ran-as-requested`. This does not grant engines verifier authority; it only prevents untrusted
or unproven bridge output from satisfying a gate. Claude remains verifier-of-record, and existing
`substituted-engine` and `delegation-integrity` dispositions keep their higher-precedence meanings.
