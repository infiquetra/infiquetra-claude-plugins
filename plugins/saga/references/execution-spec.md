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
      "pilot": "",                     // a unit_id that gates the fan-out (same tier, R3)
      "verify": { "n": 3, "pass_rule": "majority" }
                                       // optional refute-N panel (KTD5); absent = no panel
    }
  ]
}
```

### Unit.verify — refute-N judge-panel (optional, KTD5)

A unit may carry an optional `verify` block that attaches a **refute-N judge-panel** over that unit's
output. When present, the emitter appends a `parallel([...])` of `n` verifier `agent()` calls (each at the
**same `{model, effort}` tier** as the parent unit — R4), followed by a pass-rule reconciliation in the
generated script:

| Field | Type | Meaning |
|---|---|---|
| `n` | integer ≥ 1 | Number of independent adversarial verifiers. Hard cap: `VERIFY_N_CAP = 7` (above the cap, `validate` hard-blocks — guards the rate-limit overcorrection). Soft warn band: `n > 5` validates but emits a stderr warning. |
| `pass_rule` | `"majority"` \| `"unanimous"` | A finding **survives** unless refuted per this rule. `majority` → ≥ ⌈N/2⌉ verifiers refute it; `unanimous` → all N must refute. |

**Defaults for `/plan` authoring (KTD3):** `n=3`, `pass_rule="majority"` — a finding survives unless ≥2 of
3 verifiers refute it. Override per unit when the operator requests a different panel size. N=3/majority is
the conservative default: enough independent skeptics to surface noise without hitting the rate-limit
overcorrection that prompted the cap.

Absent `verify` round-trips unchanged — existing specs and the `team_emitter.py` never gain a spurious key.

## Topological-layer parallelism (KTD4)

The emitter computes **topological dependency layers** (Kahn) from each unit's `depends_on` list and any
implicit pilot barrier (`pilot` → fan-out). Units whose full dependency set is satisfied by earlier layers
run together in one `parallel([...])` wave; layers are sequenced by `await`:

- **Singleton layer** → plain `const x = await agent(...)`.
- **Multi-unit layer** → `const [x, y, z] = await parallel([...])` — one wave of thunks, destructured
  back into per-unit vars so verify panels and dependents read them.

Verify panels for units in a parallel wave are emitted **after** the wave closes (so the panel reads the
result from the already-resolved var). Within a layer, units keep their declaration order for deterministic
emission. A dependency cycle among the remaining units raises a `SpecError` at emit time (fail loudly, not
silently).

The pilot implicit barrier is included in the layer computation: a fan-out unit's pilot always lands in a
strictly earlier layer than the fan-out itself, preserving the R3 gate even in a complex topology.

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

## Capability-portable degradation (R11 / U12)

Every authored plan is **capability-portable**: it carries a runnable **inline/serial
baseline** alongside the dynamic-workflow script, so it executes on ANY host — with or
without the Workflow tool. The dynamic-workflow layer (`emit_workflow_script`) applies only
on a capable host.

On an **off-host resume** the Workflow tool is re-checked and the orchestration tier
recompiles DOWN — and **only the orchestration tier**. The unit specs and per-unit
`{model, effort}` tiers are PRESERVED across the recompile; a downgrade changes only *how*
units are dispatched (serial, inline), never *which* units run or *at what tier*.

The flow has three moving parts:

1. **`lifecycle_state.recheck_orchestration_capability(...)`** — the capability probe. Given
   the resumed `orchestration_mode` and whether the Workflow tool is available, it returns a
   structured decision: `{downgraded, from, to, note, workflow_available}`. It **never errors
   and never silently runs nothing** (AE3): on a capable host `downgraded=False` and the
   authored tier is kept; off-host it returns a runnable lower tier (`team-execution`, or the
   always-runnable `inline` floor) plus a one-line `note`. An unknown stored mode floors to
   `inline` rather than raising. Tiers ladder, most-capable first:
   `cc-workflows-ultracode → team-execution → inline`.

2. **`execution_spec.recompile_for_tier(spec, mode)`** — re-emits the *same* spec for the
   (possibly downgraded) tier: `cc-workflows-ultracode` → the dynamic `.workflow.js`; any
   other tier → the inline/serial baseline (`emit_inline_baseline`). Both preserve unit specs
   and per-unit tiers; the function always returns a runnable artifact.

3. **`saga.orchestration_downgrade`** — the recorded note. The downgrade is durable, not
   silent: the one-line note from step 1 is written to the saga so a later `/retro`/`/optimize`
   pass (and the operator) can see the plan ran degraded and why.

```bash
# Re-check host capability on an off-host resume and recompile the orchestration tier.
uv run python plugins/saga/scripts/lifecycle_state.py recheck-capability \
    --orchestration-mode cc-workflows-ultracode --no-workflow
