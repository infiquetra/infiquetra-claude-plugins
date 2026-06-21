# Execution-spec — one spec, two emitters (R9)

`/plan` authors **one** structured execution-spec and emits from it **either** a runnable
Claude Code workflow script **or** the team-execution markdown protocol. Saga stores only an
`orchestration_ref` pointer to the emitted artifact; it never vendors backend machinery
(R9, KTD6). The governance choice (does the verdict need to stick? — see
[`operator-choice.md`](./operator-choice.md) §3.1) selects *which emitter runs*, not the
authoring.

The spec schema and the workflow-script emitter live in
[`../scripts/execution_spec.py`](../scripts/execution_spec.py). The second emitter (the
`## Team Structure` markdown) is U11's `team_emitter.py`, fed by the same spec.

The worked reference — a hand-authored harness of exactly this shape — is the campaign's own
sibling `docs/plans/2026-06-21-saga-tiering-and-execution-campaign.workflow.js`. Authoring it
by hand validated the spec by walking it (KTD1) before this emitter automated it.

## Spec shape

```jsonc
{
  "name": "my-campaign",
  "description": "one-line workflow purpose",
  "repo": "/abs/path/to/repo",        // optional; emitted as the REPO constant
  "units": [
    {
      "unit_id": "U1",
      "label": "preflight",
      "tier": { "model": "haiku", "effort": "low" },   // per-unit {model, effort} (R2b)
      "prompt": "verify grounding facts ...",
      "returns": ["ready", "drift"],   // the structured-return contract (required keys)
      "depends_on": [],                // barrier: unit_ids that must finish first
      "escalation": "HALT on drift",   // operator note surfaced on a resumable HALT
      "fanout": false,                 // same op over many enumerated targets?
      "targets": [],                   // REQUIRED & non-empty when fanout=true (R10)
      "pilot": ""                      // a unit_id that gates the fan-out (same tier, R3)
    }
  ]
}
```

## The two authoring-time invariants (fail emit)

A mis-built spec is an invalid oracle, so the emitter **fails loudly** rather than emitting a
broken script. `ExecutionSpec.validate()` runs at emit time and raises `SpecError`:

- **R10 — enumerated fan-out targets.** A `fanout: true` unit with an empty / missing
  `targets` list fails emit. A fan-out without an explicit target list is a silent filter;
  the emitted agent additionally reconciles after the run (reports any declared target it did
  not complete — never silently dropped).
- **R3 — pilot/fan-out same tier.** A fan-out unit may name a `pilot` (run one target first
  to de-risk the fan-out). The pilot **must** be at the same `{model, effort}` tier as the
  fan-out — a mis-tiered pilot validates a different cost surface than the fan-out runs on, so
  it is an invalid oracle and fails emit.

It also rejects: an empty name / empty units, duplicate `unit_id`s, a `depends_on` / `pilot`
that does not resolve to a declared unit, a `targets` list without `fanout: true`, and any
`model` / `effort` outside the closed tier vocabulary (`opus|sonnet|haiku` × `low|medium|high`).

## Cheap-tier budget discipline (baked in)

Generated **cheap-tier** agents (haiku) carry the `workflow_structuredoutput_budget` lesson
baked into their emitted prompt as a rider: **cap output** (terse, no recaps), **mandatory
emit** (the final action MUST be the StructuredOutput call, even on partial work), **skim**
(open only the lines needed, never whole large files), and **batch** (parallel independent
tool calls). A budget-exhausted cheap agent that never emits its result is the failure this
prevents.

## CLI

```bash
# Validate a spec (R3/R10 invariants); exit 2 + a SPEC ERROR on a violation.
uv run python plugins/saga/scripts/execution_spec.py validate spec.json

# Emit a runnable workflow script (stdout, or -o to a file).
uv run python plugins/saga/scripts/execution_spec.py emit spec.json -o out.workflow.js
```
