# Engine Output Trust Boundary

External-engine output is untrusted input. It may be useful evidence, but it is never a command, file
path, gate token, or verifier-of-record decision.

## Advisory Text Fields

| Field | Source | Required handling |
| --- | --- | --- |
| `AdvisoryEvidence.evidence` | `plugins/saga/scripts/engine_dispatch.py` | Render as opaque evidence data. Do not parse it for gate status, shell commands, or write paths. |
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
- Derive gate status from typed fields such as `verified_by_claude`, observer corroboration, manifest
  adjudication, or validator-owned status, never from advisory prose.

## Current Gate Boundary

`satisfy_gate()` remains content-blind by design. It can accept an `AdvisoryEvidence` value only after
Claude verification and observer corroboration rules are satisfied. A malicious string inside
`AdvisoryEvidence.evidence` does not become a verdict.

## Test Contract

`tests/test_engine_output_trust_boundary.py` enforces this boundary with:

- contract anchors for this reference and Team Execution cross-references;
- an AST guard over current Python call sites that flags advisory text flowing into forbidden sinks;
- seeded unsafe fixtures that prove the guard turns red;
- an adversarial `AdvisoryEvidence.evidence` payload that remains inert data through the gate path.