# -> {"downgraded": true, "from": "cc-workflows-ultracode", "to": "team-execution", "note": "...", ...}

# Emit the runnable inline/serial baseline (the R11 floor) from a spec.
uv run python plugins/saga/scripts/execution_spec.py baseline spec.json -o baseline.md
```

## `/plan` author-validate-emit-approve-persist flow

When the operator chooses `cc-workflows-ultracode`, `/plan` follows this five-step flow before writing the
saga tick (Phase 5.2a in `skills/plan/SKILL.md`). Emit comes BEFORE approve so the operator confirms the
actual generated script, not a description of it:

1. **Author** — derive per-unit `{model, effort}` tiers from the work-shape heuristic; write thin per-unit
   prompts (KTD2 — a thin pointer to the plan, not a prose transcription); wire `depends_on` barriers and
   optional `verify` panels. Surface the tier table for operator review.

2. **Validate (HARD BLOCK)** — run the validator. A non-zero exit means the spec is malformed; do NOT
   proceed until fixed. Common failures: `depends_on` cycle, fan-out with no `targets` (R10), pilot tier
   mismatch (R3), `verify.n` above `VERIFY_N_CAP`, two unit_ids that sanitize to the same JS var.

   ```bash
   python3 plugins/saga/scripts/execution_spec.py validate docs/plans/<name>-spec.json
   ```

3. **Emit** — write the `.workflow.js` beside the spec (`emit` re-validates, so a malformed spec fails here
   too):

   ```bash
   python3 plugins/saga/scripts/execution_spec.py emit docs/plans/<name>-spec.json \
     -o docs/plans/<name>.workflow.js
   ```

4. **Approve** — surface the now-emitted `.workflow.js` and the per-unit tier table for explicit operator
   confirmation. The operator must confirm the tier assignments and the control-flow structure; a rejection
   means revising the spec and re-running validate + emit.

5. **Persist** — write the saga tick with `--orchestration-ref` pointing at the **spec JSON** (the
   canonical artifact — the `.workflow.js` is regenerable, so the ref is the spec, not the script):

   ```bash
   python3 plugins/saga/scripts/saga.py save \
     --orchestration-mode cc-workflows-ultracode \
     --orchestration-ref docs/plans/<name>-spec.json \
     --orchestration-recommended <recommend_execution_backend() output>
   ```

The spec JSON is the durable canonical artifact; the `.workflow.js` can be regenerated at any time via
`emit`. `/work` re-emits fresh from the spec at execution time, so an intermediate re-plan that changed the
spec is automatically reflected.

## CLI

```bash
# Validate a spec (R3/R10 invariants); exit 2 + a SPEC ERROR on a violation.
uv run python plugins/saga/scripts/execution_spec.py validate spec.json

# Emit a runnable workflow script (stdout, or -o to a file).
uv run python plugins/saga/scripts/execution_spec.py emit spec.json -o out.workflow.js

# Emit the runnable inline/serial baseline (R11 floor — runs on any host).
uv run python plugins/saga/scripts/execution_spec.py baseline spec.json -o baseline.md
```
