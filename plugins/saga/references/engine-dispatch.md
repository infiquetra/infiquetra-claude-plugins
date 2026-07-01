# External-engine dispatch contract

How a resolved `{engine, effort, protocol, payload}` (from `engine_resolver.resolve`) reaches an
external engine and comes back as evidence Claude verifies. This reference governs the *policy*; the
mechanism lives in `plugins/saga/scripts/engine_dispatch.py`.

The rule that governs everything here: **Claude is verifier-of-record (R13). An external engine never
holds a gated verdict.** Dispatch produces *advisory evidence*, never a decision.

## The two dispatch paths

The adapter dispatches to the wrapper each engine already owns — it does not re-implement containment.

- **Codex** (`resolution.engine_id == "codex"`) → `codex:codex-rescue`. The invocation carries
  `sandbox: read-only` (R23) and `task` set to `resolution.payload` **byte-for-byte** — the assembled
  protocol + context is forwarded verbatim, never paraphrased or shell-interpolated (R9/R11/AE5).
- **agy** (`resolution.engine_id == "agy"`) → `agy:delegate`. The invocation is an
  `agy.delegation.v1` envelope with `mode: no-write` (R23), `task` = `resolution.payload`, and `model`
  set to the registry entry's **verbatim canonical string** (e.g. `Gemini 3.1 Pro (High)`), forwarded
  byte-for-byte because agy's `--model` is passed through unmodified.

Both paths are **evidence-only by default** (R23): the engine returns proposed output; it does not
mutate the working tree. File-mutating external work is deferred until the ideation-R14 sandbox
profile exists — until then an external worker asked to change files returns the proposed change as
evidence, not an edit (AE7).

## The advisory-evidence result type (R13 enforcement)

`dispatch()` returns an `AdvisoryEvidence` — a value that carries `evidence`, `provenance`, a
`verified_by_claude` flag (default `False`), and an optional `halt`. It carries **no gated-verdict
field**. The structural guard is `satisfy_gate(evidence)`: it raises unless `verified_by_claude` is
`True`. So external evidence cannot satisfy a gated return until a distinct Claude verification step
has stamped it — a workflow cannot wire raw external output into a gate even by mistake. This is R13
made structural rather than merely asserted.

## Failure modes → halt + provenance

The runner (the thing that actually invokes the wrapper) reports a `status`. Every non-`ok` status —
`timeout`, `no-output`, `error`, `malformed`, `clone-failed` (the statuses the wrappers actually
return, cf. `plugins/agy/scripts/agy_delegate.py`) — produces an `AdvisoryEvidence` with `halt` set and
a one-line downgrade/provenance note (R24), and **never** a gated verdict. A `resolution` that already
carries a `halt` (an unavailable named engine, an unavailable panel member, or a context-window
overflow from the resolver) short-circuits: `dispatch()` returns that halt without invoking the runner.

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

Inline and cc-workflows dispatch are in scope: a wrapper subagent shells out to the engine's CLI.
team-execution dispatch (R10/R12) is **deferred** — it needs an external-engine worker context-package
slot that does not exist yet (`plugins/team-execution/skills/team-execution/SKILL.md`). Because external
engines are never gatekeepers (R13/R15), they are off team-execution's critical path, so this deferral
costs nothing today.
