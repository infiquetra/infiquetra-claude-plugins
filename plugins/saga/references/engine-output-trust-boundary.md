# Engine Output Trust Boundary

External-engine output is untrusted input. It may be useful evidence, but it is never a command, file
path, gate token, or verifier-of-record decision.

## Advisory Text Fields

| Field | Source | Required handling |
| --- | --- | --- |
| `AdvisoryEvidence.evidence` | `plugins/saga/scripts/engine_dispatch.py` | Render as opaque evidence data. Do not parse it for gate status, shell commands, or write paths. |
| `external_opinion.findings[].content` | `plugins/saga/scripts/second_opinion.py` and the enriched review/work artifact | Render as opaque evidence data only. It may be serialized under the selected finding, but never becomes a command, path, gate token, or Claude adjudication rationale. |
| Team Execution validator and reviewer finding text | `plugins/team-execution/skills/team-execution/references/validator-registry.md` and `validator-criteria.md` | Render as opaque finding data. Claude and required validators own gate interpretation; external text never supplies the gate token. |

## Forbidden Sinks

Advisory text must never be interpolated into these contexts verbatim:

- shell, `Bash`, `subprocess`, or `os.system` invocation arguments;
- `eval` or `exec`;
- file-write target paths or path traversal decisions;
- gate-decision tokens or status strings such as `PASS`, `hard-fail`, `blocked`, or `Done`.

## Required Handling

- Render advisory text as data in logs, Markdown, JSON, or review artifacts.
- Escape only for the target renderer when escaping is needed for display.
- Reject or refactor code that routes advisory text into a forbidden sink.
- Derive gate status from a bound, ready typed reconciliation plus `verified_by_claude`, observer
  corroboration, manifest adjudication, and validator-owned status, never from advisory prose.

## Current Gate Boundary

`satisfy_gate()` remains content-blind by design. Its canonical call is
`satisfy_gate(evidence, reconciliation=result, ...)`; the result is typed Claude adjudication, not
engine prose. Before checking authority, the gate requires a ready, non-replayed result bound to the
same dispatch `execution_id`, canonical intent and recipe, SHA-256 evidence digest, and ordered
source-finding IDs. Runner findings are immutable ordered metadata envelopes whose IDs encode ordinal
and content digest. Non-empty `second-opinion` and `divergence` evidence must supply typed findings;
only `offload` may use one opaque-artifact source when no findings envelope exists. Every source in a
multi-finding response needs one ordered typed item, so it cannot be collapsed into a singleton or
partially reconciled. A supplied manifest must name the same execution.

After binding, the existing authority checks still require Claude verification and observer
corroboration and still refuse panel/advisory-reviewer roles, rejected offloads, substituted,
rejected, or proof-integrity manifests, bridge-liveness contradictions, and producer-claimed-only
manifest claims. A malicious string inside `AdvisoryEvidence.evidence` remains inert data and never
becomes a verdict. Reconciliation structure accounts for the string; it does not interpret the string
as a gate token.

## Test Contract

`tests/test_engine_output_trust_boundary.py` enforces this boundary with:

- contract anchors for this reference and Team Execution cross-references;
- an AST guard over current Python call sites that flags advisory text flowing into forbidden sinks;
- seeded unsafe fixtures that prove the guard turns red;
- an adversarial `AdvisoryEvidence.evidence` payload that remains inert data through the bound
  reconciliation gate path.

`tests/test_saga_engine_dispatch.py` separately pins the gate contract: missing/not-ready results;
execution, intent, recipe, digest, source-ID, manifest, and empty-item mismatches; replay refusal; and
the existing Claude, observer, role, disposition, proof-integrity, liveness, and claim refusals. It
also pins typed multi-finding coverage and the offload-only opaque singleton exception.
