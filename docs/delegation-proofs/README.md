# Delegation-proof artifacts

Behavioral proof that a delegated **bridge** run (an external-engine teammate doing real work on
Claude's behalf — today only `agy`) actually ran and produced attributable output. Consumed by
the delegation-integrity CI gate `scripts/check_delegation_proof.py` (issue #457). This is the
*behavioral* layer on top of the *structural* marketplace-drift guard: the drift guard checks that
a plugin directory and its marketplace entry stay in sync; this checks that a bridge plugin's
version bump is backed by proof the bridge itself was exercised.

## Why this exists

`docs/engineering-journal/LEARNINGS.md` (`#agy-delegate-silent-claude-fallback`) documents a
repeated failure mode: a run believed to be genuine `agy` delegation made **zero `agy` calls** —
the spawned teammate inherited Claude's full toolset and just did the work itself, while the run
reported green. The only reliable discriminator was grepping the transcript for an actual
`agy --model` Bash call. The *name* of the spawn path is not a trustworthy signal. This gate
operationalizes that transcript-grep discriminator (per-plugin regex in
`marketplace/bridge_plugins.json`).

## Layout

```
docs/delegation-proofs/
├── README.md                 # this file
├── <plugin>/*.json           # real proof artifacts, one per delegated run (going forward)
└── examples/                 # illustrative, non-secret example(s) documenting the schema
```

## `delegation-proof.v1` schema

A proof artifact is a JSON object with these required fields:

| field                 | meaning                                                                       |
| --------------------- | ----------------------------------------------------------------------------- |
| `schema`              | must be `"delegation-proof.v1"`                                               |
| `plugin`              | bridge plugin name, must be registered in `marketplace/bridge_plugins.json`   |
| `version`             | the plugin version this run attests (must match the bumped marketplace version)|
| `run_id`              | unique identifier for the delegated run                                        |
| `bridge_command`      | the external-tool command string — must match the plugin's discriminator regex |
| `external_tool_calls` | non-empty list of external-tool calls (proves real work, not a silent no-op)   |
| `actor`               | non-empty traceable actor token for writes (proves attribution, not an orphan) |

Optional but recommended (they enable the proof-chain check):

| field               | meaning                                                             |
| ------------------- | ------------------------------------------------------------------- |
| `transcript`        | path (relative to this dir or the proof file) to the run transcript |
| `transcript_sha256` | sha256 of the transcript bytes — recomputed and compared by the gate |

A proof **verifies** only if: the schema and all required fields are present; `bridge_command`
matches the plugin discriminator; `external_tool_calls` is non-empty; `actor` is non-empty; and,
when the attested transcript file is reachable, its sha256 matches `transcript_sha256`.

## The two guards

- **Version-bump gate** (`--mode version-gate`, per-PR): a bridge plugin's `marketplace.json`
  version change requires a verifying proof for the new version, or CI fails.
- **Fleet sweep** (`--mode fleet-sweep`, continuous): classifies every recorded proof/transcript
  against the failure taxonomy — silent no-op, unrecorded fallback, untokened orphan write, broken
  proof chain — and fails on any finding.

See `docs/engineering-journal/DECISIONS.md` (`{#delegation-proof-schema-457}`) for the schema
rationale and rejected alternatives.
