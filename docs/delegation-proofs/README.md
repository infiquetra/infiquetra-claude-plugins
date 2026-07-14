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
└── examples/                 # illustrative example(s) — EXCLUDED from the enforcement surface
```

`examples/` is documentation only: the gate never loads proofs or standalone transcripts from an
`examples/` subtree, so an example artifact can neither satisfy the version gate nor seed the
fleet sweep. The shipped example is additionally version-pinned to the uncollidable
`0.0.0-example`.

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

The proof chain is **required for verification** (fail-closed as of the #457 fix round — these
fields stay outside the schema's required-field list for v1 compatibility, but a proof without an
intact chain does not verify):

| field               | meaning                                                             |
| ------------------- | ------------------------------------------------------------------- |
| `transcript`        | path (relative to this dir or the proof file) to the run transcript |
| `transcript_sha256` | sha256 of the transcript bytes — recomputed and compared by the gate |

A proof **verifies** only if: the schema and all required fields are present; `bridge_command`
matches the plugin discriminator; `external_tool_calls` is non-empty; `actor` is non-empty; the
attested `transcript` resolves to a real file; and its recomputed sha256 matches
`transcript_sha256`. Every degraded chain state fails verification in **both modes**: a dangling
transcript reference, a recorded hash with no resolvable file, an attested file with no recorded
hash, and — with the distinct fleet-sweep category `unverifiable_proof` — a proof that attests no
transcript at all. A transcript-less proof therefore does **not** satisfy the version gate.

## The two guards

- **Version-bump gate** (`--mode version-gate`, per-PR): a bridge plugin's `marketplace.json`
  version change requires a verifying proof for the new version, or CI fails.
- **Fleet sweep** (`--mode fleet-sweep`, continuous): classifies every recorded proof/transcript
  against the failure taxonomy — silent no-op, unrecorded fallback, untokened orphan write, broken
  proof chain, unverifiable proof — and fails on any finding. Standalone `.jsonl` transcripts under
  this directory are swept even without a proof (the CI job passes `--transcripts-dir` explicitly,
  and the script defaults standalone discovery to the proofs directory regardless).

## Threat model — what this gate does and does not defend against

Be plain about the trust boundary: **a proof artifact and its transcript are self-attested files
in the same repository, written by the same toolchain that ran the delegation.** An intact
sha256 chain proves the proof and the transcript agree with each other — it does not prove either
one is true. The gate therefore defends against:

- **accident and drift** — a stale proof pointing at a moved/deleted transcript, a hand-edited
  transcript, a proof copied from another run;
- **silent fallback** — the #278/#279 failure class, where the run *believed* it delegated but the
  transcript records Claude doing the work (the discriminator + taxonomy catch this);
- **silent no-ops and orphan writes** — recorded runs that did no attributable external work.

It does **not** defend against an author deliberately fabricating a consistent proof + transcript
pair. That requires attestation from outside the repo (e.g. a signed run bundle from the bridge
wrapper), which is out of scope for `delegation-proof.v1`.

See `docs/engineering-journal/DECISIONS.md` (`{#delegation-proof-schema-457}`) for the schema
rationale and rejected alternatives.
